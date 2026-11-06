#!/usr/bin/env python3
"""P2-U2b Gate A: read-only inspection of local Windows sidecar build environments.

This cannot build/install/freeze anything and never accesses PilotODIN projects.
It queries ONLY package metadata in known local virtualenvs with isolated Python.
A completed audit is NOT authority to build or to ship fonts.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
VENV_PATHS = {
    "live": ROOT / ".venv-live",
    "existing_build": ROOT / ".venv",
    "private_freezer": ROOT / "build" / "p2-pdf-frozen-resource-probe" / "tooling-venv",
}
REQUIRED_RUNTIME = (
    "fastapi", "uvicorn", "python-multipart", "pandas", "numpy", "scipy",
    "scikit-learn", "openpyxl", "joblib", "pydantic", "reportlab"
)
REQUIRED_BUILDER = ("pyinstaller", "pyinstaller-hooks-contrib")
PROBE_NAMES = (*REQUIRED_RUNTIME, *REQUIRED_BUILDER)
MIN_PROPOSED_DISK = 2 * 1024 * 1024 * 1024
PROBE_TIMEOUT = 15

_PROBE = """
import importlib.metadata as md, json, pathlib, platform, struct, sys
names = %r
versions = {}
for name in names:
    try: versions[name] = md.version(name)
    except md.PackageNotFoundError: versions[name] = None
print(json.dumps({
    "prefix":str(pathlib.Path(sys.prefix).resolve()),
    "version":[sys.version_info.major,sys.version_info.minor,sys.version_info.micro],
    "machine":platform.machine(),
    "bits":struct.calcsize("P")*8,
    "packages":versions
},sort_keys=True))
""" % (PROBE_NAMES,)


def _not_redirected(location: Path) -> None:
    for node in (location, *location.parents):
        if node.is_symlink() or (node.exists() and
                                 getattr(os.path, "isjunction", lambda _: False)(node)):
            raise ValueError("Redirected interpreter path")


def inspect_interpreter(env_dir: Path, *, run=subprocess.run) -> dict:
    """Metadata only; no imports of FastAPI, scipy, font binaries or model data."""
    _not_redirected(env_dir)
    py = env_dir / "Scripts" / "python.exe"
    if not py.is_file() or py.is_symlink():
        return {"state": "ABSENT"}
    safe_env = dict(os.environ)
    safe_env["PYTHONDONTWRITEBYTECODE"] = "1"
    safe_env["PYTHONNOUSERSITE"] = "1"
    for var in ("PYTHONPATH", "PILOTODIN_HOME", "PILOTODIN_DESKTOP_SESSION",
                "PILOTODIN_DESKTOP_PORT", "PIP_INDEX_URL", "PIP_EXTRA_INDEX_URL"):
        safe_env.pop(var, None)
    try:
        child = run([str(py), "-I", "-B", "-c", _PROBE], cwd=ROOT,
                    env=safe_env, capture_output=True, text=True, timeout=PROBE_TIMEOUT,
                    check=False)
    except subprocess.TimeoutExpired:
        return {"state": "BLOCKED", "reason": "metadata_probe_timeout"}
    except OSError:
        return {"state": "BLOCKED", "reason": "python_could_not_start"}
    if child.returncode != 0 or len(child.stdout) > 6000:
        return {"state": "BLOCKED", "reason": "python_metadata_probe_failed"}
    try:
        detail = json.loads(child.stdout)
    except (TypeError, ValueError):
        return {"state": "BLOCKED", "reason": "python_probe_invalid_json"}
    if not isinstance(detail, dict) or not isinstance(detail.get("prefix"), str) or (
            Path(detail["prefix"]).resolve().as_posix().casefold() !=
            env_dir.resolve().as_posix().casefold()):
        return {"state": "BLOCKED", "reason": "python_prefix_mismatch"}
    versions = detail.get("packages")
    v = detail.get("version")
    if (not isinstance(versions, dict) or set(versions) != set(PROBE_NAMES) or
            not isinstance(v, list) or len(v) != 3 or
            any(type(n) is not int or n <= 0 for n in v) or
            not isinstance(detail.get("bits"), int) or
            detail["bits"] not in (32, 64)):
        return {"state": "BLOCKED", "reason": "malformed_python_metadata"}
    if any(version is not None and (not isinstance(version, str) or len(version) > 120)
           for version in versions.values()):
        return {"state": "BLOCKED", "reason": "invalid_package_version"}
    return {
        "state": "INSPECTED",
        "python": ".".join(map(str, v)),
        "architecture_bits": detail["bits"],
        "runtime_present": [name for name in REQUIRED_RUNTIME if versions[name]],
        "runtime_missing": [name for name in REQUIRED_RUNTIME if not versions[name]],
        "freezer_present": [name for name in REQUIRED_BUILDER if versions[name]],
        "freezer_missing": [name for name in REQUIRED_BUILDER if not versions[name]],
        "reportlab_version": versions["reportlab"],
        "pyinstaller_version": versions["pyinstaller"],
        "hooks_version": versions["pyinstaller-hooks-contrib"],
    }


def assess(environments: dict[str, dict], free_bytes: int) -> dict:
    if (set(environments) != set(VENV_PATHS) or not isinstance(free_bytes, int)
            or isinstance(free_bytes, bool) or free_bytes < 0):
        raise ValueError("Invalid readiness inputs")
    live, private = environments["live"], environments["private_freezer"]
    critical = any(e["state"] == "BLOCKED" for e in environments.values())
    if critical or live["state"] != "INSPECTED" or private["state"] != "INSPECTED":
        state = "BLOCKED"
    else:
        state = "READINESS_AUDIT_COMPLETE_BUILD_DESIGN_REQUIRED"
    return {
        "state": state,
        "environment_metadata_only": True,
        "disk_bytes_free": free_bytes,
        "suggested_build_disk_bytes": MIN_PROPOSED_DISK,
        "sufficient_disk_for_design": free_bytes >= MIN_PROPOSED_DISK,
        "environments": environments,
        "actual_sidecar_built": False,
        "actual_sidecar_fonts_verified": False,
        "product_unicode_acceptance": "NOT_TESTED",
        "peak_memory": "NOT_MEASURED",
        "next": "REVIEW_BUILD_ENVIRONMENT_BEFORE_ANY_SIDE_CAR_FREEZE",
    }


def main() -> int:
    try:
        if sys.platform != "win32":
            raise ValueError("WindowsOnly")
        environments = {name: inspect_interpreter(path)
                        for name, path in VENV_PATHS.items()}
        outcome = assess(environments, shutil.disk_usage(ROOT).free)
    except Exception as exc:
        outcome = {"state": "BLOCKED", "failure_class": type(exc).__name__,
                   "actual_sidecar_built": False,
                   "product_unicode_acceptance": "NOT_TESTED"}
    print("P2 ACTUAL SIDECAR BUILD READINESS: " + outcome["state"])
    print(json.dumps(outcome, ensure_ascii=False, indent=2))
    return 0 if outcome["state"] == "READINESS_AUDIT_COMPLETE_BUILD_DESIGN_REQUIRED" else 2


if __name__ == "__main__":
    raise SystemExit(main())
