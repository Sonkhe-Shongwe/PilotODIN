"""Owned export transfer coordinator.

Released means the server completed its ASGI body and released its scratch;
it does not certify browser receipt, user Save As or destination persistence.
Filesystem checks are observed identity checks under the existing writer
lease, not atomic confinement against a hostile OS process.
"""
from __future__ import annotations

import hashlib
import logging
import os
import sqlite3

import anyio
from starlette.responses import JSONResponse, Response, StreamingResponse

try:
    from . import data_exports as exports, export_publication as ledger, quality, storage
except ImportError:
    import data_exports as exports
    import export_publication as ledger
    import quality, storage

CHUNK = 256 * 1024
log = logging.getLogger(__name__)


class Transfer:
    def __init__(self):
        self.receipt = None
        self.path = None
        self.stream = None
        self.identity = None
        self.staged = None
        self.uncertain = False
        self.finished = False
        self.reason = "cancelled"

    def advance(self, state, **metadata):
        # A failed transaction return may hide a successful SQLite commit.
        # Never retry blindly or unlink if the durable outcome is uncertain.
        try:
            self.receipt = storage.advance_export_publication(self.receipt,state,**metadata)
        except ledger.VersionUnavailable:
            # The admission check precedes UPDATE. The finalizer still
            # requires an exact persisted receipt before removing scratch.
            self.reason = "validation_failed"
            raise
        except BaseException:
            self.uncertain = True
            raise

    def verify(self):
        current = os.fstat(self.stream.fileno())
        if (not exports._same_metadata(self.staged,current)
                or not exports._same_metadata(current,exports._identity(self.path,self.identity))):
            self.reason = "integrity_mismatch"
            raise quality.QualityError("Export payload changed; transfer refused",409)

    def prepare(self, pid, request):
        df, self.filename = exports._prepare_data(pid,request)
        self.count, self.version = len(df), request.version
        self.format = request.format
        self.receipt = storage.begin_export_publication(pid,request.version,request.format)
        self.path = exports._scratch_directory() / self.receipt.filename
        try:
            # No following a preexisting name and no reopening after writing.
            storage.check_write_path(self.path.parent,directory=True)
            try:
                self.path.lstat()
            except FileNotFoundError:
                pass
            else:
                raise FileExistsError("Export scratch collision")
            storage.check_write_path(self.path, absent=True)
            flags = os.O_RDWR | os.O_CREAT | os.O_EXCL | getattr(os,"O_BINARY",0) | getattr(os,"O_NOFOLLOW",0)
            fd = os.open(self.path,flags,0o600)
        except FileExistsError:
            self.reason = "collision"
            raise quality.QualityError("Export scratch collision; existing file preserved",409) from None
        except storage.WorkspaceBoundaryError:
            self.reason = "unsafe_identity"
            raise
        except OSError:
            self.reason = "storage_unavailable"
            raise
        try:
            self.stream = os.fdopen(fd,"w+b")
        except BaseException:
            os.close(fd)
            self.reason = "storage_unavailable"
            raise
        self.identity = os.fstat(self.stream.fileno())
        self.reason = "validation_failed"
        self.staged = exports._serialize(df,request.format,self.path,self.stream,self.identity)
        del df
        self.verify()
        self.stream.seek(0)
        digest = hashlib.sha256()
        remaining = self.staged.st_size
        while remaining:
            chunk = self.stream.read(min(CHUNK,remaining))
            if not chunk:
                self.reason = "integrity_mismatch"
                raise quality.QualityError("Export payload truncated",409)
            remaining -= len(chunk)
            digest.update(chunk)
        self.verify()
        self.advance("staged",expected_bytes=self.staged.st_size,sha256=digest.hexdigest())
        self.advance("ready")
        self.stream.seek(0)
        self.verify()
        self.advance("transferring")
        self.reason = "cancelled"

    async def chunks(self):
        digest = hashlib.sha256()
        remaining = self.receipt.expected_bytes
        while remaining:
            chunk = await anyio.to_thread.run_sync(self.read_chunk, min(CHUNK,remaining))
            if not chunk:
                self.reason = "integrity_mismatch"
                raise RuntimeError("Export stream truncated")
            remaining -= len(chunk)
            digest.update(chunk)
            # Check the complete digest before yielding the final bytes.
            if remaining == 0 and digest.hexdigest() != self.receipt.sha256:
                self.reason = "integrity_mismatch"
                raise RuntimeError("Export stream digest changed")
            yield chunk

    def read_chunk(self, size):
        self.verify()
        chunk = self.stream.read(size)
        self.verify()
        return chunk

    def finish(self, completed):
        if self.finished:
            return
        self.finished = True
        safe = False
        try:
            if self.receipt is None or self.uncertain:
                return
            try:
                with storage.connect() as con:
                    if ledger.read(con,self.receipt.operation_id) != self.receipt:
                        self.uncertain = True
                        return
            except Exception:
                self.uncertain = True
                log.warning("Export receipt lookup failed; scratch preserved")
                return
            if self.identity is not None:
                try:
                    if self.staged is not None:
                        self.verify()
                    else:
                        exports._identity(self.path,self.identity)
                    safe = True
                except Exception:
                    self.reason = "unsafe_identity"
                    log.warning("Export cleanup identity unavailable; scratch preserved")
        finally:
            if self.stream is not None:
                try:
                    self.stream.close()
                except Exception:
                    # Never unlink or certify release when close is unconfirmed.
                    safe = False
                    self.reason = "storage_unavailable"
                    log.warning("Export handle close failed; scratch preserved")
        if self.receipt is None or self.uncertain:
            return
        try:
            if safe:
                # Closing the handle first is required on Windows. Revalidate
                # exact identity and byte metadata immediately before unlink.
                observed = exports._identity(self.path,self.identity)
                if self.staged is not None and not exports._same_metadata(self.staged,observed):
                    raise quality.QualityError("Export scratch metadata changed",409)
                storage.guarded_unlink(self.path,expected=self.identity)
            if completed and safe and self.receipt.state == "transferring":
                self.advance("released")
            else:
                blocked = (not safe and self.identity is not None) or self.reason in (
                    "collision","unsafe_identity","integrity_mismatch","storage_unavailable")
                self.advance("blocked" if blocked else "interrupted",
                             reason=self.reason if self.reason in ledger.REASONS else "interrupted_before_release")
        except Exception:
            log.warning("Export cleanup or receipt settlement failed; no release certified")
            if not self.uncertain:
                try:
                    self.advance("blocked",reason="storage_unavailable")
                except Exception:
                    log.warning("Export receipt settlement uncertain")


class _Body(StreamingResponse):
    """Track only completed ASGI body handoff, not generator exhaustion."""
    completed = False

    async def stream_response(self, send):
        await super().stream_response(send)
        self.completed = True


class ExportResponse(Response):
    """No scratch exists until ASGI calls this response; shield its finalizer."""
    def __init__(self, pid, request):
        super().__init__()
        self.pid, self.request = pid, request

    async def __call__(self, scope, receive, send):
        transfer = Transfer()
        body = None
        try:
            try:
                # Do not abandon a worker that owns a file or SQLite transaction.
                with anyio.CancelScope(shield=True):
                    await anyio.to_thread.run_sync(transfer.prepare,self.pid,self.request)
            except quality.QualityError as exc:
                await JSONResponse({"detail":str(exc)},status_code=exc.status)(scope,receive,send)
                return
            except ledger.PublicationError:
                await JSONResponse({"detail":"Export receipt or version unavailable; retry after review"},
                                   status_code=409)(scope,receive,send)
                return
            except (OSError, sqlite3.Error, storage.WorkspaceBoundaryError):
                transfer.reason = "storage_unavailable" if transfer.reason != "unsafe_identity" else transfer.reason
                await JSONResponse({"detail":"Export storage unavailable; original preserved"},
                                   status_code=503)(scope,receive,send)
                return
            body = _Body(transfer.chunks(),
                         media_type="text/csv" if transfer.format=="csv" else
                         "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                         headers={"Content-Disposition":f'attachment; filename="{transfer.filename}"',
                                  "Content-Length":str(transfer.receipt.expected_bytes),
                                  "X-PilotODIN-Export-SHA256":transfer.receipt.sha256,
                                  "X-PilotODIN-Dataset-Version":str(transfer.version),
                                  "X-PilotODIN-Exported-Rows":str(transfer.count),
                                  "Cache-Control":"no-store","X-Content-Type-Options":"nosniff"})
            await body(scope,receive,send)
        finally:
            with anyio.CancelScope(shield=True):
                await anyio.to_thread.run_sync(transfer.finish, bool(body and body.completed))
