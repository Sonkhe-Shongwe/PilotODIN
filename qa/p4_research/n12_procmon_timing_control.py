"""Measure one generated create in the same approved Procmon and ETW session."""
import argparse
import csv
import json
import ntpath
import os
from pathlib import Path
import re
import subprocess
import sys

from qa.p4_native import n12_etw_probe as etw, n12_lifetime_control as handles, n12_trace as trace
from qa.p4_native.n12_exit_corroboration import EtwLifetimes, compare_image_path
from qa.p4_research import n12_app_build as build, n12_app_journey as journey
from qa.p4_research import n12_procmon_environment_control as procmon


CONSENT = "I_APPROVE_ONE_N12_PROCMON_TIMING_CONTROL"


def approved_run(root):
    env = os.environ
    source = env.get("PILOTODIN_N12_PROCMON_TIMING_SOURCE", "")
    run_id = env.get("GITHUB_RUN_ID", "")
    trace.require(env.get("GITHUB_EVENT_NAME") == "push" and env.get("GITHUB_RUN_ATTEMPT") == "1"
                  and env.get("GITHUB_REF_NAME") == build.BRANCH
                  and env.get("PILOTODIN_N12_PROCMON_TIMING_CONSENT") == CONSENT
                  and re.fullmatch(r"[0-9a-f]{40}", source) and re.fullmatch(r"[0-9]+", run_id)
                  and build.git("rev-parse", "HEAD") == source,
                  "exact-source hosted Procmon timing approval required")
    root = trace.local_disposable_path(root, runner_temp_only=True)
    trace.require(root == Path(env["RUNNER_TEMP"]).absolute() / f"pilotodin-n12-live-{run_id}",
                  "unexpected timing capture root")
    return root, {"source_sha": source, "run_id": run_id, "run_attempt": "1"}


def capture(root, run):
    source = run["source_sha"]
    with (root / "private-timing-etw.json").open("x", encoding="utf-8") as stream:
        session = f"PilotODIN-N12-Timing-{run['run_id']}"
        devices = etw.volume_devices()
        start = journey.now()
        journey.start_journey_etw(root, session, source, "")
        try:
            with journey.checkpoint_stage("timing-child-create", source, ""):
                parent, output = handles.run_process(
                    [sys.executable, "-B", "-m", "qa.p4_research.n12_procmon_timing_control",
                     "fixture", str(root)], with_images=True,
                )
                child = json.loads(output)
        finally:
            counters, end = journey.stop_capture(root, session, {**run, "executable_sha256": ""}, start, devices)
        with journey.checkpoint_stage("timing-etw-export", source, ""):
            journey.powershell(journey.HELPER, "etw-export", "-CaptureRoot", root, timeout=180)
        json.dump({"run": run, "parent": parent, "child": child, "etw": {
            "schema_version": 1, "start_utc": start.isoformat(), "end_utc": end.isoformat(),
            "counters": counters, "volume_devices": devices,
            "events_sha256": build.digest(root / "etw.jsonl"),
        }}, stream)


def trace_process(role, handle, parent=""):
    return trace.Process(role, parent, handle["pid"], trace.windows_path(handle["image_dos"]), None,
                         journey.timestamp_from_ticks(handle["birth"]), "",
                         journey.timestamp_from_ticks(handle["exit"]))


def reduce(root, run, capture_data, window):
    trace.require(capture_data["run"] == run and window["run"] == run, "timing capture provenance mismatch")
    trace.require(window["clock_utc"] is True, "Procmon host clock was not UTC")
    csv_path = root / "capture-utf8.csv"
    trace.require(build.digest(csv_path) == window["csv_sha256"], "Procmon export digest mismatch")
    start, end = (trace.utc_time(capture_data["etw"][key]) for key in ("start_utc", "end_utc"))
    procmon_start, procmon_end = (trace.utc_time(window[key]) for key in ("start_utc", "end_utc"))
    trace.require(procmon_start <= start < end <= procmon_end and start.date() == end.date(),
                  "collectors do not share a same-day timing window")
    parent_handle, child = capture_data["parent"], capture_data["child"]
    child_handle = child["witness"]
    parent = trace_process("parent", parent_handle)
    writer = trace_process("child", child_handle, parent.guid)
    before, after = child["clock"]["before"], child["clock"]["after"]
    trace.require(parent.pid != writer.pid and parent.pid == child["parent_pid"] and writer.pid == child["pid"]
                  and ntpath.basename(writer.image) == child["image"].casefold()
                  and type(before) is int and type(after) is int
                  and trace.utc_ticks(start) <= parent_handle["birth"] <= child_handle["birth"] <= before < after
                  <= child_handle["exit"] <= parent_handle["exit"] <= trace.utc_ticks(end),
                  "fixture handles or measured create window conflict")

    def verify_lifetimes(events, devices, bounds, issues):
        trace.require("etw-event-or-buffer-loss" not in issues, "etw-event-or-buffer-loss")
        lifetimes = EtwLifetimes(events, devices, bounds)
        for process, handle in ((parent, parent_handle), (writer, child_handle)):
            trace.require(compare_image_path(handle["image_native"], process.image, devices) == "exact-path-match",
                          "original handle image paths disagree")
            lifetimes.find(process, handle_witness=handle)
        trace.require(lifetimes.parent_sequence_comparison(writer, parent) == "etw-parent-sequence-agrees",
                      "ETW parent sequence unverified")

    creates = []
    trace.inspect_etw_files(
        capture_data, root / "etw.jsonl", start, end, {p.guid: p for p in (parent, writer)},
        {writer.guid: "calibration"}, (), {}, set(), observe_lifetimes=verify_lifetimes,
        observe_create=lambda *args: creates.append(args),
    )
    with csv_path.open(encoding="utf-8-sig", newline="") as stream:
        rows = csv.DictReader(stream, strict=True)
        trace.require({"Time of Day", "PID", "Process Name", "Operation", "Path", "Result", "Detail"}
                      <= set(rows.fieldnames or ()), "Procmon export columns missing")
        report = procmon.replay_create_timing(rows, child, start, end, before=before, after=after,
                                             writer_guid=writer.guid, etw_creates=creates)
    return {**report, **run, "scope": "one-generated-create-timing",
            "procmon_shutdown_verified": window["shutdown_verified"] is True, "procmon_loss_reviewed": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("capture", "fixture", "reduce"))
    parser.add_argument("root", type=Path)
    args = parser.parse_args()
    try:
        root, run = approved_run(args.root)
        if args.action == "capture":
            capture(root, run)
        elif args.action == "fixture":
            trace.require(sys.stdin.buffer.read(1) == b"1", "parent handle witness unavailable")
            print(json.dumps(procmon.capture(root, timed=True)))
        else:
            with trace.evidence_stage("Procmon and ETW timing comparison"):
                report = reduce(root, run, trace.read_json(root / "private-timing-etw.json"),
                                trace.read_json(root / "environment-window.json"))
            print(json.dumps(report, sort_keys=True), flush=True)
            return 0 if report["status"] == "PASS" else 2
        return 0
    except trace.EvidenceValidationError as exc:
        print(f"N12 timing control blocked: {exc}", file=sys.stderr)
    except (*trace.EVIDENCE_ERRORS, subprocess.SubprocessError) as exc:
        print(f"N12 timing control blocked: {type(exc).__name__}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
