"""P5 cooperative cancellation/soft deadline tests with isolated SQLite only."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from backend import engine, main, storage


@pytest.fixture
def local_home(tmp_path, monkeypatch):
    home = tmp_path / "pilotodin-cancel-only"
    (home / "datasets").mkdir(parents=True)
    (home / "models").mkdir()
    monkeypatch.setattr(storage, "HOME", home)
    monkeypatch.setattr(storage, "DB_PATH", home / "pilotodin.sqlite3")
    storage.init()
    pid = storage.save_project("Synthetic", "fixture.csv", ".csv",
                               home / "datasets" / "fixture.csv", {"rows": 64})
    return pid, home


def config(limit=None):
    return {
        "target": "Outcome", "task": "classification", "models": ["logistic_regression"],
        "excluded": [], "quality_version": 0, "split_strategy": "random",
        "split_column": None, "max_duration_seconds": limit,
    }


def stages(eid):
    return [event["stage"] for event in storage.get_experiment(eid)["progress"]["history"]]


def test_queued_cancellation_is_immediate_idempotent_and_frees_slot(local_home):
    pid, _ = local_home
    eid = storage.new_experiment_with_capacity(pid, config())
    client = TestClient(main.app)
    response = client.post(f"/api/experiments/{eid}/cancel", json={})
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "cancelled"
    item = storage.get_experiment(eid)
    assert item["status"] == "cancelled"
    assert item["results"] is None
    assert stages(eid) == ["queued", "cancelled"]
    assert not storage.claim_queued_experiment(eid)
    assert client.post(f"/api/experiments/{eid}/cancel", json={}).json()["status"] == "already_finished"
    assert stages(eid) == ["queued", "cancelled"]
    assert storage.new_experiment_with_capacity(pid, config()) != eid
    assert client.post("/api/experiments/not-present/cancel", json={}).status_code == 404
    assert client.post(f"/api/experiments/{eid}/cancel", json={},
                       headers={"Origin": "https://external.example"}).status_code == 403


def test_running_cancellation_is_only_pending_until_checkpoint(local_home):
    pid, _ = local_home
    eid = storage.new_experiment_with_capacity(pid, config())
    assert storage.claim_queued_experiment(eid)
    assert storage.request_training_cancel(eid) == "cancellation_requested"
    active = storage.get_experiment(eid)
    assert active["status"] == "running"  # Honest: no forced sklearn interruption.
    assert active["control"]["cancel_requested"] is True
    assert stages(eid) == ["queued", "loading_data"]
    with pytest.raises(storage.TrainingInterrupted) as error:
        storage.check_training_interruption(eid)
    assert error.value.status == "cancelled"
    with pytest.raises(storage.TrainingInterrupted):
        storage.finish_running_experiment(eid, "completed", results={"wrong": "success"})
    assert storage.finish_interrupted_experiment(eid, "cancelled")
    assert storage.get_experiment(eid)["status"] == "cancelled"
    assert storage.get_experiment(eid)["results"] is None
    assert not storage.finish_interrupted_experiment(eid, "cancelled")
    assert stages(eid) == ["queued", "loading_data", "cancelled"]


def test_deadline_begins_on_claim_and_is_checked_cooperatively(local_home):
    pid, _ = local_home
    eid = storage.new_experiment(pid, config(60))
    assert storage.get_experiment(eid)["control"]["deadline_at"] is None
    assert storage.claim_queued_experiment(eid)
    deadline = storage.get_experiment(eid)["control"]["deadline_at"]
    assert datetime.fromisoformat(deadline) > datetime.now(timezone.utc)
    with storage.connect() as con:
        con.execute("UPDATE experiment_run_controls SET deadline_at=? WHERE experiment_id=?",
                    ((datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat(), eid))
    with pytest.raises(storage.TrainingInterrupted) as ex:
        storage.check_training_interruption(eid)
    assert ex.value.status == "timed_out"
    with pytest.raises(storage.TrainingInterrupted):
        storage.finish_running_experiment(eid, "completed", results={"wrong": True})
    assert storage.finish_interrupted_experiment(eid, "timed_out")
    item = storage.get_experiment(eid)
    assert item["status"] == "timed_out"
    assert "time limit" in item["error"].lower()
    assert stages(eid)[-1] == "timed_out"


def test_no_implicit_timeout_for_older_experiments(local_home):
    pid, _ = local_home
    eid = storage.new_experiment(pid, config())
    assert storage.claim_queued_experiment(eid)
    assert storage.get_experiment(eid)["control"]["deadline_at"] is None
    storage.check_training_interruption(eid)
    assert storage.finish_running_experiment(eid, "completed", results={"keep": True})
    assert storage.request_training_cancel(eid) == "already_finished"
    assert storage.get_experiment(eid)["results"] == {"keep": True}


def test_worker_exits_after_request_inside_blocking_training(local_home, monkeypatch):
    pid, home = local_home
    eid = storage.new_experiment(pid, config())
    monkeypatch.setattr(main, "df_for", lambda *_args: pd.DataFrame({"Outcome": ["Y", "N"]}))
    observed = []

    def fake_training(_frame, *, stop_check, **_kwargs):
        observed.append("fit started")
        assert storage.request_training_cancel(eid) == "cancellation_requested"
        assert storage.get_experiment(eid)["status"] == "running"
        # Simulates an expensive library call returning; checkpoint then observes request.
        stop_check()
        observed.append("incorrect continuation")

    monkeypatch.setattr(main.engine, "run_training", fake_training)
    main.train_background(eid, pid, config())
    assert observed == ["fit started"]
    assert storage.get_experiment(eid)["status"] == "cancelled"
    assert stages(eid) == ["queued", "loading_data", "training_models", "cancelled"]
    assert not (home / "models" / eid).exists()


def test_partial_artifacts_deleted_after_cancellation_during_save(local_home, monkeypatch):
    pid, home = local_home
    eid = storage.new_experiment(pid, config())
    frame = pd.DataFrame({"Outcome": ["Y", "N"], "Metric": [0, 1]})
    monkeypatch.setattr(main, "df_for", lambda *_args: frame)
    monkeypatch.setattr(main.engine, "run_training",
                        lambda *_args, **_kwargs: (
                            {"task": "classification", "models": []},
                            {"model1": object(), "model2": object()},
                            frame, frame["Outcome"],
                        ))
    dumps = []
    def fake_dump(_object, target):
        Path(target).write_bytes(b"partial file")
        dumps.append(str(target))
        if len(dumps) == 1:
            assert storage.request_training_cancel(eid) == "cancellation_requested"

    monkeypatch.setattr(main.joblib, "dump", fake_dump)
    main.train_background(eid, pid, config())
    assert len(dumps) == 1
    assert storage.get_experiment(eid)["status"] == "cancelled"
    assert storage.get_experiment(eid)["results"] is None
    assert not (home / "models" / eid).exists()
    assert stages(eid)[-1] == "cancelled"


def test_completed_artifacts_are_preserved_and_cannot_be_cancelled(local_home, monkeypatch):
    pid, home = local_home
    eid = storage.new_experiment(pid, config())
    frame = pd.DataFrame({"Outcome": ["Y", "N"], "Metric": [0, 1]})
    monkeypatch.setattr(main, "df_for", lambda *_args: frame)
    monkeypatch.setattr(main.engine, "run_training",
                        lambda *_args, **_kwargs: (
                            {"task": "classification", "models": []},
                            {"model": object()}, frame, frame["Outcome"]))
    monkeypatch.setattr(main.joblib, "dump",
                        lambda _object,target: Path(target).write_bytes(b"complete artifact"))
    main.train_background(eid, pid, config())
    assert storage.get_experiment(eid)["status"] == "completed"
    artifacts = sorted(p.name for p in (home / "models" / eid).glob("*.joblib"))
    assert artifacts == ["model.joblib", "test_set.joblib"]
    assert storage.request_training_cancel(eid) == "already_finished"
    assert sorted(p.name for p in (home / "models" / eid).glob("*.joblib")) == artifacts


def test_failed_artifact_write_does_not_leave_partial_files(local_home, monkeypatch):
    pid, home = local_home
    eid = storage.new_experiment(pid, config())
    frame = pd.DataFrame({"Outcome": ["Y", "N"]})
    monkeypatch.setattr(main, "df_for", lambda *_args: frame)
    monkeypatch.setattr(main.engine, "run_training",
                        lambda *_args, **_kwargs: (
                            {"models": []}, {"bad": object()}, frame, frame["Outcome"]))
    def fail_dump(_object,target):
        Path(target).write_bytes(b"incomplete")
        raise OSError("synthetic disk full")
    monkeypatch.setattr(main.joblib, "dump", fail_dump)
    main.train_background(eid, pid, config())
    exp = storage.get_experiment(eid)
    assert exp["status"] == "failed"
    assert "synthetic disk full" in exp["error"]
    assert exp["results"] is None
    assert not (home / "models" / eid).exists()


def test_engine_checkpoint_interrupt_is_not_swallowed_by_per_model_exception(local_home, monkeypatch):
    frame = pd.DataFrame({
        "Metric": [float(i % 11) for i in range(70)],
        "Outcome": ["Y" if i % 2 else "N" for i in range(70)],
    })
    import numpy as np
    calls = []
    def fast_cv(*_args, **_kwargs):
        calls.append("cv")
        return np.asarray([0.5, 0.55, 0.6])
    monkeypatch.setattr(engine, "cross_val_score", fast_cv)
    def stop():
        # Baseline score is 1st call, candidate CV is 2nd.
        if len(calls) >= 2:
            raise storage.TrainingInterrupted("cancelled")
    with pytest.raises(storage.TrainingInterrupted):
        engine.run_training(frame,target="Outcome",excluded=[],models=["logistic_regression"],
                            task="classification",stop_check=stop)
    assert len(calls) >= 2


def test_timeout_validation_does_not_mutate_any_existing_run(local_home):
    pid, _ = local_home
    with pytest.raises(Exception):
        main.ExperimentRequest(target="Outcome",task="classification",
            models=["logistic_regression"],max_duration_seconds=4)
    existing = storage.new_experiment(pid, config())
    assert storage.get_experiment(existing)["status"] == "queued"
