"""CF-04: expensive Quality proposal work must not hold the SQLite writer lock.

Run against the exact current PilotODIN backend after applying the patch. Every
mutation in these tests belongs to a disposable tmp_path database.
"""
from __future__ import annotations

import hashlib
import sqlite3
from pathlib import Path

import pytest

from backend import quality, quality_approvals, storage


@pytest.fixture
def proposal_case(monkeypatch, tmp_path):
    home = tmp_path / "isolated-quality"
    (home / "datasets").mkdir(parents=True)
    (home / "models").mkdir()
    monkeypatch.setattr(storage, "HOME", home)
    monkeypatch.setattr(storage, "DB_PATH", home / "pilotodin.sqlite3")
    storage.init()
    quality._init_tables()
    quality_approvals._init_tables()
    lines = ["CustomerID,Region,Revenue"]
    for i in range(36):
        region = "Gauteng" if i < 18 else " Gauteng " if i < 21 else "Mpumalanga"
        lines.append(f"{i:04d},{region},{i * 10 + 10}")
    original = ("\n".join(lines) + "\n").encode("utf-8")
    dataset = home / "datasets" / "generated.csv"
    dataset.write_bytes(original)
    pid = storage.save_project(
        "Disposable", "generated.csv", ".csv", dataset, {"rows": 36},
        original_sha256=hashlib.sha256(original).hexdigest(),
    )
    issue = next(item for item in quality.snapshot(pid)["issues"]
                 if item["kind"] == "whitespace" and item["proposal"])
    body = quality_approvals.ProposalRequest(
        operation="approve", expected_version=0, issue_id=issue["id"],
    )
    return pid, body, dataset, original


def _other_connection():
    return sqlite3.connect(storage.DB_PATH, timeout=0.2)


def _receipt_count():
    with storage.connect() as con:
        return con.execute("SELECT COUNT(*) FROM quality_approval_receipts").fetchone()[0]


def test_real_preview_releases_writer_lock_during_replay(monkeypatch, proposal_case):
    pid, body, dataset, original = proposal_case
    real_make = quality_approvals._make
    observed = []
    parsed = []
    real_reader = quality.engine.read_csv_with_identifiers

    def unlocked_reader(raw, identifier):
        assert isinstance(raw, bytes) and raw == original
        with _other_connection() as competing_writer:
            competing_writer.execute("BEGIN IMMEDIATE")
            parsed.append(True)
            competing_writer.execute("ROLLBACK")
        return real_reader(raw, identifier)

    monkeypatch.setattr(quality.engine, "read_csv_with_identifiers", unlocked_reader)

    def unlocked_make(con, project, request):
        assert not con.in_transaction, "Pandas work must happen before BEGIN IMMEDIATE"
        # BEGIN IMMEDIATE on this separate connection fails on the old code.
        with _other_connection() as competing_writer:
            competing_writer.execute("BEGIN IMMEDIATE")
            observed.append(True)
            competing_writer.execute("ROLLBACK")
        return real_make(con, project, request)

    monkeypatch.setattr(quality_approvals, "_make", unlocked_make)
    response = quality_approvals.prepare(pid, body)
    assert observed == [True]
    assert parsed == [True], "The actual typed CSV parser must run outside the writer lock"
    assert response["changed_cells"] >= 1
    assert _receipt_count() == 1
    assert quality.current_version(pid) == 0
    assert dataset.read_bytes() == original
    committed = quality_approvals.commit(pid, quality_approvals.ApprovalCommit(
        proposal_id=response["proposal_id"], proposal_hash=response["proposal_hash"]
    ))
    assert committed["version"] == 1
    assert dataset.read_bytes() == original


def test_version_change_during_preview_fails_without_receipt(monkeypatch, proposal_case):
    pid, body, _, _ = proposal_case
    real_make = quality_approvals._make

    def concurrently_advance_version(con, project, request):
        result = real_make(con, project, request)
        with _other_connection() as writer:
            writer.execute("BEGIN IMMEDIATE")
            writer.execute(
                "INSERT INTO quality_versions VALUES (?,?,?,?,?,?)",
                (pid, 1, "[]", "restore", "{}", storage.now()),
            )
            writer.execute("UPDATE quality_state SET current_version=1 WHERE project_id=?", (pid,))
        return result

    monkeypatch.setattr(quality_approvals, "_make", concurrently_advance_version)
    with pytest.raises(quality.QualityError) as exc:
        quality_approvals.prepare(pid, body)
    assert exc.value.status == 409
    assert _receipt_count() == 0
    assert quality.current_version(pid) == 1


def test_decision_change_without_version_change_fails(monkeypatch, proposal_case):
    pid, body, _, _ = proposal_case
    real_make = quality_approvals._make

    def concurrently_decide(con, project, request):
        result = real_make(con, project, request)
        with _other_connection() as writer:
            writer.execute("BEGIN IMMEDIATE")
            writer.execute(
                "INSERT INTO quality_decisions VALUES (?,?,?,?)",
                (pid, request.issue_id, "rejected", storage.now()),
            )
        return result

    monkeypatch.setattr(quality_approvals, "_make", concurrently_decide)
    with pytest.raises(quality.QualityError) as exc:
        quality_approvals.prepare(pid, body)
    assert exc.value.status == 409
    assert _receipt_count() == 0
    assert quality.current_version(pid) == 0


def test_archive_during_preview_rejects_receipt(monkeypatch, proposal_case):
    pid, body, _, _ = proposal_case
    real_make = quality_approvals._make

    def concurrently_archive(con, project, request):
        result = real_make(con, project, request)
        with _other_connection() as writer:
            writer.execute("BEGIN IMMEDIATE")
            writer.execute(
                "INSERT INTO project_lifecycle (project_id,revision,archived_at) "
                "VALUES (?,1,?) ON CONFLICT(project_id) DO UPDATE SET archived_at=excluded.archived_at",
                (pid, storage.now()),
            )
        return result

    monkeypatch.setattr(quality_approvals, "_make", concurrently_archive)
    with pytest.raises(quality.QualityError) as exc:
        quality_approvals.prepare(pid, body)
    assert exc.value.status == 409
    assert _receipt_count() == 0


def test_second_check_rejects_change_immediately_before_write_lock(monkeypatch, proposal_case):
    pid, body, _, _ = proposal_case
    real_state = quality_approvals._preview_state
    checks = []

    def state_and_race(con, project, request):
        state = real_state(con, project, request)
        checks.append(state)
        if len(checks) == 2:
            # Race after expensive work but before BEGIN IMMEDIATE.
            with _other_connection() as writer:
                writer.execute("BEGIN IMMEDIATE")
                writer.execute(
                    "INSERT INTO quality_decisions VALUES (?,?,?,?)",
                    (pid, request.issue_id, "rejected", storage.now()),
                )
        return state

    monkeypatch.setattr(quality_approvals, "_preview_state", state_and_race)
    with pytest.raises(quality.QualityError) as exc:
        quality_approvals.prepare(pid, body)
    assert exc.value.status == 409
    assert len(checks) == 3
    assert _receipt_count() == 0


def test_unverified_legacy_original_preserves_quality_recovery_error(proposal_case):
    pid, body, _, _ = proposal_case
    with storage.connect() as con:
        con.execute("DELETE FROM quality_state WHERE project_id=?", (pid,))
    with pytest.raises(quality.QualityError) as exc:
        quality_approvals.prepare(pid, body)
    assert exc.value.status == 409
    assert "checksum" in str(exc.value).lower()
    assert _receipt_count() == 0


def test_archived_stale_project_returns_archive_error_even_for_noop_preview(monkeypatch,proposal_case):
    pid, _body, dataset, original = proposal_case
    stale = quality._project(pid)
    normal_project = quality._project
    monkeypatch.setattr(quality, '_project',
                        lambda project_id: stale if project_id == pid else normal_project(project_id))
    with storage.connect() as con:
        con.execute(
            'INSERT INTO project_lifecycle (project_id,revision,archived_at) VALUES (?,1,?) '
            'ON CONFLICT(project_id) DO UPDATE SET archived_at=excluded.archived_at',
            (pid,storage.now()),
        )
    request = quality_approvals.ProposalRequest(
        operation='restore',expected_version=0,target_version=0,
    )
    with pytest.raises(quality.QualityError) as err:
        quality_approvals.prepare(pid,request)
    assert err.value.status == 409
    assert 'archived' in str(err.value).lower()
    assert _receipt_count() == 0
    assert dataset.read_bytes() == original
