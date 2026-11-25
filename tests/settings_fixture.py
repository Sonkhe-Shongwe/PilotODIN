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
