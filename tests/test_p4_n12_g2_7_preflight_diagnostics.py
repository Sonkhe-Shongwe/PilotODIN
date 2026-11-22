"""Fail-closed generated Sysmon diagnostics: synthetic, no hosted runner."""
from contextlib import redirect_stdout
from io import StringIO
import json
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from qa.p4_research import n12_generated_sysmon_bookends as b
from qa.p4_research import n12_app_journey as journey
from qa.p4_native import n12_trace as trace

SHA = "a" * 40
ENV = {
    "GITHUB_ACTIONS": "true", "RUNNER_ENVIRONMENT": "github-hosted",
    "RUNNER_OS": "Windows", "GITHUB_EVENT_NAME": "push",
    "GITHUB_REF_NAME": "feature/live-dev-workspace-20261023",
    "GITHUB_RUN_ATTEMPT": "1", "GITHUB_RUN_ID": "99991",
    "RUNNER_TEMP": "synthetic-temp",
    "PILOTODIN_N12_GENERATED_BOOKENDS_SOURCE": SHA,
    "PILOTODIN_N12_GENERATED_BOOKENDS_CONSENT": b.CONSENT,
}
ROOT = Path("synthetic-fixture-root")


class G27PreflightDiagnostics(unittest.TestCase):
    def test_invalid_host_never_reads_git(self):
        with patch.object(b, "os", SimpleNamespace(name="posix")), patch.object(b.subprocess, "run") as git:
            with self.assertRaises(b.BookendBlocked) as caught:
                b.capture_approved(SHA, ENV)
            self.assertEqual(caught.exception.blocker, "HOST_SCOPE")
            git.assert_not_called()

    def test_bad_consent_is_source_approval_before_filesystem_access(self):
        with (patch.object(b, "os", SimpleNamespace(name="nt")),
              patch.object(b.subprocess, "run", return_value=SimpleNamespace(stdout=SHA + "\n")),
              patch.object(trace, "local_disposable_path") as path,
              patch.object(journey, "sysmon_tail") as channel):
            with self.assertRaises(b.BookendBlocked) as caught:
                b.capture_approved(SHA, {**ENV, "GITHUB_RUN_ATTEMPT": "2"})
            self.assertEqual(caught.exception.blocker, "SOURCE_APPROVAL")
            path.assert_not_called()
            channel.assert_not_called()

    def test_bad_git_identity_uses_redacted_source_label(self):
        with (patch.object(b, "os", SimpleNamespace(name="nt")),
              patch.object(b.subprocess, "run", side_effect=OSError("PRIVATE C:/owner/secret")),
              patch.object(trace, "local_disposable_path") as path):
            with self.assertRaises(b.BookendBlocked) as caught:
                b.capture_approved(SHA, ENV)
            self.assertEqual(caught.exception.blocker, "SOURCE_APPROVAL")
            self.assertNotIn("secret", str(caught.exception))
            path.assert_not_called()

    def test_invalid_runner_path_never_reads_sysmon(self):
        with (patch.object(b, "os", SimpleNamespace(name="nt")),
              patch.object(b.subprocess, "run", return_value=SimpleNamespace(stdout=SHA + "\n")),
              patch.object(trace, "local_disposable_path", side_effect=ValueError("PRIVATE C:/owner/secret")),
              patch.object(journey, "sysmon_tail") as channel):
            with self.assertRaises(b.BookendBlocked) as caught:
                b.capture_approved(SHA, ENV)
            self.assertEqual(caught.exception.blocker, "RUNNER_PATH")
            channel.assert_not_called()

    def test_failed_directory_creation_is_runner_path(self):
        with (patch.object(b, "os", SimpleNamespace(name="nt")),
              patch.object(b.subprocess, "run", return_value=SimpleNamespace(stdout=SHA + "\n")),
              patch.object(trace, "local_disposable_path", return_value=ROOT),
              patch.object(Path, "mkdir", side_effect=OSError("PRIVATE runner path")),
              patch.object(journey, "sysmon_tail") as channel):
            with self.assertRaises(b.BookendBlocked) as caught:
                b.capture_approved(SHA, ENV)
            self.assertEqual(caught.exception.blocker, "RUNNER_PATH")
            channel.assert_not_called()

    def test_sysmon_channel_failure_never_runs_fixture(self):
        with (patch.object(b, "os", SimpleNamespace(name="nt")),
              patch.object(b.subprocess, "run", return_value=SimpleNamespace(stdout=SHA + "\n")),
              patch.object(trace, "local_disposable_path", return_value=ROOT),
              patch.object(Path, "mkdir", return_value=None),
              patch.object(journey, "sysmon_tail", side_effect=OSError("PRIVATE Sysmon XML")),
              patch.object(b, "run_bookend_sequence") as fixtures):
            with self.assertRaises(b.BookendBlocked) as caught:
                b.capture_approved(SHA, ENV)
            self.assertEqual(caught.exception.blocker, "SYSMON_CHANNEL")
            self.assertNotIn("XML", str(caught.exception))
            fixtures.assert_not_called()

    def test_malformed_tail_blocks_without_fixture(self):
        for tail in (True, -1, None, "88"):
            with self.subTest(tail=tail), (
                patch.object(b, "os", SimpleNamespace(name="nt")),
                patch.object(b.subprocess, "run", return_value=SimpleNamespace(stdout=SHA + "\n")),
                patch.object(trace, "local_disposable_path", return_value=ROOT),
                patch.object(Path, "mkdir", return_value=None),
                patch.object(journey, "sysmon_tail", return_value=tail),
                patch.object(b, "run_bookend_sequence") as fixtures,
            ):
                with self.assertRaises(b.BookendBlocked) as caught:
                    b.capture_approved(SHA, ENV)
                self.assertEqual(caught.exception.blocker, "SYSMON_CHANNEL")
                fixtures.assert_not_called()

    def test_good_tail_passes_next_record_to_original_sequence(self):
        with (patch.object(b, "os", SimpleNamespace(name="nt")),
              patch.object(b.subprocess, "run", return_value=SimpleNamespace(stdout=SHA + "\n")),
              patch.object(trace, "local_disposable_path", return_value=ROOT),
              patch.object(Path, "mkdir", return_value=None),
              patch.object(journey, "sysmon_tail", return_value=123),
              patch.object(b, "run_bookend_sequence",
                           return_value=b.receipt("GENERATED_BOOKENDS_CORROBORATED")) as fixtures):
            result = b.capture_approved(SHA, ENV)
            self.assertEqual(result["blocker"], "NONE")
            self.assertEqual(fixtures.call_args.args[1]["sysmon_first_record"], 124)
            self.assertFalse(result["product_launched"])

    def test_untrusted_phase_and_label_never_appear_in_public_receipt(self):
        private = "C:/owner/private PID 12345"
        exc = b.BookendBlocked(private, private)
        result = b.receipt("BLOCKED", phase=exc.phase, blocker=exc.blocker)
        body = json.dumps(result)
        self.assertEqual((result["stage"], result["blocker"]), ("preflight", "UNSPECIFIED"))
        self.assertNotIn(private, body)
        with patch.object(b, "capture_approved",
                          side_effect=b.BookendBlocked("preflight", "SYSMON_CHANNEL")):
            out = StringIO()
            with redirect_stdout(out):
                self.assertEqual(b.main(["--capture", "--source", SHA], env=ENV), 2)
            report = json.loads(out.getvalue())
            self.assertEqual((report["stage"], report["blocker"]), ("preflight", "SYSMON_CHANNEL"))
            self.assertEqual(report["native_N12_acceptance"], "NOT_EVALUATED")
            self.assertNotIn(SHA, out.getvalue())


if __name__ == "__main__":
    unittest.main()
