"""Single-use, version-bound user approval receipts for all dataset modifications.

A read-only proposal is separate from the write endpoint. The model's tool
registry has neither operation; only the user-facing desktop quality view may
submit an explicit approval. Replay and preview occur outside SQLite transactions. Final source and metadata
fences, writes and single-use consumption share one BEGIN IMMEDIATE transaction.
"""
from __future__ import annotations

from dataclasses import asdict
import hashlib
import json
import math
import secrets
from datetime import datetime, timezone, timedelta
from typing import Literal

import pandas as pd
from pydantic import BaseModel, Field

try:
    from . import quality, storage
except ImportError:
    import quality, storage


class ProposalRequest(BaseModel):
    operation: Literal['autopilot','approve','impute','undo','restore']
    expected_version: int = Field(ge=0)
    issue_id: str | None = Field(default=None,max_length=128)
    column: str | None = Field(default=None,max_length=200)
    action_id: str | None = Field(default=None,max_length=128)
    target_version: int | None = Field(default=None,ge=0)
    strategy: Literal['median'] = 'median'


class ApprovalCommit(BaseModel):
    proposal_id: str = Field(min_length=32,max_length=64)
    proposal_hash: str = Field(min_length=64,max_length=64)


def _init_tables():
    with storage.connect() as con:
        con.execute('''CREATE TABLE IF NOT EXISTS quality_approval_receipts (
            proposal_id TEXT PRIMARY KEY,
            project_id TEXT NOT NULL,
            expected_version INTEGER NOT NULL,
            proposal_hash TEXT NOT NULL,
            payload_json TEXT NOT NULL,
            issued_at TEXT NOT NULL,
            expires_at TEXT NOT NULL,
            consumed_at TEXT,
            FOREIGN KEY(project_id) REFERENCES projects(id)
        )''')
        con.execute('CREATE INDEX IF NOT EXISTS quality_approval_project ON quality_approval_receipts(project_id,expected_version)')


def _hash(payload:dict)->str:
    return hashlib.sha256(quality._json(payload).encode('utf-8')).hexdigest()


def _compare_rows(before:pd.DataFrame,after:pd.DataFrame)->tuple[int,list[dict]]:
    # Transformations never change row count in this increment; row identities
    # remain source row numbers. Structural changes require a new contract.
    if len(before)!=len(after) or list(before.columns)!=list(after.columns):
        raise quality.QualityError('Structural changes are not supported by this approval workflow')
    changed=[]
    count=0
    for column in before.columns:
        lhs,rhs=before[column],after[column]
        equal=(lhs.eq(rhs) | (lhs.isna() & rhs.isna())).fillna(False)
        indices=equal.index[~equal]
        count+=len(indices)
        # The count covers every changed cell; only the first 12 are examples.
        for i in indices[:max(0,12-len(changed))]:
            changed.append({'row_number':int(i)+1,'column':str(column),
                            'before':quality._native(lhs.loc[i]),'after':quality._native(rhs.loc[i])})
    return count,changed


def _make(con,p:dict,body:ProposalRequest):
    """Preview from one metadata snapshot and one verified original."""
    if con.in_transaction:
        raise RuntimeError("Approval preview must not hold a database transaction")
    pid=p['id']
    observed=p['_approval_snapshot']
    current=observed['current']
    version,ops=current['version'],current['ops']
    quality._check_version(version,body.expected_version)
    op=body.operation
    # Only history transitions replay a second branch from the original frame.
    # _apply returns a new frame; do not create a redundant full-size copy here.
    base,before,identity=quality._snapshot_frame(
        current,original=op in ('undo','restore'),with_identity=True)
    after=before
    decisions=quality._snapshot_decisions(current)
    steps=[]
    if op=='autopilot':
        # Fix the candidate set at preview time. Do not discover and execute
        # additional corrections at commit time.
        for issue in quality._issues(after):
            if issue['automatic'] and issue['proposal'] and issue['id'] not in decisions:
                after,affected=quality._apply(after,issue['proposal'])
                steps.append({'issue_id':issue['id'],'proposal':issue['proposal'],'affected_rows':affected})
        if not steps:
            raise quality.QualityError('No pending automatic corrections to review',409)
    elif op in ('approve','impute'):
        if not body.issue_id:
            raise quality.QualityError('A specific issue is required')
        issue=next((x for x in quality._issues(before) if x['id']==body.issue_id),None)
        if issue is None:
            raise quality.QualityError('Finding no longer exists; refresh findings',409)
        if decisions.get(body.issue_id)=='applied':
            raise quality.QualityError('This issue was already applied',409)
        if op=='approve':
            if not issue['proposal']:
                raise quality.QualityError('This finding has no executable correction')
            action=issue['proposal']
        else:
            if issue['kind']!='missing' or issue['column']!=body.column:
                raise quality.QualityError('Numeric imputation issue does not match the requested column',409)
            series=before[body.column]
            if not pd.api.types.is_numeric_dtype(series) or pd.api.types.is_bool_dtype(series):
                raise quality.QualityError('Median imputation requires a numeric column')
            present=pd.to_numeric(series,errors='coerce').replace([float('inf'),-float('inf')],float('nan')).dropna()
            if present.empty:
                raise quality.QualityError('No observed values for median imputation')
            median=float(present.median())
            if not math.isfinite(median):
                raise quality.QualityError('Invalid median imputation value')
            action={'kind':'impute_numeric_median','column':body.column,'value':median}
        after,affected=quality._apply(after,action)
        steps=[{'issue_id':body.issue_id,'proposal':action,'affected_rows':affected}]
    elif op=='undo':
        if not body.action_id or body.action_id not in ops:
            raise quality.QualityError('Action is not active in the current version',409)
        target=[id for id in ops if id!=body.action_id]
        after=quality._replay_snapshot(base,{**current,'actions':[r for r in current['actions'] if r['id']!=body.action_id]})
        steps=[{'action_id':body.action_id,'operations':target}]
    elif op=='restore':
        if body.target_version is None:
            raise quality.QualityError('Restore target version is required')
        historical=observed['target']
        target=json.loads(historical['version_row']['operations_json'])
        after=quality._replay_snapshot(base,historical)
        steps=[{'target_version':body.target_version,'operations':target}]
    return {'project_id':pid,'expected_version':version,'operation':op,'steps':steps,
            'review_binding':_review_binding(observed,identity)},before,after,identity


def _approval_snapshot(con,pid,operation,target_version=None):
    current=quality._metadata_snapshot(con,pid)
    target=None
    if operation=='restore':
        if target_version is None:
            raise quality.QualityError('Restore target version is required')
        target=quality._metadata_snapshot(con,pid,target_version=target_version)
    return {'current':current,'target':target,
            'events':quality._apply_event_rows(con,pid) if operation in ('undo','restore') else []}


def _preview_state(con,pid,body):
    return _approval_snapshot(con,pid,body.operation,body.target_version)


def _review_binding(observed,identity):
    """Bind a reviewed receipt to its exact metadata and verified source."""
    def serial(metadata):
        if metadata is None:
            return None
        digest,receipt=metadata['contract']
        return {**metadata,'contract':[digest,asdict(receipt) if receipt is not None else None]}
    return _hash({'schema':1,'current':serial(observed['current']),
                  'target':serial(observed['target']),'events':observed['events'],
                  'source_identity':[identity.st_dev,identity.st_ino,identity.st_size,
                                     identity.st_mtime_ns,identity.st_ctime_ns]})


def _project_context(observed):
    return {**observed['current']['project'],'_approval_snapshot':observed}


def _verify_approval_snapshot(con,pid,observed,identity,operation,target_version=None):
    quality._verify_staged_write(con,pid,observed['current'],identity)
    if _approval_snapshot(con,pid,operation,target_version)!=observed:
        raise quality.QualityError('Quality history or decisions changed; review it again',409)


def _require_active_for_preview(con, pid: str) -> None:
    """Read-only fast archive check; the writer-lock check remains authority."""
    row = con.execute(
        "SELECT l.archived_at FROM projects p "
        "LEFT JOIN project_lifecycle l ON l.project_id=p.id WHERE p.id=?",
        (pid,),
    ).fetchone()
    if row is None:
        raise quality.QualityError('Project no longer exists. No Quality changes were applied.', 404)
    if row['archived_at'] is not None:
        raise quality.QualityError(
            'Project is archived. Restore it in Manage projects before making Quality changes.', 409
        )


def prepare(pid:str,body:ProposalRequest)->dict:
    _init_tables()
    p=quality._project(pid)
    with storage.connect() as con:
        _require_active_for_preview(con, pid)
        con.execute('BEGIN')
        observed = _preview_state(con, pid, body)
        con.commit()
        payload,before,after,identity=_make(con,_project_context(observed),body)
        changed,examples=_compare_rows(before,after)
        del before,after
        _require_active_for_preview(con, pid)
        if not changed:
            raise quality.QualityError('This action would not change the working dataset',409)
        if _preview_state(con, pid, body) != observed:
            raise quality.QualityError('Quality state changed while preparing the preview. Review it again.',409)
        encoded = quality._json(payload)
        if len(encoded.encode('utf-8')) > quality.MAX_REPLAY_METADATA_BYTES:
            raise quality._metadata_limit()
        digest=hashlib.sha256(encoded.encode('utf-8')).hexdigest()
        proposal_id=secrets.token_hex(24)
        issued=datetime.now(timezone.utc)
        expires=issued+timedelta(minutes=10)
        # Only the receipt publication holds the writer lock. A stale version,
        # changed decision or archived project must fail without a receipt.
        con.execute('BEGIN IMMEDIATE')
        quality._require_active_for_write(con,pid)
        if _preview_state(con, pid, body) != observed:
            raise quality.QualityError('Quality state changed while preparing the preview. Review it again.',409)
        quality._verify_staged_write(con,pid,observed['current'],identity)
        con.execute('''INSERT INTO quality_approval_receipts
                     (proposal_id,project_id,expected_version,proposal_hash,payload_json,issued_at,expires_at)
                     VALUES(?,?,?,?,?,?,?)''',(
                      proposal_id,pid,body.expected_version,digest,encoded,issued.isoformat(),expires.isoformat()))
        return {'proposal_id':proposal_id,'proposal_hash':digest,'project_id':pid,
                'expected_version':body.expected_version,'operation':body.operation,
                'steps':payload['steps'],'changed_cells':changed,'preview':examples,
                'expires_at':expires.isoformat(),
                'warning':'Review the exact proposed changes. Approving creates a new immutable working version; the uploaded original is unchanged.'}


def _receipt_for_commit(con, pid: str, body: ApprovalCommit):
    rows=quality._bounded_rows(con,
        'SELECT * FROM quality_approval_receipts WHERE proposal_id=? AND project_id=? AND proposal_hash=?',
        (body.proposal_id,pid,body.proposal_hash),max_rows=1,
        max_bytes=quality.MAX_REPLAY_METADATA_BYTES+1024)
    rec=rows[0] if rows else None
    if rec is None:
        raise quality.QualityError('Approval receipt is invalid or belongs to another project',403)
    if rec['consumed_at']:
        raise quality.QualityError('Approval has already been used',409)
    if datetime.fromisoformat(rec['expires_at'])<=datetime.now(timezone.utc):
        raise quality.QualityError('Approval expired; review a new preview',409)
    if len(rec['payload_json'].encode('utf-8')) > quality.MAX_REPLAY_METADATA_BYTES:
        raise quality._metadata_limit()
    try:
        payload=json.loads(rec['payload_json'])
    except (ValueError, RecursionError) as exc:
        raise quality.QualityError('Approval contents failed integrity verification',409) from exc
    if rec['proposal_hash']!=_hash(payload):
        raise quality.QualityError('Approval contents failed integrity verification',409)
    return rec,payload


def _stage_commit(con, p:dict, version:int, ops:list[str], payload:dict):
    """Replay only the captured approved operations, outside all DB locks."""
    if con.in_transaction:
        raise RuntimeError("Approval replay must not hold a database transaction")
    observed=p['_approval_snapshot']
    current=observed['current']
    operation=payload['operation']
    steps=payload['steps']
    base,df,identity=quality._snapshot_frame(
        current,original=operation in ('undo','restore'),with_identity=True)
    if payload.get('review_binding')!=_review_binding(observed,identity):
        raise quality.QualityError('Approval source or review state changed; prepare a new preview',409)
    if operation in ('approve','impute','autopilot'):
        decisions=quality._snapshot_decisions(current)
        del base
        verified=[]
        for step in steps:
            prior=decisions.get(step['issue_id'])
            if prior=='applied' or (operation=='autopilot' and prior is not None):
                raise quality.QualityError('Approved finding has already been decided; review it again',409)
            matching=next((x for x in quality._issues(df) if x['id']==step['issue_id']),None)
            if matching is None:
                raise quality.QualityError('Approved finding changed; review it again',409)
            if operation!='impute' and matching['proposal']!=step['proposal']:
                raise quality.QualityError('Approved correction no longer matches the finding',409)
            if operation=='impute' and (matching['kind']!='missing' or matching['column']!=step['proposal']['column']):
                raise quality.QualityError('Imputation finding has changed',409)
            df,affected=quality._apply(df,step['proposal'],expected_affected=step['affected_rows'])
            verified.append((step['issue_id'],step['proposal'],affected))
        return ('actions',verified,identity)
    if operation=='undo':
        step=steps[0]
        action_id=step['action_id']
        if action_id not in ops:
            raise quality.QualityError('Action no longer active',409)
        target=[i for i in ops if i!=action_id]
        if target!=step['operations']:
            raise quality.QualityError('Undo scope changed',409)
        quality._replay_snapshot(base,{**current,'actions':[r for r in current['actions'] if r['id']!=action_id]})
        return ('undo',target,identity)
    if operation=='restore':
        step=steps[0]
        historical=observed['target']
        if historical is None or step['operations']!=json.loads(historical['version_row']['operations_json']):
            raise quality.QualityError('Restore target changed',409)
        quality._replay_snapshot(base,historical)
        return ('restore',step['operations'],identity)
    raise quality.QualityError('Unsupported approval operation',409)



def commit(pid:str,body:ApprovalCommit)->dict:
    _init_tables()
    p=quality._project(pid)
    with storage.connect() as con:
        # Preserve archive-denial precedence even when the request cached a
        # project before archive or supplied a forged/missing receipt. This is
        # a short read-only check, NOT the authority for the final write.
        _require_active_for_preview(con,pid)
        con.execute('BEGIN')
        rec,payload=_receipt_for_commit(con,pid,body)
        operation=payload['operation']
        if payload.get('project_id')!=pid or payload.get('expected_version')!=rec['expected_version']:
            raise quality.QualityError('Approval contents failed integrity verification',409)
        target_version=payload['steps'][0]['target_version'] if operation=='restore' else None
        observed=_approval_snapshot(con,pid,operation,target_version)
        version,ops=observed['current']['version'],observed['current']['ops']
        quality._check_version(version,rec['expected_version'])
        con.commit()
        p=_project_context(observed)
        staged=_stage_commit(con,p,version,ops,payload)

        con.execute('BEGIN IMMEDIATE')
        quality._require_active_for_write(con,pid)
        current,final_payload=_receipt_for_commit(con,pid,body)
        if tuple(current)!=tuple(rec) or final_payload!=payload:
            raise quality.QualityError('Approval receipt changed; review it again',409)
        _verify_approval_snapshot(con,pid,observed,staged[2],operation,target_version)

        operation=payload['operation']
        steps=payload['steps']
        outcome=[]
        if staged[0]=='actions':
            for issue_id,proposal,affected in staged[1]:
                version,action=quality._record_validated_action(con,p,ops,proposal,'explicit_receipt',issue_id,affected)
                ops=[*ops,action['id']]
                outcome.append(action)
        elif staged[0]=='undo':
            action_id=steps[0]['action_id']
            target=staged[1]
            version=quality._add_version(con,pid,target,'undo',{'action_id':action_id,'prior_version':version,'source':'explicit_receipt'})
            for _,raw in observed['events']:
                d=json.loads(raw)
                if d.get('action_id')==action_id and d.get('issue_id'):
                    con.execute('INSERT OR REPLACE INTO quality_decisions VALUES(?,?,?,?)',(pid,d['issue_id'],'undone',storage.now()))
                    break
        elif staged[0]=='restore':
            target=staged[1]
            row=con.execute('SELECT operations_json FROM quality_versions WHERE project_id=? AND version=?',
                            (pid,steps[0]['target_version'])).fetchone()
            if row is None or target!=json.loads(row['operations_json']):
                raise quality.QualityError('Restore target changed',409)
            version=quality._add_version(con,pid,target,'restore',{'from_version':steps[0]['target_version'],'prior_version':version,'source':'explicit_receipt'})
            for removed in set(ops)-set(target):
                for _,raw in observed['events']:
                    d=json.loads(raw)
                    if d.get('action_id')==removed and d.get('issue_id'):
                        con.execute('INSERT OR REPLACE INTO quality_decisions VALUES(?,?,?,?)',(pid,d['issue_id'],'undone',storage.now()))
                        break
        else:
            raise RuntimeError('Unrecognized validated approval state')
        quality._check_history_budget(con,pid)
        updated=con.execute('UPDATE quality_approval_receipts SET consumed_at=? WHERE proposal_id=? AND consumed_at IS NULL',
                            (storage.now(),body.proposal_id))
        if updated.rowcount!=1:
            raise quality.QualityError('Approval has already been used',409)
        return {'version':version,'operation':operation,'applied':outcome,'count':len(outcome),
                'approved':True,'receipt_id':body.proposal_id}
