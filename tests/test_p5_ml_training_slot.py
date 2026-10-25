"""P5 first slice: atomic single-user Low-memory ML training admission.

All cases use a fresh SQLite file under Pytest tmp_path; no owner datasets or
model artifacts are accessed and no production ML training is run.
"""
from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pandas as pd
import pytest
from fastapi import BackgroundTasks, HTTPException

from backend import main, resource_policy, storage


@pytest.fixture
def store(monkeypatch, tmp_path):
    home=tmp_path / "pilotodin-p5"
    (home/"datasets").mkdir(parents=True)
    (home/"models").mkdir()
    monkeypatch.setattr(storage,"HOME",home)
    monkeypatch.setattr(storage,"DB_PATH",home/"pilotodin.sqlite3")
    storage.init()
    pid=storage.save_project("Synthetic", "fixture.csv", ".csv",
                             home/"datasets"/"fixture.csv",{"rows":80})
    return pid


def config():
    return {"target":"Outcome","excluded":[],"models":["logistic_regression"],
            "task":"classification","quality_version":0,
            "split_strategy":"random","split_column":None}


def test_single_slot_rejects_second_and_other_project_without_new_row(store):
    a=storage.new_experiment_with_capacity(store,config())
    with pytest.raises(storage.TrainingSlotBusy):
        storage.new_experiment_with_capacity("another-project",config())
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


def test_adaptive_keeps_existing_multistart_semantics(store,monkeypatch):
    resource_policy.save_policy("adaptive")
    monkeypatch.setattr(resource_policy,"_physical_memory_bytes",
                        lambda:(8*1024**3,int(0.1*1024**3),"synthetic"))
    fake=pd.DataFrame({"Metric":[float(i%13) for i in range(80)],
                       "Outcome":["Y" if i%2 else "N" for i in range(80)]})
    monkeypatch.setattr(main.quality,"current_data",lambda _: (fake,0))
    body=main.ExperimentRequest(target="Outcome",task="classification",
        excluded_features=[],models=["logistic_regression"],
        acknowledge_random_split=True,expected_quality_version=0)
    first=main.new_experiment(store,body,BackgroundTasks())
    second=main.new_experiment(store,body,BackgroundTasks())
    assert first["id"]!=second["id"]
    assert storage.get_experiment(first["id"])["status"]=="queued"
    assert storage.get_experiment(second["id"])["status"]=="queued"


def test_terminal_status_contract_is_strict(store):
    eid=storage.new_experiment_with_capacity(store,config())
    assert storage.claim_queued_experiment(eid)
    with pytest.raises(ValueError,match="terminal"):
        storage.finish_running_experiment(eid,"running")
    assert storage.get_experiment(eid)["status"]=="running"
    assert storage.finish_running_experiment(eid,"failed",error="stopped")
    assert not storage.finish_running_experiment(eid,"completed",results={"wrong":True})
    assert storage.get_experiment(eid)["results"] is None
