"""Source and disposable readiness guards only. Never run an installer or native tool."""
from pathlib import Path
from unittest.mock import patch
import ast
import os

import pytest
from tools import live_dev

ROOT = Path(__file__).resolve().parents[1]


def prepared(tmp_path):
    root = tmp_path
    venv = root / ".venv-live"
    cache = root / ".pilotodin-dev-cache"
    frontend = root / "frontend"
    files = {
        venv / "Scripts" / "python.exe": b"inert",
        root / "backend" / "requirements.txt": b"fastapi>=0.110,<1\n",
        frontend / "package.json": b'{"name":"fixture"}',
        frontend / "package-lock.json": b'{"lockfileVersion":3}',
        frontend / "node_modules" / ".bin" / "vite.cmd": b"inert",
    }
    for path, value in files.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(value)
    cache.mkdir()
    (cache / "python-requirements.sha256").write_text(
        live_dev.fingerprint(root / "backend" / "requirements.txt"), encoding="utf-8")
    (cache / "frontend-requirements.sha256").write_text(
        live_dev.fingerprint(frontend / "package.json", frontend / "package-lock.json"), encoding="utf-8")
    return root, venv, cache, frontend


def snapshot(root):
    return {str(p.relative_to(root)): p.read_bytes() for p in root.rglob("*") if p.is_file()}


def test_ready_legacy_files_remain_unchanged(tmp_path):
    args = prepared(tmp_path)
    before = snapshot(tmp_path)
    with patch.object(live_dev.subprocess, "run") as run:
        assert live_dev.require_prepared_files(*args) == args[1] / "Scripts" / "python.exe"
        run.assert_not_called()
    assert snapshot(tmp_path) == before


@pytest.mark.parametrize("relative", [
    ".venv-live/Scripts/python.exe", "backend/requirements.txt",
    "frontend/package.json", "frontend/package-lock.json",
    "frontend/node_modules/.bin/vite.cmd", ".pilotodin-dev-cache/python-requirements.sha256",
    ".pilotodin-dev-cache/frontend-requirements.sha256",
])
def test_missing_input_refuses_without_repair(tmp_path, relative):
    args = prepared(tmp_path)
    (tmp_path / relative).unlink()
    before = snapshot(tmp_path)
    with patch.object(live_dev.subprocess, "run") as run:
        with pytest.raises(RuntimeError, match="C5_DEV_INPUT_MISSING"):
            live_dev.require_prepared_files(*args)
        run.assert_not_called()
    assert snapshot(tmp_path) == before


@pytest.mark.parametrize("relative", ["backend/requirements.txt", "frontend/package.json", "frontend/package-lock.json"])
def test_changed_input_refuses_without_repair(tmp_path, relative):
    args = prepared(tmp_path)
    (tmp_path / relative).write_bytes(b"changed")
    before = snapshot(tmp_path)
    with pytest.raises(RuntimeError, match="C5_DEV_INPUT_CHANGED"):
        live_dev.require_prepared_files(*args)
    assert snapshot(tmp_path) == before


def test_python_probe_has_no_install_or_ambient_pip_configuration(tmp_path):
    root, venv, _, _ = prepared(tmp_path)
    with patch.dict(os.environ, {"PIP_INDEX_URL": "https://example.invalid", "PYTHONPATH": "foreign"}):
        with patch.object(live_dev.subprocess, "run") as run:
            live_dev.verify_python_environment(venv / "Scripts" / "python.exe", venv,
                                               root / "backend" / "requirements.txt")
    assert run.call_count == 2
    for call in run.call_args_list:
        command = call.args[0]
        assert "install" not in command
        assert "-I" in command and "-B" in command
        assert call.kwargs["check"] is True
        assert call.kwargs["env"]["PIP_CONFIG_FILE"] == os.devnull
        assert "PIP_INDEX_URL" not in call.kwargs["env"]
        assert "PYTHONPATH" not in call.kwargs["env"]
    assert run.call_args.args[0][-1] == "check"


def test_unknown_requirements_refuse_before_subprocess(tmp_path):
    root, venv, _, _ = prepared(tmp_path)
    req = root / "backend" / "requirements.txt"
    req.write_text("-e foreign\n", encoding="utf-8")
    with patch.object(live_dev.subprocess, "run") as run:
        with pytest.raises(RuntimeError, match="FORMAT_UNREVIEWED"):
            live_dev.verify_python_environment(venv / "Scripts" / "python.exe", venv, req)
        run.assert_not_called()


def test_source_entrypoint_order_and_no_install_fallback():
    installer = (ROOT / "desktop/Build_Windows_Installer.ps1").read_text()
    executable = [line.strip() for line in installer.splitlines() if line.strip() and not line.lstrip().startswith("#")]
    assert len(executable) == 2
    assert executable[0].startswith("Write-Error 'STOP:")
    assert executable[1] == "exit 2"
    frontend = (ROOT / "desktop/Verify_Frontend_Windows.ps1").read_text()
    assert frontend.index("verify-npm-lock.mjs") < frontend.index("New-Item")
    assert "'npm_install'" not in frontend and "'install','--no-audit'" not in frontend
    live = (ROOT / "tools/live_dev.py").read_text()
    ast.parse(live)
    assert live.index("python = require_prepared_files") < live.index("subprocess.Popen")
    assert live.index("verify_python_environment(python, VENV") < live.index("subprocess.Popen")
    assert "CACHE.mkdir" not in live and "pip\", \"install" not in live and 'npm_action' not in live
    for name in ("frontend-compile.yml", "build-e-verification.yml"):
        workflow = (ROOT / ".github/workflows" / name).read_text()
        assert "npm install" not in workflow
        assert workflow.index("verify-npm-lock.mjs") < workflow.index("npm ci")
    cargo = (ROOT / ".github/workflows/p4-product-cargo-resolution.yml").read_text()
    assert "cargo generate-lockfile" not in cargo
    assert cargo.index("test -f Cargo.lock") < cargo.index("cargo metadata --locked")
    assert "git diff --exit-code -- Cargo.lock" in cargo
    self_test = (ROOT / "Self_Test_PilotODIN.bat").read_text()
    assert "pip install" not in self_test and self_test.index("verify-npm-lock.mjs") < self_test.index("-m pytest")
