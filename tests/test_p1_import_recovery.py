"""P1 import recoverability: never leave ghost projects or orphaned sources.

Every case redirects the database and datasets into its own Pytest tmp_path,
so it neither reads nor modifies the owner's existing PilotODIN workspace.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd
from fastapi.testclient import TestClient

from backend import quality, storage
from backend.main import app


def _temporary_store(monkeypatch, tmp_path):
    home = tmp_path / "isolated-import"
    (home / "datasets").mkdir(parents=True)
    (home / "models").mkdir()
    monkeypatch.setattr(storage, "HOME", home)
    monkeypatch.setattr(storage, "DB_PATH", home / "pilotodin.sqlite3")
    storage.init()
    return home


def _check_no_orphans(home: Path):
    assert storage.list_projects() == []
    with storage.connect() as con:
        assert con.execute("SELECT COUNT(*) FROM projects").fetchone()[0] == 0
        assert con.execute("SELECT COUNT(*) FROM experiments").fetchone()[0] == 0
    assert list((home / "datasets").iterdir()) == []


def _csv():
    return pd.DataFrame({
        "CustomerID": ["0001", "0002", "0003"],
        "Revenue": [100, 240, 360],
    }).to_csv(index=False).encode("utf-8")


def test_import_rollback_works_when_quality_schema_is_missing(monkeypatch, tmp_path):
    """Missing Quality tables cannot mask original initialization failure."""
    home = _temporary_store(monkeypatch, tmp_path)
    with storage.connect() as con:
        tables = {r[0] for r in con.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")}
    assert "quality_versions" not in tables
    response = TestClient(app).post(
        "/api/projects",
        files={"file": ("source.csv", _csv(), "text/csv")},
    )
    assert response.status_code == 422, response.text
    assert "Could not process dataset" in response.json()["detail"]
    _check_no_orphans(home)


def test_partial_quality_registration_is_rolled_back_atomically(monkeypatch, tmp_path):
    """If metadata saved but final registration fails, remove both records."""
    home = _temporary_store(monkeypatch, tmp_path)
    quality._init_tables()

    original = quality.register

    def interrupted_registration(pid):
        original(pid)
        raise RuntimeError("Synthetic interrupted registration")

    monkeypatch.setattr(quality, "register", interrupted_registration)
    response = TestClient(app).post(
        "/api/projects",
        files={"file": ("source.csv", _csv(), "text/csv")},
    )
    assert response.status_code == 422, response.text
    assert "Synthetic interrupted registration" in response.json()["detail"]
    _check_no_orphans(home)
    with storage.connect() as con:
        for table in ("quality_state", "quality_versions"):
            assert con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] == 0


def test_rejected_invalid_dataset_removes_staged_bytes(monkeypatch, tmp_path):
    home = _temporary_store(monkeypatch, tmp_path)
    response = TestClient(app).post(
        "/api/projects",
        files={"file": ("invalid.csv", b"single_column\nvalue\n", "text/csv")},
    )
    assert response.status_code == 422, response.text
    _check_no_orphans(home)


def test_import_rollback_failure_keeps_source_for_recovery(monkeypatch, tmp_path):
    """Never silently delete data when a database row could not be removed."""
    home = _temporary_store(monkeypatch, tmp_path)
    quality._init_tables()

    def interrupted_registration(_pid):
        raise RuntimeError("Synthetic registration interrupted")

    monkeypatch.setattr(quality, "register", interrupted_registration)
    # Simulate an unavailable rollback connection only AFTER saving project
    # metadata, so the cleanup path itself fails.
    original_connect = storage.connect
    connections = {"count": 0}

    def fail_cleanup_connection():
        connections["count"] += 1
        # Fail only when the cleanup helper uses the database schema lookup:
        # called after import read/profile and save_project have succeeded.
        if connections["count"] >= 4:
            raise OSError("Synthetic rollback storage failure")
        return original_connect()

    # Leave failure injection for a separate focused test of helper below;
    # a direct helper invocation is deterministic and does not assume an
    # internal number of storage connections in future import refactors.
    from backend.main import _rollback_failed_project_import
    missing_path = home / "datasets" / "recoverable.csv"
    missing_path.write_bytes(_csv())
    monkeypatch.setattr(storage, "connect", lambda: (_ for _ in ()).throw(
        OSError("Synthetic rollback storage failure")))
    try:
        _rollback_failed_project_import("synthetic-uncommitted-id", missing_path)
        assert False, "Expected forced rollback error"
    except OSError:
        pass
    assert missing_path.read_bytes() == _csv()
