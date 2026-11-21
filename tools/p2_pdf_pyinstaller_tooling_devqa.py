#!/usr/bin/env python3
"""Opt-in, isolated PyInstaller tooling preparation for P2 ONEFILE DevQA.

NEVER change .venv-live, .venv, application requirements or installed software.
The only new dependencies go inside:
    build/p2-pdf-frozen-resource-probe/tooling-venv/
which is ignored by Git and never used in the released PilotODIN app.
Requires explicit --prepare from the consent-based launcher. Package downloads
are possible only after affirmative consent in that separate launcher.
"""
from __future__ import annotations

from pathlib import Path
import json
import os
import re
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
TOOLING = ROOT / "build" / "p2-pdf-frozen-resource-probe" / "tooling-venv"
INSTALLER_VERSION = "6.22.3"
HOOKS_VERSION = "2026.9"
OFFICIAL_INDEX = "https://pypi.org/simple"
MAX_SETUP_SECONDS = 150
MAX_INSTALL_SECONDS = 420


def _not_redirected(location: Path) -> None:
    for entry in (location, *location.parents):
        if entry.is_symlink() or (
                entry.exists() and getattr(os.path, "isjunction", lambda _: False)(entry)):
            raise ValueError("Redirected tooling location")


def tooling_python(path: Path = TOOLING) -> Path:
    return path / "Scripts" / "python.exe"


def _run(command: list[str], *, seconds: int) -> subprocess.CompletedProcess:
    if not command or any(not isinstance(x, str) or not x for x in command):
        raise ValueError("Invalid tooling subprocess command")
    environment = dict(os.environ)
    environment["PYTHONNOUSERSITE"] = "1"
    environment["PIP_CONFIG_FILE"] = os.devnull
    for key in ("PILOTODIN_HOME", "PILOTODIN_DESKTOP_SESSION",
                "PILOTODIN_DESKTOP_PORT", "PYTHONPATH", "PIP_INDEX_URL",
                "PIP_EXTRA_INDEX_URL", "PIP_FIND_LINKS"):
        environment.pop(key, None)
    return subprocess.run(command, cwd=ROOT, env=environment,
                          capture_output=True, text=True,
                          timeout=seconds, check=False)


def inspect_tooling(path: Path = TOOLING) -> dict:
    """Check tool presence and exact versions in this dedicated venv only."""
    _not_redirected(path)
    exe = tooling_python(path)
    if not exe.is_file() or exe.is_symlink():
        return {"state": "BLOCKED", "stage": "isolated_tooling_missing"}
    command = [
        str(exe), "-I", "-c",
        ("import json,sys,importlib.metadata as m,pathlib,PyInstaller;"
         "p=pathlib.Path(sys.prefix).resolve();"
         "print(json.dumps({'prefix':str(p),"
         "'pyinstaller':m.version('pyinstaller'),"
         "'hooks':m.version('pyinstaller-hooks-contrib')}))")
    ]
    completed = _run(command, seconds=30)
    if completed.returncode != 0:
        return {"state": "BLOCKED", "stage": "tooling_import_failure",
                "exit_code": completed.returncode}
    try:
        versions = json.loads(completed.stdout)
    except (ValueError, TypeError):
        return {"state": "BLOCKED", "stage": "tooling_invalid_output"}
    if (not isinstance(versions, dict) or
            Path(versions.get("prefix", "")).resolve() != path.resolve() or
            versions.get("pyinstaller") != INSTALLER_VERSION or
            versions.get("hooks") != HOOKS_VERSION):
        return {"state": "BLOCKED", "stage": "tooling_version_or_path_mismatch"}
    return {"state": "ISOLATED_PYINSTALLER_READY",
            "pyinstaller": INSTALLER_VERSION,
            "hooks": HOOKS_VERSION,
            "scope": "DEVQA_TOOLING_ONLY",
            "production_dependencies_modified": False}


def prepare_tooling(root: Path = TOOLING) -> dict:
    if sys.platform != "win32":
        raise RuntimeError("WindowsOnly")
    _not_redirected(root)
    if root.exists() or root.is_symlink():
        # Never repair an existing incomplete environment by overwriting it.
        return inspect_tooling(root)
    if shutil.disk_usage(root.parent if root.parent.exists() else ROOT).free < 400 * 1024 * 1024:
        raise RuntimeError("InsufficientToolingDiskSpace")
    root.parent.mkdir(parents=True, exist_ok=True)
    _not_redirected(root.parent)
    setup = _run([sys.executable, "-I", "-m", "venv", str(root)],
                 seconds=MAX_SETUP_SECONDS)
    if setup.returncode != 0:
        return {"state": "BLOCKED", "stage": "isolated_venv_creation",
                "exit_code": setup.returncode}
    exe = tooling_python(root)
    if not exe.is_file():
        return {"state": "BLOCKED", "stage": "isolated_python_missing"}
    # This is a deliberately opt-in network installation to a newly created,
    # Git-ignored isolated developer environment. No global pip/config usage.
    packages = [
        f"pyinstaller=={INSTALLER_VERSION}",
        f"pyinstaller-hooks-contrib=={HOOKS_VERSION}",
    ]
    installed = _run([
        str(exe), "-I", "-m", "pip",
        "--isolated", "--disable-pip-version-check", "--no-input",
        "--no-cache-dir", "install", "--only-binary=:all:",
        "--index-url", OFFICIAL_INDEX, *packages,
    ], seconds=MAX_INSTALL_SECONDS)
    if installed.returncode != 0:
        return {"state": "BLOCKED", "stage": "pypi_tooling_install",
                "exit_code": installed.returncode}
    return inspect_tooling(root)


def main() -> int:
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prepare", action="store_true",
                        help="Requires separate interactive launcher consent")
    args = parser.parse_args()
    try:
        if args.prepare:
            decision = prepare_tooling()
        else:
            decision = inspect_tooling()
    except subprocess.TimeoutExpired:
        decision = {"state": "BLOCKED", "stage": "tooling_timeout"}
    except Exception as exc:
        decision = {"state": "BLOCKED", "stage": "tooling_prerequisite",
                    "failure_class": type(exc).__name__}
    # Only safe, non-sensitive metadata; never log pip paths, credentials,
    # wheel content, user data, full tracebacks or font binaries.
    decision.setdefault("production_dependencies_modified", False)
    decision.setdefault("product_acceptance", "NOT_TESTED")
    print("P2 ISOLATED PYINSTALLER TOOLING: " + decision["state"])
    print(json.dumps(decision, ensure_ascii=False, indent=2))
    return 0 if decision["state"] == "ISOLATED_PYINSTALLER_READY" else 2


if __name__ == "__main__":
    raise SystemExit(main())
