"""P3 W5 native historical persistence gate, with a real isolated commit.

No Tauri window is run here. All DB edits are restricted to a fresh 36-row
synthetic temporary project; the production storage path is never used.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys

import pytest

from tools import qa_foundation
from tools.Seed_P3_Native_Quality_W5_Local import PHASE
from tools.Verify_P3_Native_Quality_W5_History_Local import HistoryRefused, PASS, verify

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def seeded(tmp_path, monkeypatch):
    run, _ = qa_foundation.create_run(tmp_path / "native-w5-history", PHASE, repo=ROOT)
    workspace = run / "workspace"
    fixture = run / "fixtures" / "p3-native-w5-manifest.json"
    env = os.environ.copy()
    env["PILOTODIN_HOME"] = str(workspace)
    env.pop("PILOTODIN_DESKTOP_SESSION", None)
    result = subprocess.run(
        [sys.executable, "-B", str(ROOT / "tools/Seed_P3_Native_Quality_W5_Local.py"),
         str(fixture)],
        cwd=ROOT, env=env, capture_output=True, text=True, timeout=40, check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    manifest = json.loads(fixture.read_text(encoding="utf-8"))
    from backend import storage, quality
    from backend.main import app
    from fastapi.testclient import TestClient
    monkeypatch.setattr(storage, "HOME", workspace)
    monkeypatch.setattr(storage, "DB_PATH", workspace / "pilotodin.sqlite3")
    storage.init()
    quality._init_tables()
    return workspace, fixture, manifest, TestClient(app)


def approve(w5):
    _workspace, _fixture, data, client = w5
    pid = data["project_id"]
    proposed = client.post(
        f"/api/projects/{pid}/quality/proposals",
        json={"operation":"approve", "issue_id":data["issue_id"], "expected_version":0},
    )
    assert proposed.status_code == 200, proposed.text
    payload = proposed.json()
    assert payload["changed_cells"] == 2
    applied = client.post(
        f"/api/projects/{pid}/quality/commit",
        json={"proposal_id":payload["proposal_id"], "proposal_hash":payload["proposal_hash"]},
    )
    assert applied.status_code == 200, applied.text
    assert applied.json()["version"] == 1


def test_gate_rejects_before_actual_approved_quality_version_change(seeded):
    workspace, fixture, _data, _client = seeded
    with pytest.raises(HistoryRefused, match="project/version history"):
        verify(workspace, fixture)


def test_real_approved_quality_v1_preserves_exact_old_notes_without_writing(seeded):
    workspace, fixture, _data, _client = seeded
    approve(seeded)
    db = workspace / "pilotodin.sqlite3"
    before = hashlib.sha256(db.read_bytes()).hexdigest()
    result = verify(workspace, fixture)
    assert result["state"] == PASS
    assert result["evidence"] == "ISOLATED_SQLITE_READ_ONLY"
    assert result["product_acceptance"] == "NOT_TESTED"
    assert result["native_ui"] == "NOT_INDEPENDENTLY_OBSERVED"
    assert hashlib.sha256(db.read_bytes()).hexdigest() == before


def test_gate_rejects_lost_version_zero_note_after_quality_transition(seeded):
    workspace, fixture, data, _client = seeded
    approve(seeded)
    with sqlite3.connect(workspace / "pilotodin.sqlite3") as con:
        con.execute(
            "DELETE FROM semantic_business_context WHERE project_id=? AND quality_version=0",
            (data["project_id"],),
        )
    with pytest.raises(HistoryRefused, match="context-row count"):
        verify(workspace, fixture)


def test_gate_rejects_modified_version_zero_text_after_quality_transition(seeded):
    workspace, fixture, data, _client = seeded
    approve(seeded)
    with sqlite3.connect(workspace / "pilotodin.sqlite3") as con:
        con.execute(
            "UPDATE semantic_business_context SET domain_description=? "
            "WHERE project_id=? AND quality_version=0",
            ("TAMPERED SYNTHETIC DESCRIPTION", data["project_id"]),
        )
    with pytest.raises(HistoryRefused, match="not preserved"):
        verify(workspace, fixture)


def test_gate_rejects_unapproved_version_one_note_migration(seeded):
    workspace, fixture, data, _client = seeded
    approve(seeded)
    with sqlite3.connect(workspace / "pilotodin.sqlite3") as con:
        con.execute(
            "INSERT INTO semantic_business_context "
            "SELECT project_id, 1, domain_description, record_grain_description, "
            "field_definitions_json, updated_at FROM semantic_business_context "
            "WHERE project_id=? AND quality_version=0",
            (data["project_id"],),
        )
    with pytest.raises(HistoryRefused, match="context-row count"):
        verify(workspace, fixture)


def test_gate_rejects_wrong_workspace_manifest_pair(seeded, tmp_path):
    workspace, _fixture, _data, _client = seeded
    rogue = tmp_path / "unrelated.json"
    rogue.write_text("{}", encoding="utf-8")
    with pytest.raises(HistoryRefused, match="does not belong"):
        verify(workspace, rogue)
