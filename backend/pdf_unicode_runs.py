"""P2-U2 planning-only, source-safe PDF Unicode font-run contracts.

DORMANT: not imported by production reports/charts or the installer. This
module does NOT load or approve font files, register ReportLab fonts, render
PDFs, perform glyph shaping, or authorize distribution. Actual coverage must
later come from independently approved immutable font sources. No implicit OS
fallback, replacements, normalization, network, or global registry changes.
"""
from __future__ import annotations

from dataclasses import dataclass
from html import escape
import math
import re
import unicodedata
from typing import AbstractSet, Callable, Mapping, Sequence

ROLES = ("regular", "cjk", "symbol")
MAX_TEXT_CHARACTERS = 16_384
MAX_GLYPHS_PER_ROLE = 150_000
_FONT_NAME = re.compile(r"ODIN-[A-Za-z0-9_-]{1,48}\Z")


class PDFUnicodePlanError(ValueError):
    """A generic, non-disclosing error for unverified PDF text presentation."""


@dataclass(frozen=True)
class FontRun:
    role: str
    text: str


@dataclass(frozen=True)
class PositionedFontRun:
    role: str
    text: str
    font_name: str
    x_offset: float
    width: float


def validate_coverage(coverage: Mapping[str, AbstractSet[int]]) -> None:
    """Require explicit role coverage, NEVER infer it from user/OS font names."""
    if not isinstance(coverage, Mapping) or set(coverage) != set(ROLES):
        raise PDFUnicodePlanError("Exact three-role glyph coverage required")
    for role in ROLES:
        points = coverage[role]
        if not isinstance(points, (set, frozenset)) or len(points) > MAX_GLYPHS_PER_ROLE:
            raise PDFUnicodePlanError("Invalid or oversized role glyph coverage")
        if any(not isinstance(cp, int) or isinstance(cp, bool) or
               not 0 <= cp <= 0x10FFFF or 0xD800 <= cp <= 0xDFFF
               for cp in points):
            raise PDFUnicodePlanError("Invalid role glyph scalar")


def _bounded_text(value: str) -> None:
    if not isinstance(value, str) or len(value) > MAX_TEXT_CHARACTERS:
        raise PDFUnicodePlanError("Invalid or excessive PDF text")
    for ch in value:
        codepoint = ord(ch)
        category = unicodedata.category(ch)
        # Shape-dependent sequences and bidi need a separately reviewed engine.
        if (0xD800 <= codepoint <= 0xDFFF or
                0xFE00 <= codepoint <= 0xFE0F or
                0xE0100 <= codepoint <= 0xE01EF or
                0x1F1E6 <= codepoint <= 0x1F1FF or
                0x1F3FB <= codepoint <= 0x1F3FF or
                ch == "\u200d" or category.startswith("M") or
                unicodedata.bidirectional(ch) in ("R", "AL", "AN") or
                (category.startswith("C") and ch != "\n")):
            raise PDFUnicodePlanError("Text needs unsupported shaping or control policy")


def plan_font_runs(value: str, coverage: Mapping[str, AbstractSet[int]]) -> tuple[FontRun, ...]:
    """Lossless runs from VERIFIED-ELSEWHERE glyph coverage; never substitute.

    Role precedence is regular, then CJK, then symbol. This is not a visual
    acceptance claim or a complete grapheme-shaping engine.
    """
    _bounded_text(value)
    validate_coverage(coverage)
    if not value:
        return ()
    result: list[FontRun] = []
    role: str | None = None
    chars: list[str] = []
    for ch in value:
        selected = ("regular" if ch == "\n" else
                    next((candidate for candidate in ROLES
                          if ord(ch) in coverage[candidate]), None))
        if selected is None:
            raise PDFUnicodePlanError("No approved glyph for requested text")
        if role is not None and selected != role:
            result.append(FontRun(role, "".join(chars)))
            chars.clear()
        role = selected
        chars.append(ch)
    if chars:
        result.append(FontRun(role, "".join(chars)))
    if "".join(run.text for run in result) != value:
        raise PDFUnicodePlanError("Lossless font-run invariant failed")
    return tuple(result)


def validate_font_names(font_names: Mapping[str, str]) -> None:
    if not isinstance(font_names, Mapping) or set(font_names) != set(ROLES):
        raise PDFUnicodePlanError("All three verified registered font names required")
    if (any(not isinstance(font_names[role], str) or
            _FONT_NAME.fullmatch(font_names[role]) is None for role in ROLES) or
            len(set(font_names.values())) != 3):
        raise PDFUnicodePlanError("Unsafe or conflicting font registration names")


def paragraph_markup(runs: Sequence[FontRun], font_names: Mapping[str, str]) -> str:
    """Generate safe ReportLab paragraph markup without interpreting input HTML."""
    validate_font_names(font_names)
    if not isinstance(runs, (tuple, list)):
        raise PDFUnicodePlanError("Invalid font-run sequence")
    raw = "".join(run.text for run in runs if isinstance(run, FontRun))
    if len(raw) > MAX_TEXT_CHARACTERS or len(runs) > MAX_TEXT_CHARACTERS or len(raw) != sum(
            len(run.text) for run in runs if isinstance(run, FontRun)):
        raise PDFUnicodePlanError("Invalid or excessive font-run content")
    _bounded_text(raw)
    fragments: list[str] = []
    for run in runs:
        if not isinstance(run, FontRun) or run.role not in ROLES or not run.text:
            raise PDFUnicodePlanError("Malformed font run")
        safe = escape(run.text, quote=True).replace("\n", "<br/>")
        fragments.append(f'<font name="{font_names[run.role]}">{safe}</font>')
    return "".join(fragments)


def position_chart_runs(
    runs: Sequence[FontRun], font_names: Mapping[str, str],
    *, font_size: float, max_width: float,
    measure: Callable[[str, str, float], float], anchor: str = "middle",
) -> tuple[PositionedFontRun, ...]:
    """Measure chart text runs without clipping/truncation or changing values.

    x_offset is relative to the original chart anchor, not the drawing origin.
    Callers later draw each run in its own font; unverified overflow fails.
    """
    validate_font_names(font_names)
    if (anchor not in ("start", "middle", "end") or
            not callable(measure) or
            not isinstance(font_size, (int, float)) or isinstance(font_size, bool) or
            not isinstance(max_width, (int, float)) or isinstance(max_width, bool) or
            not math.isfinite(font_size) or not math.isfinite(max_width) or
            not 0 < font_size <= 72 or not 0 < max_width <= 5000):
        raise PDFUnicodePlanError("Invalid chart presentation measurements")
    if not isinstance(runs, (tuple, list)) or len(runs) > MAX_TEXT_CHARACTERS:
        raise PDFUnicodePlanError("Invalid bounded chart-run list")
    result: list[PositionedFontRun] = []
    total = 0.0
    for run in runs:
        if (not isinstance(run, FontRun) or run.role not in ROLES or
                not run.text or "\n" in run.text):
            raise PDFUnicodePlanError("Invalid chart glyph run")
        _bounded_text(run.text)
        width = measure(run.text, font_names[run.role], float(font_size))
        if (not isinstance(width, (int, float)) or isinstance(width, bool) or
                not math.isfinite(width) or width < 0):
            raise PDFUnicodePlanError("Unreliable chart glyph measurement")
        result.append(PositionedFontRun(run.role, run.text, font_names[run.role], total, float(width)))
        total += width
        if not math.isfinite(total) or total > max_width:
            raise PDFUnicodePlanError("Chart glyph runs exceed safe drawing width")
    offset = -total / 2 if anchor == "middle" else (-total if anchor == "end" else 0)
    return tuple(PositionedFontRun(r.role, r.text, r.font_name, r.x_offset + offset, r.width)
                 for r in result)
