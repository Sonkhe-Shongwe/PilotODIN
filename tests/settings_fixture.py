"""Explicit disposable settings adapter; never imported by product code."""
from pathlib import Path
import os

from backend.settings_storage import Store
from backend.workspace_boundary import existing_fixture_home, WorkspaceBoundaryError


def fixture_store(home):
    home = Path(home)
    if existing_fixture_home(str(home)) != home:
        raise WorkspaceBoundaryError("Fixture root changed")

    def check(path, *, missing=False, absent=False, expected=None):
        if path.parent != home or existing_fixture_home(str(home)) != home:
            raise WorkspaceBoundaryError("Fixture path outside allocated root")
        try:
            info = path.lstat()
        except FileNotFoundError:
            if missing or absent:
                return None
            raise
        if absent or (expected is not None and not os.path.samestat(info, expected)):
            raise WorkspaceBoundaryError("Fixture identity changed")
        return info

    return Store(home, check_path=check)

def fixture_dpapi(data, decrypt=False):
    """Reversible inert codec; not cryptography and never used in production."""
    marker = b"fixture-dpapi:"
    if decrypt:
        if not data.startswith(marker):
            raise OSError("Invalid synthetic ciphertext")
        return data[len(marker):][::-1]
    return marker + data[::-1]


def isolate_ai_store(monkeypatch, ai, home):
    monkeypatch.setattr(ai, "_settings_store", lambda: fixture_store(home))
    monkeypatch.setattr(ai, "_dpapi", fixture_dpapi)
    monkeypatch.setattr(ai, "_memory_keys", {})
    monkeypatch.setattr(ai, "_config_inhibited", False)
    monkeypatch.setattr(ai, "_keys_inhibited", False)
    monkeypatch.setattr(ai, "_health", {})
    monkeypatch.setattr(ai, "_cooldowns", {})
    monkeypatch.setattr(ai, "_last_background_check", 0.0)
