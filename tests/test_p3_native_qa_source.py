"""P3 native owner-QA launcher preflight and disposable seeder acceptance.

This does not run Tauri or claim physical Windows WebView2 acceptance.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import subprocess
import sys

from tools import qa_foundation

ROOT = Path(__file__).resolve().parents[1]
PHASE = "P3-NATIVE-SEMANTIC-CONTEXT"


def read(path):
    return (ROOT / path).read_text(encoding="utf-8")


def test_native_config_never_targets_installed_product_or_installer():
    config = json.loads(read("frontend/src-tauri/tauri.p3-native-semantic-qa.conf.json"))
    assert config["identifier"] == "com.pilotodin.p3semanticqa"
    assert config["identifier"] != "com.pilotodin.studio"
    assert config["build"]["devUrl"] == "http://127.0.0.1:5181/p3_native_semantic_qa.html"
    assert config["bundle"] == {"active": False, "externalBin": [], "resources": []}
    assert config["app"]["windows"][0]["label"] == "main"


def test_native_page_requires_tauri_dev_and_denies_arbitrary_api_writes():
    src = read("frontend/src/p3NativeSemanticQa.tsx")
    assert "import.meta.env.DEV" in src
    assert "VITE_PILOTODIN_NATIVE_SMOKE" in src
    assert "VITE_P3_NATIVE_SEMANTIC_QA" in src
    assert "location.origin==='http://127.0.0.1:5181'" in src
    assert "isDesktop()" in src
    assert "approvedSaves<2" in src
    assert "sessionStorage.getItem(saveCountKey)" in src
    assert "sessionStorage.setItem(saveCountKey,String(approvedSaves))" in src
    assert "method==='GET'||method==='HEAD'" in src
    assert "url.pathname==='/api/projects/'+aid+'/semantic-business-context'" in src
    assert "obj.expected_version===0" in src
    assert "fields[0]?.column==='claim_amount'" in src
    assert "Synthetic P3 native QA blocks all other writes and remote requests" in src
    assert "<UnifiedShell/>" in src
    assert "startDesktopBackend" not in src
    assert "localStorage.setItem('pilotodin-current',aid)" in src
    page = read("frontend/p3_native_semantic_qa.html")
    assert "/src/p3NativeSemanticQa.tsx" in page


def test_windows_launcher_is_isolated_preflight_only_and_records_truth():
    script = read("tools/Run_P3_Native_Semantic_QA_Local.ps1")
    bat = read("Run_PilotODIN_P3_Native_Semantic_QA.bat")
    assert "qa_foundation.py" in script
    assert "init --phase $phase --json" in script
    assert "CARGO_NET_OFFLINE='true'" in script
    assert "feature/live-dev-workspace-20261023" in script
    assert "git" in script and "status --porcelain" in script
    assert "PILOTODIN_HOME=$workspaceDir" in script
    assert "Port-Occupied 8000 -or Port-Occupied 5181" in script
    assert "VITE_P3_NATIVE_QA_PROJECT_A" in script
    assert "VITE_P3_NATIVE_QA_PROJECT_B" in script
    assert "npm run desktop:dev -- --config src-tauri/tauri.p3-native-semantic-qa.conf.json" in script
    assert "Owner-Check 'w1_dirty_switch_stay'" in script
    assert "Owner-Check 'w4_keyboard_validation'" in script
    assert "semantic_save_requests='TWO_APPROVED_SYNTHETIC_A_SAVES_ONLY'" in script
    assert "product_acceptance='NOT_TESTED'" in script
    assert "Stop-Process -Id $backendProcess.Id" in script
    assert "Compress-Archive" in script
    assert not re.search(r"(?i)npm\s+ci|cargo\s+install|winget\s+install|git\s+reset|Remove-Item\s+-Recurse", script)
    assert "Run_P3_Native_Semantic_QA_Local.ps1" in bat


def _seed(tmp_path, marker=False):
    run, _ = qa_foundation.create_run(tmp_path / "p3-qa-root", PHASE, repo=ROOT)
    workspace = run / "workspace"
    if marker:
        (workspace / "owner-safety-marker.txt").write_text("existing", encoding="utf-8")
    manifest = run / "fixtures" / "p3-native-semantic-manifest.json"
    env = os.environ.copy()
    env["PILOTODIN_HOME"] = str(workspace)
    env.pop("PILOTODIN_DESKTOP_SESSION", None)
    done = subprocess.run(
        [sys.executable, "-B", str(ROOT / "tools/Seed_P3_Native_Semantic_Context_Local.py"), str(manifest)],
        cwd=ROOT, env=env, text=True, capture_output=True, timeout=30, check=False,
    )
    return run, workspace, manifest, done


def test_disposable_seeder_imports_only_two_p3_fixtures(tmp_path):
    run, workspace, manifest_path, done = _seed(tmp_path)
    assert done.returncode == 0, done.stdout + done.stderr
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["phase"] == PHASE
    assert manifest["run_id"] == run.name
    assert len(manifest["projects"]) == 2
    assert len({item["id"] for item in manifest["projects"]}) == 2
    for label, entry in zip(("A", "B"), manifest["projects"]):
        assert entry["rows"] == 20
        original = (ROOT / "tests" / "fixtures" / f"p3_semantic_owner_{label}.csv").read_bytes()
        saved = workspace / entry["source_relative"]
        assert saved.is_relative_to(workspace)
        assert saved.read_bytes() == original
    assert not any((workspace / "models").iterdir())


def test_disposable_seeder_fails_closed_when_workspace_not_empty(tmp_path):
    _run, workspace, manifest, done = _seed(tmp_path, marker=True)
    assert done.returncode != 0
    assert not manifest.exists()
    assert (workspace / "owner-safety-marker.txt").read_text(encoding="utf-8") == "existing"
    assert not (workspace / "datasets").exists()
