"""Focused, self-contained P2 Unicode renderer seam tests.

No font binaries, mutable project DB, network or installer. Production routes
MUST continue to call render_pdf(report) with no context; these unit tests use
registered-face stand-ins and check only changed presentation boundaries.
"""
from __future__ import annotations

from types import SimpleNamespace
import unittest
from unittest.mock import patch

from backend.pdf_unicode_runs import PDFUnicodePlanError
from backend.pdf_unicode_seam import UnicodePDFContext
from backend import report_charts

NAMES = {
    "regular": "ODIN-Scoped-Regular",
    "cjk": "ODIN-Scoped-CJK",
    "symbol": "ODIN-Scoped-Symbol",
}
SCALAR = set(ord(c) for c in (
    "ABCDReport CategoryGroup Count of records by Values 0123456789.-"
    "Δ Ω ₹ <>&'\" café São Paulo R² Москва:"
))
CJK = {ord("漢"), ord("字")}
SYMBOLS = {ord("📈")}
COVERAGE = {"regular": frozenset(SCALAR),
            "cjk": frozenset(CJK),
            "symbol": frozenset(SYMBOLS)}


def context():
    fonts = {role: SimpleNamespace(
        fontName=name,
        face=SimpleNamespace(charToGlyph={
            cp: (n + 1) for n, cp in enumerate(sorted(COVERAGE[role]))
        })) for role, name in NAMES.items()}
    return UnicodePDFContext(NAMES, fonts, COVERAGE)


class P2UnicodeRendererSeamContracts(unittest.TestCase):
    def registry(self, ctx):
        return patch("reportlab.pdfbase.pdfmetrics.getFont",
                     side_effect=lambda name: ctx.font_objects[
                         next(k for k, v in NAMES.items() if v == name)])

    def test_explicit_context_retains_exact_registered_glyph_map(self):
        ctx = context()
        self.assertEqual(set(ctx.font_names), {"regular", "cjk", "symbol"})
        with self.registry(ctx):
            self.assertEqual(ctx.base_face, NAMES["regular"])
            ctx.assert_ready()

    def test_missing_glyph_or_name_identity_never_registers(self):
        valid = context()
        with self.assertRaises(PDFUnicodePlanError):
            UnicodePDFContext(NAMES, valid.font_objects,
                              {**COVERAGE, "symbol": frozenset()})
        with self.assertRaises(PDFUnicodePlanError):
            UnicodePDFContext({**NAMES, "symbol": "ODIN-Wrong"},
                              valid.font_objects, COVERAGE)

    def test_registry_aliasing_fails_closed(self):
        ctx = context()
        with patch("reportlab.pdfbase.pdfmetrics.getFont", return_value=object()):
            with self.assertRaises(PDFUnicodePlanError):
                ctx.markup("A 漢 📈")

    def test_markup_preserves_unicode_and_escapes_source_tags(self):
        ctx = context()
        with self.registry(ctx):
            result = ctx.markup("<A>& 漢 📈")
        self.assertIn("&lt;A&gt;&amp;", result)
        self.assertIn(NAMES["cjk"], result)
        self.assertIn(NAMES["symbol"], result)
        self.assertNotIn("<A>", result)

    def test_unverified_complex_sequences_are_rejected_not_substituted(self):
        ctx = context()
        with self.registry(ctx):
            for value in ("A\u200dB", "a\u0301", "🇿🇦", "🦄"):
                with self.subTest(value=repr(value)):
                    with self.assertRaises(PDFUnicodePlanError):
                        ctx.markup(value)

    def test_vector_label_creates_measured_centered_glyph_runs(self):
        from reportlab.graphics.shapes import Drawing, String
        ctx = context()
        d = Drawing(200, 45)
        with self.registry(ctx), patch(
            "reportlab.pdfbase.pdfmetrics.stringWidth",
            side_effect=lambda text, name, size: len(text) * 6):
            ctx.draw_vector_text(d, "Δ 漢 📈", x=100, y=15, font_size=11,
                                 max_width=120, anchor="middle")
        strings = [v for v in d.contents if isinstance(v, String)]
        self.assertEqual("".join(x.text for x in strings), "Δ 漢 📈")
        self.assertAlmostEqual(strings[0].x, 100 - 6*len("Δ 漢 📈")/2)
        self.assertTrue(all(x.textAnchor == "start" for x in strings))

    def test_vector_overflow_fails_before_any_shapes_are_added(self):
        from reportlab.graphics.shapes import Drawing
        ctx = context()
        d = Drawing(120, 30)
        with self.registry(ctx), patch(
            "reportlab.pdfbase.pdfmetrics.stringWidth", return_value=40):
            with self.assertRaises(PDFUnicodePlanError):
                ctx.draw_vector_text(d, "Δ 漢 📈", x=40, y=12,
                                     font_size=11, max_width=50)
        self.assertEqual(len(d.contents), 0)

    def test_actual_chart_uses_opt_in_font_runs_without_touching_aggregates(self):
        from reportlab.graphics.shapes import String
        spec = {"type": "bar", "x": "Category", "y": "",
                "aggregation": "count", "data": [
                    {"label": "漢", "value": 20.0},
                    {"label": "📈", "value": 10.0}],
                "limited": False, "note": ""}
        original = [(v["label"], v["value"]) for v in spec["data"]]
        legacy = report_charts.pdf_chart(spec, 500)
        ctx = context()
        with self.registry(ctx), patch(
            "reportlab.pdfbase.pdfmetrics.stringWidth",
            side_effect=lambda text, name, size: len(text)*4):
            enriched = report_charts.pdf_chart(spec, 500, unicode_context=ctx)
        self.assertEqual(original, [(v["label"], v["value"]) for v in spec["data"]])
        self.assertEqual((legacy.width, legacy.height),
                         (enriched.width, enriched.height))
        collected = [x.text for x in enriched.contents if isinstance(x, String)]
        self.assertIn("漢", collected)
        self.assertIn("📈", collected)

    def test_chart_refuses_unverified_non_context_objects(self):
        spec = {"type": "bar", "x": "Category", "y": "",
                "aggregation": "count", "data": [{"label": "A", "value": 2}],
                "limited": False, "note": ""}
        with self.assertRaises(ValueError):
            report_charts.pdf_chart(spec, unicode_context=object())

    def test_legacy_chart_keeps_scalar_data_and_text(self):
        from reportlab.graphics.shapes import String
        spec = {"type": "bar", "x": "Category", "y": "",
                "aggregation": "count", "data": [
                    {"label": "A", "value": 5.0},
                    {"label": "B", "value": 2.0}],
                "limited": False, "note": ""}
        old = report_charts.pdf_chart(spec, 500)
        self.assertEqual(old.width, 500)
        text = [v.text for v in old.contents if isinstance(v, String)]
        self.assertIn("A", text)
        self.assertIn("B", text)
        self.assertEqual(report_charts.measure_caption(spec), "Count of records by Category")


if __name__ == "__main__":
    unittest.main()
