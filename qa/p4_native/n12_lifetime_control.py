"""Compare short-lived Windows fixture processes with Sysmon and replay redacted timing findings."""
from __future__ import annotations

import argparse
import ctypes
from ctypes import wintypes
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
from xml.etree import ElementTree as ET

from . import n12_trace as trace
from qa.p4_research import n12_app_journey as journey


CONSENT = "I_APPROVE_ONE_N12_LIFETIME_CONTROL"
PAIRS = ("fast", "paced")
ROLES = ("parent", "child")
MILLISECOND = 10_000  # UTC ticks, each 100 ns.
FILETIME_EPOCH = 504911232000000000


def process_times(process):
    """Use the original CPython Windows Popen handle after wait, so PID reuse is irrelevant."""
    get_times = ctypes.WinDLL("kernel32", use_last_error=True).GetProcessTimes
    get_times.argtypes = (wintypes.HANDLE,) + (ctypes.POINTER(wintypes.FILETIME),) * 4
    get_times.restype = wintypes.BOOL
    created, exited, kernel, user = (wintypes.FILETIME() for _ in range(4))
    if not get_times(int(process._handle), *(ctypes.byref(t) for t in (created, exited, kernel, user))):
        raise trace.EvidenceValidationError("windows-process-times-unavailable")
    birth, end = [(t.dwHighDateTime << 32 | t.dwLowDateTime) + FILETIME_EPOCH
                  for t in (created, exited)]
    trace.require(FILETIME_EPOCH < birth <= end, "windows-process-times-invalid")
    return {"pid": process.pid, "birth": birth, "exit": end}


def run_process(command):
    with subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL) as process:
        try:
            output, _ = process.communicate(timeout=20)
        except subprocess.TimeoutExpired:
            process.kill()
            process.communicate()
            raise
        trace.require(process.returncode == 0, "lifetime-fixture-process-failed")
        return process_times(process), output


def read_records(path, first, last, target_pids):
    """Keep only identity and time fields required for matching the generated lifetimes."""
    records = []
    channel_issues = set()
    previous = first - 1
    with path.open("rb") as stream, trace.evidence_stage("lifetime Sysmon XML"):
        parser = ET.iterparse(stream, events=("start", "end"))
        _, root = next(parser)
        for phase, event in parser:
            if phase != "end" or event.tag != trace.EVENT_NS + "Event":
                continue
            sys = event.find(trace.EVENT_NS + "System")
            record = int(sys.findtext(trace.EVENT_NS + "EventRecordID"))
            trace.require(previous < record <= last, "lifetime-record-order-invalid")
            if record != previous + 1:
                channel_issues.add("record-gap")
            previous = record
            kind = int(sys.findtext(trace.EVENT_NS + "EventID"))
            if kind in {4, 16, 255}:
                channel_issues.add("collector-state-or-error")
            elif kind in {1, 5}:
                fields = event.findall(f"{trace.EVENT_NS}EventData/{trace.EVENT_NS}Data")
                data = {field.get("Name"): field.text for field in fields}
                trace.require(None not in data and len(data) == len(fields), "lifetime-event-fields-ambiguous")
                records.append({
                    "record": record, "kind": kind, "pid": int(data["ProcessId"]),
                    "guid": data["ProcessGuid"].casefold(), "parent": (data.get("ParentProcessGuid") or "").casefold(),
                    "ticks": trace.utc_ticks(trace.utc_time(data["UtcTime"] + "+00:00")), "image": data.get("Image"),
                })
            root.remove(event)
    if previous != last:
        channel_issues.add("record-gap")
    # Keep mismatched-PID exits with a known generated GUID. The bounded
    # channel can contain unrelated processes even on a disposable runner.
    guids = {row["guid"] for row in records if row["kind"] == 1 and row["pid"] in target_pids}
    return [row for row in records if row["pid"] in target_pids or row["guid"] in guids], sorted(channel_issues)


def redact(witnesses, records, channel_issues, expected_image):
    """Convert private data into a portable, fixed-schema lifetime case."""
    cases = []
    expected_image = trace.windows_path(expected_image)
    for pair in PAIRS:
        parent_guid = None
        for role in ROLES:
            witness = witnesses[pair][role]
            births = [r for r in records if r["kind"] == 1 and r["pid"] == witness["pid"]]
            birth = births[0] if len(births) == 1 else None
            exits = [r for r in records if r["kind"] == 5 and (r["pid"] == witness["pid"]
                     or (birth is not None and r["guid"] == birth["guid"]))]
            end = exits[0] if len(exits) == 1 else None
            row = {
                "case": f"{pair}-{role}", "birth_count": len(births), "exit_count": len(exits),
                "windows_duration_ticks": witness["exit"] - witness["birth"],
            }
            if birth is not None:
                if role == "parent":
                    parent_guid = birth["guid"]
                try:
                    birth_matches = trace.sysmon_image(birth["image"], 1, birth["record"]) == expected_image
                except trace.InvalidSysmonImage:
                    birth_matches = False
                row.update(birth_delta_ticks=birth["ticks"] - witness["birth"], birth_image_matches=birth_matches,
                           parent_matches=role == "parent" or (parent_guid is not None and birth["parent"] == parent_guid))
            if end is not None:
                row["exit_delta_ticks"] = end["ticks"] - witness["exit"]
            if birth is not None and end is not None:
                row.update(exit_identity_matches=(end["pid"], end["guid"]) == (birth["pid"], birth["guid"]),
                           ordered_records=birth["record"] < end["record"])
                try:
                    image = trace.sysmon_image(end["image"], 5, end["record"], birth_image=expected_image)
                    row["exit_image_matches"] = image == expected_image
                    row["unsupported_exit_image"] = False
                except trace.InvalidSysmonImage:
                    row["exit_image_matches"] = False
                    row["unsupported_exit_image"] = True
            cases.append(row)
    return {"schema_version": 1, "channel_issues": channel_issues, "cases": cases}


def replay(packet):
    """Evaluate the redacted evidence, with no dependency on Windows or raw traces."""
    trace.require(type(packet["schema_version"]) is int and packet["schema_version"] == 1
                  and isinstance(packet["channel_issues"], list)
                  and set(packet["channel_issues"]) <= {"record-gap", "collector-state-or-error"}
                  and [row["case"] for row in packet["cases"]] == [f"{p}-{r}" for p in PAIRS for r in ROLES],
                  "invalid-lifetime-replay-envelope")
    findings = {}
    for row in packet["cases"]:
        issues = set()
        for key in ("birth_count", "exit_count", "windows_duration_ticks"):
            trace.require(type(row[key]) is int and row[key] >= 0, "invalid-lifetime-replay-count")
        if row["birth_count"] != 1:
            issues.add("birth-missing-or-ambiguous")
        else:
            trace.require(type(row["birth_delta_ticks"]) is int and type(row["birth_image_matches"]) is bool
                          and type(row["parent_matches"]) is bool, "invalid-lifetime-replay-birth")
            if not row["birth_image_matches"]:
                issues.add("birth-image-unverified")
            if not row["parent_matches"]:
                issues.add("parent-unverified")
            if abs(row["birth_delta_ticks"]) > MILLISECOND:
                issues.add("birth-time-disagrees-with-windows")
        if row["exit_count"] != 1:
            issues.add("exit-missing-or-ambiguous")
        else:
            trace.require(type(row["exit_delta_ticks"]) is int, "invalid-lifetime-replay-exit")
            if abs(row["exit_delta_ticks"]) > MILLISECOND:
                issues.add("exit-time-disagrees-with-windows")
        if row["birth_count"] == row["exit_count"] == 1:
            for key in ("exit_identity_matches", "ordered_records", "exit_image_matches", "unsupported_exit_image"):
                trace.require(type(row[key]) is bool, "invalid-lifetime-replay-identity")
            if not (row["exit_identity_matches"] and row["ordered_records"]):
                issues.add("exit-identity-or-order-unverified")
            if not row["exit_image_matches"] or row["unsupported_exit_image"]:
                issues.add("exit-image-unverified")
            if row["windows_duration_ticks"] + row["exit_delta_ticks"] < row["birth_delta_ticks"]:
                issues.add("exit-before-birth")
        findings[row["case"]] = sorted(issues)
    return {"scope": "generated-lifetime-control",
            "verdict": "BLOCKED" if packet["channel_issues"] or any(findings.values()) else "PASS",
            "channel_issues": sorted(set(packet["channel_issues"])), "findings": findings}


def capture(root):
    first = journey.sysmon_tail() + 1
    witnesses = {}
    for pair in PAIRS:
        parent, output = run_process([sys.executable, "-B", "-m", "qa.p4_native.n12_lifetime_control", "--fixture-parent", pair])
        child = json.loads(output)
        trace.require(parent["birth"] <= child["birth"] <= child["exit"] <= parent["exit"],
                      "windows-parent-child-order-invalid")
        witnesses[pair] = {"parent": parent, "child": child}
    pids = {w["pid"] for pair in witnesses.values() for w in pair.values()}
    trace.require(len(pids) == len(PAIRS) * len(ROLES), "lifetime-fixture-pid-reused")
    # Give the channel a bounded flush period after the last verified exit.
    time.sleep(3)
    last = journey.sysmon_tail()
    trace.require(first <= last < first + 4096, "lifetime-record-window-invalid")
    xml = root / "lifetime-sysmon.xml"
    journey.export_sysmon(first, last, xml)
    records, issues = read_records(xml, first, last, pids)
    packet = redact(witnesses, records, issues, sys.executable)
    result = replay(packet)
    journey.report_file(root / "lifetime-replay.json", packet)
    print("N12 lifetime replay " + json.dumps(packet), flush=True)
    print("N12 lifetime verdict " + json.dumps(result), flush=True)
    return 0 if result["verdict"] == "PASS" else 2


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--capture", type=Path)
    mode.add_argument("--fixture-parent", choices=PAIRS)
    mode.add_argument("--replay", type=Path)
    args = parser.parse_args()
    try:
        if args.replay:
            result = replay(json.loads(args.replay.read_text(encoding="utf-8")))
            print(json.dumps(result))
            return 0 if result["verdict"] == "PASS" else 2
        trace.require(os.name == "nt" and os.getenv("GITHUB_ACTIONS") == "true"
                      and os.getenv("RUNNER_ENVIRONMENT") == "github-hosted"
                      and os.getenv("RUNNER_OS") == "Windows" and os.getenv("GITHUB_RUN_ATTEMPT") == "1"
                      and os.getenv("PILOTODIN_N12_LIFETIME_CONTROL_CONSENT") == CONSENT,
                      "lifetime-control-requires-approved-hosted-windows")
        if args.fixture_parent:
            code = "pass" if args.fixture_parent == "fast" else "import time; time.sleep(0.05)"
            witness, _ = run_process([sys.executable, "-B", "-c", code])
            print(json.dumps(witness))
            return 0
        source = os.getenv("PILOTODIN_N12_LIFETIME_SOURCE", "")
        trace.require(re.fullmatch(r"[0-9a-f]{40}", source) and journey.build.git("rev-parse", "HEAD") == source,
                      "lifetime-source-mismatch")
        print(f"N12 lifetime reviewed source {source}", flush=True)
        return capture(trace.local_disposable_path(args.capture, runner_temp_only=True))
    except trace.EvidenceValidationError as exc:
        print(f"N12 lifetime control blocked: {exc}", file=sys.stderr)
    except (AttributeError, KeyError, OSError, RuntimeError, TypeError, ValueError, subprocess.SubprocessError) as exc:
        print(f"N12 lifetime control blocked: {type(exc).__name__}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
