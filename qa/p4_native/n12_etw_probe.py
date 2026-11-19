"""Probe Windows ETW session counters and capture a generated N12 fixture."""
from __future__ import annotations

import ctypes
import json
import os
import subprocess
import sys
import time
from contextlib import ExitStack, contextmanager
from ctypes import wintypes
from pathlib import Path
from threading import get_native_id
from uuid import uuid4

try:
    from .n12_trace import EvidenceValidationError, local_disposable_path
except ImportError:  # Direct execution from the QA directory.
    from n12_trace import EvidenceValidationError, local_disposable_path


class WnodeHeader(ctypes.Structure):
    _fields_ = [
        ("buffer_size", wintypes.ULONG), ("provider_id", wintypes.ULONG),
        ("historical_context", ctypes.c_ulonglong), ("timestamp", ctypes.c_longlong),
        ("guid", ctypes.c_byte * 16), ("client_context", wintypes.ULONG),
        ("flags", wintypes.ULONG),
    ]


class TraceProperties(ctypes.Structure):
    _fields_ = [("wnode", WnodeHeader)] + [(name, wintypes.ULONG) for name in (
        "buffer_size", "minimum_buffers", "maximum_buffers", "maximum_file_size",
        "log_file_mode", "flush_timer", "enable_flags", "age_limit",
        "number_of_buffers", "free_buffers", "events_lost", "buffers_written",
        "log_buffers_lost", "realtime_buffers_lost",
    )] + [
        ("logger_thread_id", wintypes.HANDLE), ("log_file_name_offset", wintypes.ULONG),
        ("logger_name_offset", wintypes.ULONG),
    ]


def stop_trace(session):
    # ControlTraceW fills the statistics when it stops and flushes this session.
    properties_size = ctypes.sizeof(TraceProperties)
    name_bytes = 1024 * ctypes.sizeof(ctypes.c_wchar)
    buffer = ctypes.create_string_buffer(properties_size + 2 * name_bytes)
    properties = TraceProperties.from_buffer(buffer)
    properties.wnode.buffer_size = len(buffer)
    properties.logger_name_offset = properties_size
    properties.log_file_name_offset = properties_size + name_bytes
    control = ctypes.WinDLL("advapi32").ControlTraceW
    control.argtypes = (ctypes.c_ulonglong, wintypes.LPCWSTR,
                        ctypes.POINTER(TraceProperties), wintypes.ULONG)
    control.restype = wintypes.ULONG
    result = control(0, session, ctypes.byref(properties), 1)  # EVENT_TRACE_CONTROL_STOP
    if result != 0:
        raise RuntimeError(f"ETW stop failed with Windows status {result}.")
    return {name: getattr(properties, name) for name in (
        "events_lost", "log_buffers_lost", "realtime_buffers_lost", "buffers_written",
    )}


def volume_device(drive):
    target = ctypes.create_unicode_buffer(4096)
    query = ctypes.WinDLL("kernel32").QueryDosDeviceW
    query.argtypes = (wintypes.LPCWSTR, wintypes.LPWSTR, wintypes.DWORD)
    query.restype = wintypes.DWORD
    if not query(drive, target, len(target)):
        raise RuntimeError("Could not resolve the fixture drive's device name.")
    return target.value


def volume_devices(logical_drive_mask=None, drive_type=None, resolve=None):
    """Map every available local logical drive to its NT device prefix."""
    if logical_drive_mask is None:
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        get_logical_drives = kernel32.GetLogicalDrives
        get_logical_drives.argtypes = ()
        get_logical_drives.restype = wintypes.DWORD
        get_drive_type = kernel32.GetDriveTypeW
        get_drive_type.argtypes = (wintypes.LPCWSTR,)
        get_drive_type.restype = wintypes.UINT
        logical_drive_mask = get_logical_drives()
        if not logical_drive_mask:
            raise RuntimeError("Could not enumerate Windows logical drives.")
        drive_type = lambda drive: get_drive_type(drive + "\\")
    if drive_type is None:
        raise ValueError("A drive-type resolver is required with an injected drive mask.")
    if resolve is None:
        resolve = volume_device

    result = {}
    for index in range(26):
        if not logical_drive_mask & (1 << index):
            continue
        drive = f"{chr(65 + index)}:"
        if drive_type(drive) not in (2, 3, 6):  # removable, fixed, RAM disk
            continue
        try:
            device = resolve(drive)
        except RuntimeError:
            continue
        if isinstance(device, str) and device.casefold().startswith("\\device\\"):
            result[drive] = device
    return result


def utc_ticks():
    # Python 3.11's Windows wall clock can lag the ETW event clock by several
    # milliseconds. Read the precise UTC FILETIME before start and after stop.
    stamp = wintypes.FILETIME()
    get_time = ctypes.WinDLL("kernel32").GetSystemTimePreciseAsFileTime
    get_time.argtypes = (ctypes.POINTER(wintypes.FILETIME),)
    get_time.restype = None
    get_time(ctypes.byref(stamp))
    return (stamp.dwHighDateTime << 32 | stamp.dwLowDateTime) + 504911232000000000


def run_writer(code, *paths):
    result = subprocess.Popen(
        [sys.executable, "-B", "-c", code, *map(str, paths)],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    with result:
        try:
            if result.wait(timeout=10):
                raise RuntimeError("A generated file writer failed.")
        except subprocess.TimeoutExpired:
            result.kill()
            result.wait()
            raise
    return result.pid


def probe(root, *, calibration_only=False, thread_context=False):
    root.mkdir()
    (root / "synthetic-protected").mkdir()
    return capture_fixture(root, calibration_only=calibration_only, thread_context=thread_context)


def collector_rehearsal(root, *, rundown=False):
    from qa.p4_research import n12_app_journey as journey

    if (os.environ.get("GITHUB_RUN_ATTEMPT") != "1" or
            os.environ.get("PILOTODIN_N12_COLLECTOR_REHEARSAL_CONSENT") != "I_APPROVE_ONE_N12_COLLECTOR_REHEARSAL"):
        raise EvidenceValidationError("collector rehearsal requires separate first-run consent")
    root.mkdir()
    (root / "synthetic-protected").mkdir()
    first_record = journey.sysmon_tail(timeout=15) + 1

    def verify_fixture(fixture, fixture_start):
        manifest = {"start_utc": journey.timestamp_from_ticks(fixture_start).isoformat(),
                    "sysmon_first_record": first_record, "collector_fixture_precision": True}
        last_record = journey.verify_initial_sysmon(root, manifest, fixture)
        return {"first_record": first_record, "prelaunch_last_record": last_record}

    if rundown:
        with collect_fileio_rundown(root) as stop_wpr:
            return capture_fixture(root, calibration_only=True, thread_context=False,
                                   before_stop=stop_wpr, verify_fixture=verify_fixture)
    return capture_fixture(root, calibration_only=True, thread_context=False, verify_fixture=verify_fixture)


def verify_handle_path(stream, path):
    import msvcrt

    get_path = ctypes.WinDLL("kernel32", use_last_error=True).GetFinalPathNameByHandleW
    get_path.argtypes = (wintypes.HANDLE, wintypes.LPWSTR, wintypes.DWORD, wintypes.DWORD)
    get_path.restype = wintypes.DWORD
    name = ctypes.create_unicode_buffer(32768)
    length = get_path(msvcrt.get_osfhandle(stream.fileno()), name, len(name), 0)
    if not 0 < length < len(name) or Path(name.value.removeprefix("\\\\?\\")) != path:
        raise RuntimeError("Windows did not confirm the generated handle target.")


def write_two_handle_control(path):
    with path.open("xb", buffering=0) as first:
        verify_handle_path(first, path)
        with path.open("r+b", buffering=0) as second:
            first.close()
            verify_handle_path(second, path)
            if second.write(b"L" * 97) != 97:
                raise RuntimeError("The generated two-handle write was incomplete.")


def write_known_control(path, payload):
    with path.open("xb", buffering=0) as stream:
        verify_handle_path(stream, path)
        if stream.write(payload) != len(payload):
            raise RuntimeError("The generated known-file write was incomplete.")


def resize_known_control(path, size):
    with path.open("r+b", buffering=0) as stream:
        verify_handle_path(stream, path)
        stream.truncate(size)


def write_named_control(path):
    """Give the in-capture file a first I/O before the measured write."""
    payload = b"N" * 113
    start = utc_ticks() // 10 * 10
    with path.open("x+b", buffering=0) as stream:
        verify_handle_path(stream, path)
        if stream.write(b"seed") != 4:
            raise RuntimeError("The generated name-control seed was incomplete.")
        verify_handle_path(stream, path)
        write_start = utc_ticks() // 10 * 10
        if stream.write(payload) != len(payload):
            raise RuntimeError("The generated name-control write was incomplete.")
        write_end = utc_ticks()
        stream.seek(0)
        if stream.read() != b"seed" + payload:
            raise RuntimeError("The generated name-control payload did not match.")
    return {"path": str(path), "pid": os.getpid(), "size": len(payload),
            "start": start, "end": utc_ticks(), "prior_name_control": True, "offset": 4,
            "write_window": [write_start, write_end]}


def write_basic_info_control(path):
    import msvcrt

    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    set_time = kernel.SetFileTime
    set_time.argtypes = (wintypes.HANDLE,) + (ctypes.POINTER(wintypes.FILETIME),) * 3
    set_time.restype = wintypes.BOOL
    with path.open("xb", buffering=0) as stream:
        verify_handle_path(stream, path)
        # Set an explicit timestamp well separated from the file's creation.
        target_ns = 1_600_000_000_000_000_000
        ticks = target_ns // 100 + 116444736000000000
        timestamp = wintypes.FILETIME(ticks & 0xFFFFFFFF, ticks >> 32)
        if not set_time(msvcrt.get_osfhandle(stream.fileno()), None, None, ctypes.byref(timestamp)):
            raise RuntimeError("Windows did not apply the generated timestamp.")
        verify_handle_path(stream, path)
        if os.fstat(stream.fileno()).st_mtime_ns != target_ns:
            raise RuntimeError("The generated timestamp was not observable through the handle.")
        if stream.write(b"M" * 101) != 101:
            raise RuntimeError("The generated metadata-control write was incomplete.")


@contextmanager
def collect_fileio_rundown(root):
    wpr = Path(os.environ["SystemRoot"]) / "System32" / "wpr.exe"
    instance = ["-instancename", f"PilotODIN-{uuid4().hex}"]

    def run_wpr(*arguments):
        return subprocess.run([str(wpr), *arguments, *instance], timeout=60,
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode

    if (status := run_wpr("-start", "FileIO")) != 0:
        raise RuntimeError(f"Windows FileIO recording did not start (exit {status}).")
    stopped = False

    def stop_wpr():
        nonlocal stopped
        status = run_wpr("-stop", str(root / "rundown.etl"), "-skipPdbGen")
        if status:
            raise RuntimeError(f"Windows FileIO recording did not stop cleanly (exit {status}).")
        stopped = True
        return utc_ticks() // 10 * 10

    try:
        yield stop_wpr
    finally:
        if not stopped:
            run_wpr("-cancel")


def preopened_control(root, *, rundown=False, system_timing=False):
    root.mkdir()
    protected = root / "synthetic-protected"
    protected.mkdir()
    with ExitStack() as stack:
        controls = {}
        for label, path, size in (("protected", protected / "control.bin", 53),
                                  ("outside", root / "outside.bin", 79)):
            stream = stack.enter_context(path.open("xb", buffering=0))
            verify_handle_path(stream, path)
            controls[label] = (path, stream, b"x" * size)
        if not rundown:
            return capture_fixture(root, calibration_only=True, thread_context=True, controls=controls)
        open_comparison = comparison_stream = None
        preopened_resize = None
        if not system_timing:
            path = root / "known-resize.bin"
            stream = stack.enter_context(path.open("x+b", buffering=0))
            verify_handle_path(stream, path)
            payload = b"R" * 96
            if stream.write(payload) != len(payload):
                raise RuntimeError("The pre-opened resize seed was incomplete.")
            os.fsync(stream.fileno())
            preopened_resize = (path, stream, payload)
        if system_timing:
            comparison = protected / "untouched.bin"
            comparison_payload = b"pre-capture comparison"
            with comparison.open("xb", buffering=0) as seed:
                if seed.write(comparison_payload) != len(comparison_payload):
                    raise RuntimeError("The pre-capture comparison write was incomplete.")
                os.fsync(seed.fileno())

            def open_comparison():
                nonlocal comparison_stream
                # Open separate read-only handles while ETW is active. The
                # write controls still use their original pre-capture handles.
                for path, stream, _ in controls.values():
                    verify_handle_path(stream, path)
                    named_handle = stack.enter_context(path.open("rb", buffering=0))
                    verify_handle_path(named_handle, path)
                first = utc_ticks()
                comparison_stream = stack.enter_context(comparison.open("rb", buffering=0))
                open_window = [first, utc_ticks()]
                verify_handle_path(comparison_stream, comparison)
                first = utc_ticks()
                payload = comparison_stream.read(len(comparison_payload))
                read_window = [first, utc_ticks()]
                if payload != comparison_payload:
                    raise RuntimeError("The comparison payload was incorrect at capture start.")
                return {"path": str(comparison), "size": len(payload),
                        "open_window": open_window, "read_window": read_window}
        # Keep the control handles open through the stop-time rundown.
        with collect_fileio_rundown(root) as stop_wpr:
            capture = capture_fixture(root, calibration_only=True, thread_context=True,
                                      controls=controls, before_stop=stop_wpr,
                                      open_comparison=open_comparison, preopened_resize=preopened_resize)
            if comparison_stream is not None:
                for path, stream, payload in controls.values():
                    verify_handle_path(stream, path)
                    with path.open("rb", buffering=0) as reader:
                        if reader.read() != payload:
                            raise RuntimeError("The generated pre-opened write payload did not match.")
                comparison_stream.seek(0)
                if comparison_stream.read() != comparison_payload:
                    raise RuntimeError("The untouched comparison payload changed.")
            return capture


def capture_fixture(root, *, calibration_only, thread_context, controls=None, before_stop=None,
                    open_comparison=None, verify_fixture=None, preopened_resize=None, protected_restore=None):
    session = f"PilotODIN-N12-{uuid4().hex}"
    etl = root / "fixture.etl"
    source, destination = root / "source" / "move.bin", root / "destination" / "move.bin"
    if not calibration_only:
        source.parent.mkdir()
        destination.parent.mkdir()
        source.write_bytes(b"cross-directory marker")
    protected = root / "synthetic-protected"
    marker = protected / "transient.bin"
    resize_path = None
    if controls and before_stop is None:
        resize_path = root / "known-resize.bin"
        resize_payload = b"R" * 96
        resize_target_size = 37
        resize_path.write_bytes(resize_payload)
        resize_before_size = resize_path.stat().st_size
        if resize_before_size != len(resize_payload):
            raise RuntimeError("The generated resize seed had the wrong length.")
    providers = root / "providers.txt"
    providers.write_text(
        f"Microsoft-Windows-Kernel-File {'0x1ff0' if open_comparison is not None else '0x1ef0'} 4\n"
        f"Microsoft-Windows-Kernel-Process {'0x30' if thread_context else '0x10'} 4\n",
        encoding="ascii",
    )
    # Names, file I/O, completion, creation, writes, and delete/rename paths.
    logman = [str(Path(os.environ["SystemRoot"]) / "System32" / "logman.exe")]
    capture_start = utc_ticks() // 10 * 10
    started = subprocess.run(
        [*logman, "create", "trace", session, "-pf", str(providers),
         "-o", str(etl), "-max", "128", "-bs", "64", "-nb", "16", "128", "-ets"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=20, check=False,
    )
    if started.returncode:
        raise RuntimeError(f"ETW start failed with exit code {started.returncode}.")
    rundown_start_ticks = rundown_stop_ticks = None
    lifetime_control = None
    basic_info_control = named_control = None
    known_write = None
    resize_control = None
    try:
        comparison = open_comparison() if open_comparison is not None else None
        control_writes = {}
        for label, (path, stream, payload) in (controls or {}).items():
            first = utc_ticks()
            if stream.write(payload) != len(payload):
                raise RuntimeError("The generated pre-opened write was incomplete.")
            control_writes[label] = {"path": str(path), "size": len(payload),
                                     "start": first, "end": utc_ticks()}
        if preopened_resize is not None:
            resize_file, resize_stream, resize_seed = preopened_resize
            before_bytes = os.fstat(resize_stream.fileno()).st_size
            if before_bytes != len(resize_seed):
                raise RuntimeError("The pre-opened resize seed had the wrong length.")
            start = utc_ticks()
            resize_stream.truncate(37)
            resize_control = {"path": str(resize_file), "start": start, "end": utc_ticks(),
                              "before_bytes": before_bytes}
        if controls and before_stop is None:
            known_path = root / "known-write.bin"
            known_payload = b"K" * 61
            known_start = utc_ticks()
            known_pid = run_writer(
                "from pathlib import Path\nimport sys\n"
                "sys.path.insert(0, sys.argv[1])\n"
                "from n12_etw_probe import write_known_control\n"
                "write_known_control(Path(sys.argv[2]), bytes.fromhex(sys.argv[3]))",
                Path(__file__).parent, known_path, known_payload.hex(),
            )
            known_write = {"path": str(known_path), "pid": known_pid, "size": len(known_payload),
                           "start": known_start, "end": utc_ticks()}
            named_control = write_named_control(root / "in-capture-name.bin")
        if resize_path is not None:
            resize_start = utc_ticks()
            resize_pid = run_writer(
                "from pathlib import Path\nimport sys\n"
                "sys.path.insert(0, sys.argv[1])\n"
                "from n12_etw_probe import resize_known_control\n"
                "resize_known_control(Path(sys.argv[2]), int(sys.argv[3]))",
                Path(__file__).parent, resize_path, resize_target_size,
            )
            resize_end = utc_ticks()
        if comparison is not None:
            # Give immediate writes a separate observation interval before flushing.
            time.sleep(0.1)
            first = utc_ticks()
            os.fsync(controls["protected"][1].fileno())
            control_writes["protected"]["flush_window"] = [first, utc_ticks()]
        if before_stop is not None and controls:
            lifetime_path = root / "file-lifetime.bin"
            lifetime_start = utc_ticks()
            lifetime_pid = run_writer(
                "from pathlib import Path\nimport sys\n"
                "sys.path.insert(0, sys.argv[1])\n"
                "from n12_etw_probe import write_two_handle_control\n"
                "write_two_handle_control(Path(sys.argv[2]))",
                Path(__file__).parent, lifetime_path,
            )
            lifetime_control = {"pid": lifetime_pid, "path": str(lifetime_path), "size": 97,
                                "start": lifetime_start, "end": utc_ticks(), "two_handles": True}
            basic_info_path = root / "file-basic-info.bin"
            basic_info_start = utc_ticks()
            basic_info_pid = run_writer(
                "from pathlib import Path\nimport sys\n"
                "sys.path.insert(0, sys.argv[1])\n"
                "from n12_etw_probe import write_basic_info_control\n"
                "write_basic_info_control(Path(sys.argv[2]))",
                Path(__file__).parent, basic_info_path,
            )
            basic_info_control = {"pid": basic_info_pid, "path": str(basic_info_path), "size": 101,
                                  "start": basic_info_start, "end": utc_ticks(), "basic_info": True}
        # Give the new session a separate process launch before measuring the
        # fixture. Start the calibration parent inside the trace as well.
        run_writer("pass")
        fixture_start = utc_ticks()
        result = subprocess.run(
            [sys.executable, "-B", str(Path(__file__).with_name("n12_calibration.py")), str(root / "markers")],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=20, check=False,
        )
        if result.returncode:
            raise RuntimeError("The generated N12 calibration failed.")
        fixture = json.loads(result.stdout)
        fixture["start_window"] = [fixture_start, utc_ticks()]
        sysmon = verify_fixture(fixture, fixture_start) if verify_fixture is not None else None
        restore_evidence = protected_restore() if protected_restore is not None else None
        second_writer = None
        if not calibration_only:
            writer_start = utc_ticks()
            writer_pid = run_writer(
                "import os,sys\n"
                "try:\n with open(sys.argv[1], 'xb'): pass\n"
                "except FileExistsError: pass\n"
                "else: raise RuntimeError('Exclusive create should fail')\n"
                "os.rename(*sys.argv[1:])",
                source, destination,
            )
            second_writer = {"pid": writer_pid, "source": str(source), "destination": str(destination),
                             "start_window": [writer_start, utc_ticks()]}
            if source.exists() or destination.read_bytes() != b"cross-directory marker":
                raise RuntimeError("The cross-directory fixture did not finish at the expected destination.")
            run_writer("from pathlib import Path\nimport sys\n"
                       "path = Path(sys.argv[1])\npath.write_bytes(b'generated')\npath.unlink()", marker)
            if any(protected.iterdir()):
                raise RuntimeError("The synthetic protected directory did not return to baseline.")
    finally:
        stop_aux_error = None
        try:
            if before_stop is not None:
                rundown_start_ticks = utc_ticks() // 10 * 10
                rundown_stop_ticks = before_stop()
        except Exception as exc:
            stop_aux_error = exc
        try:
            counters = stop_trace(session)
        except RuntimeError:
            subprocess.run([*logman, "stop", session, "-ets"], stdout=subprocess.DEVNULL,
                           stderr=subprocess.DEVNULL, timeout=20, check=False)
            raise
        if stop_aux_error is not None:
            raise stop_aux_error
    if etl.stat().st_size == 0 or counters["buffers_written"] == 0:
        raise RuntimeError("ETW trace was empty.")
    mapped_devices = volume_devices()
    root_drive = root.drive.upper()
    if root_drive not in mapped_devices:
        mapped_devices[root_drive] = volume_device(root_drive)
    capture = {"fixture": fixture, "counters": counters, "device": mapped_devices[root_drive],
            "volume_devices": mapped_devices,
            "protected_root": str(protected), "second_writer": second_writer,
            "start_ticks": capture_start, "end_ticks": utc_ticks() // 10 * 10}
    if sysmon is not None:
        capture["sysmon"] = sysmon
    if restore_evidence is not None:
        capture["protected_restore"] = restore_evidence
    if controls:
        capture["preopened"] = {"pid": os.getpid(), "tid": get_native_id(), "writes": control_writes}
        if comparison is not None:
            capture["preopened"]["untouched"] = comparison
    if rundown_stop_ticks is not None:
        capture["rundown_start_ticks"] = rundown_start_ticks
        capture["rundown_stop_ticks"] = rundown_stop_ticks
    if lifetime_control is not None:
        if lifetime_path.read_bytes() != b"L" * 97:
            raise RuntimeError("The generated file lifetime control did not preserve its payload.")
        capture["file_lifetime"] = lifetime_control
    if named_control is not None:
        capture["in_capture_name_control"] = named_control
    if known_write is not None:
        if known_path.read_bytes() != known_payload:
            raise RuntimeError("The generated known-file write did not preserve its payload.")
        capture["known_write"] = known_write
    if resize_path is not None:
        resized = resize_path.read_bytes()
        if resized != resize_payload[:resize_target_size]:
            raise RuntimeError("The generated resize did not preserve the expected prefix and size.")
        capture["known_resize"] = {"path": str(resize_path), "pid": resize_pid,
                                   "start": resize_start, "end": resize_end,
                                   "before_bytes": resize_before_size, "after_bytes": len(resized)}
    if resize_control is not None:
        resize_stream.seek(0)
        resized = resize_stream.read()
        if resized != resize_seed[:37]:
            raise RuntimeError("The pre-opened resize did not preserve the expected prefix and size.")
        capture["known_preopened_resize"] = {**resize_control, "after_bytes": len(resized)}
    if basic_info_control is not None:
        if basic_info_path.read_bytes() != b"M" * 101:
            raise RuntimeError("The generated metadata-control payload did not match.")
        capture["basic_info_control"] = basic_info_control
    return capture


if __name__ == "__main__":
    try:
        options = sys.argv[2:]
        if len(sys.argv) < 2 or options not in (
            [], ["--calibration-only"], ["--calibration-only", "--thread-context"],
            ["--collector-rehearsal"], ["--collector-rehearsal", "--rundown"],
            ["--preopened-control"], ["--preopened-control", "--rundown"],
            ["--preopened-control", "--rundown", "--system-timing"],
        ):
            raise ValueError("Unexpected probe arguments.")
        root = local_disposable_path(Path(sys.argv[1]), runner_temp_only=True)
        if "--collector-rehearsal" in options:
            print(json.dumps(collector_rehearsal(root, rundown="--rundown" in options)))
        elif "--preopened-control" in options:
            print(json.dumps(preopened_control(
                root, rundown="--rundown" in options, system_timing="--system-timing" in options,
            )))
        else:
            print(json.dumps(probe(root, calibration_only="--calibration-only" in options,
                                   thread_context="--thread-context" in options)))
    except (RuntimeError, EvidenceValidationError) as exc:
        sys.exit(str(exc))
    except (IndexError, OSError, ValueError, subprocess.SubprocessError):
        sys.exit("ETW fixture probe failed before generating a report.")
