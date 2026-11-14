"""P1 real-ASGI import and failed-switch recovery using only synthetic temp data.

These requests pass through the actual FastAPI handlers, SQLite and versioned
Quality engine. Project selection and form retention belong to the separate
React/Chromium suite; an ASGI TestClient is not a native desktop UI run.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

from fastapi.testclient import TestClient

from backend import main, quality, storage


def _csv(prefix: str) -> bytes:
    rows = ["OrderID,Region,Amount,Outcome"]
    for index in range(1, 19):
        region = "North" if index % 2 else "South"
        outcome = "approved" if index % 3 else "pending"
        rows.append(f"{prefix}{index:04d},{region},{index * 13},{outcome}")
    return ("\n".join(rows) + "\n").encode("utf-8")


def _isolated_client(monkeypatch, tmp_path):
    home = tmp_path / "p1-real-api-disposable"
    (home / "datasets").mkdir(parents=True)
    (home / "models").mkdir()
    monkeypatch.setattr(storage, "HOME", home)
    monkeypatch.setattr(storage, "DB_PATH", home / "pilotodin.sqlite3")
    storage.init()
    quality._init_tables()
    client = TestClient(main.app)
    projects = {}
    for label in ("A", "B"):
        payload = _csv(label)
        result = client.post(
            "/api/projects",
            files={"file": (f"synthetic-{label}.csv", payload, "text/csv")},
        )
        assert result.status_code == 201, result.text
        project_id = result.json()["id"]
        stored = storage.get_project(project_id)
        assert stored is not None
        source = Path(stored["dataset_path"])
        assert source.parent == home / "datasets"
        assert source.read_bytes() == payload
        projects[label] = (project_id, source, payload)
    return client, home, projects


def _audit(project_id: str):
    """Read only the invariants that any failed project read must preserve."""
    with storage.connect() as con:
        state = con.execute(
            "SELECT original_sha256,current_version FROM quality_state WHERE project_id=?",
            (project_id,),
        ).fetchone()
        versions = con.execute(
            "SELECT version,operations_json,event,details_json FROM quality_versions "
            "WHERE project_id=? ORDER BY version",
            (project_id,),
        ).fetchall()
        actions = con.execute(
            "SELECT COUNT(*) FROM quality_actions WHERE project_id=?", (project_id,),
        ).fetchone()[0]
        decisions = con.execute(
            "SELECT COUNT(*) FROM quality_decisions WHERE project_id=?", (project_id,),
        ).fetchone()[0]
        location = con.execute(
            "SELECT dataset_path FROM projects WHERE id=?", (project_id,),
        ).fetchone()[0]
    assert state is not None
    return (tuple(state), tuple(tuple(row) for row in versions), actions, decisions, location)


def _assert_original_readable(client, project_id, source, payload):
    assert client.get(f"/api/projects/{project_id}").status_code == 200
    live = client.get(f"/api/projects/{project_id}/live-profile")
    assert live.status_code == 200, live.text
    assert live.json()["version"] == 0
    assert live.json()["profile"]["rows"] == 18
    scan = client.get(f"/api/projects/{project_id}/quality")
    assert scan.status_code == 200, scan.text
    assert scan.json()["version"] == 0
    assert scan.json()["rows"] == 18
    assert scan.json()["summary"]["applied_actions"] == 0
    history = client.get(f"/api/projects/{project_id}/quality/history")
    assert history.status_code == 200, history.text
    assert history.json()["current_version"] == 0
    assert [entry["event"] for entry in history.json()["versions"]] == ["original"]
    assert history.json()["actions"] == []
    assert history.json()["decisions"] == []
    assert source.read_bytes() == payload


def test_real_api_missing_destination_profile_preserves_both_quality_histories(monkeypatch, tmp_path):
    """Two real imports -> Quality v0 -> failed B profile -> usable A -> B recovery."""
    client, home, projects = _isolated_client(monkeypatch, tmp_path)
    aid, a_source, a_bytes = projects["A"]
    bid, b_source, b_bytes = projects["B"]
    assert aid != bid
    assert len(client.get("/api/projects").json()) == 2
    assert client.get("/api/health").status_code == 200
    _assert_original_readable(client, aid, a_source, a_bytes)
    _assert_original_readable(client, bid, b_source, b_bytes)
    original_a, original_b = _audit(aid), _audit(bid)
    assert original_a[0] == (hashlib.sha256(a_bytes).hexdigest(), 0)
    assert original_b[0] == (hashlib.sha256(b_bytes).hexdigest(), 0)

    # Only move a throwaway original, never rebind metadata, approve or reimport.
    temporary_missing = home / "datasets" / "synthetic-B-temporarily-unavailable"
    b_source.rename(temporary_missing)
    try:
        assert client.get(f"/api/projects/{bid}").status_code == 200
        failed = client.get(f"/api/projects/{bid}/live-profile")
        assert failed.status_code == 409, failed.text
        assert "original dataset" in failed.json()["detail"].lower()
        assert str(b_source) not in failed.text
        assert str(home) not in failed.text
        assert "traceback" not in failed.text.lower()
        # Backend does not own the selected frontend project: A's endpoints
        # MUST remain usable after a failed B read.
        _assert_original_readable(client, aid, a_source, a_bytes)
        assert _audit(aid) == original_a
        assert _audit(bid) == original_b
        assert temporary_missing.read_bytes() == b_bytes
    finally:
        temporary_missing.rename(b_source)

    _assert_original_readable(client, bid, b_source, b_bytes)
    assert _audit(aid) == original_a
    assert _audit(bid) == original_b
    assert sorted((home / "datasets").iterdir()) == sorted([a_source, b_source])


def test_real_api_transient_503_on_other_profile_cannot_damage_current_project(monkeypatch, tmp_path):
    """Inject only one B profile error into real FastAPI; A must still work."""
    client, _home, projects = _isolated_client(monkeypatch, tmp_path)
    aid, a_source, a_bytes = projects["A"]
    bid, b_source, b_bytes = projects["B"]
    original_a, original_b = _audit(aid), _audit(bid)
    real_current_data = quality.current_data

    def scoped_outage(project_id):
        if project_id == bid:
            raise quality.QualityError("Synthetic destination profile unavailable", 503)
        return real_current_data(project_id)

    with monkeypatch.context() as temporary:
        temporary.setattr(quality, "current_data", scoped_outage)
        assert client.get(f"/api/projects/{bid}").status_code == 200
        failed = client.get(f"/api/projects/{bid}/live-profile")
        assert failed.status_code == 503, failed.text
        assert failed.json()["detail"] == "Synthetic destination profile unavailable"
        _assert_original_readable(client, aid, a_source, a_bytes)
        assert _audit(aid) == original_a
        assert _audit(bid) == original_b
    _assert_original_readable(client, bid, b_source, b_bytes)
    assert _audit(aid) == original_a
    assert _audit(bid) == original_b
