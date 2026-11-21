#!/usr/bin/env python3
"""P2-U2b Gate B0: no-write build-route decision, NOT a frozen build.

Requires no new Python packages. Reads only bounded metadata for the three
already-existing venvs. Does not run pip, import scientific packages, read
font files, mutate project data, execute an installer or choose release assets.
"""
from __future__ import annotations

import json
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.p2_pdf_sidecar_build_readiness import (
    VENV_PATHS, REQUIRED_RUNTIME, inspect_interpreter, MIN_PROPOSED_DISK,
)

def _py_major_minor(value: str) -> tuple[int, int] | None:
    if not isinstance(value, str):
        return None
    parts = value.split(".")
    if len(parts) != 3 or not all(part.isdecimal() for part in parts):
        return None
    try:
        return (int(parts[0]), int(parts[1]))
    except ValueError:
        return None


def is_self_contained_candidate(item: dict) -> bool:
    """Only one complete 64-bit environment may be a build candidate."""
    if not isinstance(item, dict) or item.get("state") != "INSPECTED":
        return False
    runtime = item.get("runtime_present")
    freezer = item.get("freezer_present")
    if not isinstance(runtime, list) or not isinstance(freezer, list):
        return False
    if len(runtime) != len(set(runtime)) or len(freezer) != len(set(freezer)):
        return False
    if not set(REQUIRED_RUNTIME).issubset(runtime):
        return False
    if not {"pyinstaller", "pyinstaller-hooks-contrib"}.issubset(freezer):
        return False
    version = item.get("pyinstaller_version")
    if not isinstance(version, str) or not version.startswith("6."):
        return False
    return (item.get("architecture_bits") == 64 and
            _py_major_minor(item.get("python")) is not None)


def decide_build_route(environments: dict, free_bytes: int) -> dict:
    """A route is a design recommendation, never permission to package."""
    if (not isinstance(environments, dict) or
            set(environments) != set(VENV_PATHS) or
            type(free_bytes) is not int or free_bytes < 0):
        raise ValueError("Invalid build route inputs")
    if any(not isinstance(item, dict) or
           item.get("state") not in {"INSPECTED", "ABSENT", "BLOCKED"}
           for item in environments.values()):
        raise ValueError("Unrecognized interpreter metadata")
    live = environments["live"]
    existing = environments["existing_build"]
    private = environments["private_freezer"]
    candidates = [name for name in ("existing_build", "live")
                  if is_self_contained_candidate(environments[name])]
    live_runtime = (live.get("state") == "INSPECTED" and
                    isinstance(live.get("runtime_present"), list) and
                    set(REQUIRED_RUNTIME).issubset(live["runtime_present"]) and
                    live.get("architecture_bits") == 64)
    private_freezer = (private.get("state") == "INSPECTED" and
                       private.get("pyinstaller_version") == "6.22.3" and
                       private.get("hooks_version") == "2026.9" and
                       set(private.get("freezer_present") or ()) >=
                       {"pyinstaller", "pyinstaller-hooks-contrib"} and
                       private.get("architecture_bits") == 64)
    py_compatible = (
        live.get("state") == "INSPECTED" and
        private.get("state") == "INSPECTED" and
        _py_major_minor(live.get("python")) is not None and
        _py_major_minor(live.get("python")) == _py_major_minor(private.get("python"))
    )
    if any(item["state"] == "BLOCKED" for item in environments.values()):
        route = "INVESTIGATE_INTERPRETER_METADATA"
    elif free_bytes < MIN_PROPOSED_DISK:
        route = "INSUFFICIENT_DISK_FOR_BUILD_DESIGN"
    elif candidates:
        route = "EXISTING_SELF_CONTAINED_INTERPRETER_CANDIDATE"
    elif live_runtime and private_freezer:
        route = "DEDICATED_FULL_BUILD_ENVIRONMENT_DESIGN_REQUIRED"
    else:
        route = "REVIEW_RUNTIME_DEPENDENCIES_BEFORE_BUILD"
    compact = {}
    for name, item in environments.items():
        compact[name] = {
            "state": item["state"],
            "python": item.get("python"),
            "bits": item.get("architecture_bits"),
            "runtime_missing": item.get("runtime_missing", []),
            "pyinstaller": item.get("pyinstaller_version"),
            "hooks": item.get("hooks_version"),
            "candidate": is_self_contained_candidate(item),
        }
    return {
        "state": "BUILD_ROUTE_DESIGN_ONLY" if route not in {
            "INVESTIGATE_INTERPRETER_METADATA", "INSUFFICIENT_DISK_FOR_BUILD_DESIGN"
        } else "BLOCKED",
        "route": route,
        "primary_self_contained_candidate": candidates[0] if candidates else None,
        "private_builder_has_pinned_pyinstaller": private_freezer,
        "live_has_complete_runtime_metadata": live_runtime,
        "private_and_live_python_major_minor_match": py_compatible,
        "free_disk_ge_2gib": free_bytes >= MIN_PROPOSED_DISK,
        "environment_summary": compact,
        "not_verified": [
            "Native scientific imports and DLL integrity",
            "Wheel/requirement version constraints and full lockfile",
            "Frozen PilotODIN backend and packaged font runtime",
            "Font release authorization and PDF visual fidelity",
        ],
        "dependencies_installed": False,
        "sidecar_built": False,
        "installer_built": False,
        "production_acceptance": "NOT_TESTED",
        "next": "REVIEW_ROUTE_AND_REQUEST_EXPLICIT_BUILD_PERMISSION",
    }


def main() -> int:
    try:
        if sys.platform != "win32":
            raise ValueError("WindowsOnly")
        envs = {name: inspect_interpreter(path) for name, path in VENV_PATHS.items()}
        result = decide_build_route(envs, shutil.disk_usage(ROOT).free)
    except Exception as exc:
        result = {"state": "BLOCKED", "failure_class": type(exc).__name__,
                  "dependencies_installed": False, "sidecar_built": False,
                  "production_acceptance": "NOT_TESTED"}
    print("P2 SIDECAR BUILD ROUTE: " + result["state"])
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["state"] == "BUILD_ROUTE_DESIGN_ONLY" else 2


if __name__ == "__main__":
    raise SystemExit(main())
