"""Fast checks on P2 DevQA status conversion; cannot touch product app/data."""
import unittest

# tools path inserted explicitly by discovery runner's PYTHONPATH
from tools.p2_mixed_report_devqa import simple_status


def payload(n=3):
    return {"state": "PASS", "count": n, "tests_run": n,
            "cases": [f"test_p2_mixed_worker_contract.Test{i}.test_mr{i:02d}" for i in range(n)],
            "failures": [], "errors": [], "skipped": []}


class RunnerContract(unittest.TestCase):
    def test_bad_counts_and_empty_are_blocked(self):
        good = payload()
        self.assertEqual(simple_status(good, 3), "PASS")
        self.assertEqual(simple_status({}, 3), "BLOCKED")
        good["tests_run"] = 2
        self.assertEqual(simple_status(good, 3), "BLOCKED")

    def test_worker_error_and_skip_are_blocked(self):
        bad = payload()
        bad["errors"] = ["setUpClass"]
        self.assertEqual(simple_status(bad, 3), "BLOCKED")
        bad["errors"] = []
        bad["skipped"] = ["incomplete"]
        self.assertEqual(simple_status(bad, 3), "BLOCKED")

    def test_test_assertion_failure_cannot_pass(self):
        bad = payload()
        bad["failures"] = [bad["cases"][0]]
        bad["state"] = "FAIL"
        self.assertEqual(simple_status(bad, 3), "FAIL")
        bad["failures"] = []
        bad["state"] = "PASS"
        bad["cases"][0] = bad["cases"][1]
        self.assertEqual(simple_status(bad, 3), "BLOCKED")
