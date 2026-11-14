"""P2 regression: a saved chart count must identify its actual denominator.

These are direct tests of the production HTML/PDF chart presentation functions
using disposable, in-memory aggregate fixtures. They do not open project data,
approve release fonts, initialise SQLite, or generate a distributable PDF.
"""
from __future__ import annotations

import copy
from html import unescape
import re
import unittest
from xml.etree import ElementTree as ET

from backend import report_charts


def saved_spec(kind="bar", *, y="TransactionsInLastHour", aggregation="count"):
    chart = {
        "type": kind, "x": "Device", "y": y,
        "aggregation": aggregation,
        "data": [
            {"label": "Mobile", "value": 91.0},
            {"label": "Desktop", "value": 53.0},
            {"label": "Tablet", "value": 6.0},
        ],
        "note": "Synthetic totals; any missing Y values are not counted.",
    }
    return chart, report_charts.visual_spec(chart)


class P2SavedChartCountSemantics(unittest.TestCase):
    def test_selected_y_is_not_mislabelled_as_all_record_count(self):
        source, spec = saved_spec()
        original = copy.deepcopy(source)
        expected = "Count of non-missing TransactionsInLastHour by Device"
        self.assertEqual(report_charts.measure_caption(spec), expected)
        self.assertEqual(source, original)
        self.assertEqual([item["value"] for item in spec["data"]],
                         [91.0, 53.0, 6.0])

    def test_html_report_svg_title_and_caption_both_explain_count(self):
        _, spec = saved_spec()
        html = report_charts.html_chart(spec)
        matched = re.search(r"<svg\b.*?</svg>", html, flags=re.S)
        self.assertIsNotNone(matched)
        svg = ET.fromstring(matched.group(0))
        expected = report_charts.measure_caption(spec)
        self.assertEqual(svg.find("title").text, expected)
        self.assertIn("<strong>" + expected + "</strong>", html)
        self.assertIn("any missing Y values are not counted", unescape(html))
        self.assertNotIn("Record count by Device", html)

    def test_pdf_vector_chart_uses_same_denominator_caption(self):
        _, spec = saved_spec()
        drawing = report_charts.pdf_chart(spec, width=480)
        expected = report_charts.measure_caption(spec)
        self.assertEqual((drawing.width, drawing.height), (480, 220))
        self.assertIn(expected, [getattr(item, "text", None)
                                  for item in drawing.contents])
        self.assertEqual(len(spec["data"]), 3)

    def test_no_y_means_records_are_counted(self):
        _, spec = saved_spec(y="")
        self.assertEqual(report_charts.measure_caption(spec),
                         "Record count by Device")
        self.assertIn("Record count by Device",
                      report_charts.html_chart(spec))

    def test_existing_median_and_histogram_captions_unchanged(self):
        _, median = saved_spec(y="Revenue", aggregation="median")
        self.assertEqual(report_charts.measure_caption(median),
                         "Median of Revenue by Device")
        _, histogram = saved_spec("histogram", y="", aggregation="count")
        self.assertEqual(report_charts.measure_caption(histogram),
                         "Frequency distribution of Device")

    def test_untrusted_measure_is_escaped_not_inserted_as_html(self):
        _, spec = saved_spec(y="<script>alert(1)</script>")
        html = report_charts.html_chart(spec)
        self.assertIn("&lt;script&gt;", html)
        self.assertNotIn("<script>", html)


if __name__ == "__main__":
    unittest.main()
