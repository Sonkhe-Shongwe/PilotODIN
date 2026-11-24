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

    def test_owned_storage_uses_single_admitted_spelling(self):
        code = r"""
import os, sys
from pathlib import Path
from unittest.mock import patch
from backend.workspace_boundary import hold_process_workspace, storage_home, WorkspaceBoundaryError
supplied = Path(sys.argv[1])
owned = hold_process_workspace(str(supplied))
assert owned == supplied.resolve(strict=True)
os.environ["PILOTODIN_HOME"] = str(owned)
original_resolve = Path.resolve
def guarded_resolve(path, *args, **kwargs):
    if path == owned:
        raise AssertionError("Storage independently resolved the admitted home")
    return original_resolve(path, *args, **kwargs)
with patch.object(Path, "resolve", guarded_resolve):
    from backend import storage
    assert storage.HOME == owned
    with storage.connect() as conn:
        assert conn.execute("SELECT 1").fetchone()[0] == 1
try:
    storage_home(str(owned / "unadmitted"))
except WorkspaceBoundaryError:
    pass
else:
    raise AssertionError("Unadmitted storage home accepted")
"""
        # Match the existing engine smoke: use the original temporary
        # directory spelling, not the already resolved fixture root.
        home = Path(self.temp.name) / "raw-storage-home"
        result = subprocess.run(
            [sys.executable, "-B", "-c", code, str(home)],
            cwd=self.root_source, capture_output=True, text=True,
            timeout=15, check=False,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_canonicalization_refuses_different_physical_directory(self):
        code = r"""
import sys
from pathlib import Path
from unittest.mock import patch
from backend.workspace_boundary import hold_process_workspace, engine_workspace, WorkspaceBoundaryError
home, other = map(Path, sys.argv[1:])
with patch.object(Path, "resolve", return_value=other):
    try:
        hold_process_workspace(str(home))
    except WorkspaceBoundaryError:
        pass
    else:
        raise AssertionError("Different physical root admitted")
assert list(other.iterdir()) == []
with engine_workspace(str(home)):
    pass
"""
        other = self.root / "unrelated-root"
        other.mkdir()
        result = subprocess.run(
            [sys.executable, "-B", "-c", code, str(self.home), str(other)],
            cwd=self.root_source, capture_output=True, text=True,
            timeout=15, check=False,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_fresh_fixture_never_creates_missing_or_admits_dirty_home(self):
        from backend.workspace_boundary import existing_fixture_home, hold_fresh_fixture_workspace
        with self.assertRaises(WorkspaceBoundaryError):
            existing_fixture_home(str(self.home))
        self.assertFalse(self.home.exists())
        self.home.mkdir()
        marker = self.home / "original.txt"
        marker.write_bytes(b"preserve")
        with self.assertRaises(WorkspaceBoundaryError):
            hold_fresh_fixture_workspace(str(self.home), self.home)
        self.assertEqual(marker.read_bytes(), b"preserve")
        self.assertFalse((self.home / LOCK_NAME).exists())

    def test_fresh_fixture_refuses_competing_writer_before_storage_import(self):
        code = r"""
import sys
from pathlib import Path
from backend.workspace_boundary import hold_fresh_fixture_workspace, WorkspaceBoundaryError
try:
    hold_fresh_fixture_workspace(sys.argv[1], Path(sys.argv[1]))
except WorkspaceBoundaryError:
    assert "backend.storage" not in sys.modules
else:
    raise AssertionError("Competing fixture writer admitted")
"""
        with engine_workspace(str(self.home)):
            result = subprocess.run(
                [sys.executable, "-B", "-c", code, str(self.home)],
                cwd=self.root_source, capture_output=True, text=True,
                timeout=15, check=False,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual({p.name for p in self.home.iterdir()}, {LOCK_NAME})

    def test_direct_storage_import_refuses_implicit_empty_and_relative_home(self):
        code = r"""
import os, sys
from backend.workspace_boundary import WorkspaceBoundaryError
try:
    from backend import storage
except WorkspaceBoundaryError as exc:
    assert str(exc) == "Explicit local workspace required"
else:
    raise AssertionError("Implicit or relative storage home admitted")
"""
        for value in (None, "", "unadmitted-relative"):
            with self.subTest(value=value):
                env = os.environ.copy()
                env.pop("PILOTODIN_HOME", None)
                if value is not None:
                    env["PILOTODIN_HOME"] = value
                result = subprocess.run(
                    [sys.executable, "-B", "-c", code], cwd=self.root,
                    env={**env, "PYTHONPATH": str(self.root_source)},
                    capture_output=True, text=True, timeout=15, check=False,
                )
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertEqual(list(self.root.iterdir()), [])

    def test_direct_storage_refuses_redirected_home_before_creation(self):
        from backend.workspace_boundary import storage_home
        outside = self.root / "outside"
        outside.mkdir()
        redirect = self.root / "redirect"
        try:
            redirect.symlink_to(outside, target_is_directory=True)
        except OSError as exc:
            self.skipTest(f"Symlink unsupported in fixture: {exc}")
        with self.assertRaises(WorkspaceBoundaryError):
            storage_home(str(redirect / "data"))
        self.assertEqual(list(outside.iterdir()), [])

    def test_legacy_launcher_has_no_implicit_backend_start(self):
        source = (self.root_source / "Start_PilotODIN.bat").read_text(encoding="utf-8")
        self.assertNotIn("backend.main:app", source)
        self.assertNotIn("uvicorn", source)
        self.assertIn("Start_PilotODIN_Live_Dev.bat", source)
        self.assertIn("not migrated", source)

    def test_owned_write_boundaries_refuse_replacement_and_links(self):
        code = r"""
import os, sys
from pathlib import Path
from backend.workspace_boundary import hold_process_workspace, WorkspaceBoundaryError
home = hold_process_workspace(sys.argv[1])
os.environ["PILOTODIN_HOME"] = str(home)
from backend import storage
from backend import resource_policy
def refuse(call):
    try:
        call()
    except WorkspaceBoundaryError:
        return
    raise AssertionError("Unsafe write admitted")
original = home / "original"
original.write_bytes(b"preserve")
target = home / "resource_preferences.json"
try:
    os.link(original, target)
except OSError:
    sys.exit(77)
refuse(lambda: resource_policy.save_policy("performance"))
assert original.read_bytes() == b"preserve"
target.unlink()
resource_policy.save_policy("performance")
assert resource_policy.read_policy()["mode"] == "performance"
datasets = home / "datasets"
datasets.rename(home / "old-datasets")
datasets.mkdir()
refuse(lambda: storage.check_write_path(datasets / "new.csv", absent=True))
assert list(datasets.iterdir()) == []
refuse(lambda: storage.check_write_path(home.parent / "outside.csv", absent=True))
refuse(lambda: storage.check_write_path(home / "models" / ".." / "escape", absent=True))
assert not (home.parent / "outside.csv").exists()
"""
        result = subprocess.run(
            [sys.executable, "-B", "-c", code, str(self.home)],
            cwd=self.root_source, capture_output=True, text=True,
            timeout=15, check=False,
        )
        if result.returncode == 77:
            self.skipTest("Hard links unsupported in fixture")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_owned_upload_rejects_existing_destination_and_preserves_bytes(self):
        code = r"""
import os, sys
from unittest.mock import patch
from backend.workspace_boundary import hold_process_workspace
home = hold_process_workspace(sys.argv[1])
os.environ["PILOTODIN_HOME"] = str(home)
from backend import main, storage
from fastapi.testclient import TestClient
uid = "a" * 32
target = home / "datasets" / (uid + ".csv")
target.write_bytes(b"original")
with patch.object(storage, "uid", return_value=uid):
    response = TestClient(main.app).post("/api/projects", files={"file": ("new.csv", b"A,B\n1,2\n", "text/csv")})
assert response.status_code == 422, response.text
assert target.read_bytes() == b"original"
assert not target.with_name(target.name + ".uploading").exists()
assert storage.list_projects() == []
"""
        result = subprocess.run(
            [sys.executable, "-B", "-c", code, str(self.home)],
            cwd=self.root_source, capture_output=True, text=True,
            timeout=30, check=False,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_maintenance_never_creates_missing_home_or_database(self):
        from backend.workspace_boundary import existing_maintenance_workspace
        with self.assertRaises(WorkspaceBoundaryError):
            with existing_maintenance_workspace(str(self.home)):
                self.fail("Missing workspace admitted")
        self.assertFalse(self.home.exists())
        self.home.mkdir()
        with self.assertRaises(WorkspaceBoundaryError):
            with existing_maintenance_workspace(str(self.home)):
                self.fail("Missing database admitted")
        self.assertEqual(list(self.home.iterdir()), [])

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
