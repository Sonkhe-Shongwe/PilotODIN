"""Real multipart parser and raw ASGI receive fixtures; no live product writes."""
import asyncio

import httpx
import pytest
from starlette import formparsers
from starlette.responses import JSONResponse

from backend.resource_admission import Coordinator, GIB, Operation
from backend import resource_upload as upload


def coordinator(memory=3 * GIB):
    return Coordinator(lambda: "adaptive", lambda: memory)


@pytest.fixture
def spools(monkeypatch):
    owned = []
    real = formparsers.SpooledTemporaryFile
    def track(*args, **kwargs):
        spool = real(*args, **kwargs)
        owned.append(spool)
        return spool
    monkeypatch.setattr(formparsers, "SpooledTemporaryFile", track)
    return owned


def multipart(value=b"a,b\n1,2\n", name=b"file", ending=True):
    return (b"--abc\r\nContent-Disposition: form-data; name=\"" + name
            + b"\"; filename=\"test.csv\"\r\nContent-Type: text/csv\r\n\r\n"
            + value + (b"\r\n--abc--\r\n" if ending else b""))


async def invoke(app, events, headers=None):
    remaining = iter(events)
    sent = []
    reads = []
    async def receive():
        reads.append(1)
        return next(remaining)
    async def send(message):
        sent.append(message)
    scope = {"type":"http", "asgi":{"version":"3.0"}, "http_version":"1.1",
             "method":"POST", "scheme":"http", "path":"/api/projects",
             "raw_path":b"/api/projects", "query_string":b"", "root_path":"",
             "headers":headers if headers is not None else
                 [(b"content-type", b"multipart/form-data; boundary=abc")],
             "client":("127.0.0.1", 1234), "server":("testserver",80)}
    await app(scope, receive, send)
    return sent[0]["status"], reads


def event(body, more=False):
    return {"type":"http.request","body":body,"more_body":more}


def test_production_limits_preserved():
    assert upload.FILE_LIMIT == 40 * 1024 * 1024
    assert upload.ENVELOPE_LIMIT == 41 * 1024 * 1024


def test_busy_denial_before_first_receive_or_spool(spools):
    c = coordinator()
    lease = c.try_acquire(Operation.TRAINING).lease
    assert c.start(lease)
    async def consumer(file):
        pytest.fail("denied upload reached consumer")
    result, reads = asyncio.run(invoke(upload.OwnedUpload(consumer,c), []))
    assert result == 503 and not reads and not spools
    assert c.status()["operation"] == "training"
    assert c.release(lease)


def test_browser_form_keeps_lease_and_closes_before_response(spools):
    async def scenario():
        c = coordinator()
        async def consumer(file):
            assert c.status()["phase"] == "running"
            assert c.try_acquire(Operation.REPORT).code == "resource_busy"
            assert await file.read() == b"a,b\n1,2\n"
            assert not file.file.closed
            return JSONResponse({"accepted": True}, status_code=201)
        async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=upload.OwnedUpload(consumer,c)),
                base_url="http://testserver") as client:
            result = await client.post("/api/projects",
                                       files={"file":("test.csv", b"a,b\n1,2\n","text/csv")})
        assert result.status_code == 201
        assert len(spools) == 1 and spools[0].closed
        assert not c.status()["active"]
    asyncio.run(scenario())


@pytest.mark.parametrize("kind,expected", [
    ("file_limit",413), ("envelope",413), ("truncated",400),
    ("disconnect",400), ("wrong_part",400), ("length_mismatch",400),
    ("duplicate_length",400), ("large_declared",413), ("empty",400),
    ("two_files",400),
])
def test_refusal_and_actual_parser_spool_cleanup(kind,expected,spools,monkeypatch):
    c = coordinator()
    async def consumer(file):
        pytest.fail("invalid upload reached consumer")
    headers = [(b"content-type",b"multipart/form-data; boundary=abc")]
    body = multipart()
    events = [event(body)]
    if kind == "file_limit":
        monkeypatch.setattr(upload,"FILE_LIMIT",2)
    elif kind == "envelope":
        first = multipart(b"x",ending=False)
        monkeypatch.setattr(upload,"ENVELOPE_LIMIT",len(first)+5)
        events = [event(first,True), event(b"123456789")]
    elif kind == "truncated":
        events = [event(multipart(ending=False))]
    elif kind == "disconnect":
        events = [event(multipart(ending=False),True), {"type":"http.disconnect"}]
    elif kind == "wrong_part":
        events = [event(multipart(name=b"other"))]
    elif kind == "length_mismatch":
        headers.append((b"content-length",str(len(body)+1).encode()))
    elif kind == "duplicate_length":
        headers.extend([(b"content-length",b"100"),(b"content-length",b"100")])
    elif kind == "large_declared":
        headers.append((b"content-length",str(upload.ENVELOPE_LIMIT+1).encode()))
    elif kind == "empty":
        events = [event(multipart(b""))]
    elif kind == "two_files":
        events = [event(multipart(ending=False)+b"\r\n"+multipart())]
    result, reads = asyncio.run(invoke(upload.OwnedUpload(consumer,c),events,headers))
    assert result == expected
    if kind in {"duplicate_length","large_declared"}:
        assert not reads and not spools
    else:
        assert spools and all(s.closed for s in spools)
    assert not c.status()["active"]


def test_chunked_exact_envelope_and_file_boundary(spools,monkeypatch):
    body = multipart(b"12345")
    monkeypatch.setattr(upload,"FILE_LIMIT",5)
    monkeypatch.setattr(upload,"ENVELOPE_LIMIT",len(body))
    c = coordinator()
    async def consumer(file):
        assert await file.read() == b"12345"
        return JSONResponse({},status_code=201)
    events = [event(body[:20],True),event(body[20:-2],True),event(body[-2:])]
    status,reads = asyncio.run(invoke(upload.OwnedUpload(consumer,c),events))
    assert status == 201 and len(reads) == 3
    assert len(spools) == 1 and spools[0].closed
    assert not c.status()["active"]


def test_consumer_failure_and_cancellation_never_certify_ownership(spools):
    async def scenario():
        for cancel in (False,True):
            c = coordinator()
            entered = asyncio.Event()
            async def consumer(file):
                entered.set()
                if cancel:
                    await asyncio.Event().wait()
                raise RuntimeError("unconfirmed consumer")
            pending = asyncio.create_task(invoke(upload.OwnedUpload(consumer,c),
                                                  [event(multipart())]))
            await asyncio.wait_for(entered.wait(),5)
            if cancel:
                pending.cancel()
            with pytest.raises(asyncio.CancelledError if cancel else RuntimeError):
                await pending
            assert spools[-1].closed
            assert c.status()["phase"] == "blocked"
    asyncio.run(scenario())


def test_parser_cancellation_closes_spool_and_retains_lane(spools):
    async def scenario():
        c = coordinator()
        entered = asyncio.Event()
        async def consumer(file):
            pytest.fail("cancelled parser reached consumer")
        async def receive():
            if not entered.is_set():
                entered.set()
                return event(multipart(ending=False), True)
            await asyncio.Event().wait()
        async def send(message):
            pytest.fail("cancelled parser sent response")
        scope = {"type":"http","method":"POST","path":"/api/projects",
                 "headers":[(b"content-type",b"multipart/form-data; boundary=abc")]}
        pending = asyncio.create_task(upload.OwnedUpload(consumer,c)(scope,receive,send))
        # A spool must actually have been allocated before cancellation.
        for _ in range(100):
            if spools:
                break
            await asyncio.sleep(0.01)
        assert spools and not spools[0].closed
        pending.cancel()
        with pytest.raises(asyncio.CancelledError):
            await pending
        assert spools[0].closed and c.status()["phase"] == "blocked"
    asyncio.run(scenario())
