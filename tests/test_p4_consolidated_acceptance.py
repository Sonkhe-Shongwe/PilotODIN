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


@pytest.mark.parametrize("field", [
    "TransactionCode", "ClaimNumber", "customer_number", "batch_code",
])
def test_p4_59_high_cardinality_code_number_requires_backend_review_without_fitting(
    field, monkeypatch
):
    """Fail closed before queueing: feature advice and admission must agree."""
    from fastapi import BackgroundTasks, HTTPException
    from backend import analytics, engine

    frame = pd.DataFrame({
        "churn": ["Y", "N"] * 40,
        field: [f"SYNTHETIC-{i:03d}" for i in range(80)],
        "event_type": ["retail", "service"] * 40,
    })
    untouched = frame.copy(deep=True)
    advice = analytics.recommend_features(frame, "churn", 0)
    flagged = {item["column"] for item in advice["features"] if item["risk"] == "high"}
    assert field in flagged

    prepare = engine.preparation(frame, "churn")
    assert field in prepare["high_risk_features"]
    audit = {item["column"]: item for item in prepare["feature_audit"]}
    assert audit[field]["risk"] == "high"
    assert "likely identifier" in audit[field]["reasons"]
    assert audit["event_type"]["risk"] == "low"

    # Replace only lookup functions with synthetic in-memory evidence. An
    # unacknowledged request must be rejected before writing an experiment
    # or invoking any background model fit.
    monkeypatch.setattr(main, "project_or_404", lambda pid: {"id": pid})
    monkeypatch.setattr(main.quality, "current_data", lambda pid: (frame, 0))
    def forbidden_queue(*_args, **_kwargs):
        raise AssertionError("Safety regression: training was admitted or queued")
    monkeypatch.setattr(main.storage, "new_experiment", forbidden_queue)
    monkeypatch.setattr(main.storage, "new_experiment_with_capacity", forbidden_queue)
    request = main.ExperimentRequest(
        target="churn", task="classification",
        models=["logistic_regression"], acknowledge_random_split=True,
        acknowledge_feature_risks=False, expected_quality_version=0,
    )
    with pytest.raises(HTTPException) as blocked:
        main.new_experiment("disposable-synthetic", request, BackgroundTasks())
    assert blocked.value.status_code == 422
    assert "Review high-risk predictors" in str(blocked.value.detail)
    assert field in str(blocked.value.detail)
    assert frame.equals(untouched)


def test_p4_59_low_cardinality_codes_are_not_mistaken_for_unique_identifiers():
    """The structural flag requires near-unique observed values."""
    from backend import analytics, engine

    frame = pd.DataFrame({
        "churn": ["Y", "N"] * 40,
        "TransactionCode": ["A", "B"] * 40,
        "event_type": ["retail", "service"] * 40,
    })
    advice = analytics.recommend_features(frame, "churn", 0)
    a = {item["column"]: item for item in advice["features"]}
    prep = engine.preparation(frame, "churn")
    p = {item["column"]: item for item in prep["feature_audit"]}
    assert a["TransactionCode"]["risk"] == "low"
    assert p["TransactionCode"]["risk"] == "low"
    assert "TransactionCode" not in prep["high_risk_features"]


def test_p4_64_prepare_and_feature_advice_enforce_quality_version_without_training(
    tmp_path, monkeypatch
):
    """Pinned read-only advice fails closed on stale and mid-read revisions."""
    home = tmp_path / "p4-64-versioned-prepare"
    (home / "datasets").mkdir(parents=True)
    (home / "models").mkdir()
    monkeypatch.setattr(storage, "HOME", home)
    monkeypatch.setattr(storage, "DB_PATH", home / "pilotodin.sqlite3")
    storage.init()
    main.quality._init_tables()
    pid = storage.save_project(
        "P4-64 synthetic", "synthetic.csv", ".csv",
        home / "datasets" / "synthetic.csv", {"rows": 80}
    )
    with storage.connect() as con:
        con.execute(
            "INSERT INTO quality_state(project_id,original_sha256,current_version) "
            "VALUES (?,?,?)", (pid, "synthetic-only", 0)
        )
    frame = pd.DataFrame({
        "churn": ["Y", "N"] * 40,
        "TransactionCode": [f"SYNTHETIC-{n:03d}" for n in range(80)],
        "event_type": ["retail", "service"] * 40,
    })
    original = frame.copy(deep=True)
    state = {"version": 0}
    monkeypatch.setattr(main.quality, "current_data",
                        lambda _pid: (frame, state["version"]))
    client = TestClient(main.app)
    base = f"/api/projects/{pid}"
    for path in ("/preparation", "/features"):
        response = client.get(base + path,
                              params={"target": "churn", "expected_version": 0})
        assert response.status_code == 200, response.text
        obj = response.json()
        assert obj["quality_version" if path == "/preparation" else "version"] == 0
        flagged = (
            obj["high_risk_features"] if path == "/preparation" else
            [f["column"] for f in obj["features"] if f["risk"] == "high"]
        )
        assert "TransactionCode" in flagged
        assert client.get(base + path, params={
            "target": "churn", "expected_version": -1
        }).status_code == 422

    # Newer version is committed before the read: old Prepare and feature
    # recommendations must be rejected instead of silently recomputed.
    state["version"] = 1
    with storage.connect() as con:
        con.execute("UPDATE quality_state SET current_version=1 WHERE project_id=?",
                    (pid,))
    for path in ("/preparation", "/features"):
        old = client.get(base + path,
                         params={"target": "churn", "expected_version": 0})
        assert old.status_code == 409
        current = client.get(base + path,
                             params={"target": "churn", "expected_version": 1})
        assert current.status_code == 200, current.text
        assert current.json()["quality_version" if path == "/preparation" else "version"] == 1

    # Simulated interleaving: data loader supplied revision 0, but SQLite's
    # authoritative version is 1 at the post-calculation recheck.
    state["version"] = 0
    for path in ("/preparation", "/features"):
        interleaved = client.get(base + path,
                                 params={"target": "churn", "expected_version": 0})
        assert interleaved.status_code == 409
    assert frame.equals(original)
    assert storage.recent_experiments(pid) == []


def test_prepare_category_examples_are_bounded_and_hide_high_risk_values():
    long_label = "x" * 100
    frame = pd.DataFrame({
        "churn": ["Y", "N"] * 4,
        "event_type": [None, "retail", "retail", long_label, "service", "online", "branch", "other"],
        "TransactionCode": [f"SYNTHETIC-{i}" for i in range(8)],
        "post_outcome": ["done", "pending"] * 4,
        "is_mobile": [True, False] * 4,
        "amount": range(8),
        "empty": pd.Series([None] * 8, dtype="object"),
    })
    original = frame.copy(deep=True)
    plan = main.engine.preparation(frame, "churn")
    audit = {entry["column"]: entry for entry in plan["feature_audit"]}
    assert audit["event_type"]["category_examples"] == ["retail", "x" * 79 + "…", "service", "online", "branch"]
    assert audit["event_type"]["distinct"] == 6
    assert audit["is_mobile"]["category_examples"] == ["True", "False"]
    for column in ("TransactionCode", "post_outcome", "amount", "empty"):
        assert audit[column]["category_examples"] == []
    assert "churn" not in audit
    pd.testing.assert_frame_equal(frame, original)


def test_p4_76_numeric_imputation_allowlist_and_unfitted_pipeline():
    """Inspect actual pipeline configuration; fitting is deliberately prohibited."""
    from pydantic import ValidationError
    from backend import engine

    frame = pd.DataFrame({
        "amount": [1.0, None, 3.0, 8.0],
        "event_type": ["retail", "service", None, "retail"],
    })
    original = frame.copy(deep=True)
    default = main.ExperimentRequest(
        target="churn", task="classification", models=["logistic_regression"]
    )
    assert default.numeric_imputation == "median"
    assert default.categorical_imputation == "most_frequent"
    chosen = main.ExperimentRequest(
        target="churn", task="classification", models=["logistic_regression"],
        numeric_imputation="mean",
    )
    assert chosen.numeric_imputation == "mean"
    marker_choice = main.ExperimentRequest(target="churn", task="classification",
                                           models=["logistic_regression"], categorical_imputation="constant")
    assert marker_choice.categorical_imputation == "constant"
    with pytest.raises(ValidationError):
        main.ExperimentRequest(target="churn", task="classification", models=["logistic_regression"],
                               categorical_imputation="forward_fill")
    with pytest.raises(ValidationError):
        main.ExperimentRequest(
            target="churn", task="classification", models=["logistic_regression"],
            numeric_imputation="forward_fill",
        )
    for strategy in ("median", "mean"):
        pipe = engine.make_pipeline(frame, "classification", "logistic_regression",
                                    numeric_imputation=strategy)
        transforms = pipe.named_steps["preprocessor"].transformers
        numeric = next(steps for name, steps, _columns in transforms
                       if name == "numeric")
        categorical = next(steps for name, steps, _columns in transforms
                           if name == "categorical")
        assert numeric.named_steps["imputer"].strategy == strategy
        assert categorical.named_steps["imputer"].strategy == "most_frequent"
        assert pipe.named_steps["model"].__class__.__name__ == "LogisticRegression"
    for strategy in ("most_frequent", "constant"):
        pipe = engine.make_pipeline(frame, "classification", "logistic_regression",
                                    categorical_imputation=strategy)
        cat = next(steps for name, steps, _columns
                   in pipe.named_steps["preprocessor"].transformers if name == "categorical")
        assert cat.named_steps["imputer"].strategy == strategy
        if strategy == "constant":
            assert cat.named_steps["imputer"].fill_value == engine.CATEGORICAL_MISSING_MARKER
    with pytest.raises(ValueError, match="most_frequent or constant"):
        engine.make_pipeline(frame, "classification", "logistic_regression",
                             categorical_imputation="forward_fill")
    with pytest.raises(ValueError, match="reserved categorical missing marker"):
        collision = frame.copy(deep=True)
        collision.loc[0, "event_type"] = engine.CATEGORICAL_MISSING_MARKER
        engine.make_pipeline(collision, "classification", "logistic_regression",
                             categorical_imputation="constant")
    with pytest.raises(ValueError, match="median or mean"):
        engine.make_pipeline(frame, "classification", "logistic_regression",
                             numeric_imputation="forward_fill")
    assert frame.equals(original)


def test_p4_76_worker_forwards_persisted_strategy_without_fitting(monkeypatch):
    """Worker's config plumbing is exercised entirely with stubs, no storage/fit."""
    frame = pd.DataFrame({"amount": [1.0, None, 2.0],
                          "churn": ["Y", "N", "Y"]})
    captured = {}
    monkeypatch.setattr(main.storage, "claim_queued_experiment", lambda eid: True)
    monkeypatch.setattr(main.storage, "check_training_interruption", lambda eid: None)
    monkeypatch.setattr(main.storage, "get_project", lambda pid: {"id": pid})
    monkeypatch.setattr(main, "df_for", lambda project, version: frame)
    monkeypatch.setattr(main.storage, "advance_running_experiment",
                        lambda *args, **kwargs: True)

    def forbidden_fit(_frame, **kwargs):
        captured.update(kwargs)
        raise RuntimeError("P4-76 deliberate no-fit sentinel")

    def capture_terminal(*args, **kwargs):
        captured["terminal"] = (args, kwargs)
        return True

    monkeypatch.setattr(main.engine, "run_training", forbidden_fit)
    monkeypatch.setattr(main.storage, "finish_running_experiment", capture_terminal)
    base = {
        "target": "churn", "task": "classification", "excluded": [],
        "models": ["logistic_regression"], "quality_version": 0,
        "split_strategy": "random", "split_column": None,
        "numeric_imputation": "mean", "categorical_imputation": "constant",
    }
    main.train_background("synthetic-eid", "synthetic-pid", base)
    assert captured["numeric_imputation"] == "mean"
    assert captured["categorical_imputation"] == "constant"
    assert callable(captured["stop_check"])
    assert captured["terminal"][0][1] == "failed"
    assert "no-fit sentinel" in captured["terminal"][1]["error"]
    assert frame.equals(pd.DataFrame({"amount": [1.0, None, 2.0],
                                      "churn": ["Y", "N", "Y"]}))
