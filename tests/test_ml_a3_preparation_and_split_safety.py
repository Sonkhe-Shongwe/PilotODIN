"""Macro A3: reproducible predictor audits, reviewed leakage risk and time-fold hygiene."""
from __future__ import annotations

from datetime import date, timedelta

import joblib
import numpy as np
import pandas as pd
import pytest
from fastapi import BackgroundTasks, HTTPException
from fastapi.testclient import TestClient

from backend import engine, main, storage


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


def test_fitted_experiment_reopens_with_original_preprocessing_and_quality_version(tmp_path, monkeypatch):
    """Exercise the real worker and SQLite across two isolated ASGI lifespans."""
    home = tmp_path / "pilotodin"
    (home / "datasets").mkdir(parents=True)
    (home / "models").mkdir()
    monkeypatch.setattr(storage, "HOME", home)
    monkeypatch.setattr(storage, "DB_PATH", home / "pilotodin.sqlite3")
    monkeypatch.setattr(main.ai_provider, "CONFIG_PATH", home / "ai_settings.json")
    monkeypatch.setattr(main.ai_provider, "SECRETS_PATH", home / "ai_secrets.dpapi")
    monkeypatch.delenv("PILOTODIN_DESKTOP_SESSION", raising=False)
    storage.init()
    main.quality._init_tables()

    frame = classification_frame().drop(columns=["Final_Result_After", "Constant", "AllMissing"])
    frame.loc[frame.index % 5 == 0, "Channel"] = None
    frame.loc[1, "Channel"] = " Retail "
    original = frame.to_csv(index=False).encode("utf-8")

    def apply_quality(client, project_url, proposal):
        preview = client.post(project_url + "/quality/proposals", json=proposal)
        assert preview.status_code == 200, preview.text
        receipt = preview.json()
        commit = client.post(project_url + "/quality/commit", json={
            key: receipt[key] for key in ("proposal_id", "proposal_hash")
        })
        assert commit.status_code == 200, commit.text
        return commit.json()["version"]

    with TestClient(main.app) as client:
        created = client.post("/api/projects", files={"file": ("synthetic.csv", original, "text/csv")})
        assert created.status_code == 201, created.text
        project_id = created.json()["id"]
        project_url = f"/api/projects/{project_id}"
        assert apply_quality(client, project_url, {"operation": "autopilot", "expected_version": 0}) == 1
        response = client.post(project_url + "/experiments", json={
            "target": "Flagged", "task": "classification", "models": ["logistic_regression"],
            "excluded_features": ["CustomerID"], "acknowledge_random_split": True,
            "expected_quality_version": 1, "numeric_imputation": "mean", "categorical_imputation": "constant",
        })
        assert response.status_code == 202, response.text
        experiment_id = response.json()["id"]
        experiment_url = f"/api/experiments/{experiment_id}"
        completed = client.get(experiment_url).json()
        assert completed["status"] == "completed", completed["error"]
        assert completed["dataset_version"] == completed["current_version"] == 1
        assert completed["is_stale"] is False
        config = completed["config"]
        assert {key: config[key] for key in ("numeric_imputation", "categorical_imputation", "quality_version")} == {
            "numeric_imputation": "mean", "categorical_imputation": "constant", "quality_version": 1,
        }
        assert completed["results"]["features"] == ["Amount", "Channel"]

    with TestClient(main.app) as reopened:
        history = reopened.get(project_url).json()["experiments"]
        assert [(item["id"], item["status"]) for item in history] == [(experiment_id, "completed")]
        assert reopened.get(experiment_url).json() == completed

        artifacts = home / "models" / experiment_id
        pipe = joblib.load(artifacts / "logistic_regression.joblib")
        holdout, _ = joblib.load(artifacts / "test_set.joblib")
        approved, version = main.quality.current_data(project_id)
        assert version == 1
        development = approved.drop(index=holdout.index)
        preprocessing = pipe.named_steps["preprocessor"].named_transformers_
        numeric = preprocessing["numeric"].named_steps["imputer"]
        categorical = preprocessing["categorical"].named_steps
        assert numeric.strategy == "mean"
        assert numeric.statistics_[0] == pytest.approx(development["Amount"].mean())
        assert categorical["imputer"].strategy == "constant"
        assert engine.CATEGORICAL_MISSING_MARKER in categorical["encoder"].categories_[0]
        assert " Retail " not in categorical["encoder"].categories_[0]

        selected = reopened.post(experiment_url + "/select", json={"model_key": "logistic_regression"})
        assert selected.status_code == 200, selected.text
        predict_url = experiment_url + "/predict"
        payload = {"values": {"Amount": None, "Channel": None}}
        prediction = reopened.post(predict_url, json=payload)
        assert prediction.status_code == 200, prediction.text
        assert prediction.json()["dataset_version"] == 1

        assert apply_quality(reopened, project_url, {
            "operation": "restore", "expected_version": 1, "target_version": 0,
        }) == 2
        historical = reopened.get(experiment_url).json()
        assert historical["config"] == config
        assert historical["results"] == completed["results"]
        assert historical["selected_model"] == "logistic_regression"
        assert (historical["dataset_version"], historical["current_version"], historical["is_stale"]) == (1, 2, True)
        assert reopened.post(predict_url, json=payload).status_code == 409
        source = storage.get_project(project_id)["dataset_path"]
        assert (home / "datasets" / source).read_bytes() == original


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


@pytest.mark.parametrize("strategy,split_column", [
    ("group", "GroupKey"), ("time", "RecordTime"),
])
def test_group_and_time_keys_are_excluded_before_api_and_worker_resource_checks(
        monkeypatch, strategy, split_column):
    """Split metadata may be high-cardinality, but it must never consume model RAM."""
    n = 72
    frame = pd.DataFrame({
        "GroupKey": [f"cust_{i//6:02d}" for i in range(n)],
        "RecordTime": [(date(2026, 1, 1) + timedelta(days=i)).isoformat()
                       for i in range(n)],
        "Signal": [float(i%7) for i in range(n)],
        "Outcome": ["Yes" if i%2 else "No" for i in range(n)],
    })
    original = frame.copy(deep=True)
    real_plan = engine.training_resource_plan
    planned_predictors = []

    def audited_plan(X, rows, models=None, *, categorical_imputation="most_frequent"):
        if models is not None:
            # preparation() intentionally displays a broad BEFORE-exclusions
            # estimate. Training and API cost checks must use fitted columns.
            assert split_column not in X.columns
            planned_predictors.append(list(X.columns))
        return real_plan(X, rows, models, categorical_imputation=categorical_imputation)

    monkeypatch.setattr(engine, "training_resource_plan", audited_plan)
    monkeypatch.setattr(main, "project_or_404", lambda _: {"id": "demo"})
    monkeypatch.setattr(main.quality, "current_data", lambda _: (frame, 3))
    captured = []
    monkeypatch.setattr(main.storage, "new_experiment",
                        lambda pid, cfg: (captured.append(cfg) or "example"))

    body = main.ExperimentRequest(
        target="Outcome", task="classification", excluded_features=[],
        models=["logistic_regression"], split_strategy=strategy,
        split_column=split_column, expected_quality_version=3,
    )
    accepted = main.new_experiment("demo", body, BackgroundTasks())
    assert accepted["status"] == "queued"
    assert captured[0]["split_column"] == split_column
    assert captured[0]["excluded"] == []  # no silent rewriting of user choices

    report, _, _, _ = engine.run_training(
        frame, "Outcome", [], ["logistic_regression"], "classification",
        split_strategy=strategy, split_column=split_column)
    assert split_column not in report["features"]
    assert split_column not in {field["name"] for field in report["input_schema"]}
    assert len(planned_predictors) == 2  # one API check and one worker check
    assert all(split_column not in columns for columns in planned_predictors)
    assert frame.equals(original)

    invalid = body.model_copy(update={"split_column": "Outcome"})
    with pytest.raises(HTTPException, match="Target cannot also be a split column") as error:
        main.new_experiment("demo", invalid, BackgroundTasks())
    assert error.value.status_code == 422
    assert len(captured) == 1


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
