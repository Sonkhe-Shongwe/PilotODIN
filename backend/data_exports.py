"""Bounded, non-destructive exports of immutable PilotODIN working versions.

Exports never update a project or its source.  Filter evaluation and column
selection apply to an exact historical version, not the mutable current view.
"""
from __future__ import annotations

import math
import io
import stat
from zipfile import ZipFile, ZIP_DEFLATED
import os
import re
import tempfile
from pathlib import Path
from typing import Literal

import pandas as pd
from pydantic import BaseModel, Field, model_validator

try:
    from . import quality, storage, export_publication
except ImportError:
    import quality, storage, export_publication

MAX_EXPORT_BYTES = export_publication.MAX_EXPORT_BYTES
MAX_FILTERS = 8


class ExportFilter(BaseModel):
    column: str = Field(min_length=1, max_length=200)
    operator: Literal['eq', 'ne', 'contains', 'gt', 'lt', 'gte', 'lte', 'is_null', 'not_null']
    value: str | int | float | bool | None = None

    @model_validator(mode='after')
    def value_for_operator(self):
        if self.operator not in ('is_null', 'not_null') and self.value is None:
            raise ValueError('Filter value is required')
        if isinstance(self.value, float) and not math.isfinite(self.value):
            raise ValueError('Filter value must be finite')
        return self


class ExportRequest(BaseModel):
    version: int = Field(ge=0)
    format: Literal['csv', 'xlsx'] = 'csv'
    columns: list[str] | None = Field(default=None, max_length=100)
    filters: list[ExportFilter] = Field(default_factory=list, max_length=MAX_FILTERS)

    @model_validator(mode='after')
    def validate_columns(self):
        if self.columns is not None and (not self.columns or len(set(self.columns)) != len(self.columns)):
            raise ValueError('Selected columns must be nonempty and unique')
        return self


def _safe_excel_string(value, *, xlsx=True):
    if not isinstance(value, str):
        return value
    # Escape before checking the final cell length, including the prefix.
    if value.lstrip(' \t\r\n').startswith(('=', '+', '-', '@')) or value.startswith(('\t', '\r', '\n')):
        value = "'" + value
    if xlsx and len(value) > 32767:
        raise quality.QualityError("A cell exceeds Excel's 32,767-character limit; export as CSV instead")
    if xlsx and re.search(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', value):
        raise quality.QualityError('A cell contains characters unsupported by Excel; export as CSV instead')
    return value


def _size_error():
    return quality.QualityError('Export exceeds the 75 MB size limit; select fewer rows or columns',413)


class _BoundedOutput:
    """Seekable binary output: enforce the actual archive extent before every write.

    ZIP writers seek backwards to patch headers; a cumulative byte counter
    would reject legitimate files. This wrapper does not own/close the handle.
    """
    def __init__(self, stream, limit):
        self.stream = stream
        self.limit = limit
        self.extent = 0
        self.refused = False

    def tell(self):
        return self.stream.tell()

    def seek(self, offset, whence=os.SEEK_SET):
        base = {os.SEEK_SET:0, os.SEEK_CUR:self.tell(), os.SEEK_END:self.extent}[whence]
        target = base + offset
        if not 0 <= target <= self.limit:
            self.refused = True
            raise _size_error()
        return self.stream.seek(target)

    def seekable(self):
        return True

    def writable(self):
        return True

    def flush(self):
        self.stream.flush()

    def write(self, data):
        if self.refused or self.tell() + len(data) > self.limit:
            self.refused = True
            raise _size_error()
        written = self.stream.write(data)
        if written != len(data):
            raise OSError("Incomplete export write")
        self.extent = max(self.extent, self.tell())
        return written


class _CsvText(io.TextIOBase):
    def __init__(self, output):
        self.output = output

    def writable(self):
        return True

    def write(self, value):
        self.output.write(value.encode('utf-8'))
        return len(value)


def _write_csv(df, output):
    output.write(b'\xef\xbb\xbf')
    df.to_csv(_CsvText(output), index=False, lineterminator='\r\n')


def _xlsx_values(row):
    import numpy as np
    for item in row:
        if item is None or (not isinstance(item,(list,dict)) and pd.isna(item)):
            yield None
        elif isinstance(item,np.generic):
            yield item.item()
        elif isinstance(item,pd.Timestamp):
            dt=item.to_pydatetime()
            yield dt.isoformat() if dt.tzinfo is not None else dt
        else:
            yield item


def _write_xlsx(df, output):
    """Stream one plain worksheet directly into the ZIP, without XML scratch.

    The small adapter uses openpyxl's write-only WorksheetWriter and ExcelWriter
    internals (verified against 3.1.5). No global tempfile settings, global
    ALL_TEMP_FILES changes, pathname reopen, or separate worksheet spool.
    The standard writer still produces relationships, styles and workbook
    metadata. Keep this adapter scoped to the single, feature-free export.
    """
    from openpyxl import Workbook
    from openpyxl.worksheet._writer import WorksheetWriter
    from openpyxl.writer.excel import ExcelWriter
    from openpyxl.drawing.spreadsheet_drawing import SpreadsheetDrawing

    class DirectWorksheetWriter(ExcelWriter):
        def write_worksheet(self, ws):
            if (ws._writer is not None or ws.closed or ws._charts or ws._images
                    or ws._tables or ws._pivots or ws.path != '/xl/worksheets/sheet1.xml'):
                raise RuntimeError("Unsupported XLSX streaming worksheet contract")
            ws._drawing = SpreadsheetDrawing()
            with self._archive.open(ws.path[1:], 'w', force_zip64=True) as xml:
                writer = WorksheetWriter(ws, out=xml)
                ws._writer = writer
                try:
                    writer.write_top()
                    ws.append(list(df.columns))
                    for row in df.itertuples(index=False, name=None):
                        ws.append(list(_xlsx_values(row)))
                    ws.close()
                except BaseException:
                    # Close only this writer's generators. An output refusal
                    # remains latched; cleanup must not resume writing.
                    for generator in (ws._rows, writer.xf):
                        if generator is not None:
                            try:
                                generator.close()
                            except Exception:
                                pass
                    raise
            ws._rels = writer._rels
            self.manifest.append(ws)

    book = Workbook(write_only=True)
    book.create_sheet('Cleaned data')
    with ZipFile(output, 'w', ZIP_DEFLATED, allowZip64=True) as archive:
        DirectWorksheetWriter(book, archive).write_data()


def _identity(path, expected):
    storage.check_write_path(path, expected=expected)
    info = path.lstat()
    if (not stat.S_ISREG(info.st_mode) or not info.st_ino or info.st_nlink != 1
            or getattr(info,'st_file_attributes',0) & 0x400
            or not os.path.samestat(expected,info)):
        raise quality.QualityError("Export scratch identity changed; file preserved for review",409)
    return info


def _filter(df: pd.DataFrame, item: ExportFilter) -> pd.DataFrame:
    if item.column not in df:
        raise quality.QualityError(f'Unknown filter column: {item.column}')
    series = df[item.column]
    op = item.operator
    if op == 'is_null':
        return df[series.isna()]
    if op == 'not_null':
        return df[series.notna()]
    value = item.value
    if op == 'contains':
        if not isinstance(value, str) or not value:
            raise quality.QualityError('Contains requires a nonempty text value')
        mask = series.astype('string').str.contains(value, regex=False, case=False, na=False)
    elif op in ('eq', 'ne'):
        if pd.api.types.is_numeric_dtype(series) and not pd.api.types.is_bool_dtype(series):
            try:
                number = float(value)
            except (ValueError, TypeError):
                raise quality.QualityError(f'Filter for {item.column} requires a numeric value') from None
            if not math.isfinite(number):
                raise quality.QualityError('Numeric filter must be finite')
            mask = series.eq(number) if op == 'eq' else series.ne(number)
        else:
            mask = series.astype('string').eq(str(value)) if op == 'eq' else series.astype('string').ne(str(value))
    else:
        if not pd.api.types.is_numeric_dtype(series) or pd.api.types.is_bool_dtype(series):
            raise quality.QualityError('Range filters require a numeric column')
        try:
            number = float(value)
        except (ValueError, TypeError):
            raise quality.QualityError('Range filters require a numeric value') from None
        if not math.isfinite(number):
            raise quality.QualityError('Numeric filter must be finite')
        mask = {'gt':series.gt,'lt':series.lt,'gte':series.ge,'lte':series.le}[op](number)
    return df[mask.fillna(False)]


def prepare(pid: str, request: ExportRequest) -> tuple[Path, str, int, int]:
    """Return (temporary path, download name, row count, version).

    Callers must remove the temporary file after transfer. Files are staged in
    private local storage, never beside the uploaded source.
    """
    project = quality._project(pid)
    df = quality.data_at_version(pid, request.version)
    if request.columns is not None:
        unknown = [column for column in request.columns if column not in df.columns]
        if unknown:
            raise quality.QualityError('Unknown export column(s): ' + ', '.join(unknown[:5]))
    for f in request.filters:
        df = _filter(df, f)
    if request.columns is not None:
        df = df.loc[:,request.columns].copy()
    else:
        df = df.copy()
    # Escaping string values rather than asking office applications to treat
    # potentially malicious dataset cells as plain text is mandatory.
    for name in df.columns:
        if pd.api.types.is_object_dtype(df[name]) or pd.api.types.is_string_dtype(df[name]):
            df[name] = df[name].map(lambda value: _safe_excel_string(value, xlsx=request.format=='xlsx'))
    # CSV/XLSX header cells can carry formulas too; never allow the export
    # metadata to create a spreadsheet execution vector.
    headers = [_safe_excel_string(str(name), xlsx=request.format=='xlsx') for name in df.columns]
    if len(set(headers)) != len(headers):
        raise quality.QualityError('Spreadsheet-safe header escaping would create duplicate column names')
    df.columns = headers
    dest_dir = storage.HOME / 'export_tmp'
    storage.check_write_path(dest_dir, directory=True, missing=True)
    dest_dir.mkdir(parents=True, exist_ok=True)
    storage.check_write_path(dest_dir, directory=True)
    fd, name = tempfile.mkstemp(prefix='pilotodin-', suffix='.'+request.format, dir=dest_dir)
    path = Path(name)
    identity = None
    try:
        # Never reopen the allocated name for serialization. Verify against
        # the exact file object created by mkstemp, even in unleased fixtures.
        with os.fdopen(fd, 'w+b') as stream:
            identity = os.fstat(stream.fileno())
            _identity(path, identity)
            output = _BoundedOutput(stream, MAX_EXPORT_BYTES)
            if request.format == 'csv':
                _write_csv(df, output)
            else:
                _write_xlsx(df, output)
            output.flush()
            os.fsync(stream.fileno())
            observed = os.fstat(stream.fileno())
            if (observed.st_size != output.extent or not 1 <= observed.st_size <= MAX_EXPORT_BYTES):
                raise _size_error()
            final = _identity(path, identity)
            if (final.st_size != observed.st_size or final.st_mtime_ns != observed.st_mtime_ns
                    or final.st_ctime_ns != observed.st_ctime_ns):
                raise quality.QualityError("Export scratch changed during serialization",409)
        _identity(path, identity)
    except BaseException:
        # Release the handle before unlink (Windows). Refuse a swapped name;
        # never delete a foreign replacement or a file without identity proof.
        if identity is not None:
            _identity(path, identity)
            storage.guarded_unlink(path, expected=identity)
        raise
    safe_stem = re.sub(r'[^a-zA-Z0-9_-]+','_',str(project['name']))[:70].strip('_') or 'Dataset'
    suffix = '_filtered' if request.filters else ''
    filename = f'{safe_stem}_cleaned_v{request.version}{suffix}.{request.format}'
    return path, filename, len(df), request.version
