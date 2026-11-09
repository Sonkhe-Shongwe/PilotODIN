"""P4-05: human review queue, transparent evidence needs and lower-list alternatives.

The only persisted target context is an explicit separately consented owner note.
These tests never fit models, select targets or access real projects.
"""
from __future__ import annotations

import json

import pandas as pd

from backend import target_opportunities


def make_frame(n: int = 80) -> pd.DataFrame:
    return pd.DataFrame({
        "order_id": [f"private-order-{i}" for i in range(n)],
        "churn": ["Y", "N"] * (n // 2),
        "fraud_reported": ["Y", "N"] * (n // 2),
        "failure_flag": ["Y", "N"] * (n // 2),
        "outcome": ["Y", "N"] * (n // 2),
        "future_cost": [float(i + 100) for i in range(n)],
        "feature": [i % 7 for i in range(n)],
    })


def context(column: str) -> dict:
    return {
        "target_column": column,
        "outcome_definition": "An owner-described target outcome, not independently verified.",
        "decision_action": "Owner might consider a downstream review decision.",
        "prediction_moment": "Before the outcome is recorded in the system.",
        "label_source": "Owner-described internal operational log, unverified.",
        "updated_at": "2026-11-09T00:00:00Z",
    }


def test_review_order_is_explained_but_business_value_is_not_claimed():
    frame = make_frame()
    original = frame.copy(deep=True)
    result = target_opportunities.recommend(frame, 4, {
        "fraud_reported": context("fraud_reported")
    })
    assert frame.equals(original)
    assert result["ranking_contract"] == {
        "purpose": "human_review_queue_not_business_value_ranking",
        "ordered_by": [
            "whether_owner_described_decision",
            "observed_nonmissing_label_count",
            "deterministic_column_name",
        ],
        "business_value_verified": False,
        "model_performance_measured": False,
        "automatic_target_selection": False,
    }
    first = result["suggestions"][0]
    assert first["column"] == "fraud_reported"
    assert first["review_priority"]["position"] == 1
    assert first["review_priority"]["total_reviewable"] == result["eligible_count"]
    assert first["review_priority"]["group"] == "described_question_first"
    assert first["review_priority"]["business_value"] == "not_established"
    assert first["review_priority"]["target_safety"] == "not_established"
    assert first["review_priority"]["training_authorised"] is False
    assert result["suggestions"][0]["safe_to_train_automatically"] is False
    assert "No model trained" in result["ranking_basis"]
    assert "private-order-0" not in json.dumps(result)
    assert result == target_opportunities.recommend(frame, 4, {
        "fraud_reported": context("fraud_reported")
    })


def test_missing_decision_is_an_explicit_review_step_not_a_low_value_verdict():
    result = target_opportunities.recommend(make_frame(), 0)
    for item in result["suggestions"] + result["other_reviewable"]:
        priority = item["review_priority"]
        assert priority["position"] >= 1
        assert priority["group"] == "decision_not_described"
        assert "NOT evidence of lower business value" in priority["ordering_reason"]
        tasks = {part["topic"]: part for part in priority["required_checks"]}
        assert tasks["decision"]["state"] == "not_documented"
        assert tasks["label_provenance"]["state"] == "not_independently_verified"
        assert tasks["prediction_time"]["state"] == "not_independently_verified"
        assert tasks["validation"]["state"] == "not_independently_verified"
        assert priority["training_authorised"] is False


def test_missing_labels_and_unverified_header_clues_are_visible_without_unsafe_claims():
    df = make_frame()
    df.loc[:9, "churn"] = None
    df["post_outcome_notes"] = ["internal"] * len(df)
    result = target_opportunities.recommend(df, 1, {"churn": context("churn")})
    item = next(x for x in result["suggestions"] if x["column"] == "churn")
    tasks = {part["topic"]: part for part in item["review_priority"]["required_checks"]}
    assert "missing_labels" in tasks
    assert "possible_leakage_or_provenance" in tasks
    assert item["review_priority"]["business_value"] == "not_established"
    assert item["risk_review"]["header_flags"]
    assert item["safe_to_train_automatically"] is False


def test_additional_options_visible_without_selection_or_training():
    result = target_opportunities.recommend(make_frame(), 3)
    assert result["eligible_count"] == 5
    assert len(result["suggestions"]) == 3
    assert len(result["other_reviewable"]) == 2
    assert result["omitted_reviewable_count"] == 0
    assert [
        x["review_priority"]["position"]
        for x in result["suggestions"] + result["other_reviewable"]
    ] == [1, 2, 3, 4, 5]
    assert all(x["technical_status"] == "reviewable"
               for x in result["other_reviewable"])
    assert all(x["safe_to_train_automatically"] is False
               for x in result["other_reviewable"])


def test_large_eligible_set_is_bounded_and_manual_dropdown_remains_the_fallback():
    frame = pd.DataFrame({
        f"outcome_{j:02d}": ["Y", "N"] * 40
        for j in range(22)
    })
    result = target_opportunities.recommend(frame, 0)
    assert result["eligible_count"] == 22
    assert len(result["suggestions"]) == 3
    assert len(result["other_reviewable"]) == target_opportunities.MAX_OTHER_REVIEWABLE
    assert result["omitted_reviewable_count"] == 7
    assert all(x["review_priority"]["training_authorised"] is False
               for x in result["other_reviewable"])


def test_all_blocked_or_no_named_outcomes_abstain_without_queue_or_approval():
    unrelated = pd.DataFrame({
        "record_id": list(range(80)),
        "sensor_value": list(range(80)),
    })
    for frame in (unrelated, pd.DataFrame({
        "target": ["Y"] * 80,
        "feature": list(range(80)),
    })):
        result = target_opportunities.recommend(frame, 0)
        assert result["abstained"] is True
        assert result["suggestions"] == []
        assert result["other_reviewable"] == []
        assert result["omitted_reviewable_count"] == 0
        assert result["ranking_contract"]["automatic_target_selection"] is False
