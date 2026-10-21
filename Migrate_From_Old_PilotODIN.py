"""Move an existing PilotODIN single-user workspace to this *new* installation.

This is deliberately a one-way copy: the source is not changed. Must be run
before starting the new application (with the old application closed).
"""
from __future__ import annotations

import argparse
from pathlib import Path
import shutil
import sqlite3
import sys


def migrate(source_project: Path, destination_project: Path) -> tuple[int, int]:
    source_project = source_project.expanduser().resolve()
    destination_project = destination_project.expanduser().resolve()
    source = source_project / 'data'
    dest = destination_project / 'data'
    if not (source / 'pilotodin.sqlite3').is_file():
        raise ValueError('Old data/pilotodin.sqlite3 not found. Select the INNER PilotODIN folder.')
    if source == dest:
        raise ValueError('The old and new project paths are identical.')
    if dest.exists() and any(dest.iterdir()):
        raise ValueError('The new data folder is not empty. Migration stopped to protect existing data. Back it up first.')
    if not (destination_project / 'backend' / 'main.py').is_file():
        raise ValueError('Destination does not look like the new PilotODIN project.')
    # Make the destination only after all preconditions pass. Existing data is never overwritten.
    if dest.exists():
        dest.rmdir()
    shutil.copytree(source, dest)
    try:
        db = dest / 'pilotodin.sqlite3'
        with sqlite3.connect(db) as con:
            rows = con.execute('SELECT id,dataset_path FROM projects').fetchall()
            missing = []
            for ident, old_path in rows:
                resolved = (dest / 'datasets' / Path(old_path).name).resolve()
                if not resolved.is_relative_to((dest / 'datasets').resolve()) or not resolved.is_file():
                    missing.append(Path(old_path).name)
                else:
                    con.execute('UPDATE projects SET dataset_path=? WHERE id=?',(str(resolved),ident))
            if missing:
                raise ValueError(f'Missing migrated dataset files: {", ".join(missing[:5])}')
            count = con.execute('SELECT COUNT(*) FROM experiments').fetchone()[0]
        return len(rows), count
    except Exception:
        # Don't remove copied data on an error; it can be inspected or restored.
        raise


def main() -> int:
    ap = argparse.ArgumentParser(description='Copy previous PilotODIN projects without changing your old installation.')
    ap.add_argument('old_folder', help='Path to the OLD inner PilotODIN folder (containing a data folder)')
    args = ap.parse_args()
    try:
        projects, experiments = migrate(Path(args.old_folder), Path(__file__).resolve().parent)
    except (OSError, ValueError, sqlite3.DatabaseError) as exc:
        print(f'Could not migrate safely: {exc}', file=sys.stderr)
        return 1
    print(f'Migration complete: {projects} projects and {experiments} experiments copied.')
    print('Old files were not modified. Cloud keys are still subject to Windows DPAPI user-account protection.')
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
