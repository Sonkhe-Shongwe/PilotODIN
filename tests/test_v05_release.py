"""v0.5 regression, safety, AI handshake, and validation-path tests.

No external services, raw API keys, or browser dependencies are required.
"""
from __future__ import annotations

import io
import os
import sys
import urllib.error
from pathlib import Path
import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient
from tests.quality_compat_client import LegacyQualityClient

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from backend import ai_provider,analytics,engine
from backend.main import app

client=LegacyQualityClient(TestClient(app))

@pytest.fixture(autouse=True)
def isolate_ai(tmp_path,monkeypatch):
    monkeypatch.setattr(ai_provider,'CONFIG_PATH',tmp_path/'settings.json')
    monkeypatch.setattr(ai_provider,'SECRETS_PATH',tmp_path/'secrets.dpapi')
    ai_provider._memory_keys.clear();ai_provider._cooldowns.clear();ai_provider._health.clear()
    for v in ai_provider.ENV_KEYS.values(): monkeypatch.delenv(v,raising=False)
    yield
    ai_provider._memory_keys.clear();ai_provider._cooldowns.clear();ai_provider._health.clear()


def upload_df(df):
    res=client.post('/api/projects',files={'file':('v05.csv',df.to_csv(index=False).encode(),'text/csv')})
    assert res.status_code==201,res.text
    return res.json()['id']


def test_handshake_measures_real_provider_and_redacts_key(monkeypatch):
    key='PRIVATE_VALID_EXAMPLE_KEY_1234567'
    ai_provider.set_key('gemini',key)
    assert not next(p for p in ai_provider.config_status()['providers'] if p['id']=='gemini')['verified']
    seen=[]
    monkeypatch.setattr(ai_provider,'_call_provider',lambda *args:(seen.append(args) or 'READY'))
    response=client.post('/api/ai/test/gemini')
    assert response.status_code==200
    assert response.json()['status']=='connected'
    assert response.json()['latency_ms']>=0
    assert seen[0][3]=='Say READY'
    assert key not in response.text and key not in client.get('/api/ai/settings').text
    assert next(p for p in client.get('/api/ai/settings').json()['providers'] if p['id']=='gemini')['verified']


def test_handshake_bad_key_safely_reports_auth(monkeypatch):
    ai_provider.set_key('groq','TEST_SECRET_123456789')
    def fail(*_):
        raise urllib.error.HTTPError('https://safe.example',401,'bad_auth',None,None)
    monkeypatch.setattr(ai_provider,'_call_provider',fail)
    data=client.post('/api/ai/test/groq').json()
    assert data['status']=='authentication_failed'
    assert data['http_status']==401
    assert 'TEST_SECRET' not in str(data)


def test_manual_provider_preference_and_fallback(monkeypatch):
    ai_provider.update_settings(cloud_enabled=True,share_aggregates=True,auto_insights=False,
                                provider_order=['gemini','groq','openrouter'],timeout_seconds=20,
                                preferred_provider='groq',workspace_preferences={})
    for p in ('gemini','groq'):ai_provider.set_key(p,'TEST_KEY_123456_'+p)
    seen=[]
    def response(p,*rest):
        seen.append(p)
        if p=='groq':raise TimeoutError('not responding')
        return 'Reasoned answer'
    monkeypatch.setattr(ai_provider,'_call_provider',response)
    result=ai_provider.respond({'rows':30},'explore','Question','local')
    assert result['provider']=='gemini'
    assert seen==['groq','gemini']
    assert result['attempts'][0]['provider']=='groq'


def test_local_preference_never_uses_cloud(monkeypatch):
    ai_provider.update_settings(cloud_enabled=True,share_aggregates=True,auto_insights=False,
                                provider_order=['gemini','groq','openrouter'],timeout_seconds=20,
                                preferred_provider='local',workspace_preferences={})
    ai_provider.set_key('gemini','TEST_KEY_1234567')
    monkeypatch.setattr(ai_provider,'_call_provider',lambda *a: (_ for _ in ()).throw(AssertionError('Not allowed')))
    result=ai_provider.respond({},'quality','Review','Local answer')
    assert result['provider']=='local' and 'selected' in result['reason'].lower()


def test_per_workspace_override_supersedes_global(monkeypatch):
    ai_provider.update_settings(cloud_enabled=True,share_aggregates=True,auto_insights=False,
                                provider_order=['gemini','groq','openrouter'],timeout_seconds=20,
                                preferred_provider='gemini',workspace_preferences={'quality':'openrouter'})
    ai_provider.set_key('openrouter','TEST_KEY_OPENROUTER_123456')
    called=[]
    monkeypatch.setattr(ai_provider,'_call_provider',lambda p,*args:(called.append(p) or 'Review categories'))
    assert ai_provider.respond({},'quality','Review','local')['provider']=='openrouter'
    assert called==['openrouter']


def test_global_provider_validation_rejects_untrusted_selections():
    data={'cloud_enabled':True,'share_aggregates':True,'preferred_provider':'evil-command',
          'provider_order':['gemini','groq','openrouter'],'timeout_seconds':20}
    assert client.put('/api/ai/settings',json=data).status_code==422
    data['preferred_provider']='auto';data['workspace_preferences']={'quality':'execute_python'}
    assert client.put('/api/ai/settings',json=data).status_code==422


def test_classification_metrics_labels_and_accuracy_percent():
    y=pd.Series(['yes','no','yes','no'])
    pred=np.array(['yes','yes','yes','no'])
    report=engine.model_report('classification',y,pred)
    assert report['accuracy']==.75
    assert report['class_labels']==['no','yes']
    assert report['confusion_matrix']==[[1,1],[0,2]]
    assert report['class_report'][0]['support']==2
    assert all(0<=v['f1']<=1 for v in report['class_report'])


def test_bad_regression_is_not_sold_as_reliable():
    training={'task':'regression','test_rows':10,'baseline_cv':25,
             'models':[{'key':'gradient_boosting','cv_metric':90,'cv_std':70}]}
    report=engine.reliability_report(training,{'r2':-10,'mae':90},'gradient_boosting')
    assert report['level']=='warning'
    assert len(report['issues'])>=3


def test_group_split_excludes_group_identifier_and_runs():
    rng=np.random.default_rng(3)
    n=160
    groups=[f'person_{i//8:03d}' for i in range(n)]
    df=pd.DataFrame({'PersonGroup':groups,'Age':rng.normal(44,9,n),
                     'Region':rng.choice(['N','S'],n),'Target':rng.normal(200,18,n)})
    result,pipes,xt,yt=engine.run_training(df,'Target',[],['ridge'],'regression','group','PersonGroup')
    assert result['split_strategy']=='group'
    assert 'PersonGroup' not in result['features']
    assert result['test_rows']>0 and len(xt)==len(yt)


def test_time_split_runs_and_is_chronological():
    rng=np.random.default_rng(5)
    n=90
    d=pd.date_range('2025-01-01',periods=n,freq='D')
    # Deliberately shuffled dates force chronological sorting.
    df=pd.DataFrame({'When':d.strftime('%d/%m/%Y'),'Price':rng.normal(120,7,n),
                     'Weight':rng.normal(300,9,n)}).sample(frac=1,random_state=4).reset_index(drop=True)
    result,pipes,xt,yt=engine.run_training(df,'Weight',[],['ridge'],'regression','time','When')
    assert result['split_strategy']=='time'
    assert 'When' not in result['features']
    assert len(xt)==18


def test_time_split_rejects_ambiguous_missing_date():
    df=pd.DataFrame({'When':['unknown']*30+['2025-02-01']*30,'X':np.arange(60),'Y':np.arange(60)*1.5})
    with pytest.raises(ValueError,match='unparseable'):
        engine.run_training(df,'Y',[],['ridge'],'regression','time','When')


def test_group_split_rejects_too_few_groups():
    df=pd.DataFrame({'group':['one']*50,'X':np.arange(50),'Y':np.arange(50)*1.2})
    with pytest.raises(ValueError,match='6 distinct'):
        engine.run_training(df,'Y',[],['ridge'],'regression','group','group')


def test_chart_recommendations_skip_transaction_id_and_flag_skew():
    df=pd.DataFrame({'TransactionID':[f'{i:07}' for i in range(48)],
                     'Province':['Gauteng']*25+['Mpumalanga']*23,
                     'SalesAmount':[102]*47+[9999]})
    rec=analytics.recommended_charts(df,2)['recommendations']
    assert rec and rec[0]['x']=='Province'
    assert any('extreme' in x['title'].lower() for x in rec)
    assert all(x['x']!='TransactionID' for x in rec)


def test_investigation_allowlist_blocks_arbitrary_code():
    df=pd.DataFrame({'x':[1,2,999],'y':['N','N','S']})
    assert analytics.investigate(df,0,'numeric_distribution','x')['outliers_by_iqr']>=0
    with pytest.raises(ValueError,match='Unsupported'):
        analytics.investigate(df,0,'exec_python','x')


def test_live_profile_matches_current_quality_version():
    df=pd.DataFrame({'TransactionID':[f'{i:07}' for i in range(48)],
                     'Province':[' Gauteng ']*3+['Gauteng']*45,'SalesAmount':np.arange(48)+1})
    pid=upload_df(df)
    before=client.get(f'/api/projects/{pid}/live-profile').json()
    assert before['version']==0
    updated=client.post(f'/api/projects/{pid}/quality/autopilot',json={'expected_version':0})
    assert updated.status_code==200,updated.text
    after=client.get(f'/api/projects/{pid}/live-profile').json()
    assert after['version']==1
    assert after['profile']['columns'][1]['unique']<=before['profile']['columns'][1]['unique']


def test_investigation_endpoint_can_be_used_without_cloud():
    df=pd.DataFrame({'X':range(48),'Y':range(48),'Province':['A']*24+['B']*24})
    pid=upload_df(df)
    r=client.post(f'/api/projects/{pid}/investigate',json={'operation':'recommend_charts'})
    assert r.status_code==200 and r.json()['recommendations']
    assert client.post(f'/api/projects/{pid}/investigate',json={'operation':'eval'}).status_code==422
