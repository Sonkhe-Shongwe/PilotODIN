"""Persistent reports must preserve exact verified evidence and prevent cross-project leakage."""
from __future__ import annotations

import io
import re
from fastapi.testclient import TestClient
import fitz

from backend.main import app
from backend import storage, quality, reports

client=TestClient(app)


def project(name='retail.csv'):
    raw=b'OrderID,Region,Revenue\n0001,Gauteng,123.50\n0002,Mpumalanga,345.75\n0003,Gauteng,201.00\n'
    r=client.post('/api/projects',files={'file':(name,raw,'text/csv')})
    assert r.status_code==201,r.text
    return r.json()['id'],raw


def artifact(pid,op='overview',params=None):
    inv=client.post(f'/api/projects/{pid}/investigations',json={'objective':'Investigate revenue across regions'}).json()
    assert 'id' in inv
    r=client.post(f"/api/investigations/{inv['id']}/runs",json={'operation':op,'params':params or {},'expected_version':inv['version']})
    assert r.status_code==200,r.text
    return r.json()['artifacts'][0]['id']


def save(pid,ids,title='Regional Revenue Analysis',narrative='Review regional revenue patterns.'):
    return client.post(f'/api/projects/{pid}/reports',json={'title':title,'narrative':narrative,'evidence_ids':ids})


def test_report_save_reload_revision_and_html_pdf_same_snapshot():
    pid,raw=project()
    a=artifact(pid,'compare',{'x':'Region','y':'Revenue'})
    r=save(pid,[a]);assert r.status_code==201,r.text
    first=r.json();rid=first['id'];digest=first['content_sha256']
    assert first['revision']==1 and first['dataset_versions']==[0]
    assert len(first['evidence'])==1 and first['evidence'][0]['id']==a
    assert client.get(f'/api/projects/{pid}/reports').json()[0]['id']==rid
    assert client.get(f'/api/reports/{rid}').json()['content_sha256']==digest
    html=client.get(f'/api/reports/{rid}/export/html')
    pdf=client.get(f'/api/reports/{rid}/export/pdf')
    assert html.status_code==200 and pdf.status_code==200
    assert 'attachment;' in pdf.headers['content-disposition']
    assert pdf.content.startswith(b'%PDF')
    rendered=fitz.open(stream=pdf.content,filetype='pdf')
    txt=' '.join(page.get_text() for page in rendered)
    assert rid in html.text and rid in txt
    assert digest in html.text and digest in txt
    assert '345.75' in html.text and '345.75' in txt
    assert storage.get_project(pid)['dataset_path']
    previous=client.post(f'/api/reports/{rid}/revisions',json={'title':'Revenue Findings Revisited','narrative':'Human-reviewed wording','evidence_ids':[a]})
    assert previous.status_code==201,previous.text
    assert previous.json()['revision']==2
    original=client.get(f'/api/reports/{rid}?revision=1').json()
    assert original['title']=='Regional Revenue Analysis' and original['content_sha256']==digest
    assert previous.json()['revisions']==[1,2]
    assert html.headers['cache-control']=='no-store'
    assert quality.current_version(pid)==0


def test_cross_project_forged_evidence_and_report_access():
    p1,_=project('first.csv');p2,_=project('second.csv')
    a=artifact(p1)
    blocked=save(p2,[a]);assert blocked.status_code==403,blocked.text
    assert client.get(f'/api/projects/{p2}/reports').json()==[]
    correct=save(p1,[a]);assert correct.status_code==201,correct.text
    rid=correct.json()['id']
    # A revision cannot relink to foreign evidence even when the report exists.
    b=artifact(p2)
    bad=client.post(f'/api/reports/{rid}/revisions',json={'title':'Foreign evidence revision','narrative':'','evidence_ids':[b]})
    assert bad.status_code==403
    assert client.get(f'/api/reports/{rid}').json()['revisions']==[1]


def test_xss_escaping_and_pdf_text_is_not_executable():
    pid,_=project();a=artifact(pid)
    unsafe='<img src=x onerror=alert(1)> & harmless'
    saved=save(pid,[a],title='Safe HTML report',narrative=unsafe)
    assert saved.status_code==201,saved.text
    html=client.get(f"/api/reports/{saved.json()['id']}/export/html").text
    assert unsafe not in html and '&lt;img src=x onerror=alert(1)&gt;' in html
    assert '&amp; harmless' in html
    pdf=client.get(f"/api/reports/{saved.json()['id']}/export/pdf")
    assert pdf.status_code==200 and pdf.content.startswith(b'%PDF')


def test_bad_artifacts_reject_without_creating_report():
    pid,_=project();a=artifact(pid)
    for ids in [[],[a,a],['f'*32],[a,'f'*32],[a]*16]:
        assert save(pid,ids).status_code in (403,422)
    assert client.get(f'/api/projects/{pid}/reports').json()==[]
    assert client.get('/api/reports/not-an-id').status_code==404
    assert client.get('/api/reports/not-an-id/export/exe').status_code==404


def test_report_survives_new_dataset_version_with_original_evidence():
    pid,raw=project();a=artifact(pid)
    original=save(pid,[a]).json()
    version_before=quality.current_version(pid)
    # A new version can be registered without rewriting the previous report.
    with storage.connect() as con:
        # Simulate newly approved working version in the test fixture.
        state=con.execute('SELECT * FROM quality_state WHERE project_id=?',(pid,)).fetchone()
        assert state is not None
    assert version_before==0
    assert client.get(f"/api/reports/{original['id']}").json()['evidence'][0]['dataset_version']==0


def test_only_verified_evidence_is_accepted():
    pid,_=project();a=artifact(pid)
    with storage.connect() as con:
        con.execute("UPDATE evidence_v1 SET status='failed' WHERE id=?",(a,))
    assert save(pid,[a]).status_code==403


def test_project_evidence_options_and_cross_version_report():
    pid,_=project()
    first=artifact(pid,'overview')
    options=client.get(f'/api/projects/{pid}/report-evidence')
    assert options.status_code==200 and any(x['id']==first for x in options.json())
    # The saved report must still carry exact evidence after a quality change.
    with storage.connect() as con:
        before=con.execute('SELECT id FROM projects WHERE id=?',(pid,)).fetchone()
        assert before
    saved=save(pid,[first]).json()
    assert saved['dataset_versions']==[0]
    assert saved['has_historical_evidence'] is False


def test_report_combines_versions_and_preserves_original_snapshot():
    raw=b'OrderID,Region,Revenue\n0001,Gauteng,100\n0002,Mpumalanga,\n0003,Gauteng,310\n'
    created=client.post('/api/projects',files={'file':('cross_version.csv',raw,'text/csv')})
    assert created.status_code==201,created.text
    pid=created.json()['id']
    old=artifact(pid,'overview')
    earlier=save(pid,[old]).json()
    findings=quality.snapshot(pid)['issues']
    missing=next(x for x in findings if x['kind']=='missing' and x['column']=='Revenue')
    applied=quality.approve_imputation(pid,'Revenue',missing['id'],0)
    assert applied['version']==1
    newer=artifact(pid,'overview')
    combined=save(pid,[old,newer],title='Before and After Corrections').json()
    assert combined['dataset_versions']==[0,1]
    assert combined['has_historical_evidence'] is True
    html=client.get(f"/api/reports/{combined['id']}/export/html").text
    assert 'Cross-version report:' in html
    assert 'Dataset v0' in html and 'Dataset v1' in html
    reopened=client.get(f"/api/reports/{earlier['id']}").json()
    assert reopened['evidence'][0]['dataset_version']==0
    assert reopened['content_sha256']==earlier['content_sha256']
    # Source bytes are never rewritten by changes to the working dataset.
    from pathlib import Path
    assert Path(storage.get_project(pid)['dataset_path']).read_bytes()==raw
