"""Integrated workspace contract tests. No browser or cloud dependency."""
import io
import os
import sys
import tempfile
from pathlib import Path
os.environ.setdefault('PILOTODIN_HOME',tempfile.mkdtemp(prefix='pilotodin-macro-tests-'))
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient
from tests.quality_compat_client import LegacyQualityClient
from backend.main import app
from backend import storage,quality

c=LegacyQualityClient(TestClient(app))


def upload(frame,name='retail.csv'):
    r=c.post('/api/projects',files={'file':(name,frame.to_csv(index=False).encode('utf-8'),'text/csv')})
    assert r.status_code==201,r.text
    return r.json()['id']


def demo(n=105):
    rng=np.random.default_rng(21)
    region=np.array(['Gauteng']*45+['GAUTENG']*6+['Mpumalanga']*(n-56)+['Mpimilanga']*5)
    assert len(region)==n
    mark=rng.integers(50,400,n)
    status=np.where(mark>230,'Yes','No')
    return pd.DataFrame({'TransactionID':[f'{i:07}' for i in range(n)],'Province':region,
                         'SalesAmount':mark.astype(float),'Flagged':status,'Salesperson':rng.choice(['Nandi','Lebo'],n)})

@pytest.fixture
def pid():return upload(demo())

def test_overview_and_sane_column_metadata(pid):
    r=c.get(f'/api/projects/{pid}/explore/overview');assert r.status_code==200,r.text
    d=r.json();assert d['rows']==105 and d['version']==0
    assert {x['name'] for x in d['columns']}==set(demo().columns)
    assert d['source']=='local_computed'


def test_bounded_charts(pid):
    root=f'/api/projects/{pid}/explore/chart'
    bar=c.get(root,params={'x':'Province','kind':'bar'}).json()
    assert bar['type']=='bar' and sum(row['value'] for row in bar['data'])==105
    hist=c.get(root,params={'x':'SalesAmount','kind':'histogram','bins':8}).json()
    assert len(hist['data'])==8 and sum(row['value'] for row in hist['data'])==105
    scatter=c.get(root,params={'x':'SalesAmount','y':'TransactionID','kind':'scatter'})
    assert scatter.status_code==200, scatter.text
    box=c.get(root,params={'x':'SalesAmount','kind':'box'}).json()
    assert box['data'][0]['min']<=box['data'][0]['median']<=box['data'][0]['max']
    line=c.get(root,params={'x':'Province','y':'SalesAmount','kind':'line','aggregation':'mean'})
    assert line.status_code==200,line.text


def test_plot_validation_and_reject_unbounded_bins(pid):
    root=f'/api/projects/{pid}/explore/chart'
    assert c.get(root,params={'x':'ThisColumnDoesNotExist'}).status_code==422
    assert c.get(root,params={'x':'Province','kind':'exfiltrate'}).status_code==422
    assert c.get(root,params={'x':'Province','bins':100000}).status_code==422
    assert c.get(root,params={'x':'Province','kind':'scatter'}).status_code==422


def test_proactive_findings_and_feature_screening(pid):
    insights=c.get(f'/api/projects/{pid}/explore/insights').json()
    assert insights['method']=='deterministic_descriptive_rules'
    rec=c.get(f'/api/projects/{pid}/features',params={'target':'Flagged'}).json()
    assert rec['version']==0 and rec['target']=='Flagged'
    assert any(x['column']=='TransactionID' and x['risk']=='high' for x in rec['features'])
    assert c.get(f'/api/projects/{pid}/features?target=WRONG').status_code==422


def test_local_assistant_evidence_not_fabricated(pid):
    endpoint=f'/api/projects/{pid}/assistant'
    r=c.post(endpoint,json={'question':'Which columns have missing values?'})
    assert r.status_code==200
    assert 'missing' in r.json()['answer'].lower() and r.json()['source']=='local_computed_rules'
    assert 'LLM' in r.json()['limitations']
    assert c.post(endpoint,json={'question':' ' * 351}).status_code==422
    assert c.post(endpoint,json={'question':''}).status_code==422


def test_working_cleaned_data_propagates_to_charts_and_features(pid):
    q=c.get(f'/api/projects/{pid}/quality').json()
    correction=next(x for x in q['issues'] if x['kind']=='spelling' and x['proposal'] and x['proposal'].get('from')=='Mpimilanga')
    r=c.post(f'/api/projects/{pid}/quality/decisions',json={'expected_version':0,'issue_id':correction['id'],'decision':'approve'})
    assert r.status_code==200,r.text
    assert r.json()['version']==1 and r.json()['action']['affected_rows']==5
    chart=c.get(f'/api/projects/{pid}/explore/chart?x=Province&kind=bar').json()
    labels={x['label'] for x in chart['data']}
    assert 'Mpimilanga' not in labels and 'Mpumalanga' in labels
    assert chart['version']==1
    assert c.get(f'/api/projects/{pid}/features?target=Flagged').json()['version']==1
    # The original file is immutable even though the working view is corrected.
    raw=storage.get_project(pid)
    assert (pd.read_csv(raw['dataset_path'])['Province']=='Mpimilanga').sum()==5


def test_model_is_pinned_to_cleaned_version_then_marked_stale(pid):
    quality_data=c.get(f'/api/projects/{pid}/quality').json()
    misspelling=next(x for x in quality_data['issues'] if x['kind']=='spelling' and x['proposal'] and x['proposal'].get('from')=='Mpimilanga')
    assert c.post(f'/api/projects/{pid}/quality/decisions',json={'expected_version':0,'issue_id':misspelling['id'],'decision':'approve'}).status_code==200
    bad=c.post(f'/api/projects/{pid}/experiments',json={'target':'Flagged','task':'classification','models':['logistic_regression'],'excluded_features':['TransactionID'],
                                                                   'acknowledge_random_split':True,'expected_quality_version':0})
    assert bad.status_code==409
    r=c.post(f'/api/projects/{pid}/experiments',json={'target':'Flagged','task':'classification','models':['logistic_regression'],
                                                      'excluded_features':['TransactionID'],'acknowledge_random_split':True,'expected_quality_version':1})
    assert r.status_code==202,r.text
    eid=r.json()['id']
    exp=c.get(f'/api/experiments/{eid}').json()
    assert exp['status']=='completed',exp['error']
    assert exp['dataset_version']==1 and not exp['is_stale']
    assert c.post(f'/api/experiments/{eid}/select',json={'model_key':'logistic_regression'}).status_code==200
    prediction=c.post(f'/api/experiments/{eid}/predict',json={'values':{'Province':'Gauteng','SalesAmount':130,'Salesperson':'Nandi'}})
    assert prediction.status_code==200,prediction.text
    assert prediction.json()['target']=='Flagged' and prediction.json()['dataset_version']==1
    case=next(x for x in c.get(f'/api/projects/{pid}/quality').json()['issues'] if x['kind']=='case_variant')
    assert c.post(f'/api/projects/{pid}/quality/decisions',json={'expected_version':1,'issue_id':case['id'],'decision':'approve'}).status_code==200
    stale=c.get(f'/api/experiments/{eid}').json()
    assert stale['is_stale'] and stale['current_version']==2
    assert c.post(f'/api/experiments/{eid}/predict',json={'values':{'Province':'Gauteng','SalesAmount':130,'Salesperson':'Nandi'}}).status_code==409
    # Stale historical results remain inspectable.
    assert stale['final_results'] and stale['selected_model']=='logistic_regression'


def test_original_leading_zeros_survive_quality_and_original_profile(pid):
    original_profile=c.get(f'/api/projects/{pid}').json()['profile']
    sample=original_profile['preview'][0]['TransactionID']
    assert sample=='0000000'
    q=c.get(f'/api/projects/{pid}/quality').json()
    assert q['preview'][0]['TransactionID']=='0000000'


def test_histogram_scatter_sample_bound_and_missing():
    df=pd.DataFrame({'X':range(800),'Y':range(800),'Region':['A']*800})
    pid=upload(df)
    scatter=c.get(f'/api/projects/{pid}/explore/chart?x=X&y=Y&kind=scatter').json()
    assert scatter['sampled'] and len(scatter['data'])==500
    assert c.get(f'/api/projects/{pid}/explore/chart?x=Region&kind=histogram').status_code==422


def test_multiclass_training_and_probability_labels():
    rng=np.random.default_rng(30)
    n=90
    x=np.repeat(np.array([15,55,100]),n//3)+rng.normal(0,4,n)
    df=pd.DataFrame({'Signal':x,'Segment':np.repeat(['Bronze','Silver','Gold'],n//3)})
    pid=upload(df)
    prep=c.get(f'/api/projects/{pid}/preparation?target=Segment')
    assert prep.status_code==200 and prep.json()['task']=='classification'
    tr=c.post(f'/api/projects/{pid}/experiments',json={'target':'Segment','task':'classification','models':['logistic_regression'],
                                                       'excluded_features':[],'acknowledge_random_split':True,'expected_quality_version':0})
    assert tr.status_code==202,tr.text
    eid=tr.json()['id']
    e=c.get(f'/api/experiments/{eid}').json()
    assert e['status']=='completed',e['error']
    selected=c.post(f'/api/experiments/{eid}/select',json={'model_key':'logistic_regression'})
    assert selected.status_code==200,selected.text
    pred=c.post(f'/api/experiments/{eid}/predict',json={'values':{'Signal':60}})
    assert pred.status_code==200,pred.text
    assert len(pred.json()['probabilities'])==3

@pytest.mark.parametrize('agg,expected',[
    ('sum',30.0),('mean',15.0),('count',2.0),('median',15.0),
])
def test_bars_aggregation_methods(agg,expected):
    pid=upload(pd.DataFrame({'Group':['A','A','B'],'Value':[10,20,50]}))
    r=c.get(f'/api/projects/{pid}/explore/chart',params={'x':'Group','y':'Value','kind':'bar','aggregation':agg})
    assert r.status_code==200,r.text
    assert next(p['value'] for p in r.json()['data'] if p['label']=='A')==expected


@pytest.mark.parametrize('question,needle',[
    ('Give me a dataset overview','rows'),
    ('Tell me about duplicate rows','duplicate'),
    ('I want to train a model','cross-validation'),
    ('Check data quality problems','findings'),
    ('Where are missing cells?','Missing values'),
])
def test_local_answers_have_grounding(question,needle,pid):
    r=c.post(f'/api/projects/{pid}/assistant',json={'question':question})
    assert r.status_code==200
    assert needle.lower() in r.json()['answer'].lower()
    assert r.json()['source']=='local_computed_rules'


@pytest.mark.parametrize('kind,expected_code',[
    ('histogram',422),('box',422),('line',422),('scatter',422),('bar',200)
])
def test_chart_type_validation_for_categories(kind,expected_code,pid):
    r=c.get(f'/api/projects/{pid}/explore/chart',params={'x':'Province','kind':kind})
    assert r.status_code==expected_code,r.text


def test_reset_to_original_marks_historical_model_stale(pid):
    q=c.get(f'/api/projects/{pid}/quality').json()
    issue=next(i for i in q['issues'] if i['kind']=='case_variant')
    assert c.post(f'/api/projects/{pid}/quality/decisions',json={'expected_version':0,'issue_id':issue['id'],'decision':'approve'}).status_code==200
    restored=c.post(f'/api/projects/{pid}/quality/restore',json={'expected_version':1,'target_version':0})
    assert restored.status_code==200,restored.text
    assert restored.json()['version']==2
    data=c.get(f'/api/projects/{pid}/quality').json()
    assert data['version']==2 and data['summary']['applied_actions']==0
    # Restoring an old version does not reset the monotonically increasing counter.
    assert c.get(f'/api/projects/{pid}/explore/overview').json()['version']==2
