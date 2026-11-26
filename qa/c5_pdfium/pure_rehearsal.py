"""Exact eleven disarmed safety predicates, standard library only.

No acquisition, package installation, PDFium import or product execution.
A separately authorised, independently reviewed bootstrap must launch this
source. The disabled draft workflow deliberately cannot invoke it yet.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]


def main():
    if not (__debug__ and sys.flags.isolated and sys.flags.no_site
            and sys.flags.dont_write_bytecode):
        raise RuntimeError("PURE_REHEARSAL_REQUIRES_ISOLATED_STDLIB")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--collect-only", action="store_true")
    args = parser.parse_args()
    # Explicit checkout only; no site-packages or ambient PYTHONPATH.
    sys.path.insert(0, str(ROOT))
    from qa.c5_pdfium import staged_equivalence as stages
    from qa.c5_pdfium import staged_executor as executor
    from tools import pdf_test_inspection as pdf
    from tests import test_c5_pdfium_staged_equivalence_plan as plan_tests
    from tests import test_c5_pdfium_staged_executor as executor_tests
    from tests.c5_pdfium_fixture_helpers import disarmed_gate_check

    if not (stages.LIVE_ENABLED is False and executor.LIVE_ENABLED is False
            and executor.DISPOSITION_PIN is None
            and pdf.PDFIUM_TEST_EXECUTION_ENABLED is False):
        raise RuntimeError("PURE_REHEARSAL_REQUIRES_DISARMED_SOURCE")
    plan = stages.read_plan()
    p = plan["pure_rehearsal"]
    cases = (
        (p["test_file"] + "::test_exact_plan_and_standard_tool_commands",
         plan_tests.test_exact_plan_and_standard_tool_commands),
        (p["test_file"] + "::test_local_stage_a_gate_and_mandatory_combined_acceptance",
         plan_tests.test_local_stage_a_gate_and_mandatory_combined_acceptance),
        (p["guard_node"], disarmed_gate_check),
        (p["executor_tests"] + "::test_disarmed_executor_refuses_before_side_effects",
         executor_tests.test_disarmed_executor_refuses_before_side_effects),
        (p["executor_tests"] + "::test_malformed_fixture_refuses_before_direct_native_import",
         executor_tests.test_malformed_fixture_refuses_before_direct_native_import),
        (p["executor_tests"] + "::test_response_framing_and_archive_paths",
         executor_tests.test_response_framing_and_archive_paths),
        (p["executor_tests"] + "::test_resolution_requires_exact_local_archive_and_complete_graph",
         executor_tests.test_resolution_requires_exact_local_archive_and_complete_graph),
        (p["executor_tests"] + "::test_status_hook_rejects_incomplete_setup_call_teardown",
         executor_tests.test_status_hook_rejects_incomplete_setup_call_teardown),
        (p["executor_tests"] + "::test_completion_inventory_never_acquires_python_installer",
         executor_tests.test_completion_inventory_never_acquires_python_installer),
        (p["executor_tests"] + "::test_supplemental_identity_algorithms",
         executor_tests.test_supplemental_identity_algorithms),
        (p["executor_tests"] + "::test_font_worker_refuses_before_native_or_owner_path",
         executor_tests.test_font_worker_refuses_before_native_or_owner_path),
    )
    ids = [name for name, _ in cases]
    if len(ids) != p["expected_count"] or len(ids) != len(set(ids)):
        raise RuntimeError("PURE_REHEARSAL_CASE_SET")
    tests = [unittest.FunctionTestCase(fn) for _, fn in cases]
    labels = dict(zip(tests, ids))

    class Status(unittest.TestResult):
        def __init__(self):
            super().__init__()
            self.passed = []

        def addSuccess(self, test):
            super().addSuccess(test)
            self.passed.append(labels[test])

    result = Status()
    if not args.collect_only:
        # No default temporary directory or owner path fallback.
        scratch = Path(os.environ["TMPDIR"])
        home = Path(os.environ["PILOTODIN_HOME"])
        runner_temp = Path(os.environ["RUNNER_TEMP"])
        if not (scratch.is_absolute() and scratch.is_dir()
                and home.is_absolute() and home.is_dir()
                and runner_temp.is_absolute() and runner_temp.is_dir()
                and scratch == scratch.resolve() and home == home.resolve()
                and scratch != runner_temp.resolve()
                and scratch.is_relative_to(runner_temp.resolve())
                and home != scratch and home.is_relative_to(scratch)
                and not scratch.is_relative_to(ROOT)):
            raise RuntimeError("PURE_REHEARSAL_SCRATCH_SCOPE")
        tempfile.tempdir = str(scratch)
        unittest.TestSuite(tests).run(result)
    prohibited = sorted(name for name in sys.modules
                        if name == "pytest" or name.startswith(("pytest.", "_pytest", "pypdfium2", "PIL", "fitz", "pymupdf")))
    ok = (not prohibited and not result.errors and not result.failures and not result.skipped
          and not result.expectedFailures and not result.unexpectedSuccesses
          and (args.collect_only or (result.testsRun == len(ids) and result.passed == ids)))
    payload = {"mode": "COLLECTION" if args.collect_only else "EXECUTION",
               "collected": ids, "passed": result.passed, "executed": result.testsRun,
               "failed": [labels.get(test, "UNKNOWN") for test, _ in result.failures + result.errors],
               "skipped": [labels.get(test, "UNKNOWN") for test, _ in result.skipped],
               "xfailed": [labels.get(test, "UNKNOWN") for test, _ in result.expectedFailures],
               "unexpected_success": [labels.get(test, "UNKNOWN") for test in result.unexpectedSuccesses],
               "prohibited_imports": prohibited, "exitstatus": 0 if ok else 1}
    print(json.dumps(payload, ensure_ascii=True, sort_keys=True))
    return payload["exitstatus"]


if __name__ == "__main__":
    raise SystemExit(main())
