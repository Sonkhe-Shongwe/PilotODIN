#!/usr/bin/env python3
"""P2-U2c: explicitly authorised, isolated full scientific sidecar builder venv.

DEVQA ONLY. --inspect is read-only. --prepare creates only a NEW ignored venv
under build/p2-sidecar-env/ with consent given by the Windows launcher.
It does NOT build pilotodin-engine, alter app virtualenvs, stage Tauri binaries,
use font files, run PilotODIN, operate on projects or approve release artifacts.

Direct runtime versions are read from .venv-live; transitive dependencies are
pip-resolved on official PyPI, so this is NOT a hash-locked reproducible release
environment. Record that limitation rather than calling it release-approved.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
LIVE_PY = ROOT / ".venv-live" / "Scripts" / "python.exe"
BUILD_ROOT = ROOT / "build" / "p2-sidecar-env"
ENV_DIR = BUILD_ROOT / "venv"
REQUIREMENTS = ROOT / "backend" / "requirements.txt"
PINNED_PYINSTALLER = "6.22.3"
PINNED_HOOKS = "2026.9"
MIN_DISK = 3 * 1024**3
OFFICIAL_INDEX = "https://pypi.org/simple"
REQUIRED_LINES = (
    "fastapi>=0.110,<1",
    "uvicorn[standard]>=0.25,<1",
    "python-multipart>=0.0.9",
    "pandas>=2.2,<3",
    "numpy>=1.26,<3",
    "scikit-learn>=1.4,<2",
    "openpyxl>=3.1,<4",
    "joblib>=1.3,<2",
    "pydantic>=2,<3",
    "reportlab>=4.2,<5",
)
RUNTIME = (
    "fastapi", "uvicorn", "python-multipart", "pandas", "numpy",
    "scikit-learn", "scipy", "openpyxl", "joblib", "pydantic", "reportlab"
)
PACKAGE_KEYS = RUNTIME + ("pyinstaller", "pyinstaller-hooks-contrib")
IMPORTS = "fastapi, uvicorn, multipart, pandas, numpy, scipy, sklearn, openpyxl, joblib, pydantic, reportlab"
_PROBE = (
    "import json,importlib.metadata as m,sys,struct,pathlib;"
    "names=" + repr(RUNTIME) + ";"
    "v={};"
    "\nfor n in names:\n"
    " try: v[n]=m.version(n)\n"
    " except m.PackageNotFoundError: v[n]=None\n"
    "print(json.dumps({'prefix':str(pathlib.Path(sys.prefix).resolve()),"
    "'bits':struct.calcsize('P')*8,'python':list(sys.version_info[:3]),'versions':v}))"
)


def _safe(path: Path) -> None:
    for part in (path, *path.parents):
        if part.is_symlink() or (part.exists() and getattr(os.path, "isjunction", lambda _: False)(part)):
            raise ValueError("RedirectedDevQALocation")


def python_for(directory: Path) -> Path:
    return directory / "Scripts" / "python.exe"


def _run(argv: list[str], timeout: int) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    env.update({"PYTHONNOUSERSITE": "1", "PYTHONDONTWRITEBYTECODE": "1",
                "PIP_CONFIG_FILE": os.devnull})
    for name in ("PYTHONPATH", "PYTHONHOME", "PILOTODIN_HOME",
                 "PILOTODIN_DESKTOP_SESSION", "PILOTODIN_DESKTOP_PORT",
                 "PIP_INDEX_URL", "PIP_EXTRA_INDEX_URL", "PIP_FIND_LINKS",
                 "PIP_CONSTRAINT", "PIP_REQUIREMENT", "PIP_TARGET",
                 "PIP_PREFIX", "PIP_USER"):
        env.pop(name, None)
    return subprocess.run(argv, env=env, cwd=ROOT, capture_output=True,
                          text=True, check=False, timeout=timeout)


def check_requirements() -> None:
    lines = REQUIREMENTS.read_text(encoding="utf-8").splitlines()
    if tuple(x.strip() for x in lines if x.strip()) != REQUIRED_LINES:
        raise ValueError("BackendRequirementsChanged")


def live_versions(*, runner=_run) -> dict[str, str]:
    _safe(LIVE_PY)
    if not LIVE_PY.is_file():
        raise ValueError("LivePythonMissing")
    response = runner([str(LIVE_PY), "-I", "-B", "-c", _PROBE], 25)
    if response.returncode or len(response.stdout) > 4096:
        raise ValueError("LiveMetadataBlocked")
    result = json.loads(response.stdout)
    if (Path(result["prefix"]).resolve().as_posix().casefold() !=
            LIVE_PY.parent.parent.resolve().as_posix().casefold() or
            result["bits"] != 64 or result["python"] != [3, 12, 3] or
            set(result["versions"]) != set(RUNTIME)):
        raise ValueError("LivePythonOrVersionChanged")
    versions = result["versions"]
    if any(not isinstance(x, str) or not re.fullmatch(r"[0-9][A-Za-z0-9.!+_-]{0,70}", x)
           for x in versions.values()):
        raise ValueError("InvalidOrMissingRuntimePin")
    return versions


def pins_for(versions: dict[str, str]) -> list[str]:
    if not isinstance(versions, dict) or set(versions) != set(RUNTIME):
        raise ValueError("IncompleteRuntimeVersionSet")
    if any(not isinstance(v, str) or not re.fullmatch(r"[0-9][A-Za-z0-9.!+_-]{0,70}", v)
           for v in versions.values()):
        raise ValueError("BadVersionPin")
    # Extras must remain active, while their distribution name is uvicorn.
    pins = [("uvicorn[standard]" if n == "uvicorn" else n) + "==" + versions[n]
            for n in RUNTIME]
    return pins + ["pyinstaller==" + PINNED_PYINSTALLER,
                   "pyinstaller-hooks-contrib==" + PINNED_HOOKS]


def inspect_environment() -> dict:
    _safe(ENV_DIR)
    if not ENV_DIR.exists():
        return {"state": "ABSENT", "sidecar_built": False}
    # An incomplete, pre-existing environment is never overwritten.
    exe = python_for(ENV_DIR)
    if not exe.is_file() or exe.is_symlink():
        return {"state": "BLOCKED", "stage": "existing_incomplete_venv"}
    check = _run([str(exe), "-I", "-B", "-c",
                  "import sys, pathlib; assert pathlib.Path(sys.prefix).resolve() == pathlib.Path(" +
                  repr(str(ENV_DIR)) + ").resolve(); import PyInstaller, scipy, sklearn, reportlab"], 45)
    if check.returncode:
        return {"state": "BLOCKED", "stage": "existing_import_or_prefix_failure"}
    check = _run([str(exe), "-I", "-m", "pip", "--isolated", "check"], 45)
    if check.returncode:
        return {"state": "BLOCKED", "stage": "existing_dependency_conflicts"}
    return {"state": "EXISTING_BUILDER_REVIEW_REQUIRED",
            "release_lockfile": "NOT_APPROVED", "actual_sidecar_built": False}


def prepare(*, runner=_run) -> dict:
    if sys.platform != "win32":
        raise ValueError("WindowsOnly")
    check_requirements()
    versions = live_versions(runner=runner)
    _safe(ENV_DIR)
    if ENV_DIR.exists():
        return inspect_environment()
    if shutil.disk_usage(ROOT).free < MIN_DISK:
        return {"state": "BLOCKED", "stage": "disk_less_than_3gib"}
    # Directory creation is limited to the new ignored DevQA build root.
    BUILD_ROOT.mkdir(parents=True, exist_ok=True)
    _safe(BUILD_ROOT)
    created = runner([str(LIVE_PY), "-I", "-B", "-m", "venv", str(ENV_DIR)], 180)
    if created.returncode:
        return {"state": "BLOCKED", "stage": "isolated_venv_creation",
                "exit_code": created.returncode}
    _safe(ENV_DIR)
    exe = python_for(ENV_DIR)
    if not exe.is_file() or exe.is_symlink():
        return {"state": "BLOCKED", "stage": "new_python_missing"}
    pins = pins_for(versions)
    cmd = [str(exe), "-I", "-m", "pip", "--isolated",
           "--disable-pip-version-check", "--no-input", "--no-cache-dir",
           "install", "--only-binary=:all:", "--retries", "1",
           "--timeout", "25", "--index-url", OFFICIAL_INDEX,
           "-r", str(REQUIREMENTS), *pins]
    installed = runner(cmd, 1200)
    if installed.returncode:
        # Classify common pip failures without disclosing paths, URLs with
        # credentials, package logs or internal user data to the console.
        diagnostic = (str(installed.stderr or "") + " " + str(installed.stdout or "")).lower()[-12000:]
        if "resolutionimpossible" in diagnostic or "conflicting dependencies" in diagnostic:
            category = "dependency_resolution_conflict"
        elif "no matching distribution" in diagnostic or "could not find a version" in diagnostic:
            category = "required_binary_wheel_unavailable"
        elif "no space left on device" in diagnostic:
            category = "disk_space_exhausted"
        elif "timed out" in diagnostic or "connection" in diagnostic or "ssl" in diagnostic:
            category = "network_or_certificate_issue"
        else:
            category = "pip_install_failure_unclassified"
        return {"state": "BLOCKED", "stage": "full_runtime_wheel_resolution_or_install",
                "failure_category": category, "exit_code": installed.returncode}
    health = runner([str(exe), "-I", "-B", "-c",
                     "import fastapi,uvicorn,multipart,pandas,numpy,scipy,sklearn,openpyxl,joblib,pydantic,reportlab,PyInstaller;"
                     "import importlib.metadata as m;"
                     "assert m.version('pyinstaller')=='" + PINNED_PYINSTALLER + "';"
                     "assert m.version('pyinstaller-hooks-contrib')=='" + PINNED_HOOKS + "'"], 90)
    if health.returncode:
        return {"state": "BLOCKED", "stage": "new_environment_import_validation"}
    checked = runner([str(exe), "-I", "-m", "pip", "--isolated", "check"], 90)
    if checked.returncode:
        return {"state": "BLOCKED", "stage": "new_environment_dependency_conflict"}
    return {"state": "DEVQA_FULL_BUILDER_PREPARED",
            "runtime_direct_pins": len(RUNTIME),
            "tooling_versions": [PINNED_PYINSTALLER, PINNED_HOOKS],
            "release_lockfile": "NOT_APPROVED_TRANSITIVE_DEPS_RESOLVED_BY_PIP",
            "sidecar_built": False, "installer_built": False,
            "production_acceptance": "NOT_TESTED"}


def main() -> int:
    import argparse
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--prepare", action="store_true")
    args = ap.parse_args()
    try:
        if args.prepare:
            result = prepare()
        else:
            result = inspect_environment()
    except subprocess.TimeoutExpired:
        result = {"state": "BLOCKED", "stage": "bounded_subprocess_timeout"}
    except Exception as exc:
        result = {"state": "BLOCKED", "stage": "prerequisite",
                  "failure_class": type(exc).__name__}
    result.setdefault("sidecar_built", False)
    result.setdefault("installer_built", False)
    result.setdefault("production_acceptance", "NOT_TESTED")
    print("P2 ISOLATED FULL SIDECAR BUILDER: " + result["state"])
    print(json.dumps(result, indent=2))
    return 0 if result["state"] in {"DEVQA_FULL_BUILDER_PREPARED",
                                  "EXISTING_BUILDER_REVIEW_REQUIRED"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
