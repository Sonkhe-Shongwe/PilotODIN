"""P4-14 read-only whole recommendation queue resource bounds, synthetic only."""
from __future__ import annotations

import json

import numpy as np
import pandas as pd

from backend import target_opportunities as p4


def test_p4_14_small_dataset_preserves_complete_queue_and_order():
    frame = pd.DataFrame({
        "account_id": [f"TEST-{i // 2}" for i in range(80)],
        "churn": ["Y", "N"] * 40,
        "future_cost": [float(i + 100) for i in range(80)],
        "feature": list(range(80)),
    })
    first = p4.recommend(frame, 0)
    assert first == p4.recommend(frame, 0)
    assert first["queue_resource_review"]["truncated"] is False
    assert first["queue_resource_review"]["rows_examined"] == 80
    assert first["queue_resource_review"]["headers_examined"] == 4
    assert first["eligible_count"] == 2
    assert [x["column"] for x in first["suggestions"]] == [
        "churn", "future_cost",
    ]
    assert all(x["technical_status"] == "reviewable" for x in first["suggestions"])
    assert first["ranking_contract"]["automatic_target_selection"] is False


def test_p4_14_row_limit_abstains_without_full_predictor_scan(monkeypatch):
    rows = p4.MAX_QUEUE_ROWS + 1
    frame = pd.DataFrame({
        "account_id": [f"SYNTH-{i // 2}" for i in range(rows)],
        "churn": ["Y", "N"] * (rows // 2) + ["Y"],
        "feature": np.arange(rows),
    })
    original = frame["churn"].copy(deep=True)
    inspected = []
    actual = p4._candidate

    def spy(sample, *args, **kwargs):
        inspected.append(sample.shape)
        return actual(sample, *args, **kwargs)

    monkeypatch.setattr(p4, "_candidate", spy)
    out = p4.recommend(frame, 1)
    assert inspected == [(5000, 3)]
    assert out["abstained"] is True
    assert out["suggestions"] == []
    assert out["eligible_count"] == 0
    assert out["queue_resource_review"]["incomplete_reasons"] == ["rows"]
    assert out["queue_resource_review"]["rows_examined"] == 5000
    assert out["queue_resource_review"]["total_rows"] == rows
    assert out["blocked_examples"][0]["technical_status"] == "blocked"
    assert "truncated" in " ".join(out["blocked_examples"][0]["blockers"])
    assert out["blocked_examples"][0]["safe_to_train_automatically"] is False
    assert "SYNTH-0" not in json.dumps(out)
    assert frame["churn"].equals(original)


def test_p4_14_large_header_candidate_list_never_full_scans(monkeypatch):
    frame = pd.DataFrame({
        "account_id": [f"SYNTH-{i // 2}" for i in range(80)],
        **{f"outcome_{i:03d}": ["Y", "N"] * 40 for i in range(120)},
        "feature_late": np.arange(80),
    })
    seen = []
    real = p4._candidate

    def spy(sample, *args, **kwargs):
        seen.append((sample.shape, args[0]))
        return real(sample, *args, **kwargs)

    monkeypatch.setattr(p4, "_candidate", spy)
    out = p4.recommend(frame, 2)
    resource = out["queue_resource_review"]
    assert resource["truncated"] is True
    assert set(resource["incomplete_reasons"]) == {
        "headers", "predictors", "candidate_columns",
    }
    assert resource["headers_examined"] == 100
    assert resource["total_headers"] == 122
    assert resource["candidate_columns_examined"] == 5
    assert resource["named_outcome_headers_seen"] == 99
    assert len(seen) == 5
    assert all(shape == (80, 65) for shape, _ in seen)
    assert all(col.startswith("outcome_") for _, col in seen)
    assert out["suggestions"] == []
    assert out["other_reviewable"] == []
    assert out["blocked_count"] == 5
    assert all(x["technical_status"] == "blocked" for x in out["blocked_examples"])
    assert "SYNTH-0" not in json.dumps(out)
    assert out["ranking_contract"]["automatic_target_selection"] is False


def test_p4_14_target_after_header_cap_is_not_reported_as_no_target():
    frame = pd.DataFrame({
        **{f"feature_{i:03d}": [i] * 80 for i in range(105)},
        "churn": ["Y", "N"] * 40,
    })
    out = p4.recommend(frame, 0)
    assert out["abstained"] is True
    assert "Incomplete target screening" in out["abstention_reason"]
    assert out["queue_resource_review"]["truncated"] is True
    assert "headers" in out["queue_resource_review"]["incomplete_reasons"]
    assert out["blocked_examples"] == []
    assert out["queue_resource_review"]["candidate_columns_examined"] == 0
    assert out["ranking_contract"]["automatic_target_selection"] is False


def test_p4_14_predictor_cap_abstains_even_with_one_named_candidate():
    frame = pd.DataFrame({
        "churn": ["Y", "N"] * 40,
        **{f"feature_{i:03d}": np.arange(80) + i for i in range(65)},
    })
    out = p4.recommend(frame, 0)
    evidence = out["queue_resource_review"]
    assert "predictors" in evidence["incomplete_reasons"]
    assert evidence["headers_examined"] == 66
    assert evidence["truncated"] is True
    assert out["suggestions"] == []
    assert out["blocked_examples"][0]["column"] == "churn"
    assert out["blocked_examples"][0]["technical_status"] == "blocked"
    assert out["blocked_examples"][0]["task_hypothesis"] is None


def test_p4_14_over_ml_cap_preserves_caution_without_fake_full_label_count():
    rows = p4.engine.MAX_ML_LABELLED_ROWS + 1
    frame = pd.DataFrame({
        "churn": ["Y", "N"] * (rows // 2) + ["Y"],
        "feature": np.arange(rows),
    })
    out = p4.recommend(frame, 0)
    assert out["abstained"] is True
    assert "local ML cap" in " ".join(out["blocked_examples"][0]["blockers"])
    assert out["queue_resource_review"]["rows_examined"] == 5000
    assert out["queue_resource_review"]["total_rows"] == rows
