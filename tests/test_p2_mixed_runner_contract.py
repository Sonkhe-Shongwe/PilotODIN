"""Fast checks on P2 DevQA status conversion; cannot touch product app/data."""
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import unittest

# tools path inserted explicitly by discovery runner's PYTHONPATH
from tools.p2_mixed_report_devqa import (simple_status, finalize_diagnostics,
                                           read_worker_status, worker_status_path)


def payload(n=3):
    return {"state": "PASS", "count": n, "tests_run": n,
            "cases": [f"test_p2_mixed_worker_contract.Test{i}.test_mr{i:02d}" for i in range(n)],
            "failures": [], "errors": [], "skipped": []}


def isolated_temp_parent():
    """Use the current disposable DevQA fixtures folder when run by the launcher."""
    raw_run = os.environ.get("PILOTODIN_DEVQA_RUN")
    raw_home = os.environ.get("PILOTODIN_HOME")
    if not raw_run and not raw_home:
        return None  # Standalone pure unit-contract execution.
    if not raw_run or not raw_home:
        raise RuntimeError("Partial DevQA environment is not permitted")
    run = Path(raw_run).resolve()
    if (Path(raw_home).resolve() != run / "workspace" or
            not (run / "manifest.json").is_file() or
            not (run / "fixtures").is_dir()):
        raise RuntimeError("Refusing unverified contract fixture workspace")
    manifest = json.loads((run / "manifest.json").read_text(encoding="utf-8"))
    if manifest.get("phase") != "P2-MIXED-REPORT":
        raise RuntimeError("Refusing a foreign DevQA run")
    return str(run / "fixtures")




class RunnerContract(unittest.TestCase):
    def test_bad_counts_and_empty_are_blocked(self):
        good = payload()
        self.assertEqual(simple_status(good, 3), "PASS")
        self.assertEqual(simple_status({}, 3), "BLOCKED")
        good["tests_run"] = 2
        self.assertEqual(simple_status(good, 3), "BLOCKED")

        # The supplied Windows ZIP showed zero cases because the parent could
        # not parse the worker's stdout. Status travels in a dedicated file.
        with TemporaryDirectory(prefix="p2-protocol-", dir=isolated_temp_parent()) as tmp:
            status = worker_status_path(Path(tmp), "mixed")
            self.assertEqual(status.name, "worker-mixed.json")
            self.assertIsNone(read_worker_status(status))
            status.write_text("imported module printed a banner", encoding="utf-8")
            self.assertIsNone(read_worker_status(status))
            status.write_text(json.dumps(payload()), encoding="utf-8")
            self.assertEqual(simple_status(read_worker_status(status), 3), "PASS")

    def test_worker_error_and_skip_are_blocked(self):
        bad = payload()
        bad["errors"] = ["setUpClass"]
        self.assertEqual(simple_status(bad, 3), "BLOCKED")
        bad["errors"] = []
        bad["skipped"] = ["incomplete"]
        self.assertEqual(simple_status(bad, 3), "BLOCKED")

        # Failure-within-failure regression: archive I/O must not preserve
        # a stale REVIEW_REQUIRED in on-disk status or the run manifest.
        with TemporaryDirectory(prefix="p2-contract-", dir=isolated_temp_parent()) as temp:
            base = Path(temp)
            run = base / "runs" / "synthetic-run"
            (run / "diagnostics").mkdir(parents=True)
            (base / "archive").mkdir()
            (run / "manifest.json").write_text(
                json.dumps({"state": "READY_NOT_TESTED", "product_acceptance": "NOT_TESTED"}),
                encoding="utf-8")
            outcome = {"state": "REVIEW_REQUIRED", "stages": {}}
            with patch("tools.p2_mixed_report_devqa.zipfile.ZipFile",
                       side_effect=OSError("synthetic_archive_io_failure")):
                finalize_diagnostics(run, outcome)
            self.assertEqual(outcome["state"], "BLOCKED")
            self.assertEqual(outcome["archive_failure"], "OSError")
            self.assertEqual(json.loads((run / "manifest.json").read_text(
                encoding="utf-8"))["state"], "BLOCKED")
            self.assertEqual(json.loads((run / "diagnostics" / "result.json").read_text(
                encoding="utf-8"))["state"], "BLOCKED")
            self.assertFalse((base / "archive" / "synthetic-run.zip").exists())
            self.assertFalse((base / "archive" / "synthetic-run.partial").exists())

    def test_test_assertion_failure_cannot_pass(self):
        bad = payload()
        bad["failures"] = [bad["cases"][0]]
        bad["state"] = "FAIL"
        self.assertEqual(simple_status(bad, 3), "FAIL")
        bad["failures"] = []
        bad["state"] = "PASS"
        bad["cases"][0] = bad["cases"][1]
        self.assertEqual(simple_status(bad, 3), "BLOCKED")
