#!/usr/bin/env python3
"""P2-U1: verify and optionally stage six pinned OFL assets for build review.

Developer-only. No network, product imports, font installation, source
mutation, PyInstaller call or Tauri build. Staged copies are NOT release assets.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import sys
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from qa_foundation import default_root, safe_root
from p2_pdf_font_asset_gate import hash_file, strict_member, verify

MANIFEST = Path(__file__).with_name("p2_pdf_font_candidates.json")
TARGET = ROOT / "build" / "p2-pdf-font-preflight"
ROLES = {"regular", "cjk", "symbol"}
MAX_TOTAL = 25 * 1024 * 1024


def _not_redirected(path: Path) -> None:
    for part in (path, *path.parents):
        if part.exists() and (part.is_symlink() or
                              getattr(os.path, "isjunction", lambda _: False)(part)):
            raise ValueError("Redirected staging path")


def _expected(manifest: dict) -> list[tuple[str, str, int, str, str]]:
    """Return role, basename, pinned size, Git blob ID and asset kind."""
    if (manifest.get("schema") != 1 or
            manifest.get("status") != "CANDIDATES_UNVERIFIED_DO_NOT_SHIP" or
            manifest.get("source_repo") != "google/fonts"):
        raise ValueError("Invalid candidate identity manifest")
    entries = manifest.get("assets")
    if not isinstance(entries, list) or len(entries) != 3 or \
            {entry.get("role") for entry in entries} != ROLES:
        raise ValueError("Unexpected font roles")
    all_files = []
    for item in entries:
        for name_key, size_key, oid_key, kind in (
            ("filename", "bytes", "git_blob_sha1", "font"),
            ("license_filename", "license_bytes", "license_git_blob_sha1", "license"),
        ):
            name, size, oid = item[name_key], item[size_key], item[oid_key]
            if (not isinstance(name, str) or
                    Path(name).name != name or name in ("", ".", "..") or
                    not isinstance(size, int) or isinstance(size, bool) or
                    not 0 < size <= MAX_TOTAL or
                    not isinstance(oid, str) or len(oid) != 40 or
                    any(c not in "0123456789abcdef" for c in oid)):
                raise ValueError("Malformed pinned font or license record")
            all_files.append((item["role"], name, size, oid, kind))
    if len({item[1] for item in all_files}) != 6 or \
            sum(item[2] for item in all_files) > MAX_TOTAL:
        raise ValueError("Duplicate or oversized staged font set")
    return all_files


def audited_sources(source: Path, manifest: dict, checker=verify) -> list[dict]:
    """No mutation: validate the complete source set before any output exists."""
    if source.is_symlink() or not source.is_dir():
        raise ValueError("Existing candidate directory is required")
    source = source.resolve()
    expected = _expected(manifest)
    result = checker(source, manifest)
    if result.get("state") != "CANDIDATE_FILE_AND_CMAP_PROBE_PASS":
        raise ValueError("Pinned font/cmap source gate has not passed")
    checked = []
    for role, name, size, oid, kind in expected:
        source_file = strict_member(source, name)
        actual_size, digest, git_oid = hash_file(source_file)
        if actual_size != size or git_oid != oid:
            raise ValueError("Pinned staged source changed since verification")
        checked.append({"role": role, "name": name, "kind": kind,
                        "bytes": size, "sha256": digest, "git_blob_sha1": oid})
    return checked


def stage_for_review(source: Path, destination_parent: Path, manifest: dict,
                     *, checker=verify, identifier: str | None = None) -> dict:
    """Create one uniquely named, nonproduction build-only review directory.

    Never replace or delete an existing completed review. On failure only the
    newly created temporary folder is removed. Verify each COPY again before
    publication, preventing changed input from being reported as pinned.
    """
    source_report = audited_sources(source, manifest, checker)
    _not_redirected(destination_parent)
    destination_parent.mkdir(parents=True, exist_ok=True)
    _not_redirected(destination_parent)
    tag = identifier or uuid.uuid4().hex
    if len(tag) != 32 or any(c not in "0123456789abcdef" for c in tag):
        raise ValueError("Invalid unique review identifier")
    temporary = destination_parent / ("pending-" + tag)
    final = destination_parent / ("review-" + tag)
    if temporary.exists() or final.exists() or temporary.is_symlink() or final.is_symlink():
        raise FileExistsError("Existing review directory cannot be overwritten")
    temporary.mkdir(exist_ok=False)
    try:
        for file in source_report:
            source_path = strict_member(source.resolve(), file["name"])
            target = temporary / file["name"]
            with source_path.open("rb") as origin, target.open("xb") as output:
                remaining = file["bytes"]
                while remaining:
                    block = origin.read(min(1024 * 1024, remaining))
                    if not block:
                        raise ValueError("Source changed during copy")
                    output.write(block)
                    remaining -= len(block)
                if origin.read(1):
                    raise ValueError("Source grew during copy")
            n, sha256, git_oid = hash_file(target)
            if (n != file["bytes"] or sha256 != file["sha256"] or
                    git_oid != file["git_blob_sha1"]):
                raise ValueError("Copied candidate failed identity verification")
        receipt = {
            "schema": 1,
            "state": "BUILD_PREFLIGHT_ONLY_NOT_FOR_RELEASE",
            "source_commit": manifest["source_commit"],
            "assets": source_report,
            "license_files_included": 3,
            "packaged_sidecar_verified": False,
            "product_acceptance": "NOT_TESTED",
            "unicode_visual_acceptance": "NOT_TESTED",
            "sha256_approval": "MEASURED_RECEIPTS_NOT_INDEPENDENT_RELEASE_APPROVAL",
        }
        with (temporary / "receipt.json").open("x", encoding="utf-8") as f:
            json.dump(receipt, f, ensure_ascii=False, indent=2)
            f.write("\n")
        if final.exists() or final.is_symlink():
            raise FileExistsError("Review folder became occupied")
        temporary.rename(final)
        return {"state": receipt["state"], "asset_count": 6,
                "source_verified": True, "product_acceptance": "NOT_TESTED",
                "destination": str(final), "receipt": "receipt.json"}
    except BaseException:
        # Only the just-created pending directory is in scope for cleanup.
        shutil.rmtree(temporary)
        raise


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", action="store_true",
                        help="Explicitly copy verified files to ignored build-only review directory")
    args = parser.parse_args()
    try:
        source = safe_root(default_root() / "font-candidates", ROOT)
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        verified = audited_sources(source, manifest)
        if args.stage:
            # A destination supplied by the operator is never accepted.
            outcome = stage_for_review(source, TARGET, manifest)
        else:
            outcome = {
                "state": "SOURCE_PREFLIGHT_PASS_NOT_STAGED",
                "asset_count": len(verified),
                "font_bytes": sum(v["bytes"] for v in verified if v["kind"] == "font"),
                "source_verified": True, "product_acceptance": "NOT_TESTED",
                "sidecar_packaging": "NOT_TESTED",
            }
    except Exception as exc:
        outcome = {"state": "BLOCKED", "failure_class": type(exc).__name__,
                   "product_acceptance": "NOT_TESTED"}
    print(json.dumps(outcome, ensure_ascii=False, indent=2))
    return 0 if outcome["state"] != "BLOCKED" else 2


if __name__ == "__main__":
    sys.exit(main())
