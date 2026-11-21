#!/usr/bin/env python3
"""P2-U2f: isolated real-font / in-memory Unicode rendering experiment ONLY.

Never imported by production reports, chart renderers, or sidecar. Uses the
previously pinned six-file build-review bundle, with NO downloading, copying,
installer, user projects, saved reports, font installation or release approval.
One process per invocation to isolate ReportLab's global dynamic-font cache.
"""
from __future__ import annotations

from io import BytesIO
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

from backend.pdf_unicode_runs import (
    PDFUnicodePlanError, paragraph_markup, plan_font_runs,
    position_chart_runs, validate_coverage,
)
from p2_pdf_font_build_preflight import _not_redirected
from p2_pdf_font_resource_path_devqa import MANIFEST_PATH, REVIEW_PARENT
from p2_pdf_frozen_font_onefile_devqa import verified_review_files

TEXT = "café São Paulo R² Δ Ω Москва 漢字 ₹ 📈"
CHART_LABEL = "Δ 漢字 📈"
FONT_NAMES = {
    "regular": "ODIN-P2-U2F-Primary",
    "cjk": "ODIN-P2-U2F-CJK",
    "symbol": "ODIN-P2-U2F-Symbol",
}
MAX_PDF_BYTES = 3 * 1024 * 1024


def selected_review_sources(root: Path, entries: list[dict]) -> dict[str, Path]:
    """Return only three files from an ALREADY independently reviewed set."""
    if not isinstance(root, Path) or not root.is_absolute() or not root.is_dir():
        raise PDFUnicodePlanError("Pinned DevQA review directory is absent")
    _not_redirected(root)
    if not isinstance(entries, list) or len(entries) != 6:
        raise PDFUnicodePlanError("Full pinned six-file review is required")
    expected = {(role, kind) for role in FONT_NAMES for kind in ("font", "license")}
    identities = {}
    for entry in entries:
        if not isinstance(entry, dict):
            raise PDFUnicodePlanError("Malformed reviewed source record")
        role, kind, name = entry.get("role"), entry.get("kind"), entry.get("name")
        if ((role, kind) not in expected or (role, kind) in identities or
                not isinstance(name, str) or name in ("", ".", "..") or
                Path(name).name != name or "/" in name or "\\" in name):
            raise PDFUnicodePlanError("Invalid pinned font or notice identity")
        path = root / name
        _not_redirected(path)
        if not path.is_file() or path.is_symlink() or (
                not isinstance(entry.get("bytes"), int) or isinstance(entry.get("bytes"), bool) or
                path.stat().st_size != entry["bytes"]):
            raise PDFUnicodePlanError("Pinned DevQA font or notice missing")
        identities[role, kind] = path
    if set(identities) != expected:
        raise PDFUnicodePlanError("Incomplete pinned font and notice sources")
    return {role: identities[role, "font"] for role in FONT_NAMES}


def verified_font_coverage(fonts: dict) -> dict[str, frozenset[int]]:
    """Get actual nonzero TrueType glyph IDs from three registered faces.

    The caller must have independently checked the six source hashes and
    registered DocumentUnicodeTTFont objects. Names alone prove nothing.
    """
    if not isinstance(fonts, dict) or set(fonts) != set(FONT_NAMES):
        raise PDFUnicodePlanError("Missing scoped registered font role")
    coverage = {}
    for role, face in fonts.items():
        raw = getattr(getattr(face, "face", None), "charToGlyph", None)
        if not isinstance(raw, dict):
            raise PDFUnicodePlanError("No verified TrueType glyph map")
        points = frozenset(cp for cp, glyph in raw.items()
                           if isinstance(glyph, int) and glyph > 0)
        coverage[role] = points
    validate_coverage(coverage)
    for probe in (TEXT, CHART_LABEL):
        plan_font_runs(probe, coverage)
    return coverage


def register_scoped_faces(paths: dict[str, Path]) -> dict:
    """Restricted to the one-shot developer CLI, not a running FastAPI app."""
    if not isinstance(paths, dict) or set(paths) != set(FONT_NAMES):
        raise PDFUnicodePlanError("Expected three verified DevQA font paths")
    from reportlab.pdfbase import pdfmetrics
    from backend.pdf_unicode_cmap import (
        DocumentUnicodeTTFont, register_document_unicode_font,
    )
    result = {}
    for role, name in FONT_NAMES.items():
        path = paths[role]
        if not isinstance(path, Path) or not path.is_absolute():
            raise PDFUnicodePlanError("No verified absolute font path")
        _not_redirected(path)
        if not path.is_file() or path.is_symlink():
            raise PDFUnicodePlanError("Missing reviewed TrueType input")
        # Never recycle global ReportLab names from another live report.
        try:
            pdfmetrics.getFont(name)
        except KeyError:
            pass
        else:
            raise PDFUnicodePlanError("Conflicting process-global ReportLab name")
        obj = register_document_unicode_font(DocumentUnicodeTTFont(name, str(path)))
        if pdfmetrics.getFont(name) is not obj:
            raise PDFUnicodePlanError("Dynamic face identity mismatch")
        result[role] = obj
    return result


def make_chart_drawing(label: str, coverage: dict, measure) -> object:
    """Synthetic vector text only; leave product chart visuals intact."""
    from reportlab.graphics.shapes import Drawing, String
    from reportlab.lib import colors
    runs = position_chart_runs(
        plan_font_runs(label, coverage), FONT_NAMES,
        font_size=11.0, max_width=390.0, anchor="middle", measure=measure,
    )
    drawing = Drawing(440, 58)
    for run in runs:
        drawing.add(String(220.0 + run.x_offset, 29.0, run.text,
                           fontName=run.font_name, fontSize=11.0,
                           textAnchor="start", fillColor=colors.black))
    return drawing


def inspect_synthetic_pdf_bytes(raw: bytes) -> dict:
    """Check actual PDF text extraction for paragraphs AND vector chart runs."""
    if not isinstance(raw, bytes) or not 0 < len(raw) <= MAX_PDF_BYTES:
        raise PDFUnicodePlanError("Invalid or excessive synthetic PDF output")
    try:
        import pymupdf as fitz
    except ImportError:
        import fitz
    with fitz.open(stream=raw, filetype="pdf") as doc:
        if len(doc) != 1:
            raise PDFUnicodePlanError("Unexpected synthetic PDF pagination")
        page = doc[0]
        text = " ".join(page.get_text().split())
        # Paragraph and vector chart must BOTH preserve these text cases.
        if TEXT not in text:
            raise PDFUnicodePlanError("Mixed paragraph Unicode extraction mismatch")
        chart = text.split(TEXT, 1)[1].strip()
        if CHART_LABEL not in chart:
            raise PDFUnicodePlanError("Vector label Unicode extraction mismatch")
        if any(not page.rect.contains(rect) for rect in
               (fitz.Rect(line["bbox"]) for block in page.get_text("dict")["blocks"]
                if block.get("type") == 0 for line in block.get("lines", []))):
            raise PDFUnicodePlanError("Synthetic text outside page bounds")
    return {"paragraph_exact": True, "vector_label_exact": True,
            "one_page": True, "page_bounds_ok": True}


def probe_in_memory(root: Path, entries: list[dict]) -> dict:
    """No disk PDF. Must be called in a fresh, disposable developer process."""
    from reportlab import Version as reportlab_version
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.pdfbase import pdfmetrics
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

    if reportlab_version != "4.5.1":
        raise PDFUnicodePlanError("Owner-verified ReportLab version changed")
    sources = selected_review_sources(root, entries)
    faces = register_scoped_faces(sources)
    coverage = verified_font_coverage(faces)
    runs = plan_font_runs(TEXT, coverage)
    markup = paragraph_markup(runs, FONT_NAMES)
    style = ParagraphStyle("ODIN_P2_U2F_IN_MEMORY", fontName=FONT_NAMES["regular"],
                           fontSize=12, leading=18, wordWrap="CJK")
    paragraph = Paragraph(markup, style)
    drawing = make_chart_drawing(CHART_LABEL, coverage, pdfmetrics.stringWidth)
    output = BytesIO()
    doc = SimpleDocTemplate(output, pagesize=A4, pageCompression=1,
                            leftMargin=43, rightMargin=43,
                            topMargin=40, bottomMargin=46)
    doc.build([paragraph, Spacer(1, 20), drawing])
    result = inspect_synthetic_pdf_bytes(output.getvalue())
    return {"state": "SCOPED_FONT_CONTEXT_IN_MEMORY_PASS", "stage": "completed",
            "reportlab_version": reportlab_version, "verified_source_files": 6,
            "font_roles_registered": 3, **result,
            "product_unicode_pdf": "NOT_TESTED", "release_font_approval": "NOT_GRANTED",
            "installer": "NOT_TESTED", "visual_acceptance": "NOT_TESTED"}


def main() -> int:
    result = {"state": "BLOCKED", "stage": "prerequisite",
              "product_unicode_pdf": "NOT_TESTED", "release_font_approval": "NOT_GRANTED",
              "installer": "NOT_TESTED", "visual_acceptance": "NOT_TESTED"}
    try:
        if sys.platform != "win32":
            raise PDFUnicodePlanError("Windows-only owner scoped proof")
        from reportlab import Version as version
        if version != "4.5.1":
            raise PDFUnicodePlanError("Unexpected ReportLab version")
        manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        reviewed, entries = verified_review_files(REVIEW_PARENT, manifest)
        result = probe_in_memory(reviewed, entries)
    except Exception as exc:
        result.update({"state": "BLOCKED", "failure_stage": "source_or_render",
                       "failure_class": type(exc).__name__})
    print("P2 UNICODE FONT CONTEXT DEVQA: " + result["state"])
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["state"] == "SCOPED_FONT_CONTEXT_IN_MEMORY_PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
