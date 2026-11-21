#!/usr/bin/env python3
"""Isolated, read-only P2 research into ReportLab supplementary Unicode maps.

Loads ONLY six previously pinned font/license files from a DevQA candidate
directory. Generates two small synthetic PDFs exclusively in memory.
Temporarily varies ReportLab's ToUnicode builder within this one-process
research CLI and restores it in finally. NEVER import this in production,
monkeypatch a running FastAPI service, alter user data, or ship edited fonts.
"""
from __future__ import annotations

import hashlib
from io import BytesIO
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from qa_foundation import default_root, safe_root
from p2_pdf_font_asset_gate import verify

MANIFEST = Path(__file__).with_name("p2_pdf_font_candidates.json")
TEST_TEXT = "📈"
TEST_CODEPOINT = ord(TEST_TEXT)
MAX_PAGES = 2


def corrected_tounicode_cmap(cmap: str) -> str:
    """Correct destination values for scalar > U+FFFF as UTF-16BE surrogates.

    Preserve the source subset-code keys and all BMP values unchanged.
    Do not parse/patch arbitrary untrusted PDF streams in this function.
    """
    def correct(match):
        source_code, destination = match.groups()
        # Already encoded 8-digit destination values can represent a valid
        # surrogate pair or multiple BMP codepoints. Leave those untouched.
        if len(destination) == 8:
            return match.group(0)
        number = int(destination, 16)
        if number > 0x10FFFF or 0xD800 <= number <= 0xDFFF:
            raise ValueError("Invalid Unicode scalar in ReportLab CMap")
        if number <= 0xFFFF:
            return match.group(0)
        utf16be = chr(number).encode("utf-16-be").hex().upper()
        return "<" + source_code + "> <" + utf16be + ">"
    return re.sub(
        r"(?m)^<([0-9A-Fa-f]{2})> <([0-9A-Fa-f]{4,8})>$",
        correct, cmap)


def local_experiment(root: Path, manifest: dict) -> dict:
    """Pure developer experiment, never a product Unicode acceptance result."""
    from reportlab import Version
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.pdfbase import pdfmetrics, ttfonts
    from reportlab.platypus import Paragraph, SimpleDocTemplate
    import fitz

    safe = safe_root(root, ROOT)
    if not safe.is_dir():
        raise ValueError("Pinned staged fonts are missing")
    identity = verify(safe, manifest)
    if identity["state"] != "CANDIDATE_FILE_AND_CMAP_PROBE_PASS":
        raise ValueError("Pinned asset or glyph gate incomplete")

    symbol = next(item for item in manifest["assets"] if item["role"] == "symbol")
    symbol_file = safe / symbol["filename"]
    fontname = "ODIN-ISOLATED-SYMBOL-CMAP-RESEARCH"
    face = ttfonts.TTFont(fontname, str(symbol_file))
    if not face.face.charToGlyph.get(TEST_CODEPOINT):
        raise ValueError("No supported symbol glyph")
    pdfmetrics.registerFont(face)
    style = ParagraphStyle("ODIN_CMAP_RESEARCH", fontName=fontname,
                           fontSize=19, leading=27)
    original = ttfonts.makeToUnicodeCMap

    def build(*, adjusted: bool):
        target = BytesIO()
        try:
            if adjusted:
                ttfonts.makeToUnicodeCMap = (
                    lambda name, subset: corrected_tounicode_cmap(original(name, subset)))
            else:
                ttfonts.makeToUnicodeCMap = original
            doc = SimpleDocTemplate(target, pagesize=A4, pageCompression=1)
            doc.build([Paragraph(TEST_TEXT, style)])
        finally:
            ttfonts.makeToUnicodeCMap = original

        with fitz.open(stream=target.getvalue(), filetype="pdf") as pdf:
            if len(pdf) != 1 or len(pdf) > MAX_PAGES:
                raise ValueError("Unexpected probe PDF geometry")
            page = pdf[0]
            result = {
                "text": page.get_text().strip(),
                "visual_sha256": hashlib.sha256(
                    page.get_pixmap(matrix=fitz.Matrix(1.5, 1.5),
                                    alpha=False).samples).hexdigest(),
            }
            return result

    baseline = build(adjusted=False)
    adjusted = build(adjusted=True)
    return {
        "state": "RESEARCH_ONLY",
        "reportlab_version": Version,
        "font_asset_identity": "VERIFIED_PINNED_SIX_FILES",
        "baseline_text": baseline["text"],
        "corrected_text": adjusted["text"],
        "baseline_matches": baseline["text"] == TEST_TEXT,
        "corrected_matches": adjusted["text"] == TEST_TEXT,
        "same_rendered_pixels": baseline["visual_sha256"] == adjusted["visual_sha256"],
        "product_acceptance": "NOT_TESTED",
        "visual_acceptance": "NOT_TESTED",
        "warning": "Changing a global ReportLab function is RESEARCH ONLY. "
                   "Never use this temporary patch inside concurrent application reporting.",
    }


def main():
    try:
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        data = local_experiment(default_root() / "font-candidates", manifest)
    except Exception as exc:
        data = {"state": "BLOCKED", "reason_class": type(exc).__name__,
                "product_acceptance": "NOT_TESTED"}
    print(json.dumps(data, ensure_ascii=False, indent=2))
    return 0 if (data["state"] == "RESEARCH_ONLY" and
                 data.get("corrected_matches") and
                 data.get("same_rendered_pixels")) else 2


if __name__ == "__main__":
    raise SystemExit(main())
