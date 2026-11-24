"""Real export route plus direct ASGI fault injection, disposable source only."""
import hashlib
import os
from pathlib import Path

import anyio
import pytest
from fastapi.testclient import TestClient
from backend import data_exports, export_publication as ledger, export_transfer, main, quality, storage


@pytest.fixture
def project(tmp_path,monkeypatch):
    home=tmp_path/"workspace"
    (home/"datasets").mkdir(parents=True)
    (home/"models").mkdir()
    monkeypatch.setattr(storage,"HOME",home)
    monkeypatch.setattr(storage,"DB_PATH",home/"pilotodin.sqlite3")
    storage.init()
    quality._init_tables()
    raw=b"OrderID,Note,Amount\n0001,=SUM(1),12\n0002,Normal,3\n"
    path=home/"datasets"/"source.csv"
    path.write_bytes(raw)
    pid=storage.save_project("Generated",path.name,".csv",path,{},
                             original_sha256=hashlib.sha256(raw).hexdigest())
    return pid,home,path,raw


def receipts():
    with storage.connect() as con:
        ids=con.execute("SELECT operation_id FROM export_publications_v1 ORDER BY operation_id").fetchall()
        return [ledger.read(con,row[0]) for row in ids]


@pytest.mark.parametrize("fmt",["csv","xlsx"])
def test_live_route_binds_exact_bytes_and_releases_scratch(project,fmt):
    pid,home,path,raw=project
    with TestClient(main.app) as client:
        response=client.post(f"/api/projects/{pid}/quality/export",json={"version":0,"format":fmt})
    assert response.status_code==200,response.text
    r,=receipts()
    assert r.state=="released" and r.project_id==pid and r.quality_version==0 and r.format==fmt
    assert r.expected_bytes==len(response.content)==int(response.headers["content-length"])
    assert r.sha256==hashlib.sha256(response.content).hexdigest()
    assert response.headers["x-pilotodin-dataset-version"]=="0"
    assert response.headers["x-pilotodin-exported-rows"]=="2"
    assert list((home/"export_tmp").iterdir())==[]
    assert path.read_bytes()==raw


def asgi_response(pid,send,*,receive=None,spec="2.4"):
    async def wait_receive():
        await anyio.sleep_forever()
    async def run():
        await export_transfer.ExportResponse(pid,data_exports.ExportRequest(version=0))(
            {"type":"http","asgi":{"spec_version":spec}},receive or wait_receive,send)
    anyio.run(run)


def test_send_failure_settles_interrupted(project,monkeypatch):
    pid,home,path,raw=project
    monkeypatch.setattr(export_transfer,"CHUNK",8)
    async def send(message):
        if message["type"]=="http.response.body":
            raise OSError("synthetic disconnect")
    with pytest.raises(Exception):
        asgi_response(pid,send)
    r,=receipts()
    assert r.state=="interrupted" and r.reason_code=="cancelled"
    assert list((home/"export_tmp").iterdir())==[] and path.read_bytes()==raw


def test_disconnect_before_first_body_releases_own_scratch(project):
    pid,home,path,raw=project
    async def receive():
        return {"type":"http.disconnect"}
    async def send(message):
        await anyio.sleep_forever()
    asgi_response(pid,send,receive=receive,spec="2.3")
    r,=receipts()
    assert r.state=="interrupted"
    assert list((home/"export_tmp").iterdir())==[] and path.read_bytes()==raw


def test_commit_ack_failure_preserves_owned_bytes(project,monkeypatch):
    pid,home,path,raw=project
    real=storage.advance_export_publication
    def uncertain(receipt,state,**metadata):
        actual=real(receipt,state,**metadata)
        if state=="staged":
            raise OSError("synthetic lost commit acknowledgement")
        return actual
    monkeypatch.setattr(storage,"advance_export_publication",uncertain)
    response=TestClient(main.app).post(f"/api/projects/{pid}/quality/export",json={"version":0})
    assert response.status_code==503
    r,=receipts()
    assert r.state=="staged"
    scratch=home/"export_tmp"/r.filename
    assert scratch.stat().st_size==r.expected_bytes
    assert hashlib.sha256(scratch.read_bytes()).hexdigest()==r.sha256
    assert storage.recover_export_publications()==1
    assert scratch.exists() and path.read_bytes()==raw


def test_name_collision_never_unlinks_foreign_file(project,monkeypatch):
    pid,home,path,raw=project
    real=storage.begin_export_publication
    def collide(*args):
        r=real(*args)
        (home/"export_tmp").mkdir(exist_ok=True)
        (home/"export_tmp"/r.filename).write_bytes(b"foreign")
        return r
    monkeypatch.setattr(storage,"begin_export_publication",collide)
    response=TestClient(main.app).post(f"/api/projects/{pid}/quality/export",json={"version":0})
    assert response.status_code==409
    r,=receipts()
    assert r.state=="blocked" and r.reason_code=="collision"
    assert (home/"export_tmp"/r.filename).read_bytes()==b"foreign"
    assert path.read_bytes()==raw


def test_foreign_replacement_at_transfer_preserved(project):
    pid,home,path,raw=project
    async def send(message):
        if message["type"]=="http.response.start":
            r,=receipts()
            scratch=home/"export_tmp"/r.filename
            scratch.rename(scratch.with_suffix(".retained"))
            scratch.write_bytes(b"foreign replacement")
    with pytest.raises(Exception):
        asgi_response(pid,send)
    r,=receipts()
    assert r.state=="blocked"
    assert (home/"export_tmp"/r.filename).read_bytes()==b"foreign replacement"
    assert path.read_bytes()==raw


def test_invalid_version_no_receipt_or_scratch(project):
    pid,home,path,raw=project
    response=TestClient(main.app).post(f"/api/projects/{pid}/quality/export",json={"version":99})
    assert response.status_code==404
    assert receipts()==[] and not (home/"export_tmp").exists()
    assert path.read_bytes()==raw
