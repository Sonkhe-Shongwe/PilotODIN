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


@pytest.mark.parametrize("close_fault",["raises","returns_without_close","closes_then_raises"])
def test_actual_export_close_fault_settles_receipt_but_retains_lane(product,monkeypatch,close_fault):
    from backend.export_transfer import Transfer
    from backend import export_publication as ledger
    client,c,_,_=product
    response=upload(client)
    assert response.status_code==201,response.text
    pid=response.json()["id"]
    original_prepare=Transfer.prepare
    observed=[]
    class FaultyClose:
        def __init__(self,stream):
            self.stream=stream
        def __getattr__(self,name):
            return getattr(self.stream,name)
        def close(self):
            if close_fault=="returns_without_close":
                return
            if close_fault=="closes_then_raises":
                self.stream.close()
            raise OSError("Fixture close acknowledgement unavailable")
    def prepare(self,*args):
        original_prepare(self,*args)
        observed.append((self,self.stream))
        self.stream=FaultyClose(self.stream)
    monkeypatch.setattr(Transfer,"prepare",prepare)
    try:
        response=client.post(f"/api/projects/{pid}/quality/export",json={"version":0,"format":"csv"})
        assert response.status_code==200,response.text
        transfer,stream=observed[0]
        with storage.connect() as con:
            receipt=ledger.read(con,transfer.receipt.operation_id)
        assert receipt.state=="blocked" and receipt.reason_code=="storage_unavailable"
        assert transfer.path.exists()
        assert transfer.close_unconfirmed and not transfer.uncertain
        assert not transfer.ownership_settled()
        assert c.status()["phase"]=="blocked"
        assert client.get(f"/api/projects/{pid}/preparation").status_code==503
        assert client.get("/api/projects").status_code==200
    finally:
        for _,stream in observed:
            stream.close()


def test_actual_successful_export_releases_receipt_and_lane(product):
    from backend.export_transfer import Transfer
    client,c,_,_=product
    r=upload(client)
    assert r.status_code==201,r.text
    pid=r.json()["id"]
    r=client.post(f"/api/projects/{pid}/quality/export",json={"version":0,"format":"csv"})
    assert r.status_code==200,r.text
    assert not c.status()["active"]
    assert list((storage.HOME/"export_tmp").iterdir())==[]
    assert client.get("/api/resource/status").json()["workload"]["active"] is False


def test_resource_status_legacy_shape_and_owned_auth(product,monkeypatch):
    client,c,_,_=product
    with TestClient(main.app) as legacy:
        assert "workload" not in legacy.get("/api/resource/status").json()
    assert client.get("/api/resource/status").json()["workload"]==c.status()
    monkeypatch.setenv("PILOTODIN_DESKTOP_SESSION","fixture-secret")
    assert client.get("/api/resource/status").status_code==401
    assert client.get("/api/resource/status",headers={"X-PilotODIN-Session":"fixture-secret"}).json()["workload"]==c.status()


@pytest.fixture
def owned_cloud(monkeypatch):
    from backend import ai_provider as ai
    cfg={**ai.DEFAULTS,"cloud_enabled":True,"share_aggregates":True}
    calls=[]
    monkeypatch.setattr(ai,"_read_config",lambda:dict(cfg))
    monkeypatch.setattr(ai,"_get_key",lambda provider:"fixture-secret-key")
    def call(provider,model,system,user,key,timeout,*,strict=False,still_authorized=None):
        assert strict is True and still_authorized()
        calls.append((provider,json.loads(user)))
        return ai.ProviderText("Inert provider result","stop",False)
    monkeypatch.setattr(ai,"_call_provider",call)
    return ai,cfg,calls

@pytest.mark.parametrize("selected",[None,"auto","ollama","local"])
def test_owned_cloud_no_implicit_provider(owned_cloud,selected):
    ai,cfg,calls=owned_cloud
    result=ai.owned_cloud_insight({"row_count":3},"assistant","Question","Rules",False,selected)
    assert result["fallback"] and calls==[]

@pytest.mark.parametrize("field,value",[("cloud_enabled",False),("share_aggregates",False),
                                        ("share_aggregates","true"),("intelligence_mode","local")])
def test_owned_cloud_requires_exact_consent(owned_cloud,field,value):
    ai,cfg,calls=owned_cloud
    cfg[field]=value
    assert ai.owned_cloud_insight({},"assistant","Question","Rules",False,"gemini")["fallback"]
    assert calls==[]

@pytest.mark.parametrize("selected",["gemini","groq","openrouter"])
def test_owned_cloud_selected_destination_only_and_prediction_omitted(owned_cloud,selected):
    ai,cfg,calls=owned_cloud
    result=ai.owned_cloud_insight({"row_count":3,"prediction":{"outcome":"private"}},
                                  "predict","Question","Rules",False,selected)
    assert result["provider"]==selected and not result["fallback"]
    assert len(calls)==1 and calls[0][0]==selected
    assert calls[0][1]["verified_context"]=={"row_count":3}

def test_owned_cloud_provider_failure_never_fans_out(owned_cloud,monkeypatch):
    ai,cfg,calls=owned_cloud
    def fail(provider,*args,**kwargs):
        calls.append(provider)
        raise RuntimeError("fixture failure")
    monkeypatch.setattr(ai,"_call_provider",fail)
    result=ai.owned_cloud_insight({},"assistant","Question","Rules",False,"gemini")
    assert result["fallback"] and calls==["gemini"]

def test_owned_cloud_revocation_discards_returned_response(owned_cloud,monkeypatch):
    ai,cfg,calls=owned_cloud
    def revoke(provider,*args,**kwargs):
        calls.append(provider)
        cfg["share_aggregates"]=False
        return "Stale response"
    monkeypatch.setattr(ai,"_call_provider",revoke)
    result=ai.owned_cloud_insight({},"assistant","Question","Rules",False,"gemini")
    assert result["fallback"] and result["answer"]=="Rules" and calls==["gemini"]

def test_owned_cloud_stale_context_and_continuation_do_not_send(owned_cloud):
    ai,cfg,calls=owned_cloud
    for args,kwargs in [((None,),{"still_current":lambda:False}),(("Old private answer",),{})]:
        assert ai.owned_cloud_insight({},"assistant","Question","Rules",False,"gemini",*args,**kwargs)["fallback"]
    assert calls==[]

def test_owned_lifespan_and_verify_connected_do_not_probe(product,monkeypatch):
    from backend import ai_provider as ai
    client,*_=product
    monkeypatch.setattr(ai,"verify_connected",lambda:pytest.fail("Automatic external probe"))
    monkeypatch.setattr(ai,"test_connection",lambda *a:pytest.fail("Legacy probe"))
    assert client.post("/api/ai/verify-connected").json()["status"]=="cached"


def test_owned_transport_rechecks_at_actual_dispatch(monkeypatch):
    from backend import ai_provider as ai
    class NeverOpen:
        def open(self,*args,**kwargs):
            pytest.fail("Revoked request reached transport")
    monkeypatch.setattr(ai.urllib.request,"build_opener",lambda *a:NeverOpen())
    with pytest.raises(RuntimeError,match="no longer authorized"):
        ai._call_provider("gemini",ai.MODELS["gemini"]["routine"],"System","Question",
                          "fixture-secret-key",10,strict=True,still_authorized=lambda:False)
