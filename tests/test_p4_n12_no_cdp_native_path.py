"""Generated checks for a dormant no-CDP native launch and close path.

No native application, WebView2, real Windows process or data is touched.
"""
from contextlib import ExitStack
from pathlib import Path
from tempfile import TemporaryDirectory
import os
import unittest
from unittest.mock import patch

from qa.p4_native import n12_trace as trace
from qa.p4_native import n12_lifetime_control as control
from qa.p4_research import n12_app_journey as journey
from qa.p4_research import n12_app_lifetime as lifetime
from qa.p4_research import n12_no_cdp_native_path as native


SOURCE = "a" * 40
SHA = "b" * 64


class FakeApp:
    pid = 92231

    def __init__(self):
        self.returncode = None

    def poll(self):
        return self.returncode

    def wait(self, timeout=None):
        return self.returncode


class FakeObserver:
    latest = None

    def __init__(self, **kwargs):
        self.events = []
        FakeObserver.latest = self

    def prelaunch_hook(self, path):
        self.events.append("prelaunch")
        return object()

    def bind_process(self, app):
        self.events.append("bind")
        assert app.pid == FakeApp.pid

    def observe_readiness(self, **kwargs):
        self.events.append("ready")
        assert kwargs == {"timeout_seconds": 40, "window_timeout_seconds": 15}
        return {"native_N12_acceptance": "NOT_EVALUATED"}

    def prepare_normal_close(self):
        self.events.append("preclose")

    def verify_after_close(self, **kwargs):
        self.events.append("postclose")
        assert kwargs == {"close_request_verified": True,
                          "profile_processes_before": 2,
                          "profile_processes_after": 0}
        return {"scope": "no-cdp-source-lifecycle-witness-only",
                "profile_process_identity": "NOT_EVALUATED",
                "native_N12_acceptance": "NOT_EVALUATED",
                "network_isolation": "NOT_EVALUATED"}


class NoCdpNativePathTests(unittest.TestCase):
    def setUp(self):
        folder = TemporaryDirectory(prefix="pilotodin-no-cdp-fixture-")
        self.addCleanup(folder.cleanup)
        self.root = Path(folder.name)
        self.profile = self.root / "webview"
        self.profile.mkdir()
        (self.profile / journey.APP_TEMP_DIR).mkdir()
        self.env = {"PILOTODIN_N12_NO_CDP_STORAGE_CONSENT":
                    native.lifecycle.NATIVE_ACK_CONSENT}

    def environments(self, changes=None):
        with patch.object(trace, "windows_path", side_effect=lambda value: str(value).casefold()):
            return native.no_cdp_environments({**self.env, **(changes or {})}, self.profile)

    def test_debugger_free_disposable_qa_environments(self):
        vite, app = self.environments()
        self.assertEqual(vite["VITE_PILOTODIN_N12_NO_CDP"], "1")
        self.assertEqual(app["WEBVIEW2_USER_DATA_FOLDER"], str(self.profile))
        self.assertNotIn("WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS", app)
        self.assertNotIn("WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS", vite)
        for key in ("TEMP", "TMP", "TMPDIR"):
            self.assertEqual(app[key], str(self.profile / journey.APP_TEMP_DIR))

    def test_missing_consent_or_inherited_webview_override_blocks(self):
        for changes in (
            {"WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS": "--remote-debugging-port=9331"},
            {"WEBVIEW2_BROWSER_EXECUTABLE_FOLDER": "unsafe"},
            {"WEBVIEW2_USER_DATA_FOLDER": "unsafe"},
            {"PILOTODIN_N12_NO_CDP_STORAGE_CONSENT": "wrong"},
        ):
            with self.subTest(changes=changes):
                with self.assertRaises(trace.EvidenceValidationError):
                    self.environments(changes)
        with self.assertRaisesRegex(trace.EvidenceValidationError, "profile-unverified"):
            native.no_cdp_environments(self.env, self.root / "missing")

    def test_strict_ordered_app_launch_and_normal_close_without_cdp(self):
        binary = self.root / "pilotodin-desktop.exe"
        binary.write_bytes(b"synthetic fixture, not a real binary")
        app = FakeApp()
        events = []
        saved = {}

        def fake_spawn(*args, **kwargs):
            self.assertIn("prelaunch_log_hook", kwargs)
            self.assertEqual(kwargs["prelaunch_log_hook"].__self__, FakeObserver.latest)
            events.append("spawn")
            return app

        def fake_power(*args, **kwargs):
            events.append("profile-count")
            return "2" if events.count("profile-count") == 1 else "0"

        def normal_close(*_):
            self.assertEqual(FakeObserver.latest.events[-1], "preclose")
            events.append("normal-close")
            app.returncode = 0

        def wait_for(predicate, seconds, message):
            self.assertEqual(seconds, 25)
            self.assertTrue(predicate(), message)

        with ExitStack() as stack, \
             patch.object(native.lifecycle, "NoCdpLifecycleObserver", FakeObserver), \
             patch.object(journey, "spawn", side_effect=fake_spawn) as spawn, \
             patch.object(journey, "powershell", side_effect=fake_power), \
             patch.object(journey, "request_graceful_close", side_effect=normal_close) as close, \
             patch.object(journey, "wait_for", side_effect=wait_for), \
             patch.object(journey, "report_file", side_effect=lambda p, obj: saved.update({p.name: obj})), \
             patch.object(control, "process_images", return_value={"image_dos": "synthetic"}), \
             patch.object(control, "process_times",
                          return_value={"pid": app.pid, "birth": 42, "exit": 99}):
            manifest = {"markers": {}, "processes": []}
            result = native.run_one_no_cdp_app(
                stack=stack, manifest=manifest, root=self.root, binary=binary,
                title="PilotODIN QA", source=SOURCE, expected_hash=SHA,
                app_env={**self.env, "WEBVIEW2_USER_DATA_FOLDER": str(self.profile)},
                profile=self.profile,
            )
        self.assertEqual(FakeObserver.latest.events, ["bind", "ready", "preclose", "postclose"])
        self.assertEqual(events, ["spawn", "profile-count", "normal-close", "profile-count"])
        self.assertEqual(close.call_count, 1)
        self.assertEqual(spawn.call_count, 1)
        self.assertEqual(result["pid"], app.pid)
        self.assertEqual(list(manifest["markers"]), ["launch", "ready", "close", "profile-exit"])
        self.assertEqual(saved["no-cdp-source-witness.json"]["native_N12_acceptance"],
                         "NOT_EVALUATED")
        self.assertNotIn(str(self.root), str(saved["no-cdp-source-witness.json"]))

    def test_unsafe_app_environment_refuses_without_spawning(self):
        with ExitStack() as stack, patch.object(journey, "spawn") as spawn:
            with self.assertRaisesRegex(trace.EvidenceValidationError,
                                        "no-cdp-app-launch-scope-unverified"):
                native.run_one_no_cdp_app(
                    stack=stack, manifest={"markers": {}}, root=self.root,
                    binary=self.root / "fake.exe", title="QA", source=SOURCE,
                    expected_hash=SHA,
                    app_env={**self.env,
                             "WEBVIEW2_USER_DATA_FOLDER": str(self.profile),
                             "WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS": "--remote-debugging-port=9331"},
                    profile=self.profile,
                )
            spawn.assert_not_called()

    def test_rust_guard_closes_only_synthetic_peer_preserving_main_close_veto(self):
        src = (Path(__file__).resolve().parents[1] /
               "frontend/src-tauri/src/lib.rs").read_text(encoding="utf-8")
        ack = src.split("fn acknowledge_n12_no_cdp_close_listener_ready(", 1)[1].split(
            "// QA-only deterministic exit", 1)[0]
        self.assertIn('window.label() != "main"', ack)
        self.assertIn("eligible_n12_no_cdp_listener_ack", ack)
        self.assertIn('get_webview_window("n12peer")', ack)
        self.assertIn("peer.close()", ack)
        self.assertLess(ack.index("eligible_n12_no_cdp_listener_ack"),
                        ack.index('get_webview_window("n12peer")'))
        self.assertLess(ack.index("peer.close()"),
                        ack.index('eprintln!("N12 QA native close listener registered")'))
        self.assertNotIn("window.destroy()", ack)
        veto = src.split(".on_window_event(|window, event|", 1)[1]
        self.assertIn('if window.label() != "main" { return; }', veto)
        self.assertIn("api.prevent_close()", veto)

    def test_cli_no_cdp_refuses_without_fresh_hosted_approval(self):
        with patch.object(lifetime.sys, "argv", [
            "n12_app_lifetime", "--source", SOURCE,
            "--expected-exe-sha256", SHA, "--no-cdp",
        ]), patch.dict(os.environ, {
            "PILOTODIN_N12_APP_LIFETIME_CONSENT": "",
            "PILOTODIN_N12_NO_CDP_STORAGE_CONSENT": "",
        }), patch.object(lifetime, "preflight") as preflight:
            self.assertEqual(lifetime.main(), 2)
            preflight.assert_not_called()

    def test_original_workflows_stay_disabled_and_browser_identity_is_os_based(self):
        root = Path(__file__).resolve().parents[1]
        for path in (".github/workflows/p4-n12-app-lifetime.yml",
                     ".github/workflows/p4-n12-webview-storage.yml"):
            workflow = (root / path).read_text(encoding="utf-8")
            self.assertIn("if: $" + "{{ false }}", workflow)
            self.assertNotIn("--no-cdp", workflow)
        src = (root / "qa/p4_research/n12_app_lifetime.py").read_text(encoding="utf-8")
        self.assertIn("no_cdp_path.run_one_no_cdp_app(", src)
        self.assertIn("browser_identity.verify_profile_shutdown(", src)
        self.assertIn("no_cdp_profile=no_cdp", src)
        launch = (root / "qa/p4_research/n12_no_cdp_native_path.py").read_text(encoding="utf-8")
        self.assertNotIn("9331", launch)
        self.assertNotIn("connectOverCDP", launch)
        self.assertNotIn("cdp_browser_pid", launch)


if __name__ == "__main__":
    unittest.main()
