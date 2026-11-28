"""C4 settings request boundary, inert ASGI and both actual compositions."""
import asyncio
import json

import pytest
from backend import main, settings_http as boundary, ai_provider, resource_policy
from backend.request_auth import RequestGuard, RequestTrust
from tests.fixture_http import fixture_client
from tests.settings_fixture import isolate_ai_store, fixture_store
from tests.test_c1_product_integration import product_composition


TRUST = RequestTrust("dev", 18042, "a"*64, "http://127.0.0.1:5173")
JSON_HEADER = (b"content-type", b"application/json")


def scope(path, headers, *, auth=True, method="PUT"):
    return {"type":"http","asgi":{"version":"3.0"},"http_version":"1.1",
            "method":method,"scheme":"http","path":path,"raw_path":path.encode(),
            "root_path":"","query_string":b"","client":("127.0.0.1",50000),
            "server":("127.0.0.1",18042),
            "headers":[(b"host",b"127.0.0.1:18042"),
                       *([(TRUST.header,TRUST.secret.encode())] if auth else []),
                       *headers]}


def chunk(body, more=False):
    return {"type":"http.request","body":body,"more_body":more}


def exchange(path, headers, events, *, auth=True, method="PUT", stall=False):
    calls, responses, reads = [], [], []
    pending=iter(events)
    async def downstream(s, receive, send):
        calls.append(await receive())
        await send({"type":"http.response.start","status":200,"headers":[]})
        await send({"type":"http.response.body","body":b"ok"})
    async def receive():
        reads.append(True)
        if stall:
            await asyncio.sleep(1)
        return next(pending)
    async def send(event):
        responses.append(event)
    asyncio.run(RequestGuard(boundary.SettingsRequestGuard(downstream),TRUST)(
        scope(path,headers,auth=auth,method=method),receive,send))
    return calls,responses,reads


@pytest.mark.parametrize("path,limit", list(boundary.LIMITS.items()))
def test_declared_oversize_refused_without_receive(path,limit):
    calls,responses,reads=exchange(path,[JSON_HEADER,(b"content-length",str(limit+1).encode())],[])
    assert not calls and not reads
    assert responses[0]["status"]==413
    assert (b"cache-control",b"no-store") in responses[0]["headers"]


@pytest.mark.parametrize("path,limit", list(boundary.LIMITS.items()))
def test_exact_cap_and_streamed_overflow(path,limit):
    raw=b"{}"+b" "*(limit-2)
    calls,responses,reads=exchange(path,[JSON_HEADER,(b"transfer-encoding",b"chunked")],
                                  [chunk(raw[:10],True),chunk(raw[10:])])
    assert calls==[chunk(raw)] and len(reads)==2 and responses[0]["status"]==200
    calls,responses,reads=exchange(path,[JSON_HEADER],[chunk(raw,True),chunk(b"x",True)])
    assert not calls and len(reads)==2 and responses[0]["status"]==413


@pytest.mark.parametrize("headers,body,status,reads_expected",[
    ([],b"{}",415,0),
    ([(b"content-type",b"text/plain")],b"{}",415,0),
    ([(b"content-type",b"application/json; charset=utf-16")],b"{}",415,0),
    ([JSON_HEADER,JSON_HEADER],b"{}",400,0),
    ([JSON_HEADER,(b"content-encoding",b"gzip")],b"{}",415,0),
    ([JSON_HEADER,(b"content-length",b"2"),(b"content-length",b"2")],b"{}",400,0),
    ([JSON_HEADER,(b"content-length",b"2,2")],b"{}",400,0),
    ([JSON_HEADER,(b"content-length",b"-1")],b"{}",400,0),
    ([JSON_HEADER,(b"content-length",b"2"),(b"transfer-encoding",b"chunked")],b"{}",400,0),
    ([JSON_HEADER,(b"transfer-encoding",b"gzip")],b"{}",400,0),
    ([JSON_HEADER,(b"content-length",b"3")],b"{}",400,1),
    ([JSON_HEADER,(b"content-length",b"1")],b"{}",400,1),
    ([JSON_HEADER],b'{"key":"private-marker","key":"other"}',422,1),
    ([JSON_HEADER],b'{"nested":{"x":1,"x":2}}',422,1),
    ([JSON_HEADER],b'{"x":NaN}',422,1),
    ([JSON_HEADER],b'{"x":1e999}',422,1),
    ([JSON_HEADER],b'{"x":"\xff"}',422,1),
    ([JSON_HEADER],b'{"key":"private-marker"',422,1),
    ([JSON_HEADER],b'[]',422,1),
    ([JSON_HEADER],b'',422,1),
])
def test_refused_framing_and_json_redacted(headers,body,status,reads_expected):
    calls,responses,reads=exchange("/api/ai/key",headers,[chunk(body)])
    assert not calls and len(reads)==reads_expected
    assert responses[0]["status"]==status
    assert b"private-marker" not in responses[-1]["body"]


def test_auth_first_and_non_settings_passthrough():
    calls,responses,reads=exchange("/api/ai/key",[],[],auth=False)
    assert not calls and not reads and responses[0]["status"]==401
    raw=b"not settings JSON"
    calls,responses,reads=exchange("/api/projects",[],[chunk(raw)],method="POST")
    assert calls==[chunk(raw)] and responses[0]["status"]==200


def test_timeout_disconnect_and_empty_event_limit(monkeypatch):
    monkeypatch.setattr(boundary,"BODY_TIMEOUT",0.001)
    calls,responses,reads=exchange("/api/ai/key",[JSON_HEADER],[],stall=True)
    assert not calls and responses[0]["status"]==408
    calls,responses,reads=exchange("/api/ai/key",[JSON_HEADER],
                                   [chunk(b"{",True),{"type":"http.disconnect"}])
    assert not calls and not responses and len(reads)==2
    monkeypatch.setattr(boundary,"BODY_TIMEOUT",10)
    calls,responses,reads=exchange("/api/ai/key",[JSON_HEADER],
                                   [chunk(b"",True)]*(boundary.MAX_EMPTY_EVENTS+1))
    assert not calls and responses[0]["status"]==400


@pytest.mark.parametrize("composition",["legacy","owned"])
def test_actual_routes_bounded_before_mutation_and_valid_roundtrip(
        product_composition, tmp_path, monkeypatch, composition):
    app=main.app if composition=="legacy" else product_composition[0]
    home=tmp_path/"settings"
    home.mkdir()
    isolate_ai_store(monkeypatch,ai_provider,home)
    monkeypatch.setattr(ai_provider,"_persistent_secrets",lambda:False)
    monkeypatch.setattr(resource_policy,"_settings_store",lambda:fixture_store(home))
    def no_provider(*args,**kwargs):
        pytest.fail("Unexpected provider dispatch")
    monkeypatch.setattr(ai_provider,"_call_provider",no_provider)
    client=fixture_client(app,trust=TRUST)
    for path,limit in boundary.LIMITS.items():
        response=client.put(path,content=b"{}"+b" "*limit,
                            headers={"Content-Type":"application/json","Origin":TRUST.dev_origin})
        assert response.status_code==413, response.text
        assert response.headers["access-control-allow-origin"]==TRUST.dev_origin
        assert response.headers["cache-control"]=="no-store"
    response=client.put("/api/ai/key",content=b'{"provider":"gemini","key":"private-marker","key":"other"}',
                        headers={"Content-Type":"application/json"})
    assert response.status_code==422 and "private-marker" not in response.text
    assert not list(home.iterdir()) and ai_provider._memory_keys=={}
    assert client.put("/api/ai/settings",json={"preferred_provider":"local"}).status_code==200
    assert client.put("/api/resource/policy",json={"mode":"low_memory"}).status_code==200
    assert client.put("/api/ai/key",json={"provider":"gemini","key":"synthetic-test-key"}).status_code==200
    assert json.loads((home/"ai_settings.json").read_text())["preferred_provider"]=="local"
    assert json.loads((home/"resource_preferences.json").read_text())["mode"]=="low_memory"
    assert ai_provider._memory_keys=={"gemini":"synthetic-test-key"}
    assert not (home/"ai_secrets.dpapi").exists()
    client.close()


def test_maximum_escaped_key_fits_request_cap():
    raw=json.dumps({"provider":"gemini","key":"\U0001f680"*512}).encode("utf-8")
    assert len(raw)<boundary.LIMITS["/api/ai/key"]
    calls,responses,_=exchange("/api/ai/key",[(b"content-type",b"Application/JSON; charset=UTF-8")],
                                [chunk(raw)])
    assert calls==[chunk(raw)] and responses[0]["status"]==200
