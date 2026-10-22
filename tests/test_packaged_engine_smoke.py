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
