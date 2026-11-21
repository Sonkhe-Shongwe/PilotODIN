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




class NoCdpFileIOCollectionAndPermissionTests(TestCase):
    def test_cli_refuses_fileio_without_no_cdp_or_new_one_use_permission(self):
        from qa.p4_research import n12_app_lifetime as lifetime
        from unittest.mock import patch
        import os
        with patch.object(lifetime.sys, "argv", [
                "app-lifetime", "--source", "a" * 40,
                "--expected-exe-sha256", "b" * 64, "--fileio"]), \
             patch.object(lifetime, "preflight") as preflight, \
             patch.dict(os.environ, {}, clear=True):
            self.assertEqual(lifetime.main(), 2)
            preflight.assert_not_called()
        with patch.object(lifetime.sys, "argv", [
                "app-lifetime", "--source", "a" * 40,
                "--expected-exe-sha256", "b" * 64, "--fileio", "--no-cdp"]), \
             patch.object(lifetime, "preflight") as preflight, \
             patch.dict(os.environ, {}, clear=True):
            self.assertEqual(lifetime.main(), 2)
            preflight.assert_not_called()

    def test_capture_rejects_fileio_before_creating_root_without_fresh_approval(self):
        from qa.p4_research import n12_app_lifetime as lifetime
        from unittest.mock import patch
        import os
        with patch.object(lifetime.journey, "prepare_journey") as prepare, \
             patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(trace.EvidenceValidationError, "new-one-use-approval"):
                lifetime.capture(Path("synthetic"), Path("synthetic"),
                                 {"source_sha": "a" * 40, "executable_sha256": "b" * 64},
                                 no_cdp=True, fileio=True)
            prepare.assert_not_called()
        with patch.object(lifetime.journey, "prepare_journey") as prepare, \
             patch.dict(os.environ, {"PILOTODIN_N12_NO_CDP_FILEIO_CONSENT":
                                     lifetime.FILEIO_CONSENT}, clear=True):
            with self.assertRaisesRegex(trace.EvidenceValidationError, "new-one-use-approval"):
                lifetime.capture(Path("synthetic"), Path("synthetic"),
                                 {"source_sha": "a" * 40, "executable_sha256": "b" * 64},
                                 no_cdp=True, fileio=True)
            prepare.assert_not_called()

    def test_full_collector_reuses_journey_kernel_file_start_and_stop(self):
        from qa.p4_native import n12_lifetime_etw as etw
        from unittest.mock import patch
        import os
        with patch.dict(os.environ, {"SystemRoot": r"C:\Windows"}), \
             patch.object(etw.journey, "start_journey_etw") as start, \
             patch.object(etw.etw, "stop_trace", return_value={
                 "events_lost": 0, "log_buffers_lost": 0, "realtime_buffers_lost": 0,
                 "buffers_written": 3}) as stop, \
             patch.object(etw.etw, "utc_ticks", side_effect=[100, 200]):
            with etw.fileio_process_session(Path("disposable"), "a" * 40, "b" * 64) as session:
                self.assertEqual(session["start"], 100)
            self.assertEqual(session["end"], 200)
            self.assertEqual(session["counters"]["buffers_written"], 3)
            self.assertEqual(start.call_count, 1)
            self.assertEqual(stop.call_count, 1)
            self.assertIn("Lifetime-FileIO-", start.call_args.args[1])

    def test_full_collector_stops_on_body_error_without_reporting_a_pass(self):
        from qa.p4_native import n12_lifetime_etw as etw
        from unittest.mock import patch
        import os
        with patch.dict(os.environ, {"SystemRoot": r"C:\Windows"}), \
             patch.object(etw.journey, "start_journey_etw"), \
             patch.object(etw.etw, "stop_trace", return_value={}) as stop, \
             patch.object(etw.etw, "utc_ticks", return_value=100):
            with self.assertRaisesRegex(ValueError, "synthetic-body-failed"):
                with etw.fileio_process_session(Path("disposable"), "a" * 40, "b" * 64):
                    raise ValueError("synthetic-body-failed")
            stop.assert_called_once()

    def test_source_only_full_capture_brackets_snapshots_and_reuses_fileio_reducer(self):
        from contextlib import contextmanager, nullcontext
        from datetime import datetime, timezone
        from tempfile import TemporaryDirectory
        from unittest.mock import patch
        import os
        from qa.p4_research import n12_app_lifetime as lifetime
        source, digest = "a" * 40, "b" * 64
        provenance = {"source_sha": source, "executable_sha256": digest,
                      "cargo_lock_sha256": "c" * 64}
        base = trace.utc_ticks(datetime.now(timezone.utc))
        mock_session = {
            "start": base - 50_000_000, "end": base + 50_000_000,
            "counters": {"events_lost": 0, "log_buffers_lost": 0,
                         "realtime_buffers_lost": 0, "buffers_written": 5},
        }
        @contextmanager
        def fixture_session(*unused):
            yield mock_session
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            manifest = {"schema_version": 1, "disposable": True,
                        "source_sha": source, "executable_sha256": digest,
                        "markers": {},
                        "protected_roots": {"old": str(root / "private-old")},
                        "observed_roots": {"quality-source": str(root / "quality-source.csv")},
                        "immutable_observed": ["quality-source"],
                        "permitted_writes": {"webview": [str(root / "webview")]}}
            witness = {"pid": 50, "birth": 100, "exit": 200}
            saved = {}
            def capture_file(path, data):
                saved[path.name] = data
            env = {
                "PILOTODIN_N12_NO_CDP_FILEIO_CONSENT": lifetime.FILEIO_CONSENT,
                "PILOTODIN_N12_NO_CDP_STORAGE_CONSENT": lifetime.no_cdp_path.lifecycle.NATIVE_ACK_CONSENT,
                "PILOTODIN_N12_APP_LIFETIME_CONSENT": lifetime.CONSENT,
                "GITHUB_ACTIONS": "true", "RUNNER_ENVIRONMENT": "github-hosted",
                "RUNNER_OS": "Windows", "GITHUB_RUN_ATTEMPT": "1",
                "PILOTODIN_N12_APPROVED_SOURCE": source,
            }
            # Every Windows/native action below is mocked. Only the generated
            # fixture CSV gets written in this local temporary directory.
            with patch.dict(os.environ, env, clear=True), \
                 patch.object(lifetime.journey, "prepare_journey",
                              return_value=(manifest, root, root, root / "quality-source.csv", [])), \
                 patch.object(lifetime.journey, "snapshots",
                              return_value={"protected": {}, "observed": {}}), \
                 patch.object(lifetime.journey, "snapshot_capture_evidence",
                              return_value={"status": "PASS"}) as bracket, \
                 patch.object(lifetime.journey, "sysmon_tail", side_effect=[1, 4]), \
                 patch.object(lifetime.journey, "export_sysmon"), \
                 patch.object(lifetime.journey, "powershell") as powershell, \
                 patch.object(lifetime.journey, "report_file", side_effect=capture_file), \
                 patch.object(lifetime.journey, "checkpoint_stage",
                              side_effect=lambda *a: nullcontext()), \
                 patch.object(lifetime.etw, "fileio_process_session",
                              side_effect=fixture_session) as collector, \
                 patch.object(lifetime.etw, "process_session") as old_collector, \
                 patch.object(lifetime.n12_etw_probe, "volume_devices",
                              return_value={"C:": r"\Device\HarddiskVolume3"}), \
                 patch.object(lifetime, "launch_worker",
                              return_value=(witness, witness, None)) as worker, \
                 patch.object(lifetime.trace, "read_json", return_value={
                     "source_sha": source, "executable_sha256": digest,
                     "markers": {"launch": "x", "ready": "y", "close": "z", "profile-exit": "v"}}), \
                 patch.object(lifetime.trace, "compare_snapshots",
                              return_value=({"protected_snapshot_comparison": "MATCH"}, set())), \
                 patch.object(lifetime.build, "digest", return_value="d" * 64), \
                 patch.object(lifetime.build, "executable", return_value=root / "fake.exe"), \
                 patch.object(lifetime, "reduction",
                              return_value={"verdict": "PASS", "issues": [],
                                            "handle_comparison": {"app": "MATCH"}}), \
                 patch.object(lifetime.fileio_review, "reduce",
                              return_value={"status": "BLOCKED",
                                            "native_N12_acceptance": "NOT_EVALUATED"}) as strict, \
                 patch.object(lifetime.time, "sleep"):
                receipt = lifetime.capture(root, root, provenance, no_cdp=True, fileio=True)
            collector.assert_called_once()
            old_collector.assert_not_called()
            worker.assert_called_once()
            self.assertTrue(worker.call_args.kwargs["no_cdp"])
            bracket.assert_called_once()
            self.assertEqual(powershell.call_args.args[1], "etw-export")
            strict.assert_called_once()
            self.assertEqual(strict.call_args.args[0]["etw"]["events_sha256"], "d" * 64)
            self.assertEqual(strict.call_args.args[0]["etw"]["counters"]["buffers_written"], 5)
            self.assertTrue({"snapshot-before-start", "snapshot-before-end",
                             "snapshot-after-start", "snapshot-after-end",
                             "launch", "ready", "close", "profile-exit"} <=
                            manifest["markers"].keys())
            self.assertEqual(receipt["no_cdp_fileio"]["status"], "BLOCKED")
            self.assertEqual(saved["lifetime-report.json"]["no_cdp_fileio"]["native_N12_acceptance"],
                             "NOT_EVALUATED")

