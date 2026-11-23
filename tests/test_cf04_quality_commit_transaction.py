"""CF-04 Stage B: real pandas and SQLite commit race regressions.

Every test uses an isolated temporary database and never touches an owner workspace.
The approved source module is imported normally; tests only control scheduling
at the read-only validation boundary to exercise deterministic races.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from backend import quality, quality_approvals as approvals, storage


@pytest.fixture
def case(monkeypatch, tmp_path):
    home=tmp_path/'cf04-workspace'
    (home/'datasets').mkdir(parents=True)
    (home/'models').mkdir()
    monkeypatch.setattr(storage,'HOME',home)
    monkeypatch.setattr(storage,'DB_PATH',home/'pilotodin.sqlite3')
    storage.init()
    quality._init_tables()
    approvals._init_tables()
    with storage.connect() as con:
        con.execute('CREATE TABLE IF NOT EXISTS project_lifecycle (project_id TEXT PRIMARY KEY, archived_at TEXT)')

    # Older Build D reference lacks this fence, so the historical adapter
    # uses the same active/archive contract as the current source.
    if not hasattr(quality,'_require_active_for_write'):
        def require_active(con,pid):
            assert con.in_transaction
            row=con.execute('SELECT archived_at FROM project_lifecycle WHERE project_id=?',(pid,)).fetchone()
            if row is not None and row['archived_at'] is not None:
                raise quality.QualityError('Project is archived',409)
        monkeypatch.setattr(quality,'_require_active_for_write',require_active,raising=False)

    lines=['CustomerID,Region,Revenue']
    for i in range(36):
        region='Gauteng' if i<18 else ' Gauteng ' if i<21 else 'Mpumalanga'
        revenue='' if i==35 else str(i*10+10)
        lines.append(f'{i:04d},{region},{revenue}')
    raw=('\n'.join(lines)+'\n').encode()
    path=home/'datasets'/'generated.csv'; path.write_bytes(raw)
    pid=storage.save_project('Generated','generated.csv','.csv',path,{'rows':36})
    if hasattr(quality,'register'):
        quality.register(pid)
    else:
        with storage.connect() as con:
            con.execute('INSERT INTO quality_state VALUES (?,?,0)',(pid,hashlib.sha256(raw).hexdigest()))
            con.execute('INSERT INTO quality_versions VALUES (?,?,?,?,?,?)',(pid,0,'[]','original','{}',storage.now()))
    # Source-revision compatibility shim: October Build D used self-healing
    # _ensure; the current November source fails closed for missing hashes.
    historical_ensure=quality._ensure
    def no_legacy_backfill(con,p):
        row=con.execute('SELECT original_sha256 FROM quality_state WHERE project_id=?',
                        (p['id'],)).fetchone()
        if row is None:
            raise quality.QualityError('The original dataset has no recorded checksum',409)
        return historical_ensure(con,p)
    monkeypatch.setattr(quality,'_ensure',no_legacy_backfill)
    return pid,path,raw


def issue(pid,kind,column=None):
    return next(x for x in quality.snapshot(pid)['issues']
                if x['kind']==kind and (column is None or x['column']==column))


def make_receipt(pid,kind='approve',*,version=0,**kw):
    data=approvals.ProposalRequest(operation=kind,expected_version=version,**kw)
    return approvals.prepare(pid,data)


def commit(pid,receipt):
    return approvals.commit(pid,approvals.ApprovalCommit(proposal_id=receipt['proposal_id'],
                                                         proposal_hash=receipt['proposal_hash']))


def receipt_consumed(pid,receipt):
    with storage.connect() as con:
        row=con.execute('SELECT consumed_at FROM quality_approval_receipts WHERE proposal_id=?',
                        (receipt['proposal_id'],)).fetchone()
    return row['consumed_at'] is not None


def audit_counts(pid):
    with storage.connect() as con:
        return tuple(con.execute(f'SELECT COUNT(*) FROM {t} WHERE project_id=?',(pid,)).fetchone()[0]
                     for t in ['quality_actions','quality_versions'])


def inject_after_validation(monkeypatch, action):
    original=approvals._stage_commit
    def wrapped(con,p,version,ops,payload):
        assert not con.in_transaction
        result=original(con,p,version,ops,payload)
        action(p['id'])
        return result
    monkeypatch.setattr(approvals,'_stage_commit',wrapped)


def writer(sql,params=()):
    with sqlite3.connect(storage.DB_PATH,timeout=0.3) as con:
        con.execute('BEGIN IMMEDIATE')
        con.execute(sql,params)


def test_approved_change_preserves_source_and_receipt_is_once(case):
    pid,path,raw=case
    target=issue(pid,'whitespace')
    receipt=make_receipt(pid,issue_id=target['id'])
    result=commit(pid,receipt)
    assert result['approved'] and result['version']==1 and result['count']==1
    assert quality.current_version(pid)==1 and receipt_consumed(pid,receipt)
    assert path.read_bytes()==raw
    assert quality.current_data(pid)[0]['Region'].str.startswith(' ').sum()==0
    with pytest.raises(quality.QualityError) as exc:commit(pid,receipt)
    assert exc.value.status==409


def test_preflight_allows_parallel_writer_without_long_read_transaction(case,monkeypatch):
    pid,_,_=case
    receipt=make_receipt(pid,issue_id=issue(pid,'whitespace')['id'])
    def insert_unrelated(_pid):
        with sqlite3.connect(storage.DB_PATH,timeout=0.3) as other:
            other.execute('BEGIN IMMEDIATE')
            other.execute('CREATE TABLE IF NOT EXISTS unrelated (x TEXT)')
            other.execute('INSERT INTO unrelated VALUES (?)',('writer-acquired',))
    inject_after_validation(monkeypatch,insert_unrelated)
    assert commit(pid,receipt)['version']==1
    with storage.connect() as con:
        assert con.execute('SELECT x FROM unrelated').fetchone()[0]=='writer-acquired'


def test_version_changed_during_preflight_fails_without_consuming_receipt(case,monkeypatch):
    pid,path,raw=case
    receipt=make_receipt(pid,issue_id=issue(pid,'whitespace')['id'])
    def mutate(pid):
        with sqlite3.connect(storage.DB_PATH) as con:
            con.execute('INSERT INTO quality_versions VALUES (?,?,?,?,?,?)',(pid,1,'[]','restore','{}',storage.now()))
            con.execute('UPDATE quality_state SET current_version=1 WHERE project_id=?',(pid,))
    inject_after_validation(monkeypatch,mutate)
    with pytest.raises(quality.QualityError) as exc:commit(pid,receipt)
    assert exc.value.status==409
    assert not receipt_consumed(pid,receipt) and audit_counts(pid)==(0,2) and path.read_bytes()==raw


def test_decision_change_during_preflight_fails_closed(case,monkeypatch):
    pid,_,_=case
    target=issue(pid,'whitespace')['id']; receipt=make_receipt(pid,issue_id=target)
    inject_after_validation(monkeypatch,lambda p:writer('INSERT INTO quality_decisions VALUES(?,?,?,?)',
                                      (p,target,'rejected',storage.now())))
    with pytest.raises(quality.QualityError) as exc:commit(pid,receipt)
    assert exc.value.status==409
    assert audit_counts(pid)==(0,1) and not receipt_consumed(pid,receipt)


def test_archive_during_preflight_fails_closed(case,monkeypatch):
    pid,_,_=case
    receipt=make_receipt(pid,issue_id=issue(pid,'whitespace')['id'])
    inject_after_validation(monkeypatch,lambda p:writer(
        'INSERT INTO project_lifecycle (project_id,revision,archived_at) VALUES (?,1,?) '
        'ON CONFLICT(project_id) DO UPDATE SET archived_at=excluded.archived_at,revision=excluded.revision',
        (p,'2026-11-23')))
    with pytest.raises(quality.QualityError) as exc:commit(pid,receipt)
    assert exc.value.status==409 and not receipt_consumed(pid,receipt)


def test_source_mutation_during_preflight_cannot_commit(case,monkeypatch):
    pid,path,raw=case
    receipt=make_receipt(pid,issue_id=issue(pid,'whitespace')['id'])
    inject_after_validation(monkeypatch,lambda _:path.write_bytes(raw.replace(b'Mpumalanga',b'MPUMALANGA')))
    with pytest.raises(quality.QualityError) as exc:commit(pid,receipt)
    assert exc.value.status==409
    assert not receipt_consumed(pid,receipt) and audit_counts(pid)==(0,1)


def test_commit_never_calls_slow_record_action_or_replays_under_writer_lock(case,monkeypatch):
    pid,_,_=case
    receipt=make_receipt(pid,issue_id=issue(pid,'whitespace')['id'])
    def never(*_a,**_kw):raise AssertionError('old replay under lock')
    monkeypatch.setattr(quality,'_record_action',never)
    original=quality._materialize
    def spy(con,p,ops):
        assert not con.in_transaction, 'dataset replay occurred inside writer transaction'
        return original(con,p,ops)
    monkeypatch.setattr(quality,'_materialize',spy)
    assert commit(pid,receipt)['version']==1


def test_median_imputation_matches_reviewed_count(case):
    pid,path,raw=case
    target=issue(pid,'missing','Revenue')
    receipt=make_receipt(pid,'impute',issue_id=target['id'],column='Revenue')
    assert commit(pid,receipt)['applied'][0]['affected_rows']==1
    frame,ver=quality.current_data(pid)
    assert ver==1 and int(frame['Revenue'].isna().sum())==0 and path.read_bytes()==raw


def test_autopilot_retains_reviewed_scope_and_history(case):
    pid,path,raw=case
    receipt=make_receipt(pid,'autopilot')
    result=commit(pid,receipt)
    assert result['count']==len(receipt['steps'])>0
    assert result['version']==len(receipt['steps'])
    assert audit_counts(pid)==(len(receipt['steps']),len(receipt['steps'])+1)
    assert path.read_bytes()==raw


def test_undo_and_restore_do_not_replay_during_write_lock(case,monkeypatch):
    pid,path,raw=case
    target=issue(pid,'whitespace')['id']
    one=make_receipt(pid,issue_id=target)
    action=commit(pid,one)['applied'][0]['id']
    undo=make_receipt(pid,'undo',version=1,action_id=action)
    original=quality._materialize
    def spy(con,p,ops):
        assert not con.in_transaction
        return original(con,p,ops)
    monkeypatch.setattr(quality,'_materialize',spy)
    assert commit(pid,undo)['version']==2
    # The published current branch has a separate preview path, which may
    # legitimately replay while preparing a receipt. Inspect commit only.
    monkeypatch.setattr(quality,'_materialize',original)
    restore=make_receipt(pid,'restore',version=2,target_version=1)
    monkeypatch.setattr(quality,'_materialize',spy)
    assert commit(pid,restore)['version']==3
    assert quality.current_data(pid)[0]['Region'].str.startswith(' ').sum()==0
    assert path.read_bytes()==raw


def test_restore_target_modified_during_preflight_is_refused(case,monkeypatch):
    pid,_,_=case
    action=commit(pid,make_receipt(pid,issue_id=issue(pid,'whitespace')['id']))['applied'][0]['id']
    receipt=make_receipt(pid,'restore',version=1,target_version=0)
    inject_after_validation(monkeypatch,lambda p:writer(
        "UPDATE quality_versions SET operations_json=? WHERE project_id=? AND version=?",
        (json.dumps([action]),p,0)))
    with pytest.raises(quality.QualityError) as exc:commit(pid,receipt)
    assert exc.value.status==409 and not receipt_consumed(pid,receipt)


def test_wrong_hash_does_not_modify_project(case):
    pid,_,_=case
    rec=make_receipt(pid,issue_id=issue(pid,'whitespace')['id'])
    with pytest.raises(quality.QualityError) as exc:
        approvals.commit(pid,approvals.ApprovalCommit(proposal_id=rec['proposal_id'],proposal_hash='0'*64))
    assert exc.value.status==403
    assert audit_counts(pid)==(0,1) and not receipt_consumed(pid,rec)


def test_expired_receipt_is_rejected(case):
    pid,_,_=case
    rec=make_receipt(pid,issue_id=issue(pid,'whitespace')['id'])
    writer('UPDATE quality_approval_receipts SET expires_at=? WHERE proposal_id=?',
           ((datetime.now(timezone.utc)-timedelta(minutes=1)).isoformat(),rec['proposal_id']))
    with pytest.raises(quality.QualityError) as exc:commit(pid,rec)
    assert exc.value.status==409 and audit_counts(pid)==(0,1)


def test_missing_original_checksum_still_requires_recovery(case):
    pid,_,_=case
    rec=make_receipt(pid,issue_id=issue(pid,'whitespace')['id'])
    writer('DELETE FROM quality_state WHERE project_id=?',(pid,))
    with pytest.raises(quality.QualityError) as exc:commit(pid,rec)
    assert exc.value.status==409 and 'checksum' in str(exc.value).lower()
    assert audit_counts(pid)==(0,1)


def test_injected_write_failure_rolls_back_actions_versions_and_receipt(case,monkeypatch):
    pid,path,raw=case
    rec=make_receipt(pid,issue_id=issue(pid,'whitespace')['id'])
    def fail(*_a,**_kw):raise sqlite3.OperationalError('synthetic metadata failure')
    monkeypatch.setattr(quality,'_add_version',fail)
    with pytest.raises(sqlite3.OperationalError):commit(pid,rec)
    assert audit_counts(pid)==(0,1) and not receipt_consumed(pid,rec) and path.read_bytes()==raw


def test_same_receipt_cannot_be_committed_twice(case):
    pid,_,_=case
    rec=make_receipt(pid,issue_id=issue(pid,'whitespace')['id'])
    assert commit(pid,rec)['version']==1
    with pytest.raises(quality.QualityError) as exc:commit(pid,rec)
    assert exc.value.status==409 and audit_counts(pid)==(1,2)


def test_existing_transformation_changed_without_version_is_refused(case,monkeypatch):
    pid,_,_=case
    rec=make_receipt(pid,issue_id=issue(pid,'whitespace')['id'])
    action=commit(pid,rec)['applied'][0]['id']
    undo=make_receipt(pid,'undo',version=1,action_id=action)
    inject_after_validation(monkeypatch,lambda p:writer(
        'UPDATE quality_actions SET params_json=? WHERE project_id=? AND id=?',
        ('{}',p,action)))
    with pytest.raises(quality.QualityError) as exc:commit(pid,undo)
    assert exc.value.status==409
    assert not receipt_consumed(pid,undo) and quality.current_version(pid)==1


def test_expiry_during_preflight_rejects_before_write(case,monkeypatch):
    pid,_,_=case
    rec=make_receipt(pid,issue_id=issue(pid,'whitespace')['id'])
    inject_after_validation(monkeypatch,lambda _:writer(
        'UPDATE quality_approval_receipts SET expires_at=? WHERE proposal_id=?',
        ((datetime.now(timezone.utc)-timedelta(seconds=3)).isoformat(),rec['proposal_id'])))
    with pytest.raises(quality.QualityError) as exc:commit(pid,rec)
    assert exc.value.status==409
    assert audit_counts(pid)==(0,1) and not receipt_consumed(pid,rec)


def test_real_dataset_replay_does_not_hold_writer_lock(case,monkeypatch):
    pid,_,_=case
    rec=make_receipt(pid,issue_id=issue(pid,'whitespace')['id'])
    original=quality._materialize
    count=[0]
    def probe(con,p,ops):
        assert not con.in_transaction
        with sqlite3.connect(storage.DB_PATH,timeout=0.3) as other:
            other.execute('BEGIN IMMEDIATE')
            other.execute('CREATE TABLE IF NOT EXISTS proof_of_writer (value INT)')
            other.execute('INSERT INTO proof_of_writer VALUES (1)')
        count[0]+=1
        return original(con,p,ops)
    monkeypatch.setattr(quality,'_materialize',probe)
    assert commit(pid,rec)['version']==1 and count[0]>=1


def test_concurrent_replay_cannot_consume_same_receipt_twice(case,monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    pid,_,_=case
    rec=make_receipt(pid,issue_id=issue(pid,'whitespace')['id'])
    gate=Barrier(2)
    original=approvals._stage_commit
    def synchronize(con,p,version,ops,payload):
        staged=original(con,p,version,ops,payload)
        gate.wait(timeout=5)
        return staged
    monkeypatch.setattr(approvals,'_stage_commit',synchronize)
    def once():
        try:
            return ('ok',commit(pid,rec))
        except quality.QualityError as ex:
            return ('refused',ex.status)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results=list(pool.map(lambda _:once(),range(2)))
    assert sorted(x[0] for x in results)==['ok','refused']
    assert next(x for x in results if x[0]=='refused')[1]==409
    assert audit_counts(pid)==(1,2) and receipt_consumed(pid,rec)


def test_validated_action_helper_rejects_missing_write_transaction(case):
    pid,_,_=case
    with storage.connect() as con:
        assert not con.in_transaction
        with pytest.raises(RuntimeError,match='write transaction'):
            quality._record_validated_action(con,{'id':pid},[],
                   {'kind':'trim_whitespace','column':'Region'},'explicit_receipt','issue',3)
    assert audit_counts(pid)==(0,1)

def test_archived_stale_project_denies_forged_receipt_before_lookup(case,monkeypatch):
    """Archived-first 409 wins over invalid-receipt 403; active still rejects forged receipts."""
    pid,path,raw=case
    original_project=quality._project
    stale=original_project(pid)
    invalid=approvals.ApprovalCommit(proposal_id='0'*48,proposal_hash='0'*64)
    with pytest.raises(quality.QualityError) as exc:
        approvals.commit(pid,invalid)
    assert exc.value.status==403  # active project: forged approval remains forbidden

    with storage.connect() as con:
        con.execute(
            'INSERT INTO project_lifecycle (project_id,archived_at) VALUES (?,?) '
            'ON CONFLICT(project_id) DO UPDATE SET archived_at=excluded.archived_at',
            (pid,storage.now()))
    monkeypatch.setattr(quality,'_project',lambda q: stale if q==pid else original_project(q))
    with pytest.raises(quality.QualityError) as exc:
        approvals.commit(pid,invalid)
    assert exc.value.status==409
    assert 'archived' in str(exc.value).lower()
    with storage.connect() as con:
        assert con.execute('SELECT COUNT(*) FROM quality_approval_receipts WHERE project_id=?',(pid,)).fetchone()[0]==0
    assert audit_counts(pid)==(0,1)
    assert path.read_bytes()==raw
