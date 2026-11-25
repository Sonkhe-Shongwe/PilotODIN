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


@pytest.mark.parametrize("value",["é", "漢", "😀", '"\\\n\u0001'])
def test_cloud_serialized_byte_boundary(value):
    # Isolated serializer stress: arbitrary required keys must never be sent
    # through the actual dispatch path (covered by the projection tests).
    empty=ai._encode_insight_prompt({"required":""},"assistant","Question",None,
                                    limit=ai.CLOUD_PROMPT_LIMIT,cloud=True)
    overhead=len(empty.encode("utf-8"))
    encoded_unit=len(json.dumps(value,ensure_ascii=False).encode("utf-8"))-2
    budget=ai.CLOUD_PROMPT_LIMIT-overhead
    required=value*(budget//encoded_unit)+"a"*(budget%encoded_unit)
    context={"required":required}
    wire=ai._encode_insight_prompt(context,"assistant","Question",None,
                                   limit=ai.CLOUD_PROMPT_LIMIT,cloud=True)
    assert len(wire.encode("utf-8"))==ai.CLOUD_PROMPT_LIMIT
    assert json.loads(wire)=={"task":"assistant","question":"Question",
                              "verified_context":context}
    assert ai._encode_insight_prompt({"required":required+"a"},"assistant","Question",None,
                                    limit=ai.CLOUD_PROMPT_LIMIT,cloud=True) is None


def test_cloud_wide_unicode_retains_required_metrics_and_whole_prefix(dispatch):
    cfg,calls=dispatch
    columns=[{"name":f"{i:02d} "+'漢😀é"'*24,"kind":"numeric",
              "missing_count":0,"unique_count":50,"mean":i} for i in range(50)]
    context={"dataset_version":3,"row_count":50,"columns":columns,
             "experiment":{"metrics":{"accuracy":0.8,"sample_count":50},
                           "comparison":[{"key":"logistic_regression","status":"ready","cv_metric":0.81}]},
             "prediction":{"outcome":"PRIVATE_PREDICTION"}}
    original=json.dumps(context,ensure_ascii=False)
    question="Explain the \"score\" — 統計"
    result=ai.respond(context,"evaluate",question,"Rules",
                      selected_provider="gemini",cloud_intent=True)
    assert result["provider"]=="gemini" and len(calls)==1
    wire=calls[0][2]
    assert len(wire.encode("utf-8"))<=ai.CLOUD_PROMPT_LIMIT
    payload=json.loads(wire)
    assert payload["question"]==question and "continuation" not in payload
    evidence=payload["verified_context"]
    assert evidence["experiment"]==context["experiment"]
    assert evidence["dataset_version"]==3 and evidence["row_count"]==50
    kept=evidence["columns"]
    assert 0<len(kept)<len(columns) and kept==columns[:len(kept)]
    assert payload["omitted_context_items"]=={"columns":len(columns)-len(kept)}
    assert "PRIVATE_PREDICTION" not in wire
    assert json.dumps(context,ensure_ascii=False)==original


def test_cloud_invalid_unicode_refused_before_credential_read(dispatch,monkeypatch):
    cfg,calls=dispatch
    def unexpected(*args):
        pytest.fail("Invalid prompt reached credential read")
    monkeypatch.setattr(ai,"_get_key",unexpected)
    result=ai.respond({"columns":[{"name":"\ud800","kind":"numeric"}]},"assistant","Question","Rules",
                      selected_provider="gemini",cloud_intent=True)
    assert result["fallback"] and calls==[]


def test_cloud_encoder_refuses_history_and_keeps_local_format():
    context={"row_count":30,"prediction":{"outcome":"local"}}
    assert ai._encode_insight_prompt(context,"predict","Question","Prior answer",
                                     limit=11000,cloud=True) is None
    fresh=json.loads(ai._encode_insight_prompt(context,"predict","Question",None,limit=9000))
    assert fresh["continuation"] is None and fresh["verified_context"]==context
    local=json.loads(ai._encode_insight_prompt(context,"predict","Question","Prior answer",
                                               limit=9000))
    assert local["continuation"]["previous_answer_tail"]=="Prior answer"
    assert local["verified_context"]==context


@pytest.mark.parametrize("entry",["legacy","owned"])
def test_positive_projection_omits_nested_private_data(dispatch,entry):
    cfg,calls=dispatch
    class NoString:
        def __str__(self):
            pytest.fail("Unknown object was stringified")
    context={"dataset_version":2,"row_count":30,"column_count":4,"missing_cells":3,
             "project_id":"PRIVATE_PROJECT","dataset_path":"PRIVATE_PATH",
             "required":NoString(),"rows":[{"amount":"PRIVATE_ROW"}],
             "prediction":{"outcome":"PRIVATE_PREDICTION"},
             "columns":[
                 {"name":"amount","kind":"numeric","missing_count":0,"unique_count":20,
                  "mean":12.0,"median":11.0,"std":3.0,"min":-123456,"max":987654,
                  "sample_values":["PRIVATE_VALUE"],"future":{"secret":"PRIVATE_NESTED"}},
                 {"name":"email","kind":"categorical","unique_count":30},
                 {"name":"C:/PRIVATE_PATH","kind":"numeric","mean":123},
                 {"name":"small","kind":"numeric","missing_count":27,"unique_count":3,"mean":321.0},
                 {"name":"code","kind":"numeric","missing_count":0,"unique_count":30,"mean":999.0}],
             "quality_findings":[{"kind":"missing","column":"amount","affected_rows":3,
                                  "decision":"pending","severity":"review","details":"PRIVATE_DETAILS"}],
             "computed_patterns":[{"column":"amount","mean":12.0,"median":11.0,"observation":"PRIVATE_PROSE"},
                                  {"column":"small","mean":321.0,"median":321.0}],
             "feature_screening":[{"column":"amount","risk":"review","recommendation":"investigate",
                                    "missing_pct":0,"reasons":["PRIVATE_REASON"]}],
             "experiment":{"target":"amount","task":"regression","selected_model":"ridge",
                           "metrics":{"sample_count":20,"rmse":3.5,"accuracy":True,
                                      "evaluation_rows":["PRIVATE_HELDOUT"],"reliability":{"level":"review","issues":["PRIVATE_NOTE"]}},
                           "comparison":[{"key":"ridge","status":"ready","cv_metric":3.1,"error":"PRIVATE_ERROR"},
                                         {"key":"PRIVATE_MODEL","status":"ready","cv_metric":7}]},
             "verified_investigation":{"operation":"missingness","column":"amount","total_rows":30,"missing_rows":6,
                "missing_pct":20,"row_numbers":[1,2,3],"caution":"PRIVATE_CAUTION",
                "categorical_group_counts":[{"column":"group","groups":[{"label":"PRIVATE_CATEGORY","total_count":10}]}],
                "numeric_comparisons":[{"column":"premium","missing_group_count":6,"other_group_count":24,
                                         "missing_group_mean":1.5,"other_group_mean":2.5,"detail":"PRIVATE_COMPARISON"},
                                        {"column":"small","missing_group_count":1,"other_group_count":20,
                                         "missing_group_mean":321.0,"other_group_mean":2.5}]}}
    if entry=="legacy":
        r=ai.respond(context,"assistant","Typed question","Rules",selected_provider="gemini",cloud_intent=True)
    else:
        r=ai.owned_cloud_insight(context,"assistant","Typed question","Rules",False,"gemini")
    assert r["provider"]=="gemini" and len(calls)==1
    wire=calls[0][2]
    assert "PRIVATE_" not in wire and "321.0" not in wire and "-123456" not in wire and "987654" not in wire
    payload=json.loads(wire)
    assert payload["question"]=="Typed question" and "continuation" not in payload
    actual=payload["verified_context"]
    assert actual["columns"]==[
        {"name":"amount","kind":"numeric","missing_count":0,"unique_count":20,"mean":12.0,"median":11.0,"std":3.0},
        {"name":"small","kind":"numeric","missing_count":27,"unique_count":3}]
    assert actual["quality_findings"]==[{"kind":"missing","column":"amount","affected_rows":3,"decision":"pending","severity":"review"}]
    assert actual["computed_patterns"]==[{"column":"amount","mean":12.0,"median":11.0}]
    assert actual["feature_screening"]==[{"column":"amount","risk":"review","recommendation":"investigate","missing_pct":0}]
    assert actual["experiment"]["metrics"]=={"sample_count":20,"rmse":3.5,"reliability":{"level":"review"}}
    assert actual["experiment"]["comparison"]==[{"key":"ridge","status":"ready","cv_metric":3.1}]
    assert actual["verified_investigation"]["numeric_comparisons"]==[
        {"column":"premium","missing_group_count":6,"other_group_count":24,"missing_group_mean":1.5,"other_group_mean":2.5}]
    assert "categorical_group_counts" not in actual["verified_investigation"]
    assert context["columns"][0]["min"]==-123456 and context["prediction"]["outcome"]=="PRIVATE_PREDICTION"


@pytest.mark.parametrize("support",[None,0,4,True,"50"])
def test_unknown_or_small_support_excludes_metrics(support):
    actual=ai._cloud_project({"row_count":4,"columns":[{"name":"amount","kind":"numeric",
                     "missing_count":0,"unique_count":4,"mean":999}],
                     "experiment":{"metrics":{"sample_count":support,"accuracy":0.9},
                     "comparison":[{"key":"ridge","status":"ready","cv_metric":0.9}]}})
    assert "mean" not in actual["columns"][0]
    assert "accuracy" not in actual["experiment"]["metrics"]
    assert actual["experiment"]["comparison"]==[{"key":"ridge","status":"ready"}]


def test_invalid_required_name_does_not_dispatch(dispatch,monkeypatch):
    cfg,calls=dispatch
    monkeypatch.setattr(ai,"_get_key",lambda *_:pytest.fail("Invalid context reached credentials"))
    result=ai.respond({"target":"x"*101},"assistant","Question","Rules",
                      selected_provider="gemini",cloud_intent=True)
    assert result["fallback"] and not calls

