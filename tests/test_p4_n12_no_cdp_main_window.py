"""Generated no-CDP window identity fixtures only. No native process is started."""
from dataclasses import replace
import unittest
from unittest.mock import patch

from qa.p4_native import n12_trace as trace
from qa.p4_research import n12_no_cdp_main_window as win


APP = r"C:\PilotODIN-QA\pilotodin-desktop.exe"
TITLE = "pilotODIN QA"
BIRTH = 639098000000000000


def window(hwnd=700, pid=1234, title=TITLE, visible=True, owner=0, root=None):
    return win.WindowRecord(hwnd, pid, title, visible, owner, hwnd if root is None else root)


def good(**overrides):
    props = dict(records=[window(), window(800, title="QA hidden peer", visible=False)],
                 expected_pid=1234, expected_image=APP, observed_image=APP,
                 expected_birth_ticks=BIRTH, observed_birth_ticks=BIRTH,
                 expected_title=TITLE, process_live=True)
    props.update(overrides)
    return props


class MainWindowIdentityTests(unittest.TestCase):
    def fail_with(self, error, **overrides):
        with self.assertRaises(trace.EvidenceValidationError) as ctx:
            win.select_main_window(**good(**overrides))
        self.assertEqual(str(ctx.exception), error)

    def test_unique_main_window_and_hidden_peer_are_safe_at_selector_scope(self):
        result = win.select_main_window(**good())
        self.assertEqual((result.hwnd, result.pid, result.process_birth_ticks),
                         (700, 1234, BIRTH))
        receipt = result.redacted_receipt()
        for key in ("native_N12_acceptance", "browser_process_identity",
                    "network_isolation", "file_event_coverage"):
            self.assertEqual(receipt[key], "NOT_EVALUATED")
        self.assertNotIn(APP, repr(result))
        self.assertNotIn("1234", str(receipt))
        self.assertNotIn(TITLE, str(receipt))

    def test_missing_or_duplicate_window_blocks(self):
        self.fail_with("no-cdp-window-missing-or-ambiguous", records=[])
        self.fail_with("no-cdp-window-missing-or-ambiguous",
                       records=[window(), window(710)])
        self.fail_with("no-cdp-window-missing-or-ambiguous",
                       records=[window(title="Different")])

    def test_hidden_duplicate_or_foreign_identical_title_blocks(self):
        self.fail_with("no-cdp-window-missing-or-ambiguous",
                       records=[window(), window(710, visible=False)])
        self.fail_with("no-cdp-window-title-collision",
                       records=[window(), window(810, pid=56)])

    def test_wrong_pid_title_case_and_different_process_exe_block(self):
        self.fail_with("no-cdp-window-title-collision", records=[window(pid=58)])
        self.fail_with("no-cdp-window-missing-or-ambiguous",
                       records=[window(title=TITLE.lower())])
        self.fail_with("no-cdp-window-executable-mismatch",
                       observed_image=r"C:\Other\pilotodin-desktop.exe")

    def test_process_liveness_birth_and_pid_reuse_fail_closed(self):
        self.fail_with("no-cdp-window-process-lifetime-unverified", process_live=False)
        self.fail_with("no-cdp-window-process-lifetime-unverified",
                       observed_birth_ticks=BIRTH + 1)
        self.fail_with("no-cdp-window-process-lifetime-unverified", expected_pid=0)
        self.fail_with("no-cdp-window-process-lifetime-unverified",
                       observed_birth_ticks=None)
        self.fail_with("no-cdp-window-process-lifetime-unverified",
                       expected_birth_ticks=0)

    def test_owned_nested_or_invisible_not_main(self):
        self.fail_with("no-cdp-window-not-unique-top-level",
                       records=[window(visible=False)])
        self.fail_with("no-cdp-window-not-unique-top-level",
                       records=[window(owner=73)])
        self.fail_with("no-cdp-window-not-unique-top-level",
                       records=[window(root=500)])

    def test_untrusted_malformed_and_duplicate_window_records_fail(self):
        self.fail_with("no-cdp-window-snapshot-unverified", records=None)
        self.fail_with("no-cdp-window-snapshot-unverified",
                       records=[window(), replace(window(), title="same-handle")])
        self.fail_with("no-cdp-window-snapshot-unverified",
                       records=[replace(window(), hwnd=-3)])
        self.fail_with("no-cdp-window-snapshot-unverified",
                       records=[{"hwnd": 700}])
        self.fail_with("no-cdp-window-snapshot-unverified",
                       records=[window()] * (win.MAX_ENUM_WINDOWS + 1))

    def test_read_only_windows_entrypoint_refuses_non_windows_without_queries(self):
        if win.os.name == "nt":
            self.skipTest("Windows pure-selector CI coverage applies; no native run")
        class Process:
            pid = 1234
        with self.assertRaisesRegex(trace.EvidenceValidationError,
                                    "^no-cdp-window-windows-only$"):
            win.observe_main_window(Process(), expected_image=APP,
                                    expected_title=TITLE, expected_birth_ticks=BIRTH)

    def test_old_window_recheck_does_not_accept_changed_hwnd(self):
        class Process:
            pid = 1234
        previous = win.MainWindowIdentity(700, 1234, BIRTH)
        with patch.object(win, "observe_main_window",
                          return_value=win.MainWindowIdentity(701, 1234, BIRTH)):
            with self.assertRaisesRegex(trace.EvidenceValidationError,
                                        "^no-cdp-window-changed-before-close$"):
                win.confirm_same_main_window(previous, Process(),
                                             expected_image=APP, expected_title=TITLE)

    def test_matching_recheck_requires_same_app_birth(self):
        class Process:
            pid = 1234
        previous = win.MainWindowIdentity(700, 1234, BIRTH)
        with patch.object(win, "observe_main_window",
                          return_value=win.MainWindowIdentity(700, 1234, BIRTH + 1)):
            with self.assertRaisesRegex(trace.EvidenceValidationError,
                                        "^no-cdp-window-changed-before-close$"):
                win.confirm_same_main_window(previous, Process(),
                                             expected_image=APP, expected_title=TITLE)

    def test_no_actual_windows_api_or_close_in_fixture_suite(self):
        self.assertEqual(win.MAX_TITLE_CHARS, 1024)
        self.assertEqual(win.select_main_window(**good()).redacted_receipt()[
            "main_window_identity"], "UNIQUE_MATCHING_PROCESS_WINDOW")
        self.assertFalse(hasattr(win, "close_window"))


if __name__ == "__main__":
    unittest.main()
