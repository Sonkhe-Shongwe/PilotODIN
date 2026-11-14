"""Version-bound P4 context is user-supplied information, never validated business truth."""
from __future__ import annotations

import pandas as pd
from fastapi.testclient import TestClient

from backend import main, storage, target_opportunities


def _frame():
    return pd.DataFrame({
        "churn": ["Y","N"]*40,
        "fraud_reported": ["Y","N"]*40,
        "feature": list(range(80)),
    })


def _payload(version=2,target="churn"):
    return {
        "expected_version":version,"target_column":target,
        "outcome_definition":"Customer cancellation recorded as a historical label",
        "decision_action":"Review proactive retention interventions before cancellation",
        "prediction_moment":"At renewal review before cancellation decision is known",
        "label_source":"Historical outcome recorded by customer operations",
    }


def _client_with_projects(tmp_path,monkeypatch):
    home=tmp_path/"context-fixture"
    (home/"datasets").mkdir(parents=True)
    (home/"models").mkdir()
    monkeypatch.setattr(storage,"HOME",home)
    monkeypatch.setattr(storage,"DB_PATH",home/"pilotodin.sqlite3")
    storage.init()
    main.quality._init_tables()  # synthetic SQLite Quality state for CAS tests
    ids=[]
    for n in ("A","B"):
        ids.append(storage.save_project(n,n+".csv",".csv",home/"datasets"/(n+".csv"),{"rows":80}))
    with storage.connect() as con:
        for pid in ids:
            con.execute(
                "INSERT INTO quality_state(project_id,original_sha256,current_version) "
                "VALUES (?,?,?)", (pid,"synthetic-fixture-only",2)
            )
    monkeypatch.setattr(main.quality,"current_data",lambda pid: (_frame(),2)
                        if pid in ids else (_ for _ in ()).throw(AssertionError("wrong project")))
    return TestClient(main.app),ids


def test_user_description_persists_and_ranks_without_overriding_technical_screening(tmp_path,monkeypatch):
    client,(pid,_)=_client_with_projects(tmp_path,monkeypatch)
    base=client.get(f"/api/projects/{pid}/target-opportunities?expected_version=2")
    assert base.status_code==200
    assert base.json()["business_context_state"]=="unverified"
    before=storage.recent_experiments(pid)
    save=client.post(f"/api/projects/{pid}/target-business-context",json=_payload(),
                     headers={"Origin":"http://127.0.0.1:5173"})
    assert save.status_code==200,save.text
    assert save.json()["verification_state"]=="user_described_not_independently_verified"
    after=client.get(f"/api/projects/{pid}/target-opportunities?expected_version=2").json()
    assert after["business_context_state"]=="user_described_unverified"
    named={c["column"]:c for c in after["suggestions"]}
    assert named["churn"]["business_relevance"]=="user_described_unverified"
    assert named["churn"]["user_context"]["decision_action"]==_payload()["decision_action"]
    assert named["churn"]["safe_to_train_automatically"] is False
    assert after["suggestions"][0]["column"]=="churn"
    assert storage.recent_experiments(pid)==before==[]


def test_context_is_isolated_by_project_and_quality_version(tmp_path,monkeypatch):
    client,(one,two)=_client_with_projects(tmp_path,monkeypatch)
    assert client.post(f"/api/projects/{one}/target-business-context",json=_payload()).status_code==200
    assert storage.target_contexts(two,2)=={}
    assert storage.target_contexts(one,1)=={}
    assert storage.target_contexts(one,2)["churn"]["outcome_definition"]==_payload()["outcome_definition"]
    assert client.post(f"/api/projects/{one}/target-business-context",json=_payload(version=1)).status_code==409
    assert storage.target_contexts(one,1)=={}
    second=_payload()
    second["decision_action"]="Present a revised decision with documented customer feedback"
    assert client.post(f"/api/projects/{one}/target-business-context",json=second).status_code==200
    assert storage.target_contexts(one,2)["churn"]["decision_action"]==second["decision_action"]


def test_local_security_bad_columns_and_empty_or_too_long_descriptions(tmp_path,monkeypatch):
    client,(pid,_)=_client_with_projects(tmp_path,monkeypatch)
    path=f"/api/projects/{pid}/target-business-context"
    payload=_payload()
    assert client.post(path,json=payload,headers={"Origin":"https://remote.example"}).status_code==403
    assert storage.target_contexts(pid,2)=={}
    assert client.post(path,json=_payload(target="unknown")).status_code==422
    invalid=_payload()
    invalid["label_source"]="          "
    assert client.post(path,json=invalid).status_code==422
    invalid2=_payload()
    invalid2["outcome_definition"]="A"*601
    assert client.post(path,json=invalid2).status_code==422
    assert client.post("/api/projects/unknown/target-business-context",json=payload).status_code==404
    assert storage.target_contexts(pid,2)=={}


def test_context_does_not_override_technical_block_or_confirm_true_fraud():
    data=pd.DataFrame({
        "fraud_reported":["Y"]*75+["N"]*5,
        "churn":["Y","N"]*40,
        "feature":list(range(80)),
    })
    user={
      "fraud_reported":{
        "target_column":"fraud_reported",
        "outcome_definition":"Reported fraud as labelled by case analysts",
        "decision_action":"Send suspicious cases for manual review",
        "prediction_moment":"Before any adjudication or claim payment",
        "label_source":"Internal claim report, not court-confirmed fraud",
        "updated_at":"2026-10-25T00:00:00+00:00",
      }
    }
    out=target_opportunities.recommend(data,5,user)
    blocked={x["column"]:x for x in out["blocked_examples"]}
    assert "fraud_reported" in blocked
    assert blocked["fraud_reported"]["technical_status"]=="blocked"
    assert blocked["fraud_reported"]["safe_to_train_automatically"] is False
    assert any("at least 6" in x for x in blocked["fraud_reported"]["blockers"])
    assert "churn" in {x["column"] for x in out["suggestions"]}
    assert out["business_context_state"]=="unverified"


def test_unrelated_business_text_never_creates_a_new_label_candidate():
    data=pd.DataFrame({"first":[1,2]*25,"second":["red","blue"]*25})
    out=target_opportunities.recommend(data,0,{
        "first":{
            "outcome_definition":"This is described as churn even though its column has no outcome name",
            "decision_action":"Review the renewal process of existing customers",
            "prediction_moment":"Before renewal notices have been generated",
            "label_source":"Manual operational notes from user",
            "updated_at":"2026-10-25",
            "target_column":"first",
        }
    })
    assert out["abstained"]
    assert not out["suggestions"]



def test_quality_revision_between_initial_check_and_context_commit_returns_409(tmp_path, monkeypatch):
    # Simulate a competing, completed Quality revision in the exact gap
    # between main.quality.current_data and the later storage transaction.
    client, (pid, other) = _client_with_projects(tmp_path, monkeypatch)
    original_save = storage.save_target_context

    def quality_changed_before_commit(*args):
        with storage.connect() as con:
            con.execute(
                "UPDATE quality_state SET current_version=3 WHERE project_id=?",
                (pid,),
            )
        return original_save(*args)

    monkeypatch.setattr(storage, "save_target_context", quality_changed_before_commit)
    response = client.post(f"/api/projects/{pid}/target-business-context", json=_payload())
    assert response.status_code == 409, response.text
    assert "version changed" in response.json()["detail"]
    assert storage.target_contexts(pid, 2) == {}
    assert storage.target_contexts(pid, 3) == {}
    assert storage.target_contexts(other, 2) == {}
    assert storage.recent_experiments(pid) == []


def test_archive_between_initial_check_and_context_commit_returns_409(tmp_path, monkeypatch):
    # The read-only HTTP middleware could see an active project just before
    # another window archives it. The write transaction MUST still refuse.
    from backend import project_lifecycle

    client, (pid, other) = _client_with_projects(tmp_path, monkeypatch)
    original_save = storage.save_target_context

    def archived_before_commit(*args):
        project_lifecycle.change(pid, "archive", expected_revision=0)
        return original_save(*args)

    monkeypatch.setattr(storage, "save_target_context", archived_before_commit)
    response = client.post(f"/api/projects/{pid}/target-business-context", json=_payload())
    assert response.status_code == 409, response.text
    assert "archived" in response.json()["detail"].lower()
    assert storage.target_contexts(pid, 2) == {}
    assert storage.target_contexts(other, 2) == {}
    assert storage.recent_experiments(pid) == []
