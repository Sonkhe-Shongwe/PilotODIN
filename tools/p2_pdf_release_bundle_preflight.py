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


def packaging_decision(*, approval_status=None, approval_reference=None,
                       pinned_files=None, verified=None) -> dict:
    """Fail closed on inconsistent policy; ignore no partial signoff.

    Injected arguments are ONLY for synthetic tests. Real CLI always reads
    the immutable module constants and actual module-relative assets.
    """
    status = release.RELEASE_APPROVAL_STATUS if approval_status is None else approval_status
    reference = (release.RELEASE_APPROVAL_REFERENCE if approval_reference is None
                 else approval_reference)
    pins = release.RELEASE_PINNED_FILES if pinned_files is None else pinned_files

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

    # Enforce the identical reviewed six-file policy that the real export
    # endpoint uses. No local editable manifest/receipt or environment flag.
    original = (release.RELEASE_APPROVAL_STATUS,
                release.RELEASE_APPROVAL_REFERENCE,
                release.RELEASE_PINNED_FILES)
    # For tests, avoid mutating source state or process globals: exact inputs
    # are validated using the loader's shape contract via a local patch.
    from unittest.mock import patch
    with patch.object(release, "RELEASE_APPROVAL_STATUS", status), \
         patch.object(release, "RELEASE_APPROVAL_REFERENCE", reference), \
         patch.object(release, "RELEASE_PINNED_FILES", pins):
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
