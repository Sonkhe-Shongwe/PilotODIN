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
        self.manifest.update(source_sha="a" * 40, executable_sha256="b" * 64)
        self.life = {"verdict": "PASS", "handle_comparison": {"app": "MATCH"},
                     "source_sha": self.manifest["source_sha"],
                     "executable_sha256": self.manifest["executable_sha256"],
                     "issues": []}
        self.called = []

    def run_check(self, *, violation=None, gap=None, issues=None, role=True,
                  two_roles=False, calibrated=False, restore_verified=None):
        def strict(*a, **kwargs):
            self.called.append((a, kwargs))
            return (Counter({"webview:write": 5}), Counter(violation or {}),
                    set(), dict(gap or {}))
        from datetime import timedelta
        from contextlib import ExitStack
        from qa.p4_research import n12_app_journey as journey
        start = datetime(2026, 11, 21, tzinfo=timezone.utc)
        roots = []
        if calibrated:
            roots = [{"role": "calibration", "pid": pid, "image": r"C:\qa\synthetic.exe"}
                     for pid in (70, 71)]
            self.manifest["processes"] = roots
            self.manifest["markers"] = {
                "launch": (start + timedelta(seconds=4)).isoformat(),
                "profile-exit": (start + timedelta(seconds=6)).isoformat(),
            }
        if restore_verified is not None:
            self.manifest["observed_roots"]["write-restore-control"] = (
                r"C:\qa\write-restore-control.bin")
            self.manifest["etw"]["events_sha256"] = "c" * 64
        def binding(*a, **kw):
            roles = {"a": "app", **({"b": "webview-network"} if role else {}),
                     **({"c": "webview"} if role and two_roles else {})}
            roles.update({f"cal-{i}": "calibration" for i in range(len(roots))})
            return roles, [({"role": "app"}, object()),
                           *((root, object()) for root in roots)]
        with ExitStack() as stack:
            stack.enter_context(patch.object(
                trace, "load_capture", return_value=(start, start, {}, [], set(issues or []))))
            stack.enter_context(patch.object(trace, "bind_processes", side_effect=binding))
            stack.enter_context(patch.object(
                trace, "scope",
                return_value=([r"C:\protected"], {"webview-network": [r"C:\qa"]})))
            stack.enter_context(patch.object(trace, "windows_path",
                                            side_effect=lambda p: p.casefold()))
            stack.enter_context(patch.object(trace, "inspect_etw_files", side_effect=strict))
            stack.enter_context(patch.object(
                trace, "calibration_window", side_effect=[
                    (start + timedelta(seconds=1), start + timedelta(seconds=2)),
                    (start + timedelta(seconds=8), start + timedelta(seconds=9)),
                ]))
            stack.enter_context(patch.object(
                trace, "etw_capture_contract",
                return_value=((100, 500), {r"\device\harddiskvolume3": "c:"})))
            stack.enter_context(patch.object(trace, "etw_events", return_value=iter(())))
            if restore_verified is not None:
                stack.enter_context(patch.object(
                    journey, "same_capture_restore_evidence",
                    return_value={
                        "status": "PASS" if restore_verified else "BLOCKED",
                        "write_path_verified": {
                            "mutate": True, "restore": bool(restore_verified)},
                    }))
            return review.reduce(
                self.manifest, Path("fixture.xml"), Path("fixture.jsonl"),
                self.handle, Path("fake.exe"), lifetime_report=self.life,
                snapshot=self.snap,
                restore_control={"private": "generated-only"} if restore_verified is not None else None)

    def test_invokes_governing_strict_reducer_and_guards_immutable_original(self):
        result = self.run_check()
        self.assertEqual(len(self.called), 1)
        args, kwargs = self.called[0]
        self.assertEqual(kwargs, {})
        self.assertIn(r"c:\qa\source.csv", args[6])
        self.assertEqual(args[7]["webview-network"], [r"C:\qa"])
        self.assertEqual(result["blocker"],
                         "no-cdp-original-webview-child-handles-unverified")
        self.assertEqual(result["original_webview_child_handle_lifetimes"], "NOT_EVALUATED")
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

    def test_complete_synthetic_child_receipt_is_reviewable_never_native_acceptance(self):
        self.life["no_cdp_private_child_handle_diagnostic"] = {
            "scope": "no-cdp-private-child-handle-reducer-diagnostic-only",
            "status": "REVIEWABLE_ONLY",
            "native_N12_acceptance": "NOT_EVALUATED",
            "failed_checks": {}, "child_role_counts": {"webview-network": 1},
            "verified_handle_counts": {"webview-network": 1},
        }
        # A single child without the required browser role cannot be treated
        # as a complete original WebView2 tree.
        report = self.run_check()
        self.assertEqual(report["original_webview_child_handle_lifetimes"],
                         "UNVERIFIED_OR_INCOMPLETE")
        self.assertEqual(report["status"], "BLOCKED")

    def test_missing_original_webview_and_profile_remain_explicit(self):
        self.life["no_cdp_profile_identity"] = {
            "status": "SOURCE_OS_CORROBORATED",
            "browser_process_identity": "UNIQUE_SYSMON_ETW_APP_PROFILE",
            "profile_process_lifetimes": "SYSMON_ETW_DESCENDANTS_EXITED",
            "webview_process_count": 1, "native_N12_acceptance": "NOT_EVALUATED",
        }
        receipt = self.run_check()
        self.assertEqual(receipt["browser_command_line_profile"],
                         "UNVERIFIED_OR_INCOMPLETE")
        self.assertEqual(receipt["effective_webview_user_data_folder"], "NOT_VERIFIED")

    def test_complete_original_handle_and_profile_counts_remain_only_reviewable(self):
        self.life["no_cdp_private_child_handle_diagnostic"] = {
            "scope": "no-cdp-private-child-handle-reducer-diagnostic-only",
            "status": "REVIEWABLE_ONLY", "native_N12_acceptance": "NOT_EVALUATED",
            "failed_checks": {},
            "child_role_counts": {"webview": 1, "webview-network": 1},
            "verified_handle_counts": {"webview": 1, "webview-network": 1},
        }
        self.life["no_cdp_profile_identity"] = {
            "status": "SOURCE_OS_CORROBORATED",
            "browser_process_identity": "UNIQUE_SYSMON_ETW_APP_PROFILE",
            "profile_process_lifetimes": "SYSMON_ETW_DESCENDANTS_EXITED",
            "webview_process_count": 2, "native_N12_acceptance": "NOT_EVALUATED",
        }
        result = self.run_check(two_roles=True)
        self.assertEqual(result["original_webview_child_handle_lifetimes"],
                         "PRIVATE_ORIGINAL_HANDLES_REVIEWABLE_ONLY")
        self.assertEqual(result["browser_command_line_profile"],
                         "SYSMON_ETW_BROWSER_PROFILE_COMMAND_LINE_REVIEWED")
        self.assertEqual(result["blocker"], "same-capture-write-and-restore-unverified")
        self.assertEqual(result["effective_webview_user_data_folder"], "NOT_VERIFIED")
        self.assertEqual(result["file_mutation_acceptance"], "NOT_EVALUATED")
        self.assertEqual(result["status"], "BLOCKED")

    def test_incomplete_child_inventory_or_mismatched_profile_fails(self):
        self.life["no_cdp_private_child_handle_diagnostic"] = {
            "scope": "no-cdp-private-child-handle-reducer-diagnostic-only",
            "status": "REVIEWABLE_ONLY", "native_N12_acceptance": "NOT_EVALUATED",
            "failed_checks": {},
            "child_role_counts": {"webview": 1, "webview-network": 1},
            "verified_handle_counts": {"webview": 1, "webview-network": 1},
        }
        self.life["no_cdp_profile_identity"] = {
            "status": "SOURCE_OS_CORROBORATED",
            "browser_process_identity": "UNIQUE_SYSMON_ETW_APP_PROFILE",
            "profile_process_lifetimes": "SYSMON_ETW_DESCENDANTS_EXITED",
            "webview_process_count": 3, "native_N12_acceptance": "NOT_EVALUATED",
        }
        wrong_profile = self.run_check(two_roles=True)
        self.assertEqual(wrong_profile["blocker"],
                         "no-cdp-browser-profile-command-line-unverified")
        self.assertEqual(wrong_profile["browser_command_line_profile"],
                         "UNVERIFIED_OR_INCOMPLETE")
        self.life["no_cdp_profile_identity"]["webview_process_count"] = 2
        self.life["no_cdp_private_child_handle_diagnostic"]["verified_handle_counts"] = {
            "webview": 1, "webview-network": 2,
        }
        wrong_children = self.run_check(two_roles=True)
        self.assertEqual(wrong_children["blocker"],
                         "no-cdp-original-webview-child-handles-unverified")
        self.assertEqual(wrong_children["original_webview_child_handle_lifetimes"],
                         "UNVERIFIED_OR_INCOMPLETE")

    def synthetic_positive_lifetime_receipts(self):
        self.life["no_cdp_private_child_handle_diagnostic"] = {
            "scope": "no-cdp-private-child-handle-reducer-diagnostic-only",
            "status": "REVIEWABLE_ONLY", "native_N12_acceptance": "NOT_EVALUATED",
            "failed_checks": {},
            "child_role_counts": {"webview": 1, "webview-network": 1},
            "verified_handle_counts": {"webview": 1, "webview-network": 1},
        }
        self.life["no_cdp_profile_identity"] = {
            "status": "SOURCE_OS_CORROBORATED",
            "browser_process_identity": "UNIQUE_SYSMON_ETW_APP_PROFILE",
            "profile_process_lifetimes": "SYSMON_ETW_DESCENDANTS_EXITED",
            "webview_process_count": 2, "native_N12_acceptance": "NOT_EVALUATED",
        }

    def test_two_generated_bookends_and_both_restore_writes_can_only_be_reviewable(self):
        self.synthetic_positive_lifetime_receipts()
        result = self.run_check(two_roles=True, calibrated=True, restore_verified=True)
        self.assertEqual(result["same_capture_write_restore"],
                         "TWO_UNIQUE_WRITES_CORROBORATED")
        self.assertEqual(result["generated_calibration_bookends"],
                         "BOOKEND_OS_FILE_NETWORK_REVIEWABLE")
        self.assertEqual(result["calibration_and_transient_write_proof"],
                         "SOURCE_ONLY_CONTROL_REVIEWABLE")
        self.assertEqual(result["blocker"],
                         "full-native-product-write-containment-not-yet-proven")
        self.assertEqual(result["status"], "BLOCKED")
        self.assertEqual(result["native_N12_acceptance"], "NOT_EVALUATED")
        self.assertEqual(result["file_mutation_acceptance"], "NOT_EVALUATED")
        self.assertNotIn("synthetic.exe", json.dumps(result))

    def test_missing_restored_write_blocks_even_if_endpoints_match(self):
        self.synthetic_positive_lifetime_receipts()
        result = self.run_check(two_roles=True, calibrated=True, restore_verified=False)
        self.assertEqual(result["same_capture_write_restore"], "BLOCKED")
        self.assertEqual(result["generated_calibration_bookends"],
                         "BOOKEND_OS_FILE_NETWORK_REVIEWABLE")
        self.assertEqual(result["calibration_and_transient_write_proof"],
                         "UNVERIFIED_OR_INCOMPLETE")
        self.assertEqual(result["status"], "BLOCKED")
        self.assertGreater(result["reducer_issue_count"], 0)
        self.assertEqual(result["full_product_tree_mutation_containment"], "NOT_DEMONSTRATED")

    def test_generated_protected_control_writes_are_never_silently_exempted(self):
        self.synthetic_positive_lifetime_receipts()
        result = self.run_check(
            two_roles=True, calibrated=True, restore_verified=True,
            violation={"protected:other:write": 2})
        self.assertEqual(result["same_capture_write_restore"],
                         "TWO_UNIQUE_WRITES_CORROBORATED")
        self.assertEqual(result["prohibited_by_role"]["other"], 2)
        self.assertEqual(result["observed_prohibited_operations"], 2)
        self.assertEqual(result["blocker"], "observed-prohibited-fileio-operations")
        self.assertEqual(result["full_product_tree_mutation_containment"], "NOT_DEMONSTRATED")
        self.assertEqual(result["file_mutation_acceptance"], "NOT_EVALUATED")

    def test_etw_loss_blocks_both_positive_controls_even_when_mock_returns_pass(self):
        self.synthetic_positive_lifetime_receipts()
        self.manifest["etw"]["counters"]["events_lost"] = 1
        result = self.run_check(two_roles=True, calibrated=True, restore_verified=True)
        self.assertEqual(result["generated_calibration_bookends"], "BLOCKED")
        self.assertEqual(result["same_capture_write_restore"], "BLOCKED")
        self.assertEqual(result["calibration_and_transient_write_proof"],
                         "UNVERIFIED_OR_INCOMPLETE")
        self.assertEqual(result["etw_loss_counters"], "LOSS_OR_UNVERIFIED")
        self.assertEqual(result["status"], "BLOCKED")
        self.assertEqual(result["native_N12_acceptance"], "NOT_EVALUATED")

    def test_product_prohibited_writes_remain_even_if_controls_reviewable(self):
        self.synthetic_positive_lifetime_receipts()
        result = self.run_check(two_roles=True, calibrated=True, restore_verified=True,
                                violation={"outside-scope:webview-network:write": 113})
        self.assertEqual(result["observed_prohibited_operations"], 113)
        self.assertEqual(result["blocker"], "observed-prohibited-fileio-operations")
        self.assertEqual(result["file_mutation_acceptance"], "NOT_EVALUATED")

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
    def test_hosted_sysmon_network_event3_does_not_discard_empty_include_markers(self):
        """Source contract only: a generated TCP/UDP fixture must be observable."""
        from qa.p4_research import n12_app_build as build
        wrapper = (build.REPO / "qa/p4_native/Invoke_P4_N12_Live_Calibration.ps1"
                   ).read_text(encoding="utf-8")
        self.assertIn('<NetworkConnect onmatch="exclude" />', wrapper)
        self.assertNotIn('<NetworkConnect onmatch="include" />', wrapper)
        self.assertNotIn('$definition = $definition.Replace(', wrapper)
        self.assertIn('Event ID 3 must be captured', wrapper)
        self.assertIn('-NoCdpFileIO', wrapper)

    def test_powershell_native_entry_requires_new_scoped_permission_and_fileio_dispatch(self):
        """Source inspection only: no PowerShell command or native app runs."""
        from qa.p4_research import n12_app_build as build
        wrapper = (build.REPO / "qa/p4_native/Invoke_P4_N12_Live_Calibration.ps1"
                   ).read_text(encoding="utf-8")
        required = (
            "[switch]$NoCdpFileIO",
            "if ($NoCdpFileIO -and (",
            "-not $NoCdp -or -not $AppLifetime -or -not $WithEtw",
            "PILOTODIN_N12_NO_CDP_FILEIO_CONSENT -cne 'I_APPROVE_ONE_N12_NO_CDP_FILEIO'",
            "PILOTODIN_N12_CHILD_HANDLE_CONSENT -cne 'I_APPROVE_ONE_N12_QA_CHILD_HANDLES'",
            "PILOTODIN_N12_APP_LIFETIME_CONSENT -cne 'I_APPROVE_ONE_N12_APP_LIFETIME'",
            "PILOTODIN_N12_NO_CDP_STORAGE_CONSENT -cne 'I_APPROVE_ONE_N12_NO_CDP_STORAGE'",
            "PILOTODIN_N12_QA_AMBIENT_LOCAL_VARIANT -or",
            "PILOTODIN_N12_APPROVED_SOURCE -cne $SourceSha",
            "if ($NoCdpFileIO) { $lifetimeArgs += '--fileio' }",
            "python -B -m qa.p4_research.n12_app_lifetime @lifetimeArgs",
        )
        for marker in required:
            with self.subTest(marker=marker):
                self.assertIn(marker, wrapper)
        # All extra guards must appear before collector provisioning.
        self.assertLess(wrapper.index("if ($NoCdpFileIO -and ("),
                        wrapper.index("Get-MicrosoftCollector"))
        self.assertLess(wrapper.index("if ($NoCdpFileIO -and ("),
                        wrapper.index("python -B -m qa.p4_research.n12_app_build verify"))
        wf = (build.REPO / ".github/workflows/p4-n12-app-lifetime.yml"
              ).read_text(encoding="utf-8")
        self.assertIn("if: ${{ false }}", wf)
        self.assertNotIn("-NoCdpFileIO", wf)

    def test_new_fileio_capture_workflow_is_inert_and_requires_exact_owner_scope(self):
        """Read static workflow text only, with no Windows or app execution."""
        from qa.p4_research import n12_app_build as build
        marker = build.REPO / 'qa/p4_research/N12_NO_CDP_FILEIO_OWNER_APPROVAL.txt'
        workflow = (build.REPO / '.github/workflows/p4-n12-no-cdp-fileio.yml'
                    ).read_text(encoding='utf-8')
        self.assertFalse(marker.exists(), 'No owner has authorised this capture')
        for token in (
                'if: ${{ false }}',
                'N12_NO_CDP_FILEIO_OWNER_APPROVAL.txt',
                'scope=n12-one-build-one-no-cdp-fileio-baseline',
                'GITHUB_RUN_ATTEMPT',
                "(git rev-parse HEAD) -cne $env:GITHUB_SHA",
                'git rev-list --parents -n 1 HEAD',
                'git diff --name-only $source HEAD',
                'git checkout --detach $source',
                'I_APPROVE_ONE_N12_NO_CDP_FILEIO',
                'I_APPROVE_ONE_N12_QA_CHILD_HANDLES',
                'I_APPROVE_ONE_N12_NO_CDP_STORAGE',
                'I_APPROVE_ONE_N12_APP_LIFETIME',
                'n12_app_build stage --source',
                '-WithEtw -AppLifetime -NoCdp -NoCdpFileIO',
                'Redacted fixed-label diagnostic',
                'if: always()',
                "f.status -cne 'BLOCKED'",
                "f.native_N12_acceptance -cne 'NOT_EVALUATED'",
                'GITHUB_STEP_SUMMARY',
        ):
            with self.subTest(token=token):
                self.assertIn(token.casefold(), workflow.casefold())
        self.assertNotIn('actions/upload-artifact', workflow)
        self.assertNotIn('continue-on-error: true', workflow)
        self.assertNotIn('workflow_dispatch:', workflow)
        self.assertEqual(workflow.count('if: ${{ false }}'), 1)
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

    def test_fileio_without_original_webview_child_consent_fails_before_preflight(self):
        from qa.p4_research import n12_app_lifetime as lifetime
        from unittest.mock import patch
        import os
        source, digest = "a" * 40, "b" * 64
        env = {
            "PILOTODIN_N12_NO_CDP_FILEIO_CONSENT": lifetime.FILEIO_CONSENT,
            "PILOTODIN_N12_NO_CDP_STORAGE_CONSENT": lifetime.no_cdp_path.lifecycle.NATIVE_ACK_CONSENT,
            "PILOTODIN_N12_APP_LIFETIME_CONSENT": lifetime.CONSENT,
            "GITHUB_ACTIONS": "true", "RUNNER_ENVIRONMENT": "github-hosted",
            "RUNNER_OS": "Windows", "GITHUB_RUN_ATTEMPT": "1",
            "PILOTODIN_N12_APPROVED_SOURCE": source,
        }
        with patch.dict(os.environ, env, clear=True), \
             patch.object(lifetime.journey, "prepare_journey") as prepare:
            with self.assertRaisesRegex(trace.EvidenceValidationError, "original-child-handle-consent-required"):
                lifetime.capture(Path("fake"), Path("fake"),
                                 {"source_sha": source, "executable_sha256": digest},
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
        from contextlib import ExitStack, contextmanager, nullcontext
        from datetime import datetime, timedelta, timezone
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
                "PILOTODIN_N12_CHILD_HANDLE_CONSENT": lifetime.child_handles.CHILD_HANDLE_CONSENT,
            }
            # Every Windows/native action below is mocked. Only the generated
            # fixture CSV gets written in this local temporary directory.
            with ExitStack() as stack:
                stack.enter_context(patch.dict(os.environ, env, clear=True))
                hosted = stack.enter_context(patch.object(lifetime.child_pipe, "hosted_scope"))
                stack.enter_context(patch.object(
                    lifetime.trace, "local_disposable_path", side_effect=lambda path, **kw: path))
                initial_calibration = stack.enter_context(patch.object(
                    lifetime.journey, "run_initial_calibration"))
                finish_calibration = stack.enter_context(patch.object(
                    lifetime.journey, "calibrate", return_value={"role": "calibration",
                        "pid": 999, "image": "generated-only", "port": 9000}))
                verified_final = stack.enter_context(patch.object(
                    lifetime.journey, "verify_fixture_sysmon"))
                exercised = stack.enter_context(patch.object(
                    lifetime.restore, "exercise_restore", return_value={
                        "path": str(root / "write-restore-control.bin"),
                        "before": "e" * 64, "stages": {}}))
                stack.enter_context(patch.object(
                    lifetime.journey, "prepare_journey",
                    return_value=(manifest, root, root, root / "quality-source.csv",
                                  [root / "calibration-first", root / "calibration-last"])))
                stack.enter_context(patch.object(
                    lifetime.journey, "snapshots", return_value={"protected": {}, "observed": {}}))
                bracket = stack.enter_context(patch.object(
                    lifetime.journey, "snapshot_capture_evidence", return_value={"status": "PASS"}))
                stack.enter_context(patch.object(lifetime.journey, "sysmon_tail", side_effect=[1, 4]))
                stack.enter_context(patch.object(lifetime.journey, "export_sysmon"))
                powershell = stack.enter_context(patch.object(lifetime.journey, "powershell"))
                stack.enter_context(patch.object(
                    lifetime.journey, "report_file", side_effect=capture_file))
                stack.enter_context(patch.object(
                    lifetime.journey, "checkpoint_stage", side_effect=lambda *a: nullcontext()))
                collector = stack.enter_context(patch.object(
                    lifetime.etw, "fileio_process_session", side_effect=fixture_session))
                old_collector = stack.enter_context(patch.object(lifetime.etw, "process_session"))
                stack.enter_context(patch.object(
                    lifetime.n12_etw_probe, "volume_devices",
                    return_value={"C:": r"\Device\HarddiskVolume3"}))
                worker = stack.enter_context(patch.object(
                    lifetime, "launch_worker", return_value=(witness, witness, None)))
                stack.enter_context(patch.object(
                    lifetime.trace, "read_json", return_value={
                        "source_sha": source, "executable_sha256": digest,
                        "markers": {"launch": "x", "ready": "y",
                                    "close": "z", "profile-exit": "v"}}))
                stack.enter_context(patch.object(
                    lifetime.trace, "compare_snapshots",
                    return_value=({"protected_snapshot_comparison": "MATCH"}, set())))
                stack.enter_context(patch.object(
                    lifetime.build, "digest", return_value="d" * 64))
                stack.enter_context(patch.object(
                    lifetime.build, "executable", return_value=root / "fake.exe"))
                stack.enter_context(patch.object(
                    lifetime, "reduction", return_value={
                        "verdict": "PASS", "issues": [], "handle_comparison": {"app": "MATCH"}}))
                strict = stack.enter_context(patch.object(
                    lifetime.fileio_review, "reduce", return_value={
                        "status": "BLOCKED", "native_N12_acceptance": "NOT_EVALUATED"}))
                stack.enter_context(patch.object(lifetime.time, "sleep"))
                # Source-only test must not invoke a Windows FILETIME clock.
                clock_start = datetime(2026, 11, 21, tzinfo=timezone.utc)
                stack.enter_context(patch.object(
                    lifetime.journey, "now", side_effect=[
                        clock_start + timedelta(seconds=i) for i in range(10)]))
                receipt = lifetime.capture(root, root, provenance, no_cdp=True, fileio=True)
            collector.assert_called_once()
            initial_calibration.assert_called_once()
            finish_calibration.assert_called_once()
            verified_final.assert_called_once()
            exercised.assert_called_once_with(root / "write-restore-control.bin")
            self.assertIn("write-restore-control", manifest["observed_roots"])
            self.assertIn("write-restore-control", manifest["immutable_observed"])
            hosted.assert_called_once()
            self.assertEqual(hosted.call_args.args[1:], (source, digest))
            old_collector.assert_not_called()
            worker.assert_called_once()
            self.assertTrue(worker.call_args.kwargs["no_cdp"])
            bracket.assert_called_once()
            self.assertEqual(powershell.call_args.args[1], "etw-export")
            strict.assert_called_once()
            self.assertEqual(strict.call_args.args[0]["etw"]["events_sha256"], "d" * 64)
            self.assertEqual(strict.call_args.args[0]["etw"]["counters"]["buffers_written"], 5)
            self.assertEqual(strict.call_args.kwargs["restore_control"]["after"], "d" * 64)
            self.assertTrue({"snapshot-before-start", "snapshot-before-end",
                             "snapshot-after-start", "snapshot-after-end",
                             "restore-control-start", "restore-control-end",
                             "launch", "ready", "close", "profile-exit"} <=
                            manifest["markers"].keys())
            self.assertEqual(receipt["no_cdp_fileio"]["status"], "BLOCKED")
            self.assertEqual(saved["lifetime-report.json"]["no_cdp_fileio"]["native_N12_acceptance"],
                             "NOT_EVALUATED")

