"""Probe Windows ETW session counters and capture a generated N12 fixture."""
from __future__ import annotations

import ctypes
import json
import os
import subprocess
import sys
from contextlib import ExitStack
from ctypes import wintypes
from pathlib import Path
from threading import get_native_id
from uuid import uuid4

from n12_trace import local_disposable_path


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


def preopened_control(root):
    import msvcrt

    root.mkdir()
    protected = root / "synthetic-protected"
    protected.mkdir()
    get_path = ctypes.WinDLL("kernel32", use_last_error=True).GetFinalPathNameByHandleW
    get_path.argtypes = (wintypes.HANDLE, wintypes.LPWSTR, wintypes.DWORD, wintypes.DWORD)
    get_path.restype = wintypes.DWORD
    with ExitStack() as stack:
        controls = {}
        for label, path, size in (("protected", protected / "control.bin", 53),
                                  ("outside", root / "outside.bin", 79)):
            stream = stack.enter_context(path.open("xb", buffering=0))
            name = ctypes.create_unicode_buffer(32768)
            length = get_path(msvcrt.get_osfhandle(stream.fileno()), name, len(name), 0)
            if not 0 < length < len(name) or Path(name.value.removeprefix("\\\\?\\")) != path:
                raise RuntimeError("Windows did not confirm the generated handle target.")
            controls[label] = (path, stream, b"x" * size)
        return capture_fixture(root, calibration_only=True, thread_context=True, controls=controls)


def capture_fixture(root, *, calibration_only, thread_context, controls=None):
    session = f"PilotODIN-N12-{uuid4().hex}"
    etl = root / "fixture.etl"
    source, destination = root / "source" / "move.bin", root / "destination" / "move.bin"
    if not calibration_only:
        source.parent.mkdir()
        destination.parent.mkdir()
        source.write_bytes(b"cross-directory marker")
    protected = root / "synthetic-protected"
    marker = protected / "transient.bin"
    providers = root / "providers.txt"
    providers.write_text(
        "Microsoft-Windows-Kernel-File 0x1ef0 4\n"
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
    try:
        control_writes = {}
        for label, (path, stream, payload) in (controls or {}).items():
            first = utc_ticks()
            if stream.write(payload) != len(payload):
                raise RuntimeError("The generated pre-opened write was incomplete.")
            control_writes[label] = {"path": str(path), "size": len(payload),
                                     "start": first, "end": utc_ticks()}
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
        try:
            counters = stop_trace(session)
        except RuntimeError:
            subprocess.run([*logman, "stop", session, "-ets"], stdout=subprocess.DEVNULL,
                           stderr=subprocess.DEVNULL, timeout=20, check=False)
            raise
    if etl.stat().st_size == 0 or counters["buffers_written"] == 0:
        raise RuntimeError("ETW trace was empty.")
    capture = {"fixture": fixture, "counters": counters, "device": volume_device(root.drive),
            "protected_root": str(protected), "second_writer": second_writer,
            "start_ticks": capture_start, "end_ticks": utc_ticks() // 10 * 10}
    if controls:
        capture["preopened"] = {"pid": os.getpid(), "tid": get_native_id(), "writes": control_writes}
    return capture


if __name__ == "__main__":
    try:
        options = sys.argv[2:]
        if len(sys.argv) < 2 or options not in (
            [], ["--calibration-only"], ["--calibration-only", "--thread-context"], ["--preopened-control"],
        ):
            raise ValueError("Unexpected probe arguments.")
        root = local_disposable_path(Path(sys.argv[1]), runner_temp_only=True)
        if options == ["--preopened-control"]:
            print(json.dumps(preopened_control(root)))
        else:
            print(json.dumps(probe(root, calibration_only="--calibration-only" in options,
                                   thread_context="--thread-context" in options)))
    except RuntimeError as exc:
        sys.exit(str(exc))
    except (IndexError, OSError, ValueError, subprocess.SubprocessError):
        sys.exit("ETW fixture probe failed before generating a report.")
