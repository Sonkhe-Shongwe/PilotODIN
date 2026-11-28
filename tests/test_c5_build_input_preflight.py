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
import sys
import zipfile
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
            assert (ROOT / row["planned_lock"]).is_file()


def test_reviewed_python_locks_match_pinned_graphs_and_stay_blocked():
    from packaging.requirements import Requirement
    from packaging.tags import cpython_tags, compatible_tags
    from packaging.utils import parse_wheel_filename, canonicalize_name
    from packaging.version import Version
    from packaging.specifiers import SpecifierSet

    def pinned(path, expected):
        raw = (ROOT / path).read_bytes().replace(b"\r\n", b"\n")
        assert hashlib.sha1(b"blob " + str(len(raw)).encode("ascii")
                            + b"\0" + raw).hexdigest() == expected
        return raw

    directory = "qa/c5_wheel_metadata/"
    plan_pin = "1aa96a7172508f94b2cdc4b7aabd65e3b8f21f89"
    plan = json.loads(pinned(directory + "wheel_acquisition_plan_20261125.json", plan_pin))
    candidates = json.loads(pinned(directory + "platform_lock_candidates_45703125465.json",
                                   "6b27407f4b24942c385179bb253f692370f21df7"))
    graphs = json.loads(pinned(directory + "combined_graph_receipt_45702239980.json",
                               "6c95b4263e9d0f831aa00cfa68e9cb8268aebbd7"))
    production = json.loads(pinned(directory + "production_graph_receipt_45705552265.json",
                                   "70cdac979b732aadfad0c51d7e159a60840cc1ef"))
    base = pinned("backend/requirements.txt", "30d347462aa29b4db9c7308079f231185f4c1703")
    extra = pinned("backend/requirements-test.txt", "0ed0b88920a281167cf1dc8a3ca038096bf1e7b8")
    roots = [Requirement(line) for line in base.decode().splitlines()
             if line and not line.startswith("#")]
    test_roots = roots + [Requirement(line) for line in extra.decode().splitlines()
                          if line and not line.startswith(("#", "-r "))]
    assert len(roots) == 10 and len(test_roots) == 14
    assert len(plan["wheels"]) == 68 and plan["status"] == "PROPOSAL_ONLY_DISABLED"
    assert production["declared_graph"] == "COMPATIBLE"
    assert production["issues"] == production["unused"] == []
    assert production["enabled_extras"] == {"uvicorn": ["standard"]}
    assert {str(r) for r in roots + [Requirement("pyinstaller==6.22.3"),
                                      Requirement("pyinstaller-hooks-contrib==2026.9")]} == set(production["roots"])
    assert graphs["status"] == "DECLARED_GRAPH_COMPATIBLE_NOT_INSTALLABLE"
    total = 0
    for profile in preflight.audit_policy(ROOT)["profiles"]:
        assert profile["status"] == "BLOCKED"
        path = profile["planned_lock"]
        if path is None:
            continue
        pid = profile["id"]
        is_production = profile["purpose"] == "production-build"
        windows = profile["platform"] == "windows"
        python = "3.11.9" if windows else "3.11.18"
        rows = sorted((r for r in plan["wheels"] if pid in r["profiles"]),
                      key=lambda r: r["name"])
        count = 43 if is_production else 49
        assert len(rows) == len({r["name"] for r in rows}) == count
        total += count
        if is_production:
            selected = production["nodes"]
            assert production["reachable"] == count
            assert production["unknown_requires_python"] == ["altgraph", "pytz"]
        else:
            candidate = next(c for c in candidates["candidates"]
                             if c["profile"] == pid and c["scope"] == "source-test")
            report = next(r for r in graphs["reports"]
                          if r["profile"] == pid and r["scope"] == "source-test")
            assert report["graph_status"] == "DECLARED_GRAPH_COMPATIBLE"
            assert report["issues"] == report["unused_selected"] == []
            assert report["reachable"] == count and report["roots"] == len(test_roots)
            assert report["python"] == candidate["python_candidate"] == python
            assert report["extras"] == candidate["extras"] == {"uvicorn": ["standard"]}
            assert candidate["unknown_requires_python"] == ["pytz"]
            selected = candidate["rows"]
        assert {(r["name"], r["version"], r["filename"], r["bytes"], r["sha256"],
                 r["metadata_sha256"]) for r in rows} == {
                 (r["name"], r["version"], r["filename"], r["expected_wheel_bytes"],
                  r["expected_wheel_sha256"], r["verified_metadata_sha256"]) for r in selected}
        platforms = ["win_amd64"] if windows else (
            [f"manylinux_2_{n}_x86_64" for n in range(28, 4, -1)]
            + ["manylinux2014_x86_64", "manylinux2010_x86_64", "manylinux1_x86_64"])
        tags = set(cpython_tags((3, 11), abis=["cp311"], platforms=platforms))
        tags.update(compatible_tags((3, 11), interpreter="cp311", platforms=platforms))
        names = {r["name"]: r for r in rows}
        required = roots + [Requirement("pyinstaller==6.22.3"),
                            Requirement("pyinstaller-hooks-contrib==2026.9")] if is_production else test_roots
        for req in required:
            assert req.specifier.contains(Version(names[canonicalize_name(req.name)]["version"]))
        for r in rows:
            name, version, _, wheel_tags = parse_wheel_filename(r["filename"])
            assert name == r["name"] and version == Version(r["version"]) and wheel_tags & tags
            if r["requires_python"] is not None:
                assert SpecifierSet(r["requires_python"]).contains(Version(python))
        header = (
            f"# PilotODIN C5 reviewed expected Python lock: {pid}\n"
            "# Definition only; profile BLOCKED. Not installation or acquisition authority.\n"
            f"# CPython 3.11 x64; reviewed metadata environment {python} (not selected interpreter distribution).\n"
            f"# Expected hashes from pinned plan {plan_pin}.\n"
            "# Use only with separately authorised, verified local wheelhouse and preflight.\n"
            "--no-index\n--only-binary=:all:\n--require-hashes\n\n"
        )
        expected = header + "".join(
            f"{r['name']}{'[standard]' if r['name'] == 'uvicorn' else ''}=={r['version']}"
            f" --hash=sha256:{r['sha256']}\n" for r in rows)
        assert (ROOT / path).read_text(encoding="ascii") == expected
    assert total == 141


@pytest.mark.parametrize("change", ["missing", "tampered", "extra-index", "crlf", "linked"])
def test_existing_preflight_checks_reviewed_lock_identity(tmp_path, change, monkeypatch, capsys):
    paths = set(preflight.SOURCE_PATHS) | set(preflight.REVIEWED_LOCK_PINS) | {preflight.POLICY_PATH}
    for relative in paths:
        dst = tmp_path / relative
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_bytes((ROOT / relative).read_bytes().replace(b"\r\n", b"\n"))
    original = preflight.audit_policy
    monkeypatch.setattr(preflight, "audit_policy", lambda: original(tmp_path))
    assert preflight.main(["--audit-policy"]) == 0
    capsys.readouterr()
    relative = "backend/locks/windows-x64-cp311-source-test.txt"
    path = tmp_path / relative
    if change == "missing":
        path.unlink()
    elif change == "tampered":
        path.write_bytes(path.read_bytes().replace(b"fastapi==", b"fastapx==", 1))
    elif change == "extra-index":
        path.write_bytes(path.read_bytes() + b"--extra-index-url https://foreign.invalid/\n")
    elif change == "crlf":
        path.write_bytes(path.read_bytes().replace(b"\n", b"\r\n"))
    else:
        outside = tmp_path / "outside.txt"
        outside.write_bytes(path.read_bytes())
        path.unlink()
        try:
            path.symlink_to(outside)
        except OSError:
            pytest.skip("symlinks unavailable")
    with patch.object(subprocess, "run") as run:
        result = preflight.main(["--audit-policy"])
        run.assert_not_called()
    output = capsys.readouterr()
    if change == "crlf":
        assert result == 0 and "BLOCKED_POLICY_VALID" in output.out
    else:
        assert result == 2 and "C5_PROFILE_POLICY_BLOCKED" in output.err


def test_pip_standard_offline_hash_dry_run_on_inert_wheel(tmp_path):
    # No importable code, build backend, direct URLs or dependencies. This is
    # only a disposable fixture demonstrating pip's own hash-checking mode.
    wheelhouse = tmp_path / "wheelhouse"
    wheelhouse.mkdir()
    scratch = tmp_path / "scratch"
    scratch.mkdir()
    wheel = wheelhouse / "c5_inert_fixture-1.0-py3-none-any.whl"
    dist = "c5_inert_fixture-1.0.dist-info"
    with zipfile.ZipFile(wheel, "w") as archive:
        archive.writestr(dist + "/METADATA",
                         "Metadata-Version: 2.1\nName: c5-inert-fixture\nVersion: 1.0\n")
        archive.writestr(dist + "/WHEEL",
                         "Wheel-Version: 1.0\nRoot-Is-Purelib: true\nTag: py3-none-any\n")
        archive.writestr(dist + "/RECORD",
                         dist + "/METADATA,,\n" + dist + "/WHEEL,,\n" + dist + "/RECORD,,\n")
    digest = hashlib.sha256(wheel.read_bytes()).hexdigest()
    lock = tmp_path / "fixture.txt"
    env = {k: v for k, v in os.environ.items()
           if not k.upper().startswith("PIP_") and k.upper() not in ("PYTHONPATH", "PYTHONHOME")}
    env.update(PIP_CONFIG_FILE=os.devnull, TMP=str(scratch), TEMP=str(scratch),
               TMPDIR=str(scratch), PYTHONDONTWRITEBYTECODE="1")
    cmd = [sys.executable, "-I", "-B", "-m", "pip", "--isolated",
           "--disable-pip-version-check", "--no-input", "--no-cache-dir",
           "install", "--dry-run", "--ignore-installed", "--no-deps",
           "--no-index", "--only-binary=:all:", "--require-hashes",
           "--find-links", str(wheelhouse), "-r", str(lock)]
    def invoke(expected):
        lock.write_text("--no-index\n--only-binary=:all:\n--require-hashes\n"
                        f"c5-inert-fixture==1.0 --hash=sha256:{expected}\n", encoding="ascii")
        before = snapshot(wheelhouse)
        result = subprocess.run(cmd, cwd=tmp_path, env=env, timeout=45,
                                capture_output=True, text=True)
        assert snapshot(wheelhouse) == before
        return result
    accepted = invoke(digest)
    assert accepted.returncode == 0, accepted.stderr
    assert "Would install c5-inert-fixture-1.0" in accepted.stdout
    refused = invoke("0" * 64)
    assert refused.returncode != 0 and "hash" in refused.stderr.lower()
    wheel.unlink()
    missing = invoke(digest)
    assert missing.returncode != 0 and "No matching distribution" in missing.stderr


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


def c5_stage_fixture(tmp_path):
    from qa.c5_metadata import synthetic_staging as stage
    root = stage.create_fixture_store(tmp_path / "c5-synthetic-store")
    _, source, expected = c5_zip_fixture(
        tmp_path, [("a.txt", b"old text"), ("nested/b.bin", b"inert fixture" * 100)])
    return stage, root, source, expected


def test_c5_stage_success_and_prior_generation_preserved(tmp_path):
    stage, root, source, expected = c5_stage_fixture(tmp_path)
    first = stage.stage_fixture(root, source, expected, None)
    assert stage.verify_generation(root, first)["archive"] == expected
    before = snapshot(root / first["generation"])
    _, source, newer = c5_zip_fixture(tmp_path, [("new.txt", b"second inert fixture")])
    second = stage.stage_fixture(root, source, newer, first)
    assert first["generation"] != second["generation"]
    assert snapshot(root / first["generation"]) == before
    assert stage.pointer_bytes(root) == stage.canonical(second)
    assert stage.verify_generation(root, second)["archive"] == newer
    assert not (root / stage.LOCK).exists()


@pytest.mark.parametrize("failure", ["disk_full", "short_write", "receipt", "tamper",
                                     "replace", "stale_pointer", "held_lock"])
def test_c5_stage_failure_preserves_previous(tmp_path, monkeypatch, failure):
    import errno
    stage, root, source, expected = c5_stage_fixture(tmp_path)
    first = stage.stage_fixture(root, source, expected, None)
    before = snapshot(root / first["generation"])
    prior = stage.pointer_bytes(root)
    original = stage.write_new
    if failure == "held_lock":
        (root / stage.LOCK).mkdir()
    elif failure == "replace":
        def fail_replace(*args):
            raise OSError(errno.EACCES, "fixture")
        monkeypatch.setattr(stage.os, "replace", fail_replace)
    elif failure != "stale_pointer":
        def write(path, chunks):
            if path.name == stage.RECEIPT and failure == "receipt":
                raise OSError(errno.ENOSPC, "fixture")
            if path.name == "a.txt":
                if failure == "disk_full":
                    raise OSError(errno.ENOSPC, "fixture")
                if failure == "short_write":
                    raise preflight.Blocked("STAGE_SHORT_WRITE")
            original(path, chunks)
            if path.name == "a.txt" and failure == "tamper":
                path.write_bytes(b"bad data")
        monkeypatch.setattr(stage, "write_new", write)
    with pytest.raises(preflight.Blocked):
        stage.stage_fixture(root, source, expected, None if failure == "stale_pointer" else first)
    assert stage.pointer_bytes(root) == prior
    assert snapshot(root / first["generation"]) == before
    assert (root / stage.LOCK).exists() == (failure == "held_lock")


def test_c5_stage_postpublication_failure_is_uncertain_not_rollback(tmp_path, monkeypatch):
    stage, root, source, expected = c5_stage_fixture(tmp_path)
    first = stage.stage_fixture(root, source, expected, None)
    before = snapshot(root / first["generation"])
    real = stage.sync_dir
    def sync(path):
        if path == root and stage.pointer_bytes(root) != stage.canonical(first):
            raise OSError("fixture postpublication sync failure")
        real(path)
    monkeypatch.setattr(stage, "sync_dir", sync)
    with pytest.raises(preflight.Blocked, match="STAGE_PUBLICATION_UNCERTAIN"):
        stage.stage_fixture(root, source, expected, first)
    current = preflight.strict_json(stage.pointer_bytes(root))
    assert current != first
    assert stage.verify_generation(root, current)["archive"] == expected
    assert snapshot(root / first["generation"]) == before


def test_c5_stage_rejects_unverified_archive_before_writes(tmp_path):
    stage, root, source, expected = c5_stage_fixture(tmp_path)
    expected["sha256"] = "0" * 64
    with pytest.raises(preflight.Blocked, match="ZIP_ARCHIVE_DIGEST"):
        stage.stage_fixture(root, source, expected, None)
    assert not list(root.iterdir())


def test_c5_stage_refuses_production_names_and_existing_store(tmp_path):
    stage, root, source, expected = c5_stage_fixture(tmp_path)
    with pytest.raises(FileExistsError):
        stage.create_fixture_store(root)
    _, source, expected = c5_zip_fixture(tmp_path, [("runtime.exe", b"inert")])
    with pytest.raises(preflight.Blocked, match="STAGE_FIXTURE_SCOPE"):
        stage.stage_fixture(root, source, expected, None)
    assert not list(root.iterdir())


def test_c5_stage_uses_verified_snapshot_not_changed_source(tmp_path, monkeypatch):
    stage, root, source, expected = c5_stage_fixture(tmp_path)
    real = stage.archive.verified_candidate_snapshot
    def capture(path, expectation):
        raw = real(path, expectation)
        path.write_bytes(b"changed after snapshot")
        return raw
    monkeypatch.setattr(stage.archive, "verified_candidate_snapshot", capture)
    pointer = stage.stage_fixture(root, source, expected, None)
    assert stage.verify_generation(root, pointer)["archive"] == expected


def test_c5_stage_refuses_tampered_prior_receipt(tmp_path):
    stage, root, source, expected = c5_stage_fixture(tmp_path)
    first = stage.stage_fixture(root, source, expected, None)
    (root / first["generation"] / stage.RECEIPT).write_bytes(b"tampered")
    prior = stage.pointer_bytes(root)
    with pytest.raises(preflight.Blocked, match="STAGE_BLOCKED_BEFORE_PUBLICATION"):
        stage.stage_fixture(root, source, expected, first)
    assert stage.pointer_bytes(root) == prior


def test_c5_candidate_inventory_exact_source_and_graphs():
    from qa.c5_metadata import input_inventory as inventory
    report = inventory.review(ROOT)
    assert inventory.summary(report) == {
        "status": "BLOCKED", "profiles_blocked": 4, "python_distinct_files": 62,
        "python_platform_selections": 98, "npm_entries": 90, "npm_edges": 108,
        "npm_absent_optional_peers": 11, "cargo_entries": 457, "cargo_edges": 1428,
        "cargo_registry_checksums": 455, "vendored_source_files": 37,
        "actual_artifact_verification": False, "production_activation": False,
    }
    assert report["not_a_lock_or_release_sbom"]
    assert all(p["status"] == "BLOCKED" for p in report["profiles"])
    assert report["vendored_shell"]["unchanged_upstream_blobs"] == 33
    assert len(report["vendored_shell"]["modified_files"]) == 3
    assert all(not x["artifact_bytes_verified"] and x["redistribution"] == "UNREVIEWED"
               for x in report["python"]["distinct_files"] + report["npm"]["rows"] + report["cargo"]["rows"])
    assert {x["path"] for x in report["npm"]["rows"] if x["has_install_script"]} == {
        "node_modules/esbuild", "node_modules/fsevents",
    }
    assert all(x["declared_licence"] is None for x in report["cargo"]["rows"])
    assert next(x for x in report["assets"] if x["id"] == "pdf-release-fonts")["identity_scope"] == "EXCLUDED_NOT_APPROVED"


def test_c5_candidate_inventory_rejects_vendor_pin_tamper():
    from qa.c5_metadata import input_inventory as inventory
    doc = preflight.strict_json(inventory.graph.canonical_source(ROOT, inventory.CATALOG))
    rows = doc["vendored_shell"]["files"]
    assert inventory.tree_digest(rows) == inventory.VENDOR_TREE
    rows[0]["git_blob"] = "0" * 40
    with pytest.raises(preflight.Blocked, match="VENDOR_TREE_PIN"):
        inventory.audit_vendor(ROOT, doc["vendored_shell"], preflight.audit_policy(ROOT))


def test_c5_candidate_inventory_rejects_missing_required_npm_edge():
    from qa.c5_metadata import input_inventory as inventory
    lock = preflight.strict_json(inventory.graph.canonical_source(ROOT, "frontend/package-lock.json"))
    lock["packages"][""]["dependencies"]["fixture-missing"] = "1.0.0"
    with pytest.raises(preflight.Blocked, match="NPM_DECLARATION_UNRESOLVED"):
        inventory.npm_inventory(lock)


def test_c5_candidate_inventory_rejects_missing_cargo_edge():
    import tomllib
    from qa.c5_metadata import input_inventory as inventory
    lock = tomllib.loads(inventory.graph.canonical_source(ROOT, "frontend/src-tauri/Cargo.lock").decode())
    lock["package"][0]["dependencies"] = ["fixture-missing"]
    with pytest.raises(preflight.Blocked, match="CARGO_DEPENDENCY_UNRESOLVED"):
        inventory.cargo_inventory(lock)


# C5 historical frontdoor tests: isolate the actual main AST so any attempt
# to invoke an old helper, filesystem or subprocess fails as an undefined name.
C5_HISTORICAL_FRONTDOORS = [
    ("Run_PilotODIN_P2_Prepare_Freezer_Tooling_DevQA.bat", "tools/p2_pdf_pyinstaller_tooling_devqa.py", "prepare", "C5_HISTORICAL_FREEZER_SETUP_BLOCKED"),
    ("Run_PilotODIN_P2_Prepare_Full_Sidecar_Builder_DevQA.bat", "tools/p2_pdf_prepare_full_sidecar_builder.py", "prepare", "C5_HISTORICAL_BUILDER_SETUP_BLOCKED"),
    ("Run_PilotODIN_P2_Font_Candidates_DevQA.bat", "tools/p2_pdf_font_stage_candidates.py", "download", "C5_HISTORICAL_FONT_ACQUISITION_BLOCKED"),
    ("Run_PilotODIN_P2_Font_Build_Stage_DevQA.bat", "tools/p2_pdf_font_build_preflight.py", "stage", "C5_HISTORICAL_FONT_STAGE_BLOCKED"),
    ("Run_PilotODIN_P2_Frozen_Font_OneFile_DevQA.bat", "tools/p2_pdf_frozen_font_onefile_devqa.py", "build", "C5_HISTORICAL_ONEFILE_BUILD_BLOCKED"),
    ("Run_PilotODIN_P2_Real_Sidecar_Font_DevQA.bat", "tools/p2_pdf_real_sidecar_font_devqa.py", "build", "C5_HISTORICAL_SIDECAR_BUILD_BLOCKED"),
    ("Run_PilotODIN_P2_Recheck_Existing_Sidecar_DevQA.bat", "tools/p2_pdf_recheck_real_sidecar_devqa.py", "recheck", "C5_HISTORICAL_SIDECAR_RECHECK_BLOCKED"),
]


@pytest.mark.parametrize("bat, module, flag, reason", C5_HISTORICAL_FRONTDOORS)
def test_c5_historical_mutation_cli_refuses_before_old_helpers(
        bat, module, flag, reason, monkeypatch, capsys):
    import argparse
    import sys
    source = (ROOT / module).read_text(encoding="utf-8")
    tree = ast.parse(source)
    main = next(node for node in tree.body
                if isinstance(node, ast.FunctionDef) and node.name == "main")
    isolated = ast.Module(body=[main], type_ignores=[])
    scope = {"argparse": argparse, "__doc__": "synthetic CLI refusal"}
    exec(compile(isolated, module, "exec"), scope)
    extra = ["--run-id", "run-" + "0" * 32] if flag == "recheck" else []
    for option in ("--" + flag, "--" + flag[:4]):
        monkeypatch.setattr(sys, "argv", [module, *extra, option])
        assert scope["main"]() == 2
        assert reason in capsys.readouterr().out


@pytest.mark.parametrize("bat, module, flag, reason", C5_HISTORICAL_FRONTDOORS)
def test_c5_historical_batch_has_only_refusal(bat, module, flag, reason):
    lines = (ROOT / bat).read_text(encoding="utf-8").splitlines()
    commands = [line.strip() for line in lines
                if line.strip() and not line.lstrip().lower().startswith("rem ")]
    assert commands == [
        "@echo off",
        "echo STOP: " + reason + ". Separate reviewed exact-input approval required.",
        "exit /b 2",
    ]


@pytest.mark.parametrize("path,marker", [
    ("tools/Verify_P2_Native_Export_Local.ps1", "C5_P2_NATIVE_EXPORT_BLOCKED"),
    ("desktop/Verify_Installed_PilotODIN.ps1", "C5_INSTALLER_VERIFICATION_BLOCKED"),
])
def test_c5_native_and_install_entrypoints_refuse_before_setup(path, marker):
    source = (ROOT / path).read_text(encoding="utf-8")
    guard = source.index("Write-Error 'STOP: " + marker)
    exit_pos = source.index("\nexit 2\n", guard)
    assert exit_pos < source.index("$ErrorActionPreference = 'Stop'")
    assert "-ErrorAction Continue" in source[guard:exit_pos]
    before = source[:guard]
    assert not any(command in before for command in ("New-Item", "Start-Process", "Resolve-Path", "Invoke-WebRequest"))


def test_c5_a4_preflight_only_before_diagnostics():
    source = (ROOT / "tools/Verify_A4_Native_Windows.ps1").read_text(encoding="utf-8")
    guard = source.index("if (-not $PreflightOnly) {")
    assert "C5_A4_NATIVE_BUILD_BLOCKED" in source[guard:source.index("$ErrorActionPreference", guard)]
    assert source.index("exit 2", guard) < source.index("New-Item")
    assert guard < source.index("Resolve-Path")


def test_c5_legacy_native_export_batch_refuses():
    commands = [line.strip() for line in
                (ROOT / "Run_PilotODIN_P2_Native_Export.bat").read_text(encoding="utf-8").splitlines()
                if line.strip() and not line.lstrip().lower().startswith("rem ")]
    assert commands == ["@echo off",
                        "echo STOP: C5_P2_NATIVE_EXPORT_BLOCKED. Separate reviewed native approval required.",
                        "exit /b 2"]


def test_c5_native_executable_frontdoor_has_no_spawn():
    source = (ROOT / "frontend/scripts/p4-isolated-native-dev.mjs").read_text(encoding="utf-8")
    commands = [line.strip() for line in source.splitlines()
                if line.strip() and not line.lstrip().startswith("//")]
    assert len(commands) == 2
    assert commands[0].startswith('console.error("STOP: Native compilation is frozen')
    assert commands[1] == "process.exit(2);"
