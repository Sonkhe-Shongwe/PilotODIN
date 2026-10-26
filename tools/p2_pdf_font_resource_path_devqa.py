#!/usr/bin/env python3
"""P2-U2: read-only review of the staged font copy and future sidecar layout.

No PyInstaller build, product renderer import, user project access, downloads,
runtime font installation, app window, or changes to staged files. The actual
frozen executable and Tauri installer remain unverified.
"""
from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

from backend.pdf_font_resources import verify_pdf_font_files
from p2_pdf_font_build_preflight import _expected, audited_sources

REVIEW_PARENT = ROOT / "build" / "p2-pdf-font-preflight"
MANIFEST_PATH = ROOT / "tools" / "p2_pdf_font_candidates.json"
PROPOSED_PYINSTALLER_DEST = "backend/assets/pdf_fonts"


def review_staged_copy(parent: Path, manifest: dict) -> dict:
    """Accept exactly one existing review folder, never select it by timestamp."""
    if parent.is_symlink() or not parent.is_dir():
        raise ValueError("Build-review parent is absent or redirected")
    reviews = sorted(p for p in parent.iterdir()
                     if p.name.startswith("review-"))
    if len(reviews) != 1 or not reviews[0].is_dir() or reviews[0].is_symlink():
        raise ValueError("Expected exactly one completed review folder")
    directory = reviews[0]
    receipt_path = directory / "receipt.json"
    if not receipt_path.is_file() or receipt_path.is_symlink():
        raise ValueError("Missing review receipt")
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    if (receipt.get("schema") != 1 or
            receipt.get("state") != "BUILD_PREFLIGHT_ONLY_NOT_FOR_RELEASE" or
            receipt.get("source_commit") != manifest.get("source_commit") or
            receipt.get("license_files_included") != 3 or
            receipt.get("packaged_sidecar_verified") is not False or
            receipt.get("product_acceptance") != "NOT_TESTED" or
            not isinstance(receipt.get("assets"), list)):
        raise ValueError("Review receipt is not a valid build-only handoff")

    expected = {(role, kind, name): (size, git_id)
                for role, name, size, git_id, kind in _expected(manifest)}
    observed = {}
    for entry in receipt["assets"]:
        if not isinstance(entry, dict):
            raise ValueError("Malformed review asset identity")
        role, kind, name = (entry.get("role"), entry.get("kind"),
                            entry.get("name"))
        key = (role, kind, name)
        if key not in expected or key in observed or (
                entry.get("bytes"), entry.get("git_blob_sha1")) != expected[key]:
            raise ValueError("Receipt does not match pinned upstream identities")
        observed[key] = entry
    if len(observed) != 6:
        raise ValueError("Incomplete receipt")

    # Independent source bytes and Git-object check, not trusting receipt hashes.
    measured = audited_sources(directory, manifest)
    records = [{
        "role": row["role"],
        "kind": row["kind"],
        "name": row["name"],
        "bytes": row["bytes"],
        "sha256": row["sha256"],
    } for row in measured]
    for row in measured:
        key = row["role"], row["kind"], row["name"]
        if row["sha256"] != observed[key].get("sha256"):
            raise ValueError("Copied resource SHA-256 differs from receipt")
    checked = verify_pdf_font_files(records, resource_root=directory)
    return {
        "state": "BUILD_REVIEW_RESOURCE_PATH_CONTRACT_PASS",
        "verified_font_and_license_files": len(checked),
        "proposed_pyinstaller_add_data_destination": PROPOSED_PYINSTALLER_DEST,
        "source_review_receipt": "receipt.json",
        "actual_frozen_sidecar": "NOT_TESTED",
        "actual_pyinstaller_add_data": "NOT_CONFIGURED",
        "product_acceptance": "NOT_TESTED",
        "unicode_visual_acceptance": "NOT_TESTED",
        "warning": "Package-relative validation contract only; no frozen engine built",
    }


def main() -> int:
    try:
        manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        result = review_staged_copy(REVIEW_PARENT, manifest)
    except Exception as exc:
        result = {"state": "BLOCKED", "reason_class": type(exc).__name__,
                  "product_acceptance": "NOT_TESTED"}
    print("P2 FROZEN FONT PATH DEVQA: " + result["state"])
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["state"] == "BUILD_REVIEW_RESOURCE_PATH_CONTRACT_PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
