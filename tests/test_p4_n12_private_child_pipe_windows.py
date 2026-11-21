"""Real Windows AF_PIPE transport tests with ONLY synthetic process witnesses.

No PilotODIN/Tauri/WebView app, Sysmon, ETW, firewall changes or native
admission. The sender is a tiny disposable Python subprocess.
"""
import os
import subprocess
import sys
import unittest
from uuid import uuid4

from qa.p4_native import n12_trace as trace
from qa.p4_research import n12_private_child_pipe as bridge
from tests.test_p4_n12_private_child_pipe import SOURCE, HASH, fixture


WORKER_OK = """
import os
from multiprocessing.connection import Client
from qa.p4_research import n12_private_child_pipe as pipe
from tests.test_p4_n12_private_child_pipe import fixture
with Client(os.environ[pipe.PIPE_ENV], family='AF_PIPE',
            authkey=bytes.fromhex(os.environ[pipe.KEY_ENV])) as conn:
    conn.send_bytes(pipe.encode(fixture()))
"""
WORKER_INVALID = """
import os
from multiprocessing.connection import Client
from qa.p4_research import n12_private_child_pipe as pipe
with Client(os.environ[pipe.PIPE_ENV], family='AF_PIPE',
            authkey=bytes.fromhex(os.environ[pipe.KEY_ENV])) as conn:
    conn.send_bytes(b'{"private_witness":"never_log"}')
"""
WORKER_WRONG_KEY = """
import os
from multiprocessing.connection import Client
from qa.p4_research import n12_private_child_pipe as pipe
with Client(os.environ[pipe.PIPE_ENV], family='AF_PIPE', authkey=b'x'*32) as conn:
    conn.send_bytes(b'forbidden')
"""


@unittest.skipUnless(os.name == "nt", "Actual AF_PIPE test requires Windows")
class WindowsSyntheticPrivateChildPipeTests(unittest.TestCase):
    def channel(self):
        return bridge.PrivateChildPipe(
            address=r"\\.\pipe\pilotodin-n12-child-" + uuid4().hex,
            family="AF_PIPE", key=b"z" * 32, source=SOURCE, expected_hash=HASH,
        )

    def spawn(self, code, env):
        return subprocess.Popen(
            [sys.executable, "-B", "-c", code],
            env=env, stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )

    def reap(self, proc):
        try:
            stdout, stderr = proc.communicate(timeout=8)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.communicate(timeout=8)
            self.fail("synthetic private-pipe sender failed to terminate")
        # No private output content, path or secret is surfaced to CI.
        return proc.returncode

    def test_real_windows_named_pipe_between_two_synthetic_python_processes(self):
        with self.channel() as pipe:
            worker = self.spawn(WORKER_OK, pipe.worker_environment(dict(os.environ)))
            try:
                witness = pipe.take()
                self.assertEqual(witness, fixture())
                self.assertEqual(witness.collector_receipt["native_N12_acceptance"],
                                 "NOT_EVALUATED")
            finally:
                code = self.reap(worker)
            self.assertEqual(code, 0, "synthetic Windows sender failed")
        self.assertFalse(pipe._thread.is_alive())

    def test_real_windows_named_pipe_rejects_malformed_payload(self):
        with self.channel() as pipe:
            worker = self.spawn(WORKER_INVALID, pipe.worker_environment(dict(os.environ)))
            try:
                with self.assertRaisesRegex(trace.EvidenceValidationError,
                                            "^no-cdp-private-child-pipe-unverified$"):
                    pipe.take()
            finally:
                code = self.reap(worker)
            self.assertEqual(code, 0)
        self.assertFalse(pipe._thread.is_alive())

    def test_real_windows_named_pipe_rejects_invalid_authentication(self):
        with self.channel() as pipe:
            worker = self.spawn(WORKER_WRONG_KEY, pipe.worker_environment(dict(os.environ)))
            try:
                with self.assertRaisesRegex(trace.EvidenceValidationError,
                                            "^no-cdp-private-child-pipe-unverified$"):
                    pipe.take()
            finally:
                code = self.reap(worker)
            self.assertNotEqual(code, 0)
        self.assertFalse(pipe._thread.is_alive())

    def test_crashed_sender_cannot_be_mistaken_for_completed_witness(self):
        with self.channel() as pipe:
            worker = self.spawn("raise SystemExit(9)", pipe.worker_environment(dict(os.environ)))
            try:
                self.assertEqual(self.reap(worker), 9)
                with self.assertRaisesRegex(trace.EvidenceValidationError,
                                            "^no-cdp-private-child-pipe-unverified$"):
                    pipe.take()  # bounded, never a synthetic receipt
            finally:
                if worker.poll() is None:
                    worker.kill()
                    worker.communicate(timeout=8)
        self.assertFalse(pipe._thread.is_alive())


if __name__ == "__main__":
    unittest.main()
