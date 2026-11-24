"""Actual FastAPI routes in separate owned composition; no real model/provider."""
import json
import pytest
from fastapi.testclient import TestClient
from backend import main, storage, quality, investigations, autonomy
from backend.resource_admission import Coordinator, GIB, Operation
from backend.resource_autonomy import AutonomyStages
from backend.resource_routes import ROUTES

@pytest.fixture
def product(monkeypatch,tmp_path):
    home=tmp_path/"product"
    (home/"datasets").mkdir(parents=True)
    (home/"models").mkdir()
    monkeypatch.setattr(storage,"HOME",home)
    monkeypatch.setattr(storage,"DB_PATH",home/"pilotodin.sqlite3")
    monkeypatch.delenv("PILOTODIN_DESKTOP_SESSION",raising=False)
    storage.init()
    quality._init_tables()
    investigations.init()
    autonomy.init()
    c=Coordinator(lambda:"adaptive",lambda:3*GIB)
    a=autonomy.OwnedAutonomy(AutonomyStages(c,lambda _:pytest.fail("Unexpected planner")))
    calls=[]
    def insight(payload):
        assert not c.status()["active"]
        calls.append(json.loads(payload))
        lease=c.try_acquire(Operation.LOCAL_INFERENCE).lease
        assert c.start(lease)
        assert c.try_acquire(Operation.DATA).code=="resource_busy"
        assert c.release(lease)
        return {"answer":"Inert fixture answer","fallback":False}
    app=main.build_owned_app(c,a,insight)
    with TestClient(app) as client:
        yield client,c,a,calls
    a.drain(2)

def upload(client):
    return client.post("/api/projects",files={"file":("test.csv",b"Region,Revenue\nNorth,100\nSouth,200\nNorth,300\n","text/csv")})

def test_actual_inventory_is_bound_without_mutating_legacy(product):
    client,c,_,_=product
    from fastapi.routing import APIRoute
    assert {(method,r.path) for r in client.app.routes if isinstance(r,APIRoute) for method in r.methods}==set(ROUTES)
    legacy={r.path:r for r in main.app.routes if isinstance(r,APIRoute)}
    assert all(r is not legacy[r.path] for r in client.app.routes if isinstance(r,APIRoute))
    assert client.get("/api/health").status_code==200

def test_actual_upload_and_data_routes_are_denied_while_training_owns_lane(product,monkeypatch):
    client,c,_,_=product
    response=upload(client)
    assert response.status_code==201,response.text
    pid=response.json()["id"]
    lease=c.try_acquire(Operation.TRAINING).lease
    assert c.start(lease)
    monkeypatch.setattr(quality,"current_data",lambda *a:pytest.fail("Materialized while denied"))
    assert upload(client).status_code==503
    assert client.get(f"/api/projects/{pid}/preparation").status_code==503
    assert client.get("/api/projects").status_code==200
    assert client.get("/api/resource/status").json()["workload"]["operation"]=="training"
    assert c.release(lease)

def test_actual_validation_refusal_does_not_poison_lane(product):
    client,c,_,_=product
    assert client.post("/api/projects",files={"file":("bad.txt",b"bad")}).status_code==400
    assert not c.status()["active"]
    r=upload(client)
    assert r.status_code==201,r.text
    assert not c.status()["active"]

def test_actual_upload_uncertainty_retains_lane(product,monkeypatch):
    client,c,_,_=product
    def fail(*a,**k):
        raise main.dataset_publication.UnconfirmedPublication("fixture")
    monkeypatch.setattr(main.dataset_publication,"publish",fail)
    r=upload(client)
    assert r.status_code==500,r.text
    assert c.status()["phase"]=="blocked"

def test_actual_insight_releases_data_before_host_callback(product,monkeypatch):
    client,c,_,calls=product
    r=upload(client)
    assert r.status_code==201,r.text
    pid=r.json()["id"]
    def context(*a,**k):
        assert c.status()["operation"]=="data"
        return {"summary":"Synthetic facts"}
    monkeypatch.setattr(main.ai_context,"build",context)
    monkeypatch.setattr(main.analytics,"plan_investigation",lambda *a:None)
    monkeypatch.setattr(main.analytics,"answer",lambda *a:{"answer":"Local answer"})
    monkeypatch.setattr(main.verified_answers,"answer",lambda *a:{"analysis":None})
    monkeypatch.setattr(main.ai_provider,"respond",lambda *a:pytest.fail("Legacy inference"))
    r=client.post(f"/api/projects/{pid}/ai/insight",json={"context":"assistant","question":"Describe revenue","selected_provider":"ollama"})
    assert r.status_code==200,r.text
    assert r.json()["answer"]=="Inert fixture answer"
    assert len(calls)==1 and calls[0]["dataset_version"]==0
    assert not c.status()["active"]

def test_actual_auth_precedes_owned_upload(product,monkeypatch):
    client,c,_,_=product
    monkeypatch.setenv("PILOTODIN_DESKTOP_SESSION","private-fixture-token")
    lease=c.try_acquire(Operation.TRAINING).lease
    assert c.start(lease)
    assert upload(client).status_code==401
    assert c.release(lease)

def test_export_settlement_rejects_uncertain_receipt_or_open_handle():
    from backend.export_transfer import Transfer
    from types import SimpleNamespace
    tr=Transfer()
    tr.finished=True
    assert tr.ownership_settled()
    tr.publication_attempted=True
    assert not tr.ownership_settled()
    tr.receipt=SimpleNamespace(state="blocked")
    assert not tr.ownership_settled()
    tr.receipt=SimpleNamespace(state="released")
    tr.stream=SimpleNamespace(closed=False)
    assert not tr.ownership_settled()
    tr.stream.closed=True
    assert tr.ownership_settled()
    tr.uncertain=True
    assert not tr.ownership_settled()
