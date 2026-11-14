"""P4-53: verify public bike day-ahead categorical encoding without estimator fit.

This remains a descriptive and API preparation test against disposable files.
No modelling experiment or original Windows PilotODIN data is accessed.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

import pandas as pd
from fastapi.testclient import TestClient

from backend import engine, main, quality, storage


FIXTURES = Path(__file__).parent / "fixtures"
ORIGINAL = FIXTURES / "public_bike_daily_preday_731.csv"
TYPED = FIXTURES / "public_bike_daily_categorical_preday_731.csv"
ORIGINAL_SHA = "51e105f75acf827e5c089a8f30925fe8ab90c59df46201a9d724ad5f67588636"
TYPED_SHA = "8981926c70d117fd487ce5ac5d0381be30dd159488576646c67978a2d3139a2e"
TARGET = "daily_rentals_target"
SPLIT_COLUMN = "date"
NOMINAL = ("season", "yr", "mnth", "holiday", "weekday", "workingday")


def _read():
    assert hashlib.sha256(ORIGINAL.read_bytes()).hexdigest() == ORIGINAL_SHA
    assert hashlib.sha256(TYPED.read_bytes()).hexdigest() == TYPED_SHA
    return pd.read_csv(ORIGINAL), pd.read_csv(TYPED)


def test_numeric_category_codes_are_reversible_text_not_ordinal_regression_features():
    raw, typed = _read()
    assert raw.shape == typed.shape == (731, 8)
    assert list(raw) == list(typed) == ["date", *NOMINAL, TARGET]
    assert raw["date"].is_unique and raw["date"].is_monotonic_increasing
    assert raw["date"].equals(typed["date"])
    assert raw[TARGET].equals(typed[TARGET])
    assert raw.isna().sum().sum() == typed.isna().sum().sum() == 0
    assert not raw.duplicated().any() and not typed.duplicated().any()

    # Raw numbers are ordinal to the generic engine. Explicit prefixed TEXT
    # values make each supplied categorical code nominal and reversible.
    for field in NOMINAL:
        assert engine.inferred_kind(raw[field]) == "numeric"
        assert engine.inferred_kind(typed[field]) == "categorical"
        width = 2 if field == "mnth" else 1
        expected = raw[field].map(
            lambda number: f"{field}_{int(number):0{width}d}"
        )
        pd.testing.assert_series_equal(
            typed[field], expected, check_names=True
        )
        assert typed[field].nunique() == raw[field].nunique()

    raw_preparation = engine.preparation(raw, TARGET)
    typed_preparation = engine.preparation(typed, TARGET)
    before = {x["column"]: x for x in raw_preparation["feature_audit"]}
    after = {x["column"]: x for x in typed_preparation["feature_audit"]}
    for field in NOMINAL:
        assert before[field]["kind"] == "numeric"
        assert after[field]["kind"] == "categorical"
        assert "one-hot encoding" in after[field]["treatment"]
    assert typed_preparation["task"] == "regression"
    assert typed_preparation["missing_targets"] == 0

    # The real modelling code's config validation sees the correct six text
    # predictors after date exclusion; it does NOT call estimator.fit here.
    predictors, labels, task = engine.validate_config(
        typed, TARGET, [SPLIT_COLUMN], ["linear_regression"], "regression"
    )
    assert task == "regression"
    assert list(predictors.columns) == list(NOMINAL)
    assert all(engine.inferred_kind(predictors[c]) == "categorical" for c in NOMINAL)
    assert labels.equals(typed[TARGET])


def test_categorical_bike_disposable_api_import_target_and_prepare(tmp_path, monkeypatch):
    """Actual local endpoints operate only on a new isolated temp SQLite home."""
    home = tmp_path / "typed-bike-p4"
    (home / "datasets").mkdir(parents=True)
    (home / "models").mkdir()
    monkeypatch.setattr(storage, "HOME", home)
    monkeypatch.setattr(storage, "DB_PATH", home / "pilotodin.sqlite3")
    storage.init()
    quality._init_tables()

    source = TYPED.read_bytes()
    with TestClient(main.app) as client:
        uploaded = client.post(
            "/api/projects",
            files={"file": (TYPED.name, source, "text/csv")},
            headers={"Origin": "http://127.0.0.1:5173"},
        )
        assert uploaded.status_code == 201, uploaded.text
        pid = uploaded.json()["id"]
        profile = uploaded.json()["profile"]
        assert profile["rows"] == 731
        assert profile["columns_count"] == 8
        assert profile["missing_cells"] == 0
        assert profile["duplicate_rows"] == 0

        project = storage.get_project(pid)
        assert Path(project["dataset_path"]).is_relative_to(home / "datasets")
        assert Path(project["dataset_path"]).read_bytes() == source
        df, version = quality.current_data(pid)
        assert version == 0
        assert list(df) == [SPLIT_COLUMN, *NOMINAL, TARGET]
        assert all(engine.inferred_kind(df[c]) == "categorical" for c in NOMINAL)

        review = client.get(
            f"/api/projects/{pid}/target-opportunities",
            params={"expected_version": version},
        )
        assert review.status_code == 200, review.text
        named = [
            c for c in review.json()["suggestions"] + review.json()["other_reviewable"]
            if c["column"] == TARGET
        ]
        assert len(named) == 1
        assert named[0]["technical_status"] == "reviewable"
        assert named[0]["task_hypothesis"] == "regression"
        assert named[0]["safe_to_train_automatically"] is False
        assert named[0]["business_relevance"] == "unverified"

        preparation = client.get(
            f"/api/projects/{pid}/preparation", params={"target": TARGET}
        )
        assert preparation.status_code == 200, preparation.text
        plan = preparation.json()
        assert plan["task"] == "regression"
        assert len(plan["available_features"]) == 7
        after = {c["column"]: c for c in plan["feature_audit"]}
        assert all(after[c]["kind"] == "categorical" for c in NOMINAL)
        assert all("one-hot encoding" in after[c]["treatment"] for c in NOMINAL)
        assert SPLIT_COLUMN in plan["available_features"]
        assert plan["missing_targets"] == 0

        assert storage.recent_experiments(pid) == []
        assert list((home / "models").iterdir()) == []
        assert hashlib.sha256(TYPED.read_bytes()).hexdigest() == TYPED_SHA
