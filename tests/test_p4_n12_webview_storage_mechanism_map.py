"""WebView2 storage hypothesis source audit and adversarial drift tests."""
import copy
import json
import unittest

from qa.p4_research import n12_webview_storage_mechanism_map as study


class StorageMechanismSourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sources = study.read_sources()

    def review(self, mutate=None):
        sources = copy.deepcopy(self.sources)
        if mutate:
            mutate(sources)
        return study.inspect_sources(sources)

    def test_current_three_distinct_webview_launch_paths_and_no_native_credit(self):
        report = self.review()
        self.assertEqual(report["source_status"], "SOURCE_MATCH", report["issues"])
        self.assertEqual(report["production_window_storage"],
                         "NO_EXPLICIT_DATA_DIRECTORY_IN_WINDOW_CONFIG")
        self.assertEqual(report["qa_standard_storage"],
                         "UDF_AND_TEMP_DECLARED_DEBUG_NETLOG")
        self.assertEqual(report["qa_no_cdp_storage"],
                         "UDF_AND_TEMP_DECLARED_NO_DEBUG_ARGUMENTS")
        self.assertEqual(report["qa_ambient_variant"],
                         "DEFAULT_OFF_SOURCE_ONLY_CANDIDATE")
        self.assertEqual(report["cause_of_outside_writes"], "UNKNOWN")
        for key in ("native_app_launched", "effective_udf_observed",
                    "webview_child_fileio_attributed", "webview_child_token_verified",
                    "acl_modified", "owner_native_execution_authorized"):
            self.assertFalse(report[key])
        for key in ("native_N12_acceptance", "file_mutation_acceptance"):
            self.assertEqual(report[key], "NOT_EVALUATED")

    def test_adding_explicit_production_data_directory_requires_review(self):
        def edit(s):
            s["production_config"] = s["production_config"].replace(
                '"label": "main",', '"label": "main", "dataDirectory": "other",', 1)
        report = self.review(edit)
        self.assertEqual(report["source_status"], "SOURCE_DRIFT_BLOCKED")
        self.assertIn("production-webview-storage-config-review-required", report["issues"])
        self.assertEqual(report["native_N12_acceptance"], "NOT_EVALUATED")

    def test_qa_requested_udf_and_debug_arg_drift_are_distinct(self):
        for old, new in (
            ('"WEBVIEW2_USER_DATA_FOLDER"', '"UNREVIEWED_UDF_VARIABLE"'),
            ('"WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS"', '"UNREVIEWED_BROWSER_ARGUMENTS"'),
            ("--log-net-log=", "--unreviewed-file-output="),
        ):
            with self.subTest(token=old):
                def mutate(s):
                    s["n12_journey"] = s["n12_journey"].replace(old, new, 1)
                report = self.review(mutate)
                self.assertIn("standard-n12-webview-env-source-drift", report["issues"])
                self.assertFalse(report["effective_udf_observed"])

    def test_no_cdp_does_not_inherit_the_debug_netlog_variant(self):
        def mutate(s):
            source = s["no_cdp"]
            anchor = 'app_env = {'
            self.assertIn(anchor, source)
            s["no_cdp"] = source.replace(anchor,
                'app_env = {"WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS": "--remote-debugging-port=9331", ', 1)
        report = self.review(mutate)
        self.assertIn("no-cdp-env-source-drift", report["issues"])
        self.assertEqual(report["file_mutation_acceptance"], "NOT_EVALUATED")

    def test_ambient_variant_default_on_or_claimed_native_proof_blocks(self):
        variants = (
            ('choice in (None, "", CANDIDATE)', 'choice in (CANDIDATE,)'),
            ('"native_filesystem_containment": "NOT_VERIFIED"',
             '"native_filesystem_containment": "PASS"'),
        )
        for old, new in variants:
            with self.subTest(changed=old):
                def mutate(s):
                    self.assertIn(old, s["qa_ambient"])
                    s["qa_ambient"] = s["qa_ambient"].replace(old, new, 1)
                report = self.review(mutate)
                self.assertIn("qa-ambient-opt-in-source-drift", report["issues"])
                self.assertFalse(report["owner_native_execution_authorized"])

    def test_all_competing_hypotheses_remain_unresolved_and_include_falsifiers(self):
        plan = study.hypothesis_plan()
        self.assertEqual({x["id"] for x in plan},
                         {"H1-ambient-variable", "H2-effective-udf",
                          "H3-runtime-other-storage", "H4-debug-netlog",
                          "H5-actor-identity", "H6-completeness"})
        for row in plan:
            self.assertEqual(row["causality"], "UNRESOLVED")
            self.assertEqual(row["native_evidence"], "NOT_COLLECTED")
            self.assertTrue(row["negative_control"])
            self.assertTrue(row["discriminator"])
        report = self.review()
        self.assertNotIn("C:\\", json.dumps(report))
        self.assertNotIn("pid", json.dumps(report).lower())

    def test_invalid_sources_fail_closed_without_echoing_private_values(self):
        for invalid in (None, {}, [], {"qa_ambient": "C:\\owner\\secret.txt"}):
            with self.subTest(value=type(invalid).__name__):
                report = study.inspect_sources(invalid)
                self.assertEqual(report["source_status"], "SOURCE_DRIFT_BLOCKED")
                self.assertNotIn("secret", json.dumps(report))
                self.assertEqual(report["native_N12_acceptance"], "NOT_EVALUATED")

    def test_no_native_or_owner_data_actions_in_review_module(self):
        src = (study.ROOT / study.__file__.split("qa/")[-1]).as_posix()
        _ = src  # Do not access any host path other than fixed checked-in source.
        text = (study.ROOT / "qa/p4_research/n12_webview_storage_mechanism_map.py").read_text(
            encoding="utf-8")
        for forbidden in ("subprocess.", "ctypes.WinDLL(", "os.chmod(", ".mkdir(",
                          ".write_bytes(", "CreateProcessAsUserW(", "sysmon-tail"):
            self.assertNotIn(forbidden, text)


if __name__ == "__main__":
    unittest.main()
