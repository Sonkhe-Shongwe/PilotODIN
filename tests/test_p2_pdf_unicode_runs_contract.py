"""Synthetic P2-U2 font-run contracts. No fonts, reports, backend, or network."""
from __future__ import annotations

import math
import unittest
from backend.pdf_unicode_runs import (
    FontRun, PDFUnicodePlanError, paragraph_markup,
    plan_font_runs, position_chart_runs, validate_coverage,
)

FONT_NAMES = {"regular":"ODIN-NotoPrimary", "cjk":"ODIN-NotoCJK", "symbol":"ODIN-NotoSymbols2"}
SAMPLE = "café São Paulo R² Δ Ω Москва 漢字 ₹ 📈"
COVERAGE = {
    "regular": set(map(ord, "café São Paulo R² Δ Ω Москва ₹<x>&\"'\n0123")),
    "cjk": set(map(ord, "漢字")),
    "symbol": {ord("📈")},
}


class FontRunContracts(unittest.TestCase):
    def test_lossless_unicode_roles_and_font_precedence(self):
        runs = plan_font_runs(SAMPLE, COVERAGE)
        self.assertEqual("".join(run.text for run in runs), SAMPLE)
        self.assertEqual([r.role for r in runs if "漢" in r.text], ["cjk"])
        self.assertEqual([r.role for r in runs if "📈" in r.text], ["symbol"])
        overlap = {k: set(v) for k,v in COVERAGE.items()}
        overlap["cjk"].add(ord("c"))
        self.assertEqual(plan_font_runs("c", overlap), (FontRun("regular", "c"),))

    def test_escapes_user_markup_and_only_generates_known_font_tags(self):
        value = "<x>&\"'\n📈"
        result = paragraph_markup(plan_font_runs(value, COVERAGE), FONT_NAMES)
        self.assertIn("&lt;x&gt;&amp;&quot;&#x27;<br/>", result)
        self.assertIn("ODIN-NotoSymbols2", result)
        self.assertNotIn("<x>", result)

    def test_empty_and_lossless_newlines(self):
        self.assertEqual(plan_font_runs("", COVERAGE), ())
        self.assertEqual(paragraph_markup((), FONT_NAMES), "")
        self.assertEqual("".join(r.text for r in plan_font_runs("a\n漢", COVERAGE)), "a\n漢")

    def test_unsupported_glyph_does_not_fall_back_or_substitute(self):
        with self.assertRaisesRegex(PDFUnicodePlanError, "No approved glyph"):
            plan_font_runs("unverified glyph 🦄", COVERAGE)

    def test_rejects_shaping_and_control_sequences(self):
        for value in ("A\u200dB", "a\u0301", "📈\ufe0f", "\ud800", "\x00",
                      "\u202e", "א", "🇿🇦", "👍🏽"):
            with self.subTest(value=repr(value)), self.assertRaises(PDFUnicodePlanError):
                plan_font_runs(value, COVERAGE)

    def test_rejects_invalid_or_untrusted_role_coverage(self):
        cases = ({"regular":set()}, {"regular":set(),"cjk":set(),"symbol":{True}},
                 {"regular":set(),"cjk":set(),"symbol":{0x110000}},
                 {"regular":set(),"cjk":[],"symbol":set()})
        for case in cases:
            with self.subTest(case=str(case)), self.assertRaises(PDFUnicodePlanError):
                validate_coverage(case)

    def test_rejects_font_name_markup_injection_and_aliases(self):
        runs = plan_font_runs("c", COVERAGE)
        for wrong in ({"regular":"Bad\"/><x>","cjk":"ODIN-B","symbol":"ODIN-C"},
                      {"regular":"ODIN-Same","cjk":"ODIN-Same","symbol":"ODIN-Symbol"},
                      {"regular":"ODIN-Primary","cjk":"ODIN-CJK"}):
            with self.subTest(wrong=str(wrong)), self.assertRaises(PDFUnicodePlanError):
                paragraph_markup(runs, wrong)

    def test_rejects_oversized_text_without_mutation(self):
        with self.assertRaises(PDFUnicodePlanError):
            plan_font_runs("c"*16385, COVERAGE)

    def test_positions_mixed_font_chart_runs_from_center(self):
        runs = plan_font_runs("Δ漢📈", COVERAGE)
        result = position_chart_runs(runs, FONT_NAMES, font_size=8, max_width=100,
                                     measure=lambda text, face, pt: 10.0*len(text))
        self.assertEqual([r.x_offset for r in result], [-15, -5, 5])
        self.assertEqual([r.width for r in result], [10, 10, 10])
        self.assertEqual("".join(r.text for r in result), "Δ漢📈")

    def test_chart_end_alignment(self):
        p = position_chart_runs(plan_font_runs("Δ漢", COVERAGE), FONT_NAMES,
                                font_size=7, max_width=100,
                                measure=lambda *args: 4, anchor="end")
        self.assertEqual([x.x_offset for x in p], [-8, -4])

    def test_chart_never_silently_truncates_or_accepts_fake_width(self):
        runs = plan_font_runs("Δ漢", COVERAGE)
        with self.assertRaisesRegex(PDFUnicodePlanError, "exceed"):
            position_chart_runs(runs, FONT_NAMES, font_size=7, max_width=4,
                                measure=lambda *args: 5)
        for fake in (math.nan, math.inf, -1, "10", True):
            with self.subTest(fake=fake), self.assertRaises(PDFUnicodePlanError):
                position_chart_runs(runs, FONT_NAMES, font_size=7, max_width=100,
                                    measure=lambda *args: fake)

    def test_chart_rejects_newlines_and_invalid_geometry(self):
        with self.assertRaises(PDFUnicodePlanError):
            position_chart_runs(plan_font_runs("c\n", COVERAGE), FONT_NAMES,
                                font_size=8, max_width=100, measure=lambda *a: 4)
        for width, size in ((-1,7), (100,0), (100,math.inf)):
            with self.subTest(width=width,size=size), self.assertRaises(PDFUnicodePlanError):
                position_chart_runs(plan_font_runs("c", COVERAGE), FONT_NAMES,
                                    font_size=size, max_width=width, measure=lambda *a: 4)

    def test_no_reportlab_runtime_or_package_dependency(self):
        import backend.pdf_unicode_runs as module
        self.assertNotIn("reportlab", module.__dict__)
        self.assertNotIn("pdfmetrics", module.__dict__)


if __name__ == "__main__":
    unittest.main()
