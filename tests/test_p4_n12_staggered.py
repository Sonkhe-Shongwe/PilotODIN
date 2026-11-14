"""Synthetic checks for the generated N12 staggered-write comparison."""
import io
import json
import os
import subprocess
import sys
from collections import defaultdict

import pytest

from qa.p4_research.n12_stack import analyze, capture, symbols


DEVICE = r"\Device\HarddiskVolume3"
PROTECTED = r"C:\qa\synthetic-protected"
DEVICES = {DEVICE.casefold(): "c:"}


def comparison_evidence():
    fixture = {"preopened": {"pid": 20}, "protected_root": PROTECTED,
               "start_ticks": 100, "rundown_start_ticks": 80_000_000}
    experiment = {"pid": 21, "tid": 22, "files": {}}
    names, rows = {}, []
    for label, parent, key in (("staggered-protected", PROTECTED, 30),
                               ("staggered-outside", r"C:\qa", 31)):
        path = parent + r"\staggered.bin"
        names[key] = {analyze.canonical_file_path(path, DEVICES)}
        writes = []
        for index, (offset, payload) in enumerate(capture.STAGGERED_PAYLOADS):
            ticks = key * 100 + index * 60_000_000
            writes.append({"offset": offset, "size": len(payload), "start": ticks - 10, "end": ticks + 10})
            irp = key * 10 + index
            rows.extend([
                {"ticks": ticks, "id": 16, "pid": 21, "lifecycle": False,
                 "data": {"Irp": irp, "FileKey": key, "FileObject": key + 100,
                          "IssuingThreadId": 22, "ByteOffset": offset, "IOSize": len(payload)}},
                {"ticks": ticks + 5, "id": 24, "pid": 0, "lifecycle": False,
                 "data": {"Irp": irp, "Status": 0}},
            ])
        experiment["files"][label] = {"path": path, "writes": writes}
    return fixture, experiment, names, rows


def verify(fixture, experiment, names, rows, occupied=None):
    rows.sort(key=lambda row: row["ticks"])
    by_irp = defaultdict(list)
    for row in rows:
        by_irp[row["data"]["Irp"]].append(row)
    return analyze.staggered_writes(fixture, experiment, rows, by_irp, names, DEVICES,
                                    set() if occupied is None else occupied)


def test_fixture_staggers_writes_and_verifies_distinct_payloads(tmp_path, monkeypatch, capsys):
    (tmp_path / "synthetic-protected").mkdir()
    pauses, checked = [], []
    monkeypatch.setattr(capture.time, "sleep", pauses.append)
    monkeypatch.setattr(capture.probe, "utc_ticks", iter(range(100, 108)).__next__)
    monkeypatch.setattr(capture.probe, "verify_handle_path", lambda stream, path: checked.append(path))
    monkeypatch.setattr(capture.sys, "stdin", io.TextIOWrapper(io.BytesIO()))
    capture.staggered_comparison(tmp_path)
    report = json.loads(capsys.readouterr().out)
    assert pauses == [5]
    assert len(checked) == 2
    for record, first_tick in zip(report["files"].values(), (100, 102)):
        first, second = record["writes"]
        assert (first["start"], second["start"]) == (first_tick, first_tick + 4)
        path = next(path for path in checked if str(path) == record["path"])
        content = path.read_bytes()
        assert content[:first["size"]] == b"A" * first["size"]
        assert content[first["size"]:second["offset"]] == bytes(second["offset"] - first["size"])
        assert content[second["offset"]:] == b"B" * second["size"]


def test_cli_refuses_staggered_writes_outside_the_hosted_runner(tmp_path):
    (tmp_path / "synthetic-protected").mkdir()
    env = {**os.environ, "GITHUB_ACTIONS": "false"}
    result = subprocess.run([sys.executable, "-B", capture.__file__, "staggered", str(tmp_path)],
                            env=env, capture_output=True, text=True, timeout=10, check=False)
    assert result.returncode != 0
    assert result.stderr.strip() == "The hosted stack capture could not complete."
    assert not list(tmp_path.rglob("*.bin"))


def test_two_exact_completed_writes_establish_each_file_identity():
    result = verify(*comparison_evidence())
    assert [file["identity"] for file in result.values()] == [(30, 130), (31, 131)]
    assert all(file["verified_write_count"] == 2 for file in result.values())


@pytest.mark.parametrize("change", ["failed", "wrong-thread", "wrong-offset", "different-object",
                                    "conflicting-name", "ambiguous", "occupied"])
def test_unproven_writes_cannot_establish_the_file_identity(change):
    fixture, experiment, names, rows = comparison_evidence()
    occupied = set()
    if change == "failed":
        rows[3]["data"]["Status"] = 1
    elif change == "wrong-thread":
        rows[2]["data"]["IssuingThreadId"] = 90
    elif change == "wrong-offset":
        rows[2]["data"]["ByteOffset"] += 1
    elif change == "different-object":
        rows[2]["data"]["FileObject"] += 1
    elif change == "conflicting-name":
        names[30].add(r"c:\qa\different.bin")
    elif change == "ambiguous":
        rows.extend({**row, "data": {**row["data"], "Irp": 900}} for row in rows[2:4])
    else:
        occupied.add((30, 999))
    result = verify(fixture, experiment, names, rows, occupied)
    assert result["staggered-protected"]["identity"] is None
    assert result["staggered-protected"]["writes"] == []
    assert result["staggered-outside"]["identity"] == (31, 131)


@pytest.mark.parametrize("change", ["wrong-root", "too-close", "wrong-range"])
def test_invalid_comparison_metadata_is_rejected(change):
    fixture, experiment, names, rows = comparison_evidence()
    record = experiment["files"]["staggered-protected"]
    if change == "wrong-root":
        record["path"] = r"C:\qa\staggered.bin"
    elif change == "too-close":
        record["writes"][1]["start"] = record["writes"][0]["end"] + 1
    else:
        record["writes"][1]["offset"] = 0
    with pytest.raises(ValueError):
        verify(fixture, experiment, names, rows)


def test_paging_range_distinguishes_first_write_before_second_write():
    writes = verify(*comparison_evidence())["staggered-protected"]["writes"]
    result = analyze.range_evidence(0, 4096, 3_500, writes, True)
    assert result["completed_writes_at_request"] == 1
    assert result["overlaps"] == [{"write": 1, "bytes": 4096,
                                   "after_write_completed_and_returned": True,
                                   "ms_from_write_return": 0.049}]


def test_paging_range_keeps_coalescing_gap_and_future_ranges_visible():
    writes = verify(*comparison_evidence())["staggered-protected"]["writes"]
    coalesced = analyze.range_evidence(0, 70_000, 61_000_000, writes, True)
    assert [item["write"] for item in coalesced["overlaps"]] == [1, 2]
    assert coalesced["completed_writes_at_request"] == 2
    early = analyze.range_evidence(65_536, 8192, 3_500, writes, True)
    assert early["overlaps"][0]["after_write_completed_and_returned"] is False
    assert analyze.range_evidence(8192, 8192, 3_500, writes, True)["range_status"] == "disjoint"
    assert analyze.range_evidence(0, 8192, 3_500, writes, False)["range_status"] == "unverified"
    assert analyze.range_evidence(None, 8192, 3_500, writes, True)["range_status"] == "unverified"


def test_symbol_summary_keeps_staggered_event_number(tmp_path):
    targets = [{"control": "staggered-protected", "operation": "write", "frames": [],
                "comparison_event": 2, "stack_frames": 0,
                "request_phase": "before-wpr-stop", "completion_phase": "before-wpr-stop"}]
    assert symbols.report(targets, tmp_path)["stacks"][0]["comparison_event"] == 2
