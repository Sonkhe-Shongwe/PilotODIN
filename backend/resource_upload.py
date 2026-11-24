"""Staged C1 bounded multipart upload adapter; not registered in main.py.

Call only after trusted route matching, session and workspace checks. The
consumer must finish its work before returning a Response, must not retain the
UploadFile, and must preserve existing dataset publication protections.
"""
from contextlib import asynccontextmanager
import re

from python_multipart.exceptions import MultipartParseError
from python_multipart.multipart import parse_options_header
from starlette.datastructures import UploadFile
from starlette.formparsers import MultiPartException, MultiPartParser
from starlette.requests import ClientDisconnect, Request
from starlette.responses import JSONResponse

try:
    from .resource_http import OwnedHTTP
    from .resource_routes import ROUTES
except ImportError:
    from resource_http import OwnedHTTP
    from resource_routes import ROUTES


FILE_LIMIT = 40 * 1024 * 1024
ENVELOPE_LIMIT = FILE_LIMIT + 1024 * 1024


class UploadRefusal(Exception):
    def __init__(self, status, message):
        super().__init__(message)
        self.status = status


def _headers(request):
    lengths = request.headers.getlist("content-length")
    if len(lengths) > 1 or (lengths and not re.fullmatch(r"[0-9]{1,10}", lengths[0])):
        raise UploadRefusal(400, "Invalid upload length")
    declared = int(lengths[0]) if lengths else None
    if declared is not None and declared > ENVELOPE_LIMIT:
        raise UploadRefusal(413, "Upload exceeds multipart envelope limit")
    types = request.headers.getlist("content-type")
    if len(types) != 1:
        raise UploadRefusal(400, "Expected one multipart content type")
    try:
        media, options = parse_options_header(types[0])
    except (ValueError, TypeError, UnicodeError):
        raise UploadRefusal(400, "Invalid multipart content type") from None
    boundary = options.get(b"boundary", b"")
    if (media.lower() != b"multipart/form-data" or not 1 <= len(boundary) <= 70
            or not all(32 <= b <= 126 for b in boundary) or boundary.endswith(b" ")):
        raise UploadRefusal(400, "Invalid multipart boundary")
    return declared, boundary


async def _bounded_stream(request, declared, boundary):
    seen = 0
    closing = b"\r\n--" + boundary + b"--"
    tail_size = len(closing) + 2
    tail = b""
    async for chunk in request.stream():
        seen += len(chunk)
        if seen > ENVELOPE_LIMIT:
            raise UploadRefusal(413, "Upload exceeds multipart envelope limit")
        if declared is not None and seen > declared:
            raise UploadRefusal(400, "Upload length mismatch")
        # Keep only a tiny trailing suffix; never make a second full-body copy.
        tail = (tail + chunk[-tail_size:])[-tail_size:]
        yield chunk
    if declared is not None and seen != declared:
        raise UploadRefusal(400, "Upload length mismatch")
    # python-multipart finalize behavior is version-sensitive; require the
    # browser-compatible terminal delimiter, even if parser accepts truncation.
    if not (tail.endswith(closing) or tail.endswith(closing + b"\r\n")):
        raise UploadRefusal(400, "Incomplete multipart upload")


def _close_owned(spools):
    failure = None
    for spool in spools:
        try:
            if not spool.closed:
                spool.close()
            if not spool.closed:
                raise RuntimeError("Upload spool close unconfirmed")
        except Exception as exc:
            failure = exc
    if failure is not None:
        raise RuntimeError("Upload spool cleanup unconfirmed") from failure


@asynccontextmanager
async def bounded_upload(request):
    """Own parser spools even for overflow, disconnect and unexpected unwind."""
    declared, boundary = _headers(request)
    parser = MultiPartParser(request.headers, _bounded_stream(request, declared, boundary),
                             max_files=1, max_fields=0)
    # Reviewed version-sensitive seam, deliberately guarded and tested against
    # the resolved Starlette implementation. No parsing if unavailable.
    spools = getattr(parser, "_files_to_close_on_error", None)
    if not isinstance(spools, list) or spools:
        raise RuntimeError("Unsupported multipart spool ownership contract")
    try:
        try:
            form = await parser.parse()
        except (MultiPartException, MultipartParseError):
            raise UploadRefusal(400, "Invalid multipart upload") from None
        except ClientDisconnect:
            raise UploadRefusal(400, "Upload interrupted") from None
        parts = form.multi_items()
        if (len(parts) != 1 or parts[0][0] != "file"
                or not isinstance(parts[0][1], UploadFile)):
            raise UploadRefusal(400, "Exactly one file part is required")
        file = parts[0][1]
        if not any(spool is file.file for spool in spools):
            # Fail closed if a framework change drops the ownership inventory.
            await file.close()
            raise RuntimeError("Multipart spool ownership unconfirmed")
        if type(file.size) is not int or file.size < 0:
            raise RuntimeError("Multipart file size unconfirmed")
        if file.size > FILE_LIMIT:
            raise UploadRefusal(413, "File exceeds local 40 MB limit")
        if file.size == 0:
            raise UploadRefusal(400, "Empty file")
        yield file
    finally:
        # Synchronous close avoids an awaited cancellation point during cleanup.
        # Escaping cancellation still blocks the outer lease conservatively.
        _close_owned(spools)


class OwnedUpload(OwnedHTTP):
    """Acquire DATA before any body read; release after consumer and cleanup."""
    _lifetimes = ("upload",)

    def __init__(self, consumer, coordinator):
        async def downstream(scope, receive, send):
            request = Request(scope, receive=receive)
            try:
                async with bounded_upload(request) as file:
                    response = await consumer(file)
            except UploadRefusal as exc:
                response = JSONResponse({"detail": str(exc)}, status_code=exc.status)
            await response(scope, receive, send)

        super().__init__(downstream, coordinator, ROUTES["POST", "/api/projects"])
