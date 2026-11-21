#!/usr/bin/env python3
"""Read-only P3 native W5 historical semantic retention gate.

Checks the synthetic Quality v0->v1 database after a deliberately reviewed
native UI commit. Never writes to SQLite or prints business-description text.
Not an independent owner WebView2 observation or a release certification.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path, PureWindowsPath
import re
import sqlite3
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.Seed_P3_Native_Quality_W5_Local import DOMAIN, GRAIN, MEANING, PHASE

RUN_RE = re.compile(r"P3-NATIVE-QUALITY-W5-\d{8}T\d{6}Z-[a-f0-9]{10}\Z")
PID_RE = re.compile(r"[a-f0-9]{32}\Z")
SOURCE_RE = re.compile(r"[a-f0-9]{32}\.csv\Z")
PASS = "PASS_V0_RETAINED_V1_ABSENT"


class HistoryRefused(ValueError):
    """The synthetic W5 historical data is not proven safely preserved."""


def _json_object(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError) as exc:
        raise HistoryRefused("Synthetic W5 manifest is unreadable or invalid") from exc
    if not isinstance(data, dict):
        raise HistoryRefused("Synthetic W5 manifest must contain an object")
    return data


def verify(workspace: Path, manifest_path: Path) -> dict[str, str]:
    """Inspect exactly the isolated test database with read-only SQLite URI."""
    if workspace.is_symlink() or getattr(workspace, "is_junction", lambda: False)():
        raise HistoryRefused("Refusing redirected synthetic W5 workspace")
    try:
        workspace = workspace.resolve(strict=True)
    except OSError as exc:
        raise HistoryRefused("Synthetic W5 workspace does not exist") from exc
    run = workspace.parent
    if (workspace.name != "workspace" or not workspace.is_dir()
        or not RUN_RE.fullmatch(run.name)
        or run.is_symlink() or getattr(run, "is_junction", lambda: False)()):
        raise HistoryRefused("Not an isolated P3 native W5 QA workspace")

    expected_manifest = run / "fixtures" / "p3-native-w5-manifest.json"
    for path in (run / "manifest.json", run / "fixtures", expected_manifest):
        if path.is_symlink() or getattr(path, "is_junction", lambda: False)():
            raise HistoryRefused("Refusing redirected synthetic QA manifest")
    if manifest_path.resolve() != expected_manifest.resolve():
        raise HistoryRefused("W5 manifest does not belong to this isolated run")
    baseline = _json_object(run / "manifest.json")
    fixture = _json_object(expected_manifest)
    if (baseline.get("run_id") != run.name or fixture.get("run_id") != run.name
        or baseline.get("phase") != PHASE or fixture.get("phase") != PHASE
        or baseline.get("state") != "READY_NOT_TESTED"
        or baseline.get("product_acceptance") != "NOT_TESTED"
        or fixture.get("version") != 0 or fixture.get("rows") != 36
        or fixture.get("expected_changed_cells") != 2
        or fixture.get("scope") != "ONE_SYNTHETIC_QUALITY_PROPOSAL_AND_ONE_EXPLICIT_UI_COMMIT"):
        raise HistoryRefused("Manifest identity and synthetic acceptance scope mismatch")
    rules = baseline.get("rules")
    if not isinstance(rules, dict) or any(rules.get(key) is not True for key in
        ("synthetic_only", "no_auto_delete", "no_model_or_installer")):
        raise HistoryRefused("Missing synthetic-only DevQA policy")

    pid = fixture.get("project_id")
    if not isinstance(pid, str) or not PID_RE.fullmatch(pid):
        raise HistoryRefused("Invalid synthetic W5 project identifier")
    source = fixture.get("source_relative")
    if not isinstance(source, str):
        raise HistoryRefused("Missing synthetic W5 source-relative path")
    source_path = PureWindowsPath(source)
    if (source_path.drive or source_path.is_absolute() or len(source_path.parts) != 2
        or source_path.parts[0] != "datasets"
        or not SOURCE_RE.fullmatch(source_path.parts[1])):
        raise HistoryRefused("W5 fixture path is outside the isolated dataset folder")

    db = workspace / "pilotodin.sqlite3"
    if db.is_symlink() or getattr(db, "is_junction", lambda: False)() or not db.is_file():
        raise HistoryRefused("Isolated W5 SQLite database is missing or redirected")
    if db.resolve().parent != workspace:
        raise HistoryRefused("SQLite file escapes the isolated W5 workspace")
    try:
        # mode=ro reads SQLite's live WAL snapshot; never use immutable=1 here.
        with sqlite3.connect(db.as_uri() + "?mode=ro", uri=True, timeout=5) as con:
            con.execute("PRAGMA query_only = ON")
            projects = con.execute("SELECT id FROM projects").fetchall()
            version_rows = con.execute(
                "SELECT current_version FROM quality_state WHERE project_id=?", (pid,)
            ).fetchall()
            history = con.execute(
                "SELECT version FROM quality_versions WHERE project_id=? ORDER BY version", (pid,)
            ).fetchall()
            notes = con.execute(
                "SELECT project_id, quality_version, domain_description,"
                " record_grain_description, field_definitions_json"
                " FROM semantic_business_context"
            ).fetchall()
    except sqlite3.DatabaseError as exc:
        raise HistoryRefused("Isolated W5 SQLite history could not be read") from exc
    if (projects != [(pid,)] or version_rows != [(1,)]
        or history != [(0,), (1,)] or len(notes) != 1):
        raise HistoryRefused("W5 project/version history or context-row count disagrees")
    project, version, domain, grain, raw_fields = notes[0]
    if project != pid or version != 0 or domain != DOMAIN or grain != GRAIN:
        raise HistoryRefused("Original synthetic version-zero descriptions were not preserved")
    try:
        fields = json.loads(raw_fields)
    except (ValueError, TypeError) as exc:
        raise HistoryRefused("Stored synthetic field descriptions are malformed") from exc
    if fields != [{"column": "claim_amount", "meaning": MEANING}]:
        raise HistoryRefused("Original synthetic version-zero field meaning was changed")

    return {
        "state": PASS,
        "evidence": "ISOLATED_SQLITE_READ_ONLY",
        "native_ui": "NOT_INDEPENDENTLY_OBSERVED",
        "product_acceptance": "NOT_TESTED",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("workspace", type=Path)
    parser.add_argument("fixture_manifest", type=Path)
    args = parser.parse_args(argv)
    try:
        result = verify(args.workspace, args.fixture_manifest)
        print(json.dumps(result))
        return 0
    except HistoryRefused as exc:
        # No raw paths, SQL values or owner data in normal diagnostic output.
        print(json.dumps({"state": "BLOCKED", "reason": str(exc),
                          "product_acceptance": "NOT_TESTED"}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
