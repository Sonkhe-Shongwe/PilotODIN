"""Immutable request trust contract for the staged C3 serving boundary.

No environment lookup or framework dependency. A trusted launcher constructs
one contract before app creation; no contract means no runtime authorization.
This module is not yet installed on the existing app.
"""
from dataclasses import dataclass, field
from hmac import compare_digest
import re

_DESKTOP = frozenset(("http://tauri.localhost", "https://tauri.localhost", "tauri://localhost"))
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
                self.mode not in _DEV_MODES | {"desktop"} or
                type(self.port) is not int or not 1024 <= self.port <= 65535 or
                type(self.secret) is not str or
                re.fullmatch(r"[0-9a-f]{64}", self.secret) is None):
            raise ValueError("Invalid serving trust configuration")
        if self.mode == "desktop":
            if self.dev_origin is not None:
                raise ValueError("Mixed serving trust configuration")
        elif (type(self.dev_origin) is not str or re.fullmatch(
                r"http://(?:localhost|127\.0\.0\.1):517[3-9]", self.dev_origin) is None):
            raise ValueError("Explicit local development origin required")

    @property
    def header(self):
        return _DESKTOP_HEADER if self.mode == "desktop" else _DEV_HEADER

    @property
    def origins(self):
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
    if (b"access-control-request-method" in values or
            b"access-control-request-headers" in values):
        return Authorization(400)
    supplied = values.get(trust.header, "")
    if not compare_digest(supplied.encode("ascii"), trust.secret.encode("ascii")):
        return Authorization(401)
    return Authorization(200)
