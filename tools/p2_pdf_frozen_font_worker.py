#!/usr/bin/env python3
"""P2-U2a frozen-only reader for six independently supplied DevQA font hashes.

PyInstaller compiles this file as a STANDALONE PROBE, NOT PilotODIN's sidecar.
No server, projects, fonts registered/installed, files written, or network.
The unfrozen Python interpreter must refuse to claim a frozen PASS.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import sys

from backend import pdf_font_resources


def inspect_frozen_resources(payload: dict) -> dict:
    if not getattr(sys, "frozen", False) or not hasattr(sys, "_MEIPASS"):
        raise ValueError("Not executing in the PyInstaller bootloader")
    if not isinstance(payload, dict) or payload.get("schema") != 1:
        raise ValueError("Invalid probe input")
    entries = payload.get("assets")
    if not isinstance(entries, list) or len(entries) != 6:
        raise ValueError("Six pinned assets required")
    bundle = Path(sys._MEIPASS).resolve(strict=True)
    root = pdf_font_resources.resolve_pdf_font_root()
    # Resolve the *real module*, not an injected synthetic module path.
    module = Path(pdf_font_resources.__file__).resolve(strict=False)
    if not module.is_relative_to(bundle) or not root.resolve().is_relative_to(bundle):
        raise ValueError("Font reader is not inside extracted bundle")
    if root != module.parent / "assets" / "pdf_fonts":
        raise ValueError("Unexpected font asset lookup location")
    # Only six explicitly embedded resources are permitted, excluding no hidden
    # receipt/manifest shortcuts that could accidentally act as hash authority.
    if {p.name for p in root.iterdir()} != {entry["name"] for entry in entries}:
        raise ValueError("Unexpected or incomplete embedded font set")
    found = pdf_font_resources.verify_pdf_font_files(entries)
    if len(found) != 6:
        raise ValueError("Incomplete verification")
    return {
        "schema": 1,
        "state": "FROZEN_RESOURCE_VERIFIED",
        "frozen": True,
        "inside_pyinstaller_bundle": True,
        "embedded_file_count": 6,
        "resource_location": "backend/assets/pdf_fonts",
        "product_sidecar_tested": False,
        "release_font_approval": "NOT_GRANTED",
        "unicode_pdf_visual_acceptance": "NOT_TESTED",
    }


def main() -> int:
    try:
        raw = sys.stdin.read(16385)
        if len(raw) > 16384:
            raise ValueError("Oversized probe input")
        result = inspect_frozen_resources(json.loads(raw))
        exit_code = 0
    except Exception as exc:
        result = {"schema": 1, "state": "BLOCKED",
                  "failure_class": type(exc).__name__,
                  "product_sidecar_tested": False}
        exit_code = 2
    print(json.dumps(result, separators=(",", ":"), sort_keys=True))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
