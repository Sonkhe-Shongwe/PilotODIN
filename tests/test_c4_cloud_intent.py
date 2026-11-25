"""C4-B1 common request intent; all provider and local model seams inert."""
import asyncio
import json
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from types import SimpleNamespace
from email.message import Message
import io

import pytest
import pandas as pd
from backend import ai_context, ai_provider as ai, main
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
              "missing_count":0,"unique_count":50,"mean":i,
              "_finite_count":50,"_finite_unique_count":50} for i in range(50)]
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
    assert evidence["experiment"]=={"metrics":{"accuracy":0.8,"sample_count":50},
                                    "comparison":[{"key":"logistic_regression","status":"ready"}]}
    assert evidence["dataset_version"]==3 and evidence["row_count"]==50
    kept=evidence["columns"]
    projected=[{k:v for k,v in col.items() if not k.startswith("_")} for col in columns]
    assert 0<len(kept)<len(columns) and kept==projected[:len(kept)]
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
                  "_finite_count":30,"_finite_unique_count":20,"mean":12.0,"median":11.0,"std":3.0,"min":-123456,"max":987654,
                  "sample_values":["PRIVATE_VALUE"],"future":{"secret":"PRIVATE_NESTED"}},
                 {"name":"email","kind":"categorical","unique_count":30},
                 {"name":"C:/PRIVATE_PATH","kind":"numeric","mean":123},
                 {"name":"small","kind":"numeric","missing_count":27,"unique_count":3,"mean":321.0},
                 {"name":"code","kind":"numeric","missing_count":0,"unique_count":30,"mean":999.0}],
             "quality_findings":[{"kind":"missing","column":"amount","affected_rows":3,
                                  "decision":"pending","severity":"review","details":"PRIVATE_DETAILS"}],
             "computed_patterns":[{"column":"amount","mean":12.0,"median":11.0,
                                  "_finite_count":30,"_finite_unique_count":20,"observation":"PRIVATE_PROSE"},
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
    assert actual["experiment"]["comparison"]==[{"key":"ridge","status":"ready"}]
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


def test_actual_finite_population_controls_cloud_statistics(dispatch):
    cfg,calls=dispatch
    df=pd.DataFrame({
        "mixed":[10,20,30,float("inf"),float("-inf"),None,None],
        "balanced":[1,2,3,4,5,float("inf"),None],
        # The conservative identifier suffix filter must remain independent of support.
        "valid":[1,2,3,4,5,float("inf"),None],
        "repeated":[1,1,1,2,3,4,4],
        "skew":[1,2,3,4,50,float("inf"),None],
    })
    context=ai_context.build("inert","overview",working_data=(df,2,[]))
    local={c["name"]:c for c in context["columns"]}
    assert local["mixed"]["unique_count"]==5 and local["mixed"]["missing_count"]==2
    assert local["mixed"]["_finite_count"]==3 and local["mixed"]["_finite_unique_count"]==3
    assert local["mixed"]["mean"]==20
    assert local["balanced"]["_finite_count"]==local["balanced"]["_finite_unique_count"]==5
    assert local["valid"]["_finite_count"]==local["valid"]["_finite_unique_count"]==5
    assert local["repeated"]["_finite_count"]==7 and local["repeated"]["_finite_unique_count"]==4
    r=ai.respond(context,"overview","Explain statistics","Rules",selected_provider="gemini",cloud_intent=True)
    assert r["provider"]=="gemini" and len(calls)==1
    wire=calls[0][2]
    actual=json.loads(wire)["verified_context"]
    columns={c["name"]:c for c in actual["columns"]}
    assert "mean" not in columns["mixed"] and "median" not in columns["mixed"]
    assert "mean" not in columns["repeated"]
    assert "valid" not in columns
    assert columns["balanced"]["mean"]==3 and columns["balanced"]["median"]==3
    assert columns["skew"]["mean"]==12 and columns["skew"]["median"]==3
    assert actual["computed_patterns"]==[{"column":"skew","mean":12.0,"median":3.0}]
    assert "_finite_count" not in wire and "_finite_unique_count" not in wire
    local_prompt=json.loads(ai._encode_insight_prompt(context,"overview","Question",None,limit=9000))
    local_columns={c["name"]:c for c in local_prompt["verified_context"]["columns"]}
    assert local_columns["mixed"]["mean"]==20 and local_columns["mixed"]["max"]==30
    assert "_finite_count" not in json.dumps(local_prompt) and "_finite_unique_count" not in json.dumps(local_prompt)
    assert local["mixed"]["_finite_count"]==3


@pytest.mark.parametrize("finite,distinct",[
    (None,None),(4,4),(5,4),(True,5),("5",5),(51,5),(5,6),(50,51),
])
def test_invalid_finite_support_withholds_column_and_pattern(finite,distinct):
    context={"row_count":50,"columns":[{"name":"amount","kind":"numeric",
        "missing_count":0,"unique_count":50,"mean":99,"median":33,
        "_finite_count":finite,"_finite_unique_count":distinct}],
        "computed_patterns":[{"column":"amount","mean":99,"median":33,
        "_finite_count":finite,"_finite_unique_count":distinct}]}
    actual=ai._cloud_project(context)
    assert "mean" not in actual["columns"][0] and actual["computed_patterns"]==[]


def test_pattern_requires_own_matching_finite_witness():
    context={"row_count":10,"columns":[{"name":"amount","kind":"numeric",
        "missing_count":0,"unique_count":10,"mean":12,"median":3,
        "_finite_count":10,"_finite_unique_count":10}],
        "computed_patterns":[{"column":"amount","mean":12,"median":3,
        "_finite_count":4,"_finite_unique_count":4}]}
    actual=ai._cloud_project(context)
    assert actual["columns"][0]["mean"]==12 and actual["computed_patterns"]==[]


def test_holdout_support_never_authorizes_cv_scores(dispatch):
    cfg,calls=dispatch
    context={"experiment":{"metrics":{"sample_count":100,"accuracy":0.8,
        "baseline_test_metric":0.5,"baseline_cv":0.73,"cv_score":0.91},
        "comparison":[{"key":"ridge","status":"ready","cv_metric":0.91,"cv_std":0.02}]}}
    r=ai.respond(context,"evaluate","Explain scores","Rules",selected_provider="gemini",cloud_intent=True)
    assert r["provider"]=="gemini" and len(calls)==1
    actual=json.loads(calls[0][2])["verified_context"]["experiment"]
    assert actual["metrics"]=={"sample_count":100,"accuracy":0.8,"baseline_test_metric":0.5}
    assert actual["comparison"]==[{"key":"ridge","status":"ready"}]
    local=json.loads(ai._encode_insight_prompt(context,"evaluate","Question",None,limit=9000))
    assert local["verified_context"]["experiment"]==context["experiment"]



# B7: inert barriers, one shared slot, no external network or model.
@pytest.mark.parametrize("first",["insight","probe"])
def test_cloud_single_flight_across_insight_and_probe(dispatch,monkeypatch,first):
    cfg,calls=dispatch
    entered=Event()
    release=Event()
    original=ai._call_provider
    def blocked(*args,**kwargs):
        assert kwargs["still_authorized"]()
        calls.append(args[0])
        entered.set()
        assert release.wait(5)
        return ai.ProviderText("Late fixture","stop",False)
    monkeypatch.setattr(ai,"_call_provider",blocked)
    def insight():
        return ai.respond({},"assistant","Question","Rules",selected_provider="gemini",cloud_intent=True)
    def probe():
        return ai.owned_test_connection("groq")
    initial=ai._consent_revision
    with ThreadPoolExecutor(max_workers=1) as pool:
        future=pool.submit(insight if first=="insight" else probe)
        try:
            assert entered.wait(5)
            assert insight()["fallback"]
            assert probe()["status"]=="busy"
            # Simulate revoke then re-enable: identical flags/key do not restore
            # the old generation, and a pending network call retains its slot.
            with ai._lock:
                monkeypatch.setattr(ai,"_consent_revision",initial+2)
            assert insight()["fallback"]
            assert probe()["status"]=="busy"
            assert len(calls)==1
        finally:
            release.set()
        result=future.result(timeout=5)
    if first=="insight":
        assert result["fallback"] and result["answer"]=="Rules"
    else:
        assert result["status"]=="unavailable"
        assert not ai._health
    monkeypatch.setattr(ai,"_call_provider",original)
    assert insight()["provider"]=="gemini"
    assert probe()["status"]=="connected"


def test_cloud_revision_change_during_projection_never_reads_key(dispatch,monkeypatch):
    cfg,calls=dispatch
    original=ai._cloud_project
    def project(context):
        with ai._lock:
            monkeypatch.setattr(ai,"_consent_revision",ai._consent_revision+2)
        return original(context)
    monkeypatch.setattr(ai,"_cloud_project",project)
    monkeypatch.setattr(ai,"_get_key",lambda *_:pytest.fail("Revoked preparation reached credentials"))
    result=ai.respond({},"assistant","Question","Rules",selected_provider="gemini",cloud_intent=True)
    assert result["fallback"] and not calls and ai._cloud_slot is None


def test_cloud_revision_change_before_dispatch_denies_callback(dispatch,monkeypatch):
    cfg,calls=dispatch
    def revoked(*args,**kwargs):
        with ai._lock:
            monkeypatch.setattr(ai,"_consent_revision",ai._consent_revision+2)
        assert not kwargs["still_authorized"]()
        raise RuntimeError("inert refusal")
    monkeypatch.setattr(ai,"_call_provider",revoked)
    assert ai.respond({},"assistant","Question","Rules",selected_provider="gemini",cloud_intent=True)["fallback"]
    assert not calls and ai._cloud_slot is None


def test_cloud_dispatch_is_one_use_and_context_change_discards(dispatch,monkeypatch):
    cfg,calls=dispatch
    active=True
    def transport(*args,**kwargs):
        nonlocal active
        assert kwargs["still_authorized"]()
        assert not kwargs["still_authorized"]()
        active=False
        return ai.ProviderText("Stale fixture","stop",False)
    monkeypatch.setattr(ai,"_call_provider",transport)
    result=ai.respond({},"assistant","Question","Rules",selected_provider="gemini",
                      cloud_intent=True,still_current=lambda:active)
    assert result["fallback"] and result["answer"]=="Rules" and ai._cloud_slot is None


def test_cloud_transport_exception_releases_shared_slot(dispatch,monkeypatch):
    cfg,calls=dispatch
    original=ai._call_provider
    def fail(*args,**kwargs):
        assert kwargs["still_authorized"]()
        raise TimeoutError("inert")
    monkeypatch.setattr(ai,"_call_provider",fail)
    assert ai.owned_test_connection("gemini")["status"]=="unavailable"
    assert ai._cloud_slot is None
    monkeypatch.setattr(ai,"_call_provider",original)
    assert ai.respond({},"assistant","Question","Rules",selected_provider="groq",cloud_intent=True)["provider"]=="groq"


# B7 route-entry fences. Actual ASGI routes and owned adapter; no native
# session startup, host calls, live provider or local model execution.
@pytest.mark.parametrize("composition",["legacy","owned"])
@pytest.mark.parametrize("phase",["positive","preparation","late_publication"])
def test_cloud_http_route_generation_fence(product_composition,dispatch,monkeypatch,composition,phase):
    cfg,calls=dispatch
    _,coordinator,autonomy,_=product_composition
    monkeypatch.setattr(ai,"_consent_revision",ai.cloud_consent_revision())
    def revoke_reenable():
        with ai._lock:
            ai._consent_revision+=2

    if composition=="owned":
        from backend import resource_session
        def inert_session(bootstrap,read_mode,read_available_bytes,*,build_autonomy,build_app,build_server,demand):
            return SimpleNamespace(coordinator=coordinator,app=build_app(coordinator,autonomy))
        monkeypatch.setattr(resource_session,"DesktopResourceSession",inert_session)
        app=resource_session.compose_owned_desktop(None,lambda *_:pytest.fail("Native server construction")).app
    else:
        app=main.app
    original_build=main.ai_context.build
    original_insight=ai.owned_cloud_insight
    if phase=="preparation":
        def build(*args,**kwargs):
            result=original_build(*args,**kwargs)
            revoke_reenable()
            return result
        monkeypatch.setattr(main.ai_context,"build",build)
    elif phase=="late_publication":
        def insight(*args,**kwargs):
            result=original_insight(*args,**kwargs)
            assert result["source"]=="cloud_llm"
            revoke_reenable()
            return result
        monkeypatch.setattr(ai,"owned_cloud_insight",insight)
    with fixture_client(app) as client:
        seed=client.post("/api/projects",files={"file":("fixture.csv",b"amount,group\n1,A\n2,B\n3,A\n","text/csv")})
        assert seed.status_code==201,seed.text
        path="/api/projects/"+seed.json()["id"]+"/ai/insight"
        response=client.post(path,json={"context":"overview","selected_provider":"gemini",
                                        "cloud_intent":True,"consent_revision":-1})
        if phase=="preparation":
            assert response.status_code==200,response.text
            assert response.json()["fallback"] and not calls
        elif phase=="late_publication":
            assert response.status_code==409,response.text
            assert "Fixture answer" not in response.text and len(calls)==1
        else:
            assert response.status_code==200,response.text
            assert response.json()["provider"]=="gemini" and len(calls)==1
            assert "consent_revision" not in calls[0][2]
            assert "consent_revision" not in response.json()
        assert ai._cloud_slot is None


@pytest.mark.parametrize("witness",[False,"0",-1])
def test_cloud_expected_revision_refuses_invalid_witness_before_projection(dispatch,monkeypatch,witness):
    monkeypatch.setattr(ai,"_cloud_project",lambda *_:pytest.fail("Invalid witness reached projection"))
    monkeypatch.setattr(ai,"_get_key",lambda *_:pytest.fail("Invalid witness reached credentials"))
    result=ai.owned_cloud_insight({},"assistant","Question","Rules",False,"gemini",expected_revision=witness)
    assert result["fallback"] and not dispatch[1] and ai._cloud_slot is None


# B8 strict transport: inert HTTP responses only. No socket or provider call.
class _WireReply:
    def __init__(self, url, body, *, status=200, headers=None):
        self.url=url
        self.status=status
        self.headers=Message()
        for key,value in (headers if headers is not None else
                          [("Content-Type","application/json"),("Content-Length",str(len(body)))]):
            self.headers[key]=value
        self.stream=io.BytesIO(body)
        self.closed=False

    def geturl(self):
        return self.url

    def read1(self,size):
        assert 0 < size <= 8192
        return self.stream.read(size)

    def __enter__(self):
        return self

    def __exit__(self,*args):
        self.closed=True
        self.stream.close()


def _wire_payload(provider,finish=None):
    if provider=="gemini":
        return {"candidates":[{"content":{"parts":[{"text":"Fixture answer"}]},
                               "finishReason":finish or "STOP"}]}
    return {"choices":[{"message":{"content":"Fixture answer"},"finish_reason":finish or "stop"}]}


@pytest.mark.parametrize("provider,model",[
    ("gemini","gemini-3.1-flash-lite"),("gemini","gemini-3-flash-preview"),
    ("groq","openai/gpt-oss-120b"),("openrouter","openrouter/free")])
def test_cloud_wire_fixed_registry_and_headers(monkeypatch,provider,model):
    opened=[]
    replies=[]
    def opener(*handlers):
        assert handlers[0].proxies=={}
        assert handlers[1].redirect_request(None,None,302,"",{}, "https://invalid.test") is None
        def open_request(request,timeout):
            opened.append(request)
            assert 0 < timeout <= 10
            reply=_WireReply(request.full_url,json.dumps(_wire_payload(provider)).encode())
            replies.append(reply)
            return reply
        return SimpleNamespace(open=open_request)
    monkeypatch.setattr(ai.urllib.request,"build_opener",opener)
    monkeypatch.setattr(ai.urllib.request,"urlopen",lambda *_:pytest.fail("Non-strict transport"))
    answer=ai._call_provider(provider,model,"System","Question","fixture-secret-key",10,
                             strict=True,still_authorized=lambda:True)
    assert answer=="Fixture answer" and not answer.incomplete and replies[0].closed
    req=opened[0]
    assert req.full_url==ai._CLOUD_DESTINATIONS[(provider,model)]
    assert req.get_method()=="POST" and len(req.data)<=ai._CLOUD_WIRE_LIMIT
    assert req.get_header("Accept-encoding")=="identity"
    assert "fixture-secret-key" not in req.data.decode()
    if provider=="gemini":
        assert req.get_header("X-goog-api-key")=="fixture-secret-key"
        assert json.loads(req.data)["contents"][0]["parts"][0]["text"]=="Question"
    else:
        assert req.get_header("Authorization")=="Bearer fixture-secret-key"
        assert json.loads(req.data)["messages"][1]["content"]=="Question"


@pytest.mark.parametrize("provider,model,strict,key,timeout,user",[
    ("unknown","x",True,"fixture-secret-key",10,"Question"),
    ("gemini","../bad",True,"fixture-secret-key",10,"Question"),
    ("groq","gemini-3-flash-preview",True,"fixture-secret-key",10,"Question"),
    ("gemini","gemini-3-flash-preview",False,"fixture-secret-key",10,"Question"),
    ("gemini","gemini-3-flash-preview",True,"fixture-secret-\\rkey",10,"Question"),
    ("gemini","gemini-3-flash-preview",True,"fixture-secret-key",True,"Question"),
    ("gemini","gemini-3-flash-preview",True,"fixture-secret-key",10,"é"*5501),
    ("gemini","gemini-3-flash-preview",True,"fixture-secret-key",10,"\ud800"),
    ("gemini","gemini-3-flash-preview",True,"fixture-secret-key",10,"\u0001"*10000)])
def test_cloud_wire_refuses_invalid_request_before_opener(monkeypatch,provider,model,strict,key,timeout,user):
    monkeypatch.setattr(ai.urllib.request,"build_opener",lambda *_:pytest.fail("Invalid request reached opener"))
    with pytest.raises((ValueError,RuntimeError)):
        ai._call_provider(provider,model,"System",user,key,timeout,strict=strict,still_authorized=lambda:True)


@pytest.mark.parametrize("fault",["redirect","status","gzip","content_type","duplicate_length",
    "oversize_declared","oversize_actual","truncated","ambiguous_framing","bad_json","duplicate_json",
    "nonfinite","wrong_shape","tool_call","blocked_finish","surrogate","deadline"])
def test_cloud_wire_rejects_response_and_closes(monkeypatch,fault):
    provider="groq"
    model=ai.MODELS[provider]["routine"]
    url=ai._CLOUD_DESTINATIONS[(provider,model)]
    body=json.dumps(_wire_payload(provider)).encode()
    headers=[("Content-Type","application/json")]
    status=200
    response_url=url
    if fault=="redirect":
        response_url="https://invalid.test"
    elif fault=="status":
        status=302
    elif fault=="gzip":
        headers.append(("Content-Encoding","gzip"))
    elif fault=="content_type":
        headers=[("Content-Type","text/html")]
    elif fault=="duplicate_length":
        headers.extend([("Content-Length","10"),("Content-Length","10")])
    elif fault=="oversize_declared":
        headers.append(("Content-Length","256001"))
    elif fault=="oversize_actual":
        body=b"x"*256001
    elif fault=="truncated":
        headers.append(("Content-Length",str(len(body)+1)))
    elif fault=="ambiguous_framing":
        headers.extend([("Content-Length",str(len(body))),("Transfer-Encoding","chunked")])
    elif fault=="bad_json":
        body=b"PRIVATE_PROVIDER_BODY"
    elif fault=="duplicate_json":
        body=b'{"choices":[],"choices":[]}'
    elif fault=="nonfinite":
        body=b'{"choices":[],"value":NaN}'
    elif fault=="wrong_shape":
        body=b'{"choices":[42]}'
    elif fault=="tool_call":
        body=b'{"choices":[{"message":{"content":"Text","tool_calls":[{}]},"finish_reason":"stop"}]}'
    elif fault=="blocked_finish":
        body=json.dumps(_wire_payload(provider,"content_filter")).encode()
    elif fault=="surrogate":
        body=b'{"choices":[{"message":{"content":"\\ud800"},"finish_reason":"stop"}]}'
    reply=_WireReply(response_url,body,status=status,headers=headers)
    if fault=="deadline":
        now=[0.0]
        monkeypatch.setattr(ai.time,"monotonic",lambda:now[0])
        original=reply.read1
        def late(size):
            now[0]=11.0
            return original(size)
        reply.read1=late
    monkeypatch.setattr(ai.urllib.request,"build_opener",lambda *_:SimpleNamespace(open=lambda *a,**k:reply))
    with pytest.raises(RuntimeError,match="Selected cloud provider unavailable") as error:
        ai._call_provider(provider,model,"System","Question","fixture-secret-key",10,
                          strict=True,still_authorized=lambda:True)
    assert reply.closed and "PRIVATE_PROVIDER_BODY" not in str(error.value)


@pytest.mark.parametrize("status",[301,401,429,503])
def test_cloud_wire_closes_http_error(monkeypatch,status):
    stream=io.BytesIO(b"PRIVATE_PROVIDER_BODY")
    def fail(request,timeout):
        raise ai.urllib.error.HTTPError(request.full_url,status,"PRIVATE_REASON",None,stream)
    monkeypatch.setattr(ai.urllib.request,"build_opener",lambda *_:SimpleNamespace(open=fail))
    with pytest.raises(RuntimeError,match="Selected cloud provider unavailable") as error:
        ai._call_provider("groq",ai.MODELS["groq"]["routine"],"System","Question",
                          "fixture-secret-key",10,strict=True,still_authorized=lambda:True)
    assert stream.closed and "PRIVATE" not in str(error.value)


def test_cloud_wire_preserves_incomplete_metadata(monkeypatch):
    url=ai._CLOUD_DESTINATIONS[("groq",ai.MODELS["groq"]["routine"])]
    reply=_WireReply(url,json.dumps(_wire_payload("groq","length")).encode())
    monkeypatch.setattr(ai.urllib.request,"build_opener",lambda *_:SimpleNamespace(open=lambda *a,**k:reply))
    answer=ai._call_provider("groq",ai.MODELS["groq"]["routine"],"System","Question",
                             "fixture-secret-key",10,strict=True,still_authorized=lambda:True)
    assert answer.incomplete and answer.finish_reason=="length" and reply.closed
