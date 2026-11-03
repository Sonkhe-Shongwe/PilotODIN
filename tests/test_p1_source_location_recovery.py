"""P1 relocation guard: lost source paths never reset project or Quality history.

All filesystem and database operations happen inside Pytest's temporary
directory, never in an owner's real PilotODIN data or installed workspace.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

from fastapi.testclient import TestClient

from backend import main, quality, storage


_SOURCE = b"CustomerID,Revenue\n0001,120\n0002,240\n0003,360\n"


def _fixture(monkeypatch, tmp_path):
    home = tmp_path / "disposable-workspace"
    (home / "datasets").mkdir(parents=True)
    (home / "models").mkdir()
    monkeypatch.setattr(storage, "HOME", home)
    monkeypatch.setattr(storage, "DB_PATH", home / "pilotodin.sqlite3")
    storage.init()
    quality._init_tables()
    client = TestClient(main.app)
    response = client.post(
        "/api/projects",
        files={"file": ("synthetic.csv", _SOURCE, "text/csv")},
    )
    assert response.status_code == 201, response.text
    pid = response.json()["id"]
    saved = storage.get_project(pid)
    assert saved is not None
    return client, pid, Path(saved["dataset_path"])


def _state(pid):
    with storage.connect() as con:
        original = con.execute(
            "SELECT original_sha256, current_version FROM quality_state WHERE project_id=?",
            (pid,),
        ).fetchone()
        history = con.execute(
            "SELECT version,operations_json FROM quality_versions WHERE project_id=? "
            "ORDER BY version", (pid,),
        ).fetchall()
        path = con.execute(
            "SELECT dataset_path FROM projects WHERE id=?", (pid,)
        ).fetchone()
    return (tuple(original), [tuple(row) for row in history], path[0])


def test_missing_original_is_recoverable_conflict_without_metadata_changes(monkeypatch, tmp_path):
    client, pid, source = _fixture(monkeypatch, tmp_path)
    original_state = _state(pid)
    assert original_state[0] == (hashlib.sha256(_SOURCE).hexdigest(), 0)
    assert client.get(f"/api/projects/{pid}/live-profile").status_code == 200

    # Simulate moving an old repository without fixing the saved source path.
    moved = source.with_name("moved-original.csv")
    source.rename(moved)
    assert not source.exists()
    response = client.get(f"/api/projects/{pid}/live-profile")
    assert response.status_code == 409, response.text
    detail = response.json()["detail"]
    assert "original dataset" in detail.lower()
    assert "restore" in detail.lower()
    assert str(source) not in detail
    assert "traceback" not in response.text.lower()
    assert client.get(f"/api/projects/{pid}").status_code == 200
    assert _state(pid) == original_state
    assert moved.read_bytes() == _SOURCE

    # Restoring identical bytes at the recorded location safely resumes read.
    moved.rename(source)
    restored = client.get(f"/api/projects/{pid}/live-profile")
    assert restored.status_code == 200, restored.text
    assert restored.json()["version"] == 0
    assert _state(pid) == original_state


def test_unreadable_original_is_a_safe_conflict(monkeypatch, tmp_path):
    client, pid, source = _fixture(monkeypatch, tmp_path)
    original_state = _state(pid)

    def cannot_open(path):
        assert path == str(source)
        raise PermissionError("private machine path must not be returned")

    monkeypatch.setattr(quality, "_digest", cannot_open)
    response = client.get(f"/api/projects/{pid}/live-profile")
    assert response.status_code == 409, response.text
    assert "cannot be read" in response.json()["detail"]
    assert "private machine path" not in response.text
    assert _state(pid) == original_state


def test_changed_original_never_silently_rebinds_quality_history(monkeypatch, tmp_path):
    client, pid, source = _fixture(monkeypatch, tmp_path)
    original_state = _state(pid)
    source.write_bytes(_SOURCE + b"0004,480\n")
    response = client.get(f"/api/projects/{pid}/live-profile")
    assert response.status_code == 409
    assert "changed outside PilotODIN" in response.json()["detail"]
    assert _state(pid) == original_state
