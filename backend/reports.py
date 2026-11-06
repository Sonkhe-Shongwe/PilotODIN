"""Immutable, project-scoped, evidence-backed report revisions.

Every revision freezes the original verified evidence, including source versions.
HTML and PDF derive from the same canonical revision; no AI-generated numbers.
"""
from __future__ import annotations

from datetime import datetime, timezone
from html import escape
from io import BytesIO
import hashlib
import hmac
import json
import re
import sqlite3

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_LEFT
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, HRFlowable, KeepTogether, CondPageBreak

try:
    from . import quality, storage, report_charts, project_lifecycle
except ImportError:
    import quality, storage, report_charts, project_lifecycle

MAX_EVIDENCE = 15
MAX_SNAPSHOT = 130_000

class ReportError(Exception):
    def __init__(self, message: str, status: int = 422):
        super().__init__(message)
        self.status = status


def init():
    with storage.connect() as con:
        con.executescript('''
        CREATE TABLE IF NOT EXISTS explore_snapshots_v1 (
            id TEXT PRIMARY KEY, project_id TEXT NOT NULL, title TEXT NOT NULL,
            dataset_version INTEGER NOT NULL, configuration_json TEXT NOT NULL,
            snapshot_json TEXT NOT NULL, sha256 TEXT NOT NULL, created_at TEXT NOT NULL,
            FOREIGN KEY(project_id) REFERENCES projects(id)
        );
        CREATE INDEX IF NOT EXISTS ix_explore_snapshots_project
        ON explore_snapshots_v1(project_id,created_at DESC);
        CREATE TABLE IF NOT EXISTS reports_v1 (
            id TEXT PRIMARY KEY, project_id TEXT NOT NULL, created_at TEXT NOT NULL,
            FOREIGN KEY(project_id) REFERENCES projects(id)
        );
        CREATE INDEX IF NOT EXISTS ix_reports_v1_project ON reports_v1(project_id,created_at DESC);
        CREATE TABLE IF NOT EXISTS report_revisions_v1 (
            id TEXT PRIMARY KEY, report_id TEXT NOT NULL, number INTEGER NOT NULL,
            title TEXT NOT NULL, narrative TEXT NOT NULL, snapshot_json TEXT NOT NULL,
            content_sha256 TEXT NOT NULL, created_at TEXT NOT NULL,
            UNIQUE(report_id,number),
            FOREIGN KEY(report_id) REFERENCES reports_v1(id)
        );
        CREATE INDEX IF NOT EXISTS ix_report_revisions_v1 ON report_revisions_v1(report_id,number DESC);
        CREATE TABLE IF NOT EXISTS report_quality_audits_v1 (
            id TEXT PRIMARY KEY, project_id TEXT NOT NULL, dataset_version INTEGER NOT NULL,
            snapshot_json TEXT NOT NULL, sha256 TEXT NOT NULL, captured_at TEXT NOT NULL,
            FOREIGN KEY(project_id) REFERENCES projects(id)
        );
        CREATE INDEX IF NOT EXISTS ix_report_quality_audits_project
            ON report_quality_audits_v1(project_id,captured_at DESC);
        ''')


def _validate(title: str, narrative: str, evidence_ids: list[str]):
    if not isinstance(title, str) or not 5 <= len(title.strip()) <= 180:
        raise ReportError('Report title must be between 5 and 180 characters')
    if not isinstance(narrative, str) or len(narrative) > 6000:
        raise ReportError('Report narrative exceeds 6,000 characters')
    if not isinstance(evidence_ids, list) or not 1 <= len(evidence_ids) <= MAX_EVIDENCE:
        raise ReportError('Select between 1 and 15 verified evidence artifacts')
    if any(not isinstance(i, str) or not re.fullmatch(r'[a-f0-9]{32}', i) for i in evidence_ids):
        raise ReportError('Invalid evidence identifier')
    if len(set(evidence_ids)) != len(evidence_ids):
        raise ReportError('Duplicate evidence identifiers are not allowed')


def _explore_evidence(row: sqlite3.Row) -> dict:
    """Project-scoped, checksum-verified saved Explore analysis for report exhibit."""
    raw = row['snapshot_json']
    digest = hashlib.sha256(raw.encode('utf-8')).hexdigest()
    if digest != row['sha256']:
        raise ReportError('Saved Explore analysis failed integrity verification',409)
    snapshot = json.loads(raw)
    # The snapshot SHA covers the stored configuration SHA. Verify both before
    # turning a saved Explore view into a report's verified evidence exhibit.
    bound_config_hash=snapshot.get('configuration_sha256')
    observed_config_hash=hashlib.sha256(row['configuration_json'].encode('utf-8')).hexdigest()
    if not bound_config_hash or bound_config_hash!=observed_config_hash:
        raise ReportError('Saved Explore configuration is unverified or altered',409)
    config = json.loads(row['configuration_json'])
    if snapshot.get('version') != row['dataset_version']:
        raise ReportError('Saved Explore analysis dataset version disagrees with its evidence',409)
    plot = snapshot.get('chart')
    sample_rows = []
    if isinstance(plot,dict) and isinstance(plot.get('data'),list):
        # Report previews are bounded and may not represent all plotted points.
        # The entire approved source snapshot remains audited by its SHA-256.
        if plot.get('type') == 'box':
            sample_rows = [{k:v for k,v in point.items() if k in
                           ('label','min','q1','median','q3','max','outliers_total')}
                           for point in plot['data'][:1]]
        elif plot.get('type') == 'histogram':
            sample_rows = [{k:v for k,v in point.items() if k in
                           ('label','start','end','value')}
                           for point in plot['data'][:24]]
        elif plot.get('type') == 'scatter':
            sample_rows = [{k:v for k,v in point.items() if k in
                           ('x','y','group')} for point in plot['data'][:16]]
        else:
            sample_rows = [{k:v for k,v in point.items() if k in
                           ('label','value')} for point in plot['data'][:30]]
    result = {
        'summary': {
            'Total dataset rows': snapshot['total_rows'],
            'Rows matching saved filters': snapshot['filtered_rows'],
            'Matching missing cells': snapshot['overview']['missing_cells'],
            'Matching exact duplicates': snapshot['overview']['exact_duplicates'],
            'Chart type': plot.get('type') if plot else 'No chartable observations',
            'Displayed chart rows': len(plot.get('data',[])) if plot else 0,
            'Plotted sample': bool(plot.get('sampled',False)) if plot else False,
            'Chart groups truncated': bool(plot.get('truncated',False)) if plot else False,
            'Source snapshot SHA-256': digest,
        },
        'data': sample_rows,
        'note': 'Saved Explore calculations are descriptive, not causal. '
                'Report exhibit rows are bounded; the original immutable local '
                'snapshot is available in Explore.',
        'limitations': snapshot.get('limitations', []),
    }
    visual = report_charts.visual_spec(plot)
    if visual is not None:
        result['visual'] = visual
    return {
        'id':row['id'], 'investigation_id':None, 'objective':row['title'],
        'dataset_version':row['dataset_version'],
        'operation':'explore_snapshot',
        'params': {
            'x':config.get('x'), 'y':config.get('y'), 'kind':config.get('kind'),
            'aggregation':config.get('aggregation'),
            'filter_count':len(config.get('filters',[])),
            'filters':config.get('filters',[]),
            'color_by':config.get('color_by'),
            'source_snapshot_sha256':digest
        },
        'result':result, 'tool_version':'explore-snapshot-v1',
        'computed_at':row['created_at'], 'source_snapshot_sha256':digest
    }



MAX_QUALITY_FINDINGS = 35


def capture_quality(project_id: str, expected_version: int) -> dict:
    """Explicitly freeze a read-only, aggregate Quality audit from one approved version.

    No browser-supplied findings or per-record previews enter this snapshot.
    Holding the single SQLite write transaction while reading the source and
    its version prevents a concurrent approval from mixing audit states.
    """
    p = storage.get_project(project_id)
    if p is None:
        raise ReportError('Project does not exist', 404)
    if isinstance(expected_version, bool) or not isinstance(expected_version, int) or expected_version < 0:
        raise ReportError('Expected dataset version must be nonnegative', 422)
    with storage.connect() as con:
        con.execute('BEGIN IMMEDIATE')
        try:
            project_lifecycle.require_active_for_write(con, project_id)
            quality._ensure(con, p)
            version, active = quality._state(con, project_id)
            if version != expected_version:
                raise ReportError('Dataset version changed. Refresh Quality before capturing an audit.', 409)
            frame = quality._materialize(con, p, active)
            issues = quality._issues(frame)
            decisions = quality._decisions(con, project_id)
            original_digest = con.execute(
                'SELECT original_sha256 FROM quality_state WHERE project_id=?',
                (project_id,)
            ).fetchone()['original_sha256']
            current_event = con.execute(
                'SELECT event,created_at FROM quality_versions WHERE project_id=? AND version=?',
                (project_id,version)
            ).fetchone()
            captured = storage.now()
            # Proposals, detailed raw evidence and record previews are excluded.
            safe_explanations = {
                'exact_duplicates':'Repeated records may be legitimate; assess business grain before any removal.',
                'missing':'Missing or blank values require domain review before imputation.',
                'identifier':'Possible identifier; preserve for traceability where needed.',
                'outliers':'Values outside IQR fences may be legitimate extreme observations.',
                'whitespace':'Review surrounding whitespace before normalization.',
                'ambiguous_dates':'Review ambiguous day/month ordering before conversion.',
                'numeric_text':'Review numerical text formatting and measurement units.',
                'case_variant':'Possible capitalization mismatch; examine in Quality before merging.',
                'spelling':'Possible spelling mismatch; examine in Quality before merging.',
            }
            findings = [{
                'kind': item['kind'],
                'column': item['column'],
                'affected_rows': int(item['affected_rows']),
                'severity': item['severity'],
                'decision': decisions.get(item['id'], 'pending'),
                'title': item['title'],
                'detail': safe_explanations.get(item['kind'], 'Review this finding in Quality before treatment.'),
            } for item in issues[:MAX_QUALITY_FINDINGS]]
            raw = {
                'dataset_version': version,
                'source_original_sha256': original_digest,
                'captured_at': captured,
                'summary': {
                    'Rows in approved dataset': int(len(frame)),
                    'Columns in approved dataset': int(len(frame.columns)),
                    'Quality findings detected': int(len(issues)),
                    'Findings shown': len(findings),
                    'Approved working corrections active': int(len(active)),
                    'Version event': current_event['event'],
                    'Source original SHA-256': original_digest,
                },
                'findings': findings,
                'note': ('Read-only audit of the selected approved dataset version. '
                         'Findings are screening observations, not confirmed errors; '
                         'no corrections were applied by this capture.'),
                'limitations': [
                    ('Only the first 35 findings are displayed; counts cover all detected findings.'
                     if len(issues) > MAX_QUALITY_FINDINGS
                     else 'All detected findings are included for this version.'),
                    'No record-level values, row identifiers, source previews or proposed replacement values are exported.',
                    'Working corrections shown are version-scoped, and the uploaded source remains immutable.',
                ],
            }
            canonical = json.dumps(raw, sort_keys=True, ensure_ascii=False,
                                   allow_nan=False, separators=(',',':'))
            if len(canonical.encode('utf-8')) > MAX_SNAPSHOT:
                raise ReportError('Quality audit is too large to capture safely', 422)
            digest = hashlib.sha256(canonical.encode('utf-8')).hexdigest()
            ident = storage.uid()
            con.execute(
                '''INSERT INTO report_quality_audits_v1
                   (id,project_id,dataset_version,snapshot_json,sha256,captured_at)
                   VALUES(?,?,?,?,?,?)''',
                (ident, project_id, version, canonical, digest, captured)
            )
        except (quality.QualityError, project_lifecycle.ProjectLifecycleError) as exc:
            raise ReportError(str(exc), exc.status) from exc
    return {'id':ident,'project_id':project_id,'dataset_version':version,
            'source_snapshot_sha256':digest,'captured_at':captured,
            'findings_total':len(issues),'findings_shown':len(findings)}


def _quality_evidence(row: sqlite3.Row) -> dict:
    """Read an immutable audit, verify its stored digest and version binding."""
    raw = row['snapshot_json']
    digest = hashlib.sha256(raw.encode('utf-8')).hexdigest()
    if not hmac.compare_digest(digest, row['sha256']):
        raise ReportError('Saved Quality audit failed integrity verification',409)
    try:
        snapshot = json.loads(raw)
    except (ValueError,TypeError) as exc:
        raise ReportError('Saved Quality audit is unreadable',409) from exc
    if snapshot.get('dataset_version') != row['dataset_version']:
        raise ReportError('Saved Quality audit does not match dataset version',409)
    summary = snapshot.get('summary')
    findings = snapshot.get('findings')
    if not isinstance(summary,dict) or not isinstance(findings,list):
        raise ReportError('Saved Quality audit is incomplete',409)
    return {
        'id':row['id'], 'investigation_id':None,
        'objective':'Quality audit of dataset v'+str(row['dataset_version']),
        'dataset_version':row['dataset_version'],
        'operation':'quality_audit',
        'params':{'source_snapshot_sha256':digest,
                  'source_original_sha256':snapshot['source_original_sha256']},
        'result':{
            'summary':summary,
            'findings':[{'title':x.get('title','Finding'),
                         'detail':str(x.get('detail',''))+
                            (' | Column: '+str(x['column']) if x.get('column') else '')+
                            ' | Affected rows: '+str(x.get('affected_rows'))+
                            ' | Decision: '+str(x.get('decision','pending'))
                         } for x in findings],
            'note':snapshot.get('note',''),
            'limitations':snapshot.get('limitations',[]),
        },
        'tool_version':'quality-audit-snapshot-v1',
        'computed_at':row['captured_at'],
    }


def _model_evidence(row: sqlite3.Row) -> dict:
    """Freeze a bounded, selected-model evaluation; never copy holdout row predictions.

    An experiment is eligible only after the backend has completed training and
    committed a one-time selected-model held-out evaluation. The report embeds
    scalar metrics and aggregate class diagnostics, not evaluation_rows,
    raw input values, pipelines, or joblib artifacts.
    """
    if row['status'] != 'completed' or not row['selected_model'] or not row['final_results']:
        raise ReportError('Only completed, evaluated experiments can be reported', 403)
    try:
        config = json.loads(row['config'])
        development = json.loads(row['results'])
        final = json.loads(row['final_results'])
    except (TypeError, ValueError) as exc:
        raise ReportError('Stored experiment evaluation is not readable', 409) from exc
    if not all(isinstance(item, dict) for item in (config, development, final)):
        raise ReportError('Incomplete experiment evidence', 409)
    task = config.get('task')
    target = config.get('target')
    if task not in ('classification', 'regression') or not isinstance(target, str) or not target:
        raise ReportError('Experiment has no valid task or target', 409)
    if development.get('task') != task or final.get('target') != target:
        raise ReportError('Stored model evaluation does not match its experiment', 409)
    models = development.get('models', [])
    if not isinstance(models, list) or not any(isinstance(m, dict) and
            m.get('key') == row['selected_model'] and m.get('status') == 'ready' for m in models):
        raise ReportError('The selected model has no successful training record', 409)
    version = config.get('quality_version', 0)
    if isinstance(version, bool) or not isinstance(version, int) or version < 0:
        raise ReportError('Experiment dataset version is invalid', 409)
    primary = 'f1_macro' if task == 'classification' else 'mae'
    if isinstance(final.get(primary), bool) or not isinstance(final.get(primary), (int, float)):
        raise ReportError('Final held-out metric was not recorded', 409)

    summary = {
        'Prediction target': target,
        'Task': task.title(),
        'Selected model': row['selected_model'],
        'Validation split': config.get('split_strategy', 'random'),
        'Held-out observations': final.get('sample_count', development.get('test_rows')),
    }
    names = {
        'accuracy': 'Held-out accuracy (fraction)',
        'f1_macro': 'Held-out macro F1',
        'precision_macro': 'Held-out macro precision',
        'recall_macro': 'Held-out macro recall',
        'roc_auc': 'Held-out ROC AUC',
        'mae': 'Held-out MAE (target units)',
        'rmse': 'Held-out RMSE (target units)',
        'r2': 'Held-out R²',
        'baseline_test_metric': 'Held-out simple baseline',
        'baseline_test_label': 'Baseline metric',
        'cv_score': 'Development CV score',
        'baseline_cv': 'Development CV baseline',
        'beats_heldout_baseline': 'Outperforms held-out baseline',
    }
    for key, label in names.items():
        value = final.get(key)
        if isinstance(value, (str, bool, int, float)) and value is not None:
            summary[label] = value
    diagnostics = []
    if task == 'classification' and isinstance(final.get('class_report'), list):
        for item in final['class_report'][:30]:
            if not isinstance(item, dict):
                continue
            diagnostics.append({key: item.get(key) for key in
                                ('label', 'precision', 'recall', 'f1', 'support')})
    reliability = final.get('reliability', {})
    if not isinstance(reliability, dict):
        reliability = {}
    cautions = reliability.get('issues', [])
    if not isinstance(cautions, list):
        cautions = []
    cautions = [str(note)[:300] for note in cautions[:12] if isinstance(note, str)]
    summary['Reliability assessment'] = str(reliability.get('message', 'Not independently validated'))[:300]
    result = {
        'summary': summary,
        'data': diagnostics,
        'note': ('Selected-model held-out evaluation, fixed after model selection. '
                 'Probabilities may be uncalibrated; classification scores are not '
                 'guarantees and regression R² is not accuracy.'),
        'limitations': cautions,
    }
    # This digest is of the intentionally public-to-this-report projection,
    # excluding holdout row-level predictions and model binary contents.
    projection = json.dumps(result, sort_keys=True, ensure_ascii=False,
                            allow_nan=False, separators=(',', ':'))
    digest = hashlib.sha256(projection.encode('utf-8')).hexdigest()
    return {
        'id': row['id'], 'investigation_id': None,
        'objective': 'Evaluate ' + target, 'dataset_version': version,
        'operation': 'model_evaluation', 'params': {
            'experiment_id': row['id'], 'target': target,
            'selected_model': row['selected_model'],
            'split_strategy': config.get('split_strategy', 'random'),
            'split_column': config.get('split_column'),
            'evaluation_projection_sha256': digest,
        },
        'result': result, 'tool_version': 'saved-ml-evaluation-v1',
        'computed_at': row['created_at'],
    }


def _collect(con: sqlite3.Connection, pid: str, title: str, narrative: str, evidence_ids: list[str]):
    # Every source type is scoped to the CURRENT report project on the backend.
    # Never trust the browser's implied project or an arbitrary artifact ID.
    placeholders = ','.join('?' for _ in evidence_ids)
    rows = con.execute(f'''SELECT e.*, i.project_id, i.objective
        FROM evidence_v1 e JOIN investigations_v1 i ON e.investigation_id=i.id
        WHERE e.id IN ({placeholders}) AND i.project_id=? AND e.status='completed' ''',
        (*evidence_ids, pid)).fetchall()
    lookup = {}
    for row in rows:
        lookup[row['id']] = {
            'id':row['id'], 'investigation_id':row['investigation_id'],
            'objective':row['objective'], 'dataset_version':row['dataset_version'],
            'operation':row['operation'], 'params':json.loads(row['params']),
            'result':json.loads(row['result']), 'tool_version':row['tool_version'],
            'computed_at':row['created_at']
        }
    saved_rows = con.execute(f'''SELECT * FROM explore_snapshots_v1
        WHERE id IN ({placeholders}) AND project_id=?''',(*evidence_ids,pid)).fetchall()
    for row in saved_rows:
        if row['id'] in lookup:
            raise ReportError('Conflicting evidence identifiers from separate sources',409)
        lookup[row['id']] = _explore_evidence(row)
    model_rows = con.execute(f'''SELECT id, project_id, config, results, final_results,
        status, selected_model, created_at FROM experiments
        WHERE id IN ({placeholders}) AND project_id=? AND status='completed'
        AND selected_model IS NOT NULL AND final_results IS NOT NULL''',
        (*evidence_ids, pid)).fetchall()
    for row in model_rows:
        if row['id'] in lookup:
            raise ReportError('Conflicting evidence identifiers from separate sources', 409)
        lookup[row['id']] = _model_evidence(row)
    quality_rows = con.execute(f'''SELECT * FROM report_quality_audits_v1
        WHERE id IN ({placeholders}) AND project_id=?''',
        (*evidence_ids, pid)).fetchall()
    for row in quality_rows:
        if row['id'] in lookup:
            raise ReportError('Conflicting evidence identifiers from separate sources',409)
        lookup[row['id']] = _quality_evidence(row)
    if len(lookup) != len(evidence_ids):
        raise ReportError('Evidence is missing, unverified or belongs to another project', 403)
    evidence = [lookup[ident] for ident in evidence_ids]
    content = {
        'title':title.strip(), 'narrative':narrative,
        'project_id':pid, 'evidence':evidence,
        'dataset_versions':sorted({r['dataset_version'] for r in evidence}),
        'limitations':['Computed evidence is descriptive unless an independently validated inferential method is recorded.',
                       'Interpretations in the narrative are user-authored and have not been computationally verified.',
                       'Saved Explore chart excerpts are bounded and may be sampled or truncated; provenance is retained.'],
    }
    canonical = json.dumps(content,sort_keys=True,ensure_ascii=False,allow_nan=False,separators=(',',':'))
    if len(canonical.encode('utf-8')) > MAX_SNAPSHOT:
        raise ReportError('The selected evidence is too large for a single report revision')
    return canonical, hashlib.sha256(canonical.encode('utf-8')).hexdigest()


def save(project_id: str, title: str, narrative: str, evidence_ids: list[str], report_id: str | None = None):
    _validate(title,narrative,evidence_ids)
    if storage.get_project(project_id) is None:
        raise ReportError('Project does not exist',404)
    with storage.connect() as con:
        con.execute('BEGIN IMMEDIATE')
        try:
            project_lifecycle.require_active_for_write(con,project_id)
        except project_lifecycle.ProjectLifecycleError as exc:
            raise ReportError(str(exc),exc.status) from exc
        if report_id is not None:
            existing = con.execute('SELECT project_id FROM reports_v1 WHERE id=?',(report_id,)).fetchone()
            if existing is None:
                raise ReportError('Report does not exist',404)
            if existing['project_id'] != project_id:
                raise ReportError('Report belongs to a different project',403)
        canonical,digest=_collect(con,project_id,title,narrative,evidence_ids)
        ident=report_id or storage.uid()
        if report_id is None:
            con.execute('INSERT INTO reports_v1 VALUES (?,?,?)',(ident,project_id,storage.now()))
        else:
            latest=con.execute('''SELECT number,snapshot_json,content_sha256
                FROM report_revisions_v1 WHERE report_id=?
                ORDER BY number DESC LIMIT 1''',(ident,)).fetchone()
            if latest is not None and latest['snapshot_json']==canonical and hmac.compare_digest(latest['content_sha256'],digest):
                # No duplicate history for an identical canonical saved revision.
                result=load(ident,latest['number'])
                result['unchanged']=True
                return result
        number=con.execute('SELECT COALESCE(MAX(number),0)+1 FROM report_revisions_v1 WHERE report_id=?',(ident,)).fetchone()[0]
        revision=storage.uid()
        con.execute('''INSERT INTO report_revisions_v1
                    (id,report_id,number,title,narrative,snapshot_json,content_sha256,created_at)
                    VALUES(?,?,?,?,?,?,?,?)''',
                    (revision,ident,number,title.strip(),narrative,canonical,digest,storage.now()))
    return load(ident)


def listing(project_id: str):
    if storage.get_project(project_id) is None:
        raise ReportError('Project does not exist',404)
    with storage.connect() as con:
        rows=con.execute('''SELECT r.id, r.project_id, r.created_at, v.id AS revision_id,
           v.title, v.number AS revision, v.created_at AS updated_at
           FROM reports_v1 r JOIN report_revisions_v1 v ON v.report_id=r.id
           WHERE r.project_id=? AND v.number=(SELECT MAX(number) FROM report_revisions_v1 WHERE report_id=r.id)
           ORDER BY v.created_at DESC, v.rowid DESC''',(project_id,)).fetchall()
    return [dict(r) for r in rows]


def evidence_options(project_id: str):
    """Bounded options include both verified investigation and saved Explore evidence."""
    if storage.get_project(project_id) is None:
        raise ReportError('Project does not exist',404)
    current=quality.current_version(project_id)
    with storage.connect() as con:
        rows=con.execute("""SELECT e.id, e.operation, e.params, e.dataset_version,
            e.created_at, i.objective FROM evidence_v1 e JOIN investigations_v1 i
            ON i.id=e.investigation_id WHERE i.project_id=? AND e.status='completed'
            ORDER BY e.created_at DESC,e.rowid DESC LIMIT 100""",(project_id,)).fetchall()
        snapshots=con.execute("""SELECT * FROM explore_snapshots_v1
            WHERE project_id=?
            ORDER BY created_at DESC,rowid DESC LIMIT 50""",(project_id,)).fetchall()
        model_rows=con.execute("""SELECT id, project_id, config, results,
            final_results, status, selected_model, created_at FROM experiments
            WHERE project_id=? AND status='completed' AND selected_model IS NOT NULL
              AND final_results IS NOT NULL
            ORDER BY created_at DESC,rowid DESC LIMIT 50""",(project_id,)).fetchall()
        audit_rows=con.execute("""SELECT * FROM report_quality_audits_v1
            WHERE project_id=? ORDER BY captured_at DESC,rowid DESC LIMIT 50""",
            (project_id,)).fetchall()
    options=[{'id':r['id'],'operation':r['operation'],'params':json.loads(r['params']),
              'version':r['dataset_version'],'stale':r['dataset_version']!=current,
              'objective':r['objective'],'created_at':r['created_at'],'source':'investigation'} for r in rows]
    # Only offer snapshots that can *actually* become verified report exhibits.
    # Old result-only snapshots stay readable in Explore, but their settings
    # were never cryptographically bound to the computed values.
    for r in snapshots:
        try:
            _explore_evidence(r)
        except (ReportError,KeyError,ValueError,TypeError):
            continue
        options.append({
            'id':r['id'], 'operation':'explore_snapshot',
            'params':{'title':r['title'],'source_snapshot_sha256':r['sha256']},
            'version':r['dataset_version'], 'stale':r['dataset_version']!=current,
            'objective':r['title'],'created_at':r['created_at'],'source':'saved_explore'
        })
    # Evaluate each candidate through the same validator used when freezing
    # report evidence. Never offer unfinished models or raw held-out rows.
    for row in model_rows:
        try:
            art = _model_evidence(row)
        except (ReportError, KeyError, ValueError, TypeError, OverflowError):
            continue
        options.append({
            'id': row['id'], 'operation': 'model_evaluation',
            'params': {'target': art['params']['target'],
                       'selected_model': art['params']['selected_model']},
            'version': art['dataset_version'],
            'stale': art['dataset_version'] != current,
            'objective': art['objective'], 'created_at': row['created_at'],
            'source': 'saved_model_evaluation',
        })
    for row in audit_rows:
        try:
            art = _quality_evidence(row)
        except (ReportError,KeyError,TypeError,ValueError):
            continue
        options.append({
            'id':row['id'], 'operation':'quality_audit',
            'params':{'findings':art['result']['summary'].get('Quality findings detected',0)},
            'version':row['dataset_version'], 'stale':row['dataset_version']!=current,
            'objective':art['objective'],'created_at':row['captured_at'],
            'source':'saved_quality_audit'
        })
    return sorted(options,key=lambda entry:(entry['created_at'],entry['id']),reverse=True)[:150]



def evidence_preview(project_id: str, evidence_id: str):
    """Bounded, project-scoped read of the same evidence eligible for a report.

    Never return raw observation arrays, row IDs, prediction rows or complete
    evidence payloads. Reuse the exact verifier used by immutable report saves.
    This endpoint neither captures a Quality snapshot nor creates a revision.
    """
    if not re.fullmatch(r'[a-f0-9]{32}', evidence_id):
        raise ReportError('Invalid evidence identifier')
    if storage.get_project(project_id) is None:
        raise ReportError('Project does not exist', 404)
    with storage.connect() as con:
        canonical, _ = _collect(con, project_id, 'Evidence preview', '', [evidence_id])
    artifact = json.loads(canonical)['evidence'][0]
    result = artifact.get('result', {})
    summary = result.get('summary') if isinstance(result, dict) else None
    facts = []
    source = summary if isinstance(summary, dict) else {}
    if not source and isinstance(result, dict):
        # Legacy investigation tools do not always have a summary object.
        # Only safe scalar facts, never result.data/findings/row examples.
        source = {k: v for k, v in result.items()
                  if k not in ('data', 'rows', 'records', 'findings', 'samples',
                               'predictions', 'raw', 'note', 'warning', 'limitations')}
    scalar_count = 0
    for key, value in source.items():
        if not isinstance(key, str) or not isinstance(value, (str, int, float, bool)):
            continue
        scalar_count += 1
        if len(facts) >= 8:
            continue
        if isinstance(value, float) and not (-float('inf') < value < float('inf')):
            continue
        rendered = ('Yes' if value else 'No') if isinstance(value, bool) else str(value)
        facts.append({'label': _display_label(key)[:80],
                      'value': rendered[:140]})
    note = result.get('note', '') if isinstance(result, dict) else ''
    note = note[:240] if isinstance(note, str) else ''
    # The current Quality dataset version may differ; never silently upgrade
    # historical evidence or imply the old artifact was recomputed.
    current_version = quality.current_version(project_id)
    return {
        'id': evidence_id,
        'operation': artifact['operation'],
        'dataset_version': artifact['dataset_version'],
        'current_dataset_version': current_version,
        'historical': artifact['dataset_version'] != current_version,
        'objective': str(artifact.get('objective') or '')[:180],
        'summary': facts,
        'additional_summary_facts': max(0, scalar_count-len(facts)),
        'note': note,
        'disclosure': ('Only bounded verified aggregate facts are shown; raw rows, '
                       'predictions and detailed evidence are excluded. '
                       'The complete evidence is frozen only when you save a report.'),
    }


def load(report_id: str, revision: int | None = None):
    with storage.connect() as con:
        report=con.execute('SELECT * FROM reports_v1 WHERE id=?',(report_id,)).fetchone()
        if not report:
            raise ReportError('Report not found',404)
        if revision is None:
            row=con.execute('SELECT * FROM report_revisions_v1 WHERE report_id=? ORDER BY number DESC LIMIT 1',(report_id,)).fetchone()
        else:
            row=con.execute('SELECT * FROM report_revisions_v1 WHERE report_id=? AND number=?',(report_id,revision)).fetchone()
        if row is None:
            raise ReportError('Report revision not found',404)
        numbers=[r['number'] for r in con.execute('SELECT number FROM report_revisions_v1 WHERE report_id=? ORDER BY number',(report_id,)).fetchall()]
    stored=row['snapshot_json']
    actual_digest=hashlib.sha256(stored.encode('utf-8')).hexdigest()
    if not hmac.compare_digest(actual_digest,row['content_sha256']):
        raise ReportError('Saved report revision failed integrity verification',409)
    try:
        content=json.loads(stored)
    except (TypeError,ValueError) as exc:
        raise ReportError('Saved report revision is unreadable',409) from exc
    # The checksum authenticates a frozen blob; independently bind it to this
    # report's project and expected schema before serving it to Deliver.
    # A transplanted, validly hashed revision from another project is not valid.
    if not isinstance(content, dict) or content.get('project_id') != report['project_id']:
        raise ReportError('Saved report revision has invalid project provenance', 409)
    evidence=content.get('evidence')
    versions=content.get('dataset_versions')
    if (not isinstance(evidence,list) or not 1 <= len(evidence) <= MAX_EVIDENCE or
            not all(isinstance(art,dict) and isinstance(art.get('dataset_version'),int)
                    and art['dataset_version'] >= 0 for art in evidence) or
            not isinstance(versions,list) or versions != sorted({art['dataset_version'] for art in evidence}) or
            not isinstance(content.get('title'),str) or not isinstance(content.get('narrative'),str)):
        raise ReportError('Saved report revision has invalid evidence structure', 409)
    current=quality.current_version(report['project_id'])
    return {**content,
            'id':report_id, 'project_id':report['project_id'], 'created_at':report['created_at'],
            'revision_id':row['id'], 'revision':row['number'], 'revisions':numbers,
            'created_revision_at':row['created_at'], 'content_sha256':row['content_sha256'],
            'current_dataset_version':current,
            'has_historical_evidence':any(v!=current for v in versions)}


def _display_value(value) -> str:
    """Display a stored, verified value without recomputing or reinterpreting it."""
    if value is None:
        return "Not recorded"
    if isinstance(value, bool):
        return "Yes" if value else "No"
    if isinstance(value, (int, float, str)):
        return str(value)
    if isinstance(value, list):
        if not value:
            return "None"
        return ", ".join(_display_value(v) for v in value[:12]) + (f" (+{len(value)-12} more)" if len(value)>12 else "")
    if isinstance(value, dict):
        return "; ".join(f"{str(k).replace('_',' ')}: {_display_value(v)}" for k, v in list(value.items())[:12])
    return str(value)



def _display_label(key) -> str:
    """Keep authored metric capitalization (ROC AUC, R², macro F1)."""
    original = str(key)
    normalized = original.replace('_', ' ')
    return normalized.title() if '_' in original else normalized[:1].upper() + normalized[1:]



def _exhibit_with_disclosure(artifact: dict):
    """Shared typed display model and factual export omission counts."""
    operation=artifact.get("operation","verified analysis")
    result=artifact.get("result") or {}
    params=artifact.get("params") or {}
    facts=[]
    if isinstance(result.get("summary"),dict):
        facts.extend((_display_label(k),_display_value(v)) for k,v in result["summary"].items())
    for key,val in result.items():
        if key in ("summary","data","findings","method","operation","warning","note"):
            continue
        if isinstance(val,(int,float,str,bool)) or val is None:
            facts.append((_display_label(key),_display_value(val)))
    table_head=[]
    table_rows=[]
    group_data=result.get("data")
    if isinstance(group_data,list) and group_data and isinstance(group_data[0],dict):
        if operation=="compare":
            table_head=["Group", f"Verified median: {params.get('y','measure')}"]
            table_rows=[[_display_value(row.get("label")),_display_value(row.get("value"))] for row in group_data[:50]]
        else:
            keys=list(group_data[0])[:5]
            table_head=[_display_label(k) for k in keys]
            table_rows=[[_display_value(row.get(k)) for k in keys] for row in group_data[:40] if isinstance(row,dict)]
    elif isinstance(result.get("findings"),list):
        table_head=["Finding","Detail"]
        table_rows=[[_display_value(r.get("title",r.get("column","Finding"))),_display_value(r.get("detail",r.get("explanation","")))] for r in result["findings"][:30] if isinstance(r,dict)]
    # Keep the compact printed exhibit readable. The complete snapshot remains in
    # report_revisions_v1 and can always be audited using the saved evidence ID.
    if not facts and not table_rows:
        for k,v in list(result.items())[:20]:
            facts.append((_display_label(k),_display_value(v)))
    # The numeric limits concern this display, not the full underlying dataset.
    notices=[]
    if len(facts)>24:
        notices.append(
            f"Showing 24 of {len(facts)} saved summary facts; "
            f"{len(facts)-24} not shown in this export.")
    if isinstance(group_data,list) and group_data and isinstance(group_data[0],dict):
        if len(group_data)>len(table_rows):
            notices.append(
                f"Showing {len(table_rows)} of {len(group_data)} saved observation entries; "
                f"{len(group_data)-len(table_rows)} not shown in this export.")
    elif isinstance(result.get("findings"),list) and len(result["findings"])>len(table_rows):
        notices.append(
            f"Showing {len(table_rows)} of {len(result['findings'])} saved finding entries; "
            f"{len(result['findings'])-len(table_rows)} not shown in this export.")
    return facts[:24],table_head,table_rows,notices


def _exhibit(artifact: dict):
    """Existing three-value display contract retained for other consumers."""
    return _exhibit_with_disclosure(artifact)[:3]


def render_html(report: dict) -> bytes:
    e=lambda x:escape(str(x),quote=True)
    css='''<style>
    :root{color-scheme:light}body{font:15px/1.55 system-ui,-apple-system,Arial,sans-serif;
    background:#f5f7fc;color:#1c2847;margin:0}.page{max-width:900px;margin:32px auto;padding:24px 32px 40px;
    background:white;border:1px solid #e0e5f0;border-radius:15px;box-shadow:0 15px 35px #26316d0c}
    header{padding:12px 0 22px;border-bottom:3px solid #10a8bd}
    header .brand{font-weight:800;letter-spacing:.07em;color:#4932ad;font-size:12px}
    h1{font-size:30px;margin:10px 0;color:#172447;line-height:1.17}h2{font-size:20px;color:#35259c;margin:16px 0}
    h3{font-size:14px;color:#263354}p{overflow-wrap:anywhere}.meta{color:#65728d;font-size:12px}
    .narrative{background:#f6f7ff;border-left:4px solid #6d55e5;padding:15px;border-radius:5px}
    .evidence{border:1px solid #e0e5f0;border-radius:12px;padding:18px 20px;margin:20px 0;break-inside:avoid-page}
    .pill{display:inline-block;background:#e5f6f4;color:#0a776f;font-size:11px;font-weight:750;border-radius:99px;padding:4px 8px}
    table{border-collapse:collapse;width:100%;font-size:12px;margin:12px 0 15px;table-layout:fixed}
    th,td{padding:9px 10px;border-bottom:1px solid #e5e9f2;text-align:left;vertical-align:top;overflow-wrap:anywhere}
    th{background:#f2f2ff;color:#312390;font-weight:700}
    .warning{padding:12px;background:#fff7e6;color:#76510e;border-radius:8px}
    .verified-chart{margin:14px 0;padding:12px;border:1px solid #e0e5f0;border-radius:12px;background:#fafbfe}
    .verified-chart svg{width:100%;height:auto;max-height:340px}
    .verified-chart figcaption{color:#536482;font-size:11px;line-height:1.5;overflow-wrap:anywhere}
    footer{border-top:1px solid #e0e5f0;padding-top:15px;margin-top:22px}
    @media print{body{background:white}.page{border:0;box-shadow:none;max-width:none;margin:0;padding:0}
    .evidence{break-inside:avoid-page}thead{display:table-header-group}}
    </style>'''
    pieces=['<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>',
            e(report['title']),'</title>',css,'</head><body><main class="page">',
            '<header><div class="brand">pilot<span style="color:#5b18c8">ODIN</span> · VERIFIED REPORT</div><h1>',e(report['title']),'</h1>',
            '<div class="meta">Report ',e(report['id']),' · Revision ',e(report['revision']),' · Dataset versions ',
            e(", ".join(str(v) for v in report['dataset_versions'])),'</div></header>',
            '<section><h2>Interpretation and limitations</h2><p class="narrative">',
            e(report.get('narrative') or 'No interpretation was provided. The exhibits below contain verified local calculations.').replace('\n','<br>'),'</p>',
            '<p class="meta">Narrative is user-authored and is not independently verified.</p></section>']
    if len(report['dataset_versions'])>1:
        pieces+=['<p class="warning">Cross-version report: evidence comes from more than one dataset version.</p>']
    pieces+=['<section aria-label="Evidence register"><h2>Evidence register</h2>',
             '<p class="meta">The following saved artifacts are frozen in the order selected for this revision. '
             'Dataset versions are not automatically updated.</p>',
             '<table><thead><tr><th>Exhibit</th><th>Evidence source</th><th>Dataset version</th></tr></thead><tbody>']
    for number, art in enumerate(report['evidence'], 1):
        pieces+=['<tr><td>', e(number), '</td><td>',
                 e(art['operation'].replace('_',' ').title()), '</td><td>v',
                 e(art['dataset_version']), '</td></tr>']
    pieces+=['</tbody></table></section>']
    for art in report['evidence']:
        facts,columns,records,notices=_exhibit_with_disclosure(art)
        pieces+=['<section class="evidence"><span class="pill">VERIFIED LOCAL</span><h2>',
                 e(art['operation'].replace('_',' ').title()),'</h2><p class="meta">Dataset v',e(art['dataset_version']),
                 ' · Tool ',e(art['tool_version']),' · ',
                 e('Experiment created' if art['operation']=='model_evaluation' else 'Computed'),
                 ' ',e(art['computed_at']),'</p>',
                 '<p><strong>Investigation:</strong> ',e(art['objective']),'</p>']
        if facts:
            pieces+=['<table><thead><tr><th>Measure</th><th>Verified value</th></tr></thead><tbody>']
            for name,value in facts:
                pieces+=['<tr><td>',e(name),'</td><td>',e(value),'</td></tr>']
            pieces+=['</tbody></table>']
        visual = art.get('result', {}).get('visual') if isinstance(art.get('result'), dict) else None
        if isinstance(visual, dict):
            spec = report_charts.visual_spec(visual)
            if spec is not None:
                pieces+=['<h3>Saved chart visualization</h3>', report_charts.html_chart(spec)]
        if records:
            pieces+=['<h3>Verified observations</h3><table><thead><tr>']
            for h in columns:pieces+=['<th>',e(h),'</th>']
            pieces+=['</tr></thead><tbody>']
            for row in records:
                pieces+=['<tr>']
                for cell in row:pieces+=['<td>',e(cell),'</td>']
                pieces+=['</tr>']
            pieces+=['</tbody></table>']
        if notices:
            pieces+=['<div class="warning" role="note"><strong>Display limits</strong><ul>']
            pieces.extend('<li>'+e(item)+'</li>' for item in notices)
            pieces+=['</ul><p class="meta">The saved report retains its source evidence projection; upstream snapshots may have additional limits.</p></div>']
        if isinstance(art.get('result'), dict):
            caveat = art['result'].get('note')
            if isinstance(caveat, str) and caveat:
                pieces+=['<p class="meta"><strong>Interpretation note:</strong> ',e(caveat),'</p>']
            warnings = art['result'].get('limitations', [])
            if isinstance(warnings, list) and warnings:
                pieces+=['<div class="warning"><strong>Evidence limitations</strong><ul>']
                pieces.extend('<li>'+e(x)+'</li>' for x in warnings[:12] if isinstance(x,str))
                pieces+=['</ul></div>']
        pieces+=['<p class="meta">Evidence ID ',e(art['id']),' · Parameters ',
                 e('; '.join(f'{k}={_display_value(v)}' for k,v in art['params'].items()) or 'None'),'</p></section>']
    pieces+=['<footer><h2>Methodology and limitations</h2><ul>']
    pieces.extend('<li>'+e(x)+'</li>' for x in report['limitations'])
    pieces+=['</ul><p class="meta">Immutable report content SHA-256: ',e(report['content_sha256']),
             '</p><p class="meta">Evidence identifiers and version history are preserved in the saved PilotODIN project.</p>',
             '</footer></main></body></html>']
    return ''.join(pieces).encode('utf-8')


def render_pdf(report: dict, *, unicode_context=None) -> bytes:
    """Render the existing PDF unchanged unless an explicit verified context is supplied.

    No API route currently supplies a Unicode context. The dormant branch
    must not be enabled before independent six-file release font approval.
    """
    if unicode_context is not None:
        try:
            from .pdf_unicode_seam import UnicodePDFContext
        except ImportError:
            from pdf_unicode_seam import UnicodePDFContext
        if not isinstance(unicode_context, UnicodePDFContext):
            raise ValueError("Expected explicit verified Unicode PDF context")
        unicode_context.assert_ready()
    from reportlab.platypus import Table, TableStyle
    output=BytesIO()
    doc=SimpleDocTemplate(output,pagesize=A4,rightMargin=43,leftMargin=43,topMargin=40,bottomMargin=46,
                          title=report['title'],author='pilotODIN')
    styles=getSampleStyleSheet()
    styles.add(ParagraphStyle(name='ODIN',parent=styles['Title'],fontSize=19,leading=24,
                              textColor=colors.HexColor('#34258D'),alignment=TA_LEFT,spaceAfter=12))
    styles.add(ParagraphStyle(name='ODINBody',parent=styles['BodyText'],fontSize=9,leading=13,spaceAfter=8,wordWrap='CJK'))
    styles.add(ParagraphStyle(name='ODINMeta',parent=styles['BodyText'],fontSize=7.5,leading=10,
                              textColor=colors.HexColor('#596781'),spaceAfter=7,wordWrap='CJK'))
    styles.add(ParagraphStyle(name='ODINHeading',parent=styles['Heading2'],fontSize=13,leading=16,
                              textColor=colors.HexColor('#35259C'),spaceBefore=12,spaceAfter=8))
    if unicode_context is not None:
        for name in ('ODIN', 'ODINBody', 'ODINMeta', 'ODINHeading'):
            styles[name].fontName = unicode_context.base_face
        # Scoped density adjustment only for opt-in multilingual reports.
        # Preserve all typography/pagination on the legacy default route.
        styles['ODIN'].spaceAfter = 9
        styles['ODINBody'].spaceAfter = 5
        styles['ODINMeta'].spaceAfter = 5
        styles['ODINHeading'].spaceBefore = 8
        styles['ODINHeading'].spaceAfter = 6
    def p(value,style='ODINBody'):
        text = str(value)
        safe = (unicode_context.markup(text) if unicode_context is not None else
                escape(text).replace('\n','<br/>'))
        return Paragraph(safe, styles[style])
    def table(headers,records, *, compact=False):
        if not headers or not records:return []
        width=doc.width/max(len(headers),1)
        cells=[[p(v,'ODINMeta') for v in headers]]
        cells.extend([p(v,'ODINBody') for v in row] for row in records)
        obj=Table(cells,colWidths=[width]*len(headers),repeatRows=1,hAlign='LEFT')
        row_pad = 3 if compact else 6
        obj.setStyle(TableStyle([
          ('BACKGROUND',(0,0),(-1,0),colors.HexColor('#f0efff')),
          ('BOTTOMPADDING',(0,0),(-1,0),9),('TOPPADDING',(0,0),(-1,0),8),
          ('BOTTOMPADDING',(0,1),(-1,-1),row_pad),('TOPPADDING',(0,1),(-1,-1),row_pad),
          ('LINEBELOW',(0,0),(-1,-1),.35,colors.HexColor('#dee2ee')),
          ('VALIGN',(0,0),(-1,-1),'TOP')]))
        return [obj,Spacer(1,10)]
    story=[p('pilotODIN · VERIFIED LOCAL REPORT','ODINMeta'),p(report['title'],'ODIN'),
           p(f"Report {report['id']} · Revision {report['revision']}",'ODINMeta'),
           p(f"Content SHA-256 {report['content_sha256']}",'ODINMeta'),
           HRFlowable(width='100%',color=colors.HexColor('#1499aa'),thickness=2),Spacer(1,13),
           p('Interpretation and limitations','ODINHeading'),
           p(report.get('narrative') or 'No interpretation supplied. Verified local exhibits follow.'),
           p('Narrative is user-authored and is not independently verified.','ODINMeta')]
    if len(report['dataset_versions'])>1:
        story.append(p('Cross-version report: evidence comes from multiple dataset versions.'))
    story.extend([p('Evidence register','ODINHeading'),
                  p('Frozen saved artifacts, in the order selected for this revision. '
                    'Dataset versions are not automatically updated.','ODINMeta')])
    story.extend(table(['Exhibit','Evidence source','Dataset version'],
                       [[str(n),art['operation'].replace('_',' ').title(),
                         'v'+str(art['dataset_version'])]
                        for n,art in enumerate(report['evidence'], 1)]))
    for art in report['evidence']:
        facts,columns,records,notices=_exhibit_with_disclosure(art)
        exhibit_header=[Spacer(1,8),HRFlowable(width='100%',color=colors.HexColor('#dce0ef')),
                      p(art['operation'].replace('_',' ').title(),'ODINHeading'),
                      p(f"Evidence {art['id']} · Dataset v{art['dataset_version']} · Tool {art['tool_version']} · "
                        + ('Experiment created' if art['operation']=='model_evaluation' else 'Computed')
                        + f" {art['computed_at']}",'ODINMeta'),
                      p('Investigation: '+art['objective'])]
        visual = art.get('result', {}).get('visual') if isinstance(art.get('result'), dict) else None
        spec = report_charts.visual_spec(visual) if isinstance(visual, dict) else None
        # A short saved Explore chart was previously split from its exact
        # verified-value table by an avoidable extra page on the real BE-030
        # legacy PDF. Let its metric table repeat its header over a page
        # boundary and keep the compact chart with the short value table.
        # Other exhibit types and larger tables keep their existing layout.
        compact_explore = (unicode_context is None
                           and art.get('operation') == 'explore_snapshot'
                           and spec is not None
                           and 0 < len(facts) <= 12 and 0 < len(records) <= 8)
        fact_table=table(['Measure','Verified value'],facts,compact=compact_explore)
        if compact_explore:
            # Reserve space for the exhibit heading and initial facts, while
            # allowing the continuation rows to flow onto the next page.
            story.append(CondPageBreak(155))
            story.extend([*exhibit_header,*fact_table])
        elif fact_table and len(facts)<=18:
            # Preserve non-Explore heading and small fact table grouping.
            story.append(KeepTogether([*exhibit_header,*fact_table]))
        else:
            story.append(CondPageBreak(190))
            story.extend([*exhibit_header,*fact_table])
        chart_and_values_grouped = False
        if spec is not None:
            # Preserve exact saved vector values and labels; only opt into the
            # compact 175pt canvas for the short legacy Explore exhibit.
            chart_section = [
                p('Saved chart visualization','ODINHeading'),
                report_charts.pdf_chart(spec, width=doc.width,
                                        unicode_context=unicode_context,
                                        compact=compact_explore),
            ]
            if spec.get('note'):
                chart_section.append(p('Chart limitations: ' + spec['note'],'ODINMeta'))
            if compact_explore:
                observations=[p('Verified observations','ODINHeading'),
                              *table(columns,records,compact=True)]
                story.append(KeepTogether([*chart_section,*observations]))
                chart_and_values_grouped = True
            else:
                story.append(KeepTogether(chart_section))
        if records and not chart_and_values_grouped:
            table_section=[p('Verified observations','ODINHeading'),*table(columns,records)]
            if len(records)<=12:
                # Keep small non-Explore finding tables and their headings
                # together. Large tables still flow with repeated headers.
                story.append(KeepTogether(table_section))
            else:
                story.append(CondPageBreak(190))
                story.extend(table_section)
        if notices:
            story.append(KeepTogether([
                p('Display limits','ODINHeading'),
                *(p(item,'ODINMeta') for item in notices),
                p('The saved report retains its source evidence projection; upstream snapshots may have additional limits.','ODINMeta')
            ]))
        if isinstance(art.get('result'), dict):
            caveat = art['result'].get('note')
            if isinstance(caveat, str) and caveat:
                story.append(p('Interpretation note: '+caveat,'ODINMeta'))
            warnings = art['result'].get('limitations', [])
            if isinstance(warnings,list) and warnings:
                story.append(p('Evidence limitations','ODINHeading'))
                story.extend(p('- '+item) for item in warnings[:12] if isinstance(item,str))
        story.append(p('Parameters: '+'; '.join(f'{k}={_display_value(v)}' for k,v in art['params'].items()),'ODINMeta'))
    # Keep the final heading with its own disclosure bullets, especially
    # if a dense Unicode page would otherwise put a heading at page bottom.
    closing = [p('Methodology and limitations','ODINHeading')]
    closing.extend(p('• '+str(t)) for t in report['limitations'])
    if unicode_context is not None:
        story.append(KeepTogether(closing))
    else:
        story.extend(closing)
    def footer(canvas,document):
        canvas.saveState()
        canvas.setFont(unicode_context.base_face if unicode_context is not None else 'Helvetica',7)
        canvas.setFillColor(colors.HexColor('#6b7690'))
        canvas.drawString(43,27,'PilotODIN · Verified, version-linked analytical evidence')
        canvas.drawRightString(A4[0]-43,27,f"Page {document.page}")
        canvas.restoreState()
    doc.build(story,onFirstPage=footer,onLaterPages=footer)
    return output.getvalue()


def render_pdf_for_export(report: dict) -> bytes:
    """The only release-gated entry point for saved PDF downloads.

    Source approval is absent at this checkpoint, so the original renderer
    remains in place. A future reviewed source commit must pin all six font
    and OFL files before this can construct UnicodePDFContext.
    """
    try:
        from . import pdf_release_font_loader
    except ImportError:
        import pdf_release_font_loader
    try:
        return pdf_release_font_loader.render_export_pdf(report, render_pdf)
    except pdf_release_font_loader.PDFReleaseFontError as exc:
        # No local paths, raw font errors or partial PDF bytes in API responses.
        raise ReportError("Verified Unicode PDF resources unavailable", 503) from exc

init()
