"""P1 CI-ONLY fault injector for disposable, generated CSV originals.

Never call this against a developer's installed app or .pilotodin-dev-data.
No database mutation; only an exactly pinned source within a dedicated GitHub
runner temp directory can be hidden/restored. No user paths or hashes printed.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sqlite3
from pathlib import Path


def _sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _fixture(project_id: str):
    if os.environ.get("CI") != "true" or os.environ.get("P1_REAL_HTTP_E2E") != "1":
        raise RuntimeError("Test-only fault injection requires isolated CI")
    run_id = os.environ.get("GITHUB_RUN_ID", "")
    if not re.fullmatch(r"[0-9]+", run_id):
        raise RuntimeError("Missing trusted CI run")
    runner_raw = os.environ.get("RUNNER_TEMP", "")
    home_raw = os.environ.get("PILOTODIN_HOME", "")
    if not runner_raw or not home_raw:
        raise RuntimeError("Missing isolated runner workspace")
    runner = Path(runner_raw).resolve(strict=True)
    home = Path(home_raw).resolve(strict=True)
    if home != runner / ("pilotodin-p1-real-http-" + run_id) or home.is_symlink():
        raise RuntimeError("Refuse any non-disposable workspace")
    if not re.fullmatch(r"[0-9a-f]{32}", project_id):
        raise RuntimeError("Invalid disposable project ID")
    database = home / "pilotodin.sqlite3"
    if not database.is_file() or database.is_symlink():
        raise RuntimeError("Missing temporary database")
    with sqlite3.connect(database.as_uri() + "?mode=ro", uri=True) as con:
        rows = con.execute(
            "SELECT filename,dataset_path,file_ext FROM projects WHERE id=?",
            (project_id,),
        ).fetchall()
        if len(rows) != 1:
            raise RuntimeError("Expected one synthetic project")
        name, recorded, ext = rows[0]
        if name != "pilotodin_p1_http_A.csv" or ext != ".csv":
            raise RuntimeError("Refuse non-fixture source")
        quality = con.execute(
            "SELECT original_sha256,current_version FROM quality_state WHERE project_id=?",
            (project_id,),
        ).fetchone()
        history = con.execute(
            "SELECT version,event,operations_json FROM quality_versions "
            "WHERE project_id=? ORDER BY version", (project_id,),
        ).fetchall()
        action_count = con.execute(
            "SELECT COUNT(*) FROM quality_actions WHERE project_id=?", (project_id,)
        ).fetchone()[0]
        decision_count = con.execute(
            "SELECT COUNT(*) FROM quality_decisions WHERE project_id=?", (project_id,)
        ).fetchone()[0]
    if quality is None or quality[1] != 0 or len(history) != 1:
        raise RuntimeError("Unexpected Quality version or history")
    if tuple(history[0]) != (0, "original", "[]") or action_count or decision_count:
        raise RuntimeError("Synthetic project already has Quality edits")
    datasets = home / "datasets"
    source = Path(recorded)
    if (source.parent != datasets or source.is_symlink()
        or not re.fullmatch(r"[0-9a-f]{32}\\.csv", source.name)):
        raise RuntimeError("Refuse source outside generated fixtures")
    hidden = datasets / (source.name + ".p1-real-http-hidden")
    if hidden.is_symlink():
        raise RuntimeError("Unexpected hidden path")
    return source, hidden, quality[0]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("hide", "restore", "audit"))
    parser.add_argument("--project-id", required=True)
    args = parser.parse_args()
    source, hidden, pin = _fixture(args.project_id)
    if args.action == "hide":
        if hidden.exists() or not source.is_file() or _sha(source) != pin:
            raise RuntimeError("Original is not safely movable")
        source.rename(hidden)
        if _sha(hidden) != pin:
            raise RuntimeError("Moved disposable source fingerprint changed")
        print("P1_SYNTHETIC_SOURCE_HIDDEN")
    elif args.action == "restore":
        if source.exists() or not hidden.is_file() or _sha(hidden) != pin:
            raise RuntimeError("Original cannot be safely restored")
        hidden.rename(source)
        if _sha(source) != pin:
            raise RuntimeError("Restored disposable source fingerprint changed")
        print("P1_SYNTHETIC_SOURCE_RESTORED")
    else:
        if hidden.exists() or not source.is_file() or _sha(source) != pin:
            raise RuntimeError("Original fingerprint unavailable")
        print(json.dumps({"version": 0, "versions": 1, "actions": 0,
                          "decisions": 0, "original_sha256_matches": True},
                         sort_keys=True))


if __name__ == "__main__":
    main()
