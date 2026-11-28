"""Focused saved-HTML chart layout tests, no project DB or user datasets.

These assertions protect the exact visual issue observed in the owner's saved
Deliver report: title baseline sat too close to the high-value Y-axis tick.
The verified numeric aggregate and the ordinary PDF renderer stay unchanged.
"""
from __future__ import annotations

import copy
from html import unescape
import re
import unittest
from xml.etree import ElementTree as ET

from backend import report_charts


def fixture(kind="bar", *, caption_x="Education", caption_y="Revenue"):
    return report_charts.visual_spec({
        "type": kind, "x": caption_x, "y": caption_y,
        "aggregation": "median",
        "data": [
            {"label": "One", "value": 60540.0},
            {"label": "Two", "value": 58200.0},
            {"label": "Three", "value": 53900.0},
        ],
        "note": "Synthetic saved evidence only.", "truncated": False,
    })


def rendered_svg(spec):
    html = report_charts.html_chart(spec)
    matched = re.search(r"<svg\b.*?</svg>", html, flags=re.S)
    if not matched:
        raise AssertionError("Missing embedded saved chart SVG")
    return html, ET.fromstring(matched.group(0))


class SavedHTMLChartHeaderContracts(unittest.TestCase):
    def test_title_and_highest_axis_tick_have_distinct_y_bands(self):
        spec = fixture()
        html, svg = rendered_svg(spec)
        self.assertEqual(svg.attrib["viewBox"], "0 0 620 268")
        labels = svg.findall("text")
        heading = [e for e in labels if e.attrib.get("x") == "8"]
        tick_labels = [e for e in labels if e.attrib.get("text-anchor") == "end"]
        self.assertEqual(len(heading), 1)
        self.assertGreaterEqual(len(tick_labels), 2)
        self.assertEqual(float(heading[0].attrib["y"]), 23)
        self.assertGreaterEqual(
            min(float(t.attrib["y"]) for t in tick_labels)
              - float(heading[0].attrib["y"]), 28)
        self.assertEqual(heading[0].text, report_charts.measure_caption(spec))
        self.assertIn("Static visualization of saved aggregate values", html)

    def test_plot_height_and_original_metric_values_unchanged(self):
        for kind in ("bar", "line", "histogram"):
            with self.subTest(kind=kind):
                spec = fixture(kind)
                frozen = copy.deepcopy(spec)
                _, svg = rendered_svg(spec)
                self.assertEqual(spec, frozen)
                lines = svg.findall("line")
                grid_y = sorted(
                    float(l.attrib["y1"]) for l in lines
                    if l.attrib.get("x1") == "68.0"
                    and l.attrib.get("x2") == "605.0")
                self.assertGreaterEqual(len(grid_y), 2)
                self.assertAlmostEqual(grid_y[-1] - grid_y[0], 170.0)
                self.assertEqual([row["value"] for row in spec["data"]],
                                 [60540.0, 58200.0, 53900.0])
                self.assertEqual(svg.attrib["role"], "img")

    def test_long_measure_is_full_in_accessible_svg_title_and_caption(self):
        long_x = "synthetic_group_with_a_very_long_descriptive_business_dimension_name_for_audit"
        long_y = "revenue_amount_in_synthetic_reporting_units"
        spec = fixture(caption_x=long_x, caption_y=long_y)
        html, svg = rendered_svg(spec)
        complete = report_charts.measure_caption(spec)
        self.assertGreater(len(complete), 78)
        self.assertEqual(svg.find("title").text, complete)
        self.assertIn("<strong>" + complete + "</strong>", html)
        short = [t for t in svg.findall("text") if t.attrib.get("x") == "8"][0].text
        self.assertLessEqual(len(short), 78)
        self.assertTrue(short.endswith("…"))

    def test_untrusted_labels_are_escaped_and_cannot_become_svg_code(self):
        spec = fixture(caption_x="<script>alert(1)</script>",
                       caption_y='Sales & "Costs"')
        spec["data"][0]["label"] = "<img onerror=alert(1)>"
        html, svg = rendered_svg(spec)
        self.assertNotIn("<script>", html)
        self.assertNotIn("<img ", html)
        self.assertIn("&lt;script&gt;", html)
        self.assertIn("&lt;img", html)
        self.assertIn("&amp;", html)
        self.assertTrue(svg.find("title").text.startswith("Median"))
        self.assertEqual(len(svg.findall("script")), 0)
        self.assertEqual(len(svg.findall("image")), 0)

    def test_axis_domain_unchanged_for_mixed_negative_and_zero_values(self):
        spec = fixture()
        spec["data"] = [{"label": "Loss", "value": -8.0},
                        {"label": "Flat", "value": 0.0},
                        {"label": "Gain", "value": 12.0}]
        low, high = report_charts._domain(spec)
        self.assertEqual((low, high), (-8.0, 12.0))
        _, svg = rendered_svg(spec)
        ticks = [e.text for e in svg.findall("text")
                 if e.attrib.get("text-anchor") == "end"]
        self.assertEqual(ticks, ["-8", "0", "12"])
        self.assertEqual([p["value"] for p in spec["data"]], [-8.0, 0.0, 12.0])

    def test_ordinary_pdf_geometry_and_title_semantics_untouched(self):
        spec = fixture()
        drawing = report_charts.pdf_chart(spec, width=480)
        self.assertEqual((drawing.width, drawing.height), (480, 220))
        self.assertTrue(any(getattr(node, "text", None) ==
                            report_charts.measure_caption(spec)
                            for node in drawing.contents))
        self.assertEqual(len(spec["data"]), 3)


if __name__ == "__main__":
    unittest.main()
