"""B4 generated-data resource evidence, not an 8 GiB/native acceptance test."""
from __future__ import annotations

import hashlib
import json
from time import perf_counter

import pytest

from backend import artifact_publication, quality, quality_approvals, storage


def test_exact_csv_boundary_approval_memory_and_writer_intervals(tmp_path, monkeypatch):
    # Linux ru_maxrss is process peak RSS in KiB, cumulative (not allocation
    # attributable to a single function). This scoped CI suite runs separately.
    import sys
    if sys.platform != "linux":
        pytest.skip("The RSS measurement contract is Linux-specific")
    import resource

    home = tmp_path / "workspace"
    (home / "datasets").mkdir(parents=True)
    (home / "models").mkdir()
    monkeypatch.setattr(storage, "HOME", home)
    monkeypatch.setattr(storage, "DB_PATH", home / "pilotodin.sqlite3")
    storage.init()
    quality._init_tables()
    quality_approvals._init_tables()

    path = home / "datasets" / "boundary.csv"
    rows = 100_000
    columns = 60
    header = b"Region," + b",".join(f"m{i}".encode() for i in range(59)) + b"\n"
    numeric = b",".join([b"100000"] * 59) + b"\n"
    regular, trim = b"South," + numeric, b" North ," + numeric
    cap = artifact_publication.MAX_DATASET_BYTES
    assert cap == 40 * 1024 * 1024
    count, pad = divmod(cap - len(header) - rows * len(regular), len(trim) - len(regular))
    assert 0 < count < rows and pad in (0, 1)
    # Generate directly into a disposable file, not a giant Python list.
    with path.open("wb") as stream:
        stream.write(header)
        for row in (trim, regular):
            remaining = count if row == trim else rows - count - pad
            while remaining:
                batch = min(remaining, 1000)
                stream.write(row * batch)
                remaining -= batch
        if pad:
            stream.write(regular.replace(b"100000", b"0100000", 1))
    assert path.stat().st_size == cap
    with path.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    pid = storage.save_project("Generated boundary", path.name, ".csv", path,
                               {"rows": rows, "columns": columns}, original_sha256=digest)

    real_connect = storage.connect
    writer_intervals = []
    source_reads = []
    original_flags = []

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
                    # Includes commit/rollback and close, excludes time waiting
                    # to acquire BEGIN IMMEDIATE. An upper estimate of hold.
                    writer_intervals.append(perf_counter() - self.started)

    monkeypatch.setattr(storage, "connect", lambda: TimedConnection(real_connect()))
    real_read = quality._read_source
    def timed_read(*args, **kwargs):
        start = perf_counter()
        try:
            return real_read(*args, **kwargs)
        finally:
            source_reads.append({"capture": bool(kwargs.get("capture")),
                                 "seconds": round(perf_counter() - start, 6)})
    monkeypatch.setattr(quality, "_read_source", timed_read)

    real_snapshot = quality._snapshot_frame
    def observed_snapshot(*args, **kwargs):
        original_flags.append(kwargs.get("original", False))
        result = real_snapshot(*args, **kwargs)
        assert result[0] is None
        assert result[1].shape == (rows, columns)
        return result
    monkeypatch.setattr(quality, "_snapshot_frame", observed_snapshot)

    def peak_mib():
        return round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024, 2)

    def measure(operation, fn):
        prior_locks = len(writer_intervals)
        prior_reads = len(source_reads)
        start = perf_counter()
        result = fn()
        elapsed = perf_counter() - start
        locks = writer_intervals[prior_locks:]
        reads = source_reads[prior_reads:]
        assert len(locks) == 1
        assert [read["capture"] for read in reads] == [True, False]
        print("B4_RESOURCE " + json.dumps({
            "operation": operation, "bytes": cap, "rows": rows, "columns": columns,
            "cells": rows * columns, "elapsed_seconds": round(elapsed, 6),
            "writer_interval_seconds": round(locks[0], 6),
            "process_peak_rss_mib": peak_mib(), "source_reads": reads,
        }, sort_keys=True))
        return result

    print("B4_RESOURCE_BASELINE " + json.dumps({"process_peak_rss_mib": peak_mib()}))
    proposal = measure("preview", lambda: quality_approvals.prepare(
        pid, quality_approvals.ProposalRequest(operation="autopilot", expected_version=0)))
    assert proposal["changed_cells"] == count
    assert len(proposal["preview"]) == 12
    assert len(proposal["steps"]) == 1
    assert proposal["steps"][0]["proposal"] == {"kind": "trim_whitespace", "column": "Region"}
    committed = measure("commit", lambda: quality_approvals.commit(
        pid, quality_approvals.ApprovalCommit(proposal_id=proposal["proposal_id"],
                                             proposal_hash=proposal["proposal_hash"])))
    assert committed["version"] == 1
    assert committed["count"] == 1
    assert committed["applied"][0]["affected_rows"] == count
    assert original_flags == [False, False]
    with path.open("rb") as stream:
        assert hashlib.file_digest(stream, "sha256").hexdigest() == digest
    with real_connect() as con:
        assert con.execute("SELECT consumed_at FROM quality_approval_receipts WHERE proposal_id=?",
                           (proposal["proposal_id"],)).fetchone()[0]
    frame, version = quality.current_data(pid)
    assert version == 1 and frame.shape == (rows, columns)
    assert int((frame["Region"] == "North").sum()) == count
    assert int(frame["Region"].str.startswith(" ").sum()) == 0
