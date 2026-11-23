"""CF-03 Stage B: fail-closed FK migration of a NEW disposable SQLite copy.

Never modifies input, never overwrites output and never enables enforcement in
PilotODIN's production connection factory. An owner-approved, consistent
DISPOSABLE backup is required before use outside generated test fixtures.
"""
from __future__ import annotations

import argparse
from contextlib import closing
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import tempfile
from typing import Any

try:
    from .sqlite_fk_audit import audit_database, _quoted
except ImportError:
    from sqlite_fk_audit import audit_database, _quoted

# Exact table identities verified against development branch 995e91e. Never
# add a constraint to an unknown plugin table without a separate review.
MIGRATABLE_TABLES = frozenset({
    'quality_state', 'quality_versions', 'quality_actions', 'quality_decisions',
    'quality_approval_receipts', 'investigations_v1', 'semantic_human_review_events',
})
REQUIRED_TABLES = frozenset({'projects', 'quality_state', 'quality_versions',
                             'quality_actions', 'quality_decisions'})


class MigrationRefused(ValueError):
    """A database or migration precondition failed; input remains untouched."""


def _regular_file(path: Path) -> bool:
    return path.is_file() and not path.is_symlink()


def _schema(con: sqlite3.Connection) -> dict[str, str]:
    return {str(row[0]): str(row[1]) for row in con.execute(
        "SELECT name, sql FROM sqlite_master WHERE type='table' "
        "AND name NOT LIKE 'sqlite_%' AND sql IS NOT NULL")}


def _integrity_ok(con: sqlite3.Connection) -> None:
    # Avoid reading the owner's data: invoked only on staged backup files.
    result = list(con.execute('PRAGMA integrity_check'))
    if result != [('ok',)]:
        raise MigrationRefused('SQLite database integrity check failed')


def _row_digest(con: sqlite3.Connection, table: str) -> tuple[int, str]:
    """Private cryptographic row-stream comparison, never emit record content."""
    quoted = _quoted(table)
    column_info = list(con.execute(f'PRAGMA table_xinfo({quoted})'))
    regular = [str(col[1]) for col in column_info if int(col[6]) == 0]
    if not regular:
        raise MigrationRefused('Unexpected table layout')
    table_sql = con.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (table,)
    ).fetchone()[0]
    without_rowid = 'WITHOUT ROWID' in str(table_sql).upper()
    fields = ','.join(_quoted(col) for col in regular)
    if without_rowid:
        keys = [str(col[1]) for col in sorted(column_info, key=lambda x: int(x[5]))
                if int(col[5]) > 0]
        if not keys:
            raise MigrationRefused('WITHOUT ROWID table lacks primary keys')
        order = ','.join(_quoted(k) for k in keys)
        sql = f'SELECT {fields} FROM {quoted} ORDER BY {order}'
    else:
        sql = f'SELECT rowid,{fields} FROM {quoted} ORDER BY rowid'
    h = hashlib.sha256()
    total = 0
    for record in con.execute(sql):
        total += 1
        for item in record:
            if item is None:
                marker, encoded = b'N', b''
            elif isinstance(item, bytes):
                marker, encoded = b'B', item
            elif isinstance(item, str):
                marker, encoded = b'S', item.encode('utf-8', 'surrogatepass')
            elif isinstance(item, int):
                marker, encoded = b'I', str(item).encode('ascii')
            elif isinstance(item, float):
                marker, encoded = b'F', repr(item).encode('ascii')
            else:
                raise MigrationRefused('Unexpected SQLite value type')
            h.update(marker)
            h.update(len(encoded).to_bytes(8, 'little'))
            h.update(encoded)
    return total, h.hexdigest()


def _rebuild(con: sqlite3.Connection, table: str) -> tuple[int, str]:
    """Rebuild one listed table, retaining exact DDL and original row IDs."""
    if table not in MIGRATABLE_TABLES:
        raise MigrationRefused('Unexpected table for migration')
    table_sql_row = con.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (table,)
    ).fetchone()
    if not table_sql_row or not table_sql_row[0]:
        raise MigrationRefused('Missing required table DDL')
    original = str(table_sql_row[0])
    # SQLite stores CREATE TABLE text (no trailing semicolon). Preserve the
    # complete column and constraint declaration and optional table flags.
    opening = original.find('(')
    closing = original.rfind(')')
    if opening < 0 or closing <= opening or not original.lstrip().upper().startswith('CREATE TABLE'):
        raise MigrationRefused('Unsupported legacy table SQL')
    before = _row_digest(con, table)
    # AUTOINCREMENT is an audit-history high-water mark, not merely MAX(id).
    # Deleted event IDs must never be reused after the table rebuild.
    auto_seq = None
    if 'AUTOINCREMENT' in original.upper():
        sequence = con.execute(
            'SELECT seq FROM sqlite_sequence WHERE name=?', (table,)
        ).fetchone()
        auto_seq = int(sequence[0]) if sequence is not None else None
    temp = f'__cf03_new_{table}'
    if con.execute("SELECT 1 FROM sqlite_master WHERE name=?", (temp,)).fetchone():
        raise MigrationRefused('Temporary migration table name already exists')
    columns = list(con.execute(f'PRAGMA table_xinfo({_quoted(table)})'))
    names = [str(col[1]) for col in columns if int(col[6]) == 0]
    if 'project_id' not in names:
        raise MigrationRefused('Project identifier is missing')
    expected = [(str(row[1]), str(row[2])) for row in con.execute(f'PRAGMA table_info({_quoted(table)})')]
    existing_fks = list(con.execute(f'PRAGMA foreign_key_list({_quoted(table)})'))
    if any(str(row[2]).lower() == 'projects' and str(row[3]).lower() == 'project_id' for row in existing_fks):
        raise MigrationRefused('Project foreign key already exists')
    dependencies = list(con.execute(
        "SELECT type,name,sql FROM sqlite_master WHERE tbl_name=? "
        "AND type IN ('index','trigger') AND sql IS NOT NULL ORDER BY type,name", (table,)
    ))
    create_sql = (
        f'CREATE TABLE {_quoted(temp)} '
        + original[opening:closing].rstrip()
        + ', FOREIGN KEY(project_id) REFERENCES projects(id)'
        + original[closing:]
    )
    con.execute(create_sql)
    qcols = ','.join(_quoted(x) for x in names)
    if 'WITHOUT ROWID' in original.upper():
        con.execute(f'INSERT INTO {_quoted(temp)} ({qcols}) SELECT {qcols} FROM {_quoted(table)}')
    else:
        con.execute(f'INSERT INTO {_quoted(temp)} (rowid,{qcols}) '
                    f'SELECT rowid,{qcols} FROM {_quoted(table)}')
    if _row_digest(con, temp) != before:
        raise MigrationRefused('Staged row content differs')
    con.execute(f'DROP TABLE {_quoted(table)}')
    con.execute(f'ALTER TABLE {_quoted(temp)} RENAME TO {_quoted(table)}')
    if auto_seq is not None:
        current = con.execute(
            'SELECT seq FROM sqlite_sequence WHERE name=?', (table,)
        ).fetchone()
        if current is None:
            raise MigrationRefused('AUTOINCREMENT tracking row lost')
        con.execute(
            'UPDATE sqlite_sequence SET seq=? WHERE name=?',
            (max(auto_seq, int(current[0])), table),
        )
    for _kind, _name, sql in dependencies:
        con.execute(str(sql))
    if [(str(row[1]), str(row[2])) for row in con.execute(
            f'PRAGMA table_info({_quoted(table)})')] != expected:
        raise MigrationRefused('Column shape changed')
    if _row_digest(con, table) != before:
        raise MigrationRefused('Migrated row content differs')
    return before


def _migrate_staged_file(staged: Path, expected_gaps: set[str]) -> dict[str, Any]:
    """Mutate only the private staged copy; rollback on every failure."""
    con = sqlite3.connect(staged)
    try:
        con.execute('PRAGMA foreign_keys=OFF')  # Must be outside a transaction.
        if con.execute('PRAGMA foreign_keys').fetchone()[0] != 0:
            raise MigrationRefused('Cannot safely rebuild tables with enforcement enabled')
        _integrity_ok(con)
        con.execute('BEGIN IMMEDIATE')
        tables = _schema(con)
        if not REQUIRED_TABLES.issubset(tables):
            raise MigrationRefused('Required PilotODIN tables are absent')
        changed: list[dict[str, Any]] = []
        for table in sorted(expected_gaps):
            count, _digest = _rebuild(con, table)
            changed.append({'table': table, 'row_count': count})
        # This checks every declared relationship, including evidence_v1 ->
        # investigations_v1 after the parent table is replaced.
        if con.execute('PRAGMA foreign_key_check').fetchone():
            raise MigrationRefused('Migrated database contains broken foreign-key links')
        _integrity_ok(con)
        con.commit()
        con.execute('PRAGMA foreign_keys=ON')
        if con.execute('PRAGMA foreign_keys').fetchone()[0] != 1:
            raise MigrationRefused('Foreign-key enforcement could not be enabled')
        if con.execute('PRAGMA foreign_key_check').fetchone():
            raise MigrationRefused('Post-migration foreign-key validation failed')
        return {'migrated_tables': changed, 'foreign_keys_verified_on_disposable_copy': True}
    except Exception:
        if con.in_transaction:
            con.rollback()
        raise
    finally:
        con.close()


def migrate_disposable_backup(source: str | Path, output: str | Path, *,
                              acknowledge_disposable: bool = False) -> dict[str, Any]:
    """Migrate source to a NEW output file, never alter/replace the source.

    This is a developer test / offline prototype, not approval to migrate a
    real owner database or activate production FK enforcement.
    """
    if not acknowledge_disposable:
        raise MigrationRefused('Explicit disposable-source acknowledgement required')
    source, output = Path(source), Path(output)
    if not _regular_file(source) or output.exists() or output.is_symlink():
        raise MigrationRefused('Require existing regular source and absent output')
    if source.resolve() == output.resolve():
        raise MigrationRefused('Source and output must differ')
    if not output.parent.is_dir() or output.parent.is_symlink():
        raise MigrationRefused('Output directory must be an existing regular directory')
    before = audit_database(source)
    if not before['audit_complete'] or before['detected_orphan_links']:
        raise MigrationRefused('Source integrity audit failed')
    if before['declared_fk_violations']:
        raise MigrationRefused('Legacy declared FK violations require manual resolution')
    gaps = {x['table'] for x in before['undeclared_project_links']}
    if not gaps or not gaps.issubset(MIGRATABLE_TABLES):
        raise MigrationRefused('Unexpected or already migrated relationship schema')
    # Stage in output directory so the final hard link is atomic and cannot
    # overwrite existing output (including a raced symlink).
    fd, temp_name = tempfile.mkstemp(dir=output.parent, prefix='.pilotodin-cf03-', suffix='.sqlite3')
    staged = Path(temp_name)
    os.close(fd)
    try:
        try:
            # SQLite online backup copies a consistent snapshot, including WAL.
            read_uri = source.resolve().as_uri() + '?mode=ro'
            reader = sqlite3.connect(read_uri, uri=True)
            try:
                writer = sqlite3.connect(staged)
                try:
                    reader.backup(writer)
                finally:
                    writer.close()
            finally:
                reader.close()
            # Re-audit the snapshot, not merely the preflight source. The
            # input may have changed between the first audit and the backup.
            snapshot = audit_database(staged)
            if (not snapshot['audit_complete'] or snapshot['detected_orphan_links']
                    or {x['table'] for x in snapshot['undeclared_project_links']} != gaps):
                raise MigrationRefused('Snapshot changed or failed the integrity gate')
            summary = _migrate_staged_file(staged, gaps)
            # Optional modules may not have initialized their tables yet.
            # Their CURRENT CREATE TABLE definitions still lack FK clauses;
            # source DDL must be updated before real connection enforcement.
            with closing(sqlite3.connect(staged)) as catalog:
                missing_optional = sorted(MIGRATABLE_TABLES - set(_schema(catalog)))
            after = audit_database(staged)
            if (not after['audit_complete'] or after['detected_orphan_links']
                    or not after['full_project_fk_coverage']):
                raise MigrationRefused('Post-migration structural validation failed')
            # File content and schema reach a fully closed steady state before
            # the new filename is published. Existing files are never replaced.
            os.link(staged, output)
            return {**summary,
                    'post_audit_complete': after['audit_complete'],
                    'post_full_project_fk_coverage': after['full_project_fk_coverage'],
                    'missing_optional_tables': missing_optional,
                    'current_source_ddl_update_required': True,
                    'current_source_connection_factory_update_required': True,
                    'production_enforcement_enabled': False,
                    'official_acceptance_changed': False}
        finally:
            staged.unlink(missing_ok=True)
    except OSError as exc:
        # Avoid including owner filenames or sqlite record values in errors.
        raise MigrationRefused('Staging or atomic publish failed') from exc


def main() -> int:
    parser = argparse.ArgumentParser(description='Prototype CF-03 migration for DISPOSABLE copies only')
    parser.add_argument('source', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('--acknowledge-disposable', action='store_true')
    args = parser.parse_args()
    try:
        summary = migrate_disposable_backup(args.source, args.output,
                                             acknowledge_disposable=args.acknowledge_disposable)
    except (MigrationRefused, sqlite3.DatabaseError, OSError) as exc:
        print(json.dumps({'migration_completed': False, 'failure_type': type(exc).__name__}))
        return 2
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
