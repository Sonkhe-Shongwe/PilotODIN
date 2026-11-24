"""Generated-only B4 metadata admission, rollback and history preservation."""
import hashlib
import json
import sqlite3
from time import perf_counter

import pytest
from backend import quality, quality_approvals as approvals, storage


@pytest.fixture
def case(tmp_path, monkeypatch):
    home = tmp_path / "workspace"
    (home / "datasets").mkdir(parents=True)
    (home / "models").mkdir()
    monkeypatch.setattr(storage, "HOME", home)
    monkeypatch.setattr(storage, "DB_PATH", home / "pilotodin.sqlite3")
    storage.init()
    quality._init_tables()
    approvals._init_tables()
    raw = b"Region,Revenue\nNorth,1\n North ,2\n" + b"".join(
        f"South,{i}\n".encode() for i in range(3, 21))
    path = home / "datasets" / "source.csv"
    path.write_bytes(raw)
    pid = storage.save_project("Generated", path.name, ".csv", path, {},
                               original_sha256=hashlib.sha256(raw).hexdigest())
    return pid, path, raw


def review(pid):
    return approvals.prepare(pid, approvals.ProposalRequest(operation="autopilot", expected_version=0))


def commit(pid, receipt):
    return approvals.commit(pid, approvals.ApprovalCommit(proposal_id=receipt["proposal_id"],
                                                          proposal_hash=receipt["proposal_hash"]))


def counts(pid):
    with storage.connect() as con:
        return tuple(con.execute(f"SELECT COUNT(*) FROM {table} WHERE project_id=?", (pid,)).fetchone()[0]
                     for table in ("quality_versions", "quality_actions", "quality_decisions"))


def test_exact_row_boundary_and_rollback(case, monkeypatch):
    pid, path, raw = case
    receipt = review(pid)
    monkeypatch.setattr(quality, "MAX_HISTORY_ROWS", 1)
    with pytest.raises(quality.QualityError, match="metadata safety budget") as exc:
        commit(pid, receipt)
    assert exc.value.status == 409
    assert counts(pid) == (1, 0, 0)
    assert quality.current_version(pid) == 0
    with storage.connect() as con:
        assert con.execute("SELECT consumed_at FROM quality_approval_receipts WHERE proposal_id=?",
                           (receipt["proposal_id"],)).fetchone()[0] is None
    monkeypatch.setattr(quality, "MAX_HISTORY_ROWS", 2)
    assert commit(pid, receipt)["version"] == 1
    assert counts(pid) == (2, 1, 1)
    assert len(quality.history(pid)["versions"]) == 2
    assert quality.data_at_version(pid, 0)["Region"].iloc[1] == " North "
    assert quality.current_data(pid)[0]["Region"].iloc[1] == "North"
    assert path.read_bytes() == raw


def test_legacy_over_budget_decisions_refused_before_parse(case, monkeypatch):
    pid, path, raw = case
    with storage.connect() as con:
        con.executemany("INSERT INTO quality_decisions VALUES(?,?,?,?)",
                        [(pid, str(i), "rejected", storage.now()) for i in range(3)])
    monkeypatch.setattr(quality, "MAX_HISTORY_ROWS", 2)
    monkeypatch.setattr(quality, "_source_df", lambda *a, **k: pytest.fail("parsed oversized metadata"))
    with pytest.raises(quality.QualityError, match="metadata safety budget"):
        quality.snapshot(pid)
    with pytest.raises(quality.QualityError, match="metadata safety budget"):
        quality.history(pid)
    assert counts(pid) == (1, 0, 3)
    assert path.read_bytes() == raw


def test_oversized_receipt_is_refused_without_consumption(case, monkeypatch):
    pid, path, raw = case
    receipt = review(pid)
    with storage.connect() as con:
        con.execute("UPDATE quality_approval_receipts SET payload_json=? WHERE proposal_id=?",
                    ("x" * 100000, receipt["proposal_id"]))
    monkeypatch.setattr(quality, "MAX_REPLAY_METADATA_BYTES", 4096)
    with pytest.raises(quality.QualityError, match="metadata safety budget"):
        commit(pid, receipt)
    assert counts(pid) == (1, 0, 0)
    with storage.connect() as con:
        assert con.execute("SELECT consumed_at FROM quality_approval_receipts WHERE proposal_id=?",
                           (receipt["proposal_id"],)).fetchone()[0] is None
    assert path.read_bytes() == raw


def test_operation_list_overflow_rolls_back(case, monkeypatch):
    pid, path, raw = case
    receipt = review(pid)
    monkeypatch.setattr(quality, "MAX_ACTIVE_ACTIONS", 0)
    with pytest.raises(quality.QualityError, match="metadata safety budget"):
        commit(pid, receipt)
    assert counts(pid) == (1, 0, 0)
    assert path.read_bytes() == raw


def test_aggregate_bytes_and_sqlite_limit_restoration(case):
    pid, _, _ = case
    with storage.connect() as con:
        con.executemany("INSERT INTO quality_decisions VALUES(?,?,?,?)",
                        [(pid, str(i) * 200, "rejected", storage.now()) for i in range(3)])
        old = con.getlimit(sqlite3.SQLITE_LIMIT_LENGTH)
        sql = "SELECT * FROM quality_decisions WHERE project_id=? ORDER BY issue_id"
        rows = quality._bounded_rows(con, sql, (pid,))
        total = sum(quality._row_bytes(row) for row in rows)
        assert len(quality._bounded_rows(con, sql, (pid,), max_bytes=total)) == 3
        with pytest.raises(quality.QualityError, match="metadata safety budget"):
            quality._bounded_rows(con, sql, (pid,), max_bytes=total-1)
        assert con.getlimit(sqlite3.SQLITE_LIMIT_LENGTH) == old
        assert con.execute("SELECT 1").fetchone()[0] == 1


def test_metadata_heavy_history_measurement(case):
    import sys
    if sys.platform != "linux":
        pytest.skip("RSS units are Linux-specific")
    import resource
    pid, path, raw = case
    count = quality.MAX_HISTORY_ROWS
    with storage.connect() as con:
        con.executemany("INSERT INTO quality_decisions VALUES(?,?,?,?)",
                        [(pid, f"{i:024x}", "rejected", storage.now()) for i in range(count)])
    start = perf_counter()
    history = quality.history(pid)
    elapsed = perf_counter() - start
    assert len(history["decisions"]) == count
    assert counts(pid) == (1, 0, count)
    print("B4_METADATA " + json.dumps({"decisions": count, "history_seconds": elapsed,
          "process_peak_rss_mib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024}))
    assert path.read_bytes() == raw

def test_receipt_exact_payload_cap_not_row_allowance(case, monkeypatch):
    pid, _, _ = case
    receipt = review(pid)
    request = approvals.ApprovalCommit(proposal_id=receipt["proposal_id"],
                                      proposal_hash=receipt["proposal_hash"])
    with storage.connect() as con:
        size = len(con.execute("SELECT payload_json FROM quality_approval_receipts WHERE proposal_id=?",
                               (receipt["proposal_id"],)).fetchone()[0].encode("utf-8"))
        monkeypatch.setattr(quality, "MAX_REPLAY_METADATA_BYTES", size)
        assert approvals._receipt_for_commit(con, pid, request)[1]["operation"] == "autopilot"
        monkeypatch.setattr(quality, "MAX_REPLAY_METADATA_BYTES", size-1)
        with pytest.raises(quality.QualityError, match="metadata safety budget"):
            approvals._receipt_for_commit(con, pid, request)
    assert counts(pid) == (1, 0, 0)


def test_read_only_historical_replay_survives_unrelated_metadata_overflow(case, monkeypatch):
    pid, path, raw = case
    assert commit(pid, review(pid))["version"] == 1
    with storage.connect() as con:
        con.executemany("INSERT INTO quality_decisions VALUES(?,?,?,?)",
                        [(pid, f"{i:024x}", "rejected", storage.now()) for i in range(3)])
    monkeypatch.setattr(quality, "MAX_HISTORY_ROWS", 2)
    with pytest.raises(quality.QualityError, match="metadata safety budget"):
        quality.current_data(pid)
    assert quality.data_at_version(pid, 0)["Region"].iloc[1] == " North "
    assert quality.data_at_version(pid, 1)["Region"].iloc[1] == "North"
    metadata = quality._read_metadata(pid, target_version=1, historical_read=True)
    with storage.connect() as con:
        con.execute("BEGIN IMMEDIATE")
        with pytest.raises(RuntimeError, match="read-only"):
            quality._verify_staged_write(con, pid, metadata, None)
    assert path.read_bytes() == raw


def test_near_limit_history_approval_writer_intervals(case, monkeypatch):
    # Synthetic audit metadata, not a replay of 16,000 actual UI operations.
    # Both histories hit the configured row ceiling on the next real approval.
    pid, path, raw = case
    limit = quality.MAX_HISTORY_ROWS
    previous = limit - 2
    timestamp = storage.now()
    with storage.connect() as con:
        con.executemany("INSERT INTO quality_versions VALUES(?,?,?,?,?,?)",
                        ((pid, version, "[]", "restore",
                          json.dumps({"from_version": 0, "prior_version": version-1}), timestamp)
                         for version in range(1, previous+1)))
        con.execute("UPDATE quality_state SET current_version=? WHERE project_id=?", (previous, pid))
        con.executemany("INSERT INTO quality_decisions VALUES(?,?,?,?)",
                        ((pid, f"{i:024x}", "rejected", timestamp) for i in range(limit-1)))
    assert counts(pid) == (limit-1, 0, limit-1)
    real_connect = storage.connect
    intervals = []
    budget_times = []
    real_budget = quality._check_history_budget

    class TimedConnection:
        def __init__(self, connection):
            self.connection = connection
            self.started = None

        def __getattr__(self, name):
            return getattr(self.connection, name)

        def __enter__(self):
            self.connection.__enter__()
            return self

        def execute(self, sql, *args):
            cursor = self.connection.execute(sql, *args)
            if sql.strip().upper() == "BEGIN IMMEDIATE":
                assert self.started is None
                self.started = perf_counter()
            return cursor

        def __exit__(self, *args):
            try:
                return self.connection.__exit__(*args)
            finally:
                if self.started is not None:
                    intervals.append(perf_counter() - self.started)

    def timed_budget(*args):
        start = perf_counter()
        try:
            return real_budget(*args)
        finally:
            budget_times.append(perf_counter() - start)

    monkeypatch.setattr(storage, "connect", lambda: TimedConnection(real_connect()))
    monkeypatch.setattr(quality, "_check_history_budget", timed_budget)
    start = perf_counter()
    receipt = approvals.prepare(pid, approvals.ProposalRequest(operation="autopilot", expected_version=previous))
    preview_elapsed = perf_counter() - start
    assert len(intervals) == 1
    start = perf_counter()
    result = commit(pid, receipt)
    commit_elapsed = perf_counter() - start
    assert len(intervals) == 2 and len(budget_times) == 1
    assert result["version"] == limit-1 and result["count"] == 1
    assert counts(pid) == (limit, 1, limit)
    assert quality.current_data(pid)[0]["Region"].iloc[1] == "North"
    assert quality.data_at_version(pid, previous)["Region"].iloc[1] == " North "
    history = quality.history(pid)
    assert len(history["versions"]) == len(history["decisions"]) == limit
    assert path.read_bytes() == raw
    print("B4_HEAVY_MUTATION " + json.dumps({
        "versions": limit, "decisions": limit,
        "preview_seconds": preview_elapsed, "commit_seconds": commit_elapsed,
        "preview_writer_seconds": intervals[0], "commit_writer_seconds": intervals[1],
        "postwrite_budget_seconds": budget_times[0],
    }))
