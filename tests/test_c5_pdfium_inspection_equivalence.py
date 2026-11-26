"""Independent generated PDFium candidate fixtures; not run in detached draft.

The exact candidate must be separately authorised before this suite is executed.
No owner data, external fonts, renderer fallback or acquisition.
"""
from __future__ import annotations

import math
from unittest.mock import patch

import pytest

from tools import pdf_test_inspection as qa


def _pdf(*streams: bytes, box=(0, 0, 200, 200), rotation=0, crop=None, user_unit=None,
         unicode_hex: bytes | None = None) -> bytes:
    """Build deterministic tiny PDFs without depending on either inspection engine."""
    count = len(streams)
    ids = [4 + 2 * n for n in range(count)]
    cmap_id = 4 + 2 * count
    kids = b" ".join(f"{n} 0 R".encode("ascii") for n in ids)
    cmap_ref = f" /ToUnicode {cmap_id} 0 R".encode("ascii") if unicode_hex else b""
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Count " + str(count).encode("ascii") + b" /Kids [" + kids + b"] >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding" + cmap_ref + b" >>",
    ]
    geometry = " ".join(str(n) for n in box)
    crop_geometry = " ".join(str(n) for n in (box if crop is None else crop))
    unit = "" if user_unit is None else f" /UserUnit {user_unit}"
    for page_id, stream in zip(ids, streams):
        objects.append(
            f"<< /Type /Page /Parent 2 0 R /MediaBox [{geometry}] /CropBox [{crop_geometry}]{unit} "
            f"/Rotate {rotation} /Resources << /Font << /F1 3 0 R >> >> /Contents {page_id + 1} 0 R >>"
            .encode("ascii"))
        objects.append(b"<< /Length " + str(len(stream)).encode("ascii") +
                       b" >>\nstream\n" + stream + b"\nendstream")
    if unicode_hex:
        cmap = (
            b"/CIDInit /ProcSet findresource begin\n12 dict begin\nbegincmap\n"
            b"/CIDSystemInfo << /Registry (Adobe) /Ordering (UCS) /Supplement 0 >> def\n"
            b"/CMapName /SyntheticMap def\n/CMapType 2 def\n"
            b"1 begincodespacerange\n<00> <FF>\nendcodespacerange\n"
            b"1 beginbfchar\n<41> <" + unicode_hex + b">\nendbfchar\n"
            b"endcmap\nCMapName currentdict /CMap defineresource pop\nend\nend\n")
        objects.append(b"<< /Length " + str(len(cmap)).encode("ascii") +
                       b" >>\nstream\n" + cmap + b"endstream")
    output = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for index, obj in enumerate(objects, 1):
        offsets.append(len(output))
        output.extend(f"{index} 0 obj\n".encode("ascii") + obj + b"\nendobj\n")
    xref = len(output)
    output.extend(f"xref\n0 {len(offsets)}\n0000000000 65535 f \n".encode("ascii"))
    for offset in offsets[1:]:
        output.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
    output.extend(f"trailer\n<< /Size {len(offsets)} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n"
                  .encode("ascii"))
    return bytes(output)


def _line(text: str, x: int = 20, y: int = 150) -> bytes:
    assert text.isascii() and not any(c in text for c in "()\\")
    return f"BT /F1 12 Tf {x} {y} Td ({text}) Tj ET\n".encode("ascii")


def _within(page, tolerance=0):
    return bool(page.text_bounds) and all(
        -tolerance <= l <= r <= page.width + tolerance and
        -tolerance <= t <= b <= page.height + tolerance
        for l, t, r, b in page.text_bounds)


def test_disarmed_gate_refuses_before_metadata_or_native_import():
    with patch.object(qa, "PDFIUM_TEST_EXECUTION_ENABLED", False), \
            patch("importlib.metadata.version") as version:
        with pytest.raises(RuntimeError, match="C5_PDFIUM_TEST_EXECUTION_DISARMED"):
            qa.require_pdfium()
        version.assert_not_called()


def test_ordered_text_numbers_revision_and_raster():
    sha = "f" * 64
    raw = _pdf(_line("Overview", 20, 180) + _line("345.75", 20, 150),
               _line("Compare", 20, 180) + _line(sha, 20, 150), box=(0, 0, 600, 200))
    first, second = qa.inspect_pdf(raw, geometry=True, max_pages=2)
    assert "Overview" in first.text and "345.75" in first.text
    assert "Compare" in second.text and sha in second.text
    assert "PRIVATE_CANARY" not in first.text + second.text
    assert "Compare" not in first.text
    assert all(_within(page, 1) for page in (first, second))
    raster = qa.render_rgb(raw, 0, scale=1.3)
    assert (raster.width, raster.height) == (math.ceil(600 * 1.3), math.ceil(200 * 1.3))
    assert len(raster.rgb) == raster.width * raster.height * 3
    assert any(v != 255 for v in raster.rgb)


@pytest.mark.parametrize("x,y", [(-5, 150), (198, 150), (20, -5), (20, 198)])
def test_clipped_text_on_each_edge_is_not_hidden_by_bounded_extraction(x, y):
    page, = qa.inspect_pdf(_pdf(_line("Visible anchor") + _line("W", x, y)), geometry=True)
    assert "Visible anchor" in page.text
    assert not _within(page, 1), "Off-page glyph must survive independent geometry enumeration"


def test_nonzero_page_origin_mapping_and_rotation_refusal():
    page, = qa.inspect_pdf(_pdf(_line("Offset origin", 30, 170),
                                 box=(10, 20, 210, 220)), geometry=True)
    assert (page.width, page.height) == (200, 200)
    assert "Offset origin" in page.text and _within(page)
    with pytest.raises(ValueError, match="Rotated PDF"):
        qa.inspect_pdf(_pdf(_line("Rotation"), rotation=90), geometry=True)


def test_changed_omitted_forbidden_and_reordered_content_controls():
    def passes(raw):
        page, = qa.inspect_pdf(raw)
        text = page.text
        return ("Overview" in text and "Compare" in text and "345.75" in text
                and "PRIVATE_CANARY" not in text and text.index("Overview") < text.index("Compare"))

    original = _line("Overview", 20, 180) + _line("Compare", 20, 160) + _line("345.75", 20, 140)
    assert passes(_pdf(original))
    for stream in (original.replace(b"345.75", b"345.76"),
                   original.replace(b"Overview", b"Absent"),
                   original + _line("PRIVATE_CANARY", 20, 120),
                   _line("Compare", 20, 180) + _line("Overview", 20, 160) + _line("345.75", 20, 140)):
        assert not passes(_pdf(stream))


def test_blank_wrong_size_and_page_count_malformed_truncated_controls():
    blank = _pdf(b"")
    page, = qa.inspect_pdf(blank)
    assert not page.text.strip()
    with pytest.raises(ValueError, match="Blank PDF raster"):
        qa.render_rgb(blank, 0, scale=1.5)
    page, = qa.inspect_pdf(_pdf(_line("A4"), box=(0, 0, 500, 700)))
    assert abs(page.width - 595.276) > 1 and abs(page.height - 841.89) > 1
    with pytest.raises(ValueError, match="Unexpected PDF page count"):
        qa.inspect_pdf(_pdf(_line("First"), _line("Second")), max_pages=1)
    with pytest.raises(ValueError, match="Incomplete generated PDF"):
        qa.inspect_pdf(b"%PDF-1.4\nmalformed")
    with pytest.raises(ValueError, match="Incomplete generated PDF"):
        qa.inspect_pdf(_pdf(_line("Complete"))[:-12])


def test_supplementary_unicode_map_and_same_engine_pixel_identity():
    # The glyph is deliberately Helvetica A in both fixtures. Only the Unicode
    # map changes: this tests extraction, not actual emoji glyph coverage.
    stream = _line("A")
    wrong = _pdf(stream, unicode_hex=b"0041")
    corrected = _pdf(stream, unicode_hex=b"D83DDCC8")
    assert qa.inspect_pdf(wrong)[0].text.strip() != "📈"
    assert qa.inspect_pdf(corrected)[0].text.strip() == "📈"
    assert qa.render_rgb(wrong, 0, scale=1.5).rgb == qa.render_rgb(corrected, 0, scale=1.5).rgb


def test_bmp_unicode_map():
    page, = qa.inspect_pdf(_pdf(_line("A"), unicode_hex=b"0394"))
    assert page.text.strip() == "Δ"


def test_sparse_continuation_retains_nonfooter_extent_predicate():
    # Exercise the actual shared predicate against independently specified boxes.
    footer = qa.TextRegion((10, 185, 190, 195),
                           "PilotODIN · Verified, version-linked analytical evidence")
    top = qa.TextRegion((20, 10, 100, 25), "Parameters")
    body = qa.TextRegion((20, 90, 100, 104), "Substantial content")
    sparse = qa.PageEvidence("", 200, 200, (top, footer), ())
    filled = qa.PageEvidence("", 200, 200, (top, body, footer), ())
    assert qa.has_sparse_continuation(sparse)
    assert not qa.has_sparse_continuation(filled)
    # A real generated two-page fixture independently exercises region geometry.
    # Font-specific Unicode footer grouping remains a separate acceptance test.
    first, last = qa.inspect_pdf(_pdf(_line("First", 20, 150),
                                     _line("Parameters", 20, 180)), geometry=True)
    assert "First" in first.text
    assert "Parameters" in last.text
    assert qa.has_sparse_continuation(last)
    _, filled_last = qa.inspect_pdf(_pdf(_line("First"),
                                         _line("Parameters", 20, 180) +
                                         _line("Substantial content", 20, 80)), geometry=True)
    assert not qa.has_sparse_continuation(filled_last)


def test_fully_off_page_canary_cannot_be_silently_lost():
    raw = _pdf(_line("Visible anchor") + _line("PRIVATE_CANARY", 220, 100))
    # Either the complete text and independent outside geometry are available,
    # or the helper explicitly refuses incomplete extraction. Never pass
    # with a missing canary.
    try:
        page, = qa.inspect_pdf(raw, geometry=True)
    except ValueError as exc:
        assert str(exc) in (
            "PDF character inventory disagrees with bounded extraction",
            "Unresolved nonseparator PDF glyph geometry",
            "Unresolved loose PDF glyph geometry",
            "Unresolved PDF character inventory",
        )
    else:
        assert "PRIVATE_CANARY" in page.text
        assert not _within(page, 1)
    try:
        page, = qa.inspect_pdf(raw)
    except ValueError as exc:
        assert str(exc) in (
            "PDF character inventory disagrees with bounded extraction",
            "Unresolved nonseparator PDF glyph geometry",
            "Unresolved PDF character inventory",
        )
    else:
        assert "PRIVATE_CANARY" in page.text


def test_distinct_crop_and_user_unit_refused():
    with pytest.raises(ValueError, match="Distinct PDF crop box"):
        qa.inspect_pdf(_pdf(_line("Crop"), crop=(10, 10, 190, 190)), geometry=True)
    for token in (b"/UserUnit", b"/User#55nit"):
        raw = _pdf(_line("Scaled"), user_unit=2).replace(b"/UserUnit", token)
        # Name-escape variant checks the independent preparse refusal, not xref.
        with pytest.raises(ValueError, match="Unsupported generated PDF"):
            qa.inspect_pdf(raw, geometry=True)


def test_malformed_with_eof_requires_reader_refusal():
    qa.require_pdfium()
    from pypdfium2 import PdfiumError
    malformed = b"%PDF-1.4\nnot a PDF object or page tree\n%%EOF\n"
    # A valid suffix alone cannot make this a generated report.
    qa._check_generated_pdf(malformed)
    with pytest.raises((PdfiumError, ValueError)):
        qa.inspect_pdf(malformed)


def _footer_stream(split: bool) -> bytes:
    # Literal octal 267 is a WinAnsi middle dot, not an external font.
    if split:
        left = (b"BT /F1 7 Tf 20 10 Td (PilotODIN) Tj ET\n"
                b"BT /F1 7 Tf 58 10 Td (\\267 Verified, version-linked analytical evidence) Tj ET\n")
    else:
        left = b"BT /F1 7 Tf 20 10 Td (PilotODIN \\267 Verified, version-linked analytical evidence) Tj ET\n"
    return left + b"BT /F1 7 Tf 540 10 Td (Page 2) Tj ET\n"


@pytest.mark.parametrize("split", [False, True])
def test_generated_footer_does_not_hide_sparse_or_footer_only_page(split):
    footer = _footer_stream(split)
    first = _line("First", 20, 150)
    top = _line("Parameters", 20, 180)
    body = _line("Substantial content", 20, 80)
    _, sparse = qa.inspect_pdf(_pdf(first, top + footer, box=(0, 0, 600, 200)), geometry=True)
    assert qa.has_sparse_continuation(sparse)
    _, full = qa.inspect_pdf(_pdf(first, top + body + footer, box=(0, 0, 600, 200)), geometry=True)
    assert not qa.has_sparse_continuation(full)
    _, footer_only = qa.inspect_pdf(_pdf(first, footer, box=(0, 0, 600, 200)), geometry=True)
    with pytest.raises(ValueError, match="no nonfooter text"):
        qa.has_sparse_continuation(footer_only)


def test_ambiguous_footer_refuses_and_unrelated_bottom_text_counts():
    top = qa.TextRegion((20, 10, 100, 25), "Parameters")
    fragment = qa.TextRegion((20, 185, 70, 195), "PilotODIN")
    unrelated = qa.TextRegion((80, 185, 190, 195), "Unrelated content")
    with pytest.raises(ValueError, match="Ambiguous continuation footer"):
        qa.has_sparse_continuation(qa.PageEvidence("", 200, 200, (top, fragment, unrelated), ()))
    assert not qa.has_sparse_continuation(qa.PageEvidence("", 200, 200, (top, unrelated), ()))


def test_missing_continuation_geometry_refuses():
    with pytest.raises(ValueError, match="Missing continuation text geometry"):
        qa.has_sparse_continuation(qa.PageEvidence("Nonblank", 200, 200, (), ()))
