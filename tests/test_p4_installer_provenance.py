"""Disposable synthetic tests for P4 QA installer provenance guard; no EXE execution."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "qa" / "p4_native"))
from verify_qa_installer_provenance import main, verify  # noqa: E402

SOURCE = "bca3c57b94a425cd9ef489726e721328d12c2ead"


def sample(tmp_path: Path):
    content = b"SYNTHETIC-NOT-EXECUTABLE"
    installer = tmp_path / "pilotODIN-P4-Native-QA_1.0.0-alpha.1_x64-setup.exe"
    installer.write_bytes(content)
    doc = {
        "schema_version": 1,
        "source_commit": SOURCE,
        "runner_os": "Windows",
        "qa_identifier": "com.pilotodin.p4nativeqa",
        "existing_product_identifier": "com.pilotodin.studio",
        "disposable_ci_install_engine_smoke_passed": True,
        "compiled_exe_matches_disposable_ci_installed_exe": True,
        "installed_on_owner_windows": False,
        "native_owner_acceptance": "NOT_TESTED",
        "business_acceptance": "UNVERIFIED",
        "release_certified": False,
        "installer": {"name": installer.name, "bytes": len(content), "sha256": hashlib.sha256(content).hexdigest()},
    }
    manifest = tmp_path / "source-and-windows-artifact.json"
    manifest.write_text(json.dumps(doc), encoding="utf-8")
    return manifest, installer, doc


def test_pass_is_only_integrity_check(tmp_path, capsys):
    manifest, installer, doc = sample(tmp_path)
    assert verify(manifest, installer, SOURCE) == doc["installer"]["sha256"]
    assert main(["--manifest", str(manifest), "--installer", str(installer), "--expected-source", SOURCE]) == 0
    assert "NOT VERIFIED: manifest authenticity" in capsys.readouterr().out


@pytest.mark.parametrize("field,value", [
    ("source_commit", "0" * 40),
    ("runner_os", "Linux"),
    ("qa_identifier", "com.pilotodin.studio"),
    ("existing_product_identifier", "com.other"),
    ("disposable_ci_install_engine_smoke_passed", False),
    ("compiled_exe_matches_disposable_ci_installed_exe", False),
    ("installed_on_owner_windows", True),
    ("native_owner_acceptance", "PASS"),
    ("business_acceptance", "PASS"),
    ("release_certified", True),
    ("schema_version", True),
])
def test_fail_closed_when_manifest_claim_invalid(tmp_path, field, value):
    manifest, installer, doc = sample(tmp_path)
    doc[field] = value
    manifest.write_text(json.dumps(doc), encoding="utf-8")
    with pytest.raises(ValueError):
        verify(manifest, installer, SOURCE)


@pytest.mark.parametrize("field,value", [
    ("sha256", "0" * 64),
    ("sha256", "not-a-sha"),
    ("bytes", 4),
    ("bytes", True),
    ("name", "pilotODIN_1.0.0-alpha.1_x64-setup.exe"),
])
def test_mismatch_or_untrusted_installer_metadata_rejected(tmp_path, field, value):
    manifest, installer, doc = sample(tmp_path)
    doc["installer"][field] = value
    manifest.write_text(json.dumps(doc), encoding="utf-8")
    with pytest.raises(ValueError):
        verify(manifest, installer, SOURCE)


def test_same_size_binary_tampering_rejected(tmp_path):
    manifest, installer, _ = sample(tmp_path)
    installer.write_bytes(b"X" * installer.stat().st_size)
    with pytest.raises(ValueError, match="SHA256"):
        verify(manifest, installer, SOURCE)


def test_wrong_expected_commit_rejected(tmp_path):
    manifest, installer, _ = sample(tmp_path)
    with pytest.raises(ValueError, match="source commit"):
        verify(manifest, installer, "c" * 40)


def test_malformed_json_exits_failure(tmp_path, capsys):
    manifest, installer, _ = sample(tmp_path)
    manifest.write_text("not-json", encoding="utf-8")
    assert main(["--manifest", str(manifest), "--installer", str(installer), "--expected-source", SOURCE]) == 1
    assert "FAIL:" in capsys.readouterr().err


def test_rejects_unexpected_executable_filename(tmp_path):
    manifest, installer, _ = sample(tmp_path)
    renamed = installer.with_name("pilotODIN-P4-Native-QA_1.0.0-alpha.1_x64-setup.exe.zip")
    installer.rename(renamed)
    with pytest.raises(ValueError, match="filename"):
        verify(manifest, renamed, SOURCE)
