"""Test/DevQA-only PDFium inspection of generated PDF bytes.

No product imports, renderer fallback, package acquisition or execution entrypoint.
Candidate extraction/geometry semantics require separate equivalence evidence.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
from pathlib import Path
from threading import RLock

_LOCK = RLock()
# Detached draft: no environment or caller flag can enable native test-tool use.
PDFIUM_TEST_EXECUTION_ENABLED = False
Box = tuple[float, float, float, float]


@dataclass(frozen=True)
class TextRegion:
    bounds: Box
    text: str


@dataclass(frozen=True)
class PageEvidence:
    text: str
    width: float
    height: float
    regions: tuple[TextRegion, ...]
    glyph_bounds: tuple[Box, ...]

    @property
    def text_bounds(self) -> tuple[Box, ...]:
        # Include all independently enumerated glyphs, not just bounded text.
        return tuple(region.bounds for region in self.regions) + self.glyph_bounds


@dataclass(frozen=True)
class RasterEvidence:
    width: int
    height: int
    rgb: bytes

    def save_png(self, path: str | Path) -> None:
        from PIL import Image
        with Image.frombytes("RGB", (self.width, self.height), self.rgb) as image:
            image.save(path, format="PNG")


def require_pdfium() -> None:
    """Keep the dependency probe real, without a fallback or auto-install."""
    if PDFIUM_TEST_EXECUTION_ENABLED is not True:
        raise RuntimeError("C5_PDFIUM_TEST_EXECUTION_DISARMED")
    from importlib.metadata import version
    if version("pypdfium2") != "5.15.2":
        raise ValueError("Unexpected PDFium test dependency version")
    with _LOCK:
        import pypdfium2  # noqa: F401


def _checked_box(box) -> Box:
    left, bottom, right, top = map(float, box)
    if not all(math.isfinite(v) for v in (left, bottom, right, top)):
        raise ValueError("Nonfinite PDF geometry")
    if right < left or top < bottom:
        raise ValueError("Inverted PDF geometry")
    return left, bottom, right, top


def _top_left(box: Box, page_box: Box) -> Box:
    left, bottom, right, top = box
    page_left, _, _, page_top = page_box
    return left - page_left, page_top - top, right - page_left, page_top - bottom


def _page_geometry(page) -> tuple[float, float, Box]:
    if page.get_rotation() != 0:
        raise ValueError("Rotated PDF inspection requires reviewed geometry mapping")
    width, height = map(float, page.get_size())
    box = _checked_box(page.get_bbox())
    if not (math.isfinite(width) and math.isfinite(height) and width > 0 and height > 0
            and math.isclose(width, box[2] - box[0], rel_tol=0, abs_tol=1e-4)
            and math.isclose(height, box[3] - box[1], rel_tol=0, abs_tol=1e-4)):
        raise ValueError("Inconsistent PDF page geometry")
    return width, height, box


def _text(textpage, box: Box) -> str:
    # Only line-ending normalization; callers retain their original whitespace,
    # exact content, ordering and page-specific predicates.
    return textpage.get_text_bounded(*box, errors="strict").replace("\r\n", "\n")


def _inspect_page(page, geometry: bool) -> PageEvidence:
    width, height, box = _page_geometry(page)
    textpage = page.get_textpage()
    try:
        glyphs = []
        envelope = list(box)
        # Full character enumeration independently of the crop/page text window.
        # Zero-area separators are not visual glyphs; finite coordinates still
        # checked. Tight bounds are used for off-page ink, with loose bounds
        # included in geometry-mode checks for the old line/block predicates.
        for index in range(textpage.count_chars()):
            tight = _checked_box(textpage.get_charbox(index))
            if tight[0] == tight[2] or tight[1] == tight[3]:
                continue
            envelope = [min(envelope[0], tight[0]), min(envelope[1], tight[1]),
                        max(envelope[2], tight[2]), max(envelope[3], tight[3])]
            if geometry:
                glyphs.append(_top_left(tight, box))
                loose = _checked_box(textpage.get_charbox(index, loose=True))
                glyphs.append(_top_left(loose, box))
        # The extent is expanded only for extraction, never for acceptance.
        left, bottom, right, top = envelope
        extracted = _text(textpage, (left - 1, bottom - 1, right + 1, top + 1))
        regions = []
        if geometry:
            for index in range(textpage.count_rects()):
                region = _checked_box(textpage.get_rect(index))
                regions.append(TextRegion(_top_left(region, box), _text(textpage, region)))
        return PageEvidence(extracted, width, height, tuple(regions), tuple(glyphs))
    finally:
        textpage.close()


def inspect_pdf(raw: bytes, *, geometry: bool = False,
                max_pages: int | None = None) -> tuple[PageEvidence, ...]:
    """Return immutable evidence; no live native handles escape the lock."""
    if not isinstance(raw, bytes) or not raw.startswith(b"%PDF"):
        raise ValueError("Expected generated PDF bytes")
    require_pdfium()
    with _LOCK:
        import pypdfium2
        document = pypdfium2.PdfDocument(raw)
        try:
            count = len(document)
            if count < 1 or (max_pages is not None and count > max_pages):
                raise ValueError("Unexpected PDF page count")
            pages = []
            for index in range(count):
                page = document[index]
                try:
                    pages.append(_inspect_page(page, geometry))
                finally:
                    page.close()
            return tuple(pages)
        finally:
            document.close()


def render_rgb(raw: bytes, index: int, *, scale: float) -> RasterEvidence:
    """Render selected generated pages to independent packed RGB bytes."""
    if not isinstance(raw, bytes) or not raw.startswith(b"%PDF"):
        raise ValueError("Expected generated PDF bytes")
    if scale not in (1.3, 1.5):
        raise ValueError("Unexpected QA raster scale")
    require_pdfium()
    with _LOCK:
        import pypdfium2
        document = pypdfium2.PdfDocument(raw)
        try:
            if not 0 <= index < len(document):
                raise ValueError("Unexpected PDF page index")
            page = document[index]
            try:
                width, height, _ = _page_geometry(page)
                bitmap = page.render(scale=scale, fill_color=(255, 255, 255, 255),
                                     rev_byteorder=True, maybe_alpha=False)
                try:
                    with bitmap.to_pil() as source:
                        with source.convert("RGB") as image:
                            expected = (math.ceil(width * scale), math.ceil(height * scale))
                            if image.size != expected:
                                raise ValueError("Unexpected raster dimensions")
                            pixels = image.tobytes()
                            if len(pixels) != expected[0] * expected[1] * 3:
                                raise ValueError("Unexpected raster byte length")
                            if all(value == 255 for value in pixels):
                                raise ValueError("Blank PDF raster")
                            return RasterEvidence(*expected, pixels)
                finally:
                    bitmap.close()
            finally:
                page.close()
        finally:
            document.close()
