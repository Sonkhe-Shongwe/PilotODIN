"""Low-memory admission is tested with fake hardware: no model is loaded here."""
from __future__ import annotations

import pytest
import pandas as pd
from fastapi import BackgroundTasks, HTTPException

from backend import ai_provider, main, resource_policy, storage


@pytest.fixture
def isolated_policy(monkeypatch, tmp_path):
    monkeypatch.setattr(storage, "HOME", tmp_path)
    return tmp_path


def memory(monkeypatch, free_gib):
    if free_gib is None:
        def unavailable():
            raise OSError("Unavailable memory probe")
        monkeypatch.setattr(resource_policy, "_physical_memory_bytes", unavailable)
    else:
        monkeypatch.setattr(
            resource_policy, "_physical_memory_bytes",
            lambda: (8 * 1024**3, int(free_gib * 1024**3), "test_fixture"),
        )


@pytest.mark.parametrize("free,decision,code", [
    (0.25,"defer","low_memory_headroom"),
    (0.74,"defer","low_memory_headroom"),
    (0.75,"allow","screening_floor_met"),
    (1.09,"allow","screening_floor_met"),
    (None,"defer","memory_unavailable"),
])
def test_low_memory_training_admission(isolated_policy, monkeypatch, free, decision, code):
    resource_policy.save_policy("low_memory")
    memory(monkeypatch, free)
    result=resource_policy.admit_new_work("training")
    assert result["decision"]==decision
    assert result["code"]==code
    assert result["required_free_gib"]==0.75
    assert result["mode"]=="low_memory"
    assert resource_policy.memory_status()["status"]==(
        "unavailable" if free is None else "observed")


@pytest.mark.parametrize("free,decision", [
    (1.09,"defer"),(1.99,"defer"),(2.0,"allow"),(None,"defer")])
def test_low_memory_ai_admission(isolated_policy, monkeypatch, free, decision):
    resource_policy.save_policy("low_memory")
    memory(monkeypatch,free)
    report=resource_policy.admit_new_work("local_inference")
    assert report["decision"]==decision
    assert report["required_free_gib"]==2.0


@pytest.mark.parametrize("mode", ["adaptive","performance"])
def test_other_policies_keep_earlier_guards_without_new_headroom_refusal(
        isolated_policy, monkeypatch, mode):
    resource_policy.save_policy(mode)
    memory(monkeypatch, 0.1)
    report=resource_policy.admit_new_work("training")
    assert report["decision"]=="allow"
    assert report["code"]=="not_enforced_for_selected_mode"
    assert "hard resource" in report["note"]


def _synthetic_frame():
    return pd.DataFrame({
        "Metric": [float(i%11) for i in range(60)],
        "Outcome": ["Y" if i%2==0 else "N" for i in range(60)],
    })


def _new_training(monkeypatch):
    frame=_synthetic_frame()
    monkeypatch.setattr(main,"project_or_404",lambda _:{"id":"synthetic"})
    monkeypatch.setattr(main.quality,"current_data",lambda _: (frame,0))
    created=[]
    def create_synthetic(pid, conf):
        created.append((pid, conf))
        return "fake-experiment"
    monkeypatch.setattr(main.storage,"new_experiment",create_synthetic)
    monkeypatch.setattr(main.storage,"new_experiment_with_capacity",create_synthetic)
    body=main.ExperimentRequest(
        target="Outcome",task="classification",excluded_features=[],
        models=["logistic_regression"],split_strategy="random",
        acknowledge_random_split=True,expected_quality_version=0,
    )
    return body,created


@pytest.mark.parametrize("free", [0.4,None])
def test_blocked_training_creates_no_experiment_and_no_background_job(
        isolated_policy,monkeypatch,free):
    resource_policy.save_policy("low_memory")
    memory(monkeypatch,free)
    body,created=_new_training(monkeypatch)
    tasks=BackgroundTasks()
    with pytest.raises(HTTPException) as exc:
        main.new_experiment("synthetic",body,tasks)
    assert exc.value.status_code==503
    assert exc.value.detail["retryable"] is True
    assert exc.value.detail["operation"]=="training"
    assert exc.value.detail["code"] in ("memory_unavailable","low_memory_headroom")
    assert created==[]
    assert tasks.tasks==[]


def test_sufficient_low_memory_allows_existing_ml_guards_then_schedules(
        isolated_policy,monkeypatch):
    resource_policy.save_policy("low_memory")
    memory(monkeypatch,1.09)
    body,created=_new_training(monkeypatch)
    tasks=BackgroundTasks()
    result=main.new_experiment("synthetic",body,tasks)
    assert result["status"]=="queued"
    assert len(created)==1
    assert len(tasks.tasks)==1
    # Creating an experiment does not immediately start model training here.


def test_low_memory_ai_fallback_does_not_call_model(
        isolated_policy,monkeypatch):
    resource_policy.save_policy("low_memory")
    memory(monkeypatch,0.8)
    calls=[]
    monkeypatch.setattr(ai_provider,"_call_ollama",
                        lambda *a,**kw: calls.append("ollama"))
    monkeypatch.setattr(ai_provider.bundled_inference,"generate",
                        lambda *a,**kw: calls.append("bundled"))
    monkeypatch.setattr(ai_provider,"_read_config", lambda:{
        "intelligence_mode":"local",
        "workspace_preferences":{},
        "preferred_provider":"auto",
        "local_model_enabled":True,
        "local_model":"qwen3:1.7b",
        "local_timeout_seconds":60,
        "cloud_enabled":False,
        "share_aggregates":False,
    })
    result=ai_provider.respond({}, "assistant","What patterns?","Computed local evidence")
    assert result["source"]=="local_computed_rules"
    assert result["answer"]=="Computed local evidence"
    assert result["local_status"]=="resource_limited"
    assert "Low-memory" in result["reason"]
    assert calls==[]


def test_invalid_admission_operation_never_changes_preferences(
        isolated_policy):
    resource_policy.save_policy("low_memory")
    with pytest.raises(ValueError):
        resource_policy.admit_new_work("delete_source")
    assert resource_policy.read_policy()["mode"]=="low_memory"



def test_readonly_api_preflight_uses_same_policy_as_training(isolated_policy,monkeypatch):
    from fastapi.testclient import TestClient
    resource_policy.save_policy("low_memory")
    memory(monkeypatch,0.45)
    client=TestClient(main.app)
    before=resource_policy.read_policy()
    blocked=client.get("/api/resource/preflight?operation=training")
    assert blocked.status_code==200, blocked.text
    assert blocked.json()["decision"]=="defer"
    assert blocked.json()["code"]=="low_memory_headroom"
    assert blocked.json()["required_free_gib"]==0.75
    local=client.get("/api/resource/preflight?operation=local_inference")
    assert local.status_code==200 and local.json()["decision"]=="defer"
    assert local.json()["required_free_gib"]==2.0
    assert client.get("/api/resource/preflight?operation=arbitrary").status_code==422
    assert client.get("/api/resource/preflight?operation=local_inference",
                      headers={"Origin":"https://example.org"}).status_code==403
    assert resource_policy.read_policy()==before
