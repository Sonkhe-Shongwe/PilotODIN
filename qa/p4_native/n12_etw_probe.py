"""Probe Windows ETW session counters and capture a generated N12 fixture."""
from __future__ import annotations

import ctypes
import json
import os
import subprocess
import sys
from ctypes import wintypes
from pathlib import Path
from uuid import uuid4

from n12_calibration import calibrate
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


def probe(root):
    root.mkdir()
    session = f"PilotODIN-N12-{uuid4().hex}"
    etl = root / "fixture.etl"
    # Kernel File keywords for names, file I/O, completion, creation and writes.
    logman = [str(Path(os.environ["SystemRoot"]) / "System32" / "logman.exe")]
    started = subprocess.run(
        [*logman, "create", "trace", session, "-p", "Microsoft-Windows-Kernel-File",
         "0x2f0", "4", "-o", str(etl), "-max", "128", "-bs", "64", "-nb", "16", "128", "-ets"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=20, check=False,
    )
    if started.returncode:
        raise RuntimeError(f"ETW start failed with exit code {started.returncode}.")
    try:
        fixture = calibrate(root / "markers")
    finally:
        try:
            counters = stop_trace(session)
        except RuntimeError:
            subprocess.run([*logman, "stop", session, "-ets"], stdout=subprocess.DEVNULL,
                           stderr=subprocess.DEVNULL, timeout=20, check=False)
            raise
    if etl.stat().st_size == 0 or counters["buffers_written"] == 0:
        raise RuntimeError("ETW trace was empty.")
    return {"fixture": fixture, "counters": counters}


if __name__ == "__main__":
    try:
        print(json.dumps(probe(local_disposable_path(Path(sys.argv[1]), runner_temp_only=True))))
    except RuntimeError as exc:
        sys.exit(str(exc))
    except (IndexError, OSError, ValueError, subprocess.SubprocessError):
        sys.exit("ETW fixture probe failed before generating a report.")
