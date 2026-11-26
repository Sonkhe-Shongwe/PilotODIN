"""Test/DevQA-only PDFium inspection of generated PDF bytes.

No product imports, renderer fallback, package acquisition or execution entrypoint.
Candidate extraction/geometry semantics require separate equivalence evidence.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
import re
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


_FOOTER = "PilotODIN · Verified, version-linked analytical evidence"


def has_sparse_continuation(page: PageEvidence) -> bool:
    """Keep the non-footer max-bottom < 34% page-height predicate.

    Only exclude an exact known footer line, possibly split across PDFium
    regions. Ambiguous grouping is a refusal, never a successful verdict.
    This groups geometry for the footer only; it does not reorder page text.
    """
    regions = [region for region in page.regions if region.text.strip()]
    if not regions:
        raise ValueError("Missing continuation text geometry")
    footer_band = [region for region in regions if region.bounds[1] >= page.height * 0.9]
    body = [region for region in regions if region not in footer_band]
    if footer_band:
        # PDFium can return multiple rectangles for one baseline. Join in
        # geometric order only inside this known bottom band. Never discard
        # unrelated bottom-band content or infer an incomplete footer.
        anchor = footer_band[0].bounds
        same_line = all(min(anchor[3], region.bounds[3]) >
                        max(anchor[1], region.bounds[1]) for region in footer_band)
        line = " ".join(" ".join(region.text.split()) for region in
                        sorted(footer_band, key=lambda region: region.bounds[0]))
        if line.startswith("PilotODIN") or any(
                region.text.strip().startswith(("PilotODIN", "· Verified"))
                for region in footer_band):
            if not same_line or not re.fullmatch(re.escape(_FOOTER) + r"(?: Page [1-9][0-9]*)?", line):
                raise ValueError("Ambiguous continuation footer geometry")
        else:
            body.extend(footer_band)
    if not body:
        raise ValueError("Continuation page has no nonfooter text")
    return max(region.bounds[3] for region in body) < page.height * 0.34


def _check_generated_pdf(raw: bytes) -> None:
    if not isinstance(raw, bytes) or not raw.startswith(b"%PDF"):
        raise ValueError("Expected generated PDF bytes")
    if not raw.rstrip().endswith(b"%%EOF"):
        raise ValueError("Incomplete generated PDF")
    # Scope: ordinary generated PDFs only, not a generic PDF parser. PDFium
    # does not expose UserUnit in its helpers. Reject explicit UserUnit,
    # encryption and object streams (which could conceal page dictionaries).
    # Decode PDF name escapes before checking. Conservative false refusals
    # are preferable to accepting unsupported geometry.
    for token in re.findall(rb"/([^\s<>()\[\]{}/%]+)", raw):
        name = re.sub(rb"#([0-9A-Fa-f]{2})", lambda m: bytes([int(m[1], 16)]), token)
        if name in (b"UserUnit", b"ObjStm", b"Encrypt"):
            raise ValueError("Unsupported generated PDF page transform or container")


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
    media = page.get_mediabox(fallback_ok=False)
    crop = page.get_cropbox(fallback_ok=False)
    if media is None:
        raise ValueError("Missing explicit PDF media box")
    media = _checked_box(media)
    if crop is not None and _checked_box(crop) != media:
        raise ValueError("Distinct PDF crop box requires reviewed geometry mapping")
    box = _checked_box(page.get_bbox())
    if box != media:
        raise ValueError("Unresolved PDF page box")
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
        from pypdfium2 import raw as pdfium_raw
        glyphs = []
        inventory = []
        envelope = list(box)
        for index in range(textpage.count_chars()):
            codepoint = pdfium_raw.FPDFText_GetUnicode(textpage, index)
            generated = pdfium_raw.FPDFText_IsGenerated(textpage, index)
            if not 0 < codepoint <= 0x10FFFF or generated not in (0, 1):
                raise ValueError("Unresolved PDF character inventory")
            char = chr(codepoint)
            inventory.append(char)
            # Generated whitespace has no painted geometry. A non-generated
            # zero-area glyph is only ignorable if it is mapped whitespace.
            if generated and char.isspace():
                continue
            tight = _checked_box(textpage.get_charbox(index))
            if tight[0] == tight[2] or tight[1] == tight[3]:
                if char.isspace():
                    continue
                raise ValueError("Unresolved nonseparator PDF glyph geometry")
            envelope = [min(envelope[0], tight[0]), min(envelope[1], tight[1]),
                        max(envelope[2], tight[2]), max(envelope[3], tight[3])]
            if geometry:
                glyphs.append(_top_left(tight, box))
                loose = _checked_box(textpage.get_charbox(index, loose=True))
                if loose[0] == loose[2] or loose[1] == loose[3]:
                    raise ValueError("Unresolved loose PDF glyph geometry")
                glyphs.append(_top_left(loose, box))
        left, bottom, right, top = envelope
        extracted = _text(textpage, (left - 1, bottom - 1, right + 1, top + 1))
        # Compare the independent character inventory without rewriting the
        # returned text. Combine UTF-16 surrogate pairs if supplied as units.
        original = "".join(inventory).encode("utf-16-le", "surrogatepass").decode("utf-16-le", "strict")
        visible = lambda value: "".join(char for char in value if not char.isspace())
        if visible(original) != visible(extracted):
            raise ValueError("PDF character inventory disagrees with bounded extraction")
        regions = []
        if geometry:
            for index in range(textpage.count_rects()):
                region = _checked_box(textpage.get_rect(index))
                regions.append(TextRegion(_top_left(region, box), _text(textpage, region)))
            if extracted.strip() and (not glyphs or not any(r.text.strip() for r in regions)):
                raise ValueError("Missing nonblank PDF text geometry")
        return PageEvidence(extracted, width, height, tuple(regions), tuple(glyphs))
    finally:
        textpage.close()


def inspect_pdf(raw: bytes, *, geometry: bool = False,
                max_pages: int | None = None) -> tuple[PageEvidence, ...]:
    """Return immutable evidence; no live native handles escape the lock."""
    _check_generated_pdf(raw)
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
    _check_generated_pdf(raw)
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
