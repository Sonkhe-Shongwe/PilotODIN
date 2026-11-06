"""P3-02 user-described business metadata, not independently verified facts."""
from __future__ import annotations

import pandas as pd
from fastapi.testclient import TestClient
from backend import main, storage


def fixture(tmp_path, monkeypatch):
    home = tmp_path / "p3-business-context"
    (home / "datasets").mkdir(parents=True)
    (home / "models").mkdir()
    monkeypatch.setattr(storage, "HOME", home)
    monkeypatch.setattr(storage, "DB_PATH", home / "pilotodin.sqlite3")
    storage.init()
    ids = [
        storage.save_project(label, label + ".csv", ".csv",
                             home / "datasets" / (label + ".csv"), {"rows": 5})
        for label in ("ProjectA", "ProjectB")
    ]
    frame = pd.DataFrame({
        "claim_id": ["A", "B", "C", "D", "E"],
        "claim_amount": [10, 20, 30, 40, 50],
        "policy_number": ["P1", "P1", "P2", "P2", "P3"],
    })
    monkeypatch.setattr(main.quality, "current_data",
                        lambda project_id: (frame, 3) if project_id in ids else
                        (_ for _ in ()).throw(AssertionError("wrong project")))
    return TestClient(main.app), ids


def payload(version=3):
    return {
        "expected_version": version,
        "domain_description": "Insurance claim processing records described by the owner",
        "record_grain_description": "One submitted claim per synthetic record",
        "field_definitions": [
            {"column": "claim_amount", "meaning": "Amount requested by the claimant"}
        ],
    }


def test_save_reload_preserves_original_hypotheses(tmp_path, monkeypatch):
    client, (pid, _) = fixture(tmp_path, monkeypatch)
    path = f"/api/projects/{pid}/semantics?expected_version=3"
    before = client.get(path)
    assert before.status_code == 200
    assert before.json()["user_context"] is None
    result = client.post(f"/api/projects/{pid}/semantic-business-context",
                         json=payload())
    assert result.status_code == 200, result.text
    assert result.json()["verification_state"] == "user_described_not_independently_verified"
    after = client.get(path).json()
    assert after["domain"] == before.json()["domain"]
    assert after["grain"] == before.json()["grain"]
    assert after["user_context"]["field_definitions"][0]["column"] == "claim_amount"
    assert storage.semantic_context(pid, 3)["updated_at"]


def test_isolated_by_project_and_quality_version(tmp_path, monkeypatch):
    client, (one, two) = fixture(tmp_path, monkeypatch)
    assert client.post(f"/api/projects/{one}/semantic-business-context",
                       json=payload()).status_code == 200
    assert storage.semantic_context(two, 3) is None
    assert storage.semantic_context(one, 2) is None
    assert client.get(f"/api/projects/{two}/semantics?expected_version=3").json()["user_context"] is None
    assert client.get(f"/api/projects/{one}/semantics?expected_version=2").status_code == 409
    assert client.post(f"/api/projects/{one}/semantic-business-context",
                       json=payload(2)).status_code == 409


def test_changes_require_explicit_post_and_do_not_train(tmp_path, monkeypatch):
    client, (pid, _) = fixture(tmp_path, monkeypatch)
    assert storage.recent_experiments(pid) == []
    assert client.get(f"/api/projects/{pid}/semantics?expected_version=3").status_code == 200
    assert storage.semantic_context(pid, 3) is None
    path = f"/api/projects/{pid}/semantic-business-context"
    assert client.post(path, json=payload()).status_code == 200
    changed = payload()
    changed["domain_description"] = "Insurance case logs independently described by the owner"
    assert client.post(path, json=changed).status_code == 200
    assert storage.semantic_context(pid, 3)["domain_description"] == changed["domain_description"]
    assert storage.recent_experiments(pid) == []


def test_local_origin_and_missing_project_protection(tmp_path, monkeypatch):
    client, (pid, _) = fixture(tmp_path, monkeypatch)
    path = f"/api/projects/{pid}/semantic-business-context"
    assert client.post(path, json=payload(),
                       headers={"Origin": "https://external.example"}).status_code == 403
    assert client.post("/api/projects/missing/semantic-business-context",
                       json=payload()).status_code == 404
    assert client.get(f"/api/projects/{pid}/semantics?expected_version=3",
                      headers={"Origin": "https://external.example"}).status_code == 403
    assert storage.semantic_context(pid, 3) is None


def test_reject_invalid_or_duplicate_definitions_without_writes(tmp_path, monkeypatch):
    client, (pid, _) = fixture(tmp_path, monkeypatch)
    path = f"/api/projects/{pid}/semantic-business-context"
    bad = [
        {"expected_version": 3},
        {**payload(), "domain_description": "too short"},
        {**payload(), "field_definitions": [{"column": "not_a_field", "meaning": "Defined by the dataset owner"}]},
        {**payload(), "field_definitions": [
            {"column": "claim_id", "meaning": "Identifies one claim record"},
            {"column": "claim_id", "meaning": "Repeats the same field name"}]},
        {**payload(), "field_definitions": [
            {"column": "claim_id", "meaning": "Enough characters"}] * 9},
        {**payload(), "field_definitions": [
            {"column": "claim_id", "meaning": "x"}]},
    ]
    for value in bad:
        result = client.post(path, json=value)
        assert result.status_code == 422, result.text
        assert storage.semantic_context(pid, 3) is None


def test_one_section_only_is_valid(tmp_path, monkeypatch):
    client, (pid, _) = fixture(tmp_path, monkeypatch)
    result = client.post(f"/api/projects/{pid}/semantic-business-context",
                         json={"expected_version": 3,
                               "field_definitions": [
                                   {"column": "claim_id",
                                    "meaning": "This identifies a submitted claim"}]})
    assert result.status_code == 200, result.text
    assert result.json()["domain_description"] == ""
    assert result.json()["field_definitions"][0]["column"] == "claim_id"
