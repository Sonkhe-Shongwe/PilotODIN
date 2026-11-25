"""Bounded, authenticated settings JSON before framework body parsing.

The shared app middleware is copied into the owned composition. Only the
three existing settings PUT paths are affected; no storage or provider work.
ASGI input limits are not claims about transport/kernel buffering.
"""
import asyncio
import re

from starlette.responses import JSONResponse

try:
    from .request_auth import request_authorized
    from .settings_storage import InvalidSettings, strict_object
except ImportError:
    from request_auth import request_authorized
    from settings_storage import InvalidSettings, strict_object


LIMITS = {
    "/api/resource/policy": 4 * 1024,
    "/api/ai/settings": 16 * 1024,
    "/api/ai/key": 8 * 1024,
}
BODY_TIMEOUT = 10.0
MAX_EMPTY_EVENTS = 32
_HEADER_NAMES = frozenset((b"content-type", b"content-length",
                           b"content-encoding", b"transfer-encoding"))
_JSON_TYPE = re.compile(rb'application/json(?:[ \t]*;[ \t]*charset[ \t]*=[ \t]*(?:utf-8|"utf-8"))?')


class _Refusal(Exception):
    def __init__(self, status):
        self.status = status


def _declared_length(scope, limit):
    headers = {}
    for name, value in scope.get("headers", ()):
        name = name.lower()
        if name not in _HEADER_NAMES:
            continue
        if name in headers or len(value) > 128:
            raise _Refusal(400)
        headers[name] = value
    if _JSON_TYPE.fullmatch(headers.get(b"content-type", b"").strip().lower()) is None:
        raise _Refusal(415)
    if headers.get(b"content-encoding", b"identity").strip().lower() != b"identity":
        raise _Refusal(415)
    transfer = headers.get(b"transfer-encoding")
    length = headers.get(b"content-length")
    if transfer is not None:
        if transfer.strip().lower() != b"chunked" or length is not None:
            raise _Refusal(400)
    if length is None:
        return None
    if re.fullmatch(rb"[0-9]{1,20}", length) is None:
        raise _Refusal(400)
    declared = int(length)
    if declared > limit:
        raise _Refusal(413)
    return declared


async def _collect(receive, limit, declared):
    body = bytearray()
    empty_events = 0
    async with asyncio.timeout(BODY_TIMEOUT):
        while True:
            event = await receive()
            if event.get("type") == "http.disconnect":
                return None
            if event.get("type") != "http.request":
                raise _Refusal(400)
            chunk = event.get("body", b"")
            more = event.get("more_body", False)
            if type(chunk) is not bytes or type(more) is not bool:
                raise _Refusal(400)
            if len(chunk) > limit - len(body):
                raise _Refusal(413)
            if declared is not None and len(chunk) > declared - len(body):
                raise _Refusal(400)
            if more and not chunk:
                empty_events += 1
                if empty_events > MAX_EMPTY_EVENTS:
                    raise _Refusal(400)
            body.extend(chunk)
            if not more:
                break
    if declared is not None and len(body) != declared:
        raise _Refusal(400)
    raw = bytes(body)
    strict_object(raw, limit)
    return raw


class SettingsRequestGuard:
    """Validate a small JSON envelope, then replay the exact admitted bytes."""
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        limit = LIMITS.get(scope.get("path")) if (
            scope.get("type") == "http" and scope.get("method") == "PUT"
        ) else None
        if limit is None:
            await self.app(scope, receive, send)
            return
        if not request_authorized(scope):
            await self._refuse(scope, receive, send, 401)
            return
        try:
            declared = _declared_length(scope, limit)
            raw = await _collect(receive, limit, declared)
        except _Refusal as exc:
            await self._refuse(scope, receive, send, exc.status)
            return
        except InvalidSettings:
            await self._refuse(scope, receive, send, 422)
            return
        except TimeoutError:
            await self._refuse(scope, receive, send, 408)
            return
        if raw is None:
            return  # disconnected before a complete request; no mutation
        replayed = False

        async def replay():
            nonlocal replayed
            if not replayed:
                replayed = True
                return {"type": "http.request", "body": raw, "more_body": False}
            return await receive()

        await self.app(scope, replay, send)

    @staticmethod
    async def _refuse(scope, receive, send, status):
        detail = {
            400: "Invalid settings request framing",
            401: "Local API request refused",
            408: "Settings request body timed out",
            413: "Settings request exceeds size limit",
            415: "Settings require UTF-8 JSON",
            422: "Invalid settings request",
        }[status]
        await JSONResponse({"detail": detail}, status_code=status,
                           headers={"Cache-Control": "no-store"})(scope, receive, send)
