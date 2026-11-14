"""Read-only P4-16 QA installer checksum check against a separately sourced CI manifest.

This helper does not install, execute, unpack, trust-sign, or approve the binary.
A matching hash is only file-integrity evidence, never native or release acceptance.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import sys

_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_SHA1 = re.compile(r"[0-9a-f]{40}\Z")
_QA_ID = "com.pilotodin.p4nativeqa"
_PRODUCTION_ID = "com.pilotodin.studio"


def _hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify(manifest_path: Path, installer_path: Path, expected_source: str) -> str:
    """Return verified file SHA256; raise ValueError/OSError on any mismatch.

    Caller must obtain the JSON from the independently identified GitHub Actions
    run. No cryptographic provenance signature is provided by this check.
    """
    if not _SHA1.fullmatch(expected_source):
        raise ValueError("Expected source must be an exact lowercase 40-character commit SHA")
    with manifest_path.open("r", encoding="utf-8-sig") as source:
        manifest = json.load(source)
    if not isinstance(manifest, dict):
        raise ValueError("Manifest must be a JSON object")
    if type(manifest.get("schema_version")) is not int or manifest["schema_version"] != 1:
        raise ValueError("Unsupported provenance manifest schema")
    if manifest.get("source_commit") != expected_source:
        raise ValueError("Manifest does not match independently selected source commit")
    if manifest.get("runner_os") != "Windows":
        raise ValueError("Manifest does not describe Windows CI")
    if manifest.get("qa_identifier") != _QA_ID or manifest.get("existing_product_identifier") != _PRODUCTION_ID:
        raise ValueError("QA and original product identifiers do not match expected isolated variants")
    for name in ("disposable_ci_install_engine_smoke_passed", "compiled_exe_matches_disposable_ci_installed_exe"):
        if manifest.get(name) is not True:
            raise ValueError(f"CI verification gate not positively recorded: {name}")
    if (manifest.get("installed_on_owner_windows") is not False
            or manifest.get("native_owner_acceptance") != "NOT_TESTED"
            or manifest.get("business_acceptance") != "UNVERIFIED"
            or manifest.get("release_certified") is not False):
        raise ValueError("Manifest incorrectly represents owner/native/business/release acceptance")
    installer = manifest.get("installer")
    if not isinstance(installer, dict):
        raise ValueError("Missing installer metadata")
    name, size, expected_hash = (installer.get(k) for k in ("name", "bytes", "sha256"))
    if not isinstance(name, str) or not name.startswith("pilotODIN-P4-Native-QA_") or not name.endswith("_x64-setup.exe"):
        raise ValueError("Installer filename is not the isolated P4 QA NSIS variant")
    if installer_path.name != name:
        raise ValueError("Provided installer filename differs from manifest")
    if type(size) is not int or size <= 0:
        raise ValueError("Missing or invalid installer byte count")
    if not isinstance(expected_hash, str) or not _SHA256.fullmatch(expected_hash):
        raise ValueError("Missing or invalid installer SHA256")
    if not installer_path.is_file():
        raise ValueError("Installer file not found")
    if installer_path.stat().st_size != size:
        raise ValueError("Installer byte count differs from manifest")
    actual_hash = _hash_file(installer_path)
    if actual_hash != expected_hash:
        raise ValueError("Installer SHA256 differs from manifest")
    return actual_hash


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True, help="Independently obtained source-and-windows-artifact.json")
    parser.add_argument("--installer", type=Path, required=True, help="Already extracted P4 QA NSIS exe, NOT a ZIP")
    parser.add_argument("--expected-source", required=True, help="Commit SHA independently checked on GitHub")
    args = parser.parse_args(argv)
    try:
        digest = verify(args.manifest, args.installer, args.expected_source)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1
    print(f"PASS: QA installer bytes match supplied CI manifest (SHA256 {digest}).")
    print("NOT VERIFIED: manifest authenticity, owner installation, coexistence, UI, 8 GB, business acceptance or release.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
