"""Document-scoped supplementary-plane ToUnicode repair for ReportLab TTFont.

This small module is not yet wired into PilotODIN's PDF renderer. It prevents
incorrect copy/search text for Unicode scalars > U+FFFF when ReportLab emits
those values as 5-6 hex digits instead of UTF-16BE surrogate pairs.

No process-wide ReportLab monkeypatch, PDF rewrite, font installation, data
access, or network request. The caller must supply a licensed, verified TTF
and fail closed on ReportLab's process-global dynamic-font alias behavior.
"""
from __future__ import annotations

import re

from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

# ReportLab-generated bfchar entries encode an 8-bit subset index as <HH>.
_BFCHAR_ENTRY = re.compile(
    r"^(?P<prefix>[ \t]*<[0-9a-fA-F]{2}>[ \t]+)<(?P<value>[0-9a-fA-F]{4,8})>"
    r"(?P<suffix>[ \t]*)$"
)


def repair_reportlab_tounicode(cmap: str) -> tuple[str, int]:
    """Return (same-format CMap, count of repaired astral destinations).

    Only inspect explicit bfchar mappings in a ReportLab-generated CMap.
    All other lines and existing four/eight-digit destinations are preserved.
    Reject malformed bfchar content, invalid surrogate scalars and unfinished
    sections instead of accidentally changing some unrelated PDF structure.
    """
    if not isinstance(cmap, str) or len(cmap) > 512_000:
        raise ValueError("Invalid or oversized ReportLab Unicode CMap")
    in_bfchar = False
    bfchar_seen = False
    changed = 0
    lines = []
    for line in cmap.splitlines(keepends=True):
        content = line.rstrip("\r\n")
        ending = line[len(content):]
        if content.strip().endswith("beginbfchar"):
            if in_bfchar:
                raise ValueError("Nested bfchar section")
            in_bfchar = True
            bfchar_seen = True
        elif content.strip() == "endbfchar":
            if not in_bfchar:
                raise ValueError("Unexpected bfchar end")
            in_bfchar = False
        elif in_bfchar:
            match = _BFCHAR_ENTRY.fullmatch(content)
            if not match:
                raise ValueError("Unexpected ReportLab bfchar mapping")
            value = match["value"]
            if len(value) in (5, 6):
                scalar = int(value, 16)
                if not 0x10000 <= scalar <= 0x10FFFF:
                    raise ValueError("Invalid supplementary Unicode scalar")
                encoded = chr(scalar).encode("utf-16-be").hex().upper()
                content = match["prefix"] + "<" + encoded + ">" + match["suffix"]
                changed += 1
            elif len(value) == 4:
                scalar = int(value, 16)
                if 0xD800 <= scalar <= 0xDFFF:
                    raise ValueError("Unpaired UTF-16 surrogate")
            elif len(value) == 8:
                try:
                    bytes.fromhex(value).decode("utf-16-be", errors="strict")
                except UnicodeError as exc:
                    raise ValueError("Invalid existing UTF-16BE destination") from exc
        lines.append(content + ending)
    if in_bfchar or not bfchar_seen:
        raise ValueError("Incomplete ReportLab bfchar section")
    return "".join(lines), changed


class DocumentUnicodeTTFont(TTFont):
    """Correct only this font's new ToUnicode streams in the supplied document."""

    def addObjects(self, doc):
        before = set(doc.idToObject)
        super().addObjects(doc)
        cmaps = [
            obj for key, obj in doc.idToObject.items()
            if key not in before and
            isinstance(key, str) and key.startswith("toUnicodeCMap:")
        ]
        if not cmaps:
            raise ValueError("Missing newly generated font ToUnicode streams")
        # Prepare all mappings first: one malformed stream must not silently
        # leave the document with a partial repair.
        repaired = []
        for stream in cmaps:
            corrected, _count = repair_reportlab_tounicode(stream.content)
            repaired.append((stream, corrected))
        for stream, content in repaired:
            stream.content = content


def register_document_unicode_font(font: DocumentUnicodeTTFont):
    """Fail if ReportLab aliases our font to an earlier ordinary TTFont.

    ReportLab's process-global dynamic-font registry keys by internal face
    name, not just the requested external font name. Registering an ordinary
    font first can silently shadow a later subclass. This check rejects that
    situation rather than claiming the repair has been activated.
    """
    if not isinstance(font, DocumentUnicodeTTFont):
        raise TypeError("Expected DocumentUnicodeTTFont instance")
    pdfmetrics.registerFont(font)
    if pdfmetrics.getFont(font.fontName) is not font:
        raise RuntimeError("Conflicting earlier ReportLab dynamic font registration")
    return font
