"""Synthetic N12 evidence tests. Never launch PilotODIN or change Windows auditing."""
from __future__ import annotations

import csv
import hashlib
import json
import subprocess
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from xml.etree import ElementTree as ET

import pytest

from qa.p4_native import n12_calibration, n12_etw_probe, n12_trace as trace
from qa.p4_native.n12_etw_correlate import (
    check_write_object_path, correlate, correlate_requests, decode_rundown_report,
    file_lifetime_report, preopened_report, preopened_resize_report, write_paging_flag,
)


def test_volume_devices_maps_all_local_logical_drives_only():
    mask = sum(1 << index for index in (2, 3, 4, 5))
    drive_types = {"C:": 3, "D:": 3, "E:": 4, "F:": 5}
    resolved = {"C:": r"\Device\HarddiskVolume3",
                "D:": r"\Device\HarddiskVolume4"}
    result = n12_etw_probe.volume_devices(
        logical_drive_mask=mask,
        drive_type=lambda drive: drive_types[drive],
        resolve=lambda drive: resolved[drive],
    )
    assert result == resolved


def test_etw_failed_open_and_reused_pid_and_file_object():
    capture = {
        "fixture": {"child_pid": 12, "start_window": [1, 3],
                    "fixture": r"D:\qa\original", "renamed_fixture": r"D:\qa\renamed"},
        "second_writer": {"pid": 20, "start_window": [4, 6],
                          "source": r"D:\qa\source", "destination": r"D:\qa\destination"},
        "device": r"\Device\HarddiskVolume3", "protected_root": r"D:\qa\protected",
    }
    rows = []

    def event(event_id, pid, *, lifecycle=False, **data):
        rows.append({"id": event_id, "pid": pid, "ticks": len(rows) + 1,
                     "lifecycle": lifecycle, "data": data})

    event(1, 0, lifecycle=True, ProcessID=12)
    event(12, 12, FileObject=8, Irp=11, FileName=r"D:\qa\original")
    event(24, 0, Irp=11, Status=0, ExtraInformation=2)
    event(2, 0, lifecycle=True, ProcessID=12)
    event(1, 0, lifecycle=True, ProcessID=20)
    event(12, 20, FileObject=8, Irp=11, FileName=r"D:\qa\source")
    event(24, 0, Irp=11, Status="0xc0000035", ExtraInformation=2)
    event(1, 0, lifecycle=True, ProcessID=12)
    event(16, 12, FileObject=8, Irp=11)
    event(24, 0, Irp=11, Status=0)
    # A process already running when the trace starts can open an existing file.
    event(12, 99, FileObject=9, Irp=13, FileName=r"D:\qa\protected\private-file")
    event(24, 0, Irp=13, Status=0, ExtraInformation=1)
    event(12, 12, FileObject=8, Irp=11,
          FileName=r"\Device\HarddiskVolume3\qa\protected\private-file")
    event(24, 0, Irp=11, Status=0, ExtraInformation=2)
    event(16, 12, FileObject=8, Irp=11)
    event(24, 0, Irp=11, Status=0)
    event(14, 12, FileObject=8)
    event(16, 12, FileObject=8, Irp=11)
    event(24, 0, Irp=11, Status=0)
    # A new open also invalidates an old object mapping if its close was absent.
    event(12, 12, FileObject=8, Irp=11, FileName=r"D:\qa\protected\private-file")
    event(24, 0, Irp=11, Status=0, ExtraInformation=1)
    event(12, 12, FileObject=8, Irp=11, FileName=r"D:\qa\untracked")
    event(24, 0, Irp=11, Status=0, ExtraInformation=1)
    event(16, 12, FileObject=8, Irp=11)
    event(24, 0, Irp=11, Status=0)

    assert correlate(capture, rows) == {
        "operations": {"fixture:create:original": 1, "other:create:protected": 1,
                       "other:write:protected": 1},
        "failed": {"second-writer:open:source": 1},
        "unresolved": {},
        "protected_writes": 2,
    }

    # Two overlapping requests cannot share a success completion.
    event(12, 12, FileObject=9, Irp=15, FileName=r"D:\qa\protected\private-file")
    event(12, 12, FileObject=10, Irp=15, FileName=r"D:\qa\untracked")
    event(24, 0, Irp=15, Status=0, ExtraInformation=2)
    report = correlate(capture, rows)
    assert report["protected_writes"] == 2
    assert report["unresolved"] == {"other:open:irp-reused-before-completion": 1}

    # Overwriting through an open still requires writer attribution.
    event(12, 99, FileObject=9, Irp=16, FileName=r"D:\qa\protected\private-file")
    event(24, 0, Irp=16, Status=0, ExtraInformation=3)
    report = correlate(capture, rows)
    assert report["protected_writes"] == 3
    assert report["operations"]["other:overwrite:protected"] == 1
    assert report["unresolved"]["other:open:process-lifetime-missing"] == 1

    # The smaller combined rehearsal fixture has no second writer.
    capture["second_writer"] = None
    report = correlate(capture, rows[:4])
    assert report == {"operations": {"fixture:create:original": 1}, "failed": {},
                      "unresolved": {}, "protected_writes": 0}
    assert correlate(capture, rows[1:4])["unresolved"] == {
        "fixture:process-start-missing-or-ambiguous": 1,
        "other:open:process-lifetime-missing": 1,
    }

def test_strict_reducer_correlates_protected_writer_to_preopened_control_identity():
    details = Counter()
    records = []
    path = r"C:\protected\control.bin"
    events = [
        {"id": 16, "pid": 4, "tid": 88, "ticks": 110, "lifecycle": False,
         "data": {"FileKey": 40, "FileObject": 400, "Irp": 7, "IOSize": 8,
                  "ByteOffset": 0, "IssuingThreadId": 88}},
        {"id": 24, "pid": 0, "tid": 0, "ticks": 120, "lifecycle": False,
         "data": {"Irp": 7, "Status": 0}},
    ]
    unresolved = correlate_requests(
        events, lambda value: value,
        lambda pid, birth, ticks: ("other", "system"),
        lambda value: value.casefold().startswith(r"c:\protected"),
        lambda *args: records.append(args),
        strict=True, details=details,
        rundown=[{"key": 40, "path": path}],
        initial_process_births={4: 100},
        preopened_control_file_keys={40},
        preopened_control_file_objects={400},
    )
    assert unresolved == {}
    assert len(records) == 1
    assert details["other:event-16:write:preopened-control-filekey-match"] == 1
    assert details["other:event-16:write:preopened-control-fileobject-match"] == 1


def test_strict_etw_tracks_allocation_and_keeps_file_keys_diagnostic():
    protected = r"C:\protected\private.txt"
    outside = r"C:\outside\private.txt"
    events = []

    def event(kind, pid=7, **data):
        events.append({"id": kind, "pid": pid, "ticks": len(events) + 1, "data": data})

    event(1, ProcessID=7)
    events[-1]["lifecycle"] = True
    event(12, FileObject=1, Irp=1, FileName=protected)
    event(24, Irp=1, Status=0, ExtraInformation=1)
    event(17, FileObject=1, Irp=2, InfoClass=19)
    event(24, Irp=2, Status=0)
    event(34, FileObject=2, Irp=3)
    event(24, Irp=3, Status=0)
    event(10, FileKey=40, FileName=outside)
    event(16, pid=8, FileObject=2, FileKey=40, Irp=4, IssuingThreadId=81)
    event(24, Irp=4, Status=0)
    event(10, FileKey=40, FileName=protected)
    event(3, ProcessID=7, ThreadID=71)
    events[-1]["lifecycle"] = True
    event(16, pid=8, FileObject=1, FileKey=40, Irp=5, IssuingThreadId=71)
    event(24, Irp=5, Status=0)
    event(4, ProcessID=7, ThreadID=71)
    events[-1]["lifecycle"] = True
    event(11, FileKey=40)
    event(16, pid=8, FileObject=2, FileKey=40, Irp=6, IssuingThreadId=71)
    event(24, Irp=6, Status=0)
    event(16, FileObject=1, Irp=7)
    event(34, FileObject=1, Irp=7)
    event(24, Irp=7, Status=0)

    details, completed = Counter(), []
    unresolved = correlate_requests(
        events, lambda value: value or None,
        lambda pid, birth, ticks: ("calibration", "child") if pid == 7 else ("other", None),
        lambda path: path == protected,
        lambda role, identity, operation, source, dest, start, end, success:
            completed.append((operation, source, success)),
        strict=True, details=details, process_bookends={8}, thread_bookends={81: 8},
    )
    assert completed == [("allocate", protected, True)]
    assert unresolved == {"other:write:path-missing": 3, "other:write:process-lifetime-missing": 3,
                          "calibration:write:irp-reused-before-completion": 1}
    for context in ("outside-tracked-paths", "ambiguous-name", "unseen-key"):
        assert details[f"other:event-16:write-request:file-key-context-{context}"] == 1
        assert details[f"other:event-16:write-request:same-process-at-bookends:{context}"] == 1
    for reason in ("bookend-header-agrees", "header-differs", "issuing-thread-handle-path",
                   "unmatched-thread-lifetime"):
        assert details[f"other:event-16:write-request:{reason}"] == 1
    for context in ("outside-tracked-paths", "issuing-thread-handle-candidate", "unseen-key"):
        assert details[f"write-path-gap:{context}"] == 1
    assert "private.txt" not in json.dumps(details)


def test_webview_write_path_replay_is_bounded_and_preserves_strict_coverage():
    events = []

    def event(kind, **data):
        events.append({"id": kind, "pid": 7, "ticks": len(events) + 1, "data": data,
                       "lifecycle": kind in {1, 3}})

    event(1, ProcessID=7)
    event(3, ProcessID=7, ThreadID=71)
    for index in range(68):
        key = 100 + index
        path = r"C:\profile\private.txt" if index == 0 else r"C:\elsewhere\private.txt"
        event(10, FileKey=key, FileName=path)
        event(16, FileObject=300 + index, FileKey=key, Irp=400 + index, IssuingThreadId=71)
        if index == 2:
            event(10, FileKey=key, FileName=r"C:\another\private.txt")
        if index == 3:
            event(11, FileKey=key)
        if index == 4:
            continue  # Missing completion never enters the sample.
        event(24, Irp=400 + index, Status=0xC0000022 if index == 5 else 0)
    for index in range(19):
        if index == 7:
            event(11, FileKey=100)
            event(10, FileKey=100, FileName=r"C:\elsewhere\private-renamed.txt")
        event(16, FileObject=300, FileKey=100, Irp=500 + index, IssuingThreadId=71)
        completion_identity = {"FileKey": 989} if index == 3 else {}
        event(24, Irp=500 + index, Status=0, **completion_identity)

    result = {}
    completed = []
    unresolved = correlate_requests(
        events, lambda value: value or None,
        lambda pid, birth, ticks: ("webview-network", "private-process"),
        lambda path: False, lambda *args: completed.append(args), strict=True,
        webview_write_candidates=result,
        classify_webview_path=lambda path: ("candidate-permitted" if "profile" in path
                                           else "candidate-outside-scope"),
    )
    assert unresolved == {"webview-network:write:path-missing": 85,
                          "webview-network:write:completion-missing": 1}
    assert len(completed) == 1 and completed[0][-1] is False
    assert (result["eligible"], result["sampled"], result["eligible_outside_sample"]) == (85, 64, 2)
    assert result["outcomes"] == {
        "webview-network:write:request-time:candidate-permitted": 1,
        "webview-network:write:request-time:candidate-outside-scope": 61,
        "webview-network:write:request-time:conflicting-or-unmapped-name": 1,
        "webview-network:write:request-time:possible-name-change": 1,
    }
    assert result["pairs"][0] == {
        "eligible": 20, "checked": 16, "supported": 15, "blocked": 1, "unchecked": 4,
        "outcomes": {
            "webview-network:write:request-time:candidate-permitted": 7,
            "webview-network:write:request-time:candidate-outside-scope": 8,
            "webview-network:write:completion-check:completion-file-identity-conflict": 1,
        },
    }
    pairs = result["pairs"]
    assert len(pairs) == 64
    assert sum(pair["eligible"] for pair in pairs) + result["eligible_outside_sample"] == result["eligible"]
    assert all(pair["checked"] == pair["supported"] + pair["blocked"] == sum(pair["outcomes"].values())
               and pair["eligible"] == pair["checked"] + pair["unchecked"] for pair in pairs)
    assert "private" not in json.dumps(result)


def test_webview_candidate_replay_matches_known_paths_and_rejects_conflicting_completion(tmp_path):
    start, end = (trace.utc_time(instant(second)) for second in (0, 1))
    origin = trace.utc_ticks(start)
    profile = r"c:\qa\profile"
    protected = r"c:\qa\protected"
    outside = r"c:\qa\profile-sibling"
    rows = []
    pid, thread = 7, 71

    def emit(kind, *, owner=pid, lifecycle=False, **data):
        rows.append({"ticks": origin + len(rows) + 1, "id": kind, "pid": owner,
                     "lifecycle": lifecycle, "data": data})

    def complete(irp, **data):
        emit(24, owner=0, Irp=irp, Status=0, **data)

    def write(obj, key, irp):
        emit(16, FileObject=obj, FileKey=key, Irp=irp, IssuingThreadId=thread)

    emit(1, owner=0, lifecycle=True, ProcessID=pid)
    emit(3, owner=0, lifecycle=True, ProcessID=pid, ThreadID=thread)
    for index, root in enumerate((profile, protected, outside), 1):
        path = root + r"\private-write.bin"
        emit(12, FileObject=index, Irp=index, FileName=path)
        complete(index, ExtraInformation=1)
        write(index, index, index + 10)
        complete(index + 10)

        # Replay the same known target with a pre-opened handle and a name event.
        emit(10, FileKey=index + 100, FileName=path)
        write(index + 100, index + 100, index + 100)
        complete(index + 100)

    path = outside + r"\private-replay.bin"
    emit(10, FileKey=201, FileName=path)
    write(201, 201, 201)
    complete(201, FileObject=999)

    emit(10, FileKey=202, FileName=path)
    write(202, 202, 202)
    emit(19, FileObject=202, FileKey=202, Irp=302)
    emit(27, FileObject=202, Irp=302, FilePath=protected + r"\private-rename.bin")
    complete(302)
    complete(202)

    emit(10, FileKey=203, FileName=path)
    write(203, 203, 203)
    emit(12, FileObject=203, FileKey=303, Irp=303, FileName=path)
    complete(303, ExtraInformation=1)
    complete(203)

    write(204, 204, 204)
    emit(10, FileKey=204, FileName=path)
    complete(204)

    emit(10, FileKey=205, FileName=path)
    write(0, 205, 205)
    complete(205)

    emit(10, FileKey=206, FileName=path)
    write(206, 206, 206)
    emit(2, owner=0, lifecycle=True, ProcessID=pid)
    emit(1, owner=0, lifecycle=True, ProcessID=pid)
    complete(206)

    payload = "".join(json.dumps(row) + "\n" for row in rows).encode()
    etw_path = tmp_path / "known-webview.jsonl"
    etw_path.write_bytes(payload)
    manifest = {"etw": {
        "schema_version": 1, "start_utc": instant(0), "end_utc": instant(1),
        "events_sha256": hashlib.sha256(payload).hexdigest(),
        "volume_devices": {"C:": r"\Device\HarddiskVolume3"},
        "counters": {"events_lost": 0, "log_buffers_lost": 0,
                     "realtime_buffers_lost": 0, "buffers_written": 1},
    }}
    role = "webview-network"
    processes = {"webview": trace.Process("webview", "app", pid, "msedgewebview2.exe", None, start, "")}
    arguments = (manifest, etw_path, start, end, processes, {"webview": role}, [protected], {role: [profile]})
    checked, baseline_issues, checked_issues = {}, set(), set()
    baseline = trace.inspect_etw_files(*arguments, baseline_issues)
    result = trace.inspect_etw_files(*arguments, checked_issues, webview_write_candidates=checked)
    assert result == baseline
    assert checked_issues == baseline_issues == {"etw-mutation-coverage-unresolved"}
    counts, violations, _, unresolved = result
    assert counts[f"{role}:write"] == 3
    assert violations[f"protected:{role}:write"] == 1
    assert violations[f"outside-scope:{role}:write"] == 2
    assert violations[f"protected:{role}:rename"] == 1
    assert unresolved[f"{role}:write:path-missing"] == 8
    assert unresolved[f"{role}:write:identity-missing"] == 1
    assert (checked["eligible"], checked["sampled"], checked["eligible_outside_sample"]) == (7, 7, 0)
    assert checked["outcomes"] == {
        f"{role}:write:request-time:candidate-permitted": 1,
        f"{role}:write:request-time:candidate-protected": 1,
        f"{role}:write:request-time:candidate-outside-scope": 1,
        f"{role}:write:completion-check:completion-file-identity-conflict": 1,
        f"{role}:write:request-time:possible-name-change": 1,
        f"{role}:write:request-time:conflicting-object-file-key": 1,
        f"{role}:write:completion-check:process-lifetime-unverified-at-completion": 1,
    }
    assert sum(pair["supported"] for pair in checked["pairs"]) == 3
    assert sum(pair["blocked"] for pair in checked["pairs"]) == 4
    assert "private" not in json.dumps(checked)


@pytest.mark.parametrize("compare_credit", [False, True])
@pytest.mark.parametrize(("case", "expected"), [
    ("outside", "consistent-outside-protected-path"),
    ("protected", "consistent-protected-path"),
    ("completion-at-start", "completion-at-or-after-rundown-start"),
    ("process-exit", "process-lifetime-unverified-at-completion"),
    ("completion-object", "completion-file-identity-conflict"),
    ("late-object-reuse", "object-key-association-unverified"),
    ("late-rename", "lifetime-invalidated"),
    ("ambiguous-name", "ambiguous-or-unmapped-name"),
    ("missing-key", "not-in-rundown"),
])
def test_background_rundown_checks_the_identity_at_completion(case, expected, compare_credit):
    private_path = r"C:\QA\private-protected.bin"
    outside = r"C:\elsewhere\private-outside.bin"
    events = [
        {"id": 16, "pid": 7, "ticks": 3, "data": {"FileObject": 9, "FileKey": 40, "Irp": 1}},
        {"id": 24, "pid": 0, "ticks": 5, "data": {"Irp": 1, "Status": 0}},
    ]
    guards = list(events)
    names = [{"key": 40, "path": private_path if case == "protected" else outside}]
    if case == "process-exit":
        events.insert(1, {"id": 2, "pid": 7, "ticks": 4, "lifecycle": True, "data": {"ProcessID": 7}})
    if case == "completion-object":
        events[-1]["data"]["FileObject"] = 99
    if case == "late-object-reuse":
        guards.append({"id": 16, "pid": 7, "ticks": 14, "data": {"FileObject": 9, "FileKey": 41}})
    if case == "late-rename":
        guards.append({"id": 19, "pid": 7, "ticks": 14, "data": {"FileObject": 9, "FileKey": 40}})
    if case == "ambiguous-name":
        names.append({"key": 40, "path": private_path})
    if case == "missing-key":
        names.clear()

    diagnostics = {}
    credited = []
    credit_summary = {} if compare_credit else None
    unresolved = correlate_requests(
        events, lambda value: value or None, lambda *_: ("other", "private-owner"),
        lambda path: path == private_path, lambda *args: credited.append(args),
        strict=True, initial_process_births={7: 1}, rundown=names, rundown_guard_events=guards,
        calibration_diagnostics=diagnostics, calibration_end=8, diagnostic_rundown_stop=12,
        rundown_verification_start=5 if case == "completion-at-start" else 10,
        rundown_credit=credit_summary,
    )
    assert diagnostics["path_candidates"][f"other:write:no-prior-name-completion-check:{expected}"] == 1
    if compare_credit and case in {"outside", "protected"}:
        path = private_path if case == "protected" else outside
        scope = "protected" if case == "protected" else "outside-protected"
        assert unresolved == {}
        assert credited == [("other", "private-owner", "write", path, None, 3, 5, True)]
        assert credit_summary == {
            "credited_paths": {f"other:write:{scope}": 1},
            "remaining_paths_by_reason": {},
        }
    else:
        assert unresolved == {"other:write:path-missing": 1}
        assert credited == []
        if compare_credit:
            assert credit_summary == {
                "credited_paths": {},
                "remaining_paths_by_reason": {f"other:write:completion-check:{expected}": 1},
            }
    assert "private" not in json.dumps(diagnostics)


def test_strict_etw_counts_only_successful_write_gaps_using_request_time_names():
    protected = r"C:\protected\private.txt"
    outside = r"C:\outside\private.txt"
    events = []

    def event(kind, ticks, **data):
        events.append({"id": kind, "pid": 7, "ticks": ticks, "data": data})

    event(10, 1, FileKey=40, FileName=outside)
    event(16, 2, FileObject=9, FileKey=40, Irp=1)
    event(10, 3, FileKey=40, FileName=protected)
    event(24, 4, Irp=1, Status=0)
    event(16, 5, FileObject=9, FileKey=41, Irp=2)
    event(10, 6, FileKey=41, FileName=protected)
    event(24, 7, Irp=2, Status=0)
    event(14, 8, FileObject=9, FileKey=41)
    event(16, 9, FileObject=9, FileKey=41, Irp=3)
    event(24, 10, Irp=3, Status=0)
    event(16, 11, FileObject=9, FileKey=42, Irp=4)
    event(10, 11, FileKey=42, FileName=outside)
    event(24, 12, Irp=4, Status=0)
    event(16, 13, FileObject=9, FileKey=42, Irp=5)
    event(24, 14, Irp=5, Status=0xC0000022)
    event(16, 15, FileObject=9, FileKey=42, Irp=6)
    event(16, 16, FileObject=9, FileKey=42, Irp=7)
    event(16, 17, FileObject=10, FileKey=43, Irp=7)
    event(24, 18, Irp=7, Status=0)
    event(13, 19, FileObject=12, FileKey=42)
    event(14, 20, FileObject=12, FileKey=42)
    event(16, 21, FileObject=9, FileKey=42, Irp=8)
    event(24, 22, Irp=8, Status=0)
    event(10, 23, FileKey=44, FileName=protected)
    event(10, 24, FileKey=44, FileName=outside)
    event(16, 25, FileObject=9, FileKey=44, Irp=9)
    event(24, 26, Irp=9, Status=0)
    details = Counter()

    unresolved = correlate_requests(
        events, lambda value: value or None,
        lambda pid, birth, ticks: ("other", None), lambda path: path == protected,
        lambda *args: None, strict=True, details=details, initial_process_births={7: 0},
    )

    assert unresolved["other:write:path-missing"] == 6
    assert {key: count for key, count in details.items() if key.startswith("write-path-gap:")} == {
        "write-path-gap:outside-tracked-paths": 1,
        "write-path-gap:unseen-key": 1,
        "write-path-gap:invalidated-name": 2,
        "write-path-gap:same-timestamp-name-transition": 1,
        "write-path-gap:ambiguous-name": 1,
    }
    assert {key: count for key, count in details.items() if key.startswith("write-name-invalidation:")} == {
        "write-name-invalidation:event-14:same-object": 1,
        "write-name-invalidation:event-13:different-object": 1,
    }
    public_counts = Counter()

    def count_gap(role, thread, context):
        public_counts[f"{role}:{thread}:{context}"] += 1

    assert correlate_requests(
        events, lambda value: value or None,
        lambda pid, birth, ticks: ("other", None), lambda path: path == protected,
        lambda *args: None, strict=True, initial_process_births={7: 0},
        record_write_name_gap=count_gap,
    ) == unresolved
    assert public_counts == {f"other:no-thread-id:{context}": 1 for context in (
        "outside-tracked-paths", "unseen-key", "invalidated-name:event-14:same-object",
        "same-timestamp-name-transition", "invalidated-name:event-13:different-object", "ambiguous-name",
    )}
    assert "private.txt" not in json.dumps(public_counts)


@pytest.mark.parametrize(("fault", "reason"), [
    (None, None),
    ("reused-object", "write-missing-or-ambiguous"),
    ("cleanup-other-object", "cleanup-close-order-unverified"),
    ("tied-end-events", "cleanup-close-order-unverified"),
    ("tied-open-completion", "open-completion-unverified"),
    ("failed-write", "write-completion-unverified"),
])
def test_generated_file_lifetime_requires_ordered_same_object_evidence(fault, reason):
    path = r"C:\private\control.bin"
    control = {"path": path, "pid": 7, "size": 97, "start": 1, "end": 20}
    events = []

    def event(kind, ticks, **data):
        events.append({"id": kind, "pid": 7, "ticks": ticks, "lifecycle": False, "data": data})

    event(12, 2, FileName=path, FileObject=50, Irp=1)
    event(24, 5 if fault == "tied-open-completion" else 3, Irp=1, Status=0)
    if fault == "reused-object":
        event(12, 4, FileName=r"C:\private\another.bin", FileObject=50, Irp=3)
    event(16, 5, FileObject=50, FileKey=60, Irp=2, IOSize=97, ByteOffset=0)
    event(10, 6, FileName=path, FileKey=60)
    event(24, 7, Irp=2, Status=0xC0000022 if fault == "failed-write" else 0)
    event(13, 8, FileObject=51 if fault == "cleanup-other-object" else 50, FileKey=60)
    event(14, 8 if fault == "tied-end-events" else 9, FileObject=50, FileKey=60)

    report = file_lifetime_report(control, events, {})
    if reason:
        assert report["status"] == "BLOCKED"
        assert report["reason"] == reason
        if fault == "cleanup-other-object":
            assert report["observed_end_events"] == [14]
        if fault == "tied-end-events":
            assert report["observed_end_events"] == [13, 14]
            assert not report["end_timestamps_distinct"]
    else:
        assert report == {
            "status": "PASS", "reason": None, "open_and_write_completed": True,
            "observed_end_events": [13, 14],
            "end_order": ["after-write-completion", "after-write-completion"],
            "end_timestamps_distinct": True, "end_key_matches_write": [True, True],
            "matching_name_before_write": False, "matching_name_at_or_after_write": True,
        }
    assert "control.bin" not in json.dumps(report)


@pytest.mark.parametrize(("fault", "reason"), [
    (None, "completed-open-and-write"),
    ("missing-close", "completed-open-and-write"),
    ("early-cleanup", "file-object-lifetime-changed"),
    ("wrong-name", "open-missing-or-ambiguous"),
    ("failed-write", "write-completion-unverified"),
    ("rename", "possible-name-change"),
])
def test_known_file_report_only_discloses_a_verified_fixture_match(fault, reason):
    root = r"C:\private-fixture"
    path = root + r"\known-write.bin"
    capture = {
        "device": r"\Device\HarddiskVolume3",
        "protected_root": root + r"\synthetic-protected",
        "preopened": {"pid": 6, "tid": 7, "writes": {
            "protected": {"start": 30, "end": 32, "size": 53},
            "outside": {"start": 30, "end": 32, "size": 79},
        }},
        "known_write": {"path": path, "pid": 8, "size": 61, "start": 1, "end": 20},
    }
    records = [
        (2, 12, {"FileName": root + r"\unexpected.bin" if fault == "wrong-name" else path,
                 "FileObject": 50, "Irp": 1}),
        (3, 24, {"Irp": 1, "Status": 0}),
        (5, 16, {"FileObject": 50, "FileKey": 60, "Irp": 2, "IOSize": 61, "ByteOffset": 0}),
        (7, 24, {"Irp": 2, "Status": 1 if fault == "failed-write" else 0}),
        (6 if fault == "early-cleanup" else 8, 13, {"FileObject": 50, "FileKey": 60}),
    ]
    if fault != "missing-close":
        records.append((9, 14, {"FileObject": 50, "FileKey": 60}))
    if fault == "rename":
        records.append((6, 19, {"FileObject": 50, "FileKey": 60}))
    events = [{"id": kind, "ticks": ticks, "pid": 8, "lifecycle": False, "data": data}
              for ticks, kind, data in records]
    result = preopened_report(capture, events)["known_write"]
    teardown = result.pop("cleanup_close", None)
    matched = fault in {None, "missing-close"}
    assert result == {
        "operation": "write", "expected_file": "known-write.bin",
        "matched_file": "known-write.bin" if matched else None,
        "status": "PASS" if matched else "BLOCKED", "reason": reason,
    }
    if fault == "missing-close":
        assert teardown == {"status": "BLOCKED", "reason": "cleanup-close-order-unverified",
                            "observed_events": [13]}
    elif fault == "early-cleanup":
        assert teardown["status"] == "BLOCKED"
    elif fault is None:
        assert teardown == {"status": "PASS", "reason": None, "observed_events": [13, 14]}


@pytest.mark.parametrize(("fault", "reason"), [
    (None, "completed-open-and-resize"),
    ("allocation", "resize-missing-or-ambiguous"),
    ("wrong-object", "resize-missing-or-ambiguous"),
    ("duplicate", "resize-missing-or-ambiguous"),
    ("failed", "resize-completion-unverified"),
    ("rename", "possible-name-change"),
])
def test_known_resize_links_only_the_completed_end_of_file_change(fault, reason):
    root = r"C:\private-fixture"
    path = root + r"\known-resize.bin"
    capture = {
        "device": r"\Device\HarddiskVolume3",
        "protected_root": root + r"\synthetic-protected",
        "preopened": {"pid": 6, "tid": 7, "writes": {
            "protected": {"start": 30, "end": 32, "size": 53},
            "outside": {"start": 30, "end": 32, "size": 79},
        }},
        "known_resize": {"path": path, "pid": 8, "start": 1, "end": 20,
                         "before_bytes": 96, "after_bytes": 37},
    }
    records = [
        (2, 12, {"FileName": path, "FileObject": 51, "Irp": 1}),
        (3, 24, {"Irp": 1, "Status": 0}),
        (5, 17, {"FileObject": 99 if fault == "wrong-object" else 51, "FileKey": 61, "Irp": 2,
                 "InfoClass": 19 if fault == "allocation" else 20}),
        (7, 24, {"Irp": 2, "Status": 1 if fault == "failed" else 0}),
    ]
    if fault == "rename":
        records.append((6, 19, {"FileObject": 51, "FileKey": 61}))
    if fault == "duplicate":
        records.append((6, 17, {"FileObject": 51, "FileKey": 61, "Irp": 3, "InfoClass": 20}))
    events = [{"id": kind, "ticks": ticks, "pid": 8, "lifecycle": False, "data": data}
              for ticks, kind, data in records]
    report = preopened_report(capture, events)["known_resize"]
    assert report == {
        "operation": "resize", "expected_file": "known-resize.bin",
        "matched_file": "known-resize.bin" if fault is None else None,
        "status": "PASS" if fault is None else "BLOCKED", "reason": reason,
        "before_bytes": 96, "after_bytes": 37,
    }


@pytest.mark.parametrize(("fault", "reason"), [
    (None, "completed-resize-credited-by-rundown"),
    ("missing-key", "resize-rundown-path-unverified"),
    ("conflicting-name", "resize-rundown-path-unverified"),
    ("lifetime-changed", "resize-rundown-path-unverified"),
    ("late-completion", "resize-completion-unverified-before-rundown"),
    ("open-in-capture", "resize-already-has-path"),
])
def test_preopened_resize_compares_the_same_request_against_rundown(fault, reason):
    path = r"C:\private-fixture\known-resize.bin"
    capture = {
        "protected_root": r"C:\private-fixture\synthetic-protected",
        "preopened": {"pid": 8},
        "known_preopened_resize": {"path": path, "start": 3_000_000, "end": 3_200_000,
                                   "before_bytes": 96, "after_bytes": 37},
    }
    records = [
        (3_100_000, 17, {"FileObject": 51, "FileKey": 61, "Irp": 2, "InfoClass": 20}),
        (8_000_000 if fault == "late-completion" else 3_150_000, 24, {"Irp": 2, "Status": 0}),
    ]
    if fault == "lifetime-changed":
        records.append((6_000_000, 13, {"FileObject": 51, "FileKey": 61}))
    if fault == "open-in-capture":
        records.extend([
            (2_000_000, 12, {"FileObject": 51, "FileName": path, "Irp": 1}),
            (2_100_000, 24, {"Irp": 1, "Status": 0, "ExtraInformation": 1}),
        ])
    events = [{"id": kind, "ticks": ticks, "pid": 8, "lifecycle": False, "data": data}
              for ticks, kind, data in records]
    rundown = [] if fault == "missing-key" else [{"key": 61, "path": path}]
    if fault == "conflicting-name":
        rundown.append({"key": 61, "path": r"C:\different.bin"})
    result = preopened_resize_report(capture, events, rundown, {}, 1_000_000,
                                     (1_500_000, 10_000_000), (8_000_000, 9_000_000))
    details = result.pop("path_evidence", {})
    assert result == {
        "operation": "resize", "expected_file": "known-resize.bin",
        "matched_file": "known-resize.bin" if fault is None else None,
        "status": "PASS" if fault is None else "BLOCKED", "reason": reason,
        "before_bytes": 96, "after_bytes": 37,
        "without_rundown": {"open-in-capture": "path-present", "late-completion": "unverified"}.get(
            fault, "path-unresolved"),
    }
    if fault is None:
        assert details["no-prior-name-completion-check:consistent-fixture-target-path"] == 1
    if fault == "conflicting-name":
        assert details["no-prior-name-completion-check:ambiguous-or-unmapped-name"] == 1
    if fault == "lifetime-changed":
        assert details["no-prior-name-completion-check:lifetime-invalidated"] == 1


@pytest.mark.parametrize(("name_at", "wrong_name", "verdict"), [
    (4, False, "matches-handle-path"),
    (4, True, "different-from-handle-path"),
    (5, False, "ambiguous-event-order"),
    (6, False, "no-prior-name-in-lifetime"),
    (None, False, "no-prior-name-in-lifetime"),
])
def test_in_capture_name_control_measures_prior_name(name_at, wrong_name, verdict):
    path = r"C:\private\control.bin"
    control = {"path": path, "pid": 7, "size": 113, "start": 1, "end": 12,
               "prior_name_control": True, "offset": 4, "write_window": [5, 7]}
    records = [
        (2, 12, {"FileName": path, "FileObject": 50, "Irp": 1}),
        (3, 24, {"Irp": 1, "Status": 0}),
        (5, 16, {"FileObject": 50, "FileKey": 60, "Irp": 2, "IOSize": 113, "ByteOffset": 4}),
        (6, 16, {"FileObject": 50, "FileKey": 60, "Irp": 3, "IOSize": 113, "ByteOffset": 4, "IOFlags": 2}),
        (7, 24, {"Irp": 2, "Status": 0}),
        (8, 13, {"FileObject": 50, "FileKey": 60}),
        (9, 14, {"FileObject": 50, "FileKey": 60}),
    ]
    if name_at is not None:
        records.append((name_at, 10, {"FileObject": 60,
                                     "FileName": r"C:\private\other.bin" if wrong_name else path}))
    events = [{"id": kind, "ticks": ticks, "pid": 7, "lifecycle": False, "data": data}
              for ticks, kind, data in records]
    result = file_lifetime_report(control, events, {})
    assert result["status"] == "PASS"
    assert result["request_time_path"] == verdict
    assert "private" not in json.dumps(result)
    assert file_lifetime_report(dict(control, offset=0), events, {}) == {
        "status": "BLOCKED", "reason": "write-missing-or-ambiguous",
        "write_candidates": {"same_object": 2, "same_process": 2, "same_size": 2, "same_offset": 0,
                             "in_write_window_nonpaging": 0},
        "request_relationships": {"distinct_request_ids": 0, "request_ids_shared_by_candidates": 0,
                                  "candidates_without_request_id": 0,
                                  "candidates_with_ordered_successful_completion": 0},
        "shared_request_rejection": "too-few-candidates",
    }


@pytest.mark.parametrize(("second_id", "extra_completions", "expected"), [
    (997, [], (1, 1, 0, 1)),
    (998, [], (2, 0, 0, 1)),
    (998, [(8, 998, 0)], (2, 0, 0, 2)),
    (998, [(8, 998, 0xC0000022)], (2, 0, 0, 1)),
    (998, [(8, 998, 0), (8, 998, 0)], (2, 0, 0, 1)),
    (None, [], (1, 0, 1, 1)),
    (0, [], (1, 0, 1, 1)),
])
def test_in_capture_name_control_counts_request_relationships(second_id, extra_completions, expected):
    path = r"C:\private\control.bin"
    control = {"path": path, "pid": 7, "size": 113, "start": 1, "end": 12,
               "prior_name_control": True, "offset": 4, "write_window": [5, 6]}
    write = {"FileObject": 50, "FileKey": 60, "IOSize": 113, "ByteOffset": 4}
    records = [
        (2, 12, {"FileName": path, "FileObject": 50, "Irp": 1}),
        (3, 24, {"Irp": 1, "Status": 0}),
        (5, 16, dict(write, Irp=997)),
        (6, 16, dict(write, Irp=second_id)),
        (7, 24, {"Irp": 997, "Status": 0}),
        *((ticks, 24, {"Irp": irp, "Status": status}) for ticks, irp, status in extra_completions),
    ]
    events = [{"id": kind, "ticks": ticks, "pid": 7, "lifecycle": False, "data": data}
              for ticks, kind, data in records]
    result = file_lifetime_report(control, events, {})
    assert result["status"] == "BLOCKED"
    assert result["reason"] == "write-missing-or-ambiguous"
    assert result["request_relationships"] == dict(zip((
        "distinct_request_ids", "request_ids_shared_by_candidates", "candidates_without_request_id",
        "candidates_with_ordered_successful_completion",
    ), expected))
    assert "request_time_path" not in result
    assert result.get("shared_request_rejection") == {
        998: "candidate-request-ids-differ",
        None: "candidate-request-id-unavailable",
        0: "candidate-request-id-unavailable",
    }.get(second_id)
    assert all(private not in json.dumps(result) for private in ("private", "997", "998"))


@pytest.mark.parametrize(("scenario", "verdict"), [
    ("shared", "matches-handle-path"),
    ("late-name", "no-prior-name-in-lifetime"),
    ("wrong-name", "different-from-handle-path"),
    ("rename-between", "possible-name-change"),
    ("rename-at-first", "possible-name-change"),
    ("late-open-completion", "open-completion-unverified"),
    ("other-key", None),
    ("missing-key", None),
    ("reuse", None),
    ("tied-writes", None),
    ("tied-completions", None),
    ("completion-before-last", None),
    ("extra-completion", None),
])
def test_in_capture_name_control_trials_shared_request_paths(scenario, verdict):
    path = r"C:\private\control.bin"
    control = {"path": path, "pid": 7, "size": 113, "start": 1, "end": 30,
               "prior_name_control": True, "offset": 4, "write_window": [10, 15]}
    write = {"FileObject": 50, "FileKey": 60, "IOSize": 113, "ByteOffset": 4, "Irp": 997}
    records = [
        (2, 12, {"FileName": path, "FileObject": 50, "Irp": 1}),
        (11 if scenario == "late-open-completion" else 3, 24, {"Irp": 1, "Status": 0}),
        (11 if scenario == "late-name" else 5, 10,
         {"FileObject": 60, "FileName": r"C:\private\other.bin" if scenario == "wrong-name" else path}),
        (10, 16, write),
        (10 if scenario == "tied-writes" else 12, 16,
         dict(write, FileKey={"other-key": 61, "missing-key": None}.get(scenario, 60))),
        (11 if scenario == "completion-before-last" else 17, 24, {"Irp": 997, "Status": 0}),
        (25, 13, {"FileObject": 50, "FileKey": 60}),
        (26, 14, {"FileObject": 50, "FileKey": 60}),
    ]
    if scenario in {"rename-between", "rename-at-first"}:
        records.append((10 if scenario == "rename-at-first" else 11, 27, {"FileKey": 60, "FileObject": 50}))
    if scenario in {"reuse", "extra-completion", "tied-completions"}:
        records.append((17 if scenario == "tied-completions" else 20, 24, {"Irp": 997, "Status": 0}))
    if scenario == "reuse":
        records.append((19, 16, dict(write, IOSize=9)))
    events = [{"id": kind, "ticks": ticks, "pid": 7, "lifecycle": False, "data": data}
              for ticks, kind, data in records]
    result = file_lifetime_report(control, events, {})
    assert result["status"] == ("PASS" if scenario == "shared" else "BLOCKED")
    assert result.get("shared_request_path_trial") == verdict
    assert result.get("shared_request_rejection") == {
        "other-key": "candidate-file-keys-differ",
        "missing-key": "candidate-file-key-unavailable",
        "reuse": "extra-or-intervening-request-events",
        "tied-writes": "tied-candidate-timestamps",
        "tied-completions": "last-candidate-completion-unverified",
        "completion-before-last": "last-candidate-completion-unverified",
        "extra-completion": "extra-or-intervening-request-events",
    }.get(scenario)
    assert result.get("request_time_path") == (verdict if scenario in {"shared", "wrong-name"} else None)
    assert "private" not in json.dumps(result)


@pytest.mark.parametrize(("fault", "reason"), [
    (None, None),
    ("missing-final-close", None),
    ("same-object", "distinct-file-objects-unverified"),
    ("wrong-key", "cleanup-and-write-shared-key-unverified"),
    ("early-cleanup", "first-cleanup-between-second-open-and-write-unverified"),
    ("reused-second-object", "second-object-ended-before-write-completion"),
    ("reused-before-write", None),
    ("tied-name", None),
])
def test_two_handles_distinguish_shared_key_from_write_object(fault, reason):
    path = r"C:\private\control.bin"
    control = {"path": path, "pid": 7, "size": 97, "start": 1, "end": 20, "two_handles": True}
    events = []

    def event(kind, ticks, **data):
        events.append({"id": kind, "pid": 7, "ticks": ticks, "lifecycle": False, "data": data})

    first = 51 if fault == "same-object" else 50
    event(12, 2, FileName=path, FileObject=first, Irp=1)
    event(24, 3, Irp=1, Status=0)
    event(10, 4, FileName=path, FileKey=60)
    event(12, 5, FileName=path, FileObject=51, Irp=2)
    event(24, 6, Irp=2, Status=0)
    if fault != "same-object":
        event(13, 4 if fault == "early-cleanup" else 7, FileObject=first,
              FileKey=61 if fault == "wrong-key" else 60)
    if fault == "reused-before-write":
        event(13, 8, FileObject=51, FileKey=60)
        event(14, 9, FileObject=51, FileKey=60)
        event(12, 10, FileName=r"C:\private\reused.bin", FileObject=51, Irp=4)
        event(24, 11, Irp=4, Status=0)
        event(16, 12, FileObject=51, FileKey=61, Irp=3, IOSize=97, ByteOffset=0)
        event(24, 13, Irp=3, Status=0)
        assert file_lifetime_report(control, events, {}) == {
            "status": "BLOCKED", "reason": "write-missing-or-ambiguous",
        }
        return
    event(16, 8, FileObject=51, FileKey=60, Irp=3, IOSize=97, ByteOffset=0)
    if fault == "tied-name":
        event(10, 8, FileName=path, FileKey=60)
    if fault == "reused-second-object":
        event(12, 9, FileName=r"C:\private\reused.bin", FileObject=51, Irp=4)
    event(24, 10, Irp=3, Status=0)
    event(13, 11, FileObject=51, FileKey=60)
    if fault != "missing-final-close":
        event(14, 12, FileObject=51, FileKey=60)

    report = file_lifetime_report(control, events, {})
    if fault is None:
        assert report["status"] == "PASS" and report["reason"] is None
    elif fault == "missing-final-close":
        assert report["status"] == "BLOCKED" and report["reason"] == "cleanup-close-order-unverified"
    if reason:
        assert report["overlap"] == {"status": "BLOCKED", "reason": reason}
    else:
        assert report["overlap"] == {
            "status": "PASS", "first_cleanup_before_second_write": True,
            "matching_name_in_key_lifetime": True, "conflicting_name_in_key_lifetime": False,
            "name_transition_tied_with_write": fault == "tied-name",
            "first_invalidation_is_first_cleanup": fault != "tied-name",
        }
    path_blockers = {"tied-name": "ambiguous-event-order",
                     "reused-second-object": "file-object-lifetime-changed"}
    if fault in {None, "missing-final-close", *path_blockers}:
        expected = path_blockers.get(fault)
        assert report["write_object_path"] == {
            "status": "BLOCKED" if expected else "PASS", "reason": expected,
        }
    assert "control.bin" not in json.dumps(report)


@pytest.mark.parametrize(("fault", "reason"), [
    ("failed-open", "open-completion-unverified"),
    ("tied-open", "open-completion-unverified"),
    ("conflicting-name", "conflicting-or-unmapped-name"),
    ("rename-other-object", "possible-name-change"),
    ("same-object-cleanup", "file-object-lifetime-changed"),
    ("cleanup-at-open-completion", "ambiguous-event-order"),
    ("ambiguous-cleanup-object", "file-object-lifetime-changed"),
    ("unrelated-rename", None),
])
def test_write_object_path_rejects_uncertain_evidence(fault, reason):
    path = r"c:\private\control.bin"

    def event(kind, ticks, **data):
        return {"id": kind, "ticks": ticks, "lifecycle": False, "data": data}

    opened = event(12, 2, FileName=path, FileObject=51, Irp=1)
    write = event(16, 8, FileObject=51, FileKey=60, Irp=2)
    completion = event(24, 8 if fault == "tied-open" else 3, Irp=1,
                       Status=0xC0000022 if fault == "failed-open" else 0)
    extra = {
        "conflicting-name": event(10, 4, FileKey=60, FileName=r"c:\outside\alias.bin"),
        "rename-other-object": event(27, 5, FileKey=60, FileObject=50),
        "same-object-cleanup": event(13, 5, FileObject=51, FileKey=60),
        "cleanup-at-open-completion": event(13, 3, FileObject=51, FileKey=60),
        "ambiguous-cleanup-object": event(13, 5, FileKey=60),
        "unrelated-rename": event(27, 5, FileKey=61, FileObject=52),
    }.get(fault)
    events = [opened, completion, write, event(24, 9, Irp=2, Status=0)]
    if extra:
        events.append(extra)
    assert check_write_object_path(sorted(events, key=lambda item: item["ticks"]),
                                   opened, write, 9, path, {}) == reason


@pytest.mark.parametrize(("fault", "outcome"), [
    (None, "candidate-protected"),
    ("outside", "candidate-outside-protected"),
    ("no-open", "no-observed-open"),
    ("failed-open", "open-completion-unverified"),
    ("reused-object", "open-completion-unverified"),
    ("ambiguous-completion", "write-completion-unverified"),
    ("ambiguous-open", "ambiguous-event-order"),
    ("unknown-process", "open-process-lifetime-unverified"),
    ("process-exited", "open-process-lifetime-unverified"),
    ("conflicting-name", "conflicting-or-unmapped-name"),
    ("same-object-cleanup", "file-object-lifetime-changed"),
    ("rename-path", "possible-name-change"),
    ("set-information", "possible-name-change"),
    ("unknown-information-class", "possible-name-change"),
    ("fsctl", "possible-name-change"),
    ("unknown-fsctl", "possible-name-change"),
])
def test_unresolved_write_open_evidence_does_not_change_the_audit(fault, outcome):
    protected = r"c:\protected\file.bin"
    path = r"c:\outside\file.bin" if fault == "outside" else protected
    events = []

    def emit(kind, ticks, pid=7, lifecycle=False, **data):
        events.append({"id": kind, "ticks": ticks, "pid": pid, "lifecycle": lifecycle, "data": data})

    if fault != "no-open":
        emit(12, 2, FileName=path, FileObject=51, Irp=1)
        emit(24, 3, Irp=1, Status=0xC0000022 if fault == "failed-open" else 0, ExtraInformation=1)
    emit(10, 4, FileKey=60, FileName=path)
    emit(13, 5, FileKey=60, FileObject=51 if fault == "same-object-cleanup" else 50)
    if fault == "reused-object":
        emit(12, 6, FileObject=51, Irp=3, FileName=r"c:\outside\reused.bin")
    if fault == "process-exited":
        emit(2, 6, lifecycle=True, ProcessID=7)
    if fault == "conflicting-name":
        emit(10, 6, FileKey=60, FileName=r"c:\outside\alias.bin")
    if fault == "ambiguous-open":
        emit(12, 8, FileObject=51, Irp=3, FileName=path)
    blocking_events = {
        "rename-path": (27, {}, "event-27"),
        "set-information": (17, {"InfoClass": "0x4"}, "event-17-info-4"),
        "unknown-information-class": (17, {"InfoClass": 256}, "event-17-info-unknown"),
        "fsctl": (23, {"InfoClass": "0x900C4"}, "event-23-fsctl-0x000900C4"),
        "unknown-fsctl": (23, {}, "event-23-fsctl-unknown"),
    }
    expected_name_change = {}
    if fault in blocking_events:
        kind, fields, label = blocking_events[fault]
        emit(kind, 6, FileObject=52, FileKey=60, Irp=5, **fields)
        emit(24, 7, Irp=5, Status=0xC0000022)
        # A later possible path change must not inflate the count.
        emit(26, 7, FileObject=53, FileKey=60)
        expected_name_change[f"write-gap-name-change-event:{label}"] = 1
    emit(16, 8, pid=4, FileObject=51, FileKey=60, Irp=2)
    emit(24, 9, Irp=2, Status=0)
    if fault == "ambiguous-completion":
        emit(24, 9, Irp=2, Status=0)
    emit(16, 10, pid=4, FileObject=51, FileKey=60, Irp=4)
    emit(24, 11, Irp=4, Status=0xC0000022)
    details = Counter()
    records = []
    unresolved = correlate_requests(
        events, lambda value: value or None, lambda *args: ("other", None),
        lambda value: value == protected, lambda *args: records.append(args),
        strict=True, details=details, initial_process_births={4: 0} if fault == "unknown-process"
        else {4: 0, 7: 0},
    )
    assert unresolved["other:write:path-missing"] == 1
    assert not any(record[-1] for record in records)
    assert {name: count for name, count in details.items() if name.startswith("write-gap-open-evidence:")} == {
        f"write-gap-open-evidence:{outcome}": 1,
    }
    assert {name: count for name, count in details.items()
            if name.startswith("write-gap-name-change-event:")} == expected_name_change


def test_no_open_writes_partition_by_request_time_and_verified_process_context():
    events = []

    def emit(kind, ticks, pid=7, lifecycle=False, **data):
        events.append({"id": kind, "ticks": ticks, "pid": pid, "lifecycle": lifecycle, "data": data})

    def write(ticks, irp, pid, thread, *, status=0):
        emit(16, ticks, pid=pid, FileObject=51, FileKey=60, Irp=irp, IssuingThreadId=thread)
        emit(24, ticks + 1, Irp=irp, Status=status)

    emit(1, 2, lifecycle=True, ProcessID=7)
    emit(3, 3, lifecycle=True, ProcessID=7, ThreadID=81)
    emit(1, 4, lifecycle=True, ProcessID=8)
    write(9, 1, 4, 81)
    write(10, 2, 7, 82)
    write(12, 3, 8, 81)
    emit(4, 13, lifecycle=True, ProcessID=7, ThreadID=81)
    write(13, 4, 7, 81)
    write(14, 5, 7, 81, status=0xC0000022)
    emit(2, 15, lifecycle=True, ProcessID=8)
    write(15, 6, 8, 0)
    write(16, 7, 9, 83)

    images = {7: "wpr.exe", 8: r"C:\private\unknown.exe", 9: "python.exe"}
    details = Counter()
    unresolved = correlate_requests(
        events, lambda value: value or None, lambda pid, *_: ("other", images.get(pid)),
        lambda value: False, lambda *args: None, strict=True, details=details,
        initial_process_births={9: 0}, thread_bookends={82: 9, 83: 99},
        rundown_window=(10, 12),
    )

    prefix = "write-gap-no-open-context:"
    assert {key.removeprefix(prefix): count for key, count in details.items()
            if key.startswith(prefix)} == {
        "before-wpr-stop:header-system-context:issuer-wpr.exe": 1,
        "during-wpr-stop:header-wpr.exe:issuer-python.exe": 1,
        "during-wpr-stop:header-other-verified-image:issuer-wpr.exe": 1,
        "after-wpr-stop:header-wpr.exe:issuer-unverified": 1,
        "after-wpr-stop:header-unverified:issuer-unverified": 1,
        "after-wpr-stop:header-python.exe:issuer-unverified": 1,
    }
    assert details["write-gap-open-evidence:no-observed-open"] == 6
    assert unresolved["other:write:path-missing"] == 6


@pytest.mark.parametrize(("fault", "expected"), [
    (None, "candidate-outside-protected"),
    ("protected", "candidate-protected"),
    ("missing-key", "missing-file-key"),
    ("later-name", "no-prior-name-in-lifetime"),
    ("name-deleted", "no-prior-name-in-lifetime"),
    ("reset-name", "candidate-outside-protected"),
    ("tied-name-reset", "ambiguous-event-order"),
    ("tied-write", "ambiguous-event-order"),
    ("unmapped", "conflicting-or-unmapped-name"),
    ("alias", "conflicting-or-unmapped-name"),
    ("conflicting-object-key", "conflicting-object-file-key"),
    ("same-object-cleanup", "file-object-lifetime-changed"),
    ("other-object-cleanup", "candidate-outside-protected"),
    ("rename-during-write", "possible-name-change"),
    ("rename-after-completion", "candidate-outside-protected"),
    ("tied-completion", "write-completion-unverified"),
])
def test_no_open_path_evidence_is_diagnostic_only(fault, expected):
    outside, protected = r"c:\outside.bin", r"c:\protected\file.bin"
    events = []

    def emit(kind, ticks, **data):
        events.append({"id": kind, "ticks": ticks, "pid": 7, "lifecycle": False, "data": data})

    path = protected if fault == "protected" else outside
    emit(10, 1, FileKey=60, FileName=protected if fault == "reset-name" else path)
    emit(10, 2 if fault != "later-name" else 12, FileKey=60, FileName=path)
    if fault == "later-name":
        events.pop(0)
    if fault in {"name-deleted", "reset-name", "tied-name-reset"}:
        emit(11, 2 if fault == "tied-name-reset" else 3, FileKey=60)
        if fault == "reset-name":
            emit(10, 4, FileKey=60, FileName=outside)
    if fault in {"alias", "unmapped", "tied-write"}:
        emit(10, 8 if fault == "tied-write" else 4, FileKey=60,
             FileName="" if fault == "unmapped" else protected)
    if fault == "conflicting-object-key":
        emit(14, 5, FileKey=61, FileObject=51)
    if fault in {"same-object-cleanup", "other-object-cleanup"}:
        emit(13, 5, FileKey=60, FileObject=51 if fault == "same-object-cleanup" else 52)
    if fault in {"rename-during-write", "rename-after-completion"}:
        emit(27, 9 if fault == "rename-during-write" else 12, FileKey=60, FileObject=51)
    emit(16, 8, Irp=1, FileObject=51, FileKey=0 if fault == "missing-key" else 60)
    emit(24, 10, Irp=1, Status=0)
    if fault == "tied-completion":
        emit(24, 10, Irp=1, Status=0)

    details = Counter()
    observed = []
    unresolved = correlate_requests(
        events, lambda value: value or None, lambda *_: ("other", None),
        lambda value: value == protected, lambda *args: observed.append(args),
        strict=True, details=details, rundown_window=(6, 11),
    )
    assert unresolved == {"other:write:path-missing": 1, "other:write:process-lifetime-missing": 1}
    assert observed == []
    assert details["write-gap-open-evidence:no-observed-open"] == 1
    prefix = "write-gap-no-open-path:"
    assert {key: count for key, count in details.items() if key.startswith(prefix)} == {
        f"{prefix}during-wpr-stop:header-unverified:issuer-unverified:{expected}": 1,
    }


@pytest.mark.parametrize(("metadata_status", "expected"), [(0, "PASS"), (0xC0000022, "BLOCKED")])
def test_basic_info_control_requires_a_successful_class_4_completion(metadata_status, expected):
    path = r"c:\fixture\metadata.bin"
    control = {"path": path, "pid": 7, "size": 101, "start": 1, "end": 10, "basic_info": True}
    records = [
        (12, {"FileName": path, "FileObject": 51, "Irp": 1}),
        (24, {"Irp": 1, "Status": 0}),
        (17, {"InfoClass": 4, "FileObject": 51, "FileKey": 60, "Irp": 2}),
        (24, {"Irp": 2, "Status": metadata_status}),
        (16, {"FileObject": 51, "FileKey": 60, "Irp": 3, "IOSize": 101, "ByteOffset": 0}),
        (24, {"Irp": 3, "Status": 0}),
    ]
    events = [{"id": kind, "ticks": ticks, "pid": 7, "lifecycle": False, "data": data}
              for ticks, (kind, data) in enumerate(records, 2)]
    report = file_lifetime_report(control, events, {})
    assert report["timestamp_trace"] == expected
    assert report["first_blocking_operation"] == "event-17-info-4"
    assert report["class_4_path_trial"] == {
        "status": expected, "reason": None if expected == "PASS" else "possible-name-change",
    }
    assert report["status"] == "BLOCKED"


@pytest.mark.parametrize(("later_event", "trial_outcome"), [
    (None, "candidate-protected"),
    ("rename", "event-27"),
    ("name-conflict", "conflicting-or-unmapped-name"),
    ("cleanup", "file-object-lifetime-changed"),
    ("tied-completion", "event-17-info-4"),
    ("failed-completion", "event-17-info-4"),
])
def test_class_4_trial_keeps_strict_metadata_and_write_accounting(later_event, trial_outcome):
    path = r"c:\fixture\metadata.bin"
    events = []

    def emit(kind, ticks, pid=7, **data):
        events.append({"id": kind, "ticks": ticks, "pid": pid, "lifecycle": False, "data": data})

    emit(12, 2, FileName=path, FileObject=51, Irp=1)
    emit(24, 3, Irp=1, Status=0, ExtraInformation=1)
    emit(17, 4, InfoClass=4, FileObject=51, FileKey=60, Irp=2)
    emit(24, 8 if later_event == "tied-completion" else 5, Irp=2,
         Status=0xC0000022 if later_event == "failed-completion" else 0)
    if later_event == "rename":
        emit(27, 6, FileObject=52, FileKey=60)
    if later_event == "name-conflict":
        emit(10, 6, FileKey=60, FileName=r"c:\other\different.bin")
    if later_event == "cleanup":
        emit(13, 6, FileObject=51, FileKey=60)
    emit(16, 8, pid=4, FileObject=51, FileKey=60, Irp=3)
    emit(24, 9, Irp=3, Status=0)
    details = Counter()
    records = []
    unresolved = correlate_requests(
        events, lambda value: value or None, lambda *args: ("other", None),
        lambda value: value == path, lambda *args: records.append(args),
        strict=True, details=details, initial_process_births={4: 0, 7: 0},
    )
    assert unresolved["other:write:path-missing"] == 1
    assert details["write-gap-name-change-event:event-17-info-4"] == 1
    assert details[f"write-gap-class-4-trial:{trial_outcome}"] == 1
    assert [record[2] for record in records if record[-1]] == (
        [] if later_event == "failed-completion" else ["unsupported"]
    )


def test_two_handle_fixture_verifies_the_second_handle_after_closing_first(tmp_path, monkeypatch):
    path = tmp_path / "generated.bin"
    handles = []

    def verify(stream, target):
        assert target == path
        assert not stream.closed
        if handles:
            assert handles[0].closed
        handles.append(stream)

    monkeypatch.setattr(n12_etw_probe, "verify_handle_path", verify)
    n12_etw_probe.write_two_handle_control(path)
    assert len(handles) == 2
    assert handles[0] is not handles[1]
    assert all(stream.closed for stream in handles)
    assert path.read_bytes() == b"L" * 97


def test_strict_etw_recovers_preopened_write_from_unique_stable_rundown():
    protected = r"C:\protected\private.txt"
    events = [
        {"id": 1, "pid": 0, "ticks": 1, "lifecycle": True, "data": {"ProcessID": 7}},
        {"id": 16, "pid": 7, "ticks": 2, "lifecycle": False,
         "data": {"FileObject": 9, "FileKey": "0x28", "Irp": 11}},
        {"id": 24, "pid": 0, "ticks": 3, "lifecycle": False, "data": {"Irp": 11, "Status": 0}},
    ]
    completed = []
    unresolved = correlate_requests(
        events, lambda value: value or None,
        lambda pid, birth, ticks: ("app", "app") if pid == 7 and birth == 1 else ("other", None),
        lambda value: value == protected,
        lambda role, identity, operation, source, destination, requested, finished, success:
            completed.append((operation, source, success)),
        strict=True,
        rundown=[{"key": "0x28", "path": protected}, {"key": 40, "path": protected}],
    )
    assert completed == [("write", protected, True)]
    assert unresolved == {}


@pytest.mark.parametrize("transition", [
    "name-create", "name-delete", "open", "close", "rename", "delete", "unsupported",
    "post-window-rename", "conflicting-rundown",
])
def test_strict_etw_rundown_fails_closed_on_ambiguous_key_lifetimes(transition):
    protected = r"C:\protected\private.txt"
    outside = r"C:\outside\private.txt"
    lifecycle = {"id": 1, "pid": 0, "ticks": 1, "lifecycle": True, "data": {"ProcessID": 7}}
    write = {"id": 16, "pid": 7, "ticks": 2, "lifecycle": False,
             "data": {"FileObject": 9, "FileKey": 40, "Irp": 11}}
    completion = {"id": 24, "pid": 0, "ticks": 3, "lifecycle": False,
                  "data": {"Irp": 11, "Status": 0}}
    events = [lifecycle, write, completion]
    guard = list(events)
    rundown = [{"key": 40, "path": protected}]
    if transition == "name-create":
        guard.append({"id": 10, "pid": 0, "ticks": 4, "lifecycle": False,
                      "data": {"FileKey": 40, "FileName": outside}})
    elif transition == "name-delete":
        guard.append({"id": 11, "pid": 0, "ticks": 4, "lifecycle": False,
                      "data": {"FileKey": 40}})
    elif transition == "open":
        guard.append({"id": 12, "pid": 0, "ticks": 4, "lifecycle": False,
                      "data": {"FileObject": 40, "Irp": 12}})
    elif transition == "close":
        guard.append({"id": 14, "pid": 0, "ticks": 4, "lifecycle": False,
                      "data": {"FileObject": 40}})
    elif transition == "rename":
        guard.append({"id": 19, "pid": 0, "ticks": 4, "lifecycle": False,
                      "data": {"FileKey": 40, "FileObject": 40, "Irp": 12}})
    elif transition == "delete":
        guard.append({"id": 18, "pid": 0, "ticks": 4, "lifecycle": False,
                      "data": {"FileKey": 40, "FileObject": 40, "Irp": 12}})
    elif transition == "unsupported":
        guard.append({"id": 17, "pid": 0, "ticks": 4, "lifecycle": False,
                      "data": {"FileKey": 40, "InfoClass": 4, "Irp": 12}})
    elif transition == "post-window-rename":
        guard.append({"id": 19, "pid": 0, "ticks": 40, "lifecycle": False,
                      "data": {"FileKey": 40, "FileObject": 40, "Irp": 12}})
    elif transition == "conflicting-rundown":
        rundown.append({"key": "0x28", "path": outside})

    completed = []
    unresolved = correlate_requests(
        events, lambda value: value or None,
        lambda pid, birth, ticks: ("app", "app") if pid == 7 and birth == 1 else ("other", None),
        lambda value: value == protected,
        lambda role, identity, operation, source, destination, requested, finished, success:
            completed.append((operation, source, success)),
        strict=True, rundown=rundown, rundown_guard_events=guard,
    )
    assert completed == []
    assert unresolved["app:write:path-missing"] == 1


def test_read_native_rundown_requires_manifest_digest_and_decoder(tmp_path):
    rundown_path = tmp_path / "rundown.jsonl"
    entry = {"key": "0x28", "path": r"\Device\HarddiskVolume3\QA\home\cache.sqlite",
             "decoder": "tdh+raw-schema"}
    payload = (json.dumps(entry) + "\n").encode("utf-8")
    rundown_path.write_bytes(payload)
    manifest = {"etw": {
        "start_utc": "2026-11-14T00:00:00Z",
        "rundown_stop_utc": "2026-11-14T00:00:09Z",
        "end_utc": "2026-11-14T00:00:10Z",
        "rundown_sha256": hashlib.sha256(payload).hexdigest(),
    }}
    assert trace.read_rundown_file(rundown_path, manifest) == [
        {"key": 40, "path": entry["path"]}
    ]
    rundown_path.write_bytes(payload.replace(b"cache.sqlite", b"changed.sqlite"))
    with pytest.raises(ValueError, match="FileIO rundown SHA-256 mismatch"):
        trace.read_rundown_file(rundown_path, manifest)


def test_read_native_rundown_rejects_stop_outside_etw_window(tmp_path):
    rundown_path = tmp_path / "rundown.jsonl"
    payload = (json.dumps({"key": "0x28", "path": r"\\Device\\HarddiskVolume3\\QA\\cache.sqlite",
                           "decoder": "tdh+raw-schema"}) + "\\n").encode("utf-8")
    rundown_path.write_bytes(payload)
    manifest = {"etw": {
        "start_utc": "2026-11-14T00:00:00Z",
        "rundown_stop_utc": "2026-11-14T00:00:11Z",
        "end_utc": "2026-11-14T00:00:10Z",
        "rundown_sha256": hashlib.sha256(payload).hexdigest(),
    }}
    with pytest.raises(ValueError, match="within the ETW capture window"):
        trace.read_rundown_file(rundown_path, manifest)


def test_process_bookends_reject_pid_reuse_and_traced_lifetimes():
    before = [{"pid": pid, "birth_ticks": 10, "name": f"process-{pid}.exe"} for pid in (7, 8, 9, 10)]
    after = [{"pid": 7, "birth_ticks": 10, "name": "process-7.exe"},
             {"pid": 8, "birth_ticks": 30, "name": "process-8.exe"}, before[2]]
    records = trace.stable_process_bookend_records({"before": before, "after": after}, 20, {9})
    assert records == {7: {"birth_ticks": 10, "name": "process-7.exe"}}
    assert trace.stable_process_bookends({"before": before, "after": after}, 20, {9}) == {7}
    with pytest.raises(ValueError, match="duplicate process bookend"):
        trace.stable_process_bookends({"before": before, "after": after + [after[0]]}, 20, {9})


def test_thread_bookends_exclude_reused_and_ambiguous_ids():
    before = [{"tid": tid, "pid": 7, "birth_ticks": 10} for tid in (70, 71, 72, 73, 74)]
    after = [before[0], dict(before[1], birth_ticks=25), before[2], before[3], before[3]]
    bookends = {"threads_before": before, "threads_after": after}
    assert trace.stable_thread_bookends(bookends, 20, {7}, {72}) == {70: 7}
    assert trace.stable_thread_bookends(bookends, 20, {8}, {72}) == {}


@pytest.mark.parametrize(("value", "expected"), [
    ("0x203", "set"), ("514", "set"), (0x201, "clear"), (0, "clear"),
    (None, "unavailable"), ("malformed", "unavailable"), (True, "unavailable"),
    (-1, "unavailable"), (0x100000002, "unavailable"),
])
def test_system_write_paging_flag_only_decodes_valid_uint32_values(value, expected):
    assert write_paging_flag({"IOFlags": value}) == expected


@pytest.mark.parametrize(("fault", "identity_evidence"), [
    (None, "completed-open-and-read"),
    ("missing-read", "read-unverified"),
    ("failed-open", "existing-file-open-completion-unverified"),
    ("wrong-file-object", "read-unverified"),
    ("object-reuse", "file-object-lifetime-changed"),
    ("cleanup", "file-object-lifetime-changed"),
    ("conflicting-key", "conflicting-file-key"),
    ("name-delete", "possible-name-change"),
    ("conflicting-name", "conflicting-or-unmapped-name"),
    ("conflicting-rundown-name", "conflicting-rundown-name"),
])
def test_system_control_timing_tracks_only_matching_successful_requests(fault, identity_evidence):
    protected = r"C:\protected\private.bin"
    outside = r"C:\outside.bin"
    untouched = r"C:\protected\private-untouched.bin"
    capture = {
        "device": r"\Device\HarddiskVolume3", "protected_root": r"C:\protected",
        "start_ticks": 1, "end_ticks": 3_000_000,
        "rundown_start_ticks": 1_500_000, "rundown_stop_ticks": 2_500_000,
        "preopened": {"pid": 7, "tid": 71, "untouched": {
            "path": untouched, "size": 22, "open_window": [10, 30], "read_window": [40, 60],
        }, "writes": {
            "protected": {"path": protected, "size": 53, "start": 100, "end": 300,
                          "flush_window": [400_000, 500_000]},
            "outside": {"path": outside, "size": 79, "start": 150_000, "end": 250_000},
        }},
    }
    rundown = [{"key": key, "path": path}
               for key, path in ((40, protected), (41, outside), (42, untouched))]
    events = []

    def emit(kind, ticks, pid=4, **data):
        events.append({"id": kind, "ticks": ticks, "pid": pid, "lifecycle": False, "data": data})

    def request(kind, ticks, completed, irp, key, obj, pid=4, status=0, **data):
        emit(kind, ticks, pid, Irp=irp, FileKey=key, FileObject=obj, **data)
        emit(24, completed, Irp=irp, Status=status)

    emit(12, 20, 7, Irp=11, FileObject=420, FileName=untouched, ThreadId=71)
    emit(24, 25, Irp=11, Status=0xC0000022 if fault == "failed-open" else 0, ExtraInformation=1)
    if fault != "missing-read":
        request(15, 45, 50, 12, 42, 421 if fault == "wrong-file-object" else 420,
                pid=7, IOSize=22, ByteOffset=0, IssuingThreadId=71)
    request(16, 150, 160, 1, 40, 400, pid=7, IOSize=53, ByteOffset=0, IssuingThreadId=71)
    request(16, 200_000, 200_001, 2, 41, 410, pid=7, IOSize=79, ByteOffset=0, IssuingThreadId=71)
    request(21, 400_000, 500_000, 3, 40, 400, pid=7, ThreadId=71)
    request(16, 450_000, 460_000, 4, 40, 400, IOFlags=0x203)
    request(17, 499_999, 500_001, 5, 40, 400, InfoClass=20)
    request(17, 480_000, 490_000, 6, 40, 400, InfoClass=4)
    request(16, 480_000, 490_000, 7, 40, 401)
    request(16, 480_000, 490_000, 8, 40, 400, status=0xC0000022, IOFlags=0x203)
    request(16, 1_500_000, 2_500_000, 9, 42, 420, IOFlags=0x203)
    request(17, 2_500_001, 2_500_002, 10, 41, 410, InfoClass=20)
    request(16, 2_500_003, 2_500_004, 13, 41, 410, IOFlags=0x201)
    request(16, 2_500_005, 2_500_006, 14, 41, 410)
    emit(24, 460_000, Irp=4, Status=0)  # Tied completion is ambiguous.

    if fault == "object-reuse":
        emit(12, 1_600_000, 8, FileObject=420, FileName=outside)
    elif fault == "cleanup":
        emit(13, 1_600_000, FileKey=42, FileObject=420)
    elif fault == "conflicting-key":
        emit(16, 1_600_000, FileKey=43, FileObject=420)
    elif fault == "name-delete":
        emit(11, 1_600_000, FileKey=42)
    elif fault == "conflicting-name":
        emit(10, 1_600_000, FileKey=42, FileName=outside)
    elif fault == "conflicting-rundown-name":
        rundown.append({"key": 42, "path": outside})

    result = preopened_report(capture, events, rundown)["control_write_timing"]
    assert result == {
        "protected": {
            "identity": "file-key-and-object", "explicit_flush_trace": "confirmed",
            "system_successful_operations": {"resize:explicit-flush:after-flush-before-wpr-stop": 1},
            "system_successful_write_paging_flags": {},
            "system_requests_without_verified_success": 2,
        },
        "outside": {
            "identity": "file-key-and-object",
            "system_successful_operations": {"resize:after-wpr-stop:after-wpr-stop": 1,
                                             "write:after-wpr-stop:after-wpr-stop": 2},
            "system_successful_write_paging_flags": {"after-wpr-stop:clear": 1,
                                                     "after-wpr-stop:unavailable": 1},
            "system_requests_without_verified_success": 0,
        },
        "untouched": {
            "identity": "file-key-and-object" if fault is None else "unverified",
            "identity_evidence": identity_evidence,
            "system_successful_operations": {"write:during-wpr-stop:during-wpr-stop": 1}
            if fault is None else {},
            "system_successful_write_paging_flags": {"during-wpr-stop:set": 1} if fault is None else {},
            "system_requests_without_verified_success": 0,
        },
    }
    assert "private" not in json.dumps(result)

    if fault is None:
        without_comparison_name = [row for row in rundown if row["key"] != 42]
        assert preopened_report(capture, events, without_comparison_name)["control_write_timing"] == result


@pytest.mark.parametrize(("fault", "expected"), [
    (None, "matches-handle-path"),
    ("wrong-path", "different-from-handle-path"),
    ("no-name", "no-prior-name-in-lifetime"),
    ("same-object-open", "same-object-open-observed"),
    ("tied-completion", "write-completion-unverified"),
    ("wrong-thread", "control-request-unverified"),
    ("failed-completion", "control-request-unverified"),
    ("rundown-missing-key", "matches-handle-path"),
    ("rename-after-completion", "matches-handle-path"),
    ("rename-before-request", "possible-name-change"),
    ("rename-during-request", "possible-name-change"),
    ("key-reused-with-new-lifetime", "matches-handle-path"),
    ("key-reused-with-conflicting-name", "conflicting-or-unmapped-name"),
    ("key-reuse-during-request", "possible-name-change"),
    ("same-object-key-reused", "conflicting-object-file-key"),
])
def test_preopened_path_validation_compares_exact_paths(fault, expected):
    protected, outside = r"C:\protected\private.bin", r"C:\outside.bin"
    old_path = r"C:\outside\previous-name.bin"
    capture = {"device": r"\Device\HarddiskVolume3", "protected_root": r"C:\protected",
               "preopened": {"pid": 7, "tid": 71, "writes": {
                   "protected": {"path": protected, "size": 53, "start": 100, "end": 200},
                   "outside": {"path": outside, "size": 79, "start": 300, "end": 400},
               }}}
    events = []

    def emit(kind, ticks, **data):
        events.append({"id": kind, "ticks": ticks, "pid": 7, "lifecycle": False, "data": data})

    emit(12, 20, FileObject=41 if fault == "same-object-open" else 90, FileName=protected)
    if fault != "no-name":
        fixture_name = r"C:\protected\alias.bin" if fault == "wrong-path" else protected
        emit(10, 30, FileKey=40, FileName=fixture_name)
    if fault in {"key-reused-with-new-lifetime", "key-reused-with-conflicting-name"}:
        emit(10, 25, FileKey=40, FileName=old_path)
        if fault == "key-reused-with-new-lifetime":
            emit(11, 27, FileKey=40)
    if fault == "key-reuse-during-request":
        emit(11, 153, FileKey=40)
        emit(10, 154, FileKey=40, FileName=old_path)
    if fault == "same-object-key-reused":
        emit(14, 40, FileKey=39, FileObject=41)
    rename_ticks = {"rename-before-request": 145, "rename-during-request": 155,
                    "rename-after-completion": 165}
    if fault in rename_ticks:
        emit(27, rename_ticks[fault], FileKey=40, FileObject=41)
    emit(10, 31, FileKey=50, FileName=outside)
    emit(16, 150, Irp=1, FileKey=40, FileObject=41, IOSize=53, ByteOffset=0,
         IssuingThreadId=72 if fault == "wrong-thread" else 71)
    emit(24, 160, Irp=1, Status=0xC0000022 if fault == "failed-completion" else 0)
    if fault == "tied-completion":
        emit(24, 160, Irp=1, Status=0)
    emit(16, 350, Irp=2, FileKey=50, FileObject=51, IOSize=79, ByteOffset=0, IssuingThreadId=71)
    emit(24, 370, Irp=2, Status=0)
    rundown = [{"key": 50, "path": outside}]
    if fault != "rundown-missing-key":
        later_path = old_path if fault == "rename-after-completion" else protected
        rundown.append({"key": 40, "path": later_path})

    for report in (preopened_report(capture, events), preopened_report(capture, events, rundown)):
        assert report["preopened_path_validation"] == {"protected": expected, "outside": "matches-handle-path"}
        assert "private.bin" not in json.dumps(report)
    if fault == "rename-after-completion":
        assert report["targets"]["protected"]["rundown_name"] == "conflicting-or-different"
    if fault == "rundown-missing-key":
        assert report["targets"]["protected"]["rundown_name"] == "unavailable"


def test_preopened_control_requires_completion_and_does_not_infer_names():
    protected, outside = r"C:\protected\private.bin", r"C:\outside.bin"
    capture = {"device": r"\Device\HarddiskVolume3", "protected_root": r"C:\protected",
               "preopened": {"pid": 7, "tid": 71, "writes": {
                   "protected": {"path": protected, "size": 53, "start": 100, "end": 200},
                   "outside": {"path": outside, "size": 79, "start": 300, "end": 400}}}}

    def event(kind, ticks, **data):
        return {"id": kind, "pid": 7, "ticks": ticks, "lifecycle": False, "data": data}

    events = [
        event(10, 90, FileKey=40, FileName=protected),
        event(16, 150, Irp=1, FileKey=40, FileObject=400, IOSize=53, ByteOffset=0, IssuingThreadId=71),
        event(24, 160, Irp=1, Status=0),
        event(16, 350, Irp=2, FileKey=41, FileObject=410, IOSize=79, ByteOffset=0, IssuingThreadId=71),
        event(16, 360, Irp=2, FileKey=41, IOSize=12, ByteOffset=0),
        event(24, 370, Irp=2, Status=0),
        event(10, 380, FileKey=41, FileName=outside),
    ]
    file_keys, file_objects = {}, {}
    targets = preopened_report(capture, events, file_keys=file_keys, file_objects=file_objects)["targets"]
    assert file_keys == {"protected": 40, "outside": 41}
    assert file_objects == {"protected": 400, "outside": 410}
    assert targets["protected"] == {"request_candidates": 1, "completion": "success",
                                    "issuing_thread": "matches", "name_evidence": "matches-target"}
    assert targets["outside"] == {"request_candidates": 1, "completion": "unverified",
                                  "issuing_thread": "matches", "name_evidence": "unavailable"}
    assert "private.bin" not in json.dumps(targets)
    events.append(event(10, 91, FileKey=40, FileName=outside))
    assert preopened_report(capture, events)["targets"]["protected"]["name_evidence"] == "conflicting-or-different"
    rundown = [{"key": "0x28", "path": protected}, {"key": "41", "path": outside},
               {"key": "41", "path": protected}]
    report = preopened_report(capture, events, rundown)
    assert report["rundown_keys"] == 2
    assert report["targets"]["protected"]["rundown_name"] == "matches-target"
    assert report["targets"]["outside"]["rundown_name"] == "conflicting-or-different"
    assert report["targets"]["outside"]["completion"] == "unverified"
    assert "private.bin" not in json.dumps(report)


def test_trace_report_decodes_only_classic_rundown_names(tmp_path, capsys):
    source = tmp_path / "trace.xml"
    source.write_text(
        '<Events><Event xmlns="http://schemas.microsoft.com/win/2004/08/events/event">'
        '<System><Provider Guid="{90CBDC39-4A3E-11D1-84F4-0000F80464E3}"/>'
        '<Opcode>36</Opcode></System><EventData><Data Name="FileObject">0x28</Data>'
        '<Data Name="FileName">private-path</Data></EventData></Event></Events>',
        encoding="utf-8",
    )
    target = tmp_path / "names.jsonl"
    decode_rundown_report(source, target)
    assert json.loads(target.read_text(encoding="utf-8")) == {"key": 40, "path": "private-path"}
    assert capsys.readouterr().out.endswith('{"opcode_36": 1, "decoded_names": 1}\n')


BASE = "2026-11-13"
PYTHON = r"C:\Runtime\python.exe"
APP = r"C:\Build\pilotodin-desktop.exe"
WEBVIEW = r"C:\Runtime\msedgewebview2.exe"
FIXTURE = r"C:\QA\fixture.csv"
PROTECTED = r"C:\Original\PilotODIN"
FIELDNAMES = ["Time of Day", "PID", "Operation", "Path", "Result", "Detail", "Process Name"]


def instant(second):
    return f"{BASE}T00:00:{second:02}+00:00"


@pytest.mark.parametrize(("fault", "reason"), [
    (None, "N12 ETW export passed validation: 1 events."),
    ("digest", "ETW export digest mismatch"),
    ("outside-capture", "ETW event timestamp outside capture"),
    ("wrong-timestamp-type", "ETW event timestamp outside capture"),
    ("wrong-envelope", "invalid ETW event envelope"),
    ("truncated", "ETW event stream: JSONDecodeError"),
    ("empty", "ETW event export is empty"),
    ("lost", "ETW reported event or buffer loss"),
    ("missing-device", "ETW volume mappings are missing"),
])
def test_windows_etw_export_preflight(tmp_path, fault, reason):
    event = {"ticks": trace.utc_ticks(trace.utc_time(instant(1))),
             "id": 24, "pid": None, "lifecycle": False, "data": {"Status": "0x0"}}
    if fault == "outside-capture":
        event["ticks"] = trace.utc_ticks(trace.utc_time(instant(3)))
    if fault == "wrong-timestamp-type":
        event["ticks"] = str(event["ticks"])
    if fault == "wrong-envelope":
        event["data"] = "private-event-field"
    payload = (json.dumps(event) + "\n").encode()
    if fault == "truncated":
        payload = b'{"private-event-field":'
    if fault == "empty":
        payload = b""
    events = tmp_path / "private-etw.jsonl"
    events.write_bytes(payload)
    start, end = (instant(second).replace("+00:00", ".0000000Z") for second in (0, 2))
    manifest = {
        "start_utc": start, "end_utc": end,
        "etw": {"schema_version": 1, "start_utc": start, "end_utc": end,
                "events_sha256": "0" * 64 if fault == "digest" else hashlib.sha256(payload).hexdigest(),
                "volume_devices": {} if fault == "missing-device" else {"C:": r"\Device\HarddiskVolume3"},
                "counters": {"events_lost": int(fault == "lost"), "log_buffers_lost": 0,
                             "realtime_buffers_lost": 0, "buffers_written": 1}},
    }
    source = tmp_path / "private-manifest.json"
    source.write_text(json.dumps(manifest), encoding="utf-8-sig")
    result = subprocess.run([sys.executable, trace.__file__, "check-etw-export", str(source), str(events)],
                            capture_output=True, text=True, check=False)
    if fault is None:
        assert result.returncode == 0, result.stderr
        assert result.stdout.strip() == reason
    else:
        assert result.returncode == 2
        assert not result.stdout
        assert reason in result.stderr
        assert "private-" not in result.stderr


class Evidence:
    def __init__(self):
        self.events = []
        self.files = []
        self.manifest = {
            "schema_version": 1, "disposable": True,
            "source_sha": "f" * 40, "executable_sha256": "e" * 64,
            "start_utc": instant(0), "end_utc": instant(59),
            "markers": dict(zip(trace.MINIMUM_MARKERS, map(instant, [13, 18, 25, 30, 36, 45]))),
            "sysmon_first_record": 100,
            "procmon_all_events": True, "procmon_loss_reviewed": True, "procmon_clock_utc": True,
            "loopback_ports": [8000, 9001, 9002],
            "protected_roots": {"original": PROTECTED},
            "observed_roots": {"fixture": FIXTURE, "test-home": r"C:\QA\home"},
            "immutable_observed": ["fixture"],
            "permitted_writes": {
                "app": [r"C:\QA\home"], "backend": [r"C:\QA\home"],
                "webview": [r"C:\QA\home"], "webview-network": [r"C:\QA\home"],
                "calibration": [r"C:\QA\calibration"],
            },
            "processes": [{"role": role, "pid": pid, "image": image} for role, pid, image in (
                ("app", 1, APP), ("app", 2, APP), ("backend", 10, PYTHON), ("driver", 20, PYTHON))],
        }
        self.before = {
            key: {label: {"root_id": hashlib.sha256(trace.windows_path(path).encode()).hexdigest(),
                          "state": "file" if label == "fixture" else "directory", "digest": "1" * 64}
                  for label, path in self.manifest[f"{key}_roots"].items()}
            for key in ("protected", "observed")
        }
        self.after = json.loads(json.dumps(self.before))
        self.birth(14, 10, "backend", PYTHON)
        self.birth(19, 1, "app1", APP)
        self.birth(20, 3, "web1", WEBVIEW, "app1")
        self.birth(21, 4, "net1", WEBVIEW, "web1",
                   command="msedgewebview2.exe --utility-sub-type=network.mojom.NetworkService")
        self.birth(24, 20, "driver", PYTHON)
        self.end(29, "driver")
        self.end(31, "net1")
        self.end(32, "web1")
        self.end(33, "app1")
        self.birth(37, 2, "app2", APP)
        self.birth(38, 3, "web2", WEBVIEW, "app2")
        self.birth(39, 4, "net2", WEBVIEW, "web2",
                   command="msedgewebview2.exe --utility-sub-type=network.mojom.NetworkService")
        self.end(46, "net2")
        self.end(47, "web2")
        self.end(48, "app2")
        self.end(49, "backend")
        self.connect(23, "net1", "127.0.0.1", 8000)
        self.write(27, 3, "WriteFile", r"C:\QA\home\wv-cache", exe="msedgewebview2.exe")
        self.write(28, 10, "WriteFile", r"C:\QA\home\data.sqlite")
        self.calibration(1, 30, 9001)
        self.calibration(50, 40, 9002)

    def birth(self, second, pid, guid, image, parent="", command=""):
        self.events.append((second, 1, {"ProcessGuid": guid, "ParentProcessGuid": parent,
                                        "ProcessId": str(pid), "Image": image, "CommandLine": command,
                                        "Hashes": "SHA256=" + "E" * 64}))

    def end(self, second, guid):
        birth = next(fields for _, kind, fields in self.events
                     if kind == 1 and fields["ProcessGuid"] == guid)
        self.events.append((second, 5, {key: birth[key] for key in ("ProcessGuid", "ProcessId", "Image")}))

    def connect(self, second, guid, ip, port, protocol="tcp", initiated=True, pid=None):
        if pid is None:
            pid = next(fields["ProcessId"] for _, kind, fields in self.events
                       if kind == 1 and fields["ProcessGuid"] == guid)
        self.events.append((second, 3, {"ProcessGuid": guid, "ProcessId": str(pid), "Protocol": protocol,
                                        "Initiated": str(initiated).lower(), "DestinationIp": ip,
                                        "DestinationPort": str(port), "SourcePort": "53000"}))

    def write(self, second, pid, operation, path, detail="", exe="python.exe", result="SUCCESS"):
        self.files.append([f"00:00:{second:02}.1234567", str(pid), operation, path, result, detail, exe])

    def calibration(self, second, pid, port):
        parent, child = f"parent{pid}", f"child{pid}"
        original, renamed = rf"C:\QA\calibration\{pid}\marker", rf"C:\QA\calibration\{pid}\renamed"
        self.manifest["processes"].append({"role": "calibration", "pid": pid, "image": PYTHON,
                                           "fixture": original, "renamed_fixture": renamed, "port": port})
        self.birth(second, pid, parent, PYTHON)
        self.birth(second + 1, pid + 1, child, PYTHON, parent)
        self.write(second + 2, pid + 1, "CreateFile", original, "OpenResult: Created")
        self.write(second + 2, pid + 1, "WriteFile", original)
        self.write(second + 2, pid + 1, "SetEndOfFileInformationFile", original)
        self.write(second + 2, pid + 1, "SetRenameInformationFile", original, f"FileName: {renamed}")
        self.write(second + 2, pid + 1, "SetDispositionInformationFile", renamed, "Delete: True")
        self.connect(second + 3, child, "127.0.0.1", port)
        self.connect(second + 3, child, "::ffff:127.0.0.1", port, "udp")
        self.end(second + 4, child)
        self.end(second + 5, parent)

    def save(self, path, *, omit_record=None):
        sysmon = path / "sysmon.xml"
        procmon = path / "procmon.csv"
        root = ET.Element("Events")
        for record, (second, kind, fields) in enumerate(sorted(self.events, key=lambda e: e[0]), 100):
            if record == omit_record:
                continue
            event = ET.SubElement(root, trace.EVENT_NS + "Event")
            system = ET.SubElement(event, trace.EVENT_NS + "System")
            ET.SubElement(system, trace.EVENT_NS + "EventID").text = str(kind)
            ET.SubElement(system, trace.EVENT_NS + "EventRecordID").text = str(record)
            ET.SubElement(system, trace.EVENT_NS + "TimeCreated", SystemTime=instant(second))
            data = ET.SubElement(event, trace.EVENT_NS + "EventData")
            fields = {"UtcTime": f"{BASE} 00:00:{second:02}.000", **fields}
            for key, value in fields.items():
                ET.SubElement(data, trace.EVENT_NS + "Data", Name=key).text = value
        ET.ElementTree(root).write(sysmon, encoding="utf-8")
        self.manifest["sysmon_last_record"] = record
        with procmon.open("w", encoding="utf-8-sig", newline="") as stream:
            writer = csv.writer(stream)
            writer.writerow(FIELDNAMES)
            writer.writerows(self.files)
        return sysmon, procmon

    def report(self, path, **kwargs):
        return trace.audit(self.manifest, *self.save(path, **kwargs), self.before, self.after)


def test_calibrated_trace_reports_scoped_results_and_keeps_history(tmp_path):
    report = Evidence().report(tmp_path)
    assert report["coverage"] == "CALIBRATED"
    assert report["network"] == report["filesystem"] == "PASS_SCOPED"
    assert report["historical_port_443_disposition"] == "UNATTRIBUTED"
    assert report["native_n12_accepted"] is False
    assert report["process_roles"]["webview-network"] == 2
    assert report["file_events"]["calibration:resize"] == 2
    assert report["unresolved_file_paths"] == []


def test_sysmon_observations_require_calibration_and_feed_combined_audit(tmp_path):
    evidence = Evidence()
    evidence.connect(40, "net2", "203.0.113.23", 443, "udp")
    evidence.events = [event for event in evidence.events if not
                       (event[2].get("ProcessGuid") == "child30" and event[2].get("Protocol") == "udp")]
    sysmon, procmon = evidence.save(tmp_path)
    endpoints, launches = [], {}
    observed = trace.inspect_journey_sysmon(evidence.manifest, sysmon, private_endpoints=endpoints,
                                            private_app_launches=launches)
    assert observed.issues == {"calibration-tcp-or-udp-missing"}
    assert observed.network_counts["webview-network:udp:non-loopback"] == 1
    assert len(endpoints) == 1 and launches[endpoints[0]["process_guid"]] == "relaunch"
    assert "203.0.113.23" not in json.dumps(observed.unexpected_connections)
    result = trace.complete_journey_audit(evidence.manifest, observed, procmon, evidence.before, evidence.after)
    assert result["coverage"] == "BLOCKED" and result["filesystem"] == "BLOCKED"
    assert result["unexpected_connections"] == observed.unexpected_connections
    assert result == trace.audit(evidence.manifest, sysmon, procmon, evidence.before, evidence.after)


def test_identical_sysmon_exit_payloads_preserve_the_audit(tmp_path):
    evidence = Evidence()
    baseline = evidence.report(tmp_path)
    evidence.end(33, "app1")
    evidence.end(46, "net2")
    sysmon, procmon = evidence.save(tmp_path)
    tree = ET.parse(sysmon)
    replay = [event for event in tree.getroot() if
              event.findtext(f"{trace.EVENT_NS}System/{trace.EVENT_NS}EventID") == "5" and
              event.findtext(f"{trace.EVENT_NS}EventData/{trace.EVENT_NS}Data[@Name='ProcessGuid']") == "app1"]
    replay[-1].find(f"{trace.EVENT_NS}System/{trace.EVENT_NS}TimeCreated").set("SystemTime", instant(34))
    tree.write(sysmon, encoding="utf-8")
    report = trace.audit(evidence.manifest, sysmon, procmon, evidence.before, evidence.after)
    assert report == dict(baseline, sysmon_repeated_process_exits=2)


@pytest.mark.parametrize("prefix", ["\\\\?\\", "\\??\\"])
def test_sysmon_drive_aliases_preserve_full_image_identity(tmp_path, prefix):
    evidence = Evidence()
    baseline = evidence.report(tmp_path)
    fields = next(fields for _, kind, fields in evidence.events if kind == 1 and fields["ProcessGuid"] == "app1")
    fields["Image"] = prefix + APP
    assert evidence.report(tmp_path) == baseline

    exit_fields = next(fields for _, kind, fields in evidence.events
                       if kind == 5 and fields["ProcessGuid"] == "app1")
    exit_fields["Image"] = prefix + r"C:\unrelated\pilotodin.exe"
    with pytest.raises(trace.EvidenceValidationError, match="process exit image disagrees with birth"):
        evidence.report(tmp_path)


@pytest.mark.parametrize(("event_id", "image", "category"), [
    (1, None, "missing"),
    (1, "", "empty"),
    (1, r"\\server\share\private.exe", "unc"),
    (1, r"\Device\HarddiskVolume3\private.exe", "device-or-extended"),
    (1, r"C:private.exe", "drive-relative"),
    (1, "private.exe", "executable-basename"),
    (5, "-", "dash-placeholder"),
    (5, " <unknown> ", "text-placeholder"),
    (5, "  PILOTODIN-DESKTOP.EXE  ", "basename-matches-birth"),
    (5, "private.exe", "basename-differs-from-birth"),
    (5, r"private-bin\pilotodin-desktop.exe", "relative-path"),
    (5, "private-bin/pilotodin-desktop.exe", "relative-path"),
    (5, r'"C:\Build\pilotodin-desktop.exe"', "quoted-image"),
    (5, "private-opaque-value", "relative-or-unrecognized"),
    (5, r"\\?\C:\private\..\private.exe", "device-or-extended"),
    (5, r"\\?\GLOBALROOT\Device\private.exe", "device-or-extended"),
])
def test_invalid_sysmon_image_reports_record_and_form_without_raw_path(tmp_path, event_id, image, category):
    evidence = Evidence()
    events = sorted(evidence.events, key=lambda event: event[0])
    record, fields = next((record, fields) for record, (_, kind, fields) in enumerate(events, 100)
                          if kind == event_id and fields["ProcessGuid"] == "app1")
    if image is None:
        del fields["Image"]
    else:
        fields["Image"] = image
    with pytest.raises(trace.EvidenceValidationError) as rejected:
        evidence.report(tmp_path)
    assert str(rejected.value) == f"Sysmon XML: invalid process Image (event {event_id}, record {record}, {category})"


@pytest.mark.parametrize("later_findings", [False, True])
def test_diagnostic_audit_keeps_an_unsupported_exit_unverified(tmp_path, later_findings):
    evidence = Evidence()
    evidence.end(33, "app1")
    for _, kind, fields in evidence.events:
        if kind == 5 and fields["ProcessGuid"] == "app1":
            fields["Image"] = "private opaque\tPILOTODIN-DESKTOP.EXE"
    if later_findings:
        evidence.write(42, 2, "WriteFile", PROTECTED + r"\private.csv", exe="pilotodin-desktop.exe")
        evidence.connect(43, "net2", "127.0.0.1", 9443)
    sysmon, procmon = evidence.save(tmp_path)
    rejected = []
    report = trace.audit(evidence.manifest, sysmon, procmon, evidence.before, evidence.after,
                         rejected_sysmon_exits=rejected)
    assert report["coverage"] == "BLOCKED"
    assert report["trace_verdict_scope"] == "diagnostic-only-unverified-sysmon-exit"
    assert {"sysmon-exit-image-unverified", "process-exit-missing",
            "app-lifecycle-does-not-match-journey"} <= set(report["coverage_issues"])
    assert report["sysmon_repeated_process_exits"] == 0
    assert report["protected_snapshot_comparison"] == "MATCH"
    assert report["native_n12_accepted"] is False
    assert report["filesystem"] == report["network"] == ("FAIL" if later_findings else "BLOCKED")
    assert len(rejected) == 2
    assert all(item == {"record": item["record"], "category": "basename-differs-from-birth",
                        "has_whitespace": True, "has_control": True,
                        "ends_with_birth_basename": True} for item in rejected)


def test_diagnostic_audit_refuses_a_conflicting_retry_of_an_unsupported_exit(tmp_path):
    evidence = Evidence()
    exit_fields = next(fields for _, kind, fields in evidence.events if kind == 5
                       and fields["ProcessGuid"] == "app1")
    exit_fields["Image"] = "private-opaque-value"
    evidence.end(33, "app1")
    sysmon, procmon = evidence.save(tmp_path)
    with pytest.raises(trace.EvidenceValidationError, match="conflicting process exit payloads"):
        trace.audit(evidence.manifest, sysmon, procmon, evidence.before, evidence.after,
                    rejected_sysmon_exits=[])


@pytest.mark.parametrize(("field", "value", "message"), [
    ("UtcTime", f"{BASE} 00:00:34.001", "conflicting process exit timestamps"),
    ("ProcessId", "999", "process exit PID disagrees with birth"),
    ("Image", r"C:\Private\another.exe", "process exit image disagrees with birth"),
    ("User", r"PRIVATE\account", "conflicting process exit payloads"),
])
def test_conflicting_sysmon_exit_payloads_still_block_audit(tmp_path, field, value, message):
    evidence = Evidence()
    evidence.end(33, "app1")
    evidence.events[-1][2][field] = value
    with pytest.raises(trace.EvidenceValidationError, match=f"^Sysmon XML: {message}$"):
        evidence.report(tmp_path)


def test_identical_sysmon_exit_cannot_reuse_a_channel_record_id(tmp_path):
    evidence = Evidence()
    evidence.end(33, "app1")
    sysmon, procmon = evidence.save(tmp_path)
    tree = ET.parse(sysmon)
    first, repeated = [event.find(f"{trace.EVENT_NS}System/{trace.EVENT_NS}EventRecordID")
                       for event in tree.getroot()
                       if event.findtext(f"{trace.EVENT_NS}System/{trace.EVENT_NS}EventID") == "5" and
                       event.findtext(f"{trace.EVENT_NS}EventData/{trace.EVENT_NS}Data[@Name='ProcessGuid']") == "app1"]
    repeated.text = first.text
    tree.write(sysmon, encoding="utf-8")
    with pytest.raises(trace.EvidenceValidationError, match="Sysmon export must be in ascending record order"):
        trace.audit(evidence.manifest, sysmon, procmon, evidence.before, evidence.after)


def test_sysmon_exit_cannot_precede_birth(tmp_path):
    evidence = Evidence()
    evidence.end(33, "app1")
    evidence.events[-1][2]["UtcTime"] = f"{BASE} 00:00:17.999"
    with pytest.raises(trace.EvidenceValidationError, match="process exit precedes birth"):
        evidence.report(tmp_path)
    sysmon, procmon = evidence.save(tmp_path)
    with pytest.raises(trace.EvidenceValidationError, match="conflicting process exit timestamps"):
        trace.audit(evidence.manifest, sysmon, procmon, evidence.before, evidence.after,
                    rejected_sysmon_exits=[])
    evidence.events.pop()
    first_exit = next(fields for _, kind, fields in evidence.events
                      if kind == 5 and fields["ProcessGuid"] == "app1")
    first_exit["UtcTime"] = f"{BASE} 00:00:17.999"
    sysmon, procmon = evidence.save(tmp_path)
    rejected = []
    result = trace.audit(evidence.manifest, sysmon, procmon, evidence.before, evidence.after,
                         rejected_sysmon_exits=rejected)
    assert result["trace_verdict_scope"] == "diagnostic-only-unverified-sysmon-exit"
    assert result["coverage"] == result["filesystem"] == result["network"] == "BLOCKED"
    assert {"sysmon-exit-time-unverified", "process-exit-missing"} <= set(result["coverage_issues"])
    assert rejected == [{"record": rejected[0]["record"], "category": "exit-before-birth",
                         "exit_minus_birth_ticks": -10_010_000}]


def test_sysmon_exit_with_repeated_payload_field_is_blocked(tmp_path):
    evidence = Evidence()
    sysmon, procmon = evidence.save(tmp_path)
    tree = ET.parse(sysmon)
    exit_data = next(event.find(trace.EVENT_NS + "EventData") for event in tree.getroot()
                     if event.findtext(f"{trace.EVENT_NS}System/{trace.EVENT_NS}EventID") == "5")
    ET.SubElement(exit_data, trace.EVENT_NS + "Data", Name="ProcessId").text = "999"
    tree.write(sysmon, encoding="utf-8")
    with pytest.raises(trace.EvidenceValidationError, match="ambiguous process exit fields"):
        trace.audit(evidence.manifest, sysmon, procmon, evidence.before, evidence.after)


def test_etw_audit_combines_sysmon_and_filesystem_evidence(tmp_path):
    evidence = Evidence()
    evidence.manifest.pop("procmon_loss_reviewed")
    sysmon, _ = evidence.save(tmp_path)
    etw_path = tmp_path / "etw.jsonl"
    rows = []
    request = 0

    def emit(second, pid, event_id, *, lifecycle=False, **data):
        rows.append(dict(ticks=trace.utc_ticks(trace.utc_time(instant(second))) + len(rows),
                         pid=pid, id=event_id, lifecycle=lifecycle, data=data))

    def mutation(second, pid, obj, kind, **fields):
        nonlocal request
        request += 1
        destination = fields.pop("Destination", None)
        outcome = fields.pop("Outcome", None)
        emit(second, pid, kind, FileObject=obj, Irp=request, **fields)
        if destination:
            emit(second, pid, 27, FileObject=obj, Irp=request, FilePath=destination)
        completion = {} if outcome is None else {"ExtraInformation": outcome}
        emit(second, 0, 24, Irp=request, Status=0, **completion)

    for pid, second in ((31, 2), (41, 51)):
        root = next(p for p in evidence.manifest["processes"] if p.get("pid") == pid - 1)
        emit(second, 0, 1, lifecycle=True, ProcessID=pid)
        mutation(second + 1, pid, 8, 12, FileName="\\??\\" + root["fixture"], Outcome=2)
        mutation(second + 1, pid, 8, 16)
        mutation(second + 1, pid, 8, 17, InfoClass=20)
        mutation(second + 1, pid, 8, 19,
                 Destination=r"\Device\HarddiskVolume3" + root["renamed_fixture"][2:])
        mutation(second + 1, pid, 8, 18)
        emit(second + 2, 0, 2, lifecycle=True, ProcessID=pid)

    emit(14, 0, 1, lifecycle=True, ProcessID=10)
    mutation(27, 10, 3, 12, FileName=r"\\?\C:\QA\home\data.sqlite", Outcome=1)
    mutation(28, 10, 3, 16)
    evidence.manifest["etw"] = {
        "schema_version": 1, "start_utc": instant(0), "end_utc": instant(59),
        "volume_devices": {"C:": r"\Device\HarddiskVolume3"},
        "counters": {"events_lost": 0, "log_buffers_lost": 0,
                     "realtime_buffers_lost": 0, "buffers_written": 1},
    }

    def report(rundown=None, **options):
        etw_path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
        evidence.manifest["etw"]["events_sha256"] = hashlib.sha256(etw_path.read_bytes()).hexdigest()
        return trace.audit(evidence.manifest, sysmon, etw_path, evidence.before, evidence.after,
                           etw=True, rundown=rundown, **options)

    clean = report()
    rejected = []
    assert report(rejected_sysmon_exits=rejected) == clean
    assert rejected == []
    assert clean["coverage"] == "CALIBRATED"
    assert clean["network"] == clean["filesystem"] == "PASS_SCOPED"
    assert clean["coverage_issues"] == clean["unexpected_connections"] == clean["unexpected_snapshot_changes"] == []
    assert clean["file_violations"] == clean["etw_unresolved_mutations"] == {}
    assert clean["process_roles"]["app"] == 2
    assert clean["process_roles"]["calibration"] == 4
    assert clean["snapshot_changes"]["protected:original"] is False
    assert clean["snapshot_changes"]["observed:fixture"] is False
    assert clean["protected_snapshot_comparison"] == "MATCH"
    assert clean["file_events"]["backend:write"] == 1
    assert clean["native_n12_accepted"] is False
    assert report(describe_path_gaps=True) == {
        **clean, "etw_path_gap_context": {}, "etw_write_name_gap_context": {},
        "etw_webview_write_path_candidates": {
            "eligible": 0, "sampled": 0, "outcomes": {}, "pairs": [], "eligible_outside_sample": 0,
        },
    }
    observed = trace.inspect_journey_sysmon(evidence.manifest, sysmon, etw=True)
    ordinary = trace.complete_journey_audit(
        evidence.manifest, observed, etw_path, evidence.before, evidence.after, etw=True,
        describe_path_gaps=True, webview_dominant_writes=True,
    )
    comparison = trace.complete_journey_audit(
        evidence.manifest, observed, etw_path, evidence.before, evidence.after, etw=True,
        describe_path_gaps=True, webview_dominant_writes=True, credit_verified_webview_writes=True,
    )
    assert ordinary["coverage"] == "CALIBRATED"
    assert ordinary["filesystem"] == ordinary["network"] == "PASS_SCOPED"
    assert ordinary["etw_unresolved_mutations"] == {}
    assert comparison == {
        **ordinary, "etw_webview_write_credit": {
            "status": "compared", "credited_paths": {}, "remaining_path_gaps": 0,
        },
    }

    cli_inputs = []
    for name, value in (("manifest", evidence.manifest), ("before", evidence.before),
                        ("after", evidence.after)):
        input_path = tmp_path / f"{name}.json"
        input_path.write_text(json.dumps(value), encoding="utf-8")
        cli_inputs.append(input_path)
    manifest_path, before_path, after_path = cli_inputs
    output = tmp_path / "audit.json"
    result = subprocess.run([sys.executable, str(Path(trace.__file__)), "audit-etw",
                             *map(str, (manifest_path, sysmon, etw_path, before_path, after_path, output))],
                            capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stderr
    assert json.loads(output.read_text(encoding="utf-8")) == clean

    # Diagnostic hooks receive the same strict findings without changing their verdict.
    launches = {}
    assert report(private_app_launches=launches) == clean
    assert launches == {"net1": "first", "net2": "relaunch"}
    first_app = next(row for _, kind, row in evidence.events if kind == 1 and row["ProcessGuid"] == "app1")
    first_app["Hashes"] = "SHA256=" + "D" * 64
    evidence.save(tmp_path)
    launches.clear()
    mismatched = report(private_app_launches=launches)
    assert launches == {}
    assert "app-sha256-missing-or-mismatched" in mismatched["coverage_issues"]
    first_app["Hashes"] = "SHA256=" + "E" * 64
    evidence.save(tmp_path)
    mutation(28, 10, 4, 12, FileName=r"C:\QA\outside\private-name", Outcome=1)
    mutation(28, 10, 4, 16)
    outside = []
    writers = []
    flagged = report(record_outside_scope=lambda *row: outside.append(row),
                     record_outside_writer=lambda *row: writers.append(row))
    assert flagged == report()
    assert flagged["filesystem"] == "FAIL"
    assert flagged["file_violations"]["outside-scope:backend:write"] == 1
    assert outside == [("backend", "write", (r"c:\qa\outside\private-name",))]
    assert writers == [(*outside[0], "python.exe")]
    assert "private-name" not in json.dumps(flagged)

    # The hosted mode uses this same ETW path after an unsupported Sysmon exit.
    exit_fields = next(row for _, kind, row in evidence.events if kind == 5 and row["ProcessGuid"] == "app1")
    exit_fields["Image"] = "private-opaque-image"
    evidence.connect(43, "net2", "127.0.0.1", 9443)
    evidence.save(tmp_path)
    rejected = []
    partial = report(rejected_sysmon_exits=rejected)
    assert partial["trace_verdict_scope"] == "diagnostic-only-unverified-sysmon-exit"
    assert partial["coverage"] == "BLOCKED"
    assert partial["filesystem"] == partial["network"] == "FAIL"
    assert partial["file_violations"] == flagged["file_violations"]
    assert partial["unexpected_connections"][0]["role"] == "webview-network"
    assert rejected[0]["category"] == "relative-or-unrecognized"
    assert "private-opaque-image" not in json.dumps([rejected, partial])
    exit_fields["Image"] = APP
    exit_fields["UtcTime"] = f"{BASE} 00:00:18.999"
    evidence.save(tmp_path)
    rejected = []
    earlier_exit = report(rejected_sysmon_exits=rejected)
    assert earlier_exit["coverage"] == "BLOCKED"
    assert earlier_exit["network"] == earlier_exit["filesystem"] == "FAIL"
    assert earlier_exit["file_violations"] == partial["file_violations"]
    assert earlier_exit["unexpected_connections"] == partial["unexpected_connections"]
    assert rejected == [{"record": rejected[0]["record"], "category": "exit-before-birth",
                         "exit_minus_birth_ticks": -10_000}]
    del exit_fields["UtcTime"]
    evidence.events.pop()
    exit_fields["Image"] = APP
    evidence.save(tmp_path)
    del rows[-4:]

    # Background identities can come from two matching snapshots, even when
    # there was no process-start event during the capture. Scoped app/backend
    # identities and PIDs with a recorded lifecycle transition stay excluded.
    emit(25, 72, 16, FileObject=711, FileKey=733, Irp=701, IssuingThreadId=88)
    emit(25, 0, 24, Irp=701, Status=0)
    emit(26, 73, 16, FileObject=721, FileKey=743, Irp=702, IssuingThreadId=89)
    emit(26, 0, 24, Irp=702, Status=0)
    emit(27, 73, 2, lifecycle=True, ProcessID=73)
    mutation(28, 72, 7, 12, FileName=PROTECTED + r"\private-marker", Outcome=1)
    mutation(28, 72, 7, 16)
    rows_added = 9
    baseline = report()
    assert baseline["etw_unresolved_mutations"]["other:write:process-lifetime-missing"] == 3
    before_start = trace.utc_ticks(trace.utc_time(instant(0))) - 10
    entries = [{"pid": pid, "birth_ticks": before_start} for pid in (10, 72, 73)]
    with_bookends = report(journey_bookends={"before": entries, "after": entries}, describe_path_gaps=True)
    assert with_bookends["etw_background_process_bookends"] == {
        "status": "checked", "stable_background_processes": 1,
    }
    assert with_bookends["etw_unresolved_mutations"]["other:write:process-lifetime-missing"] == 1
    assert with_bookends["etw_unresolved_mutations"]["other:write:path-missing"] == 2
    assert with_bookends["etw_path_gap_context"] == {
        "other:event-16:write:file-key:header-lifetime:unverified-thread": 1,
        "other:event-16:write:file-key:no-header-lifetime:unverified-thread": 1,
    }
    assert with_bookends["etw_write_name_gap_context"] == {"other:unverified-thread:unseen-key": 2}
    assert with_bookends["file_violations"]["protected:other:write"] == 1
    assert with_bookends["filesystem"] == "FAIL"
    assert with_bookends["coverage"] == "BLOCKED"
    assert with_bookends["native_n12_accepted"] is False
    assert "private-marker" not in json.dumps(with_bookends)
    del rows[-rows_added:]

    emit(21, 0, 1, lifecycle=True, ProcessID=4)
    emit(22, 0, 3, lifecycle=True, ProcessId=4, TThreadId=88)
    emit(23, 0, 10, FileKey=733, FileName=PROTECTED + r"\private-name-only.bin")
    mutation(24, 4, 711, 16, FileKey=733, IssuingThreadId=88)
    named = report(describe_path_gaps=True)
    assert named["etw_write_name_gap_context"] == {"webview-network:thread-header-agrees:tracked": 1}
    assert named["etw_unresolved_mutations"] == {"webview-network:write:path-missing": 1}
    assert named["coverage"] == named["filesystem"] == named["network"] == "BLOCKED"
    assert named["file_violations"] == {}
    assert "private-name-only" not in json.dumps(named)
    del rows[-5:]

    # A pre-opened backend handle has no in-capture name event. The native
    # stop-time rundown may resolve it only while its file key remains stable.
    emit(29, 10, 16, FileObject=9, FileKey="0x28", Irp=99)
    emit(29, 0, 24, Irp=99, Status=0)
    rundown_path = tmp_path / "rundown.jsonl"
    rundown_entry = {"key": "0x28",
                     "path": r"\Device\HarddiskVolume3\QA\home\cache.sqlite",
                     "decoder": "tdh+raw-schema"}
    rundown_payload = (json.dumps(rundown_entry) + "\n").encode("utf-8")
    rundown_path.write_bytes(rundown_payload)
    evidence.manifest["etw"]["rundown_sha256"] = hashlib.sha256(rundown_payload).hexdigest()
    evidence.manifest["etw"]["rundown_stop_utc"] = evidence.manifest["etw"]["end_utc"]
    rundown = trace.read_rundown_file(rundown_path, evidence.manifest)
    recovered = report(rundown)
    assert recovered["coverage"] == "CALIBRATED"
    assert recovered["network"] == recovered["filesystem"] == "PASS_SCOPED"
    assert recovered["file_events"]["backend:write"] == 2
    assert recovered["file_key_rundown_records"] == 1

    recovered_manifest = tmp_path / "manifest-rundown.json"
    recovered_manifest.write_text(json.dumps(evidence.manifest), encoding="utf-8")
    recovered_output = tmp_path / "audit-rundown.json"
    result = subprocess.run(
        [sys.executable, str(Path(trace.__file__)), "audit-etw",
         *map(str, (recovered_manifest, sysmon, etw_path, before_path, after_path, recovered_output)),
         "--rundown", str(rundown_path)],
        capture_output=True, text=True, check=False,
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(recovered_output.read_text(encoding="utf-8")) == recovered

    # Restore the calibration-only fixture: it intentionally has no rundown
    # input and must not inherit the extra pre-opened write from the audit test.
    del rows[-2:]
    evidence.manifest["etw"].pop("rundown_sha256", None)
    etw_path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
    evidence.manifest["etw"]["events_sha256"] = hashlib.sha256(etw_path.read_bytes()).hexdigest()

    calibration_manifest = dict(evidence.manifest, calibration=next(
        root for root in evidence.manifest["processes"] if root["role"] == "calibration"
    ))
    # Replay the measured collector boundary. The full ETW window includes
    # the Sysmon timestamp, while the narrower fixture window starts later.
    recorded = trace.utc_ticks(trace.utc_time(instant(1)))
    precision_manifest = dict(calibration_manifest, collector_fixture_precision=True, calibration=dict(
        calibration_manifest["calibration"], child_pid=31,
        start_window=[recorded + 2220, trace.utc_ticks(trace.utc_time(instant(7)))],
        parent_created_utc_ticks=recorded + 9807,
    ))
    adjusted = trace.check_calibration(precision_manifest, sysmon, etw_path, etw=True)
    assert adjusted["coverage"] == "CALIBRATED" and adjusted["fixture_birth_adjusted"] is True
    manifest_path.write_text(json.dumps(precision_manifest), encoding="utf-8")
    precision_output = tmp_path / "precision-calibration.json"
    result = subprocess.run([sys.executable, str(Path(trace.__file__)), "check-calibration-etw",
                             *map(str, (manifest_path, sysmon, etw_path, precision_output))],
                            capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stderr
    assert json.loads(precision_output.read_text(encoding="utf-8")) == adjusted
    stale_manifest = dict(precision_manifest, calibration=dict(
        precision_manifest["calibration"], parent_created_utc_ticks=recorded + 10_000_000,
    ))
    stale = trace.check_calibration(stale_manifest, sysmon, etw_path, etw=True)
    assert stale["coverage"] == "BLOCKED" and stale["fixture_birth_adjusted"] is False
    assert "precision-fixture-birth-outside-window" in stale["coverage_issues"]
    wrong_child = dict(precision_manifest, calibration=dict(precision_manifest["calibration"], child_pid=999))
    assert "calibration-child-lifecycle-missing" in trace.check_calibration(
        wrong_child, sysmon, etw_path, etw=True)["coverage_issues"]
    manifest_path.write_text(json.dumps(calibration_manifest), encoding="utf-8")
    calibration_output = tmp_path / "calibration.json"
    result = subprocess.run([sys.executable, str(Path(trace.__file__)), "check-calibration-etw",
                             *map(str, (manifest_path, sysmon, etw_path, calibration_output))],
                            capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stderr
    assert json.loads(calibration_output.read_text(encoding="utf-8"))["coverage"] == "CALIBRATED"

    emit(1, 0, 1, lifecycle=True, ProcessID=30)
    emit(6, 0, 2, lifecycle=True, ProcessID=30)
    mutation(3, 31, 8, 17, InfoClass=4)
    report()
    fixture = dict(calibration_manifest["calibration"], child_pid=31,
                   start_window=[trace.utc_ticks(trace.utc_time(instant(n))) for n in (0, 7)])
    calibration_manifest["calibration"] = fixture
    preflight = trace.check_etw_preflight(calibration_manifest, fixture, etw_path)
    assert preflight["expected_fixture_operations_matched"]
    assert preflight["coverage_issues"] == ["etw-mutation-coverage-unresolved"]
    assert preflight["etw_unresolved_event_types"]["calibration:event-17:info-4:unsupported-file-operation"] == 1
    assert r"C:\QA" not in json.dumps(preflight)

    # Exercise the optional digest-pinned rundown path through the preflight CLI.
    preflight_rundown_path = tmp_path / "preflight-rundown.jsonl"
    preflight_entry = {"key": "0x28", "path": r"\Device\HarddiskVolume3\QA\home\cache.sqlite",
                       "decoder": "tdh+raw-schema"}
    preflight_payload = (json.dumps(preflight_entry) + "\n").encode("utf-8")
    preflight_rundown_path.write_bytes(preflight_payload)
    preflight_manifest = dict(
        calibration_manifest,
        etw=dict(calibration_manifest["etw"],
                 rundown_sha256=hashlib.sha256(preflight_payload).hexdigest(),
                 rundown_stop_utc=calibration_manifest["etw"]["end_utc"]),
    )
    preflight_manifest_path = tmp_path / "preflight-manifest.json"
    preflight_manifest_path.write_text(json.dumps(preflight_manifest), encoding="utf-8")
    preflight_fixture_path = tmp_path / "preflight-fixture.json"
    preflight_fixture_path.write_text(json.dumps({"fixture": fixture}), encoding="utf-8")
    preflight_cli = subprocess.run(
        [sys.executable, str(Path(trace.__file__)), "check-etw-preflight",
         str(preflight_manifest_path), str(preflight_fixture_path), str(etw_path),
         "--rundown", str(preflight_rundown_path)],
        capture_output=True, text=True, check=False,
    )
    assert preflight_cli.returncode == 0, preflight_cli.stderr
    assert json.loads(preflight_cli.stdout)["file_key_rundown_records"] == 1

    del rows[-4:]
    report()

    blocked_output = tmp_path / "blocked.json"
    command = [sys.executable, trace.__file__, "check-calibration-etw",
               *map(str, (manifest_path, sysmon, etw_path, blocked_output))]
    saved_etw = etw_path.read_bytes()
    etw_path.write_bytes(b" " + saved_etw)
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    assert result.returncode == 2
    assert result.stderr.strip() == "N12 BLOCKED: ETW event stream: ETW export digest mismatch."
    assert not blocked_output.exists()
    etw_path.write_bytes(saved_etw)

    saved_sysmon = sysmon.read_bytes()
    sysmon_tree = ET.parse(sysmon)
    sysmon_tree.find(f".//{trace.EVENT_NS}EventRecordID").text = "private-record"
    sysmon_tree.write(sysmon, encoding="utf-8")
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    assert result.returncode == 2
    assert result.stderr.strip() == "N12 BLOCKED: Sysmon XML: ValueError."
    assert not blocked_output.exists()
    sysmon.write_bytes(saved_sysmon)

    mutation(29, 10, 5, 16)  # Pre-opened handle with no captured path.
    mutation(30, 10, 6, 12, FileName=r"\Device\UnmappedVolume\private.bin", Outcome=2)
    mutation(30, 10, 3, 17, InfoClass=4)  # Unhandled metadata operation.
    unresolved = report()
    assert unresolved["filesystem"] == "BLOCKED"
    assert unresolved["protected_snapshot_comparison"] == "MATCH"
    assert unresolved["etw_unresolved_mutations"] == {
        "backend:write:path-missing": 1,
        "backend:create:path-missing": 1,
        "backend:unsupported-file-operation": 1,
    }

    # PID 99 was already running at capture start. Its observed rename into
    # the protected root must still fail even though attribution is incomplete.
    mutation(31, 99, 9, 12, FileName=r"C:\QA\scratch\private.bin", Outcome=1)
    mutation(32, 99, 9, 19, Destination=r"\Device\HarddiskVolume3\Original\PilotODIN\private.bin")
    mutation(33, 99, 9, 16)
    bad = report()
    assert bad["filesystem"] == "FAIL"
    assert bad["file_violations"] == {"protected:other:rename": 1, "protected:other:write": 1}
    assert "etw-mutation-coverage-unresolved" in bad["coverage_issues"]
    assert "private.bin" not in json.dumps(bad)
    calibration_manifest["etw"] = evidence.manifest["etw"]
    rehearsal = trace.check_calibration(calibration_manifest, sysmon, etw_path, etw=True)
    assert "calibration-protected-mutation" in rehearsal["coverage_issues"]

    evidence.manifest["etw"]["counters"]["events_lost"] = 1
    assert "etw-event-or-buffer-loss" in report()["coverage_issues"]
    # A valid JSONL payload with different bytes must fail the digest check.
    etw_path.write_bytes(b" " + etw_path.read_bytes())
    with pytest.raises(ValueError, match="ETW export digest mismatch"):
        trace.audit(evidence.manifest, sysmon, etw_path, evidence.before, evidence.after, etw=True)


def test_native_rundown_flows_through_strict_reducer_for_preopened_controls(tmp_path):
    start, end = instant(0), instant(20)
    base_ticks = trace.utc_ticks(trace.utc_time(start))
    protected_root = r"C:\QA\synthetic-protected"
    protected_path = protected_root + r"\control.bin"
    outside_path = r"C:\QA\outside.bin"
    protected_ticks, outside_ticks = base_ticks + 20_000_000, base_ticks + 40_000_000
    rows = []

    def emit(event_id, pid, ticks, **data):
        rows.append({"id": event_id, "pid": pid, "ticks": ticks,
                     "lifecycle": False, "data": data})

    emit(16, 10, protected_ticks, FileObject=100, Irp=1, FileKey="0x28",
         IOSize=53, ByteOffset=0, IssuingThreadId=77)
    emit(24, 0, protected_ticks + 1, Irp=1, Status=0)
    emit(10, 99, protected_ticks + 2, FileKey="0x28",
         FileName=r"\Device\HarddiskVolume3\QA\synthetic-protected\control.bin")
    emit(16, 10, outside_ticks, FileObject=101, Irp=2, FileKey="0x29",
         IOSize=79, ByteOffset=0, IssuingThreadId=77)
    emit(24, 0, outside_ticks + 1, Irp=2, Status=0)
    emit(10, 99, outside_ticks + 2, FileKey="0x29",
         FileName=r"\Device\HarddiskVolume3\QA\outside.bin")

    events_path = tmp_path / "preopened-etw.jsonl"
    rundown_path = tmp_path / "native-rundown.jsonl"
    manifest_path = tmp_path / "preopened-manifest.json"
    capture_path = tmp_path / "preopened-capture.json"
    bookends_path = tmp_path / "preopened-bookends.json"
    rundown_entries = [
        {"key": "0x28", "path": r"\Device\HarddiskVolume3\QA\synthetic-protected\control.bin",
         "decoder": "tdh+raw-schema"},
        {"key": "0x29", "path": r"\Device\HarddiskVolume3\QA\outside.bin",
         "decoder": "tdh+raw-schema"},
        {"key": "0x2b", "path": r"\Device\HarddiskVolume3\QA\synthetic-protected\unrelated.bin",
         "decoder": "tdh+raw-schema"},
        {"key": "0x2d", "path": r"\Device\HarddiskVolume3\QA\synthetic-protected\compressed.bin",
         "decoder": "tdh+raw-schema"},
        {"key": "0x31", "path": r"\\Device\\HarddiskVolume3\\QA\\synthetic-protected\\resized.bin",
         "decoder": "tdh+raw-schema"},
        {"key": "0x32", "path": r"\Device\HarddiskVolume3\QA\synthetic-protected\etw-started.bin",
         "decoder": "tdh+raw-schema"},
        {"key": "0x33", "path": r"\Device\HarddiskVolume3\QA\synthetic-protected\ambiguous.bin",
         "decoder": "tdh+raw-schema"},
        {"key": "0x37", "path": r"\Device\HarddiskVolume3\QA\outside-compressed.bin",
         "decoder": "tdh+raw-schema"},
    ]
    rundown_payload = ("".join(json.dumps(entry) + "\n" for entry in rundown_entries)).encode()
    rundown_path.write_bytes(rundown_payload)
    capture = {
        "device": r"\Device\HarddiskVolume3",
        "protected_root": protected_root,
        "preopened": {
            "pid": 10, "tid": 77,
            "writes": {
                "protected": {"path": protected_path, "size": 53,
                              "start": protected_ticks - 1_000, "end": protected_ticks + 1_000},
                "outside": {"path": outside_path, "size": 79,
                            "start": outside_ticks - 1_000, "end": outside_ticks + 1_000},
            },
        },
    }
    manifest = {
        "start_utc": start, "end_utc": end,
        "protected_roots": {"synthetic": protected_root},
        "etw": {
            "schema_version": 1, "start_utc": start, "end_utc": end,
            "rundown_stop_utc": instant(19),
            "events_sha256": "", "rundown_sha256": hashlib.sha256(rundown_payload).hexdigest(),
            "volume_devices": {"C:": r"\Device\HarddiskVolume3"},
            "counters": {"events_lost": 0, "log_buffers_lost": 0,
                         "realtime_buffers_lost": 0, "buffers_written": 1},
        },
    }

    bookends = {
        "before": [
            {"pid": 10, "birth_ticks": base_ticks - 10_000, "name": "python.exe"},
            {"pid": 99, "birth_ticks": base_ticks - 20_000, "name": "other-writer.exe"},
        ],
        "after": [
            {"pid": 10, "birth_ticks": base_ticks - 10_000, "name": "python.exe"},
            {"pid": 99, "birth_ticks": base_ticks - 20_000, "name": "other-writer.exe"},
        ],
        "threads_before": [
            {"tid": 77, "pid": 10, "birth_ticks": base_ticks - 5_000},
            {"tid": 88, "pid": 99, "birth_ticks": base_ticks - 6_000},
        ],
        "threads_after": [
            {"tid": 77, "pid": 10, "birth_ticks": base_ticks - 5_000},
            {"tid": 88, "pid": 99, "birth_ticks": base_ticks - 6_000},
        ],
    }
    bookends_path.write_text(json.dumps(bookends), encoding="utf-8")

    def run():
        payload = ("".join(json.dumps(row) + "\n" for row in rows)).encode()
        events_path.write_bytes(payload)
        manifest["etw"]["events_sha256"] = hashlib.sha256(payload).hexdigest()
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        capture_path.write_text(json.dumps(capture), encoding="utf-8")
        return subprocess.run(
            [sys.executable, str(Path(trace.__file__)), "check-etw-preopened-rundown",
             str(manifest_path), str(capture_path), str(events_path),
             "--rundown", str(rundown_path), "--process-bookends", str(bookends_path)],
            capture_output=True, text=True, check=False,
        )

    result = run()
    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout)
    assert report["control_status"] == "PASS"
    assert report["known_preopened_write"] == {
        "operation": "write", "expected_file": "outside.bin", "matched_file": "outside.bin",
        "status": "PASS", "reason": "strict-rundown-path-recovered",
    }
    assert report["strict_coverage"] == "BLOCKED"  # the expected protected write remains a violation
    assert report["protected_control_classification"] == "PROTECTED_WRITE_DETECTED"
    assert report["outside_control_classification"] == "OUTSIDE_PROTECTED_ROOTS"
    assert report["rundown_control_keys_recovered"] == 2
    assert report["file_events"]["preopened-control:write"] == 2
    assert report["file_violations"] == {"protected:preopened-control:write": 1}
    assert report["unrelated_file_violations"] == {}
    assert report["protected_system_write_paging_flags"] == {}
    assert report["unresolved_controls"] == {}
    assert report["unrelated_unresolved_mutations"] == {}
    assert report["compression_request_outcomes"] == {}
    assert report["successful_write_path_gaps"] == {}
    assert report["stable_process_bookends"] == 2
    assert report["stable_thread_bookends"] == 2
    assert all(target["completion"] == "success" and target["issuing_thread"] == "matches"
               and target["rundown_name"] == "matches-target"
               for target in report["targets"].values())
    assert protected_path not in result.stdout and outside_path not in result.stdout

    # An unrelated protected write and an unsupported mutation remain global blockers.
    unrelated_name_ticks = base_ticks + 55_000_000
    unrelated_write_ticks = base_ticks + 56_000_000
    emit(10, 99, unrelated_name_ticks, FileKey="0x2b",
         FileName=r"\Device\HarddiskVolume3\QA\synthetic-protected\unrelated.bin")
    emit(16, 99, unrelated_write_ticks, FileObject=102, Irp=3, FileKey="0x2b",
         IOSize=31, ByteOffset=0, IssuingThreadId=88)
    emit(24, 0, unrelated_write_ticks + 1, Irp=3, Status=0)
    unrelated_ticks = base_ticks + 60_000_000
    emit(17, 99, unrelated_ticks, FileObject=103, Irp=4, FileKey="0x2a", InfoClass=4)
    emit(24, 0, unrelated_ticks + 1, Irp=4, Status=0)
    emit(23, 99, unrelated_ticks + 2, FileObject=104, Irp=5, FileKey="0x2c", InfoClass=0xDEADBEEF)
    emit(24, 0, unrelated_ticks + 3, Irp=5, Status=0)
    emit(23, 99, unrelated_ticks + 4, FileObject=105, Irp=6, FileKey="0x2d", InfoClass=0x9C040)
    emit(24, 0, unrelated_ticks + 5, Irp=6, Status=0)
    emit(10, 99, unrelated_ticks + 6, FileKey="0x2d",
         FileName=r"\Device\HarddiskVolume3\QA\synthetic-protected\compressed.bin")
    emit(23, 99, unrelated_ticks + 7, FileObject=106, Irp=7, FileKey="0x2e", InfoClass=0x900A8)
    emit(24, 0, unrelated_ticks + 8, Irp=7, Status=0)
    emit(23, 99, unrelated_ticks + 9, FileObject=107, Irp=8, FileKey="0x2f", InfoClass=0x9009C)
    emit(24, 0, unrelated_ticks + 10, Irp=8, Status=0)
    # A later close invalidates the stop-time path for this earlier resize.
    emit(17, 99, unrelated_ticks + 11, FileObject=109, Irp=10, FileKey="0x31", InfoClass=20)
    emit(24, 0, unrelated_ticks + 12, Irp=10, Status=0)
    emit(14, 99, unrelated_ticks + 13, FileObject=109, FileKey="0x31")
    # FSCTL_READ_USN_JOURNAL is a documented read-only query, even without a rundown path.
    emit(23, 99, unrelated_ticks + 11, FileObject=108, Irp=9, FileKey="0x30", InfoClass=0x900BB)
    emit(24, 0, unrelated_ticks + 12, Irp=9, Status=0)
    # Kernel ProcessStart header context can be the parent. Use ProcessID/ImageFileName in event data.
    rows.append({
        "id": 1, "pid": 10, "ticks": unrelated_ticks + 16, "lifecycle": True,
        "data": {"ProcessId": 98, "ImageFileName": r"C:\Windows\System32\etw-writer.exe"},
    })
    rows.append({
        "id": 3, "pid": 10, "ticks": unrelated_ticks + 17, "lifecycle": True,
        "data": {"ProcessId": 98, "TThreadId": 98},
    })
    emit(16, 98, unrelated_ticks + 18, FileObject=110, Irp=11, FileKey="0x32",
         IOSize=22, ByteOffset=0, IssuingThreadId=98)
    emit(24, 0, unrelated_ticks + 19, Irp=11, Status=0)

    # This FileKey has protected and outside NameCreate candidates; neither path may be chosen.
    emit(10, 99, unrelated_ticks + 20, FileKey="0x33",
         FileName=r"\Device\HarddiskVolume3\QA\synthetic-protected\ambiguous.bin")
    emit(10, 99, unrelated_ticks + 21, FileKey="0x33",
         FileName=r"\Device\HarddiskVolume3\QA\synthetic-outside\ambiguous.bin")
    emit(16, 99, unrelated_ticks + 22, FileObject=111, Irp=12, FileKey="0x33",
         IOSize=9, ByteOffset=0, IssuingThreadId=88)
    emit(24, 0, unrelated_ticks + 23, Irp=12, Status=0)

    emit(10, 99, unrelated_ticks + 24, FileKey="0x34",
         FileName=r"\Device\HarddiskVolume99\QA\synthetic-protected\unknown-volume.bin")
    emit(10, 99, unrelated_ticks + 25, FileKey="0x35")

    # Reconcile compression requests even when they fail or fall outside the protected roots.
    for index, file_key, completion in (
        (13, "0x36", {"Status": 0xC0000022}),
        (14, "0x37", {"Status": 0}),
        (15, "0x38", {"Status": 0}),
        (16, "0x39", {}),
        (17, "0x3a", None),
    ):
        ticks = unrelated_ticks + 2 * index
        emit(23, 99, ticks, FileObject=100 + index, Irp=index, FileKey=file_key, InfoClass=0x9C040)
        if completion is not None:
            emit(24, 0, ticks + 1, Irp=index, **completion)
    emit(23, 99, unrelated_ticks + 36, Irp=18, FileKey="0x3b", InfoClass=0x9C040)
    for ticks in (unrelated_ticks + 37, unrelated_ticks + 38):
        emit(23, 99, ticks, FileObject=119, Irp=19, FileKey="0x3c", InfoClass=0x9C040)
    emit(24, 0, unrelated_ticks + 39, Irp=19, Status=0)

    result = run()
    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout)
    assert report["control_status"] == "PASS"
    assert report["strict_coverage"] == "BLOCKED"
    assert "etw-mutation-coverage-unresolved" in report["coverage_issues"]
    assert report["unrelated_unresolved_mutations"]["other:unsupported-file-operation"] == 2
    assert report["unrelated_unresolved_event_types"]["other:event-17:info-4:unsupported-file-operation"] == 1
    assert report["unrelated_unresolved_event_types"]["other:event-17:info-4:unsupported:path-missing"] == 1
    assert report["unrelated_unresolved_event_types"]["other:event-23:fsctl-0xDEADBEEF:unsupported-file-operation"] == 1
    assert report["unrelated_unresolved_event_types"]["other:event-23:fsctl-0xDEADBEEF:unsupported:path-missing"] == 1
    assert report["unrelated_unresolved_event_types"]["other:event-23:fsctl-0xDEADBEEF:rundown-context-not-in-rundown"] == 1
    assert report["unrelated_unresolved_mutations"]["other:resize:path-missing"] == 1
    assert report["successful_write_path_gaps"] == {"ambiguous-name": 1}
    assert report["unresolved_write_open_evidence"] == {"no-observed-open": 1}
    assert report["unresolved_write_without_open_context"] == {
        "unavailable:header-other-verified-image:issuer-other-verified-image": 1,
    }
    assert report["unresolved_write_without_open_path_evidence"] == {
        "unavailable:header-other-verified-image:issuer-other-verified-image:conflicting-or-unmapped-name": 1,
    }
    assert report["unresolved_write_name_change_events"] == {}
    assert "other:compression:process-lifetime-missing" not in report["unrelated_unresolved_mutations"]
    assert report["unrelated_unresolved_mutations"]["other:compression:path-missing"] == 1
    assert report["compression_request_outcomes"] == {
        "observed": 9,
        "successful-completion:protected": 1,
        "successful-completion:outside-protected": 1,
        "successful-completion:unresolved-path": 1,
        "failed-completion": 1,
        "missing-status": 1,
        "missing-completion": 1,
        "missing-request-identity": 1,
        "irp-reused-before-completion": 1,
        "ambiguous-irp": 1,
    }
    assert report["unrelated_unresolved_event_types"]["other:event-17:resize:rundown-context-lifetime-invalidated"] == 1
    assert report["unrelated_unresolved_event_types"]["other:event-17:resize:rundown-invalidated-by-event-14:FileKey"] == 1
    assert report["unrelated_unresolved_event_types"]["other:event-17:resize:process-context-stable-bookend"] == 1
    assert report["protected_writer_processes"]["protected-writer:other-writer.exe:write"] == 1
    assert report["protected_writer_processes"]["protected-writer:other-writer.exe:compression"] == 1
    assert report["protected_writer_processes"]["protected-writer:etw-writer.exe:write"] == 1
    assert report["protected_writer_targets"]["protected-writer-target:other-writer.exe:write:unrelated.bin"] == 1
    assert report["protected_writer_targets"]["protected-writer-target:etw-writer.exe:write:etw-started.bin"] == 1
    assert report["other_process_image_events"]["other:event-16:process-image-etw-writer.exe"] == 1
    assert report["issuing_thread_owner_images"]["other:event-16:write:issuing-thread-owner-etw-writer.exe"] == 1
    assert report["rundown_invalidation_events"]["other:event-17:resize:rundown-invalidated-by-event-14:FileKey"] == 1
    assert report["rundown_name_candidate_events"]["other:event-16:write:name-candidate-set-size-event10-2"] >= 1
    assert report["rundown_name_candidate_events"]["other:event-16:write:name-candidates-event10-protected"] >= 1
    assert report["rundown_name_candidate_events"]["other:event-16:write:name-candidates-event10-outside-protected"] >= 1
    assert report["rundown_name_candidate_events"]["other:event-16:write:name-candidates-rundown-protected"] >= 1
    assert report["name_event_path_forms"]["n12:name-event-10:path-form-device-unmapped"] == 1
    assert report["name_event_path_forms"]["n12:name-event-10:path-form-missing"] == 1
    assert report["unmapped_name_event_devices"]["n12:name-event-10:unmapped-device-harddiskvolume99"] == 1
    assert report["volume_device_mapping_drives"] == ["C:"]
    assert report["unrelated_unresolved_mutations"]["other:write:path-missing"] == 1
    assert report["unrelated_file_violations"]["protected:other:write"] == 2
    assert report["unrelated_file_violations"]["protected:other:compression"] == 1
    assert "other-writer.exe" in json.dumps(report["protected_writer_processes"])
    assert "etw-writer.exe" in json.dumps(report["protected_writer_processes"])
    assert "Windows" not in result.stdout
    assert "synthetic-protected" not in result.stdout
    assert not any("fsctl-0x000900A8" in key for key in report["unrelated_unresolved_event_types"])
    assert not any("fsctl-0x0009009C" in key for key in report["unrelated_unresolved_event_types"])
    assert not any("fsctl-0x000900BB" in key for key in report["unrelated_unresolved_event_types"])
    assert report["unresolved_controls"] == {}

    # The strict report retains the violations and describes only successful
    # protected writes with a System header. A resize has no IOFlags field.
    stop_start = base_ticks + 180_000_000
    capture.update(rundown_start_ticks=stop_start, rundown_stop_ticks=base_ticks + 190_000_000)
    for offset, pid, key, obj, status, fields in (
        (0, 4, "0x28", 100, 0, {"IOFlags": "0x203"}),
        (2, 4, "0x2b", 102, 0, {}),
        (4, 4, "0x28", 100, 0xC0000022, {"IOFlags": 0}),
        (6, 4, "0x29", 101, 0, {"IOFlags": "0x203"}),
        (8, 99, "0x28", 100, 0, {"IOFlags": "0x203"}),
    ):
        irp = 40 + offset
        emit(16, pid, stop_start + offset, FileKey=key, FileObject=obj, Irp=irp, **fields)
        emit(24, 0, stop_start + offset + 1, Irp=irp, Status=status)
    emit(17, 4, stop_start + 10, FileKey="0x28", FileObject=100, Irp=50, InfoClass=20)
    emit(24, 0, stop_start + 11, Irp=50, Status=0)
    result = run()
    assert result.returncode == 0, result.stderr
    paging_report = json.loads(result.stdout)
    assert paging_report["protected_system_write_paging_flags"] == {
        "control-key-and-object:during-wpr-stop:set": 1,
        "other-protected-identity:during-wpr-stop:unavailable": 1,
    }
    assert paging_report["file_violations"]["protected:other:write"] == 5
    assert paging_report["file_violations"]["protected:other:resize"] == 1
    assert paging_report["strict_coverage"] == "BLOCKED"

    # A conflicting NameCreate cannot override the digest-pinned rundown.
    late_transition_ticks = base_ticks + 195_000_000
    emit(10, 99, late_transition_ticks, FileKey="0x28",
         FileName=r"\Device\HarddiskVolume3\QA\renamed-control.bin")
    result = run()
    assert result.returncode == 2
    failed_report = json.loads(result.stdout)
    assert failed_report["control_status"] == "FAIL"
    assert failed_report["rundown_control_keys_recovered"] == 1
    assert failed_report["rundown_control_key_invalidations"]["protected"]["event-10:NameAmbiguous"] == 1
    assert protected_path not in result.stdout and outside_path not in result.stdout

    # A post-rundown NameDelete still invalidates the stop-time mapping.
    rows.pop()
    emit(11, 99, late_transition_ticks + 1, FileKey="0x28")
    result = run()
    assert result.returncode == 2
    failed_report = json.loads(result.stdout)
    assert failed_report["control_status"] == "FAIL"
    assert failed_report["rundown_control_keys_recovered"] == 1
    assert failed_report["rundown_control_key_invalidations"]["protected"]["event-11:FileKey"] == 1
    assert protected_path not in result.stdout and outside_path not in result.stdout


def standalone_capture(tmp_path, evidence, **kwargs):
    sysmon, procmon = evidence.save(tmp_path, **kwargs)
    keys = ("schema_version", "disposable", "start_utc", "end_utc", "sysmon_first_record",
            "sysmon_last_record", "procmon_all_events", "procmon_loss_reviewed", "procmon_clock_utc")
    manifest = {key: evidence.manifest[key] for key in keys}
    manifest["calibration"] = next(root for root in evidence.manifest["processes"]
                                   if root["role"] == "calibration")
    return manifest, sysmon, procmon


def test_unresolved_paths_are_counted_and_redacted_in_both_modes(tmp_path):
    evidence = Evidence()
    for _ in range(2):
        evidence.write(4, 31, "WriteFile", r"\Device\NamedPipe\private-pipe")
    evidence.write(4, 31, "WriteFile", r"\\?\Volume{private-id}\private-file")
    evidence.write(4, 555, "SetRenameInformationFile", r"C:\QA\unknown",
                   "ReplaceIfExists: True", exe="private-process.exe")
    evidence.write(4, 555, "SetLinkInformationFile", r"C:\QA\unknown",
                   r"FileName: \\private-server\private-share", exe="private-process.exe")
    evidence.write(4, 555, "SetRenameInformationFile", r"\Device\private-volume\private-file")
    evidence.write(4, 555, "WriteFile", r"\Device\NamedPipe\private-ignored-pipe")

    expected = [
        ("calibration", "write", "source", "device-or-extended", 1),
        ("calibration", "write", "source", "named-pipe", 2),
        ("other", "link", "destination", "unc", 1),
        ("other", "rename", "destination", "destination-field-missing", 1),
        ("other", "rename", "source", "device-or-extended", 1),
    ]
    for report in (trace.check_calibration(*standalone_capture(tmp_path, evidence)),
                   evidence.report(tmp_path)):
        assert report["coverage"] == "BLOCKED"
        assert "file-mutation-path-unresolved" in report["coverage_issues"]
        assert report["unresolved_file_paths"] == [
            dict(role=role, operation=operation, field=field, kind=kind, count=count)
            for role, operation, field, kind, count in expected
        ]
        assert "private-" not in json.dumps(report)


def test_standalone_calibration_cli_requires_no_app_journey(tmp_path):
    evidence = Evidence()
    evidence.events.clear()
    evidence.files.clear()
    evidence.manifest["processes"].clear()
    evidence.calibration(1, 30, 9001)
    manifest, sysmon, procmon = standalone_capture(tmp_path, evidence)
    input_path = tmp_path / "calibration.json"
    output_path = tmp_path / "summary.json"
    input_path.write_text(json.dumps(manifest), encoding="utf-8")
    command = [sys.executable, trace.__file__, "check-calibration",
               *map(str, (input_path, sysmon, procmon, output_path))]
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stderr
    summary = json.loads(output_path.read_text(encoding="utf-8"))
    assert summary["coverage"] == "CALIBRATED"
    assert summary["file_events"]["calibration:rename"] == 1
    assert summary["native_n12_accepted"] is False
    assert r"C:\\QA" not in json.dumps(summary)
    assert subprocess.run(command, capture_output=True, check=False).returncode == 2


def test_combined_calibration_cli_reports_stable_processes_and_diagnostic_candidates(tmp_path):
    evidence = Evidence()
    evidence.events.clear()
    evidence.manifest["processes"].clear()
    evidence.calibration(1, 30, 9001)
    manifest, sysmon, _ = standalone_capture(tmp_path, evidence)
    manifest["protected_roots"] = {"synthetic": PROTECTED}
    start = trace.utc_ticks(trace.utc_time(manifest["start_utc"]))
    rows = []

    def emit(second, pid, event_id, *, lifecycle=False, **fields):
        rows.append(dict(ticks=start + second * 10_000_000 + len(rows),
                         pid=pid, id=event_id, lifecycle=lifecycle, data=fields))

    def mutate(pid, kind, obj, *, destination=None, **fields):
        irp = len(rows) + 1
        open_result = fields.pop("open_result", None)
        emit(3, pid, kind, FileObject=obj, Irp=irp, **fields)
        if destination:
            emit(3, pid, 27, FileObject=obj, Irp=irp, FilePath=destination)
        completion = {} if open_result is None else {"ExtraInformation": open_result}
        emit(3, 0, 24, Irp=irp, Status=0, **completion)

    fixture = manifest["calibration"]
    emit(2, 0, 1, lifecycle=True, ProcessID=31)
    mutate(31, 12, 1, FileName=fixture["fixture"], open_result=2)
    mutate(31, 16, 1)
    mutate(31, 17, 1, InfoClass=20)
    mutate(31, 19, 1, destination=fixture["renamed_fixture"])
    mutate(31, 18, 1)
    emit(5, 0, 2, lifecycle=True, ProcessID=31)

    mutate(72, 16, 2, FileKey="0x32", IssuingThreadId=83)
    mutate(72, 17, 2, InfoClass=20)
    mutate(72, 12, 3, FileName=PROTECTED + r"\private-target.bin", open_result=1)
    mutate(72, 19, 3, destination=PROTECTED + r"\private-renamed.bin")
    mutate(73, 16, 4)
    mutate(74, 16, 5)
    emit(4, 0, 2, lifecycle=True, ProcessID=74)
    mutate(30, 16, 6)  # Sysmon-scoped parent with no corresponding ETW start.

    etw_path = tmp_path / "events.jsonl"
    etw_path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
    manifest["etw"] = {
        "schema_version": 1, "start_utc": manifest["start_utc"], "end_utc": manifest["end_utc"],
        "events_sha256": hashlib.sha256(etw_path.read_bytes()).hexdigest(),
        "volume_devices": {"C:": r"\Device\HarddiskVolume3"},
        "counters": dict(events_lost=0, log_buffers_lost=0, realtime_buffers_lost=0, buffers_written=1),
    }
    manifest_path = tmp_path / "calibration.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    entries = [{"pid": pid, "birth_ticks": start - 10, "name": "private-process.exe"}
               for pid in (30, 31, 72, 73, 74)]
    snapshots = {"before": entries, "after": [dict(entry) for entry in entries]}
    snapshots["after"][3]["birth_ticks"] += 1  # PID reused between snapshots.
    bookends_path = tmp_path / "process-bookends.json"
    bookends_path.write_text(json.dumps(snapshots), encoding="utf-8-sig")
    command = [sys.executable, trace.__file__, "check-calibration-etw", *map(str, (manifest_path, sysmon, etw_path))]

    def report(label, *options):
        output_path = tmp_path / f"{label}.json"
        result = subprocess.run([*command, str(output_path), *map(str, options)],
                                capture_output=True, text=True, check=False)
        assert (result.returncode, result.stdout.strip(), result.stderr) == (
            2, "N12 collector calibration: BLOCKED", "",
        )
        return json.loads(output_path.read_text(encoding="utf-8"))

    baseline = report("baseline")
    reduced = report("with-bookends", "--process-bookends", bookends_path)
    assert baseline["etw_background_process_bookends"] == {"status": "unavailable"}
    assert reduced["etw_background_process_bookends"] == {"status": "checked", "stable_background_processes": 1}
    assert baseline["etw_unresolved_mutations"] == {
        "other:write:process-lifetime-missing": 3,
        "other:resize:process-lifetime-missing": 1,
        "other:rename:process-lifetime-missing": 1,
        "other:write:path-missing": 3,
        "other:resize:path-missing": 1,
        "unattributed:write:process-lifetime-missing": 1,
        "unattributed:write:path-missing": 1,
    }
    assert reduced["etw_unresolved_mutations"] == {
        "other:write:process-lifetime-missing": 2,
        "other:write:path-missing": 3,
        "other:resize:path-missing": 1,
        "unattributed:write:process-lifetime-missing": 1,
        "unattributed:write:path-missing": 1,
    }
    assert reduced["etw_path_gap_context"] == {
        "other:event-16:write:file-key:header-lifetime:unverified-thread": 1,
        "other:event-16:write:no-file-key:no-header-lifetime:no-thread-id": 2,
        "other:event-17:resize:no-file-key:header-lifetime:no-thread-id": 1,
        "unattributed:event-16:write:no-file-key:no-header-lifetime:no-thread-id": 1,
    }
    for summary in (baseline, reduced):
        assert summary["coverage_issues"] == ["calibration-protected-mutation", "etw-mutation-coverage-unresolved"]
        assert summary["file_violations"] == {"protected:other:rename": 1}
        assert summary["file_events"] == {f"calibration:{operation}": 1
                                          for operation in ("create", "write", "resize", "rename", "delete")}
        assert summary["native_n12_accepted"] is False
        assert "private-" not in json.dumps(summary)

    bookends_path.write_text(json.dumps({"before": entries, "after": []}), encoding="utf-8")
    output_path = tmp_path / "missing-after.json"
    result = subprocess.run([*command, str(output_path), "--process-bookends", str(bookends_path)],
                            capture_output=True, text=True, check=False)
    assert result.returncode == 2
    assert result.stderr.strip() == "N12 BLOCKED: expected two non-empty process snapshots."
    assert not output_path.exists()

    protected = PROTECTED + r"\private-candidate.bin"
    outside = r"C:\QA\outside\private-candidate.bin"
    emit(2, 0, 10, FileKey=201, FileName=protected)
    mutate(72, 16, 21, FileKey=201)
    emit(2, 0, 10, FileKey=202, FileName=outside)
    mutate(72, 17, 22, FileKey=202, InfoClass=20)
    emit(2, 0, 10, FileKey=203, FileName=outside)
    emit(2, 0, 10, FileKey=203, FileName=protected)
    mutate(72, 16, 23, FileKey=203)
    mutate(72, 17, 24, FileKey=204, InfoClass=20)
    emit(4, 0, 10, FileKey=204, FileName=outside)  # A later name cannot prove a request-time path.
    emit(2, 0, 10, FileKey=205, FileName=outside)
    emit(2, 72, 13, FileObject=25, FileKey=205)
    mutate(72, 16, 25, FileKey=205)
    emit(2, 0, 10, FileKey=206, FileName=outside)
    emit(2, 72, 13, FileObject=26, FileKey=207)  # Same object, conflicting key.
    mutate(72, 16, 26, FileKey=206)
    mutate(72, 17, 27, FileKey=208, InfoClass=20)
    mutate(72, 17, 28, FileKey=211, InfoClass=20)
    emit(3, 72, 13, FileObject=28, FileKey=211)
    emit(3, 72, 16, FileObject=29, FileKey=209, Irp=0xabcdef)
    end = trace.utc_ticks(trace.utc_time(manifest["end_utc"]))
    for irp, distance in ((900, 100_000), (901, 100_001), (902, 1_000_001)):
        rows.append(dict(ticks=end - distance, id=16, pid=72, lifecycle=False,
                         data=dict(FileObject=29, FileKey=209, Irp=irp)))
    mutate(72, 16, 30, FileKey=210)
    # Let the rundown stop share the completion's timestamp for one otherwise eligible key.
    for row in rows[-2:]:
        row["ticks"] = start + 40_000_000 - (0 if row["id"] == 24 else 10)

    etw_path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
    rundown_path = tmp_path / "rundown.jsonl"
    rundown_path.write_text("".join(json.dumps(dict(key=key, path=path, decoder="tdh")) + "\n"
                                    for key, path in ((201, protected), (202, outside), (203, outside),
                                                      (204, outside), (205, outside), (206, outside),
                                                      (208, outside), (208, protected), (210, outside),
                                                      (211, outside))),
                            encoding="utf-8")
    manifest["etw"].update(events_sha256=hashlib.sha256(etw_path.read_bytes()).hexdigest(),
                           rundown_sha256=hashlib.sha256(rundown_path.read_bytes()).hexdigest(),
                           rundown_stop_utc=instant(4))
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    plain = report("candidate-baseline")
    diagnosed = report("candidates", "--rundown", rundown_path)
    assert diagnosed["etw_unresolved_mutations"] == plain["etw_unresolved_mutations"]
    assert diagnosed["coverage_issues"] == plain["coverage_issues"]
    assert diagnosed["file_violations"] == plain["file_violations"]
    diagnostics = diagnosed["etw_calibration_diagnostics"]
    assert diagnostics["unmatched_write_timing"] == {
        "other:last-10ms": 1, "other:10-to-100ms-before-end": 1, "other:over-100ms-before-end": 2,
    }
    assert diagnostics["path_candidates"] == {
        "other:write:request-time:no-prior-name-in-lifetime": 2,
        "other:write:request-time:missing-file-key": 2,
        "other:write:request-time:candidate-protected": 1,
        "other:write:request-time:conflicting-or-unmapped-name": 1,
        "other:write:request-time:file-object-lifetime-changed": 1,
        "other:write:request-time:conflicting-object-file-key": 1,
        "other:resize:request-time:missing-file-key": 1,
        "other:resize:request-time:candidate-outside-protected": 1,
        "other:resize:request-time:no-prior-name-in-lifetime": 3,
        "unattributed:write:request-time:missing-file-key": 1,
        "other:write:rundown:not-in-rundown": 1,
        "other:write:rundown:missing-file-key": 2,
        "other:write:rundown:candidate-protected": 1,
        "other:write:rundown:lifetime-invalidated": 2,
        "other:write:rundown:conflicting-object-file-key": 1,
        "other:write:rundown:completion-at-or-after-rundown": 1,
        "other:write:no-prior-name-rundown:not-in-rundown": 1,
        "other:write:no-prior-name-rundown:completion-at-or-after-rundown": 1,
        "other:resize:rundown:missing-file-key": 1,
        "other:resize:rundown:candidate-outside-protected": 2,
        "other:resize:rundown:ambiguous-or-unmapped-name": 1,
        "other:resize:rundown:lifetime-invalidated": 1,
        "other:resize:no-prior-name-rundown:candidate-outside-protected": 1,
        "other:resize:no-prior-name-rundown:ambiguous-or-unmapped-name": 1,
        "other:resize:no-prior-name-rundown:lifetime-invalidated": 1,
        "unattributed:write:rundown:missing-file-key": 1,
    }
    assert "private-" not in json.dumps(diagnosed)
    assert "abcdef" not in json.dumps(diagnosed)

    missing_start = tmp_path / "missing-rundown-start.json"
    result = subprocess.run([*command, str(missing_start), "--rundown", str(rundown_path),
                             "--credit-verified-rundown"], capture_output=True, text=True, check=False)
    assert result.returncode == 2
    assert "requires the FileIO rundown start timestamp" in result.stderr
    assert not missing_start.exists()

    mutate(72, 16, 31, FileKey=212)
    mutate(72, 17, 32, FileKey=213, InfoClass=19)
    mutate(72, 17, 33, FileKey=214, InfoClass=4)
    etw_path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
    with rundown_path.open("a", encoding="utf-8") as rundown_stream:
        rundown_stream.write(json.dumps(dict(key=212, path=protected, decoder="tdh")) + "\n")
    manifest["etw"].update(events_sha256=hashlib.sha256(etw_path.read_bytes()).hexdigest(),
                           rundown_sha256=hashlib.sha256(rundown_path.read_bytes()).hexdigest(),
                           rundown_start_utc=instant(4), rundown_stop_utc=instant(5))
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    bookends_path.write_text(json.dumps(snapshots), encoding="utf-8-sig")
    verification_baseline = report("verification-baseline", "--process-bookends", bookends_path)
    verified = report("completion-check", "--process-bookends", bookends_path, "--rundown", rundown_path)
    assert verified["etw_unresolved_mutations"] == verification_baseline["etw_unresolved_mutations"]
    assert verified["file_violations"] == verification_baseline["file_violations"]
    assert verified["coverage_issues"] == verification_baseline["coverage_issues"]
    outcomes = verified["etw_calibration_diagnostics"]["path_candidates"]
    assert outcomes["other:resize:no-prior-name-completion-check:consistent-outside-protected-path"] == 1
    assert outcomes["other:resize:no-prior-name-completion-check:lifetime-invalidated"] == 1
    assert "private-" not in json.dumps(verified)

    credited = report("strict-comparison", "--process-bookends", bookends_path,
                      "--rundown", rundown_path, "--credit-verified-rundown")
    credit = credited["etw_rundown_credit"]
    assert credit["status"] == "compared"
    assert credit["credited_paths"] == {"other:resize:outside-protected": 1, "other:write:protected": 1}
    remaining = credit["remaining_paths_by_reason"]
    assert remaining["other:write:completion-check:completion-at-or-after-rundown-start"] == 1
    assert remaining["other:resize:request-time:candidate-outside-protected"] == 1
    assert remaining["other:allocate:outside-rundown-credit-scope"] == 1
    assert remaining["other:unsupported:outside-rundown-credit-scope"] == 1
    assert credited["etw_unresolved_mutations"]["other:unsupported-file-operation"] == 1
    assert remaining["other:resize:completion-check:lifetime-invalidated"] == 1
    assert sum(remaining.values()) == sum(count for label, count in credited["etw_unresolved_mutations"].items()
                                          if label.endswith(":path-missing"))
    unresolved = verified["etw_unresolved_mutations"].copy()
    unresolved["other:resize:path-missing"] -= 1
    unresolved["other:write:path-missing"] -= 1
    assert credited["etw_unresolved_mutations"] == unresolved
    assert credited["file_violations"] == verified["file_violations"] | {"protected:other:write": 1}
    assert credited["file_events"] == verified["file_events"]
    assert credited["coverage_issues"] == verified["coverage_issues"]
    assert credited["native_n12_accepted"] is False
    assert "private-" not in json.dumps(credited)

    manifest["etw"]["counters"]["events_lost"] = 1
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    lossy = report("strict-comparison-with-etw-loss", "--process-bookends", bookends_path,
                   "--rundown", rundown_path, "--credit-verified-rundown")
    loss = lossy["etw_rundown_credit"]
    assert loss["status"] == "blocked-etw-loss"
    assert loss["credited_paths"] == {}
    assert loss["remaining_paths_by_reason"]["other:write:rundown-verification-unavailable"] > 0
    assert sum(loss["remaining_paths_by_reason"].values()) == sum(
        count for label, count in lossy["etw_unresolved_mutations"].items() if label.endswith(":path-missing"))
    assert lossy["etw_unresolved_mutations"] == verified["etw_unresolved_mutations"]
    assert lossy["file_violations"] == verified["file_violations"]
    assert "etw-event-or-buffer-loss" in lossy["coverage_issues"]

    payload = rundown_path.read_bytes()
    rundown_path.write_bytes(payload + payload.splitlines(keepends=True)[0])
    invalid_output = tmp_path / "invalid-digest.json"
    result = subprocess.run([*command, str(invalid_output), "--rundown", str(rundown_path)],
                            capture_output=True, text=True, check=False)
    assert result.returncode == 2
    assert "FileIO rundown SHA-256 mismatch" in result.stderr and not invalid_output.exists()


def test_standalone_calibration_blocks_missing_udp_and_record_gap(tmp_path):
    evidence = Evidence()
    evidence.events = [event for event in evidence.events if not
                       (event[2].get("ProcessGuid") == "child30" and event[2].get("Protocol") == "udp")]
    evidence.manifest["procmon_loss_reviewed"] = False
    report = trace.check_calibration(*standalone_capture(tmp_path, evidence, omit_record=110))
    assert report["coverage"] == "BLOCKED"
    assert {"calibration-tcp-or-udp-missing", "sysmon-record-gap",
            "procmon-coverage-not-confirmed"} <= set(report["coverage_issues"])


def test_wrong_calibration_rename_destination_blocks_both_modes(tmp_path):
    evidence = Evidence()
    row = next(row for row in evidence.files if row[1] == "31" and row[2] == "SetRenameInformationFile")
    row[5] = r"FileName: C:\QA\calibration\30\wrong"
    standalone = trace.check_calibration(*standalone_capture(tmp_path, evidence))
    journey = evidence.report(tmp_path)
    for report in (standalone, journey):
        assert report["coverage"] == "BLOCKED"
        assert "calibration-file-events-missing" in report["coverage_issues"]


def test_calibration_blocks_missing_executable_hash_and_out_of_scope_effects(tmp_path):
    evidence = Evidence()
    next(fields for _, kind, fields in evidence.events
         if kind == 1 and fields["ProcessGuid"] == "child30").pop("Hashes")
    evidence.write(4, 31, "WriteFile", r"C:\QA\other.txt")
    evidence.connect(4, "child30", "203.0.113.23", 443)
    report = trace.check_calibration(*standalone_capture(tmp_path, evidence))
    assert report["coverage"] == "BLOCKED"
    assert {"calibration-image-identity-missing-or-mismatched", "calibration-writes-outside-fixture",
            "calibration-unexpected-connection"} <= set(report["coverage_issues"])


def test_external_webview_connection_is_unattributed_and_report_is_redacted(tmp_path):
    evidence = Evidence()
    evidence.connect(40, "net2", "203.0.113.23", 443, "udp")
    report = evidence.report(tmp_path)
    assert report["network"] == "PARTIAL"
    assert report["unexpected_connections"] == [
        {"role": "webview-network", "utc": instant(40), "protocol": "udp",
         "port": 443, "kind": "non-loopback", "purpose": "unattributed"}
    ]
    assert "203.0.113.23" not in json.dumps(report)
    assert "Original" not in json.dumps(report)


def test_loopback_wrong_port_fails_and_inbound_does_not_count_as_outbound(tmp_path):
    evidence = Evidence()
    evidence.connect(41, "net2", "::1", 9033)
    evidence.connect(41, "backend", "203.0.113.1", 8000, initiated=False)
    report = evidence.report(tmp_path)
    assert report["network"] == "FAIL"
    assert report["connections"]["backend:tcp:inbound"] == 1


@pytest.mark.parametrize(("guid", "pid", "issue"), [
    ("net1", 999, "connection-pid-disagrees-with-birth"),
    ("unknown", 4, "connection-guid-unresolved-for-scoped-pid"),
])
def test_connection_identity_conflicts_block_a_clean_audit(tmp_path, guid, pid, issue):
    evidence = Evidence()
    evidence.connect(24, guid, "127.0.0.1", 8000, pid=pid)
    report = evidence.report(tmp_path)
    assert report["network"] == "BLOCKED"
    assert report["coverage_issues"] == [issue]


@pytest.mark.parametrize(("time", "guid", "address", "port", "protocol"), [
    (24, "net1", "127.0.0.1", 9001, "tcp"),
    (4, "child30", "127.0.0.1", 8000, "tcp"),
    (4, "child30", "127.0.0.1", 9002, "tcp"),
    (24, "net1", "127.0.0.1", 8000, "udp"),
    (24, "net1", "127.0.0.2", 8000, "tcp"),
    (24, "net1", "127.0.0.1", 9331, "tcp"),
    (24, "backend", "127.0.0.1", 8000, "tcp"),
])
def test_scoped_loopback_rejects_wrong_role_protocol_or_destination(tmp_path, time, guid, address, port, protocol):
    evidence = Evidence()
    evidence.manifest["loopback_ports"].extend((5173, 9331))
    evidence.connect(24, "driver", "127.0.0.1", 9331)
    evidence.connect(time, guid, address, port, protocol)
    report = evidence.report(tmp_path)
    assert report["network"] == "FAIL"
    assert len(report["unexpected_connections"]) == 1
    assert report["unexpected_connections"][0]["port"] == port


@pytest.mark.parametrize("guid", ["backend", "net2", "driver"])
def test_final_calibration_requires_verified_exit_of_scoped_processes(tmp_path, guid):
    evidence = Evidence()
    evidence.events = [(50 if kind == 5 and fields["ProcessGuid"] == guid else second, kind, fields)
                       for second, kind, fields in evidence.events]
    report = evidence.report(tmp_path)
    assert report["network"] == report["filesystem"] == "BLOCKED"
    assert report["coverage_issues"] == ["final-calibration-before-scoped-exit"]


def test_pid_reuse_and_protected_write_from_unrelated_process(tmp_path):
    evidence = Evidence()
    evidence.birth(34, 4, "unrelated", WEBVIEW)
    evidence.end(36, "unrelated")
    evidence.connect(35, "unrelated", "203.0.113.23", 443)
    evidence.write(35, 4, "WriteFile", PROTECTED + r"\temporary", exe="msedgewebview2.exe")
    evidence.write(35, 4, "SetDispositionInformationFile", PROTECTED + r"\temporary",
                   exe="msedgewebview2.exe", detail="Delete: True")
    report = evidence.report(tmp_path)
    assert report["network"] == "PASS_SCOPED"
    assert report["filesystem"] == "FAIL"
    assert report["unexpected_snapshot_changes"] == []
    assert report["protected_snapshot_comparison"] == "MATCH"
    assert report["file_violations"] == {"protected:other:write": 1, "protected:other:delete": 1}


def test_rename_destination_and_prefix_collision(tmp_path):
    evidence = Evidence()
    evidence.write(27, 10, "SetRenameInformationFile", r"C:\QA\home\move",
                   rf"FileName: {PROTECTED}\target")
    evidence.write(27, 10, "WriteFile", r"C:\QA\home-extra\not-allowed")
    report = evidence.report(tmp_path)
    assert report["file_violations"] == {
        "outside-scope:backend:rename": 1, "protected:backend:rename": 1,
        "outside-scope:backend:write": 1,
    }


def test_driver_scratch_scope_does_not_allow_other_writes(tmp_path):
    evidence = Evidence()
    evidence.manifest["permitted_writes"]["driver"] = [r"C:\QA\capture\driver-temp"]
    evidence.write(25, 20, "WriteFile", r"C:\QA\capture\driver-temp\playwright-artifacts\trace")
    assert evidence.report(tmp_path)["filesystem"] == "PASS_SCOPED"

    evidence.write(26, 20, "WriteFile", r"C:\QA\capture\driver-temp-other\trace")
    evidence.write(27, 20, "WriteFile", PROTECTED + r"\trace")
    evidence.write(28, 10, "WriteFile", r"C:\QA\capture\driver-temp\backend-file")
    assert evidence.report(tmp_path)["file_violations"] == {
        "outside-scope:driver:write": 2, "protected:driver:write": 1,
        "outside-scope:backend:write": 1,
    }


def test_create_open_and_failed_write_are_not_mutations(tmp_path):
    evidence = Evidence()
    evidence.write(27, 10, "CreateFile", FIXTURE, "OpenResult: Opened")
    evidence.write(27, 10, "WriteFile", FIXTURE, result="ACCESS DENIED")
    report = evidence.report(tmp_path)
    assert report["filesystem"] == "PASS_SCOPED"


def test_immutable_fixture_hash_difference_fails(tmp_path):
    evidence = Evidence()
    evidence.after["observed"]["fixture"]["digest"] = "2" * 64
    report = evidence.report(tmp_path)
    assert report["filesystem"] == "FAIL"
    assert report["unexpected_snapshot_changes"] == ["observed:fixture"]
    assert report["protected_snapshot_comparison"] == "CHANGED"

    evidence.before["observed"]["fixture"]["state"] = "absent"
    evidence.after["observed"]["fixture"] = evidence.before["observed"]["fixture"].copy()
    missing = evidence.report(tmp_path)
    assert missing["protected_snapshot_comparison"] == "BLOCKED"
    assert missing["filesystem"] == "BLOCKED"


def test_missing_records_and_calibration_block_a_clean_result(tmp_path):
    evidence = Evidence()
    evidence.files = [row for row in evidence.files if not (row[1] == "41" and row[2] == "WriteFile")]
    report = evidence.report(tmp_path, omit_record=110)
    assert report["coverage"] == report["network"] == report["filesystem"] == "BLOCKED"
    assert {"sysmon-record-gap", "calibration-file-events-missing"} <= set(report["coverage_issues"])


def test_missing_exit_blocks_coverage(tmp_path):
    evidence = Evidence()
    exit_event = next(event for event in evidence.events
                      if event[1] == 5 and event[2]["ProcessGuid"] == "app2")
    evidence.events.remove(exit_event)
    report = evidence.report(tmp_path)
    assert "process-exit-missing" in report["coverage_issues"]
    assert "app-lifecycle-does-not-match-journey" in report["coverage_issues"]


def test_lost_procmon_coverage_and_unresolved_rename_block(tmp_path):
    evidence = Evidence()
    evidence.manifest["procmon_loss_reviewed"] = False
    evidence.write(25, 999, "SetRenameInformationFile", r"C:\QA\scratch")
    report = evidence.report(tmp_path)
    assert {"procmon-coverage-not-confirmed", "file-mutation-path-unresolved"} <= set(
        report["coverage_issues"])


def test_snapshot_refuses_overlap_and_path_aliases():
    evidence = Evidence()
    evidence.manifest["permitted_writes"]["app"] = [r"C:\Original\temp\.."]
    with pytest.raises(ValueError, match="overlap"):
        trace.scope(evidence.manifest)


def test_calibration_sends_actual_tcp_udp_and_leaves_no_files(monkeypatch, tmp_path):
    # CLI launches are guarded. Redirect only the child factory for this
    # portable local unit test so it uses exactly the same loopback operation.
    popen = subprocess.Popen

    def spawn(command):
        code = ("import sys; from pathlib import Path; "
                "from qa.p4_native.n12_calibration import calibrate_child; "
                "d=Path(sys.argv[1]); calibrate_child(d/'n12-marker.bin', "
                "d/'n12-renamed.bin', int(sys.argv[2]))")
        return popen([command[0], "-c", code, *command[-2:]])

    monkeypatch.setattr(n12_calibration.subprocess, "Popen", spawn)
    directory = tmp_path / "calibration"
    outcome = n12_calibration.calibrate(directory)
    assert outcome["port"] > 0
    assert 1 <= outcome["tcp_sender_port"] <= 65535
    assert 1 <= outcome["udp_sender_port"] <= 65535
    assert outcome["child_pid"] > 0 and outcome["child_pid"] != outcome["pid"]
    assert outcome["role"] == "calibration"
    assert list(directory.iterdir()) == []


def test_cli_refuses_owner_snapshot_and_audit_output_overwrite(tmp_path, monkeypatch):
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    module = Path(trace.__file__)
    absent = tmp_path / "absent.json"
    result = subprocess.run([sys.executable, str(module), "snapshot", str(absent), str(absent)],
                            capture_output=True, text=True, check=False)
    assert result.returncode == 2
    assert not absent.exists()
    evidence = Evidence()
    sysmon, procmon = evidence.save(tmp_path)
    files = []
    for name, payload in (("manifest", evidence.manifest), ("before", evidence.before),
                          ("after", evidence.after)):
        path = tmp_path / f"{name}.json"
        path.write_text(json.dumps(payload), encoding="utf-8")
        files.append(path)
    command = [sys.executable, str(module), "audit",
               *map(str, (files[0], sysmon, procmon, files[1], files[2], absent))]
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stderr
    saved = absent.read_bytes()
    assert subprocess.run(command, capture_output=True, check=False).returncode == 2
    assert absent.read_bytes() == saved


def test_procmon_time_requires_utc_clock_and_24_hour_format():
    start = datetime(2026, 11, 13, tzinfo=timezone.utc)
    assert trace.capture_time("14:12:01.0123456", start).microsecond == 12345
    with pytest.raises(ValueError):
        trace.capture_time("2:12:01 PM", start)


def test_exact_executable_identity_is_required(tmp_path):
    evidence = Evidence()
    evidence.manifest["executable_sha256"] = "f" * 64
    report = evidence.report(tmp_path)
    assert "app-sha256-missing-or-mismatched" in report["coverage_issues"]
    assert report["coverage"] == "BLOCKED"


def test_private_endpoints_include_matching_fields_only_when_requested(tmp_path):
    evidence = Evidence()
    evidence.connect(40, "net2", "203.0.113.23", 443)
    endpoints = []
    report = trace.audit(evidence.manifest, *evidence.save(tmp_path), evidence.before,
                         evidence.after, private_endpoints=endpoints)
    assert endpoints[0]["address"] == "203.0.113.23"
    assert endpoints[0]["source_port"] == 53000
    assert endpoints[0]["process_guid"] == "net2"
    assert "203.0.113.23" not in json.dumps(report)
