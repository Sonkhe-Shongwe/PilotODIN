"""Synthetic no-CDP Kernel-File reduction bridge, never a native app run."""
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
import json
from unittest import TestCase
from unittest.mock import patch

from qa.p4_native import n12_trace as trace
from qa.p4_research import n12_no_cdp_fileio_review as review


class NoCdpFileIOReviewTests(TestCase):
    def setUp(self):
        self.manifest = {
            "schema_version": 1,
            "etw": {"schema_version": 1,
                    "counters": {"events_lost": 0, "log_buffers_lost": 0,
                                 "realtime_buffers_lost": 0, "buffers_written": 4}},
            "observed_roots": {"quality-source": r"C:\qa\source.csv"},
            "immutable_observed": ["quality-source"],
        }
        self.snap = {"protected_snapshot_comparison": "MATCH"}
        self.handle = {"pid": 7091, "birth": 7, "exit": 8}
        self.life = {"verdict": "PASS", "handle_comparison": {"app": "MATCH"}}
        self.called = []

    def run_check(self, *, violation=None, gap=None, issues=None, role=True):
        def strict(*a, **kwargs):
            self.called.append((a, kwargs))
            return (Counter({"webview:write": 5}), Counter(violation or {}),
                    set(), dict(gap or {}))
        start = datetime(2026, 11, 21, tzinfo=timezone.utc)
        with patch.object(trace, "load_capture", return_value=(start, start, {}, [], set(issues or []))), \
             patch.object(trace, "bind_processes",
                          return_value=({"a": "app", **({"b": "webview-network"} if role else {})},
                                        [("a", object())])), \
             patch.object(trace, "scope",
                          return_value=([r"C:\protected"], {"webview-network": [r"C:\qa"]})), \
             patch.object(trace, "windows_path", side_effect=lambda p: p.casefold()), \
             patch.object(trace, "inspect_etw_files", side_effect=strict):
            return review.reduce(self.manifest, Path("fixture.xml"), Path("fixture.jsonl"),
                                 self.handle, Path("fake.exe"),
                                 lifetime_report=self.life, snapshot=self.snap)

    def test_invokes_governing_strict_reducer_and_guards_immutable_original(self):
        result = self.run_check()
        self.assertEqual(len(self.called), 1)
        args, kwargs = self.called[0]
        self.assertEqual(kwargs, {})
        self.assertIn(r"c:\qa\source.csv", args[6])
        self.assertEqual(args[7]["webview-network"], [r"C:\qa"])
        self.assertEqual(result["blocker"],
                         "full-n12-calibration-and-transient-write-control-not-collected")
        self.assertEqual(result["original_app_handle_join"], "MATCH")
        self.assertEqual(result["etw_loss_counters"], "ZERO_REPORTED_NOT_FULL_COMPLETENESS")
        self.assertEqual(result["status"], "BLOCKED")
        self.assertEqual(result["native_N12_acceptance"], "NOT_EVALUATED")
        self.assertEqual(result["file_mutation_acceptance"], "NOT_EVALUATED")
        self.assertFalse(result["owner_native_execution_authorized"])

    def test_prohibited_write_is_retained_and_not_reclassified(self):
        result = self.run_check(violation={"outside-scope:webview-network:write": 113})
        self.assertEqual(result["blocker"], "observed-prohibited-fileio-operations")
        self.assertEqual(result["observed_prohibited_operations"], 113)
        self.assertEqual(result["prohibited_by_role"]["webview-network"], 113)
        self.assertEqual(result["protected_endpoints"], "MATCH")
        self.assertEqual(result["status"], "BLOCKED")

    def test_path_loss_and_missing_actor_remain_blocked(self):
        result = self.run_check(gap={"webview-network:write:path-missing": 15},
                                issues={"etw-mutation-coverage-unresolved"}, role=False)
        self.assertEqual(result["blocker"], "fileio-evidence-or-original-process-identity-unresolved")
        self.assertEqual(result["missing_mutation_path_credits"], 15)
        self.assertEqual(result["remaining_webview_network_write_path_gaps"], 15)
        self.assertEqual(result["scoped_role_count"], 0)
        self.assertEqual(result["reducer_issue_count"], 2)

    def test_redacted_output_does_not_include_private_witness_content(self):
        result = self.run_check(violation={"outside-scope:webview-network:write": 2})
        payload = json.dumps(result)
        for private in ("7091", "source.csv", r"C:\protected", "private-process-guid"):
            self.assertNotIn(private, payload)
        self.assertEqual(result["effective_webview_user_data_folder"], "NOT_VERIFIED")
        self.assertEqual(result["calibration_and_transient_write_proof"], "NOT_COLLECTED")

    def test_fail_closed_if_strict_reducer_raises(self):
        with patch.object(trace, "load_capture", side_effect=trace.EvidenceValidationError("bad-digest")):
            report = review.reduce(self.manifest, None, None, self.handle, "fake.exe",
                                   lifetime_report=self.life, snapshot=self.snap)
        self.assertEqual(report["blocker"], "strict-fileio-reducer-or-evidence-invalid")
        self.assertEqual(report["observed_prohibited_operations"], 0)
        self.assertEqual(report["status"], "BLOCKED")

    def test_absent_or_invalid_original_app_witness_is_blocked(self):
        for bad in (None, {}, {"pid": True}, {"pid": 0}, {"pid": "7091"}):
            with self.subTest(bad=bad):
                receipt = review.reduce(self.manifest, None, None, bad, "fake.exe",
                                        lifetime_report=self.life, snapshot=self.snap)
                self.assertEqual(receipt["blocker"], "incomplete-fileio-review-envelope")
                self.assertEqual(receipt["native_N12_acceptance"], "NOT_EVALUATED")

    def test_even_perfect_mocked_input_never_claims_n12_acceptance(self):
        result = self.run_check()
        self.assertEqual(result["full_product_tree_mutation_containment"], "NOT_DEMONSTRATED")
        self.assertFalse(result["owner_native_execution_authorized"])


