"""Compare Sysmon attribution for an immediate and a retained loopback fixture child."""

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

from qa.p4_native import n12_trace as trace
from qa.p4_research import n12_app_journey as journey


# Keep the same file operations, socket endpoints and strict validator in both cases.
CASES = (("immediate", 0), ("held", 4), ("held", 4),
         ("immediate", 0), ("immediate", 0), ("held", 4))


def compare(root: Path) -> dict:
    results = []
    for index, (name, hold_seconds) in enumerate(CASES, 1):
        phase = f"socket-control-{index}-{name}"
        print(f"N12 socket lifetime stage {phase} channel read", flush=True)
        first = journey.sysmon_tail(timeout=15) + 1
        start = journey.now()
        time.sleep(journey.INITIAL_FIXTURE_LEAD_IN_SECONDS)
        print(f"N12 socket lifetime stage {phase} fixture launch", flush=True)
        raw = journey.quiet(
            [sys.executable, "-B", str(journey.NATIVE / "n12_calibration.py"),
             str(root / phase), "--child-hold-seconds", str(hold_seconds)],
            timeout=25,
        )
        fixture = json.loads(raw)
        end = journey.now()
        verdict = {"case": name, "hold_seconds": hold_seconds, "status": "PASS"}
        try:
            journey.verify_fixture_sysmon(root, first, start, end, fixture, phase=phase)
        except trace.EvidenceValidationError as exc:
            verdict.update(status="BLOCKED", reason=str(exc))
        results.append(verdict)
        print("N12 socket lifetime case " + json.dumps(verdict), flush=True)
    return {"cases": results,
            "passed": {name: sum(row["status"] == "PASS" for row in results if row["case"] == name)
                       for name in ("immediate", "held")}}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    args = parser.parse_args()
    try:
        allowed = {"GITHUB_ACTIONS": "true", "GITHUB_RUN_ATTEMPT": "1",
                   "RUNNER_ENVIRONMENT": "github-hosted", "RUNNER_OS": "Windows"}
        trace.require(os.name == "nt" and all(os.environ.get(key) == value for key, value in allowed.items()),
                      "socket comparison requires a first-attempt hosted Windows runner")
        root = trace.local_disposable_path(args.directory, runner_temp_only=True)
        report = compare(root)
        print("N12 socket lifetime comparison " + json.dumps(report), flush=True)
    except (OSError, RuntimeError, ValueError, subprocess.SubprocessError) as exc:
        print(f"N12 socket lifetime comparison could not complete ({type(exc).__name__}).",
              file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
