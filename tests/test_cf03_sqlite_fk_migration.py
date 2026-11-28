"""CF-03 Stage B: generated SQLite files exclusively, never owner workspaces."""
from __future__ import annotations

import hashlib
from pathlib import Path
import sqlite3

import pytest

from backend.sqlite_fk_audit import audit_database
from backend.sqlite_fk_migration import (
    MIGRATABLE_TABLES, MigrationRefused, migrate_disposable_backup,
)


def _fixture(tmp_path: Path, *, all_tables: bool = True, wal: bool = False) -> Path:
    db = tmp_path / 'generated_source.sqlite3'
    with sqlite3.connect(db) as con:
        if wal:
            con.execute('PRAGMA journal_mode=WAL')
        con.executescript('''
            CREATE TABLE projects (id TEXT PRIMARY KEY);
            CREATE TABLE experiments(
              id TEXT PRIMARY KEY, project_id TEXT NOT NULL,
              FOREIGN KEY(project_id) REFERENCES projects(id));
            CREATE TABLE quality_state (
              project_id TEXT PRIMARY KEY, original_sha256 TEXT NOT NULL,
              current_version INTEGER NOT NULL DEFAULT 0);
            CREATE TABLE quality_versions (
              project_id TEXT NOT NULL, version INTEGER NOT NULL,
              operations_json TEXT NOT NULL, event TEXT NOT NULL,
              details_json TEXT NOT NULL, created_at TEXT NOT NULL,
              PRIMARY KEY (project_id, version));
            CREATE TABLE quality_actions (
              id TEXT PRIMARY KEY, project_id TEXT NOT NULL,
              kind TEXT NOT NULL, column_name TEXT NOT NULL, params_json TEXT NOT NULL,
              source TEXT NOT NULL, affected_rows INTEGER NOT NULL, created_at TEXT NOT NULL);
            CREATE TABLE quality_decisions (
              project_id TEXT NOT NULL, issue_id TEXT NOT NULL,
              status TEXT NOT NULL, created_at TEXT NOT NULL,
              PRIMARY KEY(project_id,issue_id));
            CREATE TABLE quality_approval_receipts (
              proposal_id TEXT PRIMARY KEY, project_id TEXT NOT NULL,
              expected_version INTEGER NOT NULL, proposal_hash TEXT NOT NULL,
              payload_json TEXT NOT NULL, issued_at TEXT NOT NULL,
              expires_at TEXT NOT NULL, consumed_at TEXT);
            CREATE INDEX quality_approval_project
                ON quality_approval_receipts(project_id,expected_version);
            CREATE TABLE investigations_v1 (
              id TEXT PRIMARY KEY, project_id TEXT NOT NULL, objective TEXT NOT NULL,
              dataset_version INTEGER NOT NULL, status TEXT NOT NULL,
              created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
            CREATE INDEX ix_investigations_v1_project
              ON investigations_v1(project_id, updated_at DESC);
            CREATE TABLE evidence_v1 (
              id TEXT PRIMARY KEY, investigation_id TEXT NOT NULL,
              result TEXT NOT NULL,
              FOREIGN KEY(investigation_id) REFERENCES investigations_v1(id));
            CREATE TABLE semantic_human_review_events (
              event_id INTEGER PRIMARY KEY AUTOINCREMENT,
              project_id TEXT NOT NULL, quality_version INTEGER NOT NULL,
              column_name TEXT NOT NULL, hypothesis_role TEXT NOT NULL,
              hypothesis_hash TEXT NOT NULL, revision INTEGER NOT NULL,
              previous_decision TEXT, decision TEXT NOT NULL, occurred_at TEXT NOT NULL);
            CREATE INDEX semantic_review_event_lookup ON semantic_human_review_events
              (project_id, quality_version,column_name,hypothesis_role,event_id);
            CREATE TABLE migration_trigger_log (event TEXT NOT NULL);
            CREATE TRIGGER quality_action_insert AFTER INSERT ON quality_actions
              BEGIN INSERT INTO migration_trigger_log VALUES ('quality_added'); END;
        ''')
        con.execute("INSERT INTO projects VALUES('p1')")
        con.execute("INSERT INTO experiments VALUES('e1','p1')")
        con.execute("INSERT INTO quality_state VALUES('p1','hash',0)")
        con.execute("INSERT INTO quality_versions VALUES('p1',0,'[]','original','{}','2026')")
        con.execute("INSERT INTO quality_actions VALUES('a1','p1','replace','SKU','{}','approved',1,'2026')")
        con.execute("INSERT INTO quality_decisions VALUES('p1','finding','applied','2026')")
        con.execute("INSERT INTO quality_approval_receipts VALUES('receipt1','p1',0,'hash','{}','2026','2027','2026')")
        con.execute("INSERT INTO investigations_v1 VALUES('i1','p1','pricing',0,'draft','2026','2026')")
        con.execute("INSERT INTO evidence_v1 VALUES('ev1','i1','evidence')")
        con.execute("INSERT INTO semantic_human_review_events VALUES(3,'p1',0,'SKU','identifier','sha',1,NULL,'accepted','2026')")
    return db


def _run(db: Path, *, output: Path | None = None):
    dst = output or db.with_name('migrated.sqlite3')
    return dst, migrate_disposable_backup(db, dst, acknowledge_disposable=True)


def _names(db):
    with sqlite3.connect(db) as con:
        return set(x[0] for x in con.execute(
            "SELECT name FROM sqlite_master WHERE type IN ('index','trigger') AND sql IS NOT NULL"))


def test_safe_migration_covers_all_seven_relationships_and_preserves_bytes(tmp_path):
    db = _fixture(tmp_path)
    before_hash = hashlib.sha256(db.read_bytes()).hexdigest()
    before_names = _names(db)
    before_audit = audit_database(db)
    assert {x['table'] for x in before_audit['undeclared_project_links']} == MIGRATABLE_TABLES
    out, report = _run(db)
    assert out.exists()
    assert report['production_enforcement_enabled'] is False
    assert report['current_source_ddl_update_required'] is False
    assert report['current_source_connection_factory_update_required'] is False
    assert report['optional_table_creation_must_be_rechecked'] is False
    assert report['legacy_database_activation_requires_separate_approval'] is True
    assert report['post_full_project_fk_coverage']
    assert {r['table'] for r in report['migrated_tables']} == MIGRATABLE_TABLES
    assert hashlib.sha256(db.read_bytes()).hexdigest() == before_hash
    assert _names(out) == before_names
    after = audit_database(out)
    assert after['audit_complete'] and after['full_project_fk_coverage']
    assert not after['detected_orphan_links']
    with sqlite3.connect(out) as con:
        con.execute('PRAGMA foreign_keys=ON')
        assert con.execute('PRAGMA foreign_keys').fetchone()[0] == 1
        assert con.execute("SELECT consumed_at FROM quality_approval_receipts").fetchone()[0] == '2026'
        assert con.execute("SELECT event_id FROM semantic_human_review_events").fetchone()[0] == 3
        assert con.execute("SELECT result FROM evidence_v1").fetchone()[0] == 'evidence'
        assert con.execute("SELECT event FROM migration_trigger_log").fetchone()[0] == 'quality_added'
        con.execute("INSERT INTO quality_actions VALUES('a2','p1','replace','A','{}','approved',1,'2026')")
        assert con.execute("SELECT COUNT(*) FROM migration_trigger_log").fetchone()[0] == 2


@pytest.mark.parametrize('table,statement', [
    ('quality_state', "INSERT INTO quality_state VALUES('absent','hash',0)"),
    ('quality_versions', "INSERT INTO quality_versions VALUES('absent',0,'[]','original','{}','2026')"),
    ('quality_actions', "INSERT INTO quality_actions VALUES('a2','absent','replace','SKU','{}','approved',1,'2026')"),
    ('quality_decisions', "INSERT INTO quality_decisions VALUES('absent','finding','applied','2026')"),
    ('quality_approval_receipts', "INSERT INTO quality_approval_receipts VALUES('r2','absent',0,'hash','{}','2026','2027',NULL)"),
    ('investigations_v1', "INSERT INTO investigations_v1 VALUES('i2','absent','pricing',0,'draft','2026','2026')"),
    ('semantic_human_review_events', "INSERT INTO semantic_human_review_events VALUES(4,'absent',0,'SKU','identifier','sha',1,NULL,'accepted','2026')"),
])
def test_migrated_db_rejects_all_seven_orphans_when_fk_enabled(tmp_path, table, statement):
    db = _fixture(tmp_path)
    out, _ = _run(db)
    con = sqlite3.connect(out)
    try:
        con.execute('PRAGMA foreign_keys=ON')
        with pytest.raises(sqlite3.IntegrityError):
            con.execute(statement)
    finally:
        con.rollback()
        con.close()


def test_migration_refuses_legacy_undeclared_orphans_and_creates_no_output(tmp_path):
    db = _fixture(tmp_path)
    with sqlite3.connect(db) as con:
        con.execute("INSERT INTO quality_state VALUES('orphan','hash',0)")
    before = db.read_bytes()
    with pytest.raises(MigrationRefused, match='integrity audit'):
        _run(db)
    assert db.read_bytes() == before
    assert not (tmp_path / 'migrated.sqlite3').exists()


def test_migration_refuses_declared_fk_orphans(tmp_path):
    db = _fixture(tmp_path)
    with sqlite3.connect(db) as con:  # FK off to model legacy data.
        con.execute("INSERT INTO experiments VALUES('e2','ghost')")
    with pytest.raises(MigrationRefused):
        _run(db)
    assert not (tmp_path / 'migrated.sqlite3').exists()


def test_migration_refuses_overwriting_existing_output(tmp_path):
    db = _fixture(tmp_path)
    out = tmp_path / 'migrated.sqlite3'
    out.write_bytes(b'protected-existing-output')
    with pytest.raises(MigrationRefused, match='absent output'):
        _run(db, output=out)
    assert out.read_bytes() == b'protected-existing-output'


def test_disposable_acknowledgment_is_mandatory(tmp_path):
    db = _fixture(tmp_path)
    with pytest.raises(MigrationRefused, match='acknowledgement'):
        migrate_disposable_backup(db, tmp_path / 'migrated.sqlite3')
    assert not (tmp_path / 'migrated.sqlite3').exists()


def test_migration_refuses_symlink_input(tmp_path):
    db = _fixture(tmp_path)
    link = tmp_path / 'source-link.sqlite3'
    try:
        link.symlink_to(db)
    except OSError:
        pytest.skip('Symlinks not permitted')
    with pytest.raises(MigrationRefused):
        _run(link)


def test_migration_refuses_unknown_table_relationship_gap(tmp_path):
    db = _fixture(tmp_path)
    with sqlite3.connect(db) as con:
        con.execute('CREATE TABLE plugin_notes(project_id TEXT, private_value TEXT)')
        con.execute("INSERT INTO plugin_notes VALUES('p1','secret')")
    with pytest.raises(MigrationRefused, match='Unexpected'):
        _run(db)


def test_migration_refuses_partial_schema(tmp_path):
    db = tmp_path / 'generated_source.sqlite3'
    with sqlite3.connect(db) as con:
        con.execute('CREATE TABLE projects(id TEXT PRIMARY KEY)')
        con.execute('CREATE TABLE quality_state(project_id TEXT PRIMARY KEY)')
    with pytest.raises(MigrationRefused):
        _run(db)


def test_second_migration_is_refused_instead_of_overwriting(tmp_path):
    db = _fixture(tmp_path)
    out, _ = _run(db)
    with pytest.raises(MigrationRefused, match='already migrated'):
        migrate_disposable_backup(out, tmp_path / 'second.sqlite3', acknowledge_disposable=True)


def test_destination_symlink_even_broken_is_never_followed(tmp_path):
    db = _fixture(tmp_path)
    victim = tmp_path / 'victim.sqlite3'
    out = tmp_path / 'migrated.sqlite3'
    try:
        out.symlink_to(victim)
    except OSError:
        pytest.skip('Symlinks not permitted')
    with pytest.raises(MigrationRefused):
        _run(db, output=out)
    assert not victim.exists()


def test_migration_failure_does_not_publish_partial_copy(tmp_path, monkeypatch):
    from backend import sqlite_fk_migration as mod
    db = _fixture(tmp_path)
    before = hashlib.sha256(db.read_bytes()).hexdigest()
    def failing_rebuild(*args):
        raise RuntimeError('Synthetic interrupted rebuild')
    monkeypatch.setattr(mod, '_rebuild', failing_rebuild)
    with pytest.raises(RuntimeError, match='Synthetic'):
        _run(db)
    assert hashlib.sha256(db.read_bytes()).hexdigest() == before
    assert not (tmp_path / 'migrated.sqlite3').exists()
    assert not list(tmp_path.glob('.pilotodin-cf03-*'))


def test_disposable_wal_snapshot_contains_latest_committed_rows(tmp_path):
    db = _fixture(tmp_path)
    reader = sqlite3.connect(db)
    try:
        assert reader.execute('PRAGMA journal_mode=WAL').fetchone()[0] == 'wal'
        reader.execute("INSERT INTO projects VALUES('p2')")
        reader.commit()
        out, _ = _run(db)
        with sqlite3.connect(out) as con:
            assert con.execute("SELECT COUNT(*) FROM projects").fetchone()[0] == 2
    finally:
        reader.close()


def test_audit_autoincrement_never_reuses_deleted_event_identifiers(tmp_path):
    db = _fixture(tmp_path)
    with sqlite3.connect(db) as con:
        con.execute("INSERT INTO semantic_human_review_events VALUES(500,'p1',0,'SKU','identifier','sha',1,NULL,'accepted','2026')")
        con.execute('DELETE FROM semantic_human_review_events WHERE event_id=500')
        assert con.execute("SELECT seq FROM sqlite_sequence WHERE name='semantic_human_review_events'").fetchone()[0] == 500
    out, _ = _run(db)
    with sqlite3.connect(out) as con:
        con.execute("INSERT INTO semantic_human_review_events (project_id,quality_version,column_name,hypothesis_role,hypothesis_hash,revision,decision,occurred_at) "
                    "VALUES('p1',0,'SKU','identifier','sha',1,'accepted','2026')")
        assert con.execute('SELECT MAX(event_id) FROM semantic_human_review_events').fetchone()[0] == 501


def test_absent_optional_table_is_reported_as_future_ddl_risk(tmp_path):
    db = _fixture(tmp_path)
    with sqlite3.connect(db) as con:
        con.execute('DROP TABLE quality_approval_receipts')
    out, report = _run(db)
    assert report['missing_optional_tables'] == ['quality_approval_receipts']
    assert report['current_source_ddl_update_required'] is False
    assert report['current_source_connection_factory_update_required'] is False
    assert report['optional_table_creation_must_be_rechecked'] is True
    assert report['legacy_database_activation_requires_separate_approval'] is True
    assert report['production_enforcement_enabled'] is False
    assert audit_database(out)['full_project_fk_coverage']
    # An unvetted alternate CREATE TABLE can reintroduce a missing link;
    # a missing optional table cannot be treated as production clearance.
    with sqlite3.connect(out) as con:
        con.execute('CREATE TABLE quality_approval_receipts (proposal_id TEXT,project_id TEXT NOT NULL)')
    assert not audit_database(out)['full_project_fk_coverage']


def test_every_existing_project_rowid_is_preserved(tmp_path):
    db = _fixture(tmp_path)
    with sqlite3.connect(db) as con:
        original = {table: con.execute(f'SELECT rowid FROM "{table}" ORDER BY rowid').fetchall()
                    for table in MIGRATABLE_TABLES}
    out, _ = _run(db)
    with sqlite3.connect(out) as con:
        for table, expected in original.items():
            assert con.execute(f'SELECT rowid FROM "{table}" ORDER BY rowid').fetchall() == expected


def test_windows_staging_connections_closed_before_atomic_publication(tmp_path, monkeypatch):
    """Windows cannot unlink a SQLite file while a connection still owns it."""
    import os
    from backend import sqlite_fk_migration as migration

    db = _fixture(tmp_path)
    opened = []
    raw_connect = sqlite3.connect
    raw_link = os.link

    class Tracked(sqlite3.Connection):
        was_closed = False

        def close(self):
            self.was_closed = True
            return super().close()

    def tracked_connect(database, *args, **kwargs):
        if isinstance(database, Path) and database.name.startswith('.pilotodin-cf03-'):
            kwargs['factory'] = Tracked
            con = raw_connect(database, *args, **kwargs)
            opened.append(con)
            return con
        return raw_connect(database, *args, **kwargs)

    def guarded_link(source, output, *args, **kwargs):
        assert len(opened) >= 2, 'Expected staged writer and schema-catalog connections'
        assert all(con.was_closed for con in opened), 'SQLite connection remained open at publication'
        return raw_link(source, output, *args, **kwargs)

    monkeypatch.setattr(migration.sqlite3, 'connect', tracked_connect)
    monkeypatch.setattr(migration.os, 'link', guarded_link)
    output, _report = _run(db)
    assert output.is_file()
    assert all(con.was_closed for con in opened)
