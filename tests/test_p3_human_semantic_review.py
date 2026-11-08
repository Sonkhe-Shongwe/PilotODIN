"""P3-03 owner-assessed field hypotheses: real local API, SQLite, and safety.

All data and deliberate mutations are confined to pytest tmp_path.
No model fitting, source edits or actual user project access.
"""
from __future__ import annotations

import sqlite3
import pandas as pd
from fastapi.testclient import TestClient
from backend import main, quality, storage


def prepared(tmp_path, monkeypatch):
    home=tmp_path/"p3-human-review"
    (home/"datasets").mkdir(parents=True)
    (home/"models").mkdir()
    monkeypatch.setattr(storage,"HOME",home)
    monkeypatch.setattr(storage,"DB_PATH",home/"pilotodin.sqlite3")
    storage.init()
    quality._init_tables()
    raw=("claim_id,claim_amount,policy_number,Region\n"+
         "".join(f"C{i:03d},{100+i},P{i%4},{' Mpumalanga ' if i in (1,2) else 'Gauteng'}\n"
                 for i in range(36))).encode("utf-8")
    client=TestClient(main.app)
    result=client.post("/api/projects",
        files={"file":("synthetic_owner_review.csv",raw,"text/csv")})
    assert result.status_code==201,result.text
    pid=result.json()["id"]
    return client,pid,home,raw


def candidate(client,pid,version=0,role="possible_monetary_measure"):
    r=client.get(f"/api/projects/{pid}/semantic-reviews?expected_version={version}")
    assert r.status_code==200,r.text
    return next(x for x in r.json()["candidates"] if x["column"]=="claim_amount" and x["role"]==role)


def proposal(item,*,version=0,decision="acceptable",note="",revision=None):
    return {
        "expected_version":version,
        "column":item["column"],"role":item["role"],
        "hypothesis_hash":item["hypothesis_hash"],
        "decision":decision,"explanation":note,
        "expected_revision":item["revision"] if revision is None else revision,
    }


def test_no_automatic_review_and_explicit_save_reload(tmp_path,monkeypatch):
    client,pid,home,raw=prepared(tmp_path,monkeypatch)
    entry=candidate(client,pid)
    assert entry["review"] is None and entry["revision"]==0
    with storage.connect() as con:
        assert con.execute("SELECT count(*) FROM semantic_human_reviews").fetchone()[0]==0
        assert con.execute("SELECT count(*) FROM semantic_human_review_events").fetchone()[0]==0
    path=f"/api/projects/{pid}/semantic-reviews"
    created=client.post(path,json=proposal(entry))
    assert created.status_code==200,created.text
    assert created.json()["revision"]==1
    assert created.json()["review_state"]=="owner_attestation_not_independently_verified"
    again=candidate(client,pid)
    assert again["review"]["decision"]=="acceptable"
    assert again["review"]["revision"]==1
    assert again["revision"]==1
    with storage.connect() as con:
        assert con.execute("SELECT count(*) FROM semantic_human_review_events").fetchone()[0]==1
        assert tuple(con.execute("SELECT revision,decision FROM semantic_human_review_events").fetchone())==(1,"acceptable")
    assert client.get(f"/api/projects/{pid}/semantics?expected_version=0").json()["user_context"] is None
    assert storage.recent_experiments(pid)==[]
    assert __import__("pathlib").Path(storage.get_project(pid)["dataset_path"]).read_bytes()==raw


def test_revision_edit_audit_and_concurrent_writes(tmp_path,monkeypatch):
    client,pid,home,_=prepared(tmp_path,monkeypatch)
    path=f"/api/projects/{pid}/semantic-reviews"
    entry=candidate(client,pid)
    first=client.post(path,json=proposal(entry))
    assert first.status_code==200
    changed=client.post(path,json=proposal(entry,decision="needs_correction",
                note="The column means the claimed amount in local currency.",revision=1))
    assert changed.status_code==200,changed.text
    assert changed.json()["revision"]==2
    stale=client.post(path,json=proposal(entry,decision="cannot_assess",revision=1))
    assert stale.status_code==409
    assert candidate(client,pid)["review"]["decision"]=="needs_correction"
    with storage.connect() as con:
        rows=con.execute(
            "SELECT revision,previous_decision,decision FROM semantic_human_review_events ORDER BY event_id"
        ).fetchall()
        assert [tuple(row) for row in rows]==[
            (1,None,"acceptable"),(2,"acceptable","needs_correction")
        ]
        assert con.execute("SELECT count(*) FROM semantic_human_reviews").fetchone()[0]==1


def test_reject_unsafe_or_unreviewable_inputs_without_mutation(tmp_path,monkeypatch):
    client,pid,home,_=prepared(tmp_path,monkeypatch)
    item=candidate(client,pid)
    endpoint=f"/api/projects/{pid}/semantic-reviews"
    invalid=[
        {**proposal(item),"hypothesis_hash":"f"*64},
        {**proposal(item),"column":"unknown_field"},
        {**proposal(item),"role":"possible_outcome"},
        {**proposal(item),"decision":"needs_correction","explanation":"short"},
        {**proposal(item),"decision":"verified_truth"},
        {**proposal(item),"expected_version":5},
        {**proposal(item),"expected_version":-1},
    ]
    for bad in invalid:
        answer=client.post(endpoint,json=bad)
        assert answer.status_code in (409,422),answer.text
    assert client.post(endpoint,json=proposal(item),
        headers={"Origin":"https://untrusted.example"}).status_code==403
    assert client.get(endpoint+"?expected_version=0",
        headers={"Origin":"https://untrusted.example"}).status_code==403
    assert client.post("/api/projects/missing/semantic-reviews",
        json=proposal(item)).status_code==404
    with storage.connect() as con:
        assert con.execute("SELECT count(*) FROM semantic_human_reviews").fetchone()[0]==0


def test_independent_projects_and_quality_version_boundary(tmp_path,monkeypatch):
    client,one,home,raw=prepared(tmp_path,monkeypatch)
    entry=candidate(client,one)
    assert client.post(f"/api/projects/{one}/semantic-reviews",
                       json=proposal(entry)).status_code==200
    uploaded=client.post("/api/projects",
        files={"file":("synthetic_other.csv",raw,"text/csv")})
    assert uploaded.status_code==201
    two=uploaded.json()["id"]
    assert candidate(client,two)["review"] is None
    snapshot=client.get(f"/api/projects/{one}/quality").json()
    issue=next(i for i in snapshot["issues"] if i["column"]=="Region" and
        i["kind"]=="whitespace" and i["affected_rows"]==2)
    prepared_change=client.post(f"/api/projects/{one}/quality/proposals",json={
        "issue_id":issue["id"],"operation":"approve","expected_version":0
    })
    assert prepared_change.status_code==200,prepared_change.text
    receipt=prepared_change.json()
    assert client.post(f"/api/projects/{one}/quality/commit",json={
        "proposal_id":receipt["proposal_id"],"proposal_hash":receipt["proposal_hash"],
    }).status_code==200
    assert client.get(f"/api/projects/{one}/semantic-reviews?expected_version=0").status_code==409
    assert client.post(f"/api/projects/{one}/semantic-reviews",
                       json=proposal(entry)).status_code==409
    fresh=candidate(client,one,version=1)
    assert fresh["review"] is None and fresh["revision"]==0
    assert candidate(client,two)["review"] is None
    with storage.connect() as con:
        old=con.execute(
            "SELECT decision FROM semantic_human_reviews WHERE project_id=? AND quality_version=0",
            (one,)
        ).fetchone()
        assert old is not None and old["decision"]=="acceptable"
        assert con.execute(
            "SELECT count(*) FROM semantic_human_reviews WHERE project_id=? AND quality_version=1",
            (one,)
        ).fetchone()[0]==0
    assert __import__("pathlib").Path(storage.get_project(one)["dataset_path"]).read_bytes()==raw


def test_transaction_gate_refuses_incorrect_current_quality_state(tmp_path,monkeypatch):
    client,pid,home,_=prepared(tmp_path,monkeypatch)
    item=candidate(client,pid)
    # Simulates a concurrent Quality commit between candidate GET and write,
    # even if an API-level view returns a previously cached version.
    # Simulate a concurrent commit AFTER the API saw the old Quality frame.
    # Keep the deliberately stale API-level snapshot while testing SQLite's
    # independent BEGIN IMMEDIATE + quality_state write gate.
    stale_frame,_=main.quality.current_data(pid)
    monkeypatch.setattr(main.quality, "current_data",
        lambda project_id:(stale_frame,0) if project_id==pid else
            (_ for _ in ()).throw(AssertionError("Other project")))
    with storage.connect() as con:
        con.execute("UPDATE quality_state SET current_version=1 WHERE project_id=?",(pid,))
    assert client.post(f"/api/projects/{pid}/semantic-reviews",
                       json=proposal(item)).status_code==409
    with storage.connect() as con:
        assert con.execute("SELECT count(*) FROM semantic_human_reviews").fetchone()[0]==0
