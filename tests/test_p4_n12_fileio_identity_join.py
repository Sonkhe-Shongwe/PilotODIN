"""Adversarial ETW writer/known-path lifetime regressions; source-only data."""
import copy
import json
import unittest

from qa.p4_native.n12_etw_correlate import correlate_requests
from qa.p4_research import n12_fileio_identity_join as join


def synthetic_candidate():
    return {
        "scope": join.SCOPE,
        "source_sha": "a" * 40,
        "capture": {"start_ticks": 90, "end_ticks": 230,
                    "digest_verified": True, "zero_etw_loss": True,
                    "positive_transient_write_observed": True},
        "process": {"pid": 7, "birth_ticks": 100, "exit_ticks": 200,
                    "etw_birth_ticks": 100, "etw_exit_ticks": 200,
                    "original_handle_birth_ticks": 100, "original_handle_exit_ticks": 200,
                    "original_handle_retained": True, "exact_image_verified": True,
                    "unique_etw_sequence": True, "parent_sequence_verified": True,
                    "sysmon_guid_verified": True},
        "write": {"pid": 7, "birth_ticks": 100, "request_ticks": 140,
                  "completion_ticks": 150, "request_event_id": 16, "completion_event_id": 24,
                  "irp": 1002, "completion_irp": 1002,
                  "file_object": 400, "file_key": 40, "thread_owner_verified": True,
                  "unique_completion": True, "completion_identity_verified": True,
                  "completion_success": True, "path_evidence": "same-original-open-handle",
                  "name_epoch_unchanged": True, "destination_scope": "permitted"},
    }


def known_path_trace(*, early_exit=False, pid_reuse=False):
    """Only generated ETW IDs and a fake path. No native WebView2 process."""
    def row(kind, ticks, data, *, lifecycle=False, pid=7):
        return {"id": kind, "ticks": ticks, "data": data,
                "lifecycle": lifecycle, "pid": pid}
    file_path = r"C:\qa\permitted\synthetic.bin"
    rows = [
        row(1, 100, {"ProcessID": 7}, lifecycle=True),
        row(3, 110, {"ProcessID": 7, "ThreadID": 71}, lifecycle=True),
        row(12, 120, {"FileObject": 400, "Irp": 1001, "FileName": file_path}),
        row(24, 130, {"Irp": 1001, "Status": 0, "ExtraInformation": 1}, pid=0),
        row(16, 140, {"FileObject": 400, "FileKey": 40,
                      "Irp": 1002, "IssuingThreadId": 71}),
    ]
    if early_exit or pid_reuse:
        rows.append(row(2, 145, {"ProcessID": 7}, lifecycle=True, pid=0))
    if pid_reuse:
        rows.append(row(1, 147, {"ProcessID": 7}, lifecycle=True, pid=0))
    rows.append(row(24, 150, {"Irp": 1002, "Status": 0}, pid=0))
    if not early_exit and not pid_reuse:
        rows.append(row(2, 200, {"ProcessID": 7}, lifecycle=True, pid=0))
    if pid_reuse:
        rows.append(row(2, 210, {"ProcessID": 7}, lifecycle=True, pid=0))
    return rows, file_path


class FileIOJoinSourceTests(unittest.TestCase):
    def test_source_contract_names_actual_reducers_not_runtime_truth(self):
        result = join.source_contract()
        self.assertEqual(result["status"], "SOURCE_MATCH", result["issues"])
        self.assertEqual(result["actual_original_webview_handle_evidence"], "NOT_COLLECTED")
        self.assertFalse(result["known-path-completion-lifetime_proven"])
        self.assertEqual(result["native_N12_acceptance"], "NOT_EVALUATED")

    def test_synthetic_exact_join_is_reviewable_but_never_native_pass(self):
        result = join.review_candidate(synthetic_candidate())
        self.assertEqual(result["join_status"], "REVIEWABLE_ONLY", result["issues"])
        self.assertEqual(result["destination_scope"], "permitted")
        self.assertFalse(result["process_to_write_provenance_verified"])
        self.assertFalse(result["fileio_capture_completeness_certified"])
        self.assertEqual(result["native_N12_acceptance"], "NOT_EVALUATED")
        self.assertEqual(result["file_mutation_acceptance"], "NOT_EVALUATED")
        self.assertFalse(result["owner_native_execution_authorized"])

    def test_prohibited_path_is_still_reviewable_as_violation_not_permission(self):
        receipt = synthetic_candidate()
        receipt["write"]["destination_scope"] = "outside-scope"
        result = join.review_candidate(receipt)
        self.assertEqual(result["join_status"], "REVIEWABLE_ONLY")
        self.assertEqual(result["destination_scope"], "outside-scope")
        self.assertEqual(result["file_mutation_acceptance"], "NOT_EVALUATED")

    def test_early_exit_pid_reuse_and_tied_time_fail_closed(self):
        for change in (
            lambda r: r["process"].update(exit_ticks=145, etw_exit_ticks=145,
                                           original_handle_exit_ticks=145),
            lambda r: r["write"].update(birth_ticks=147),
            lambda r: r["write"].update(completion_ticks=200),
            lambda r: r["write"].update(request_ticks=100),
            lambda r: r["process"].update(etw_birth_ticks=102),
            lambda r: r["process"].update(original_handle_exit_ticks=201),
        ):
            with self.subTest(change=str(change.__code__.co_firstlineno)):
                row = synthetic_candidate()
                change(row)
                self.assertEqual(join.review_candidate(row)["join_status"], "BLOCKED")

    def test_irp_thread_path_epoch_and_completion_identity_are_independent(self):
        for category, alteration in (
            ("irp", {"completion_irp": 42}),
            ("event", {"completion_event_id": 16}),
            ("thread", {"thread_owner_verified": False}),
            ("completion", {"completion_identity_verified": False}),
            ("duplicate", {"unique_completion": False}),
            ("name", {"name_epoch_unchanged": False}),
            ("rundown-only", {"path_evidence": "stop-time-rundown-only"}),
            ("no-path", {"path_evidence": "NOT_COLLECTED"}),
            ("unmapped", {"destination_scope": "unknown"}),
        ):
            with self.subTest(category=category):
                row = synthetic_candidate()
                row["write"].update(alteration)
                report = join.review_candidate(row)
                self.assertEqual(report["join_status"], "BLOCKED")
                self.assertEqual(report["destination_scope"], "UNVERIFIED")

    def test_capture_loss_original_handles_and_positive_controls_all_required(self):
        edits = (
            ("capture", "zero_etw_loss"),
            ("capture", "positive_transient_write_observed"),
            ("capture", "digest_verified"),
            ("process", "original_handle_retained"),
            ("process", "exact_image_verified"),
            ("process", "parent_sequence_verified"),
            ("process", "sysmon_guid_verified"),
            ("process", "unique_etw_sequence"),
        )
        for category, key in edits:
            with self.subTest(field=key):
                row = synthetic_candidate()
                row[category][key] = False
                self.assertEqual(join.review_candidate(row)["join_status"], "BLOCKED")

    def test_unknown_fields_boolean_pids_and_private_paths_do_not_appear_in_report(self):
        rows = [
            None, {}, [], {"scope": join.SCOPE, "source_sha": "b" * 40},
            {**synthetic_candidate(), "private-file": "C:\\owner\\private.txt"},
        ]
        for row in rows:
            result = join.review_candidate(row)
            self.assertEqual(result["join_status"], "BLOCKED")
            self.assertNotIn("private", json.dumps(result))
        row = synthetic_candidate()
        row["process"]["pid"] = True
        self.assertEqual(join.review_candidate(row)["issues"], ["numeric-identity-invalid"])

    def test_actual_strict_known_path_reducer_can_emit_after_process_exit(self):
        rows, path = known_path_trace(early_exit=True)
        emitted = []
        unresolved = correlate_requests(
            rows, lambda name: name or None,
            lambda pid, birth, ticks: ("webview-network", "synthetic-writer")
            if birth == 100 else ("unattributed", None),
            lambda path: False, lambda *row: emitted.append(row),
            strict=True, initial_process_births={},
        )
        # Preserve the existing reducer, do not reclassify its original result:
        # a known opened path can be emitted after a request owner has exited.
        self.assertEqual(unresolved, {})
        self.assertIn(("webview-network", "synthetic-writer", "write",
                       path, None, 140, 150, True), emitted)
        fixture = synthetic_candidate()
        fixture["process"].update(exit_ticks=145, etw_exit_ticks=145,
                                  original_handle_exit_ticks=145)
        report = join.review_candidate(fixture)
        self.assertIn("fileio-completion-outside-original-process-lifetime", report["issues"])
        self.assertEqual(report["join_status"], "BLOCKED")

    def test_pid_reuse_before_completion_cannot_supply_same_original_process(self):
        rows, path = known_path_trace(pid_reuse=True)
        emitted = []
        unresolved = correlate_requests(
            rows, lambda name: name or None,
            lambda pid, birth, ticks: ("webview-network", "synthetic-writer"),
            lambda path: False, lambda *row: emitted.append(row),
            strict=True,
        )
        self.assertEqual(unresolved, {})
        self.assertIn(("webview-network", "synthetic-writer", "write",
                       path, None, 140, 150, True), emitted)
        fixture = synthetic_candidate()
        fixture["process"].update(exit_ticks=145, etw_exit_ticks=145,
                                  original_handle_exit_ticks=145)
        self.assertEqual(join.review_candidate(fixture)["join_status"], "BLOCKED")


if __name__ == "__main__":
    unittest.main()
