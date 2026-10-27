"""Release-gated, offline font loader for the REAL report PDF export route.

The release approval state and six exact hashes are deliberately UNSET.
Neither user input, a local receipt, an environment variable nor a font
installed on Windows can grant release approval. Normal exports remain on
the existing legacy PDF path until a reviewed source commit supplies all
release identities, complete OFL notices and a recorded approval reference.

The real Unicode path is serialized per process because ReportLab's dynamic
font registry is process-global. This is not yet concurrency/release approval.
No fonts are copied, installed, downloaded or otherwise shipped by this file.
"""
from __future__ import annotations

import re
from threading import RLock
from typing import Callable

try:
    from .pdf_font_resources import PDFResourceError, verify_pdf_font_files
    from .pdf_unicode_seam import UnicodePDFContext
except ImportError:  # The original desktop_runner also supports direct backend imports.
    from pdf_font_resources import PDFResourceError, verify_pdf_font_files
    from pdf_unicode_seam import UnicodePDFContext

# THESE ARE REVIEW GATES, NOT USER CONFIGURATION FLAGS.
# NEVER substitute the existing mutable DevQA source receipt for these pins.
RELEASE_APPROVAL_STATUS = "NOT_GRANTED"
RELEASE_APPROVAL_REFERENCE = ""
# Immutable code-pinned rows only AFTER independent face/OFL/redistribution approval:
# (role, kind, exact_basename, exact_size_bytes, lowercase_sha256)
RELEASE_PINNED_FILES: tuple[tuple[str, str, str, int, str], ...] = ()

_FONT_NAMES = {
    "regular": "ODIN-Release-NotoSans",
    "cjk": "ODIN-Release-NotoSC",
    "symbol": "ODIN-Release-NotoSymbols",
}
_ROLES = ("regular", "cjk", "symbol")
_HEX64 = re.compile(r"[0-9a-f]{64}\Z")
_APPROVAL_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._/-]{7,127}\Z")
_LOCK = RLock()
_CONTEXT: UnicodePDFContext | None = None
_CONTEXT_POLICY: tuple | None = None


class PDFReleaseFontError(ValueError):
    """Safe error: never include local font paths, glyphs, private user data."""


def _approved_records() -> list[dict]:
    """Fail closed for any partial, malformed or unofficial release decision."""
    if RELEASE_APPROVAL_STATUS != "GRANTED_BY_INDEPENDENT_OWNER_REVIEW":
        raise PDFReleaseFontError("Release font approval absent")
    if (not isinstance(RELEASE_APPROVAL_REFERENCE, str) or
            not _APPROVAL_ID.fullmatch(RELEASE_APPROVAL_REFERENCE)):
        raise PDFReleaseFontError("Independent release approval reference absent")
    if not isinstance(RELEASE_PINNED_FILES, tuple) or len(RELEASE_PINNED_FILES) != 6:
        raise PDFReleaseFontError("Six immutable font and licence pins required")
    entries = []
    pairs = set()
    filenames = set()
    for item in RELEASE_PINNED_FILES:
        if not isinstance(item, tuple) or len(item) != 5:
            raise PDFReleaseFontError("Malformed approved font identity")
        role, kind, name, size, digest = item
        if (role not in _ROLES or kind not in ("font", "license") or
                (role, kind) in pairs or
                not isinstance(name, str) or name in filenames or
                not isinstance(size, int) or isinstance(size, bool) or size <= 0 or
                not isinstance(digest, str) or not _HEX64.fullmatch(digest)):
            raise PDFReleaseFontError("Invalid or duplicate approved font identity")
        pairs.add((role, kind))
        filenames.add(name)
        entries.append({"role": role, "kind": kind,
                        "name": name, "bytes": size, "sha256": digest})
    if pairs != {(r, kind) for r in _ROLES for kind in ("font", "license")}:
        raise PDFReleaseFontError("Incomplete approved font and OFL set")
    return entries


def release_pdf_enabled() -> bool:
    """Source-only gate; never enable from HTTP, process env or DevQA receipt."""
    return RELEASE_APPROVAL_STATUS == "GRANTED_BY_INDEPENDENT_OWNER_REVIEW"


def _verified_context() -> UnicodePDFContext:
    """Requires caller's RLock; reverify all six immutable files EACH export."""
    global _CONTEXT, _CONTEXT_POLICY

    entries = _approved_records()
    try:
        # With no explicit root override this checks ONLY backend/assets/pdf_fonts
        # resolved beside backend/pdf_font_resources.py (including in PyInstaller).
        sources = verify_pdf_font_files(entries)
    except (PDFResourceError, OSError, ValueError) as exc:
        # The release endpoint must never leak extracted local asset paths.
        raise PDFReleaseFontError("Missing or altered approved PDF font resources") from exc

    policy = (RELEASE_APPROVAL_REFERENCE, RELEASE_PINNED_FILES)
    if _CONTEXT is not None and _CONTEXT_POLICY == policy:
        try:
            _CONTEXT.assert_ready()
        except Exception as exc:
            raise PDFReleaseFontError("ReportLab registration changed") from exc
        return _CONTEXT

    # This branch can run ONLY with approved, code-pinned release identities.
    from reportlab.pdfbase import pdfmetrics
    try:
        from .pdf_unicode_cmap import (
            DocumentUnicodeTTFont, register_document_unicode_font,
        )
    except ImportError:
        from pdf_unicode_cmap import (
            DocumentUnicodeTTFont, register_document_unicode_font,
        )

    registered = {}
    try:
        for role in _ROLES:
            name = _FONT_NAMES[role]
            try:
                pdfmetrics.getFont(name)
            except KeyError:
                pass
            else:
                raise PDFReleaseFontError("Conflicting existing font registration")
            obj = register_document_unicode_font(
                DocumentUnicodeTTFont(name, str(sources[role + "_font"]))
            )
            if pdfmetrics.getFont(name) is not obj:
                raise PDFReleaseFontError("Mismatched ReportLab font identity")
            registered[role] = obj

        coverage = {}
        for role, obj in registered.items():
            charmap = getattr(getattr(obj, "face", None), "charToGlyph", None)
            if not isinstance(charmap, dict):
                raise PDFReleaseFontError("Missing verified TrueType glyph coverage")
            coverage[role] = frozenset(
                cp for cp, glyph in charmap.items()
                if isinstance(cp, int) and not isinstance(cp, bool)
                and isinstance(glyph, int) and not isinstance(glyph, bool)
                and glyph > 0
            )
        context = UnicodePDFContext(_FONT_NAMES, registered, coverage)
        context.assert_ready()
    except PDFReleaseFontError:
        raise
    except Exception as exc:
        raise PDFReleaseFontError("Approved PDF font registration failed") from exc

    _CONTEXT = context
    _CONTEXT_POLICY = policy
    return context


def render_export_pdf(report: dict, renderer: Callable) -> bytes:
    """Single point of integration for the authenticated PDF export endpoint.

    Prior to release approval the existing render_pdf(report) runs unchanged.
    AFTER approval, invalid/missing fonts must FAIL, never silently fall back
    to Helvetica or a less capable export. The lock covers the entire render
    to isolate dynamic glyph assignment and ReportLab font registration.
    """
    if not release_pdf_enabled():
        return renderer(report)
    with _LOCK:
        context = _verified_context()
        try:
            return renderer(report, unicode_context=context)
        except PDFReleaseFontError:
            raise
        except Exception as exc:
            raise PDFReleaseFontError("Verified Unicode PDF export failed") from exc
