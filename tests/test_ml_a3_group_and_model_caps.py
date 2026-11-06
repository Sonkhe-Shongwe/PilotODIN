"""A3 integration guardrails: no collision between true missing and literal group IDs;
and no silently huge kernel/neighbour fitting on an 8 GB local-first machine."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from backend import engine


def group_frame():
    groups=[None, "(Missing group)", "G2", "G3", "G4", "G5", "G6", "G7"]
    return pd.DataFrame({
        "GroupID": [groups[i%8] for i in range(96)],
        "Measure": [float((i*11)%23) for i in range(96)],
        "Target": [float(100+i*.7+(i%9)*2) for i in range(96)]
    })


def test_true_null_and_literal_group_id_never_coalesce_across_holdout_or_cv(monkeypatch):
    frame=group_frame()
    unchanged=frame.copy(deep=True)
    seen={}
    original_split=engine.GroupShuffleSplit
    original_cv=engine.cross_val_score

    class GroupSpy:
        def __init__(self,*args,**kwargs):
            self.inner=original_split(*args,**kwargs)

        def split(self,X,y,groups):
            seen["all_groups"]=pd.Series(groups,index=X.index)
            yield from self.inner.split(X,y,groups)

    def audited_cross_validation(estimator,X,y,*,cv,groups=None,**kwargs):
        assert groups is not None
        assert isinstance(cv,engine.GroupKFold)
        assert len(groups)==len(X)
        for training,validation in cv.split(X,y,groups=groups):
            training_groups=set(pd.Series(groups).iloc[training])
            validation_groups=set(pd.Series(groups).iloc[validation])
            assert not training_groups.intersection(validation_groups)
        seen["cv_calls"]=seen.get("cv_calls",0)+1
        return original_cv(estimator,X,y,cv=cv,groups=groups,**kwargs)

    monkeypatch.setattr(engine,"GroupShuffleSplit",GroupSpy)
    monkeypatch.setattr(engine,"cross_val_score",audited_cross_validation)
    report,_,X_test,y_test=engine.run_training(
        frame,target="Target",excluded=[],models=["linear_regression"],
        task="regression",split_strategy="group",split_column="GroupID")
    codes=seen["all_groups"]
    assert codes.nunique()==8
    missing_code=int(codes[frame["GroupID"].isna()].iloc[0])
    literal_code=int(codes[frame["GroupID"].eq("(Missing group)")].iloc[0])
    assert missing_code!=literal_code
    assert codes[frame["GroupID"].isna()].nunique()==1
    assert codes[frame["GroupID"].eq("(Missing group)")].nunique()==1
    holdout=set(codes.loc[y_test.index])
    training=set(codes.drop(index=y_test.index))
    assert not training.intersection(holdout)
    assert seen["cv_calls"]==2  # baseline + selected model
    assert report["split_strategy"]=="group"
    assert "GroupID" not in report["features"]
    assert len(X_test)==len(y_test)
    assert unchanged.equals(frame)


@pytest.mark.parametrize("model,limit,task",[
    ("svr",engine.MAX_KERNEL_MODEL_ROWS,"regression"),
    ("svm",engine.MAX_KERNEL_MODEL_ROWS,"classification"),
    ("knn",engine.MAX_NEIGHBOUR_MODEL_ROWS,"regression"),
])
def test_expensive_models_refuse_oversized_labelled_data_before_training(model,limit,task):
    n=limit+1
    frame=pd.DataFrame({
        "Predictor":np.arange(n,dtype=float),
        "Target":([float(i*i%91) for i in range(n)] if task=="regression"
                  else ["A" if i%2 else "B" for i in range(n)])
    })
    copy=frame.copy(deep=True)
    plan=engine.training_resource_plan(frame[["Predictor"]],n,[model])
    assert plan["selected_model_row_limit"]==limit
    assert plan["within_local_budget"] is False
    assert plan["estimated_dense_training_mb"]<5
    with pytest.raises(ValueError,match="resource guardrail exceeded"):
        engine.validate_config(frame,"Target",[],[model],task)
    assert copy.equals(frame)


def test_model_comparisons_obey_the_strictest_selected_cap():
    x=pd.DataFrame({"X":[1.]*35})
    plan=engine.training_resource_plan(x,6000,["random_forest","svm","knn"])
    assert plan["selected_model_row_limit"]==engine.MAX_KERNEL_MODEL_ROWS
    assert "Kernel" in plan["selected_model_guard"]
    assert plan["within_local_budget"] is False

    neighbour=engine.training_resource_plan(x,6000,["knn","random_forest"])
    assert neighbour["selected_model_row_limit"]==engine.MAX_NEIGHBOUR_MODEL_ROWS
    assert neighbour["within_local_budget"] is True
    assert neighbour["model_family_row_limits"]["svr"]==engine.MAX_KERNEL_MODEL_ROWS

    general=engine.training_resource_plan(x,6000,["random_forest"])
    assert general["selected_model_row_limit"]==engine.MAX_ML_LABELLED_ROWS
    assert general["within_local_budget"] is True
