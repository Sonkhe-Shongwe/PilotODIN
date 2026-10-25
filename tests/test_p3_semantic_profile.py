"""P3 semantic hypotheses: observed-vs-inferred boundaries on isolated synthetic data."""
from __future__ import annotations

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from backend import main, semantic_profile, storage


def test_insurance_is_a_header_hypothesis_not_confirmed_business_meaning():
    data = pd.DataFrame({
        "claim_id": [f"C{i:03}" for i in range(12)],
        "policy_number": ["P1", "P1", "P2", "P2"] * 3,
        "incident_date": [f"2026-01-{i+1:02}" for i in range(12)],
        "claim_amount": [100 + i for i in range(12)],
        "fraud_reported": ["Y", "N"] * 6,
    })
    out = semantic_profile.overview(data, 4)
    assert out["version"] == 4
    assert out["domain"]["state"] == "hypothesis"
    assert out["domain"]["label"] == "Insurance"
    assert out["grain"]["identifier_column"] == "claim_id"
    assert out["grain"]["state"] == "hypothesis"
    hints={x["column"]:{h["role"] for h in x["hypotheses"]} for x in out["fields"]}
    assert "possible_identifier" in hints["claim_id"]
    assert "possible_time_field" in hints["incident_date"]
    assert "possible_monetary_measure" in hints["claim_amount"]
    assert "possible_outcome" in hints["fraud_reported"]
    assert "unverified" in out["inferred"].lower()
    assert "automatic target selection" in out["note"]


def test_retail_is_tentative_and_does_not_claim_order_grain():
    data=pd.DataFrame({
        "order_id":["A","A","B","B","C","C"],
        "product_sku":["XX","YY"]*3,
        "order_price":[10,20,30,40,50,60],
    })
    out=semantic_profile.overview(data, 0)
    assert out["domain"]["label"] == "Retail"
    assert out["domain"]["state"] == "hypothesis"
    assert out["grain"]["state"] == "unknown"
    assert out["grain"]["identifier_column"] is None
    assert "record grain" in out["grain"]["reason"].lower()


def test_no_semantic_signal_abstains_without_inventing_domain_or_target():
    data=pd.DataFrame({"alpha":[1,1,2,2],"beta":["red","blue","red","blue"]})
    out=semantic_profile.overview(data, 2)
    assert out["domain"]["state"]=="unknown"
    assert out["domain"]["label"] is None
    assert out["grain"]["state"]=="unknown"
    assert out["fields"] == []
    assert "context" in out["domain"]["reason"].lower()
    assert out["version"] == 2


def test_single_composite_header_is_not_independent_domain_evidence():
    data=pd.DataFrame({"product_sku":["A","B","C"], "value":[1,2,3]})
    out=semantic_profile.overview(data,0)
    assert out["domain"]["state"]=="unknown"
    assert out["domain"]["label"] is None


def test_conflicting_domain_clues_abstain_instead_of_ranking_by_guesswork():
    data=pd.DataFrame({
        "order_id":range(8), "product_sku":["A","B"]*4,
        "account_id":range(8), "loan_balance":[100,200]*4,
    })
    out=semantic_profile.overview(data, 0)
    assert out["domain"]["state"]=="unknown"
    assert "multiple domains" in out["domain"]["reason"]
    assert out["grain"]["state"]=="unknown"  # Several unique IDs.


def test_all_missing_and_empty_rows_have_no_false_entity_claim():
    data=pd.DataFrame({"incident_date":[None]*8,"notes":[None]*8})
    out=semantic_profile.overview(data, 7)
    assert out["domain"]["state"]=="unknown"
    assert out["grain"]["state"]=="unknown"
    assert out["rows"] == 8
    assert out["fields"]
    assert all(f["observed"]["missing"]==8 for f in out["fields"])
    empty=semantic_profile.overview(pd.DataFrame({"record_id":[]}), 1)
    assert empty["rows"] == 0
    assert empty["grain"]["state"]=="unknown"


def test_response_is_bounded_and_never_exports_sample_values():
    data=pd.DataFrame({
        **{f"field_{i}": [f"private_{i}_one",f"private_{i}_two"] for i in range(100)},
        "customer_id": ["C1","C2"],
    })
    out=semantic_profile.overview(data, 0)
    assert out["columns_total"] == 101
    assert out["columns_examined"] == semantic_profile.MAX_FIELDS
    assert out["fields"] == []  # No high-risk heuristics guessed for arbitrary fields.
    raw=str(out)
    assert "private_24_one" not in raw
    assert "private_0_two" not in raw


def test_duplicate_column_names_are_rejected_without_state_mutation():
    data=pd.DataFrame([[1,2]],columns=["x","x"])
    with pytest.raises(ValueError,match="unique column"):
        semantic_profile.overview(data,0)


def test_semantic_api_is_project_scoped_and_version_pinned(tmp_path, monkeypatch):
    home=tmp_path/"semantic-fixture"
    (home/"datasets").mkdir(parents=True)
    (home/"models").mkdir()
    monkeypatch.setattr(storage,"HOME",home)
    monkeypatch.setattr(storage,"DB_PATH",home/"pilotodin.sqlite3")
    storage.init()
    pid=storage.save_project("Synthetic","fixture.csv",".csv",home/"datasets"/"fixture.csv",{"rows":6})
    data=pd.DataFrame({"claim_id":["X1","X2","X3"],"premium_cost":[3,4,5],"policy_code":["P1","P2","P3"]})
    # No writes, imports or Model Lab jobs on the test path.
    monkeypatch.setattr(main.quality,"current_data",lambda project_id:
                        (data,3) if project_id==pid else (_ for _ in ()).throw(AssertionError("wrong project")))
    client=TestClient(main.app)
    ok=client.get(f"/api/projects/{pid}/semantics?expected_version=3")
    assert ok.status_code==200,ok.text
    assert ok.json()["version"]==3
    assert ok.json()["domain"]["label"]=="Insurance"
    assert client.get(f"/api/projects/{pid}/semantics?expected_version=2").status_code==409
    assert client.get(f"/api/projects/{pid}/semantics").status_code==422
    assert client.get("/api/projects/unknown/semantics?expected_version=3").status_code==404
    assert client.get(f"/api/projects/{pid}/semantics?expected_version=-1").status_code==422
    assert client.get(f"/api/projects/{pid}/semantics?expected_version=3",
                      headers={"Origin":"https://external.example"}).status_code==403
