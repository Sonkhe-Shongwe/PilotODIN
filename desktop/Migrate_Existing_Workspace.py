"""Copy a previous PilotODIN workspace to the desktop app storage.

Run with the old app and the new desktop app CLOSED. This never moves or
modifies the original source folder and never overwrites existing destination.
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import shutil
import sqlite3
import sys
import uuid


def desktop_data_dir() -> Path:
    value = os.environ.get("LOCALAPPDATA")
    if not value:
        raise RuntimeError("This migration command must be run from Windows")
    return Path(value) / "com.pilotodin.studio" / "data"


def migrate(source_inner_folder: Path, destination_data: Path) -> tuple[int, int]:
    source = (source_inner_folder / "data").resolve()
    target = destination_data.resolve()
    if not (source / "pilotodin.sqlite3").is_file():
        raise ValueError("Select the OLD inner PilotODIN folder containing data/pilotodin.sqlite3")
    if source == target:
        raise ValueError("Source and destination are identical")
    if target.exists() and any(target.iterdir()):
        raise ValueError("Desktop data already exists. Migration stopped to avoid overwriting it")
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.parent / (".pilotodin-migration-" + uuid.uuid4().hex)
    try:
        shutil.copytree(source, temporary)
        with sqlite3.connect(temporary / "pilotodin.sqlite3") as conn:
            projects = conn.execute("SELECT id, dataset_path FROM projects").fetchall()
            for project_id, old_path in projects:
                filename = Path(old_path).name
                migrated = target / "datasets" / filename
                if not (temporary / "datasets" / filename).is_file():
                    raise ValueError(f"Missing dataset in migration copy: {filename}")
                conn.execute("UPDATE projects SET dataset_path=? WHERE id=?", (str(migrated), project_id))
            experiments = conn.execute("SELECT COUNT(*) FROM experiments").fetchone()[0]
            conn.commit()
        # Only place the finished, checked copy into final location.
        if target.exists():
            if any(target.iterdir()):
                raise ValueError("Target became occupied during migration")
            target.rmdir()
        temporary.replace(target)
        return len(projects), experiments
    finally:
        if temporary.exists():
            shutil.rmtree(temporary)


def main() -> int:
    parser = argparse.ArgumentParser(description="Safely copy the existing Studio projects into the native desktop workspace")
    parser.add_argument("old_inner_pilotodin", type=Path, help="Previous inner PilotODIN folder")
    args = parser.parse_args()
    try:
        projects, experiments = migrate(args.old_inner_pilotodin, desktop_data_dir())
        print(f"Copied {projects} projects and {experiments} experiments. Original data untouched.")
    except (OSError, ValueError, RuntimeError, sqlite3.DatabaseError) as exc:
        print(f"Migration safely stopped: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
