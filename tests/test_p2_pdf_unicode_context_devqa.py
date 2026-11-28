"""P2-U2f pure synthetic adapter safety checks. No actual font/PDF/user data."""
from __future__ import annotations

import hashlib
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from tools import p2_pdf_unicode_context_devqa as qa
from backend.pdf_unicode_runs import PDFUnicodePlanError


def synthetic_entries(root: Path) -> list[dict]:
    items = []
    for role in qa.FONT_NAMES:
        for kind in ("font", "license"):
            name = role + (".ttf" if kind == "font" else "-OFL.txt")
            data = ("synthetic-" + role + "-" + kind).encode("ascii")
            (root / name).write_bytes(data)
            items.append({"role": role, "kind": kind, "name": name,
                          "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()})
    return items


class P2UnicodeContextDevQAContracts(unittest.TestCase):
    def test_sources_must_be_exact_six_roles_and_notices(self):
        with TemporaryDirectory(prefix="p2-u2f-") as td:
            parent = Path(td)
            entries = synthetic_entries(parent)
            sources = qa.selected_review_sources(parent, entries)
            self.assertEqual(set(sources), set(qa.FONT_NAMES))
            self.assertTrue(all(v.parent == parent for v in sources.values()))
            for invalid in (entries[:5], entries + [entries[0]],
                            [dict(entries[0], name="../escape.ttf"), *entries[1:]],
                            [dict(entries[0], bytes=1), *entries[1:]]):
                with self.subTest(count=len(invalid)), self.assertRaises(PDFUnicodePlanError):
                    qa.selected_review_sources(parent, invalid)

    def test_missing_source_blocks_before_registration(self):
        with TemporaryDirectory(prefix="p2-u2f-") as td:
            parent = Path(td)
            entries = synthetic_entries(parent)
            (parent / "symbol-OFL.txt").unlink()
            with self.assertRaises(PDFUnicodePlanError):
                qa.selected_review_sources(parent, entries)

    def test_glyph_coverage_comes_from_nonzero_registered_faces(self):
        regular = frozenset(ord(x) for x in qa.TEXT if x not in "漢字📈")
        font = lambda points: SimpleNamespace(face=SimpleNamespace(
            charToGlyph={cp: index + 1 for index, cp in enumerate(points)}))
        faces = {"regular": font(regular), "cjk": font({ord("漢"), ord("字")}),
                 "symbol": font({ord("📈")})}
        coverage = qa.verified_font_coverage(faces)
        self.assertIn(ord("📈"), coverage["symbol"])
        self.assertNotIn(ord("📈"), coverage["regular"])
        faces["symbol"].face.charToGlyph[ord("📈")] = 0
        with self.assertRaises(PDFUnicodePlanError):
            qa.verified_font_coverage(faces)

    def test_fake_or_incomplete_glyph_map_rejected(self):
        face = SimpleNamespace(face=SimpleNamespace(charToGlyph=[]))
        for fonts in ({}, {"regular": face, "cjk": face, "symbol": face}):
            with self.assertRaises(PDFUnicodePlanError):
                qa.verified_font_coverage(fonts)

    def test_font_registration_never_accepts_unreviewed_names_or_locations(self):
        with self.assertRaises(PDFUnicodePlanError):
            qa.register_scoped_faces({})
        with self.assertRaises(PDFUnicodePlanError):
            qa.register_scoped_faces({k: Path("relative.ttf") for k in qa.FONT_NAMES})

    def test_conflicting_global_reportlab_registration_is_blocked(self):
        with TemporaryDirectory(prefix="p2-u2f-") as td:
            p = Path(td) / "fake.ttf"
            p.write_bytes(b"not-an-actual-font")
            paths = {k: p for k in qa.FONT_NAMES}
            with patch("reportlab.pdfbase.pdfmetrics.getFont", return_value=object()):
                with self.assertRaisesRegex(PDFUnicodePlanError, "Conflicting"):
                    qa.register_scoped_faces(paths)

    def test_chart_measurement_only_and_lossless_label(self):
        cov = {"regular": set(map(ord, "Δ ")), "cjk": set(map(ord, "漢字")),
               "symbol": {ord("📈")}}
        from backend.pdf_unicode_runs import plan_font_runs, position_chart_runs
        runs = position_chart_runs(plan_font_runs(qa.CHART_LABEL, cov), qa.FONT_NAMES,
                                   font_size=11, max_width=390,
                                   measure=lambda s, n, pt: len(s) * 6)
        self.assertEqual("".join(x.text for x in runs), qa.CHART_LABEL)
        self.assertAlmostEqual(runs[0].x_offset, -len(qa.CHART_LABEL) * 3)

    def test_synthetic_pdf_guard_rejects_missing_or_oversized(self):
        for raw in (b"", b"something-other-than-a-pdf", "not bytes",
                    b"x" * (qa.MAX_PDF_BYTES + 1)):
            with self.subTest(length=len(raw)):
                with self.assertRaises(Exception):
                    qa.inspect_synthetic_pdf_bytes(raw)

    def test_entrypoint_default_blocks_on_non_windows_without_writes(self):
        with patch.object(qa.sys, "platform", "linux"), \
             patch.object(qa, "verified_review_files") as guard, \
             patch("builtins.print"):
            self.assertEqual(qa.main(), 2)
            guard.assert_not_called()

    def test_production_renderer_and_files_are_not_imported_by_adapter(self):
        for name in ("reports", "report_charts", "desktop_runner", "fitz", "requests"):
            self.assertNotIn(name, qa.__dict__)
        self.assertEqual(qa.TEXT, "café São Paulo R² Δ Ω Москва 漢字 ₹ 📈")


if __name__ == "__main__":
    unittest.main()
