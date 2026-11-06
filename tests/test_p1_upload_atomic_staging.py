"""P1 import byte staging: recoverable I/O failures leave no partial project source.

All tests use a temporary project database; never access a user's workspace.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

from fastapi.testclient import TestClient

from backend import main, quality, storage


def _isolated(monkeypatch, tmp_path):
    home=tmp_path/"isolated-upload"
    (home/"datasets").mkdir(parents=True)
    (home/"models").mkdir()
    monkeypatch.setattr(storage,"HOME",home)
    monkeypatch.setattr(storage,"DB_PATH",home/"pilotodin.sqlite3")
    storage.init()
    quality._init_tables()
    return home


def _data():
    return b"CustomerID,Revenue\n0001,100\n0002,200\n0003,300\n"


def _upload():
    return TestClient(main.app).post(
        "/api/projects",
        files={"file":("source.csv",_data(),"text/csv")},
    )


def _empty(home):
    assert storage.list_projects()==[]
    assert list((home/"datasets").iterdir())==[]
    with storage.connect() as con:
        for name in ("projects","quality_state","quality_versions"):
            assert con.execute("SELECT COUNT(*) FROM "+name).fetchone()[0]==0


def test_fsync_failure_cleans_partial_upload_before_metadata(monkeypatch,tmp_path):
    home=_isolated(monkeypatch,tmp_path)
    def interrupted(_fd):
        raise OSError("Synthetic disk synchronization failure")
    monkeypatch.setattr(main.os,"fsync",interrupted)
    response=_upload()
    assert response.status_code==422,response.text
    assert "Synthetic disk synchronization failure" in response.json()["detail"]
    _empty(home)


def test_replace_failure_cleans_temporary_upload(monkeypatch,tmp_path):
    home=_isolated(monkeypatch,tmp_path)
    def interrupted(_src,_dst):
        raise OSError("Synthetic atomic rename failure")
    monkeypatch.setattr(main.os,"replace",interrupted)
    response=_upload()
    assert response.status_code==422,response.text
    assert "Synthetic atomic rename failure" in response.json()["detail"]
    _empty(home)


def test_successful_import_pins_complete_original_sha_and_no_staging(monkeypatch,tmp_path):
    home=_isolated(monkeypatch,tmp_path)
    response=_upload()
    assert response.status_code==201,response.text
    pid=response.json()["id"]
    project=storage.get_project(pid)
    source=Path(project["dataset_path"])
    assert source.parent==home/"datasets"
    assert source.read_bytes()==_data()
    assert sorted(p.name for p in (home/"datasets").iterdir())==[source.name]
    with storage.connect() as con:
        state=con.execute("SELECT original_sha256,current_version FROM quality_state WHERE project_id=?",(pid,)).fetchone()
        assert state is not None
        assert state["original_sha256"]==hashlib.sha256(_data()).hexdigest()
        assert state["current_version"]==0


def test_bad_content_after_atomic_publish_still_rolls_back(monkeypatch,tmp_path):
    home=_isolated(monkeypatch,tmp_path)
    response=TestClient(main.app).post(
        "/api/projects",files={"file":("invalid.csv",b"only_column\nhello\n","text/csv")}
    )
    assert response.status_code==422,response.text
    _empty(home)
