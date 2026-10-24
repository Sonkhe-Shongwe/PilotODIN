"""Macro A3: reproducible predictor audits, reviewed leakage risk and time-fold hygiene."""
from __future__ import annotations

from datetime import date, timedelta

import numpy as np
import pandas as pd
import pytest
from fastapi import BackgroundTasks, HTTPException

from backend import engine, main


def classification_frame():
    n=40
    return pd.DataFrame({
        "CustomerID":[f"C{i:04d}" for i in range(n)],
        "Final_Result_After":["Closed" if i%2 else "Open" for i in range(n)],
        "Amount":[float(i) if i%7 else np.nan for i in range(n)],
        "Channel":["Retail" if i%3 else "Online" for i in range(n)],
        "Constant":["Same"]*n,
        "AllMissing":[None]*n,
        "Flagged":["Yes" if i%2 else "No" for i in range(n)],
    })


def time_frame(total=70):
    assert total%2==0
    days=[date(2026,1,1)+timedelta(days=i//2) for i in range(total)]
    return pd.DataFrame({
        "ObservedAt":[d.isoformat() for d in days],
        "Balance":[float(i%11) for i in range(total)],
        "FutureValue":[float(i*.5+2*(i%7)) for i in range(total)],
    })


def test_prepare_explains_every_candidate_without_preemptive_mutation():
    frame=classification_frame()
    before=frame.copy(deep=True)
    plan=engine.preparation(frame,"Flagged")
    assert plan["task"]=="classification"
    assert len(plan["feature_audit"])==len(frame.columns)-1
    assert {x["column"] for x in plan["feature_audit"]}==set(frame.columns)-{"Flagged"}
    flagged=set(plan["high_risk_features"])
    assert flagged=={"CustomerID","Final_Result_After"}
    by_name={x["column"]:x for x in plan["feature_audit"]}
    assert by_name["CustomerID"]["risk"]=="high"
    assert "identifier" in "; ".join(by_name["CustomerID"]["reasons"])
    assert "outcome leakage" in "; ".join(by_name["Final_Result_After"]["reasons"])
    assert by_name["Amount"]["kind"]=="numeric" and by_name["Amount"]["missing"]==6
    assert "training folds" in by_name["Amount"]["treatment"]
    assert by_name["Channel"]["kind"]=="categorical"
    assert by_name["AllMissing"]["default_included"] is False
    assert by_name["Constant"]["risk"]=="review"
    assert frame.equals(before)


def test_train_api_refuses_unreviewed_included_risks_and_records_acknowledgement(monkeypatch):
    frame=classification_frame()
    monkeypatch.setattr(main,"project_or_404",lambda _:{"id":"safe-demo"})
    monkeypatch.setattr(main.quality,"current_data",lambda _: (frame,3))
    captured=[]
    monkeypatch.setattr(main.storage,"new_experiment",lambda pid,cfg: (captured.append((pid,cfg)) or "experiment-example"))
    body=dict(
        target="Flagged",task="classification",excluded_features=["Constant","AllMissing"],
        models=["logistic_regression"],split_strategy="random",
        acknowledge_random_split=True,expected_quality_version=3,
    )
    with pytest.raises(HTTPException) as denied:
        main.new_experiment("safe-demo",main.ExperimentRequest(**body),BackgroundTasks())
    assert denied.value.status_code==422
    assert "CustomerID" in denied.value.detail
    assert not captured

    approved=main.ExperimentRequest(**body,acknowledge_feature_risks=True)
    created=main.new_experiment("safe-demo",approved,BackgroundTasks())
    assert created["status"]=="queued"
    assert captured[0][1]["acknowledge_feature_risks"] is True
    assert captured[0][1]["reviewed_high_risk_features"]==["CustomerID","Final_Result_After"]

    without_risk=main.ExperimentRequest(**{**body,
        "excluded_features":["CustomerID","Final_Result_After","Constant","AllMissing"]})
    main.new_experiment("safe-demo",without_risk,BackgroundTasks())
    assert captured[1][1]["acknowledge_feature_risks"] is False
    assert captured[1][1]["reviewed_high_risk_features"]==[]


def test_chronological_holdout_rejects_identical_boundary_timestamps():
    # 72 rows, two per date: 80% cut = 57; that splits one day's observations.
    frame=time_frame(72)
    with pytest.raises(ValueError,match="boundary crosses identical timestamps"):
        engine.run_training(frame,target="FutureValue",excluded=[],models=["linear_regression"],
                            task="regression",split_strategy="time",split_column="ObservedAt")


def test_time_cv_never_splits_equal_timestamps_across_any_fold(monkeypatch):
    frame=time_frame(70)
    original=engine.cross_val_score
    inspected=[]

    def audited_cv(estimator,X,y,*,cv,**kwargs):
        assert isinstance(cv,list)
        for training,validation in cv:
            assert len(training)>0 and len(validation)>0
            earlier=pd.to_datetime(frame.loc[X.iloc[training].index,"ObservedAt"])
            later=pd.to_datetime(frame.loc[X.iloc[validation].index,"ObservedAt"])
            assert set(earlier).isdisjoint(set(later))
            assert earlier.max() < later.min()
            inspected.append((len(training),len(validation)))
        return original(estimator,X,y,cv=cv,**kwargs)

    monkeypatch.setattr(engine,"cross_val_score",audited_cv)
    report,pipelines,test_X,test_y=engine.run_training(
        frame,target="FutureValue",excluded=[],models=["linear_regression"],
        task="regression",split_strategy="time",split_column="ObservedAt")
    assert report["split_strategy"]=="time"
    assert report["folds"]==3
    assert report["features"]==["Balance"]
    assert len(test_X)==14 and len(test_y)==14
    assert "ObservedAt" not in report["input_schema"][0]["name"]
    assert len(inspected)==report["folds"]*2  # baseline + one selected algorithm
    assert "linear_regression" in pipelines
