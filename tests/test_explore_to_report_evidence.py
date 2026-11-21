"""Saved Explore evidence must be verified and reportable, without source-data copies."""
from __future__ import annotations

import fitz
from fastapi.testclient import TestClient

from backend import main, quality, reports, saved_analyses, storage

client=TestClient(main.app)


def make_project(name):
    data=b"OrderID,Region,Revenue,Loss\n0001,North,120,20\n0002,South,180,30\n0003,North,240,40\n0004,South,280,55\n"
    response=client.post("/api/projects",files={"file":(name,data,"text/csv")})
    assert response.status_code==201,response.text
    return response.json()["id"],data


def save_explore(pid, title="North regional breakdown"):
    response=client.post(f"/api/projects/{pid}/explore/saved",json={
      "title":title, "expected_version":quality.current_version(pid),
      "x":"Region", "y":"Revenue", "kind":"bar", "aggregation":"sum",
      "bins":12, "correlation_method":"pearson",
      "filters":[{"column":"Region","op":"eq","value":"North"}]
    })
    assert response.status_code==201,response.text
    return response.json()


def save_report(pid,ids):
    return client.post(f"/api/projects/{pid}/reports",json={
       "title":"Verified region evidence","narrative":"Human-reviewed and descriptive.",
       "evidence_ids":ids
    })


def test_saved_explore_appears_as_deliver_option_and_renders_same_verified_numbers():
    pid,data=make_project("reportable.csv")
    snap=save_explore(pid)
    options=client.get(f"/api/projects/{pid}/report-evidence")
    assert options.status_code==200,options.text
    choice=next(item for item in options.json() if item["id"]==snap["id"])
    assert choice["operation"]=="explore_snapshot"
    assert choice["version"]==snap["dataset_version"]
    assert choice["objective"]==snap["title"]
    assert choice["source"]=="saved_explore"
    result=save_report(pid,[snap["id"]])
    assert result.status_code==201,result.text
    report=result.json()
    assert len(report["evidence"])==1
    evidence=report["evidence"][0]
    assert evidence["operation"]=="explore_snapshot"
    assert evidence["dataset_version"]==snap["dataset_version"]
    assert evidence["params"]["source_snapshot_sha256"]==snap["sha256"]
    assert evidence["result"]["summary"]["Rows matching saved filters"]==2
    assert evidence["result"]["data"][0]["value"]==360
    rendered=client.get(f"/api/reports/{report['id']}/export/html")
    pdf=client.get(f"/api/reports/{report['id']}/export/pdf")
    assert rendered.status_code==200 and pdf.status_code==200
    assert "North" in rendered.text and "360" in rendered.text
    assert snap["sha256"] in rendered.text
    text=" ".join(p.get_text() for p in fitz.open(stream=pdf.content,filetype="pdf"))
    assert "360" in text and "North" in text
    assert storage.get_project(pid) is not None


def test_mixed_investigation_and_explore_evidence_keeps_exact_artifact_revisions():
    pid,_=make_project("mixed.csv")
    snap=save_explore(pid)
    investigation=client.post(f"/api/projects/{pid}/investigations",json={"objective":"Examine revenue by region"}).json()
    run=client.post(f"/api/investigations/{investigation['id']}/runs",json={
       "operation":"overview","params":{},"expected_version":investigation["version"]
    })
    assert run.status_code==200,run.text
    first=run.json()["artifacts"][0]["id"]
    report=save_report(pid,[first,snap["id"]])
    assert report.status_code==201,report.text
    assert [a["id"] for a in report.json()["evidence"]]==[first,snap["id"]]
    assert report.json()["dataset_versions"]==[0]
    assert len(report.json()["evidence"])==2


def test_cross_project_snapshot_forgery_and_mutated_source_are_rejected():
    first,_=make_project("owner.csv")
    second,_=make_project("not-owner.csv")
    snapshot=save_explore(first)
    rejected=save_report(second,[snapshot["id"]])
    assert rejected.status_code==403
    assert client.get(f"/api/projects/{second}/report-evidence").status_code==200
    assert snapshot["id"] not in [e["id"] for e in client.get(f"/api/projects/{second}/report-evidence").json()]
    with storage.connect() as con:
        con.execute("UPDATE explore_snapshots_v1 SET snapshot_json=? WHERE id=?",('{"tampered":true}',snapshot["id"]))
    broken=save_report(first,[snapshot["id"]])
    assert broken.status_code==409
    assert client.get(f"/api/projects/{first}/reports").json()==[]


def test_historical_explore_snapshot_remains_frozen_in_report():
    pid,_=make_project("historical.csv")
    snapshot=save_explore(pid)
    # Current version changes after user-approved quality treatment.
    # Report still embeds original evidence bytes and original v0 provenance.
    original=save_report(pid,[snapshot["id"]])
    assert original.status_code==201,original.text
    saved=client.get(f"/api/reports/{original.json()['id']}").json()
    assert saved["dataset_versions"]==[snapshot["dataset_version"]]
    assert saved["evidence"][0]["result"]["data"][0]["value"]==360
    with storage.connect() as con:
        stored=con.execute("SELECT snapshot_json FROM report_revisions_v1 WHERE report_id=?",(saved["id"],)).fetchone()
    assert stored and "explore_snapshot" in stored["snapshot_json"]


def test_reporting_refuses_snapshot_whose_chart_settings_were_changed():
    import json
    pid,_=make_project("tampered_filters.csv")
    snapshot=save_explore(pid)
    with storage.connect() as con:
        original=con.execute("SELECT configuration_json FROM explore_snapshots_v1 WHERE id=?",(snapshot["id"],)).fetchone()[0]
        config=json.loads(original)
        config["filters"]=[]
        con.execute("UPDATE explore_snapshots_v1 SET configuration_json=? WHERE id=?",
                    (json.dumps(config,sort_keys=True,separators=(',',':')),snapshot["id"]))
    options=client.get(f"/api/projects/{pid}/report-evidence")
    assert options.status_code==200,options.text
    assert snapshot["id"] not in {entry["id"] for entry in options.json()}
    response=save_report(pid,[snapshot["id"]])
    assert response.status_code==409,response.text
    assert "configuration" in response.text.lower()
    assert client.get(f"/api/projects/{pid}/reports").json()==[]


def test_legacy_saved_results_are_readable_in_explore_but_absent_from_deliver():
    import hashlib,json
    pid,_=make_project("legacy-report-options.csv")
    saved=save_explore(pid)
    with storage.connect() as con:
        original=con.execute("SELECT snapshot_json FROM explore_snapshots_v1 WHERE id=?",(saved["id"],)).fetchone()[0]
        result=json.loads(original)
        del result["configuration_sha256"]
        canonical=json.dumps(result,sort_keys=True,ensure_ascii=False,allow_nan=False,separators=(',',':'))
        con.execute("UPDATE explore_snapshots_v1 SET snapshot_json=?,sha256=? WHERE id=?",
                    (canonical,hashlib.sha256(canonical.encode()).hexdigest(),saved["id"]))
    visible=client.get(f"/api/projects/{pid}/explore/saved/{saved['id']}")
    assert visible.status_code==200,visible.text
    assert visible.json()["configuration_verified"] is False
    library=client.get(f"/api/projects/{pid}/explore/saved")
    assert library.status_code==200 and library.json()[0]["configuration_verified"] is False
    choices=client.get(f"/api/projects/{pid}/report-evidence")
    assert choices.status_code==200
    assert saved["id"] not in {entry["id"] for entry in choices.json()}
    rejected=save_report(pid,[saved["id"]])
    assert rejected.status_code==409
