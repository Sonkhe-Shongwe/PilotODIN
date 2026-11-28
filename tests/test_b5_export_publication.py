"""B5 receipt tests: generated disposable SQLite, no owner files or native app."""
import sqlite3

import pytest
from backend import export_publication as ledger
from backend.artifact_publication import PublicationError, begin_durable

PID = "a"*32
DIGEST = "b"*64


@pytest.fixture
def db(tmp_path):
    con = sqlite3.connect(tmp_path/"fixture.sqlite3")
    con.executescript("""
        CREATE TABLE projects(id TEXT PRIMARY KEY);
        CREATE TABLE quality_versions(project_id TEXT,version INTEGER);
        CREATE TABLE project_lifecycle(project_id TEXT,archived_at TEXT);
    """)
    con.execute("INSERT INTO projects VALUES (?)",(PID,))
    con.execute("INSERT INTO quality_versions VALUES (?,0)",(PID,))
    ledger.ensure_schema(con)
    con.commit()
    yield con
    con.close()


def intent(con, i=1, fmt="csv"):
    return ledger.insert_intent(con,f"{i:032x}",PID,0,fmt)


def stage(con, receipt, size=8):
    return ledger.advance(con,receipt,"staged",expected_bytes=size,sha256=DIGEST)


@pytest.mark.parametrize("fmt",["csv","xlsx"])
def test_complete_lifecycle(db,fmt):
    begin_durable(db)
    r=intent(db,fmt=fmt)
    assert r.filename == "pilotodin-"+r.operation_id+"."+fmt
    r=stage(db,r,ledger.MAX_EXPORT_BYTES)
    for state in ("ready","transferring","released"):
        r=ledger.advance(db,r,state)
    db.commit()
    assert ledger.read(db,r.operation_id)==r
    assert r.expected_bytes==ledger.MAX_EXPORT_BYTES and r.sha256==DIGEST
    assert ledger.pending_page(db)==[]
    begin_durable(db)
    with pytest.raises(PublicationError,match="Illegal"):
        ledger.advance(db,r,"interrupted",reason="cancelled")
    db.rollback()


def test_stage_over_limit_and_stale_transition(db):
    begin_durable(db)
    r=intent(db)
    with pytest.raises(PublicationError,match="payload"):
        stage(db,r,ledger.MAX_EXPORT_BYTES+1)
    assert ledger.read(db,r.operation_id)==r
    staged=stage(db,r)
    with pytest.raises(PublicationError,match="changed"):
        stage(db,r)
    with pytest.raises(PublicationError,match="immutable"):
        ledger.advance(db,staged,"ready",expected_bytes=7,sha256=DIGEST)
    with pytest.raises(PublicationError,match="Illegal"):
        ledger.advance(db,staged,"released")
    db.rollback()
    assert ledger.read(db,r.operation_id) is None


@pytest.mark.parametrize("state",["intent","staged","ready","transferring"])
def test_interrupted_recovery_preserves_payload_and_is_idempotent(db,tmp_path,state):
    begin_durable(db)
    r=intent(db)
    if state!="intent":
        r=stage(db,r)
        if state in ("ready","transferring"):
            r=ledger.advance(db,r,"ready")
        if state=="transferring":
            r=ledger.advance(db,r,"transferring")
    db.commit()
    foreign=tmp_path/r.filename
    foreign.write_bytes(b"unknown")
    begin_durable(db)
    assert ledger.reconcile_pending(db)==1
    db.commit()
    actual=ledger.read(db,r.operation_id)
    assert actual.state=="interrupted" and actual.expected_bytes==r.expected_bytes
    assert actual.sha256==r.sha256 and foreign.read_bytes()==b"unknown"
    begin_durable(db)
    assert ledger.reconcile_pending(db)==0
    db.commit()
    assert ledger.read(db,r.operation_id)==actual


def test_admission_and_recovery_pages(db,monkeypatch):
    monkeypatch.setattr(ledger,"MAX_PENDING",3)
    begin_durable(db)
    for i in (1,2,3):
        intent(db,i)
    with pytest.raises(PublicationError,match="pending"):
        intent(db,4)
    db.commit()
    page=ledger.pending_page(db,limit=2)
    assert [r.operation_id for r in page]==[f"{i:032x}" for i in (1,2)]
    assert len(ledger.pending_page(db,after=page[-1].operation_id))==1
    begin_durable(db)
    assert ledger.reconcile_pending(db)==3
    db.commit()
    assert ledger.pending_page(db)==[]


def test_reject_unknown_archive_and_unsafe_id(db):
    begin_durable(db)
    with pytest.raises(PublicationError,match="unavailable"):
        ledger.insert_intent(db,"1"*32,PID,99,"csv")
    with pytest.raises(PublicationError,match="Invalid"):
        ledger.insert_intent(db,"../foreign",PID,0,"csv")
    db.execute("INSERT INTO project_lifecycle VALUES (?,?)",(PID,"archived"))
    with pytest.raises(PublicationError,match="unavailable"):
        intent(db)
    db.rollback()


def test_schema_refuses_weaker_table(db):
    ledger.ensure_schema(db)
    db.execute("DROP TABLE export_publications_v1")
    db.execute("CREATE TABLE export_publications_v1(operation_id TEXT)")
    with pytest.raises(PublicationError,match="Incompatible"):
        ledger.ensure_schema(db)


def test_recovery_overflow_rolls_back(db,monkeypatch):
    begin_durable(db)
    for i in (1,2,3):
        intent(db,i)
    db.commit()
    monkeypatch.setattr(ledger,"MAX_PENDING",2)
    begin_durable(db)
    with pytest.raises(PublicationError,match="recovery limit"):
        ledger.reconcile_pending(db)
    db.rollback()
    assert len(ledger.pending_page(db))==3
