#!/usr/bin/env python3
"""P2-U2d: explicitly opt-in TRUE PilotODIN frozen backend DevQA, not release.

Builds backend/desktop_runner.py in a unique ignored directory using the
previously consented separate full scientific builder. A TEST-ONLY PyInstaller
runtime hook validates six source-pinned OFL font/notice bytes before importing
the real FastAPI app. Reuses the established disposable backend smoke contract.
NEVER calls the normal Tauri/NSIS staging builder or changes production code.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))
from p2_pdf_font_resource_path_devqa import REVIEW_PARENT, MANIFEST_PATH
from p2_pdf_frozen_font_onefile_devqa import verified_review_files, EXTRACTED_DEST
from p2_pdf_font_build_preflight import _not_redirected
from p2_pdf_font_asset_gate import hash_file
from p2_pdf_prepare_full_sidecar_builder import ENV_DIR, python_for, inspect_environment
from desktop.verify_packaged_engine import smoke_test_engine

OUTPUT_BASE = ROOT / "build" / "p2-sidecar-env" / "real-sidecar-proofs"
ENTRY = ROOT / "backend" / "desktop_runner.py"
HOOK_TEMPLATE = ROOT / "tools" / "p2_pdf_sidecar_font_hook_template.py"
NAME = "pilotodin-p2-real-engine-devqa"
HOOK_REPLACE = "PINNED_ASSETS = None  # P2_REPLACE_WITH_VERIFIED_SIX_FILE_LITERAL"
MIN_FREE = 4 * 1024**3
BUILD_TIMEOUT = 2100
STARTUP_SECONDS = 180


def _state(state: str, stage: str, **extra) -> dict:
    return {
        "state": state, "stage": stage,
        "actual_pilotodin_sidecar": ("SCOPED_DEVQA_PASS"
            if state == "SCOPED_REAL_SIDECAR_FONT_RUNTIME_PASS" else "NOT_VERIFIED"),
        "packaged_fonts": ("SIX_VERIFIED_IN_RUNTIME_HOOK"
            if state == "SCOPED_REAL_SIDECAR_FONT_RUNTIME_PASS" else "NOT_VERIFIED"),
        "product_unicode_pdf": "NOT_TESTED",
        "release_font_approval": "NOT_GRANTED",
        "native_installer": "NOT_TESTED",
        "runtime_hook_release_status": "DEVQA_ONLY_NOT_FOR_RELEASE",
        "peak_memory": "NOT_MEASURED", **extra,
    }


def write_hook(template: str, entries: list[dict], output: Path) -> None:
    if template.count(HOOK_REPLACE) != 1:
        raise ValueError("Hook substitution marker missing or duplicated")
    if len(entries) != 6 or len({x["name"] for x in entries}) != 6:
        raise ValueError("Exactly six code-pinned identities needed")
    generated = template.replace(HOOK_REPLACE, "PINNED_ASSETS = " + repr(entries))
    compile(generated, str(output), "exec")
    with output.open("x", encoding="utf-8") as handle:
        handle.write(generated)


def pyinstaller_args(py: Path, inputs: Path, hook: Path, output: Path) -> list[str]:
    if sys.platform != "win32":
        raise ValueError("Windows frozen engine only")
    if not ENTRY.is_file() or not hook.is_file() or not inputs.is_dir():
        raise ValueError("Real sidecar build input missing")
    return [
        str(py), "-I", "-m", "PyInstaller",
        "--noconfirm", "--onefile", "--console", "--noupx",
        "--log-level", "WARN",
        "--name", NAME,
        "--paths", str(ROOT),
        "--collect-all", "sklearn",
        "--collect-all", "scipy",
        "--collect-submodules", "sklearn",
        "--hidden-import", "uvicorn.logging",
        "--hidden-import", "uvicorn.loops.auto",
        "--hidden-import", "uvicorn.protocols.http.auto",
        "--hidden-import", "uvicorn.protocols.websockets.auto",
        "--hidden-import", "uvicorn.lifespan.on",
        "--hidden-import", "backend.pdf_font_resources",
        "--runtime-hook", str(hook),
        "--add-data", str(inputs) + ":" + EXTRACTED_DEST,
        "--distpath", str(output / "dist"),
        "--workpath", str(output / "work"),
        "--specpath", str(output / "spec"),
        str(ENTRY),
    ]


def run_real_sidecar(
    run: Path, reviewed: Path, entries: list[dict], *,
    subprocess_run=subprocess.run, smoke=smoke_test_engine,
) -> dict:
    """One dev-only build; never overwrite a previous proof or app executable."""
    locations = {
        n: run / n for n in ("dist", "work", "spec", "inputs",
                            "cache", "temp", "unrelated-cwd")
    }
    for p in locations.values():
        p.mkdir(exist_ok=False)
    if shutil.disk_usage(run).free < MIN_FREE:
        return _state("BLOCKED", "free_disk_under_4gib")
    if inspect_environment().get("state") != "EXISTING_BUILDER_REVIEW_REQUIRED":
        return _state("BLOCKED", "full_builder_import_or_dependency_check")
    py = python_for(ENV_DIR)
    if not py.is_file() or py.is_symlink():
        return _state("BLOCKED", "full_builder_missing")
    if len(entries) != 6:
        return _state("BLOCKED", "incomplete_font_identities")
    before = {x["name"]: x["sha256"] for x in entries}
    if len(before) != 6:
        return _state("BLOCKED", "duplicate_font_identifiers")
    for entry in entries:
        filename = entry["name"]
        source = reviewed / filename
        _not_redirected(source)
        if not source.is_file() or hash_file(source)[1] != entry["sha256"]:
            return _state("BLOCKED", "font_source_changed")
        dest = locations["inputs"] / filename
        with source.open("rb") as src, dest.open("xb") as dst:
            shutil.copyfileobj(src, dst, length=1024 * 1024)
        if hash_file(dest)[1] != entry["sha256"]:
            return _state("FAIL", "copied_font_integrity")
    if {p.name for p in locations["inputs"].iterdir()} != set(before):
        return _state("FAIL", "unexpected_packaged_file")
    hook = run / "p2-devqa-runtime-hook.py"
    write_hook(HOOK_TEMPLATE.read_text(encoding="utf-8"), entries, hook)
    command = pyinstaller_args(py, locations["inputs"], hook, run)
    environment = dict(os.environ)
    environment.update({"PYINSTALLER_CONFIG_DIR": str(locations["cache"]),
                        "TMP": str(locations["temp"]), "TEMP": str(locations["temp"]),
                        "PYTHONNOUSERSITE": "1", "PYTHONDONTWRITEBYTECODE": "1"})
    for key in ("PYTHONPATH", "PYTHONHOME", "PILOTODIN_HOME",
                "PILOTODIN_DESKTOP_SESSION", "PILOTODIN_DESKTOP_PORT",
                "PILOTODIN_P2_REAL_SIDECAR_DEVQA"):
        environment.pop(key, None)
    buildlog = run / "pyinstaller-private.log"
    print("Building actual FastAPI/scientific sidecar in a NEW ignored DevQA folder.", flush=True)
    started = time.monotonic()
    with buildlog.open("xb") as output:
        built = subprocess_run(command, cwd=ROOT, env=environment,
                              stdout=output, stderr=subprocess.STDOUT,
                              timeout=BUILD_TIMEOUT, check=False)
    seconds = round(time.monotonic() - started, 2)
    if built.returncode:
        return _state("BLOCKED", "real_sidecar_pyinstaller",
                      build_exit_code=built.returncode)
    exe = locations["dist"] / (NAME + ".exe")
    if not exe.is_file() or exe.is_symlink() or exe.stat().st_size <= 0:
        return _state("BLOCKED", "real_sidecar_executable_missing")
    for entry in entries:
        if (hash_file(reviewed / entry["name"])[1] != entry["sha256"] or
                hash_file(locations["inputs"] / entry["name"])[1] != entry["sha256"]):
            return _state("FAIL", "font_changed_during_build")
    # The isolated existing smoke function uses a random loopback port, random
    # session token, fresh temporary user home/SQLite, 401/403 checks, and
    # always terminates the entire Windows frozen process tree.
    # A working HTTP API proves that the fail-closed PyInstaller runtime hook
    # executed before the real app, otherwise the frozen interpreter exits.
    previous = os.environ.get("PILOTODIN_P2_REAL_SIDECAR_DEVQA")
    os.environ["PILOTODIN_P2_REAL_SIDECAR_DEVQA"] = "1"
    print("Executing REAL frozen engine with disposable token, home and SQLite.", flush=True)
    started = time.monotonic()
    try:
        observed = smoke([str(exe)], ROOT, STARTUP_SECONDS)
    except Exception as exc:
        return _state("FAIL", "real_sidecar_isolated_smoke",
                      failure_class=type(exc).__name__)
    finally:
        if previous is None:
            os.environ.pop("PILOTODIN_P2_REAL_SIDECAR_DEVQA", None)
        else:
            os.environ["PILOTODIN_P2_REAL_SIDECAR_DEVQA"] = previous
    smoke_seconds = round(time.monotonic() - started, 2)
    if (not isinstance(observed, dict) or
            any(observed.get(x) is not True for x in
                ("passed", "auth_required", "wrong_origin_rejected", "user_storage_isolated")) or
            observed.get("model_started") is not False):
        return _state("FAIL", "real_sidecar_smoke_contract")
    exe_size, exe_sha, _ = hash_file(exe)
    return _state("SCOPED_REAL_SIDECAR_FONT_RUNTIME_PASS", "completed",
                  actual_scientific_engine=True,
                  disposable_session_and_storage=True,
                  auth_and_origin_checks=True,
                  model_started=False,
                  exe_bytes=exe_size, exe_sha256=exe_sha,
                  build_seconds=seconds, smoke_seconds=smoke_seconds,
                  release_policy="DEVQA_BUILD_ONLY_NOT_DISTRIBUTABLE")


def main() -> int:
    argp = argparse.ArgumentParser(description=__doc__)
    argp.add_argument("--build", action="store_true")
    args = argp.parse_args()
    result = _state("BLOCKED", "explicit_consent_required")
    if args.build:
        phase = "os_prerequisite"
        try:
            if os.name != "nt":
                raise ValueError("WindowsOnly")
            phase = "source_font_review"
            manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
            reviewed, entries = verified_review_files(REVIEW_PARENT, manifest)
            phase = "devqa_output_root"
            _not_redirected(OUTPUT_BASE)
            OUTPUT_BASE.mkdir(parents=True, exist_ok=True)
            _not_redirected(OUTPUT_BASE)
            run = OUTPUT_BASE / ("run-" + uuid.uuid4().hex)
            run.mkdir(exist_ok=False)
            try:
                result = run_real_sidecar(run, reviewed, entries)
            except subprocess.TimeoutExpired:
                result = _state("BLOCKED", "build_or_smoke_timeout")
            except Exception as exc:
                result = _state("BLOCKED", "sidecar_devqa_execution",
                                failure_class=type(exc).__name__)
            result["run_id"] = run.name
        except Exception as exc:
            result = _state("BLOCKED", phase, failure_class=type(exc).__name__)
    print("P2 REAL SIDECAR FONT DEVQA: " + result["state"])
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["state"] == "SCOPED_REAL_SIDECAR_FONT_RUNTIME_PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
