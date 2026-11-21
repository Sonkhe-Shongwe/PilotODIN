"""Source-only no-CDP lifecycle stitching; all subprocess/window effects mocked."""
from contextlib import ExitStack
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from qa.p4_native import n12_trace as trace
from qa.p4_research import n12_app_journey as journey
from qa.p4_research import n12_no_cdp_log_witness as log
from qa.p4_research import n12_no_cdp_lifecycle as lifecycle
from qa.p4_research import n12_no_cdp_main_window as win


SOURCE = "a" * 40
EXE_SHA = "b" * 64
IMAGE = r"C:\PilotODIN-QA\pilotodin-desktop.exe"
PROFILE = r"C:\DisposableQA\webview"
TITLE = "PilotODIN QA"
BIRTH = 639098000000000000


class FakeProcess:
    pid = 9312
    returncode = None

    def poll(self):
        return self.returncode

    def wait(self, timeout=None):
        return self.returncode

    def kill(self):
        # Match the existing QA stack's fail-safe cleanup for a fake launch.
        self.returncode = -9


def fake_handle(app):
    return {"pid": app.pid, "birth": BIRTH, "exit": None}


def fake_window(app, **expected):
    assert (expected["expected_image"], expected["expected_title"],
            expected["expected_birth_ticks"]) == (IMAGE, TITLE, BIRTH)
    return win.MainWindowIdentity(9411, app.pid, BIRTH)


def fake_recheck(previous, app, **expected):
    assert previous.hwnd == 9411
    assert (expected["expected_image"], expected["expected_title"]) == (IMAGE, TITLE)
    return previous


class NoCdpLifecycleStitchTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.root = Path(self.folder.name)
        self.process = FakeProcess()

    def observer(self, stack, **changes):
        a = {"stack": stack, "expected_source": SOURCE, "actual_source": SOURCE,
             "expected_executable_sha256": EXE_SHA, "actual_executable_sha256": EXE_SHA,
             "expected_image": IMAGE, "expected_title": TITLE}
        a.update(changes)
        return lifecycle.NoCdpLifecycleObserver(**a)

    def synthetic_spawn(self, stack, observer):
        log_path = self.root / "app.log"
        manifest = {"processes": []}
        def popen(*args, **kwargs):
            self.assertEqual(log_path.read_bytes(), b"")
            self.assertFalse(observer._witness.handle.closed)
            return self.process
        with patch.object(journey.subprocess, "Popen", side_effect=popen) as call:
            journey.spawn(stack, manifest, "app", ["not-run.exe"], {},
                          self.root, log_path,
                          prelaunch_log_hook=observer.prelaunch_hook)
            call.assert_called_once()
        self.assertEqual(manifest["processes"][0]["pid"], self.process.pid)
        return log_path

    def source_run(self):
        stack = ExitStack()
        self.addCleanup(stack.close)
        observer = self.observer(stack)
        file = self.synthetic_spawn(stack, observer)
        observer.bind_process(self.process, handle_reader=fake_handle)
        file.write_bytes(log.MARKER + b"\n")
        receipt = observer.observe_readiness(window_observer=fake_window)
        return observer, file, receipt

    def test_strict_ordered_lifecycle_has_no_native_acceptance_and_held_log(self):
        observer, file, ready = self.source_run()
        self.assertEqual(ready["native_N12_acceptance"], "NOT_EVALUATED")
        self.assertFalse(observer._witness.handle.closed)
        close_ready = observer.prepare_normal_close(recheck_window=fake_recheck)
        self.assertEqual(close_ready["normal_close"], "EXTERNAL_HELPER_REQUIRED")
        self.process.returncode = 0  # Fake the separately reviewed normal OS close
        receipt = observer.verify_after_close(
            close_request_verified=True,
            profile_processes_before=2, profile_processes_after=0)
        self.assertEqual(receipt["profile_process_identity"], "NOT_EVALUATED")
        self.assertEqual(receipt["browser_process_identity"], "NOT_EVALUATED")
        self.assertEqual(receipt["native_N12_acceptance"], "NOT_EVALUATED")
        self.assertEqual(receipt["network_isolation"], "NOT_EVALUATED")
        self.assertNotIn(str(file), str(receipt))
        self.assertNotIn("9312", str(receipt))
        self.assertNotIn("9411", str(receipt))
        with self.assertRaisesRegex(trace.EvidenceValidationError,
                                    "^no-cdp-postclose-stage-invalid$"):
            observer.verify_after_close(close_request_verified=True,
                                        profile_processes_before=1,
                                        profile_processes_after=0)

    def test_reject_stale_log_before_any_process_creation(self):
        with ExitStack() as stack, patch.object(journey.subprocess, "Popen") as popen:
            observer = self.observer(stack)
            file = self.root / "app.log"
            file.write_bytes(b"old log\n")
            with self.assertRaises(FileExistsError):
                journey.spawn(stack, {"processes": []}, "app", ["fake.exe"], {},
                              self.root, file, prelaunch_log_hook=observer.prelaunch_hook)
            popen.assert_not_called()

    def test_wrong_provenance_blocks_in_prelaunch_and_keeps_no_process(self):
        with ExitStack() as stack, patch.object(journey.subprocess, "Popen") as popen:
            observer = self.observer(stack, actual_executable_sha256="c" * 64)
            with self.assertRaisesRegex(trace.EvidenceValidationError,
                                        "^no-cdp-executable-unverified$"):
                journey.spawn(stack, {"processes": []}, "app", ["fake.exe"], {},
                              self.root, self.root / "app.log",
                              prelaunch_log_hook=observer.prelaunch_hook)
            popen.assert_not_called()

    def test_missing_log_marker_does_not_reach_close(self):
        with ExitStack() as stack:
            observer = self.observer(stack)
            self.synthetic_spawn(stack, observer)
            observer.bind_process(self.process, handle_reader=fake_handle)
            ticks = iter([0.0, 1.0, 2.0])
            with self.assertRaisesRegex(trace.EvidenceValidationError,
                                        "^no-cdp-readiness-timeout$"):
                observer.observe_readiness(window_observer=fake_window,
                                           timeout_seconds=1,
                                           clock=lambda: next(ticks),
                                           sleep=lambda _: None)
            with self.assertRaisesRegex(trace.EvidenceValidationError,
                                        "^no-cdp-close-stage-invalid$"):
                observer.prepare_normal_close(recheck_window=fake_recheck)

    def test_missing_verified_window_does_not_permit_readiness(self):
        with ExitStack() as stack:
            observer = self.observer(stack)
            file = self.synthetic_spawn(stack, observer)
            observer.bind_process(self.process, handle_reader=fake_handle)
            file.write_bytes(log.MARKER + b"\n")
            with self.assertRaisesRegex(trace.EvidenceValidationError,
                                        "^no-cdp-window-result-unverified$"):
                observer.observe_readiness(window_observer=lambda *_args, **_kwargs: None)
            with self.assertRaisesRegex(trace.EvidenceValidationError,
                                        "^no-cdp-close-stage-invalid$"):
                observer.prepare_normal_close(recheck_window=fake_recheck)

    def test_changed_window_identity_blocks_before_external_close(self):
        observer, file, _ = self.source_run()
        with self.assertRaisesRegex(trace.EvidenceValidationError,
                                    "^no-cdp-window-recheck-unverified$"):
            observer.prepare_normal_close(
                recheck_window=lambda *_a, **_kw: win.MainWindowIdentity(
                    9999, self.process.pid, BIRTH))
        self.assertFalse(observer._close_prepared)
        self.assertTrue(file.is_file())

    def test_early_or_nonzero_exit_does_not_yield_success(self):
        observer, _, _ = self.source_run()
        observer.prepare_normal_close(recheck_window=fake_recheck)
        for code in (None, 7):
            self.process.returncode = code
            with self.subTest(code=code):
                with self.assertRaisesRegex(trace.EvidenceValidationError,
                                            "^no-cdp-graceful-close-unverified$"):
                    observer.verify_after_close(
                        close_request_verified=True, profile_processes_before=1,
                        profile_processes_after=0)

    def test_close_without_os_proof_never_qualifies(self):
        observer, _, _ = self.source_run()
        observer.prepare_normal_close(recheck_window=fake_recheck)
        self.process.returncode = 0
        with self.assertRaisesRegex(trace.EvidenceValidationError,
                                    "^no-cdp-graceful-close-unverified$"):
            observer.verify_after_close(
                close_request_verified=False,
                profile_processes_before=1, profile_processes_after=0)

    def test_profile_diagnostic_requires_preclose_positive_and_postclose_zero(self):
        observer, _, _ = self.source_run()
        observer.prepare_normal_close(recheck_window=fake_recheck)
        self.process.returncode = 0
        for before, after in ((0, 0), (1, 1), (1, -1), (True, 0), (1, False),
                              (None, 0), (1, None)):
            with self.subTest(before=before, after=after):
                with self.assertRaisesRegex(
                    trace.EvidenceValidationError,
                    "^no-cdp-profile-count-diagnostic-unverified$",
                ):
                    observer.verify_after_close(
                        close_request_verified=True,
                        profile_processes_before=before, profile_processes_after=after)

    def test_postclose_second_marker_is_rejected(self):
        observer, file, _ = self.source_run()
        observer.prepare_normal_close(recheck_window=fake_recheck)
        file.write_bytes(log.MARKER + b"\n" + log.MARKER + b"\n")
        self.process.returncode = 0
        with self.assertRaisesRegex(trace.EvidenceValidationError,
                                    "^no-cdp-postclose-marker-missing-or-duplicate$"):
            observer.verify_after_close(
                close_request_verified=True,
                profile_processes_before=1, profile_processes_after=0)

    def test_prelaunch_observer_single_use_and_cleanup(self):
        with ExitStack() as stack:
            observer = self.observer(stack)
            self.synthetic_spawn(stack, observer)
            with self.assertRaisesRegex(trace.EvidenceValidationError,
                                        "^no-cdp-prelaunch-repeated$"):
                observer.prelaunch_hook(self.root / "app.log")
            self.assertFalse(observer._witness.handle.closed)
        self.assertTrue(observer._witness.handle.closed)

    def test_no_cdp_environment_refuses_unconsented_debugged_or_unscoped(self):
        app = {"PILOTODIN_N12_NO_CDP_STORAGE_CONSENT": lifecycle.NATIVE_ACK_CONSENT,
               "WEBVIEW2_USER_DATA_FOLDER": PROFILE}
        vite = {"VITE_PILOTODIN_N12_NO_CDP": "1"}
        self.assertTrue(lifecycle.verify_opt_in_environment(
            vite_env=vite, app_env=app, expected_profile=PROFILE))
        bad = [
            (vite, {**app, "WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS":
                     "--remote-debugging-port=9331"}, PROFILE,
             "no-cdp-browser-override-present"),
            (vite, {**app, "WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS": "--log-net-log=a"}, PROFILE,
             "no-cdp-browser-override-present"),
            (vite, {**app, "WEBVIEW2_USER_DATA_FOLDER": r"C:\Wrong"}, PROFILE,
             "no-cdp-profile-setting-mismatch"),
            ({"VITE_PILOTODIN_N12_NO_CDP": "0"}, app, PROFILE,
             "no-cdp-opt-in-consent-missing"),
            (vite, {"WEBVIEW2_USER_DATA_FOLDER": PROFILE}, PROFILE,
             "no-cdp-opt-in-consent-missing"),
            ({**vite, "WEBVIEW2_BROWSER_EXECUTABLE_FOLDER": "secret"}, app, PROFILE,
             "no-cdp-vite-browser-override-present"),
        ]
        for vite_env, app_env, profile, label in bad:
            with self.subTest(label=label):
                with self.assertRaisesRegex(trace.EvidenceValidationError,
                                            "^" + label + "$"):
                    lifecycle.verify_opt_in_environment(
                        vite_env=vite_env, app_env=app_env,
                        expected_profile=profile)

    def test_lifecycle_has_no_launch_or_close_or_native_main(self):
        self.assertFalse(hasattr(lifecycle.NoCdpLifecycleObserver, "launch"))
        self.assertFalse(hasattr(lifecycle.NoCdpLifecycleObserver, "close"))
        self.assertFalse(hasattr(lifecycle, "main"))


if __name__ == "__main__":
    unittest.main()
