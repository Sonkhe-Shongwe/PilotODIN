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
    """Bounded options include both verified investigation and saved Explore evidence."""
    if storage.get_project(project_id) is None:
        raise ReportError('Project does not exist',404)
    current=quality.current_version(project_id)
    with storage.connect() as con:
        rows=con.execute("""SELECT e.id, e.operation, e.params, e.dataset_version,
            e.created_at, i.objective FROM evidence_v1 e JOIN investigations_v1 i
            ON i.id=e.investigation_id WHERE i.project_id=? AND e.status='completed'
            ORDER BY e.created_at DESC,e.rowid DESC LIMIT 100""",(project_id,)).fetchall()
        snapshots=con.execute("""SELECT id,title,dataset_version,created_at,sha256
            FROM explore_snapshots_v1 WHERE project_id=?
            ORDER BY created_at DESC,rowid DESC LIMIT 50""",(project_id,)).fetchall()
    options=[{'id':r['id'],'operation':r['operation'],'params':json.loads(r['params']),
              'version':r['dataset_version'],'stale':r['dataset_version']!=current,
              'objective':r['objective'],'created_at':r['created_at'],'source':'investigation'} for r in rows]
    options.extend({
        'id':r['id'], 'operation':'explore_snapshot',
        'params':{'title':r['title'],'source_snapshot_sha256':r['sha256']},
        'version':r['dataset_version'], 'stale':r['dataset_version']!=current,
        'objective':r['title'],'created_at':r['created_at'],'source':'saved_explore'
    } for r in snapshots)
    return sorted(options,key=lambda entry:(entry['created_at'],entry['id']),reverse=True)[:150]


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


def _exhibit(artifact: dict):
    """Shared typed display model for both HTML and PDF (snapshot is immutable)."""
    operation=artifact.get("operation","verified analysis")
    result=artifact.get("result") or {}
    params=artifact.get("params") or {}
    facts=[]
    if isinstance(result.get("summary"),dict):
        facts.extend((str(k).replace("_"," ").title(),_display_value(v)) for k,v in result["summary"].items())
    for key,val in result.items():
        if key in ("summary","data","findings","method","operation","warning","note"):
            continue
        if isinstance(val,(int,float,str,bool)) or val is None:
            facts.append((key.replace("_"," ").title(),_display_value(val)))
    table_head=[]
    table_rows=[]
    group_data=result.get("data")
    if isinstance(group_data,list) and group_data and isinstance(group_data[0],dict):
        if operation=="compare":
            table_head=["Group", f"Verified median: {params.get('y','measure')}"]
            table_rows=[[_display_value(row.get("label")),_display_value(row.get("value"))] for row in group_data[:50]]
        else:
            keys=list(group_data[0])[:5]
            table_head=[str(k).replace("_"," ").title() for k in keys]
            table_rows=[[_display_value(row.get(k)) for k in keys] for row in group_data[:40] if isinstance(row,dict)]
    elif isinstance(result.get("findings"),list):
        table_head=["Finding","Detail"]
        table_rows=[[_display_value(r.get("title",r.get("column","Finding"))),_display_value(r.get("detail",r.get("explanation","")))] for r in result["findings"][:30] if isinstance(r,dict)]
    # Keep the compact printed exhibit readable. The complete snapshot remains in
    # report_revisions_v1 and can always be audited using the saved evidence ID.
    if not facts and not table_rows:
        for k,v in list(result.items())[:20]:
            facts.append((str(k).replace("_"," ").title(),_display_value(v)))
    return facts[:24],table_head,table_rows


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
    for art in report['evidence']:
        facts,columns,records=_exhibit(art)
        pieces+=['<section class="evidence"><span class="pill">VERIFIED LOCAL</span><h2>',
                 e(art['operation'].replace('_',' ').title()),'</h2><p class="meta">Dataset v',e(art['dataset_version']),
                 ' · Tool ',e(art['tool_version']),' · Computed ',e(art['computed_at']),'</p>',
                 '<p><strong>Investigation:</strong> ',e(art['objective']),'</p>']
        if facts:
            pieces+=['<table><thead><tr><th>Measure</th><th>Verified value</th></tr></thead><tbody>']
            for name,value in facts:
                pieces+=['<tr><td>',e(name),'</td><td>',e(value),'</td></tr>']
            pieces+=['</tbody></table>']
        if records:
            pieces+=['<h3>Verified observations</h3><table><thead><tr>']
            for h in columns:pieces+=['<th>',e(h),'</th>']
            pieces+=['</tr></thead><tbody>']
            for row in records:
                pieces+=['<tr>']
                for cell in row:pieces+=['<td>',e(cell),'</td>']
                pieces+=['</tr>']
            pieces+=['</tbody></table>']
        pieces+=['<p class="meta">Evidence ID ',e(art['id']),' · Parameters ',
                 e('; '.join(f'{k}={_display_value(v)}' for k,v in art['params'].items()) or 'None'),'</p></section>']
    pieces+=['<footer><h2>Methodology and limitations</h2><ul>']
    pieces.extend('<li>'+e(x)+'</li>' for x in report['limitations'])
    pieces+=['</ul><p class="meta">Immutable report content SHA-256: ',e(report['content_sha256']),
             '</p><p class="meta">Evidence identifiers and version history are preserved in the saved PilotODIN project.</p>',
             '</footer></main></body></html>']
    return ''.join(pieces).encode('utf-8')


def render_pdf(report: dict) -> bytes:
    """Print the same exhibit summaries as HTML, with provenance and page numbers."""
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
    def p(value,style='ODINBody'):
        return Paragraph(escape(str(value)).replace('\n','<br/>'),styles[style])
    def table(headers,records):
        if not headers or not records:return []
        width=doc.width/max(len(headers),1)
        cells=[[p(v,'ODINMeta') for v in headers]]
        cells.extend([p(v,'ODINBody') for v in row] for row in records)
        obj=Table(cells,colWidths=[width]*len(headers),repeatRows=1,hAlign='LEFT')
        obj.setStyle(TableStyle([
          ('BACKGROUND',(0,0),(-1,0),colors.HexColor('#f0efff')),
          ('BOTTOMPADDING',(0,0),(-1,0),9),('TOPPADDING',(0,0),(-1,0),8),
          ('BOTTOMPADDING',(0,1),(-1,-1),6),('TOPPADDING',(0,1),(-1,-1),6),
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
    for art in report['evidence']:
        facts,columns,records=_exhibit(art)
        story.extend([Spacer(1,8),HRFlowable(width='100%',color=colors.HexColor('#dce0ef')),
                      p(art['operation'].replace('_',' ').title(),'ODINHeading'),
                      p(f"Evidence {art['id']} · Dataset v{art['dataset_version']} · Tool {art['tool_version']} · Computed {art['computed_at']}",'ODINMeta'),
                      p('Investigation: '+art['objective'])])
        story.extend(table(['Measure','Verified value'],facts))
        if records:
            story.append(p('Verified observations','ODINHeading'))
            story.extend(table(columns,records))
        story.append(p('Parameters: '+'; '.join(f'{k}={_display_value(v)}' for k,v in art['params'].items()),'ODINMeta'))
    story.extend([p('Methodology and limitations','ODINHeading')])
    story.extend(p('• '+str(t)) for t in report['limitations'])
    def footer(canvas,document):
        canvas.saveState()
        canvas.setFont('Helvetica',7)
        canvas.setFillColor(colors.HexColor('#6b7690'))
        canvas.drawString(43,27,'PilotODIN · Verified, version-linked analytical evidence')
        canvas.drawRightString(A4[0]-43,27,f"Page {document.page}")
        canvas.restoreState()
    doc.build(story,onFirstPage=footer,onLaterPages=footer)
    return output.getvalue()

init()
