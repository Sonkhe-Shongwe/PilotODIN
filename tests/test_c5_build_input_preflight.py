"""Source and disposable readiness guards only. Never run an installer or native tool."""
from pathlib import Path
from unittest.mock import patch
import ast
import copy
import hashlib
import json
import os
import shutil
import subprocess

import pytest
from tools import live_dev, build_input_preflight as preflight

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


def test_policy_source_pins_and_all_candidate_profiles_blocked(capsys):
    policy = preflight.audit_policy(ROOT)
    assert len(policy["profiles"]) == 4
    assert preflight.main(["--audit-policy"]) == 0
    assert "BLOCKED_POLICY_VALID" in capsys.readouterr().out
    for row in policy["profiles"]:
        with patch.dict(os.environ, {"PILOTODIN_ALLOW_BUILD": "1", "PIP_INDEX_URL": "foreign"}):
            assert preflight.main(["--profile", row["id"]]) == 2
        output = json.loads(capsys.readouterr().out)
        assert output["status"] == "BLOCKED"
        assert output["blockers"]
        if row["planned_lock"]:
            assert not (ROOT / row["planned_lock"]).exists()


@pytest.mark.parametrize("change", [
    lambda p: p["profiles"].pop(),
    lambda p: p["profiles"].append(copy.deepcopy(p["profiles"][0])),
    lambda p: p["profiles"][0].update(status="READY"),
    lambda p: p["profiles"][0].update(blockers=[]),
    lambda p: p["profiles"][0].update(planned_lock="../foreign"),
    lambda p: p["source_inputs"][0].update(path="../foreign"),
    lambda p: p.update(schema_version=True),
    lambda p: p.update(override=True),
])
def test_policy_cannot_grant_unreviewed_readiness(change):
    doc = preflight.audit_policy(ROOT)
    change(doc)
    with pytest.raises(preflight.Blocked):
        preflight.validate_policy(doc)


def test_policy_duplicate_and_nonfinite_json_refused():
    for raw in (b'{"a":1,"a":2}', b'{"a":NaN}', b'{"a":1e2,"\\u0061":2}'):
        with pytest.raises(preflight.Blocked):
            preflight.strict_json(raw)


def candidate_wheel(tmp_path):
    # These are deliberately inert bytes, not a real executable wheel.
    data = b"synthetic non-wheel test input"
    filename = "fixture_package-1.2.3-py3-none-any.whl"
    row = {
        "name": "fixture-package",
        "version": "1.2.3",
        "filename": filename,
        "bytes": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
        "source": "https://files.pythonhosted.org/packages/ab/cd/" + "0"*60 + "/" + filename,
        "metadata_source": "https://pypi.org/pypi/fixture-package/1.2.3/json",
        "license_expression": "MIT",
        "license_review": "synthetic test only",
    }
    (tmp_path / filename).write_bytes(data)
    return row


def test_candidate_wheel_exact_bytes_read_only(tmp_path):
    row = candidate_wheel(tmp_path)
    before = snapshot(tmp_path)
    with patch.object(subprocess, "run") as run, patch.object(subprocess, "Popen") as popen:
        assert preflight.verify_candidate_wheel_bytes(tmp_path, [row], {"py3-none-any"}) == {
            row["filename"]: row["sha256"]
        }
        run.assert_not_called()
        popen.assert_not_called()
    assert snapshot(tmp_path) == before


@pytest.mark.parametrize("mutate", [
    lambda p, r: (p / r["filename"]).unlink(),
    lambda p, r: (p / "extra.whl").write_bytes(b"extra"),
    lambda p, r: (p / "unreviewed").mkdir(),
    lambda p, r: (p / r["filename"]).write_bytes(b"x" * r["bytes"]),
    lambda p, r: (p / r["filename"]).write_bytes(b"short"),
    lambda p, r: r.update(bytes=True),
    lambda p, r: r.update(sha256="x" * 64),
    lambda p, r: r.update(filename="../outside.whl"),
    lambda p, r: r.update(filename="fixture_package-1.2.3.tar.gz"),
    lambda p, r: r.update(name="Fixture_Package"),
    lambda p, r: r.update(version="9.9.9"),
    lambda p, r: r.update(source="https://foreign.invalid/fixture.whl"),
    lambda p, r: r.update(metadata_source="https://foreign.invalid/metadata"),
    lambda p, r: r.update(license_expression="unknown"),
    lambda p, r: r.update(license_review="pending"),
    lambda p, r: r.update(unreviewed=True),
])
def test_candidate_wheel_refuses_drift_or_unreviewed_input(tmp_path, mutate):
    row = candidate_wheel(tmp_path)
    mutate(tmp_path, row)
    before = snapshot(tmp_path)
    with patch.object(subprocess, "run") as run:
        with pytest.raises(preflight.Blocked):
            preflight.verify_candidate_wheel_bytes(tmp_path, [row], {"py3-none-any"})
        run.assert_not_called()
    assert snapshot(tmp_path) == before


def test_candidate_wheel_requires_independently_reviewed_compatible_tags(tmp_path):
    row = candidate_wheel(tmp_path)
    for tags in (set(), {"cp311-cp311-win_amd64"}, {"bad tag"}):
        with pytest.raises(preflight.Blocked):
            preflight.verify_candidate_wheel_bytes(tmp_path, [row], tags)
    with pytest.raises(preflight.Blocked):
        preflight.verify_candidate_wheel_bytes(tmp_path, [row, row], {"py3-none-any"})


def test_hardlink_wheel_refused_when_supported(tmp_path):
    row = candidate_wheel(tmp_path)
    source = tmp_path / row["filename"]
    outside = tmp_path.parent / (tmp_path.name + "-outside")
    try:
        os.link(source, outside)
    except OSError:
        pytest.skip("hardlink unavailable in disposable fixture")
    try:
        with pytest.raises(preflight.Blocked):
            preflight.verify_candidate_wheel_bytes(tmp_path, [row], {"py3-none-any"})
    finally:
        outside.unlink()


def test_symlink_wheel_refused_when_supported(tmp_path):
    row = candidate_wheel(tmp_path)
    source = tmp_path / row["filename"]
    outside = tmp_path.parent / (tmp_path.name + "-outside")
    outside.write_bytes(source.read_bytes())
    source.unlink()
    try:
        try:
            source.symlink_to(outside)
        except OSError:
            pytest.skip("symlink unavailable in disposable fixture")
        with pytest.raises(preflight.Blocked):
            preflight.verify_candidate_wheel_bytes(tmp_path, [row], {"py3-none-any"})
    finally:
        outside.unlink()


def test_cargo_missing_or_linked_inputs_refuse_before_command(tmp_path):
    if os.name != "posix" or not shutil.which("bash"):
        pytest.skip("exact bash workflow guard is Linux-only")
    source = (ROOT / ".github/workflows/p4-product-cargo-resolution.yml").read_text()
    guard = source[source.index("          test -f Cargo.lock"):source.index("          python - <<'PY'")]
    assert "&&" not in guard
    assert 'cargo metadata --locked --no-deps --manifest-path "$PWD/Cargo.toml"' in source
    # Run only the extracted four read-only guard statements, never cargo.
    script = "set -euo pipefail\n" + guard + "\nprintf reached"
    for missing in ("Cargo.lock", "Cargo.toml"):
        for name in ("Cargo.lock", "Cargo.toml"):
            (tmp_path / name).write_text("inert")
        (tmp_path / missing).unlink()
        result = subprocess.run(["bash", "-c", script], cwd=tmp_path,
                                capture_output=True, text=True)
        assert result.returncode != 0 and not result.stdout
    for name in ("Cargo.lock", "Cargo.toml"):
        (tmp_path / name).write_text("inert")
    (tmp_path / "Cargo.toml").unlink()
    (tmp_path / "Cargo.toml").symlink_to(tmp_path / "Cargo.lock")
    result = subprocess.run(["bash", "-c", script], cwd=tmp_path,
                            capture_output=True, text=True)
    assert result.returncode != 0 and not result.stdout
    (tmp_path / "Cargo.toml").unlink()
    (tmp_path / "Cargo.toml").write_text("inert")
    result = subprocess.run(["bash", "-c", script], cwd=tmp_path,
                            capture_output=True, text=True)
    assert result.returncode == 0 and result.stdout == "reached"
