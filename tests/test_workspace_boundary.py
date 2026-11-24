"""Disposable Python-only workspace ownership regressions; no native app."""
from contextlib import contextmanager
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from backend.workspace_boundary import (
    LOCK_NAME, WorkspaceBoundaryError, engine_workspace,
)


class WorkspaceBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="pilotodin-lease-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.home = self.root / "data"
        self.root_source = Path(__file__).resolve().parents[1]

    def test_missing_final_directory_and_reuse_empty_marker(self):
        with engine_workspace(str(self.home)) as owned:
            self.assertEqual(owned, self.home)
            self.assertEqual((owned / LOCK_NAME).stat().st_size, 0)
        with engine_workspace(str(self.home)):
            self.assertTrue((self.home / LOCK_NAME).is_file())

    def test_second_process_refused_before_database_import(self):
        env = {**os.environ, "PILOTODIN_HOME": str(self.home),
               "PILOTODIN_DESKTOP_SESSION": "s" * 64,
               "PILOTODIN_DESKTOP_PORT": "12345"}
        env.pop("PILOTODIN_DESKTOP_WATCH_STDIN", None)
        with engine_workspace(str(self.home)):
            child = subprocess.run(
                [sys.executable, "-B", "-m", "backend.desktop_runner"],
                cwd=self.root_source, env=env, capture_output=True, text=True,
                timeout=10, check=False,
            )
            self.assertEqual(child.returncode, 2, child.stderr)
            self.assertIn("Workspace already in use or locking unavailable", child.stderr)
            self.assertFalse((self.home / "pilotodin.sqlite3").exists())
            self.assertFalse((self.home / "datasets").exists())
        with engine_workspace(str(self.home)):
            pass

    def test_independent_workspaces_can_run(self):
        with engine_workspace(str(self.home)):
            with engine_workspace(str(self.root / "other")):
                pass

    def test_abrupt_process_exit_releases_lock(self):
        code = ("import os,sys; from backend.workspace_boundary import engine_workspace\n"
                "with engine_workspace(sys.argv[1]):\n"
                "    os._exit(0)\n")
        result = subprocess.run([sys.executable, "-B", "-c", code, str(self.home)],
                                cwd=self.root_source, timeout=10, check=False)
        self.assertEqual(result.returncode, 0)
        with engine_workspace(str(self.home)):
            pass

    def test_exception_releases_original_descriptor(self):
        with self.assertRaisesRegex(ValueError, "test exception"):
            with engine_workspace(str(self.home)):
                raise ValueError("test exception")
        with engine_workspace(str(self.home)):
            pass

    def test_relative_and_missing_ancestor_refused(self):
        for value in ("relative-workspace", str(self.home / "child")):
            with self.assertRaises(WorkspaceBoundaryError):
                with engine_workspace(value):
                    self.fail("invalid root admitted")
        self.assertFalse(self.home.exists())

    def test_nonempty_lock_not_overwritten(self):
        self.home.mkdir()
        marker = self.home / LOCK_NAME
        marker.write_bytes(b"unknown existing file")
        with self.assertRaises(WorkspaceBoundaryError):
            with engine_workspace(str(self.home)):
                self.fail("nonempty lock admitted")
        self.assertEqual(marker.read_bytes(), b"unknown existing file")

    def test_hardlinked_lock_refused_without_touching_target(self):
        self.home.mkdir()
        target = self.root / "unrelated"
        target.touch()
        try:
            os.link(target, self.home / LOCK_NAME)
        except OSError as exc:
            self.skipTest(f"Hard links unsupported in fixture: {exc}")
        with self.assertRaises(WorkspaceBoundaryError):
            with engine_workspace(str(self.home)):
                self.fail("hardlinked lock admitted")
        self.assertEqual(target.stat().st_size, 0)
        self.assertTrue((self.home / LOCK_NAME).exists())

    def test_wrong_type_dataset_directory_refused(self):
        self.home.mkdir()
        (self.home / "datasets").write_bytes(b"do not replace")
        with self.assertRaises(WorkspaceBoundaryError):
            with engine_workspace(str(self.home)):
                self.fail("invalid directory admitted")
        self.assertEqual((self.home / "datasets").read_bytes(), b"do not replace")
        self.assertFalse((self.home / LOCK_NAME).exists())

    def _owned_database_case(self, operation):
        code = r"""
import os, sys
from pathlib import Path
from unittest.mock import patch
from backend.workspace_boundary import hold_process_workspace, WorkspaceBoundaryError
home = hold_process_workspace(sys.argv[1])
os.environ["PILOTODIN_HOME"] = str(home)
from backend import storage
with storage.connect() as conn:
    assert conn.execute("SELECT 1").fetchone()[0] == 1
db = home / "pilotodin.sqlite3"
operation = sys.argv[2]
if operation == "replace":
    saved = home / "saved-original.sqlite"
    db.rename(saved)
    db.write_bytes(b"replacement, not a database")
    protected = saved.read_bytes()
elif operation == "missing":
    saved = home / "saved-original.sqlite"
    db.rename(saved)
    protected = saved.read_bytes()
elif operation == "hardlink":
    saved = home / "other-file"
    saved.write_bytes(b"do not open")
    protected = saved.read_bytes()
    try:
        os.link(saved, home / "pilotodin.sqlite3-wal")
    except OSError:
        sys.exit(77)
elif operation == "different-path":
    storage.DB_PATH = home / "other.sqlite"
    saved = db
    protected = saved.read_bytes()
else:
    raise AssertionError("unknown case")
with patch.object(storage.sqlite3, "connect", side_effect=AssertionError("SQLite opened unsafe path")):
    try:
        storage.connect()
    except WorkspaceBoundaryError:
        pass
    else:
        raise AssertionError("unsafe database path admitted")
assert saved.read_bytes() == protected
if operation == "replace":
    assert db.read_bytes() == b"replacement, not a database"
elif operation == "missing":
    assert not db.exists()
elif operation == "different-path":
    assert not storage.DB_PATH.exists()
"""
        result = subprocess.run(
            [sys.executable, "-B", "-c", code, str(self.home), operation],
            cwd=self.root_source, capture_output=True, text=True,
            timeout=15, check=False,
        )
        if result.returncode == 77 and operation == "hardlink":
            self.skipTest("Hard links unsupported in fixture")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_owned_database_rejects_replacement_before_sqlite_open(self):
        self._owned_database_case("replace")

    def test_owned_database_rejects_disappearance_before_sqlite_open(self):
        self._owned_database_case("missing")

    def test_owned_database_rejects_hardlinked_sidecar_before_sqlite_open(self):
        self._owned_database_case("hardlink")

    def test_owned_database_rejects_different_path_before_sqlite_open(self):
        self._owned_database_case("different-path")

    def test_static_redirected_ancestor_refused(self):
        outside = self.root / "outside"
        outside.mkdir()
        redirect = self.root / "redirect"
        try:
            redirect.symlink_to(outside, target_is_directory=True)
        except OSError as exc:
            self.skipTest(f"Symlink unsupported in fixture: {exc}")
        with self.assertRaises(WorkspaceBoundaryError):
            with engine_workspace(str(redirect / "data")):
                self.fail("redirect admitted")
        self.assertEqual(list(outside.iterdir()), [])


if __name__ == "__main__":
    unittest.main()
