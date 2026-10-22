"""Executable end-to-end tests using a temporary local project store."""
import io
import os
import sys
import tempfile
from pathlib import Path

os.environ['PILOTODIN_HOME'] = tempfile.mkdtemp(prefix='pilotodin-tests-')
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient
from backend.main import app

client=TestClient(app)


def upload_frame(frame:pd.DataFrame, ext='.csv'):
    if ext=='.csv': data=frame.to_csv(index=False).encode()
    else:
        f=io.BytesIO()
        frame.to_excel(f,index=False)
        data=f.getvalue()
    resp=client.post('/api/projects',files={'file':('sample'+ext,data,'text/csv')})
    assert resp.status_code==201, resp.text
    return resp.json()['id']


def train(pid,target,task,models,exclude=[]):
    result=client.post(f'/api/projects/{pid}/experiments',json={
        'target':target,'task':task,'models':models,'excluded_features':exclude,
        'acknowledge_random_split':True})
    assert result.status_code==202, result.text
    exp=client.get(f'/api/experiments/{result.json()["id"]}').json()
    assert exp['status']=='completed',exp.get('error')
    return exp


def test_binary_classification_end_to_end():
    rng=np.random.default_rng(11)
    n=110
    age=rng.integers(25,75,n).astype(float)
    score=age + rng.normal(0,13,n)
    labels=np.where(score>51,'high','low')
    area=rng.choice(['North','South','East'],n)
    frame=pd.DataFrame({'PatientID':[f'P{i}' for i in range(n)],'Age':age,'Area':area,'HeartDisease':labels})
    frame.loc[5:10,'Age']=np.nan
    pid=upload_frame(frame)
    profile=client.get(f'/api/projects/{pid}').json()['profile']
    assert 'HeartDisease' in profile['target_candidates']
    assert profile['missing_cells']==6
    prep=client.get(f'/api/projects/{pid}/preparation?target=HeartDisease').json()
    assert prep['task']=='classification'
    assert any(x['column']=='PatientID' for x in prep['recommend_exclude'])
    exp=train(pid,'HeartDisease','classification',['logistic_regression','random_forest'],['PatientID'])
    assert exp['results']['test_rows']>0
    assert len(exp['results']['models'])==2
    selected=client.post(f'/api/experiments/{exp["id"]}/select',json={'model_key':'random_forest'})
    assert selected.status_code==200, selected.text
    assert 0<=selected.json()['final_results']['accuracy']<=1
    response=client.post(f'/api/experiments/{exp["id"]}/predict',json={'values':{'Age':55,'Area':'North'}})
    assert response.status_code==200,response.text
    assert response.json()['prediction'] in ['high','low']
    assert len(response.json()['probabilities'])==2
    second=client.post(f'/api/experiments/{exp["id"]}/select',json={'model_key':'logistic_regression'})
    assert second.status_code==409


def test_regression_end_to_end_xlsx():
    rng=np.random.default_rng(1)
    n=90
    areas=rng.choice(['CBD','Suburbs'],n)
    size=rng.integers(50,230,n)
    price=100_000+size*1800+(areas=='CBD')*30_000+rng.normal(0,13000,n)
    frame=pd.DataFrame({'PropertySize':size,'Area':areas,'SellingPrice':price})
    pid=upload_frame(frame,'.xlsx')
    prep=client.get(f'/api/projects/{pid}/preparation?target=SellingPrice').json()
    assert prep['task']=='regression'
    exp=train(pid,'SellingPrice','regression',['linear_regression','ridge','random_forest'])
    assert exp['results']['primary_metric'].startswith('MAE')
    resp=client.post(f'/api/experiments/{exp["id"]}/select',json={'model_key':'linear_regression'})
    assert resp.status_code==200, resp.text
    assert 'mae' in resp.json()['final_results']
    pred=client.post(f'/api/experiments/{exp["id"]}/predict',json={'values':{'PropertySize':100,'Area':'CBD'}})
    assert pred.status_code==200
    assert isinstance(pred.json()['prediction'],(int,float))


def test_multiclass_preparation_and_unapproved_split():
    frame=pd.DataFrame({'predictor':np.arange(60),'category':list('abc')*20})
    pid=upload_frame(frame)
    prep=client.get(f'/api/projects/{pid}/preparation?target=category')
    assert prep.status_code==200 and prep.json()['task']=='classification'
    req=client.post(f'/api/projects/{pid}/experiments',json={'target':'predictor','task':'regression','models':['linear_regression'],'acknowledge_random_split':False})
    assert req.status_code==422


def test_reject_unrelated_file():
    r=client.post('/api/projects',files={'file':('program.py',b'print(1)','text/plain')})
    assert r.status_code==400


def test_saved_pipeline_reusable_from_new_api_client():
    """Models and experiments are stored on disk, not in transient React state."""
    rng=np.random.default_rng(17)
    frame=pd.DataFrame({
        'FloorAreaSqm':rng.integers(45,200,80),
        'Bedrooms':rng.integers(1,5,80),
        'Province':rng.choice(['Gauteng','Mpumalanga'],80),
    })
    frame['Price']=150_000+frame['FloorAreaSqm']*1700+frame['Bedrooms']*15_000
    pid=upload_frame(frame)
    exp=train(pid,'Price','regression',['linear_regression'])
    select=client.post(f'/api/experiments/{exp["id"]}/select',json={'model_key':'linear_regression'})
    assert select.status_code==200,select.text
    # A fresh API client reads the persisted experiment and fitted pipeline artifacts.
    with TestClient(app) as resumed_client:
        saved=resumed_client.get(f'/api/projects/{pid}').json()
        assert any(item['id']==exp['id'] for item in saved['experiments'])
        response=resumed_client.post(f'/api/experiments/{exp["id"]}/predict',json={
            'values':{'FloorAreaSqm':125,'Bedrooms':3,'Province':'Gauteng'}})
        assert response.status_code==200,response.text
        assert isinstance(response.json()['prediction'],(int,float))


def test_backend_rejects_unrelated_prediction_fields():
    """The UI must omit hidden stale form values after switching projects."""
    rng=np.random.default_rng(23)
    frame=pd.DataFrame({'Amount':rng.integers(10,100,75),'Flagged':np.where(rng.random(75)>.5,'Yes','No')})
    pid=upload_frame(frame)
    exp=train(pid,'Flagged','classification',['logistic_regression'])
    assert client.post(f'/api/experiments/{exp["id"]}/select',json={'model_key':'logistic_regression'}).status_code==200
    result=client.post(f'/api/experiments/{exp["id"]}/predict',json={'values':{'Amount':50,'OldProjectField':'invalid'}})
    assert result.status_code==422
    assert 'Unknown prediction features' in result.json()['detail']
