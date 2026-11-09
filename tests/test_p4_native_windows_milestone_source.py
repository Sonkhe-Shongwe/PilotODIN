"""P4-16 windows builder contract, no owner/native activity permitted here."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_p4_16_qa_identity_keeps_original_installation_separate():
    qa = json.loads((ROOT / "frontend/src-tauri/tauri.p4-native-qa.conf.json")
                    .read_text(encoding="utf-8"))
    original = json.loads((ROOT / "frontend/src-tauri/tauri.conf.json")
                          .read_text(encoding="utf-8"))
    assert qa["identifier"] == "com.pilotodin.p4nativeqa"
    assert qa["identifier"] != original["identifier"]
    assert qa["productName"] == "pilotODIN-P4-Native-QA"
    assert qa["bundle"]["active"] is True
    assert qa["bundle"]["targets"] == ["nsis"]
    # All runtime/model resource requirements remain inherited from the
    # normal Tauri config; this overlay must NOT replace real sidecar inputs.
    assert "externalBin" not in qa["bundle"]
    assert "resources" not in qa["bundle"]
    assert "frontendDist" not in qa.get("build", {})


def test_p4_16_workflow_requires_real_assets_identity_and_passed_ci_install():
    workflow = (ROOT / ".github/workflows/p4-native-windows-milestone.yml"
                ).read_text(encoding="utf-8")
    for fragment in (
        "runs-on: windows-2022",
        "git rev-parse HEAD",
        "$env:GITHUB_SHA",
        "Stage_Pinned_Offline_AI.ps1",
        "verify_live_bundled_inference.py",
        "Build_Python_Sidecar.ps1",
        "npx tauri build --config src-tauri/tauri.p4-native-qa.conf.json --no-binary-patching",
        "Installed QA EXE differs from the source-matched compiled EXE; fail closed.",
        "Source-matched compiled and CI-installed Windows EXE SHA256: MATCH",
        "Verify_Installed_PilotODIN.ps1",
        "installed-engine-smoke-result.json",
        "Get-FileHash",
        "source-and-windows-artifact.json",
        "installed_on_owner_windows = $false",
        "native_owner_acceptance = 'NOT_TESTED'",
        "release_certified = $false",
    ):
        assert fragment in workflow
    assert "actions/create-release" not in workflow
    assert "gh release create" not in workflow
    assert "Start-Process -FilePath" not in workflow  # only existing CI verifier
    assert "release:" not in workflow


def test_p4_16_historical_native_release_scripts_not_mutated():
    assert (ROOT / "desktop/Build_Windows_Installer.ps1").exists()
    assert (ROOT / "desktop/Stage_Pinned_Offline_AI.ps1").exists()
    assert (ROOT / "desktop/Verify_Installed_PilotODIN.ps1").exists()
    assert (ROOT / "qa/p4_native/README.md").exists()
