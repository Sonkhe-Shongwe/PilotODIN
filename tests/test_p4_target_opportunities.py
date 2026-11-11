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
    main.quality._init_tables()
    pid=storage.save_project("Synthetic","data.csv",".csv",home/"datasets"/"data.csv",{"rows":80})
    with storage.connect() as con:
        con.execute(
            "INSERT INTO quality_state(project_id,original_sha256,current_version) "
            "VALUES (?,?,?)", (pid, "synthetic-only", 4)
        )
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


def test_nonfinite_two_class_numeric_target_is_blocked_not_a_classification():
    # pandas counts infinities as labelled and sees two distinct classes.
    # The previous task inference accepted +inf/-inf as a well-supported
    # classification target even though they cannot be trusted outcomes.
    frame = pd.DataFrame({
        "churn": [float("inf")] * 40 + [float("-inf")] * 40,
        "feature": [i % 8 for i in range(80)],
    })
    original = frame.copy(deep=True)
    review = target_opportunities.recommend(frame, 0)
    assert review["abstained"] is True
    assert review["suggestions"] == []
    assert review["eligible_count"] == 0
    blocked = {x["column"]: x for x in review["blocked_examples"]}["churn"]
    assert blocked["labelled_rows"] == 80  # observed, but unusable
    assert blocked["distinct_labels"] == 2
    assert blocked["technical_status"] == "blocked"
    assert blocked["task_hypothesis"] is None
    assert blocked["safe_to_train_automatically"] is False
    assert any("finite" in message.lower() for message in blocked["blockers"])
    assert frame.equals(original)


def test_nonfinite_numeric_target_also_blocked_in_explicit_manual_inspection():
    frame = pd.DataFrame({
        "churn": [1.0] * 40 + [float("inf")] * 40,
        "feature": [i % 8 for i in range(80)],
    })
    result = target_opportunities.inspect_manual_target(frame, 2, "churn")
    candidate = result["candidate"]
    assert result["training_authorised"] is False
    assert candidate["technical_status"] == "blocked"
    assert candidate["task_hypothesis"] is None
    assert any("finite" in message.lower() for message in candidate["blockers"])
    assert candidate["decision_utility"]["training_authorised"] is False


def test_finite_binary_numeric_target_remains_structurally_reviewable():
    frame = pd.DataFrame({
        "outcome": [0.0, 1.0] * 40,
        "feature": [i % 8 for i in range(80)],
    })
    review = target_opportunities.recommend(frame, 3)
    assert not review["abstained"]
    candidate = review["suggestions"][0]
    assert candidate["column"] == "outcome"
    assert candidate["task_hypothesis"] == "classification"
    assert candidate["technical_status"] == "reviewable"
    assert candidate["safe_to_train_automatically"] is False


@pytest.mark.parametrize("header", [
    "outcome_created_at", "churn_updated_at", "fraud_reported_at",
])
def test_timestamp_named_outcome_string_values_are_blocked(header):
    # Two distinct ISO timestamp strings were previously inferred as two
    # classification labels because created_at/updated_at got split on '_'.
    frame = pd.DataFrame({
        header: ["2026-01-01T00:00:00", "2026-01-02T00:00:00"] * 40,
        "feature": [i % 9 for i in range(80)],
    })
    original = frame.copy(deep=True)
    result = target_opportunities.recommend(frame, 0)
    assert result["abstained"] is True
    assert result["suggestions"] == []
    candidate = {item["column"]: item for item in result["blocked_examples"]}[header]
    assert candidate["technical_status"] == "blocked"
    assert candidate["labelled_rows"] == 80
    assert candidate["distinct_labels"] == 2
    assert candidate["task_hypothesis"] is None
    assert candidate["safe_to_train_automatically"] is False
    assert any("date/time" in x for x in candidate["blockers"])
    assert frame.equals(original)


def test_timestamp_named_manual_target_is_not_approved():
    frame = pd.DataFrame({
        "outcome_created_at": ["2026-01-01", "2026-01-02"] * 40,
        "feature": [i % 7 for i in range(80)],
    })
    result = target_opportunities.inspect_manual_target(frame, 2, "outcome_created_at")
    candidate = result["candidate"]
    assert candidate["technical_status"] == "blocked"
    assert candidate["task_hypothesis"] is None
    assert candidate["decision_utility"]["training_authorised"] is False
    assert result["training_authorised"] is False
    assert any("date/time" in x for x in candidate["blockers"])


def test_valid_numeric_future_cost_target_preserved_after_timestamp_guard():
    frame = pd.DataFrame({
        "future_cost": [float(i + 110) for i in range(80)],
        "feature": [i % 8 for i in range(80)],
    })
    result = target_opportunities.recommend(frame, 1)
    assert not result["abstained"]
    candidate = result["suggestions"][0]
    assert candidate["column"] == "future_cost"
    assert candidate["task_hypothesis"] == "regression"
    assert candidate["technical_status"] == "reviewable"
    assert candidate["safe_to_train_automatically"] is False



@pytest.mark.parametrize("case", ["unlabelled_only", "constant_when_labelled"])
def test_predictors_varying_only_outside_labelled_records_are_blocked(case):
    # Forty labels satisfy the label and minority-class thresholds, but a
    # globally varying feature is unusable for labelled supervised examples.
    labelled = ["Y", "N"] * 20
    if case == "unlabelled_only":
        feature = [None] * 40 + [i % 7 for i in range(40)]
    else:
        feature = [1] * 40 + [i % 7 for i in range(40)]
    frame = pd.DataFrame({
        "churn": labelled + [None] * 40,
        "feature": feature,
    })
    before = frame.copy(deep=True)
    assert frame["feature"].nunique(dropna=True) > 1
    assert frame.loc[frame["churn"].notna(), "feature"].nunique(dropna=True) <= 1

    queue = target_opportunities.recommend(frame, 4)
    assert queue["abstained"] is True
    assert queue["suggestions"] == []
    candidate = {item["column"]: item for item in queue["blocked_examples"]}["churn"]
    assert candidate["labelled_rows"] == 40
    assert candidate["missing_labels"] == 40
    assert candidate["technical_status"] == "blocked"
    assert candidate["task_hypothesis"] is None
    assert any("No non-constant, non-empty candidate predictor" in b
               for b in candidate["blockers"])
    assert candidate["safe_to_train_automatically"] is False
    assert frame.equals(before)


def test_manual_inspection_blocks_unlabelled_only_predictor_variation():
    frame = pd.DataFrame({
        "churn": ["Y", "N"] * 20 + [None] * 40,
        "feature": [None] * 40 + [i % 9 for i in range(40)],
    })
    before = frame.copy(deep=True)
    inspected = target_opportunities.inspect_manual_target(frame, 2, "churn")
    candidate = inspected["candidate"]
    assert inspected["training_authorised"] is False
    assert candidate["technical_status"] == "blocked"
    assert candidate["task_hypothesis"] is None
    assert candidate["decision_utility"]["training_authorised"] is False
    assert any("No non-constant, non-empty candidate predictor" in b
               for b in candidate["blockers"])
    assert frame.equals(before)


def test_partly_missing_labels_with_varying_labelled_predictor_stay_reviewable():
    # Missing target labels do not alone invalidate a supervised hypothesis.
    # Variability within the labelled subset remains enough for P4 screening.
    frame = pd.DataFrame({
        "churn": ["Y", "N"] * 20 + [None] * 40,
        "feature": [i % 7 for i in range(40)] + [None] * 40,
    })
    review = target_opportunities.recommend(frame, 0)
    assert review["abstained"] is False
    candidate = review["suggestions"][0]
    assert candidate["column"] == "churn"
    assert candidate["labelled_rows"] == 40
    assert candidate["missing_labels"] == 40
    assert candidate["technical_status"] == "reviewable"
    assert candidate["task_hypothesis"] == "classification"
    assert any("missing" in w.lower() for w in candidate["review_warnings"])
    assert candidate["safe_to_train_automatically"] is False


@pytest.mark.parametrize("blank_text", ["", " ", "\t", " \t "])
def test_p4_blank_text_outcomes_are_not_counted_as_real_labels(blank_text):
    # Previously, forty whitespace-only strings could masquerade as
    # forty valid members of a second target class.
    frame = pd.DataFrame({
        "churn": ["Y"] * 40 + [blank_text] * 40,
        "feature": list(range(80)),
    })
    original = frame.copy(deep=True)
    result = target_opportunities.recommend(frame, 3)
    assert result["abstained"] is True
    assert result["suggestions"] == []
    candidate = {x["column"]: x for x in result["blocked_examples"]}["churn"]
    assert candidate["labelled_rows"] == 40
    assert candidate["missing_labels"] == 40
    assert candidate["distinct_labels"] == 1
    assert candidate["technical_status"] == "blocked"
    assert candidate["task_hypothesis"] is None
    assert candidate["safe_to_train_automatically"] is False
    assert any("Blank or whitespace-only" in x for x in candidate["blockers"])
    manual = target_opportunities.inspect_manual_target(frame, 3, "churn")
    assert manual["candidate"]["technical_status"] == "blocked"
    assert manual["candidate"]["labelled_rows"] == 40
    assert manual["training_authorised"] is False
    assert frame.equals(original)


def test_p4_one_whitespace_label_does_not_silently_make_reviewable_target():
    frame = pd.DataFrame({
        "churn": ["Y", "N"] * 40 + [" \t "],
        "feature": list(range(81)),
    })
    result = target_opportunities.recommend(frame, 0)
    assert result["abstained"]
    candidate = {x["column"]: x for x in result["blocked_examples"]}["churn"]
    assert candidate["labelled_rows"] == 80
    assert candidate["missing_labels"] == 1
    assert candidate["distinct_labels"] == 2
    assert candidate["technical_status"] == "blocked"
    assert candidate["task_hypothesis"] is None
    assert any("Blank or whitespace-only" in x for x in candidate["blockers"])
    # Original text labels remain untouched, not silently trimmed or imputed.
    assert frame.loc[80, "churn"] == " \t "


@pytest.mark.parametrize("predictor", [
    [" ", "\t"] * 40,
    ["", " "] * 40,
    ["only-one", " "] * 40,
])
def test_p4_blank_only_or_constant_nonblank_predictor_cannot_support_target(predictor):
    # Raw two-string values are not evidence of a usable predictor when
    # some or all values are only whitespace.
    frame = pd.DataFrame({
        "churn": ["Y", "N"] * 40,
        "feature": predictor,
    })
    before = frame.copy(deep=True)
    assert frame["feature"].nunique(dropna=True) == 2
    queue = target_opportunities.recommend(frame, 0)
    assert queue["abstained"] is True
    assert queue["suggestions"] == []
    candidate = {item["column"]: item for item in queue["blocked_examples"]}["churn"]
    assert candidate["labelled_rows"] == 80
    assert candidate["technical_status"] == "blocked"
    assert candidate["task_hypothesis"] is None
    assert candidate["safe_to_train_automatically"] is False
    assert any("No non-constant, non-empty candidate predictor" in blocker
               for blocker in candidate["blockers"])
    manual = target_opportunities.inspect_manual_target(frame, 0, "churn")
    assert manual["candidate"]["technical_status"] == "blocked"
    assert manual["training_authorised"] is False
    assert frame.equals(before)


def test_p4_two_real_predictor_categories_with_blank_values_stay_reviewable():
    # Missing text values are ignored for predictor-variation screening, not
    # silently rewritten. Two genuine categories still support structural review.
    frame = pd.DataFrame({
        "churn": ["Y", "N"] * 40,
        "feature": ["first", "second", " "] * 26 + ["first", "second"],
    })
    before = frame.copy(deep=True)
    candidate = target_opportunities.recommend(frame, 0)["suggestions"][0]
    assert candidate["column"] == "churn"
    assert candidate["technical_status"] == "reviewable"
    assert candidate["safe_to_train_automatically"] is False
    assert frame.equals(before)


@pytest.mark.parametrize("padded_label", ["Y ", " Y", "\tY", "Y\n", "  Y  "])
def test_p4_padded_target_label_cannot_be_a_false_second_class(padded_label):
    # Before the guard, 40 plain "Y" and 40 padded "Y" were considered two
    # well-supported classification classes. The temporary review excludes
    # malformed strings without silently trimming or modifying Quality data.
    frame = pd.DataFrame({
        "churn": ["Y"] * 40 + [padded_label] * 40,
        "feature": list(range(80)),
    })
    before = frame.copy(deep=True)
    result = target_opportunities.recommend(frame, 3)
    assert result["abstained"] is True
    assert result["suggestions"] == []
    candidate = {x["column"]: x for x in result["blocked_examples"]}["churn"]
    assert candidate["labelled_rows"] == 40
    assert candidate["missing_labels"] == 40
    assert candidate["distinct_labels"] == 1
    assert candidate["technical_status"] == "blocked"
    assert candidate["task_hypothesis"] is None
    assert candidate["safe_to_train_automatically"] is False
    assert any("Leading or trailing whitespace" in x for x in candidate["blockers"])
    manual = target_opportunities.inspect_manual_target(frame, 3, "churn")
    assert manual["candidate"]["technical_status"] == "blocked"
    assert manual["candidate"]["labelled_rows"] == 40
    assert manual["training_authorised"] is False
    assert frame.equals(before)


def test_p4_single_padded_label_blocks_otherwise_valid_target_without_imputation():
    frame = pd.DataFrame({
        "churn": ["Y", "N"] * 40 + [" N "],
        "feature": list(range(81)),
    })
    snapshot = frame.copy(deep=True)
    result = target_opportunities.recommend(frame, 6)
    candidate = {x["column"]: x for x in result["blocked_examples"]}["churn"]
    assert result["abstained"] is True
    assert candidate["labelled_rows"] == 80
    assert candidate["missing_labels"] == 1
    assert candidate["distinct_labels"] == 2
    assert candidate["technical_status"] == "blocked"
    assert candidate["task_hypothesis"] is None
    assert any("Leading or trailing whitespace" in x for x in candidate["blockers"])
    assert frame.equals(snapshot)


def test_p4_internal_spaces_in_real_text_outcomes_remain_valid_for_review():
    frame = pd.DataFrame({
        "churn": ["in progress", "not resolved"] * 40,
        "feature": list(range(80)),
    })
    before = frame.copy(deep=True)
    result = target_opportunities.recommend(frame, 0)
    candidate = {x["column"]: x for x in result["suggestions"]}["churn"]
    assert candidate["technical_status"] == "reviewable"
    assert candidate["task_hypothesis"] == "classification"
    assert candidate["labelled_rows"] == 80
    assert candidate["missing_labels"] == 0
    assert candidate["distinct_labels"] == 2
    assert candidate["safe_to_train_automatically"] is False
    assert target_opportunities.inspect_manual_target(frame, 0, "churn")["training_authorised"] is False
    assert frame.equals(before)


@pytest.mark.parametrize("predictor", [
    [float("inf"), float("-inf")] * 40,
    [2.0, float("inf")] * 40,
    [2.0, float("-inf")] * 40,
])
def test_p4_nonfinite_numeric_predictor_does_not_establish_usable_variation(predictor):
    # Pandas treats infinities as nonmissing, distinct values, but no finite
    # two-value predictor remains after screening. Training remains forbidden.
    frame = pd.DataFrame({"churn": ["Y", "N"] * 40, "signal": predictor})
    original = frame.copy(deep=True)
    assert frame["signal"].nunique(dropna=True) == 2
    result = target_opportunities.recommend(frame, 0)
    assert result["abstained"] is True
    assert result["suggestions"] == []
    candidate = {x["column"]: x for x in result["blocked_examples"]}["churn"]
    assert candidate["labelled_rows"] == 80
    assert candidate["technical_status"] == "blocked"
    assert candidate["task_hypothesis"] is None
    assert any("No non-constant, non-empty candidate predictor" in x
               for x in candidate["blockers"])
    assert candidate["safe_to_train_automatically"] is False
    manual = target_opportunities.inspect_manual_target(frame, 0, "churn")
    assert manual["candidate"]["technical_status"] == "blocked"
    assert manual["training_authorised"] is False
    assert frame.equals(original)


def test_p4_two_finite_numeric_predictor_values_still_support_structural_review():
    frame = pd.DataFrame({
        "churn": ["Y", "N"] * 40,
        "signal": [0.0, 1.0, float("inf"), float("-inf")] * 20,
    })
    original = frame.copy(deep=True)
    result = target_opportunities.recommend(frame, 0)
    candidate = {x["column"]: x for x in result["suggestions"]}["churn"]
    assert candidate["technical_status"] == "reviewable"
    assert candidate["task_hypothesis"] == "classification"
    assert candidate["safe_to_train_automatically"] is False
    manual = target_opportunities.inspect_manual_target(frame, 0, "churn")
    assert manual["candidate"]["technical_status"] == "reviewable"
    assert manual["training_authorised"] is False
    assert frame.equals(original)


def test_p4_missing_numeric_predictor_values_remain_not_usable():
    frame = pd.DataFrame({
        "churn": ["Y", "N"] * 40,
        "signal": [float("nan"), float("inf"), float("-inf"), 4.0] * 20,
    })
    original = frame.copy(deep=True)
    result = target_opportunities.recommend(frame, 0)
    assert result["abstained"] is True
    candidate = {x["column"]: x for x in result["blocked_examples"]}["churn"]
    assert candidate["technical_status"] == "blocked"
    assert candidate["safe_to_train_automatically"] is False
    assert frame.equals(original)


@pytest.mark.parametrize("predictor", [
    ["Gold", "Gold "] * 40,
    ["Gold", " Gold"] * 40,
    ["Gold", "\tGold"] * 40,
    ["Gold ", " Gold"] * 40,
])
def test_p4_padded_text_predictor_does_not_create_spurious_variation(predictor):
    # Padding is not a second usable predictor category. No data are trimmed
    # or written, and both shortlist and explicit manual review must abstain.
    frame = pd.DataFrame({"churn": ["Y", "N"] * 40, "feature": predictor})
    before = frame.copy(deep=True)
    assert frame["feature"].nunique(dropna=True) == 2
    review = target_opportunities.recommend(frame, 0)
    assert review["abstained"] is True
    assert review["suggestions"] == []
    candidate = {item["column"]: item for item in review["blocked_examples"]}["churn"]
    assert candidate["labelled_rows"] == 80
    assert candidate["technical_status"] == "blocked"
    assert candidate["task_hypothesis"] is None
    assert candidate["safe_to_train_automatically"] is False
    assert any("No non-constant, non-empty candidate predictor" in blocker
               for blocker in candidate["blockers"])
    manual = target_opportunities.inspect_manual_target(frame, 0, "churn")
    assert manual["candidate"]["technical_status"] == "blocked"
    assert manual["training_authorised"] is False
    assert frame.equals(before)


def test_p4_real_text_predictor_variation_survives_padding_and_internal_spaces():
    # Two genuine categories remain enough for STRUCTURAL review only.
    # Padded strings are not silently corrected or approved for model fitting.
    frame = pd.DataFrame({
        "churn": ["Y", "N"] * 40,
        "feature": ["High risk", "Low risk", " High risk", "Low risk "] * 20,
    })
    before = frame.copy(deep=True)
    review = target_opportunities.recommend(frame, 0)
    candidate = {item["column"]: item for item in review["suggestions"]}["churn"]
    assert candidate["technical_status"] == "reviewable"
    assert candidate["task_hypothesis"] == "classification"
    assert candidate["safe_to_train_automatically"] is False
    manual = target_opportunities.inspect_manual_target(frame, 0, "churn")
    assert manual["candidate"]["technical_status"] == "reviewable"
    assert manual["training_authorised"] is False
    assert frame.equals(before)


@pytest.mark.parametrize("numeric_labels", [
    [float("inf"), float("-inf")] * 40,
    [1.0, float("inf")] * 40,
    [1.0, float("-inf")] * 40,
])
def test_p4_categorical_numeric_target_infinities_fail_closed(numeric_labels):
    # pandas labels with CategoricalDtype are not considered numeric by
    # is_numeric_dtype(series), even when the categories are numeric.
    frame = pd.DataFrame({
        "churn": pd.Categorical(numeric_labels),
        "feature": [i % 8 for i in range(80)],
    })
    original = frame.copy(deep=True)
    assert not pd.api.types.is_numeric_dtype(frame["churn"])
    assert pd.api.types.is_numeric_dtype(frame["churn"].cat.categories.dtype)
    queue = target_opportunities.recommend(frame, 0)
    assert queue["abstained"] is True
    candidate = {item["column"]: item for item in queue["blocked_examples"]}["churn"]
    assert candidate["technical_status"] == "blocked"
    assert candidate["task_hypothesis"] is None
    assert candidate["safe_to_train_automatically"] is False
    assert any("finite" in blocker.lower() for blocker in candidate["blockers"])
    manual = target_opportunities.inspect_manual_target(frame, 0, "churn")
    assert manual["candidate"]["technical_status"] == "blocked"
    assert manual["training_authorised"] is False
    assert frame.equals(original)


@pytest.mark.parametrize("numeric_predictor", [
    [float("inf"), float("-inf")] * 40,
    [3.0, float("inf")] * 40,
    [3.0, float("-inf")] * 40,
])
def test_p4_categorical_numeric_predictor_infinities_not_variation(numeric_predictor):
    frame = pd.DataFrame({
        "churn": ["Y", "N"] * 40,
        "signal": pd.Categorical(numeric_predictor),
    })
    original = frame.copy(deep=True)
    assert not pd.api.types.is_numeric_dtype(frame["signal"])
    queue = target_opportunities.recommend(frame, 1)
    assert queue["abstained"] is True
    candidate = {item["column"]: item for item in queue["blocked_examples"]}["churn"]
    assert candidate["technical_status"] == "blocked"
    assert candidate["task_hypothesis"] is None
    assert any("No non-constant, non-empty candidate predictor" in blocker
               for blocker in candidate["blockers"])
    manual = target_opportunities.inspect_manual_target(frame, 1, "churn")
    assert manual["candidate"]["technical_status"] == "blocked"
    assert manual["training_authorised"] is False
    assert frame.equals(original)


def test_p4_categorical_numeric_finite_controls_remain_structural_only():
    frame = pd.DataFrame({
        "churn": pd.Categorical([0.0, 1.0] * 40),
        "signal": pd.Categorical([10.0, 20.0, float("inf"), float("-inf")] * 20),
    })
    original = frame.copy(deep=True)
    queue = target_opportunities.recommend(frame, 7)
    candidate = {item["column"]: item for item in queue["suggestions"]}["churn"]
    assert candidate["technical_status"] == "reviewable"
    assert candidate["task_hypothesis"] == "classification"
    assert candidate["safe_to_train_automatically"] is False
    manual = target_opportunities.inspect_manual_target(frame, 7, "churn")
    assert manual["candidate"]["technical_status"] == "reviewable"
    assert manual["training_authorised"] is False
    assert frame.equals(original)


def test_p4_categorical_complex_target_is_explicitly_blocked():
    frame = pd.DataFrame({
        "churn": pd.Categorical([complex(1, 1), complex(2, 2)] * 40),
        "feature": [i % 5 for i in range(80)],
    })
    original = frame.copy(deep=True)
    result = target_opportunities.recommend(frame, 0)
    candidate = {item["column"]: item for item in result["blocked_examples"]}["churn"]
    assert candidate["technical_status"] == "blocked"
    assert candidate["task_hypothesis"] is None
    assert any("Complex-valued" in blocker for blocker in candidate["blockers"])
    assert frame.equals(original)


@pytest.mark.parametrize("name, values", [
    ("outcome", pd.date_range("2026-01-01", periods=2).repeat(40)),
    ("churn", pd.date_range("2026-01-01", periods=2, tz="UTC").repeat(40)),
])
def test_p4_datetime_categorical_outcome_is_not_classification(name, values):
    # An unqualified outcome header must not make datetime categories into
    # ordinary two-class outcomes. The existing header-only *_at guard cannot
    # detect a CategoricalDtype holding datetime64 timestamps.
    frame = pd.DataFrame({
        name: pd.Categorical(values),
        "signal": [i % 8 for i in range(80)],
    })
    before = frame.copy(deep=True)
    assert not pd.api.types.is_datetime64_any_dtype(frame[name])
    assert pd.api.types.is_datetime64_any_dtype(frame[name].cat.categories.dtype)
    queue = target_opportunities.recommend(frame, 2)
    assert queue["abstained"] is True
    candidate = {item["column"]: item for item in queue["blocked_examples"]}[name]
    assert candidate["technical_status"] == "blocked"
    assert candidate["task_hypothesis"] is None
    assert candidate["safe_to_train_automatically"] is False
    assert any("date/time" in reason for reason in candidate["blockers"])
    manual = target_opportunities.inspect_manual_target(frame, 2, name)
    assert manual["candidate"]["technical_status"] == "blocked"
    assert manual["candidate"]["task_hypothesis"] is None
    assert manual["training_authorised"] is False
    assert frame.equals(before)


def test_p4_ordinary_categorical_outcome_and_duration_target_stay_reviewable():
    # Ordinary classification categories and numeric duration outcomes
    # retain structural-review semantics, never training authorisation.
    cat_frame = pd.DataFrame({
        "outcome": pd.Categorical(["Y", "N"] * 40),
        "signal": [i % 7 for i in range(80)],
    })
    duration_frame = pd.DataFrame({
        "time_to_resolution": [float(i + 1) for i in range(80)],
        "kind": ["A", "B"] * 40,
    })
    for frame, name, task in (
        (cat_frame, "outcome", "classification"),
        (duration_frame, "time_to_resolution", "regression"),
    ):
        before = frame.copy(deep=True)
        queue = target_opportunities.recommend(frame, 3)
        candidate = {item["column"]: item for item in queue["suggestions"]}[name]
        assert candidate["technical_status"] == "reviewable"
        assert candidate["task_hypothesis"] == task
        assert candidate["safe_to_train_automatically"] is False
        manual = target_opportunities.inspect_manual_target(frame, 3, name)
        assert manual["candidate"]["technical_status"] == "reviewable"
        assert manual["training_authorised"] is False
        assert frame.equals(before)
