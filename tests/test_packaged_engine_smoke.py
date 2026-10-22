"""Exercise the exact smoke contract using the real unfrozen engine.

Windows CI runs it again using the actual PyInstaller EXE, not a mock.
"""
import importlib.util
from pathlib import Path
import sys

_SCRIPT = Path(__file__).resolve().parents[1] / 'desktop' / 'verify_packaged_engine.py'
spec = importlib.util.spec_from_file_location('packaged_smoke_gate', _SCRIPT)
assert spec is not None and spec.loader is not None
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def test_engine_smoke_contract_uses_real_running_backend():
    root = Path(__file__).resolve().parents[1]
    result = mod.smoke_test_engine([sys.executable, '-m', 'backend.desktop_runner'], root, 25)
    assert result == {
        'passed': True, 'auth_required': True, 'wrong_origin_rejected': True,
        'user_storage_isolated': True, 'model_started': False,
    }


def test_smoke_cleanup_checks_unlocked_sqlite_file(tmp_path):
    db = tmp_path / 'pilotodin.sqlite3'
    db.write_bytes(b'SQLite format 3\\x00')
    mod._wait_for_database_unlock(db, timeout_seconds=1)
    assert db.exists()
    assert db.read_bytes().startswith(b'SQLite format 3')
    assert not db.with_name(db.name + '.smoke-unlock-check').exists()


def test_smoke_cleanup_tolerates_database_never_created(tmp_path):
    mod._wait_for_database_unlock(tmp_path / 'never-created.sqlite3', timeout_seconds=1)
