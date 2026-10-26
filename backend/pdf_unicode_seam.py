"""Dormant, caller-supplied PDF Unicode presentation seam.

No production route enables this. No assets, downloads, font registrations,
installer or mutable project state are touched by this module. Future release
loader MUST independently pin/approve six files and register
DocumentUnicodeTTFont faces before constructing this context.

This is not an approval API. Its explicit instance is test/developer-only
until an independently approved release loader is implemented.
"""
from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping

from .pdf_unicode_runs import (
    PDFUnicodePlanError, plan_font_runs, paragraph_markup,
    position_chart_runs, validate_coverage, validate_font_names,
    ROLES,
)


@dataclass(frozen=True)
class UnicodePDFContext:
    """An explicit, pre-registered and identity-verified font context.

    A caller must supply exact font objects, their three safe names, and
    already-verified Unicode glyph coverage. A future RELEASE-specific
    factory (NOT YET IMPLEMENTED) must verify signed-off fixed SHA-256 and
    OFL assets before making this context available to a product endpoint.
    """
    font_names: Mapping[str, str]
    font_objects: Mapping[str, object]
    glyph_coverage: Mapping[str, frozenset[int]]

    def __post_init__(self):
        validate_font_names(self.font_names)
        validate_coverage(self.glyph_coverage)
        if set(self.font_objects) != set(ROLES):
            raise PDFUnicodePlanError("All three registered font roles required")
        names = dict(self.font_names)
        faces = dict(self.font_objects)
        coverage = {role: frozenset(self.glyph_coverage[role]) for role in ROLES}
        for role in ROLES:
            face = faces[role]
            if getattr(face, "fontName", None) != names[role]:
                raise PDFUnicodePlanError("Registered font name/role mismatch")
            raw = getattr(getattr(face, "face", None), "charToGlyph", None)
            if not isinstance(raw, dict):
                raise PDFUnicodePlanError("Missing actual registered glyph map")
            actual = frozenset(cp for cp, glyph in raw.items()
                               if isinstance(glyph, int) and not isinstance(glyph, bool)
                               and glyph > 0)
            if actual != coverage[role]:
                raise PDFUnicodePlanError("Glyph coverage differs from registered face")
        object.__setattr__(self, "font_names", MappingProxyType(names))
        object.__setattr__(self, "font_objects", MappingProxyType(faces))
        object.__setattr__(self, "glyph_coverage", MappingProxyType(coverage))

    def assert_ready(self) -> None:
        """Fail if another export has changed ReportLab's process font cache."""
        from reportlab.pdfbase import pdfmetrics
        for role in ROLES:
            if pdfmetrics.getFont(self.font_names[role]) is not self.font_objects[role]:
                raise PDFUnicodePlanError("Registered ReportLab font identity changed")

    @property
    def base_face(self) -> str:
        return self.font_names["regular"]

    def markup(self, text: str) -> str:
        self.assert_ready()
        return paragraph_markup(plan_font_runs(text, self.glyph_coverage), self.font_names)

    def draw_vector_text(
        self, drawing, value: str, *, x: float, y: float,
        font_size: float, max_width: float, anchor: str = "start",
        fill_color=None,
    ) -> None:
        """Emit separate measured ReportLab String runs; no silent fallback."""
        from reportlab.graphics.shapes import String
        from reportlab.pdfbase import pdfmetrics

        self.assert_ready()
        if not isinstance(value, str):
            raise PDFUnicodePlanError("Vector label must be Unicode text")
        if not value:
            return
        runs = position_chart_runs(
            plan_font_runs(value, self.glyph_coverage),
            self.font_names,
            font_size=font_size, max_width=max_width,
            anchor=anchor, measure=pdfmetrics.stringWidth,
        )
        for run in runs:
            drawing.add(String(
                x + run.x_offset, y, run.text, fontName=run.font_name,
                fontSize=font_size, textAnchor="start", fillColor=fill_color,
            ))
