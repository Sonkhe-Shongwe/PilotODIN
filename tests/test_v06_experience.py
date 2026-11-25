"""v0.6 regression checks for startup connection status and resilient AI routing.

No live cloud services or secret files are needed.
"""
from __future__ import annotations
import json
import sys
import urllib.error
from pathlib import Path
import pytest
from tests.fixture_http import fixture_client
from tests.settings_fixture import isolate_ai_store
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from backend.main import app
from backend import ai_provider

client=fixture_client(app)

@pytest.fixture(autouse=True)
def isolate(tmp_path,monkeypatch):
    isolate_ai_store(monkeypatch, ai_provider, tmp_path)
    ai_provider._memory_keys.clear();ai_provider._cooldowns.clear();ai_provider._health.clear()
    monkeypatch.setattr(ai_provider,'_last_background_check',0.0)
    for env in ai_provider.ENV_KEYS.values():monkeypatch.delenv(env,raising=False)
    yield
    ai_provider._memory_keys.clear();ai_provider._cooldowns.clear();ai_provider._health.clear()

def allow():
    ai_provider.update_settings(cloud_enabled=True,share_aggregates=True,auto_insights=True,
        provider_order=list(ai_provider.PROVIDERS),timeout_seconds=9,local_model_enabled=False)

def unavailable(status):
    return urllib.error.HTTPError('https://provider.invalid',status,'unavailable',None,None)

def test_cloud_stays_opt_in_startup(monkeypatch):
    ai_provider.set_key('gemini','TEST_SECRET_12345678')
    monkeypatch.setattr(ai_provider,'_call_provider',lambda *a,**k:pytest.fail('must not send request'))
    response=client.post('/api/ai/verify-connected')
    assert response.status_code==200 and response.json()['status']=='cached'
    assert all(p['status']=='unverified' for p in response.json()['providers'])


def test_startup_never_probes_even_configured_keys(monkeypatch):
    allow();ai_provider.set_key('gemini','TEST_SECRET_12345678')
    monkeypatch.setattr(ai_provider,'_call_provider',lambda *a,**k:pytest.fail('must not send request'))
    response=client.post('/api/ai/verify-connected')
    assert response.status_code==200 and response.json()['status']=='cached'
    assert all(p['status']=='unverified' for p in response.json()['providers'])


def test_passive_status_reuses_explicit_check_without_extra_calls(monkeypatch):
    allow();ai_provider.set_key('gemini','TEST_SECRET_12345678')
    seen=[]
    def fake(p,*args,**kwargs):
        assert kwargs['strict'] is True and kwargs['still_authorized']()
        seen.append(p)
        return 'READY'
    monkeypatch.setattr(ai_provider,'_call_provider',fake)
    assert client.post('/api/ai/verify-connected').json()['status']=='cached' and not seen
    assert client.post('/api/ai/test/gemini',json={'cloud_intent':True}).json()['status']=='connected'
    for _ in range(2):
        result=client.post('/api/ai/verify-connected').json()
        assert result['status']=='cached'
        assert next(p for p in result['providers'] if p['provider']=='gemini')['status']=='connected'
    assert seen==['gemini']


def test_new_key_invalidates_cached_explicit_status_without_probe(monkeypatch):
    allow();ai_provider.set_key('gemini','TEST_SECRET_12345678')
    seen=[]
    def fake(p,*args,**kwargs):
        assert kwargs['strict'] is True and kwargs['still_authorized']()
        seen.append(p)
        return 'READY'
    monkeypatch.setattr(ai_provider,'_call_provider',fake)
    assert client.post('/api/ai/test/gemini',json={'cloud_intent':True}).json()['status']=='connected'
    ai_provider.set_key('groq','TEST_SECRET_12345678')
    result=client.post('/api/ai/verify-connected').json()
    assert result['status']=='cached' and all(p['status']=='unverified' for p in result['providers'])
    assert seen==['gemini']


def test_gemini_503_does_not_retry_secondary_model(monkeypatch):
    allow();ai_provider.set_key('gemini','TEST_SECRET_12345678')
    seen=[]
    def fake(p,model,*args,**kwargs):
        assert kwargs['strict'] is True and kwargs['still_authorized']()
        seen.append((p,model))
        raise unavailable(503)
    monkeypatch.setattr(ai_provider,'_call_provider',fake)
    response=ai_provider.respond({'row_count':12},'overview','Analyse','Local only',selected_provider='gemini',cloud_intent=True)
    assert response['provider']=='local' and response['fallback']
    assert response['attempts']==[{'provider':'gemini','status':'unavailable'}]
    assert seen==[('gemini','gemini-3.1-flash-lite')]


def test_gemini_failure_never_dispatches_to_saved_groq(monkeypatch):
    allow()
    for p in ('gemini','groq'):ai_provider.set_key(p,'TEST_SECRET_12345678')
    seen=[]
    def fake(p,model,*args,**kwargs):
        assert kwargs['strict'] is True and kwargs['still_authorized']()
        seen.append((p,model))
        raise unavailable(503)
    monkeypatch.setattr(ai_provider,'_call_provider',fake)
    response=ai_provider.respond({},'quality','Advice','local fallback',selected_provider='gemini',cloud_intent=True)
    assert response['provider']=='local' and response['fallback']
    assert seen==[('gemini','gemini-3.1-flash-lite')]


def test_429_does_not_retry_same_provider(monkeypatch):
    allow();ai_provider.set_key('gemini','TEST_SECRET_12345678')
    calls=[]
    def fake(p,*args,**kwargs):
        assert kwargs['strict'] is True and kwargs['still_authorized']()
        calls.append(p)
        raise unavailable(429)
    monkeypatch.setattr(ai_provider,'_call_provider',fake)
    response=ai_provider.respond({},'quality','Advice','local fallback',selected_provider='gemini',cloud_intent=True)
    assert response['provider']=='local' and calls==['gemini']
    assert response['attempts']==[{'provider':'gemini','status':'unavailable'}]


def test_cloud_status_contains_no_credentials(monkeypatch):
    allow();ai_provider.set_key('gemini','A_SECRET_THAT_MUST_NEVER_LEAK_123')
    monkeypatch.setattr(ai_provider,'_call_provider',lambda *a,**k:pytest.fail('Unexpected probe'))
    result=client.post('/api/ai/verify-connected')
    assert result.status_code==200 and result.json()['status']=='cached'
    assert 'A_SECRET_THAT_MUST_NEVER_LEAK_123' not in result.text


def test_reject_cross_site_health_checks():
    response=client.post('/api/ai/verify-connected',headers={'Origin':'https://malicious.example'})
    assert response.status_code==403
