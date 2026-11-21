"""P1 original-source relink: owner data must never be used by these fixtures."""
from __future__ import annotations
import hashlib
from pathlib import Path
import sqlite3

import pytest

from tools import p1_relink_original_source as relocation


DATA = b"CustomerID,Revenue\n0001,120\n0002,240\n"
ID = "a" * 32


def workspace(tmp_path):
    repo = tmp_path / "project-repo"
    home = repo / ".pilotodin-dev-data"
    (home / "datasets").mkdir(parents=True)
    (home / "models").mkdir()
    (home / "models" / "marker.txt").write_text("keep this")
    original = home / "datasets" / "synthetic.csv"
    original.write_bytes(DATA)
    old = str(tmp_path / "old-checkout" / ".pilotodin-dev-data" / "datasets" / original.name)
    db = home / "pilotodin.sqlite3"
    with sqlite3.connect(db) as con:
        con.executescript("""
            CREATE TABLE projects (id TEXT PRIMARY KEY, name TEXT, dataset_path TEXT);
            CREATE TABLE quality_state (project_id TEXT PRIMARY KEY, original_sha256 TEXT, current_version INTEGER);
            CREATE TABLE quality_versions (project_id TEXT, version INTEGER, operations_json TEXT,
                PRIMARY KEY (project_id, version));
            CREATE TABLE quality_actions (id TEXT, project_id TEXT, params_json TEXT);
            CREATE TABLE quality_decisions (project_id TEXT, issue_id TEXT, status TEXT);
        """)
        con.execute("INSERT INTO projects VALUES (?,?,?)", (ID, "day", old))
        con.execute("INSERT INTO quality_state VALUES (?,?,?)",
                    (ID, hashlib.sha256(DATA).hexdigest(), 2))
        con.execute("INSERT INTO quality_versions VALUES (?,?,?)",
                    (ID, 2, '["kept-action"]'))
        con.execute("INSERT INTO quality_actions VALUES (?,?,?)",
                    ("kept-action", ID, '{"kind":"reviewed"}'))
        con.execute("INSERT INTO quality_decisions VALUES (?,?,?)",
                    (ID, "kept-issue", "approved"))
    return repo, home, db, old, original


def rows(db):
    with sqlite3.connect(db) as con:
        return {
            table: con.execute(f"SELECT * FROM {table}").fetchall()
            for table in ("projects", "quality_state", "quality_versions",
                          "quality_actions", "quality_decisions")
        }


def test_inspect_is_read_only_and_confirms_exact_original(tmp_path):
    _, home, db, old, original = workspace(tmp_path)
    before = rows(db)
    plan = relocation.inspect(home, "day")
    assert plan.project_id == ID
    assert plan.old_path == old
    assert plan.candidate == original.resolve()
    assert plan.quality_version == 2
    assert rows(db) == before


def test_backup_first_relinks_only_path_and_preserves_history(tmp_path, monkeypatch):
    repo, home, db, old, original = workspace(tmp_path)
    plan = relocation.inspect(home, "day")
    before = rows(db)
    backup = tmp_path / "owner-backup-new"
    monkeypatch.setattr(relocation, "_check_backend_stopped", lambda: None)
    relocation.apply(home, plan, backup, ID, repo)
    after = rows(db)
    assert after["projects"] == [(ID, "day", str(original.resolve()))]
    for table in ("quality_state", "quality_versions",
                  "quality_actions", "quality_decisions"):
        assert after[table] == before[table]
    assert original.read_bytes() == DATA
    assert (backup / "datasets" / "synthetic.csv").read_bytes() == DATA
    assert (backup / "models" / "marker.txt").read_text() == "keep this"
    assert rows(backup / "pilotodin.sqlite3") == before
    with pytest.raises(relocation.RecoveryBlocked, match="already reachable"):
        relocation.inspect(home, "day")


def test_requires_confirmation_and_keeps_db_unmodified(tmp_path, monkeypatch):
    repo, home, db, _, _ = workspace(tmp_path)
    before = rows(db)
    monkeypatch.setattr(relocation, "_check_backend_stopped", lambda: None)
    with pytest.raises(relocation.RecoveryBlocked, match="confirmation"):
        relocation.apply(home, relocation.inspect(home, "day"),
                         tmp_path / "backup", "wrong-id", repo)
    assert rows(db) == before
    assert not (tmp_path / "backup").exists()


def test_hash_mismatch_blocks_without_backup_or_update(tmp_path, monkeypatch):
    repo, home, db, _, original = workspace(tmp_path)
    original.write_bytes(b"modified data")
    before = rows(db)
    with pytest.raises(relocation.RecoveryBlocked, match="differs"):
        relocation.inspect(home, "day")
    assert rows(db) == before


def test_missing_or_symlink_candidate_blocks(tmp_path):
    _, home, db, _, original = workspace(tmp_path)
    original.unlink()
    with pytest.raises(relocation.RecoveryBlocked, match="missing"):
        relocation.inspect(home, "day")


def test_backup_inside_project_refused(tmp_path, monkeypatch):
    repo, home, db, _, _ = workspace(tmp_path)
    monkeypatch.setattr(relocation, "_check_backend_stopped", lambda: None)
    with pytest.raises(relocation.RecoveryBlocked, match="outside"):
        relocation.apply(home, relocation.inspect(home, "day"),
                         repo / "backup", ID, repo)


def test_backend_listener_refuses_relink(tmp_path, monkeypatch):
    repo, home, db, _, _ = workspace(tmp_path)
    def blocked():
        raise relocation.RecoveryBlocked("Port 8000 is in use")
    monkeypatch.setattr(relocation, "_check_backend_stopped", blocked)
    with pytest.raises(relocation.RecoveryBlocked, match="in use"):
        relocation.apply(home, relocation.inspect(home, "day"),
                         tmp_path / "backup", ID, repo)
    assert not (tmp_path / "backup").exists()


def test_missing_quality_version_blocks(tmp_path):
    _, home, db, _, _ = workspace(tmp_path)
    with sqlite3.connect(db) as con:
        con.execute("DELETE FROM quality_versions")
    with pytest.raises(relocation.RecoveryBlocked, match="version"):
        relocation.inspect(home, "day")


def test_windows_absolute_saved_reference_resolves_only_verified_candidate(tmp_path, monkeypatch):
    repo, home, db, _, original = workspace(tmp_path)
    legacy = r"C:\older\PilotODIN\.pilotodin-dev-data\datasets\synthetic.csv"
    with sqlite3.connect(db) as con:
        con.execute("UPDATE projects SET dataset_path=? WHERE id=?", (legacy, ID))
    plan = relocation.inspect(home, "day")
    assert plan.old_path == legacy
    assert plan.candidate == original.resolve()
    monkeypatch.setattr(relocation, "_check_backend_stopped", lambda: None)
    backup = tmp_path / "complete-backup"
    relocation.apply(home, plan, backup, ID, repo)
    assert rows(db)["projects"] == [(ID, "day", str(original.resolve()))]
    assert rows(backup / "pilotodin.sqlite3")["projects"] == [(ID, "day", legacy)]
    assert original.read_bytes() == DATA


def test_mismatch_after_inspection_blocks_without_touching_anything(tmp_path, monkeypatch):
    repo, home, db, _, original = workspace(tmp_path)
    plan = relocation.inspect(home, "day")
    before = rows(db)
    original.write_bytes(b"changed after owner inspected")
    monkeypatch.setattr(relocation, "_check_backend_stopped", lambda: None)
    with pytest.raises(relocation.RecoveryBlocked, match="fingerprint"):
        relocation.apply(home, plan, tmp_path / "backup", ID, repo)
    assert rows(db) == before
    assert not (tmp_path / "backup").exists()


def test_closed_port_timeout_windows_only_accepts_confirmed_native_no_listener(monkeypatch):
    """Win localhost can time out without a listener. Require native proof."""
    from types import SimpleNamespace

    def timeout(*_args, **_kwargs):
        raise TimeoutError("Synthetic Windows TCP timeout")

    monkeypatch.setattr(relocation.socket, "create_connection", timeout)
    monkeypatch.setattr(relocation.sys, "platform", "win32")

    commands = []
    def run(args, **kwargs):
        commands.append((args, kwargs))
        return SimpleNamespace(returncode=0, stdout="P1_NO_LISTENER\n", stderr="")

    monkeypatch.setattr(relocation.subprocess, "run", run)
    relocation._check_backend_stopped()
    assert len(commands) == 1
    assert commands[0][0][:3] == ["powershell.exe", "-NoProfile", "-NonInteractive"]
    assert "Get-NetTCPConnection -State Listen" in commands[0][0][-1]
    assert commands[0][1]["timeout"] == 15


@pytest.mark.parametrize(
    "returncode,stdout,expected",
    [
        (0, "P1_LISTENER_PRESENT\n", "listener"),
        (25, "", "check failed"),
        (0, "", "Unexpected"),
        (0, "P1_NO_LISTENER\nUNTRUSTED OUTPUT\n", "Unexpected"),
        (0, "something else", "Unexpected"),
    ],
)
def test_windows_listener_check_fails_closed_for_busy_or_ambiguous_state(
    monkeypatch, returncode, stdout, expected
):
    from types import SimpleNamespace

    monkeypatch.setattr(
        relocation.subprocess, "run",
        lambda *_a, **_k: SimpleNamespace(returncode=returncode, stdout=stdout),
    )
    with pytest.raises(relocation.RecoveryBlocked, match=expected):
        relocation._check_windows_listening_port()


def test_windows_listener_check_fails_closed_if_powershell_errors(monkeypatch):
    def cannot_run(*_args, **_kwargs):
        raise FileNotFoundError("Synthetic PowerShell unavailable")
    monkeypatch.setattr(relocation.subprocess, "run", cannot_run)
    with pytest.raises(relocation.RecoveryBlocked, match="independently verify"):
        relocation._check_windows_listening_port()


def test_non_windows_socket_timeout_stays_blocked(monkeypatch):
    def timeout(*_args, **_kwargs):
        raise TimeoutError("Synthetic socket timeout")
    monkeypatch.setattr(relocation.socket, "create_connection", timeout)
    monkeypatch.setattr(relocation.sys, "platform", "linux")
    with pytest.raises(relocation.RecoveryBlocked, match="Cannot verify"):
        relocation._check_backend_stopped()


def test_any_established_tcp_connection_blocks_relink(monkeypatch):
    class DummyConnection:
        closed = False
        def close(self):
            self.closed = True
    connection = DummyConnection()
    monkeypatch.setattr(
        relocation.socket, "create_connection", lambda *_a, **_k: connection
    )
    with pytest.raises(relocation.RecoveryBlocked, match="Port 8000 is in use"):
        relocation._check_backend_stopped()
    assert connection.closed
