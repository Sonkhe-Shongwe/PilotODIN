"""Bounded, non-destructive exports of immutable PilotODIN working versions.

Exports never update a project or its source.  Filter evaluation and column
selection apply to an exact historical version, not the mutable current view.
"""
from __future__ import annotations

import math
import os
import re
import tempfile
from pathlib import Path
from typing import Literal

import pandas as pd
from pydantic import BaseModel, Field, model_validator

try:
    from . import quality, storage
except ImportError:
    import quality, storage

MAX_EXPORT_BYTES = 75 * 1024 * 1024
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


def _safe_excel_string(value):
    if not isinstance(value, str):
        return value
    # Reject silent Excel truncation or modification of original text.
    if len(value) > 32767:
        raise quality.QualityError('A cell exceeds Excel\'s 32,767-character limit; export as CSV instead')
    if re.search(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', value):
        raise quality.QualityError('A cell contains characters unsupported by Excel; export as CSV instead')
    # Prevent spreadsheet formula execution even through leading whitespace.
    if value.lstrip(' \t\r\n').startswith(('=', '+', '-', '@')) or value.startswith(('\t', '\r', '\n')):
        return "'" + value
    return value


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
            df[name] = df[name].map(_safe_excel_string)
    # CSV/XLSX header cells can carry formulas too; never allow the export
    # metadata to create a spreadsheet execution vector.
    headers = [_safe_excel_string(str(name)) for name in df.columns]
    if len(set(headers)) != len(headers):
        raise quality.QualityError('Spreadsheet-safe header escaping would create duplicate column names')
    df.columns = headers
    dest_dir = storage.HOME / 'export_tmp'
    dest_dir.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix='pilotodin-', suffix='.'+request.format, dir=dest_dir)
    os.close(fd)
    path = Path(name)
    try:
        if request.format == 'csv':
            df.to_csv(path, index=False, encoding='utf-8-sig', lineterminator='\r\n')
        else:
            # Streaming writer avoids constructing a second large workbook in
            # memory on 8 GB Windows machines. Still subject to dataset limits.
            from openpyxl import Workbook
            from datetime import datetime
            import numpy as np
            book = Workbook(write_only=True)
            sheet = book.create_sheet('Cleaned data')
            sheet.append(list(df.columns))
            for row in df.itertuples(index=False, name=None):
                values=[]
                for item in row:
                    if item is None or (not isinstance(item,(list,dict)) and pd.isna(item)):
                        values.append(None)
                    elif isinstance(item,np.generic):
                        values.append(item.item())
                    elif isinstance(item,pd.Timestamp):
                        dt=item.to_pydatetime()
                        # Excel has no timezone-aware datetime type. Preserve
                        # the original offset as ISO text instead of silently
                        # stripping its meaning.
                        values.append(dt.isoformat() if dt.tzinfo is not None else dt)
                    else:
                        values.append(item)
                sheet.append(values)
            book.save(path)
        if path.stat().st_size > MAX_EXPORT_BYTES:
            raise quality.QualityError('Export exceeds the 75 MB size limit; select fewer rows or columns',413)
    except Exception:
        path.unlink(missing_ok=True)
        raise
    safe_stem = re.sub(r'[^a-zA-Z0-9_-]+','_',str(project['name']))[:70].strip('_') or 'Dataset'
    suffix = '_filtered' if request.filters else ''
    filename = f'{safe_stem}_cleaned_v{request.version}{suffix}.{request.format}'
    return path, filename, len(df), request.version
