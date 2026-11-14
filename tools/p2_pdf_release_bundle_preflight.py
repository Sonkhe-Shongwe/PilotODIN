#!/usr/bin/env python3
"""Source-controlled P2 release font packaging preflight.

This tool has NO signoff authority. It only reads the installed source policy
and checks the exact six unmodified font/OFL release resources. It does not
copy, stage, download, build, install, or modify anything. It must run BEFORE
PyInstaller is invoked. No developer receipt or candidate source is trusted.
"""
from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend import pdf_release_font_loader as release
from backend.pdf_font_resources import PDFResourceError, verify_pdf_font_files

PASS = "APPROVED_PACKAGING_SOURCE_READY"
DENIED = "NOT_APPROVED_LEGACY_ENGINE_ONLY"
BLOCKED = "BLOCKED"


def packaging_decision(*, verified=None) -> dict:
    """Read current code-pinned release policy, never mutable DevQA receipts."""
    status = release.RELEASE_APPROVAL_STATUS
    reference = release.RELEASE_APPROVAL_REFERENCE
    pins = release.RELEASE_PINNED_FILES

    if status == "NOT_GRANTED":
        if reference or pins:
            raise ValueError("Incomplete unapproved font source policy")
        return {
            "state": DENIED, "include_font_resources": False,
            "sidecar_pdf_unicode": "DISABLED",
            "release_approval": "NOT_GRANTED",
        }

    if status != "GRANTED_BY_INDEPENDENT_OWNER_REVIEW":
        raise ValueError("Unrecognized release approval policy")

    # Enforce the SAME release contract used by authenticated PDF exports.
    # Synthetic callers may inject a verifier but never override source state.
    records = release._approved_records()
    verifier = verify_pdf_font_files if verified is None else verified
    resolved = verifier(records)
    if (not isinstance(resolved, dict) or
            set(resolved) != {role + "_" + kind
                             for role in ("regular", "cjk", "symbol")
                             for kind in ("font", "license")}):
        raise ValueError("Approved six-resource verification incomplete")
    return {
        "state": PASS, "include_font_resources": True,
        "verified_release_files": 6,
        "release_approval": "GRANTED_BY_INDEPENDENT_OWNER_REVIEW",
        "resource_destination": "backend/assets/pdf_fonts",
    }

def main() -> int:
    try:
        state = packaging_decision()
        rc = 0
    except Exception as exc:
        state = {
            "state": BLOCKED, "stage": "font_release_packaging_policy",
            "failure_class": type(exc).__name__,
            "include_font_resources": False,
            "release_approval": "NOT_GRANTED_OR_INVALID",
        }
        rc = 2
    print(json.dumps(state, ensure_ascii=False, separators=(",", ":")))
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
