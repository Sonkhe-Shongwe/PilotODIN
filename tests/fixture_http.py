"""Explicit in-process HTTP fixture, outside the shipped application.

Use the actual immutable request guard and a synthetic loopback ASGI peer.
This helper does not bind a socket, modify environment, import storage or
monkeypatch the framework. Callers still own disposable data setup.
"""
from secrets import token_hex

from fastapi.testclient import TestClient
from backend.request_auth import RequestGuard, RequestTrust


def fixture_client(app, *, trust=None, authenticated=True):
    """Construct a guarded ASGI client, with explicit negative-test opt-out.

    The default is a fresh per-client development capability at the existing
    loopback contract. For auth-negative tests, supply an immutable trust
    explicitly and set authenticated=False; requests still pass the guard.
    """
    if type(authenticated) is not bool:
        raise ValueError("Explicit fixture authentication selection required")
    if trust is None:
        if not authenticated:
            raise ValueError("Negative fixture requires explicit trust")
        trust = RequestTrust("dev", 8000, token_hex(32), "http://127.0.0.1:5173")
    if not isinstance(trust, RequestTrust):
        raise ValueError("Explicit fixture request trust required")
    headers = {trust.header.decode("ascii"): trust.secret} if authenticated else {}
    return TestClient(RequestGuard(app, trust),
                      base_url=f"http://127.0.0.1:{trust.port}",
                      client=("127.0.0.1", 50000),
                      headers=headers, follow_redirects=False)
