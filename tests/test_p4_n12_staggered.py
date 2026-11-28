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
    pauses, checked, live_pairs = [], [], []
    monkeypatch.setattr(capture.time, "sleep", pauses.append)
    monkeypatch.setattr(capture.probe, "utc_ticks", iter(range(100, 108)).__next__)
    monkeypatch.setattr(capture.probe, "verify_handle_path", lambda stream, path: checked.append(path))
    monkeypatch.setattr(capture, "verify_same_file", lambda writer, reader: live_pairs.append(
        writer.fileno() != reader.fileno() and writer.name == reader.name))
    monkeypatch.setattr(capture.sys, "stdin", io.TextIOWrapper(io.BytesIO()))
    capture.staggered_comparison(tmp_path)
    report = json.loads(capsys.readouterr().out)
    assert pauses == [5]
    assert len(checked) == 4 and live_pairs == [True, True]
    for record, first_tick in zip(report["files"].values(), (100, 102)):
        assert record["same_file_distinct_handles"] is True
        first, second = record["writes"]
        assert (first["start"], second["start"]) == (first_tick, first_tick + 4)
        path = next(path for path in checked if str(path) == record["path"])
        content = path.read_bytes()
        assert content[:first["size"]] == b"A" * first["size"]
        assert content[first["size"]:second["offset"]] == bytes(second["offset"] - first["size"])
        assert content[second["offset"]:] == b"B" * second["size"]


@pytest.mark.parametrize("changed", ["volume", "file-id"])
def test_handle_witness_rejects_different_volume_or_file_id(monkeypatch, changed):
    first, second = object(), object()
    same = (27, bytes(range(16)))
    other = (28, same[1]) if changed == "volume" else (27, b"B" * 16)
    monkeypatch.setattr(capture, "windows_file_identity", lambda handle: same if handle is first else other)
    with pytest.raises(RuntimeError, match="different files"):
        capture.verify_same_file(first, second)


def test_companion_candidate_counts_expose_failed_join_without_certifying_partial_matches():
    rows = []
    by_irp = defaultdict(list)
    for i, (key, obj, pid, status, event_id, info) in enumerate((
        (30, 130, 4, 0, 16, None),
        (30, 901, 4, 0, 16, None),
        (902, 130, 4, 0, 16, None),
        (903, 904, 4, 0, 17, 20),
        (30, 130, 4294967295, 0, 16, None),
        (30, 130, 21, 0, 16, None),
        (30, 130, 4, 1, 16, None),
        (30, 130, 4, 0, 17, 19),
        (909, 910, 4, 0, 16, None),
        (911, 912, 4, 0, 16, None),
        (913, 914, 4, 0, 16, None),
    ), 1):
        request = {"ticks": i * 10, "id": event_id, "pid": pid, "lifecycle": False,
                   "data": {"Irp": i, "FileKey": key, "FileObject": obj, "InfoClass": info, "IOFlags": 2}}
        completion = {"ticks": i * 10 + 1, "id": 24, "pid": 0, "lifecycle": False,
                      "data": {"Irp": i, "Status": status}}
        rows.extend([request, completion])
        by_irp[i] = [request, completion]
    path = PROTECTED.casefold() + r"\staggered.bin"
    exact, counts = analyze.staggered_candidates(
        rows, by_irp, {903: {path}}, {909: {path, "unknown"}}, {914: {path}},
        path, (30, 130), 21, 200, lambda _: "before-stop",
    )
    assert exact == [(rows[0], 11)]
    assert counts == {f"{operation}:before-stop:{relation}:{header}:{outcome}:{paging}": 1
                      for operation, relation, header, outcome, paging in (
                          ("write", "exact-pair", "system", "success", "set"),
                          ("write", "key-only", "system", "success", "set"),
                          ("write", "object-only", "system", "success", "set"),
                          ("resize", "rundown-name-only", "system", "success", "not-applicable"),
                          ("write", "exact-pair", "sentinel", "success", "set"),
                          ("write", "exact-pair", "fixture-writer", "success", "set"),
                          ("write", "exact-pair", "system", "unverified", "set"),
                          ("write", "trace-name-candidate-only", "system", "success", "set"),
                          ("write", "open-path-candidate-only", "system", "success", "set"),
                      )}


def test_classic_candidates_report_rejection_by_stage():
    original = analyze.Request(2, 68, 4, 22, 22, 10, 30, 130, 4096, 2, 0)
    item = {"data": {"Irp": 10, "IssuingThreadId": 22, "IOFlags": 2, "IOSize": 4096, "ByteOffset": 0}}
    candidates, counts = analyze.classic_candidates([
        original, original._replace(obj=999), original._replace(issuing=55),
        original._replace(offset=7), original._replace(irp=11),
    ], item, 68, (30, 130), True)
    assert candidates == [original]
    assert counts == {"classic-file-identity-mismatch": 1, "classic-process-or-thread-mismatch": 1,
                      "classic-operation-fields-mismatch": 1}
    assert analyze.classic_candidates([original], item, 68, (30, 130), False) == (
        [], {"classic-name-unverified": 1})


def test_report_keeps_path_candidates_when_staggered_reference_pair_is_absent(tmp_path, monkeypatch):
    fixture, experiment, _, _ = comparison_evidence()
    fixture.update(
        device=DEVICE, end_ticks=90_000_000, rundown_stop_ticks=81_000_000,
        counters={"events_lost": 0, "log_buffers_lost": 0, "realtime_buffers_lost": 0},
    )
    fixture["preopened"]["writes"] = {
        "protected": {"path": PROTECTED + r"\control.bin"},
        "outside": {"path": r"C:\qa\outside.bin"},
    }
    target = experiment["files"]["staggered-protected"]["path"]
    comparisons = {"staggered": experiment, "flushed": {"path": r"C:\qa\flushed.bin"},
                   "untouched": {"path": r"C:\qa\untouched.bin"}}
    events = [
        {"id": 12, "pid": 4, "ticks": 10, "lifecycle": False,
         "data": {"FileObject": 130, "FileName": target}},
        {"id": 16, "pid": 4, "ticks": 110, "lifecycle": False,
         "data": {"Irp": 1, "FileKey": 30, "FileObject": 130, "IOFlags": 2}},
        {"id": 24, "pid": 0, "ticks": 111, "lifecycle": False, "data": {"Irp": 1, "Status": 0}},
    ]
    (tmp_path / "fixture.json").write_text(json.dumps(fixture))
    (tmp_path / "events.jsonl").write_text("\n".join(map(json.dumps, events)))
    (tmp_path / "rundown.jsonl").write_text("")
    (tmp_path / "stack-rows.tsv").write_text("")
    monkeypatch.setattr(analyze, "preopened_report", lambda *args, **kwargs: {"targets": {}})
    monkeypatch.setattr(analyze, "comparison_identities", lambda *args: {
        "flushed": {"identity": None, "explicit_flush": False}, "untouched": {"identity": None},
    })
    known = {"path": r"C:\qa\stack-control.bin", "write": [120, 130], "resize": [140, 150]}
    decoder = {"pointer_size": 8, "events_lost": 0, "header_events_lost": 0,
               "buffers_lost": 0, "decode_errors": 0}
    symbols = []
    result = analyze.report(tmp_path, known, decoder, comparisons, symbols)

    protected = result["system_context"]["staggered-protected"]
    assert protected["identity"] == "unverified"
    assert protected["companion_candidate_counts"] == {
        "write:before-wpr-stop:open-path-candidate-only:system:success:set": 1,
    }
    assert protected["stack_join_counts"] == {} and protected["write"] == [] and symbols == []
    assert target.casefold() not in json.dumps(result).casefold()


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
