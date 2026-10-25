"""P4 two-axis review is descriptive evidence, not target authorization."""
from __future__ import annotations

import pandas as pd
from backend import target_opportunities


def _frame():
    return pd.DataFrame({
        "churn": ["Y", "N"] * 40,
        "fraud_reported": ["Y", "N"] * 40,
        "visits": list(range(80)),
    })


def _user_context():
    return {
        "outcome_definition": "A retrospective historical cancellation label",
        "decision_action": "Evaluate retention assistance for renewal customers",
        "prediction_moment": "Before the renewal outcome is known",
        "label_source": "Reported outcomes entered by case staff, not independently verified",
    }


def test_technical_and_decision_axes_are_independent_when_business_context_missing():
    response = target_opportunities.recommend(_frame(), 4)
    candidate = next(x for x in response["suggestions"] if x["column"] == "churn")
    axes = candidate["assessment_axes"]
    assert axes["technical"]["state"] == "structurally_reviewable"
    assert axes["decision"]["state"] == "undocumented"
    assert axes["technical"]["labelled_rows"] == 80
    assert axes["technical"]["distinct_labels"] == 2
    assert axes["review_required"] is True
    assert axes["safe_to_train_automatically"] is False
    assert "model performance" in axes["technical"]["limitations"]


def test_user_description_does_not_verify_decision_or_make_training_safe():
    response = target_opportunities.recommend(_frame(), 4, {"churn": _user_context()})
    candidate = next(x for x in response["suggestions"] if x["column"] == "churn")
    assert candidate["assessment_axes"]["technical"]["state"] == "structurally_reviewable"
    assert candidate["assessment_axes"]["decision"]["state"] == "user_described_unverified"
    assert candidate["assessment_axes"]["decision"]["basis"] == "user_description_only"
    assert "not been independently verified" in candidate["assessment_axes"]["decision"]["limitations"]
    assert candidate["assessment_axes"]["safe_to_train_automatically"] is False
    assert candidate["safe_to_train_automatically"] is False
    assert candidate["business_relevance"] == "user_described_unverified"


def test_blocked_rare_label_remains_blocked_even_with_user_description():
    frame = _frame()
    frame["fraud_reported"] = ["Y"] * 75 + ["N"] * 5
    response = target_opportunities.recommend(frame, 4, {"fraud_reported": _user_context()})
    blocked = next(x for x in response["blocked_examples"] if x["column"] == "fraud_reported")
    axes = blocked["assessment_axes"]
    assert axes["technical"]["state"] == "structurally_blocked"
    assert axes["decision"]["state"] == "user_described_unverified"
    assert blocked["technical_status"] == "blocked"
    assert axes["safe_to_train_automatically"] is False


def test_reported_fraud_source_does_not_become_verified_by_context():
    response = target_opportunities.recommend(_frame(), 4, {"fraud_reported": _user_context()})
    candidate = next(x for x in response["suggestions"] if x["column"] == "fraud_reported")
    assert candidate["risk_review"]["label_cue"] == "possibly_unconfirmed_or_proxy"
    assert candidate["assessment_axes"]["decision"]["state"] == "user_described_unverified"
    assert candidate["assessment_axes"]["review_required"] is True


def test_no_named_outcome_still_abstains_despite_user_context():
    frame = pd.DataFrame({"colour": ["red", "blue"] * 40, "visits": list(range(80))})
    response = target_opportunities.recommend(frame, 1, {"colour": _user_context()})
    assert response["abstained"] is True
    assert response["suggestions"] == []


def test_evidence_axes_deterministic_and_no_personal_rows_exposed():
    frame = pd.DataFrame({
        "churn": ["Y", "N"] * 40,
        "account_id": [f"private-id-{i}" for i in range(80)],
        "visits": list(range(80)),
    })
    one = target_opportunities.recommend(frame, 2)
    two = target_opportunities.recommend(frame, 2)
    assert one == two
    out = str(one)
    assert "private-id-" not in out
    assert "Y'" not in out
    assert "fit" not in one["ranking_basis"].casefold()
    assert one["suggestions"][0]["assessment_axes"]["safe_to_train_automatically"] is False


def test_two_axis_metadata_does_not_change_bounded_sorting():
    frame = _frame()
    plain = target_opportunities.recommend(frame, 3)
    described = target_opportunities.recommend(frame, 3, {"churn": _user_context()})
    assert len(plain["suggestions"]) <= target_opportunities.MAX_SUGGESTIONS
    assert described["suggestions"][0]["column"] == "churn"
    assert [c["column"] for c in plain["suggestions"]] == [
        c["column"] for c in target_opportunities.recommend(frame, 3)["suggestions"]
    ]
    assert all(c["assessment_axes"]["review_required"] for c in described["suggestions"])
