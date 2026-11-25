"""Explicit in-process HTTP fixture, outside the shipped application.

Use the actual immutable request guard and a synthetic loopback ASGI peer.
This helper does not bind a socket, modify environment, import storage or
monkeypatch the framework. Callers still own disposable data setup.
"""
from secrets import token_hex

import httpx
from fastapi.testclient import TestClient
from backend.request_auth import RequestGuard, RequestTrust


def _fixture_contract(trust, authenticated):
    """Fresh default trust, or an explicitly supplied immutable contract."""
    if type(authenticated) is not bool:
        raise ValueError("Explicit fixture authentication selection required")
    if trust is None:
        if not authenticated:
            raise ValueError("Negative fixture requires explicit trust")
        trust = RequestTrust("dev", 8000, token_hex(32), "http://127.0.0.1:5173")
    if not isinstance(trust, RequestTrust):
        raise ValueError("Explicit fixture request trust required")
    headers = {trust.header.decode("ascii"): trust.secret} if authenticated else {}
    return trust, headers


def fixture_client(app, *, trust=None, authenticated=True):
    """Guarded synchronous ASGI client, with explicit negative-test opt-out."""
    trust, headers = _fixture_contract(trust, authenticated)
    return TestClient(RequestGuard(app, trust),
                      base_url=f"http://127.0.0.1:{trust.port}",
                      client=("127.0.0.1", 50000),
                      headers=headers, follow_redirects=False)


def async_fixture_client(app, *, trust=None, authenticated=True):
    """Guarded asynchronous ASGI client; no lifespan or socket is started.

    Keep original HTTPX scheduling and propagated application exceptions.
    Negative cases require explicit trust and still pass the same guard.
    """
    trust, headers = _fixture_contract(trust, authenticated)
    transport = httpx.ASGITransport(app=RequestGuard(app, trust),
                                   client=("127.0.0.1", 50000),
                                   raise_app_exceptions=True)
    return httpx.AsyncClient(transport=transport,
                             base_url=f"http://127.0.0.1:{trust.port}",
                             headers=headers, follow_redirects=False,
                             trust_env=False)
