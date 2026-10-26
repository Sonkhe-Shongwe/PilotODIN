#!/usr/bin/env python3
"""One isolated P2 four-source report DevQA gate. No Tauri, models or user data.

Runs existing FastAPI/SQLite via TestClient ONLY against disposable DevQA home.
Archived evidence is status-only: never source CSV, rendered HTML/PDF, or rows.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from qa_foundation import create_run, default_root, scan_files

EXPECTED = {"contract": 3, "mixed": 9}
PATTERNS = {"contract": "test_p2_mixed_runner_contract.py",
            "mixed": "test_p2_mixed_report_devqa.py"}


def simple_status(result, required):
    """Fail closed on missing, forged-looking or partial worker outcomes."""
    if not isinstance(result, dict) or not isinstance(required, int) or required <= 0:
        return "BLOCKED"
    if (result.get("count") != required or result.get("tests_run") != required or
            result.get("skipped") or result.get("errors")):
        return "BLOCKED"
    if result.get("failures"):
        return "FAIL"
    if result.get("state") != "PASS":
        return "BLOCKED"
    cases = result.get("cases")
    if not isinstance(cases, list) or len(cases) != required:
        return "BLOCKED"
    if any(not isinstance(case, str) or not case.startswith("test_p2_mixed_") for case in cases):
        return "BLOCKED"
    if len(set(cases)) != required:
        return "BLOCKED"
    return "PASS"


def discover(pattern):
    suite = unittest.defaultTestLoader.discover(str(ROOT / "tests"), pattern=pattern)
    def names(node):
        for item in node:
            if isinstance(item, unittest.TestSuite):
                yield from names(item)
            else:
                yield item.id()
    return suite, list(names(suite))


def worker(kind):
    """Child process environment is isolated BEFORE importing the app."""
    try:
        if kind not in PATTERNS:
            raise RuntimeError("Invalid focused worker type")
        if kind == "mixed":
            home = Path(os.environ["PILOTODIN_HOME"]).resolve()
            run = Path(os.environ["PILOTODIN_DEVQA_RUN"]).resolve()
            if home != run / "workspace" or not (run / "manifest.json").is_file():
                raise RuntimeError("Refusing unexpected test workspace")
            # Imports of backend modules only occur when unittest loads tests.
            import fitz
            import fastapi
        suite, names = discover(PATTERNS[kind])
        if len(names) != EXPECTED[kind]:
            raise RuntimeError("Focused test count has changed; review before running")
        result = unittest.TestResult()
        suite.run(result)
        failed = sorted({item.id() for item, _ in result.failures})
        errors = sorted({item.id() for item, _ in result.errors})
        skipped = sorted({item.id() for item, _ in result.skipped})
        state = ("BLOCKED" if errors or skipped or result.testsRun != len(names)
                 else "FAIL" if failed else "PASS")
        output = {"state": state, "count": len(names),
                  "tests_run": result.testsRun,
                  "cases": names, "failures": failed,
                  "errors": errors, "skipped": skipped}
    except Exception:
        # Details are deliberately not serialized to avoid leaking test-row content.
        output = {"state": "BLOCKED", "count": EXPECTED.get(kind, 0),
                  "tests_run": 0, "cases": [], "failures": [],
                  "errors": ["worker_bootstrap"], "skipped": []}
    print(json.dumps(output, sort_keys=True))
    return 0 if output["state"] == "PASS" else 2


def checksum(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for part in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(part)
    return h.hexdigest()


def execute():
    run = None
    root = ROOT
    result = {"schema": 1, "state": "BLOCKED", "product_acceptance": "NOT_TESTED",
              "scope": "P2 synthetic four-evidence report API/rendering, no native Save As",
              "stages": {}, "unverified": [
                  "reader-facing row/fact/finding omission disclosure",
                  "true visual A4 clipping/print quality, beyond text and page bounds",
                  "installed release and real dataset behavior"]}
    try:
        if os.name != "nt" or not os.environ.get("LOCALAPPDATA"):
            raise RuntimeError("Requires Windows with LOCALAPPDATA")
        if os.environ.get("PILOTODIN_HOME"):
            # Respect a legitimate existing user home; subprocess uses ONLY run/workspace.
            result["preexisting_home_overridden_only_in_test_child"] = True
        qa_root = default_root()
        # qa_foundation validates the root and its ancestors; also refuse linked
        # preexisting *children* before allocating inside runs or archiving.
        is_link = lambda p: p.is_symlink() or getattr(p, "is_junction", lambda: False)()
        for directory in (qa_root, qa_root / "runs", qa_root / "archive"):
            if directory.exists() and is_link(directory):
                raise RuntimeError("DevQA contains linked run/archive directory")
        run, manifest = create_run(qa_root, "P2-MIXED-REPORT", root)
        if (run.parent.resolve() != (qa_root / "runs").resolve()
                or (run / "workspace").is_symlink()
                or (run / "manifest.json").is_symlink()):
            raise RuntimeError("DevQA run provenance or workspace link invalid")
        result["run_id"] = run.name
        manifest_path = run / "manifest.json"
        selected = ["tools/p2_mixed_report_devqa.py",
                    "tests/test_p2_mixed_runner_contract.py",
                    "tests/test_p2_mixed_report_devqa.py"]
        findings, blocks = scan_files(root, selected)
        # Preflight risk questions are visible in the result; do not silently suppress.
        result["preflight"] = {"blockers": blocks, "findings": findings,
                               "source_sha256": {item: checksum(root / item) for item in selected}}
        if blocks:
            raise RuntimeError("Static source preflight BLOCKED")
        env = os.environ.copy()
        env["PILOTODIN_HOME"] = str(run / "workspace")
        env["PILOTODIN_DEVQA_RUN"] = str(run)
        env["RL_invariant"] = "1"
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        env["PYTHONPATH"] = str(root)
        # Run pure standard-library QA-contract cases first. No product import.
        for kind in ("contract", "mixed"):
            cmd = [sys.executable, "-B", str(Path(__file__).resolve()), "--worker", kind]
            try:
                completed = subprocess.run(cmd, cwd=root, env=env, capture_output=True,
                                           text=True, timeout=180, check=False)
            except subprocess.TimeoutExpired:
                result["stages"][kind] = {"state": "BLOCKED", "reason": "worker_timeout"}
                break
            try:
                reply = json.loads(completed.stdout.strip())
            except (ValueError, TypeError):
                reply = {"state": "BLOCKED", "count": 0, "tests_run": 0}
            assessed = simple_status(reply, EXPECTED[kind])
            if completed.returncode not in (0, 2) or (completed.returncode == 0) != (assessed == "PASS"):
                assessed = "BLOCKED"
            result["stages"][kind] = {
                "state": assessed,
                "count": reply.get("count", 0), "tests_run": reply.get("tests_run", 0),
                "failed_cases": reply.get("failures", []), "error_cases": reply.get("errors", []),
                "skipped_cases": reply.get("skipped", [])}
            if assessed != "PASS":
                break
        stages = result["stages"]
        if all(stages.get(k, {}).get("state") == "PASS" for k in ("contract", "mixed")):
            result["state"] = "REVIEW_REQUIRED"  # Product boundaries intentionally unverified.
            result["scoped_tests"] = "9 PASS; 3 runner contract tests PASS"
        elif any(entry.get("state") == "FAIL" for entry in stages.values()):
            result["state"] = "FAIL"
        else:
            result["state"] = "BLOCKED"
    except Exception:
        result["state"] = "BLOCKED"
        result["bootstrap_failure"] = True
    finally:
        if run is not None:
            # Write one status-only diagnostic even if worker discovery or fixtures fail.
            status = run / "diagnostics" / "result.json"
            manifest_path = run / "manifest.json"
            try:
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                manifest["state"] = result["state"]
                manifest["product_acceptance"] = "NOT_TESTED"
                manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
                status.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
                archive = run.parent.parent / "archive" / (run.name + ".zip")
                with zipfile.ZipFile(archive, "x", zipfile.ZIP_DEFLATED) as bundle:
                    bundle.write(status, "result.json")
                    bundle.write(manifest_path, "manifest.json")
                result["archive"] = str(archive)
            except (OSError, ValueError, RuntimeError) as exc:
                result["state"] = "BLOCKED"
                result["archive_failure"] = type(exc).__name__
            print("P2 MIXED-REPORT DEVQA: " + result["state"])
            print("RUN: " + str(run))
            if result.get("archive"):
                print("STATUS-ONLY DIAGNOSTIC ZIP: " + result["archive"])
            elif result.get("archive_failure"):
                print("ZIP BLOCKED: " + result["archive_failure"])
            for name, stage in result["stages"].items():
                print(name.upper() + " TESTS: " + stage["state"] + " (" +
                      str(stage.get("tests_run", 0)) + " executed)")
            if result["state"] == "REVIEW_REQUIRED":
                print("Focused test cases passed; disclosure and visual-layout risks STILL require review.")
        else:
            print("P2 MIXED-REPORT DEVQA: BLOCKED before run allocation. No product test started.")
    return 0 if result["state"] == "REVIEW_REQUIRED" else 2


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--worker", choices=("contract", "mixed"))
    args = ap.parse_args()
    if args.worker:
        return worker(args.worker)
    return execute()


if __name__ == "__main__":
    raise SystemExit(main())
