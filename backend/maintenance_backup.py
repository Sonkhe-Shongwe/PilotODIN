"""B3 offline maintenance: stage a consistent SQLite snapshot, never activate it.

No application entrypoint, automatic migration, backup certification or
artifact inventory is provided by this first component. A staged database
alone is NOT a complete PilotODIN backup. Only cooperating workspace writers
are excluded by the shared lease; filesystem checks are not a sandbox.
"""
from __future__ import annotations

from contextlib import closing
from dataclasses import dataclass
import hashlib
import os
from pathlib import Path
import sqlite3
import time

try:
    from .workspace_boundary import (
        existing_fixture_home, existing_fixture_file,
        existing_maintenance_workspace, pinned_existing_directory,
        WorkspaceBoundaryError,
    )
except ImportError:
    from workspace_boundary import (
        existing_fixture_home, existing_fixture_file,
        existing_maintenance_workspace, pinned_existing_directory,
        WorkspaceBoundaryError,
    )


class SnapshotBlocked(RuntimeError):
    """Fixed-category maintenance refusal; a stage is never auto-deleted."""


@dataclass(frozen=True)
class StagedDatabase:
    size: int
    sha256: str


_DB = "pilotodin.sqlite3"
_CHUNK = 1024 * 1024


def _same(a, b):
    return (os.path.samestat(a, b) and a.st_size == b.st_size
            and a.st_mtime_ns == b.st_mtime_ns and a.st_ctime_ns == b.st_ctime_ns)


def _fingerprint(path, verify, checkpoint):
    verify()
    initial = existing_fixture_file(path)
    digest = hashlib.sha256()
    count = 0
    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
    with os.fdopen(os.open(path, flags), "rb") as stream:
        if not _same(initial, os.fstat(stream.fileno())):
            raise SnapshotBlocked("Snapshot input identity changed")
        while True:
            checkpoint()
            block = stream.read(_CHUNK)
            if not block:
                break
            count += len(block)
            if count > initial.st_size:
                raise SnapshotBlocked("Snapshot input size changed")
            digest.update(block)
        if not _same(initial, os.fstat(stream.fileno())):
            raise SnapshotBlocked("Snapshot input changed")
    if count != initial.st_size or not _same(initial, existing_fixture_file(path)):
        raise SnapshotBlocked("Snapshot input changed")
    verify()
    return StagedDatabase(count, digest.hexdigest())


def _absent(path):
    try:
        path.lstat()
    except FileNotFoundError:
        return True
    return False


def _source_files(home):
    """Refuse possible hot rollback recovery and avoid creating WAL sidecars.

    SQLite read-only WAL access can still use an existing shared-memory file.
    Require both sidecars already present for WAL-header databases; do not
    use immutable=1 (which could miss committed WAL data).
    """
    database = home / _DB
    info = existing_fixture_file(database)
    with database.open("rb") as stream:
        header = stream.read(100)
        if not _same(info, os.fstat(stream.fileno())):
            raise SnapshotBlocked("Database header identity changed")
    if len(header) != 100 or header[:16] != b"SQLite format 3\x00":
        raise SnapshotBlocked("Invalid source database header")
    if not _absent(home / (_DB + "-journal")):
        raise SnapshotBlocked("Source rollback journal requires independent review")
    wal, shm = home / (_DB + "-wal"), home / (_DB + "-shm")
    if header[18:20] == b"\x02\x02":
        if _absent(wal) or _absent(shm):
            raise SnapshotBlocked("Read-only WAL snapshot requires existing WAL and SHM")
        existing_fixture_file(wal)
        existing_fixture_file(shm)
        return (database, wal)
    if header[18:20] != b"\x01\x01" or not _absent(wal) or not _absent(shm):
        raise SnapshotBlocked("Unexpected source journal configuration")
    return (database,)


def stage_database_snapshot(home: Path, destination: Path, *, confirmed=False):
    """Create one fresh, isolated stage with a verified standalone database.

    The caller must explicitly confirm a new absolute destination outside
    the source. No CLI/API or automatic invocation is wired. Failure retains
    any stage bytes for review, never promotes or replaces a destination.
    """
    if confirmed is not True:
        raise SnapshotBlocked("Explicit snapshot destination confirmation required")
    deadline = time.monotonic() + 120.0

    def checkpoint():
        if time.monotonic() > deadline:
            raise SnapshotBlocked("Database snapshot time budget exceeded")

    try:
        destination = Path(destination)
        if not destination.is_absolute() or ".." in destination.parts or not destination.name:
            raise SnapshotBlocked("Choose a fresh absolute stage destination")
        parent = existing_fixture_home(str(destination.parent))
        if os.name == "nt" and (":" in destination.name or destination.name.endswith((" ", "."))):
            raise SnapshotBlocked("Invalid stage directory name")
        destination = parent / destination.name
        with existing_maintenance_workspace(str(home)) as (source, verify_source):
            if destination.is_relative_to(source) or source.is_relative_to(destination):
                raise SnapshotBlocked("Stage must be outside the source workspace")
            with pinned_existing_directory(parent) as verify_parent:
                if not _absent(destination):
                    raise SnapshotBlocked("Snapshot destination already exists")
                inputs = _source_files(source)
                fingerprints = tuple(_fingerprint(p, verify_source, checkpoint) for p in inputs)
                verify_source()
                verify_parent()
                destination.mkdir(exist_ok=False)
                stage_id = destination.lstat()
                with pinned_existing_directory(destination, expected=stage_id) as verify_stage:
                    def verify():
                        checkpoint()
                        verify_source()
                        verify_parent()
                        verify_stage()

                    verify()
                    db = destination / _DB
                    with db.open("xb") as stream:
                        identity = os.fstat(stream.fileno())
                    if not os.path.samestat(identity, existing_fixture_file(db)):
                        raise SnapshotBlocked("Staged database identity changed")
                    with closing(sqlite3.connect((source / _DB).as_uri() + "?mode=ro",
                                                 uri=True, timeout=2)) as original:
                        original.execute("PRAGMA query_only=ON")
                        with closing(sqlite3.connect(db.as_uri() + "?mode=rw",
                                                     uri=True, timeout=2)) as staged:
                            def progress(status, remaining, total):
                                verify()

                            original.backup(staged, pages=128, progress=progress, sleep=0.05)
                            verify()
                            # WAL source snapshots must become standalone DBs,
                            # without copying source journal or SHM files.
                            if staged.execute("PRAGMA journal_mode=DELETE").fetchone()[0] != "delete":
                                raise SnapshotBlocked("Cannot make snapshot standalone")
                            staged.set_progress_handler(lambda: int(time.monotonic() > deadline), 1000)
                            if staged.execute("PRAGMA integrity_check").fetchone() != ("ok",):
                                raise SnapshotBlocked("Database integrity check failed")
                            if staged.execute("PRAGMA foreign_key_check").fetchone() is not None:
                                raise SnapshotBlocked("Database foreign-key violations; migration review required")
                    verify()
                    if not os.path.samestat(identity, existing_fixture_file(db)):
                        raise SnapshotBlocked("Staged database identity changed")
                    with db.open("r+b") as stream:
                        if not os.path.samestat(identity, os.fstat(stream.fileno())):
                            raise SnapshotBlocked("Staged database identity changed")
                        os.fsync(stream.fileno())
                    if set(p.name for p in destination.iterdir()) != {_DB}:
                        raise SnapshotBlocked("Unexpected staged database sidecars or files")
                    receipt = _fingerprint(db, verify, checkpoint)
                    if _source_files(source) != inputs or tuple(
                        _fingerprint(p, verify_source, checkpoint) for p in inputs
                    ) != fingerprints:
                        raise SnapshotBlocked("Source database or WAL changed during snapshot")
                    verify()
                    return receipt
    except SnapshotBlocked:
        raise
    except (OSError, sqlite3.Error, WorkspaceBoundaryError) as exc:
        raise SnapshotBlocked("Database snapshot unavailable or unsafe; any stage retained") from exc
