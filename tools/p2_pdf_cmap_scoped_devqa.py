#!/usr/bin/env python3
"""Isolated owner Windows proof for a document-scoped Unicode font helper.

Each mode runs in a DIFFERENT process because ReportLab caches dynamic fonts
by internal face name. No production renderer, real projects, models, native
app, installer, PDF output files or internet access. Reads only the six already
verified font/license candidates in local DevQA.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

PHASE = "P2_PDF_CMAP_SCOPED_RESEARCH"
EXPECTED = "📈"
TEST_COUNT = 9


def candidate_font():
    from qa_foundation import default_root, safe_root
    from p2_pdf_font_asset_gate import verify

    root = safe_root(default_root() / "font-candidates", ROOT)
    manifest_file = ROOT / "tools" / "p2_pdf_font_candidates.json"
    manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
    if not root.is_dir():
        raise ValueError("Existing verified font-candidates folder is required")
    checked = verify(root, manifest)
    if checked["state"] != "CANDIDATE_FILE_AND_CMAP_PROBE_PASS":
        raise ValueError("Pinned candidate font/OF L integrity gate failed")
    symbols = [x for x in manifest["assets"] if x["role"] == "symbol"]
    if len(symbols) != 1:
        raise ValueError("Symbol font manifest is ambiguous")
    return root / symbols[0]["filename"]


def render_child(mode):
    from reportlab import Version as reportlab_version
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.platypus import Paragraph, SimpleDocTemplate
    try:
        import pymupdf as fitz
    except ImportError:
        import fitz

    font_path = candidate_font()
    name = "ODIN-P2-ISOLATED-FONT-" + mode.upper()
    if mode == "corrected":
        from backend.pdf_unicode_cmap import (
            DocumentUnicodeTTFont, register_document_unicode_font)
        font = register_document_unicode_font(DocumentUnicodeTTFont(name, str(font_path)))
        if pdfmetrics.getFont(name) is not font:
            raise ValueError("ReportLab dynamic font registry replaced corrected font")
    elif mode == "baseline":
        font = TTFont(name, str(font_path))
        pdfmetrics.registerFont(font)
    else:
        raise ValueError("Unsupported child mode")
    report = io.BytesIO()
    doc = SimpleDocTemplate(report, pageCompression=1)
    doc.build([Paragraph(EXPECTED, ParagraphStyle("ODIN_CMAP_TEST",
                                                 fontName=name, fontSize=18))])
    with fitz.open(stream=report.getvalue(), filetype="pdf") as pdf:
        if len(pdf) != 1:
            raise ValueError("Unexpected scoped font experiment page count")
        page = pdf[0]
        extracted = page.get_text().strip()
        pixels = page.get_pixmap(matrix=fitz.Matrix(1.5, 1.5), alpha=False).samples
        return {"mode": mode, "exact": extracted == EXPECTED,
                "extracted_codepoints": ["U+%04X" % ord(c) for c in extracted][:12],
                "pixel_sha256": hashlib.sha256(pixels).hexdigest(),
                "reportlab_version": reportlab_version}


def run_unit_worker():
    suite = unittest.defaultTestLoader.discover(
        str(ROOT / "tests"), pattern="test_p2_pdf_unicode_cmap_unit.py")
    expected = suite.countTestCases()
    result = unittest.TestResult()
    suite.run(result)
    return {"state": "PASS" if
            expected == TEST_COUNT and result.testsRun == TEST_COUNT and
            not (result.failures or result.errors or result.skipped)
            else "FAIL",
            "expected": TEST_COUNT, "executed": result.testsRun,
            "failures": len(result.failures), "errors": len(result.errors),
            "skipped": len(result.skipped)}


def invoke(mode):
    p = subprocess.run(
        [sys.executable, "-B", str(Path(__file__).resolve()), "--mode", mode],
        cwd=ROOT, env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
        capture_output=True, text=True, timeout=100, check=False)
    try:
        data = json.loads(p.stdout)
    except ValueError:
        return {"state": "BLOCKED", "worker": mode, "reason": "malformed_worker_json"}
    if not isinstance(data, dict) or data.get("mode") != mode:
        return {"state": "BLOCKED", "worker": mode, "reason": "unexpected_worker_response"}
    if p.returncode != 0 and not (mode == "unit" and data.get("state") == "FAIL"):
        return {"state": "BLOCKED", "worker": mode, "exit_code": p.returncode,
                "failure_class": data.get("failure_class", "worker_nonzero")}
    return data


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("baseline", "corrected", "unit"))
    args = parser.parse_args()
    if args.mode:
        try:
            if args.mode == "unit":
                out = {"mode": "unit", **run_unit_worker()}
            else:
                out = render_child(args.mode)
            print(json.dumps(out, ensure_ascii=False))
            return 0 if out.get("state", "PASS") == "PASS" else 2
        except Exception as exc:
            print(json.dumps({"mode": args.mode, "state": "BLOCKED",
                              "failure_class": type(exc).__name__}))
            return 2

    report = {
        "phase": PHASE, "state": "BLOCKED",
        "product_acceptance": "NOT_TESTED",
        "visual_acceptance": "NOT_TESTED",
        "warning": "Scoped isolated helper proof only, not app/P2 PDF acceptance",
    }
    try:
        if os.name != "nt" or not os.environ.get("LOCALAPPDATA"):
            raise ValueError("Windows LOCALAPPDATA required")
        unit = invoke("unit")
        base = invoke("baseline")
        safe = invoke("corrected")
        report.update({"unit_tests": unit, "baseline": base, "corrected": safe})
        ready = (
            unit.get("state") == "PASS" and
            base.get("exact") is False and
            safe.get("exact") is True and
            isinstance(base.get("pixel_sha256"), str) and
            base["pixel_sha256"] == safe.get("pixel_sha256") and
            base.get("reportlab_version") == safe.get("reportlab_version")
        )
        if ready:
            report["state"] = "SCOPED_EXPERIMENT_PASS"
        elif unit.get("state") == "FAIL":
            report["state"] = "FAIL"
        elif any(x.get("state") == "BLOCKED" for x in (unit, base, safe)):
            report["state"] = "BLOCKED"
        else:
            report["state"] = "REVIEW_REQUIRED"
    except subprocess.TimeoutExpired:
        report["state"] = "BLOCKED"
        report["reason"] = "worker_timeout"
    except Exception as exc:
        report["state"] = "BLOCKED"
        report["reason_class"] = type(exc).__name__

    print("P2 DOCUMENT-SCOPED CMAP DEVQA: " + report["state"])
    print("UNIT TESTS: " + str(report.get("unit_tests", {}).get("executed", 0)) +
          " / " + str(TEST_COUNT))
    print("BASELINE EXACT: " + str(report.get("baseline", {}).get("exact")))
    print("CORRECTED EXACT: " + str(report.get("corrected", {}).get("exact")))
    print("RENDER PIXELS IDENTICAL: " + str(
        report.get("baseline", {}).get("pixel_sha256") is not None and
        report.get("baseline", {}).get("pixel_sha256") ==
        report.get("corrected", {}).get("pixel_sha256")))
    print("REPORTLAB: " + str(report.get("corrected", {}).get("reportlab_version", "unknown")))
    print("NO fonts copied or production reports generated.")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["state"] == "SCOPED_EXPERIMENT_PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
