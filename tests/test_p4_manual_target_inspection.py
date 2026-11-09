"""P4-12 exact manual target review beyond bounded queues, synthetic only."""
from __future__ import annotations

import json

import pandas as pd
from fastapi.testclient import TestClient

from backend import main, storage, target_opportunities


def synthetic_frame() -> pd.DataFrame:
    frame = pd.DataFrame({
        "account_id": [f"PRIVATE-SYNTH-{i // 2}" for i in range(80)],
        "feature": [i % 9 for i in range(80)],
    })
    for j in range(22):
        frame[f"outcome_{j:02d}"] = ["Y", "N"] * 40
    for j in range(6):
        frame[f"rare_outcome_{j:02d}"] = ["Y"] * 76 + ["N"] * 4
    return frame


def test_p4_12_selected_column_outside_caps_is_screened_without_reordering():
    frame = synthetic_frame()
    original = frame.copy(deep=True)
    before = target_opportunities.recommend(frame, 3)
    assert len(before["suggestions"]) == 3
    assert len(before["other_reviewable"]) == 12
    assert before["omitted_reviewable_count"] == 7
    assert before["blocked_count"] == 6
    assert len(before["blocked_examples"]) == 5
    reviewed = target_opportunities.inspect_manual_target(frame, 3, "outcome_21")
    assert reviewed["version"] == 3
    assert reviewed["column"] == "outcome_21"
    assert reviewed["inspection_scope"] == "single_manual_column_not_ranked_or_approved"
    assert reviewed["name_hint"] == "supported_outcome_name"
    assert reviewed["training_authorised"] is False
    c = reviewed["candidate"]
    assert c["technical_status"] == "reviewable"
    assert c["task_hypothesis"] == "classification"
    assert "review_priority" not in c
    assert c["safe_to_train_automatically"] is False
    assert c["decision_utility"]["verified_label_origin"] is False
    assert c["decision_utility"]["verified_prediction_time"] is False
    assert c["decision_utility"]["measured_decision_benefit"] is False
    assert c["decision_utility"]["entity_repetition"]["repeated"][0]["additional_occurrences"] == 40
    blocked = target_opportunities.inspect_manual_target(frame, 3, "rare_outcome_05")
    assert blocked["candidate"]["technical_status"] == "blocked"
    assert any("at least 6" in item for item in blocked["candidate"]["blockers"])
    assert blocked["training_authorised"] is False
    unrelated = target_opportunities.inspect_manual_target(frame, 3, "account_id")
    assert unrelated["name_hint"] == "no_supported_outcome_name"
    assert unrelated["candidate"]["technical_status"] == "blocked"
    assert unrelated["candidate"]["task_hypothesis"] is None
    assert any("No supported outcome-name clue" in s for s in unrelated["candidate"]["blockers"])
    assert any("identifier" in s for s in unrelated["candidate"]["blockers"])
    assert "PRIVATE-SYNTH-0" not in json.dumps(reviewed)
    assert "PRIVATE-SYNTH-0" not in json.dumps(blocked)
    assert "PRIVATE-SYNTH-0" not in json.dumps(unrelated)
    assert frame.equals(original)
    assert target_opportunities.recommend(frame, 3) == before


def test_p4_12_local_version_project_and_invalid_column_rejection(tmp_path, monkeypatch):
    home = tmp_path / "p4-12-only"
    (home / "datasets").mkdir(parents=True)
    (home / "models").mkdir()
    monkeypatch.setattr(storage, "HOME", home)
    monkeypatch.setattr(storage, "DB_PATH", home / "pilotodin.sqlite3")
    storage.init()
    ids = [
        storage.save_project(n, n + ".csv", ".csv", home / "datasets" / (n + ".csv"), {"rows": 80})
        for n in ("A", "B")
    ]
    version = {ids[0]: 3, ids[1]: 0}
    frames = {ids[0]: synthetic_frame(), ids[1]: pd.DataFrame({
        "account_id": ["B-" + str(i) for i in range(80)],
        "future_cost": [float(i + 100) for i in range(80)],
    })}
    monkeypatch.setattr(main.quality, "current_data",
                        lambda pid: (frames[pid], version[pid]))
    client = TestClient(main.app)
    a, b = ids
    path = f"/api/projects/{a}/target-opportunities/inspect"
    good = client.get(path, params={"expected_version": 3, "column": "outcome_21"})
    assert good.status_code == 200, good.text
    assert good.json()["project_id"] == a
    assert good.json()["candidate"]["column"] == "outcome_21"
    assert good.json()["training_authorised"] is False
    assert client.get(path, params={"expected_version": 2, "column": "outcome_21"}).status_code == 409
    assert client.get(path, params={"column": "outcome_21"}).status_code == 422
    assert client.get(path, params={"expected_version": 3}).status_code == 422
    assert client.get(path, params={"expected_version": 3, "column": "not_here"}).status_code == 422
    assert client.get(path, params={"expected_version": 3, "column": "a" * 201}).status_code == 422
    assert client.get(path, params={"expected_version": -1, "column": "outcome_21"}).status_code == 422
    assert client.get(path, params={"expected_version": 3, "column": "outcome_21"},
                      headers={"Origin": "https://outside.example"}).status_code == 403
    assert client.get(
        "/api/projects/missing/target-opportunities/inspect",
        params={"expected_version": 3, "column": "outcome_21"},
    ).status_code == 404
    assert client.get(
        f"/api/projects/{b}/target-opportunities/inspect",
        params={"expected_version": 0, "column": "outcome_21"},
    ).status_code == 422
    assert client.get(
        f"/api/projects/{b}/target-opportunities/inspect",
        params={"expected_version": 0, "column": "future_cost"},
    ).status_code == 200
    version[a] = 4
    assert client.get(path, params={"expected_version": 3, "column": "outcome_21"}).status_code == 409
    now = client.get(path, params={"expected_version": 4, "column": "outcome_21"})
    assert now.status_code == 200
    assert now.json()["candidate"]["quality_version"] == 4
    assert storage.target_contexts(a, 3) == {}
    assert storage.target_contexts(b, 0) == {}
    assert storage.recent_experiments(a) == []
    assert storage.recent_experiments(b) == []


def test_p4_12_user_descriptions_do_not_promote_or_verify_arbitrary_field():
    frame = synthetic_frame()
    text = {
        "outcome_21": {
            "target_column": "outcome_21",
            "decision_action": "Owner described an action",
            "prediction_moment": "Before the labelled event",
            "label_source": "Owner-described record, not independently verified",
            "outcome_definition": "Hypothetical outcome",
            "updated_at": "2026-11-09T00:00:00Z",
        },
        "feature": {
            "target_column": "feature",
            "decision_action": "Owner calls this a new goal",
            "prediction_moment": "Unverified",
            "label_source": "Unverified",
            "outcome_definition": "Unverified",
            "updated_at": "2026-11-09T00:00:00Z",
        },
    }
    named = target_opportunities.inspect_manual_target(frame, 1, "outcome_21", text)
    assert named["candidate"]["user_context"]["verification_state"] == (
        "user_described_not_independently_verified"
    )
    assert named["candidate"]["decision_utility"]["verified_label_origin"] is False
    plain = target_opportunities.inspect_manual_target(frame, 1, "feature", text)
    assert plain["name_hint"] == "no_supported_outcome_name"
    assert plain["candidate"]["technical_status"] == "blocked"
    assert plain["candidate"]["business_relevance"] == "user_described_unverified"
    assert plain["candidate"]["decision_utility"]["training_authorised"] is False
