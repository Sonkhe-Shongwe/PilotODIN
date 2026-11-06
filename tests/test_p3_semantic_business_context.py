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

def test_actual_approved_quality_version_change_does_not_reuse_prior_semantic_context(
    tmp_path, monkeypatch
):
    """Real proposal/commit path: a human description must stay on its old version."""
    from pathlib import Path
    from backend import quality

    home = tmp_path / "p3-disposable-version-transition"
    (home / "datasets").mkdir(parents=True)
    (home / "models").mkdir()
    monkeypatch.setattr(storage, "HOME", home)
    monkeypatch.setattr(storage, "DB_PATH", home / "pilotodin.sqlite3")
    storage.init()
    quality._init_tables()
    client = TestClient(main.app)

    regions = (
        ["Mpumalanga"] * 20
        + ["Mpimilanga"] * 3
        + [" Mpumalanga "] * 2
        + ["Gauteng"] * 11
    )
    original = (
        "claim_id,Region,claim_amount,policy_number\\n"
        + "".join(
            f"C{i:03d},{region},{100 + i},P{i % 4}\\n"
            for i, region in enumerate(regions)
        )
    ).encode("utf-8")
    imported = client.post(
        "/api/projects",
        files={"file": ("synthetic_p3_version.csv", original, "text/csv")},
    )
    assert imported.status_code == 201, imported.text
    pid = imported.json()["id"]
    original_path = Path(storage.get_project(pid)["dataset_path"])
    assert original_path.read_bytes() == original
    assert quality.current_version(pid) == 0

    saved = client.post(
        f"/api/projects/{pid}/semantic-business-context",
        json={**payload(0), "domain_description": "Version zero synthetic insurance notes"},
    )
    assert saved.status_code == 200, saved.text
    assert saved.json()["verification_state"] == "user_described_not_independently_verified"
    before = client.get(f"/api/projects/{pid}/semantics?expected_version=0")
    assert before.status_code == 200, before.text
    assert before.json()["user_context"]["domain_description"] == (
        "Version zero synthetic insurance notes"
    )

    # Review the exact synthetic whitespace correction, then explicitly approve
    # only its one-time receipt. Legacy direct/autopilot writes are not permitted.
    preview = client.post(
        f"/api/projects/{pid}/quality/proposals",
        json={"operation": "autopilot", "expected_version": 0},
    )
    assert preview.status_code == 200, preview.text
    reviewed = preview.json()
    assert reviewed["changed_cells"] == 2
    assert reviewed["expected_version"] == 0
    committed = client.post(
        f"/api/projects/{pid}/quality/commit",
        json={
            "proposal_id": reviewed["proposal_id"],
            "proposal_hash": reviewed["proposal_hash"],
        },
    )
    assert committed.status_code == 200, committed.text
    assert committed.json()["version"] == 1
    assert quality.current_version(pid) == 1
    assert original_path.read_bytes() == original

    # A stale GET or Save cannot make version-0 owner notes appear current.
    assert client.get(f"/api/projects/{pid}/semantics?expected_version=0").status_code == 409
    assert client.post(
        f"/api/projects/{pid}/semantic-business-context",
        json=payload(0),
    ).status_code == 409
    current = client.get(f"/api/projects/{pid}/semantics?expected_version=1")
    assert current.status_code == 200, current.text
    assert current.json()["user_context"] is None
    assert storage.semantic_context(pid, 0)["domain_description"] == (
        "Version zero synthetic insurance notes"
    )
    assert storage.semantic_context(pid, 1) is None

    # Version 1 may get new explicit notes, never a silent migration of v0.
    next_notes = client.post(
        f"/api/projects/{pid}/semantic-business-context",
        json={**payload(1), "domain_description": "Separate version one insurance notes"},
    )
    assert next_notes.status_code == 200, next_notes.text
    assert storage.semantic_context(pid, 1)["domain_description"] == (
        "Separate version one insurance notes"
    )
    assert storage.semantic_context(pid, 0)["domain_description"] == (
        "Version zero synthetic insurance notes"
    )
    assert original_path.read_bytes() == original

