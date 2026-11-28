"""Synthetic redacted replay of published N12 native run counts, never native acceptance."""
from copy import deepcopy
import unittest
from qa.p4_native import n12_trace as trace
from qa.p4_research.n12_mutation_triage import summarize

GAP = "webview-network:write:path-missing"
OTHER = "other:write:path-missing"
SHA = "a" * 64


def example():
    unresolved = {GAP: 227087, OTHER: 4190, "other:resize:path-missing": 1327,
                  "other:write:process-lifetime-missing": 42,
                  "webview:write:path-missing": 930}
    violations = {"outside-scope:webview:create": 8,
                  "outside-scope:webview:overwrite": 4,
                  "outside-scope:webview:write": 4,
                  "outside-scope:backend:write": 1}
    return {
        "file_evidence_source": "etw", "coverage": "BLOCKED", "filesystem": "FAIL",
        "etw_unresolved_mutations": unresolved, "file_violations": violations,
        "webview_credit_comparison": {
            "status": "completed", "coverage": "BLOCKED", "filesystem": "FAIL",
            "etw_events_sha256": SHA, "baseline_webview_write_path_gaps": 227087,
            "etw_unresolved_mutations": {**unresolved, GAP: 15},
            "file_violations": {**violations, "outside-scope:webview-network:write": 113},
            "etw_webview_write_credit": {
                "status": "compared",
                "credited_paths": {"permitted": 226959, "outside-scope": 113},
                "remaining_path_gaps": 15,
            },
        },
        "background_rundown_comparison": {
            "status": "completed", "etw_events_sha256": SHA,
            "baseline_write_path_gaps": 4190,
            "verified_paths": {"outside-tracked": 78},
            "remaining_write_path_gaps": 4112,
        },
    }


class FileMutationTriageTests(unittest.TestCase):
    def test_known_published_evidence_reconciles_without_native_acceptance(self):
        report = summarize(example())
        self.assertEqual(report["comparison"], "RECONCILED")
        self.assertEqual(report["webview_network_write_paths"], {
            "ordinary_unresolved": 227087, "credited_permitted": 226959,
            "credited_outside_scope": 113, "remaining_unresolved": 15,
        })
        self.assertEqual(report["background_write_paths"]["remaining_unresolved"], 4112)
        self.assertIn("out-of-scope-file-operations", report["blockers"])
        self.assertEqual(report["file_mutation_acceptance"], "NOT_EVALUATED")
        self.assertNotIn(SHA, repr(report))

    def test_missing_or_blocked_compare_refuses(self):
        x = example()
        x["webview_credit_comparison"]["status"] = "blocked"
        self.assertEqual(summarize(x)["comparison"], "BLOCKED")

    def test_changed_credit_numbers_fail_closed(self):
        for value in (-1, True, 22, 226000):
            x = example()
            x["webview_credit_comparison"]["etw_webview_write_credit"][
                "credited_paths"]["permitted"] = value
            with self.subTest(value=value):
                with self.assertRaises(trace.EvidenceValidationError):
                    summarize(x)

    def test_paths_cannot_be_credited_while_hidden_violations_disappear(self):
        x = example()
        x["webview_credit_comparison"]["file_violations"].pop(
            "outside-scope:webview-network:write")
        with self.assertRaisesRegex(trace.EvidenceValidationError,
                                    "^mutation-triage-violations-concealed$"):
            summarize(x)

    def test_other_mutation_gaps_cannot_be_silently_removed(self):
        x = example()
        x["webview_credit_comparison"]["etw_unresolved_mutations"][OTHER] = 0
        with self.assertRaisesRegex(trace.EvidenceValidationError,
                                    "^mutation-triage-credit-inconsistent$"):
            summarize(x)

    def test_background_missing_or_wrong_capture_blocks(self):
        x = example()
        x["background_rundown_comparison"]["status"] = "blocked"
        self.assertEqual(summarize(x)["comparison"], "BLOCKED")
        x = example()
        x["background_rundown_comparison"]["etw_events_sha256"] = "b" * 64
        with self.assertRaisesRegex(trace.EvidenceValidationError,
                                    "^mutation-triage-background-inconsistent$"):
            summarize(x)

    def test_background_math_cannot_be_falsified(self):
        x = example()
        x["background_rundown_comparison"]["remaining_write_path_gaps"] = 0
        with self.assertRaisesRegex(trace.EvidenceValidationError,
                                    "^mutation-triage-background-inconsistent$"):
            summarize(x)

    def test_no_private_payload_in_public_report(self):
        x = example()
        x["private_path"] = "C:\\Private\\Secret"
        self.assertNotIn("Secret", repr(summarize(x)))


if __name__ == "__main__":
    unittest.main()
