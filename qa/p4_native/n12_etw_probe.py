"""Probe Windows ETW session counters and capture a generated N12 fixture."""
from __future__ import annotations

import ctypes
import json
import os
import subprocess
import sys
import time
from ctypes import wintypes
from pathlib import Path
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
    return time.time_ns() // 100 + 621355968000000000


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


def probe(root):
    root.mkdir()
    session = f"PilotODIN-N12-{uuid4().hex}"
    etl = root / "fixture.etl"
    source, destination = root / "source" / "move.bin", root / "destination" / "move.bin"
    source.parent.mkdir()
    destination.parent.mkdir()
    source.write_bytes(b"cross-directory marker")
    protected = root / "synthetic-protected"
    protected.mkdir()
    marker = protected / "transient.bin"
    providers = root / "providers.txt"
    providers.write_text(
        "Microsoft-Windows-Kernel-File 0x1ef0 4\n"
        "Microsoft-Windows-Kernel-Process 0x10 4\n",
        encoding="ascii",
    )
    # Names, file I/O, completion, creation, writes, and delete/rename paths.
    logman = [str(Path(os.environ["SystemRoot"]) / "System32" / "logman.exe")]
    started = subprocess.run(
        [*logman, "create", "trace", session, "-pf", str(providers),
         "-o", str(etl), "-max", "128", "-bs", "64", "-nb", "16", "128", "-ets"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=20, check=False,
    )
    if started.returncode:
        raise RuntimeError(f"ETW start failed with exit code {started.returncode}.")
    try:
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
        writer_start = utc_ticks()
        writer_pid = run_writer(
            "import os,sys\n"
            "try:\n with open(sys.argv[1], 'xb'): pass\n"
            "except FileExistsError: pass\n"
            "else: raise RuntimeError('Exclusive create should fail')\n"
            "os.rename(*sys.argv[1:])",
            source, destination,
        )
        writer_window = [writer_start, utc_ticks()]
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
    return {"fixture": fixture, "counters": counters, "device": volume_device(root.drive),
            "protected_root": str(protected), "second_writer": {
                "pid": writer_pid, "source": str(source), "destination": str(destination),
                "start_window": writer_window,
            }}


if __name__ == "__main__":
    try:
        print(json.dumps(probe(local_disposable_path(Path(sys.argv[1]), runner_temp_only=True))))
    except RuntimeError as exc:
        sys.exit(str(exc))
    except (IndexError, OSError, ValueError, subprocess.SubprocessError):
        sys.exit("ETW fixture probe failed before generating a report.")
