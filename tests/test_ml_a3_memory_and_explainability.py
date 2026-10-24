"""Macro A3: bounded post-selection explanations and 8 GB training preflight.

All tests are deterministic, CPU-only, use tiny memory footprints and never
start bundled AI, modify user datasets, or create real model artifacts.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from sklearn.tree import DecisionTreeClassifier
from sklearn.dummy import DummyRegressor

from backend import engine


def test_bounded_classification_sensitivity_is_reproducible_and_read_only():
    n=140
    x=pd.DataFrame({
        "ActualSignal":np.arange(n,dtype=float),
        "Irrelevant":[(i*13)%11 for i in range(n)]
    })
    truth=pd.Series(np.where(x["ActualSignal"]>=70,"High","Low"))
    model=DecisionTreeClassifier(random_state=42,max_depth=2).fit(x,truth)
    untouched=x.copy(deep=True)
    one=engine.bounded_feature_sensitivity(model,x,truth,"classification")
    two=engine.bounded_feature_sensitivity(model,x,truth,"classification")
    assert one==two
    assert one["status"]=="computed"
    assert one["sample_rows"]==64 and one["total_test_rows"]==n
    assert one["features_evaluated"]==2 and one["total_predictors"]==2
    assert one["repeats"]==2 and one["seed"]==42
    assert one["sampled"] is True
    assert one["data_source"]=="Frozen held-out set, AFTER model choice"
    assert one["metric"]=="Macro F1 loss"
    by_field={row["feature"]:row for row in one["scores"]}
    assert by_field["ActualSignal"]["mean_importance"]>0
    assert by_field["Irrelevant"]["mean_importance"]==0
    assert x.equals(untouched)
    assert len(one["limitations"])>=3


def test_partial_coverage_does_not_pretend_untested_predictors_are_unimportant():
    x=pd.DataFrame({f"F{i:02d}":[(row+i)%7 for row in range(80)] for i in range(18)})
    truth=pd.Series([float(i%4) for i in range(80)])
    model=DummyRegressor(strategy="mean").fit(x,truth)
    result=engine.bounded_feature_sensitivity(model,x,truth,"regression")
    assert result["status"]=="computed"
    assert result["features_evaluated"]==8
    assert result["total_predictors"]==18
    assert result["sample_rows"]==64
    assert result["metric"]=="MAE increase"
    assert result["sampled"] is True
    assert len({v["feature"] for v in result["scores"]})==8
    assert all(v["mean_importance"]==0 for v in result["scores"])
    assert all("F" in v["feature"] for v in result["scores"])
    assert not any(v["feature"]=="UNTESTED" for v in result["scores"])


def test_insufficient_holdout_disables_diagnostic_instead_of_inventing_importance():
    x=pd.DataFrame({"OnlyField":[1,2,3,4,5,6,7,8,9]})
    y=pd.Series(range(9))
    result=engine.bounded_feature_sensitivity(None,x,y,"regression")
    assert result["status"]=="unavailable"
    assert "Too few" in result["reason"]


def test_training_budget_reports_dense_memory_limits_without_fitting():
    columns={f"Segment{i:02d}":[f"g{j:02d}" for j in range(25)] for i in range(80)}
    x=pd.DataFrame(columns)
    plan=engine.training_resource_plan(x,29_000)
    assert plan["labelled_rows"]==29_000
    assert plan["source_features"]==80
    assert plan["estimated_encoded_columns"]==80*25
    assert plan["estimated_dense_training_mb"]>256
    assert plan["within_local_budget"] is False
    assert plan["row_limit"]==30_000
    assert plan["estimated_dense_mb_limit"]==256


def test_resource_guard_rejects_too_many_labelled_rows_before_fit():
    df=pd.DataFrame({"Units":np.arange(30_001,dtype=int),
                     "Revenue":np.arange(30_001,dtype=float)*1.05})
    original=df.copy(deep=True)
    with pytest.raises(ValueError,match="Local training resource guardrail exceeded"):
        engine.validate_config(df,"Revenue",[],["linear_regression"],"regression")
    assert df.equals(original)


def test_prepare_exposes_candid_before_exclusion_estimate():
    df=pd.DataFrame({"Age":[10+i%8 for i in range(40)],
                     "Country":["SA" if i%2 else "ZA" for i in range(40)],
                     "Outcome":["Yes" if i%2 else "No" for i in range(40)]})
    prep=engine.preparation(df,"Outcome")
    plan=prep["resource_plan"]
    assert plan["labelled_rows"]==40
    assert plan["source_features"]==2
    assert plan["within_local_budget"] is True
    assert "before manual exclusions" in prep["resource_plan_scope"]
    assert "Not a peak RAM measurement" in plan["note"]
