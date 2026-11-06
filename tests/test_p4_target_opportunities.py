"""P4 deterministic target opportunities: no model fitting, no target selection."""
from __future__ import annotations

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from backend import main, storage, target_opportunities


def insurance_frame():
    return pd.DataFrame({
        "claim_id": [f"C{i:03}" for i in range(80)],
        "policy_number": [f"P{i//2:03}" for i in range(80)],
        "incident_date": [f"2026-01-{i%28+1:02}" for i in range(80)],
        "claim_amount": [500+i for i in range(80)],
        "fraud_reported": ["Y" if i % 4 == 0 else "N" for i in range(80)],
        "incident_type": ["Traffic", "Theft"] * 40,
    })


def test_insurance_shortlist_is_explicit_review_only():
    out=target_opportunities.recommend(insurance_frame(),3)
    assert out["version"]==3
    assert out["business_context_state"]=="unverified"
    assert out["abstained"] is False
    selected={item["column"]:item for item in out["suggestions"]}
    assert "fraud_reported" in selected
    item=selected["fraud_reported"]
    assert item["technical_status"]=="reviewable"
    assert item["task_hypothesis"]=="classification"
    assert item["smallest_class"]==20
    assert item["labelled_rows"]==80
    assert item["quality_version"]==3
    assert item["business_relevance"]=="unverified"
    assert item["safe_to_train_automatically"] is False
    assert any("not proof of confirmed fraud" in w for w in item["review_warnings"])
    assert "claim_id" not in selected
    assert "incident_date" not in selected
    assert "No model trained" in out["ranking_basis"]
    assert "raw label values" in out["privacy"]


def test_rare_class_and_insufficient_label_support_are_blocked():
    data=pd.DataFrame({
        "outcome": ["rare"]*5+["major"]*75,
        "churn": ["Y","N"]*10 + [None]*60,
        "account_id": list(range(80)),
        "feature": list(range(80)),
    })
    out=target_opportunities.recommend(data,0)
    assert out["abstained"]
    candidates={x["column"]:x for x in out["blocked_examples"]}
    assert "outcome" in candidates
    assert any("6" in b for b in candidates["outcome"]["blockers"])
    assert "churn" in candidates
    assert any("30" in b for b in candidates["churn"]["blockers"])


def test_ambiguous_no_outcome_abstains_without_arbitrary_numeric_target():
    data=pd.DataFrame({
        "record_id":range(50), "col1":list(range(50)),
        "col2":list(range(100,150)), "date":list(range(50)),
    })
    out=target_opportunities.recommend(data,5)
    assert out["abstained"] is True
    assert not out["suggestions"]
    assert out["eligible_count"]==0
    assert out["abstention_reason"]
    assert "auto" not in out["ranking_basis"].lower()


def test_value_regression_cannot_be_mistaken_for_predictive_accuracy():
    frame=pd.DataFrame({
        "future_revenue":[10.5+i*.8 for i in range(70)],
        "product":["A","B"]*35,
        "customer_id":range(70),
    })
    out=target_opportunities.recommend(frame,9)
    matches=[item for item in out["suggestions"] if item["column"]=="future_revenue"]
    assert len(matches)==1
    candidate=matches[0]
    assert candidate["task_hypothesis"]=="regression"
    assert candidate["technical_status"]=="reviewable"
    assert "score" not in candidate
    assert "performance" not in candidate
    assert candidate["business_relevance"]=="unverified"


def test_time_to_resolution_can_be_a_duration_outcome_not_a_timestamp():
    data=pd.DataFrame({
        "time_to_resolution":[float(i+1) for i in range(70)],
        "case_type":["Complaint","Inquiry"]*35,
        "feature":[i%7 for i in range(70)],
    })
    out=target_opportunities.recommend(data,1)
    matches=[x for x in out["suggestions"] if x["column"]=="time_to_resolution"]
    assert len(matches)==1
    assert matches[0]["task_hypothesis"]=="regression"
    assert matches[0]["business_relevance"]=="unverified"


def test_text_identifiers_empty_and_constant_labels_never_get_reviewable_shortlist():
    data=pd.DataFrame({
        "target_id":[f"ID{i}" for i in range(40)],
        "label":["Y"]*40,
        "status":[None]*40,
        "value":range(40),
    })
    out=target_opportunities.recommend(data,0)
    assert out["abstained"]
    blocked={item["column"]:item for item in out["blocked_examples"]}
    assert blocked["target_id"]["technical_status"]=="blocked"
    assert "identifier" in " ".join(blocked["target_id"]["blockers"]).lower()
    assert blocked["label"]["technical_status"]=="blocked"
    assert blocked["status"]["technical_status"]=="blocked"


def test_derived_scores_and_probabilities_are_not_treated_as_true_outcomes():
    data=pd.DataFrame({
        "fraud_score":[0.01*i for i in range(70)],
        "churn_probability":[0.02*i for i in range(70)],
        "predicted_outcome":["Y","N"]*35,
        "feature":[i%5 for i in range(70)],
    })
    out=target_opportunities.recommend(data,0)
    assert out["abstained"]
    blocked={x["column"]:x for x in out["blocked_examples"]}
    assert all("ground-truth" in " ".join(x["blockers"]) for x in blocked.values())


def test_missing_labels_are_aggregated_without_personal_values():
    data=pd.DataFrame({
        "churn":["Y","N"]*22+[None]*16,
        "account_id":[f"private-person-{i}" for i in range(60)],
        "usage":[i%10 for i in range(60)],
    })
    out=target_opportunities.recommend(data,1)
    c=out["suggestions"][0]
    assert c["column"]=="churn"
    assert c["missing_labels"]==16
    assert any("missing" in x.lower() for x in c["review_warnings"])
    dumped=str(out)
    assert "private-person-0" not in dumped
    assert "'Y'" not in dumped


def test_record_limit_blocks_candidate_without_training():
    size=target_opportunities.engine.MAX_ML_LABELLED_ROWS + 1
    data=pd.DataFrame({
        "target":["Y","N"]*(size//2)+(["Y"] if size%2 else []),
        "predictor":list(range(size)),
    })
    out=target_opportunities.recommend(data,2)
    assert out["abstained"]
    assert "local ML cap" in " ".join(out["blocked_examples"][0]["blockers"])


def test_deterministic_bounded_shortlist():
    data=pd.DataFrame({
        "churn":["Y","N"]*45,
        "fraud_reported":["Y","N"]*45,
        "failure_flag":["Y","N"]*45,
        "outcome":["Y","N"]*45,
        "cost":[float(x) for x in range(90)],
        "feature":list(range(90)),
    })
    first=target_opportunities.recommend(data,0)
    assert first==target_opportunities.recommend(data,0)
    assert len(first["suggestions"])<=target_opportunities.MAX_SUGGESTIONS
    assert first["eligible_count"]>len(first["suggestions"])
    assert all(c["safe_to_train_automatically"] is False for c in first["suggestions"])


def test_duplicate_column_names_rejected_without_data_edits():
    frame=pd.DataFrame([[1,2],[3,4]],columns=["outcome","outcome"])
    original=frame.copy()
    with pytest.raises(ValueError,match="unique column"):
        target_opportunities.recommend(frame,0)
    assert frame.equals(original)


def test_project_version_and_origin_guards_are_enforced(tmp_path, monkeypatch):
    home=tmp_path/"p4-fixture"
    (home/"datasets").mkdir(parents=True)
    (home/"models").mkdir()
    monkeypatch.setattr(storage,"HOME",home)
    monkeypatch.setattr(storage,"DB_PATH",home/"pilotodin.sqlite3")
    storage.init()
    pid=storage.save_project("Synthetic","data.csv",".csv",home/"datasets"/"data.csv",{"rows":80})
    monkeypatch.setattr(main.quality,"current_data",lambda id: (
        insurance_frame(),4
    ) if id==pid else (_ for _ in ()).throw(AssertionError("wrong project")))
    client=TestClient(main.app)
    path=f"/api/projects/{pid}/target-opportunities?expected_version=4"
    local=client.get(path,headers={"Origin":"http://127.0.0.1:5173"})
    assert local.status_code==200,local.text
    assert local.json()["version"]==4
    assert any(item["column"]=="fraud_reported" for item in local.json()["suggestions"])
    assert client.get(path,headers={"Origin":"https://external.example"}).status_code==403
    assert client.get(f"/api/projects/{pid}/target-opportunities?expected_version=3").status_code==409
    assert client.get(f"/api/projects/{pid}/target-opportunities").status_code==422
    assert client.get("/api/projects/missing/target-opportunities?expected_version=4").status_code==404
    assert client.get(f"/api/projects/{pid}/target-opportunities?expected_version=-1").status_code==422
    assert storage.recent_experiments(pid)==[]
