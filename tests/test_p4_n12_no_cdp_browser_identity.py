"""Generated source-only controls for browser identity, never a native N12 run."""
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
import unittest

from qa.p4_native import n12_trace as trace
from qa.p4_research.n12_no_cdp_browser_identity import (
    resolve_browser_identity, verify_profile_shutdown,
)


BASE = datetime(2026, 11, 21, tzinfo=timezone.utc)
APP = r"C:\PilotODIN-QA\pilotodin.exe"
WEBVIEW = r"C:\EdgeRuntime\150.0.0.0\msedgewebview2.exe"
PROFILE = r"C:\Disposable QA\webview"
SHA = "a" * 64


def p(guid, parent, pid, image, command, start, end, sha=None):
    return trace.Process(guid=guid, parent=parent, pid=pid, image=trace.windows_path(image),
                         sha256=sha, start=start, command=command, end=end)


class EtwFixture:
    """Test double. Does not substitute for real EtwLifetimes and ETW loss proof."""
    def __init__(self):
        self.corrupt_parent = False
        self.corrupt_stop = False
        self.corrupt_child_parent = False

    def find(self, process, *, handle_witness=None):
        if process.guid == "app":
            assert handle_witness == {"pid": 101, "birth": trace.utc_ticks(BASE),
                                      "exit": trace.utc_ticks(BASE + timedelta(seconds=6))}
        # Synthetic sequence chain: app(4) -> browser(6) -> children(8/10).
        if process.guid == "app":
            parent, parent_sequence, sequence = 1, 0, 4
        elif process.guid == "browser":
            parent, parent_sequence, sequence = 101, 4, 6
        else:
            parent = 303 if process.parent == "renderer" else 202
            parent_sequence = 8 if process.parent == "renderer" else 6
            sequence = 8 if process.guid == "renderer" else 10
            if self.corrupt_child_parent:
                parent_sequence += 1
        birth = SimpleNamespace(pid=process.pid, creation=trace.utc_ticks(process.start),
                                parent=parent, parent_sequence=parent_sequence,
                                sequence=sequence)
        if process.end is None:
            raise trace.EvidenceValidationError("etw-stop-missing-or-ambiguous")
        stop = SimpleNamespace(exit=trace.utc_ticks(process.end)
                               - int(self.corrupt_stop) * 9_000_000_000)
        return birth, stop

    def parent_sequence_comparison(self, child, parent):
        return ("etw-parent-sequence-conflict"
                if self.corrupt_parent or (self.corrupt_child_parent
                                           and child.guid not in ("app", "browser"))
                else "etw-parent-sequence-agrees")


def fixture():
    app = p("app", "root", 101, APP, '"pilotodin.exe"', BASE,
            BASE + timedelta(seconds=6), SHA)
    browser = p("browser", "app", 202, WEBVIEW,
                f'"{WEBVIEW}" --user-data-dir="{PROFILE}" --no-first-run',
                BASE + timedelta(seconds=2), BASE + timedelta(seconds=5))
    renderer = p("renderer", "browser", 303, WEBVIEW,
                 f'"{WEBVIEW}" --type=renderer --user-data-dir="{PROFILE}"',
                 BASE + timedelta(seconds=2), BASE + timedelta(seconds=5))
    return {
        "processes": {q.guid: q for q in (app, browser, renderer)},
        "roles": {"app": "app", "browser": "webview", "renderer": "webview"},
        "app_guid": "app", "expected_app_image": APP, "expected_app_sha256": SHA,
        "disposable_profile": PROFILE,
        "launch": BASE + timedelta(seconds=1),
        "ready": BASE + timedelta(seconds=3),
        "close": BASE + timedelta(seconds=4),
        "capture_end": BASE + timedelta(seconds=7),
        "app_handle_witness": {"pid": 101, "birth": trace.utc_ticks(BASE),
                               "exit": trace.utc_ticks(BASE + timedelta(seconds=6))},
        "etw_lifetimes": EtwFixture(),
    }


class NoCdpBrowserIdentityTests(unittest.TestCase):
    def fail_with(self, params, label):
        with self.assertRaises(trace.EvidenceValidationError) as ctx:
            resolve_browser_identity(**params)
        self.assertEqual(str(ctx.exception), label)

    def test_unique_corroborated_browser_only_returns_redacted_scoped_receipt(self):
        params = fixture()
        result = resolve_browser_identity(**params)
        self.assertEqual(result.guid, "browser")
        receipt = result.redacted_receipt()
        self.assertEqual(receipt["browser_process_identity"], "UNIQUE_SYSMON_ETW_APP_PROFILE")
        self.assertEqual(receipt["native_N12_acceptance"], "NOT_EVALUATED")
        self.assertEqual(receipt["network_isolation"], "NOT_EVALUATED")
        self.assertNotIn("202", str(receipt))
        self.assertNotIn(PROFILE, repr(result))

    def test_missing_browser_or_multiple_browser_fails(self):
        a = fixture()
        del a["processes"]["browser"]
        self.fail_with(a, "no-cdp-browser-zero-or-multiple")
        b = fixture()
        b["processes"]["browser2"] = p("browser2", "app", 404, WEBVIEW,
             f'"{WEBVIEW}" --user-data-dir="{PROFILE}"',
             BASE + timedelta(seconds=2), BASE + timedelta(seconds=5))
        b["roles"]["browser2"] = "webview"
        self.fail_with(b, "no-cdp-browser-zero-or-multiple")

    def test_unbound_webview_is_not_ignored(self):
        a = fixture()
        a["roles"].pop("browser")
        self.fail_with(a, "no-cdp-webview-role-unverified")

    def test_reused_pid_does_not_win_based_on_number(self):
        a = fixture()
        a["processes"]["other"] = p("other", "root", 202, WEBVIEW,
                 f'"{WEBVIEW}" --user-data-dir="{PROFILE}"',
                 BASE + timedelta(seconds=2), BASE + timedelta(seconds=5))
        result = resolve_browser_identity(**a)
        self.assertEqual(result.guid, "browser")

    def test_missing_mismatched_or_duplicate_profile_switch_refused(self):
        for command, label in (
            (f'"{WEBVIEW}"', "no-cdp-browser-profile-ambiguous"),
            (f'"{WEBVIEW}" --user-data-dir="{PROFILE}" --user-data-dir="{PROFILE}"',
             "no-cdp-browser-profile-ambiguous"),
            (f'"{WEBVIEW}" --user-data-dir="C:\Wrong"', "no-cdp-browser-profile-mismatch"),
            (f'"{WEBVIEW}" --user-data-dir=relative', "no-cdp-browser-profile-invalid"),
            (f'"{WEBVIEW}" --user-data-dir "{PROFILE}"', "no-cdp-browser-profile-ambiguous"),
        ):
            with self.subTest(command=command[:20]):
                a = fixture()
                a["processes"]["browser"].command = command
                self.fail_with(a, label)

    def test_debug_flags_refused_on_browser_or_descendant(self):
        for who in ("browser", "renderer"):
            for switch in ("--remote-debugging-port=9331", "--log-net-log=x",
                           "--remote-debugging-pipe"):
                with self.subTest(who=who, switch=switch):
                    a = fixture()
                    a["processes"][who].command += " " + switch
                    self.fail_with(a, "no-cdp-debug-switch-present")

    def test_app_hash_and_image_and_handle_required(self):
        a = fixture()
        a["expected_app_sha256"] = "b" * 64
        self.fail_with(a, "no-cdp-app-source-unverified")
        b = fixture()
        b["expected_app_image"] = r"C:\Unknown\pilotodin.exe"
        self.fail_with(b, "no-cdp-app-source-unverified")
        c = fixture()
        c["app_handle_witness"] = None
        self.fail_with(c, "no-cdp-app-handle-unverified")

    def test_direct_app_parent_and_time_required(self):
        a = fixture()
        a["processes"]["browser"].parent = "renderer"
        self.fail_with(a, "no-cdp-browser-zero-or-multiple")
        b = fixture()
        b["processes"]["browser"].start = BASE - timedelta(seconds=1)
        self.fail_with(b, "no-cdp-browser-lifetime-unverified")
        c = fixture()
        c["processes"]["browser"].end = BASE + timedelta(seconds=3)
        self.fail_with(c, "no-cdp-browser-lifetime-unverified")

    def test_etw_parent_sequence_conflict_blocks(self):
        a = fixture()
        a["etw_lifetimes"].corrupt_parent = True
        self.fail_with(a, "no-cdp-etw-browser-ancestry-or-lifetime-unverified")

    def test_etw_stop_conflict_blocks(self):
        a = fixture()
        a["etw_lifetimes"].corrupt_stop = True
        self.fail_with(a, "no-cdp-etw-browser-ancestry-or-lifetime-unverified")

    def test_release_not_possible_from_pure_receipt(self):
        receipt = resolve_browser_identity(**fixture()).redacted_receipt()
        for key in ("native_N12_acceptance", "file_event_coverage", "network_isolation"):
            self.assertEqual(receipt[key], "NOT_EVALUATED")


def profile_fixture():
    f = fixture()
    f["profile_exit"] = BASE + timedelta(seconds=5, milliseconds=500)
    f["capture_loss_reviewed"] = True
    f["capture_issues"] = set()
    return f


def add_profile_child(args, *, guid="network", parent="browser",
                      end=BASE + timedelta(seconds=5)):
    child = p(guid, parent, 501, WEBVIEW,
              f'"{WEBVIEW}" --type=utility',
              BASE + timedelta(seconds=3), end)
    args["processes"][guid] = child
    args["roles"][guid] = "webview-network"
    return child


class NoCdpProfileShutdownSourceTests(unittest.TestCase):
    def test_browser_renderer_and_network_exit_with_private_receipt(self):
        args = profile_fixture()
        add_profile_child(args)
        result = verify_profile_shutdown(**args)
        self.assertEqual(len(result.webview_guids), 3)
        receipt = result.redacted_receipt()
        self.assertEqual(receipt["profile_process_lifetimes"], "SYSMON_ETW_DESCENDANTS_EXITED")
        self.assertEqual(receipt["webview_process_count"], 3)
        for key in ("native_N12_acceptance", "file_event_coverage",
                    "network_isolation", "profile_isolation"):
            self.assertEqual(receipt[key], "NOT_EVALUATED")
        self.assertNotIn(PROFILE, repr(result))
        self.assertNotIn("501", str(receipt))

    def test_source_loss_or_unreviewed_capture_never_claims_profile_exit(self):
        for field, value in (
            ("capture_loss_reviewed", False),
            ("capture_issues", {"etw-event-or-buffer-loss"}),
            ("capture_issues", {"sysmon-record-gap"}),
            ("capture_issues", {"sysmon-restart-config-change-or-error"}),
            ("capture_issues", None),
        ):
            with self.subTest(field=field, value=value):
                args = profile_fixture()
                args[field] = value
                with self.assertRaisesRegex(trace.EvidenceValidationError,
                                            "^no-cdp-profile-process-coverage-unverified$"):
                    verify_profile_shutdown(**args)

    def test_renderer_still_alive_after_profile_exit_blocks(self):
        args = profile_fixture()
        args["processes"]["renderer"].end = BASE + timedelta(seconds=6)
        with self.assertRaisesRegex(trace.EvidenceValidationError,
                                    "^no-cdp-profile-descendant-exit-unverified$"):
            verify_profile_shutdown(**args)

    def test_network_child_missing_stop_blocks(self):
        args = profile_fixture()
        add_profile_child(args, end=None)
        with self.assertRaisesRegex(trace.EvidenceValidationError,
                                    "^etw-stop-missing-or-ambiguous$"):
            verify_profile_shutdown(**args)

    def test_mismatched_descendant_parent_sequence_blocks(self):
        args = profile_fixture()
        args["etw_lifetimes"].corrupt_child_parent = True
        with self.assertRaisesRegex(trace.EvidenceValidationError,
                                    "^no-cdp-profile-etw-parent-or-lifetime-unverified$"):
            verify_profile_shutdown(**args)

    def test_renderer_outside_verified_browser_subtree_blocks(self):
        args = profile_fixture()
        args["processes"]["renderer"].parent = "app"
        # No explicit profile switch on this malformed branch, to isolate
        # the process-ancestry decision from the independent contender gate.
        args["processes"]["renderer"].command = f'"{WEBVIEW}" --type=renderer'
        with self.assertRaisesRegex(trace.EvidenceValidationError,
                                    "^no-cdp-profile-webview-unbound-parent$"):
            verify_profile_shutdown(**args)

    def test_external_webview_with_same_profile_blocks(self):
        args = profile_fixture()
        args["processes"]["outside"] = p("outside", "root", 901, WEBVIEW,
                     f'"{WEBVIEW}" --user-data-dir="{PROFILE}"',
                     BASE + timedelta(seconds=1), BASE + timedelta(seconds=5))
        with self.assertRaisesRegex(trace.EvidenceValidationError,
                                    "^no-cdp-profile-external-contender$"):
            verify_profile_shutdown(**args)

    def test_unrelated_profile_is_not_assigned_to_app(self):
        args = profile_fixture()
        args["processes"]["outside"] = p("outside", "root", 901, WEBVIEW,
                     f'"{WEBVIEW}" --user-data-dir="C:\\OtherProfile"',
                     BASE + timedelta(seconds=1), BASE + timedelta(seconds=5))
        self.assertEqual(verify_profile_shutdown(**args).redacted_receipt()[
            "native_N12_acceptance"], "NOT_EVALUATED")

    def test_descendant_explicit_different_profile_blocks(self):
        args = profile_fixture()
        # Replace the single existing switch; appending would instead
        # correctly fail the duplicate-switch parser first.
        args["processes"]["renderer"].command = (
            f'"{WEBVIEW}" --type=renderer --user-data-dir="C:\\Wrong"'
        )
        with self.assertRaisesRegex(trace.EvidenceValidationError,
                                    "^no-cdp-profile-child-profile-mismatch$"):
            verify_profile_shutdown(**args)

    def test_roles_process_keys_and_profile_stage_are_strict(self):
        args = profile_fixture()
        args["roles"].pop("renderer")
        with self.assertRaisesRegex(trace.EvidenceValidationError,
                                    "^no-cdp-webview-role-unverified$"):
            verify_profile_shutdown(**args)
        args = profile_fixture()
        args["processes"]["wrong"] = args["processes"].pop("renderer")
        with self.assertRaisesRegex(trace.EvidenceValidationError,
                                    "^no-cdp-profile-process-map-unverified$"):
            verify_profile_shutdown(**args)
        args = profile_fixture()
        args["profile_exit"] = BASE + timedelta(seconds=4, milliseconds=700)
        with self.assertRaisesRegex(trace.EvidenceValidationError,
                                    "^no-cdp-profile-descendant-exit-unverified$"):
            verify_profile_shutdown(**args)

    def test_no_profile_end_before_close_or_after_capture(self):
        for seconds in (3, 7):
            args = profile_fixture()
            args["profile_exit"] = BASE + timedelta(seconds=seconds)
            with self.assertRaisesRegex(trace.EvidenceValidationError,
                                        "^no-cdp-profile-exit-stage-unverified$"):
                verify_profile_shutdown(**args)


if __name__ == "__main__":
    unittest.main()
