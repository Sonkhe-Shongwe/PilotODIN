"""B1 upload coordinator: immutable bytes, exclusive writes, conservative recovery."""
from __future__ import annotations

from contextlib import closing
import hashlib
import logging
import os
from pathlib import Path
import stat

try:
    from . import artifact_publication as ledger, engine, storage
    from .workspace_boundary import pinned_existing_directory
except ImportError:
    import artifact_publication as ledger
    import engine
    import storage
    from workspace_boundary import pinned_existing_directory

_CHUNK = 1024 * 1024


class UnconfirmedPublication(RuntimeError):
    """The outcome or cleanup cannot safely be established."""


def _identity(path, expected=None):
    storage.check_write_path(path, expected=expected)
    info = path.lstat()
    if (not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or not info.st_ino
            or getattr(info, "st_file_attributes", 0) & 0x400
            or (expected is not None and not os.path.samestat(expected, info))):
        raise ledger.PublicationError("Unsafe publication file identity")
    return info


def _same_bytes_metadata(a, b):
    return (os.path.samestat(a, b) and a.st_size == b.st_size
            and a.st_mtime_ns == b.st_mtime_ns and a.st_ctime_ns == b.st_ctime_ns)


def _require_absent(path, verify_parent):
    """Distinguish a known name collision from an unsafe workspace."""
    verify_parent()
    storage.check_write_path(path.parent, directory=True)
    try:
        path.lstat()
    except FileNotFoundError:
        pass
    else:
        raise FileExistsError("Dataset publication destination already exists")
    try:
        storage.check_write_path(path, absent=True)
    except storage.WorkspaceBoundaryError:
        # A name may appear between lstat and the managed absence check.
        # Revalidate the parent before treating that rejection as a collision.
        verify_parent()
        storage.check_write_path(path.parent, directory=True)
        try:
            path.lstat()
        except FileNotFoundError:
            pass
        else:
            raise FileExistsError("Dataset publication destination already exists") from None
        raise


def _check_unreferenced(receipt, paths):
    with closing(storage.connect()) as con:
        if storage.publication_reference_conflict(con, receipt, paths):
            raise ledger.PublicationError("Publication reference conflict")


def _write_exclusive(path, raw, owned, verify_parent):
    _require_absent(path, verify_parent)
    with path.open("xb") as output:
        # Track only files opened by this operation; never a collision target.
        owned[path] = os.fstat(output.fileno())
        for offset in range(0, len(raw), _CHUNK):
            chunk = raw[offset:offset + _CHUNK]
            if output.write(chunk) != len(chunk):
                raise OSError("Incomplete dataset write")
        output.flush()
        os.fsync(output.fileno())
    verify_parent()
    _identity(path, owned[path])


def _verified_file(path, receipt, expected, verify_parent):
    verify_parent()
    before = _identity(path, expected)
    if before.st_size != receipt.expected_bytes:
        raise ledger.PublicationError("Dataset publication size mismatch")
    digest = hashlib.sha256()
    count = 0
    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
    with os.fdopen(os.open(path, flags), "rb") as source:
        opened = os.fstat(source.fileno())
        if not _same_bytes_metadata(before, opened):
            raise ledger.PublicationError("Dataset publication identity changed")
        while True:
            chunk = source.read(_CHUNK)
            if not chunk:
                break
            count += len(chunk)
            if count > receipt.expected_bytes:
                raise ledger.PublicationError("Dataset publication size mismatch")
            digest.update(chunk)
        if not _same_bytes_metadata(opened, os.fstat(source.fileno())):
            raise ledger.PublicationError("Dataset publication bytes changed")
    after = _identity(path, before)
    verify_parent()
    if (not _same_bytes_metadata(before, after) or count != receipt.expected_bytes
            or digest.hexdigest() != receipt.sha256):
        raise ledger.PublicationError("Dataset publication digest mismatch")
    return after


def _sync_parent(parent, verify_parent):
    verify_parent()
    if os.name == "posix":
        fd = os.open(parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
                     | getattr(os, "O_NOFOLLOW", 0))
        try:
            if not os.path.samestat(os.fstat(fd), parent.lstat()):
                raise ledger.PublicationError("Dataset directory identity changed")
            os.fsync(fd)
        finally:
            os.close(fd)
    verify_parent()


def _cleanup_owned(con, receipt, owned, paths, verify_parent, *, committed=False):
    for path in paths:
        if path not in owned:
            continue
        verify_parent()
        _identity(path, owned[path])
        if storage.publication_reference_conflict(con, receipt, (path,), allow_subject=committed):
            raise ledger.PublicationError("Publication reference conflict")
        storage.guarded_unlink(path, expected=owned[path])
        verify_parent()


def _committed_metadata(con, receipt, final):
    row = con.execute("SELECT dataset_path,file_ext FROM projects WHERE id=?",
                      (receipt.subject_id,)).fetchone()
    state = con.execute("SELECT original_sha256,current_version FROM quality_state WHERE project_id=?",
                        (receipt.subject_id,)).fetchone()
    version = con.execute("SELECT operations_json,event FROM quality_versions WHERE project_id=? AND version=0",
                          (receipt.subject_id,)).fetchone()
    return (row is not None and tuple(row) == (str(final), receipt.suffix)
            and state is not None and tuple(state) == (receipt.sha256, 0)
            and version is not None and tuple(version) == ("[]", "original"))


def _settle_failure(receipt, final, staging, owned, verify_parent, error):
    """Read fresh authoritative state; do not delete when the outcome is unclear."""
    try:
        with storage.connect() as con:
            ledger.begin_durable(con)
            current = ledger.read(con, receipt.operation_id)
            if current is None or (current.subject_id, current.sha256, current.suffix,
                                   current.expected_bytes) != (receipt.subject_id, receipt.sha256,
                                                               receipt.suffix, receipt.expected_bytes):
                raise UnconfirmedPublication("Publication receipt cannot be confirmed")
            if current.state == "committed":
                if not _committed_metadata(con, current, final):
                    raise UnconfirmedPublication("Committed metadata cannot be confirmed")
                # No file deletion before verifying the committed source.
                return current
            if current.state not in ledger.NONTERMINAL:
                raise UnconfirmedPublication("Publication state cannot be confirmed")
            if storage.publication_reference_conflict(con, current, (final, staging)):
                ledger.advance(con, current, "blocked", reason="reference_conflict")
                return None
            # Missing Quality schema is a known rollback, not a committed import.
            _cleanup_owned(con, current, owned, (final, staging), verify_parent)
            if isinstance(error, FileExistsError):
                reason = "collision"
            elif isinstance(error, storage.WorkspaceBoundaryError):
                reason = "unsafe_identity"
            elif isinstance(error, OSError):
                reason = "storage_unavailable"
            else:
                reason = "validation_failed"
            ledger.advance(con, current, "interrupted", reason=reason)
            return None
    except Exception as exc:
        raise UnconfirmedPublication("Import outcome or cleanup could not be confirmed") from exc


def publish(filename: str, suffix: str, raw: bytes):
    digest = hashlib.sha256(raw).hexdigest()
    try:
        receipt = storage.begin_dataset_publication(suffix, len(raw), digest)
    except Exception as exc:
        # Intent commit is itself potentially ambiguous; no payload created.
        raise UnconfirmedPublication("Import intent could not be confirmed") from exc
    parent = storage.HOME / "datasets"
    final = parent / receipt.final_name
    staging = parent / receipt.staging_name
    owned = {}
    profile = None
    try:
        with pinned_existing_directory(parent) as verify_parent:
            try:
                _require_absent(final, verify_parent)
                _require_absent(staging, verify_parent)
                _check_unreferenced(receipt, (final, staging))
                _write_exclusive(staging, raw, owned, verify_parent)
                _verified_file(staging, receipt, owned[staging], verify_parent)
                # The original immutable upload bytes have the same size and
                # SHA-256 as verified staging. No parser reopens its filename.
                frame = engine.read_data(raw, suffix)
                profile = engine.profile(frame, filename)
                del frame
                receipt = storage.advance_dataset_publication(receipt, "staged")
                receipt = storage.advance_dataset_publication(receipt, "publishing")
                _check_unreferenced(receipt, (final, staging))
                _write_exclusive(final, raw, owned, verify_parent)
                verified = _verified_file(final, receipt, owned[final], verify_parent)
                _sync_parent(parent, verify_parent)

                def verify_final():
                    verify_parent()
                    if not _same_bytes_metadata(verified, _identity(final, verified)):
                        raise ledger.PublicationError("Verified final dataset changed")

                receipt = storage.commit_dataset_publication(
                    receipt, filename, profile, verify_final=verify_final)
            except Exception as error:
                committed = _settle_failure(receipt, final, staging, owned, verify_parent, error)
                if committed is None:
                    raise
                receipt = committed
                if profile is None or final not in owned:
                    raise UnconfirmedPublication("Committed import response cannot be confirmed")
                try:
                    _verified_file(final, receipt, owned[final], verify_parent)
                except Exception as exc:
                    raise UnconfirmedPublication("Committed source cannot be confirmed") from exc
            # Success is not converted to failure merely because staging remains.
            try:
                with storage.connect() as con:
                    ledger.begin_durable(con)
                    if ledger.read(con, receipt.operation_id) != receipt:
                        raise ledger.PublicationError("Committed receipt changed")
                    # The subject's own final reference is expected, but any
                    # reference to the staging path still blocks cleanup.
                    _cleanup_owned(con, receipt, owned, (staging,), verify_parent, committed=True)
            except Exception:
                logging.warning("Dataset publication staging cleanup deferred")
            return receipt.subject_id, profile
    except storage.WorkspaceBoundaryError as exc:
        raise UnconfirmedPublication("Dataset publication directory unavailable") from exc


def recover_pending():
    """Startup-only classification. Never promote, move or delete payload files."""
    # Do not inspect unrelated payload directories if there is no pending work.
    with closing(storage.connect()) as con:
        if not ledger.pending_page(con, limit=1):
            return 0
    count = 0
    cursor = ""
    parent = storage.HOME / "datasets"
    with pinned_existing_directory(parent) as verify_parent:
        while True:
            with storage.connect() as con:
                ledger.begin_durable(con)
                page = ledger.pending_page(con, after=cursor)
                if not page:
                    return count
                if count + len(page) > 4096:
                    raise ledger.PublicationError("Publication recovery limit reached")
                for receipt in page:
                    verify_parent()
                    paths = (parent / receipt.final_name, parent / receipt.staging_name)
                    reason = None
                    try:
                        for path in paths:
                            try:
                                _identity(path)
                            except FileNotFoundError:
                                pass
                            except storage.WorkspaceBoundaryError:
                                # Managed preflight wraps missing files; distinguish
                                # absent name without accepting a redirected entry.
                                try:
                                    path.lstat()
                                except FileNotFoundError:
                                    verify_parent()
                                else:
                                    raise
                        if storage.publication_reference_conflict(con, receipt, paths):
                            reason = "reference_conflict"
                    except (OSError, RuntimeError):
                        reason = "unsafe_identity"
                    ledger.advance(con, receipt, "blocked" if reason else "interrupted",
                                   reason=reason or "interrupted_before_commit")
                    cursor = receipt.operation_id
                    count += 1
