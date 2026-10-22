"""Build D backend acceptance: saved evidence must remain real across the unified UI journey.

UI/visual checks live separately; this checks the real contracts consumed by Build D.
"""
from pathlib import Path
import pandas as pd
from fastapi.testclient import TestClient
from backend.main import app
from backend import storage

client=TestClient(app)


def test_build_d_import_investigate_compare_quality_resume_without_mutating_source():
    data=(Path(__file__).resolve().parents[1]/'examples'/'demo_property_prices.csv').read_bytes()
    imported=client.post('/api/projects',files={'file':('demo_property_prices.csv',data,'text/csv')})
    assert imported.status_code==201, imported.text
    pid=imported.json()['id']
    profile=client.get(f'/api/projects/{pid}/live-profile')
    assert profile.status_code==200
    assert profile.json()['profile']['rows']==150
    assert profile.json()['profile']['missing_cells']==3
    inv=client.post(f'/api/projects/{pid}/investigations',json={'objective':'How does PropertyPrice vary by Province?'})
    assert inv.status_code==201,inv.text
    key=inv.json()['id'];version=inv.json()['version']
    url=f'/api/investigations/{key}/runs'
    runs=[('overview',{}),('compare',{'x':'Province','y':'PropertyPrice'}),('missingness',{'column':'Bedrooms'})]
    ids=[]
    for op,params in runs:
        r=client.post(url,json={'operation':op,'params':params,'expected_version':version})
        assert r.status_code==200,r.text
        artifacts=r.json()['artifacts']
        assert len(artifacts)==len(ids)+1
        assert all(a['status']=='completed' and a['version']==version for a in artifacts)
        ids.append(artifacts[-1]['id'])
    saved=client.get(f'/api/investigations/{key}')
    assert saved.status_code==200
    assert [a['id'] for a in saved.json()['artifacts']]==ids
    actual={d['label']:d['value'] for d in saved.json()['artifacts'][1]['result']['data']}
    dataframe=pd.read_csv(Path(storage.get_project(pid)['dataset_path']))
    assert actual==dataframe.groupby('Province')['PropertyPrice'].median().to_dict()
    assert saved.json()['artifacts'][2]['result']['missing_rows']==3
    assert not saved.json()['stale']
    assert Path(storage.get_project(pid)['dataset_path']).read_bytes()==data
    assert client.get(f'/api/projects/{pid}/investigations').json()[0]['evidence_count']==3
