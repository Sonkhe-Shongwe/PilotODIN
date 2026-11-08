#!/usr/bin/env python3
"""Offline, read-only review of a P3 W5 status-only native QA archive.

A valid report is NOT independent proof that WebView2 was observed, nor a P3
phase or product release certification. The archive records owner testimony.
No contents are extracted and no user files or Git state are changed.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path, PureWindowsPath
import re
import stat
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from tools.Seed_P3_Native_Quality_W5_Local import source_bytes

PHASE = "P3-NATIVE-QUALITY-W5"
CONTENTS = frozenset({"result.json", "manifest.json", "p3-native-w5-manifest.json"})
RUN_RE = re.compile(r"P3-NATIVE-QUALITY-W5-(\d{8}T\d{6}Z)-([a-f0-9]{10})\Z")
SHA_RE = re.compile(r"[a-f0-9]{40}\Z")
HASH_RE = re.compile(r"[a-f0-9]{64}\Z")
ID_RE = re.compile(r"[a-f0-9]{32}\Z")
SUCCESS = {
    "native_mode": "OWNER_WINDOW_CLOSED_WITH_ZERO_TAURI_EXIT",
    "quality_version": "PASS_V0_TO_V1",
    "version_history": "PASS_EXACTLY_V0_V1",
    "stale_semantic_get": "PASS_HTTP_409",
    "stale_semantic_post": "PASS_HTTP_409",
    "current_semantic_context": "PASS_EMPTY_V1",
    "historical_semantic_context": "PASS_V0_RETAINED_V1_ABSENT",
    "original_sha256": "PASS_UNCHANGED",
    "request_audit": "PASS_ONE_PROPOSAL_ONE_UI_COMMIT_ONE_REJECTED_STALE_POST",
    "owner_native_ui": "OWNER_REPORTED_PASS",
    "installer": "NOT_BUILT",
    "model_or_ai": "NOT_LAUNCHED",
    "scope": "SYNTHETIC_NATIVE_P3_W5_ONLY",
    "product_acceptance": "NOT_TESTED",
}

class ArchiveRefused(ValueError):
    """Unsafe, inconsistent or unsupported QA evidence."""


def _no_duplicate_pairs(pairs: list[tuple[str, object]]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ArchiveRefused("Duplicate JSON key is not accepted")
        result[key] = value
    return result


def _reject_constant(value: str) -> None:
    raise ArchiveRefused("Non-finite JSON number is not accepted: " + value)


def _read_json(z: zipfile.ZipFile, name: str) -> dict:
    raw = z.read(name)
    try:
        data = json.loads(raw.decode("utf-8-sig"),
                          object_pairs_hook=_no_duplicate_pairs,
                          parse_constant=_reject_constant)
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ArchiveRefused("Invalid UTF-8 JSON in " + name) from exc
    if not isinstance(data, dict):
        raise ArchiveRefused("Expected a JSON object in " + name)
    return data


def inspect_archive(path: Path, expected_source: str | None = None) -> dict:
    """Return a bounded, redacted verdict; never extract files."""
    name = path.name
    prefix = name.removesuffix("-p3-w5-status.zip")
    if not name.endswith("-p3-w5-status.zip") or not RUN_RE.fullmatch(prefix):
        raise ArchiveRefused("Unexpected P3 W5 status-only archive filename")
    if expected_source is not None and not SHA_RE.fullmatch(expected_source):
        raise ArchiveRefused("Expected source SHA must be exactly 40 lowercase hex characters")
    if not path.is_file() or path.is_symlink():
        raise ArchiveRefused("A regular local status-only ZIP file is required")
    if path.stat().st_size > 150_000:
        raise ArchiveRefused("Status archive exceeds the 150 KB limit")

    try:
        with zipfile.ZipFile(path, mode="r") as z:
            info = z.infolist()
            if len(info) != 3 or {i.filename for i in info} != CONTENTS:
                raise ArchiveRefused("Expected exactly the three flat status JSON files")
            if any(i.is_dir() or i.flag_bits & 1 or i.file_size > 40_000
                   or i.compress_size > 70_000 or
                   (i.create_system == 3 and stat.S_ISLNK(i.external_attr >> 16))
                   for i in info):
                raise ArchiveRefused("Archive contains an encrypted, linked, oversized or non-file entry")
            if sum(i.file_size for i in info) > 100_000:
                raise ArchiveRefused("Uncompressed archive exceeds status-only limit")
            if z.testzip() is not None:
                raise ArchiveRefused("Archive ZIP CRC integrity check failed")
            outcome = _read_json(z, "result.json")
            baseline = _read_json(z, "manifest.json")
            fixture = _read_json(z, "p3-native-w5-manifest.json")
    except (zipfile.BadZipFile, EOFError, OSError, RuntimeError) as exc:
        raise ArchiveRefused("Corrupted or inaccessible status-only ZIP") from exc

    for label, obj in (("result", outcome), ("baseline", baseline), ("fixture", fixture)):
        if obj.get("phase") != PHASE:
            raise ArchiveRefused(label + " phase is not P3 native Quality W5")
    if baseline.get("run_id") != prefix or fixture.get("run_id") != prefix:
        raise ArchiveRefused("Manifest run IDs differ from the immutable filename")
    if baseline.get("schema_version") != 1 or baseline.get("state") != "READY_NOT_TESTED" or \
       baseline.get("product_acceptance") != "NOT_TESTED":
        raise ArchiveRefused("Unexpected DevQA creation-stage manifest")
    rules = baseline.get("rules")
    if not isinstance(rules, dict) or any(rules.get(k) is not True for k in
        ("synthetic_only", "no_auto_delete", "no_model_or_installer")):
        raise ArchiveRefused("DevQA isolation rules missing or disabled")
    if outcome.get("product_acceptance") != "NOT_TESTED":
        raise ArchiveRefused("Archive falsely claims product acceptance")
    if outcome.get("installer") != "NOT_BUILT" or outcome.get("model_or_ai") != "NOT_LAUNCHED":
        raise ArchiveRefused("Archive is outside the approved W5 scope")

    pid = fixture.get("project_id")
    issue = fixture.get("issue_id")
    if not isinstance(pid, str) or not ID_RE.fullmatch(pid):
        raise ArchiveRefused("Missing synthetic project identifier")
    if not isinstance(issue, str) or not 1 <= len(issue) <= 128:
        raise ArchiveRefused("Missing synthetic Quality finding identifier")
    source_path = fixture.get("source_relative")
    if not isinstance(source_path, str):
        raise ArchiveRefused("Missing synthetic source path")
    location = PureWindowsPath(source_path)
    if location.is_absolute() or location.drive or len(location.parts) != 2 or \
       location.parts[0] != "datasets" or not re.fullmatch(r"[a-f0-9]{32}\.csv", location.parts[1]):
        raise ArchiveRefused("Synthetic source path is not a safe dataset-relative CSV path")
    raw = source_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    if fixture.get("rows") != 36 or fixture.get("version") != 0 or \
       fixture.get("expected_changed_cells") != 2 or \
       fixture.get("original_bytes") != len(raw) or fixture.get("original_sha256") != digest:
        raise ArchiveRefused("Manifest does not match the immutable synthetic 36-row fixture")
    source_head = outcome.get("source_head")
    if not isinstance(source_head, str) or not SHA_RE.fullmatch(source_head):
        raise ArchiveRefused("Missing valid Git source HEAD declaration")
    if expected_source is not None and source_head != expected_source:
        raise ArchiveRefused("Archive source SHA does not match independently supplied expected source")

    if outcome.get("state") != "REVIEW_REQUIRED":
        return {
            "verdict": "NOT_ACCEPTED",
            "archive_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "source_head_declared": source_head,
            "owner_native_observation": "NOT_ACCEPTED",
            "reason": "Recorded native QA run did not reach REVIEW_REQUIRED success path",
            "native_acceptance": "PENDING_INDEPENDENT_REVIEW",
            "product_acceptance": "NOT_TESTED",
        }
    if outcome.get("failure_category") != "":
        raise ArchiveRefused("Successful QA archive has a nonempty failure category")
    # The native preflight permits exactly these attested worktree states.
    # A dirty tracked checkout can never be represented as scoped W5 success.
    if outcome.get("source_worktree") not in (
        "CLEAN", "TRACKED_CLEAN_EXPECTED_UNTRACKED_TAURI"
    ):
        raise ArchiveRefused("W5 checkout source was not clean or safely scoped")
    for field, expected in SUCCESS.items():
        if outcome.get(field) != expected:
            raise ArchiveRefused("Success claim mismatches required field: " + field)
    return {
        "verdict": "STATUS_ARCHIVE_INTEGRITY_PASS",
        "archive_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "source_head_declared": source_head,
        "source_worktree_reported": outcome["source_worktree"],
        "source_sha_matches_supplied_expectation": expected_source is not None,
        "synthetic_source_sha256": digest,
        "original_data_integrity": "RUNNER_REPORTED_PASS",
        "native_request_audit": "RUNNER_REPORTED_PASS",
        "owner_native_observation": "OWNER_REPORTED_PASS_NOT_INDEPENDENTLY_OBSERVED",
        "native_acceptance": "PENDING_INDEPENDENT_REVIEW",
        "product_acceptance": "NOT_TESTED",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("status_zip", type=Path, help="Status-only ZIP from a completed synthetic W5 run")
    parser.add_argument("--expected-source", help="Independently verified exact 40-character Git HEAD")
    args = parser.parse_args(argv)
    try:
        verdict = inspect_archive(args.status_zip, args.expected_source)
        print(json.dumps(verdict, indent=2))
        return 0 if verdict["verdict"] == "STATUS_ARCHIVE_INTEGRITY_PASS" else 2
    except (ArchiveRefused, FileNotFoundError, PermissionError) as exc:
        print(json.dumps({
            "verdict": "REFUSED",
            "reason": str(exc),
            "native_acceptance": "PENDING_INDEPENDENT_REVIEW",
            "product_acceptance": "NOT_TESTED",
        }, indent=2))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
