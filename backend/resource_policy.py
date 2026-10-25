"""P1 read-only Windows resource observations and per-device UI policy.

Resource modes are display/persistence only in this increment. Heavy-task
preflight/scheduling is a separate P5 gate; do not claim enforcement or E2.
No model downloads, network calls or process enumeration occur here.
"""
from __future__ import annotations

import ctypes
import json
import os
import sys
import tempfile
import threading
from datetime import datetime, timezone
from pathlib import Path

try:
    from . import storage
except ImportError:
    import storage

MODES = ("adaptive", "low_memory", "performance")
_lock = threading.RLock()


def _path() -> Path:
    # Resolve dynamically so isolated Pytest HOME patches never write to
    # the owner's normal PilotODIN home.
    return storage.HOME / "resource_preferences.json"


def read_policy() -> dict:
    with _lock:
        try:
            content = _path().read_text(encoding="utf-8")
        except FileNotFoundError:
            return {"mode": "adaptive", "source": "default", "warning": None}
        except OSError:
            return {"mode": "adaptive", "source": "fallback",
                    "warning": "Resource preferences could not be read; nothing was overwritten."}
        try:
            value = json.loads(content)
            if (not isinstance(value, dict) or value.get("schema_version") != 1
                    or value.get("mode") not in MODES):
                raise ValueError("Unsupported resource preference data")
            return {"mode": value["mode"], "source": "saved", "warning": None}
        except (ValueError, TypeError):
            return {"mode": "adaptive", "source": "fallback",
                    "warning": "Saved resource preferences are invalid; nothing was overwritten."}


def save_policy(mode: str) -> dict:
    if mode not in MODES:
        raise ValueError("Unknown resource policy")
    with _lock:
        target = _path()
        target.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary = tempfile.mkstemp(prefix=".resource-policy-",
                                                suffix=".tmp", dir=str(target.parent))
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as file:
                json.dump({"schema_version": 1, "mode": mode}, file, separators=(",", ":"))
                file.flush()
                os.fsync(file.fileno())
            os.replace(temporary, target)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
        return {"mode": mode, "source": "saved", "warning": None}


def _physical_memory_bytes() -> tuple[int, int, str]:
    if sys.platform == "win32":
        class MEMORYSTATUSEX(ctypes.Structure):
            _fields_ = [
                ("dwLength", ctypes.c_ulong),
                ("dwMemoryLoad", ctypes.c_ulong),
                ("ullTotalPhys", ctypes.c_ulonglong),
                ("ullAvailPhys", ctypes.c_ulonglong),
                ("ullTotalPageFile", ctypes.c_ulonglong),
                ("ullAvailPageFile", ctypes.c_ulonglong),
                ("ullTotalVirtual", ctypes.c_ulonglong),
                ("ullAvailVirtual", ctypes.c_ulonglong),
                ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
            ]
        state = MEMORYSTATUSEX()
        state.dwLength = ctypes.sizeof(state)
        if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(state)):
            raise OSError("Windows physical memory observation unavailable")
        return int(state.ullTotalPhys), int(state.ullAvailPhys), "windows_global_memory_status"
    if sys.platform.startswith("linux"):
        values = {}
        for line in Path("/proc/meminfo").read_text(encoding="ascii").splitlines():
            key, sep, value = line.partition(":")
            if sep and key in ("MemTotal", "MemAvailable"):
                values[key] = int(value.strip().split()[0]) * 1024
        return values["MemTotal"], values["MemAvailable"], "linux_meminfo_estimate"
    raise OSError("Memory observation unsupported on this platform")


def memory_status() -> dict:
    observed_at = datetime.now(timezone.utc).isoformat()
    try:
        total, available, source = _physical_memory_bytes()
        if total <= 0 or not 0 <= available <= total:
            raise ValueError("Invalid memory observation")
        return {
            "status": "observed", "total_gib": round(total / (1024 ** 3), 3),
            "available_gib": round(available / (1024 ** 3), 3),
            "source": source, "measured_at_utc": observed_at,
            "note": "Instantaneous system memory; available RAM is not a model's peak budget.",
        }
    except (OSError, ValueError, KeyError, AttributeError):
        return {
            "status": "unavailable", "total_gib": None, "available_gib": None,
            "source": "unavailable", "measured_at_utc": observed_at,
            "note": "Physical memory could not be measured; no capacity is assumed.",
        }


def status() -> dict:
    return {
        "policy": read_policy(),
        "memory": memory_status(),
        "policy_effect": "display_only_p1_not_enforced",
        "offline_8gb_ai_feasibility": "NOT_TESTED",
    }
