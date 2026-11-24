"""Fail-closed, non-launching product-tree containment source review."""
import copy
import json
import unittest

from qa.p4_research import n12_product_tree_isolation_review as review


class ProductTreeIsolationReviewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original = review.load_sources()

    def test_current_product_topology_is_detected_but_not_credited(self):
        result = review.review_source_topology(self.original)
        self.assertEqual(result["review_status"], "SOURCE_MATCH", result["issues"])
        self.assertEqual(result["issues"], [])
        self.assertEqual(result["generated_writer_restriction"],
                         "CONTROL_ONLY_NOT_PRODUCT_PROOF")
        self.assertEqual(result["conclusion"],
                         "PRODUCT_PROCESS_TREE_CONTAINMENT_NOT_DEMONSTRATED")
        self.assertEqual(result["native_N12_acceptance"], "NOT_EVALUATED")
        self.assertEqual(result["file_mutation_acceptance"], "NOT_EVALUATED")
        for name in ("windows_token_or_acl_operations_performed",
                     "native_app_launched", "owner_native_execution_authorized"):
            self.assertFalse(result[name])

    def test_backend_or_inference_spawn_drift_blocks_instead_of_inference(self):
        for name, original, changed, issue in (
            ("backend", '.shell().sidecar("pilotodin-engine")',
             '.shell().sidecar("other-engine")', "backend-shell-child-source-drift"),
            ("inference", '.shell().sidecar("pilotodin-inference")',
             '.shell().sidecar("other-inference")', "inference-shell-child-source-drift"),
            ("backend-temp", '.env("TEMP", worker_temp.as_os_str())',
             '.env("TEMP", "C:/unknown")', "backend-shell-child-source-drift"),
        ):
            with self.subTest(name=name):
                sources = dict(self.original)
                # Only mutate the relevant function to avoid false credit
                rust = sources["rust"]
                if name == "backend-temp":
                    start = rust.index("fn launch_backend(")
                    end = rust.index("fn verify_bundled_model(", start)
                    rust = rust[:start] + rust[start:end].replace(original, changed, 1) + rust[end:]
                else:
                    rust = rust.replace(original, changed, 1)
                sources["rust"] = rust
                result = review.review_source_topology(sources)
                self.assertEqual(result["review_status"], "SOURCE_DRIFT_BLOCKED")
                self.assertIn(issue, result["issues"])
                self.assertEqual(result["native_N12_acceptance"], "NOT_EVALUATED")

    def test_async_inference_dispatch_and_owned_spawn_drift_block(self):
        cases = (
            ("launch_bundled_ai", "start_owned_inference(work_app, work_attempt)",
             "unreviewed_worker(work_app, work_attempt)", "inference-async-dispatch-source-drift"),
            ("launch_bundled_ai", "tauri::async_runtime::spawn_blocking(move ||",
             "tauri::async_runtime::spawn(move ||", "inference-async-dispatch-source-drift"),
            ("launch_bundled_ai", "attempt.joined.store(true, Ordering::Release)",
             "attempt.joined.store(false, Ordering::Release)", "inference-async-dispatch-source-drift"),
            ("launch_bundled_ai", "*startup = Some(attempt.clone())",
             "*startup = None", "inference-async-dispatch-source-drift"),
            ("start_owned_inference", '.env("TMP", worker_temp.as_os_str())',
             '.env("TMP", "C:/unknown")', "inference-shell-child-source-drift"),
            ("start_owned_inference", ".set_process_group(true)",
             ".set_process_group(false)", "inference-shell-child-source-drift"),
            ("start_owned_inference", "storage_pins.verify()?",
             "unreviewed_verify()?", "inference-shell-child-source-drift"),
            ("start_owned_inference", "current.connection.token != attempt.backend_token",
             "false", "inference-shell-child-source-drift"),
            ("start_owned_inference", "Arc::ptr_eq(s, &attempt)",
             "true", "inference-shell-child-source-drift"),
            ("start_owned_inference", "_storage_pins: storage_pins, _model: model",
             "_storage_pins: discarded, _model: model", "inference-shell-child-source-drift"),
        )
        for function, before, after, issue in cases:
            with self.subTest(function=function, before=before):
                sources = dict(self.original)
                body = review._function(sources["rust"], function)
                self.assertIn(before, body)
                sources["rust"] = sources["rust"].replace(body, body.replace(before, after, 1), 1)
                result = review.review_source_topology(sources)
                self.assertEqual(result["review_status"], "SOURCE_DRIFT_BLOCKED")
                self.assertIn(issue, result["issues"])
                self.assertEqual(result["native_N12_acceptance"], "NOT_EVALUATED")

    def test_duplicate_worker_or_command_is_not_accepted(self):
        for function, issue in (
                ("launch_bundled_ai", "inference-async-dispatch-source-drift"),
                ("start_owned_inference", "inference-shell-child-source-drift")):
            with self.subTest(function=function):
                sources = dict(self.original)
                sources["rust"] += "\n" + review._function(sources["rust"], function)
                result = review.review_source_topology(sources)
                self.assertEqual(result["review_status"], "SOURCE_DRIFT_BLOCKED")
                self.assertIn(issue, result["issues"])
                self.assertEqual(result["native_N12_acceptance"], "NOT_EVALUATED")

    def test_modified_webview_or_qa_redirect_contract_blocks(self):
        changes = (
            ("config", '"label": "main"', '"label": "other"', "configured-webview-main-source-drift"),
            ("qa_ambient", '"native_filesystem_containment": "NOT_VERIFIED"',
             '"native_filesystem_containment": "PASS"',
             "qa-only-ambient-variant-source-drift"),
            ("token_probe", '"file_protection_verified": False',
             '"file_protection_verified": True',
             "read-only-token-capability-source-drift"),
            ("fixture", '"owner_native_execution_authorized": False',
             '"owner_native_execution_authorized": True',
             "generated-writer-only-fixture-source-drift"),
        )
        for key, before, after, issue in changes:
            with self.subTest(key=key):
                sources = dict(self.original)
                self.assertIn(before, sources[key])
                sources[key] = sources[key].replace(before, after, 1)
                result = review.review_source_topology(sources)
                self.assertEqual(result["review_status"], "SOURCE_DRIFT_BLOCKED")
                self.assertIn(issue, result["issues"])

    def test_new_product_token_launch_requires_independent_review(self):
        sources = dict(self.original)
        sources["rust"] += "\n// proposed CreateRestrictedToken path, not reviewed\n"
        result = review.review_source_topology(sources)
        self.assertIn("product-security-launch-source-changed-review-required", result["issues"])
        self.assertEqual(result["decision"], "DO_NOT_PROMOTE_RESTRICTED_WRITER_TO_R02_5")

    def test_invalid_inputs_fail_without_echoing_private_paths(self):
        for value in (None, [], {}, {"rust": "C:\\owner\\secret.csv"}):
            with self.subTest(value=type(value).__name__):
                output = review.review_source_topology(value)
                self.assertEqual(output["review_status"], "SOURCE_DRIFT_BLOCKED")
                self.assertNotIn("secret", json.dumps(output))
                self.assertEqual(output["native_N12_acceptance"], "NOT_EVALUATED")

    def test_no_native_or_protected_root_capability_in_this_module(self):
        source = (review.ROOT / "qa/p4_research/n12_product_tree_isolation_review.py").read_text(
            encoding="utf-8")
        for forbidden in ("subprocess.", "ctypes.WinDLL(", "CreateProcessAsUserW(",
                          "os.chmod(", ".mkdir(", ".unlink(", ".write_bytes("):
            self.assertNotIn(forbidden, source)
        report = review.review_source_topology(copy.deepcopy(self.original))
        for field in ("tauri_parent_token_evidence", "webview2_process_token_evidence",
                      "backend_worker_token_evidence", "inference_worker_token_evidence",
                      "fileio_complete_runtime_evidence"):
            self.assertEqual(report[field], "NOT_COLLECTED")


if __name__ == "__main__":
    unittest.main()
