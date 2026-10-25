"""A4-3: explicitly captured Quality audits are immutable, scoped and aggregate only."""
from __future__ import annotations

import hashlib
from pathlib import Path

import fitz
from fastapi.testclient import TestClient

from backend.main import app
from backend import quality, storage

client=TestClient(app)
PRIVATE_CATEGORY="CobaltSecret"


def project(name="quality-a4.csv"):
    lines=["OrderID,Region,Revenue,Optional"]
    for i in range(1,25):
        region=PRIVATE_CATEGORY if i<=12 else PRIVATE_CATEGORY.lower()
        amount=1000 if i==24 else (20+i)
        optional="" if i in (2,5,9) else "yes"
        lines.append(f"{i:04d},{region},{amount},{optional}")
    original=("\n".join(lines)+"\n").encode()
    r=client.post("/api/projects",files={"file":(name,original,"text/csv")})
    assert r.status_code==201,r.text
    return r.json()["id"],original


def capture(pid,version=0):
    return client.post(f"/api/projects/{pid}/report-quality",
                       json={"expected_version":version})


def make_report(pid,evidence):
    return client.post(f"/api/projects/{pid}/reports",json={
        "title":"Audited Data Quality Findings",
        "narrative":"Human-authored explanation of verified aggregate Quality findings.",
        "evidence_ids":[evidence],
    })


def test_explicit_quality_capture_is_read_only_and_reportable():
    pid,original=project()
    original_file=Path(storage.get_project(pid)["dataset_path"])
    version_before=quality.current_version(pid)
    reply=capture(pid,version_before)
    assert reply.status_code==201,reply.text
    captured=reply.json()
    assert captured["dataset_version"]==version_before==0
    assert captured["findings_total"]>=1
    assert original_file.read_bytes()==original
    assert quality.current_version(pid)==version_before
    with storage.connect() as con:
        audit=con.execute("SELECT * FROM report_quality_audits_v1 WHERE id=?",
                          (captured["id"],)).fetchone()
    assert audit["sha256"]==hashlib.sha256(audit["snapshot_json"].encode()).hexdigest()
    # No row previews or raw category examples in snapshot or rendered exports.
    assert PRIVATE_CATEGORY not in audit["snapshot_json"]
    assert PRIVATE_CATEGORY.lower() not in audit["snapshot_json"]
    assert '"preview"' not in audit["snapshot_json"]
    assert '"proposal"' not in audit["snapshot_json"]
    listed=client.get(f"/api/projects/{pid}/report-evidence")
    assert listed.status_code==200,listed.text
    item=next(x for x in listed.json() if x["id"]==captured["id"])
    assert item["source"]=="saved_quality_audit"
    assert item["operation"]=="quality_audit" and item["version"]==version_before

    response=make_report(pid,captured["id"])
    assert response.status_code==201,response.text
    saved=response.json()
    fact=saved["evidence"][0]
    assert fact["dataset_version"]==version_before
    assert fact["result"]["summary"]["Rows in approved dataset"]==24
    assert fact["result"]["summary"]["Approved working corrections active"]==0
    # Check the JSON structure, not the word "preview" in a safety warning.
    assert "preview" not in fact["result"]
    assert "row_values" not in fact["result"]
    assert PRIVATE_CATEGORY not in str(fact)
    html=client.get(f"/api/reports/{saved['id']}/export/html")
    pdf=client.get(f"/api/reports/{saved['id']}/export/pdf")
    assert html.status_code==200 and pdf.status_code==200
    pdf_text=" ".join(page.get_text() for page in fitz.open(
        stream=pdf.content,filetype="pdf"))
    for expected in ["Quality Audit","24","Findings"]:
        assert expected in html.text and expected in pdf_text
    assert PRIVATE_CATEGORY not in html.text and PRIVATE_CATEGORY not in pdf_text
    assert original_file.read_bytes()==original


def test_capture_refuses_stale_expected_version_and_foreign_project():
    first,_=project("quality-owner.csv")
    other,_=project("quality-other.csv")
    assert capture(first,99).status_code==409
    source=capture(first).json()
    assert make_report(other,source["id"]).status_code==403
    choices=client.get(f"/api/projects/{other}/report-evidence").json()
    assert source["id"] not in [item["id"] for item in choices]


def test_corrupted_quality_audit_is_not_offered_or_reported():
    pid,_=project("quality-corrupt.csv")
    a=capture(pid).json()
    with storage.connect() as con:
        con.execute("UPDATE report_quality_audits_v1 SET snapshot_json=? WHERE id=?",
                    ('{"dataset_version":0,"summary":{"Rows in approved dataset":999}}',a["id"]))
    options=client.get(f"/api/projects/{pid}/report-evidence").json()
    assert a["id"] not in [item["id"] for item in options]
    result=make_report(pid,a["id"])
    assert result.status_code==409


def test_original_quality_snapshot_is_frozen_across_version_change():
    pid,_=project("quality-historical.csv")
    a=capture(pid).json()
    report=make_report(pid,a["id"]).json()
    with storage.connect() as con:
        quality._add_version(con,pid,[],"restore",{"reason":"isolated version-test fixture"})
    assert quality.current_version(pid)==1
    options=client.get(f"/api/projects/{pid}/report-evidence").json()
    option=next(x for x in options if x["id"]==a["id"])
    assert option["stale"] is True
    reopened=client.get(f"/api/reports/{report['id']}?revision=1")
    assert reopened.status_code==200
    assert reopened.json()["dataset_versions"]==[0]
    assert reopened.json()["has_historical_evidence"] is True
    assert reopened.json()["content_sha256"]==report["content_sha256"]


def test_corrupt_saved_report_revision_refuses_reload_and_download():
    pid,_=project("quality-report-corrupt.csv")
    a=capture(pid).json()
    report=make_report(pid,a["id"]).json()
    rid=report["id"]
    with storage.connect() as con:
        con.execute("UPDATE report_revisions_v1 SET snapshot_json=? WHERE report_id=?",
                    ('{"title":"forged"}',rid))
    assert client.get(f"/api/reports/{rid}").status_code==409
    assert client.get(f"/api/reports/{rid}/export/html").status_code==409
    assert client.get(f"/api/reports/{rid}/export/pdf").status_code==409


def test_valid_sha256_cannot_transplant_another_projects_revision():
    first,_=project("quality-revision-owner.csv")
    second,_=project("quality-revision-foreign.csv")
    owner_audit=capture(first).json()
    foreign_audit=capture(second).json()
    source=make_report(first,owner_audit["id"]).json()
    target=make_report(second,foreign_audit["id"]).json()
    assert source["project_id"] != target["project_id"]
    with storage.connect() as con:
        original=con.execute(
            "SELECT snapshot_json,content_sha256 FROM report_revisions_v1 WHERE report_id=?",
            (source["id"],)
        ).fetchone()
        con.execute(
            "UPDATE report_revisions_v1 SET snapshot_json=?,content_sha256=? WHERE report_id=?",
            (original["snapshot_json"],original["content_sha256"],target["id"])
        )
    # Matching SHA only authenticates the blob: it must also belong to this
    # specific project/report's provenance. Never emit foreign-project facts.
    for suffix in ("", "/export/html", "/export/pdf"):
        assert client.get(f"/api/reports/{target['id']}{suffix}").status_code==409
    assert client.get(f"/api/reports/{source['id']}").status_code==200
