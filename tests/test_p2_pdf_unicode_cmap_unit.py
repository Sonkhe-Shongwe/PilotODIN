"""Pure P2 ToUnicode correction contracts, no font binaries or user data.

The production renderer is intentionally NOT connected to the new helper.
These tests cover deterministic CMap parsing and the ReportLab alias hazard.
"""
from __future__ import annotations

from types import SimpleNamespace
import unittest
from unittest.mock import patch

from backend.pdf_unicode_cmap import (
    DocumentUnicodeTTFont, register_document_unicode_font,
    repair_reportlab_tounicode,
)

C_MAP = (
    "/CIDInit /ProcSet findresource begin\n"
    "3 beginbfchar\n"
    "<00> <0041>\n"
    "<01> <1F4C8>\n"
    "<02> <6F22>\n"
    "endbfchar\n"
    "endcmap\n"
)


class P2DocumentUnicodeContracts(unittest.TestCase):
    def test_astral_scalar_utf16be_while_bmp_remains_unchanged(self):
        fixed, count = repair_reportlab_tounicode(C_MAP)
        self.assertEqual(count, 1)
        self.assertEqual(
            fixed,
            C_MAP.replace("<01> <1F4C8>", "<01> <D83DDCC8>"))
        self.assertIn("<00> <0041>", fixed)
        self.assertIn("<02> <6F22>", fixed)

    def test_repeat_repair_is_idempotent(self):
        fixed, _ = repair_reportlab_tounicode(C_MAP)
        second, count = repair_reportlab_tounicode(fixed)
        self.assertEqual(second, fixed)
        self.assertEqual(count, 0)

    def test_reject_unpaired_surrogate_and_beyond_unicode(self):
        for value in ("<D800>", "<DFFF>", "<110000>", "<D8000000>"):
            with self.subTest(value=value):
                bad = C_MAP.replace("<01> <1F4C8>", "<01> " + value)
                with self.assertRaises(ValueError):
                    repair_reportlab_tounicode(bad)

    def test_reject_malformed_and_oversized_cmap(self):
        for value in (C_MAP.replace("endbfchar", ""),
                      C_MAP.replace("<01> <1F4C8>", "<01>"),
                      "A" * 512001,
                      5):
            with self.subTest(form=str(value)[:45]):
                with self.assertRaises(ValueError):
                    repair_reportlab_tounicode(value)

    def test_nonmatching_cmap_stream_text_preserved(self):
        sample = C_MAP.replace("\n", "\r\n")
        repaired, count = repair_reportlab_tounicode(sample)
        self.assertEqual(count, 1)
        self.assertEqual(repaired.count("\r\n"), sample.count("\r\n"))

    def test_one_font_only_patches_new_document_streams(self):
        old = SimpleNamespace(content=C_MAP)
        changed = SimpleNamespace(content=C_MAP)
        document = SimpleNamespace(idToObject={"toUnicodeCMap:OLD": old})
        def original(_font, doc):
            doc.idToObject["toUnicodeCMap:NEW"] = changed
        font = DocumentUnicodeTTFont.__new__(DocumentUnicodeTTFont)
        with patch("reportlab.pdfbase.ttfonts.TTFont.addObjects", original):
            font.addObjects(document)
        self.assertEqual(old.content, C_MAP)
        self.assertIn("<D83DDCC8>", changed.content)

    def test_repair_is_all_or_nothing_across_subsets(self):
        first = SimpleNamespace(content=C_MAP)
        second = SimpleNamespace(content=C_MAP.replace("endbfchar", ""))
        doc = SimpleNamespace(idToObject={})
        def original(_font, document):
            document.idToObject["toUnicodeCMap:A"] = first
            document.idToObject["toUnicodeCMap:B"] = second
        font = DocumentUnicodeTTFont.__new__(DocumentUnicodeTTFont)
        with patch("reportlab.pdfbase.ttfonts.TTFont.addObjects", original):
            with self.assertRaises(ValueError):
                font.addObjects(doc)
        self.assertEqual(first.content, C_MAP)

    def test_registry_alias_is_rejected_not_silent(self):
        obj = DocumentUnicodeTTFont.__new__(DocumentUnicodeTTFont)
        obj.fontName = "ODIN-TEST-ALIAS"
        with patch("backend.pdf_unicode_cmap.pdfmetrics.registerFont"), \
             patch("backend.pdf_unicode_cmap.pdfmetrics.getFont",
                   return_value=object()):
            with self.assertRaisesRegex(RuntimeError, "Conflicting"):
                register_document_unicode_font(obj)

    def test_registration_requires_safe_font_type(self):
        with self.assertRaises(TypeError):
            register_document_unicode_font(object())


if __name__ == "__main__":
    unittest.main()
