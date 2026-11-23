"""CF-03: synthetic-only read-only FK audit, never owner's database."""
from __future__ import annotations

import hashlib
from pathlib import Path
import sqlite3

import pytest

from backend.sqlite_fk_audit import audit_database


def _database(tmp_path: Path) -> Path:
    db = tmp_path / "generated.sqlite3"
    with sqlite3.connect(db) as con:
        con.executescript("""
            CREATE TABLE projects(id TEXT PRIMARY KEY);
            CREATE TABLE experiments(
                id TEXT PRIMARY KEY, project_id TEXT NOT NULL,
                FOREIGN KEY(project_id) REFERENCES projects(id));
            CREATE TABLE quality_state(project_id TEXT PRIMARY KEY, version INTEGER);
            CREATE TABLE semantic_business_context(
                project_id TEXT NOT NULL,
                FOREIGN KEY(project_id) REFERENCES projects(id));
        """)
    return db


def _insert(db, sql, args=()):
    with sqlite3.connect(db) as con:  # Deliberate legacy FK=OFF fixture.
        assert con.execute("PRAGMA foreign_keys").fetchone()[0] == 0
        con.execute(sql, args)


def test_clean_generated_database_reports_coverage_gap_without_orphan(tmp_path):
    db = _database(tmp_path)
    _insert(db, "INSERT INTO projects VALUES ('a')")
    _insert(db, "INSERT INTO experiments VALUES ('e','a')")
    _insert(db, "INSERT INTO quality_state VALUES ('a',0)")
    report = audit_database(db)
    assert report["audit_complete"]
    assert report["declared_fk_violations"] == []
    assert report["undeclared_project_links"] == [{"table": "quality_state", "orphan_count": 0}]
    assert not report["full_project_fk_coverage"]
    assert report["detected_orphan_links"] == 0
    assert report["enforcement_authorized"] is False


def test_fk_check_reports_declared_orphan_with_counts_only(tmp_path):
    db = _database(tmp_path)
    _insert(db, "INSERT INTO experiments VALUES ('secret-record-id','ghost-project-id')")
    report = audit_database(db)
    assert report["declared_fk_violations"] == [
        {"child_table": "experiments", "parent_table": "projects", "count": 1}]
    assert report["detected_orphan_links"] == 1
    assert "secret-record-id" not in str(report)
    assert "ghost-project-id" not in str(report)


def test_undeclared_project_link_orphan_is_counted(tmp_path):
    db = _database(tmp_path)
    _insert(db, "INSERT INTO quality_state VALUES ('ghost-project-id',0)")
    report = audit_database(db)
    assert report["declared_fk_violations"] == []
    assert report["unprotected_project_orphans"] == 1
    assert report["detected_orphan_links"] == 1


def test_database_bytes_unchanged_by_audit(tmp_path):
    db = _database(tmp_path)
    before = hashlib.sha256(db.read_bytes()).hexdigest()
    audit_database(db)
    after = hashlib.sha256(db.read_bytes()).hexdigest()
    assert before == after
    assert sorted(x.name for x in tmp_path.iterdir()) == [db.name]


def test_missing_database_rejected_without_creating_it(tmp_path):
    db = tmp_path / "absent.sqlite3"
    with pytest.raises(ValueError):
        audit_database(db)
    assert not db.exists()


def test_symlink_is_rejected(tmp_path):
    db = _database(tmp_path)
    link = tmp_path / "link.sqlite3"
    try:
        link.symlink_to(db)
    except OSError:
        pytest.skip("Symlink creation not enabled")
    with pytest.raises(ValueError):
        audit_database(link)


def test_incomplete_schema_cannot_be_considered_clean(tmp_path):
    db = tmp_path / "generated.sqlite3"
    with sqlite3.connect(db) as con:
        con.execute("CREATE TABLE unconnected(project_id TEXT)")
    report = audit_database(db)
    assert report["audit_complete"] is False
    assert report["project_table_present"] is False
    assert report["enforcement_authorized"] is False


def test_pragmas_only_enforce_constraints_declared_in_schema(tmp_path):
    db = _database(tmp_path)
    with sqlite3.connect(db) as con:
        con.execute("PRAGMA foreign_keys=ON")
        assert con.execute("PRAGMA foreign_keys").fetchone()[0] == 1
        with pytest.raises(sqlite3.IntegrityError):
            con.execute("INSERT INTO experiments VALUES ('e','no-project')")
        # This missing Quality FK is NOT enforced by merely turning on PRAGMA.
        con.execute("INSERT INTO quality_state VALUES ('no-project',0)")
    report = audit_database(db)
    assert report["unprotected_project_orphans"] == 1


def test_current_source_schema_inventory_finds_seven_unguarded_project_links(tmp_path):
    """Source-derived table subset from the 22 Nov 2026 published branch."""
    db = tmp_path / "current-schema-subset.sqlite3"
    with sqlite3.connect(db) as con:
        con.executescript("""
            CREATE TABLE projects (id TEXT PRIMARY KEY);
            CREATE TABLE project_lifecycle (
                project_id TEXT PRIMARY KEY,
                FOREIGN KEY(project_id) REFERENCES projects(id));
            CREATE TABLE experiments (
                id TEXT PRIMARY KEY, project_id TEXT NOT NULL,
                FOREIGN KEY(project_id) REFERENCES projects(id));
            CREATE TABLE semantic_business_context (
                project_id TEXT, FOREIGN KEY(project_id) REFERENCES projects(id));
            CREATE TABLE semantic_human_review_events (
                event_id INTEGER PRIMARY KEY, project_id TEXT NOT NULL);
            CREATE TABLE quality_state (
                project_id TEXT PRIMARY KEY, original_sha256 TEXT, current_version INTEGER);
            CREATE TABLE quality_versions (
                project_id TEXT, version INTEGER, PRIMARY KEY(project_id,version));
            CREATE TABLE quality_actions (id TEXT PRIMARY KEY, project_id TEXT);
            CREATE TABLE quality_decisions (project_id TEXT, issue_id TEXT);
            CREATE TABLE quality_approval_receipts (
                proposal_id TEXT PRIMARY KEY, project_id TEXT NOT NULL);
            CREATE TABLE investigations_v1 (id TEXT PRIMARY KEY, project_id TEXT NOT NULL);
            CREATE TABLE evidence_v1 (
                id TEXT PRIMARY KEY, investigation_id TEXT,
                FOREIGN KEY(investigation_id) REFERENCES investigations_v1(id));
        """)
    report = audit_database(db)
    assert {item["table"] for item in report["undeclared_project_links"]} == {
        "semantic_human_review_events", "quality_state", "quality_versions",
        "quality_actions", "quality_decisions", "quality_approval_receipts",
        "investigations_v1",
    }
    assert report["declared_foreign_key_count"] == 4
    assert report["detected_orphan_links"] == 0
    assert not report["full_project_fk_coverage"]


def test_enabling_foreign_keys_does_not_retroactively_repair_legacy_data(tmp_path):
    db = _database(tmp_path)
    _insert(db, "INSERT INTO experiments VALUES ('old-orphan','missing')")
    with sqlite3.connect(db) as con:
        con.execute("PRAGMA foreign_keys=ON")
        assert con.execute("PRAGMA foreign_keys").fetchone()[0] == 1
        assert con.execute("SELECT id FROM experiments").fetchone()[0] == "old-orphan"
        with pytest.raises(sqlite3.IntegrityError):
            con.execute("INSERT INTO experiments VALUES ('new-orphan','missing')")
    assert audit_database(db)["declared_fk_violations"] == [
        {"child_table": "experiments", "parent_table": "projects", "count": 1}]


def test_untrusted_table_names_are_properly_quoted(tmp_path):
    db = tmp_path / "generated.sqlite3"
    table_name = 'weird"\' project table'
    with sqlite3.connect(db) as con:
        con.execute("CREATE TABLE projects(id TEXT PRIMARY KEY)")
        con.execute('CREATE TABLE "weird""\' project table"(project_id TEXT)')
        con.execute('INSERT INTO "weird""\' project table" VALUES (?)', ('missing',))
    report = audit_database(db)
    assert report["undeclared_project_links"] == [{"table": table_name, "orphan_count": 1}]


def test_all_project_tables_covered_when_schema_declares_parent_fk(tmp_path):
    db = _database(tmp_path)
    with sqlite3.connect(db) as con:
        con.execute("DROP TABLE quality_state")
        con.execute("CREATE TABLE quality_state(project_id TEXT PRIMARY KEY, "
                    "FOREIGN KEY(project_id) REFERENCES projects(id))")
    report = audit_database(db)
    assert report["audit_complete"]
    assert report["full_project_fk_coverage"]
    assert report["undeclared_project_links"] == []
    assert report["enforcement_authorized"] is False
