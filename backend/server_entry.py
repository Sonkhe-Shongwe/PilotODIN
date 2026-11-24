"""Writer-owned ASGI factory for explicitly isolated dev and hosted QA.

Use uvicorn --factory. Ownership is acquired in the serving worker, before
analytical storage import, including reload replacements. Direct in-process
synthetic imports remain unchanged. The production desktop runner has its
own token-authenticated entrypoint.
"""
from __future__ import annotations

import os
from pathlib import Path
import re

from backend.workspace_boundary import WorkspaceBoundaryError, hold_process_workspace

ROOT = Path(__file__).resolve().parents[1]


def admitted_home(env):
    mode = env.get("PILOTODIN_SERVER_MODE", "")
    value = env.get("PILOTODIN_HOME", "")
    home = Path(value)
    if (not value or not home.is_absolute() or ".." in home.parts
            or env.get("PILOTODIN_DESKTOP_SESSION")):
        raise WorkspaceBoundaryError("Explicit isolated non-desktop workspace required")
    if mode == "dev":
        if home != ROOT / ".pilotodin-dev-data":
            raise WorkspaceBoundaryError("Unexpected development workspace")
    elif mode == "hosted-fixture":
        runner = Path(env.get("RUNNER_TEMP", ""))
        run_id = env.get("GITHUB_RUN_ID", "")
        if (env.get("CI") != "true" or env.get("GITHUB_ACTIONS") != "true"
                or not re.fullmatch(r"[0-9]+", run_id)
                or not runner.is_absolute() or ".." in runner.parts
                or not home.is_relative_to(runner) or home == runner):
            raise WorkspaceBoundaryError("Unexpected hosted fixture workspace")
        relative = home.relative_to(runner)
        browser = relative.parts == ("pilotodin-p1-real-http-" + run_id,)
        native = (len(relative.parts) >= 2
                  and relative.parts[-1] == "P4-71-only-home-" + run_id
                  and home.is_dir())
        if not (browser or native):
            raise WorkspaceBoundaryError("Unexpected hosted fixture workspace")
    else:
        raise WorkspaceBoundaryError("Explicit server mode required")
    return home


def owned_app():
    home = admitted_home(os.environ)
    owned = hold_process_workspace(str(home))
    os.environ["PILOTODIN_HOME"] = str(owned)
    from backend.main import app
    return app
