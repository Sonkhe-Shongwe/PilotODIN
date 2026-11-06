#!/usr/bin/env python3
"""P2 single coherent actual report-renderer Unicode DevQA, NOT a release.

Read only previous six approved-for-DevQA candidate files, render ONE synthetic
actual backend.reports.render_pdf(report, unicode_context=...) output and save
it only in a new ignored DevQA proof directory with explicit operator consent.
NEVER imports a real project, upgrades package deps, copies original fonts,
writes the live user home, launches Tauri/PyInstaller, or authorizes font release.
"""
from __future__ import annotations

import copy
import hashlib
import json
import os
from pathlib import Path
import sys
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

from p2_pdf_font_build_preflight import _not_redirected
from p2_pdf_font_resource_path_devqa import MANIFEST_PATH, REVIEW_PARENT
from p2_pdf_frozen_font_onefile_devqa import verified_review_files
from p2_pdf_unicode_context_devqa import (
    FONT_NAMES, register_scoped_faces, verified_font_coverage,
)
from backend.pdf_unicode_seam import UnicodePDFContext

PROOF_ROOT = ROOT / "build" / "p2-unicode-real-report-devqa"
EXPECTED_LABELS = ("café São Paulo R² Δ Ω Москва 漢字 ₹ 📈",
                   "Median of Revenue by Region 漢字", "📈", "漢字")
MAX_PDF_BYTES = 8 * 1024 * 1024


def synthetic_revision() -> dict:
    """Synthetic checked numbers; no backend reads or user datasets."""
    art = {
        "id": "9" * 32, "operation": "compare", "dataset_version": 1,
        "tool_version": "p2-synthetic", "computed_at": "2026-10-26T00:00:00Z",
        "objective": "Compare verified 漢字 versus 📈 categories.",
        "params": {"x": "Region 漢字", "y": "Revenue"},
        "result": {
            "data": [{"label": "漢字", "value": 20.0},
                     {"label": "📈", "value": 10.0}],
            "visual": {"type": "bar", "x": "Region 漢字", "y": "Revenue",
                       "aggregation": "median",
                       "data": [{"label": "漢字", "value": 20.0},
                                {"label": "📈", "value": 10.0}]},
        },
    }
    return {
        "id": "a" * 32, "revision": 3,
        "title": EXPECTED_LABELS[0],
        "narrative": "Verified local synthetic report. Москва · 漢字 · 📈.",
        "dataset_versions": [1],
        "content_sha256": "f" * 64,
        "evidence": [art],
        "limitations": ["Synthetic-only evidence; no causal or model claim.",
                        "Currency ₹ and symbol 📈 are font rendering probes."],
    }


def proof_bytes(report: dict, context: UnicodePDFContext) -> tuple[bytes, dict]:
    """Use actual product renderer on immutable input; no persistent data read."""
    try:
        import pymupdf as fitz
    except ImportError:
        import fitz
    from backend import reports

    original = copy.deepcopy(report)
    before_hash = hashlib.sha256(
        json.dumps(report, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()
    html_before = reports.render_html(report)

    # Regression on the normal default renderer: no Unicode context supplied,
    # no dependency on the new font files or an approved-release manifest.
    legacy = {
        "id": "b" * 32, "revision": 1, "title": "Synthetic ASCII baseline",
        "narrative": "Ordinary safe reporting remains available.",
        "dataset_versions": [1], "content_sha256": "e" * 64,
        "evidence": [], "limitations": ["No actual project records."],
    }
    ascii_pdf = reports.render_pdf(legacy)
    with fitz.open(stream=ascii_pdf, filetype="pdf") as baseline:
        if len(baseline) != 1 or "Synthetic ASCII baseline" not in baseline[0].get_text():
            raise ValueError("Legacy default report rendering regression")

    raw = reports.render_pdf(report, unicode_context=context)
    html_after = reports.render_html(report)
    if report != original or html_before != html_after or (
            before_hash != hashlib.sha256(
                json.dumps(report, ensure_ascii=False, sort_keys=True).encode("utf-8")
            ).hexdigest()):
        raise ValueError("Synthetic immutable report or HTML mutated")
    if not isinstance(raw, bytes) or not 0 < len(raw) <= MAX_PDF_BYTES:
        raise ValueError("Real renderer returned invalid or excessive PDF")
    with fitz.open(stream=raw, filetype="pdf") as doc:
        if not 1 <= len(doc) <= 4:
            raise ValueError("Unexpected real renderer PDF page count")
        # The previous real owner PDF put only parameters and two limitations
        # on a nearly empty page 2. Text extraction passed but visual QA did
        # not. Reject that exact sparse-continuation failure in future runs.
        if len(doc) > 1:
            last = doc[-1]
            bounds = [block[:4] for block in last.get_text("blocks")
                      if len(block) >= 5 and isinstance(block[4], str)
                      and block[4].strip() and
                      not block[4].strip().startswith("PilotODIN · Verified")]
            if bounds and max(box[3] for box in bounds) < last.rect.height * 0.34:
                raise ValueError("Sparse continuation page in synthetic Unicode PDF")
        pages = [page.get_text() for page in doc]
        text = " ".join(" ".join(pages).split())
        for label in EXPECTED_LABELS:
            if label not in text:
                raise ValueError("Unicode report/chart extraction mismatch")
        for item in ("20", "10", "f" * 64, "PilotODIN", "Page 1",
                     "Synthetic-only evidence"):
            if item not in text:
                raise ValueError("Saved numeric/evidence/footer text missing")
        for page in doc:
            for block in page.get_text("dict")["blocks"]:
                if block.get("type") != 0:
                    continue
                for line in block.get("lines", []):
                    if not page.rect.contains(fitz.Rect(line["bbox"])):
                        raise ValueError("Synthetic report text outside page bounds")
        pages_count = len(doc)
    return raw, {
        "real_backend_report_pdf": True,
        "legacy_default_report_preserved": True,
        "unicode_title_narrative_table_chart": True,
        "chart_metric_values_unchanged": True,
        "immutable_revision_and_html": True,
        "footer_and_pages": True,
        "page_bounds": True,
        "pages": pages_count,
        "pdf_bytes": len(raw),
        "pdf_sha256": hashlib.sha256(raw).hexdigest(),
    }


def run() -> dict:
    from reportlab import Version
    if sys.platform != "win32" or Version != "4.5.1":
        raise ValueError("Owner Windows and approved ReportLab version required")
    if os.environ.get("PILOTODIN_HOME"):
        raise ValueError("Do not run with a preexisting project-home marker")
    _not_redirected(PROOF_ROOT)
    if not PROOF_ROOT.exists():
        PROOF_ROOT.mkdir(parents=True, exist_ok=False)
    if not PROOF_ROOT.is_dir():
        raise ValueError("Invalid ignored DevQA proof location")
    _not_redirected(PROOF_ROOT)
    run_dir = PROOF_ROOT / ("run-" + uuid.uuid4().hex)
    _not_redirected(run_dir)
    run_dir.mkdir(exist_ok=False)

    # Environment chosen BEFORE backend.storage/reports are first imported.
    disposable_home = run_dir / "home"
    disposable_home.mkdir(exist_ok=False)
    os.environ["PILOTODIN_HOME"] = str(disposable_home)
    try:
        manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        folder, entries = verified_review_files(REVIEW_PARENT, manifest)
        if len(entries) != 6:
            raise ValueError("Pinned six-file review incomplete")
        # No copying font binaries; original already-reviewed sources read-only.
        paths = {
            e["role"]: folder / e["name"]
            for e in entries if e["kind"] == "font"
        }
        if set(paths) != set(FONT_NAMES):
            raise ValueError("Pinned DevQA face roles incomplete")
        fonts = register_scoped_faces(paths)
        coverage = verified_font_coverage(fonts)
        context = UnicodePDFContext(FONT_NAMES, fonts, coverage)
        raw, evidence = proof_bytes(synthetic_revision(), context)
        output = run_dir / "SYNTHETIC_PilotODIN_Unicode_Report_DevQA_NOT_FOR_RELEASE.pdf"
        _not_redirected(output)
        with output.open("xb") as stream:
            stream.write(raw)
        return {
            "state": "SCOPED_ACTUAL_REPORT_UNICODE_SOURCE_PASS",
            "stage": "synthetic_real_report_renderer",
            "verified_devqa_fonts_and_notices": 6,
            **evidence, "proof_pdf_name": output.name,
            "proof_run_id": run_dir.name,
            "visual_acceptance": "OWNER_REVIEW_PENDING",
            "production_release_approval": "NOT_GRANTED",
            "product_unicode_pdf": "NOT_ACCEPTED",
            "installer": "NOT_TESTED",
        }
    finally:
        os.environ.pop("PILOTODIN_HOME", None)


def main() -> int:
    try:
        result = run()
    except Exception as exc:
        result = {
            "state": "BLOCKED", "stage": "isolated_product_unicode_source",
            "failure_class": type(exc).__name__,
            "product_unicode_pdf": "NOT_ACCEPTED",
            "production_release_approval": "NOT_GRANTED",
            "installer": "NOT_TESTED",
        }
    print("P2 ACTUAL SYNTHETIC REPORT UNICODE DEVQA: " + result["state"])
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["state"] == "SCOPED_ACTUAL_REPORT_UNICODE_SOURCE_PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
