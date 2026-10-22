"""Multi-provider intelligence: opt-in privacy, routing, resilience and API contracts.

No actual cloud calls or API credentials required. Live provider connectivity must
be tested by a user who has their own credentials configured.
"""
from __future__ import annotations
import io
import json
import os
import sys
import tempfile
import urllib.error
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import pytest
from fastapi.testclient import TestClient
from backend import ai_provider,ai_context,quality,storage
from backend.main import app

client=TestClient(app)

@pytest.fixture(autouse=True)
def clean_ai_config(tmp_path,monkeypatch):
    monkeypatch.setattr(ai_provider,'CONFIG_PATH',tmp_path/'ai_settings.json')
    monkeypatch.setattr(ai_provider,'SECRETS_PATH',tmp_path/'ai_secrets.dpapi')
    ai_provider._memory_keys.clear();ai_provider._cooldowns.clear()
    for env in ai_provider.ENV_KEYS.values():monkeypatch.delenv(env,raising=False)
    yield
    ai_provider._memory_keys.clear();ai_provider._cooldowns.clear()

@pytest.fixture
def pid():
    csv='TransactionID,Province,SalesAmount,CustomerSegment,InvoiceDate\n'
    for i in range(48):
        place='Private Person Alice' if i==20 else ('Mpimilanga' if i in (21,22,23) else 'Gauteng')
        amount=8900 if i==31 else (100+i%7)
        csv+=f'{i:07},{place},{amount},{"Retail" if i%2 else "Corporate"},14/04/2025\n'
    r=client.post('/api/projects',files={'file':('custom.csv',csv.encode(),'text/csv')})
    assert r.status_code==201,r.text
    return r.json()['id']


def settings(**opts):
    return ai_provider.update_settings(cloud_enabled=opts.get('cloud_enabled',True),
         share_aggregates=opts.get('share_aggregates',True),
         auto_insights=opts.get('auto_insights',False),
         provider_order=opts.get('provider_order',['gemini','groq','openrouter']),
         timeout_seconds=opts.get('timeout_seconds',5))


def test_disabled_by_default_and_no_credentials_leaked():
    r=client.get('/api/ai/settings')
    assert r.status_code==200
    assert r.json()['cloud_enabled'] is False
    assert r.json()['share_aggregates'] is False
    assert len(r.json()['providers'])==3
    assert all(not x['connected'] for x in r.json()['providers'])


def test_keys_stored_and_never_returned():
    key='MY_SENSITIVE_TEST_KEY_1234567'
    r=client.put('/api/ai/key',json={'provider':'gemini','key':key})
    assert r.status_code==200 and r.json()['providers'][0]['connected']
    assert key not in r.text and key not in client.get('/api/ai/settings').text
    assert ai_provider._get_key('gemini')==key
    assert not ai_provider.CONFIG_PATH.exists()
    assert not ai_provider.SECRETS_PATH.exists() if sys.platform!='win32' else ai_provider.SECRETS_PATH.exists()


def test_remove_key():
    ai_provider.set_key('groq','groq_valid_test_key_12345')
    r=client.put('/api/ai/key',json={'provider':'groq','remove':True})
    assert r.status_code==200 and not next(x for x in r.json()['providers'] if x['id']=='groq')['connected']

@pytest.mark.parametrize('provider,key', [('grok','goodsecret123456'),('gemini','a'),('groq','contains spaces 12345')])
def test_key_validation(provider,key):
    assert client.put('/api/ai/key',json={'provider':provider,'key':key}).status_code==422


def test_cloud_cannot_enable_without_opt_in():
    r=client.put('/api/ai/settings',json={'cloud_enabled':True,'share_aggregates':False})
    assert r.status_code==422
    assert client.get('/api/ai/settings').json()['cloud_enabled'] is False


def test_settings_persist_without_creds():
    r=client.put('/api/ai/settings',json={'cloud_enabled':True,'share_aggregates':True,
                    'provider_order':['groq','gemini','openrouter'],'timeout_seconds':12,'auto_insights':True})
    assert r.status_code==200,r.text
    assert client.get('/api/ai/settings').json()['provider_order'][0]=='groq'
    assert json.loads(ai_provider.CONFIG_PATH.read_text())['auto_insights']
    assert 'API_KEY' not in ai_provider.CONFIG_PATH.read_text()

@pytest.mark.parametrize('order', [[],['gemini','groq'],['gemini','gemini','groq'],['groq','openrouter','random']])
def test_invalid_orders_rejected(order):
    r=client.put('/api/ai/settings',json={'share_aggregates':True,'provider_order':order})
    assert r.status_code==422

@pytest.mark.parametrize('seconds',[1,2,46,100])
def test_invalid_timeouts_rejected(seconds):
    r=client.put('/api/ai/settings',json={'share_aggregates':True,'timeout_seconds':seconds})
    assert r.status_code==422


def test_no_origin_cross_site_for_ai_settings_or_inference(pid):
    h={'Origin':'https://external.attacker.example'}
    assert client.get('/api/ai/settings',headers=h).status_code==403
    assert client.put('/api/ai/key',headers=h,json={'provider':'gemini','key':'testkey123456789'}).status_code==403
    assert client.post(f'/api/projects/{pid}/ai/insight',headers=h,json={'context':'quality'}).status_code==403


def test_local_without_keys_does_not_attempt_cloud(pid,monkeypatch):
    def wrong(*a):raise AssertionError('Cloud must not run')
    monkeypatch.setattr(ai_provider,'_call_provider',wrong)
    r=client.post(f'/api/projects/{pid}/ai/insight',json={'context':'quality','question':'What issues?'})
    assert r.status_code==200,r.text
    assert r.json()['provider']=='local' and r.json()['fallback']
    assert r.json()['privacy']=='summary_only_no_rows'


def test_connected_but_cloud_not_enabled_still_local(pid,monkeypatch):
    ai_provider.set_key('gemini','api_key_gemini_sample_123')
    monkeypatch.setattr(ai_provider,'_call_provider',lambda *args: (_ for _ in ()).throw(AssertionError('Must not call cloud')))
    assert client.post(f'/api/projects/{pid}/ai/insight',json={'context':'assistant','question':'Tell me about quality'}).json()['fallback']


def test_primary_gemini_cloud_result(pid,monkeypatch):
    settings();ai_provider.set_key('gemini','gemini_local_testing_key')
    called=[]
    def fake(provider,model,system,user,key,timeout):
        called.append((provider,model,user));return 'Check the outlier and confirm categories before trusting the mean.'
    monkeypatch.setattr(ai_provider,'_call_provider',fake)
    r=client.post(f'/api/projects/{pid}/ai/insight',json={'context':'explore'})
    assert r.status_code==200 and not r.json()['fallback']
    assert r.json()['provider']=='gemini'
    assert r.json()['model']=='gemini-3.1-flash-lite'
    assert called[0][0]=='gemini'
    assert 'Private Person Alice' not in called[0][2]
    assert 'Mpimilanga' not in called[0][2]


def test_deeper_model_route(pid,monkeypatch):
    settings();ai_provider.set_key('gemini','gemini_local_testing_key')
    used=[]
    monkeypatch.setattr(ai_provider,'_call_provider',lambda p,m,*a: (used.append(m) or 'Exploratory finding'))
    r=client.post(f'/api/projects/{pid}/ai/insight',json={'context':'model','deep':True,'target':'SalesAmount'})
    assert r.status_code==200 and used==['gemini-3-flash-preview']


def test_gemini_rate_limit_fails_over_to_groq(pid,monkeypatch):
    settings();ai_provider.set_key('gemini','gemini_local_testing_key');ai_provider.set_key('groq','groq_local_testing_key')
    called=[]
    def fake(p,*_):
        called.append(p)
        if p=='gemini':raise urllib.error.HTTPError('https://example.test',429,'quota',None,None)
        return 'Groq verified interpretation'
    monkeypatch.setattr(ai_provider,'_call_provider',fake)
    r=client.post(f'/api/projects/{pid}/ai/insight',json={'context':'quality'})
    assert r.status_code==200 and r.json()['provider']=='groq'
    assert r.json()['attempts']==[{'provider':'gemini','status':'http_429'}]
    assert called==['gemini','groq']


def test_three_failures_result_in_local_fallback(pid,monkeypatch):
    settings()
    for p in ai_provider.PROVIDERS:ai_provider.set_key(p,'local_testing_key_for_'+p)
    called=[]
    def fail(p,*_):called.append(p);raise TimeoutError('sensitive_private_key_never_report')
    monkeypatch.setattr(ai_provider,'_call_provider',fail)
    r=client.post(f'/api/projects/{pid}/ai/insight',json={'context':'assistant','question':'What is the dataset overview?'})
    assert r.status_code==200
    data=r.json()
    assert data['fallback'] and data['provider']=='local' and len(data['attempts'])==3
    assert 'sensitive_private_key' not in r.text
    assert called==list(ai_provider.PROVIDERS)


def test_cooldown_prevents_repeated_failed_provider(pid,monkeypatch):
    settings();ai_provider.set_key('gemini','gemini_local_testing_key');ai_provider.set_key('groq','groq_local_testing_key')
    called=[]
    def fake(p,*_):
        called.append(p)
        if p=='gemini':raise urllib.error.HTTPError('https://test',429,'quota',None,None)
        return 'Fallback results'
    monkeypatch.setattr(ai_provider,'_call_provider',fake)
    for _ in range(2):assert client.post(f'/api/projects/{pid}/ai/insight',json={'context':'overview'}).status_code==200
    assert called==['gemini','groq','groq']


def test_context_has_no_raw_rows_or_category_values(pid):
    data=ai_context.build(pid,'quality')
    serialized=json.dumps(data)
    assert 'Private Person Alice' not in serialized
    assert 'Mpimilanga' not in serialized
    assert '0000020' not in serialized
    assert 'dataset_path' not in serialized
    assert 'sample_values' not in serialized
    assert 'SalesAmount' in serialized and 'quality_findings' in serialized
    assert any(x['column']=='SalesAmount' for x in data['computed_patterns'])

@pytest.mark.parametrize('scope',list(ai_context.TASKS))
def test_all_application_workspaces_have_ai_scope(pid,scope):
    response=client.post(f'/api/projects/{pid}/ai/insight',json={'context':scope})
    assert response.status_code==200,response.text
    assert response.json()['scope']==scope
    assert response.json()['provider']=='local'


def test_invalid_workspace_and_missing_project(pid):
    assert client.post(f'/api/projects/{pid}/ai/insight',json={'context':'execute_python'}).status_code==422
    assert client.post('/api/projects/absent/ai/insight',json={'context':'quality'}).status_code==404


def test_ai_requests_cannot_change_dataset_or_approve_actions(pid):
    version=quality.current_version(pid)
    data=storage.get_project(pid)
    before=Path(data['dataset_path']).read_bytes()
    for task in ('quality','prepare','predict','model'):
        assert client.post(f'/api/projects/{pid}/ai/insight',json={'context':task}).status_code==200
    assert quality.current_version(pid)==version
    assert Path(data['dataset_path']).read_bytes()==before


def test_env_var_key_detected_without_writing_to_disk(monkeypatch):
    monkeypatch.setenv('GEMINI_API_KEY','environment_secret_for_test')
    status=client.get('/api/ai/settings').json()
    assert status['providers'][0]['connected']
    assert 'environment_secret_for_test' not in json.dumps(status)


def test_prompt_never_contains_secret(pid,monkeypatch):
    settings(); key='gemini_private_super_secret_key'
    ai_provider.set_key('gemini',key)
    def fake(p,m,system,user,cred,timeout):
        assert cred==key
        assert key not in user and key not in system
        assert 'No personal data' in system
        return 'Use validated rules.'
    monkeypatch.setattr(ai_provider,'_call_provider',fake)
    assert client.post(f'/api/projects/{pid}/ai/insight',json={'context':'quality'}).status_code==200

class _HTTPReply:
    def __init__(self,data):self.data=json.dumps(data).encode('utf-8')
    def __enter__(self):return self
    def __exit__(self,*_):return False
    def read(self,limit):return self.data[:limit]


def test_real_gemini_wire_format_without_network(monkeypatch):
    sent=[]
    def fake(request,timeout):
        sent.append(request)
        return _HTTPReply({'candidates':[{'content':{'parts':[{'text':'Evidence-based Gemini answer.'}]}}]})
    monkeypatch.setattr(ai_provider.urllib.request,'urlopen',fake)
    value=ai_provider._call_provider('gemini','gemini-3.1-flash-lite','system','question','test-secret-key',7)
    assert value=='Evidence-based Gemini answer.'
    assert '/models/gemini-3.1-flash-lite:generateContent' in sent[0].full_url
    assert sent[0].get_header('X-goog-api-key')=='test-secret-key'
    request=json.loads(sent[0].data)
    assert request['contents'][0]['parts'][0]['text']=='question'
    assert request['systemInstruction']['parts'][0]['text']=='system'
    assert sent[0].full_url.startswith('https://')


@pytest.mark.parametrize('provider,expected_domain',[
    ('groq','api.groq.com'),('openrouter','openrouter.ai')
])
def test_openai_compatible_wire_format_without_network(monkeypatch,provider,expected_domain):
    sent=[]
    def fake(request,timeout):
        sent.append(request)
        return _HTTPReply({'choices':[{'message':{'content':'Validated response'}}]})
    monkeypatch.setattr(ai_provider.urllib.request,'urlopen',fake)
    txt=ai_provider._call_provider(provider,ai_provider.MODELS[provider]['routine'],'instructions','context','secret',5)
    assert txt=='Validated response'
    req=sent[0];assert expected_domain in req.full_url
    assert req.get_header('Authorization')=='Bearer secret'
    assert json.loads(req.data)['messages'][1]['content']=='context'


def test_corrupt_response_triggers_safe_local_fallback(pid,monkeypatch):
    settings();ai_provider.set_key('gemini','gemini_local_testing_key')
    monkeypatch.setattr(ai_provider,'_call_provider',lambda *a: '')
    r=client.post(f'/api/projects/{pid}/ai/insight',json={'context':'quality'}).json()
    assert r['fallback'] is True and r['provider']=='local'


def test_no_sensitive_values_in_model_metrics_context(pid):
    ctx=ai_context.build(pid,'prepare',target='SalesAmount')
    text=json.dumps(ctx)
    assert 'Private Person Alice' not in text
    assert 'Mpimilanga' not in text
    assert ctx['target']=='SalesAmount'
    assert any(x['column']=='TransactionID' for x in ctx['feature_screening'])


def test_invalid_probability_objects_excluded_from_cloud_context(pid):
    # No valid experiment ID: untrusted prediction input must not be transmitted.
    ctx=ai_context.build(pid,'predict',experiment_id='unknown',prediction={'prediction':'private_payload','probabilities':[{'class':'Alice','probability':1}]})
    assert 'private_payload' not in json.dumps(ctx)


def test_useful_local_quality_and_explore_advice(pid):
    context=ai_context.build(pid,'quality')
    text=ai_context.local_advice(context,'quality')
    assert 'identifier' in text.lower() and 'quality changes require' in text.lower()
    explored=ai_context.local_advice(ai_context.build(pid,'explore'),'explore')
    assert 'mean' in explored.lower() and 'median' in explored.lower()
