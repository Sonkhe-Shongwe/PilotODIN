"""v0.2B Increment 1: quality engine acceptance and adversarial tests."""
from __future__ import annotations

import io
import os
import sys
import tempfile
from pathlib import Path

# The pre-existing tests configure the same storage root before importing the app.
# Keep this test file self-contained if run alone.
os.environ.setdefault("PILOTODIN_HOME", tempfile.mkdtemp(prefix="pilotodin-quality-") )
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient
from tests.quality_compat_client import LegacyQualityClient
from backend.main import app
from backend import storage

client = LegacyQualityClient(TestClient(app))


def sample_frame():
    n=36
    values=["Mpumalanga"]*20+["Mpimilanga"]*3+[" Mpumalanga "]*2+["Gauteng"]*11
    return pd.DataFrame({
        "CustomerID": [f"00{i:03}" for i in range(n)],
        "Province":values,
        "Amount": [float(100 + i % 7) for i in range(35)] + [1200.0],
        "Segment": ["Retail"]*30+["Corporate"]*4+[None]*2,
    })


def upload(frame=None):
    if frame is None: frame=sample_frame()
    b=frame.to_csv(index=False).encode()
    r=client.post("/api/projects",files={"file":("quality.csv",b,"text/csv")})
    assert r.status_code==201,r.text
    return r.json()["id"],b


def snap(pid):
    r=client.get(f"/api/projects/{pid}/quality")
    assert r.status_code==200, r.text
    return r.json()


def issue_id(state, kind, column=None):
    return next(x["id"] for x in state["issues"] if x["kind"]==kind and (column is None or x["column"]==column))


def autopilot(pid, version):
    return client.post(f"/api/projects/{pid}/quality/autopilot",json={"expected_version":version})


def decide(pid, version, id, value="approve"):
    return client.post(f"/api/projects/{pid}/quality/decisions",json={"expected_version":version,"issue_id":id,"decision":value})


def test_issue_discovery_and_classification():
    pid,_=upload()
    view=snap(pid)
    assert view["version"]==0
    assert view["rows"]==36
    assert view["summary"]["automatic_available"]==1
    assert any(x["kind"]=="missing" and x["column"]=="Segment" and x["affected_rows"]==2 for x in view["issues"])
    assert any(x["kind"]=="spelling" and x["column"]=="Province" for x in view["issues"])
    assert any(x["kind"]=="outliers" for x in view["issues"])
    assert not any(x["automatic"] and x["kind"]!="whitespace" for x in view["issues"])
    assert snap(pid)["version"]==0  # GET is read-only with respect to dataset versions


def test_narrow_autopilot_and_idempotence():
    pid, original = upload()
    before = snap(pid)
    r=autopilot(pid,before["version"])
    assert r.status_code==200,r.text
    data=r.json()
    assert data["count"]==1 and data["applied"][0]["kind"]=="trim_whitespace"
    v=snap(pid)
    assert v["version"]==1 and v["summary"]["applied_actions"]==1
    assert not any(x["kind"]=="whitespace" and x["column"]=="Province" for x in v["issues"])
    # Spelling is not silently changed.
    assert any(x["kind"]=="spelling" for x in v["issues"])
    assert autopilot(pid,v["version"]).json()["count"]==0
    assert Path(storage.get_project(pid)["dataset_path"]).read_bytes()==original


def test_approval_preview_undo_and_redo_with_restore():
    pid,_=upload()
    s=snap(pid)
    auto=autopilot(pid,s["version"]).json()
    a_id=auto["applied"][0]["id"]
    state=snap(pid)
    typo_id=issue_id(state,"spelling","Province")
    preview=client.get(f"/api/projects/{pid}/quality/preview",params={"issue_id":typo_id,"limit":2}).json()
    assert preview["total_matching_rows"]==3
    assert preview["rows"][0]["working"]["Province"]=="Mpimilanga"
    assert preview["rows"][0]["proposed"]["Province"]=="Mpumalanga"
    approved=decide(pid,1,typo_id).json()
    assert approved["version"]==2 and approved["applied"] is True
    correction_id=approved["action"]["id"]
    assert snap(pid)["version"]==2
    assert not any(x["kind"]=="spelling" for x in snap(pid)["issues"])
    res=client.post(f"/api/projects/{pid}/quality/undo",json={"expected_version":2,"action_id":correction_id})
    assert res.status_code==200 and res.json()["version"]==3
    assert any(x["kind"]=="spelling" for x in snap(pid)["issues"])
    history=client.get(f"/api/projects/{pid}/quality/history").json()
    assert any(x["id"]==a_id and x["active"] for x in history["actions"])
    assert any(x["id"]==correction_id and not x["active"] for x in history["actions"])
    redo=client.post(f"/api/projects/{pid}/quality/restore",json={"expected_version":3,"target_version":2})
    assert redo.status_code==200 and redo.json()["version"]==4
    assert not any(x["kind"]=="spelling" for x in snap(pid)["issues"])


def test_undo_first_transformation_preserves_independent_later_action():
    pid,_=upload()
    auto=autopilot(pid,0).json()
    first_id=auto["applied"][0]["id"]
    issue=issue_id(snap(pid),"spelling","Province")
    approved=decide(pid,1,issue).json()
    assert approved["version"]==2
    undo=client.post(f"/api/projects/{pid}/quality/undo",json={"expected_version":2,"action_id":first_id})
    assert undo.status_code==200,undo.text
    assert snap(pid)["version"]==3
    assert any(x["kind"]=="whitespace" for x in snap(pid)["issues"])
    assert not any(x["kind"]=="spelling" and x.get("proposal",{}).get("from")=="Mpimilanga" for x in snap(pid)["issues"])
    # User opted out of this automatic correction, so it must not reapply.
    assert autopilot(pid,3).json()["count"]==0


def test_undo_conflict_for_dependent_transformations():
    frame=sample_frame()
    frame.loc[20:22,"Province"]=" Mpimilanga "
    pid,_=upload(frame)
    auto=autopilot(pid,0).json()
    first_id=auto["applied"][0]["id"]
    typo=issue_id(snap(pid),"spelling","Province")
    assert decide(pid,1,typo).status_code==200
    # Removing the trim step means the later correction would now match 0 rows.
    r=client.post(f"/api/projects/{pid}/quality/undo",json={"expected_version":2,"action_id":first_id})
    assert r.status_code==409,r.text
    assert snap(pid)["version"]==2


def test_rejected_proposal_persists_and_cannot_apply_twice():
    pid,_=upload()
    s=snap(pid)
    typo=issue_id(s,"spelling","Province")
    r=decide(pid,0,typo,"reject")
    assert r.status_code==200 and r.json()["version"]==0
    candidate=next(x for x in snap(pid)["issues"] if x["id"]==typo)
    assert candidate["decision"]=="rejected"
    assert decide(pid,0,typo,"reject").status_code==409


def test_explicit_reapproval_after_rejection_or_undo():
    pid,_=upload()
    typo=issue_id(snap(pid),"spelling","Province")
    assert decide(pid,0,typo,"reject").status_code==200
    # The user's explicit new approval supersedes a prior refusal.
    approved=decide(pid,0,typo,"approve")
    assert approved.status_code==200
    act=approved.json()["action"]["id"]
    assert client.post(f"/api/projects/{pid}/quality/undo",json={"expected_version":1,"action_id":act}).status_code==200
    assert snap(pid)["version"]==2
    assert decide(pid,2,typo,"approve").status_code==200
    assert snap(pid)["version"]==3


def test_reject_non_executable_action_and_invalid_input():
    pid,_=upload()
    s=snap(pid)
    missing=issue_id(s,"missing","Segment")
    r=decide(pid,0,missing)
    assert r.status_code==422
    assert snap(pid)["version"]==0
    assert decide(pid,0,missing,"fabricate").status_code==422
    assert client.get(f"/api/projects/{pid}/quality/preview",params={"limit":201}).status_code==422


def test_stale_version_approval_blocked():
    pid,_=upload()
    typo=issue_id(snap(pid),"spelling","Province")
    assert autopilot(pid,0).status_code==200
    assert decide(pid,0,typo,"reject").status_code==409
    assert autopilot(pid,0).status_code==409
    assert snap(pid)["version"]==1


def test_restore_previous_version_and_no_unwanted_reauto():
    pid,_=upload()
    a=autopilot(pid,0).json()
    assert a["version"]==1
    r=client.post(f"/api/projects/{pid}/quality/restore",json={"expected_version":1,"target_version":0})
    assert r.status_code==200 and r.json()["version"]==2
    assert any(x["kind"]=="whitespace" for x in snap(pid)["issues"])
    assert autopilot(pid,2).json()["count"]==0
    history=client.get(f"/api/projects/{pid}/quality/history").json()
    assert [v["version"] for v in history["versions"]]==[0,1,2]


def test_identifier_leading_zero_preserved_in_quality_preview():
    pid,_=upload()
    pre=client.get(f"/api/projects/{pid}/quality/preview").json()
    assert pre["rows"][0]["original"]["CustomerID"]=="00000"
    assert pre["rows"][0]["working"]["CustomerID"]=="00000"
    assert not any(x["column"]=="CustomerID" and x["automatic"] for x in snap(pid)["issues"])


def test_ambiguous_date_and_duplicate_detections_remain_review_only():
    frame=sample_frame()
    frame["InvoiceDate"]=["03/04/2025"]*36
    frame.loc[35]=frame.loc[34].copy()
    pid,_=upload(frame)
    s=snap(pid)
    assert any(x["kind"]=="ambiguous_dates" for x in s["issues"])
    assert any(x["kind"]=="exact_duplicates" for x in s["issues"])
    assert not any(x["kind"] in ("exact_duplicates","ambiguous_dates") and x["automatic"] for x in s["issues"])


def test_source_tampering_blocks_replay():
    pid,_=upload()
    assert snap(pid)["version"]==0
    path=Path(storage.get_project(pid)["dataset_path"])
    path.write_bytes(path.read_bytes()+b"\n")
    r=client.get(f"/api/projects/{pid}/quality")
    assert r.status_code==409
    assert "changed" in r.json()["detail"]


def test_restart_persists_versions_and_decisions():
    pid,_=upload()
    assert autopilot(pid,0).json()["version"]==1
    from fastapi.testclient import TestClient
    with TestClient(app) as fresh:
        assert fresh.get(f"/api/projects/{pid}/quality").json()["version"]==1
        assert len(fresh.get(f"/api/projects/{pid}/quality/history").json()["actions"])==1


def test_unknown_project_does_not_create_state():
    assert client.get("/api/projects/not_a_project/quality").status_code==404


def test_regression_original_workflow_stays_independent():
    pid,_=upload()
    assert autopilot(pid,0).status_code==200
    # The prior project profile still reflects the original upload, by design.
    existing=client.get(f"/api/projects/{pid}")
    assert existing.status_code==200
    assert existing.json()["profile"]["rows"]==36
    assert snap(pid)["summary"]["applied_actions"]==1

# v0.2B Increment 1.1: detection-quality regression tests.
def test_real_messy_dataset_no_date_spelling_or_overlapping_whitespace_proposals():
    """Reproduces the two defects found in the user's manual API walkthrough."""
    demo = Path(__file__).resolve().parents[1] / "examples" / "demo_quality_issues.csv"
    pid, source = upload(pd.read_csv(demo, dtype={"TransactionID": str}))
    before = snap(pid)
    assert before["version"] == 0
    assert before["summary"] == {
        "issues": 7, "automatic_available": 1, "review_required": 5,
        "information": 1, "applied_actions": 0,
    }
    assert not any(x["kind"] == "spelling" and x["column"] == "InvoiceDate" for x in before["issues"])
    assert not any(x["kind"] == "spelling" and x["column"] == "Province"
                   and x["proposal"]["from"].strip() == "Mpumalanga" for x in before["issues"])
    assert any(x["kind"] == "ambiguous_dates" and x["column"] == "InvoiceDate" for x in before["issues"])
    assert any(x["kind"] == "spelling" and x["column"] == "Province"
               and x["proposal"]["from"] == "Mpimilanga" for x in before["issues"])

    first = autopilot(pid, 0)
    assert first.status_code == 200 and first.json()["count"] == 1
    current = snap(pid)
    assert current["version"] == 1
    assert not any(x["kind"] == "whitespace" and x["column"] == "Province" for x in current["issues"])
    # Undo does not fabricate a duplicate spelling proposal or reapply an undone action.
    undo = client.post(f"/api/projects/{pid}/quality/undo", json={
        "expected_version": 1, "action_id": first.json()["applied"][0]["id"]})
    assert undo.status_code == 200 and undo.json()["version"] == 2
    undone = snap(pid)
    assert undone["summary"]["issues"] == 7
    assert any(x["kind"] == "whitespace" and x["decision"] == "undone" for x in undone["issues"])
    assert autopilot(pid, 2).json()["count"] == 0
    assert Path(storage.get_project(pid)["dataset_path"]).read_bytes() == source


@pytest.mark.parametrize("column,common,rare", [
    ("InvoiceDate", "14/04/2025", "03/04/2025"),
    ("ObservedValue", "2025-04-14", "2025-04-03"),
    ("ObservedValue", "14.04.2025", "03.04.2025"),
    ("Period", "Apr 2025", "May 2025"),
    ("Product", "INV-2025-100", "INV-2025-101"),
    ("Product", "SKU001", "SKU002"),
    ("Product", "https://example.com/a", "https://example.com/b"),
])
def test_structured_values_never_fuzzy_merged(column, common, rare):
    frame = sample_frame()
    frame[column] = [common] * 34 + [rare] * 2
    pid, _ = upload(frame)
    issues = snap(pid)["issues"]
    assert not any(x["column"] == column and x["kind"] in {"spelling", "case_variant"} for x in issues)
    assert not any(x["column"] == column and x["automatic"] for x in issues)


def test_whitespace_first_then_new_findings_after_approval():
    frame = sample_frame()
    frame.loc[0:1, "Province"] = " GAUTENG "
    pid, _ = upload(frame)
    start = snap(pid)
    # While the source has surrounding spaces, don't also call it a spelling mistake.
    assert not any(x["kind"] == "spelling" and x["column"] == "Province"
                   and x["proposal"]["from"] == " GAUTENG " for x in start["issues"])
    done = autopilot(pid, 0)
    assert done.status_code == 200 and done.json()["count"] == 1
    after = snap(pid)
    assert not any(x["kind"] == "whitespace" for x in after["issues"])
    # True case inconsistency can now surface as a separate, approval-only decision.
    assert any(x["kind"] == "case_variant" and x["column"] == "Province"
               and x["proposal"]["from"] == "GAUTENG" for x in after["issues"])


def test_date_field_names_do_not_confuse_candidate_with_date():
    frame = sample_frame()
    frame["Candidate"] = ["Mpumalanga"] * 33 + ["Mpimilanga"] * 3
    pid, _ = upload(frame)
    assert any(x["kind"] == "spelling" and x["column"] == "Candidate" for x in snap(pid)["issues"])
