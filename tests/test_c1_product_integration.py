"""Actual FastAPI routes in separate owned composition; no real model/provider."""
import json
import pytest
from contextlib import closing
from secrets import token_hex
from tests.fixture_http import fixture_client
from backend.request_auth import RequestTrust
from backend import main, storage, quality, investigations, autonomy
from backend.resource_admission import Coordinator, GIB, Operation
from backend.resource_autonomy import AutonomyStages
from backend.resource_routes import ROUTES

@pytest.fixture
def product_composition(monkeypatch,tmp_path):
    home=tmp_path/"product"
    (home/"datasets").mkdir(parents=True)
    (home/"models").mkdir()
    monkeypatch.setattr(storage,"HOME",home)
    monkeypatch.setattr(storage,"DB_PATH",home/"pilotodin.sqlite3")
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
    try:
        yield app,c,a,calls
    finally:
        a.drain(2)


@pytest.fixture
def product(product_composition):
    app,c,a,calls=product_composition
    with fixture_client(app) as client:
        yield client,c,a,calls

def upload(client):
    return client.post("/api/projects",files={"file":("test.csv",b"Region,Revenue\nNorth,100\nSouth,200\nNorth,300\n","text/csv")})

def test_actual_inventory_is_bound_without_mutating_legacy(product,product_composition):
    client,c,_,_=product
    app,_,_,_=product_composition
    from fastapi.routing import APIRoute
    assert {(method,r.path) for r in app.routes if isinstance(r,APIRoute) for method in r.methods}==set(ROUTES)
    legacy={r.path:r for r in main.app.routes if isinstance(r,APIRoute)}
    assert all(r is not legacy[r.path] for r in app.routes if isinstance(r,APIRoute))
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

def test_actual_auth_precedes_owned_upload(product,product_composition):
    client,c,_,_=product
    app,_,_,_=product_composition
    trust=RequestTrust("desktop",9012,token_hex(32))
    lease=c.try_acquire(Operation.TRAINING).lease
    assert c.start(lease)
    try:
        # Do not start another app lifespan or alter the existing coordinator.
        with closing(fixture_client(app,trust=trust,authenticated=False)) as denied:
            assert upload(denied).status_code==401
        assert upload(client).status_code==503
    finally:
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


def test_resource_status_legacy_shape_and_owned_auth(product,product_composition,monkeypatch):
    client,c,_,_=product
    app,_,_,_=product_composition
    with fixture_client(main.app) as legacy:
        assert "workload" not in legacy.get("/api/resource/status").json()
    assert client.get("/api/resource/status").json()["workload"]==c.status()
    trust=RequestTrust("desktop",9012,token_hex(32))
    with closing(fixture_client(app,trust=trust,authenticated=False)) as desktop:
        assert desktop.get("/api/resource/status").status_code==401
        headers={"X-PilotODIN-Session":trust.secret}
        assert desktop.get("/api/resource/status",headers=headers).json()["workload"]==c.status()
        # Runtime environment changes must not replace a captured contract.
        replacement=token_hex(32)
        monkeypatch.setenv("PILOTODIN_DESKTOP_SESSION",replacement)
        assert desktop.get("/api/resource/status",headers={"X-PilotODIN-Session":replacement}).status_code==401
        assert desktop.get("/api/resource/status",headers=headers).json()["workload"]==c.status()


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


# C3 route-wide refusal uses the real ASGI compositions and the exact C1
# route inventory. No application lifespan, actual model or provider is run.
def _c3_scope(method, path, port=18042, headers=None):
    return {
        "type": "http", "asgi": {"version": "3.0", "spec_version": "2.4"},
        "http_version": "1.1", "scheme": "http", "method": method,
        "path": path, "raw_path": path.encode("ascii"), "query_string": b"",
        "root_path": "", "client": ("127.0.0.1", 50000),
        "server": ("127.0.0.1", port),
        "headers": [(b"host", f"127.0.0.1:{port}".encode("ascii"))] + list(headers or []),
    }


def _c3_path(template):
    import re
    return re.sub(r"\{[^}]+\}", "a"*32, template)


async def _c3_exchange(app, scope):
    messages = []
    async def receive():
        pytest.fail("Refused request or preflight accessed its body")
    async def send(message):
        messages.append(message)
    await app(scope, receive, send)
    assert messages and messages[0]["type"] == "http.response.start"
    return messages[0]


def _c3_refusal_witnesses(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("Denied HTTP reached archive or scratch storage")
    monkeypatch.setattr(main.project_lifecycle, "archived_mutation_project", forbidden)
    monkeypatch.setattr(storage, "check_scratch", forbidden)


@pytest.mark.parametrize("composition", ("legacy", "owned"))
def test_c3_bare_app_refuses_every_route_even_with_legacy_credentials(
        product_composition, monkeypatch, composition):
    import asyncio
    from fastapi.routing import APIRoute
    app = main.app if composition == "legacy" else product_composition[0]
    observed = {(method, route.path) for route in app.routes if isinstance(route, APIRoute)
                for method in route.methods}
    assert observed == set(ROUTES) and len(observed) == 76
    _c3_refusal_witnesses(monkeypatch)
    secret = "b"*64
    monkeypatch.setenv("PILOTODIN_DESKTOP_SESSION", secret)
    monkeypatch.setenv("PILOTODIN_DESKTOP_ALLOW_DEV", "1")
    async def exercise():
        for method, template in sorted(observed):
            path = _c3_path(template)
            for headers in ([], [(b"x-pilotodin-session", secret.encode("ascii"))],
                            [(b"x-pilotodin-dev-capability", secret.encode("ascii"))]):
                scope = _c3_scope(method, path, headers=headers)
                # A forged truthy/serialized witness does not confer authority.
                scope["pilotodin.request_authorized"] = True
                result = await _c3_exchange(app, scope)
                assert result["status"] == 401, (composition, method, template)
                assert (b"cache-control", b"no-store") in result["headers"]
            result = await _c3_exchange(app, _c3_scope("OPTIONS", path, headers=[
                (b"origin", b"http://tauri.localhost"),
                (b"access-control-request-method", method.encode("ascii")),
                (b"access-control-request-headers", b"x-pilotodin-session"),
            ]))
            assert result["status"] == 401, (composition, "OPTIONS", template)
    asyncio.run(exercise())


@pytest.mark.parametrize("composition", ("legacy", "owned"))
@pytest.mark.parametrize("mode,origin", (("desktop", "https://tauri.localhost"),
                                         ("dev", "http://127.0.0.1:5173")))
def test_c3_outer_guard_routewide_negative_and_bounded_preflight_matrix(
        product_composition, monkeypatch, composition, mode, origin):
    import asyncio
    from backend.request_auth import RequestGuard
    app = main.app if composition == "legacy" else product_composition[0]
    _c3_refusal_witnesses(monkeypatch)
    trust = RequestTrust(mode, 18042, "a"*64, origin if mode == "dev" else None)
    guarded = RequestGuard(app, trust)
    good = (trust.header, trust.secret.encode("ascii"))
    other = b"x-pilotodin-session" if mode == "dev" else b"x-pilotodin-dev-capability"
    origin_header = (b"origin", origin.encode("ascii"))

    async def exercise():
        assert len(ROUTES) == 76
        for method, template in sorted(ROUTES):
            path = _c3_path(template)
            cases = (
                ([], 401),
                ([(trust.header, b"b"*64)], 401),
                ([good, (other, b"b"*64)], 401),
                ([good, good], 400),
                ([good, (b"host", b"127.0.0.1:18042")], 400),
                ([good, (b"origin", b"https://invalid.example")], 403),
                ([good, (b"x-forwarded-for", b"127.0.0.1")], 403),
                ([good, (b"origin", b"\xff")], 400),
            )
            for headers, expected in cases:
                scope = _c3_scope(method, path, headers=headers)
                scope["pilotodin.request_authorized"] = True
                assert (await _c3_exchange(guarded, scope))["status"] == expected, (
                    composition, mode, method, template, expected)
            for override in ({"client": ("192.0.2.1", 50000)},
                             {"server": ("127.0.0.1", 18043)},
                             {"scheme": "https"}):
                scope = _c3_scope(method, path, headers=[good, origin_header])
                scope.update(override)
                assert (await _c3_exchange(guarded, scope))["status"] == 403
            scope = _c3_scope(method, path, headers=[good])
            scope["headers"][0] = (b"host", b"localhost:18043")
            assert (await _c3_exchange(guarded, scope))["status"] == 403
            negotiation = [
                origin_header, (b"access-control-request-method", method.encode("ascii")),
                (b"access-control-request-headers", trust.header + b", content-type"),
            ]
            result = await _c3_exchange(guarded, _c3_scope("OPTIONS", path, headers=negotiation))
            assert result["status"] == 204, (composition, mode, method, template)
            assert (b"access-control-allow-origin", origin_header[1]) in result["headers"]
            refused = negotiation[:-1] + [(b"access-control-request-headers", trust.header+b", authorization")]
            assert (await _c3_exchange(guarded, _c3_scope("OPTIONS", path, headers=refused)))["status"] == 403
    asyncio.run(exercise())


@pytest.mark.parametrize("composition", ("legacy", "owned"))
def test_c3_authorized_archive_then_scratch_order(product_composition, monkeypatch, composition):
    app = main.app if composition == "legacy" else product_composition[0]
    trace = []
    def archive(method, path):
        trace.append("archive")
        return None
    def scratch():
        trace.append("scratch")
    monkeypatch.setattr(main.project_lifecycle, "archived_mutation_project", archive)
    monkeypatch.setattr(storage, "check_scratch", scratch)
    with closing(fixture_client(app)) as client:
        result = client.get("/api/health")
    assert result.status_code == 200
    assert trace == ["archive", "scratch"]


def test_c3_direct_local_control_requires_identity_witness(monkeypatch):
    from fastapi import HTTPException, Request
    monkeypatch.setenv("PILOTODIN_DESKTOP_SESSION", "b"*64)
    scope = _c3_scope("GET", "/api/ai/settings", headers=[(b"x-pilotodin-session", b"b"*64)])
    scope["pilotodin.request_authorized"] = True
    with pytest.raises(HTTPException) as error:
        main._local_request(Request(scope))
    assert error.value.status_code == 401
