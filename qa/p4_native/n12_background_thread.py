"""Check paired journey snapshots against one known pre-existing ETW writer."""
import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from threading import get_native_id
import time

from qa.p4_native import n12_etw_probe as probe, n12_trace as trace
from qa.p4_native.n12_etw_correlate import completion_evidence, number
from qa.p4_research import n12_app_build as build, n12_app_journey as journey


CONSENT = "I_APPROVE_ONE_N12_BACKGROUND_THREAD"
PAYLOAD = b"PilotODIN background thread control\n"


def write_once(root):
    path = root / "background.bin"
    with path.open("xb", buffering=0) as stream:
        probe.verify_handle_path(stream, path)
        identity = root / "identity.tmp"
        identity.write_text(str(get_native_id()), encoding="ascii")
        identity.rename(root / "ready")
        if sys.stdin.buffer.read(1) != b"w":
            raise RuntimeError("The background writer was not signalled.")
        if stream.write(PAYLOAD) != len(PAYLOAD):
            raise RuntimeError("The background write was incomplete.")
        (root / "done").touch(exist_ok=False)
        # Remain alive with the same thread and handle for the second snapshot.
        sys.stdin.buffer.read(1)


def wait_for_marker(writer, marker):
    deadline = time.monotonic() + 10
    while writer.poll() is None and time.monotonic() < deadline:
        if marker.is_file():
            return
        time.sleep(0.025)
    raise RuntimeError("The background writer did not reach its expected checkpoint.")


def capture_control(root):
    env = os.environ
    reviewed = env.get("PILOTODIN_N12_BACKGROUND_THREAD_SOURCE", "")
    trace.require(env.get("GITHUB_EVENT_NAME") == "push" and env.get("GITHUB_RUN_ATTEMPT") == "1"
                  and env.get("GITHUB_REF_NAME") == build.BRANCH
                  and env.get("PILOTODIN_N12_BACKGROUND_THREAD_CONSENT") == CONSENT
                  and re.fullmatch(r"[0-9a-f]{40}", reviewed), "fresh background writer approval is required")
    root = trace.local_disposable_path(root, runner_temp_only=True)
    trace.require(build.git("rev-parse", "HEAD") == reviewed
                  and not build.git("status", "--porcelain", "--untracked-files=no"),
                  "checkout differs from the approved background writer source")
    root.mkdir()
    with subprocess.Popen([sys.executable, "-B", "-m", __spec__.name, "writer", str(root)],
                          stdin=subprocess.PIPE, stdout=subprocess.DEVNULL,
                          stderr=subprocess.DEVNULL) as writer:
        try:
            wait_for_marker(writer, root / "ready")
            tid = int((root / "ready").read_text(encoding="ascii"))
            before, threads_before = journey.process_bookend()
            trace.require(before and threads_before, "the first journey snapshot is unavailable")

            def exercise():
                control["start"] = probe.utc_ticks()
                writer.stdin.write(b"w")
                writer.stdin.flush()
                wait_for_marker(writer, root / "done")
                control["end"] = probe.utc_ticks()

            control = {"pid": writer.pid, "tid": tid}
            capture = probe.capture_fixture(root, calibration_only=True, thread_context=True,
                                            after_calibration=exercise)
            after, threads_after = journey.process_bookend()
            trace.require(after and threads_after, "the second journey snapshot is unavailable")
            writer.stdin.close()
            trace.require(writer.wait(timeout=10) == 0, "the background writer did not exit cleanly")
        finally:
            if writer.poll() is None:
                writer.kill()

    trace.require((root / "background.bin").read_bytes() == PAYLOAD,
                  "the generated file did not contain the expected write")
    capture["background_thread"] = {
        **control, "bookends": {
            "before": [row for row in before if row["pid"] == writer.pid],
            "after": [row for row in after if row["pid"] == writer.pid],
            "threads_before": [row for row in threads_before if row["tid"] == tid],
            "threads_after": [row for row in threads_after if row["tid"] == tid],
        },
    }
    return capture


def reduce_control(manifest, control, path):
    trace.require(manifest["schema_version"] == 1 and manifest["disposable"] is True,
                  "expected a disposable background writer manifest")
    start, end = (trace.utc_time(manifest[key]) for key in ("start_utc", "end_utc"))
    issues = set()
    bounds, _ = trace.etw_capture_contract(manifest, start, end, issues)
    trace.require(not issues, "ETW reported event or buffer loss")
    events = list(trace.etw_events(path, bounds, manifest["etw"]["events_sha256"]))
    pid, tid, first, last = (control[key] for key in ("pid", "tid", "start", "end"))
    trace.require(all(type(value) is int and value > 0 for value in (pid, tid, first, last))
                  and bounds[0] <= first < last <= bounds[1], "invalid background writer or write window")

    process_ids, thread_ids = set(), set()
    for event in events:
        if event["lifecycle"]:
            data = event["data"]
            if event["id"] in (1, 2):
                process_ids.add(number(data.get("ProcessID", data.get("ProcessId"))))
            elif event["id"] in (3, 4):
                thread_ids.add(number(data.get("ThreadID", data.get("TThreadId"))))
    bookends = control["bookends"]
    processes = trace.stable_process_bookend_records(bookends, bounds[0], process_ids)
    threads = trace.stable_thread_bookends(bookends, bounds[0], processes, thread_ids)
    trace.require(threads.get(tid) == pid, "paired snapshots did not corroborate the known writer thread")

    # Use the tolerance already applied to the independent pre-opened writer.
    earliest = max(bounds[0], first - 100_000)
    latest = min(bounds[1], last + 100_000)
    files = sorted((event for event in events if not event["lifecycle"]), key=lambda event: event["ticks"])
    written = [
        event for event in files if event["id"] == 16 and event["pid"] == pid
        and earliest <= event["ticks"] <= latest
        and number(event["data"].get("IOSize")) == len(PAYLOAD)
        and number(event["data"].get("ByteOffset")) == 0
    ]
    trace.require(len(written) == 1, "the trace did not contain one matching write")
    request = written[0]
    data = request["data"]
    trace.require(number(data.get("IssuingThreadId", data.get("ThreadId"))) == tid,
                  "the trace did not identify the expected issuing thread")
    completion, _ = completion_evidence(files, request, latest + 1)
    trace.require(completion is not None,
                  "the matching write lacked a verified successful completion")
    trace.require(all(number(completion["data"].get(field)) in {None, 0, number(data.get(field))}
                      for field in ("FileKey", "FileObject")), "completion file identity conflicts with the write")
    return {"control_status": "PASS", "known_completed_writes": 1,
            "issuing_thread": "bookend-header-agrees", "validated_etw_events": len(events),
            "scope": "background writer thread identity"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_subparsers(dest="mode", required=True)
    for mode in ("capture", "writer"):
        modes.add_parser(mode).add_argument("root", type=Path)
    reduce = modes.add_parser("reduce")
    for name in ("manifest", "capture", "events"):
        reduce.add_argument(name, type=Path)
    args = parser.parse_args()
    try:
        if args.mode == "writer":
            write_once(trace.local_disposable_path(args.root, runner_temp_only=True))
            return 0
        if args.mode == "capture":
            result = capture_control(args.root)
        else:
            result = reduce_control(trace.read_json(args.manifest),
                                    trace.read_json(args.capture)["background_thread"], args.events)
        print(json.dumps(result, sort_keys=True))
        return 0
    except trace.EvidenceValidationError as exc:
        print(f"N12 background writer BLOCKED: {exc}", file=sys.stderr)
    except (*trace.EVIDENCE_ERRORS, RuntimeError, subprocess.SubprocessError) as exc:
        print(f"N12 background writer BLOCKED: {type(exc).__name__}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
