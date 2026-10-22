"""Persistent, evidence-linked, read-only PilotODIN investigation objects.

The tool registry deliberately only calls existing validated local analytics. No
arbitrary code execution, model-generated SQL, external disclosure or data edits.
"""
from __future__ import annotations

import json
import re
import pandas as pd
try:
    from . import analytics, quality, storage
except ImportError:
    import analytics, quality, storage

ALLOWED = frozenset({'overview', 'compare', 'missingness', 'distribution'})


def init():
    with storage.connect() as con:
        con.executescript('''
        CREATE TABLE IF NOT EXISTS investigations_v1 (
          id TEXT PRIMARY KEY, project_id TEXT NOT NULL, objective TEXT NOT NULL,
          dataset_version INTEGER NOT NULL, status TEXT NOT NULL,
          created_at TEXT NOT NULL, updated_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS ix_investigations_v1_project
          ON investigations_v1(project_id, updated_at DESC);
        CREATE TABLE IF NOT EXISTS evidence_v1 (
          id TEXT PRIMARY KEY, investigation_id TEXT NOT NULL,
          operation TEXT NOT NULL, params TEXT NOT NULL, result TEXT NOT NULL,
          dataset_version INTEGER NOT NULL, tool_version TEXT NOT NULL,
          status TEXT NOT NULL, created_at TEXT NOT NULL,
          FOREIGN KEY(investigation_id) REFERENCES investigations_v1(id)
        );
        CREATE INDEX IF NOT EXISTS ix_evidence_v1_investigation
          ON evidence_v1(investigation_id,created_at);
        ''')
        columns={r['name'] for r in con.execute('PRAGMA table_info(evidence_v1)').fetchall()}
        if 'execution_key' not in columns:
            con.execute('ALTER TABLE evidence_v1 ADD COLUMN execution_key TEXT')
        con.execute('CREATE UNIQUE INDEX IF NOT EXISTS ix_evidence_v1_receipt ON evidence_v1(execution_key)')


def _short(row):
    d = dict(row)
    d['version'] = d.pop('dataset_version')
    return d


def _receipt_params(operation: str, params: dict) -> dict:
    """Normalise caller arguments to the verified persisted tool contract."""
    if operation == 'compare':
        return {'x':params.get('x'),'y':params.get('y'),'aggregation':'median'}
    if operation in ('missingness','distribution'):
        return {'column':params.get('column')}
    return {}


def create(project_id: str, objective: str):
    version = quality.current_version(project_id)
    uid, now = storage.uid(), storage.now()
    with storage.connect() as con:
        con.execute('INSERT INTO investigations_v1 VALUES (?,?,?,?,?,?,?)',
                    (uid, project_id, objective, version, 'draft', now, now))
    return load(uid)


def listing(project_id: str):
    current = quality.current_version(project_id)
    with storage.connect() as con:
        rows = con.execute('''SELECT i.*, (SELECT COUNT(*) FROM evidence_v1 e
           WHERE e.investigation_id=i.id AND e.status='completed') AS evidence_count
           FROM investigations_v1 i WHERE i.project_id=? ORDER BY i.updated_at DESC LIMIT 60''',
                           (project_id,)).fetchall()
    return [{'id': r['id'], 'project_id': r['project_id'], 'objective': r['objective'],
             'version': r['dataset_version'], 'status': r['status'],
             'evidence_count': r['evidence_count'], 'created_at': r['created_at'],
             'updated_at': r['updated_at'], 'stale': r['dataset_version'] != current}
            for r in rows]


def load(ident: str):
    with storage.connect() as con:
        row = con.execute('SELECT * FROM investigations_v1 WHERE id=?', (ident,)).fetchone()
        if not row:
            return None
        records = con.execute('SELECT * FROM evidence_v1 WHERE investigation_id=? ORDER BY created_at, rowid',
                              (ident,)).fetchall()
    current = quality.current_version(row['project_id'])
    result = _short(row)
    result.update({'current_version': current, 'stale': current != row['dataset_version'],
                   'artifacts': [{**{'id': e['id'], 'operation': e['operation'],
                                    'params': json.loads(e['params']), 'result': json.loads(e['result']),
                                    'version': e['dataset_version'], 'tool_version': e['tool_version'],
                                    'status': e['status'], 'created_at': e['created_at'],
                                    'execution_key': e['execution_key']},
                                   'stale': e['dataset_version'] != current}
                                 for e in records]})
    return result


def run(ident: str, operation: str, params: dict, expected_version: int, *, execution_key: str | None = None):
    """One synchronous, bounded, verified tool execution per user gesture."""
    if operation not in ALLOWED:
        raise ValueError('Unsupported read-only investigation tool')
    if execution_key is not None:
        if not isinstance(execution_key,str) or not re.fullmatch(r'[a-f0-9]{32}:[0-7]',execution_key):
            raise ValueError('Invalid execution receipt')
        with storage.connect() as con:
            prev=con.execute('SELECT investigation_id,operation,params FROM evidence_v1 WHERE execution_key=?',
                             (execution_key,)).fetchone()
        if prev:
            if prev['investigation_id']!=ident or prev['operation']!=operation or json.loads(prev['params'])!=_receipt_params(operation,params):
                raise RuntimeError('Execution receipt mismatch')
            return load(ident)
    investigation = load(ident)
    if investigation is None:
        raise KeyError('Investigation not found')
    if expected_version != investigation['version'] or investigation['stale']:
        raise RuntimeError('Dataset version changed. Start a new investigation to preserve prior evidence.')
    project_id = investigation['project_id']
    df, current = quality.current_data(project_id)
    if current != expected_version:
        raise RuntimeError('Dataset changed during the investigation. Refresh before running a tool.')
    args = {}
    if operation == 'overview':
        result = analytics.investigate(df, current, 'overview')
    elif operation == 'compare':
        x, y = params.get('x'), params.get('y')
        if not isinstance(x, str) or not isinstance(y, str) or x not in df or y not in df:
            raise ValueError('Select existing category and numeric columns')
        if x == y or len(x) > 200 or len(y) > 200:
            raise ValueError('Select different, valid columns')
        if not pd.api.types.is_numeric_dtype(df[y]):
            raise ValueError('Comparison metric must be a numeric column')
        # Chart returns bounded groups and discloses truncation.
        result = analytics.chart(df, current, x, y, 'bar', 'median')
        args = {'x': x, 'y': y, 'aggregation': 'median'}
    elif operation == 'missingness':
        column = params.get('column')
        if not isinstance(column, str) or column not in df:
            raise ValueError('Select an existing column')
        result = analytics.missingness_diagnostics(df, current, column)
        args = {'column': column}
    else:
        column = params.get('column')
        if not isinstance(column, str) or column not in df:
            raise ValueError('Select an existing column')
        result = analytics.investigate(df, current, 'numeric_distribution', column)
        args = {'column': column}
    eid, now = storage.uid(), storage.now()
    payload = json.dumps(result, allow_nan=False)
    with storage.connect() as con:
        # Reserve the write lock BEFORE validating version; quality commits
        # cannot slip in between the final check and the evidence insert.
        con.execute('BEGIN IMMEDIATE')
        if quality.current_version(project_id) != current:
            raise RuntimeError('Dataset changed while processing. Result was not saved.')
        if execution_key is not None:
            prev=con.execute('SELECT investigation_id,operation,params FROM evidence_v1 WHERE execution_key=?',
                             (execution_key,)).fetchone()
            if prev:
                if prev['investigation_id']!=ident or prev['operation']!=operation or json.loads(prev['params'])!=args:
                    raise RuntimeError('Execution receipt mismatch')
                return load(ident)
        con.execute('''INSERT INTO evidence_v1
            (id,investigation_id,operation,params,result,dataset_version,tool_version,status,created_at,execution_key)
            VALUES (?,?,?,?,?,?,?,?,?,?)''',
            (eid,ident,operation,json.dumps(args),payload,current,'analytics.v0.8','completed',now,execution_key))
        con.execute("UPDATE investigations_v1 SET status='needs_review', updated_at=? WHERE id=?",
                    (now, ident))
    return load(ident)


init()
