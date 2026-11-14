"""P4-55 one-time *research-only* use of current PilotODIN engine on public bike data.

Explicit conversational approval: user "okay next" after offer of ONE bounded
disposable model fit using the public research fixture. No owner machine,
project, native build, installer, private dataset or persistent model artifact.
Not independent Gate C and not an unbiased untouched final holdout.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error

from backend import engine

SOURCE = Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "public_bike_daily_categorical_preday_731.csv"
SOURCE_SHA256 = "8981926c70d117fd487ce5ac5d0381be30dd159488576646c67978a2d3139a2e"
TARGET = "daily_rentals_target"
SPLIT = "date"
PREDICTORS = ("season", "yr", "mnth", "holiday", "weekday", "workingday")
MODELS = ("ridge", "random_forest")
EXPECTED_BASELINE_MEDIAN_MAE = 2259.1632653061224
EXPECTED_CALENDAR_MONTH_WORKDAY_MAE = 2353.1418


def main() -> None:
    assert "RUNNER_TEMP" in os.environ, "Refuse execution except in disposable hosted runner"
    source_bytes = SOURCE.read_bytes()
    assert hashlib.sha256(source_bytes).hexdigest() == SOURCE_SHA256
    df = pd.read_csv(SOURCE)
    assert len(df) == 731
    assert list(df.columns) == [SPLIT, *PREDICTORS, TARGET]
    assert df.isna().sum().sum() == 0
    dates = pd.to_datetime(df[SPLIT], errors="raise")
    assert dates.is_unique and dates.is_monotonic_increasing
    assert dates.iloc[0].strftime("%Y-%m-%d") == "2011-01-01"
    assert dates.iloc[-1].strftime("%Y-%m-%d") == "2012-12-31"
    assert all(engine.inferred_kind(df[c]) == "categorical" for c in PREDICTORS)

    # No import or modification of any local project, model artefact, SQLite
    # database, original app home, private outcome or separate service.
    X, y, task = engine.validate_config(df, TARGET, [SPLIT], list(MODELS), "regression")
    assert task == "regression" and list(X.columns) == list(PREDICTORS)
    assert len(y) == 731
    assert all(engine.inferred_kind(X[c]) == "categorical" for c in PREDICTORS)

    cut = int(len(y) * .8)
    assert cut == 584
    assert dates.iloc[cut - 1].strftime("%Y-%m-%d") == "2012-08-06"
    assert dates.iloc[cut].strftime("%Y-%m-%d") == "2012-08-07"
    y_train = df[TARGET].iloc[:cut].to_numpy(dtype=float)
    y_test_expected = df[TARGET].iloc[cut:].to_numpy(dtype=float)
    fixed_median = float(np.median(y_train))
    baseline_holdout_mae = float(mean_absolute_error(
        y_test_expected, np.full(len(y_test_expected), fixed_median)
    ))
    assert fixed_median == 4200.0
    assert abs(baseline_holdout_mae - EXPECTED_BASELINE_MEDIAN_MAE) < .00001

    # The ONLY training call. PilotODIN runs 3 chronological CV folds,
    # fits exactly 2 specified models ON DEVELOPMENT, then hands back a
    # chronologically held-out frame. No model is serialised or uploaded.
    result, fitted, X_holdout, y_holdout = engine.run_training(
        df,
        target=TARGET,
        excluded=[],
        models=list(MODELS),
        task="regression",
        split_strategy="time",
        split_column=SPLIT,
    )
    assert result["split_strategy"] == "time"
    assert result["split_column"] == SPLIT
    assert result["train_rows"] == 584
    assert result["test_rows"] == 147
    assert result["folds"] == 3
    assert result["labelled_rows"] == 731
    assert result["features"] == list(PREDICTORS)
    assert list(X_holdout) == list(PREDICTORS)
    assert list(y_holdout.to_numpy(dtype=float)) == list(y_test_expected)
    assert result["baseline_reference"] == fixed_median
    assert set(fitted) <= set(MODELS)
    assert len(fitted) >= 1
    ready = [m for m in result["models"] if m["status"] == "ready"]
    assert len(ready) >= 1

    # ONE predeclared winner selected ONLY from earlier chronological CV.
    chosen = min(ready, key=lambda m: (m["cv_metric"], MODELS.index(m["key"])))
    prediction = fitted[chosen["key"]].predict(X_holdout)
    assert len(prediction) == 147 and np.isfinite(prediction).all()
    holdout_mae = float(mean_absolute_error(y_holdout, prediction))
    baseline_cv = float(result["baseline_cv"])
    improvement = baseline_holdout_mae - holdout_mae

    # Report aggregates ONLY. The final holdout is already historically
    # inspected in P4-54, thus this is *exploratory retrospective research*,
    # not a fresh-blind performance acceptance result.
    report = {
        "status": "research_fit_completed_not_business_approval",
        "experiment": "P4-55_one_disposable_public_bike_model_fit",
        "dataset_sha256": SOURCE_SHA256,
        "source": "public_UCI_Bike_Sharing_2011_2012_derivative_CC_BY_4_0",
        "model_fitting_calls": "one_call_to_engine_run_training_with_two_predeclared_estimators",
        "train_rows": 584,
        "holdout_rows": 147,
        "development_end": "2012-08-06",
        "holdout_start": "2012-08-07",
        "target": TARGET,
        "task": "regression",
        "split_strategy": result["split_strategy"],
        "split_column": result["split_column"],
        "features": result["features"],
        "models_predeclared": MODELS,
        "cv_folds": result["folds"],
        "cv_baseline_median_mae": baseline_cv,
        "cv_models": [
            {"key": m["key"], "status": m["status"],
             **({"cv_mae": m["cv_metric"], "cv_std": m["cv_std"]}
                 if m["status"] == "ready" else {"error": m["error"]})}
            for m in result["models"]
        ],
        "cv_selected_model": chosen["key"],
        "final_holdout_selected_model_mae": round(holdout_mae, 5),
        "final_holdout_fixed_dev_median_mae": round(baseline_holdout_mae, 5),
        "final_holdout_month_workday_reference_mae": EXPECTED_CALENDAR_MONTH_WORKDAY_MAE,
        "selected_vs_median_mae_reduction": round(improvement, 5),
        "selected_beats_fixed_median_on_holdout": improvement > 0,
        "selection_basis": "development_chronological_CV_only",
        "model_exported": False,
        "training_installed_app": False,
        "real_business_gate_c_verified": False,
        "fully_unseen_holdout": False,
        "holdout_note": "P4-54 already examined aggregated final holdout outcomes; exploratory retrospective only.",
        "operational_limits": [
            "No independent decision-owner or cost-benefit signoff",
            "Day-ahead holiday and working-day label availability unverified",
            "Citywide demand not station-level resource allocation",
            "2013+ year categories unobserved",
            "No rolling timestamp feature latency verification",
            "No native Windows / 8GB offline hardware measurement",
        ],
    }
    print("P4_55_RESEARCH_SUMMARY_JSON=" + json.dumps(report, sort_keys=True))
    assert hashlib.sha256(SOURCE.read_bytes()).hexdigest() == SOURCE_SHA256


if __name__ == "__main__":
    main()
