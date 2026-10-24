"""Immutable Explore snapshots must be recomputed, scoped, bounded and versioned."""
from __future__ import annotations

import hashlib
import json
import sqlite3
import pandas as pd
import pytest
from fastapi import HTTPException

from backend import main, saved_analyses


@pytest.fixture
def saved_store(tmp_path,monkeypatch):
    db=tmp_path/"explore-tests.sqlite3"
    def connect():
        conn=sqlite3.connect(db,timeout=15)
        conn.row_factory=sqlite3.Row
        return conn
    monkeypatch.setattr(saved_analyses.storage,"connect",connect)
    monkeypatch.setattr(saved_analyses.storage,"get_project",lambda project: {"id":project} if project in ("a","b") else None)
    current={"version":2}
    frame=pd.DataFrame({
        "ClaimID":["A1","A2","A3","A4","A5","A6"],
        "Region":["North","South","North","South","North","South"],
        "Amount":[10,20,30,40,50,60],
        "Loss":[5,10,15,20,25,30]
    })
    monkeypatch.setattr(saved_analyses.quality,"current_data",lambda _: (frame,current["version"]))
    monkeypatch.setattr(saved_analyses.quality,"current_version",lambda _: current["version"])
    with connect() as con:
        con.execute("CREATE TABLE projects (id TEXT PRIMARY KEY)")
        con.executemany("INSERT INTO projects VALUES(?)",[("a",),("b",)])
    return frame,current,connect


def save_example(project_id="a",version=2,**kwargs):
    payload=dict(title="North claim investigation",expected_version=version,
        x="Region",y="Amount",kind="bar",aggregation="sum",bins=12,
        correlation_method="pearson",filters=[{"column":"Region","op":"eq","value":"North"}])
    return saved_analyses.save(project_id,**(payload|kwargs))


def test_save_is_server_recomputed_immutable_with_integrity_proof(saved_store):
    df,state,conn=saved_store
    before=df.copy(deep=True)
    result=save_example()
    assert result["dataset_version"]==2 and not result["stale"]
    assert result["snapshot"]["filtered_rows"]==3
    assert result["snapshot"]["total_rows"]==6
    assert result["snapshot"]["chart"]["data"][0]["value"]==90
    assert result["configuration"]["filters"][0]["value"]=="North"
    with conn() as con:
        saved=con.execute("SELECT * FROM explore_snapshots_v1 WHERE id=?",(result["id"],)).fetchone()
    assert result["sha256"]==hashlib.sha256(saved["snapshot_json"].encode()).hexdigest()
    assert saved["dataset_version"]==2
    assert result["configuration_verified"] is True
    assert result["snapshot"]["configuration_sha256"]==hashlib.sha256(saved["configuration_json"].encode()).hexdigest()
    assert df.equals(before)
    assert len(saved_analyses.listing("a"))==1


def test_stale_read_shows_frozen_result_without_auto_recomputation(saved_store):
    df,current,_=saved_store
    original=save_example()
    current["version"]=3
    df.loc[df["Region"]=="North","Amount"]=999
    old=saved_analyses.load("a",original["id"])
    assert old["stale"] and old["current_dataset_version"]==3
    assert old["snapshot"]["chart"]["data"][0]["value"]==90
    assert saved_analyses.listing("a")[0]["stale"]
    with pytest.raises(saved_analyses.SavedAnalysisError) as err:
        save_example(version=2)
    assert err.value.status==409


def test_project_scoping_and_tamper_detection(saved_store):
    _,_,conn=saved_store
    saved=save_example("a")
    with pytest.raises(saved_analyses.SavedAnalysisError) as err:
        saved_analyses.load("b",saved["id"])
    assert err.value.status==404
    assert saved_analyses.listing("b")==[]
    with conn() as db:
        db.execute("UPDATE explore_snapshots_v1 SET snapshot_json=? WHERE id=?",
                   ('{"modified":true}', saved["id"]))
    with pytest.raises(saved_analyses.SavedAnalysisError,match="integrity") as err:
        saved_analyses.load("a",saved["id"])
    assert err.value.status==409


def test_save_rejects_invalid_filter_chart_and_unbounded_title(saved_store):
    with pytest.raises(saved_analyses.SavedAnalysisError):
        save_example(title="x")
    with pytest.raises(ValueError):
        save_example(filters=[{"column":"ClaimID","op":"eq","value":"A1"}])
    with pytest.raises(saved_analyses.SavedAnalysisError):
        save_example(kind="unsafe")
    with pytest.raises(saved_analyses.SavedAnalysisError):
        save_example(x="NotAField")


def test_empty_filter_result_saves_trustworthy_zero_counts(saved_store):
    result=save_example(filters=[
        {"column":"Region","op":"eq","value":"North"},
        {"column":"Amount","op":"range","min":60,"max":60}
    ])
    assert result["snapshot"]["filtered_rows"]==0
    assert result["snapshot"]["chart"] is None
    assert result["snapshot"]["overview"]["rows"]==0


def test_http_api_roundtrip_keeps_project_scope_and_version(saved_store,monkeypatch):
    monkeypatch.setattr(main,"project_or_404",lambda pid: {"id":pid} if pid in ("a","b") else None)
    body=main.SaveExploreAnalysisRequest(title="A frozen analysis",expected_version=2,
           x="Region",y="Amount",kind="bar",aggregation="sum",
           filters=[main.ExploreFilterClause(column="Region",op="eq",value="North")])
    saved=main.save_explore_analysis("a",body)
    assert saved["project_id"]=="a" and saved["sha256"]
    assert len(main.list_saved_explore_analyses("a"))==1
    assert main.read_saved_explore_analysis("a",saved["id"])["id"]==saved["id"]
    with pytest.raises(HTTPException) as exc:
        main.read_saved_explore_analysis("b",saved["id"])
    assert exc.value.status_code==404


def test_configuration_corruption_detected_even_when_numeric_snapshot_sha_still_matches(saved_store):
    _,_,conn=saved_store
    result=save_example()
    with conn() as con:
        original=con.execute("SELECT configuration_json FROM explore_snapshots_v1 WHERE id=?",(result["id"],)).fetchone()[0]
        altered=json.loads(original);altered["filters"]=[]
        con.execute("UPDATE explore_snapshots_v1 SET configuration_json=? WHERE id=?",
                    (json.dumps(altered,sort_keys=True,separators=(',',':')),result["id"]))
    with pytest.raises(saved_analyses.SavedAnalysisError,match="configuration integrity") as err:
        saved_analyses.load("a",result["id"])
    assert err.value.status==409


def test_legacy_snapshot_checksum_still_readable_but_settings_unverified(saved_store):
    _,_,conn=saved_store
    result=save_example()
    with conn() as con:
        row=con.execute("SELECT snapshot_json FROM explore_snapshots_v1 WHERE id=?",(result["id"],)).fetchone()
        snapshot=json.loads(row["snapshot_json"])
        del snapshot["configuration_sha256"]
        canonical=json.dumps(snapshot,sort_keys=True,ensure_ascii=False,allow_nan=False,separators=(',',':'))
        con.execute("UPDATE explore_snapshots_v1 SET snapshot_json=?,sha256=? WHERE id=?",
                    (canonical,hashlib.sha256(canonical.encode()).hexdigest(),result["id"]))
    legacy=saved_analyses.load("a",result["id"])
    assert legacy["configuration_verified"] is False
    assert legacy["snapshot"]["filtered_rows"]==3
