"""Staged C1 framework lifetime tests: inert synthetic ASGI, no product data."""
import asyncio

import httpx
import pytest
from fastapi import BackgroundTasks, FastAPI, HTTPException
from starlette.responses import StreamingResponse

from backend.resource_admission import Coordinator, GIB, Operation
from backend.resource_http import OwnedHTTP
from backend.resource_routes import ROUTES


REQUEST = ROUTES["GET", "/api/projects/{project_id}/preparation"]
STREAM = ROUTES["POST", "/api/projects/{project_id}/quality/export"]


def coordinator(memory=3 * GIB):
    return Coordinator(lambda: "performance", lambda: memory)


@pytest.mark.parametrize("plan", [
    ROUTES["POST", "/api/projects"],
    ROUTES["POST", "/api/projects/{project_id}/experiments"],
    ROUTES["POST", "/api/investigations/{investigation_id}/autonomy/start"],
    ROUTES["POST", "/api/projects/{project_id}/ai/insight"],
    ROUTES["GET", "/api/health"],
])
def test_special_lifetimes_cannot_use_generic_adapter(plan):
    with pytest.raises(ValueError):
        OwnedHTTP(None, coordinator(), plan)


def test_refusal_precedes_any_downstream_body_read_or_allocation():
    async def scenario():
        calls = []
        async def downstream(scope, receive, send):
            calls.append("allocated")
        c = coordinator(0)
        async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=OwnedHTTP(downstream, c, REQUEST)),
                base_url="http://testserver") as client:
            result = await client.post("/", content=b"inert")
        assert result.status_code == 503
        assert result.json()["detail"]["code"] == "low_memory_headroom"
        assert not calls and not c.status()["active"]
    asyncio.run(scenario())


@pytest.mark.parametrize("stream", [False, True])
def test_real_framework_holds_lane_through_background_or_stream_cleanup(stream):
    async def scenario():
        c = coordinator()
        entered, complete = asyncio.Event(), asyncio.Event()
        app = FastAPI()
        if stream:
            @app.get("/")
            async def endpoint():
                async def chunks():
                    yield b"first"
                    entered.set()
                    await complete.wait()
                    yield b"last"
                return StreamingResponse(chunks())
        else:
            async def background():
                entered.set()
                await complete.wait()
            @app.get("/")
            async def endpoint(tasks: BackgroundTasks):
                tasks.add_task(background)
                return {"status": "accepted"}
        wrapped = OwnedHTTP(app, c, STREAM if stream else REQUEST)
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=wrapped),
                                     base_url="http://testserver") as client:
            pending = asyncio.create_task(client.get("/"))
            try:
                await asyncio.wait_for(entered.wait(), 5)
                assert not pending.done()
                assert c.status()["phase"] == "running"
                assert c.try_acquire(Operation.TRAINING).code == "resource_busy"
                denied = await client.get("/")
                assert denied.status_code == 503
                assert denied.json()["detail"]["code"] == "resource_busy"
            finally:
                complete.set()
                result = await asyncio.wait_for(pending, 5)
            assert result.status_code == 200
            if stream:
                assert result.content == b"firstlast"
            assert not c.status()["active"]
            new = c.try_acquire(Operation.TRAINING)
            assert new.allowed and c.release(new.lease)
    asyncio.run(scenario())


def test_handled_framework_error_does_not_leak_lease():
    async def scenario():
        c = coordinator()
        app = FastAPI()
        @app.get("/")
        async def endpoint():
            raise HTTPException(status_code=422, detail="invalid fixture")
        async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=OwnedHTTP(app, c, REQUEST)),
                base_url="http://testserver") as client:
            result = await client.get("/")
        assert result.status_code == 422
        assert not c.status()["active"]
    asyncio.run(scenario())


@pytest.mark.parametrize("cancel", [False, True])
def test_unconfirmed_downstream_exit_keeps_lane_blocked(cancel):
    async def scenario():
        c = coordinator()
        entered = asyncio.Event()
        async def downstream(scope, receive, send):
            entered.set()
            if cancel:
                await asyncio.Event().wait()
            raise RuntimeError("unconfirmed worker exit")
        async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=OwnedHTTP(downstream, c, REQUEST)),
                base_url="http://testserver") as client:
            pending = asyncio.create_task(client.get("/"))
            await asyncio.wait_for(entered.wait(), 5)
            if cancel:
                pending.cancel()
            with pytest.raises(asyncio.CancelledError if cancel else RuntimeError):
                await pending
        assert c.status()["phase"] == "blocked"
        assert c.try_acquire(Operation.EXPORT).code == "ownership_unknown"
    asyncio.run(scenario())
