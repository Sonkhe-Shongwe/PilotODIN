"""P1 original-source relink: owner data must never be used by these fixtures."""
from __future__ import annotations
import hashlib
from pathlib import Path
import sqlite3

import pytest

from tools import p1_relink_original_source as relocation


DATA = b"CustomerID,Revenue\n0001,120\n0002,240\n"
ID = "a" * 32


def workspace(tmp_path):
    repo = tmp_path / "project-repo"
    home = repo / ".pilotodin-dev-data"
    (home / "datasets").mkdir(parents=True)
    (home / "models").mkdir()
    (home / "models" / "marker.txt").write_text("keep this")
    original = home / "datasets" / "synthetic.csv"
    original.write_bytes(DATA)
    old = str(tmp_path / "old-checkout" / ".pilotodin-dev-data" / "datasets" / original.name)
    db = home / "pilotodin.sqlite3"
    with sqlite3.connect(db) as con:
        con.executescript("""
            CREATE TABLE projects (id TEXT PRIMARY KEY, name TEXT, dataset_path TEXT);
            CREATE TABLE quality_state (project_id TEXT PRIMARY KEY, original_sha256 TEXT, current_version INTEGER);
            CREATE TABLE quality_versions (project_id TEXT, version INTEGER, operations_json TEXT,
                PRIMARY KEY (project_id, version));
            CREATE TABLE quality_actions (id TEXT, project_id TEXT, params_json TEXT);
            CREATE TABLE quality_decisions (project_id TEXT, issue_id TEXT, status TEXT);
        """)
        con.execute("INSERT INTO projects VALUES (?,?,?)", (ID, "day", old))
        con.execute("INSERT INTO quality_state VALUES (?,?,?)",
                    (ID, hashlib.sha256(DATA).hexdigest(), 2))
        con.execute("INSERT INTO quality_versions VALUES (?,?,?)",
                    (ID, 2, '["kept-action"]'))
        con.execute("INSERT INTO quality_actions VALUES (?,?,?)",
                    ("kept-action", ID, '{"kind":"reviewed"}'))
        con.execute("INSERT INTO quality_decisions VALUES (?,?,?)",
                    (ID, "kept-issue", "approved"))
    return repo, home, db, old, original


def rows(db):
    with sqlite3.connect(db) as con:
        return {
            table: con.execute(f"SELECT * FROM {table}").fetchall()
            for table in ("projects", "quality_state", "quality_versions",
                          "quality_actions", "quality_decisions")
        }


def test_inspect_is_read_only_and_confirms_exact_original(tmp_path):
    _, home, db, old, original = workspace(tmp_path)
    before = rows(db)
    plan = relocation.inspect(home, "day")
    assert plan.project_id == ID
    assert plan.old_path == old
    assert plan.candidate == original.resolve()
    assert plan.quality_version == 2
    assert rows(db) == before


def test_backup_first_relinks_only_path_and_preserves_history(tmp_path, monkeypatch):
    repo, home, db, old, original = workspace(tmp_path)
    plan = relocation.inspect(home, "day")
    before = rows(db)
    backup = tmp_path / "owner-backup-new"
    monkeypatch.setattr(relocation, "_check_backend_stopped", lambda: None)
    relocation.apply(home, plan, backup, ID, repo)
    after = rows(db)
    assert after["projects"] == [(ID, "day", str(original.resolve()))]
    for table in ("quality_state", "quality_versions",
                  "quality_actions", "quality_decisions"):
        assert after[table] == before[table]
    assert original.read_bytes() == DATA
    assert (backup / "datasets" / "synthetic.csv").read_bytes() == DATA
    assert (backup / "models" / "marker.txt").read_text() == "keep this"
    assert rows(backup / "pilotodin.sqlite3") == before
    with pytest.raises(relocation.RecoveryBlocked, match="already reachable"):
        relocation.inspect(home, "day")


def test_requires_confirmation_and_keeps_db_unmodified(tmp_path, monkeypatch):
    repo, home, db, _, _ = workspace(tmp_path)
    before = rows(db)
    monkeypatch.setattr(relocation, "_check_backend_stopped", lambda: None)
    with pytest.raises(relocation.RecoveryBlocked, match="confirmation"):
        relocation.apply(home, relocation.inspect(home, "day"),
                         tmp_path / "backup", "wrong-id", repo)
    assert rows(db) == before
    assert not (tmp_path / "backup").exists()


def test_hash_mismatch_blocks_without_backup_or_update(tmp_path, monkeypatch):
    repo, home, db, _, original = workspace(tmp_path)
    original.write_bytes(b"modified data")
    before = rows(db)
    with pytest.raises(relocation.RecoveryBlocked, match="differs"):
        relocation.inspect(home, "day")
    assert rows(db) == before


def test_missing_or_symlink_candidate_blocks(tmp_path):
    _, home, db, _, original = workspace(tmp_path)
    original.unlink()
    with pytest.raises(relocation.RecoveryBlocked, match="missing"):
        relocation.inspect(home, "day")


def test_backup_inside_project_refused(tmp_path, monkeypatch):
    repo, home, db, _, _ = workspace(tmp_path)
    monkeypatch.setattr(relocation, "_check_backend_stopped", lambda: None)
    with pytest.raises(relocation.RecoveryBlocked, match="outside"):
        relocation.apply(home, relocation.inspect(home, "day"),
                         repo / "backup", ID, repo)


def test_backend_listener_refuses_relink(tmp_path, monkeypatch):
    repo, home, db, _, _ = workspace(tmp_path)
    def blocked():
        raise relocation.RecoveryBlocked("Port 8000 is in use")
    monkeypatch.setattr(relocation, "_check_backend_stopped", blocked)
    with pytest.raises(relocation.RecoveryBlocked, match="in use"):
        relocation.apply(home, relocation.inspect(home, "day"),
                         tmp_path / "backup", ID, repo)
    assert not (tmp_path / "backup").exists()


def test_missing_quality_version_blocks(tmp_path):
    _, home, db, _, _ = workspace(tmp_path)
    with sqlite3.connect(db) as con:
        con.execute("DELETE FROM quality_versions")
    with pytest.raises(relocation.RecoveryBlocked, match="version"):
        relocation.inspect(home, "day")
