"""Compare Sysmon attribution for an immediate and a retained loopback fixture child."""

import argparse
from contextlib import contextmanager
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from uuid import uuid4

from qa.p4_native import n12_etw_probe as etw
from qa.p4_native import n12_trace as trace
from qa.p4_research import n12_app_journey as journey


# Keep the same file operations, socket endpoints and strict validator in both cases.
CASES = (("immediate", 0), ("held", 4), ("held", 4),
         ("immediate", 0), ("immediate", 0), ("held", 4))


FILE_ACTIVITY = """from pathlib import Path
import sys

original = Path(sys.argv[1]) / 'generated.bin'
renamed = original.with_name('generated-renamed.bin')
with original.open('xb') as stream:
    stream.write(b'n12' * 16384)
    stream.truncate(4096)
original.rename(renamed)
renamed.unlink()
"""


def activity_worker(directory: Path) -> int:
    completed = 0
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline and not (directory / "stop").exists():
        etw.run_writer(FILE_ACTIVITY, directory)
        completed += 1
        if completed == 1:
            (directory / "ready").touch()
        time.sleep(0.08)
    return completed


@contextmanager
def background_activity(directory: Path, summary: dict):
    directory.mkdir()
    with subprocess.Popen(
        [sys.executable, "-B", "-m", "qa.p4_research.n12_socket_lifetime_control", str(directory), "--activity-worker"],
        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
    ) as child:
        try:
            journey.wait_for((directory / "ready").exists, 10, "generated activity did not start", child)
            yield child
        finally:
            (directory / "stop").touch()
            try:
                output, _ = child.communicate(timeout=12)
            except subprocess.TimeoutExpired:
                journey.cleanup_process(child)
                raise
        trace.require(child.returncode == 0, "generated activity failed")
        summary["generated_writer_processes"] = int(output)


def launch_fixture(root: Path, phase: str, hold_seconds: int):
    start = journey.now()
    time.sleep(journey.INITIAL_FIXTURE_LEAD_IN_SECONDS)
    print(f"N12 socket lifetime stage {phase} fixture launch", flush=True)
    raw = journey.quiet(
        [sys.executable, "-B", str(journey.NATIVE / "n12_calibration.py"),
         str(root / phase), "--child-hold-seconds", str(hold_seconds)],
        timeout=25,
    )
    end = journey.now()
    return start, end, json.loads(raw)


def trace_fixture(root: Path, phase: str, hold_seconds: int, summary: dict):
    capture_root = root / (phase + "-capture")
    capture_root.mkdir()
    session = f"PilotODIN-N12-Socket-{uuid4().hex}"
    logman = str(Path(os.environ["SystemRoot"]) / "System32" / "logman.exe")
    with background_activity(capture_root / "activity", summary) as activity:
        journey.start_capture(capture_root, session, logman)
        try:
            time.sleep(1)
            scope = launch_fixture(root, phase, hold_seconds)
            trace.require(activity.poll() is None, "generated activity ended before the marker window froze")
        finally:
            summary["etw"] = etw.stop_trace(session)
    # Match the settle pause between stopping the full trace and the final check.
    time.sleep(3)
    return scope


def compare(root: Path, *, etw_boundary: bool = False) -> dict:
    results = []
    for index, (name, hold_seconds) in enumerate(CASES, 1):
        phase = f"socket-control-{index}-{name}"
        print(f"N12 socket lifetime stage {phase} channel read", flush=True)
        first = journey.sysmon_tail(timeout=15) + 1
        environment = {}
        if etw_boundary:
            start, end, fixture = trace_fixture(root, phase, hold_seconds, environment)
        else:
            start, end, fixture = launch_fixture(root, phase, hold_seconds)
        verdict = {"case": name, "hold_seconds": hold_seconds, "status": "PASS", **environment}
        try:
            journey.verify_fixture_sysmon(root, first, start, end, fixture, phase=phase)
        except trace.EvidenceValidationError as exc:
            verdict.update(status="BLOCKED", reason=str(exc))
        results.append(verdict)
        print("N12 socket lifetime case " + json.dumps(verdict), flush=True)
    return {"etw_boundary": etw_boundary, "cases": results,
            "passed": {name: sum(row["status"] == "PASS" for row in results if row["case"] == name)
                       for name in ("immediate", "held")}}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--etw-boundary", action="store_true")
    mode.add_argument("--activity-worker", action="store_true")
    args = parser.parse_args()
    try:
        allowed = {"GITHUB_ACTIONS": "true", "GITHUB_RUN_ATTEMPT": "1",
                   "RUNNER_ENVIRONMENT": "github-hosted", "RUNNER_OS": "Windows"}
        trace.require(os.name == "nt" and all(os.environ.get(key) == value for key, value in allowed.items()),
                      "socket comparison requires a first-attempt hosted Windows runner")
        root = trace.local_disposable_path(args.directory, runner_temp_only=True)
        if args.activity_worker:
            print(activity_worker(root))
            return 0
        report = compare(root, etw_boundary=args.etw_boundary)
        print("N12 socket lifetime comparison " + json.dumps(report), flush=True)
    except (OSError, RuntimeError, ValueError, subprocess.SubprocessError) as exc:
        print(f"N12 socket lifetime comparison could not complete ({type(exc).__name__}).",
              file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
