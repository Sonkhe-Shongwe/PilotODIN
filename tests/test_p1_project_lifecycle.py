"""Disposable project lifecycle API acceptance, no owner database or files accessed."""
from __future__ import annotations

import hashlib
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend import main, quality, storage


@pytest.fixture
def workspace(monkeypatch, tmp_path):
    home = tmp_path / "synthetic-project-lifecycle"
    (home / "datasets").mkdir(parents=True)
    (home / "models").mkdir()
    monkeypatch.setattr(storage, "HOME", home)
    monkeypatch.setattr(storage, "DB_PATH", home / "pilotodin.sqlite3")
    storage.init()
    quality._init_tables()
    client = TestClient(main.app)
    ids = []
    sources = []
    for name in ("alpha", "beta"):
        payload = ("Key,Amount,Flag\n" + "".join(
            f"{name}{i:03d},{i*11},{'yes' if i%2 else 'no'}\n" for i in range(1, 19)
        )).encode()
        result = client.post(
            "/api/projects",files={"file":(name+".csv", payload,"text/csv")}
        )
        assert result.status_code == 201, result.text
        pid = result.json()["id"]
        ids.append(pid)
        path = Path(storage.get_project(pid)["dataset_path"])
        sources.append((path,payload,hashlib.sha256(payload).hexdigest()))
    return client, home, ids, sources


def _change(client, pid, action, revision, *, name=None):
    body = {"action":action,"expected_revision":revision}
    if name is not None:
        body["name"] = name
    return client.put(f"/api/projects/{pid}/lifecycle",json=body)


def test_rename_archive_restore_retains_all_original_bytes_quality_and_identity(workspace):
    client, home, (a,b), sources = workspace
    a_path,a_bytes,a_digest = sources[0]
    b_path,b_bytes,b_digest = sources[1]
    with storage.connect() as con:
        before = con.execute(
            "SELECT original_sha256,current_version FROM quality_state WHERE project_id=?", (a,)
        ).fetchone()
        before = tuple(before)
    initial = client.get("/api/projects/manage").json()
    assert {(r["id"],r["revision"],r["archived_at"]) for r in initial} == {
        (a,0,None),(b,0,None)
    }
    assert _change(client,a,"rename",0,name="  Analysis One  ").json()["name"] == "Analysis One"
    assert client.get(f"/api/projects/{a}").json()["name"] == "Analysis One"
    archived = _change(client,a,"archive",1)
    assert archived.status_code == 200, archived.text
    assert archived.json()["revision"] == 2
    assert archived.json()["archived_at"] is not None
    assert {x["id"] for x in client.get("/api/projects").json()} == {b}
    assert client.get(f"/api/projects/{a}").status_code == 404
    assert client.get(f"/api/projects/{a}/quality").status_code == 404
    assert {x["id"] for x in client.get("/api/projects/manage").json()} == {a,b}
    restored = _change(client,a,"restore",2)
    assert restored.status_code == 200,restored.text
    assert restored.json()["revision"] == 3
    assert restored.json()["archived_at"] is None
    assert client.get(f"/api/projects/{a}").json()["name"] == "Analysis One"
    assert {x["id"] for x in client.get("/api/projects").json()} == {a,b}
    assert a_path.read_bytes() == a_bytes
    assert b_path.read_bytes() == b_bytes
    assert hashlib.sha256(a_path.read_bytes()).hexdigest() == a_digest
    assert hashlib.sha256(b_path.read_bytes()).hexdigest() == b_digest
    with storage.connect() as con:
        after = con.execute(
            "SELECT original_sha256,current_version FROM quality_state WHERE project_id=?", (a,)
        ).fetchone()
        assert tuple(after) == before
        assert con.execute("SELECT COUNT(*) FROM quality_versions WHERE project_id=?", (a,)).fetchone()[0] == 1
        assert con.execute("SELECT COUNT(*) FROM projects").fetchone()[0] == 2
    # No filesystem cleanup or backdoor delete occurs.
    assert sorted(home.joinpath("datasets").iterdir()) == sorted([a_path,b_path])


def test_stale_revision_and_invalid_names_fail_without_mutations(workspace):
    client,_home,(a,b),sources=workspace
    assert _change(client,a,"rename",0,name="Team Review").status_code == 200
    assert _change(client,a,"archive",0).status_code == 409
    assert _change(client,a,"rename",0,name="Stale").status_code == 409
    for name in (" ","X"*81,"Bad\nName"):
        response = _change(client,a,"rename",1,name=name)
        assert response.status_code == 422,response.text
    assert _change(client,b,"rename",0,name="Team Review").status_code == 409
    assert _change(client,"f"*32,"archive",0).status_code == 404
    assert _change(client,a,"restore",1).status_code == 409
    assert client.delete(f"/api/projects/{a}/lifecycle").status_code == 405
    a_row=next(p for p in client.get("/api/projects/manage").json() if p["id"]==a)
    assert a_row["name"] == "Team Review" and a_row["revision"]==1 and a_row["archived_at"] is None
    for path,payload,_ in sources:
        assert path.read_bytes()==payload


def test_active_training_and_odin_runs_fail_closed_before_archive(workspace):
    client,_home,(a,_b),sources=workspace
    eid=storage.new_experiment(a,{"target":"Flag"})
    blocked=_change(client,a,"archive",0)
    assert blocked.status_code==409
    assert "training" in blocked.json()["detail"].lower()
    with storage.connect() as con:
        con.execute("UPDATE experiments SET status='completed' WHERE id=?",(eid,))
        # Simulate a still-running ODIN job with only disposable metadata.
        con.execute("CREATE TABLE odin_runs (id TEXT,project_id TEXT,status TEXT)")
        con.execute("INSERT INTO odin_runs VALUES (?,?,?)",("synthetic-job",a,"running"))
    blocked=_change(client,a,"archive",0)
    assert blocked.status_code==409
    assert "ODIN" in blocked.json()["detail"]
    with storage.connect() as con:
        con.execute("UPDATE odin_runs SET status='failed'")
    ok=_change(client,a,"archive",0)
    assert ok.status_code==200,ok.text
    assert ok.json()["revision"]==1
    for path,payload,_ in sources:
        assert path.read_bytes()==payload
