"""P5 first slice: atomic single-user Low-memory ML training admission.

All cases use a fresh SQLite file under Pytest tmp_path; no owner datasets or
model artifacts are accessed and no production ML training is run.
"""
from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
from hashlib import sha256
from threading import Barrier

import pandas as pd
import pytest
from fastapi import BackgroundTasks, HTTPException

from backend import main, quality, resource_policy, storage
from tests.settings_fixture import fixture_store


@pytest.fixture
def store(monkeypatch, tmp_path):
    home=tmp_path / "pilotodin-p5"
    (home/"datasets").mkdir(parents=True)
    (home/"models").mkdir()
    monkeypatch.setattr(storage,"HOME",home)
    monkeypatch.setattr(resource_policy, "_settings_store", lambda: fixture_store(home))
    monkeypatch.setattr(storage,"DB_PATH",home/"pilotodin.sqlite3")
    storage.init()
    quality._init_tables()
    raw = ("Metric,Outcome\n" + "".join(f"{i % 13},{'Y' if i % 2 else 'N'}\n" for i in range(80))).encode()
    source = home / "datasets" / "fixture.csv"
    source.write_bytes(raw)
    return storage.save_project("Synthetic", "fixture.csv", ".csv", source, {"rows": 80},
                                original_sha256=sha256(raw).hexdigest())


def config():
    return {"target":"Outcome","excluded":[],"models":["logistic_regression"],
            "task":"classification","quality_version":0,
            "split_strategy":"random","split_column":None}


def test_single_slot_rejects_second_and_other_project_without_new_row(store):
    a=storage.new_experiment_with_capacity(store,config())
    another = storage.save_project("Other project", "other.csv", ".csv",
                                   storage.HOME / "datasets" / "other.csv", {"rows":80})
    with pytest.raises(storage.TrainingSlotBusy):
        storage.new_experiment_with_capacity(another,config())
    with storage.connect() as con:
        rows=con.execute("SELECT id,status FROM experiments").fetchall()
    assert [(r["id"],r["status"]) for r in rows]==[(a,"queued")]
    assert storage.claim_queued_experiment(a)
    assert not storage.claim_queued_experiment(a)
    with pytest.raises(storage.TrainingSlotBusy):
        storage.new_experiment_with_capacity(store,config())
    assert storage.finish_running_experiment(a,"completed",results={"models":[]})
    assert not storage.finish_running_experiment(a,"failed",error="late writer")
    assert storage.get_experiment(a)["status"]=="completed"
    second=storage.new_experiment_with_capacity(store,config())
    assert second!=a
    assert storage.get_experiment(second)["status"]=="queued"


def test_atomic_concurrent_reservations_have_exactly_one_winner(store):
    count=8
    gate=Barrier(count)
    def contend(_):
        gate.wait(timeout=10)
        try:
            return ("reserved",storage.new_experiment_with_capacity(store,config()))
        except storage.TrainingSlotBusy:
            return ("busy",None)
    with ThreadPoolExecutor(max_workers=count) as pool:
        outcomes=list(pool.map(contend,range(count)))
    assert sum(status=="reserved" for status,_ in outcomes)==1
    assert sum(status=="busy" for status,_ in outcomes)==count-1
    with storage.connect() as con:
        assert con.execute("SELECT count(*) FROM experiments").fetchone()[0]==1


def test_process_restart_marks_only_nonterminal_work_failed(store,monkeypatch):
    running=storage.new_experiment_with_capacity(store,config())
    assert storage.claim_queued_experiment(running)
    # Model another program version's queued work from before this gate.
    queued=storage.new_experiment(store,config())
    done=storage.new_experiment(store,config())
    assert storage.claim_queued_experiment(done)
    assert storage.finish_running_experiment(done,"completed",results={"keep":"yes"})
    monkeypatch.setattr(main.ai_provider,"config_status",
                        lambda:{"cloud_enabled":False,"share_aggregates":False})
    async def restart():
        async with main._lifespan(main.app):
            return True
    assert asyncio.run(restart())
    for eid in (running,queued):
        exp=storage.get_experiment(eid)
        assert exp["status"]=="failed"
        assert "interrupted by application restart" in exp["error"]
        assert exp["results"] is None
        assert not storage.claim_queued_experiment(eid)
    assert storage.get_experiment(done)["status"]=="completed"
    assert storage.get_experiment(done)["results"]=={"keep":"yes"}
    assert storage.recover_interrupted_experiments()==0
    assert storage.new_experiment_with_capacity(store,config())


def test_terminal_and_interrupted_workers_never_retrain(store,monkeypatch):
    eid=storage.new_experiment_with_capacity(store,config())
    storage.recover_interrupted_experiments()
    def forbidden(*args,**kwargs):
        raise AssertionError("No training was supposed to execute")
    monkeypatch.setattr(main.engine,"run_training",forbidden)
    main.train_background(eid,store,config())
    assert storage.get_experiment(eid)["status"]=="failed"


def test_raised_worker_error_releases_slot_without_fake_results(store,monkeypatch):
    eid=storage.new_experiment_with_capacity(store,config())
    monkeypatch.setattr(main,"df_for",
                        lambda _p,_v: pd.DataFrame({"Outcome":["Y","N"]}))
    def failed_train(*args,**kwargs):
        raise RuntimeError("Synthetic training interruption")
    monkeypatch.setattr(main.engine,"run_training",failed_train)
    main.train_background(eid,store,config())
    exp=storage.get_experiment(eid)
    assert exp["status"]=="failed"
    assert "Synthetic training interruption" in exp["error"]
    assert exp["results"] is None
    assert storage.new_experiment_with_capacity(store,config())


def test_low_memory_api_busy_refuses_before_background_enqueue(store,monkeypatch):
    resource_policy.save_policy("low_memory")
    monkeypatch.setattr(resource_policy,"_physical_memory_bytes",
                        lambda:(8*1024**3, int(1.5*1024**3),"synthetic"))
    fake=pd.DataFrame({"Metric":[float(i%13) for i in range(80)],
                       "Outcome":["Y" if i%2 else "N" for i in range(80)]})
    monkeypatch.setattr(main.quality,"current_data",lambda _: (fake,0))
    body=main.ExperimentRequest(target="Outcome",task="classification",
        excluded_features=[],models=["logistic_regression"],
        acknowledge_random_split=True,expected_quality_version=0)
    queued=BackgroundTasks()
    started=main.new_experiment(store,body,queued)
    assert started["status"]=="queued"
    assert len(queued.tasks)==1
    original=storage.get_experiment(started["id"])
    refused=BackgroundTasks()
    with pytest.raises(HTTPException) as err:
        main.new_experiment(store,body,refused)
    assert err.value.status_code==503
    assert err.value.detail["code"]=="ml_training_slot_busy"
    assert err.value.detail["retryable"] is True
    assert refused.tasks==[]
    assert storage.get_experiment(started["id"])==original
    with storage.connect() as con:
        assert con.execute("SELECT count(*) FROM experiments").fetchone()[0]==1


@pytest.mark.parametrize("first_mode", ["low_memory", "adaptive", "performance"])
@pytest.mark.parametrize("second_mode", ["low_memory", "adaptive", "performance"])
def test_all_policy_modes_share_one_atomic_training_slot(
        store, monkeypatch, first_mode, second_mode):
    """A policy change cannot bypass the workstation-wide memory-safety slot."""
    monkeypatch.setattr(resource_policy, "_physical_memory_bytes",
                        lambda: (8 * 1024**3, int(2.5 * 1024**3), "synthetic"))
    fake = pd.DataFrame({"Metric": [float(i % 13) for i in range(80)],
                         "Outcome": ["Y" if i % 2 else "N" for i in range(80)]})
    monkeypatch.setattr(main.quality, "current_data", lambda _: (fake, 0))
    body = main.ExperimentRequest(
        target="Outcome", task="classification", excluded_features=[],
        models=["logistic_regression"], acknowledge_random_split=True,
        expected_quality_version=0,
    )
    resource_policy.save_policy(first_mode)
    first_tasks = BackgroundTasks()
    first = main.new_experiment(store, body, first_tasks)
    assert first["status"] == "queued" and len(first_tasks.tasks) == 1

    resource_policy.save_policy(second_mode)
    refused_tasks = BackgroundTasks()
    with pytest.raises(HTTPException) as blocked:
        main.new_experiment(store, body, refused_tasks)
    assert blocked.value.status_code == 503
    assert blocked.value.detail["code"] == "ml_training_slot_busy"
    assert blocked.value.detail["retryable"] is True
    assert refused_tasks.tasks == []
    with storage.connect() as con:
        assert con.execute("SELECT COUNT(*) FROM experiments").fetchone()[0] == 1

    assert storage.claim_queued_experiment(first["id"])
    with pytest.raises(HTTPException) as running:
        main.new_experiment(store, body, BackgroundTasks())
    assert running.value.detail["code"] == "ml_training_slot_busy"

    assert storage.finish_running_experiment(first["id"], "completed",
                                             results={"models": []})
    after = main.new_experiment(store, body, BackgroundTasks())
    assert after["id"] != first["id"]
    assert storage.get_experiment(after["id"])["status"] == "queued"


def test_terminal_status_contract_is_strict(store):
    eid=storage.new_experiment_with_capacity(store,config())
    assert storage.claim_queued_experiment(eid)
    with pytest.raises(ValueError,match="terminal"):
        storage.finish_running_experiment(eid,"running")
    assert storage.get_experiment(eid)["status"]=="running"
    assert storage.finish_running_experiment(eid,"failed",error="stopped")
    assert not storage.finish_running_experiment(eid,"completed",results={"wrong":True})
    assert storage.get_experiment(eid)["results"] is None
