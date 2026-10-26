#!/usr/bin/env python3
"""P2-U2a: opt-in stand-alone PyInstaller ONEFILE resource proof for DevQA.

This NEVER packages or runs PilotODIN's actual desktop_runner.py, Tauri or
an installer. It reads one earlier verified ignored build-review folder,
uses existing PyInstaller >=6 in .venv-live, and builds a unique ignored probe
containing only six pinned candidate font/OFL resources and the tiny verifier.
It never uses pip, a network downloader, user projects or installed fonts.

PASS proves the extracted resources are reachable and match source SHA-256s
inside THIS frozen probe; NOT that fonts are release-approved or working in
the production sidecar.
"""
from __future__ import annotations

import argparse
import hashlib
from importlib import metadata
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
from p2_pdf_font_resource_path_devqa import REVIEW_PARENT, MANIFEST_PATH, review_staged_copy
from p2_pdf_font_build_preflight import _expected, _not_redirected
from p2_pdf_font_asset_gate import hash_file

BUILD_ROOT = ROOT / "build" / "p2-pdf-frozen-resource-probe"
EXTRACTED_DEST = "backend/assets/pdf_fonts"
PROBE_ENTRY = ROOT / "tools" / "p2_pdf_frozen_font_worker.py"
TIMEOUT_BUILD_SECONDS = 900
TIMEOUT_RUN_SECONDS = 120


def verified_review_files(parent: Path, manifest: dict) -> tuple[Path, list[dict]]:
    """Re-check receipt, all six pinned bytes and complete OFL notices."""
    decision = review_staged_copy(parent, manifest)
    if decision["state"] != "BUILD_REVIEW_RESOURCE_PATH_CONTRACT_PASS":
        raise ValueError("Existing font review is not accepted")
    candidates = [p for p in parent.iterdir() if p.name.startswith("review-")]
    if len(candidates) != 1:
        raise ValueError("Expected exactly one reviewed font bundle")
    review = candidates[0]
    _not_redirected(review)
    assets = []
    for role, name, size, git_oid, kind in _expected(manifest):
        source = review / name
        _not_redirected(source)
        if not source.is_file():
            raise ValueError("Missing reviewed font or OFL source")
        length, sha, identity = hash_file(source)
        if length != size or identity != git_oid:
            raise ValueError("Font review bytes changed")
        assets.append({"role": role, "kind": kind,
                       "name": name, "bytes": size, "sha256": sha})
    if len(assets) != 6:
        raise ValueError("Incomplete approved-for-review set")
    return review, assets


def detect_existing_pyinstaller() -> str:
    """Use only installed PyInstaller 6; never install from this DevQA gate."""
    try:
        version = metadata.version("pyinstaller")
    except metadata.PackageNotFoundError as exc:
        raise RuntimeError("PyInstallerMissing") from exc
    try:
        major = int(version.split(".", 1)[0])
    except ValueError as exc:
        raise RuntimeError("PyInstallerVersionUnreadable") from exc
    if major != 6:
        raise RuntimeError("PyInstaller6Required")
    return version


def build_arguments(source: Path, assets: list[dict], output: Path) -> list[str]:
    """Single frozen worker, six file-specific --add-data, isolated dirs only."""
    if sys.platform != "win32":
        raise ValueError("Windows-only PyInstaller resource proof")
    if not PROBE_ENTRY.is_file():
        raise ValueError("DevQA probe worker missing")
    names = [v["name"] for v in assets]
    if len(names) != 6 or len(set(names)) != 6 or any(
            not isinstance(n, str) or Path(n).name != n or
            "/" in n or "\\" in n or n in (".", "..")
            for n in names):
        raise ValueError("Six safe named inputs required")
    name = "pilotodin-p2-frozen-font-probe"
    command = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm", "--onefile", "--console", "--noupx",
        "--log-level", "ERROR",
        "--name", name,
        "--paths", str(ROOT),
        "--distpath", str(output / "dist"),
        "--workpath", str(output / "work"),
        "--specpath", str(output / "spec"),
    ]
    # One freshly created six-file directory avoids PyInstaller treating the
    # Noto variable-font [brackets] in individual source paths as glob syntax.
    # The source directory must contain exactly the six verified filenames.
    if not source.is_dir() or {p.name for p in source.iterdir()} != set(names):
        raise ValueError("Isolated PyInstaller input is incomplete")
    command.extend(["--add-data", str(source) + ":" + EXTRACTED_DEST])
    command.append(str(PROBE_ENTRY))
    return command


def _outcome(state: str, *, stage: str, **fields) -> dict:
    return {
        "state": state,
        "stage": stage,
        "actual_frozen_probe": ("PASS" if state == "SCOPED_FROZEN_RESOURCE_PROBE_PASS"
                                else "NOT_VERIFIED"),
        "actual_pilotodin_sidecar": "NOT_TESTED",
        "actual_installer": "NOT_TESTED",
        "release_font_approval": "NOT_GRANTED",
        "product_unicode_acceptance": "NOT_TESTED",
        **fields,
    }


def run_onefile_proof(run_dir: Path, assets: list[dict], reviewed: Path,
                      *, subprocess_run=subprocess.run) -> dict:
    """Produce and execute a standalone executable. No old run is overwritten."""
    spec = run_dir / "spec"
    work = run_dir / "work"
    dist = run_dir / "dist"
    cwd = run_dir / "unrelated-working-directory"
    cache = run_dir / "pyinstaller-cache"
    temp = run_dir / "onefile-extract-temp"
    inputs = run_dir / "six-verified-build-inputs"
    for path in (spec, work, dist, cwd, cache, temp, inputs):
        path.mkdir(exist_ok=False)
    if shutil.disk_usage(run_dir).free < 750 * 1024 * 1024:
        raise RuntimeError("InsufficientIsolatedBuildDiskSpace")
    pyinstaller_version = detect_existing_pyinstaller()
    before = [(row["name"], hash_file(reviewed / row["name"])[1]) for row in assets]
    if any(before[i][1] != assets[i]["sha256"] for i in range(6)):
        raise ValueError("Reviewed source changed before build")
    # No receipt or sidecar binaries are copied. Preserve original glyph/font
    # names inside the bundle, but never pass bracketed filenames to globbing.
    for asset in assets:
        dest = inputs / asset["name"]
        with (reviewed / asset["name"]).open("rb") as original, dest.open("xb") as target:
            shutil.copyfileobj(original, target, length=1024 * 1024)
        count, copied_sha, _ = hash_file(dest)
        if count != asset["bytes"] or copied_sha != asset["sha256"]:
            raise ValueError("Isolated PyInstaller input hash mismatch")
    command = build_arguments(inputs, assets, run_dir)
    isolated_environment = dict(os.environ)
    isolated_environment["PYINSTALLER_CONFIG_DIR"] = str(cache)
    isolated_environment["TMP"] = str(temp)
    isolated_environment["TEMP"] = str(temp)
    for key in ("PILOTODIN_HOME", "PILOTODIN_DESKTOP_SESSION",
                "PILOTODIN_DESKTOP_PORT", "PYTHONPATH"):
        isolated_environment.pop(key, None)
    print("Running isolated PyInstaller 6 ONEFILE DevQA build (not the app).", flush=True)
    started = time.monotonic()
    built = subprocess_run(command, cwd=ROOT, env=isolated_environment,
                          capture_output=True, text=True,
                          timeout=TIMEOUT_BUILD_SECONDS, check=False)
    elapsed_build = round(time.monotonic() - started, 2)
    if built.returncode != 0:
        return _outcome("BLOCKED", stage="pyinstaller_build",
                        reason="build_nonzero", exit_code=built.returncode,
                        pyinstaller=pyinstaller_version)
    exe = dist / "pilotodin-p2-frozen-font-probe.exe"
    if not exe.is_file() or exe.is_symlink() or exe.stat().st_size <= 0:
        return _outcome("BLOCKED", stage="executable_missing")
    # Source before/after + frozen-child digest must agree; bundle contents
    # cannot be accepted on the strength of a mutable adjacent receipt alone.
    after = [(row["name"], hash_file(reviewed / row["name"])[1]) for row in assets]
    staged_after = [(row["name"], hash_file(inputs / row["name"])[1]) for row in assets]
    if before != after or before != staged_after:
        return _outcome("FAIL", stage="source_changed_during_packaging")
    payload = json.dumps({"schema": 1, "assets": assets}, separators=(",", ":"))
    print("Executing frozen worker from a different empty working directory.", flush=True)
    started = time.monotonic()
    child = subprocess_run([str(exe)], input=payload, cwd=cwd, env=isolated_environment,
                           capture_output=True, text=True,
                           timeout=TIMEOUT_RUN_SECONDS, check=False)
    elapsed_run = round(time.monotonic() - started, 2)
    try:
        reported = json.loads(child.stdout.strip())
    except (ValueError, AttributeError):
        return _outcome("BLOCKED", stage="worker_invalid_output",
                        worker_exit_code=child.returncode)
    if isinstance(reported, dict) and reported.get("state") == "BLOCKED":
        return _outcome("BLOCKED", stage="frozen_worker_prerequisite",
                        worker_exit_code=child.returncode,
                        failure_class=reported.get("failure_class", "WorkerBlocked"))
    if (not isinstance(reported, dict) or
            child.returncode != 0 or
            reported.get("schema") != 1 or
            reported.get("state") != "FROZEN_RESOURCE_VERIFIED" or
            reported.get("frozen") is not True or
            reported.get("inside_pyinstaller_bundle") is not True or
            reported.get("embedded_file_count") != 6 or
            reported.get("resource_location") != EXTRACTED_DEST or
            reported.get("product_sidecar_tested") is not False):
        return _outcome("FAIL", stage="frozen_worker_verification",
                        worker_exit_code=child.returncode,
                        worker_state=reported.get("state") if isinstance(reported, dict)
                        else "INVALID")
    exe_hash = hashlib.sha256()
    with exe.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            exe_hash.update(chunk)
    return _outcome(
        "SCOPED_FROZEN_RESOURCE_PROBE_PASS", stage="completed",
        bundled_six_files_verified=True, mapped_location=EXTRACTED_DEST,
        pyinstaller=pyinstaller_version,
        exe_bytes=exe.stat().st_size, exe_sha256=exe_hash.hexdigest(),
        build_seconds=elapsed_build, frozen_start_seconds=elapsed_run,
        peak_memory="NOT_MEASURED",
        release_policy="BUILD_REVIEW_ONLY_NOT_DISTRIBUTABLE",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build", action="store_true",
                        help="Explicit consent for isolated frozen DevQA build")
    args = parser.parse_args()
    if not args.build:
        result = _outcome("BLOCKED", stage="consent_required")
    else:
        try:
            if os.name != "nt":
                raise ValueError("Windows-only gate")
            manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
            reviewed, assets = verified_review_files(REVIEW_PARENT, manifest)
            _not_redirected(BUILD_ROOT)
            BUILD_ROOT.mkdir(parents=True, exist_ok=True)
            _not_redirected(BUILD_ROOT)
            run_dir = BUILD_ROOT / ("probe-" + uuid.uuid4().hex)
            run_dir.mkdir(exist_ok=False)
            try:
                result = run_onefile_proof(run_dir, assets, reviewed)
            except subprocess.TimeoutExpired:
                result = _outcome("BLOCKED", stage="subprocess_timeout")
            except Exception as exc:
                result = _outcome("BLOCKED", stage="probe_setup_or_execution",
                                  failure_class=type(exc).__name__,
                                  reason=str(exc) if str(exc) in {
                                      "PyInstallerMissing", "PyInstaller6Required",
                                      "PyInstallerVersionUnreadable"} else "inspect_setup")
            result["run_id"] = run_dir.name
        except Exception as exc:
            result = _outcome("BLOCKED", stage="source_or_build_preflight",
                              failure_class=type(exc).__name__)
    print("P2 ACTUAL ONEFILE RESOURCE DEVQA: " + result["state"])
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["state"] == "SCOPED_FROZEN_RESOURCE_PROBE_PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
