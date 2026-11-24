"""B3 offline maintenance: stage SQLite and referenced payloads, never activate.

No application entrypoint, automatic migration, restore or final certification.
Only cooperating workspace writers are excluded by the shared lease;
filesystem checks are not a sandbox. Unknown files and secrets are not copied.
"""
from __future__ import annotations

from contextlib import closing
from dataclasses import dataclass
import hashlib
import json
import re
import os
from pathlib import Path
import sqlite3
import time

try:
    from . import artifact_publication, model_publication
    from .workspace_boundary import (
        existing_fixture_home, existing_fixture_file,
        existing_maintenance_workspace, pinned_existing_directory,
        WorkspaceBoundaryError,
    )
except ImportError:
    import artifact_publication
    import model_publication
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
_MAX_RECORDS = 10000
_MAX_FILES = 60000
_MAX_MANIFEST_BYTES = 16 * 1024 * 1024
_ID = re.compile(r"[a-f0-9]{32}\Z")
_SHA = re.compile(r"[a-f0-9]{64}\Z")
_DATASET_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,180}\.(?:csv|xlsx)\Z", re.IGNORECASE)
_RESERVED = {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)), *(f"LPT{i}" for i in range(1, 10))}


def _same(a, b):
    return (os.path.samestat(a, b) and a.st_size == b.st_size
            and a.st_mtime_ns == b.st_mtime_ns and a.st_ctime_ns == b.st_ctime_ns)


def _fingerprint(path, verify, checkpoint, *, output=None, expected_size=None):
    verify()
    initial = existing_fixture_file(path)
    if not initial.st_ino or (expected_size is not None and initial.st_size != expected_size):
        raise SnapshotBlocked("Snapshot input size or identity mismatch")
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
            if output is not None and output.write(block) != len(block):
                raise SnapshotBlocked("Incomplete backup payload write")
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
    return _stage(home, destination, confirmed=confirmed, include_payloads=False)


def stage_workspace_backup(home: Path, destination: Path, *, confirmed=False):
    """Stage database plus recorded payloads; not a restore or certification."""
    return _stage(home, destination, confirmed=confirmed, include_payloads=True)


def _stage(home, destination, *, confirmed, include_payloads):
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
                    manifest = None
                    if include_payloads:
                        manifest = _stage_payloads(source, destination, receipt, verify, checkpoint)
                    if _source_files(source) != inputs or tuple(
                        _fingerprint(p, verify_source, checkpoint) for p in inputs
                    ) != fingerprints:
                        raise SnapshotBlocked("Source database or WAL changed during snapshot")
                    verify()
                    if manifest is not None:
                        # Last staged record, not a certification marker. A
                        # later restore must independently verify every byte.
                        raw = json.dumps(manifest, sort_keys=True, separators=(",", ":"),
                                         ensure_ascii=True, allow_nan=False).encode("ascii")
                        if len(raw) > _MAX_MANIFEST_BYTES:
                            raise SnapshotBlocked("Backup manifest limit exceeded")
                        with (destination / "manifest.json").open("xb") as output:
                            if output.write(raw) != len(raw):
                                raise SnapshotBlocked("Incomplete backup manifest")
                            output.flush()
                            os.fsync(output.fileno())
                        verify()
                        return manifest
                    return receipt
    except SnapshotBlocked:
        raise
    except (OSError, sqlite3.Error, WorkspaceBoundaryError, artifact_publication.PublicationError,
            ValueError, TypeError, KeyError) as exc:
        raise SnapshotBlocked("Database snapshot unavailable or unsafe; any stage retained") from exc


def _bounded_rows(con, sql, args=()):
    rows = con.execute(sql + " LIMIT ?", (*args, _MAX_RECORDS + 1)).fetchall()
    if len(rows) > _MAX_RECORDS:
        raise SnapshotBlocked("Backup catalogue limit exceeded")
    return rows


def _inventory(con, source, verify, checkpoint):
    """Derive exact paths from authoritative records, never from a tree scan."""
    plan = {}
    projects = {}
    folded = set()

    def add(relative, sha, size, limit):
        key = relative.as_posix()
        if key.casefold() in folded or len(plan) >= _MAX_FILES:
            raise SnapshotBlocked("Backup payload collision or inventory limit")
        path = source / relative
        verify()
        info = existing_fixture_file(path)
        if not info.st_ino or not 1 <= info.st_size <= limit or (size is not None and size != info.st_size):
            raise SnapshotBlocked("Referenced payload size mismatch")
        plan[key] = (StagedDatabase(info.st_size, sha), info)
        folded.add(key.casefold())

    for row in _bounded_rows(con, "SELECT p.id,p.dataset_path,p.file_ext,q.original_sha256,q.current_version "
                                  "FROM projects p LEFT JOIN quality_state q ON p.id=q.project_id ORDER BY p.id"):
        checkpoint()
        pid, stored, suffix, digest, version = row
        if not isinstance(pid, str) or not _ID.fullmatch(pid) or not isinstance(digest, str) or not _SHA.fullmatch(digest):
            raise SnapshotBlocked("Missing or invalid original provenance")
        if type(version) is not int or version < 0:
            raise SnapshotBlocked("Missing Quality version")
        for v in {0, version}:
            if con.execute("SELECT 1 FROM quality_versions WHERE project_id=? AND version=?", (pid, v)).fetchone() is None:
                raise SnapshotBlocked("Missing Quality history")
        path = Path(stored)
        if (not path.is_absolute() or path.parent != source / "datasets"
                or not _DATASET_NAME.fullmatch(path.name)
                or path.name.split(".")[0].upper() in _RESERVED
                or suffix not in (".csv", ".xlsx") or path.suffix.lower() != suffix):
            raise SnapshotBlocked("Recorded dataset is outside the admitted source layout")
        rows = con.execute("SELECT operation_id FROM artifact_publications_v1 WHERE subject_id=?", (pid,)).fetchall()
        expected_size = None
        if rows:
            if len(rows) != 1:
                raise SnapshotBlocked("Ambiguous dataset publication receipt")
            receipt = artifact_publication.read(con, rows[0][0])
            if receipt.state != "committed" or receipt.sha256 != digest or receipt.suffix != suffix:
                raise SnapshotBlocked("Dataset publication provenance mismatch")
            expected_size = receipt.expected_bytes
        add(Path("datasets") / path.name, digest, expected_size, artifact_publication.MAX_DATASET_BYTES)
        projects[pid] = digest

    if con.execute("SELECT 1 FROM artifact_publications_v1 a LEFT JOIN projects p ON a.subject_id=p.id "
                   "WHERE a.state='committed' AND p.id IS NULL LIMIT 1").fetchone():
        raise SnapshotBlocked("Committed dataset has no catalogue reference")
    if con.execute("SELECT 1 FROM artifact_publications_v1 WHERE state IN ('intent','staged','publishing') LIMIT 1").fetchone():
        raise SnapshotBlocked("Unsettled dataset publication; recovery required")

    for eid, pid, status, config_raw, results_raw in _bounded_rows(
        con, "SELECT id,project_id,status,config,results FROM experiments ORDER BY id"
    ):
        checkpoint()
        if not isinstance(eid, str) or not _ID.fullmatch(eid) or pid not in projects:
            raise SnapshotBlocked("Invalid experiment reference")
        receipt = model_publication.read(con, eid)
        if status in ("queued", "running") or (receipt is not None and receipt.state in ("intent","staged","publishing")):
            raise SnapshotBlocked("Unsettled experiment; recovery required")
        if status != "completed":
            if receipt is not None and receipt.state == "committed":
                raise SnapshotBlocked("Committed model has no completed experiment")
            continue
        if receipt is None or receipt.state != "committed":
            raise SnapshotBlocked("Legacy or unverified completed model; backup certification blocked")
        config, results = json.loads(config_raw), json.loads(results_raw)
        receipt.verify_binding(pid, config, projects[pid], results)
        if con.execute("SELECT 1 FROM quality_versions WHERE project_id=? AND version=?",
                       (pid, receipt.quality_version)).fetchone() is None:
            raise SnapshotBlocked("Model Quality version missing")
        directory = source / "models" / eid
        with pinned_existing_directory(directory) as verify_dir:
            verify()
            verify_dir()
            expected = set(receipt.files)
            # At most six names are expected; fail immediately on extras.
            observed = set()
            with os.scandir(directory) as entries:
                for entry in entries:
                    if entry.name not in expected:
                        raise SnapshotBlocked("Unexpected model directory entry")
                    observed.add(entry.name)
            if observed != expected:
                raise SnapshotBlocked("Missing model directory entry")
            for name, item in receipt.files.items():
                add(Path("models") / eid / name, item["sha256"], item["size"], model_publication.MAX_FILE_BYTES)
            verify_dir()
    if con.execute("SELECT 1 FROM model_publications_v1 m LEFT JOIN experiments e ON m.experiment_id=e.id "
                   "WHERE m.state='committed' AND e.id IS NULL LIMIT 1").fetchone():
        raise SnapshotBlocked("Committed model has no experiment")
    return plan


def _stage_payloads(source, destination, database_receipt, verify, checkpoint):
    with closing(sqlite3.connect((destination / _DB).as_uri() + "?mode=ro", uri=True)) as con:
        con.execute("PRAGMA query_only=ON")
        plan = _inventory(con, source, verify, checkpoint)
    records = {_DB: {"size": database_receipt.size, "sha256": database_receipt.sha256}}
    # All destinations derive from admitted names and are exclusive.
    directories = {}
    for key, (expected, source_identity) in sorted(plan.items()):
        relative = Path(key)
        path = source / relative
        target = destination / relative
        verify()
        for parent in reversed(relative.parents):
            if parent == Path("."):
                continue
            directory = destination / parent
            if directory not in directories:
                # Validate the original parent identity BEFORE creating any
                # child, not only when opening the subsequent payload file.
                with pinned_existing_directory(directory.parent,
                                               expected=directories.get(directory.parent)) as verify_parent:
                    verify()
                    verify_parent()
                    directory.mkdir(exist_ok=False)
                    directory_identity = directory.lstat()
                    with pinned_existing_directory(directory, expected=directory_identity) as verify_created:
                        verify_parent()
                        verify_created()
                        verify()
                    directories[directory] = directory_identity
            else:
                with pinned_existing_directory(directory, expected=directories[directory]) as verify_existing:
                    verify()
                    verify_existing()
        with pinned_existing_directory(path.parent) as verify_input:
            with pinned_existing_directory(target.parent, expected=directories[target.parent]) as verify_output:
                def verify_copy():
                    verify()
                    verify_input()
                    verify_output()
                verify_copy()
                if not _same(source_identity, existing_fixture_file(path)):
                    raise SnapshotBlocked("Referenced payload changed after inventory")
                with target.open("xb") as output:
                    target_id = os.fstat(output.fileno())
                    copied = _fingerprint(path, verify_copy, checkpoint, output=output, expected_size=expected.size)
                    output.flush()
                    os.fsync(output.fileno())
                if (copied != expected or not os.path.samestat(target_id, existing_fixture_file(target))
                        or _fingerprint(target, verify_copy, checkpoint, expected_size=expected.size) != expected):
                    raise SnapshotBlocked("Referenced payload digest mismatch")
                records[key] = {"size": expected.size, "sha256": expected.sha256}
    # Recheck authoritative inventory and source bytes before publishing the
    # staged manifest; no new reference is silently ignored.
    with closing(sqlite3.connect((destination / _DB).as_uri() + "?mode=ro", uri=True)) as con:
        final_plan = _inventory(con, source, verify, checkpoint)
    if set(final_plan) != set(plan):
        raise SnapshotBlocked("Backup inventory changed")
    for key, (expected, identity) in plan.items():
        current, current_identity = final_plan[key]
        if current != expected or not _same(identity, current_identity):
            raise SnapshotBlocked("Referenced payload changed")
        if _fingerprint(source / key, verify, checkpoint, expected_size=expected.size) != expected:
            raise SnapshotBlocked("Referenced payload digest mismatch")
        if _fingerprint(destination / key, verify, checkpoint, expected_size=expected.size) != expected:
            raise SnapshotBlocked("Staged payload digest mismatch")
    if _fingerprint(destination / _DB, verify, checkpoint) != database_receipt:
        raise SnapshotBlocked("Staged database changed")
    return {"schema_version": 1, "scope": "recorded_project_payloads",
            "files": records}
