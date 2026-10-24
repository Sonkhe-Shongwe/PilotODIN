"""Immutable, project-scoped saved Explore analyses and computed evidence.

A save recomputes from the approved local dataset, never accepts chart/metric
values from a browser. Stored snapshots remain readable after Quality changes
but must not silently rerun against a different approved version.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3

from . import analytics, explore_filters, quality, storage

MAX_SAVED = 50
MAX_SNAPSHOT_BYTES = 110_000


class SavedAnalysisError(ValueError):
    def __init__(self, message: str, status: int = 422):
        super().__init__(message)
        self.status = status


def _init(con: sqlite3.Connection):
    con.executescript("""
        CREATE TABLE IF NOT EXISTS explore_snapshots_v1 (
            id TEXT PRIMARY KEY,
            project_id TEXT NOT NULL,
            title TEXT NOT NULL,
            dataset_version INTEGER NOT NULL,
            configuration_json TEXT NOT NULL,
            snapshot_json TEXT NOT NULL,
            sha256 TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY(project_id) REFERENCES projects(id)
        );
        CREATE INDEX IF NOT EXISTS ix_explore_snapshots_project
        ON explore_snapshots_v1(project_id,created_at DESC);
    """)


def _config(x: str, y: str | None, kind: str, aggregation: str,
            bins: int, correlation_method: str, filters: list[dict], color_by: str | None = None) -> dict:
    if kind not in ('auto','bar','histogram','scatter','line','box'):
        raise SavedAnalysisError('Unsupported chart type')
    if aggregation not in ('mean','sum','median','count'):
        raise SavedAnalysisError('Unsupported aggregation')
    if correlation_method not in ('pearson','spearman'):
        raise SavedAnalysisError('Unsupported correlation method')
    if not 4 <= bins <= 40:
        raise SavedAnalysisError('Histogram bins must be between 4 and 40')
    return {'x':x, 'y':y, 'kind':kind, 'aggregation':aggregation,
            'bins':bins, 'correlation_method':correlation_method,
            'filters':filters, 'color_by':color_by}


def capture(frame, version: int, config: dict) -> dict:
    """Recompute the entire evidence bundle from one local working snapshot."""
    x=config['x']; y=config['y']; kind=config['kind']
    subset=explore_filters.apply(frame, config['filters'])
    if x not in frame.columns or (y is not None and y not in frame.columns):
        raise SavedAnalysisError('Chart variables are missing from the approved dataset')
    chart=None
    if len(subset):
        try:
            chart=analytics.chart(subset, version, x, y, kind,
                                  config['aggregation'], config['bins'],config.get('color_by'))
        except ValueError as exc:
            # No unsupported or invalid chart can become verified evidence.
            raise SavedAnalysisError(f'Cannot save this chart: {exc}') from exc
    overview=analytics.describe(subset,version)
    correlation=analytics.correlation(subset,version,config['correlation_method'])
    # Do not capture row-level references in immutable reports: scatter indices
    # only have meaning against the ephemeral filtered dataframe.
    if chart and chart['type']=='scatter':
        chart={**chart,'data':[{key:value for key,value in point.items()
                               if key!='row_ref'} for point in chart['data']]}
    return {'version':version, 'total_rows':len(frame), 'filtered_rows':len(subset),
            'overview':overview, 'chart':chart, 'correlation':correlation,
            'source':'locally_recomputed_approved_dataset',
            'limitations':['A saved analysis is descriptive and does not establish causation.',
                           'Scatter plots may be sampled; categorical charts may truncate groups.',
                           'Snapshot evidence does not include source-level records.']}


def save(project_id: str, *, title: str, expected_version: int,
         x: str, y: str | None, kind: str, aggregation: str, bins: int,
         correlation_method: str, filters: list[dict], color_by: str | None = None) -> dict:
    if not isinstance(title,str) or not 4 <= len(title.strip()) <= 120:
        raise SavedAnalysisError('Give this analysis a title between 4 and 120 characters')
    if storage.get_project(project_id) is None:
        raise SavedAnalysisError('Project does not exist',404)
    frame,version=quality.current_data(project_id)
    if version!=expected_version:
        raise SavedAnalysisError('Dataset version changed. Refresh Explore before saving.',409)
    config=_config(x,y,kind,aggregation,bins,correlation_method,filters,color_by)
    config_json=json.dumps(config,sort_keys=True,allow_nan=False,separators=(',',':'))
    snapshot=capture(frame,version,config)
    snapshot['configuration_sha256']=hashlib.sha256(config_json.encode('utf-8')).hexdigest()
    canonical=json.dumps(snapshot,sort_keys=True,ensure_ascii=False,allow_nan=False,separators=(',',':'))
    if len(canonical.encode('utf-8'))>MAX_SNAPSHOT_BYTES:
        raise SavedAnalysisError('This analysis is too large to save. Choose a smaller chart or fewer fields.')
    digest=hashlib.sha256(canonical.encode('utf-8')).hexdigest()
    identity=storage.uid();created_at=storage.now()
    with storage.connect() as conn:
        _init(conn)
        conn.execute("""INSERT INTO explore_snapshots_v1
          (id,project_id,title,dataset_version,configuration_json,snapshot_json,sha256,created_at)
          VALUES(?,?,?,?,?,?,?,?)""",
          (identity,project_id,title.strip(),version,config_json,canonical,digest,created_at))
    return load(project_id,identity)


def listing(project_id: str) -> list[dict]:
    if storage.get_project(project_id) is None:
        raise SavedAnalysisError('Project does not exist',404)
    with storage.connect() as conn:
        _init(conn)
        rows=conn.execute("""SELECT id,title,dataset_version,sha256,created_at
          FROM explore_snapshots_v1 WHERE project_id=?
          ORDER BY created_at DESC,rowid DESC LIMIT ?""",(project_id,MAX_SAVED)).fetchall()
    current=quality.current_version(project_id)
    return [{**dict(row),'stale':row['dataset_version']!=current} for row in rows]


def load(project_id: str, snapshot_id: str) -> dict:
    if storage.get_project(project_id) is None:
        raise SavedAnalysisError('Project does not exist',404)
    with storage.connect() as conn:
        _init(conn)
        row=conn.execute('SELECT * FROM explore_snapshots_v1 WHERE id=? AND project_id=?',
                         (snapshot_id,project_id)).fetchone()
    if row is None:
        raise SavedAnalysisError('Saved analysis not found in this project',404)
    canonical=row['snapshot_json']
    checksum=hashlib.sha256(canonical.encode('utf-8')).hexdigest()
    if checksum!=row['sha256']:
        raise SavedAnalysisError('Saved analysis integrity check failed',409)
    snapshot=json.loads(canonical)
    configuration_hash=snapshot.get('configuration_sha256')
    observed_hash=hashlib.sha256(row['configuration_json'].encode('utf-8')).hexdigest()
    configuration_verified=configuration_hash is not None and configuration_hash==observed_hash
    if configuration_hash is not None and not configuration_verified:
        raise SavedAnalysisError('Saved analysis configuration integrity check failed',409)
    current=quality.current_version(project_id)
    return {'id':row['id'],'project_id':project_id,'title':row['title'],
            'dataset_version':row['dataset_version'],'created_at':row['created_at'],
            'sha256':checksum,'configuration_verified':configuration_verified,
            'current_dataset_version':current,
            'stale':row['dataset_version']!=current,
            'configuration':json.loads(row['configuration_json']),
            'snapshot':snapshot}
