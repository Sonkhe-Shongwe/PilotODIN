"""Source-reviewed, separately consent-gated *generated* Sysmon bookends.

No PilotODIN launch, no owner data, no installer, no native acceptance.
Importing this module and calling --help cannot initiate collection. The actual
Windows entry requires a NEW source-pinned one-use hosted approval and Sysmon
provisioning by the separately reviewed, normally DISARMED workflow.
"""
from __future__ import annotations

import argparse
from collections.abc import Mapping
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import subprocess
import sys

SCOPE = "n12-generated-sysmon-bookends-only"
CONSENT = "I_APPROVE_ONE_N12_GENERATED_SYSMON_BOOKENDS"
PHASES = ("initial", "final")
LEAD_SECONDS = 0.05


class BookendBlocked(RuntimeError):
    """A fixed-label failure, never a raw process path or event payload."""

    def __init__(self, phase):
        self.phase = phase if phase in ("preflight", *PHASES) else "preflight"
        super().__init__("generated-sysmon-" + self.phase + "-blocked")


def receipt(status, *, phase="none"):
    """Never serialize supplied source identifiers, PIDs, paths or IPs."""
    return {
        "scope": SCOPE,
        "status": status,
        "stage": phase,
        "evidence": "GENERATED_FIXTURE_ONLY",
        "product_launched": False,
        "original_file_handle_evidence": "NOT_COLLECTED",
        "file_mutation_acceptance": "NOT_EVALUATED",
        "native_N12_acceptance": "NOT_EVALUATED",
    }


def require_hosted_approval(source, env, actual_sha):
    """Fail before touching a collector or generated fixture."""
    if (type(source) is not str or re.fullmatch(r"[0-9a-f]{40}", source) is None
            or not isinstance(env, Mapping) or type(actual_sha) is not str
            or actual_sha != source
            or env.get("GITHUB_ACTIONS") != "true"
            or env.get("RUNNER_ENVIRONMENT") != "github-hosted"
            or env.get("RUNNER_OS") != "Windows"
            or env.get("GITHUB_EVENT_NAME") != "push"
            or env.get("GITHUB_REF_NAME") != "feature/live-dev-workspace-20261023"
            or env.get("GITHUB_RUN_ATTEMPT") != "1"
            or type(env.get("GITHUB_RUN_ID")) is not str
            or not re.fullmatch(r"[0-9]+", env["GITHUB_RUN_ID"])
            or env.get("PILOTODIN_N12_GENERATED_BOOKENDS_SOURCE") != source
            or env.get("PILOTODIN_N12_GENERATED_BOOKENDS_CONSENT") != CONSENT
            or not env.get("RUNNER_TEMP")):
        raise BookendBlocked("preflight")


def run_bookend_sequence(root, manifest, *, clock, pause, generate, verify):
    """Only injected fixture callbacks; all events are checked in original windows.

    This seam performs NO host work itself. A real approved runner supplies the
    existing calibration and strict Sysmon verifier. Synthetic tests supply fakes.
    """
    if (type(manifest) is not dict or type(manifest.get("sysmon_first_record")) is not int
            or manifest["sysmon_first_record"] < 1
            or type(manifest.get("processes")) is not list
            or type(manifest.get("loopback_ports")) is not list
            or not all(callable(fn) for fn in (clock, pause, generate, verify))):
        raise BookendBlocked("preflight")
    # Each phase must begin at the previous VERIFIED Sysmon channel tail + 1.
    # Re-reading the initial fixture in the final window can falsely classify
    # a recycled parent PID as a pre-window birth, and can obscure gaps.
    next_first_record = manifest["sysmon_first_record"]
    for phase in PHASES:
        try:
            # Both windows begin BEFORE sleeping and spawning the generated
            # parent, preventing millisecond-truncated Sysmon UtcTime events
            # from appearing before the real audit start. No tolerance added.
            start = clock()
            if type(start) is not datetime or start.tzinfo is None:
                raise ValueError("generated-bookend-start-clock-invalid")
            pause(LEAD_SECONDS)
            record = generate(root / ("generated-" + phase), manifest,
                              child_hold_seconds=4)
            end = clock()
            if (type(end) is not datetime or end.tzinfo is None
                    or end <= start or type(record) is not dict
                    or record.get("role") != "calibration"):
                raise ValueError("generated-bookend-window-or-fixture-invalid")
            verified_last = verify(root, next_first_record, start, end, record,
                                   phase=phase)
            if type(verified_last) is not int or verified_last < next_first_record:
                raise ValueError("generated-bookend-sysmon-tail-unverified")
            next_first_record = verified_last + 1
        except Exception as exc:
            raise BookendBlocked(phase) from exc
    return receipt("GENERATED_BOOKENDS_CORROBORATED")


def capture_approved(source, env):
    """Optional future Windows entry; not invoked by source-only GitHub CI."""
    # Source identity and consent must precede the FIRST Sysmon channel read,
    # directory creation, generated socket/process, or file change.
    if os.name != "nt" or not isinstance(env, Mapping):
        raise BookendBlocked("preflight")
    try:
        result = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True,
                                check=True, timeout=10, text=True)
        actual = result.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        raise BookendBlocked("preflight") from None
    require_hosted_approval(source, env, actual)
    from qa.p4_native import n12_trace as trace
    from qa.p4_research import n12_app_journey as journey

    run_id = env["GITHUB_RUN_ID"]
    try:
        root = trace.local_disposable_path(
            Path(env["RUNNER_TEMP"]) / ("pilotodin-n12-generated-bookends-" + run_id),
            runner_temp_only=True)
        root.mkdir(exist_ok=False)
        manifest = {"processes": [], "loopback_ports": [],
                    "sysmon_first_record": journey.sysmon_tail() + 1}
        return run_bookend_sequence(
            root, manifest, clock=journey.now, pause=journey.time.sleep,
            generate=journey.calibrate, verify=journey.verify_fixture_sysmon)
    except BookendBlocked:
        raise
    except Exception:
        raise BookendBlocked("preflight") from None


def main(argv=None, *, env=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--capture", action="store_true")
    parser.add_argument("--source")
    args = parser.parse_args(argv)
    if not args.capture or args.source is None:
        print(json.dumps(receipt("BLOCKED", phase="preflight"), sort_keys=True))
        return 2
    try:
        result = capture_approved(args.source, os.environ if env is None else env)
        print(json.dumps(result, sort_keys=True))
        return 0
    except BookendBlocked as exc:
        print(json.dumps(receipt("BLOCKED", phase=exc.phase), sort_keys=True))
        return 2


if __name__ == "__main__":
    sys.exit(main())
