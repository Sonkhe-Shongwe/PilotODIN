"""Bounded, read-only CSV/XLSX dimension preflight before pandas allocation.

The limits are existing PilotODIN dataset shape limits. The ZIP ceilings are
additional conservative resource guards and require real 8 GB calibration.
No original file is modified and no worksheet content is cached here.
"""
from __future__ import annotations

import csv
import posixpath
import re
from threading import Lock
from codecs import BOM_UTF8
from pathlib import Path
from xml.etree import ElementTree as ET
from zipfile import BadZipFile, ZipFile

MAX_ROWS = 100_000
MAX_COLUMNS = 100
MAX_CELLS = 6_000_000
# Temporary safety ceilings, not a claim of validated 8 GB capacity.
MAX_XLSX_MEMBERS = 2048
MAX_XLSX_TOTAL_UNCOMPRESSED = 256 * 1024 * 1024
MAX_XLSX_MEMBER_UNCOMPRESSED = 128 * 1024 * 1024
MAX_XLSX_METADATA_BYTES = 2 * 1024 * 1024
MAX_XLSX_COMPRESSION_RATIO = 1000
# Prevent a small workbook from causing unbounded shared-string allocation.
# Conservative candidate budgets, not validated 8 GB performance limits.
MAX_XLSX_SHARED_STRINGS_XML = 32 * 1024 * 1024
MAX_XLSX_SHARED_STRING_ENTRIES = 200_000

_SPREADSHEET_NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
_OFFICE_REL_ID = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"
_PACKAGE_REL = "{http://schemas.openxmlformats.org/package/2006/relationships}Relationship"
_CONTENT_OVERRIDE = "{http://schemas.openxmlformats.org/package/2006/content-types}Override"
_CELL_REF = re.compile(r"([A-Z]+)([1-9][0-9]*)\Z")
_LIMIT_ERROR = "Current guardrail: 100,000 rows, 100 columns and 6 million cells maximum"
# csv.field_size_limit is process-global; serialize overrides across preflights.
_CSV_FIELD_LIMIT_LOCK = Lock()
MAX_CSV_FIELD_BYTES = 40 * 1024 * 1024  # Existing upload size ceiling.



def _check_shape(rows: int, columns: int) -> None:
    if rows > MAX_ROWS or columns > MAX_COLUMNS or rows * columns > MAX_CELLS:
        raise ValueError(_LIMIT_ERROR)


def _csv_dimensions(path: str | Path, encoding: str) -> None:
    # csv.reader defaults to a 128 KiB field ceiling, while pandas accepts
    # valid larger text fields. Do not introduce silent data rejection as a
    # side effect of the new dimension preflight. Keep any temporary override
    # bounded by the existing 40 MiB upload cap, and restore it on *all* exits.
    # The stdlib setting is process-global, so two simultaneous PilotODIN
    # preflights must not race each other's saved values.
    with _CSV_FIELD_LIMIT_LOCK:
        original_limit = csv.field_size_limit()
        requested = max(original_limit, min(Path(path).stat().st_size, MAX_CSV_FIELD_BYTES))
        try:
            csv.field_size_limit(requested)
            with open(path, "r", encoding=encoding, errors="strict", newline="") as source:
                reader = csv.reader(source)
                # pandas ignores blank physical lines unless quoted into a cell.
                header = next((row for row in reader if row), [])
                columns = len(header)
                _check_shape(0, columns)
                rows = 0
                for row in reader:
                    if not row:
                        continue
                    rows += 1
                    _check_shape(rows, max(columns, len(row)))
        finally:
            csv.field_size_limit(original_limit)


def _preflight_csv(path: str | Path) -> None:
    try:
        _csv_dimensions(path, "utf-8-sig")
    except UnicodeDecodeError:
        # Match read_csv_with_identifiers: an explicit UTF-8 BOM forbids a
        # fallback that could reinterpret malformed source bytes as CP1252.
        with open(path, "rb") as source:
            if source.read(len(BOM_UTF8)) == BOM_UTF8:
                raise
        _csv_dimensions(path, "cp1252")
    except csv.Error as exc:
        raise ValueError(f"CSV preflight failed: {exc}") from exc


def _limited_xml(archive: ZipFile, member: str) -> ET.Element:
    info = archive.getinfo(member)
    if info.file_size > MAX_XLSX_METADATA_BYTES:
        raise ValueError("XLSX workbook metadata exceeds preflight budget")
    with archive.open(info) as source:
        return ET.parse(source).getroot()


def _first_worksheet(archive: ZipFile) -> str:
    book = _limited_xml(archive, "xl/workbook.xml")
    rels = _limited_xml(archive, "xl/_rels/workbook.xml.rels")
    targets = {node.attrib.get("Id"): node.attrib.get("Target", "")
               for node in rels.iter(_PACKAGE_REL)
               if node.attrib.get("Type", "").endswith("/worksheet")}
    for sheet in book.iter(_SPREADSHEET_NS + "sheet"):
        target = targets.get(sheet.attrib.get(_OFFICE_REL_ID))
        if target is None:
            continue  # Chartsheets are not data worksheets.
        if not target or "\\" in target:
            raise ValueError("Invalid XLSX worksheet reference")
        member = (posixpath.normpath(target.lstrip("/")) if target.startswith("/")
                  else posixpath.normpath(posixpath.join("xl", target)))
        if not member.startswith("xl/worksheets/") or member not in archive.namelist():
            raise ValueError("XLSX worksheet is outside the workbook")
        return member
    raise ValueError("XLSX workbook has no readable worksheet")


def _preflight_shared_strings(archive: ZipFile) -> None:
    """Bound each real shared-string part, even when moved from its usual path.

    openpyxl resolves shared strings from [Content_Types].xml, not solely
    from xl/sharedStrings.xml. A renamed part must not bypass this budget.
    """
    content_types = _limited_xml(archive, "[Content_Types].xml")
    names = set(archive.namelist())
    members: set[str] = set()
    if "xl/sharedStrings.xml" in names:
        members.add("xl/sharedStrings.xml")
    for item in content_types.iter(_CONTENT_OVERRIDE):
        content_type = item.attrib.get("ContentType", "")
        if not content_type.endswith(".sharedStrings+xml"):
            continue
        part = item.attrib.get("PartName", "")
        if not part.startswith("/") or "\\" in part:
            raise ValueError("Invalid XLSX shared-string reference")
        member = posixpath.normpath(part.lstrip("/"))
        if member.startswith("../") or member not in names:
            raise ValueError("Invalid XLSX shared-string reference")
        members.add(member)
    count = 0
    for member in sorted(members):
        info = archive.getinfo(member)
        if info.file_size > MAX_XLSX_SHARED_STRINGS_XML:
            raise ValueError("XLSX shared-string table exceeds preflight resource budget")
        with archive.open(info) as source:
            root = None
            for event, node in ET.iterparse(source, events=("start", "end")):
                if root is None and event == "start":
                    root = node
                if event == "end" and node.tag == _SPREADSHEET_NS + "si":
                    count += 1
                    if count > MAX_XLSX_SHARED_STRING_ENTRIES:
                        raise ValueError("XLSX shared-string table exceeds preflight resource budget")
                    node.clear()
                    if root is not None:
                        root.clear()


def _excel_column(cell_ref: str) -> tuple[int, int]:
    match = _CELL_REF.fullmatch(cell_ref)
    if match is None:
        raise ValueError("Invalid XLSX cell coordinate")
    col = 0
    for letter in match.group(1):
        col = col * 26 + (ord(letter) - 64)
        if col > MAX_COLUMNS:
            raise ValueError(_LIMIT_ERROR)
    return col, int(match.group(2))


def _preflight_xlsx(path: str | Path) -> None:
    try:
        with ZipFile(path) as archive:
            entries = archive.infolist()
            if len(entries) > MAX_XLSX_MEMBERS:
                raise ValueError("XLSX has too many archive members")
            names = [item.filename for item in entries]
            if len(names) != len(set(names)):
                raise ValueError("XLSX has duplicate archive member names")
            total = 0
            for item in entries:
                total += item.file_size
                if (item.file_size > MAX_XLSX_MEMBER_UNCOMPRESSED or
                        total > MAX_XLSX_TOTAL_UNCOMPRESSED or
                        item.file_size > max(1, item.compress_size) * MAX_XLSX_COMPRESSION_RATIO):
                    raise ValueError("XLSX expanded archive exceeds preflight resource budget")
                if item.flag_bits & 1:
                    raise ValueError("Encrypted XLSX archive entries are not supported")
            member = _first_worksheet(archive)
            _preflight_shared_strings(archive)
            with archive.open(member) as source:
                current_row = 0
                physical_rows = 0
                row_cells = 0
                max_row_seen = 0
                max_column_seen = 0
                saw_header = False
                # Stream real cell/row XML rather than trust the often-incorrect
                # sheet <dimension> metadata; do not load shared strings.
                for event, node in ET.iterparse(source, events=("start", "end")):
                    if node.tag == _SPREADSHEET_NS + "row" and event == "start":
                        # A workbook can repeat/forge row coordinates. Count
                        # every physical XML row in addition to its declared
                        # coordinate, or a tiny ZIP can bypass the row limit.
                        physical_rows += 1
                        _check_shape(max(0, physical_rows - 1), max_column_seen)
                        row_cells = 0
                        current_row += 1
                        raw = node.attrib.get("r")
                        if raw is not None:
                            if not raw.isdecimal() or int(raw) < 1:
                                raise ValueError("Invalid XLSX row coordinate")
                            current_row = int(raw)
                        # A sparse sheet can declare its 100th column in the
                        # header and its final row in a later, narrow row.
                        # Combine bounds across the entire selected sheet.
                        max_row_seen = max(max_row_seen, current_row, physical_rows)
                        _check_shape(max(0, max_row_seen - 1), max_column_seen)
                    elif node.tag == _SPREADSHEET_NS + "c" and event == "end":
                        row_cells += 1
                        max_column_seen = max(max_column_seen, row_cells)
                        ref = node.attrib.get("r")
                        if ref:
                            col, row = _excel_column(ref)
                            max_row_seen = max(max_row_seen, row)
                            max_column_seen = max(max_column_seen, col)
                        _check_shape(max(0, max_row_seen - 1), max_column_seen)
                        node.clear()
                    elif node.tag == _SPREADSHEET_NS + "row" and event == "end":
                        saw_header = True
                        node.clear()
                    elif event == "end":
                        node.clear()
                if not saw_header:
                    return  # The ordinary reader will reject empty sheets.
    except (BadZipFile, KeyError, ET.ParseError) as exc:
        raise ValueError("Invalid or unsafe XLSX workbook") from exc


def preflight_dataset(path: str | Path, ext: str) -> None:
    """Fail closed on shape/expansion before any pandas CSV/XLSX materialization."""
    if ext == ".csv":
        _preflight_csv(path)
    elif ext == ".xlsx":
        _preflight_xlsx(path)
    else:
        raise ValueError("Only CSV and XLSX files are supported")
