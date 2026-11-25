"""Immutable request trust contract for the staged C3 serving boundary.

No environment lookup or framework dependency. A trusted launcher constructs
one contract before app creation; no contract means no runtime authorization.
The desktop runner installs this boundary outside both product compositions.
"""
from dataclasses import dataclass, field
from hmac import compare_digest
import re

_DESKTOP = frozenset(("http://tauri.localhost", "https://tauri.localhost", "tauri://localhost"))
_DESKTOP_MODES = frozenset(("desktop", "desktop-debug"))
_DEBUG_ORIGINS = frozenset(f"http://{host}:{port}" for host in ("127.0.0.1", "localhost")
                           for port in range(5173, 5180))
_DEV_MODES = frozenset(("dev", "hosted-fixture", "local-devqa"))
_DESKTOP_HEADER = b"x-pilotodin-session"
_DEV_HEADER = b"x-pilotodin-dev-capability"
_METHODS = frozenset(("GET", "POST", "PUT", "PATCH", "DELETE", "HEAD"))
_SINGLE = frozenset((b"host", b"origin", _DESKTOP_HEADER, _DEV_HEADER,
                     b"access-control-request-method", b"access-control-request-headers"))


@dataclass(frozen=True)
class RequestTrust:
    mode: str
    port: int
    secret: str = field(repr=False)
    dev_origin: str | None = None

    def __post_init__(self):
        if (type(self.mode) is not str or
                self.mode not in _DEV_MODES | _DESKTOP_MODES or
                type(self.port) is not int or not 1024 <= self.port <= 65535 or
                type(self.secret) is not str or
                re.fullmatch(r"[0-9a-f]{64}", self.secret) is None):
            raise ValueError("Invalid serving trust configuration")
        if self.mode in _DESKTOP_MODES:
            if self.dev_origin is not None:
                raise ValueError("Mixed serving trust configuration")
        elif (type(self.dev_origin) is not str or re.fullmatch(
                r"http://(?:localhost|127\.0\.0\.1):517[3-9]", self.dev_origin) is None):
            raise ValueError("Explicit local development origin required")

    @property
    def header(self):
        return _DESKTOP_HEADER if self.mode in _DESKTOP_MODES else _DEV_HEADER

    @property
    def origins(self):
        if self.mode == "desktop-debug":
            return _DESKTOP | _DEBUG_ORIGINS
        return _DESKTOP if self.mode == "desktop" else frozenset((self.dev_origin,))


@dataclass(frozen=True)
class Authorization:
    status: int
    preflight: bool = False

    @property
    def allowed(self):
        return self.status == 200


def _local_address(value, expected_port=None):
    return (isinstance(value, (tuple, list)) and len(value) == 2 and
            value[0] == "127.0.0.1" and type(value[1]) is int and
            1 <= value[1] <= 65535 and
            (expected_port is None or value[1] == expected_port))


def authorize(scope, trust):
    """Check raw ASGI transport and headers before any route or storage read.

    A successful preflight authorizes CORS negotiation only. No credential is
    inferred from origin or Host. Runtime forwarding must be disabled by the
    launcher; forwarded headers are also refused here.
    """
    if not isinstance(trust, RequestTrust):
        return Authorization(503)
    if (scope.get("type") != "http" or scope.get("scheme") != "http" or
            not _local_address(scope.get("client")) or
            not _local_address(scope.get("server"), trust.port)):
        return Authorization(403)
    values = {}
    for pair in scope.get("headers", ()):
        if (not isinstance(pair, (tuple, list)) or len(pair) != 2 or
                not all(isinstance(part, bytes) for part in pair)):
            return Authorization(400)
        name, value = pair
        name = name.lower()
        if name == b"forwarded" or name.startswith(b"x-forwarded-"):
            return Authorization(403)
        if name not in _SINGLE:
            continue
        if name in values or len(value) > 256:
            return Authorization(400)
        try:
            decoded = value.decode("ascii")
        except UnicodeError:
            return Authorization(400)
        if any(ord(char) < 33 or ord(char) > 126 for char in decoded):
            # Header lists may contain spaces between comma-delimited names.
            if name != b"access-control-request-headers" or any(
                    ord(char) < 32 or ord(char) > 126 for char in decoded):
                return Authorization(400)
        values[name] = decoded
    if values.get(b"host") not in (f"127.0.0.1:{trust.port}", f"localhost:{trust.port}"):
        return Authorization(403)
    origin = values.get(b"origin")
    if origin is not None and origin not in trust.origins:
        return Authorization(403)
    other = _DEV_HEADER if trust.header == _DESKTOP_HEADER else _DESKTOP_HEADER
    if other in values:
        return Authorization(401)
    if scope.get("method") == "OPTIONS":
        method = values.get(b"access-control-request-method")
        names = values.get(b"access-control-request-headers", "").lower().split(",")
        requested = [name.strip(" ") for name in names]
        allowed = {"content-type", trust.header.decode("ascii")}
        if (origin is None or method not in _METHODS or
                trust.header in values or
                len(requested) != len(set(requested)) or
                trust.header.decode("ascii") not in requested or
                not set(requested) <= allowed):
            return Authorization(403)
        return Authorization(200, preflight=True)
    if scope.get("method") not in _METHODS:
        return Authorization(405)
    if (b"access-control-request-method" in values or
            b"access-control-request-headers" in values):
        return Authorization(400)
    supplied = values.get(trust.header, "")
    if not compare_digest(supplied.encode("ascii"), trust.secret.encode("ascii")):
        return Authorization(401)
    return Authorization(200)


def desktop_trust_from_environ(environ):
    """Capture launcher inputs once, before workspace or analytical imports.

    Rust explicitly supplies the existing debug flag from debug_assertions.
    A release launch supplies 0; absent flag is strict desktop (old verifier).
    No dev capability or non-desktop serving mode is admitted here.
    """
    if any(environ.get(key) for key in ("PILOTODIN_SERVER_MODE",
                                       "PILOTODIN_DEV_CAPABILITY",
                                       "PILOTODIN_DEV_ORIGIN",
                                       "PILOTODIN_DEV_PORT")):
        raise ValueError("Mixed serving trust configuration")
    debug = environ.get("PILOTODIN_DESKTOP_ALLOW_DEV", "0")
    port = environ.get("PILOTODIN_DESKTOP_PORT", "")
    if debug not in ("0", "1") or not isinstance(port, str) or not re.fullmatch(r"[0-9]{4,5}", port):
        raise ValueError("Invalid desktop serving trust configuration")
    return RequestTrust("desktop-debug" if debug == "1" else "desktop",
                        int(port), environ.get("PILOTODIN_DESKTOP_SESSION", ""))


def live_dev_trust_from_environ(environ):
    """Explicit paired Live Dev only; no inherited desktop or QA capability."""
    if (environ.get("PILOTODIN_SERVER_MODE") != "dev"
            or environ.get("PILOTODIN_DEV_PORT") != "8000"
            or environ.get("PILOTODIN_DEV_ORIGIN") != "http://127.0.0.1:5173"
            or environ.get("PILOTODIN_DESKTOP_ALLOW_DEV", "0") != "0"
            or any(environ.get(key) for key in (
                "PILOTODIN_DESKTOP_SESSION", "PILOTODIN_DESKTOP_PORT",
                "PILOTODIN_DESKTOP_WATCH_STDIN", "PILOTODIN_CONTROL_MODE",
                "PILOTODIN_CONTROL_GENERATION", "PILOTODIN_CONTROL_CAPABILITY"))):
        raise ValueError("Invalid Live Dev serving configuration")
    return RequestTrust("dev", 8000, environ.get("PILOTODIN_DEV_CAPABILITY", ""),
                        "http://127.0.0.1:5173")


def hosted_browser_trust_from_environ(environ):
    """Exact disposable browser fixture, not the separately gated native QA."""
    if (environ.get("PILOTODIN_SERVER_MODE") != "hosted-fixture"
            or environ.get("CI") != "true" or environ.get("GITHUB_ACTIONS") != "true"
            or environ.get("P1_REAL_HTTP_E2E") != "1"
            or not re.fullmatch(r"[0-9]+", environ.get("GITHUB_RUN_ID", ""))
            or environ.get("PILOTODIN_DEV_PORT") != "8000"
            or environ.get("PILOTODIN_DEV_ORIGIN") != "http://127.0.0.1:5178"
            or environ.get("PILOTODIN_DESKTOP_ALLOW_DEV", "0") != "0"
            or any(environ.get(key) for key in (
                "PILOTODIN_DESKTOP_SESSION", "PILOTODIN_DESKTOP_PORT",
                "PILOTODIN_DESKTOP_WATCH_STDIN", "PILOTODIN_CONTROL_MODE",
                "PILOTODIN_CONTROL_GENERATION", "PILOTODIN_CONTROL_CAPABILITY"))):
        raise ValueError("Invalid hosted browser serving configuration")
    return RequestTrust("hosted-fixture", 8000, environ.get("PILOTODIN_DEV_CAPABILITY", ""),
                        "http://127.0.0.1:5178")


def local_report_chain_trust_from_environ(environ):
    """Exact managed P2 report-chain launcher; the factory admits its workspace."""
    port = environ.get("PILOTODIN_DEV_PORT", "")
    if (environ.get("PILOTODIN_SERVER_MODE") != "local-devqa"
            or environ.get("RL_invariant") != "1"
            or environ.get("PILOTODIN_DEV_ORIGIN") != "http://127.0.0.1:5176"
            or not isinstance(port, str)
            or re.fullmatch(r"[1-9][0-9]{3,4}", port) is None
            or int(port) == 5176
            or environ.get("PILOTODIN_DESKTOP_ALLOW_DEV", "0") != "0"
            or any(environ.get(key) for key in (
                "PILOTODIN_DESKTOP_SESSION", "PILOTODIN_DESKTOP_PORT",
                "PILOTODIN_DESKTOP_WATCH_STDIN", "PILOTODIN_CONTROL_MODE",
                "PILOTODIN_CONTROL_GENERATION", "PILOTODIN_CONTROL_CAPABILITY"))):
        raise ValueError("Invalid managed report-chain serving configuration")
    return RequestTrust("local-devqa", int(port),
                        environ.get("PILOTODIN_DEV_CAPABILITY", ""),
                        "http://127.0.0.1:5176")


# Exact existing fixed-port local DevQA phases, not arbitrary QA origins.
_LOCAL_QA_PORTS = {
    "P2-NATIVE-DELIVER-CONSENT": 5177,
    "P2-NATIVE-TWO-WINDOW-DELIVER": 5177,
    "P3-NATIVE-SEMANTIC-CONTEXT": 5178,
    "P3-NATIVE-QUALITY-W5": 5178,
}


def local_fixed_qa_trust_from_environ(environ, phase):
    origin = f"http://127.0.0.1:{_LOCAL_QA_PORTS.get(phase, 0)}"
    if (phase not in _LOCAL_QA_PORTS
            or environ.get("PILOTODIN_SERVER_MODE") != "local-devqa"
            or environ.get("PILOTODIN_DEV_PORT") != "8000"
            or environ.get("PILOTODIN_DEV_ORIGIN") != origin
            or environ.get("PILOTODIN_DESKTOP_ALLOW_DEV", "0") != "0"
            or any(environ.get(key) for key in (
                "PILOTODIN_DESKTOP_SESSION", "PILOTODIN_DESKTOP_PORT",
                "PILOTODIN_DESKTOP_WATCH_STDIN", "PILOTODIN_CONTROL_MODE",
                "PILOTODIN_CONTROL_GENERATION", "PILOTODIN_CONTROL_CAPABILITY"))):
        raise ValueError("Invalid fixed-port local DevQA serving configuration")
    return RequestTrust("local-devqa", 8000,
                        environ.get("PILOTODIN_DEV_CAPABILITY", ""), origin)


# In-process identity witness, never a request header or serialized token.
# The outer guard overwrites any incoming value on the admitted HTTP scope.
_AUTHORIZED = object()
_SCOPE_KEY = "pilotodin.request_authorized"


def request_authorized(scope):
    return scope.get(_SCOPE_KEY) is _AUTHORIZED


class RequestGuard:
    """Outer ASGI boundary; never call analytical code for denied HTTP or OPTIONS."""

    def __init__(self, app, trust):
        if not isinstance(trust, RequestTrust):
            raise ValueError("Explicit serving trust required")
        self._app = app
        self._trust = trust

    async def __call__(self, scope, receive, send):
        kind = scope.get("type")
        if kind == "lifespan":
            await self._app(scope, receive, send)
            return
        if kind == "websocket":
            await send({"type": "websocket.close", "code": 1008})
            return
        if kind != "http":
            raise ValueError("Unsupported transport")
        decision = authorize(scope, self._trust)
        if not decision.allowed:
            body = b'{"detail":"Local API request refused"}'
            await send({"type": "http.response.start", "status": decision.status,
                        "headers": [(b"content-type", b"application/json"),
                                    (b"content-length", str(len(body)).encode("ascii")),
                                    (b"cache-control", b"no-store")]})
            await send({"type": "http.response.body", "body": body})
            return
        if decision.preflight:
            headers = {name.lower(): value for name, value in scope["headers"]}
            await send({"type": "http.response.start", "status": 204,
                        "headers": [(b"access-control-allow-origin", headers[b"origin"]),
                                    (b"access-control-allow-methods", headers[b"access-control-request-method"]),
                                    (b"access-control-allow-headers",
                                     b"content-type, " + self._trust.header),
                                    (b"vary", b"Origin, Access-Control-Request-Method, Access-Control-Request-Headers"),
                                    (b"cache-control", b"no-store")]})
            await send({"type": "http.response.body", "body": b""})
            return
        admitted = dict(scope)
        admitted[_SCOPE_KEY] = _AUTHORIZED
        await self._app(admitted, receive, send)
