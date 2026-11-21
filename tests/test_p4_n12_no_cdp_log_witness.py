"""Disposable local log fixtures, no WebView, native app or ACL changes."""
from dataclasses import replace
from contextlib import ExitStack
from unittest.mock import patch
from pathlib import Path
import tempfile
import unittest

from qa.p4_native.n12_trace import EvidenceValidationError
from qa.p4_research import n12_no_cdp_log_witness as reader
from qa.p4_research import n12_app_journey as journey


SOURCE = "a" * 40
EXE = "b" * 64


class FakeProcess:
    pid = 8123
    returncode = None

    def poll(self):
        return self.returncode


def prelaunch(path):
    return reader.prepare_prelaunch_log(
        path,
        expected_source=SOURCE, actual_source=SOURCE,
        expected_executable_sha256=EXE, actual_executable_sha256=EXE,
    )


class NoCdpLogWitnessTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.file = Path(self.folder.name) / "app.log"
        self.file.write_bytes(b"")
        self.app = FakeProcess()

    def observe(self, witness=None, *, sleep=lambda _: None, clock=None, **kwargs):
        # Use fake ticking clock to avoid tests relying on wall clock.
        if clock is None:
            ticks = iter([0.0, 1.0, 2.0, 3.0, 4.0])
            clock = lambda: next(ticks)
        return reader.wait_for_readiness(
            witness or prelaunch(self.file), self.app,
            expected_pid=8123, main_window_identity_verified=True,
            clock=clock, sleep=sleep, timeout_seconds=2, **kwargs,
        )

    def test_clean_marker_and_normal_close_are_only_log_witness_not_native_acceptance(self):
        witness = prelaunch(self.file)
        self.file.write_bytes(b"unrelated private path\n" + reader.MARKER + b"\n")
        ready = self.observe(witness)
        self.app.returncode = 0
        result = reader.verify_after_normal_close(
            witness, ready, process=self.app, expected_pid=8123,
            close_request_verified=True,
        )
        self.assertEqual(result["marker"], "observed-once-before-close")
        self.assertEqual(result["browser_process_identity"], "NOT_EVALUATED")
        self.assertEqual(result["native_N12_acceptance"], "NOT_EVALUATED")
        self.assertFalse(result["owner_native_execution_authorized"])
        self.assertNotIn("private", str(result))
        self.assertNotIn(self.folder.name, str(result))

    def test_marker_absent_times_out_with_fixed_redacted_reason(self):
        witness = prelaunch(self.file)
        self.file.write_bytes(b"private: " + reader.MARKER + b" suffix\n")
        with self.assertRaisesRegex(EvidenceValidationError, "^no-cdp-readiness-timeout$"):
            self.observe(witness)

    def test_stale_prelaunch_and_wrong_provenance_are_rejected(self):
        self.file.write_bytes(reader.MARKER + b"\n")
        with self.assertRaisesRegex(EvidenceValidationError, "^no-cdp-prelaunch-log-not-empty-or-unique$"):
            prelaunch(self.file)
        self.file.write_bytes(b"")
        with self.assertRaisesRegex(EvidenceValidationError, "^no-cdp-source-unverified$"):
            reader.prepare_prelaunch_log(
                self.file, expected_source=SOURCE, actual_source="c" * 40,
                expected_executable_sha256=EXE, actual_executable_sha256=EXE,
            )
        with self.assertRaisesRegex(EvidenceValidationError, "^no-cdp-executable-unverified$"):
            reader.prepare_prelaunch_log(
                self.file, expected_source=SOURCE, actual_source=SOURCE,
                expected_executable_sha256=EXE, actual_executable_sha256="c" * 64,
            )

    def test_duplicate_preclose_blocks_without_exposing_raw_log(self):
        witness = prelaunch(self.file)
        self.file.write_bytes(reader.MARKER + b"\nsecret\n" + reader.MARKER + b"\n")
        with self.assertRaisesRegex(EvidenceValidationError, "^no-cdp-marker-duplicate$"):
            self.observe(witness)

    def test_duplicate_postclose_blocks_even_with_zero_exit(self):
        witness = prelaunch(self.file)
        self.file.write_bytes(reader.MARKER + b"\n")
        observed = self.observe(witness)
        self.file.write_bytes(reader.MARKER + b"\n" + reader.MARKER + b"\n")
        self.app.returncode = 0
        with self.assertRaisesRegex(EvidenceValidationError, "^no-cdp-postclose-marker-missing-or-duplicate$"):
            reader.verify_after_normal_close(
                witness, observed, process=self.app,
                expected_pid=8123, close_request_verified=True,
            )

    def test_provisional_does_not_bypass_close_or_nonzero_exit(self):
        witness = prelaunch(self.file)
        self.file.write_bytes(reader.MARKER + b"\n")
        observed = self.observe(witness)
        self.app.returncode = 1
        for value in (False, True):
            with self.subTest(close_verified=value):
                with self.assertRaisesRegex(EvidenceValidationError, "^no-cdp-graceful-close-unverified$"):
                    reader.verify_after_normal_close(
                        witness, observed, process=self.app,
                        expected_pid=8123, close_request_verified=value,
                    )

    def test_pid_window_and_process_liveness_must_be_verified(self):
        witness = prelaunch(self.file)
        self.file.write_bytes(reader.MARKER + b"\n")
        with self.assertRaisesRegex(EvidenceValidationError, "^no-cdp-app-process-identity-unverified$"):
            reader.wait_for_readiness(witness, self.app, expected_pid=8124,
                                      main_window_identity_verified=True)
        with self.assertRaisesRegex(EvidenceValidationError, "^no-cdp-window-identity-unverified$"):
            reader.wait_for_readiness(witness, self.app, expected_pid=8123,
                                      main_window_identity_verified=False)
        self.app.returncode = 0
        with self.assertRaisesRegex(EvidenceValidationError, "^no-cdp-app-exited-before-readiness$"):
            self.observe(witness)

    def test_replaced_log_and_symlink_block(self):
        witness = prelaunch(self.file)
        self.assertFalse(witness.handle.closed)
        try:
            self.file.unlink()
        except PermissionError:
            # On Windows an open read handle may prevent replacement.
            # Exercise identity rejection with a synthetic changed identity.
            with self.assertRaisesRegex(EvidenceValidationError, "^no-cdp-log-identity-changed$"):
                self.observe(replace(witness, inode=witness.inode + 1))
        else:
            self.file.write_bytes(reader.MARKER + b"\n")
            with self.assertRaisesRegex(EvidenceValidationError, "^no-cdp-log-identity-changed$"):
                self.observe(witness)
        finally:
            witness.close()
        self.assertTrue(witness.handle.closed)
        if self.file.exists():
            self.file.unlink()
        target = Path(self.folder.name) / "private.log"
        target.write_bytes(reader.MARKER + b"\n")
        try:
            self.file.symlink_to(target)
        except (OSError, NotImplementedError):
            self.skipTest("host does not permit symlinks")
        with self.assertRaisesRegex(EvidenceValidationError, "^no-cdp-log-path-unverified$"):
            prelaunch(self.file)

    def test_missing_and_oversize_logs_block(self):
        witness = prelaunch(self.file)
        missing = Path(self.folder.name) / "missing" / "app.log"
        with self.assertRaisesRegex(EvidenceValidationError, "^no-cdp-log-unavailable$"):
            self.observe(replace(witness, path=missing))
        self.file.write_bytes(b"q" * (reader.MAX_LOG_BYTES + 1))
        with self.assertRaisesRegex(EvidenceValidationError, "^no-cdp-log-size-limit$"):
            self.observe(witness)
        witness.close()

    def test_prelaunch_handle_remains_live_until_explicit_disposal(self):
        with prelaunch(self.file) as witness:
            self.assertFalse(witness.handle.closed)
            self.file.write_bytes(reader.MARKER + b"\n")
            self.assertEqual(self.observe(witness).marker_lines_before_close, 1)
        self.assertTrue(witness.handle.closed)
        with self.assertRaisesRegex(EvidenceValidationError, "^no-cdp-log-identity-changed$"):
            self.observe(witness)

    def test_fragmented_log_ack_is_not_accepted_until_newline(self):
        witness = prelaunch(self.file)
        self.file.write_bytes(reader.MARKER)
        def append_newline(_seconds):
            self.file.write_bytes(reader.MARKER + b"\n")
        ready = self.observe(witness, sleep=append_newline)
        self.assertEqual(ready.marker_lines_before_close, 1)


    def test_spawn_prelaunch_witness_is_pinned_before_popen_and_survives_close(self):
        # No real process is launched, and the old CDP/default path is not changed.
        log = Path(self.folder.name) / "prelaunch" / "app.log"
        log.parent.mkdir()
        manifest = {"processes": []}
        captured = []
        process = FakeProcess()
        with ExitStack() as stack:
            def before_spawn(path):
                self.assertEqual(path, log)
                self.assertFalse(captured)
                pinned = prelaunch(path)
                captured.append(pinned)
                stack.callback(pinned.close)
                return pinned

            def fake_popen(*args, **kwargs):
                self.assertEqual(len(captured), 1)
                self.assertFalse(captured[0].handle.closed)
                self.assertEqual(log.read_bytes(), b"")
                self.assertEqual(kwargs["stdout"].name, str(log))
                return process

            with patch.object(journey.subprocess, "Popen", side_effect=fake_popen) as launch:
                result = journey.spawn(
                    stack, manifest, "app", ["qa-fake.exe"], {}, log.parent, log,
                    prelaunch_log_hook=before_spawn,
                )
            self.assertIs(result, process)
            launch.assert_called_once()
            self.assertEqual(manifest["processes"][0]["pid"], process.pid)
            with log.open("ab") as handle:
                handle.write(reader.MARKER + b"\n")
            provisional = reader.wait_for_readiness(
                captured[0], process, expected_pid=process.pid,
                main_window_identity_verified=True,
            )
            process.returncode = 0
            evidence = reader.verify_after_normal_close(
                captured[0], provisional, process=process, expected_pid=process.pid,
                close_request_verified=True,
            )
            self.assertEqual(evidence["native_N12_acceptance"], "NOT_EVALUATED")
        self.assertTrue(captured[0].handle.closed)

    def test_spawn_prelaunch_rejection_is_before_process_start(self):
        log = Path(self.folder.name) / "prelaunch" / "app.log"
        log.parent.mkdir()
        manifest = {"processes": []}
        with ExitStack() as stack, patch.object(journey.subprocess, "Popen") as launch:
            def reject(_path):
                raise EvidenceValidationError("no-cdp-prelaunch-blocked")
            with self.assertRaisesRegex(EvidenceValidationError, "^no-cdp-prelaunch-blocked$"):
                journey.spawn(stack, manifest, "app", ["fake.exe"], {}, log.parent, log,
                              prelaunch_log_hook=reject)
            launch.assert_not_called()
        self.assertEqual(manifest, {"processes": []})
        self.assertEqual(log.read_bytes(), b"")

    def test_spawn_prelaunch_refuses_non_app_closed_or_missing_witness(self):
        for mode in ("backend", "closed", "missing"):
            with self.subTest(mode=mode), ExitStack() as stack:
                log = Path(self.folder.name) / (mode + ".dir") / "app.log"
                log.parent.mkdir()
                held = []
                def hook(path):
                    if mode == "missing":
                        return None
                    witness = prelaunch(path)
                    held.append(witness)
                    stack.callback(witness.close)
                    if mode == "closed":
                        witness.close()
                    return witness
                manifest = {"processes": []}
                with patch.object(journey.subprocess, "Popen") as launch:
                    with self.assertRaisesRegex(
                        EvidenceValidationError,
                        "^no-cdp-prelaunch-hook-invalid$" if mode == "backend"
                        else "^no-cdp-prelaunch-witness-unverified$",
                    ):
                        journey.spawn(stack, manifest, mode if mode == "backend" else "app",
                                      ["fake.exe"], {}, log.parent, log,
                                      prelaunch_log_hook=hook)
                    launch.assert_not_called()
                self.assertEqual(manifest["processes"], [])

    def test_unmodified_spawn_still_supports_existing_callers(self):
        log = Path(self.folder.name) / "default" / "app.log"
        log.parent.mkdir()
        process = FakeProcess()
        process.returncode = 0
        with ExitStack() as stack, patch.object(journey.subprocess, "Popen",
                                                return_value=process) as launch:
            journey.spawn(stack, {"processes": []}, "app", ["legacy-fake.exe"],
                          {}, log.parent, log)
            launch.assert_called_once()
            self.assertEqual(log.read_bytes(), b"")

    def test_missing_close_proof_never_yields_verified_receipt(self):
        witness = prelaunch(self.file)
        self.file.write_bytes(reader.MARKER + b"\n")
        observed = self.observe(witness)
        with self.assertRaisesRegex(EvidenceValidationError, "^no-cdp-graceful-close-unverified$"):
            reader.verify_after_normal_close(
                witness, observed, process=self.app,
                expected_pid=8123, close_request_verified=False,
            )


if __name__ == "__main__":
    unittest.main()
