"""Corroborate generated Windows process lifetimes with kernel-process ETW."""
from __future__ import annotations

from contextlib import contextmanager
import json
import os
from pathlib import Path
import re
import subprocess
from uuid import uuid4

from . import n12_etw_probe as etw
from . import n12_trace as trace
from qa.p4_research import n12_app_journey as journey


COUNTERS = ("events_lost", "log_buffers_lost", "realtime_buffers_lost", "buffers_written")


@contextmanager
def process_session(root, source):
    """Capture only kernel process start/stop evidence on the approved runner."""
    session = f"PilotODIN-N12-Lifetime-{uuid4().hex}"
    logman = str(Path(os.environ["SystemRoot"]) / "System32" / "logman.exe")
    command = [logman, "create", "trace", session, "-p", "Microsoft-Windows-Kernel-Process",
               "0x10", "4", "-o", str(root / "lifetime.etl"), "-max", "16", "-ets"]
    evidence = {"start": etw.utc_ticks()}
    try:
        with journey.checkpoint_stage("lifetime-etw-start", source, ""):
            journey.quiet(command)
    except subprocess.TimeoutExpired:
        stop_session(logman, session, source, primary_error=True)
        raise
    try:
        yield evidence
    except BaseException:
        stop_session(logman, session, source, primary_error=True)
        raise
    evidence["counters"] = stop_session(logman, session, source)
    evidence["end"] = etw.utc_ticks()


def stop_session(logman, session, source, *, primary_error=False):
    try:
        with journey.checkpoint_stage("lifetime-etw-stop", source, ""):
            return etw.stop_trace(session)
    except Exception:
        try:
            with journey.checkpoint_stage("lifetime-etw-stop-fallback", source, ""):
                journey.quiet([logman, "stop", session, "-ets"])
        except Exception:
            pass  # Preserve the original failure.
        if not primary_error:
            raise


def payload_ticks(value):
    """Keep the seventh fractional digit present in Windows FILETIME XML."""
    match = re.fullmatch(r"(\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d)(?:\.(\d{1,7}))?(?:Z|\+00:00)", value)
    trace.require(match is not None, "lifetime-etw-invalid-payload-time")
    seconds, fraction = match.groups()
    return trace.utc_ticks(trace.utc_time(seconds + "+00:00")) + int((fraction or "0").ljust(7, "0"))


def unsigned(value):
    trace.require(re.fullmatch(r"[0-9]{1,20}", value) is not None and int(value) < 2**64,
                  "lifetime-etw-invalid-identity")
    return int(value)


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
                      "creation": payload_ticks(data["CreateTime"])}
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
