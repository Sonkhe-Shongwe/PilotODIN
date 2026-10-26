#!/usr/bin/env python3
"""Fixture ONLY: two synthetic saved revisions plus expected backend HTML/PDF hashes.

The caller MUST set PILOTODIN_HOME to a fresh empty temporary directory before
launch. This tool does not write outside that directory or load ML/AI models.
"""
from __future__ import annotations
import hashlib
import json
import os
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

def main()->int:
    if len(sys.argv)!=2:
        raise RuntimeError("Expected one synthetic manifest output path.")
    if os.environ.get("RL_invariant")!="1":
        raise RuntimeError("Native full-chain synthetic test must request reproducible ReportLab PDF metadata.")
    from reportlab import rl_config
    if rl_config.invariant != 1:
        raise RuntimeError("ReportLab did not activate invariant PDF output in synthetic QA.")
    home_value=os.environ.get("PILOTODIN_HOME","")
    if not home_value:
        raise RuntimeError("PILOTODIN_HOME must be an isolated temporary directory.")
    home=Path(home_value).resolve()
    manifest=Path(sys.argv[1]).resolve()
    if not home.is_dir() or not manifest.parent.is_dir() or home not in manifest.parents:
        raise RuntimeError("Refusing to write outside explicitly isolated temporary home.")
    if list(home.iterdir()):
        # A created staging manifest directory is okay, existing actual data isn't.
        allowed={"logs","datasets","models"}
        if any(p.name not in allowed for p in home.iterdir()):
            raise RuntimeError("Isolated home is not empty; refusing to touch existing content.")
    os.environ.pop("PILOTODIN_DESKTOP_SESSION",None)
    sys.path.insert(0,str(ROOT))
    from fastapi.testclient import TestClient
    from backend.main import app
    from backend import storage
    csv=b"OrderID,Region,Revenue\nA0001,North,140\nA0002,South,210\nA0003,North,310\nA0004,South,440\n"
    client=TestClient(app)
    created=client.post("/api/projects",files={"file":("native-chain-synthetic.csv",csv,"text/csv")})
    if created.status_code!=201:
        raise RuntimeError("Creating synthetic project failed, HTTP "+str(created.status_code))
    project_id=created.json()["id"]
    source=Path(storage.get_project(project_id)["dataset_path"]).resolve()
    if not source.is_relative_to((home/"datasets").resolve()) or source.read_bytes()!=csv:
        raise RuntimeError("Synthetic source escaped isolated dataset directory or was altered.")
    audit=client.post(f"/api/projects/{project_id}/report-quality",json={"expected_version":0})
    if audit.status_code!=201:raise RuntimeError("Synthetic Quality snapshot creation failed")
    evidence_id=audit.json()["id"]
    original=client.post(f"/api/projects/{project_id}/reports",json={
        "title":"P2 Native Chain Synthetic Revision One",
        "narrative":"Only synthetic evidence for Windows integration QA.",
        "evidence_ids":[evidence_id],
    })
    if original.status_code!=201:raise RuntimeError("Synthetic report revision 1 creation failed")
    report_id=original.json()["id"]
    revised=client.post(f"/api/reports/{report_id}/revisions",json={
        "title":"P2 Native Chain Synthetic Revision Two",
        "narrative":"Frozen second revision from an isolated synthetic dataset.",
        "evidence_ids":[evidence_id],
    })
    if revised.status_code!=201 or revised.json()["revision"]!=2:
        raise RuntimeError("Synthetic report revision 2 creation failed")
    first=client.get(f"/api/reports/{report_id}?revision=1")
    second=client.get(f"/api/reports/{report_id}?revision=2")
    if first.status_code!=200 or second.status_code!=200 or first.json()["title"]==second.json()["title"]:
        raise RuntimeError("Frozen report revisions were not independently retrievable.")
    exports={}
    for fmt in ("pdf","html"):
        response=client.get(f"/api/reports/{report_id}/export/{fmt}?revision=2")
        if response.status_code!=200:raise RuntimeError(f"{fmt} export HTTP {response.status_code}")
        if fmt=="pdf" and not response.content.startswith(b"%PDF-"):
            raise RuntimeError("Synthetic PDF export signature incorrect")
        if fmt=="html" and not response.content.lower().startswith(b"<!doctype html"):
            raise RuntimeError("Synthetic HTML export signature incorrect")
        expected_name=f"pilotodin_report_{report_id[:12]}_rev2.{fmt}"
        if expected_name not in response.headers.get("content-disposition",""):
            raise RuntimeError(f"Expected {fmt} filename not returned by backend")
        # Strict proof that the same immutable revision renders identically at
        # two different calls before crossing the TestClient/Uvicorn boundary.
        repeated=client.get(f"/api/reports/{report_id}/export/{fmt}?revision=2")
        if repeated.status_code!=200 or repeated.content!=response.content:
            raise RuntimeError(f"Synthetic {fmt} export changed between repeated requests; refuse digest baseline.")
        exports[fmt]={
            "filename":expected_name,
            "sha256":hashlib.sha256(response.content).hexdigest(),
            "bytes":len(response.content),
        }
    record={
        "project_id":project_id,"report_id":report_id,"revision":2,
        "title":second.json()["title"],
        "source_sha256":hashlib.sha256(csv).hexdigest(),
        "source_relative":str(source.relative_to(home)),
        "exports":exports
    }
    manifest.write_text(json.dumps(record,indent=2),encoding="utf-8")
    print("Synthetic project/report v1 and v2 created; PDF/HTML twice-rendered digest checks PASS.")
    return 0

if __name__=="__main__":
    raise SystemExit(main())
