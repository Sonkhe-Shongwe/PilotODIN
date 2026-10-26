#!/usr/bin/env python3
"""Developer-only probe of local font candidates for PilotODIN PDF exports.

No changes to backend, projects, datasets, Windows fonts or package installations.
ReportLab TTFont coverage, embedded PDF extraction and license review are
separate questions. This probe does NOT certify visual quality or font licensing.
"""
from __future__ import annotations

import argparse
import hashlib
from html import escape
import io
import json
from pathlib import Path
import sys

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import SimpleDocTemplate, Paragraph
import fitz

SAMPLES = {
    "latin": "café São Paulo R²",
    "greek": "Δ Ω",
    "cyrillic": "Москва",
    "rupee": "₹",
    "cjk": "漢字",
    "emoji": "📈",
    "mixed": "café São Paulo R² Δ Ω Москва 漢字 ₹ 📈",
}
# Do not infer that one Unicode-font family supports every writing system.
FAMILIES = ("regular", "cjk", "emoji")
MAX_FONT_BYTES = 32 * 1024 * 1024


def _digest(path):
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def _font(name, path):
    if not path.is_file() or path.is_symlink() or path.stat().st_size > MAX_FONT_BYTES:
        raise ValueError("Missing, linked or oversized explicit font candidate")
    font = TTFont("ODIN-PROBE-" + name.upper(), str(path))
    pdfmetrics.registerFont(font)
    mapping = font.face.charToGlyph
    return font, {cp for cp, glyph in mapping.items() if glyph}


def font_runs(text, coverage):
    """Choose explicit glyph-bearing faces, preserving original code points."""
    runs, missing = [], set()
    for char in text:
        match = next((family for family in FAMILIES if
                      ord(char) in coverage.get(family, set())), None)
        if match is None:
            missing.add(ord(char))
        elif runs and runs[-1][0] == match:
            runs[-1] = (match, runs[-1][1] + char)
        else:
            runs.append((match, char))
    return runs, sorted(missing)


def audit(paths):
    """Run a pure synthetic probe; never create a persistent PDF or read user data."""
    coverage = {}
    fonts = {}
    identities = {}
    for family in FAMILIES:
        path = paths.get(family)
        if path is None:
            continue
        font, glyphs = _font(family, path)
        fonts[family] = font
        coverage[family] = glyphs
        identities[family] = {
            "basename": path.name, "bytes": path.stat().st_size,
            "sha256": _digest(path)
        }
    results = {}
    for label, text in SAMPLES.items():
        runs, missing = font_runs(text, coverage)
        if missing:
            results[label] = {"state": "UNSUPPORTED",
                              "codepoints": ["U+%04X" % cp for cp in missing]}
            continue
        output = io.BytesIO()
        style = ParagraphStyle("ODIN_FONT_PROBE",
                               fontName=fonts["regular"].fontName,
                               fontSize=13, leading=19)
        doc = SimpleDocTemplate(output, pagesize=A4)
        markup = "".join(
            '<font name="' + escape(fonts[family].fontName, quote=True) + '">' +
            escape(segment) + '</font>'
            for family, segment in runs)
        try:
            doc.build([Paragraph(markup, style)])
            with fitz.open(stream=output.getvalue(), filetype="pdf") as pdf:
                extracted = " ".join(" ".join(page.get_text().split()) for page in pdf)
        except Exception as exc:
            results[label] = {"state": "RENDER_ERROR",
                              "class": type(exc).__name__}
            continue
        results[label] = {
            "state": "EXTRACTED_EXACT" if " ".join(text.split()) in extracted else "MISMATCH",
            "font_families_used": list(dict.fromkeys(family for family, _ in runs)),
        }
    return {"scope": "DEVELOPER_PROBE_NOT_ACCEPTANCE",
            "font_assets": identities, "samples": results,
            "limitations": ["No visual glyph/line collision proof",
                            "No OFL license or release bundling approval",
                            "No Windows .venv-live execution",
                            "Complex script shaping/emoji sequences untested",
                            "Emoji may render visibly yet fail exact ToUnicode extraction"]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--regular", type=Path, required=True,
                        help="Explicit local Latin/Greek/Cyrillic candidate TTF")
    parser.add_argument("--cjk", type=Path, help="Optional explicit CJK candidate TTF")
    parser.add_argument("--emoji", type=Path, help="Optional explicit monochrome emoji candidate TTF")
    args = parser.parse_args()
    try:
        result = audit({name: getattr(args, name) for name in FAMILIES})
    except Exception as exc:
        print(json.dumps({"state": "BLOCKED", "reason": type(exc).__name__,
                          "scope": "DEVELOPER_PROBE_NOT_ACCEPTANCE"}))
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if all(case["state"] == "EXTRACTED_EXACT"
                    for case in result["samples"].values()) else 2


if __name__ == "__main__":
    sys.exit(main())
