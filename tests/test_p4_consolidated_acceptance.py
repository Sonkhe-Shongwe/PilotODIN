"""P4-15 consolidated scoped phase-exit regressions, exclusively synthetic.

These tests support source-level engineering confidence, not physical Windows,
business suitability, legal approval, model accuracy or formal phase closure.
"""
from __future__ import annotations

import json

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from backend import main, storage, target_opportunities


def _frame(kind: str) -> pd.DataFrame:
    n = 80
    original = {
        "account_id": [f"P415-PRIVATE-{i // 2}" for i in range(n)],
        "feature": [i % 13 for i in range(n)],
    }
    if kind == "classification":
        original["churn"] = ["Y", "N"] * 40
    elif kind == "regression":
        original["future_cost"] = [float(110 + i) for i in range(n)]
    elif kind == "rare":
        original["churn"] = ["Y"] * 76 + ["N"] * 4
    elif kind == "insufficient":
        original["churn"] = ["Y", "N"] * 12 + [None] * 56
    elif kind == "no_outcome":
        original["generic_measure"] = [i * 5 for i in range(n)]
    elif kind == "wide":
        original["churn"] = ["Y", "N"] * 40
        original.update({f"feature_{j:03d}": [i % 9 for i in range(n)]
                         for j in range(70)})
    else:
        raise AssertionError("Unknown synthetic case")
    return pd.DataFrame(original)


@pytest.mark.parametrize("kind,task,abstained,truncated", [
    ("classification", "classification", False, False),
    ("regression", "regression", False, False),
    ("rare", None, True, False),
    ("insufficient", None, True, False),
    ("no_outcome", None, True, False),
    ("wide", None, True, True),
])
def test_p4_15_consolidated_queue_cases(kind, task, abstained, truncated):
    frame = _frame(kind)
    before = frame.copy(deep=True)
    queue = target_opportunities.recommend(frame, 0)
    assert queue["abstained"] is abstained
    assert queue["queue_resource_review"]["truncated"] is truncated
    assert queue["ranking_contract"]["automatic_target_selection"] is False
    assert queue["ranking_contract"]["business_value_verified"] is False
    assert queue["ranking_contract"]["model_performance_measured"] is False
    assert all(not c["safe_to_train_automatically"] for c in (
        queue["suggestions"] + queue["other_reviewable"] +
        queue["blocked_examples"]
    ))
    assert all(not c["decision_utility"]["training_authorised"] for c in (
        queue["suggestions"] + queue["other_reviewable"] +
        queue["blocked_examples"]
    ))
    if task is None:
        assert queue["suggestions"] == []
        assert queue["other_reviewable"] == []
        assert queue["abstention_reason"]
        if kind == "wide":
            assert "Incomplete target screening" in queue["abstention_reason"]
        elif kind in ("rare", "insufficient"):
            assert queue["blocked_examples"][0]["technical_status"] == "blocked"
    else:
        candidate = queue["suggestions"][0]
        assert candidate["task_hypothesis"] == task
        assert candidate["review_priority"]["training_authorised"] is False
        assert candidate["decision_utility"]["verified_label_origin"] is False
        assert candidate["decision_utility"]["verified_prediction_time"] is False
        assert candidate["decision_utility"]["verified_group_independence"] is False
        assert candidate["decision_utility"]["measured_decision_benefit"] is False
        assert candidate["decision_utility"]["entity_repetition"]["repeated"][0][
            "additional_occurrences"
        ] == 40
    assert "P415-PRIVATE-0" not in json.dumps(queue)
    assert frame.equals(before)


def test_p4_15_queue_abstention_does_not_authorise_manual_inspection():
    frame = _frame("wide")
    original = frame.copy(deep=True)
    listed = target_opportunities.recommend(frame, 5)
    assert listed["queue_resource_review"]["truncated"] is True
    assert listed["suggestions"] == []
    manual = target_opportunities.inspect_manual_target(frame, 5, "churn")
    assert manual["column"] == "churn"
    assert manual["version"] == 5
    assert manual["resource_review"]["truncated"] is True
    assert manual["candidate"]["technical_status"] == "blocked"
    assert manual["candidate"]["task_hypothesis"] is None
    assert manual["training_authorised"] is False
    assert manual["candidate"]["decision_utility"]["measured_decision_benefit"] is False
    assert frame.equals(original)
    assert "P415-PRIVATE-0" not in json.dumps(manual)


def test_p4_15_ambiguous_label_and_duplicate_header_cannot_create_approval():
    frame = pd.DataFrame({
        "account_id": [f"P415-PRIVATE-{i}" for i in range(80)],
        "churn_probability": [i / 100 for i in range(80)],
        "feature": list(range(80)),
    })
    before = frame.copy(deep=True)
    queue = target_opportunities.recommend(frame, 0)
    assert queue["abstained"] is True
    assert queue["blocked_examples"][0]["technical_status"] == "blocked"
    assert "ground-truth" in " ".join(queue["blocked_examples"][0]["blockers"])
    manual = target_opportunities.inspect_manual_target(frame, 0, "feature")
    assert manual["candidate"]["technical_status"] == "blocked"
    assert manual["name_hint"] == "no_supported_outcome_name"
    assert manual["training_authorised"] is False
    assert frame.equals(before)
    duplicated = pd.DataFrame([["Y", "N", 1]] * 40,
                              columns=["churn", "churn", "feature"])
    with pytest.raises(ValueError, match="unique column"):
        target_opportunities.recommend(duplicated, 0)
    with pytest.raises(ValueError, match="unique column"):
        target_opportunities.inspect_manual_target(duplicated, 0, "churn")


def test_p4_15_api_project_version_description_origin_and_no_training(
    tmp_path, monkeypatch
):
    home = tmp_path / "p4-15-isolated"
    (home / "datasets").mkdir(parents=True)
    (home / "models").mkdir()
    monkeypatch.setattr(storage, "HOME", home)
    monkeypatch.setattr(storage, "DB_PATH", home / "pilotodin.sqlite3")
    storage.init()
    main.quality._init_tables()  # controlled Quality CAS state in disposable DB
    a = storage.save_project("Synthetic A", "a.csv", ".csv",
                             home / "datasets" / "a.csv", {"rows": 80})
    b = storage.save_project("Synthetic B", "b.csv", ".csv",
                             home / "datasets" / "b.csv", {"rows": 80})
    c = storage.save_project("Synthetic C", "c.csv", ".csv",
                             home / "datasets" / "c.csv", {"rows": 80})
    versions = {a: 0, b: 0, c: 0}
    with storage.connect() as con:
        for pid in (a,b,c):
            con.execute(
                "INSERT INTO quality_state(project_id,original_sha256,current_version) "
                "VALUES (?,?,?)", (pid,"synthetic-fixture-only",0)
            )
    frames = {
        a: _frame("classification"),
        b: _frame("regression"),
        c: _frame("wide"),
    }
    monkeypatch.setattr(main.quality, "current_data",
                        lambda pid: (frames[pid], versions[pid]))
    client = TestClient(main.app)
    base_a = f"/api/projects/{a}"
    base_b = f"/api/projects/{b}"
    base_c = f"/api/projects/{c}"
    for pid, expected in [(a, "churn"), (b, "future_cost")]:
        response = client.get(f"/api/projects/{pid}/target-opportunities",
                              params={"expected_version": 0})
        assert response.status_code == 200
        assert response.json()["suggestions"][0]["column"] == expected
    partial = client.get(base_c + "/target-opportunities",
                         params={"expected_version": 0})
    assert partial.status_code == 200
    assert partial.json()["queue_resource_review"]["truncated"] is True
    assert partial.json()["suggestions"] == []
    detail = client.get(base_c + "/target-opportunities/inspect",
                        params={"expected_version": 0, "column": "churn"})
    assert detail.status_code == 200
    assert detail.json()["candidate"]["technical_status"] == "blocked"
    assert detail.json()["training_authorised"] is False
    description = {
        "expected_version": 0,
        "target_column": "churn",
        "outcome_definition": "User-described synthetic cancellation outcome",
        "decision_action": "User-described synthetic review action",
        "prediction_moment": "Before the synthetic event is observed",
        "label_source": "Unverified synthetic owner description",
    }
    save = client.post(base_a + "/target-business-context", json=description)
    assert save.status_code == 200, save.text
    a0 = client.get(base_a + "/target-opportunities",
                    params={"expected_version": 0}).json()
    assert a0["suggestions"][0]["user_context"]["verification_state"] == (
        "user_described_not_independently_verified"
    )
    assert a0["suggestions"][0]["decision_utility"]["measured_decision_benefit"] is False
    assert storage.target_contexts(b, 0) == {}
    assert storage.target_contexts(c, 0) == {}
    versions[a] = 1
    with storage.connect() as con:
        con.execute("UPDATE quality_state SET current_version=1 WHERE project_id=?", (a,))
    assert client.get(base_a + "/target-opportunities",
                      params={"expected_version": 0}).status_code == 409
    assert client.get(base_a + "/target-opportunities/inspect",
                      params={"expected_version": 0, "column": "churn"}).status_code == 409
    assert client.post(base_a + "/target-business-context",
                       json=description).status_code == 409
    new = client.get(base_a + "/target-opportunities",
                     params={"expected_version": 1})
    assert new.status_code == 200
    assert new.json()["suggestions"][0]["user_context"] is None
    assert client.get(base_b + "/target-opportunities/inspect",
                      params={"expected_version": 0, "column": "churn"}).status_code == 422
    assert client.get(base_c + "/target-opportunities/inspect",
                      params={"expected_version": 0, "column": "churn"},
                      headers={"Origin": "https://not-local.example"}).status_code == 403
    assert storage.target_contexts(a, 0)["churn"]["outcome_definition"] == (
        description["outcome_definition"]
    )
    assert storage.target_contexts(a, 1) == {}
    for pid in (a, b, c):
        assert storage.recent_experiments(pid) == []
