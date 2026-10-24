"""Bounded, read-only chart-to-record inspection on one filtered data snapshot.

Selection may only target rendered bar groups, histogram bins, or visible scatter
points. All references are ephemeral positions scoped to the approved dataset
version and the current filter list, not persistent IDs or cloud evidence.
"""
from __future__ import annotations

import math
from typing import Any

import numpy as np
import pandas as pd

try:
    from . import analytics
except ImportError:
    import analytics

MAX_INSPECT_ROWS = 25
MAX_DISPLAY_COLUMNS = 16
MAX_CELL_CHARS = 240


def _cell(value: Any) -> str | int | float | bool | None:
    if value is None:
        return None
    if isinstance(value, (pd.Timestamp,)):
        return value.isoformat()
    if isinstance(value, (np.integer, int)) and not isinstance(value, (bool, np.bool_)):
        return int(value)
    if isinstance(value, (np.floating, float)):
        return float(value) if math.isfinite(float(value)) else None
    if isinstance(value, (bool, np.bool_)):
        return bool(value)
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    return str(value)[:MAX_CELL_CHARS]


def inspect(
    frame: pd.DataFrame, version: int, *, x: str, y: str | None,
    kind: str, aggregation: str, bins: int,
    selection: dict[str, Any], offset: int = 0, limit: int = 12
) -> dict:
    if offset < 0 or not (1 <= limit <= MAX_INSPECT_ROWS):
        raise ValueError("Invalid inspector pagination")
    if not len(frame):
        raise ValueError("Nothing to inspect: no records match the active filters")
    plot = analytics.chart(frame, version, x, y, kind, aggregation, bins)
    chosen = selection.get("kind")
    if chosen == "category" and plot["type"] == "bar":
        label = selection.get("label")
        valid = {item["label"] for item in plot["data"]}
        if not isinstance(label, str) or label not in valid:
            raise ValueError("Select a visible chart category")
        column = frame[x].fillna("(Missing)").astype(str)
        positions = np.flatnonzero(column.eq(label).to_numpy())
        detail = f"Category {label} in {x}"
    elif chosen == "bin" and plot["type"] == "histogram":
        bin_index = selection.get("bin_index")
        if isinstance(bin_index, bool) or not isinstance(bin_index, int) or not (0 <= bin_index < len(plot["data"])):
            raise ValueError("Select a visible histogram interval")
        item = plot["data"][bin_index]
        numeric = pd.to_numeric(frame[x], errors="coerce").replace([np.inf, -np.inf], np.nan)
        mask = numeric.ge(item["start"]) & (numeric.le(item["end"]) if bin_index == len(plot["data"]) - 1 else numeric.lt(item["end"]))
        positions = np.flatnonzero(mask.to_numpy())
        detail = f"Histogram interval {item['label']} in {x}"
    elif chosen == "point" and plot["type"] == "scatter":
        row_ref = selection.get("row_ref")
        displayed = {item["row_ref"] for item in plot["data"]}
        if isinstance(row_ref, bool) or not isinstance(row_ref, int) or row_ref not in displayed:
            raise ValueError("Select a visible scatter point")
        positions = np.array([row_ref], dtype=int)
        detail = f"Selected point in {x} versus {y}"
    else:
        raise ValueError("This chart selection is not supported")
    total = int(len(positions))
    page = positions[offset:offset + limit]
    # Put inspected X and Y first, then bounded source columns. No arbitrary
    # full-data export and no implicit transfer to AI/cloud providers.
    ordered = list(dict.fromkeys([name for name in (x, y) if name in frame.columns] +
                                 [name for name in frame.columns]))
    columns = ordered[:MAX_DISPLAY_COLUMNS]
    indices = [frame.columns.get_loc(name) for name in columns]
    # Imported datasets normally have unique column names; enforce the contract
    # for manually constructed frames rather than selecting ambiguous fields.
    if not frame.columns.is_unique:
        raise ValueError("Record inspection requires unique field names")
    rows = []
    for ref in page:
        record = frame.iloc[int(ref)]
        rows.append({
            "filtered_row_number": int(ref) + 1,
            "cells": [_cell(record.iloc[int(pos)]) for pos in indices]
        })
    measure_count = total
    if y and plot["type"] == "bar":
        measure_count = int(pd.to_numeric(frame.iloc[positions][y], errors="coerce").notna().sum())
    return {
        "version": version, "selection_kind": chosen, "description": detail,
        "matched_rows": total, "measure_rows": measure_count,
        "offset": offset, "limit": limit, "columns": columns, "rows": rows,
        "truncated_columns": len(frame.columns) > len(columns),
        "note": "Read-only local preview. Row numbers refer to the current filtered snapshot, not permanent record IDs."
    }
