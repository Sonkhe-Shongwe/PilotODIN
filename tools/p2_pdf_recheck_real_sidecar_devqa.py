#!/usr/bin/env python3
"""P2-U2d follow-up: reuse one existing isolated frozen engine, never rebuild.

The first owner run reached the final executable fingerprint and returned a
ValueError because the FONT-only 32 MiB size gate was reused for a full engine.
This separate DevQA check reads the prior ignored build, validates its original
six-file hook attestation and exact pinned staged sources, then re-executes ONLY
the established disposable auth/SQLite smoke with a fresh hook attestation.
Neither pip, PyInstaller, Tauri, production reports nor user projects are run.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import sys
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

from p2_pdf_font_resource_path_devqa import REVIEW_PARENT, MANIFEST_PATH
from p2_pdf_frozen_font_onefile_devqa import verified_review_files
from p2_pdf_font_build_preflight import _not_redirected
from p2_pdf_font_asset_gate import hash_file
from p2_pdf_real_sidecar_font_devqa import (
    OUTPUT_BASE, NAME, HOOK_TEMPLATE, HOOK_REPLACE, STARTUP_SECONDS,
    expected_attestation, fingerprint_frozen_executable, _state,
)
from desktop.verify_packaged_engine import smoke_test_engine

RUN_NAME = re.compile(r"run-[0-9a-f]{32}\Z")
RECHECK_ROOT = OUTPUT_BASE
REQUIRED_SMOKE_FLAGS = ("passed", "auth_required", "wrong_origin_rejected",
                        "user_storage_isolated")


def inspect_stored_run(run_id: str) -> tuple[Path, list[dict], int, str]:
    """No writes: accept only our unchanged and previously attested DevQA build."""
    if not isinstance(run_id, str) or not RUN_NAME.fullmatch(run_id):
        raise ValueError("InvalidRunIdentifier")
    _not_redirected(RECHECK_ROOT)
    prior = RECHECK_ROOT / run_id
    _not_redirected(prior)
    if not prior.is_dir():
        raise ValueError("PriorDevQARunAbsent")
    exe = prior / "dist" / (NAME + ".exe")
    hook = prior / "p2-devqa-runtime-hook.py"
    receipt = prior / "font-attestation.json"
    inputs = prior / "inputs"
    for path in (exe, hook, receipt, inputs):
        _not_redirected(path)
    if not inputs.is_dir() or not hook.is_file() or not receipt.is_file():
        raise ValueError("PriorDevQAArtifactsIncomplete")
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    reviewed, entries = verified_review_files(REVIEW_PARENT, manifest)
    if len(entries) != 6:
        raise ValueError("PinnedSixResourceReviewIncomplete")
    if {p.name for p in inputs.iterdir()} != {e["name"] for e in entries}:
        raise ValueError("PriorStagedResourceSetMismatch")
    for item in entries:
        staged = inputs / item["name"]
        source = reviewed / item["name"]
        for asset in (staged, source):
            _not_redirected(asset)
            if (not asset.is_file() or asset.stat().st_size != item["bytes"]
                    or hash_file(asset)[1] != item["sha256"]):
                raise ValueError("PriorSourceOrStagedAssetChanged")
    template = HOOK_TEMPLATE.read_text(encoding="utf-8")
    if template.count(HOOK_REPLACE) != 1:
        raise ValueError("RuntimeHookTemplateChanged")
    expected_hook = template.replace(HOOK_REPLACE, "PINNED_ASSETS = " + repr(entries))
    if hook.read_text(encoding="utf-8") != expected_hook:
        raise ValueError("PriorGeneratedHookMismatch")
    if receipt.stat().st_size > 4096 or json.loads(
            receipt.read_text(encoding="utf-8")) != expected_attestation(entries):
        raise ValueError("PriorFrozenHookAttestationMissingOrInvalid")
    size, sha = fingerprint_frozen_executable(exe)
    return exe, entries, size, sha


def recheck_existing_run(run_id: str, *, smoke=smoke_test_engine) -> dict:
    """One new proof directory, no recompilation or mutation of original run."""
    try:
        exe, entries, size, sha = inspect_stored_run(run_id)
    except Exception as exc:
        return _state("BLOCKED", "previous_frozen_run_review",
                      failure_class=type(exc).__name__)
    _not_redirected(RECHECK_ROOT)
    new_run = RECHECK_ROOT / ("run-" + uuid.uuid4().hex)
    new_run.mkdir(exist_ok=False)
    _not_redirected(new_run)
    proof = new_run / "font-attestation.json"
    previous = {key: os.environ.get(key) for key in
                ("PILOTODIN_P2_REAL_SIDECAR_DEVQA",
                 "PILOTODIN_P2_DEVQA_ATTESTATION")}
    os.environ["PILOTODIN_P2_REAL_SIDECAR_DEVQA"] = "1"
    os.environ["PILOTODIN_P2_DEVQA_ATTESTATION"] = str(proof.resolve())
    try:
        observed = smoke([str(exe)], ROOT, STARTUP_SECONDS)
    except Exception as exc:
        return _state("FAIL", "reused_real_sidecar_isolated_smoke",
                      failure_class=type(exc).__name__, proof_run_id=new_run.name)
    finally:
        for key, prior_value in previous.items():
            if prior_value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = prior_value
    if (not isinstance(observed, dict) or
            any(observed.get(key) is not True for key in REQUIRED_SMOKE_FLAGS) or
            observed.get("model_started") is not False):
        return _state("FAIL", "reused_real_sidecar_smoke_contract",
                      proof_run_id=new_run.name)
    if not proof.is_file() or proof.is_symlink() or proof.stat().st_size > 4096:
        return _state("FAIL", "fresh_frozen_hook_attestation_missing",
                      proof_run_id=new_run.name)
    try:
        actual_receipt = json.loads(proof.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError):
        return _state("FAIL", "fresh_frozen_hook_attestation_invalid",
                      proof_run_id=new_run.name)
    if actual_receipt != expected_attestation(entries):
        return _state("FAIL", "fresh_frozen_hook_attestation_mismatch",
                      proof_run_id=new_run.name)
    try:
        after_size, after_sha = fingerprint_frozen_executable(exe)
    except Exception as exc:
        return _state("FAIL", "reused_executable_fingerprint",
                      failure_class=type(exc).__name__, proof_run_id=new_run.name)
    if (size, sha) != (after_size, after_sha):
        return _state("FAIL", "reused_executable_changed",
                      proof_run_id=new_run.name)
    return _state("SCOPED_REAL_SIDECAR_FONT_RUNTIME_PASS", "reused_frozen_engine_completed",
                  actual_scientific_engine=True, reused_existing_frozen_build=True,
                  original_build_run_id=run_id, proof_run_id=new_run.name,
                  disposable_session_and_storage=True, auth_and_origin_checks=True,
                  model_started=False, exe_bytes=size, exe_sha256=sha,
                  release_policy="DEVQA_BUILD_ONLY_NOT_DISTRIBUTABLE")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", required=True)
    options = parser.add_mutually_exclusive_group(required=True)
    options.add_argument("--inspect", action="store_true")
    options.add_argument("--recheck", action="store_true")
    args = parser.parse_args()
    if args.inspect:
        try:
            _, _, size, sha = inspect_stored_run(args.run_id)
            result = _state("PRIOR_REAL_SIDECAR_READY_FOR_SCOPED_RECHECK",
                            "prior_attestation_and_executable_inspected",
                            prior_run_id=args.run_id, exe_bytes=size,
                            exe_sha256=sha)
        except Exception as exc:
            result = _state("BLOCKED", "previous_frozen_run_review",
                            failure_class=type(exc).__name__)
    else:
        try:
            result = recheck_existing_run(args.run_id)
        except Exception as exc:
            result = _state("BLOCKED", "isolated_recheck_setup",
                            failure_class=type(exc).__name__)
    print("P2 EXISTING REAL SIDECAR RECHECK DEVQA: " + result["state"])
    print(json.dumps(result, indent=2))
    return 0 if result["state"] in {
        "PRIOR_REAL_SIDECAR_READY_FOR_SCOPED_RECHECK",
        "SCOPED_REAL_SIDECAR_FONT_RUNTIME_PASS"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
