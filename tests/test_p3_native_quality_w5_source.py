"""Synthetic-only P3 native W5 QA contracts. No Tauri/native acceptance here."""
from __future__ import annotations
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from hashlib import sha256
from tools import qa_foundation

ROOT=Path(__file__).resolve().parents[1]
PHASE="P3-NATIVE-QUALITY-W5"

def read(path):
    return (ROOT/path).read_text(encoding="utf-8")

def test_native_w5_separate_identity():
    config=json.loads(read("frontend/src-tauri/tauri.p3-native-quality-w5-qa.conf.json"))
    assert config["identifier"]=="com.pilotodin.p3qualityw5qa"
    assert config["identifier"] not in ("com.pilotodin.studio","com.pilotodin.p3semanticqa")
    assert config["build"]["devUrl"]=="http://127.0.0.1:5178/p3_native_quality_w5_qa.html"
    assert config["bundle"]=={"active":False,"externalBin":[],"resources":[]}
    assert "/src/p3NativeQualityW5Qa.tsx" in read("frontend/p3_native_quality_w5_qa.html")

def test_native_w5_client_has_no_unreviewed_write_path():
    source=read("frontend/src/p3NativeQualityW5Qa.tsx")
    for item in (
        "import.meta.env.DEV","VITE_P3_NATIVE_QUALITY_W5_QA","isDesktop()",
        "location.origin==='http://127.0.0.1:5178'",
        "sessionStorage.getItem(key)","sessionStorage.setItem(key,JSON.stringify(budget))",
        "budget.proposals===0&&budget.commits===0","body.issue_id===issueId",
        "body.expected_version===0","budget.proposals=1;saveBudget()",
        "r.changed_cells===2","body.proposal_id===receipt.proposal_id",
        "body.proposal_hash===receipt.proposal_hash","budget.commits=1;saveBudget()",
        "W5 refused an unreviewed, repeated or out-of-scope write.",
        "<UnifiedShell/>","localStorage.setItem('pilotodin-current',pid)",
    ):
        assert item in source,item
    assert "startDesktopBackend" not in source
    assert "autopilot" not in source

def test_native_w5_runner_guard_and_evidence():
    source=read("tools/Run_P3_Native_Quality_W5_QA_Local.ps1")
    bat=read("Run_PilotODIN_P3_Native_Quality_W5_QA.bat")
    for expected in (
        "qa_foundation.py","init --phase $phase --json","status --porcelain",
        "PILOTODIN_HOME=$workspaceDir","Port-Occupied 8000 -or Port-Occupied 5178",
        "VITE_P3_NATIVE_W5_PROJECT","VITE_P3_NATIVE_W5_ISSUE",
        "npm run desktop:dev -- --config src-tauri/tauri.p3-native-quality-w5-qa.conf.json",
        "PASS_V0_TO_V1","PASS_EXACTLY_V0_V1","PASS_EMPTY_V1","PASS_HTTP_409",
        "PASS_UNCHANGED","PASS_ONE_PROPOSAL_ONE_UI_COMMIT_ONE_REJECTED_STALE_POST",
        "OWNER_REPORTED_PASS","product_acceptance='NOT_TESTED'",
        "Stop-Process -Id $backendProcess.Id","Compress-Archive",
    ):
        assert expected in source,expected
    assert "Run_P3_Native_Quality_W5_QA_Local.ps1" in bat
    assert not re.search(r"(?i)npm\s+ci|cargo\s+install|winget\s+install|git\s+reset|Remove-Item\s+-Recurse",source)

def _seed(tmp_path,dirty=False):
    run,_=qa_foundation.create_run(tmp_path/"w5-qa-root",PHASE,repo=ROOT)
    workspace=run/"workspace"
    if dirty:(workspace/"owner-marker.txt").write_text("untouched",encoding="utf-8")
    manifest=run/"fixtures"/"p3-native-w5-manifest.json"
    env=os.environ.copy()
    env["PILOTODIN_HOME"]=str(workspace)
    env.pop("PILOTODIN_DESKTOP_SESSION",None)
    result=subprocess.run(
        [sys.executable,"-B",str(ROOT/"tools/Seed_P3_Native_Quality_W5_Local.py"),str(manifest)],
        cwd=ROOT,env=env,capture_output=True,text=True,timeout=40,check=False
    )
    return workspace,manifest,result

def test_w5_seeder_exact_source_and_v0(tmp_path):
    from tools.Seed_P3_Native_Quality_W5_Local import source_bytes
    raw=source_bytes()
    assert len(raw.splitlines())==37
    assert raw.count(b" Mpumalanga ")==2
    workspace,output,completed=_seed(tmp_path)
    assert completed.returncode==0,completed.stdout+completed.stderr
    record=json.loads(output.read_text(encoding="utf-8"))
    assert record["phase"]==PHASE and record["version"]==0
    assert record["rows"]==36 and record["expected_changed_cells"]==2
    assert re.fullmatch(r"[a-f0-9]{32}",record["project_id"])
    assert record["issue_id"]
    original=workspace/record["source_relative"]
    assert original.is_relative_to(workspace) and original.read_bytes()==raw
    assert record["original_sha256"]==sha256(raw).hexdigest()
    assert not any((workspace/"models").iterdir())

def test_w5_seeder_fails_closed_on_nonempty_workspace(tmp_path):
    workspace,manifest,completed=_seed(tmp_path,dirty=True)
    assert completed.returncode!=0
    assert not manifest.exists()
    assert (workspace/"owner-marker.txt").read_text(encoding="utf-8")=="untouched"
    assert not (workspace/"datasets").exists()

def test_w5_native_origin_uses_existing_allowlist(tmp_path,monkeypatch):
    from fastapi.testclient import TestClient
    from backend import main,storage
    c=json.loads(read("frontend/src-tauri/tauri.p3-native-quality-w5-qa.conf.json"))
    origin=c["build"]["devUrl"].split("/p3_native_quality_w5_qa.html")[0]
    assert origin=="http://127.0.0.1:5178"
    home=tmp_path/"w5-origin-only"
    (home/"datasets").mkdir(parents=True)
    (home/"models").mkdir()
    monkeypatch.setattr(storage,"HOME",home)
    monkeypatch.setattr(storage,"DB_PATH",home/"pilotodin.sqlite3")
    storage.init()
    client=TestClient(main.app)
    pre=client.options("/api/projects/not_a_project/quality/proposals",headers={
      "Origin":origin,"Access-Control-Request-Method":"POST",
      "Access-Control-Request-Headers":"content-type",
    })
    assert pre.status_code==200 and pre.headers["access-control-allow-origin"]==origin
    good=client.get("/api/projects/not_a_project/quality",headers={"Origin":origin})
    assert good.status_code==404
    bad=client.get("/api/projects/not_a_project/quality",headers={"Origin":"http://127.0.0.1:5181"})
    # CORS forbids the response even though this read-only Quality route
    # returns 404 for an absent project rather than calling _local_request.
    # Browser access depends on the allow-origin header, not this status.
    assert bad.status_code==404
    assert "access-control-allow-origin" not in bad.headers
