"""v0.6 regression checks for startup connection status and resilient AI routing.

No live cloud services or secret files are needed.
"""
from __future__ import annotations
import json
import sys
import urllib.error
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from backend.main import app
from backend import ai_provider

client=TestClient(app)

@pytest.fixture(autouse=True)
def isolate(tmp_path,monkeypatch):
    monkeypatch.setattr(ai_provider,'CONFIG_PATH',tmp_path/'settings.json')
    monkeypatch.setattr(ai_provider,'SECRETS_PATH',tmp_path/'secrets.dpapi')
    ai_provider._memory_keys.clear();ai_provider._cooldowns.clear();ai_provider._health.clear()
    monkeypatch.setattr(ai_provider,'_last_background_check',0.0)
    for env in ai_provider.ENV_KEYS.values():monkeypatch.delenv(env,raising=False)
    yield
    ai_provider._memory_keys.clear();ai_provider._cooldowns.clear();ai_provider._health.clear()

def allow():
    ai_provider.update_settings(cloud_enabled=True,share_aggregates=True,auto_insights=True,
        provider_order=list(ai_provider.PROVIDERS),timeout_seconds=9)

def unavailable(status):
    return urllib.error.HTTPError('https://provider.invalid',status,'unavailable',None,None)

def test_cloud_stays_opt_in_startup(monkeypatch):
    ai_provider.set_key('gemini','TEST_SECRET_12345678')
    monkeypatch.setattr(ai_provider,'test_connection',lambda _: (_ for _ in ()).throw(AssertionError('must not send request')))
    response=client.post('/api/ai/verify-connected')
    assert response.status_code==200
    assert response.json()['status']=='disabled'

def test_startup_verifies_only_configured_keys(monkeypatch):
    allow();ai_provider.set_key('gemini','TEST_SECRET_12345678')
    seen=[]
    def fake(p):
        seen.append(p)
        ai_provider._health[p]={'status':'connected'}
        return {'provider':p,'status':'connected'}
    monkeypatch.setattr(ai_provider,'test_connection',fake)
    response=client.post('/api/ai/verify-connected')
    assert response.status_code==200 and response.json()['status']=='checked'
    assert seen==['gemini']
    assert response.json()['providers']==[{'provider':'gemini','status':'connected'}]

def test_startup_reuses_recent_verification_without_extra_api_calls(monkeypatch):
    allow();ai_provider.set_key('gemini','TEST_SECRET_12345678')
    seen=[]
    monkeypatch.setattr(ai_provider,'test_connection',lambda p: seen.append(p) or {'provider':p,'status':'connected'})
    assert client.post('/api/ai/verify-connected').json()['status']=='checked'
    assert client.post('/api/ai/verify-connected').json()['status']=='cached'
    assert seen==['gemini']

def test_new_key_invalidates_cached_startup_results(monkeypatch):
    allow();ai_provider.set_key('gemini','TEST_SECRET_12345678')
    seen=[]
    monkeypatch.setattr(ai_provider,'test_connection',lambda p: seen.append(p) or {'provider':p,'status':'connected'})
    client.post('/api/ai/verify-connected')
    ai_provider.set_key('groq','TEST_SECRET_12345678')
    assert client.post('/api/ai/verify-connected').json()['status']=='checked'
    assert seen.count('gemini')==2 and seen.count('groq')==1

def test_gemini_503_retries_secondary_model(monkeypatch):
    allow();ai_provider.set_key('gemini','TEST_SECRET_12345678')
    seen=[]
    def fake(p,model,*_):
        seen.append((p,model))
        if model=='gemini-3.1-flash-lite':raise unavailable(503)
        return 'Grounded summary from alternate Gemini model.'
    monkeypatch.setattr(ai_provider,'_call_provider',fake)
    response=ai_provider.respond({'row_count':12},'overview','Analyse','Local only')
    assert response['provider']=='gemini' and response['model']=='gemini-2.5-flash-lite'
    assert response['attempts'][0]['status']=='http_503_retry_alternate'
    assert len(seen)==2

def test_secondary_gemini_failure_then_groq(monkeypatch):
    allow()
    for p in ('gemini','groq'):ai_provider.set_key(p,'TEST_SECRET_12345678')
    seen=[]
    def fake(p,model,*_):
        seen.append((p,model))
        if p=='gemini':raise unavailable(503)
        return 'Recovered by independent provider'
    monkeypatch.setattr(ai_provider,'_call_provider',fake)
    response=ai_provider.respond({},'quality','Advice','local fallback')
    assert response['provider']=='groq'
    assert seen[-1]==('groq','openai/gpt-oss-120b')
    assert len(seen)==3

def test_429_does_not_retry_same_provider(monkeypatch):
    allow();ai_provider.set_key('gemini','TEST_SECRET_12345678')
    calls=[]
    def fake(p,*_):calls.append(p);raise unavailable(429)
    monkeypatch.setattr(ai_provider,'_call_provider',fake)
    response=ai_provider.respond({},'quality','Advice','local fallback')
    assert response['provider']=='local' and calls==['gemini']
    assert response['attempts']==[{'provider':'gemini','status':'http_429'}]

def test_cloud_status_contains_no_credentials(monkeypatch):
    allow();ai_provider.set_key('gemini','A_SECRET_THAT_MUST_NEVER_LEAK_123')
    monkeypatch.setattr(ai_provider,'test_connection',lambda p:{'provider':p,'status':'unavailable','message':'Overloaded'})
    result=client.post('/api/ai/verify-connected')
    assert result.status_code==200
    assert 'A_SECRET_THAT_MUST_NEVER_LEAK_123' not in result.text

def test_reject_cross_site_health_checks():
    response=client.post('/api/ai/verify-connected',headers={'Origin':'https://malicious.example'})
    assert response.status_code==403
