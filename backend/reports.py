"""Immutable, project-scoped, evidence-backed report revisions.

Every revision freezes the original verified evidence, including source versions.
HTML and PDF derive from the same canonical revision; no AI-generated numbers.
"""
from __future__ import annotations

from datetime import datetime, timezone
from html import escape
from io import BytesIO
import hashlib
import json
import re
import sqlite3

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_LEFT
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, HRFlowable, KeepTogether

try:
    from . import quality, storage
except ImportError:
    import quality, storage

MAX_EVIDENCE = 15
MAX_SNAPSHOT = 130_000

class ReportError(Exception):
    def __init__(self, message: str, status: int = 422):
        super().__init__(message)
        self.status = status


def init():
    with storage.connect() as con:
        con.executescript('''
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


def _collect(con: sqlite3.Connection, pid: str, title: str, narrative: str, evidence_ids: list[str]):
    # The JOIN is the security boundary. Never trust the project's identity from
    # the frontend or an evidence ID without checking its actual owner.
    placeholders = ','.join('?' for _ in evidence_ids)
    rows = con.execute(f'''SELECT e.*, i.project_id, i.objective
        FROM evidence_v1 e JOIN investigations_v1 i ON e.investigation_id=i.id
        WHERE e.id IN ({placeholders}) AND i.project_id=? AND e.status='completed' ''',
        (*evidence_ids, pid)).fetchall()
    lookup = {r['id']:r for r in rows}
    if len(lookup) != len(evidence_ids):
        raise ReportError('Evidence is missing, unverified or belongs to another project', 403)
    evidence = []
    for ident in evidence_ids:
        row = lookup[ident]
        evidence.append({
            'id':row['id'], 'investigation_id':row['investigation_id'],
            'objective':row['objective'], 'dataset_version':row['dataset_version'],
            'operation':row['operation'], 'params':json.loads(row['params']),
            'result':json.loads(row['result']), 'tool_version':row['tool_version'],
            'computed_at':row['created_at'],
        })
    content = {
        'title':title.strip(), 'narrative':narrative,
        'project_id':pid, 'evidence':evidence,
        'dataset_versions':sorted({r['dataset_version'] for r in evidence}),
        'limitations':['Computed evidence is descriptive unless an independently validated inferential method is recorded.',
                       'Interpretations in the narrative are user-authored and have not been computationally verified.'],
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
    """Bounded project-local evidence metadata for Deliver."""
    if storage.get_project(project_id) is None:
        raise ReportError('Project does not exist',404)
    current=quality.current_version(project_id)
    with storage.connect() as con:
        rows=con.execute("""SELECT e.id, e.operation, e.params, e.dataset_version,
           e.created_at, i.objective FROM evidence_v1 e JOIN investigations_v1 i
           ON i.id=e.investigation_id WHERE i.project_id=? AND e.status='completed'
           ORDER BY e.created_at DESC,e.rowid DESC LIMIT 150""",(project_id,)).fetchall()
    return [{'id':r['id'],'operation':r['operation'],'params':json.loads(r['params']),
             'version':r['dataset_version'],'stale':r['dataset_version']!=current,
             'objective':r['objective'],'created_at':r['created_at']} for r in rows]


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
    content=json.loads(row['snapshot_json'])
    current=quality.current_version(report['project_id'])
    return {'id':report_id, 'project_id':report['project_id'], 'created_at':report['created_at'],
            'revision_id':row['id'], 'revision':row['number'], 'revisions':numbers,
            'created_revision_at':row['created_at'], 'content_sha256':row['content_sha256'],
            'current_dataset_version':current, 'has_historical_evidence':any(v!=current for v in content['dataset_versions']),
            **content}


def render_html(report: dict) -> bytes:
    e=lambda x:escape(str(x),quote=True)
    pieces=['<!doctype html><html lang="en"><head><meta charset="utf-8"><title>',e(report['title']),
            '</title><style>body{font:15px/1.55 system-ui,Arial;color:#19213b;margin:40px auto;max-width:850px;padding:0 24px}',
            'h1,h2{color:#31218D}header{border-bottom:3px solid #148F9B;padding-bottom:16px}',
            'section{border-top:1px solid #ddd;padding:22px 0}pre{white-space:pre-wrap;overflow-wrap:anywhere;background:#f7f8fc;padding:14px}',
            '.meta{color:#596480}.warn{background:#fff7e2;padding:12px}@media print{body{margin:15mm;max-width:initial}}</style></head><body>',
            '<header><small>pilotODIN · Saved Report</small><h1>',e(report['title']),'</h1><p class="meta">Report ',e(report['id']),
            ' · Revision ',e(report['revision']),' · Content SHA-256 ',e(report['content_sha256']),'</p></header>',
            '<h2>Narrative (user-authored)</h2><p>',e(report['narrative']).replace('\n','<br>'),'</p>']
    if len(report['dataset_versions'])>1:
        pieces.append('<p class="warn">Cross-version report: evidence originates from dataset versions '+e(', '.join(map(str,report['dataset_versions'])))+'.</p>')
    for art in report['evidence']:
        pieces.extend(['<section><h2>',e(art['operation'].replace('_',' ').title()),'</h2><p class="meta">Evidence ',e(art['id']),
            ' · Dataset v',e(art['dataset_version']),' · Tool ',e(art['tool_version']),
            ' · Computed ',e(art['computed_at']),'</p><p>Investigation: ',e(art['objective']),'</p>',
            '<h3>Parameters</h3><pre>',e(json.dumps(art['params'],indent=2,sort_keys=True,ensure_ascii=False)),'</pre>',
            '<h3>Verified result</h3><pre>',e(json.dumps(art['result'],indent=2,sort_keys=True,ensure_ascii=False)),'</pre></section>'])
    pieces.extend(['<h2>Limitations</h2><ul>',*(f'<li>{e(x)}</li>' for x in report['limitations']),'</ul></body></html>'])
    return ''.join(pieces).encode('utf-8')


def render_pdf(report: dict) -> bytes:
    # Programmatic, offline ReportLab renderer. The same immutable snapshot as HTML.
    out=BytesIO()
    pdf=SimpleDocTemplate(out,pagesize=A4,rightMargin=42,leftMargin=42,topMargin=40,bottomMargin=40,
                          title=report['title'],author='pilotODIN')
    styles=getSampleStyleSheet()
    styles.add(ParagraphStyle(name='ODIN',parent=styles['Title'],fontSize=19,leading=24,textColor=colors.HexColor('#31218D'),alignment=TA_LEFT,spaceAfter=14))
    styles.add(ParagraphStyle(name='ODINBody',parent=styles['BodyText'],fontSize=9,leading=13,spaceAfter=8,wordWrap='CJK'))
    styles.add(ParagraphStyle(name='ODINMeta',parent=styles['BodyText'],fontSize=7,leading=10,textColor=colors.HexColor('#526178'),spaceAfter=8,wordWrap='CJK'))
    styles.add(ParagraphStyle(name='ODINCode',parent=styles['BodyText'],fontName='Courier',fontSize=6.7,leading=9.5,wordWrap='CJK',leftIndent=10))
    story=[Paragraph('pilotODIN · Saved Report',styles['ODINMeta']),Paragraph(escape(report['title']),styles['ODIN']),
           Paragraph(escape(f"Report {report['id']} · Revision {report['revision']} · SHA-256 {report['content_sha256']}"),styles['ODINMeta']),
           HRFlowable(width='100%',color=colors.HexColor('#148F9B'),thickness=2),Spacer(1,14),
           Paragraph('Narrative (user-authored)',styles['Heading2']),
           Paragraph(escape(report['narrative']).replace('\n','<br/>'),styles['ODINBody'])]
    if len(report['dataset_versions'])>1:
        story.append(Paragraph('Cross-version report: datasets '+escape(', '.join(map(str,report['dataset_versions']))),styles['ODINBody']))
    for art in report['evidence']:
        story.extend([Spacer(1,10),HRFlowable(width='100%',color=colors.HexColor('#DBDDE8')),
          Paragraph(escape(art['operation'].replace('_',' ').title()),styles['Heading2']),
          Paragraph(escape(f"Evidence {art['id']} · Dataset v{art['dataset_version']} · Tool {art['tool_version']} · Computed {art['computed_at']}"),styles['ODINMeta']),
          Paragraph('Investigation: '+escape(art['objective']),styles['ODINBody']),
          Paragraph('Parameters',styles['Heading3'])])
        for key, obj in [('parameters',art['params']),('result',art['result'])]:
            if key=='result':story.append(Paragraph('Verified result',styles['Heading3']))
            # Serialize scalars as escaped text (not executable PDF markup). Each source
            # JSON line is wrapped for the page width; no numerical result is recomputed.
            raw=json.dumps(obj,indent=2,sort_keys=True,ensure_ascii=False)
            for line in raw.splitlines():
                # Allow extremely long strings to wrap rather than exceed page margins.
                story.append(Paragraph(escape(line) if line.strip() else '&#160;',styles['ODINCode']))
    story.extend([Spacer(1,10),Paragraph('Limitations',styles['Heading2'])])
    story.extend(Paragraph('• '+escape(text),styles['ODINBody']) for text in report['limitations'])
    pdf.build(story)
    return out.getvalue()

init()
