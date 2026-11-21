"""Capture and verify one generated protected-file write and restore."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys

from qa.p4_native import n12_etw_probe as probe, n12_trace as trace
from qa.p4_native.n12_etw_correlate import file_lifetime_report, number
from qa.p4_research import n12_app_build as build


CONSENT = "I_APPROVE_ONE_N12_PROTECTED_RESTORE"
ORIGINAL = b"PilotODIN original\n"
MODIFIED = b"PilotODIN modified\n"
STAGES = ("mutate", "restore")


def write_payload(path, payload):
    with path.open("r+b", buffering=0) as stream:
        probe.verify_handle_path(stream, path)
        if stream.write(payload) != len(payload):
            raise RuntimeError("The protected control write was incomplete.")


def exercise_restore(path):
    before = build.digest(path)
    trace.require(before == hashlib.sha256(ORIGINAL).hexdigest(), "the generated restore baseline changed")
    stages = {}
    for label, payload in zip(STAGES, (MODIFIED, ORIGINAL)):
        start = probe.utc_ticks()
        pid = probe.run_writer(
            "from pathlib import Path\nimport sys\n"
            "from qa.p4_native.n12_protected_restore import write_payload\n"
            "write_payload(Path(sys.argv[1]), bytes.fromhex(sys.argv[2]))",
            path, payload.hex(),
        )
        stages[label] = {"pid": pid, "start": start, "end": probe.utc_ticks(), "size": len(payload)}
        if path.read_bytes() != payload:
            raise RuntimeError("The protected control content did not match the generated write.")
        stages[label]["digest"] = hashlib.sha256(payload).hexdigest()
    return {"path": str(path), "before": before, "stages": stages}


def capture_control(root):
    env = os.environ
    reviewed = env.get("PILOTODIN_N12_PROTECTED_RESTORE_SOURCE", "")
    trace.require(env.get("GITHUB_EVENT_NAME") == "push" and env.get("GITHUB_RUN_ATTEMPT") == "1"
                  and env.get("GITHUB_REF_NAME") == build.BRANCH
                  and env.get("PILOTODIN_N12_PROTECTED_RESTORE_CONSENT") == CONSENT
                  and re.fullmatch(r"[0-9a-f]{40}", reviewed), "fresh protected restore approval is required")
    root = trace.local_disposable_path(root, runner_temp_only=True)
    trace.require(build.git("rev-parse", "HEAD") == reviewed
                  and not build.git("status", "--porcelain", "--untracked-files=no"),
                  "checkout differs from the approved protected restore source")

    root.mkdir()
    protected = root / "synthetic-protected"
    protected.mkdir()
    path = protected / "restore.bin"
    path.write_bytes(ORIGINAL)
    capture = probe.capture_fixture(root, calibration_only=True, thread_context=True,
                                    protected_restore=lambda: exercise_restore(path))
    capture["protected_restore"]["after"] = build.digest(path)
    return capture


def inspect_restore_writes(control, records, devices, bounds, expected_path, *, require_single_write=False):
    """Verify two generated writes from an independently witnessed sequence."""
    target = trace.windows_path(str(expected_path))
    trace.require(trace.windows_path(control["path"]) == target, "the restore target differs from the fixture")
    stages = control["stages"]
    baseline = hashlib.sha256(ORIGINAL).hexdigest()
    trace.require(control["before"] == control["after"] == stages["restore"]["digest"] == baseline
                  and stages["mutate"]["digest"] == hashlib.sha256(MODIFIED).hexdigest(),
                  "the protected control's change and restore were not verified")

    roles, births, verified, write_issues = {}, {}, {}, {}
    previous_end = bounds[0]
    for label in STAGES:
        stage = stages[label]
        pid, first, last = stage["pid"], stage["start"], stage["end"]
        trace.require(type(pid) is int and pid > 0 and pid not in roles
                      and type(first) is int and type(last) is int
                      and previous_end <= first < last <= bounds[1] and stage["size"] == len(ORIGINAL),
                      "invalid protected control writer, window or write length")
        previous_end = last
        lifetimes = [event for event in records if event["lifecycle"] and event["id"] in {1, 2}
                     and number(event["data"].get("ProcessID", event["data"].get("ProcessId"))) == pid]
        trace.require(len(lifetimes) == 2 and [event["id"] for event in lifetimes] == [1, 2]
                      and first <= lifetimes[0]["ticks"] < lifetimes[1]["ticks"] <= last,
                      "the protected control writer lifetime is missing or ambiguous")
        born, exited = [event["ticks"] for event in lifetimes]
        roles[pid], births[pid] = label, born
        result = file_lifetime_report({**stage, "path": target, "start": born, "end": exited}, records, devices,
                                      verify_write_path=True, require_single_write=require_single_write)
        path_evidence = result.get("write_object_path", {})
        verified[label] = result["status"] == "PASS" and path_evidence.get("status") == "PASS"
        if not verified[label]:
            write_issues[label] = result.get("reason") or path_evidence.get("reason") or "write-path-unverified"
    return roles, births, verified, write_issues


def reduce_control(manifest, control, path):
    trace.require(manifest["schema_version"] == 1 and manifest["disposable"] is True,
                  "expected a disposable protected restore manifest")
    start, end = (trace.utc_time(manifest[key]) for key in ("start_utc", "end_utc"))
    issues = set()
    bounds, devices = trace.etw_capture_contract(manifest, start, end, issues)
    with trace.evidence_stage("ETW restore event stream"):
        records = list(trace.etw_events(path, bounds, manifest["etw"]["events_sha256"]))
    protected = [trace.windows_path(root) for root in manifest["protected_roots"].values()]
    target = trace.windows_path(control["path"])
    trace.require(any(trace.inside(target, root) for root in protected), "restore target is outside the protected scope")
    roles, births, verified, write_issues = inspect_restore_writes(control, records, devices, bounds, target)

    _, violations, _, unresolved = trace.inspect_etw_files(
        manifest, path, start, end, {}, {}, protected,
        {label: protected for label in STAGES}, issues,
        synthetic_process_roles=roles, synthetic_process_births=births,
    )
    observed = {label: violations.get(f"protected:{label}:write", 0) for label in STAGES}
    scoped_gaps = any(key.split(":")[0] in STAGES for key in unresolved)
    status = all(verified.values()) and all(count == 1 for count in observed.values()) and not scoped_gaps
    status = status and not (issues - {"etw-mutation-coverage-unresolved"})
    return {"control_status": "PASS" if status else "BLOCKED", "endpoint_match": True,
            "write_path_verified": verified, "write_issues": write_issues, "protected_writes": observed,
            "strict_coverage": "BLOCKED" if issues else "CALIBRATED", "coverage_issues": sorted(issues)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_subparsers(dest="mode", required=True)
    modes.add_parser("capture").add_argument("root", type=Path)
    reduce = modes.add_parser("reduce")
    for name in ("manifest", "capture", "events"):
        reduce.add_argument(name, type=Path)
    args = parser.parse_args()
    try:
        if args.mode == "capture":
            print(json.dumps(capture_control(args.root)))
            return 0
        result = reduce_control(trace.read_json(args.manifest), trace.read_json(args.capture)["protected_restore"],
                                args.events)
        print(json.dumps(result, sort_keys=True))
        return 0 if result["control_status"] == "PASS" else 2
    except trace.EvidenceValidationError as exc:
        print(f"N12 protected restore BLOCKED: {exc}", file=sys.stderr)
    except (*trace.EVIDENCE_ERRORS, RuntimeError, subprocess.SubprocessError) as exc:
        print(f"N12 protected restore BLOCKED: {type(exc).__name__}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
