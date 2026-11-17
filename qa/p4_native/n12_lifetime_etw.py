"""Corroborate generated Windows process lifetimes with kernel-process ETW."""
from __future__ import annotations

from contextlib import contextmanager
import json
import os
from pathlib import Path
import subprocess
from uuid import uuid4

from . import n12_etw_probe as etw
from .n12_exit_corroboration import compare_image_path, compare_stop_image
from . import n12_trace as trace
from .n12_trace import etw_payload_ticks as payload_ticks, etw_unsigned as unsigned
from qa.p4_research import n12_app_journey as journey


COUNTERS = ("events_lost", "log_buffers_lost", "realtime_buffers_lost", "buffers_written")


@contextmanager
def process_session(root, source, executable_sha256=""):
    """Capture only kernel process start/stop evidence on the approved runner."""
    session = f"PilotODIN-N12-Lifetime-{uuid4().hex}"
    logman = str(Path(os.environ["SystemRoot"]) / "System32" / "logman.exe")
    command = [logman, "create", "trace", session, "-p", "Microsoft-Windows-Kernel-Process",
               "0x10", "4", "-o", str(root / "lifetime.etl"), "-max", "16", "-ets"]
    evidence = {"start": etw.utc_ticks()}
    try:
        with journey.checkpoint_stage("lifetime-etw-start", source, executable_sha256):
            journey.quiet(command)
    except subprocess.TimeoutExpired:
        stop_session(logman, session, source, executable_sha256, primary_error=True)
        raise
    try:
        yield evidence
    except BaseException:
        stop_session(logman, session, source, executable_sha256, primary_error=True)
        raise
    evidence["counters"] = stop_session(logman, session, source, executable_sha256)
    evidence["end"] = etw.utc_ticks()


def stop_session(logman, session, source, executable_sha256, *, primary_error=False):
    try:
        with journey.checkpoint_stage("lifetime-etw-stop", source, executable_sha256):
            return etw.stop_trace(session)
    except Exception:
        try:
            with journey.checkpoint_stage("lifetime-etw-stop-fallback", source, executable_sha256):
                journey.quiet([logman, "stop", session, "-ets"])
        except Exception:
            pass  # Preserve the original failure.
        if not primary_error:
            raise


def read_process_events(path, target_pids, start, end):
    """Use payload PID because creation can be logged in another process's context."""
    events = []
    with trace.evidence_stage("lifetime ETW export"), path.open(encoding="utf-8") as stream:
        for index, line in enumerate(stream):
            row = json.loads(line)
            data = row["data"]
            pid = unsigned(data["ProcessID"])
            seq = unsigned(data["ProcessSequenceNumber"]) if "ProcessSequenceNumber" in data else None
            events.append((index, row, pid, seq))

        sequences = {seq for _, row, pid, seq in events if row["id"] == 1 and
                     pid in target_pids and seq is not None}
        records = []
        for index, row, pid, seq in events:
            if pid not in target_pids and seq not in sequences:
                continue
            kind, stamp, version, data = row["id"], row["ticks"], row["version"], row["data"]
            trace.require(type(kind) is int and kind in (1, 2) and type(stamp) is int
                          and type(version) is int and version >= 0
                          and (version < (3 if kind == 1 else 2) or seq is not None),
                          "lifetime-etw-invalid-record")
            record = {"index": index, "kind": kind, "pid": pid, "sequence": seq,
                      "ticks": stamp, "in_window": start <= stamp <= end,
                      "creation": payload_ticks(data["CreateTime"]), "image": data.get("ImageName")}
            if kind == 1:
                record["parent"] = unsigned(data["ParentProcessID"])
                parent_sequence = data.get("ParentProcessSequenceNumber")
                trace.require(version < 3 or parent_sequence is not None, "lifetime-etw-parent-sequence-missing")
                record["parent_sequence"] = unsigned(parent_sequence) if parent_sequence is not None else None
            else:
                record["exit"] = payload_ticks(data["ExitTime"])
            records.append(record)
    return records


def redact(witnesses, records, counters, observer_pid):
    """Retain only case labels, counts, relative times and join outcomes."""
    cases = []
    for pair, group in witnesses.items():
        parent, child = group["parent"], group["child"]
        parent_start = None
        for role, witness in (("parent", parent), ("child", child)):
            starts = [r for r in records if r["kind"] == 1 and r["pid"] == witness["pid"]]
            start = starts[0] if len(starts) == 1 else None
            sequence = start["sequence"] if start is not None else None
            stops = [r for r in records if r["kind"] == 2 and
                     (r["pid"] == witness["pid"] or (sequence is not None and r["sequence"] == sequence))]
            stop = stops[0] if len(stops) == 1 else None
            row = {"case": f"{pair}-{role}", "start_count": len(starts), "stop_count": len(stops)}
            if start is not None:
                row.update(start_event_delta_ticks=start["ticks"] - witness["birth"],
                           create_delta_ticks=start["creation"] - witness["birth"],
                           start_in_window=start["in_window"],
                           parent_matches=start["parent"] == (observer_pid if role == "parent" else parent["pid"]))
                if role == "parent":
                    parent_start = start
                else:
                    row["parent_matches"] &= parent_start is not None and (
                        start["parent_sequence"] == parent_start["sequence"])
            if stop is not None:
                row.update(stop_event_delta_ticks=stop["ticks"] - witness["exit"],
                           exit_delta_ticks=stop["exit"] - witness["exit"],
                           stop_in_window=stop["in_window"])
            if start is not None and stop is not None:
                row.update(identity_matches=(start["pid"], sequence, start["creation"]) ==
                           (stop["pid"], stop["sequence"], stop["creation"]),
                           ordered=start["index"] < stop["index"] and start["ticks"] <= stop["ticks"],
                           sequence_unique=sequence is None or all(
                               r["pid"] == witness["pid"] for r in records if r["sequence"] == sequence))
            cases.append(row)
    return {"counters": {key: counters[key] for key in COUNTERS}, "cases": cases}


def findings(packet, windows_cases, bound):
    """Evaluate the redacted ETW data before attempting a Sysmon comparison."""
    counters, cases = packet["counters"], packet["cases"]
    trace.require(set(counters) == set(COUNTERS) and all(type(n) is int and n >= 0 for n in counters.values())
                  and [r["case"] for r in cases] == [r["case"] for r in windows_cases],
                  "invalid-lifetime-etw-replay")
    issues = []
    if not counters["buffers_written"]:
        issues.append("etw-no-buffers-written")
    if any(counters[key] for key in COUNTERS[:-1]):
        issues.append("etw-event-or-buffer-loss")
    by_case = {}
    for row, windows in zip(cases, windows_cases):
        problems = []
        for count, times, flags in (
            ("start_count", ("start_event_delta_ticks", "create_delta_ticks"), ("start_in_window", "parent_matches")),
            ("stop_count", ("stop_event_delta_ticks", "exit_delta_ticks"), ("stop_in_window",)),
        ):
            trace.require(type(row[count]) is int and row[count] >= 0, "invalid-lifetime-etw-count")
            if row[count] != 1:
                problems.append(count.replace("_count", "-missing-or-ambiguous"))
                continue
            for key in times:
                trace.require(type(row[key]) is int, "invalid-lifetime-etw-delta")
                # The event timestamp measures when ETW emitted the record.
                # Compare the provider's lifecycle payload with the process handle.
                if key in {"create_delta_ticks", "exit_delta_ticks"} and abs(row[key]) > bound:
                    problems.append(key.replace("_delta_ticks", "") + "-disagrees-with-windows")
            for key in flags:
                trace.require(type(row[key]) is bool, "invalid-lifetime-etw-match")
                if not row[key]:
                    problems.append(key.replace("_", "-") + "-unverified")
        if row["start_count"] == row["stop_count"] == 1:
            for key in ("identity_matches", "ordered", "sequence_unique"):
                trace.require(type(row[key]) is bool, "invalid-lifetime-etw-identity")
                if not row[key]:
                    problems.append(key.replace("_", "-") + "-unverified")
            if windows["windows_duration_ticks"] + row["exit_delta_ticks"] < row["create_delta_ticks"]:
                problems.append("exit-before-creation")
        by_case[row["case"]] = problems
    for index in range(0, len(cases), 2):
        parent, child = cases[index:index + 2]
        if child["start_count"] != 1:
            continue
        offset = windows_cases[index + 1]["windows_birth_after_parent_ticks"]
        duration = windows_cases[index]["windows_duration_ticks"]
        for start, stop in (("start_event_delta_ticks", "stop_event_delta_ticks"),
                            ("create_delta_ticks", "exit_delta_ticks")):
            child_start = offset + child[start]
            if ((parent["start_count"] == 1 and child_start < parent[start]) or
                    (parent["stop_count"] == 1 and child_start > duration + parent[stop])):
                by_case[child["case"]].append(f"parent-lifetime-conflict-{start.removesuffix('_delta_ticks')}")
    return issues, {label: sorted(problems) for label, problems in by_case.items()}


def image_path_report(witnesses, records, packet, windows_cases, devices, expected_image):
    """Compare exact executable paths after independently verifying the ETW lifetime."""
    issues, timing = findings(packet, windows_cases, 0)
    expected = trace.windows_path(expected_image)
    cases = []
    for pair, group in witnesses.items():
        for role, witness in group.items():
            label = f"{pair}-{role}"
            starts = [r for r in records if r["kind"] == 1 and r["pid"] == witness["pid"]]
            row = {"case": label, "timing_issues": timing[label],
                   "handle_dos_matches": trace.windows_path(witness["image_dos"]) == expected,
                   "handle_native_comparison": compare_image_path(witness["image_native"], expected, devices),
                   "etw_start_comparison": "start-missing-or-ambiguous",
                   "etw_native_matches": False, "sequence_present": False}
            if len(starts) == 1:
                start = starts[0]
                image = start["image"]
                row.update(sequence_present=start["sequence"] is not None,
                           etw_start_comparison=compare_image_path(image, expected, devices),
                           etw_native_matches=isinstance(image, str) and
                           image.casefold() == witness["image_native"].casefold())
            cases.append(row)
    passed = not issues and all(
        not row["timing_issues"] and row["sequence_present"] and row["handle_dos_matches"]
        and row["handle_native_comparison"] == "exact-path-match"
        and row["etw_start_comparison"] == "exact-path-match" and row["etw_native_matches"]
        for row in cases
    )
    return {"scope": "generated-process-image-path-control", "verdict": "PASS" if passed else "BLOCKED",
            "etw_issues": issues, "collector_counters": packet["counters"], "cases": cases}


def stop_image_report(witness, records, session, devices, expected_image):
    """Identify the observed stop-field form for one independently witnessed fixture."""
    counters = session["counters"]
    issues = []
    if any(counters[key] for key in COUNTERS[:-1]) or not counters["buffers_written"]:
        issues.append("etw-coverage-unverified")
    starts = [row for row in records if row["kind"] == 1 and row["pid"] == witness["pid"]]
    stops = [row for row in records if row["kind"] == 2 and row["pid"] == witness["pid"]]
    if len(starts) != 1 or len(stops) != 1:
        issues.append("etw-pair-missing-or-ambiguous")
    expected = trace.windows_path(expected_image)
    label = "unverified-pair"
    prefix_length = None
    if len(starts) == len(stops) == 1:
        start, stop = starts[0], stops[0]
        sequence = start["sequence"]
        if not (sequence is not None and stop["sequence"] == sequence and
                sum(row["sequence"] == sequence for row in records) == 2 and
                start["creation"] == stop["creation"] == witness["birth"] and stop["exit"] == witness["exit"] and
                session["start"] <= witness["birth"] <= witness["exit"] <= session["end"] and
                start["in_window"] and stop["in_window"] and start["index"] < stop["index"] and
                start["ticks"] < stop["ticks"]):
            issues.append("etw-pair-identity-or-time-unverified")
        image = start["image"]
        if not (trace.windows_path(witness["image_dos"]) == expected and
                compare_image_path(witness["image_native"], expected, devices) == "exact-path-match" and
                isinstance(image, str) and image.casefold() == witness["image_native"].casefold()):
            issues.append("etw-start-image-or-handle-unverified")
        label = compare_stop_image(stop["image"], expected, devices)
        if label == "short-basename-prefix":
            prefix_length = len(stop["image"])
        if label in {"missing-image", "invalid-image-type"}:
            issues.append("etw-stop-image-unavailable")
    return {"scope": "generated-long-image-stop-field", "verdict": "BLOCKED" if issues else "PASS",
            "issues": issues, "stop_image_form": label, "observed_prefix_length": prefix_length,
            "collector_counters": counters}
