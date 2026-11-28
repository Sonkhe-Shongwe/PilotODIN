"""Compare short-lived Windows fixture processes with Sysmon and replay redacted timing findings."""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import ctypes
from ctypes import wintypes
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time
from types import SimpleNamespace
from xml.etree import ElementTree as ET

from . import n12_etw_probe
from . import n12_lifetime_etw as etw
from . import n12_trace as trace
from qa.p4_research import n12_app_journey as journey


CONSENT = "I_APPROVE_ONE_N12_LIFETIME_CONTROL"
ETW_CONSENT = "I_APPROVE_ONE_N12_LIFETIME_ETW_CONTROL"
PAIRS = ("fast", "paced")
ROLES = ("parent", "child")
MILLISECOND = 10_000  # UTC ticks, each 100 ns.
FILETIME_EPOCH = 504911232000000000


def process_times(process, *, allow_running=False):
    """Use a retained Windows process handle after exit, so PID reuse is irrelevant."""
    get_times = ctypes.WinDLL("kernel32", use_last_error=True).GetProcessTimes
    get_times.argtypes = (wintypes.HANDLE,) + (ctypes.POINTER(wintypes.FILETIME),) * 4
    get_times.restype = wintypes.BOOL
    created, exited, kernel, user = (wintypes.FILETIME() for _ in range(4))
    if not get_times(int(process._handle), *(ctypes.byref(t) for t in (created, exited, kernel, user))):
        raise trace.EvidenceValidationError("windows-process-times-unavailable")
    birth, end = [(t.dwHighDateTime << 32 | t.dwLowDateTime) + FILETIME_EPOCH
                  for t in (created, exited)]
    if allow_running and end == FILETIME_EPOCH:
        trace.require(FILETIME_EPOCH < birth, "windows-process-times-invalid")
        return {"pid": process.pid, "birth": birth, "exit": None}
    trace.require(FILETIME_EPOCH < birth <= end, "windows-process-times-invalid")
    return {"pid": process.pid, "birth": birth, "exit": end}


def process_images(process):
    """Read both image representations from the retained handle before exit."""
    query = ctypes.WinDLL("kernel32", use_last_error=True).QueryFullProcessImageNameW
    query.argtypes = (wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD))
    query.restype = wintypes.BOOL
    images = {}
    buffer = ctypes.create_unicode_buffer(32768)
    for flags, key in ((0, "image_dos"), (1, "image_native")):
        size = wintypes.DWORD(len(buffer))
        trace.require(query(int(process._handle), flags, buffer, ctypes.byref(size)) and size.value > 0,
                      f"windows-process-{key}-unavailable")
        images[key] = buffer[:size.value]
    return images


@contextmanager
def open_process_query_handle(pid):
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    open_process = kernel.OpenProcess
    open_process.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
    open_process.restype = wintypes.HANDLE
    close_handle = kernel.CloseHandle
    close_handle.argtypes = (wintypes.HANDLE,)
    close_handle.restype = wintypes.BOOL
    handle = open_process(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
    trace.require(handle, "windows-process-query-handle-unavailable")
    try:
        yield SimpleNamespace(pid=pid, _handle=handle)
    finally:
        close_handle(handle)


def run_process(command, *, with_images=False, fixture_input=b"1", creationflags=0, hold_seconds=0,
                env=None, cwd=None):
    # The pipe holds even the fast fixture until its executable paths are recorded.
    stdin = subprocess.PIPE if with_images else None
    with subprocess.Popen(command, stdin=stdin, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                          creationflags=creationflags, env=env, cwd=cwd) as process:
        try:
            images = process_images(process) if with_images else {}
            if hold_seconds:
                time.sleep(hold_seconds)
            output, _ = process.communicate(input=fixture_input if with_images else None, timeout=20)
        except (trace.EvidenceValidationError, subprocess.TimeoutExpired):
            process.kill()
            process.communicate()
            raise
        trace.require(process.returncode == 0, "lifetime-fixture-process-failed")
        return process_times(process) | images, output


def read_records(path, first, last, target_pids, *, include_descendants=False):
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
    if include_descendants:
        children = {}
        for row in records:
            if row["kind"] == 1:
                children.setdefault(row["parent"], set()).add(row["guid"])
        pending = list(guids)
        while pending:
            descendants = children.get(pending.pop(), set()) - guids
            guids.update(descendants)
            pending.extend(descendants)
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
            if role == "child":
                row["windows_birth_after_parent_ticks"] = witness["birth"] - witnesses[pair]["parent"]["birth"]
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
    return {"schema_version": 2, "channel_issues": channel_issues, "cases": cases}


def replay(packet):
    """Evaluate the redacted evidence, with no dependency on Windows or raw traces."""
    version = packet["schema_version"]
    if type(version) is int and version == 3:
        return replay_corroboration(packet)
    trace.require(type(version) is int and version in (1, 2)
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
    if version == 2:
        for parent, child in zip(packet["cases"][::2], packet["cases"][1::2]):
            offset = child["windows_birth_after_parent_ticks"]
            duration = parent["windows_duration_ticks"]
            trace.require(type(offset) is int and 0 <= offset <= duration - child["windows_duration_ticks"],
                          "invalid-lifetime-replay-parent-window")
            if child["birth_count"] == 1:
                child_birth = offset + child["birth_delta_ticks"]
                issues = findings[child["case"]]
                if parent["birth_count"] == 1 and child_birth < parent["birth_delta_ticks"]:
                    issues.append("parent-start-after-child-birth")
                if parent["exit_count"] == 1 and child_birth > duration + parent["exit_delta_ticks"]:
                    issues.append("parent-exit-before-child-birth")
                issues.sort()
    return {"scope": "generated-lifetime-control",
            "verdict": "BLOCKED" if packet["channel_issues"] or any(findings.values()) else "PASS",
            "channel_issues": sorted(set(packet["channel_issues"])), "findings": findings}


def replay_corroboration(packet):
    sysmon = packet["sysmon"]
    trace.require(type(sysmon["schema_version"]) is int and sysmon["schema_version"] == 2,
                  "lifetime-corroboration-requires-sysmon-schema-2")
    sysmon_result = replay(sysmon)
    etw_issues, etw_findings = etw.findings(packet["etw"], sysmon["cases"], MILLISECOND)
    comparisons = {}
    for row, observed in zip(sysmon["cases"], packet["etw"]["cases"]):
        label = row["case"]
        if etw_issues or etw_findings[label]:
            comparisons[label] = "etw-unverified"
        elif sysmon_result["channel_issues"] or any(
            item not in {"birth-time-disagrees-with-windows", "exit-time-disagrees-with-windows"}
            for item in sysmon_result["findings"][label]
        ):
            comparisons[label] = "sysmon-identity-or-coverage-unverified"
        else:
            deltas = [(row["birth_delta_ticks"], observed["create_delta_ticks"]),
                      (row["exit_delta_ticks"], observed["exit_delta_ticks"])]
            disagreements = [(sysmon_delta, etw_delta) for sysmon_delta, etw_delta in deltas
                             if abs(sysmon_delta) > MILLISECOND]
            if disagreements:
                comparisons[label] = ("etw-and-handles-agree-sysmon-time-differs" if all(
                    abs(sysmon_delta - etw_delta) > MILLISECOND for sysmon_delta, etw_delta in disagreements
                ) else "sysmon-and-etw-timing-inconclusive")
            elif any(abs(sysmon_delta - etw_delta) > MILLISECOND for sysmon_delta, etw_delta in deltas):
                comparisons[label] = "collectors-differ-within-handle-bound"
            else:
                comparisons[label] = "all-agree-within-bound"
    return {
        "scope": "generated-lifetime-etw-corroboration",
        "verdict": "PASS" if all(c == "all-agree-within-bound" for c in comparisons.values()) else "BLOCKED",
        "sysmon": sysmon_result, "etw_issues": etw_issues, "etw_findings": etw_findings, "comparisons": comparisons,
    }


def gather_witnesses(*, with_images=False):
    witnesses = {}
    for pair in PAIRS:
        parent, output = run_process([
            sys.executable, "-B", "-m", "qa.p4_native.n12_lifetime_control", "--fixture-parent", pair,
        ], with_images=with_images)
        child = json.loads(output)
        trace.require(parent["birth"] <= child["birth"] <= child["exit"] <= parent["exit"],
                      "windows-parent-child-order-invalid")
        witnesses[pair] = {"parent": parent, "child": child}
    pids = {w["pid"] for pair in witnesses.values() for w in pair.values()}
    trace.require(len(pids) == len(PAIRS) * len(ROLES), "lifetime-fixture-pid-reused")
    return witnesses, pids


def capture(root, source, *, with_etw=False):
    with_images = with_etw and os.getenv("PILOTODIN_N12_IMAGE_PATH_CONTROL") == "1"
    with_stop_image = with_images and os.getenv("PILOTODIN_N12_STOP_IMAGE_CONTROL") == "1"
    alias = None
    alias_witness = None
    if with_stop_image:
        system_cmd = Path(os.environ["SystemRoot"]) / "System32" / "cmd.exe"
        alias = root / "pilotodin-stop-image-fixture.exe"
        with system_cmd.open("rb") as source_file, alias.open("xb") as target:
            shutil.copyfileobj(source_file, target)
    with journey.checkpoint_stage("lifetime-window-open", source, ""):
        first = journey.sysmon_tail() + 1
    if with_etw:
        with etw.process_session(root, source) as session:
            with journey.checkpoint_stage("lifetime-fixtures", source, ""):
                witnesses, pids = gather_witnesses(with_images=True) if with_images else gather_witnesses()
                if alias is not None:
                    alias_witness, _ = run_process([str(alias), "/d", "/q"], with_images=True,
                                                   fixture_input=b"exit /b 0\r\n")
                    trace.require(alias_witness["pid"] not in pids, "lifetime-fixture-pid-reused")
    else:
        with journey.checkpoint_stage("lifetime-fixtures", source, ""):
            witnesses, pids = gather_witnesses()
    xml = root / "lifetime-sysmon.xml"
    with journey.checkpoint_stage("lifetime-sysmon-export", source, ""):
        # Give the channel a bounded flush period after the last verified exit.
        time.sleep(3)
        last = journey.sysmon_tail()
        trace.require(first <= last < first + 4096, "lifetime-record-window-invalid")
        journey.export_sysmon(first, last, xml)
    with journey.checkpoint_stage("lifetime-reduction", source, ""):
        records, issues = read_records(xml, first, last, pids)
        packet = redact(witnesses, records, issues, sys.executable)
        result = replay(packet)
        print("N12 lifetime replay " + json.dumps(packet), flush=True)
        print("N12 lifetime verdict " + json.dumps(result), flush=True)
    if with_etw:
        with journey.checkpoint_stage("lifetime-etw-export", source, ""):
            journey.powershell(journey.HELPER, "etw-process-export", root, timeout=90)
        with journey.checkpoint_stage("lifetime-corroboration", source, ""):
            lifecycle = etw.read_process_events(root / "lifetime-etw.jsonl", pids, session["start"], session["end"])
            public_etw = etw.redact(witnesses, lifecycle, session["counters"], os.getpid())
            packet = {"schema_version": 3, "sysmon": packet, "etw": public_etw}
            result = replay(packet)
            print("N12 lifetime ETW replay " + json.dumps(packet), flush=True)
            print("N12 lifetime ETW verdict " + json.dumps(result), flush=True)
        if with_images:
            with journey.checkpoint_stage("lifetime-image-path-comparison", source, ""):
                devices = trace.etw_device_aliases(n12_etw_probe.volume_devices())
                result = etw.image_path_report(witnesses, lifecycle, public_etw, packet["sysmon"]["cases"],
                                               devices, sys.executable)
                print("N12 lifetime image path verdict " + json.dumps(result), flush=True)
        if alias_witness is not None:
            with journey.checkpoint_stage("lifetime-stop-image-comparison", source, ""):
                records = etw.read_process_events(root / "lifetime-etw.jsonl", {alias_witness["pid"]},
                                                  session["start"], session["end"])
                stop_image = etw.stop_image_report(alias_witness, records, session, devices, str(alias))
                print("N12 lifetime stop-image verdict " + json.dumps(stop_image), flush=True)
                if stop_image["verdict"] != "PASS":
                    result = stop_image
    with journey.checkpoint_stage("lifetime-local-copy", source, ""):
        journey.report_file(root / "lifetime-replay.json", packet)
    return 0 if result["verdict"] == "PASS" else 2


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--capture", type=Path)
    mode.add_argument("--capture-etw", type=Path)
    mode.add_argument("--fixture-parent", choices=PAIRS)
    mode.add_argument("--replay", type=Path)
    args = parser.parse_args()
    try:
        if args.replay:
            result = replay(json.loads(args.replay.read_text(encoding="utf-8")))
            print(json.dumps(result))
            return 0 if result["verdict"] == "PASS" else 2
        consent = os.getenv("PILOTODIN_N12_LIFETIME_CONTROL_CONSENT")
        allowed_consent = ({ETW_CONSENT} if args.capture_etw else
                           {CONSENT, ETW_CONSENT} if args.fixture_parent else {CONSENT})
        trace.require(os.name == "nt" and os.getenv("GITHUB_ACTIONS") == "true"
                      and os.getenv("RUNNER_ENVIRONMENT") == "github-hosted"
                      and os.getenv("RUNNER_OS") == "Windows" and os.getenv("GITHUB_RUN_ATTEMPT") == "1"
                      and consent in allowed_consent,
                      "lifetime-control-requires-approved-hosted-windows")
        if args.fixture_parent:
            code = "pass" if args.fixture_parent == "fast" else "import time; time.sleep(0.05)"
            with_images = consent == ETW_CONSENT and os.getenv("PILOTODIN_N12_IMAGE_PATH_CONTROL") == "1"
            if with_images:
                trace.require(sys.stdin.buffer.read(1) == b"1", "fixture-start-signal-missing")
                code = "import sys; assert sys.stdin.buffer.read(1) == b'1'; " + code
            witness, _ = run_process([sys.executable, "-B", "-c", code], with_images=with_images)
            print(json.dumps(witness))
            return 0
        source = os.getenv("PILOTODIN_N12_LIFETIME_SOURCE", "")
        trace.require(re.fullmatch(r"[0-9a-f]{40}", source) and journey.build.git("rev-parse", "HEAD") == source,
                      "lifetime-source-mismatch")
        print(f"N12 lifetime reviewed source {source}", flush=True)
        root = trace.local_disposable_path(args.capture_etw or args.capture, runner_temp_only=True)
        if args.capture_etw and os.getenv("PILOTODIN_N12_DRIVER_EXIT_CONTROL") == "1":
            from qa.p4_research import n12_driver_exit_control

            return n12_driver_exit_control.capture(root, source)
        return capture(root, source, with_etw=args.capture_etw is not None)
    except trace.EvidenceValidationError as exc:
        print(f"N12 lifetime control blocked: {exc}", file=sys.stderr)
    except (AttributeError, KeyError, OSError, RuntimeError, TypeError, ValueError, subprocess.SubprocessError) as exc:
        print(f"N12 lifetime control blocked: {type(exc).__name__}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
