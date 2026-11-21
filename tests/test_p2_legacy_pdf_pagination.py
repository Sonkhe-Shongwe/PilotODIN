"""P2 BE-030: real, in-memory standard PDF pagination regression.

The fixture reproduces the owner-reviewed eight-row three-exhibit report.
No FastAPI, user home, network, font assets, model, saved file or installer.
The PDF is rendered by the REAL production backend in memory.
"""
from __future__ import annotations

import unittest

try:
    import pymupdf as fitz
except ImportError:
    import fitz

from backend import reports, report_charts, pdf_release_font_loader


SHA = "75af98c24ab9036d357f9633b0f388e8e4c40097c7b77910604add2b0465cc44"
VALUES = [("West", 710.0), ("South", 405.0),
          ("North", 380.0), ("East", 310.0)]
STAMP = "2026-11-06T13:29:40.253948+00:00"


def art(operation, name, result, params=None, stamp=STAMP):
    return {
        "id": ("a" if operation == "overview" else
               "b" if operation == "compare" else "c") * 32,
        "operation": operation,
        "objective": name,
        "dataset_version": 0,
        "tool_version": "explore-snapshot-v1" if operation == "explore_snapshot"
                        else "analytics.v0.8",
        "computed_at": stamp,
        "params": params or {},
        "result": result,
    }


def fixture():
    """Synthetic report content, no side effects and no data source access."""
    visual = {
        "type": "bar", "x": "Region", "y": "Revenue",
        "aggregation": "sum", "sampled": False, "truncated": False,
        "data": [{"label": label, "value": val} for label, val in VALUES],
        "note": "Descriptive relationships do not establish causation.",
    }
    overview = art("overview", "Synthetic overview report evidence", {
        "summary": {"Columns Count": 3, "Exact Duplicates": 0,
                    "Missing Cells": 0, "Rows": 8, "Version": 0}
    })
    compare = art("compare", "Synthetic compare report evidence", {
        "summary": {"Aggregation": "median", "Sampled": False,
                    "Truncated": False, "Type": "bar", "Version": 0,
                    "X": "Region", "Y": "Revenue"},
        "data": [{"label": label, "value": val}
                 for label, val in [("West", 355.0), ("South", 202.5),
                                    ("North", 190.0), ("East", 155.0)]],
        "note": "Descriptive relationships do not establish causation.",
    }, {"aggregation": "median", "x": "Region", "y": "Revenue"})
    snapshot = art("explore_snapshot", "Synthetic Regional Revenue Bar Chart", {
        "summary": {
            "Chart groups truncated": False,
            "Chart type": "bar",
            "Displayed chart rows": 4,
            "Matching exact duplicates": 0,
            "Matching missing cells": 0,
            "Plotted sample": False,
            "Rows matching saved filters": 8,
            "Source snapshot SHA-256": SHA,
            "Total dataset rows": 8,
        },
        "visual": visual,
        "data": [{"label": label, "value": val} for label, val in VALUES],
        "note": "Saved Explore calculations are descriptive, not causal. "
                "Report exhibit rows are bounded; the original immutable "
                "local snapshot is available in Explore.",
        "limitations": [
            "A saved analysis is descriptive and does not establish causation.",
            "Scatter plots may be sampled; categorical charts may truncate groups.",
            "Snapshot evidence does not include source-level records.",
        ],
    }, {"aggregation": "sum", "color_by": None, "filter_count": 0,
        "filters": None, "kind": "bar", "source_snapshot_sha256": SHA,
        "x": "Region", "y": "Revenue"})
    return {
        "id": "d" * 32,
        "revision": 1,
        "title": "Synthetic Regional Revenue Review",
        "content_sha256": "e" * 64,
        "dataset_versions": [0],
        "narrative": (
            "Purpose and decision: Review only eight disposable order records.\n"
            "Verified findings: Read the frozen aggregates and chart in this report.\n"
            "Limitations: These example values do not establish real-world causation.\n"
            "Next steps: Request an independently validated dataset before decisions."
        ),
        "limitations": [
            "Computed evidence is descriptive unless an independently validated "
            "inferential method is recorded.",
            "Interpretations in the narrative are user-authored and have not "
            "been computationally verified.",
            "Saved Explore chart excerpts are bounded and may be sampled or "
            "truncated; provenance is retained.",
        ],
        "evidence": [overview, compare, snapshot],
    }


class P2BE030LegacyPDFPagination(unittest.TestCase):
    def test_exact_synthetic_example_reduced_and_chart_values_kept_together(self):
        self.assertEqual(pdf_release_font_loader.RELEASE_APPROVAL_STATUS, "NOT_GRANTED")
        self.assertEqual(pdf_release_font_loader.RELEASE_PINNED_FILES, ())
        self.assertEqual(pdf_release_font_loader.RELEASE_APPROVAL_REFERENCE, "")
        document = fixture()
        payload = reports.render_pdf_for_export(document)
        self.assertTrue(payload.startswith(b"%PDF-"))
        with fitz.open(stream=payload, filetype="pdf") as pdf:
            self.assertEqual(len(pdf), 3, "Small saved chart must not create a fourth page")
            texts = [page.get_text() for page in pdf]
            self.assertTrue(all(text.strip() for text in texts))
            full_text = "\n".join(texts)
            for phrase in (
                document["title"], "Evidence register", "Overview",
                "Compare", "Explore Snapshot", "Saved chart visualization",
                "Source snapshot SHA-256", "Methodology and limitations",
                SHA, "355.0", "202.5", "190.0", "155.0",
                "710.0", "405.0", "380.0", "310.0"
            ):
                self.assertIn(phrase, full_text)
            chart_pages = [i for i, text in enumerate(texts)
                           if "Saved chart visualization" in text]
            observation_pages = [i for i, text in enumerate(texts)
                                 if "Label\nValue" in text]
            self.assertEqual(chart_pages, [2])
            self.assertEqual(observation_pages, [2])
            # The document now continues the metric table across pages with
            # a repeated header. It must not strand the chart/value table.
            self.assertIn("Measure\nVerified value", texts[2])
            self.assertIn("Methodology and limitations", texts[2])
            self.assertEqual([f"Page {n}" in t for n, t in enumerate(texts, 1)],
                             [True, True, True])

    def test_chart_default_size_and_opt_in_size_are_distinct(self):
        spec = report_charts.visual_spec(fixture()["evidence"][2]["result"]["visual"])
        self.assertIsNotNone(spec)
        self.assertEqual(report_charts.pdf_chart(spec).height, 220.0)
        self.assertEqual(report_charts.pdf_chart(spec, compact=True).height, 175.0)
        # Source point order and numbers are unmodified by presentation.
        self.assertEqual([(x["label"], x["value"]) for x in spec["data"]], VALUES)


if __name__ == "__main__":
    unittest.main()
