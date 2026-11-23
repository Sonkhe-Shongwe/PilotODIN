"""Generated-only CF-01 regressions; no project, owner data, or native app."""
from __future__ import annotations

import csv
from io import BytesIO
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED

import pytest
from openpyxl import Workbook
from backend.import_preflight import preflight_dataset


def test_csv_too_many_rows_rejected_before_pandas(tmp_path: Path):
    path = tmp_path / "over.csv"
    with path.open("w", newline="", encoding="utf-8") as stream:
        stream.write("OrderNumber,Revenue\n")
        stream.writelines(f"{i:06d},1\n" for i in range(100_001))
    with pytest.raises(ValueError, match="100,000 rows"):
        preflight_dataset(path, ".csv")


def test_csv_too_many_columns_rejected(tmp_path: Path):
    path = tmp_path / "wide.csv"
    path.write_text(",".join(f"c{i}" for i in range(101)) + "\n" + ",".join("1" for _ in range(101)), encoding="utf-8")
    with pytest.raises(ValueError, match="100 columns"):
        preflight_dataset(path, ".csv")


def test_csv_six_million_cell_limit(tmp_path: Path):
    path = tmp_path / "cells.csv"
    header = ",".join(f"c{i}" for i in range(100)) + "\n"
    row = ",".join("1" for _ in range(100)) + "\n"
    with path.open("w", encoding="utf-8") as stream:
        stream.write(header)
        stream.write(row * 60_001)
    with pytest.raises(ValueError, match="6 million cells"):
        preflight_dataset(path, ".csv")


def test_csv_utf8_bom_and_cp1252_fallback(tmp_path: Path):
    utf = tmp_path / "bom.csv"
    utf.write_bytes(b"\xef\xbb\xbfSKU,Revenue\n0007,42\n")
    preflight_dataset(utf, ".csv")
    legacy = tmp_path / "legacy.csv"
    legacy.write_bytes("SKU,Region\n0007,Café\n".encode("cp1252"))
    preflight_dataset(legacy, ".csv")
    malformed = tmp_path / "bad_bom.csv"
    malformed.write_bytes(b"\xef\xbb\xbfSKU,Region\n0007,\xff\n")
    with pytest.raises(UnicodeDecodeError):
        preflight_dataset(malformed, ".csv")


def _write_sheet(path: Path, rows=3, columns=2, second_sheet=False):
    book = Workbook(write_only=True)
    sheet = book.create_sheet("Data")
    sheet.append([f"col{i}" for i in range(columns)])
    for _ in range(rows):
        sheet.append(["x"] * columns)
    if second_sheet:
        another = book.create_sheet("Unselected")
        another.append(["X", "Y"])
    book.save(path)


def test_xlsx_normal_and_multiple_sheets(tmp_path: Path):
    path = tmp_path / "normal.xlsx"
    _write_sheet(path, second_sheet=True)
    preflight_dataset(path, ".xlsx")


def test_xlsx_more_than_row_limit(tmp_path: Path):
    path = tmp_path / "over.xlsx"
    _write_sheet(path, rows=100_001)
    with pytest.raises(ValueError, match="100,000 rows"):
        preflight_dataset(path, ".xlsx")


def test_xlsx_wide_row(tmp_path: Path):
    path = tmp_path / "wide.xlsx"
    _write_sheet(path, rows=1, columns=101)
    with pytest.raises(ValueError, match="100 columns"):
        preflight_dataset(path, ".xlsx")


def test_xlsx_rejects_deceptive_dimensions(tmp_path: Path):
    path = tmp_path / "sparse.xlsx"
    _write_sheet(path, rows=1)
    # Repackage without changing source files: forged row coordinate is far
    # outside the declared normal sheet dimension.
    with ZipFile(path) as source:
        members = {name: source.read(name) for name in source.namelist()}
    sheet_name = next(name for name in members if name.startswith("xl/worksheets/sheet"))
    members[sheet_name] = members[sheet_name].replace(b'r="2"', b'r="100002"', 1)
    with ZipFile(path, "w", ZIP_DEFLATED) as archive:
        for name, data in members.items():
            archive.writestr(name, data)
    with pytest.raises(ValueError, match="100,000 rows"):
        preflight_dataset(path, ".xlsx")


def test_xlsx_rejects_expansion_before_parsing(tmp_path: Path):
    path = tmp_path / "bomb.xlsx"
    with ZipFile(path, "w", ZIP_DEFLATED) as archive:
        archive.writestr("xl/workbook.xml", b"x" * (129 * 1024 * 1024))
    with pytest.raises(ValueError, match="resource budget"):
        preflight_dataset(path, ".xlsx")


def test_read_only_original_bytes(tmp_path: Path):
    path = tmp_path / "clean.csv"
    path.write_bytes(b"SKU,Revenue\n0007,11\n")
    original = path.read_bytes()
    preflight_dataset(path, ".csv")
    assert path.read_bytes() == original


def test_oversize_csv_read_data_rejected_before_pandas(tmp_path: Path, monkeypatch):
    """The existing product reader has no chance to materialize a rejected CSV."""
    from backend import engine
    path = tmp_path / "too-wide.csv"
    path.write_text(",".join(f"h{i}" for i in range(101)) + "\n", encoding="utf-8")
    monkeypatch.setattr(engine.pd, "read_csv", lambda *a, **kw: pytest.fail("pandas must not run"))
    with pytest.raises(ValueError, match="100 columns"):
        engine.read_data(str(path), ".csv")


def test_oversize_xlsx_read_data_rejected_before_pandas(tmp_path: Path, monkeypatch):
    from backend import engine
    path = tmp_path / "too-wide.xlsx"
    _write_sheet(path, rows=1, columns=101)
    monkeypatch.setattr(engine.pd, "read_excel", lambda *a, **kw: pytest.fail("pandas must not run"))
    with pytest.raises(ValueError, match="100 columns"):
        engine.read_data(str(path), ".xlsx")


def test_shared_strings_count_bound_before_reader(tmp_path: Path):
    """Small compressed sheet with a huge string table cannot escape row limits."""
    path = tmp_path / "big-strings.xlsx"
    _write_sheet(path, rows=1, columns=2)
    # Realistic XML table element; the worksheet itself is tiny.
    table = (b'<?xml version="1.0" encoding="utf-8"?>'
             b'<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
             + b'<si><t>x</t></si>' * 200_001 + b'</sst>')
    with ZipFile(path, "a", ZIP_DEFLATED) as archive:
        archive.writestr("xl/sharedStrings.xml", table)
    with pytest.raises(ValueError, match="shared-string table"):
        preflight_dataset(path, ".xlsx")


def test_duplicate_archive_members_rejected(tmp_path: Path):
    path = tmp_path / "duplicates.xlsx"
    _write_sheet(path, rows=1, columns=2)
    from warnings import catch_warnings, simplefilter
    with catch_warnings():
        simplefilter("ignore", UserWarning)
        with ZipFile(path, "a", ZIP_DEFLATED) as archive:
            archive.writestr("xl/workbook.xml", "<fake/>")
    with pytest.raises(ValueError, match="duplicate archive member"):
        preflight_dataset(path, ".xlsx")


def test_valid_csv_leading_zero_identifier_through_reader(tmp_path: Path):
    """CF-01 remains compatible with the already-verified CF-02 typing rule."""
    from backend import engine
    path = tmp_path / "identifiers.csv"
    path.write_bytes("OrderNumber,SKU,Revenue,City\n0007,0012,42,Café\n".encode("cp1252"))
    df = engine.read_data(str(path), ".csv")
    assert df.iloc[0]["OrderNumber"] == "0007"
    assert df.iloc[0]["SKU"] == "0012"
    assert df.iloc[0]["Revenue"] == 42
    assert df.iloc[0]["City"] == "Café"


def test_valid_xlsx_multi_sheet_through_reader(tmp_path: Path):
    from backend import engine
    path = tmp_path / "two-sheet.xlsx"
    book = Workbook()
    first = book.active
    first.append(["SKU", "Revenue"])
    first.append(["0007", 42])
    second = book.create_sheet("Other")
    second.append(["not", "selected"])
    book.save(path)
    df = engine.read_data(str(path), ".xlsx")
    assert df.shape == (1, 2)
    assert df.iloc[0]["Revenue"] == 42


def test_rejected_csv_preserves_original_bytes(tmp_path: Path):
    path = tmp_path / "wide-original.csv"
    path.write_bytes((",".join(f"h{i}" for i in range(101)) + "\n" + ",".join("v" for _ in range(101)) + "\n").encode("utf-8"))
    original = path.read_bytes()
    with pytest.raises(ValueError, match="100 columns"):
        preflight_dataset(path, ".csv")
    assert path.read_bytes() == original


def test_rejected_xlsx_preserves_original_bytes(tmp_path: Path):
    path = tmp_path / "wide-original.xlsx"
    _write_sheet(path, rows=1, columns=101)
    original = path.read_bytes()
    with pytest.raises(ValueError, match="100 columns"):
        preflight_dataset(path, ".xlsx")
    assert path.read_bytes() == original


def test_xlsx_repeated_row_coordinates_cannot_bypass_physical_limit(tmp_path: Path):
    """Regression: v2 wrongly accepted 100001 repeated r=2 worksheet rows."""
    path = tmp_path / "repeated-rows.xlsx"
    _write_sheet(path, rows=1)
    with ZipFile(path) as source:
        members = {name: source.read(name) for name in source.namelist()}
    worksheet = next(name for name in members if name.startswith("xl/worksheets/sheet"))
    repeated = (b'<row r="2"><c r="A2" t="inlineStr">'
                b'<is><t>test</t></is></c></row>') * 100_001
    assert b"</sheetData>" in members[worksheet]
    members[worksheet] = members[worksheet].replace(
        b"</sheetData>", repeated + b"</sheetData>", 1)
    with ZipFile(path, "w", ZIP_DEFLATED) as archive:
        for member, data in members.items():
            archive.writestr(member, data)
    assert path.stat().st_size < 1_000_000  # Small archive, very many XML rows.
    with pytest.raises(ValueError, match="100,000 rows"):
        preflight_dataset(path, ".xlsx")


def test_csv_exact_row_limit_accepted(tmp_path: Path):
    path = tmp_path / "exactly_100k.csv"
    with path.open("w", encoding="utf-8") as source:
        source.write("SKU,Revenue\n")
        source.write("0001,1\n" * 100_000)
    preflight_dataset(path, ".csv")


def test_xlsx_exact_row_limit_accepted(tmp_path: Path):
    path = tmp_path / "exactly_100k.xlsx"
    _write_sheet(path, rows=100_000)
    preflight_dataset(path, ".xlsx")


def test_xlsx_moved_shared_strings_cannot_bypass_budget(tmp_path: Path):
    """openpyxl loads renamed shared-string parts from [Content_Types].xml."""
    path = tmp_path / "aliased-shared-strings.xlsx"
    _write_sheet(path, rows=1)
    with ZipFile(path) as source:
        members = {name: source.read(name) for name in source.namelist()}
    fake_table = (b'<?xml version="1.0" encoding="utf-8"?>'
                  b'<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
                  + b'<si><t>x</t></si>' * 200_001 + b'</sst>')
    moved_path = "xl/movedStrings.xml"
    members[moved_path] = fake_table
    override = (b'<Override PartName="/xl/movedStrings.xml" '
                b'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sharedStrings+xml"/>')
    assert b'</Types>' in members['[Content_Types].xml']
    members['[Content_Types].xml'] = members['[Content_Types].xml'].replace(
        b'</Types>', override + b'</Types>', 1)
    with ZipFile(path, "w", ZIP_DEFLATED) as archive:
        for member, data in members.items():
            archive.writestr(member, data)
    with pytest.raises(ValueError, match="shared-string table"):
        preflight_dataset(path, ".xlsx")


def test_csv_large_valid_text_field_survives_preflight_and_reader(tmp_path: Path):
    """Preflight must not impose csv.reader's default 128 KiB field cap."""
    from backend import engine
    path = tmp_path / "legitimate-long-field.csv"
    notes = "A" * 160_000
    path.write_text('SKU,Notes,Revenue\n0007,"' + notes + '",1\n', encoding="utf-8")
    before = path.read_bytes()
    old_limit = csv.field_size_limit()
    preflight_dataset(path, ".csv")
    assert csv.field_size_limit() == old_limit
    frame = engine.read_data(str(path), ".csv")
    assert frame.iloc[0]["Notes"] == notes
    assert frame.iloc[0]["SKU"] == "0007"
    assert path.read_bytes() == before


def test_csv_field_size_global_is_restored_after_row_guard_failure(tmp_path: Path):
    path = tmp_path / "too-wide-long-field.csv"
    long_field = "A" * 160_000
    path.write_text(",".join(f"c{i}" for i in range(101)) + "\n" +
                    long_field + "," * 100, encoding="utf-8")
    old_limit = csv.field_size_limit()
    with pytest.raises(ValueError, match="100 columns"):
        preflight_dataset(path, ".csv")
    assert csv.field_size_limit() == old_limit


def test_csv_field_size_global_is_restored_after_bom_decode_error(tmp_path: Path):
    path = tmp_path / "malformed-bom.csv"
    path.write_bytes(b"\xef\xbb\xbfSKU,Notes\n0007," + b"a" * 160_000 + b"\xff")
    old_limit = csv.field_size_limit()
    with pytest.raises(UnicodeDecodeError):
        preflight_dataset(path, ".csv")
    assert csv.field_size_limit() == old_limit


def _sparse_late_xlsx(path: Path, last_row: int, width: int = 100) -> None:
    """Sparse sheet dimension is not the same as number of populated cells."""
    book = Workbook()
    sheet = book.active
    sheet.append([f"c{i}" for i in range(width)])
    sheet.cell(row=last_row, column=1, value="last")
    book.save(path)


def test_sparse_xlsx_cross_row_cell_budget_rejected_before_pandas(tmp_path: Path, monkeypatch):
    from backend import engine
    path = tmp_path / "sparse_over_6m.xlsx"
    _sparse_late_xlsx(path, 60_002)
    original = path.read_bytes()
    assert path.stat().st_size < 15_000
    monkeypatch.setattr(engine.pd, "read_excel", lambda *a, **kw: pytest.fail("pandas must not run"))
    with pytest.raises(ValueError, match="6 million cells"):
        engine.read_data(str(path), ".xlsx")
    assert path.read_bytes() == original


def test_sparse_xlsx_exact_cell_budget_accepted_at_preflight(tmp_path: Path):
    path = tmp_path / "sparse_exact_6m.xlsx"
    _sparse_late_xlsx(path, 60_001)
    preflight_dataset(path, ".xlsx")


def test_quality_blocks_oversized_legacy_xlsx_before_pandas(tmp_path: Path, monkeypatch):
    from backend import engine, quality
    path = tmp_path / "legacy_large.xlsx"
    _sparse_late_xlsx(path, 60_002)
    monkeypatch.setattr(engine, "read_xlsx_with_identifiers", lambda *a, **kw: pytest.fail("Quality reader must not run"))
    with pytest.raises(quality.QualityError, match="6 million cells") as error:
        quality._source_df({"dataset_path": str(path), "file_ext": ".xlsx"})
    assert error.value.status == 409


def test_quality_blocks_oversized_legacy_csv_before_pandas(tmp_path: Path, monkeypatch):
    from backend import engine, quality
    path = tmp_path / "legacy_wide.csv"
    path.write_text(",".join(f"c{i}" for i in range(101)) + "\n1,2\n", encoding="utf-8")
    monkeypatch.setattr(engine, "read_csv_with_identifiers", lambda *a, **kw: pytest.fail("Quality reader must not run"))
    with pytest.raises(quality.QualityError, match="100 columns") as error:
        quality._source_df({"dataset_path": str(path), "file_ext": ".csv"})
    assert error.value.status == 409
