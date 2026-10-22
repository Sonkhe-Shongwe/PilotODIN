"""Investigations persist verified read-only artifacts and honor data lineage."""
import io
import importlib
from pathlib import Path

import pandas as pd
from fastapi.testclient import TestClient
from tests.quality_compat_client import LegacyQualityClient

from backend.main import app
from backend import quality, storage, investigations

client = LegacyQualityClient(TestClient(app))


def new_project():
    raw = (Path(__file__).resolve().parents[1] / 'examples' / 'demo_property_prices.csv').read_bytes()
    response = client.post('/api/projects', files={'file':('property_example.csv', raw, 'text/csv')})
    assert response.status_code == 201, response.text
    return response.json()['id'], raw


def new_investigation(pid):
    r = client.post(f'/api/projects/{pid}/investigations', json={'objective':'How does property price vary by province?'})
    assert r.status_code == 201, r.text
    return r.json()


def test_new_investigation_starts_empty_and_resumes_after_reload():
    pid, raw = new_project()
    inv = new_investigation(pid)
    assert inv['version'] == 0 and inv['artifacts'] == []
    assert client.get(f'/api/projects/{pid}/investigations').json()[0]['id'] == inv['id']
    first = client.post(f"/api/investigations/{inv['id']}/runs", json={'operation':'overview','params':{},'expected_version':0})
    assert first.status_code == 200, first.text
    artifact = first.json()['artifacts'][0]
    assert artifact['result']['summary']['rows'] == 150
    assert artifact['version'] == 0 and artifact['status'] == 'completed'
    assert artifact['tool_version'] == 'analytics.v0.8'
    importlib.reload(investigations)
    restored = client.get(f"/api/investigations/{inv['id']}").json()
    assert restored['artifacts'][0]['id'] == artifact['id']
    assert not restored['stale']
    assert Path(storage.get_project(pid)['dataset_path']).read_bytes() == raw


def test_compare_evidence_is_calculated_and_versioned():
    pid, _ = new_project()
    inv = new_investigation(pid)
    response = client.post(f"/api/investigations/{inv['id']}/runs",
                           json={'operation':'compare','params':{'x':'Province','y':'PropertyPrice'},'expected_version':0})
    assert response.status_code == 200, response.text
    art = response.json()['artifacts'][0]
    assert art['params'] == {'x':'Province','y':'PropertyPrice','aggregation':'median'}
    assert art['result']['type'] == 'bar'
    data = pd.read_csv(Path(storage.get_project(pid)['dataset_path']))
    expected = data.groupby('Province')['PropertyPrice'].median().to_dict()
    result = {d['label']:d['value'] for d in art['result']['data']}
    assert result == expected


def test_invalid_tools_and_columns_never_create_artifacts():
    pid, _ = new_project()
    inv = new_investigation(pid)
    url = f"/api/investigations/{inv['id']}/runs"
    for payload in [
        {'operation':'execute_python','params':{'code':'print(1)'},'expected_version':0},
        {'operation':'compare','params':{'x':'bad','y':'PropertyPrice'},'expected_version':0},
        {'operation':'compare','params':{'x':'Province','y':'Province'},'expected_version':0},
        {'operation':'distribution','params':{'column':'none'},'expected_version':0},
        {'operation':'missingness','params':{'column':'Province'},'expected_version':0},
    ]:
        r = client.post(url,json=payload)
        assert r.status_code == 422, r.text
    assert client.get(f"/api/investigations/{inv['id']}").json()['artifacts'] == []


def test_quality_change_marks_prior_evidence_stale_and_rejects_new_run():
    pid, raw = new_project()
    inv = new_investigation(pid)
    run_url = f"/api/investigations/{inv['id']}/runs"
    assert client.post(run_url,json={'operation':'missingness','params':{'column':'Bedrooms'},'expected_version':0}).status_code == 200
    state = client.get(f'/api/projects/{pid}/quality').json()
    missing_issue = next(i for i in state['issues'] if i['kind']=='missing' and i['column']=='Bedrooms')
    changed = client.post(f'/api/projects/{pid}/quality/impute',json={
        'expected_version':0,'issue_id':missing_issue['id'],'column':'Bedrooms','strategy':'median'})
    assert changed.status_code == 200, changed.text
    restored = client.get(f"/api/investigations/{inv['id']}").json()
    assert restored['stale'] and restored['current_version'] == 1 and restored['artifacts'][0]['stale']
    assert client.post(run_url,json={'operation':'overview','params':{},'expected_version':0}).status_code == 409
    fresh = new_investigation(pid)
    assert fresh['version'] == 1 and not fresh['stale']
    assert Path(storage.get_project(pid)['dataset_path']).read_bytes() == raw


def test_missing_id_bad_version_and_empty_objective_handled():
    pid, _ = new_project()
    assert client.get('/api/investigations/no-such-id').status_code == 404
    assert client.post(f'/api/projects/{pid}/investigations',json={'objective':'short'}).status_code == 422
    inv = new_investigation(pid)
    assert client.post(f"/api/investigations/{inv['id']}/runs",json={
        'operation':'overview','params':{},'expected_version':9}).status_code == 409
