#!/usr/bin/env python3
"""Focused, synthetic-only P2 report disclosure and PDF-page-bounds QA.

No API server, native Save As, ML training, Qwen, installer or user data.
The only archived outputs are final result.json and manifest.json.
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
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))
from qa_foundation import create_run, default_root, scan_files

PHASE = "P2-REPORT-DISPLAY"
PATTERN = "test_p2_report_display_disclosure.py"
COUNT = 5


def safe_result_file(run):
    return run / "diagnostics" / "worker-display.json"


def worker():
    run = None
    phase = "workspace_check"
    try:
        home = Path(os.environ["PILOTODIN_HOME"]).resolve()
        run = Path(os.environ["PILOTODIN_DEVQA_RUN"]).resolve()
        if home != run / "workspace" or not (run / "manifest.json").is_file():
            raise RuntimeError("Invalid isolated workspace")
        manifest = json.loads((run / "manifest.json").read_text(encoding="utf-8"))
        if manifest.get("phase") != PHASE or manifest.get("state") != "READY_NOT_TESTED":
            raise RuntimeError("Nonfresh DevQA run")
        phase = "discovery"
        suite = unittest.defaultTestLoader.discover(str(ROOT / "tests"), pattern=PATTERN)
        def members(node):
            for item in node:
                if isinstance(item, unittest.TestSuite):
                    yield from members(item)
                else:
                    yield item.id()
        names = list(members(suite))
        if len(names) != COUNT or len(set(names)) != COUNT:
            raise RuntimeError("Focused test count mismatch")
        phase = "execution_or_fixture"
        result = unittest.TestResult()
        suite.run(result)
        errors = sorted({case.id() for case, _ in result.errors})
        failures = sorted({case.id() for case, _ in result.failures})
        skipped = sorted({case.id() for case, _ in result.skipped})
        state = ("BLOCKED" if errors or skipped or result.testsRun != COUNT
                 else "FAIL" if failures else "PASS")
        output = {"state": state, "count": COUNT, "tests_run": result.testsRun,
                  "cases": names, "errors": errors, "failures": failures, "skipped": skipped}
    except Exception:
        output = {"state": "BLOCKED", "count": 0, "tests_run": 0, "cases": [],
                  "errors": ["bootstrap_" + phase], "failures": [], "skipped": []}
    try:
        if run is None:
            return 2
        safe_result_file(run).write_text(json.dumps(output, sort_keys=True) + "\n",
                                         encoding="utf-8")
    except (OSError, ValueError):
        return 2
    return 0 if output["state"] == "PASS" else 2


def sha(path):
    h = hashlib.sha256()
    with path.open("rb") as file:
        for block in iter(lambda: file.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def execute():
    run = None
    result = {
        "schema": 1, "state": "BLOCKED", "product_acceptance": "NOT_TESTED",
        "scope": "Synthetic export omission disclosures and PDF page bounds only",
        "unverified": [
            "human visual glyph clipping, font coverage, overlapping text and print readability",
            "arbitrary real datasets and installed native Windows release",
            "full HTML/PDF numerical parity beyond the focused synthetic exhibit",
        ],
    }
    try:
        if os.name != "nt" or not os.environ.get("LOCALAPPDATA"):
            raise RuntimeError("Windows LOCALAPPDATA required")
        root = default_root()
        run, _ = create_run(root, PHASE, ROOT)
        result["run_id"] = run.name
        selected = ["backend/reports.py", "tests/test_p2_report_display_disclosure.py",
                    "tools/p2_report_display_devqa.py"]
        findings, blockers = scan_files(ROOT, selected)
        result["preflight"] = {"findings": findings, "blockers": blockers,
                               "source_sha256": {name: sha(ROOT / name) for name in selected}}
        if blockers:
            raise RuntimeError("Source preflight blocked")
        env = os.environ.copy()
        env["PILOTODIN_HOME"] = str(run / "workspace")
        env["PILOTODIN_DEVQA_RUN"] = str(run)
        env.pop("PILOTODIN_DESKTOP_SESSION", None)
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        env["PYTHONPATH"] = str(ROOT)
        try:
            child = subprocess.run(
                [sys.executable, "-B", str(Path(__file__).resolve()), "--worker"],
                cwd=ROOT, env=env, capture_output=True, text=True,
                timeout=180, check=False)
            result["worker_returncode"] = child.returncode
            try:
                worker_result = json.loads(safe_result_file(run).read_text(encoding="utf-8"))
            except (ValueError, OSError, UnicodeError):
                worker_result = {}
            result["tests"] = {
                "count": worker_result.get("count", 0),
                "executed": worker_result.get("tests_run", 0),
                "failures": worker_result.get("failures", []),
                "errors": worker_result.get("errors", []),
                "skipped": worker_result.get("skipped", []),
            }
            cases = worker_result.get("cases")
            complete = (child.returncode == 0 and
                        worker_result.get("state") == "PASS" and
                        worker_result.get("count") == COUNT and
                        worker_result.get("tests_run") == COUNT and
                        isinstance(cases, list) and len(set(cases)) == COUNT and
                        all(isinstance(c, str) and c.startswith("test_p2_report_display_disclosure.")
                            for c in cases) and
                        not any((worker_result.get("failures"), worker_result.get("errors"),
                                 worker_result.get("skipped"))))
            if complete:
                result["state"] = "REVIEW_REQUIRED"
            elif worker_result.get("failures"):
                result["state"] = "FAIL"
            else:
                result["state"] = "BLOCKED"
        except subprocess.TimeoutExpired:
            result["reason"] = "worker_timeout"
            result["state"] = "BLOCKED"
    except Exception:
        result["state"] = "BLOCKED"
        result["bootstrap_failure"] = True
    finally:
        if run is not None:
            archive = run.parent.parent / "archive" / (run.name + ".zip")
            partial = archive.with_suffix(".partial")
            def persist():
                manifest_file = run / "manifest.json"
                manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
                manifest["state"] = result["state"]
                manifest["product_acceptance"] = "NOT_TESTED"
                manifest_file.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
                output = run / "diagnostics" / "result.json"
                output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
                return output, manifest_file
            try:
                output, manifest_file = persist()
                with zipfile.ZipFile(partial, "x", zipfile.ZIP_DEFLATED) as z:
                    z.write(output, "result.json")
                    z.write(manifest_file, "manifest.json")
                partial.replace(archive)
                result["archive"] = str(archive)
            except (OSError, ValueError, RuntimeError, zipfile.BadZipFile) as exc:
                result["state"] = "BLOCKED"
                result["archive_failure"] = type(exc).__name__
                try:
                    partial.unlink(missing_ok=True)
                except OSError:
                    result["archive_cleanup_failed"] = True
                try:
                    persist()
                except (OSError, ValueError, RuntimeError):
                    result["status_persist_failed"] = True
            print("P2 REPORT DISPLAY DEVQA: " + result["state"])
            print("RUN: " + str(run))
            if result.get("archive"):
                print("STATUS-ONLY ZIP: " + result["archive"])
            if "tests" in result:
                print("DISPLAY TESTS: " + str(result["tests"]["executed"]) +
                      "/" + str(COUNT) + " executed")
                if result["tests"]["errors"] or result["tests"]["failures"]:
                    print("ERROR/FAIL CASES: " + ", ".join(
                        result["tests"]["errors"] + result["tests"]["failures"]))
            if result["state"] == "REVIEW_REQUIRED":
                print("Focused checks PASS; independent human visual PDF acceptance remains open.")
        else:
            print("P2 REPORT DISPLAY DEVQA: BLOCKED before workspace allocation")
    return 0 if result["state"] == "REVIEW_REQUIRED" else 2


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--worker", action="store_true")
    args = parser.parse_args()
    raise SystemExit(worker() if args.worker else execute())
