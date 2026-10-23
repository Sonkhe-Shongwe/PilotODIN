"""Privacy-preserving local model routing tests. No Ollama installation required."""
from __future__ import annotations
import json
import sys
import urllib.error
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from backend import ai_provider
from backend.main import app
client=TestClient(app)

@pytest.fixture(autouse=True)
def config(tmp_path, monkeypatch):
    monkeypatch.setattr(ai_provider,'CONFIG_PATH',tmp_path/'settings.json')
    monkeypatch.setattr(ai_provider,'SECRETS_PATH',tmp_path/'keys.dpapi')
    ai_provider._memory_keys.clear();ai_provider._cooldowns.clear()
    for env in ai_provider.ENV_KEYS.values():monkeypatch.delenv(env,raising=False)
    yield
    ai_provider._memory_keys.clear();ai_provider._cooldowns.clear()


def setmode(mode='hybrid', cloud=False):
    return ai_provider.update_settings(
        cloud_enabled=cloud, share_aggregates=cloud, auto_insights=False,
        provider_order=list(ai_provider.PROVIDERS),timeout_seconds=7,
        intelligence_mode=mode,local_model='qwen3:1.7b',local_timeout_seconds=50)


def ctx():return {'row_count':50,'missing_cells':3,'column_count':4}


def fake_local(monkeypatch):
    requests=[]
    def run(model,system,user,timeout):
        requests.append((model,json.loads(user),timeout))
        return ai_provider.ProviderText('The provided data have 3 missing cells. Investigate first.','stop',False)
    monkeypatch.setattr(ai_provider,'_call_ollama',run)
    return requests


def test_default_is_hybrid_and_cloud_opt_in():
    data=client.get('/api/ai/settings').json()
    assert data['intelligence_mode']=='hybrid'
    assert data['local_model']=='qwen3:1.7b'
    assert data['local_ai']['url']=='http://127.0.0.1:11434'
    assert not data['cloud_enabled']


def test_local_model_before_cloud_even_when_cloud_enabled(monkeypatch):
    requests=fake_local(monkeypatch)
    monkeypatch.setattr(ai_provider,'_call_provider',lambda *args: (_ for _ in ()).throw(AssertionError('Cloud not expected')))
    setmode(cloud=True)
    ai_provider.set_key('gemini','key_for_test_00000999')
    r=ai_provider.respond(ctx(),'assistant','What is missing?','local guidance')
    assert r['source']=='local_llm' and r['provider']=='ollama'
    assert requests[0][1]['verified_context']==ctx()


def test_hybrid_local_failure_then_consented_cloud(monkeypatch):
    setmode(cloud=True)
    ai_provider.set_key('gemini','key_for_test_00000999')
    monkeypatch.setattr(ai_provider,'_call_ollama',lambda *a: (_ for _ in ()).throw(TimeoutError('LOCAL_PRIVATE_ERROR')))
    calls=[]
    monkeypatch.setattr(ai_provider,'_call_provider',lambda *args: (calls.append(args[0]) or 'Grounded cloud explanation'))
    r=ai_provider.respond(ctx(),'quality','What should I check?','local')
    # A local TimeoutError is now reported precisely without leaking its message.
    assert r['provider']=='gemini' and r['local_status']=='timeout'
    assert calls==['gemini']
    assert 'LOCAL_PRIVATE_ERROR' not in json.dumps(r)


def test_hybrid_refuses_cloud_without_consent(monkeypatch):
    setmode(cloud=False)
    ai_provider.set_key('groq','saved-but-not-authorized_12345')
    monkeypatch.setattr(ai_provider,'_call_ollama',lambda *a: (_ for _ in ()).throw(TimeoutError('offline')))
    monkeypatch.setattr(ai_provider,'_call_provider',lambda *a: (_ for _ in ()).throw(AssertionError('No cloud without consent')))
    r=ai_provider.respond(ctx(),'explore','Tell me','local statistical facts')
    assert r['source']=='local_computed_rules'
    assert r['answer']=='local statistical facts'
    assert r['provider']=='local'


def test_offline_mode_overrides_cloud_preference(monkeypatch):
    setmode(mode='local',cloud=True)
    fake_local(monkeypatch)
    ai_provider.set_key('gemini','key_for_test_00000999')
    monkeypatch.setattr(ai_provider,'_call_provider',lambda *a: (_ for _ in ()).throw(AssertionError('No cloud in local mode')))
    assert ai_provider.respond(ctx(),'assistant','Hi','local',selected_provider='gemini')['provider']=='ollama'


def test_cloud_first_falls_back_to_local_when_no_consent(monkeypatch):
    setmode(mode='cloud',cloud=False)
    fake_local(monkeypatch)
    monkeypatch.setattr(ai_provider,'_call_provider',lambda *a: (_ for _ in ()).throw(AssertionError('No cloud permitted')))
    assert ai_provider.respond(ctx(),'assistant','Hi','local')['provider']=='ollama'


def test_explicit_local_rules_bypasses_models(monkeypatch):
    setmode(mode='hybrid',cloud=True)
    monkeypatch.setattr(ai_provider,'_call_ollama',lambda *a: (_ for _ in ()).throw(AssertionError('LLM not permitted')))
    monkeypatch.setattr(ai_provider,'_call_provider',lambda *a: (_ for _ in ()).throw(AssertionError('Cloud not permitted')))
    r=ai_provider.respond(ctx(),'assistant','Hi','local',selected_provider='local')
    assert r['provider']=='local'


def test_explicit_ollama_does_not_escalate(monkeypatch):
    setmode(mode='hybrid',cloud=True)
    ai_provider.set_key('gemini','key_for_test_00000999')
    monkeypatch.setattr(ai_provider,'_call_ollama',lambda *a: (_ for _ in ()).throw(TimeoutError()))
    monkeypatch.setattr(ai_provider,'_call_provider',lambda *a: (_ for _ in ()).throw(AssertionError('No cloud when Ollama selected')))
    assert ai_provider.respond(ctx(),'assistant','Hi','deterministic',selected_provider='ollama')['fallback']

@pytest.mark.parametrize('payload',[
    {'intelligence_mode':'unlimited'}, {'local_model':'http://evil.site'},
    {'local_model':'bad model name'}, {'local_model':'../'*30},
    {'local_timeout_seconds':4},{'local_timeout_seconds':200},
])
def test_bad_model_settings_rejected(payload):
    r=client.put('/api/ai/settings',json={**payload,'provider_order':list(ai_provider.PROVIDERS)})
    assert r.status_code==422,r.text


def test_local_status_has_no_network_access_if_offline(monkeypatch):
    def fail(*a,**k): raise urllib.error.URLError('no local server')
    monkeypatch.setattr(ai_provider,'_ollama_request',fail)
    r=client.get('/api/ai/local/status')
    assert r.status_code==200 and r.json()['status']=='not_running'


def test_model_missing_does_not_download(monkeypatch):
    paths=[]
    def f(path,**kwargs):
        paths.append(path)
        return {'models':[{'name':'gemma3:1b'}]}
    monkeypatch.setattr(ai_provider,'_ollama_request',f)
    assert client.get('/api/ai/local/status').json()['status']=='model_missing'
    assert paths==['/api/tags']


def test_local_api_is_fixed_loopback(monkeypatch):
    import urllib.request
    calls=[]
    class Response:
        def __enter__(self):return self
        def __exit__(self,*a):pass
        def read(self,n):return b'{"models":[]}'
    class Opener:
        def open(self,request,timeout):calls.append((request.full_url,timeout));return Response()
    monkeypatch.setattr(urllib.request,'build_opener',lambda *args:Opener())
    ai_provider._ollama_request('/api/tags')
    assert calls[0][0]=='http://127.0.0.1:11434/api/tags'
    with pytest.raises(ValueError):ai_provider._ollama_request('http://evil.site')
