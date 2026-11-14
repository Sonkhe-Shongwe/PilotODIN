#!/usr/bin/env python3
"""Offline candidate asset gate for PilotODIN PDF fonts; NEVER a production installer.

Accept only explicit local developer font/license files and the repo's pinned
candidate manifest. This tool does not download, copy, install or bundle fonts.
A positive result does NOT mean multilingual PDF visual acceptance.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import sys

MAX_ASSET_BYTES = 32 * 1024 * 1024
ROLES = {
    "regular": "ΔΩМосква₹",
    "cjk": "漢字",
    "symbol": "📈",
}


def hash_file(path: Path) -> tuple[int, str, str]:
    """Return size, SHA256 and Git blob SHA1 without loading the whole binary."""
    size = path.stat().st_size
    if size <= 0 or size > MAX_ASSET_BYTES:
        raise ValueError("Asset has invalid or excessive size")
    sha256 = hashlib.sha256()
    git_sha = hashlib.sha1(b"blob " + str(size).encode("ascii") + b"\0")
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            sha256.update(block)
            git_sha.update(block)
    return size, sha256.hexdigest(), git_sha.hexdigest()


def strict_member(directory: Path, name: str) -> Path:
    if (not isinstance(name, str) or not name or
            Path(name).name != name or name in (".", "..")):
        raise ValueError("Manifest asset must be a single basename")
    path = directory / name
    if not path.is_file() or path.is_symlink() or path.resolve().parent != directory:
        raise ValueError("Missing or redirected local candidate")
    return path


def verify(root: Path, manifest: dict) -> dict:
    if root.is_symlink() or not root.is_dir():
        raise ValueError("Explicit asset root must be an actual directory")
    root = root.resolve()
    if (manifest.get("schema") != 1 or
            manifest.get("status") != "CANDIDATES_UNVERIFIED_DO_NOT_SHIP" or
            not re.fullmatch(r"[a-f0-9]{40}", manifest.get("source_commit", ""))):
        raise ValueError("Manifest identity is invalid")
    assets = manifest.get("assets")
    if not isinstance(assets, list) or len(assets) != 3:
        raise ValueError("Expected exactly three candidate font roles")
    import_errors = []
    details = []
    seen = set()
    for entry in assets:
        role = entry.get("role")
        if role not in ROLES or role in seen:
            raise ValueError("Unknown or duplicate font role")
        seen.add(role)
        font_path = strict_member(root, entry["filename"])
        license_path = strict_member(root, entry["license_filename"])
        if not (re.fullmatch(r"[a-f0-9]{40}", entry["git_blob_sha1"]) and
                re.fullmatch(r"[a-f0-9]{40}", entry["license_git_blob_sha1"])):
            raise ValueError("Invalid pinned Git blob checksum")
        font_size, font_sha256, font_git = hash_file(font_path)
        license_size, _, license_git = hash_file(license_path)
        if (font_size != entry["bytes"] or font_git != entry["git_blob_sha1"] or
                license_git != entry["license_git_blob_sha1"]):
            raise ValueError("Pinned candidate font or license does not match")
        if license_size < 500 or "SIL OPEN FONT LICENSE" not in license_path.read_text(
                encoding="utf-8", errors="strict").upper():
            raise ValueError("Font license text is not recognized")
        try:
            # Actual ReportLab compatibility, not just file extension/cmap.
            from reportlab.pdfbase.ttfonts import TTFont
            candidate = TTFont("ODIN-CANDIDATE-" + role.upper(), str(font_path))
            cmap = candidate.face.charToGlyph
            missing = sorted({"U+%04X" % ord(ch) for ch in ROLES[role]
                              if not cmap.get(ord(ch))})
            font_state = "GLYPHS_PRESENT" if not missing else "MISSING_REQUIRED_GLYPHS"
        except Exception as exc:
            font_state, missing = "REPORTLAB_FONT_REJECTED", [type(exc).__name__]
        details.append({
            "role": role, "file": font_path.name, "bytes": font_size,
            "sha256": font_sha256, "format_gate": font_state,
            "missing_or_error": missing,
        })
    if seen != set(ROLES):
        raise ValueError("Incomplete candidate roles")
    passed = all(entry["format_gate"] == "GLYPHS_PRESENT" for entry in details)
    return {
        "state": "CANDIDATE_FILE_AND_CMAP_PROBE_PASS" if passed else "CANDIDATE_REVIEW_REQUIRED",
        "product_acceptance": "NOT_TESTED",
        "font_assets": details,
        "remaining": [
            "ReportLab exact PDF extraction, especially supplementary-plane emoji",
            "visual glyph and paragraph/chart geometry on Windows",
            "static/variable face weight and CJK font size/memory",
            "Tauri / frozen Python offline resource path and license packaging",
        ]
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--asset-root", type=Path, required=True,
                        help="Existing directory of manually obtained candidate binaries and OFL notices")
    parser.add_argument("--manifest", type=Path,
                        default=Path(__file__).with_name("p2_pdf_font_candidates.json"))
    args = parser.parse_args()
    try:
        manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
        outcome = verify(args.asset_root, manifest)
    except (OSError, ValueError, KeyError, TypeError, ImportError) as exc:
        outcome = {"state": "BLOCKED", "failure_class": type(exc).__name__,
                   "product_acceptance": "NOT_TESTED"}
    print(json.dumps(outcome, ensure_ascii=False, indent=2))
    return 0 if outcome["state"] == "CANDIDATE_FILE_AND_CMAP_PROBE_PASS" else 2


if __name__ == "__main__":
    sys.exit(main())
