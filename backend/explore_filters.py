"""Validated, version-scoped filters for read-only Explore calculations.

No row contents are returned. Filters act on a temporary working-data snapshot
and never change Quality's approved dataset or ML model inputs.
"""
from __future__ import annotations

import math
import re
from typing import Any

import numpy as np
import pandas as pd

MAX_FILTERS = 4
MAX_CATEGORIES = 24
_IDENTIFIER = re.compile(r"(?:id|key|code|number)$", re.IGNORECASE)


def catalog(df: pd.DataFrame, version: int) -> dict:
    columns = []
    for name in df.columns:
        if _IDENTIFIER.search(str(name)):
            continue
        series = df[name]
        if pd.api.types.is_numeric_dtype(series) and not pd.api.types.is_bool_dtype(series):
            numeric = pd.to_numeric(series, errors="coerce").replace([np.inf, -np.inf], np.nan).dropna()
            if len(numeric):
                lower, upper = float(numeric.min()), float(numeric.max())
                if math.isfinite(lower) and math.isfinite(upper):
                    columns.append({"name": name, "kind": "numeric", "min": lower,
                                    "max": upper, "missing": int(series.isna().sum())})
        else:
            unique = int(series.nunique(dropna=True))
            if 0 < unique <= MAX_CATEGORIES:
                values = series.dropna().astype(str).value_counts()
                # Display only bounded categorical options. Never send full data rows.
                columns.append({"name": name, "kind": "categorical",
                                "options": [str(v) for v in values.index[:MAX_CATEGORIES]],
                                "missing": int(series.isna().sum())})
    return {"version": version, "columns": columns, "max_filters": MAX_FILTERS,
            "note": "Filters apply to live charts, statistics and correlation; source data stays unchanged."}


def apply(df: pd.DataFrame, filters: list[dict[str, Any]]) -> pd.DataFrame:
    if len(filters) > MAX_FILTERS:
        raise ValueError(f"No more than {MAX_FILTERS} filters can be applied")
    allowed = {item["name"]: item for item in catalog(df, 0)["columns"]}
    seen: set[str] = set()
    mask = pd.Series(True, index=df.index, dtype=bool)
    for item in filters:
        name = item.get("column")
        if not isinstance(name, str) or name not in allowed or name in seen:
            raise ValueError("Filter column is unavailable or repeated")
        seen.add(name)
        spec = allowed[name]
        operator = item.get("op")
        if spec["kind"] == "categorical":
            value = item.get("value")
            if operator != "eq" or not isinstance(value, str) or value not in spec["options"]:
                raise ValueError("Choose an available categorical value")
            mask &= df[name].notna() & df[name].astype(str).eq(value)
        elif spec["kind"] == "numeric":
            if operator != "range":
                raise ValueError("Numeric filters require an inclusive range")
            low, high = item.get("min"), item.get("max")
            if any(isinstance(n, bool) or not isinstance(n, (int, float)) or not math.isfinite(n)
                   for n in (low, high)) or low > high:
                raise ValueError("Enter a finite numerical range with minimum <= maximum")
            numeric = pd.to_numeric(df[name], errors="coerce").replace([np.inf, -np.inf], np.nan)
            mask &= numeric.ge(low) & numeric.le(high)
    return df.loc[mask].copy()
