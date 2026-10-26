#!/usr/bin/env python3
"""Read-only review of verified developer font candidates, with no downloads.

This is NOT production Unicode acceptance or a product runtime dependency.
"""
from __future__ import annotations
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from qa_foundation import default_root, safe_root
from p2_pdf_font_asset_gate import verify
from p2_pdf_font_coverage_probe import audit

MANIFEST = Path(__file__).with_name("p2_pdf_font_candidates.json")


def review(root, manifest):
    """Check pinned bytes and licenses BEFORE rendering synthetic text in memory."""
    checked = safe_root(root, ROOT)
    if not checked.is_dir():
        raise ValueError("Previously staged candidate directory is missing")
    gate = verify(checked, manifest)
    assets = {
        entry["role"]: checked / entry["filename"] for entry in manifest["assets"]
    }
    summaries = [
        {
            "role": entry["role"],
            "format": entry["format_gate"],
            "missing_or_error": entry["missing_or_error"],
        } for entry in gate["font_assets"]
    ]
    # Only run PDF extraction after verification of ALL six pinned assets.
    # A font-parser failure must never conceal the valid cmap/identity report.
    extraction_error = None
    try:
        samples = audit({"regular": assets["regular"], "cjk": assets["cjk"],
                         "emoji": assets["symbol"]})
        states = {k: v["state"] for k, v in samples["samples"].items()}
    except Exception as exc:
        extraction_error = type(exc).__name__
        states = {"probe": "BLOCKED_FONT_PARSE_OR_RENDER"}
    return {
        "state": ("CANDIDATE_REVIEW_REQUIRED" if
                  gate["state"] != "CANDIDATE_FILE_AND_CMAP_PROBE_PASS" or
                  extraction_error is not None or
                  any(x != "EXTRACTED_EXACT" for x in states.values())
                  else "CANDIDATE_EXTRACTION_PASS_VISUAL_PENDING"),
        "extraction_error_class": extraction_error,
        "asset_integrity": "VERIFIED_PINNED_FONT_AND_LICENSE_BYTES",
        "cmap_gate": gate["state"],
        "fonts": summaries,
        "exact_pdf_extraction": states,
        "product_acceptance": "NOT_TESTED",
        "visual_acceptance": "NOT_TESTED",
        "note": "Offline read-only candidate review. No production fonts or apps changed.",
    }


def main():
    try:
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        outcome = review(default_root() / "font-candidates", manifest)
    except Exception as exc:
        outcome = {
            "state": "BLOCKED",
            "failure_class": type(exc).__name__,
            "asset_integrity": "NOT_VERIFIED",
            "product_acceptance": "NOT_TESTED",
        }
    print("P2 FONT LOCAL CANDIDATE REVIEW: " + outcome["state"])
    for font in outcome.get("fonts", []):
        missing = ", ".join(font["missing_or_error"]) or "none"
        print(font["role"].upper() + ": " + font["format"] + " | missing: " + missing)
    for label, result in outcome.get("exact_pdf_extraction", {}).items():
        print("TEXT " + label.upper() + ": " + result)
    print("ASSET IDENTITY: " + outcome["asset_integrity"])
    if outcome["state"] == "BLOCKED":
        print("REVIEW BLOCKER: " + outcome["failure_class"])
    print("Full local review result (no font bytes):")
    print(json.dumps(outcome, ensure_ascii=False, indent=2))
    # Requiring actual rendered visual review remains a separate gate.
    return 0 if outcome["state"] == "CANDIDATE_EXTRACTION_PASS_VISUAL_PENDING" else 2


if __name__ == "__main__":
    raise SystemExit(main())
