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


def production_fixture(project, c, monkeypatch, *, queue_error=None):
    """Use actual endpoint body, real SQLite queue and an inert worker."""
    from backend import main
    import pandas as pd
    frame = pd.DataFrame({"feature": [1,2,3], "target": [0,1,0]})
    calls = []
    def current_data(pid):
        assert pid == project
        assert c.status()["phase"] == "reserved"
        return frame, 0
    monkeypatch.setattr(main.quality, "current_data", current_data)
    monkeypatch.setattr(main.engine, "validate_config",
                        lambda *args, **kwargs: (frame[["feature"]], None, None))
    monkeypatch.setattr(main.engine, "check_categorical_missing_marker", lambda *args: None)
    monkeypatch.setattr(main.engine, "preparation", lambda *args: {"high_risk_features":[]})
    monkeypatch.setattr(main.resource_policy, "admit_new_work",
                        lambda *args: pytest.fail("Owned route must not use parallel admission"))
    monkeypatch.setattr(main.engine, "run_training",
                        lambda *args, **kwargs: pytest.fail("Model fit prohibited"))
    # Fixture project is metadata-only; the test verifies queue/worker binding,
    # not Quality materialization or model publication.
    with storage.connect() as con:
        con.execute("CREATE TABLE IF NOT EXISTS quality_state "
                    "(project_id TEXT PRIMARY KEY, original_sha256 TEXT, current_version INTEGER)")
        con.execute("INSERT INTO quality_state VALUES (?, ?, 0)", (project, "0"*64))
    def worker(eid, pid, config):
        assert pid == project and config["quality_version"] == 0
        assert c.status()["phase"] == "running"
        assert storage.claim_queued_experiment(eid)
        calls.append(eid)
        assert storage.finish_running_experiment(eid,"failed",error="Inert fixture stopped")
    monkeypatch.setattr(main,"train_background",worker)
    if queue_error is not None:
        monkeypatch.setattr(storage,"new_experiment_with_capacity",queue_error)
    # Register the existing endpoint on an isolated FastAPI router, not the
    # production app. The trusted wrapper is supplied only by this fixture.
    app = FastAPI()
    app.post("/api/projects/{project_id}/experiments", status_code=202)(main.new_experiment)
    return TrainingHTTP(app,c), calls


async def production_post(app, project):
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),
                                 base_url="http://testserver") as client:
        return await client.post(f"/api/projects/{project}/experiments",json={
            "target":"target","task":"classification","models":["logistic"],
            "acknowledge_random_split":True,"expected_quality_version":0})


def test_actual_production_endpoint_binds_existing_worker(project, monkeypatch):
    c = coordinator()
    app,calls = production_fixture(project,c,monkeypatch)
    result = asyncio.run(production_post(app,project))
    assert result.status_code == 202, result.text
    eid = result.json()["id"]
    assert calls == [eid] and durable.terminal(eid)
    assert not c.status()["active"]


def test_actual_production_endpoint_known_slot_refusal_releases(project, monkeypatch):
    c = coordinator()
    existing = queue(project)
    app,calls = production_fixture(project,c,monkeypatch)
    result = asyncio.run(production_post(app,project))
    assert result.status_code == 503, result.text
    assert result.json()["detail"]["code"] == "ml_training_slot_busy"
    assert not calls and storage.get_experiment(existing)["status"] == "queued"
    assert not c.status()["active"]


def test_actual_production_endpoint_unknown_queue_ack_blocks(project, monkeypatch):
    c = coordinator()
    real = storage.new_experiment_with_capacity
    ids = []
    def lost_ack(*args, **kwargs):
        ids.append(real(*args, **kwargs))
        raise OSError("synthetic queue acknowledgement loss")
    app,calls = production_fixture(project,c,monkeypatch,queue_error=lost_ack)
    with pytest.raises(OSError,match="acknowledgement"):
        asyncio.run(production_post(app,project))
    assert len(ids) == 1 and not calls
    assert storage.get_experiment(ids[0])["status"] == "queued"
    assert c.status()["phase"] == "blocked"


def test_raw_task_cancellation_during_finalizer_retains_unknown_lane(project, monkeypatch):
    async def scenario():
        c = coordinator()
        entered, resume, settled = Event(), Event(), Event()
        real = durable.settle_unstarted
        def paused(eid):
            entered.set()
            try:
                assert resume.wait(10)
                return real(eid)
            finally:
                settled.set()
        monkeypatch.setattr(durable,"settle_unstarted",paused)
        app,ids = make_app(project,c,lambda eid: pytest.fail("worker"),register=False)
        task = asyncio.create_task(post(app))
        try:
            assert await asyncio.to_thread(entered.wait,5)
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await asyncio.wait_for(task,5)
            assert c.status()["phase"] == "blocked"
            assert c.try_acquire(Operation.DATA).code == "ownership_unknown"
        finally:
            resume.set()
        assert await asyncio.to_thread(settled.wait,5)
        assert durable.terminal(ids[0])
        assert c.status()["phase"] == "blocked"
    asyncio.run(scenario())


def test_invalid_server_scope_owner_fails_closed():
    from backend.resource_training import optional_training_owner
    assert optional_training_owner({}) is None
    with pytest.raises(RuntimeError):
        optional_training_owner({"pilotodin.training_ownership": None})
