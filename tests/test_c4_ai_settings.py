"""Settings integration only: disposable roots, fake DPAPI, zero provider calls."""
import base64
import json
from unittest.mock import patch

import pytest
from backend import ai_provider as ai, settings_storage as store, storage
from backend.main import app
from tests.fixture_http import fixture_client
from tests.settings_fixture import isolate_ai_store, fixture_dpapi


@pytest.fixture
def home(tmp_path, monkeypatch):
    isolate_ai_store(monkeypatch, ai, tmp_path)
    monkeypatch.setattr(ai, "_persistent_secrets", lambda: False)
    for env in ai.ENV_KEYS.values():
        monkeypatch.delenv(env, raising=False)
    def no_network(*args, **kwargs):
        pytest.fail("Unexpected provider or model dispatch")
    monkeypatch.setattr(ai, "_call_provider", no_network)
    monkeypatch.setattr(ai, "_call_ollama", no_network)
    return tmp_path


def save(**changes):
    return ai.update_settings(**{**store.ai_defaults(), **changes})


def test_missing_and_legacy_valid_config(home):
    assert ai._read_config() == store.ai_defaults()
    path=home/"ai_settings.json"
    assert not path.exists()
    path.write_text('{"cloud_enabled":true,"share_aggregates":true}', encoding="utf-8")
    assert ai._read_config()["cloud_enabled"] is True
    assert ai._read_config()["local_model"] == "qwen3:1.7b"
    old_stage=home/"ai_settings.tmp"
    old_stage.write_bytes(b"historical-stage")
    save(preferred_provider="local")
    assert json.loads(path.read_text())["preferred_provider"] == "local"
    assert old_stage.read_bytes() == b"historical-stage"
    assert not list(home.glob(".ai-settings-*"))


@pytest.mark.parametrize("raw", [
    b'{"cloud_enabled":"true","share_aggregates":true}',
    b'{"cloud_enabled":true,"share_aggregates":true,"future":1}',
    b'{"cloud_enabled":true,"cloud_enabled":false}',
    b'x'*16385,
])
def test_invalid_config_preserved_and_cloud_off(home, raw):
    path=home/"ai_settings.json"
    path.write_bytes(raw)
    assert ai._read_config()["intelligence_mode"] == "local"
    assert ai.config_status()["settings_warning"]
    assert ai._get_key("gemini") is None
    with pytest.raises(OSError):
        save(cloud_enabled=True,share_aggregates=True)
    assert path.read_bytes()==raw
    assert not list(home.glob(".ai-settings-*"))


def test_memory_keys_no_disk_and_no_ambient_fallback(home, monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY","ambient-fixture-key")
    assert ai._get_key("gemini") is None
    key="generated-fixture-key"
    ai.set_key("gemini",key)
    assert ai._get_key("gemini")==key
    assert key not in repr(ai.config_status())
    ai.set_key("gemini",remove=True)
    assert ai._get_key("gemini") is None
    assert not list(home.iterdir())


def test_fake_dpapi_legacy_roundtrip_and_remove(home,monkeypatch):
    monkeypatch.setattr(ai,"_persistent_secrets",lambda:True)
    path=home/"ai_secrets.dpapi"
    key="synthetic-legacy-key"
    path.write_bytes(base64.b64encode(fixture_dpapi(json.dumps({"groq":key}).encode())))
    assert ai._get_key("groq")==key
    ai.set_key("gemini","new-synthetic-key")
    assert ai._get_key("groq")==key
    assert key.encode() not in path.read_bytes()
    assert key not in repr(ai.config_status())
    ai.set_key("groq",remove=True)
    assert ai._get_key("groq") is None
    assert not list(home.glob(".secrets-*"))


def test_corrupt_ciphertext_preserved(home,monkeypatch):
    monkeypatch.setattr(ai,"_persistent_secrets",lambda:True)
    path=home/"ai_secrets.dpapi"
    path.write_bytes(b"malformed")
    save(cloud_enabled=True,share_aggregates=True)
    status=ai.config_status()
    assert status["credential_warning"] and status["cloud_enabled"] is False
    assert ai._get_key("gemini") is None
    with pytest.raises(OSError):
        ai.set_key("gemini","new-synthetic-key")
    assert path.read_bytes()==b"malformed"
    assert not list(home.glob(".secrets-*"))


def test_encryption_failure_keeps_old_ciphertext(home,monkeypatch):
    monkeypatch.setattr(ai,"_persistent_secrets",lambda:True)
    path=home/"ai_secrets.dpapi"
    ai.set_key("gemini","prior-synthetic-key")
    before=path.read_bytes()
    def broken(data,decrypt=False):
        if decrypt:
            return fixture_dpapi(data,True)
        raise OSError("private-marker")
    monkeypatch.setattr(ai,"_dpapi",broken)
    with pytest.raises(OSError) as error:
        ai.set_key("gemini","new-synthetic-key")
    assert "private-marker" not in str(error.value)
    assert path.read_bytes()==before
    assert ai._get_key("gemini") is None
    assert ai.config_status()["credential_warning"]


def test_uncertain_config_save_inhibits_cloud(home,monkeypatch):
    save(cloud_enabled=True,share_aggregates=True)
    ai.set_key("gemini","prior-synthetic-key")
    actual=store.os.replace
    def ambiguous(src,dst):
        actual(src,dst)
        raise OSError("private-marker")
    monkeypatch.setattr(store.os,"replace",ambiguous)
    client=fixture_client(app)
    response=client.put("/api/ai/settings",json=store.ai_defaults())
    assert response.status_code==503
    assert response.json()["detail"]["code"]=="settings_commit_uncertain"
    assert "private-marker" not in response.text
    assert ai._read_config()["cloud_enabled"] is False
    assert ai._get_key("gemini") is None
    assert json.loads((home/"ai_settings.json").read_text())["cloud_enabled"] is False


@pytest.mark.parametrize("path,payload",[
    ("/api/ai/key",{"provider":"gemini","key":"secret marker "*50}),
    ("/api/ai/key",{"provider":"gemini","key":"secret-marker-valid","remove":"false"}),
    ("/api/ai/key",{"provider":"gemini","key":"secret-marker-valid","unknown":"secret-marker"}),
    ("/api/ai/key",{"provider":"gemini","key":"secret-marker-valid","remove":True}),
    ("/api/ai/settings",{"cloud_enabled":"true","share_aggregates":True,"unknown":"secret-marker"}),
    ("/api/ai/settings",{"timeout_seconds":True}),
    ("/api/ai/settings",{"local_timeout_seconds":30.0}),
])
def test_api_strict_and_redacted(home,path,payload):
    response=fixture_client(app).put(path,json=payload)
    assert response.status_code==422
    assert "secret-marker" not in response.text
    assert "secret marker" not in response.text
    assert not list(home.iterdir())


def test_unleased_real_adapter_refuses_ai_mutation(tmp_path,monkeypatch):
    monkeypatch.setattr(storage,"HOME",tmp_path)
    monkeypatch.setattr(ai,"_config_inhibited",False)
    monkeypatch.setattr(ai,"_keys_inhibited",False)
    assert ai._read_config()["settings_warning"]
    with pytest.raises(OSError):
        save()
    with pytest.raises(OSError):
        ai.set_key("gemini","generated-fixture-key")
    assert not list(tmp_path.iterdir())
