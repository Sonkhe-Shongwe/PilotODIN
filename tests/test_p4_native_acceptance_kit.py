"""P4-10 synthetic Windows kit self-checks, never native acceptance."""
from __future__ import annotations

import csv
import hashlib
import io
import json
import subprocess
import sys
from pathlib import Path

import pandas as pd
import pytest

from qa.p4_native import generate_fixtures as kit
from backend import target_opportunities


def test_five_generated_cases_are_deterministic_and_screened_safely():
    first = kit.fixture_contents()
    assert first == kit.fixture_contents()
    assert len(first) == 5
    assert set(first) == {f"p4_{x}.csv" for x in kit.CASE_ORDER}
    expectation = {
        "classification": ("classification", False),
        "regression": ("regression", False),
        "rare_class": (None, True),
        "insufficient_labels": (None, True),
        "no_named_target": (None, True),
    }
    for case, (task, abstained) in expectation.items():
        content = first[f"p4_{case}.csv"]
        assert content.startswith(b"account_id,feature,")
        assert b"\r" not in content
        data = pd.read_csv(io.BytesIO(content))
        assert len(data) == kit.ROW_COUNT == 80
        assert not data.columns.duplicated().any()
        assert data["account_id"].nunique() == 40
        assert data["account_id"].notna().sum() == 80
        assert data["account_id"].iloc[0] == "P4-SYNTH-000"
        response = target_opportunities.recommend(data, 0)
        assert response["abstained"] is abstained
        assert response["ranking_contract"]["automatic_target_selection"] is False
        assert "P4-SYNTH-000" not in json.dumps(response)
        if case == "classification":
            assert response["eligible_count"] == 5
            assert len(response["suggestions"]) == 3
            assert len(response["other_reviewable"]) == 2
        if task:
            column = "future_cost" if task == "regression" else "churn"
            item = next(x for x in response["suggestions"] if x["column"] == column)
            assert item["task_hypothesis"] == task
            assert item["review_priority"]["training_authorised"] is False
            rep = item["decision_utility"]["entity_repetition"]["repeated"]
            assert rep[0]["additional_occurrences"] == 40
        else:
            assert response["suggestions"] == []
            if case == "rare_class":
                assert response["blocked_examples"][0]["smallest_class"] == 4
            if case == "insufficient_labels":
                assert response["blocked_examples"][0]["labelled_rows"] == 24
                assert response["blocked_examples"][0]["missing_labels"] == 56
    manifest = kit.manifest_for(first)
    assert manifest["verification_state"] == "UNTESTED"
    assert manifest["synthetic_only"] is True
    assert manifest["sha256"] == {
        filename: hashlib.sha256(data).hexdigest() for filename, data in first.items()
    }


def test_writer_creates_new_only_and_rejects_overwriting(tmp_path):
    destination = tmp_path / "p4-owner-test-synthetic"
    assert kit.create_kit(destination) == destination
    assert (destination / "README.md").is_file()
    assert (destination / "RESULTS_TEMPLATE.md").is_file()
    manifest = json.loads((destination / "MANIFEST.json").read_text("utf-8"))
    for filename, expected in manifest["sha256"].items():
        assert hashlib.sha256((destination / filename).read_bytes()).hexdigest() == expected
    snapshot = {p.name: p.read_bytes() for p in destination.iterdir()}
    with pytest.raises(FileExistsError):
        kit.create_kit(destination)
    assert {p.name: p.read_bytes() for p in destination.iterdir()} == snapshot


def test_record_template_starts_unverified_and_contains_no_false_pass():
    source_dir = Path(kit.__file__).resolve().parent
    record = (source_dir / "RESULTS_TEMPLATE.md").read_text("utf-8")
    guide = (source_dir / "README.md").read_text("utf-8")
    assert "Record status:** UNTESTED" in record
    assert "NOT APPROVED" in record
    assert "P8" in record
    assert "Do not trigger a training experiment" in guide
    assert "verifiable native build/source commit" in guide
