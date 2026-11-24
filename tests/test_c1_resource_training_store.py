"""Real disposable SQLite and FastAPI background integration; no model fit."""
import asyncio
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier, Event

import httpx
import pytest
from fastapi import BackgroundTasks, FastAPI, HTTPException, Request

from backend import storage, resource_training_store as durable
from backend.resource_admission import Coordinator, GIB, Operation
from backend.resource_training import TrainingHTTP, training_owner


@pytest.fixture
def project(monkeypatch, tmp_path):
    home = tmp_path / "training-store"
    (home / "datasets").mkdir(parents=True)
    (home / "models").mkdir()
    monkeypatch.setattr(storage, "HOME", home)
    monkeypatch.setattr(storage, "DB_PATH", home / "pilotodin.sqlite3")
    storage.init()
    source = home / "datasets" / "fixture.csv"
    source.write_bytes(b"a,b\n1,2\n")
    return storage.save_project("Fixture", "fixture.csv", ".csv", source, {"rows": 1})


def queue(project, single=True):
    create = storage.new_experiment_with_capacity if single else storage.new_experiment
    return create(project, {})


def coordinator(memory=3 * GIB):
    return Coordinator(lambda: "adaptive", lambda: memory)


def test_exact_settlement_preserves_other_queued_records(project):
    eid = queue(project)
    other = queue(project, single=False)
    assert durable.settle_unstarted(eid)
    record = storage.get_experiment(eid)
    assert record["status"] == "failed"
    assert [x["stage"] for x in record["progress"]["history"]] == ["queued", "failed"]
    assert durable.terminal(eid)
    assert durable.settle_unstarted(eid)
    assert len(storage.get_experiment(eid)["progress"]["history"]) == 2
    assert storage.get_experiment(other)["status"] == "queued"
    assert not storage.claim_queued_experiment(eid)


def test_settlement_releases_existing_durable_slot(project):
    eid = queue(project)
    with pytest.raises(storage.TrainingSlotBusy):
        queue(project)
    assert durable.settle_unstarted(eid)
    next_id = queue(project)
    assert next_id != eid
    assert storage.get_experiment(next_id)["status"] == "queued"


def test_running_and_missing_records_are_not_settled(project):
    eid = queue(project)
    assert storage.claim_queued_experiment(eid)
    assert not durable.settle_unstarted(eid)
    assert not durable.terminal(eid)
    assert not durable.settle_unstarted("missing")
    assert not durable.terminal("missing")
    assert storage.get_experiment(eid)["status"] == "running"
    assert storage.finish_running_experiment(eid, "failed", error="Synthetic worker stopped")
    assert durable.terminal(eid)
    assert not durable.settle_unstarted(eid)


def test_queued_cancel_is_preserved(project):
    eid = queue(project)
    assert storage.request_training_cancel(eid) == "cancelled"
    before = storage.get_experiment(eid)
    assert durable.settle_unstarted(eid)
    assert durable.terminal(eid)
    assert storage.get_experiment(eid) == before


def test_inconsistent_status_is_not_a_witness(project):
    eid = queue(project)
    with storage.connect() as con:
        con.execute("UPDATE experiments SET status='failed' WHERE id=?", (eid,))
    assert not durable.terminal(eid)
    assert not durable.settle_unstarted(eid)
    assert storage.get_experiment(eid)["progress"]["stage"] == "queued"


def test_progress_failure_rolls_back_exact_settlement(project, monkeypatch):
    eid = queue(project)
    def fail(*args):
        raise OSError("fixture progress failure")
    monkeypatch.setattr(storage, "_append_progress", fail)
    with pytest.raises(OSError, match="fixture progress"):
        durable.settle_unstarted(eid)
    assert storage.get_experiment(eid)["status"] == "queued"
    assert not durable.terminal(eid)


def test_real_claim_vs_settlement_race(project):
    eid = queue(project)
    barrier = Barrier(2)
    def claim():
        barrier.wait(timeout=5)
        return storage.claim_queued_experiment(eid)
    def settle():
        barrier.wait(timeout=5)
        return durable.settle_unstarted(eid)
    with ThreadPoolExecutor(max_workers=2) as pool:
        a, b = pool.submit(claim), pool.submit(settle)
        claimed, settled = a.result(10), b.result(10)
    assert claimed != settled
    assert storage.get_experiment(eid)["status"] == ("running" if claimed else "failed")


def make_app(project, c, worker, *, reject=False, register=True):
    app = FastAPI()
    ids = []
    @app.post("/train", status_code=202)
    def train(request: Request, background_tasks: BackgroundTasks):
        owner = training_owner(request.scope)
        assert c.status()["phase"] == "reserved"
        assert c.try_acquire(Operation.DATA).code == "resource_busy"
        if reject:
            raise HTTPException(status_code=422, detail="Synthetic validation refusal")
        owner.publication_started()
        eid = queue(project)
        ids.append(eid)
        callback = owner.bind(eid, worker, durable.settle_unstarted, durable.terminal)
        if register:
            background_tasks.add_task(callback)
        return {"id": eid, "status": "queued"}
    return TrainingHTTP(app,c), ids


async def post(app):
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),
                                 base_url="http://testserver") as client:
        return await client.post("/train")


def test_http_denial_and_validation_do_not_create_queue(project):
    for memory,reject,code in ((0,False,503),(3*GIB,True,422)):
        c = coordinator(memory)
        app, ids = make_app(project,c,lambda eid: pytest.fail("worker"),reject=reject)
        result = asyncio.run(post(app))
        assert result.status_code == code and not ids
        assert not c.status()["active"]
    with storage.connect() as con:
        assert con.execute("SELECT COUNT(*) FROM experiments").fetchone()[0] == 0


def test_actual_background_worker_holds_lane_until_durable_terminal(project):
    async def scenario():
        c = coordinator()
        entered, resume = Event(), Event()
        def worker(eid):
            assert storage.claim_queued_experiment(eid)
            assert c.status()["phase"] == "running"
            entered.set()
            assert resume.wait(5)
            assert storage.finish_running_experiment(eid,"failed",error="Inert fixture stopped")
        app, ids = make_app(project,c,worker)
        task = asyncio.create_task(post(app))
        try:
            assert await asyncio.to_thread(entered.wait,5)
            assert not task.done()
            assert storage.get_experiment(ids[0])["status"] == "running"
            assert c.try_acquire(Operation.EXPORT).code == "resource_busy"
        finally:
            resume.set()
        result = await asyncio.wait_for(task,10)
        assert result.status_code == 202
        assert durable.terminal(ids[0])
        assert not c.status()["active"]
    asyncio.run(scenario())


def test_return_without_background_registration_settles_exact_queue(project):
    c = coordinator()
    app, ids = make_app(project,c,lambda eid: pytest.fail("worker"),register=False)
    assert asyncio.run(post(app)).status_code == 202
    assert durable.terminal(ids[0])
    assert storage.get_experiment(ids[0])["status"] == "failed"
    assert not c.status()["active"]


def test_failed_response_delivery_settles_before_callback(project):
    c = coordinator()
    app, ids = make_app(project,c,lambda eid: pytest.fail("worker started"))
    async def broken(scope, receive, send):
        async def fail_send(message):
            raise OSError("synthetic response delivery failure")
        await app(scope,receive,fail_send)
    with pytest.raises(OSError,match="response delivery"):
        asyncio.run(post(broken))
    assert len(ids) == 1 and durable.terminal(ids[0])
    assert storage.get_experiment(ids[0])["status"] == "failed"
    assert not c.status()["active"]


def test_worker_return_without_terminal_state_blocks_lane(project):
    c = coordinator()
    def worker(eid):
        assert storage.claim_queued_experiment(eid)
    app, ids = make_app(project,c,worker)
    assert asyncio.run(post(app)).status_code == 202
    assert storage.get_experiment(ids[0])["status"] == "running"
    assert c.status()["phase"] == "blocked"
    assert c.try_acquire(Operation.DATA).code == "ownership_unknown"


def test_worker_exception_retains_actual_running_record(project):
    c = coordinator()
    def worker(eid):
        assert storage.claim_queued_experiment(eid)
        raise OSError("synthetic worker failure")
    app, ids = make_app(project,c,worker)
    with pytest.raises(OSError,match="worker failure"):
        asyncio.run(post(app))
    assert storage.get_experiment(ids[0])["status"] == "running"
    assert c.status()["phase"] == "blocked"
