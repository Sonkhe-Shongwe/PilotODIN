"""Isolated P1 resource status and per-device preference regressions."""
import json
import pytest
from fastapi.testclient import TestClient
from backend import resource_policy, storage
from backend.main import app


@pytest.fixture
def isolated_home(monkeypatch, tmp_path):
    monkeypatch.setattr(storage, "HOME", tmp_path)
    return tmp_path


def test_default_mode_does_not_create_file(isolated_home):
    assert resource_policy.read_policy()["mode"] == "adaptive"
    assert not (isolated_home / "resource_preferences.json").exists()


@pytest.mark.parametrize("mode", ["adaptive", "low_memory", "performance"])
def test_mode_persists_atomically(isolated_home, mode):
    resource_policy.save_policy(mode)
    assert resource_policy.read_policy()["mode"] == mode
    assert json.loads((isolated_home / "resource_preferences.json").read_text()) == {
        "schema_version": 1, "mode": mode
    }
    assert list(isolated_home.glob(".resource-policy-*")) == []


def test_invalid_disk_preferences_are_read_only_fallback(isolated_home):
    path = isolated_home / "resource_preferences.json"
    for saved in ("{unfinished", '{"schema_version":99,"mode":"adaptive"}'):
        path.write_text(saved, encoding="utf-8")
        result = resource_policy.read_policy()
        assert result["source"] == "fallback"
        assert result["mode"] == "adaptive"
        assert result["warning"]
        assert path.read_text(encoding="utf-8") == saved


def test_atomic_replace_failure_preserves_saved_mode(isolated_home, monkeypatch):
    resource_policy.save_policy("low_memory")
    path = isolated_home / "resource_preferences.json"
    before = path.read_bytes()
    def cannot_replace(_first, _second):
        raise OSError("Simulated storage error")
    monkeypatch.setattr(resource_policy.os, "replace", cannot_replace)
    with pytest.raises(OSError):
        resource_policy.save_policy("performance")
    assert path.read_bytes() == before
    assert list(isolated_home.glob(".resource-policy-*")) == []


def test_measured_ram_is_deterministic_when_injected(monkeypatch):
    monkeypatch.setattr(resource_policy, "_physical_memory_bytes",
                        lambda: (8*1024**3, int(1.25*1024**3), "fixture"))
    result = resource_policy.memory_status()
    assert result["status"] == "observed"
    assert result["total_gib"] == 8
    assert result["available_gib"] == 1.25
    assert result["source"] == "fixture"


def test_memory_unavailable_is_truthfully_null(monkeypatch):
    def unavailable():
        raise OSError("Unsupported device")
    monkeypatch.setattr(resource_policy, "_physical_memory_bytes", unavailable)
    result = resource_policy.memory_status()
    assert result["status"] == "unavailable"
    assert result["total_gib"] is None
    assert result["available_gib"] is None


def test_api_mode_roundtrip_and_validation(isolated_home, monkeypatch):
    monkeypatch.setattr(resource_policy, "_physical_memory_bytes",
                        lambda: (8*1024**3, 1024**3, "fixture"))
    client = TestClient(app)
    status = client.get("/api/resource/status")
    assert status.status_code == 200, status.text
    assert status.json()["memory"]["available_gib"] == 1.0
    assert status.json()["policy"]["mode"] == "adaptive"
    assert status.json()["policy_effect"] == "display_only_p1_not_enforced"
    saved = client.put("/api/resource/policy", json={"mode": "low_memory"})
    assert saved.status_code == 200, saved.text
    assert saved.json()["policy"]["mode"] == "low_memory"
    assert client.get("/api/resource/status").json()["policy"]["mode"] == "low_memory"
    assert client.put("/api/resource/policy", json={"mode": "invalid_mode"}).status_code == 422
    assert client.put("/api/resource/policy",
                      json={"mode": "performance", "unknown": True}).status_code == 422
    assert client.get("/api/resource/status").json()["policy"]["mode"] == "low_memory"


def test_local_origin_scope_for_resource_controls(isolated_home):
    client=TestClient(app)
    response = client.put("/api/resource/policy",json={"mode":"performance"},
                          headers={"Origin":"https://example.org"})
    assert response.status_code == 403
    assert client.get("/api/resource/status",
                      headers={"Origin":"https://example.org"}).status_code == 403
