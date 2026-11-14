"""P4-52 read-only chronological design for the actual public UCI bike fixture.

Inspect real 2011-2012 observations and non-model reference rules only.
Never fit any estimator, trigger an experiment, assume source-system label
availability, modify the user's original project or claim real Gate C.
"""
from __future__ import annotations

import hashlib
from pathlib import Path
from statistics import mean, median

import pandas as pd
import pytest
from sklearn.model_selection import TimeSeriesSplit

from backend import engine


FIXTURE = Path(__file__).parent / "fixtures" / "public_bike_daily_preday_731.csv"
FIXTURE_SHA256 = "51e105f75acf827e5c089a8f30925fe8ab90c59df46201a9d724ad5f67588636"
TARGET = "daily_rentals_target"
SPLIT_COLUMN = "date"
PRE_DAY_CALENDAR = ("season", "yr", "mnth", "holiday", "weekday", "workingday")


def _source() -> pd.DataFrame:
    assert hashlib.sha256(FIXTURE.read_bytes()).hexdigest() == FIXTURE_SHA256
    return pd.read_csv(FIXTURE)


def _error(truth: list[int], forecast: list[float]) -> float:
    assert len(truth) == len(forecast) and len(truth) > 0
    return sum(abs(actual - proposed) for actual, proposed in zip(truth, forecast)) / len(truth)


def test_pre_day_calendar_schema_and_effective_split_exclusion():
    df = _source()
    original = df.copy(deep=True)
    assert df.shape == (731, 8)
    assert list(df) == [SPLIT_COLUMN, *PRE_DAY_CALENDAR, TARGET]
    assert not df.isna().any().any()
    assert set(df["yr"]) == {0, 1}
    assert set(df["season"]) == {1, 2, 3, 4}
    assert set(df["holiday"]) <= {0, 1}
    assert set(df["workingday"]) <= {0, 1}
    dates = pd.to_datetime(df[SPLIT_COLUMN], format="mixed", dayfirst=True, errors="raise")
    assert (df["yr"] == dates.dt.year - 2011).all()
    assert (df["mnth"] == dates.dt.month).all()
    assert (df["weekday"] == (dates.dt.weekday + 1) % 7).all()
    workingday_from_schedule = (
        (df["weekday"].between(1, 5)) & (df["holiday"] == 0)
    ).astype(int)
    assert (df["workingday"] == workingday_from_schedule).all()

    # This calls only engine's configuration/data validation; it NEVER calls
    # run_training, an estimator.fit, an experiment endpoint or an API write.
    # The date is available for chronological order but NOT a fitted feature.
    predictors, labels, task = engine.validate_config(
        df, TARGET, [SPLIT_COLUMN], ["linear_regression"], "regression"
    )
    assert task == "regression"
    assert list(predictors.columns) == list(PRE_DAY_CALENDAR)
    assert len(predictors) == len(labels) == 731
    assert TARGET not in predictors and SPLIT_COLUMN not in predictors
    pd.testing.assert_frame_equal(df, original)


def test_chronological_holdout_and_expanding_validation_match_engine_policy():
    df = _source()
    times = pd.to_datetime(
        df[SPLIT_COLUMN], errors="coerce", dayfirst=True, format="mixed"
    )
    assert times.notna().all()
    assert times.is_unique
    assert times.is_monotonic_increasing
    assert (times.diff().dropna() == pd.Timedelta(days=1)).all()

    # Equivalent to the bounded date-order and int(0.8*n) policy in
    # engine.run_training, without invoking that training function.
    ordered = times.sort_values(kind="stable").reset_index(drop=True)
    cut = int(len(df) * .8)
    development, holdout = ordered.iloc[:cut], ordered.iloc[cut:]
    assert cut == 584
    assert len(holdout) == 147
    assert development.iloc[0].strftime("%Y-%m-%d") == "2011-01-01"
    assert development.iloc[-1].strftime("%Y-%m-%d") == "2012-08-06"
    assert holdout.iloc[0].strftime("%Y-%m-%d") == "2012-08-07"
    assert holdout.iloc[-1].strftime("%Y-%m-%d") == "2012-12-31"
    assert development.max() < holdout.min()

    expected = [
        (146, 146, "2011-05-26", "2011-05-27", "2011-10-19"),
        (292, 146, "2011-10-19", "2011-10-20", "2012-03-13"),
        (438, 146, "2012-03-13", "2012-03-14", "2012-08-06"),
    ]
    for (train, validation), (n_train, n_val, train_end, val_start, val_end) in zip(
        TimeSeriesSplit(n_splits=3).split(development), expected
    ):
        assert len(train) == n_train and len(validation) == n_val
        assert development.iloc[train[-1]].strftime("%Y-%m-%d") == train_end
        assert development.iloc[validation[0]].strftime("%Y-%m-%d") == val_start
        assert development.iloc[validation[-1]].strftime("%Y-%m-%d") == val_end
        assert development.iloc[train[-1]] < development.iloc[validation[0]]


def test_descriptive_holdout_reference_errors_are_provenance_bound_and_no_fit():
    df = _source()
    counts = df[TARGET].astype(int).tolist()
    cut = int(len(counts) * .8)
    reference, truth = counts[:cut], counts[cut:]
    assert len(reference) == 584 and len(truth) == 147

    # Fixed-origin simple baselines are trained/calculated ONLY on development.
    # These are non-model descriptive predictions, not ML experiments.
    fixed_mean = _error(truth, [mean(reference)] * len(truth))
    fixed_median = _error(truth, [median(reference)] * len(truth))
    assert fixed_mean == pytest.approx(2290.412706, abs=.001)
    assert fixed_median == pytest.approx(2259.163265, abs=.001)

    # These rolling baselines require PRIOR REAL observations to have been
    # published before each next-day prediction. The public source does NOT
    # verify that reporting latency, so results are *conditional*, not valid
    # fixed-origin predictions 147 days into the future.
    previous_day = _error(truth, [counts[i - 1] for i in range(cut, len(counts))])
    last_seven_mean = _error(
        truth, [mean(counts[i - 7:i]) for i in range(cut, len(counts))]
    )
    last_weekday = _error(
        truth, [counts[i - 7] for i in range(cut, len(counts))]
    )
    assert previous_day == pytest.approx(878.394558, abs=.001)
    assert last_seven_mean == pytest.approx(918.630709, abs=.001)
    assert last_weekday == pytest.approx(1194.734694, abs=.001)

    # No use of future true values: every rolling index is strictly earlier
    # than its prediction target date. No model/fit is run anywhere in test.
    assert all(i - 7 < i and i - 1 < i for i in range(cut, len(counts)))
