"""Build E: export exact immutable versions without spreadsheet execution risks."""
from __future__ import annotations

import io
import csv
import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault('PILOTODIN_HOME', tempfile.mkdtemp(prefix='pilotodin-export-'))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient
import openpyxl
import pandas as pd
from backend.main import app
from backend import quality, storage

client = TestClient(app)


def project():
    data = pd.DataFrame({
        'OrderID':['0001','0002','0003','0004'],
        'Region':['Gauteng','Mpumalanga','Gauteng','Mpumalanga'],
        'Revenue':[100.0,200.0,None,400.0],
        'Note':['=HYPERLINK("http://example.test")','+SUM(1,2)','-CMD','Normal']
    })
    raw = data.to_csv(index=False).encode('utf-8')
    response = client.post('/api/projects',files={'file':('orders.csv',raw,'text/csv')})
    assert response.status_code == 201, response.text
    return response.json()['id'], raw


def exported(pid, version=0, fmt='csv', columns=None, filters=None):
    body = {'version':version,'format':fmt}
    if columns is not None:body['columns']=columns
    if filters is not None:body['filters']=filters
    return client.post(f'/api/projects/{pid}/quality/export',json=body)


def test_csv_export_preserves_source_original_and_identifier():
    pid, raw = project()
    original_path = Path(storage.get_project(pid)['dataset_path'])
    response=exported(pid)
    assert response.status_code==200,response.text
    rows=list(csv.DictReader(io.StringIO(response.content.decode('utf-8-sig'))))
    assert len(rows)==4
    assert rows[0]['OrderID']=='0001'
    assert rows[0]['Note'].startswith("'=")
    assert rows[1]['Note'].startswith("'+")
    assert rows[2]['Note'].startswith("'-")
    assert original_path.read_bytes()==raw
    assert quality.current_version(pid)==0
    assert response.headers['X-PilotODIN-Dataset-Version']=='0'
    assert response.headers['X-PilotODIN-Exported-Rows']=='4'
    assert response.headers['Cache-Control']=='no-store'


def test_exact_historical_export_and_filtered_subset():
    pid, _ = project()
    state = quality.snapshot(pid)
    issue=next(x for x in state['issues'] if x['kind']=='missing' and x['column']=='Revenue')
    next_version=quality.approve_imputation(pid,'Revenue',issue['id'],0)['version']
    assert next_version==1
    before=list(csv.DictReader(io.StringIO(exported(pid,0).content.decode('utf-8-sig'))))
    after=list(csv.DictReader(io.StringIO(exported(pid,1).content.decode('utf-8-sig'))))
    assert before[2]['Revenue']==''
    assert after[2]['Revenue']!=''
    assert quality.current_version(pid)==1
    response=exported(pid,0,columns=['OrderID','Region'],filters=[{'column':'Region','operator':'eq','value':'Gauteng'}])
    assert response.status_code==200,response.text
    assert 'filtered' in response.headers['content-disposition']
    subset=list(csv.DictReader(io.StringIO(response.content.decode('utf-8-sig'))))
    assert len(subset)==2
    assert list(subset[0])==['OrderID','Region']
    assert subset[0]['OrderID']=='0001'


def test_xlsx_export_is_spreadsheet_safe():
    pid,raw=project()
    response=exported(pid,fmt='xlsx')
    assert response.status_code==200,response.text
    wb=openpyxl.load_workbook(io.BytesIO(response.content),read_only=False,data_only=False)
    ws=wb.active
    headers=[cell.value for cell in ws[1]]
    assert headers==['OrderID','Region','Revenue','Note']
    for row in (2,3,4):
        cell=ws.cell(row,4)
        assert cell.data_type!='f'
        assert cell.value.startswith("'")
    assert ws.cell(2,1).value=='0001'
    assert quality.current_version(pid)==0
    assert Path(storage.get_project(pid)['dataset_path']).read_bytes()==raw


def test_invalid_version_columns_filter_fail_without_side_effects():
    pid,raw=project()
    invalid=[
      {'version':900,'format':'csv'},
      {'version':0,'format':'csv','columns':['Missing']},
      {'version':0,'format':'csv','columns':['Region','Region']},
      {'version':0,'format':'csv','filters':[{'column':'Unknown','operator':'eq','value':'a'}]},
      {'version':0,'format':'csv','filters':[{'column':'Region','operator':'gt','value':20}]},
      {'version':0,'format':'exe'},
    ]
    for body in invalid:
        result=client.post(f'/api/projects/{pid}/quality/export',json=body)
        assert result.status_code in (404,422), (body,result.status_code,result.text)
    assert quality.current_version(pid)==0
    assert Path(storage.get_project(pid)['dataset_path']).read_bytes()==raw
    assert not list((storage.HOME/'export_tmp').glob('pilotodin-*'))


def test_filtered_numeric_and_missing_rows():
    pid,_=project()
    assert exported(pid,filters=[{'column':'Revenue','operator':'gte','value':200}]).headers['X-PilotODIN-Exported-Rows']=='2'
    assert exported(pid,filters=[{'column':'Revenue','operator':'is_null'}]).headers['X-PilotODIN-Exported-Rows']=='1'
    assert exported(pid,filters=[{'column':'Region','operator':'contains','value':'GAU'}]).headers['X-PilotODIN-Exported-Rows']=='2'


def test_dangerous_column_header_escaped_for_excel():
    df=pd.DataFrame({'OrderID':['001','002'],'=HYPERLINK("https://example.test")':['a','b'],'Revenue':[5,6]})
    r=client.post('/api/projects',files={'file':('headers.csv',df.to_csv(index=False).encode(),'text/csv')})
    assert r.status_code==201,r.text
    pid=r.json()['id']
    csv_result=exported(pid,fmt='csv')
    assert csv_result.status_code==200,csv_result.text
    assert "'=HYPERLINK" in csv_result.content.decode('utf-8-sig')
    excel_result=exported(pid,fmt='xlsx')
    assert excel_result.status_code==200,excel_result.text
    wb=openpyxl.load_workbook(io.BytesIO(excel_result.content))
    assert wb.active.cell(1,2).data_type!='f'
    assert wb.active.cell(1,2).value.startswith("'=")
