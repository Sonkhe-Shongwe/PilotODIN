"""B5 integration: startup, certified schema and backup inventory, no native app."""
import hashlib
import sqlite3
from pathlib import Path

import pytest
from tests.fixture_http import fixture_client
from backend import export_publication as ledger, main, maintenance_backup, quality, storage, sqlite_fk_gate
from backend.artifact_publication import PublicationError


@pytest.fixture
def fixture(tmp_path, monkeypatch):
    home=tmp_path/"workspace"
    (home/"datasets").mkdir(parents=True)
    (home/"models").mkdir()
    (home/"export_tmp").mkdir()
    monkeypatch.setattr(storage,"HOME",home)
    monkeypatch.setattr(storage,"DB_PATH",home/"pilotodin.sqlite3")
    # No optional provider connection or network work in this fixture.
    monkeypatch.setattr(main.ai_provider,"config_status",lambda: {"cloud_enabled":False})
    storage.init()
    quality._init_tables()
    raw=b"Region,Revenue\nNorth,1\nSouth,2\n"
    path=home/"datasets"/"source.csv"
    path.write_bytes(raw)
    pid=storage.save_project("Generated",path.name,".csv",path,{"rows":2},
                             original_sha256=hashlib.sha256(raw).hexdigest())
    return home,pid,path,raw


def test_new_schema_keeps_fk_certification_and_idempotent_init(fixture):
    home,pid,path,raw=fixture
    storage.init()
    with storage.connect() as con:
        assert sqlite_fk_gate.gate_version(con)==1
        assert con.execute("PRAGMA foreign_keys").fetchone()[0]==1
        sqlite_fk_gate.validate_schema(con)
        assert ledger.validate_existing_schema(con)
        assert not list(con.execute("PRAGMA foreign_key_list(export_publications_v1)"))
    r=storage.begin_export_publication(pid,0,"csv")
    assert r.project_id==pid and r.subject_id==pid
    assert path.read_bytes()==raw
    storage.init()
    with storage.connect() as con:
        assert ledger.read(con,r.operation_id)==r


def test_startup_classifies_pending_without_touching_any_scratch(fixture):
    home,pid,path,raw=fixture
    intent=storage.begin_export_publication(pid,0,"csv")
    active=storage.begin_export_publication(pid,0,"xlsx")
    active=storage.advance_export_publication(active,"staged",expected_bytes=8,sha256="a"*64)
    active=storage.advance_export_publication(active,"ready")
    active=storage.advance_export_publication(active,"transferring")
    terminal=storage.begin_export_publication(pid,0,"csv")
    terminal=storage.advance_export_publication(terminal,"blocked",reason="collision")
    scratch=home/"export_tmp"
    entries={intent.filename:b"unverified",active.filename:b"mismatch",terminal.filename:b"collision",
             "pilotodin-unknown.csv":b"foreign"}
    for name,data in entries.items():
        (scratch/name).write_bytes(data)
    with fixture_client(main.app) as client:
        with storage.connect() as con:
            for old in (intent,active):
                actual=ledger.read(con,old.operation_id)
                assert actual.state=="interrupted"
                assert actual.expected_bytes==old.expected_bytes and actual.sha256==old.sha256
            assert ledger.read(con,terminal.operation_id)==terminal
        assert storage.recover_export_publications()==0
    assert {p.name:p.read_bytes() for p in scratch.iterdir()}==entries
    assert path.read_bytes()==raw


def test_legacy_db_additive_schema_without_recertification(fixture):
    home,pid,path,raw=fixture
    with storage.connect() as con:
        con.execute("DROP TABLE export_publications_v1")
        con.execute("DROP TABLE pilotodin_fk_gate_v1")
    storage.init()
    with storage.connect() as con:
        assert ledger.validate_existing_schema(con)
        assert sqlite_fk_gate.gate_version(con) is None
        assert con.execute("PRAGMA foreign_keys").fetchone()[0]==0
    assert path.read_bytes()==raw


def test_backup_inventory_refuses_unsettled_and_excludes_scratch(fixture):
    home,pid,path,raw=fixture
    r=storage.begin_export_publication(pid,0,"csv")
    scratch=home/"export_tmp"/r.filename
    scratch.write_bytes(b"foreign")
    with sqlite3.connect(storage.DB_PATH) as con:
        con.execute("PRAGMA query_only=ON")
        with pytest.raises(maintenance_backup.SnapshotBlocked,match="Unsettled export"):
            maintenance_backup._inventory(con,home,lambda:None,lambda:None)
    assert storage.recover_export_publications()==1
    with sqlite3.connect(storage.DB_PATH) as con:
        con.execute("PRAGMA query_only=ON")
        plan=maintenance_backup._inventory(con,home,lambda:None,lambda:None)
    assert set(plan)=={"datasets/source.csv"}
    assert scratch.read_bytes()==b"foreign" and path.read_bytes()==raw


def test_deletion_impact_counts_retained_receipts_without_authorizing_deletion(fixture):
    home,pid,path,raw=fixture
    r=storage.begin_export_publication(pid,0,"csv")
    result=main.project_delete_impact.impact(pid,0)
    assert result["deletion_available"] is False
    assert "export_publications_v1" not in result["unclassified_tables"]
    record=next(row for row in result["records"] if row["key"]=="export_publications_v1")
    assert record["count"]==1
    with storage.connect() as con:
        assert ledger.read(con,r.operation_id)==r
    assert path.read_bytes()==raw


def test_conflicting_schema_is_refused_without_rewrite(fixture):
    home,pid,path,raw=fixture
    with storage.connect() as con:
        con.execute("DROP TABLE export_publications_v1")
        con.execute("CREATE TABLE export_publications_v1(subject_id TEXT)")
    with pytest.raises(PublicationError,match="Incompatible"):
        storage.init()
    with storage.connect() as con:
        assert [row[1] for row in con.execute("PRAGMA table_info(export_publications_v1)")]==["subject_id"]
    assert path.read_bytes()==raw
