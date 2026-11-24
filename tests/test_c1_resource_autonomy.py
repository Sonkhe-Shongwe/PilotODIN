"""Staged actual autonomy worker: disposable data, inert owned planner only."""
import json
import threading
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend import autonomy, investigations, quality, storage
from backend.main import app
from backend.resource_admission import Coordinator, GIB, Operation
from backend.resource_autonomy import AutonomyStages, ResourceDeferred, MAX_CONTEXT_BYTES


def coordinator():
    return Coordinator(lambda: "adaptive", lambda: 3 * GIB)


@pytest.fixture
def fixture(monkeypatch,tmp_path):
    home=tmp_path/"autonomy"
    (home/"datasets").mkdir(parents=True)
    (home/"models").mkdir()
    monkeypatch.setattr(storage,"HOME",home)
    monkeypatch.setattr(storage,"DB_PATH",home/"pilotodin.sqlite3")
    storage.init()
    quality._init_tables()
    investigations.init()
    autonomy.init()
    with TestClient(app) as client:
        response=client.post("/api/projects",files={"file":("test.csv",b"Region,Revenue\nNorth,100\nSouth,200\nNorth,300\n","text/csv")})
        assert response.status_code==201,response.text
        pid=response.json()["id"]
        response=client.post(f"/api/projects/{pid}/investigations",json={"objective":"Inspect overview"})
        assert response.status_code==201,response.text
        inv=response.json()["id"]
    with monkeypatch.context() as m:
        m.setattr(autonomy,"_launch",lambda *_:None)
        run=autonomy.start(inv,planner=lambda _:pytest.fail("Legacy planner"))
    return pid,inv,run["id"]


def proposal(intent="run_tool"):
    return {"intent":intent,"tool":"overview" if intent=="run_tool" else "none",
            "columns":[],"reason":"Synthetic verified inspection"}


def run_worker(run_id,stages):
    # Use actual thread ownership, but join it explicitly in this fixture.
    with autonomy._LOCK:
        t=threading.Thread(target=autonomy._worker,
                           args=(run_id,lambda _:pytest.fail("Legacy planner"),stages))
        autonomy._ACTIVE[run_id]=t
        t.start()
    t.join(10)
    assert not t.is_alive()


def test_actual_worker_separates_data_and_owned_inference(fixture,monkeypatch):
    pid,inv,eid=fixture
    c=coordinator()
    original=quality.current_data
    calls=[]
    def checked(*args,**kwargs):
        assert c.status()["operation"]=="data"
        calls.append("data")
        return original(*args,**kwargs)
    monkeypatch.setattr(quality,"current_data",checked)
    def owned(payload):
        assert not c.status()["active"]
        ctx=json.loads(payload)
        lease=c.try_acquire(Operation.LOCAL_INFERENCE).lease
        assert c.start(lease)
        assert c.try_acquire(Operation.DATA).code=="resource_busy"
        calls.append("inference")
        result=proposal("suggest_finish" if ctx["verified_evidence"] else "run_tool")
        assert c.release(lease)  # inert fixture, NOT native exit evidence
        return result
    original_path=Path(storage.get_project(pid)["dataset_path"])
    before=original_path.read_bytes()
    run_worker(eid,AutonomyStages(c,owned))
    state=autonomy.for_investigation(inv)
    assert state["status"]=="ready_for_review",state
    assert len(investigations.load(inv)["artifacts"])==1
    assert state["steps"][0]["evidence_id"]
    assert calls.count("inference")==2 and calls.count("data")>=3
    assert not c.status()["active"] and original_path.read_bytes()==before


def test_busy_data_stage_preserves_resumable_checkpoint(fixture):
    _,inv,eid=fixture
    c=coordinator()
    lease=c.try_acquire(Operation.TRAINING).lease
    assert c.start(lease)
    run_worker(eid,AutonomyStages(c,lambda _:pytest.fail("Denied planner")))
    state=autonomy.for_investigation(inv)
    assert state["status"]=="interrupted" and state["steps"]==[]
    assert c.status()["operation"]=="training"
    assert c.release(lease)


def test_cancelled_plan_is_discarded(fixture):
    _,inv,eid=fixture
    c=coordinator()
    def owned(payload):
        assert autonomy.cancel(inv)["status"]=="cancelled"
        return proposal()
    run_worker(eid,AutonomyStages(c,owned))
    state=autonomy.for_investigation(inv)
    assert state["status"]=="cancelled" and state["steps"]==[]
    assert not investigations.load(inv)["artifacts"]


def test_stale_plan_is_discarded(fixture):
    pid,inv,eid=fixture
    c=coordinator()
    def owned(payload):
        assert quality.restore(pid,0,0)["version"]==1
        return proposal()
    run_worker(eid,AutonomyStages(c,owned))
    state=autonomy.for_investigation(inv)
    assert state["status"]=="stale" and state["steps"]==[]
    assert not investigations.load(inv)["artifacts"]


def test_pending_step_deferral_does_not_duplicate(fixture):
    _,inv,eid=fixture
    c=coordinator()
    sid=autonomy._claim_step(eid,0,proposal())
    def fail_plan(payload):
        raise ResourceDeferred("host_busy")
    run_worker(eid,AutonomyStages(c,fail_plan))
    state=autonomy.for_investigation(inv)
    assert state["status"]=="interrupted"
    assert state["steps"][0]["id"]==sid and state["steps"][0]["status"]=="completed"
    assert len(investigations.load(inv)["artifacts"])==1


def test_context_ceiling_releases_known_refusal():
    c=coordinator()
    stages=AutonomyStages(c,lambda _:pytest.fail("Oversized planner"))
    with pytest.raises(ResourceDeferred,match="context_limit"):
        stages.context(lambda: {"value":"x"*MAX_CONTEXT_BYTES})
    assert not c.status()["active"]


def test_unknown_data_unwind_retains_lane():
    c=coordinator()
    stages=AutonomyStages(c,lambda _:pytest.fail("Planner"))
    def fail():
        raise OSError("Synthetic unknown cleanup")
    with pytest.raises(OSError):
        stages.data(fail)
    assert c.status()["phase"]=="blocked"
    assert c.try_acquire(Operation.TRAINING).code=="ownership_unknown"


@pytest.mark.parametrize("value", [
    {"x": "a" * (MAX_CONTEXT_BYTES + 1)},
    {"x": "😀" * (MAX_CONTEXT_BYTES // 4)},
    {"x": [""] * 8193},
    {"x": 1 << 257},
])
def test_context_preflight_and_encoded_limits(value):
    c=coordinator()
    stages=AutonomyStages(c,lambda _:pytest.fail("Oversized planner"))
    with pytest.raises(ResourceDeferred,match="context_limit"):
        stages.context(lambda: value)
    assert not c.status()["active"]


def test_context_depth_and_utf8_exact_boundary():
    from backend.resource_autonomy import bounded_context_bytes, ContextLimit
    value="leaf"
    for _ in range(18):
        value=[value]
    with pytest.raises(ContextLimit):
        bounded_context_bytes(value)
    value="a"*(MAX_CONTEXT_BYTES-2)
    assert len(bounded_context_bytes(value))==MAX_CONTEXT_BYTES
    with pytest.raises(ContextLimit):
        bounded_context_bytes(value+"a")
    assert json.loads(bounded_context_bytes({"name":"Café 東京","n":1}))=={"name":"Café 東京","n":1}


def test_stored_context_size_refuses_before_decoding(fixture,monkeypatch):
    _,inv,eid=fixture
    c=coordinator()
    with storage.connect() as con:
        con.execute("INSERT INTO evidence_v1 "
                    "(id,investigation_id,operation,params,result,dataset_version,tool_version,status,created_at) "
                    "VALUES (?,?,?,?,?,?,?,?,?)",
                    (storage.uid(),inv,"overview","{}","x"* (256*1024+1),0,
                     "fixture","completed",storage.now()))
    monkeypatch.setattr(quality,"current_data",lambda *_:pytest.fail("Oversized history reached materialization"))
    run_worker(eid,AutonomyStages(c,lambda _:pytest.fail("Oversized history reached planner")))
    state=autonomy.for_investigation(inv)
    assert state["status"]=="interrupted"
    assert "context_limit" in state["stop_reason"]
    assert not c.status()["active"]


def test_non_tool_cancel_after_claim_cannot_be_overwritten(fixture,monkeypatch):
    _,inv,eid=fixture
    c=coordinator()
    real=autonomy._owned_claim_step
    def claim(*args):
        sid=real(*args)
        assert sid
        assert autonomy.cancel(inv)["status"]=="cancelled"
        return sid
    monkeypatch.setattr(autonomy,"_owned_claim_step",claim)
    run_worker(eid,AutonomyStages(c,lambda _:proposal("suggest_finish")))
    state=autonomy.for_investigation(inv)
    assert state["status"]=="cancelled"
    assert state["steps"][0]["status"]=="proposed"


def test_non_tool_version_change_after_claim_is_stale(fixture,monkeypatch):
    pid,inv,eid=fixture
    c=coordinator()
    real=autonomy._owned_claim_step
    def claim(*args):
        sid=real(*args)
        assert sid
        assert quality.restore(pid,0,0)["version"]==1
        return sid
    monkeypatch.setattr(autonomy,"_owned_claim_step",claim)
    run_worker(eid,AutonomyStages(c,lambda _:proposal("suggest_finish")))
    state=autonomy.for_investigation(inv)
    assert state["status"]=="stale"
    assert state["steps"][0]["status"]=="proposed"


def test_tool_cancel_at_data_stage_boundary(fixture,monkeypatch):
    _,inv,eid=fixture
    c=coordinator()
    real=autonomy._owned_tool_receipt
    def after_admission(*args):
        assert c.status()["operation"]=="data"
        assert autonomy.cancel(inv)["status"]=="cancelled"
        return real(*args)
    monkeypatch.setattr(autonomy,"_owned_tool_receipt",after_admission)
    monkeypatch.setattr(investigations,"run",lambda *a,**k:pytest.fail("Cancelled tool began"))
    run_worker(eid,AutonomyStages(c,lambda _:proposal()))
    state=autonomy.for_investigation(inv)
    assert state["status"]=="cancelled" and state["steps"][0]["status"]=="proposed"
    assert not c.status()["active"]


def test_committed_tool_receipt_survives_cooperative_cancel(fixture,monkeypatch):
    _,inv,eid=fixture
    c=coordinator()
    real=investigations.run
    def after_commit(*args,**kwargs):
        evidence=real(*args,**kwargs)
        assert autonomy.cancel(inv)["status"]=="cancelled"
        return evidence
    monkeypatch.setattr(investigations,"run",after_commit)
    run_worker(eid,AutonomyStages(c,lambda _:proposal()))
    state=autonomy.for_investigation(inv)
    assert state["status"]=="cancelled" and state["steps"][0]["status"]=="completed"
    assert state["steps"][0]["evidence_id"]==investigations.load(inv)["artifacts"][0]["id"]
    assert not c.status()["active"]


def test_terminal_step_rollback_is_atomic(fixture):
    _,inv,eid=fixture
    autonomy._set(eid,"running")
    # Avoid _row orphan recovery for this direct DB transaction fixture.
    with storage.connect() as con:
        con.execute("CREATE TRIGGER fixture_fail_terminal BEFORE UPDATE OF status ON odin_runs "
                    "WHEN NEW.status='needs_review' BEGIN SELECT RAISE(ABORT,'fixture rollback'); END")
    state={"dataset_version":0}
    sid=autonomy._owned_claim_step(eid,0,proposal("suggest_finish"),state)
    assert sid
    import sqlite3
    with pytest.raises(sqlite3.IntegrityError,match="fixture rollback"):
        autonomy._owned_finish_step(eid,sid,state,"needs_review","fixture")
    with storage.connect() as con:
        assert con.execute("SELECT status FROM odin_runs WHERE id=?",(eid,)).fetchone()[0]=="running"
        assert con.execute("SELECT status FROM odin_run_steps WHERE id=?",(sid,)).fetchone()[0]=="proposed"
