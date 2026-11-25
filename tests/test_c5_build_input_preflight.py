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
from types import SimpleNamespace

import pytest
from tools import live_dev, build_input_preflight as preflight
from desktop import verify_inference_assets as assets

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


@pytest.mark.parametrize("pass_number", [1, 2])
def test_wheelhouse_both_scans_refuse_first_extra_entry(tmp_path, pass_number):
    row = candidate_wheel(tmp_path)
    real_scan = preflight.os.scandir
    visits = []
    calls = 0

    class ExtraEntries:
        def __enter__(self):
            def entries():
                visits.append("expected")
                yield SimpleNamespace(name=row["filename"])
                visits.append("extra")
                yield SimpleNamespace(name="unexpected.whl")
                raise AssertionError("enumeration did not stop at first unexpected entry")
            return entries()

        def __exit__(self, *args):
            return False

    def scan(path):
        nonlocal calls
        calls += 1
        return ExtraEntries() if calls == pass_number else real_scan(path)

    before = snapshot(tmp_path)
    with patch.object(preflight.os, "scandir", side_effect=scan):
        with pytest.raises(preflight.Blocked, match="UNEXPECTED_WHEELHOUSE_ENTRY"):
            preflight.verify_candidate_wheel_bytes(tmp_path, [row], {"py3-none-any"})
    assert visits == ["expected", "extra"]
    assert snapshot(tmp_path) == before


@pytest.mark.parametrize("filename", [
    "fixture.package-1.2.3-py3-none-any.whl",
    "fixture+package-1.2.3-py3-none-any.whl",
    "fixture_package-1.2.3-PY3-none-any.whl",
    "fixture_package-1.2.3-py3-none-any.whl\n",
])
def test_candidate_filename_grammar_rejects_noncanonical_spelling(tmp_path, filename):
    row = candidate_wheel(tmp_path)
    row["filename"] = filename
    with pytest.raises(preflight.Blocked):
        preflight.validate_candidate_wheels([row], {"py3-none-any"})


def test_schema_matches_candidate_filename_and_version_patterns():
    import re
    doc = json.loads((ROOT / "contracts/build_inputs_v1.schema.json").read_text())
    properties = doc["$defs"]["candidateWheel"]["properties"]
    assert properties["filename"]["pattern"] == "^" + preflight.FILENAME.pattern + "$"
    assert properties["version"]["pattern"] == "^" + preflight.VERSION.pattern + "$"


def test_observed_inventory_is_not_an_expected_lock_or_authority():
    inventory = preflight.strict_json(
        (ROOT / "contracts/c5_observed_python_wheels_2026-11-25.json").read_bytes())
    assert inventory["schema_version"] == 1
    assert len(inventory["profiles"]) == 2
    sets = []
    for profile in inventory["profiles"]:
        assert profile["status"] == "OBSERVED_ONLY_BLOCKED"
        rows = profile["selected_wheels"]
        assert len(rows) == 49
        assert len({row["name"] for row in rows}) == 49
        assert all(preflight.FILENAME.fullmatch(row["filename"]) for row in rows)
        assert all(row[key] is None for row in rows
                   for key in ("artifact_sha256", "artifact_bytes", "requires_dist", "license_review"))
        assert profile["observed_cpython"].startswith("3.11.")
        with pytest.raises(preflight.Blocked):
            preflight.validate_candidate_wheels(rows, {"py3-none-any"})
        sets.append({row["name"] for row in rows})
    assert sets[0] - sets[1] == {"colorama"}
    assert sets[1] - sets[0] == {"uvloop"}


@pytest.mark.parametrize("name,reason", [
    ("Build_Python_Sidecar.ps1", "C5_SIDECAR_BUILD_BLOCKED"),
    ("Stage_Pinned_Offline_AI.ps1", "C5_AI_ACQUISITION_BLOCKED"),
    ("Stage_Bundled_Inference.ps1", "C5_AI_STAGING_BLOCKED"),
])
def test_mutating_entrypoints_are_unconditionally_frozen(name, reason):
    body = (ROOT / "desktop" / name).read_text()
    lines = [line.strip() for line in body.splitlines()
             if line.strip() and not line.lstrip().startswith("#")]
    assert len(lines) == 2
    assert lines[0].startswith("Write-Error 'STOP: " + reason)
    assert lines[0].endswith("-ErrorAction Continue")
    assert lines[1] == "exit 2"


def test_production_inference_preflight_cannot_bless_any_root(tmp_path):
    with patch.object(assets, "checked_directory") as check, \
            patch.object(assets, "read_exact") as read, \
            patch.dict(os.environ, {"PILOTODIN_ALLOW_BUILD": "1",
                                    "PILOTODIN_EXPECTED_MODEL_SHA256": "0" * 64}):
        with pytest.raises(preflight.Blocked, match="C5_INFERENCE_PROVENANCE_BLOCKED"):
            assets.verify(tmp_path)
        check.assert_not_called()
        read.assert_not_called()
    assert not list(tmp_path.iterdir())


def inert_pe(*, dll=False, machine=0x8664):
    # Header-only inert synthetic data. No executable sections or machine code.
    data = bytearray(128)
    data[:2] = b"MZ"
    data[60:64] = (64).to_bytes(4, "little")
    data[64:68] = b"PE\0\0"
    data[68:70] = machine.to_bytes(2, "little")
    data[84:86] = (2).to_bytes(2, "little")
    data[86:88] = (0x2002 if dll else 0x0002).to_bytes(2, "little")
    data[88:90] = (0x20b).to_bytes(2, "little")
    return bytes(data)


def inference_fixture(root):
    base = root / "frontend" / "src-tauri"
    models = base / "resources" / "models"
    dlls = base / "resources" / "llama-runtime"
    notices = base / "resources" / "licenses"
    binary = base / "binaries"
    for directory in (models, dlls, notices, binary):
        directory.mkdir(parents=True)
    def put(path, data):
        path.write_bytes(data)
        return {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}
    expected = {
        "model": put(models / assets.MODEL_FILE, b"GGUF\x03\0\0\0fixture"),
        "server": put(binary / assets.SERVER_FILE, inert_pe()),
        "dlls": {"mock.dll": put(dlls / "mock.dll", inert_pe(dll=True))},
        "notices": {name: put(notices / name, b"inert synthetic notice")
                    for name in assets.REQUIRED_NOTICES},
    }
    (models / assets.RECEIPT).write_text(json.dumps(assets.expected_receipt(expected)),
                                         encoding="utf-8")
    return expected, models, binary, dlls, notices


def test_candidate_inference_independent_exact_inventory_is_read_only(tmp_path):
    expected, *_ = inference_fixture(tmp_path)
    before = snapshot(tmp_path)
    with patch.object(subprocess, "run") as run, patch.object(subprocess, "Popen") as popen:
        assets.verify_candidate_bundle(tmp_path, expected)
        run.assert_not_called()
        popen.assert_not_called()
    assert snapshot(tmp_path) == before


@pytest.mark.parametrize("kind", [
    "model_changed", "server_changed", "dll_changed", "notice_changed",
    "extra_model", "extra_dll", "extra_notice", "missing_dll", "missing_notice",
    "empty_expected_dlls", "case_collision", "unsafe_dll", "receipt_duplicate",
    "receipt_unknown", "receipt_bool", "self_blessed_hash", "wrong_machine",
    "wrong_dll_role", "wrong_gguf",
])
def test_candidate_inference_refuses_unreviewed_or_mismatched_bytes(tmp_path, kind):
    expected, models, binary, dlls, notices = inference_fixture(tmp_path)
    receipt = models / assets.RECEIPT
    model = models / assets.MODEL_FILE
    server = binary / assets.SERVER_FILE
    dll = dlls / "mock.dll"
    notice = notices / "THIRD-PARTY-SOURCES.txt"
    paths = {"model_changed": model, "server_changed": server,
             "dll_changed": dll, "notice_changed": notice}
    if kind in paths:
        path = paths[kind]
        path.write_bytes(b"x" * path.stat().st_size)
    elif kind in ("extra_model", "extra_dll", "extra_notice"):
        {"extra_model": models, "extra_dll": dlls, "extra_notice": notices}[kind].joinpath("unknown.txt").write_bytes(b"x")
    elif kind == "missing_dll":
        dll.unlink()
    elif kind == "missing_notice":
        notice.unlink()
    elif kind == "empty_expected_dlls":
        expected["dlls"] = {}
    elif kind == "case_collision":
        expected["dlls"]["MOCK.DLL"] = expected["dlls"]["mock.dll"]
    elif kind == "unsafe_dll":
        expected["dlls"]["../bad.dll"] = expected["dlls"]["mock.dll"]
    elif kind == "receipt_duplicate":
        receipt.write_text(receipt.read_text().replace("{", '{"schema_version":1,', 1))
    elif kind == "receipt_unknown":
        doc = json.loads(receipt.read_text())
        doc["approval"] = True
        receipt.write_text(json.dumps(doc))
    elif kind == "receipt_bool":
        doc = json.loads(receipt.read_text())
        doc["schema_version"] = True
        receipt.write_text(json.dumps(doc))
    elif kind == "self_blessed_hash":
        dll.write_bytes(b"x" * dll.stat().st_size)
        doc = json.loads(receipt.read_text())
        doc["runtime_dll_sha256"]["mock.dll"] = hashlib.sha256(dll.read_bytes()).hexdigest()
        receipt.write_text(json.dumps(doc))
    else:
        path, row, data = {
            "wrong_machine": (server, expected["server"], inert_pe(machine=0x14c)),
            "wrong_dll_role": (dll, expected["dlls"]["mock.dll"], inert_pe()),
            "wrong_gguf": (model, expected["model"], b"GGUF\xff\0\0\0fixture"),
        }[kind]
        path.write_bytes(data)
        row.update(bytes=len(data), sha256=hashlib.sha256(data).hexdigest())
        receipt.write_text(json.dumps(assets.expected_receipt(expected)))
    before = snapshot(tmp_path)
    with pytest.raises(preflight.Blocked):
        assets.verify_candidate_bundle(tmp_path, expected)
    assert snapshot(tmp_path) == before


def test_candidate_inference_rejects_linked_dll(tmp_path):
    expected, _, _, dlls, _ = inference_fixture(tmp_path)
    dll = dlls / "mock.dll"
    outside = tmp_path.parent / (tmp_path.name + "-outside.dll")
    try:
        os.link(dll, outside)
    except OSError:
        pytest.skip("hardlink unavailable")
    try:
        with pytest.raises(preflight.Blocked):
            assets.verify_candidate_bundle(tmp_path, expected)
    finally:
        outside.unlink()


def test_read_exact_prefix_is_bounded_and_from_hashed_bytes(tmp_path):
    path = tmp_path / "inert"
    content = b"header" + b"x" * 70000
    path.write_bytes(content)
    assert preflight.read_exact(path, size=len(content), prefix_bytes=6) == (
        hashlib.sha256(content).hexdigest(), b"header")
    with pytest.raises(preflight.Blocked):
        preflight.read_exact(path, size=len(content), prefix_bytes=65537)


def test_legacy_analytics_digest_import_remains_read_only(tmp_path, monkeypatch):
    # Existing analytics QA modules import the top-level desktop module.
    # Reproduce that import route as well as the package import.
    import importlib
    monkeypatch.syspath_prepend(str(ROOT / "desktop"))
    legacy = importlib.import_module("verify_inference_assets")
    cases = importlib.import_module("offline_analytics_cases")
    assert cases.sha256 is legacy.sha256
    path = tmp_path / "inert.bin"
    data = b"synthetic read-only digest fixture"
    path.write_bytes(data)
    before = snapshot(tmp_path)
    assert legacy.sha256(path) == hashlib.sha256(data).hexdigest()
    assert assets.sha256(path) == hashlib.sha256(data).hexdigest()
    with pytest.raises(preflight.Blocked, match="C5_INFERENCE_PROVENANCE_BLOCKED"):
        legacy.verify(tmp_path)
    assert snapshot(tmp_path) == before


def test_c5_release_graph_exact_pinned_candidate_profiles():
    from qa.c5_metadata import graph_review as graph
    report = graph.review(ROOT)
    assert report["status"] == "BLOCKED"
    assert report["receipt_sha256"] == graph.RECEIPT_SHA
    windows, linux = report["profiles"]
    for p in (windows, linux):
        assert p["status"] == "BLOCKED"
        assert p["declared_graph"] == "COMPATIBLE_PARTIAL"
        assert len(p["root_requirements"]) == 14
        assert p["reachable_packages"] == len(p["nodes"]) == 49
        assert len(p["active_edges"]) == 59
        assert p["enabled_extras"] == {"uvicorn": ["standard"]}
        assert all(n["selected_wheel_metadata"] == "UNVERIFIED" for n in p["nodes"])
        assert all(n["license_state"] == "DECLARED_NOT_REVIEWED" for n in p["nodes"])
        assert [n["name"] for n in p["nodes"] if n["release_python"] == "UNKNOWN"] == ["pytz"]
    assert len(windows["unknown_release_dependencies"]) == 23
    assert len(linux["unknown_release_dependencies"]) == 22
    assert windows["inactive_declarations"] == 288
    assert linux["inactive_declarations"] == 301
    win_edges = {(e["from"], e["to"]) for e in windows["active_edges"]}
    lin_edges = {(e["from"], e["to"]) for e in linux["active_edges"]}
    assert win_edges - lin_edges == {("pytest", "colorama")}
    assert lin_edges - win_edges == {("uvicorn", "uvloop")}


def test_c5_graph_rejects_wrong_platform_marker_and_version():
    from qa.c5_metadata import graph_review as graph
    from packaging.requirements import Requirement
    from packaging.tags import Tag
    env = graph.target_environment("3.11.9", "win32")
    assert not graph.marker_active(Requirement('uvloop; sys_platform != "win32"'), env, {"standard"})
    with pytest.raises(preflight.Blocked, match="UNVERIFIED_MARKER_ENVIRONMENT"):
        graph.marker_active(Requirement('fixture; platform_release == "1"'), env, set())
    with pytest.raises(preflight.Blocked, match="DECLARED_VERSION_CONFLICT"):
        graph.check_requirement(Requirement("fixture>=2"), {"fixture": {"version": "1"}})
    with pytest.raises(preflight.Blocked, match="DECLARED_DEPENDENCY_MISSING"):
        graph.check_requirement(Requirement("fixture"), {})
    assert Tag("cp310", "abi3", "win_amd64") in graph.candidate_tags("win32")
    assert Tag("cp311", "cp311", "win_amd64") not in graph.candidate_tags("linux")
    assert Tag("cp311", "cp311", "manylinux_2_29_x86_64") not in graph.candidate_tags("linux")


def test_c5_graph_rejects_changed_receipt_before_parsing(monkeypatch):
    from qa.c5_metadata import graph_review as graph
    real = graph.canonical_source
    def changed(root, path):
        raw = real(root, path)
        return raw + b"\n" if path == graph.RECEIPT else raw
    monkeypatch.setattr(graph, "canonical_source", changed)
    with pytest.raises(preflight.Blocked, match="METADATA_RECEIPT_PIN"):
        graph.review(ROOT)


def test_c5_graph_distinguishes_unknown_python_from_incompatible():
    from qa.c5_metadata import graph_review as graph
    assert graph.check_python(None, "3.11.9") == "UNKNOWN"
    assert graph.check_python(">=3.11,<4", "3.11.9") == "COMPATIBLE_DECLARATION"
    with pytest.raises(preflight.Blocked, match="REQUIRES_PYTHON_CONFLICT"):
        graph.check_python(">=3.12", "3.11.9")


def c5_zip_fixture(tmp_path, names=None, compression=None):
    import zipfile
    from tools import c5_archive_preflight as archive
    names = names if names is not None else [
        ("runtime/llama-server.exe", b"inert server header fixture"),
        ("runtime/mock.dll", b"inert library fixture" * 5000),
        ("LICENSE.txt", b"synthetic notice"),
        ("empty.txt", b""),
    ]
    path = tmp_path / "fixture.zip"
    with zipfile.ZipFile(path, "w", compression=compression if compression is not None
                         else zipfile.ZIP_DEFLATED) as z:
        for name, data in names:
            z.writestr(name, data)
    raw = path.read_bytes()
    expected = {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest(),
                "members": {name: {"bytes": len(data),
                                   "sha256": hashlib.sha256(data).hexdigest()}
                            for name, data in names}}
    return archive, path, expected


@pytest.mark.parametrize("compression", [0, 8])
def test_c5_zip_candidate_exact_bytes_read_only(tmp_path, compression):
    archive, path, expected = c5_zip_fixture(tmp_path, compression=compression)
    before = snapshot(tmp_path)
    with patch.object(subprocess, "run") as run, patch.object(subprocess, "Popen") as popen:
        archive.verify_candidate_archive(path, expected)
        run.assert_not_called()
        popen.assert_not_called()
    assert snapshot(tmp_path) == before


@pytest.mark.parametrize("bad_name", [
    "../escape.dll", "/absolute.dll", "C:/drive.dll", "dir\\escape.dll",
    "runtime.dll:stream", "CON.dll", "dir/NUL.txt", "dir//file.dll",
    "dir/../file.dll", "dir./file.dll", "dir/file.dll.", "dir/file .dll",
    "dir/\u00e9.dll", "dir/",
])
def test_c5_zip_rejects_unsafe_expected_member(tmp_path, bad_name):
    archive, path, expected = c5_zip_fixture(tmp_path, [(bad_name, b"inert")])
    before = snapshot(tmp_path)
    with pytest.raises(preflight.Blocked, match="UNSAFE_ZIP_NAME"):
        archive.verify_candidate_archive(path, expected)
    assert snapshot(tmp_path) == before


@pytest.mark.parametrize("names", [
    [("runtime/a.dll", b"a"), ("Runtime/b.dll", b"b")],
    [("a.dll", b"a"), ("A.dll", b"b")],
    [("runtime", b"a"), ("runtime/b.dll", b"b")],
])
def test_c5_zip_rejects_path_collisions(tmp_path, names):
    archive, path, expected = c5_zip_fixture(tmp_path, names)
    with pytest.raises(preflight.Blocked, match="ZIP_.*COLLISION|ZIP_DUPLICATE_NAME"):
        archive.verify_candidate_archive(path, expected)


@pytest.mark.parametrize("mutation", [
    "wrong_archive_hash", "wrong_member_hash", "missing_expected",
    "extra_expected", "local_name", "local_offset", "central_link",
    "central_reparse", "central_encrypted", "central_zip64", "central_method",
    "trailer", "crc", "compressed_data", "duplicate_central_name",
])
def test_c5_zip_refuses_malformed_or_mismatched_bytes(tmp_path, mutation):
    import struct
    archive, path, expected = c5_zip_fixture(
        tmp_path, [("a.dll", b"first inert fixture"), ("b.dll", b"other inert fixture")])
    raw = bytearray(path.read_bytes())
    central = raw.index(b"PK\x01\x02")
    second = raw.index(b"PK\x01\x02", central + 4)
    if mutation == "wrong_archive_hash":
        expected["sha256"] = "0" * 64
    elif mutation == "wrong_member_hash":
        expected["members"]["a.dll"]["sha256"] = "0" * 64
    elif mutation == "missing_expected":
        del expected["members"]["a.dll"]
    elif mutation == "extra_expected":
        expected["members"]["extra.dll"] = expected["members"]["a.dll"]
    else:
        if mutation == "local_name":
            raw[archive.LOCAL.size] = ord("z")
        elif mutation == "local_offset":
            struct.pack_into("<I", raw, second + 42, 0)
        elif mutation == "central_link":
            struct.pack_into("<I", raw, central + 38, 0o120777 << 16)
        elif mutation == "central_reparse":
            struct.pack_into("<I", raw, central + 38, 0x400)
        elif mutation == "central_encrypted":
            struct.pack_into("<H", raw, central + 8, 1)
        elif mutation == "central_zip64":
            struct.pack_into("<H", raw, central + 6, 45)
        elif mutation == "central_method":
            struct.pack_into("<H", raw, central + 10, 99)
        elif mutation == "trailer":
            raw.extend(b"trailer")
        elif mutation == "crc":
            struct.pack_into("<I", raw, central + 16, 0)
            struct.pack_into("<I", raw, 14, 0)
        elif mutation == "compressed_data":
            raw[archive.LOCAL.size + len("a.dll")] ^= 0xff
        elif mutation == "duplicate_central_name":
            raw[second + archive.CENTRAL.size] = ord("a")
        path.write_bytes(raw)
        expected["bytes"] = len(raw)
        expected["sha256"] = hashlib.sha256(raw).hexdigest()
    before = snapshot(tmp_path)
    with pytest.raises(preflight.Blocked):
        archive.verify_candidate_archive(path, expected)
    assert snapshot(tmp_path) == before


def test_c5_zip_bounds_refuse_before_reading(tmp_path):
    archive, path, expected = c5_zip_fixture(tmp_path)
    expected["bytes"] = archive.MAX_ARCHIVE + 1
    with patch.object(archive, "read_exact") as read:
        with pytest.raises(preflight.Blocked, match="ZIP_EXPECTED_ARCHIVE_IDENTITY"):
            archive.verify_candidate_archive(path, expected)
        read.assert_not_called()
    expected["bytes"] = path.stat().st_size
    expected["members"]["runtime/mock.dll"]["bytes"] = archive.MAX_MEMBER + 1
    with patch.object(archive, "read_exact") as read:
        with pytest.raises(preflight.Blocked, match="ZIP_EXPECTED_MEMBER_IDENTITY"):
            archive.verify_candidate_archive(path, expected)
        read.assert_not_called()


def test_c5_zip_rejects_actual_extra_safe_name_even_with_new_archive_hash(tmp_path):
    archive, path, expected = c5_zip_fixture(tmp_path, [("expected.dll", b"fixture")])
    expected["members"] = {"other.dll": expected["members"]["expected.dll"]}
    with pytest.raises(preflight.Blocked, match="ZIP_MEMBER_NOT_EXPECTED"):
        archive.verify_candidate_archive(path, expected)
