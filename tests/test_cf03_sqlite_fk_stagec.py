"""CF-03 Stage C: disposable schema, legacy and connection-gate regression tests.

All databases are Pytest tmp_path files. Never inspect the owner's DB.
"""
from __future__ import annotations

import sqlite3

import pytest

from backend import quality, storage, sqlite_fk_gate


def _fresh(monkeypatch, tmp_path):
    path = tmp_path / "fresh.sqlite3"
    monkeypatch.setattr(storage, "DB_PATH", path)
    assert not path.exists()
    storage.init()
    return path


def _open_legacy(monkeypatch, tmp_path):
    path = tmp_path / "legacy.sqlite3"
    # Existing user file may have declared FK violations, even if later init
    # creates additional new tables through CREATE TABLE IF NOT EXISTS.
    with sqlite3.connect(path) as con:
        con.executescript("""
          CREATE TABLE projects(id TEXT PRIMARY KEY);
          CREATE TABLE project_lifecycle(project_id TEXT PRIMARY KEY,
            FOREIGN KEY(project_id) REFERENCES projects(id));
          INSERT INTO project_lifecycle VALUES('orphan');
        """)
    monkeypatch.setattr(storage, "DB_PATH", path)
    storage.init()
    return path


def _fk(con, name):
    return any(r[2] == "projects" and r[3] == "project_id" and r[4] == "id"
               for r in con.execute(f'PRAGMA foreign_key_list("{name}")'))


def test_fresh_database_is_certified_and_per_connection_fk_is_enabled(monkeypatch, tmp_path):
    _fresh(monkeypatch, tmp_path)
    with storage.connect() as con:
        assert con.execute('PRAGMA foreign_keys').fetchone()[0] == 1
        assert sqlite_fk_gate.gate_version(con) == 1
        assert _fk(con, 'semantic_human_review_events')
    with storage.connect() as other:
        assert other.execute('PRAGMA foreign_keys').fetchone()[0] == 1


def test_fresh_database_reinit_does_not_rewrite_gate(monkeypatch, tmp_path):
    _fresh(monkeypatch, tmp_path)
    with storage.connect() as con:
        assert con.execute(f'SELECT COUNT(*) FROM {sqlite_fk_gate.GATE_TABLE}').fetchone()[0] == 1
    storage.init()
    with storage.connect() as con:
        assert sqlite_fk_gate.gate_version(con) == 1
        assert con.execute(f'SELECT COUNT(*) FROM {sqlite_fk_gate.GATE_TABLE}').fetchone()[0] == 1


def test_successful_context_manager_closes_underlying_connection(monkeypatch, tmp_path):
    _fresh(monkeypatch, tmp_path)
    with storage.connect() as con:
        assert con.execute('SELECT 1').fetchone()[0] == 1
    with pytest.raises(sqlite3.ProgrammingError, match='closed'):
        con.execute('SELECT 1')


def test_exception_in_context_rolls_back_and_closes(monkeypatch, tmp_path):
    _fresh(monkeypatch, tmp_path)
    with pytest.raises(RuntimeError, match='Synthetic'):
        with storage.connect() as con:
            con.execute("INSERT INTO projects (id,name,filename,file_ext,dataset_path,profile,created_at) "
                        "VALUES('p','Project','file','.csv','p','{}','today')")
            raise RuntimeError('Synthetic aborted work')
    with pytest.raises(sqlite3.ProgrammingError, match='closed'):
        con.execute('SELECT 1')
    with storage.connect() as con2:
        assert con2.execute('SELECT COUNT(*) FROM projects').fetchone()[0] == 0


def test_fresh_complete_schema_declares_seven_parent_links(monkeypatch, tmp_path):
    _fresh(monkeypatch, tmp_path)
    quality._init_tables()
    from backend import investigations
    investigations.init()
    try:
        from backend import quality_approvals
    except ImportError:
        pytest.skip('Quality approval module unavailable in historical fixture')
    quality_approvals._init_tables()
    names = {
        'quality_state','quality_versions','quality_actions','quality_decisions',
        'quality_approval_receipts','investigations_v1','semantic_human_review_events',
    }
    with storage.connect() as con:
        assert con.execute('PRAGMA foreign_keys').fetchone()[0] == 1
        assert {name for name in names if _fk(con,name)} == names
        sqlite_fk_gate.validate_schema(con)


@pytest.mark.parametrize('table,sql', [
    ('quality_state', "INSERT INTO quality_state VALUES('ghost','sha',0)"),
    ('quality_versions', "INSERT INTO quality_versions VALUES('ghost',0,'[]','original','{}','today')"),
    ('quality_actions', "INSERT INTO quality_actions VALUES('a','ghost','replace','SKU','{}','approved',1,'today')"),
    ('quality_decisions', "INSERT INTO quality_decisions VALUES('ghost','finding','rejected','today')"),
    ('quality_approval_receipts', "INSERT INTO quality_approval_receipts VALUES('r','ghost',0,'sha','{}','today','tomorrow',NULL)"),
    ('investigations_v1', "INSERT INTO investigations_v1 VALUES('i','ghost','question',0,'draft','today','today')"),
    ('semantic_human_review_events', "INSERT INTO semantic_human_review_events (project_id,quality_version,column_name,hypothesis_role,hypothesis_hash,revision,decision,occurred_at) VALUES('ghost',0,'SKU','text','sha',1,'accepted','today')"),
])
def test_protected_tables_reject_project_orphans(monkeypatch, tmp_path, table, sql):
    _fresh(monkeypatch, tmp_path)
    quality._init_tables()
    from backend import investigations, quality_approvals
    investigations.init()
    quality_approvals._init_tables()
    with pytest.raises(sqlite3.IntegrityError):
        with storage.connect() as con:
            con.execute(sql)


def test_legacy_declared_orphans_are_not_auto_enforced_or_certified(monkeypatch, tmp_path):
    _open_legacy(monkeypatch, tmp_path)
    with storage.connect() as con:
        assert con.execute('PRAGMA foreign_keys').fetchone()[0] == 0
        assert sqlite_fk_gate.gate_version(con) is None
        assert con.execute('SELECT project_id FROM project_lifecycle').fetchone()[0] == 'orphan'
    with sqlite3.connect(storage.DB_PATH) as raw:
        assert not sqlite_fk_gate._gate_present(raw)


def test_bad_legacy_declared_orphans_refuse_manual_certification(monkeypatch, tmp_path):
    _open_legacy(monkeypatch, tmp_path)
    with storage.connect() as con:
        with pytest.raises(sqlite_fk_gate.ForeignKeyGateError, match='violations'):
            sqlite_fk_gate.certify_new_schema(con)
    with storage.connect() as con:
        assert sqlite_fk_gate.gate_version(con) is None
        assert con.execute('SELECT project_id FROM project_lifecycle').fetchone()[0] == 'orphan'


def test_clean_existing_database_remains_unverified_until_explicit_certification(monkeypatch, tmp_path):
    path=tmp_path/'existing.sqlite3'
    with sqlite3.connect(path) as con:
        con.execute('CREATE TABLE preexisting_stamp(value TEXT)')
        con.execute("INSERT INTO preexisting_stamp VALUES ('keep me')")
    monkeypatch.setattr(storage,'DB_PATH',path)
    storage.init()
    with storage.connect() as con:
        assert sqlite_fk_gate.gate_version(con) is None
        assert con.execute('PRAGMA foreign_keys').fetchone()[0] == 0
        assert con.execute('SELECT value FROM preexisting_stamp').fetchone()[0] == 'keep me'
        # This deliberate step models the separately authorized certification
        # of a disposable migrated copy. Runtime init never does it itself.
        sqlite_fk_gate.certify_new_schema(con)
    with storage.connect() as con:
        assert con.execute('PRAGMA foreign_keys').fetchone()[0] == 1
        assert con.execute('SELECT value FROM preexisting_stamp').fetchone()[0] == 'keep me'


def test_incomplete_schema_rejects_certification_without_gate(tmp_path):
    path=tmp_path/'incomplete.sqlite3'
    with sqlite3.connect(path) as con:
        con.execute('CREATE TABLE projects(id TEXT PRIMARY KEY)')
        with pytest.raises(sqlite_fk_gate.ForeignKeyGateError, match='incomplete'):
            sqlite_fk_gate.certify_new_schema(con)
        assert sqlite_fk_gate.gate_version(con) is None


def test_unprotected_project_relation_refuses_certification(monkeypatch,tmp_path):
    _open_legacy(monkeypatch,tmp_path)
    with sqlite3.connect(storage.DB_PATH) as con:
        con.execute('DELETE FROM project_lifecycle')
        con.execute('CREATE TABLE unprotected_records (project_id TEXT NOT NULL, other TEXT)')
        con.commit()
        with pytest.raises(sqlite_fk_gate.ForeignKeyGateError, match='coverage'):
            sqlite_fk_gate.certify_new_schema(con)
        assert sqlite_fk_gate.gate_version(con) is None


def test_malformed_existing_gate_fails_closed(monkeypatch,tmp_path):
    path = tmp_path/'malformed.sqlite3'
    with sqlite3.connect(path) as con:
        con.execute('CREATE TABLE pilotodin_fk_gate_v1(id INTEGER, version INTEGER)')
        con.execute('INSERT INTO pilotodin_fk_gate_v1 VALUES(1,999)')
    monkeypatch.setattr(storage,'DB_PATH',path)
    with pytest.raises(sqlite_fk_gate.ForeignKeyGateError, match='Unrecognized'):
        storage.connect()


def test_transaction_begun_prevents_late_fk_activation(tmp_path):
    path=tmp_path/'tx.sqlite3'
    with sqlite3.connect(path) as con:
        con.execute('CREATE TABLE pilotodin_fk_gate_v1(id INTEGER, version INTEGER)')
        con.execute('INSERT INTO pilotodin_fk_gate_v1 VALUES(1,1)')
        con.commit()
        con.execute('BEGIN')
        with pytest.raises(sqlite_fk_gate.ForeignKeyGateError, match='transaction'):
            sqlite_fk_gate.configure_connection(con)


def test_schema_recertification_not_allowed(monkeypatch,tmp_path):
    _fresh(monkeypatch,tmp_path)
    with storage.connect() as con:
        with pytest.raises(sqlite_fk_gate.ForeignKeyGateError, match='already certified'):
            sqlite_fk_gate.certify_new_schema(con)


def test_optional_table_created_after_fresh_seal_stays_protected(monkeypatch,tmp_path):
    _fresh(monkeypatch,tmp_path)
    from backend import investigations, quality_approvals
    investigations.init()
    quality_approvals._init_tables()
    with storage.connect() as con:
        assert _fk(con,'investigations_v1')
        assert _fk(con,'quality_approval_receipts')
        assert con.execute('PRAGMA foreign_keys').fetchone()[0] == 1


def _legacy_full_schema_without_seven_fks(monkeypatch, tmp_path):
    """Synthesize the current core schema plus the exact seven old FK gaps."""
    path=tmp_path/'legacy_full.sqlite3'
    # File pre-exists before initialization, so runtime never seals it.
    with sqlite3.connect(path) as con:
        con.execute('CREATE TABLE legacy_compatibility_note (value TEXT)')
        con.execute("INSERT INTO legacy_compatibility_note VALUES ('preserved')")
    monkeypatch.setattr(storage,'DB_PATH',path)
    storage.init()
    with sqlite3.connect(path) as con:
        # Existing core table cannot be ALTERed by CREATE IF NOT EXISTS.
        con.execute('DROP TABLE semantic_human_review_events')
        con.executescript('''
          CREATE TABLE semantic_human_review_events (
            event_id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id TEXT NOT NULL, quality_version INTEGER NOT NULL,
            column_name TEXT NOT NULL, hypothesis_role TEXT NOT NULL,
            hypothesis_hash TEXT NOT NULL, revision INTEGER NOT NULL,
            previous_decision TEXT, decision TEXT NOT NULL, occurred_at TEXT NOT NULL);
          CREATE TABLE quality_state(project_id TEXT PRIMARY KEY,
            original_sha256 TEXT NOT NULL,current_version INTEGER NOT NULL DEFAULT 0);
          CREATE TABLE quality_versions(project_id TEXT NOT NULL,version INTEGER NOT NULL,
            operations_json TEXT NOT NULL,event TEXT NOT NULL,details_json TEXT NOT NULL,
            created_at TEXT NOT NULL,PRIMARY KEY(project_id,version));
          CREATE TABLE quality_actions(id TEXT PRIMARY KEY, project_id TEXT NOT NULL,
            kind TEXT NOT NULL,column_name TEXT NOT NULL,params_json TEXT NOT NULL,
            source TEXT NOT NULL,affected_rows INTEGER NOT NULL,created_at TEXT NOT NULL);
          CREATE TABLE quality_decisions(project_id TEXT NOT NULL,issue_id TEXT NOT NULL,
            status TEXT NOT NULL,created_at TEXT NOT NULL,PRIMARY KEY(project_id,issue_id));
          CREATE TABLE quality_approval_receipts(proposal_id TEXT PRIMARY KEY,
            project_id TEXT NOT NULL,expected_version INTEGER NOT NULL,
            proposal_hash TEXT NOT NULL,payload_json TEXT NOT NULL,
            issued_at TEXT NOT NULL,expires_at TEXT NOT NULL,consumed_at TEXT);
          CREATE TABLE investigations_v1(id TEXT PRIMARY KEY,project_id TEXT NOT NULL,
            objective TEXT NOT NULL,dataset_version INTEGER NOT NULL,status TEXT NOT NULL,
            created_at TEXT NOT NULL,updated_at TEXT NOT NULL);
          CREATE TABLE evidence_v1(id TEXT PRIMARY KEY,investigation_id TEXT NOT NULL,
            operation TEXT NOT NULL,params TEXT NOT NULL,result TEXT NOT NULL,
            dataset_version INTEGER NOT NULL,tool_version TEXT NOT NULL,
            status TEXT NOT NULL,created_at TEXT NOT NULL,
            FOREIGN KEY(investigation_id) REFERENCES investigations_v1(id));
        ''')
        con.execute("INSERT INTO projects VALUES('p1','Project','f.csv','.csv','data','{}','today')")
        con.execute("INSERT INTO quality_state VALUES('p1','hash',0)")
        con.execute("INSERT INTO quality_versions VALUES('p1',0,'[]','original','{}','today')")
        con.execute("INSERT INTO quality_actions VALUES('a1','p1','replace','SKU','{}','approved',1,'today')")
        con.execute("INSERT INTO quality_decisions VALUES('p1','f1','applied','today')")
        con.execute("INSERT INTO quality_approval_receipts VALUES('r1','p1',0,'hash','{}','today','tomorrow',NULL)")
        con.execute("INSERT INTO investigations_v1 VALUES('i1','p1','question',0,'draft','today','today')")
        con.execute("INSERT INTO evidence_v1 VALUES('e1','i1','evidence','{}','{}',0,'local','completed','today')")
        con.execute("INSERT INTO semantic_human_review_events (event_id,project_id,quality_version,column_name,hypothesis_role,hypothesis_hash,revision,decision,occurred_at) VALUES(75,'p1',0,'SKU','identifier','sha',1,'accepted','today')")
    return path


def test_disposable_migration_then_explicit_seal_enforces_all_links(monkeypatch,tmp_path):
    from backend.sqlite_fk_audit import audit_database
    from backend.sqlite_fk_migration import migrate_disposable_backup
    legacy=_legacy_full_schema_without_seven_fks(monkeypatch,tmp_path)
    before=audit_database(legacy)
    assert len(before['undeclared_project_links'])==7
    output=tmp_path/'migrated-copy.sqlite3'
    result=migrate_disposable_backup(legacy,output,acknowledge_disposable=True)
    assert len(result['migrated_tables'])==7
    assert result['production_enforcement_enabled'] is False
    with sqlite3.connect(output) as con:
        sqlite_fk_gate.certify_new_schema(con)
    monkeypatch.setattr(storage,'DB_PATH',output)
    with storage.connect() as verified:
        assert verified.execute('PRAGMA foreign_keys').fetchone()[0]==1
        assert verified.execute("SELECT value FROM legacy_compatibility_note").fetchone()[0]=='preserved'
        assert verified.execute("SELECT event_id FROM semantic_human_review_events").fetchone()[0]==75
        assert verified.execute("SELECT result FROM evidence_v1").fetchone()[0]=='{}'
        with pytest.raises(sqlite3.IntegrityError):
            verified.execute("INSERT INTO quality_decisions VALUES('ghost','issue','rejected','today')")
    # The original legacy input remains unsealed and its records preserved.
    monkeypatch.setattr(storage,'DB_PATH',legacy)
    with storage.connect() as older:
        assert older.execute('PRAGMA foreign_keys').fetchone()[0]==0
        assert older.execute("SELECT COUNT(*) FROM quality_decisions").fetchone()[0]==1
        assert sqlite_fk_gate.gate_version(older) is None


def test_disposable_migration_refuses_orphan_and_never_certifies_source(monkeypatch,tmp_path):
    from backend.sqlite_fk_migration import migrate_disposable_backup, MigrationRefused
    legacy=_legacy_full_schema_without_seven_fks(monkeypatch,tmp_path)
    with sqlite3.connect(legacy) as con:
        con.execute("INSERT INTO quality_decisions VALUES('orphan','f2','applied','today')")
    output=tmp_path/'refused-copy.sqlite3'
    with pytest.raises(MigrationRefused):
        migrate_disposable_backup(legacy,output,acknowledge_disposable=True)
    assert not output.exists()
    with storage.connect() as con:
        assert con.execute('PRAGMA foreign_keys').fetchone()[0]==0
        assert sqlite_fk_gate.gate_version(con) is None
        assert con.execute("SELECT COUNT(*) FROM quality_decisions").fetchone()[0]==2
