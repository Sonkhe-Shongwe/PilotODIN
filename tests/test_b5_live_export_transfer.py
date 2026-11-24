"""Real export route plus direct ASGI fault injection, disposable source only."""
import hashlib
import errno
from concurrent.futures import ThreadPoolExecutor
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
        response=client.post(f"/api/projects/{pid}/quality/export",
                             json={"version":0,"format":fmt},
                             headers={"Origin":"https://tauri.localhost"})
    assert response.status_code==200,response.text
    r,=receipts()
    assert r.state=="released" and r.project_id==pid and r.quality_version==0 and r.format==fmt
    assert r.expected_bytes==len(response.content)==int(response.headers["content-length"])
    assert r.sha256==hashlib.sha256(response.content).hexdigest()==response.headers["x-pilotodin-export-sha256"]
    assert response.headers["access-control-allow-origin"]=="https://tauri.localhost"
    exposed={name.strip().lower() for name in response.headers["access-control-expose-headers"].split(",")}
    assert {"content-disposition","content-length","x-pilotodin-dataset-version",
            "x-pilotodin-exported-rows","x-pilotodin-export-sha256"} <= exposed
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

def test_archive_after_stage_refuses_transfer_and_releases_scratch(project,monkeypatch):
    pid,home,path,raw=project
    real=storage.advance_export_publication
    def archive_after_stage(receipt,state,**metadata):
        actual=real(receipt,state,**metadata)
        if state=="staged":
            main.project_lifecycle.change(pid,"archive",0)
        return actual
    monkeypatch.setattr(storage,"advance_export_publication",archive_after_stage)
    response=TestClient(main.app).post(f"/api/projects/{pid}/quality/export",json={"version":0})
    assert response.status_code==409
    r,=receipts()
    assert r.state=="interrupted" and r.reason_code=="validation_failed"
    assert list((home/"export_tmp").iterdir())==[]
    assert path.read_bytes()==raw


@pytest.mark.parametrize("error",[errno.EACCES,errno.ENOSPC])
def test_write_failure_settles_without_deleting_foreign_scratch(project,monkeypatch,error):
    pid,home,path,raw=project
    scratch=home/"export_tmp"
    scratch.mkdir()
    foreign=scratch/"foreign.csv"
    foreign.write_bytes(b"foreign")
    def fail(frame,output):
        output.write(b"partial")
        raise OSError(error,"synthetic write refusal")
    monkeypatch.setattr(data_exports,"_write_csv",fail)
    response=TestClient(main.app).post(f"/api/projects/{pid}/quality/export",json={"version":0})
    assert response.status_code==503
    r,=receipts()
    assert r.state=="blocked" and r.reason_code=="storage_unavailable"
    assert list(scratch.iterdir())==[foreign]
    assert foreign.read_bytes()==b"foreign" and path.read_bytes()==raw


def test_receipt_lookup_failure_preserves_payload_and_pending_receipt(project,monkeypatch):
    pid,home,path,raw=project
    transfer=export_transfer.Transfer()
    transfer.prepare(pid,data_exports.ExportRequest(version=0))
    def unavailable(*args,**kwargs):
        raise OSError("synthetic receipt read failure")
    with monkeypatch.context() as patch:
        patch.setattr(ledger,"read",unavailable)
        transfer.finish(True)
    assert transfer.stream.closed and transfer.uncertain
    assert transfer.path.exists()
    r,=receipts()
    assert r.state=="transferring"
    assert hashlib.sha256(transfer.path.read_bytes()).hexdigest()==r.sha256
    assert path.read_bytes()==raw


def test_unlink_failure_does_not_certify_release(project,monkeypatch):
    pid,home,path,raw=project
    def refuse(*args,**kwargs):
        raise PermissionError("synthetic unlink refusal")
    monkeypatch.setattr(storage,"guarded_unlink",refuse)
    response=TestClient(main.app).post(f"/api/projects/{pid}/quality/export",json={"version":0})
    assert response.status_code==200
    r,=receipts()
    assert r.state=="blocked" and r.reason_code=="storage_unavailable"
    assert (home/"export_tmp"/r.filename).read_bytes()==response.content
    assert path.read_bytes()==raw


def test_modified_payload_refuses_final_chunk(project,monkeypatch):
    pid,home,path,raw=project
    monkeypatch.setattr(export_transfer,"CHUNK",8)
    sent=[]
    async def send(message):
        if message["type"]=="http.response.start":
            r,=receipts()
            scratch=home/"export_tmp"/r.filename
            with scratch.open("r+b") as f:
                f.write(b"changed!")
        elif message["type"]=="http.response.body":
            sent.append(message)
    with pytest.raises(Exception):
        asgi_response(pid,send)
    r,=receipts()
    assert r.state=="blocked"
    assert not sent
    assert (home/"export_tmp"/r.filename).exists()
    assert path.read_bytes()==raw


def test_concurrent_live_exports_independent_receipts(project):
    pid,home,path,raw=project
    # Startup recovery must never run concurrently with live requests.
    def request(fmt):
        client=TestClient(main.app)
        try:
            result=client.post(f"/api/projects/{pid}/quality/export",json={"version":0,"format":fmt})
            assert result.status_code==200,result.text
            return fmt,hashlib.sha256(result.content).hexdigest()
        finally:
            client.close()
    with ThreadPoolExecutor(max_workers=2) as pool:
        results=dict(pool.map(request,("csv","xlsx")))
    rows=receipts()
    assert len(rows)==2 and all(r.state=="released" for r in rows)
    assert {r.format:r.sha256 for r in rows}==results
    assert list((home/"export_tmp").iterdir())==[]
    assert path.read_bytes()==raw


def test_real_75_mib_output_extent_and_one_byte_refusal(tmp_path):
    limit=ledger.MAX_EXPORT_BYTES
    path=tmp_path/"generated.bin"
    with path.open("w+b") as stream:
        output=data_exports._BoundedOutput(stream,limit)
        block=b"x"*(1024*1024)
        for _ in range(75):
            output.write(block)
        output.flush()
        assert os.fstat(stream.fileno()).st_size==limit==output.extent
        with pytest.raises(quality.QualityError) as exc:
            output.write(b"x")
        assert exc.value.status==413
        assert os.fstat(stream.fileno()).st_size==limit

def test_unconfirmed_close_preserves_scratch_and_blocks_release(project):
    pid,home,path,raw=project
    transfer=export_transfer.Transfer()
    transfer.prepare(pid,data_exports.ExportRequest(version=0))
    original=transfer.stream
    class CloseRefusal:
        def fileno(self):
            return original.fileno()
        def close(self):
            raise PermissionError("synthetic close refusal")
    transfer.stream=CloseRefusal()
    try:
        transfer.finish(True)
        r,=receipts()
        assert r.state=="blocked" and r.reason_code=="storage_unavailable"
        assert transfer.path.exists()
        assert hashlib.sha256(transfer.path.read_bytes()).hexdigest()==r.sha256
        assert path.read_bytes()==raw
    finally:
        original.close()


def test_export_metadata_requires_desktop_session_and_allowed_origin(project,monkeypatch):
    pid,home,path,raw=project
    secret="synthetic-export-session"
    monkeypatch.setenv("PILOTODIN_DESKTOP_SESSION",secret)
    monkeypatch.delenv("PILOTODIN_DESKTOP_ALLOW_DEV",raising=False)
    endpoint=f"/api/projects/{pid}/quality/export"
    with TestClient(main.app) as client:
        for headers,version,status in (
            ({"Origin":"https://tauri.localhost"},0,401),
            ({"Origin":"https://untrusted.invalid","X-PilotODIN-Session":secret},0,403),
            ({"Origin":"https://tauri.localhost","X-PilotODIN-Session":secret},99,404),
        ):
            rejected=client.post(endpoint,json={"version":version},headers=headers)
            assert rejected.status_code==status,rejected.text
            assert "x-pilotodin-export-sha256" not in rejected.headers
        assert receipts()==[] and not (home/"export_tmp").exists()
        accepted=client.post(endpoint,json={"version":0},headers={
            "Origin":"https://tauri.localhost","X-PilotODIN-Session":secret})
    assert accepted.status_code==200,accepted.text
    receipt,=receipts()
    assert receipt.state=="released"
    assert accepted.headers["x-pilotodin-export-sha256"]==receipt.sha256==hashlib.sha256(accepted.content).hexdigest()
    assert accepted.headers["access-control-allow-origin"]=="https://tauri.localhost"
    assert path.read_bytes()==raw and list((home/"export_tmp").iterdir())==[]


def test_attestation_canonical_vector_and_refusals(monkeypatch):
    from backend import export_attestation
    from dataclasses import replace
    receipt = ledger.Receipt("b"*32, "a"*32, 7, "csv", 1, 25, "c"*64,
                             "transferring", None, "now", "now")
    monkeypatch.setenv("PILOTODIN_DESKTOP_SESSION", "2"*64)
    monkeypatch.setenv(export_attestation.KEY_ENV, "1"*64)
    expected = "6e628fe3aaae0e3f2d01ddc839d74b607b730b09f893108632ef63dde2e55fb3"
    filename = "Generated_cleaned_v7_filtered.csv"
    assert export_attestation.headers_for_transfer(receipt, filename, 2)["X-PilotODIN-Export-MAC"] == expected
    assert export_attestation.headers_for_transfer(receipt, filename, 3)["X-PilotODIN-Export-MAC"] != expected
    with pytest.raises(ledger.PublicationError):
        export_attestation.headers_for_transfer(receipt, "../"+filename, 2)
    with pytest.raises(ledger.PublicationError):
        export_attestation.headers_for_transfer(replace(receipt, state="released"), filename, 2)
    monkeypatch.setenv(export_attestation.KEY_ENV, "2"*64)
    with pytest.raises(ledger.PublicationError):
        export_attestation.headers_for_transfer(receipt, filename, 2)
    monkeypatch.delenv(export_attestation.KEY_ENV)
    assert export_attestation.headers_for_transfer(receipt, filename, 2) == {}


@pytest.mark.parametrize("fmt", ["csv", "xlsx"])
def test_live_attestation_binds_receipt_and_response(project, monkeypatch, fmt):
    import hmac
    pid,home,path,raw=project
    secret="2"*64
    key="1"*64
    monkeypatch.setenv("PILOTODIN_DESKTOP_SESSION",secret)
    monkeypatch.setenv("PILOTODIN_DATASET_EXPORT_KEY",key)
    with TestClient(main.app) as client:
        response=client.post(f"/api/projects/{pid}/quality/export",
                             json={"version":0,"format":fmt},
                             headers={"Origin":"https://tauri.localhost","X-PilotODIN-Session":secret})
    assert response.status_code==200,response.text
    r,=receipts()
    assert r.state=="released"
    assert response.headers["x-pilotodin-export-project"]==pid
    assert response.headers["x-pilotodin-export-operation"]==r.operation_id
    filename=response.headers["content-disposition"].split('"')[1]
    message="\n".join(("PilotODIN/export-receipt/v1",pid,r.operation_id,"0",fmt,
                       str(len(response.content)),hashlib.sha256(response.content).hexdigest(),
                       filename,"2",""))
    assert response.headers["x-pilotodin-export-mac"]==hmac.digest(key.encode(),message.encode(),"sha256").hex()
    assert key not in str(response.headers) and secret not in str(response.headers)
    assert "x-pilotodin-export-mac" in response.headers["access-control-expose-headers"].lower()
    assert path.read_bytes()==raw and list((home/"export_tmp").iterdir())==[]
