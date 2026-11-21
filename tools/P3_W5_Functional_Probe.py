#!/usr/bin/env python3
"""Observe isolated P3 W5 data correctness independently of native window exit.

Runs concurrently with the real Windows Tauri QA window. Never approves a
Quality correction. The only write attempted is a deliberately stale semantic
POST that MUST be rejected with HTTP 409. Writes a bounded diagnostic JSON in
the disposable DevQA run, not to any user dataset or source checkout.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path, PureWindowsPath
import re
import sys
import time
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from tools.Seed_P3_Native_Quality_W5_Local import PHASE, source_bytes
from tools.Verify_P3_Native_Quality_W5_History_Local import verify as verify_history

PASS_FIELDS = {
    "quality_version": "PASS_V0_TO_V1",
    "version_history": "PASS_EXACTLY_V0_V1",
    "current_semantic_context": "PASS_EMPTY_V1",
    "historical_semantic_context": "PASS_V0_RETAINED_V1_ABSENT",
    "stale_semantic_get": "PASS_HTTP_409",
    "stale_semantic_post": "PASS_HTTP_409",
    "original_sha256": "PASS_UNCHANGED",
    "request_audit": "PASS_ONE_PROPOSAL_ONE_UI_COMMIT_ONE_REJECTED_STALE_POST",
}
API = "http://127.0.0.1:8000/api"
MAX_SECONDS = 900  # Time for owner to review and approve one synthetic correction.


class ProbeFailure(ValueError):
    """Synthetic data invariants were not established."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ProbeFailure(message)


def assess_functional_snapshot(
    quality: dict[str, Any],
    history: dict[str, Any],
    current: dict[str, Any],
    preview: dict[str, Any],
) -> None:
    """The same contracts must be satisfied in a good and deliberately bad test."""
    require(quality.get("version") == 1, "QUALITY_VERSION_NOT_ONE")
    versions = [item.get("version") for item in history.get("versions", [])]
    require(history.get("current_version") == 1 and versions == [0, 1],
            "HISTORY_NOT_EXACTLY_V0_V1")
    require(current.get("version") == 1 and current.get("user_context") is None,
            "V1_CONTEXT_NOT_EMPTY")
    rows = preview.get("rows", [])
    require(preview.get("version") == 1 and len(rows) >= 3,
            "V1_PREVIEW_UNEXPECTED")
    for index in (1, 2):
        row = rows[index]
        require(row.get("original", {}).get("Region") == " Mpumalanga " and
                row.get("working", {}).get("Region") == "Mpumalanga",
                "REGION_CORRECTION_NOT_EXACT")


def check_write_audit(log: str, project_id: str) -> None:
    mutations = re.findall(r'(?m)"(?:POST|PUT|PATCH|DELETE) /api/[^\r\n]+', log)
    expected = [
        f'POST /api/projects/{project_id}/quality/proposals HTTP/1.1" 200',
        f'POST /api/projects/{project_id}/quality/commit HTTP/1.1" 200',
        f'POST /api/projects/{project_id}/semantic-business-context HTTP/1.1" 409',
    ]
    require(len(mutations) == 3, "UNEXPECTED_BACKEND_WRITE_COUNT")
    for index, value in enumerate(expected):
        require(value in mutations[index], "UNEXPECTED_BACKEND_WRITE_ORDER")


def request_json(path: str, *, payload: dict | None = None) -> tuple[int, dict]:
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    request = Request(API + path, data=data,
                      headers={"Content-Type": "application/json"} if data else {},
                      method="POST" if data is not None else "GET")
    try:
        with urlopen(request, timeout=12) as response:
            status = response.status
            raw = response.read(1_000_000)
    except HTTPError as exc:
        status = exc.code
        raw = exc.read(1_000_000)
    except (OSError, URLError) as exc:
        raise ProbeFailure("LOCAL_BACKEND_UNREACHABLE") from exc
    try:
        response_json = json.loads(raw)
    except (ValueError, UnicodeError):
        response_json = {}
    return status, response_json if isinstance(response_json, dict) else {}


def fetch_expected(path: str) -> dict:
    status, body = request_json(path)
    require(status == 200, "BACKEND_READ_NOT_200")
    return body


def write_result(destination: Path, state: str, checks: dict, reason: str = "") -> None:
    result = {
        "phase": PHASE,
        "functional_state": state,
        "checks": checks,
        "failure_category": reason[:120],
        "native_shutdown": "INDEPENDENT_NOT_TESTED",
        "product_acceptance": "NOT_TESTED",
    }
    temporary = destination.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    temporary.replace(destination)


def observe(workspace: Path) -> int:
    require(workspace.name == "workspace" and workspace.is_dir() and
            not workspace.is_symlink(), "UNSAFE_PROBE_WORKSPACE")
    run = workspace.parent
    manifest_path = run / "fixtures" / "p3-native-w5-manifest.json"
    metadata = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
    baseline = json.loads((run / "manifest.json").read_text(encoding="utf-8-sig"))
    require(metadata.get("phase") == PHASE and baseline.get("phase") == PHASE and
            metadata.get("run_id") == run.name and baseline.get("run_id") == run.name and
            baseline.get("state") == "READY_NOT_TESTED" and
            baseline.get("product_acceptance") == "NOT_TESTED" and
            metadata.get("version") == 0 and metadata.get("rows") == 36 and
            metadata.get("expected_changed_cells") == 2,
            "INVALID_SYNTHETIC_PROBE_MANIFEST")
    pid = metadata.get("project_id", "")
    require(isinstance(pid, str) and bool(re.fullmatch(r"[a-f0-9]{32}", pid)),
            "INVALID_SYNTHETIC_PROJECT_ID")
    relative = PureWindowsPath(str(metadata.get("source_relative", "")))
    require(not relative.is_absolute() and not relative.drive and
            len(relative.parts) == 2 and relative.parts[0] == "datasets" and
            bool(re.fullmatch(r"[a-f0-9]{32}\.csv", relative.parts[1])),
            "UNSAFE_SYNTHETIC_SOURCE_PATH")
    original = workspace.joinpath(*relative.parts)
    require(original.is_file() and not original.is_symlink() and
            original.resolve().is_relative_to(workspace.resolve()),
            "SYNTHETIC_ORIGINAL_MISSING")
    expected_sha = hashlib.sha256(source_bytes()).hexdigest()
    require(metadata.get("original_sha256") == expected_sha and
            hashlib.sha256(original.read_bytes()).hexdigest() == expected_sha,
            "SYNTHETIC_BASELINE_HASH_MISMATCH")

    destination = run / "diagnostics" / "functional-result.json"
    checks = {field: "NOT_CHECKED" for field in PASS_FIELDS}
    write_result(destination, "WAITING_FOR_REVIEWED_CORRECTION", checks)
    end = time.monotonic() + MAX_SECONDS
    while time.monotonic() < end:
        try:
            status, quality = request_json(f"/projects/{pid}/quality")
        except ProbeFailure:
            time.sleep(1)
            continue
        if status == 200 and quality.get("version") == 1:
            break
        if status == 200 and quality.get("version") not in (0, 1):
            raise ProbeFailure("UNEXPECTED_QUALITY_VERSION")
        time.sleep(1)
    else:
        raise ProbeFailure("EXPLICIT_CORRECTION_NOT_OBSERVED")

    history = fetch_expected(f"/projects/{pid}/quality/history")
    current = fetch_expected(f"/projects/{pid}/semantics?expected_version=1")
    preview = fetch_expected(
        f"/projects/{pid}/quality/preview?offset=0&limit=10&expected_version=1"
    )
    assess_functional_snapshot(quality, history, current, preview)
    for field in ("quality_version", "version_history", "current_semantic_context"):
        checks[field] = PASS_FIELDS[field]
    write_result(destination, "VERIFYING", checks)

    status, _ = request_json(f"/projects/{pid}/semantics?expected_version=0")
    require(status == 409, "STALE_SEMANTIC_GET_NOT_REJECTED")
    checks["stale_semantic_get"] = PASS_FIELDS["stale_semantic_get"]
    stale = {
        "expected_version": 0,
        "domain_description": "Synthetic old version context must not migrate",
        "record_grain_description": "One original synthetic insurance claim per row",
        "field_definitions": [
            {"column": "claim_amount", "meaning": "Synthetic requested amount for old version"}
        ],
    }
    status, _ = request_json(f"/projects/{pid}/semantic-business-context", payload=stale)
    require(status == 409, "STALE_SEMANTIC_POST_NOT_REJECTED")
    checks["stale_semantic_post"] = PASS_FIELDS["stale_semantic_post"]
    result = verify_history(workspace, manifest_path)
    require(result.get("state") == PASS_FIELDS["historical_semantic_context"] and
            result.get("evidence") == "ISOLATED_SQLITE_READ_ONLY",
            "SQLITE_VERSION_HISTORY_NOT_PRESERVED")
    checks["historical_semantic_context"] = PASS_FIELDS["historical_semantic_context"]
    require(hashlib.sha256(original.read_bytes()).hexdigest() == expected_sha,
            "SYNTHETIC_ORIGINAL_CHANGED")
    checks["original_sha256"] = PASS_FIELDS["original_sha256"]
    # Uvicorn access logs are written to the local DevQA run only.
    log = run / "logs" / "backend-stdout.log"
    for _ in range(16):  # tolerate delayed file flushing, never create requests
        try:
            check_write_audit(log.read_text(encoding="utf-8", errors="replace"), pid)
            break
        except (ProbeFailure, OSError):
            time.sleep(0.25)
    else:
        raise ProbeFailure("BACKEND_WRITE_AUDIT_NOT_EXACT")
    checks["request_audit"] = PASS_FIELDS["request_audit"]
    write_result(destination, "PASS", checks)
    print("W5 DATA FUNCTIONAL PASS: independent of native window shutdown", flush=True)
    return 0


def main() -> int:
    workspace = Path(os.environ.get("PILOTODIN_HOME", "")).resolve()
    destination = workspace.parent / "diagnostics" / "functional-result.json"
    try:
        return observe(workspace)
    except Exception as exc:
        # Fail closed, use only bounded failure categories, never leak data.
        reason = str(exc) if isinstance(exc, ProbeFailure) else "PROBE_INTERNAL_ERROR"
        if destination.parent.is_dir() and workspace.name == "workspace":
            earlier = {}
            if destination.exists():
                try:
                    earlier = json.loads(destination.read_text(encoding="utf-8"))
                except (ValueError, OSError):
                    pass
            checks = earlier.get("checks", {}) if isinstance(earlier, dict) else {}
            write_result(destination, "FAIL_OR_INCOMPLETE", checks, reason)
        print("W5 DATA PROBE INCOMPLETE: " + reason[:120], flush=True)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
