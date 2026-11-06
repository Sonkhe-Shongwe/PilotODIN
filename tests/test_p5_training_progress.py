"""P5 durable factual progress: synthetic SQLite migration, transitions and API polling.

No real dataset or offline model is opened; all tests run under tmp_path.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from backend import main, storage


@pytest.fixture
def home(tmp_path, monkeypatch):
    workspace = tmp_path / "isolated-progress"
    (workspace / "models").mkdir(parents=True)
    (workspace / "datasets").mkdir()
    monkeypatch.setattr(storage, "HOME", workspace)
    monkeypatch.setattr(storage, "DB_PATH", workspace / "pilotodin.sqlite3")
    storage.init()
    project_id = storage.save_project(
        "Synthetic", "synthetic.csv", ".csv",
        workspace / "datasets" / "synthetic.csv", {"rows": 50},
    )
    return project_id, workspace


def config():
    return {
        "target": "Outcome", "excluded": [], "models": ["logistic_regression"],
        "task": "classification", "quality_version": 0,
        "split_strategy": "random", "split_column": None,
    }


def event_stages(eid):
    return [e["stage"] for e in storage.get_experiment(eid)["progress"]["history"]]


@pytest.mark.parametrize("allocator", ["new_experiment", "new_experiment_with_capacity"])
def test_queued_event_persisted_for_both_admission_paths(home, allocator):
    pid, _ = home
    eid = getattr(storage, allocator)(pid, config())
    progress = storage.get_experiment(eid)["progress"]
    assert progress["stage"] == "queued"
    assert progress["label"] == "Waiting to start"
    assert progress["history_available"] is True
    assert event_stages(eid) == ["queued"]
    assert progress["updated_at"] is not None
    assert storage.get_experiment(eid)["status"] == "queued"


def test_running_stage_sequence_is_monotonic_and_durable(home):
    pid, _ = home
    eid = storage.new_experiment_with_capacity(pid, config())
    assert storage.claim_queued_experiment(eid)
    assert not storage.claim_queued_experiment(eid)
    assert event_stages(eid) == ["queued", "loading_data"]
    assert storage.advance_running_experiment(
        eid, "training_models", "Training began with confirmed development data."
    )
    assert not storage.advance_running_experiment(
        eid, "training_models", "Cannot report same stage twice."
    )
    assert storage.advance_running_experiment(
        eid, "saving_artifacts", "Fit returned; saving model artifacts."
    )
    assert not storage.advance_running_experiment(
        eid, "training_models", "Cannot move backwards."
    )
    with pytest.raises(ValueError):
        storage.advance_running_experiment(eid, "fake_progress", "Nope")
    assert storage.finish_running_experiment(eid, "completed", results={"models": []})
    assert event_stages(eid) == [
        "queued", "loading_data", "training_models", "saving_artifacts", "completed",
    ]
    assert storage.get_experiment(eid)["results"] == {"models": []}
    assert not storage.advance_running_experiment(eid, "training_models", "Late writer.")
    assert not storage.finish_running_experiment(eid, "failed", error="Stale worker")
    assert event_stages(eid)[-1] == "completed"
    assert storage.get_experiment(eid)["progress"]["updated_at"]


def test_legacy_experiments_do_not_receive_invented_milestones(home):
    pid, _ = home
    eid = storage.new_experiment(pid, config())
    with storage.connect() as con:
        con.execute("DELETE FROM experiment_progress_events WHERE experiment_id=?", (eid,))
        con.execute("UPDATE experiments SET status='running' WHERE id=?", (eid,))
    old = storage.get_experiment(eid)
    assert old["status"] == "running"
    assert old["progress"]["stage"] == "running_legacy"
    assert old["progress"]["history"] == []
    assert old["progress"]["history_available"] is False
    assert "Historical" in old["progress"]["detail"]


def test_original_completed_history_survives_progress_migration(home):
    pid, _ = home
    eid = storage.new_experiment(pid, config())
    assert storage.claim_queued_experiment(eid)
    assert storage.finish_running_experiment(
        eid, "completed", results={"historical_metric": 0.8},
    )
    events = storage.get_experiment(eid)["progress"]["history"]
    storage.init()  # Idempotent migration on existing DB.
    reopened = storage.get_experiment(eid)
    assert reopened["results"] == {"historical_metric": 0.8}
    assert reopened["progress"]["history"] == events
    assert reopened["progress"]["stage"] == "completed"


def test_recovery_adds_one_terminal_event_and_preserves_completed_model(home):
    pid, _ = home
    orphan = storage.new_experiment(pid, config())
    assert storage.claim_queued_experiment(orphan)
    complete = storage.new_experiment(pid, config())
    assert storage.claim_queued_experiment(complete)
    assert storage.finish_running_experiment(
        complete, "completed", results={"accepted": True},
    )
    complete_history = event_stages(complete)
    assert storage.recover_interrupted_experiments() == 1
    assert storage.recover_interrupted_experiments() == 0
    assert event_stages(orphan) == ["queued", "loading_data", "failed"]
    assert "restart" in storage.get_experiment(orphan)["progress"]["detail"].lower()
    assert storage.get_experiment(orphan)["status"] == "failed"
    assert storage.get_experiment(complete)["status"] == "completed"
    assert storage.get_experiment(complete)["results"] == {"accepted": True}
    assert event_stages(complete) == complete_history


def test_read_only_experiment_endpoint_exposes_persisted_progress(home, monkeypatch):
    pid, _ = home
    eid = storage.new_experiment(pid, config())
    monkeypatch.setattr(main.quality, "current_version", lambda _: 0)
    client = TestClient(main.app)
    reply = client.get(f"/api/experiments/{eid}")
    assert reply.status_code == 200, reply.text
    data = reply.json()
    assert data["project_id"] == pid
    assert data["progress"]["stage"] == "queued"
    assert data["progress"]["history"][0]["stage"] == "queued"
    assert data["progress"]["history_available"] is True
    assert data["results"] is None
    assert client.get("/api/experiments/nonexistent").status_code == 404


def test_worker_milestones_are_observed_not_estimated(home, monkeypatch):
    pid, workspace = home
    eid = storage.new_experiment(pid, config())
    observed = []
    frame = pd.DataFrame({"Outcome": ["Y", "N"], "Metric": [1, 2]})
    monkeypatch.setattr(main, "df_for", lambda _p, _v: frame)

    def simulated_training(_frame, **_kwargs):
        observed.append(("engine", storage.get_experiment(eid)["progress"]["stage"]))
        return {"models": [], "task": "classification"}, {"fake": object()}, frame, frame["Outcome"]

    def simulated_save(*_args, **_kwargs):
        observed.append(("save", storage.get_experiment(eid)["progress"]["stage"]))

    monkeypatch.setattr(main.engine, "run_training", simulated_training)
    monkeypatch.setattr(main.joblib, "dump", simulated_save)
    main.train_background(eid, pid, config())
    assert observed == [("engine", "training_models"), ("save", "saving_artifacts"),
                        ("save", "saving_artifacts")]
    assert event_stages(eid) == [
        "queued", "loading_data", "training_models", "saving_artifacts", "completed",
    ]
    assert storage.get_experiment(eid)["status"] == "completed"
    assert not list((workspace / "models" / eid).glob("*.joblib"))  # Only synthetic stub.
    assert storage.get_experiment(eid)["results"]["task"] == "classification"


def test_worker_failure_preserves_real_last_stage_and_no_results(home, monkeypatch):
    pid, _ = home
    eid = storage.new_experiment(pid, config())
    monkeypatch.setattr(main, "df_for", lambda _p, _v: pd.DataFrame({"Metric": [1, 2]}))

    def failed_training(_frame, **_kwargs):
        assert storage.get_experiment(eid)["progress"]["stage"] == "training_models"
        raise RuntimeError("Synthetic model failure")

    monkeypatch.setattr(main.engine, "run_training", failed_training)
    main.train_background(eid, pid, config())
    record = storage.get_experiment(eid)
    assert record["status"] == "failed"
    assert record["results"] is None
    assert "Synthetic model failure" in record["error"]
    assert event_stages(eid) == [
        "queued", "loading_data", "training_models", "failed",
    ]


def test_stale_worker_cannot_emit_new_milestones_after_restart(home, monkeypatch):
    pid, _ = home
    eid = storage.new_experiment(pid, config())
    storage.recover_interrupted_experiments()
    called = []
    monkeypatch.setattr(main.engine, "run_training",
                        lambda *_args, **_kwargs: called.append("trained"))
    main.train_background(eid, pid, config())
    assert called == []
    assert event_stages(eid) == ["queued", "failed"]
    assert storage.get_experiment(eid)["status"] == "failed"
