"""Synthetic checks for the compile-only N12 staging and provenance entry point."""
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from qa.p4_research import n12_app_build as build


SOURCE = "a" * 40


@pytest.fixture
def staged_runner(tmp_path, monkeypatch):
    crate = tmp_path / "checkout" / "src-tauri"
    crate.mkdir(parents=True)
    for name in ("tauri.conf.json", "tauri.p4-native-qa.conf.json", "tauri.p4-isolated-native-dev.conf.json"):
        (crate / name).write_bytes((build.CRATE / name).read_bytes())
    monkeypatch.setattr(build, "CRATE", crate)
    settings = {"GITHUB_RUN_ID": "123", "GITHUB_EVENT_NAME": "push", "GITHUB_REF_NAME": build.BRANCH,
                "GITHUB_RUN_ATTEMPT": "1", "PILOTODIN_P4_UNPACKAGED_NATIVE_DEV_CONSENT": build.CONSENT,
                "PILOTODIN_N12_APPROVED_SOURCE": SOURCE, "RUNNER_TEMP": str(tmp_path),
                "LOCALAPPDATA": str(tmp_path / "local"), "APPDATA": str(tmp_path / "roaming")}
    for key, value in settings.items():
        monkeypatch.setenv(key, value)
    for key in ("PILOTODIN_HOME", "WEBVIEW2_USER_DATA_FOLDER", "TAURI_CONFIG"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setattr(build, "git", lambda *args: SOURCE if args[0] == "rev-parse" else "")
    monkeypatch.setattr(build, "local_disposable_path", lambda value, **kw: value)
    return crate


def test_staging_compiles_once_and_writes_provenance_for_the_same_binary(staged_runner, monkeypatch):
    commands = []

    def fake_cargo(command, *, cwd, env, check):
        commands.append(command)
        assert cwd == staged_runner and check
        config = json.loads(env["TAURI_CONFIG"])
        assert config["identifier"] == build.QA_ID
        assert config["bundle"] == {"active": False, "externalBin": [], "resources": []}
        target_dir = Path(env["CARGO_TARGET_DIR"])
        binary = target_dir / build.TARGET / "debug" / build.EXE
        binary.parent.mkdir(parents=True)
        binary.write_bytes(b"synthetic executable")
        (cwd / "Cargo.lock").write_text("synthetic resolved lock")

    monkeypatch.setattr(build.subprocess, "run", fake_cargo)
    root = build.stage_root(SOURCE)
    record = build.stage(root, SOURCE)
    assert commands == [["cargo", "build", "--bin", "pilotodin-desktop", "--target", build.TARGET,
                         "--target-dir", str(root / "cargo")]]
    assert build.verify(root, SOURCE, record["executable_sha256"]) == record
    with pytest.raises(FileExistsError):
        build.stage(root, SOURCE)
    assert len(commands) == 1
    (staged_runner / "Cargo.lock").write_text("synthetic changed lock")
    with pytest.raises(build.EvidenceValidationError):
        build.verify(root, SOURCE, record["executable_sha256"])
    (staged_runner / "Cargo.lock").write_text("synthetic resolved lock")
    build.executable(root).write_bytes(b"replacement executable")
    with pytest.raises(build.EvidenceValidationError):
        build.verify(root, SOURCE, record["executable_sha256"])


@pytest.mark.parametrize("condition", ["protected-root", "inherited-profile", "platform-config"])
def test_unsafe_app_identity_inputs_block_before_staging(staged_runner, monkeypatch, condition):
    if condition == "protected-root":
        (Path(os.environ["LOCALAPPDATA"]) / build.PROTECTED_IDS[0]).mkdir(parents=True)
    elif condition == "inherited-profile":
        monkeypatch.setenv("WEBVIEW2_USER_DATA_FOLDER", "inherited")
    else:
        (staged_runner / "tauri.windows.conf.json").write_text("{}")
    monkeypatch.setattr(build.subprocess, "run", lambda *a, **kw: pytest.fail("Cargo should not run"))
    root = build.stage_root(SOURCE)
    with pytest.raises(build.EvidenceValidationError):
        build.stage(root, SOURCE)
    assert not root.exists()


def test_local_cli_refuses_before_staging(tmp_path):
    env = {**os.environ, "GITHUB_ACTIONS": "false", "GITHUB_EVENT_NAME": "push",
           "GITHUB_REF_NAME": build.BRANCH, "GITHUB_RUN_ATTEMPT": "1",
           "GITHUB_RUN_ID": "123", "RUNNER_TEMP": str(tmp_path),
           "PILOTODIN_N12_APPROVED_SOURCE": SOURCE, "PILOTODIN_P4_UNPACKAGED_NATIVE_DEV_CONSENT": build.CONSENT}
    result = subprocess.run([sys.executable, "-B", "-m", "qa.p4_research.n12_app_build", "stage", "--source", SOURCE],
                            cwd=build.REPO, env=env, capture_output=True, text=True, timeout=15)
    assert result.returncode == 2
    assert "requires disposable hosted Windows" in result.stderr
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize("failure", ["retry", "wrong-source", "tracked-change"])
def test_stage_requires_first_attempt_and_clean_approved_source(staged_runner, monkeypatch, failure):
    if failure == "retry":
        monkeypatch.setenv("GITHUB_RUN_ATTEMPT", "2")
    elif failure == "wrong-source":
        monkeypatch.setenv("PILOTODIN_N12_APPROVED_SOURCE", "b" * 40)
    else:
        monkeypatch.setattr(build, "git", lambda *args: SOURCE if args[0] == "rev-parse" else " M Cargo.toml")
    with pytest.raises(build.EvidenceValidationError):
        build.stage_root(SOURCE)
