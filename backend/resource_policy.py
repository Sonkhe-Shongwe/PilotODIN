"""P1 read-only Windows resource observations and per-device UI policy.

Low-memory mode adds bounded headroom admission checks before NEW
local training and local inference requests. This is not a peak-RAM bound,
durable task scheduler, AI model loader or E2 offline certificate.
No network calls or unrelated process enumeration occur here.
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
_GIB_BYTES = 1024 ** 3
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
        storage.check_write_path(target, missing=True)
        target.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary = tempfile.mkstemp(prefix=".resource-policy-",
                                                suffix=".tmp", dir=str(target.parent))
        identity = None
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as file:
                identity = os.fstat(file.fileno())
                json.dump({"schema_version": 1, "mode": mode}, file, separators=(",", ":"))
                file.flush()
                os.fsync(file.fileno())
            storage.check_write_path(Path(temporary), expected=identity)
            storage.check_write_path(target, missing=True)
            os.replace(temporary, target)
        finally:
            storage.guarded_unlink(Path(temporary), expected=identity)
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
            "status": "observed", "total_gib": round(total / _GIB_BYTES, 3),
            "available_gib": round(available / _GIB_BYTES, 3),
            "available_bytes": available,
            "source": source, "measured_at_utc": observed_at,
            "note": "Instantaneous system memory; available RAM is not a model's peak budget.",
        }
    except (OSError, ValueError, KeyError, AttributeError):
        return {
            "status": "unavailable", "total_gib": None, "available_gib": None,
            "available_bytes": None,
            "source": "unavailable", "measured_at_utc": observed_at,
            "note": "Physical memory could not be measured; no capacity is assumed.",
        }


# Screening floors, NOT estimated application peaks or hardware guarantees.
# Low-memory applies only to new requests, never to an in-progress task.
# Existing per-model/row/matrix caps remain the authoritative ML limits.
LOW_MEMORY_MIN_FREE_GIB = {
    "training": 0.75,
    "local_inference": 2.0,
}


def _r03_profile() -> str | None:
    profile = os.environ.get("PILOTODIN_R03_BENCHMARK")
    home = storage.HOME
    if (sys.platform == "win32" and profile in ("baseline", "candidate")
            and os.environ.get("PILOTODIN_DESKTOP_SESSION")
            and home.name == profile and home.parent.name == "data"
            and home.parent.parent.name == "com.pilotodin.p4r03benchmark"):
        return profile
    return None


def _minimum_free_gib(operation: str) -> float:
    if operation == "local_inference" and _r03_profile() == "candidate":
        return 1.50
    return LOW_MEMORY_MIN_FREE_GIB[operation]


def record_r03_event(stage: str, **fields) -> None:
    """Record only caller-supplied measurements in the disposable QA profile."""
    profile = _r03_profile()
    if profile is None:
        return
    event = {"at_utc": datetime.now(timezone.utc).isoformat(), "profile": profile,
             "stage": stage, **fields}
    try:
        with _lock:
            path = storage.HOME / "r03-benchmark.jsonl"
            storage.check_write_path(path, missing=True)
            with path.open("a", encoding="utf-8") as stream:
                stream.write(json.dumps(event, separators=(",", ":")) + "\n")
    except (OSError, storage.WorkspaceBoundaryError):
        # Measurement is optional and must not change the admission decision.
        return


def admit_new_work(operation: str) -> dict:
    """Bounded policy-based admission; side-effect-free and deterministic.

    Other policy modes retain the pre-existing behavior until task scheduling
    and measured model budgets are implemented. Missing RAM readings are
    treated conservatively only when the user selected Low-memory.
    """
    if operation not in LOW_MEMORY_MIN_FREE_GIB:
        raise ValueError("Unknown resource admission operation")
    policy = read_policy()["mode"]
    minimum = _minimum_free_gib(operation)
    if policy != "low_memory":
        return {
            "decision": "allow", "code": "not_enforced_for_selected_mode",
            "mode": policy, "operation": operation, "available_gib": None,
            "available_bytes": None,
            "required_free_gib": minimum,
            "note": "Existing operation-specific hard resource and integrity limits still apply.",
        }
    observed = memory_status()
    available_bytes = observed["available_bytes"]
    if observed["status"] != "observed" or available_bytes is None:
        return {
            "decision": "defer", "code": "memory_unavailable",
            "mode": policy, "operation": operation, "available_gib": None,
            "available_bytes": None,
            "required_free_gib": minimum,
            "note": "Cannot measure available RAM in Low-memory mode. Close unnecessary apps or retry later.",
        }
    if available_bytes < minimum * _GIB_BYTES:
        return {
            "decision": "defer", "code": "low_memory_headroom",
            "mode": policy, "operation": operation, "available_gib": observed["available_gib"],
            "available_bytes": available_bytes,
            "required_free_gib": minimum,
            "note": ("Low-memory mode deferred new " + operation.replace("_", " ")
                     + " because available RAM is below a conservative screening floor. "
                     "This is not a measured peak task requirement; retry when more RAM is available."),
        }
    return {
        "decision": "allow", "code": "screening_floor_met",
        "mode": policy, "operation": operation, "available_gib": observed["available_gib"],
        "available_bytes": available_bytes,
        "required_free_gib": minimum,
        "note": "Admission screening passed; this does not guarantee peak RAM fit or offline AI feasibility.",
    }


def status() -> dict:
    return {
        "policy": read_policy(),
        "memory": memory_status(),
        "policy_effect": "low_memory_new_work_preflight_only_no_scheduler",
        "offline_8gb_ai_feasibility": "NOT_TESTED",
        "low_memory_training_min_free_gib": LOW_MEMORY_MIN_FREE_GIB["training"],
        "low_memory_local_inference_min_free_gib": _minimum_free_gib("local_inference"),
    }
