"""Conservative one-project relink for relocated DEV-ONLY PilotODIN source files.

Default is READ ONLY. Application backend must be stopped before --apply.
Never use against installed-app data, and never invent replacement CSV bytes.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import os
from pathlib import Path, PureWindowsPath
import re
import shutil
import socket
import subprocess
import sqlite3
import sys

# CLI invocation by filename must resolve the same backend boundary module
# as the normal application, without importing storage or initializing SQLite.
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from backend.workspace_boundary import (
    LOCK_NAME, WorkspaceBoundaryError, existing_fixture_home,
    existing_fixture_file, existing_maintenance_workspace,
)


class RecoveryBlocked(RuntimeError):
    """A precondition failed; leave existing project and Quality history alone."""


@dataclass(frozen=True)
class Inspection:
    project_id: str
    old_path: str
    candidate: Path
    pinned_sha256: str
    quality_version: int


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _readonly_db(db: Path):
    # Do not let SQLite silently create a new project database.
    return sqlite3.connect(db.resolve().as_uri() + "?mode=ro", uri=True)


def inspect(home: Path, project_name: str) -> Inspection:
    """Check both metadata and candidate bytes, without opening the DB writable."""
    try:
        home = existing_fixture_home(str(home))
        db = home / "pilotodin.sqlite3"
        dataset_dir = home / "datasets"
        existing_fixture_file(db)
        existing_fixture_home(str(dataset_dir))
    except WorkspaceBoundaryError as exc:
        raise RecoveryBlocked("Isolated workspace database or datasets directory is missing/unsafe.") from exc
    with _readonly_db(db) as con:
        projects = con.execute(
            "SELECT id,dataset_path FROM projects WHERE name=?", (project_name,)
        ).fetchall()
        if len(projects) != 1:
            raise RecoveryBlocked("Expected exactly one named project; no change permitted.")
        project_id, old_path = projects[0]
        state = con.execute(
            "SELECT original_sha256,current_version FROM quality_state WHERE project_id=?",
            (project_id,),
        ).fetchone()
        if state is None:
            raise RecoveryBlocked("Pinned original Quality fingerprint is missing.")
        expected, version = state
        if not isinstance(expected, str) or not re.fullmatch(r"[0-9a-fA-F]{64}", expected):
            raise RecoveryBlocked("Pinned original Quality fingerprint is invalid.")
        version_row = con.execute(
            "SELECT 1 FROM quality_versions WHERE project_id=? AND version=?",
            (project_id, version),
        ).fetchone()
        if version_row is None:
            raise RecoveryBlocked("Current Quality history version is missing. Do not relink.")
    filename = PureWindowsPath(old_path).name
    if not filename or filename in (".", "..") or not filename.lower().endswith((".csv", ".xlsx")):
        raise RecoveryBlocked("Stored original source reference is invalid.")
    candidate = dataset_dir / filename
    try:
        existing_fixture_file(candidate)
    except WorkspaceBoundaryError as exc:
        raise RecoveryBlocked("Original candidate is missing or unsafe.") from exc
    if candidate.resolve().parent != dataset_dir.resolve():
        raise RecoveryBlocked("Candidate is not directly inside isolated datasets directory.")
    if Path(old_path).is_file():
        raise RecoveryBlocked("Recorded original source is already reachable; no relink required.")
    if _sha256(candidate).lower() != expected.lower():
        raise RecoveryBlocked("Candidate differs from immutable original fingerprint; no relink.")
    return Inspection(str(project_id), str(old_path), candidate.resolve(), expected.lower(), int(version))


def _check_windows_listening_port() -> None:
    """Windows-only secondary proof when loopback connect times out.

    A Windows firewall can timeout a connection to a *closed* localhost port
    instead of refusing it. Only a successful native TCP-table enumeration
    showing ZERO listeners may allow backup/relink. Fail closed on all errors.
    """
    script = (
        "$ErrorActionPreference='Stop';"
        "try {"
        " $listeners=@(Get-NetTCPConnection -State Listen -ErrorAction Stop"
        " | Where-Object { $_.LocalPort -eq 8000 });"
        " if ($listeners.Count -eq 0) { Write-Output 'P1_NO_LISTENER' }"
        " else { Write-Output 'P1_LISTENER_PRESENT' }"
        "} catch { exit 25 }"
    )
    try:
        result = subprocess.run(
            ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script],
            capture_output=True, text=True, check=False, timeout=15,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise RecoveryBlocked(
            "Cannot independently verify Windows port 8000 listener state."
        ) from exc
    if result.returncode != 0:
        raise RecoveryBlocked(
            "Windows listener check failed. No database changes were applied."
        )
    result_line = result.stdout.strip()
    if result_line == "P1_NO_LISTENER":
        return
    if result_line == "P1_LISTENER_PRESENT":
        raise RecoveryBlocked(
            "Windows reports a port 8000 listener. Stop the backend first."
        )
    raise RecoveryBlocked("Unexpected Windows listener-check output. No relink.")


def _check_backend_stopped() -> None:
    # Fail closed if port 8000 is occupied, even by a service other than PilotODIN.
    try:
        connection = socket.create_connection(("127.0.0.1", 8000), timeout=0.4)
    except ConnectionRefusedError:
        return
    except TimeoutError as exc:
        # Some Windows configurations silently drop closed-port TCP probes.
        # Only the operating system's own *successful* TCP listener listing
        # can resolve that ambiguity; never treat a timeout as no listener.
        if sys.platform == "win32":
            _check_windows_listening_port()
            return
        raise RecoveryBlocked(
            "Cannot verify that the local backend is stopped."
        ) from exc
    except OSError as exc:
        raise RecoveryBlocked("Cannot verify that the local backend is stopped.") from exc
    else:
        connection.close()
        raise RecoveryBlocked("Port 8000 is in use. Stop the development backend first.")


def _manifest(root: Path) -> dict[str, str]:
    """Verify every byte of the backup, not only the SQLite database."""
    entries: dict[str, str] = {}
    for directory, names, files in os.walk(root, followlinks=False):
        d = Path(directory)
        try:
            for name in names:
                existing_fixture_home(str(d / name))
            for name in files:
                file = d / name
                existing_fixture_file(file)
                # A persistent empty coordination marker is not project data.
                # Never copy its OS lock into a backup or treat it as proof.
                if d == root and name == LOCK_NAME:
                    continue
                entries[file.relative_to(root).as_posix()] = _sha256(file)
        except WorkspaceBoundaryError as exc:
            raise RecoveryBlocked("Workspace contains an unsafe entry; backup blocked.") from exc
    return entries


def apply(home: Path, plan: Inspection, backup_to: Path, confirm_id: str, repo_root: Path) -> None:
    """Backup everything, then atomically relink one metadata field only."""
    if confirm_id != plan.project_id:
        raise RecoveryBlocked("Explicit project ID confirmation does not match.")
    try:
        home = existing_fixture_home(str(home))
        repo_root = existing_fixture_home(str(repo_root))
        if not backup_to.is_absolute() or ".." in backup_to.parts:
            raise RecoveryBlocked("Choose a new absolute backup folder.")
        backup_to = existing_fixture_home(str(backup_to.parent)) / backup_to.name
    except WorkspaceBoundaryError as exc:
        raise RecoveryBlocked("Unsafe maintenance or backup location.") from exc
    if home != repo_root / ".pilotodin-dev-data":
        raise RecoveryBlocked("Only the isolated development workspace is supported.")
    if backup_to.exists() or backup_to.is_symlink():
        raise RecoveryBlocked("Choose a new backup folder under an existing parent directory.")
    if backup_to.is_relative_to(repo_root) or backup_to.is_relative_to(home):
        raise RecoveryBlocked("Backups must be outside the repository and workspace.")
    _check_backend_stopped()
    try:
        with existing_maintenance_workspace(str(home)) as owned:
            _apply_owned(owned, plan, backup_to)
    except WorkspaceBoundaryError as exc:
        raise RecoveryBlocked("Workspace ownership or physical admission refused.") from exc


def _apply_owned(home: Path, plan: Inspection, backup_to: Path) -> None:
    initial_manifest = _manifest(home)
    size = sum((home / key).stat().st_size for key in initial_manifest)
    if shutil.disk_usage(backup_to.parent).free < size + 64 * 1024 * 1024:
        raise RecoveryBlocked("Insufficient free space for full development-workspace backup.")
    db = home / "pilotodin.sqlite3"
    # Hold the write-reservation lock for a consistent snapshot and sole metadata update.
    con = sqlite3.connect(db, timeout=8, isolation_level=None)
    try:
        con.execute("BEGIN IMMEDIATE")
        if inspect(home, "day") != plan:
            raise RecoveryBlocked("Project identity, source or Quality state changed. Reinspect.")
        if _manifest(home) != initial_manifest:
            raise RecoveryBlocked("Workspace changed during preflight. No relink.")
        def ignore_coordination(directory, names):
            return {LOCK_NAME} if Path(directory) == home and LOCK_NAME in names else set()

        shutil.copytree(home, backup_to, ignore=ignore_coordination)
        if _manifest(backup_to) != initial_manifest:
            raise RecoveryBlocked("Full backup comparison failed. Metadata unchanged.")
        if _sha256(plan.candidate) != plan.pinned_sha256:
            raise RecoveryBlocked("Candidate source changed during backup.")
        updated = con.execute(
            "UPDATE projects SET dataset_path=? WHERE id=? AND dataset_path=?",
            (str(plan.candidate), plan.project_id, plan.old_path),
        )
        if updated.rowcount != 1:
            raise RecoveryBlocked("Recorded path changed concurrently; update cancelled.")
        stored = con.execute(
            "SELECT original_sha256,current_version FROM quality_state WHERE project_id=?",
            (plan.project_id,),
        ).fetchone()
        if stored != (plan.pinned_sha256, plan.quality_version):
            raise RecoveryBlocked("Quality pin/version changed. Update cancelled.")
        con.execute("COMMIT")
    except Exception:
        if con.in_transaction:
            con.execute("ROLLBACK")
        raise
    finally:
        con.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-name", required=True, help="Existing isolated project name")
    parser.add_argument("--apply", action="store_true", help="Owner authorises backed-up metadata relink")
    parser.add_argument("--backup-to", type=Path, help="New full backup directory OUTSIDE the repository")
    parser.add_argument("--confirm-id", help="Explicit original project ID confirmation for --apply")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    if Path.cwd().resolve() != root:
        parser.error("Run from the PilotODIN repository root, not another directory.")
    home = root / ".pilotodin-dev-data"
    try:
        plan = inspect(home, args.project_name)
        print("Saved original exists: False")
        print("Candidate under isolated datasets: True")
        print("Candidate matches pinned original: True")
        print("Quality version exists: True")
        print("Project ID for explicit approval:", plan.project_id)
        if not args.apply:
            print("READ ONLY: no backup or database modification performed.")
            return 0
        if args.project_name != "day":
            raise RecoveryBlocked("This P1 recovery increment is scoped to the day project only.")
        if args.backup_to is None or not args.confirm_id:
            raise RecoveryBlocked("--apply requires --backup-to and --confirm-id.")
        apply(home, plan, args.backup_to, args.confirm_id, root)
        print("BACKUP VERIFIED AND SINGLE SOURCE-PATH RELINK COMMITTED.")
        print("Original dataset, Quality version, approvals and transformations unchanged.")
        return 0
    except (RecoveryBlocked, OSError, sqlite3.Error) as exc:
        print(f"RECOVERY BLOCKED: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
