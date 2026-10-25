"""P4 prediction-time cues are conservative, deterministic and read-only."""
from __future__ import annotations

import pandas as pd
from backend import target_timing_review, target_opportunities


def _context(moment="Before renewal outcome is known", source="Verified churn records supplied by operations"):
    return {
        "outcome_definition": "Customer renewal outcome",
        "decision_action": "Prioritize retention assistance",
        "prediction_moment": moment,
        "label_source": source,
    }


def test_missing_context_never_becomes_a_safety_clearance():
    review = target_timing_review.review_prediction_context(["churn","visits"],"churn",None)
    assert review["status"] == "context_missing"
    assert review["timing_cue"] == "not_determined"
    assert review["label_cue"] == "not_determined"
    assert review["safe_to_train_automatically"] is False
    assert len(review["questions"]) >= 3


def test_before_event_statement_cannot_verify_temporal_safety():
    review = target_timing_review.review_prediction_context(["churn","visits"],"churn",_context())
    assert review["status"] == "needs_human_review"
    assert review["timing_cue"] == "not_determined"
    assert "not clearance" in review["note"].lower()
    assert review["safe_to_train_automatically"] is False


def test_after_event_cue_is_tentative_and_does_not_block_or_authorize_training():
    ctx = _context("After the case is closed and the outcome is known")
    review = target_timing_review.review_prediction_context(["churn","visits"],"churn",ctx)
    assert review["timing_cue"] == "possible_after_event_wording"
    assert review["verification"] == "unverified_user_text_and_header_clues"
    assert review["safe_to_train_automatically"] is False


def test_reported_labels_and_unclear_origin_raise_questions_not_factual_conclusions():
    reported=target_timing_review.review_prediction_context(["fraud_reported"],"fraud_reported",
        _context(source="Reported suspected cases, not confirmed fraud"))
    unclear=target_timing_review.review_prediction_context(["churn"],"churn",
        _context(source="Unknown source not documented"))
    assert reported["label_cue"] == "possibly_unconfirmed_or_proxy"
    assert unclear["label_cue"] == "source_unclear"
    assert reported["safe_to_train_automatically"] is False


def test_header_only_flags_are_bounded_and_exclude_the_target():
    columns=["fraud_reported"]+[f"final_outcome_{i}" for i in range(7)]+["customer_id"]
    out=target_timing_review.review_prediction_context(columns,"fraud_reported",_context())
    assert len(out["header_flags"]) == 5
    assert out["header_review_incomplete"] is True
    assert all(flag["basis"]=="header_name_only" for flag in out["header_flags"])
    assert all(flag["column"]!="fraud_reported" for flag in out["header_flags"])


def test_existing_target_screening_not_changed_by_new_review():
    frame=pd.DataFrame({
        "fraud_reported":["Y","N"]*40,
        "final_decision":["yes","no"]*40,
        "event_count":list(range(80)),
    })
    plain=target_opportunities.recommend(frame,2)
    described=target_opportunities.recommend(frame,2,{
        "fraud_reported":_context(source="Historical reported cases (not court confirmed)")
    })
    first=plain["suggestions"][0]
    second=described["suggestions"][0]
    assert first["technical_status"]==second["technical_status"]=="reviewable"
    assert first["safe_to_train_automatically"] is second["safe_to_train_automatically"] is False
    assert second["risk_review"]["label_cue"]=="possibly_unconfirmed_or_proxy"
    assert second["risk_review"]["header_flags"][0]["column"]=="final_decision"
    assert "risk_review" in first
    assert frame.equals(frame.copy())
    assert described==target_opportunities.recommend(frame,2,{
        "fraud_reported":_context(source="Historical reported cases (not court confirmed)")
    })


def test_ambiguous_dataset_still_abstains_regardless_of_context():
    frame=pd.DataFrame({"unknown":[1,2]*25,"feature":[1,2]*25})
    response=target_opportunities.recommend(frame,1,{
        "unknown":_context()
    })
    assert response["abstained"]
    assert response["suggestions"]==[]
