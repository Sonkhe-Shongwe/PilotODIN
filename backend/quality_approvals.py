"""Single-use, version-bound user approval receipts for all dataset modifications.

A read-only proposal is separate from the write endpoint. The model's tool
registry has neither operation; only the user-facing desktop quality view may
submit an explicit approval. All validation and commit occurs under SQLite's
BEGIN IMMEDIATE transaction, with failure rolling back the receipt consumption.
"""
from __future__ import annotations

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
            consumed_at TEXT
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
        for i in indices:
            if len(changed)<12:
                changed.append({'row_number':int(i)+1,'column':str(column),
                                'before':quality._native(lhs.loc[i]),'after':quality._native(rhs.loc[i])})
    return count,changed


def _make(con,p:dict,body:ProposalRequest)->tuple[dict,pd.DataFrame,pd.DataFrame]:
    pid=p['id']
    quality._ensure(con,p)
    version,ops=quality._state(con,pid)
    quality._check_version(version,body.expected_version)
    before=quality._materialize(con,p,ops)
    after=before.copy()
    op=body.operation
    steps=[]
    if op=='autopilot':
        # Fix the candidate set at preview time. Do not discover and execute
        # additional corrections at commit time.
        decisions=quality._decisions(con,pid)
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
        if quality._decisions(con,pid).get(body.issue_id)=='applied':
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
        after=quality._materialize(con,p,target)
        steps=[{'action_id':body.action_id,'operations':target}]
    elif op=='restore':
        if body.target_version is None:
            raise quality.QualityError('Restore target version is required')
        row=con.execute('SELECT operations_json FROM quality_versions WHERE project_id=? AND version=?',(pid,body.target_version)).fetchone()
        if row is None:
            raise quality.QualityError('Version to restore does not exist',404)
        target=json.loads(row['operations_json'])
        after=quality._materialize(con,p,target)
        steps=[{'target_version':body.target_version,'operations':target}]
    return {'project_id':pid,'expected_version':version,'operation':op,'steps':steps},before,after


def prepare(pid:str,body:ProposalRequest)->dict:
    _init_tables()
    p=quality._project(pid)
    with storage.connect() as con:
        con.execute('BEGIN IMMEDIATE')
        payload,before,after=_make(con,p,body)
        changed,examples=_compare_rows(before,after)
        if not changed:
            raise quality.QualityError('This action would not change the working dataset',409)
        digest=_hash(payload)
        proposal_id=secrets.token_hex(24)
        issued=datetime.now(timezone.utc)
        expires=issued+timedelta(minutes=10)
        con.execute('''INSERT INTO quality_approval_receipts
                     (proposal_id,project_id,expected_version,proposal_hash,payload_json,issued_at,expires_at)
                     VALUES(?,?,?,?,?,?,?)''',(
                      proposal_id,pid,body.expected_version,digest,quality._json(payload),issued.isoformat(),expires.isoformat()))
        return {'proposal_id':proposal_id,'proposal_hash':digest,'project_id':pid,
                'expected_version':body.expected_version,'operation':body.operation,
                'steps':payload['steps'],'changed_cells':changed,'preview':examples,
                'expires_at':expires.isoformat(),
                'warning':'Review the exact proposed changes. Approving creates a new immutable working version; the uploaded original is unchanged.'}


def commit(pid:str,body:ApprovalCommit)->dict:
    _init_tables()
    p=quality._project(pid)
    with storage.connect() as con:
        con.execute('BEGIN IMMEDIATE')
        rec=con.execute('SELECT * FROM quality_approval_receipts WHERE proposal_id=? AND project_id=?',
                        (body.proposal_id,pid)).fetchone()
        if rec is None or rec['proposal_hash']!=body.proposal_hash:
            raise quality.QualityError('Approval receipt is invalid or belongs to another project',403)
        if rec['consumed_at']:
            raise quality.QualityError('Approval has already been used',409)
        if datetime.fromisoformat(rec['expires_at'])<=datetime.now(timezone.utc):
            raise quality.QualityError('Approval expired; review a new preview',409)
        quality._ensure(con,p)
        version,ops=quality._state(con,pid)
        quality._check_version(version,rec['expected_version'])
        payload=json.loads(rec['payload_json'])
        if rec['proposal_hash']!=_hash(payload):
            raise quality.QualityError('Approval contents failed integrity verification',409)
        operation=payload['operation']
        steps=payload['steps']
        outcome=[]
        if operation in ('approve','impute','autopilot'):
            for step in steps:
                matching=next((x for x in quality._issues(quality._materialize(con,p,ops)) if x['id']==step['issue_id']),None)
                if matching is None:
                    raise quality.QualityError('Approved finding changed; review it again',409)
                if operation!='impute' and matching['proposal']!=step['proposal']:
                    raise quality.QualityError('Approved correction no longer matches the finding',409)
                if operation=='impute' and (matching['kind']!='missing' or matching['column']!=step['proposal']['column']):
                    raise quality.QualityError('Imputation finding has changed',409)
                version,action=quality._record_action(con,p,ops,step['proposal'],'explicit_receipt',step['issue_id'])
                if action['affected_rows']!=step['affected_rows']:
                    raise quality.QualityError('Approved affected-row count changed; review again',409)
                ops=[*ops,action['id']]
                outcome.append(action)
        elif operation=='undo':
            action_id=steps[0]['action_id']
            if action_id not in ops:
                raise quality.QualityError('Action no longer active',409)
            target=[i for i in ops if i!=action_id]
            if target!=steps[0]['operations']:
                raise quality.QualityError('Undo scope changed',409)
            quality._materialize(con,p,target)
            version=quality._add_version(con,pid,target,'undo',{'action_id':action_id,'prior_version':version,'source':'explicit_receipt'})
            # Suppress automatic re-application of undone corrections.
            for r in con.execute("SELECT details_json FROM quality_versions WHERE project_id=? AND event='apply'",(pid,)):
                d=json.loads(r['details_json'])
                if d.get('action_id')==action_id and d.get('issue_id'):
                    con.execute('INSERT OR REPLACE INTO quality_decisions VALUES(?,?,?,?)',(pid,d['issue_id'],'undone',storage.now()))
                    break
        elif operation=='restore':
            target=steps[0]['operations']
            if target != json.loads(con.execute('SELECT operations_json FROM quality_versions WHERE project_id=? AND version=?',
                                               (pid,steps[0]['target_version'])).fetchone()['operations_json']):
                raise quality.QualityError('Restore target changed',409)
            quality._materialize(con,p,target)
            version=quality._add_version(con,pid,target,'restore',{'from_version':steps[0]['target_version'],'prior_version':version,'source':'explicit_receipt'})
            for removed in set(ops)-set(target):
                for r in con.execute("SELECT details_json FROM quality_versions WHERE project_id=? AND event='apply'",(pid,)):
                    d=json.loads(r['details_json'])
                    if d.get('action_id')==removed and d.get('issue_id'):
                        con.execute('INSERT OR REPLACE INTO quality_decisions VALUES(?,?,?,?)',(pid,d['issue_id'],'undone',storage.now()))
                        break
        else:
            raise quality.QualityError('Unsupported approval operation',409)
        con.execute('UPDATE quality_approval_receipts SET consumed_at=? WHERE proposal_id=?',(storage.now(),body.proposal_id))
        return {'version':version,'operation':operation,'applied':outcome,'count':len(outcome),
                'approved':True,'receipt_id':body.proposal_id}
