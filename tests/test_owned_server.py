"""Owned server admission and fixed shutdown protocol on generated fixtures."""
from pathlib import Path
import os
import subprocess
import sys
import tempfile
from threading import Thread
from types import SimpleNamespace
import unittest

from backend.desktop_runner import SHUTDOWN_REQUEST, _watch_desktop_pipe
from backend.server_entry import ROOT, admitted_home
from backend.workspace_boundary import WorkspaceBoundaryError, engine_workspace


class OwnedServerTests(unittest.TestCase):
    def test_dev_home_is_exact_and_explicit(self):
        env = {"PILOTODIN_SERVER_MODE": "dev",
               "PILOTODIN_HOME": str(ROOT / ".pilotodin-dev-data")}
        self.assertEqual(admitted_home(env), ROOT / ".pilotodin-dev-data")
        for changes in ({"PILOTODIN_HOME": str(ROOT / "data")},
                        {"PILOTODIN_SERVER_MODE": ""},
                        {"PILOTODIN_DESKTOP_SESSION": "secret"}):
            with self.assertRaises(WorkspaceBoundaryError):
                admitted_home({**env, **changes})

    def test_hosted_home_scope_and_competing_writer_before_import(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            home = root / "pilotodin-p1-real-http-123"
            env = {**os.environ, "PILOTODIN_SERVER_MODE": "hosted-fixture",
                   "PILOTODIN_HOME": str(home), "PILOTODIN_DESKTOP_SESSION": "",
                   "CI": "true", "GITHUB_ACTIONS": "true", "GITHUB_RUN_ID": "123",
                   "RUNNER_TEMP": str(root)}
            self.assertEqual(admitted_home(env), home)
            for invalid in ({"GITHUB_RUN_ID": "456"}, {"CI": "false"},
                            {"PILOTODIN_HOME": str(root / "other")}):
                with self.assertRaises(WorkspaceBoundaryError):
                    admitted_home({**env, **invalid})
            with engine_workspace(str(home)):
                code = ("from backend.server_entry import owned_app; "
                        "owned_app()")
                result = subprocess.run([sys.executable, "-B", "-c", code],
                    cwd=ROOT, env=env, capture_output=True, text=True, timeout=10)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("Workspace already in use", result.stderr)
                self.assertFalse((home / "pilotodin.sqlite3").exists())
                self.assertFalse((home / "datasets").exists())

    def test_owned_pipe_accepts_fragmented_stop_without_eof(self):
        server = SimpleNamespace(should_exit=False)
        rd, wr = os.pipe()
        thread = Thread(target=_watch_desktop_pipe, args=(server, rd), daemon=True)
        try:
            thread.start()
            os.write(wr, SHUTDOWN_REQUEST[:4])
            os.write(wr, SHUTDOWN_REQUEST[4:])
            thread.join(2)
            self.assertFalse(thread.is_alive())
            self.assertTrue(server.should_exit)
        finally:
            os.close(wr)
            thread.join(2)
            os.close(rd)

    def test_eof_or_invalid_pipe_is_fail_closed(self):
        for message in (b"", b"unexpected"):
            server = SimpleNamespace(should_exit=False)
            rd, wr = os.pipe()
            try:
                if message:
                    os.write(wr, message)
                os.close(wr)
                _watch_desktop_pipe(server, rd)
                self.assertTrue(server.should_exit)
            finally:
                os.close(rd)


if __name__ == "__main__":
    unittest.main()
