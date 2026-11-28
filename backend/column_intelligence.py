"""Read-only, version-pinned column investigation for approved working datasets.

Physical dtype is reported separately from a heuristic analytical role.
No implicit data conversions, row mutations, AI calls or large row exports.
"""
from __future__ import annotations

import math
import re
from typing import Any

import numpy as np
import pandas as pd

MAX_EXAMPLES = 8
MAX_TOP_VALUES = 10
MAX_SAMPLE_ROWS = 12
MAX_TEXT = 160
DATE_PREFIX = re.compile(r"^\d{4}[-/]\d{1,2}[-/]\d{1,2}(?:[ T].*)?$")
IDENTIFIER_NAME = re.compile(r"(?:^id$|[_\s-]id$|id$|key$|code$|number$)", re.I)


def _clean(value: Any) -> str | int | float | bool | None:
    if value is None:
        return None
    if isinstance(value, (pd.Timestamp, np.datetime64)):
        try:
            return pd.Timestamp(value).isoformat()
        except (ValueError, TypeError):
            return None
    if isinstance(value, (bool, np.bool_)):
        return bool(value)
    if isinstance(value, (np.integer, int)):
        return int(value)
    if isinstance(value, (np.floating, float)):
        numeric = float(value)
        return numeric if math.isfinite(numeric) else None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    return str(value)[:MAX_TEXT]


def _numeric_dtype(series: pd.Series) -> bool:
    return pd.api.types.is_numeric_dtype(series) and not pd.api.types.is_bool_dtype(series)


def _role(series: pd.Series) -> tuple[str, str, list[str]]:
    observed = series.dropna()
    n = len(observed)
    if n == 0:
        return "unknown", "Every value is missing; no meaningful type can be inferred.", []
    if pd.api.types.is_bool_dtype(series):
        return "boolean", "Stored as boolean true/false values.", []
    if pd.api.types.is_datetime64_any_dtype(series):
        return "datetime", "Stored as a datetime type.", []
    if _numeric_dtype(series):
        return "numeric", "Stored as a numeric type; statistics use finite observed values.", []
    # Do not infer full-column types from a few examples. These hints explicitly
    # describe only a bounded sample, and never change the stored dtype.
    sample = observed.iloc[:min(n, 200)].astype(str).str.strip()
    date_hits = int(sample.str.match(DATE_PREFIX).sum())
    numeric_hits = int(pd.to_numeric(sample, errors="coerce").notna().sum())
    warnings: list[str] = []
    if date_hits >= max(3, math.ceil(len(sample) * .9)):
        warnings.append("Date-shaped text: dates have not been parsed or converted. Review locale and format.")
        return "date-like text", "At least 90% of up to 200 non-missing sample values resemble ISO-style dates. Stored as text.", warnings
    if numeric_hits >= max(3, math.ceil(len(sample) * .9)):
        warnings.append("Numeric-looking text: stored as text. Review separators, currency symbols and parsing.")
        return "numeric-like text", "At least 90% of up to 200 non-missing sample values parse as numbers. Stored as text.", warnings
    unique = int(observed.nunique())
    if unique <= 24 or unique <= max(2, round(n * .1)):
        return "categorical", "A bounded number of distinct labels; suitable for group counts.", warnings
    return "text", "Text or high-cardinality labels. Do not automatically treat as model categories.", warnings


def _metadata(series: pd.Series, name: str, rows: int) -> dict:
    missing = int(series.isna().sum())
    distinct = int(series.nunique(dropna=True))
    role, explanation, hints = _role(series)
    identifier = bool(IDENTIFIER_NAME.search(name)) and distinct >= max(3, math.ceil(rows * .8))
    if identifier:
        hints.append("Possible identifier: high distinctness and identifier-like name. Review before modelling.")
    if distinct == 1 and rows > 1:
        hints.append("Constant field: only one non-missing distinct value.")
    if missing == rows and rows > 0:
        hints.append("Completely missing field.")
    return {
        "name": name, "dtype": str(series.dtype), "role": role,
        "role_explanation": explanation, "rows": rows,
        "non_null": rows - missing, "missing": missing,
        "missing_pct": round(100 * missing / rows, 2) if rows else 0.0,
        "unique": distinct, "unique_pct": round(100 * distinct / (rows - missing), 2) if rows > missing else 0.0,
        "identifier_candidate": identifier, "warnings": hints,
    }


def overview(frame: pd.DataFrame, version: int) -> dict:
    if not frame.columns.is_unique:
        raise ValueError("Column investigation requires distinct field names")
    columns = [_metadata(frame[name], str(name), len(frame)) for name in frame.columns]
    return {
        "version": version, "rows": len(frame), "column_count": len(columns),
        "columns": columns,
        "role_counts": {role: sum(1 for item in columns if item["role"] == role)
                        for role in sorted({item["role"] for item in columns})},
        "note": "Stored pandas dtypes and heuristic analytical roles describe the current approved dataset version. No changes are applied."
    }


def detail(frame: pd.DataFrame, version: int, name: str) -> dict:
    if not frame.columns.is_unique:
        raise ValueError("Column investigation requires distinct field names")
    if name not in frame.columns:
        raise ValueError("Requested column not found in this working dataset")
    series = frame[name]
    meta = _metadata(series, name, len(frame))
    observed = series.dropna()
    examples = [_clean(value) for value in observed.drop_duplicates().head(MAX_EXAMPLES).tolist()]
    samples = [{"row_number": i + 1, "value": _clean(value), "missing": bool(pd.isna(value))}
               for i, value in enumerate(series.iloc[:MAX_SAMPLE_ROWS].tolist())]
    if meta["role"] in ("numeric",) and _numeric_dtype(series):
        numeric = pd.to_numeric(series, errors="coerce").replace([np.inf, -np.inf], np.nan).dropna()
        meta["invalid_or_nonfinite"] = int((series.notna() & ~pd.to_numeric(series, errors="coerce").replace([np.inf,-np.inf],np.nan).notna()).sum())
        if len(numeric):
            meta["statistics"] = {
                "count": int(len(numeric)),
                "min": _clean(numeric.min()), "q1": _clean(numeric.quantile(.25)),
                "median": _clean(numeric.median()), "mean": _clean(numeric.mean()),
                "q3": _clean(numeric.quantile(.75)), "max": _clean(numeric.max()),
                "std": _clean(numeric.std()) if len(numeric)>1 else None,
                "zero_count": int((numeric == 0).sum()),
                "negative_count": int((numeric < 0).sum()),
            }
        else:
            meta["statistics"] = None
        meta["distribution"] = []
    else:
        # Value counts can be large; return only a bounded top-10 summary,
        # with explicit non-missing denominator.
        counts = observed.astype(str).value_counts(dropna=False).head(MAX_TOP_VALUES)
        meta["distribution"] = [
            {"value": str(label)[:MAX_TEXT], "count": int(count),
             "pct": round(100 * int(count) / len(observed), 2) if len(observed) else 0.0}
            for label, count in counts.items()
        ]
        meta["statistics"] = None
        meta["invalid_or_nonfinite"] = 0
    return {
        "version": version, **meta, "examples": examples,
        "sample_rows": samples,
        "sample_note": f"First {len(samples)} rows in current working version; examples are first {len(examples)} distinct non-missing observed values.",
        "distribution_note": "Top observed labels; counts exclude missing values." if meta["distribution"]
                             else "Numerical distribution is described by min, quartiles, median and mean.",
    }
