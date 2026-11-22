"""Adversarial generated Sysmon bookend contract, never host instrumentation."""
from datetime import datetime, timedelta, timezone
from collections import UserDict
import os
from types import SimpleNamespace
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch
import io
import json
from contextlib import redirect_stdout

from qa.p4_research import n12_generated_sysmon_bookends as bookends


SOURCE = "a" * 40
GOOD_ENV = {
    "GITHUB_ACTIONS": "true", "RUNNER_ENVIRONMENT": "github-hosted",
    "RUNNER_OS": "Windows", "GITHUB_EVENT_NAME": "push",
    "GITHUB_REF_NAME": "feature/live-dev-workspace-20261023",
    "GITHUB_RUN_ATTEMPT": "1", "GITHUB_RUN_ID": "99991",
    "RUNNER_TEMP": r"D:\runner\_temp",
    "PILOTODIN_N12_GENERATED_BOOKENDS_SOURCE": SOURCE,
    "PILOTODIN_N12_GENERATED_BOOKENDS_CONSENT": bookends.CONSENT,
}


class GeneratedBookendSourceTests(TestCase):
    def setUp(self):
        self.root = Path("synthetic-only")
        self.manifest = {"sysmon_first_record": 42, "processes": [], "loopback_ports": []}
        self.start = datetime(2026, 11, 22, 16, 4, 4, 757471, tzinfo=timezone.utc)
        self.events = []

    def run_sequence(self, *, broken=None):
        moments = [self.start, self.start + timedelta(seconds=4),
                   self.start + timedelta(seconds=5), self.start + timedelta(seconds=9)]

        def clock():
            self.events.append("clock")
            return moments.pop(0)

        def pause(seconds):
            self.events.append(("pause", seconds))

        def generate(path, manifest, *, child_hold_seconds):
            self.events.append(("generate", path.name, child_hold_seconds))
            self.assertIs(manifest, self.manifest)
            if broken == "generate-final" and path.name == "generated-final":
                raise ValueError(r"C:\private\sensitive-name")
            return {"role": "calibration", "fixture": True}

        def verify(root, first, start, end, record, *, phase):
            self.events.append(("verify", phase, first, start, end))
            self.assertEqual(root, self.root)
            self.assertEqual(first, 42)
            self.assertEqual(record, {"role": "calibration", "fixture": True})
            if phase == broken:
                raise ValueError("parent-birth-before-window")

        return bookends.run_bookend_sequence(
            self.root, self.manifest, clock=clock, pause=pause,
            generate=generate, verify=verify)

    def test_two_generated_fixtures_have_window_first_and_strict_checks(self):
        result = self.run_sequence()
        self.assertEqual(result["status"], "GENERATED_BOOKENDS_CORROBORATED")
        self.assertFalse(result["product_launched"])
        self.assertEqual(result["native_N12_acceptance"], "NOT_EVALUATED")
        self.assertEqual([entry[1] for entry in self.events if isinstance(entry, tuple)
                          and entry[0] == "generate"], ["generated-initial", "generated-final"])
        self.assertEqual([entry[0] if isinstance(entry, tuple) else entry for entry in self.events],
                         ["clock", "pause", "generate", "clock", "verify"] * 2)
        self.assertEqual([event[1] for event in self.events if isinstance(event, tuple)
                          and event[0] == "pause"], [0.05, 0.05])

    def test_initial_failure_blocks_second_fixture_without_retry(self):
        with self.assertRaises(bookends.BookendBlocked) as cm:
            self.run_sequence(broken="initial")
        self.assertEqual(cm.exception.phase, "initial")
        self.assertNotIn("generated-final", str(self.events))
        self.assertEqual(sum(e[0] == "generate" for e in self.events if isinstance(e, tuple)), 1)

    def test_final_birth_boundary_failure_stays_blocked(self):
        with self.assertRaises(bookends.BookendBlocked) as cm:
            self.run_sequence(broken="final")
        self.assertEqual(cm.exception.phase, "final")
        self.assertEqual(sum(e[0] == "generate" for e in self.events if isinstance(e, tuple)), 2)

    def test_failed_fixture_does_not_run_verifier_or_leak_private_path(self):
        with self.assertRaises(bookends.BookendBlocked) as cm:
            self.run_sequence(broken="generate-final")
        self.assertEqual(cm.exception.phase, "final")
        self.assertNotIn("private", str(cm.exception))
        self.assertEqual(sum(e[0] == "verify" for e in self.events if isinstance(e, tuple)), 1)

    def test_invalid_manifest_is_rejected_before_callbacks(self):
        for manifest in (None, [], {}, {"sysmon_first_record": True,
                                        "processes": [], "loopback_ports": []},
                         {"sysmon_first_record": 0,
                          "processes": [], "loopback_ports": []}):
            with self.subTest(manifest=manifest):
                with self.assertRaises(bookends.BookendBlocked) as cm:
                    bookends.run_bookend_sequence(self.root, manifest,
                        clock=lambda: 1, pause=lambda s: None,
                        generate=lambda *a, **kw: None, verify=lambda *a, **kw: None)
                self.assertEqual(cm.exception.phase, "preflight")

    def test_untrusted_consent_and_source_reject_without_host_access(self):
        for name, value in (
            ("GITHUB_ACTIONS", "false"), ("RUNNER_OS", "Linux"),
            ("RUNNER_ENVIRONMENT", "self-hosted"),
            ("GITHUB_EVENT_NAME", "workflow_dispatch"),
            ("GITHUB_RUN_ATTEMPT", "2"),
            ("PILOTODIN_N12_GENERATED_BOOKENDS_SOURCE", "b" * 40),
            ("PILOTODIN_N12_GENERATED_BOOKENDS_CONSENT", "none"),
            ("RUNNER_TEMP", ""), ("GITHUB_RUN_ID", "not-a-run"),
        ):
            with self.subTest(name=name):
                env = {**GOOD_ENV, name: value}
                with self.assertRaises(bookends.BookendBlocked):
                    bookends.require_hosted_approval(SOURCE, env, SOURCE)
        with self.assertRaises(bookends.BookendBlocked):
            bookends.require_hosted_approval(SOURCE, GOOD_ENV, "b" * 40)
        with self.assertRaises(bookends.BookendBlocked):
            bookends.require_hosted_approval(True, GOOD_ENV, SOURCE)

    def test_cli_requires_explicit_capture_and_never_emits_private_data(self):
        for argv in ([], ["--source", SOURCE]):
            out = io.StringIO()
            with redirect_stdout(out):
                self.assertEqual(bookends.main(argv, env={}), 2)
            report = json.loads(out.getvalue())
            self.assertEqual(report["status"], "BLOCKED")
            self.assertEqual(report["stage"], "preflight")
            self.assertNotIn("private", out.getvalue())
        with patch.object(bookends, "capture_approved", side_effect=bookends.BookendBlocked("final")):
            out = io.StringIO()
            with redirect_stdout(out):
                self.assertEqual(bookends.main(["--capture", "--source", SOURCE], env=GOOD_ENV), 2)
            self.assertEqual(json.loads(out.getvalue())["stage"], "final")

    def test_non_windows_host_rejects_before_git_or_fixture(self):
        with patch.object(bookends.subprocess, "run") as process:
            with self.assertRaises(bookends.BookendBlocked):
                bookends.capture_approved(SOURCE, GOOD_ENV)
            process.assert_not_called()

    def test_malformed_run_id_or_invalid_clock_fail_closed(self):
        with self.assertRaises(bookends.BookendBlocked):
            bookends.require_hosted_approval(SOURCE, {**GOOD_ENV, "GITHUB_RUN_ID": 123}, SOURCE)
        with self.assertRaises(bookends.BookendBlocked) as cm:
            bookends.run_bookend_sequence(
                self.root, self.manifest, clock=lambda: 123,
                pause=lambda seconds: None, generate=lambda *a, **k: {},
                verify=lambda *a, **k: None)
        self.assertEqual(cm.exception.phase, "initial")

    def test_live_cli_environment_mapping_is_accepted_without_collection(self):
        # os.environ is os._Environ, NOT a built-in dict. This is the exact
        # argument that main() sends to capture_approved on hosted Windows.
        self.assertIsNot(type(os.environ), dict)
        with patch.dict(os.environ, GOOD_ENV, clear=True):
            bookends.require_hosted_approval(SOURCE, os.environ, SOURCE)
            bookends.require_hosted_approval(SOURCE, UserDict(GOOD_ENV), SOURCE)
            observed = []

            def capture(source, env):
                observed.append((source, env is os.environ))
                bookends.require_hosted_approval(source, env, SOURCE)
                return bookends.receipt("GENERATED_BOOKENDS_CORROBORATED")

            with patch.object(bookends, "capture_approved", side_effect=capture):
                output = io.StringIO()
                with redirect_stdout(output):
                    self.assertEqual(bookends.main(["--capture", "--source", SOURCE]), 0)
            self.assertEqual(observed, [(SOURCE, True)])
            self.assertEqual(json.loads(output.getvalue())["product_launched"], False)

    def test_windows_entry_reaches_hosted_guard_with_real_environ_mapping(self):
        # This remains entirely synthetic and stops at the guard. It would
        # have failed on the former type(env) is not dict source gate.
        with (
            patch.object(bookends.os, "name", "nt"),
            patch.object(bookends.subprocess, "run",
                         return_value=SimpleNamespace(stdout=SOURCE + "\n")) as git,
            patch.object(bookends, "require_hosted_approval",
                         side_effect=bookends.BookendBlocked("preflight")) as guard,
        ):
            with self.assertRaises(bookends.BookendBlocked):
                bookends.capture_approved(SOURCE, os.environ)
        git.assert_called_once()
        guard.assert_called_once()
        self.assertIs(guard.call_args.args[1], os.environ)
        self.assertEqual(guard.call_args.args[2], SOURCE)

    def test_mapping_does_not_bypass_invalid_source_consent_or_nonmapping(self):
        bookends.require_hosted_approval(SOURCE, UserDict(GOOD_ENV), SOURCE)
        for bad in (None, [], "", 17, [("GITHUB_ACTIONS", "true")]):
            with self.subTest(value=repr(bad)):
                with self.assertRaises(bookends.BookendBlocked):
                    bookends.require_hosted_approval(SOURCE, bad, SOURCE)
        with self.assertRaises(bookends.BookendBlocked):
            bookends.require_hosted_approval(
                SOURCE, UserDict({**GOOD_ENV, "GITHUB_RUN_ATTEMPT": "2"}), SOURCE)
        with self.assertRaises(bookends.BookendBlocked):
            bookends.require_hosted_approval(SOURCE, UserDict(GOOD_ENV), "b" * 40)

    def test_cli_success_remains_calibration_only(self):
        with patch.object(bookends, "capture_approved", return_value=bookends.receipt("GENERATED_BOOKENDS_CORROBORATED")):
            out = io.StringIO()
            with redirect_stdout(out):
                self.assertEqual(bookends.main(["--capture", "--source", SOURCE], env=GOOD_ENV), 0)
            report = json.loads(out.getvalue())
            self.assertFalse(report["product_launched"])
            self.assertEqual(report["file_mutation_acceptance"], "NOT_EVALUATED")


if __name__ == "__main__":
    import unittest
    unittest.main()
