"""P4 read-only feasibility with user-supplied public UCI Bike Sharing daily data.

This tests an actual disposable local API import on a hosted runner, NEVER the
owner's Windows installation. It creates no experiment or model and does not
approve a live demand forecasting business decision.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

import pandas as pd
from fastapi.testclient import TestClient

from backend import main, quality, storage


FIXTURE = Path(__file__).parent / "fixtures" / "public_bike_daily_preday_731.csv"
FIXTURE_SHA256 = "51e105f75acf827e5c089a8f30925fe8ab90c59df46201a9d724ad5f67588636"
COLUMNS = (
    "date", "season", "yr", "mnth", "holiday", "weekday",
    "workingday", "daily_rentals_target",
)


def test_public_bike_csv_disposable_import_review_and_prepare(tmp_path, monkeypatch):
    source = FIXTURE.read_bytes()
    assert hashlib.sha256(source).hexdigest() == FIXTURE_SHA256
    assert len(source) == 20701
    csv = pd.read_csv(FIXTURE)
    assert csv.shape == (731, 8)
    assert tuple(csv.columns) == COLUMNS
    assert not csv.isna().any().any()
    assert csv["date"].is_unique
    assert csv["date"].iloc[0] == "2011-01-01"
    assert csv["date"].iloc[-1] == "2012-12-31"
    assert csv["daily_rentals_target"].nunique() == 696

    # All writes are under pytest's disposable temp directory, never an
    # installed Windows application or any pre-existing project home.
    home = tmp_path / "p4-public-bike-project"
    (home / "datasets").mkdir(parents=True)
    (home / "models").mkdir()
    monkeypatch.setattr(storage, "HOME", home)
    monkeypatch.setattr(storage, "DB_PATH", home / "pilotodin.sqlite3")
    storage.init()
    quality._init_tables()
    origin = {"Origin": "http://127.0.0.1:5173"}
    with TestClient(main.app) as client:
        uploaded = client.post(
            "/api/projects",
            files={"file": (FIXTURE.name, source, "text/csv")},
            headers=origin,
        )
        assert uploaded.status_code == 201, uploaded.text
        profile = uploaded.json()["profile"]
        pid = uploaded.json()["id"]
        assert profile["rows"] == 731
        assert profile["columns_count"] == 8
        assert profile["missing_cells"] == 0
        assert profile["duplicate_rows"] == 0
        assert "daily_rentals_target" in profile["target_candidates"]
        project = storage.get_project(pid)
        assert project is not None
        imported_path = Path(project["dataset_path"])
        assert imported_path.is_relative_to(home / "datasets")
        assert imported_path.read_bytes() == source
        frame, version = quality.current_data(pid)
        assert version == 0
        pd.testing.assert_frame_equal(frame, csv)

        review = client.get(
            f"/api/projects/{pid}/target-opportunities",
            params={"expected_version": version},
            headers=origin,
        )
        assert review.status_code == 200, review.text
        ranked = review.json()
        assert ranked["abstained"] is False
        assert ranked["queue_resource_review"]["truncated"] is False
        candidate = next(
            x for x in ranked["suggestions"] + ranked["other_reviewable"]
            if x["column"] == "daily_rentals_target"
        )
        assert candidate["technical_status"] == "reviewable"
        assert candidate["task_hypothesis"] == "regression"
        assert candidate["labelled_rows"] == 731
        assert candidate["missing_labels"] == 0
        assert candidate["safe_to_train_automatically"] is False
        assert candidate["business_relevance"] == "unverified"
        assert candidate["user_context"] is None
        assert ranked["ranking_contract"]["automatic_target_selection"] is False
        assert ranked["ranking_contract"]["business_value_verified"] is False

        inspected = client.get(
            f"/api/projects/{pid}/target-opportunities/inspect",
            params={"expected_version": version, "column": "daily_rentals_target"},
            headers=origin,
        )
        assert inspected.status_code == 200, inspected.text
        manual = inspected.json()
        assert manual["candidate"]["technical_status"] == "reviewable"
        assert manual["candidate"]["task_hypothesis"] == "regression"
        assert manual["training_authorised"] is False
        assert manual["resource_review"]["truncated"] is False

        prep = client.get(
            f"/api/projects/{pid}/preparation",
            params={"target": "daily_rentals_target"},
            headers=origin,
        )
        assert prep.status_code == 200, prep.text
        plan = prep.json()
        assert plan["task"] == "regression"
        assert plan["target"] == "daily_rentals_target"
        assert plan["missing_targets"] == 0
        assert len(plan["available_features"]) == 7
        assert "date" in plan["available_features"]
        assert "daily_rentals_target" not in plan["available_features"]
        assert len(plan["feature_audit"]) == 7
        assert any("time or group validation strategy" in s for s in plan["warnings"])
        # Critical: source PREPARATION does not exclude date automatically.
        # User must choose Time split, date column, before considering a fit.
        assert storage.recent_experiments(pid) == []
        assert list((home / "models").iterdir()) == []
        assert hashlib.sha256(FIXTURE.read_bytes()).hexdigest() == FIXTURE_SHA256
