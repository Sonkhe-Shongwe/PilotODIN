"""Focused P2 display-limit and PDF-bound checks against synthetic frozen reports.

Tests do not create real user projects, import files, train models or save reports.
The dedicated DevQA runner sets PILOTODIN_HOME before this module is imported.
"""
from __future__ import annotations

import copy
import json
import os
from pathlib import Path
import re
import unittest

import fitz
from backend import reports, report_charts

ROWS = [{"label": "Synthetic Group " + str(i), "value": i + 1}
        for i in range(45)]
FINDINGS = [{"title": "Synthetic Finding " + str(i),
             "detail": "Synthetic screening evidence, not a confirmed error"}
            for i in range(35)]
FACTS = {"Synthetic metric " + str(i): i for i in range(30)}


def artifact(operation, result, index):
    return {
        "id": format(index, "032x"),
        "operation": operation,
        "dataset_version": 0,
        "tool_version": "synthetic-display-test-v1",
        "computed_at": "2026-10-26T00:00:00+00:00",
        "objective": "Synthetic read-only test of display completeness",
        "params": {},
        "result": copy.deepcopy(result),
    }


def report_fixture():
    bars = report_charts.visual_spec({
        "type": "bar", "x": "Region", "y": "Revenue", "aggregation": "sum",
        "data": ROWS[:20], "truncated": True,
    })
    if bars is None:
        raise AssertionError("Synthetic chart fixture was not accepted")
    return {
        "id": "9" * 32, "title": "Synthetic P2 disclosure report",
        "revision": 1, "content_sha256": "a" * 64, "dataset_versions": [0],
        "narrative": "Synthetic evidence only. User interpretation is unverified.",
        "limitations": ["Illustrative data only, not an actual dataset assessment."],
        "evidence": [
            artifact("overview", {"summary": FACTS}, 1),
            artifact("explore_snapshot", {"data": ROWS, "visual": bars,
                                        "note": "Some saved categories were already bounded upstream."}, 2),
            artifact("quality_audit", {"findings": FINDINGS}, 3),
            artifact("compare", {"data": ROWS + ROWS[:8]}, 4),
        ],
    }


class P2DisplayQuality(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        home = os.environ.get("PILOTODIN_HOME")
        run = os.environ.get("PILOTODIN_DEVQA_RUN")
        if not home or not run:
            raise RuntimeError("Test requires a fresh isolated DevQA environment")
        root = Path(run).resolve()
        if (Path(home).resolve() != root / "workspace" or
                not (root / "manifest.json").is_file()):
            raise RuntimeError("Refusing unverified P2 display QA home")
        manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
        if (manifest.get("phase") != "P2-REPORT-DISPLAY" or
                manifest.get("state") != "READY_NOT_TESTED"):
            raise RuntimeError("Unexpected P2 DevQA run state")

    def test_01_fact_and_observation_omission_counts(self):
        report = report_fixture()
        facts, _, _, notices = reports._exhibit_with_disclosure(report["evidence"][0])
        self.assertEqual(len(facts), 24)
        self.assertIn("Showing 24 of 30 saved summary facts; 6 not shown", notices[0])
        _, _, rows, row_notes = reports._exhibit_with_disclosure(report["evidence"][1])
        self.assertEqual(len(rows), 40)
        self.assertIn("Showing 40 of 45 saved observation entries; 5 not shown", row_notes[0])
        self.assertEqual(len(reports._exhibit(report["evidence"][1])), 3)

    def test_02_finding_and_compare_omission_counts(self):
        report = report_fixture()
        _, _, findings, notes = reports._exhibit_with_disclosure(report["evidence"][2])
        self.assertEqual(len(findings), 30)
        self.assertIn("Showing 30 of 35 saved finding entries; 5 not shown", notes[0])
        _, _, comparisons, notes = reports._exhibit_with_disclosure(report["evidence"][3])
        self.assertEqual(len(comparisons), 50)
        self.assertIn("Showing 50 of 53 saved observation entries; 3 not shown", notes[0])

    def test_03_html_pdf_display_limit_parity(self):
        saved = report_fixture()
        before = copy.deepcopy(saved)
        html = reports.render_html(saved).decode("utf-8")
        with fitz.open(stream=reports.render_pdf(saved), filetype="pdf") as pdf:
            text = " ".join(" ".join(p.get_text().split()) for p in pdf)
        for marker in ("Showing 24 of 30 saved summary facts",
                       "Showing 40 of 45 saved observation entries",
                       "Showing 30 of 35 saved finding entries",
                       "Showing 50 of 53 saved observation entries",
                       "The complete frozen evidence remains"):
            self.assertIn(marker, html)
            self.assertIn(marker, text)
        self.assertIn("Visual shows a bounded subset", html)
        self.assertIn("Visual shows a bounded subset", text)
        self.assertEqual(saved, before)

    def test_04_no_invented_omission_for_small_evidence(self):
        simple = artifact("overview", {"summary": {"Rows": 4},
                                       "data": [{"label": "North", "value": 4}]}, 5)
        facts, _, rows, notices = reports._exhibit_with_disclosure(simple)
        self.assertEqual(len(facts), 1)
        self.assertEqual(len(rows), 1)
        self.assertEqual(notices, [])

    def test_05_dense_pdf_page_bound_smoke(self):
        doc = report_fixture()
        originals = copy.deepcopy(doc)
        dense = copy.deepcopy(doc)
        dense["narrative"] = ("Long synthetic explanation with whitespace and limits. " * 25)
        dense["evidence"] = []
        for i in range(3):
            for art in originals["evidence"]:
                copy_art = copy.deepcopy(art)
                copy_art["id"] = format(len(dense["evidence"]) + 1, "032x")
                copy_art["objective"] = ("Long synthetic investigation objective " * 5)
                dense["evidence"].append(copy_art)
        self.assertEqual(len(dense["evidence"]), 12)
        with fitz.open(stream=reports.render_pdf(dense), filetype="pdf") as pdf:
            self.assertGreaterEqual(len(pdf), 3)
            for page in pdf:
                self.assertAlmostEqual(page.rect.width, 595.276, delta=1)
                self.assertAlmostEqual(page.rect.height, 841.89, delta=1)
                for box in page.get_text("blocks"):
                    x0, y0, x1, y1 = box[:4]
                    self.assertGreaterEqual(x0, -1)
                    self.assertGreaterEqual(y0, -1)
                    self.assertLessEqual(x1, page.rect.width + 1)
                    self.assertLessEqual(y1, page.rect.height + 1)
        # Page bounds and extracted text do not certify glyph rendering,
        # baseline collisions, typeface coverage or human print readability.
        self.assertEqual(doc, originals)


if __name__ == "__main__":
    unittest.main()
