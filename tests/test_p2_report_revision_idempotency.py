"""P2: genuine immutable report revisions without duplicate no-change writes.

Safety: this module must not import backend.main or initialise the storage home
unless the dedicated runner has installed a new temporary PILOTODIN_HOME
containing our exact marker. All uploaded data and evidence are synthetic.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import hashlib
import os
from pathlib import Path
import tempfile

import pytest

HOME = Path(os.environ.get("PILOTODIN_HOME", "/")).resolve()
MARKER = HOME / ".pilotodin-p2-idempotency-synthetic"
SAFE = (
    os.environ.get("PILOTODIN_P2_REPORT_IDEMPOTENCY_TEST") == "1"
    and HOME.is_absolute()
    and Path(tempfile.gettempdir()).resolve() in HOME.parents
    and MARKER.is_file()
)
if not SAFE:
    pytest.skip("Only the isolated disposable P2 report runner may import backend.main",
                allow_module_level=True)

from fastapi.testclient import TestClient
from backend.main import app
from backend import storage

client = TestClient(app)
SOURCE = b"OrderID,Region,Revenue\n001,West,19.00\n002,East,25.00\n003,West,41.00\n"


def project():
    response = client.post("/api/projects", files={
        "file": ("P2_Disposable_Reports.csv", SOURCE, "text/csv")})
    assert response.status_code == 201, response.text
    return response.json()["id"]


def evidence(pid, operation="overview", params=None):
    investigation = client.post(
        f"/api/projects/{pid}/investigations",
        json={"objective": "Review synthetic-only saved results"})
    assert investigation.status_code in (200, 201), investigation.text
    meta = investigation.json()
    run = client.post(
        f"/api/investigations/{meta['id']}/runs",
        json={"operation": operation, "params": params or {},
              "expected_version": meta["version"]})
    assert run.status_code == 200, run.text
    return run.json()["artifacts"][0]["id"]


def payload(ids, title="Synthetic Reporting Review", narrative="Verified synthetic records."):
    return {"title": title, "narrative": narrative, "evidence_ids": ids}


def create(pid, data):
    response = client.post(f"/api/projects/{pid}/reports", json=data)
    assert response.status_code == 201, response.text
    return response.json()


def revise(report_id, data):
    return client.post(f"/api/reports/{report_id}/revisions", json=data)


def stored_revisions(report_id):
    with storage.connect() as con:
        return con.execute(
            "SELECT number,content_sha256 FROM report_revisions_v1 "
            "WHERE report_id=? ORDER BY number", (report_id,)).fetchall()


def test_duplicate_identical_revision_is_noop_with_same_hash_id_and_source_bytes():
    pid = project()
    eid = evidence(pid)
    initial = create(pid, payload([eid]))
    rid = initial["id"]
    with storage.connect() as con:
        path = con.execute("SELECT dataset_path FROM projects WHERE id=?",
                           (pid,)).fetchone()["dataset_path"]
    source_digest = hashlib.sha256(Path(path).read_bytes()).hexdigest()
    duplicate = revise(rid, payload([eid]))
    assert duplicate.status_code == 200, duplicate.text
    result = duplicate.json()
    assert result["unchanged"] is True
    for key in ("id", "revision", "revision_id", "created_revision_at",
                "content_sha256", "evidence", "dataset_versions"):
        assert result[key] == initial[key]
    assert result["revisions"] == [1]
    assert len(stored_revisions(rid)) == 1
    assert hashlib.sha256(Path(path).read_bytes()).hexdigest() == source_digest


def test_title_whitespace_that_normalizes_to_same_snapshot_does_not_create_revision():
    pid = project()
    eid = evidence(pid)
    first = create(pid, payload([eid]))
    repeated = revise(first["id"], payload(
        [eid], title="  Synthetic Reporting Review  "))
    assert repeated.status_code == 200, repeated.text
    assert repeated.json()["revision"] == 1
    assert repeated.json()["unchanged"] is True
    assert len(stored_revisions(first["id"])) == 1


def test_real_change_creates_one_revision_and_original_exports_remain_immutable():
    pid = project()
    eid = evidence(pid)
    first = create(pid, payload([eid]))
    rid = first["id"]
    new = payload([eid], narrative="Rewritten interpretation on synthetic evidence.")
    updated = revise(rid, new)
    assert updated.status_code == 201, updated.text
    data = updated.json()
    assert data["revision"] == 2
    assert data.get("unchanged") is not True
    assert data["content_sha256"] != first["content_sha256"]
    second_call = revise(rid, new)
    assert second_call.status_code == 200, second_call.text
    assert second_call.json()["revision_id"] == data["revision_id"]
    assert second_call.json()["revisions"] == [1, 2]
    original = client.get(f"/api/reports/{rid}?revision=1")
    assert original.status_code == 200
    assert original.json()["content_sha256"] == first["content_sha256"]
    assert original.json()["narrative"] == first["narrative"]
    assert len(stored_revisions(rid)) == 2


def test_same_evidence_different_order_is_real_new_revision():
    pid = project()
    ids = [
        evidence(pid, "overview"),
        evidence(pid, "compare", {"x": "Region", "y": "Revenue"})
    ]
    first = create(pid, payload(ids))
    newer = revise(first["id"], payload(list(reversed(ids))))
    assert newer.status_code == 201, newer.text
    assert newer.json()["revision"] == 2
    assert [x["id"] for x in newer.json()["evidence"]] == list(reversed(ids))
    assert len(stored_revisions(first["id"])) == 2


def test_latest_corrupt_snapshot_is_refused_and_never_silently_hidden():
    pid = project()
    eid = evidence(pid)
    first = create(pid, payload([eid]))
    with storage.connect() as con:
        con.execute(
            "UPDATE report_revisions_v1 SET snapshot_json=? WHERE report_id=?",
            ('{"corrupt":true}', first["id"]))
    response = revise(first["id"], payload([eid]))
    assert response.status_code == 409
    assert len(stored_revisions(first["id"])) == 1


def test_simultaneous_identical_submissions_do_not_create_duplicate_revisions():
    pid = project()
    eid = evidence(pid)
    first = create(pid, payload([eid]))
    with ThreadPoolExecutor(max_workers=3) as pool:
        results = list(pool.map(lambda _: revise(first["id"], payload([eid])),
                                range(3)))
    assert all(result.status_code == 200 for result in results), [
        (r.status_code, r.text) for r in results]
    assert all(r.json()["revision_id"] == first["revision_id"] for r in results)
    assert len(stored_revisions(first["id"])) == 1


def test_evidence_fact_preview_is_project_scoped_read_only_and_never_exposes_rows():
    pid = project()
    eid = evidence(pid, "overview")
    before = client.get(f"/api/projects/{pid}/reports").json()
    response = client.get(f"/api/projects/{pid}/report-evidence/{eid}/preview")
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["id"] == eid
    assert data["operation"] == "overview"
    assert data["dataset_version"] == 0
    assert data["current_dataset_version"] == 0
    assert data["historical"] is False
    assert len(data["summary"]) <= 8
    assert all(isinstance(f["label"], str) and len(f["label"]) <= 80
               and isinstance(f["value"], str) and len(f["value"]) <= 140
               for f in data["summary"])
    assert "raw rows" in data["disclosure"]
    assert not ({"data", "rows", "records", "result", "findings",
                 "predictions", "evidence"} & set(data))
    assert client.get(f"/api/projects/{pid}/reports").json() == before
    with storage.connect() as con:
        assert con.execute(
            "SELECT COUNT(*) FROM report_revisions_v1 v "
            "JOIN reports_v1 r ON v.report_id=r.id WHERE r.project_id=?",
            (pid,)
        ).fetchone()[0] == 0


def test_evidence_fact_preview_refuses_foreign_or_invalid_evidence():
    pid = project()
    eid = evidence(pid, "overview")
    other = project()
    assert client.get(
        f"/api/projects/{other}/report-evidence/{eid}/preview"
    ).status_code == 403
    assert client.get(
        f"/api/projects/{pid}/report-evidence/not-a-uuid/preview"
    ).status_code == 422
    assert client.get(
        f"/api/projects/{pid}/report-evidence/{'f'*32}/preview"
    ).status_code == 403
    assert client.get(
        f"/api/projects/{'e'*32}/report-evidence/{eid}/preview"
    ).status_code == 404


def test_quality_evidence_fact_preview_is_bounded_and_rejects_tampering():
    pid = project()
    audit = client.post(
        f"/api/projects/{pid}/report-quality", json={"expected_version": 0})
    assert audit.status_code == 201, audit.text
    eid = audit.json()["id"]
    response = client.get(f"/api/projects/{pid}/report-evidence/{eid}/preview")
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["operation"] == "quality_audit"
    assert data["dataset_version"] == 0
    assert any("findings" in fact["label"].lower() for fact in data["summary"])
    assert "findings" not in data
    assert "data" not in data
    assert not isinstance(data.get("summary"), dict)
    with storage.connect() as con:
        con.execute(
            "UPDATE report_quality_audits_v1 SET snapshot_json=? WHERE id=?",
            ('{"dataset_version":0,"summary":{"Quality findings detected":999}}', eid))
    denied = client.get(f"/api/projects/{pid}/report-evidence/{eid}/preview")
    assert denied.status_code == 409
    assert "integrity" in denied.json()["detail"].lower()
