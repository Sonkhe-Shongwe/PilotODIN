"""G2.9 original WebView FILE handle admission regression, source-only.

These are not Windows captures. No handle enumeration, process launch,
ETW, filesystem writes, protected path inspection, or native acceptance.
"""
from dataclasses import replace
from pathlib import Path
import unittest

from qa.p4_research.n12_physical_destination import (
    PrivateHandlePath, Corroboration, assess_private_destination,
)
from qa.p4_research.n12_fileio_identity_join import _result as source_join_result
from qa.p4_research.n12_no_cdp_fileio_review import _fixed_report
from qa.p4_research.n12_private_child_pipe import WITNESS_FIELDS


REPO = Path(__file__).resolve().parents[1]
TARGET = r"\\?\C:\QA\UDF\EBWebView\Network\native-writer.tmp"
ROOT = PrivateHandlePath(r"\\?\C:\QA\UDF", 123, "permitted_root_handle")
ALL_CLAIMS = Corroboration(True, True, True, True, True, True, True, True, True)


def evaluate(origin, *, proofs=ALL_CLAIMS):
    return assess_private_destination(
        write_target=PrivateHandlePath(TARGET, 123, origin),
        allowed_roots=(ROOT,), request_time_path=TARGET,
        corroboration=proofs,
    )


class OriginalWebViewFileHandleAdmission(unittest.TestCase):
    def source(self, name):
        return (REPO / name).read_text(encoding="utf-8")

    def test_live_sampler_observes_original_process_handles_not_file_handles(self):
        source = self.source("qa/p4_research/n12_no_cdp_child_handles.py")
        self.assertIn("open_process_query_handle", source)
        self.assertIn("process_times(handle", source)
        self.assertNotIn("observe_supplied_windows_handle(", source)
        self.assertNotIn("NtQuerySystemInformation(", source)

    def test_authenticated_pipe_transports_process_lifetimes_not_file_handles(self):
        self.assertEqual(WITNESS_FIELDS, frozenset({
            "pid", "birth", "exit", "image_dos", "image_native", "parent_pid",
        }))
        self.assertFalse({"FileObject", "FileKey", "Irp", "file_handle"} & WITNESS_FIELDS)

    def test_generated_writer_original_handle_is_a_process_handle(self):
        source = self.source("qa/p4_research/n12_fileio_identity_join.py")
        self.assertIn('keys = ("pid", "birth_ticks", "exit_ticks")', source)
        self.assertIn('"sysmon_original_webview_identity": "NOT_COLLECTED"', source)
        self.assertIn('"native_N12_acceptance": "NOT_EVALUATED"', source)

    def test_path_adapter_cannot_attest_origin_or_kernel_pointer(self):
        source = self.source("qa/p4_research/n12_physical_destination.py")
        self.assertIn("GetFinalPathNameByHandleW", source)
        self.assertIn("GetFileInformationByHandle", source)
        self.assertIn('"UNVERIFIED_HANDLE_PROVENANCE"', source)
        self.assertNotIn("NtQuerySystemInformation(", source)

    def test_process_handle_can_never_be_a_file_destination_witness(self):
        result = evaluate("original_process_handle")
        self.assertEqual(result.status, "BLOCKED")
        self.assertEqual(result.reason, "NOT_AN_ORIGINAL_FILE_HANDLE")

    def test_reopened_by_path_is_not_original_webview_file_handle(self):
        result = evaluate("reopened_file")
        self.assertEqual(result.status, "BLOCKED")
        self.assertEqual(result.reason, "NOT_AN_ORIGINAL_FILE_HANDLE")

    def test_path_adapter_unverified_origin_stays_blocked(self):
        result = evaluate("UNVERIFIED_HANDLE_PROVENANCE")
        self.assertEqual(result.status, "BLOCKED")
        self.assertEqual(result.public_receipt()["native_N12_acceptance"], "NOT_EVALUATED")

    def test_false_original_file_handle_claim_blocks_even_with_same_name(self):
        for field in ("same_original_file_handle", "etw_fileobject_and_irp_join",
                      "request_time_path_epoch", "capture_loss_independently_clear"):
            with self.subTest(field=field):
                result = evaluate("original_file_handle",
                                  proofs=replace(ALL_CLAIMS, **{field: False}))
                self.assertEqual(result.status, "BLOCKED")

    def test_even_all_unverified_claims_only_get_candidate_not_native_pass(self):
        result = evaluate("original_file_handle")
        self.assertEqual(result.status, "CONTAINED_CANDIDATE_ONLY")
        public = result.public_receipt()
        self.assertEqual(public["native_N12_acceptance"], "NOT_EVALUATED")
        self.assertNotIn(TARGET, repr(result))
        self.assertNotIn(TARGET, str(public))

    def test_source_join_never_authenticates_process_to_write(self):
        result = source_join_result([])
        self.assertEqual(result["join_status"], "REVIEWABLE_ONLY")
        self.assertFalse(result["process_to_write_provenance_verified"])
        self.assertEqual(result["evidence_origin"], "UNVERIFIED_INPUT")
        self.assertEqual(result["native_N12_acceptance"], "NOT_EVALUATED")

    def test_no_cdp_governing_reducer_never_calls_generated_file_witness_pass(self):
        result = _fixed_report(
            blocker="full-native-product-write-containment-not-yet-proven",
            child_handles="PRIVATE_ORIGINAL_HANDLES_REVIEWABLE_ONLY",
            browser_profile="SYSMON_ETW_BROWSER_PROFILE_COMMAND_LINE_REVIEWED",
            calibration_status="BOOKEND_OS_FILE_NETWORK_REVIEWABLE",
            restore_status="TWO_UNIQUE_WRITES_CORROBORATED",
        )
        self.assertEqual(result["status"], "BLOCKED")
        self.assertEqual(result["native_N12_acceptance"], "NOT_EVALUATED")
        self.assertEqual(result["full_product_tree_mutation_containment"], "NOT_DEMONSTRATED")

    def test_live_no_cdp_app_has_no_original_file_handle_adapter_call(self):
        for name in ("qa/p4_research/n12_no_cdp_native_path.py",
                     "qa/p4_research/n12_app_lifetime.py",
                     "qa/p4_research/n12_no_cdp_fileio_review.py"):
            with self.subTest(name=name):
                source = self.source(name)
                self.assertNotIn("observe_supplied_windows_handle(", source)
                self.assertNotIn("review_private_write_pair(", source)

    def test_both_native_workflows_stay_disabled(self):
        for name in (".github/workflows/p4-n12-no-cdp-fileio.yml",
                     ".github/workflows/p4-n12-generated-sysmon-bookends.yml"):
            with self.subTest(name=name):
                self.assertIn("    if: ${{ false }}", self.source(name))
        self.assertFalse((REPO / "qa/p4_research/N12_GENERATED_BOOKENDS_OWNER_APPROVAL_G2_8_FRESH_ONE_USE.txt").exists())


if __name__ == "__main__":
    unittest.main()
