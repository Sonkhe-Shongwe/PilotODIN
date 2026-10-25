"""P0: one real API journey for persistent ML evidence and version safety.

Runs entirely on generated CSV records in a temporary database/data home.
No real insurance data, user project files, hosted CI, or installed app paths.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd
from fastapi.testclient import TestClient

from backend import quality, storage
from backend.main import app


def _dataset() -> bytes:
    n = 80
    df = pd.DataFrame({
        "incident_hour_of_the_day": [(i * 3) % 24 for i in range(n)],
        "number_of_vehicles_involved": [1 + i % 4 for i in range(n)],
        "premium": [400.0 + (i % 17) * 13 for i in range(n)],
        "Region": [
            " Gauteng " if i % 19 == 0
            else "Gauteng" if i % 2 else "Mpumalanga"
            for i in range(n)
        ],
        "fraud_reported": ["Y" if i % 5 == 0 or i % 7 == 0 else "N"
                           for i in range(n)],
    })
    return df.to_csv(index=False).encode("utf-8")


def test_p0_import_train_select_reopen_predict_version_and_project_isolation(
        monkeypatch, tmp_path):
    """A real server-backed train and approval, not a mocked front-end journey."""
    home = tmp_path / "isolated-p0-ml-home"
    (home / "datasets").mkdir(parents=True)
    (home / "models").mkdir()
    monkeypatch.setattr(storage, "HOME", home)
    monkeypatch.setattr(storage, "DB_PATH", home / "pilotodin.sqlite3")
    storage.init()
    client = TestClient(app)
    original = _dataset()

    def import_project(filename):
        response = client.post(
            "/api/projects",
            files={"file": (filename, original, "text/csv")},
        )
        assert response.status_code == 201, response.text
        return response.json()["id"]

    own = import_project("synthetic_claims_A.csv")
    other = import_project("synthetic_claims_B.csv")
    assert own != other
    assert len(client.get("/api/projects").json()) == 2

    body = {
        "target": "fraud_reported",
        "task": "classification",
        "models": ["logistic_regression"],
        "excluded_features": [],
        "split_strategy": "random",
        "acknowledge_random_split": True,
        "acknowledge_feature_risks": True,
        "expected_quality_version": 0,
    }
    started = client.post(f"/api/projects/{own}/experiments", json=body)
    assert started.status_code == 202, started.text
    eid = started.json()["id"]
    # Starlette TestClient completes ordinary FastAPI background tasks before
    # returning control to this synchronous request, including model saving.
    selected_project = client.get(f"/api/projects/{own}").json()
    foreign_project = client.get(f"/api/projects/{other}").json()
    assert eid in [x["id"] for x in selected_project["experiments"]]
    assert eid not in [x["id"] for x in foreign_project["experiments"]]

    completed = client.get(f"/api/experiments/{eid}")
    assert completed.status_code == 200, completed.text
    trained = completed.json()
    assert trained["status"] == "completed", trained.get("error")
    assert trained["dataset_version"] == trained["current_version"] == 0
    assert trained["is_stale"] is False
    assert trained["project_id"] == own
    assert trained["selected_model"] is None
    assert "logistic_regression" in {
        row["key"] for row in trained["results"]["models"]
        if row["status"] == "ready"
    }
    assert (home / "models" / eid / "logistic_regression.joblib").is_file()
    assert (home / "models" / eid / "test_set.joblib").is_file()

    chosen = client.post(f"/api/experiments/{eid}/select",
                         json={"model_key": "logistic_regression"})
    assert chosen.status_code == 200, chosen.text
    first_metrics = chosen.json()["final_results"]
    assert chosen.json()["selected_model"] == "logistic_regression"
    assert first_metrics["sample_count"] == trained["results"]["test_rows"]
    assert "baseline_test_metric" in first_metrics

    # Simulate re-opening the saved experiment through a freshly constructed
    # API client. Final metrics and selection must be read from SQLite rather
    # than recomputed or silently replaced by a different model.
    reopened = TestClient(app).get(f"/api/experiments/{eid}")
    assert reopened.status_code == 200, reopened.text
    again = reopened.json()
    assert again["selected_model"] == "logistic_regression"
    assert again["final_results"] == first_metrics
    assert again["results"] == trained["results"]
    assert again["is_stale"] is False

    valid = {
        "incident_hour_of_the_day": 12,
        "number_of_vehicles_involved": 1,
        "premium": 465,
        "Region": "Gauteng",
    }
    prediction = client.post(f"/api/experiments/{eid}/predict",
                             json={"values": valid})
    assert prediction.status_code == 200, prediction.text
    assert prediction.json()["dataset_version"] == 0
    assert prediction.json()["prediction"] in ("N", "Y")
    assert prediction.json()["experimental_only"] is True

    for invalid, field in [
        ({**valid, "incident_hour_of_the_day": 25}, "incident_hour_of_the_day"),
        ({**valid, "number_of_vehicles_involved": -1}, "number_of_vehicles_involved"),
        ({**valid, "number_of_vehicles_involved": 1.5}, "number_of_vehicles_involved"),
    ]:
        rejected = client.post(f"/api/experiments/{eid}/predict",
                               json={"values": invalid})
        assert rejected.status_code == 422, rejected.text
        assert field in rejected.json()["detail"]

    # Version changes must use the real explicit reviewed Quality receipt.
    # The original uploaded source remains immutable while ML becomes stale.
    issues = quality.snapshot(own)["issues"]
    whitespace = next(x for x in issues if x["kind"] == "whitespace"
                      and x["column"] == "Region")
    proposed = client.post(f"/api/projects/{own}/quality/proposals", json={
        "operation": "approve", "expected_version": 0, "issue_id": whitespace["id"]
    })
    assert proposed.status_code == 200, proposed.text
    receipt = proposed.json()
    assert receipt["changed_cells"] > 0
    approved = client.post(f"/api/projects/{own}/quality/commit", json={
        "proposal_id": receipt["proposal_id"],
        "proposal_hash": receipt["proposal_hash"],
    })
    assert approved.status_code == 200, approved.text
    assert approved.json()["version"] == 1
    assert quality.current_version(other) == 0
    assert Path(storage.get_project(own)["dataset_path"]).read_bytes() == original

    historical = client.get(f"/api/experiments/{eid}")
    assert historical.status_code == 200
    hist = historical.json()
    assert hist["is_stale"] is True
    assert hist["dataset_version"] == 0 and hist["current_version"] == 1
    assert hist["final_results"] == first_metrics
    assert hist["selected_model"] == "logistic_regression"

    blocked = client.post(f"/api/experiments/{eid}/predict",
                          json={"values": valid})
    assert blocked.status_code == 409
    assert "older dataset version" in blocked.json()["detail"]
    assert client.post(f"/api/experiments/{eid}/select",
                       json={"model_key": "logistic_regression"}).status_code == 409
    assert client.post(f"/api/projects/{own}/experiments",
                       json=body).status_code == 409
    assert len(client.get(f"/api/projects/{own}").json()["experiments"]) == 1
    assert client.get(f"/api/projects/{other}").json()["experiments"] == []
    assert Path(storage.get_project(other)["dataset_path"]).read_bytes() == original
