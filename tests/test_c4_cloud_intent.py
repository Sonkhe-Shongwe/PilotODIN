"""C4-B1 common request intent; all provider and local model seams inert."""
import asyncio
import json

import pytest
from backend import ai_provider as ai, main
from tests.fixture_http import fixture_client
from tests.test_c1_product_integration import product_composition


@pytest.fixture
def dispatch(monkeypatch):
    cfg={**ai.DEFAULTS, "cloud_enabled":True,"share_aggregates":True}
    calls=[]
    monkeypatch.setattr(ai,"_read_config",lambda:dict(cfg))
    monkeypatch.setattr(ai,"_get_key",lambda provider:"inert-fixture-key")
    monkeypatch.setattr(ai,"_health",{})
    monkeypatch.setattr(ai.resource_policy,"admit_new_work",lambda *_:{"decision":"allow"})
    monkeypatch.setattr(ai,"_call_ollama",lambda *a: (_ for _ in ()).throw(TimeoutError("inert")))
    monkeypatch.setattr(ai.bundled_inference,"generate",lambda *a: (_ for _ in ()).throw(TimeoutError("inert")))
    def provider(p,m,system,user,key,timeout,*,strict=False,still_authorized=None):
        assert strict is True and still_authorized()
        calls.append((p,m,user))
        return ai.ProviderText("Fixture answer","stop",False)
    monkeypatch.setattr(ai,"_call_provider",provider)
    return cfg,calls


@pytest.mark.parametrize("selected,intent",[(None,False),(None,True),("auto",True),
    ("local",True),("ollama",True),("gemini",False),("gemini","true"),("invalid",True)])
def test_no_implicit_cloud(dispatch,selected,intent):
    cfg,calls=dispatch
    cfg.update(preferred_provider="gemini",workspace_preferences={"assistant":"groq"})
    r=ai.respond({"row_count":30},"assistant","Question","Rules",
                 selected_provider=selected,cloud_intent=intent)
    assert r["fallback"] and calls==[]


@pytest.mark.parametrize("selected",["gemini","groq"])
def test_shared_explicit_cloud(dispatch,selected):
    cfg,calls=dispatch
    r=ai.respond({"row_count":30},"assistant","Question","Rules",
                 selected_provider=selected,cloud_intent=True)
    assert r["provider"]==selected and len(calls)==1
    assert calls[0][0]==selected and json.loads(calls[0][2])["verified_context"]=={"row_count":30}


@pytest.mark.parametrize("change",[{"cloud_enabled":False},{"share_aggregates":False},
    {"intelligence_mode":"local"},{"share_aggregates":"true"}])
def test_explicit_cloud_still_needs_saved_consent(dispatch,change):
    cfg,calls=dispatch
    cfg.update(change)
    assert ai.respond({},"assistant","Question","Rules",selected_provider="gemini",
                      cloud_intent=True)["fallback"]
    assert calls==[]


def test_no_alternate_provider_or_model_on_failure(dispatch,monkeypatch):
    cfg,calls=dispatch
    def fail(p,m,*args,**kwargs):
        calls.append((p,m))
        raise TimeoutError("private-marker")
    monkeypatch.setattr(ai,"_call_provider",fail)
    def no_local(*a,**kw):
        pytest.fail("Explicit cloud failure woke a local worker")
    monkeypatch.setattr(ai,"_call_ollama",no_local)
    monkeypatch.setattr(ai.bundled_inference,"generate",no_local)
    r=ai.respond({},"assistant","Question","Rules",selected_provider="gemini",cloud_intent=True)
    assert r["fallback"] and calls==[("gemini",ai.MODELS["gemini"]["routine"])]
    assert "private-marker" not in str(r)


def test_no_openrouter_project_dispatch_until_disclosure(dispatch):
    cfg,calls=dispatch
    r=ai.respond({},"assistant","Question","Rules",selected_provider="openrouter",cloud_intent=True)
    assert r["fallback"] and "disclosure" in r["reason"] and calls==[]


@pytest.mark.parametrize("composition",["legacy","owned"])
def test_provider_status_and_connection_intent(product_composition,dispatch,composition):
    cfg,calls=dispatch
    app=main.app if composition=="legacy" else product_composition[0]
    with fixture_client(app) as client:
        assert client.post("/api/ai/verify-connected").json()["status"]=="cached"
        assert client.post("/api/ai/test/gemini",json={}).json()["status"]=="explicit_intent_required"
        assert client.post("/api/ai/test/gemini",json={"cloud_intent":"true"}).status_code==422
        assert not calls
        assert client.post("/api/ai/test/gemini",json={"cloud_intent":True}).json()["status"]=="connected"
        assert len(calls)==1 and calls[0][2]=="Say READY"
        cfg["share_aggregates"]=False
        assert client.post("/api/ai/test/gemini",json={"cloud_intent":True}).json()["status"]=="not_configured"
        assert len(calls)==1


def test_startup_no_probe_even_with_saved_cloud(dispatch,monkeypatch):
    cfg,calls=dispatch
    for module,name in [(main.dataset_publication,"recover_pending"),
                        (main.storage,"recover_model_publications"),
                        (main.storage,"recover_export_publications"),
                        (main.storage,"recover_interrupted_experiments")]:
        monkeypatch.setattr(module,name,lambda:0)
    def no_status():
        pytest.fail("Startup attempted provider configuration/probe")
    monkeypatch.setattr(ai,"config_status",no_status)
    async def run():
        async with main._lifespan(main.app):
            pass
    asyncio.run(run())
    assert calls==[]


def test_legacy_http_named_request_requires_intent(product_composition,dispatch):
    cfg,calls=dispatch
    client=fixture_client(main.app)
    try:
        seed=client.post("/api/projects",files={"file":("fixture.csv",b"amount,group\n1,A\n2,B\n3,A\n","text/csv")})
        assert seed.status_code==201,seed.text
        path="/api/projects/"+seed.json()["id"]+"/ai/insight"
        base={"context":"overview","selected_provider":"gemini"}
        assert client.post(path,json=base).json()["fallback"]
        assert client.post(path,json={**base,"cloud_intent":"true"}).status_code==422
        assert calls==[]
        response=client.post(path,json={**base,"cloud_intent":True})
        assert response.status_code==200,response.text
        assert response.json()["provider"]=="gemini" and len(calls)==1
    finally:
        client.close()
