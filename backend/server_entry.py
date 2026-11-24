"""Writer-owned ASGI factory for explicitly isolated dev, local DevQA and hosted QA.

Use uvicorn --factory. Ownership is acquired in the serving worker, before
analytical storage import, including reload replacements. Direct in-process
synthetic imports remain unchanged. The production desktop runner has its
own token-authenticated entrypoint.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import re

from backend.workspace_boundary import (
    LOCK_NAME, WorkspaceBoundaryError, existing_fixture_file,
    existing_fixture_home, hold_process_workspace,
)

ROOT = Path(__file__).resolve().parents[1]

# Exact existing allocator phases and seed outputs, not a general QA path mode.
LOCAL_FIXTURES = {
    "P2-NATIVE-DELIVER-CONSENT": (
        "synthetic-consent-manifest.json", "OWNER_NATIVE_DIALOG_OBSERVATION_NOT_ACCEPTANCE", 1),
    "P2-NATIVE-TWO-WINDOW-DELIVER": (
        "two-window-manifest.json", "SYNTHETIC_TWO_WINDOW_OWNER_VISUAL_NOT_RELEASE", 2),
    "P3-NATIVE-SEMANTIC-CONTEXT": (
        "p3-native-semantic-manifest.json", "SYNTHETIC_NATIVE_P3_SEMANTIC_EDITOR_OWNER_VISUAL_QA_ONLY", 2),
    "P3-NATIVE-QUALITY-W5": (
        "p3-native-w5-manifest.json", "ONE_SYNTHETIC_QUALITY_PROPOSAL_AND_ONE_EXPLICIT_UI_COMMIT", 1),
}


def _fixture_manifest(path):
    try:
        info = existing_fixture_file(path)
        if info.st_size > 65536:
            raise WorkspaceBoundaryError("Invalid local fixture manifest")
        with path.open("rb") as stream:
            raw = stream.read(65537)
        if len(raw) > 65536:
            raise WorkspaceBoundaryError("Invalid local fixture manifest")
        value = json.loads(raw.decode("utf-8-sig"))
        if not isinstance(value, dict):
            raise WorkspaceBoundaryError("Invalid local fixture manifest")
        return value
    except (OSError, UnicodeError, ValueError) as exc:
        raise WorkspaceBoundaryError("Invalid local fixture manifest") from exc


def _local_fixture_home(env, home):
    base = Path(env.get("LOCALAPPDATA", ""))
    if not base.is_absolute() or ".." in base.parts or home.name != "workspace":
        raise WorkspaceBoundaryError("Unexpected local fixture workspace")
    # Only the allocator's existing default root is admitted, never arbitrary
    # caller-selected fixture roots or production/dev data.
    runs = existing_fixture_home(str(base / "PilotODIN" / "DevQA" / "runs"))
    owned = existing_fixture_home(str(home))
    run = owned.parent
    if run.parent != runs or owned.name != "workspace":
        raise WorkspaceBoundaryError("Unexpected local fixture workspace")
    phase = next((key for key in LOCAL_FIXTURES
                  if re.fullmatch(re.escape(key) + r"-[0-9]{8}T[0-9]{6}Z-[a-f0-9]{10}", run.name)), None)
    if phase is None:
        raise WorkspaceBoundaryError("Unexpected local fixture workspace")
    allocation = _fixture_manifest(run / "manifest.json")
    if (allocation.get("schema_version") != 1 or allocation.get("run_id") != run.name
            or allocation.get("phase") != phase
            or allocation.get("state") != "READY_NOT_TESTED"
            or allocation.get("product_acceptance") != "NOT_TESTED"
            or allocation.get("relative_paths") != {"backend": "workspace", "exports": "exports", "logs": "logs"}
            or allocation.get("rules") != {"synthetic_only": True, "no_auto_delete": True, "no_model_or_installer": True}):
        raise WorkspaceBoundaryError("Invalid local fixture allocation")
    filename, scope, count = LOCAL_FIXTURES[phase]
    seed = _fixture_manifest(run / "fixtures" / filename)
    if seed.get("phase") != phase or seed.get("run_id") != run.name or seed.get("scope") != scope:
        raise WorkspaceBoundaryError("Invalid local fixture seed")
    if count == 1:
        ids = [seed.get("project_id")]
    else:
        projects = seed.get("projects")
        if not isinstance(projects, list) or len(projects) != count or not all(isinstance(item, dict) for item in projects):
            raise WorkspaceBoundaryError("Invalid local fixture seed")
        ids = [item.get("id") for item in projects]
    if (not all(isinstance(item, str) and re.fullmatch(r"[a-f0-9]{32}", item) for item in ids)
            or len(set(ids)) != count):
        raise WorkspaceBoundaryError("Invalid local fixture seed")
    if existing_fixture_file(owned / LOCK_NAME).st_size != 0:
        raise WorkspaceBoundaryError("Invalid local fixture writer marker")
    if existing_fixture_file(owned / "pilotodin.sqlite3").st_size == 0:
        raise WorkspaceBoundaryError("Invalid local fixture database")
    return owned


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
    elif mode == "local-devqa":
        return _local_fixture_home(env, home)
    else:
        raise WorkspaceBoundaryError("Explicit server mode required")
    return home


def owned_app():
    home = admitted_home(os.environ)
    owned = hold_process_workspace(str(home))
    if os.environ.get("PILOTODIN_SERVER_MODE") == "local-devqa":
        if _local_fixture_home(os.environ, owned) != owned:
            raise WorkspaceBoundaryError("Local fixture workspace changed")
    os.environ["PILOTODIN_HOME"] = str(owned)
    from backend.main import app
    return app
