"""P4-09 phase-exit negative matrix: synthetic evidence, NOT owner acceptance.

Never fits a model, accesses real projects, certifies business utility or
substitutes for a physical Windows Tauri test.
"""
from __future__ import annotations

import json

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from backend import main, storage, target_opportunities


def _frame(kind: str) -> pd.DataFrame:
    rows = 80
    frame = {
        "account_id": [f"SYNTH-ACCOUNT-{i // 2}" for i in range(rows)],
        "feature": [i % 9 for i in range(rows)],
    }
    if kind == "classification":
        frame["churn"] = ["Y", "N"] * 40
    elif kind == "regression":
        frame["future_cost"] = [float(110 + i) for i in range(rows)]
    elif kind == "rare":
        frame["churn"] = ["Y"] * 76 + ["N"] * 4
    elif kind == "insufficient":
        frame["churn"] = ["Y", "N"] * 12 + [None] * 56
    elif kind == "no_named_target":
        frame["generic_measure"] = [i * 3 for i in range(rows)]
    else:
        raise AssertionError("unknown synthetic fixture")
    return pd.DataFrame(frame)


def _context(column: str) -> dict:
    return {
        "target_column": column,
        "outcome_definition": "Synthetic outcome description by operations",
        "decision_action": "A human might review a synthetic future event",
        "prediction_moment": "Before the synthetic event is recorded",
        "label_source": "Owner-described synthetic source, not independently verified",
        "updated_at": "2026-11-09T00:00:00Z",
    }


@pytest.mark.parametrize("kind,task,abstain", [
    ("classification", "classification", False),
    ("regression", "regression", False),
    ("rare", None, True),
    ("insufficient", None, True),
    ("no_named_target", None, True),
])
def test_p4_09_classification_regression_rare_missing_and_abstention(
    kind, task, abstain
):
    frame = _frame(kind)
    original = frame.copy(deep=True)
    target = "future_cost" if kind == "regression" else "churn"
    out = target_opportunities.recommend(frame, 0, {target: _context(target)})
    assert frame.equals(original)
    assert out["abstained"] is abstain
    assert out["ranking_contract"]["automatic_target_selection"] is False
    assert out["ranking_contract"]["business_value_verified"] is False
    assert out["ranking_contract"]["model_performance_measured"] is False
    assert "SYNTH-ACCOUNT-" not in json.dumps(out)
    if task is None:
        assert out["suggestions"] == []
        assert out["other_reviewable"] == []
        if kind in {"rare", "insufficient"}:
            blocked = out["blocked_examples"][0]
            assert blocked["technical_status"] == "blocked"
            assert blocked["safe_to_train_automatically"] is False
            reason = "at least 6" if kind == "rare" else "at least 30"
            assert any(reason in x for x in blocked["blockers"])
            assert blocked["user_context"]["verification_state"] == (
                "user_described_not_independently_verified"
            )
    else:
        review = out["suggestions"][0]
        assert review["task_hypothesis"] == task
        assert review["review_priority"]["training_authorised"] is False
        assert review["review_priority"]["business_value"] == "not_established"
        assert review["safe_to_train_automatically"] is False
        utility = review["decision_utility"]
        assert utility["verified_label_origin"] is False
        assert utility["verified_prediction_time"] is False
        assert utility["verified_group_independence"] is False
        assert utility["measured_decision_benefit"] is False
        assert utility["entity_repetition"]["repeated"][0]["column"] == "account_id"
        assert utility["entity_repetition"]["repeated"][0]["additional_occurrences"] == 40


def test_p4_09_project_and_quality_version_isolation_and_stale_rejection(
    tmp_path, monkeypatch
):
    home = tmp_path / "p4-09-synthetic"
    (home / "datasets").mkdir(parents=True)
    (home / "models").mkdir()
    monkeypatch.setattr(storage, "HOME", home)
    monkeypatch.setattr(storage, "DB_PATH", home / "pilotodin.sqlite3")
    storage.init()
    main.quality._init_tables()  # synthetic fixture uses controlled version state
    a = storage.save_project("Synthetic A", "a.csv", ".csv",
                             home / "datasets" / "a.csv", {"rows": 80})
    b = storage.save_project("Synthetic B", "b.csv", ".csv",
                             home / "datasets" / "b.csv", {"rows": 80})
    version = {a: 0, b: 0}
    with storage.connect() as con:
        for pid in (a,b):
            con.execute(
                "INSERT INTO quality_state(project_id,original_sha256,current_version) "
                "VALUES (?,?,?)", (pid,"synthetic-fixture-only",0)
            )
    frames = {a: _frame("classification"), b: _frame("regression")}
    monkeypatch.setattr(main.quality, "current_data",
                        lambda pid: (frames[pid], version[pid]))
    client = TestClient(main.app)
    a0 = f"/api/projects/{a}/target-opportunities?expected_version=0"
    b0 = f"/api/projects/{b}/target-opportunities?expected_version=0"
    assert client.get(a0).status_code == 200
    assert client.get(b0).status_code == 200
    payload = {
        "expected_version": 0,
        "target_column": "churn",
        "outcome_definition": "Synthetic cancellation outcome recorded by support",
        "decision_action": "Consider early outreach to a synthetic customer",
        "prediction_moment": "Before renewal occurs in the synthetic records",
        "label_source": "A synthetic user-described operational source",
    }
    save = client.post(f"/api/projects/{a}/target-business-context", json=payload)
    assert save.status_code == 200, save.text
    assert client.get(a0).json()["suggestions"][0]["user_context"] is not None
    assert client.get(b0).json()["suggestions"][0]["user_context"] is None
    assert storage.target_contexts(b, 0) == {}
    # Simulated new approved Quality version, not a Quality approval test.
    version[a] = 1
    with storage.connect() as con:
        con.execute("UPDATE quality_state SET current_version=1 WHERE project_id=?", (a,))
    frames[a] = _frame("classification").assign(
        feature=lambda f: f["feature"] * 2
    )
    assert client.get(a0).status_code == 409
    assert client.post(
        f"/api/projects/{a}/target-business-context", json=payload
    ).status_code == 409
    current = client.get(
        f"/api/projects/{a}/target-opportunities?expected_version=1"
    )
    assert current.status_code == 200, current.text
    assert current.json()["suggestions"][0]["user_context"] is None
    assert current.json()["suggestions"][0]["quality_version"] == 1
    assert storage.target_contexts(a, 0)["churn"]["outcome_definition"] == (
        payload["outcome_definition"]
    )
    assert storage.target_contexts(a, 1) == {}
    assert client.get(b0).json()["suggestions"][0]["user_context"] is None
    assert client.get(
        f"/api/projects/{a}/target-opportunities?expected_version=1",
        headers={"Origin": "https://untrusted.example"},
    ).status_code == 403
    assert storage.recent_experiments(a) == []
    assert storage.recent_experiments(b) == []


def test_p4_09_duplicate_headers_and_derived_score_do_not_get_approved():
    duplicated = pd.DataFrame(
        [["Y", "N", 1]] * 40, columns=["churn", "churn", "feature"]
    )
    with pytest.raises(ValueError, match="unique column"):
        target_opportunities.recommend(duplicated, 0)
    out = target_opportunities.recommend(pd.DataFrame({
        "churn_probability": [0.01 * i for i in range(80)],
        "feature": [i % 7 for i in range(80)],
    }), 0)
    assert out["abstained"]
    assert out["suggestions"] == []
    assert out["blocked_examples"][0]["safe_to_train_automatically"] is False
