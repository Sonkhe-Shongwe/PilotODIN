"""Bounded local diagnostics for Quality outlier and identifier findings.

Read-only. Uses the SAME finite-value Tukey rule and approved dataset version
as Quality's issue discovery and row preview. No automatic exclusions,
imputation, type coercions or data exports.
"""
from __future__ import annotations

import pandas as pd

from . import quality

MAX_EXAMPLE_ROWS = 40
MAX_TOP_GROUPS = 8


def inspect(project_id: str, issue_id: str, expected_version: int) -> dict:
    frame, version = quality.current_data(project_id)
    if version != expected_version:
        raise quality.QualityError("Working dataset changed. Refresh Quality before investigating findings.",409)
    issue = next((i for i in quality._issues(frame) if i["id"] == issue_id),None)
    if issue is None:
        raise quality.QualityError("Finding no longer exists in this approved version",404)
    col=issue["column"]
    if not col or issue["kind"] not in ("outliers","identifier"):
        raise quality.QualityError("Detailed investigation is currently available for outliers and identifiers only",422)
    series=frame[col]
    total=len(frame)
    common={
        "project_id":project_id,"version":version,"issue_id":issue_id,
        "kind":issue["kind"],"column":col,"stored_dtype":str(series.dtype),
        "dataset_rows":total,"affected_rows":issue["affected_rows"],
        "recommended_action":"Review records and domain expectations before choosing a treatment. No changes have been applied.",
    }
    if issue["kind"]=="outliers":
        profile=quality._outlier_profile(series)
        if not profile or not profile["outliers"]:
            raise quality.QualityError("This outlier finding is no longer valid",409)
        rows=frame.index[profile["mask"]].tolist()
        if len(rows)!=issue["affected_rows"]:
            raise quality.QualityError("Outlier detection disagrees with preview counts",409)
        finite=pd.to_numeric(series,errors="coerce").replace([float("inf"),float("-inf")],float("nan"))
        lower=int(finite.lt(profile["low"]).fillna(False).sum())
        upper=int(finite.gt(profile["high"]).fillna(False).sum())
        return {**common,"affected_row_numbers":[int(i)+1 for i in rows[:MAX_EXAMPLE_ROWS]],
                "shown_row_numbers":min(len(rows),MAX_EXAMPLE_ROWS),
                "statistical_method":"Tukey 1.5×IQR fences on finite numeric observations",
                "statistics":{
                    "q1":profile["q1"],"q3":profile["q3"],"iqr":profile["iqr"],
                    "lower_fence":profile["low"],"upper_fence":profile["high"],
                    "finite_observations":profile["finite_count"],
                    "excluded_nonfinite":profile["excluded_count"],
                    "median":profile["median"],"min":profile["min"],"max":profile["max"],
                    "below_lower_fence":lower,"above_upper_fence":upper
                },
                "warning":"Outliers may be genuine, important extreme values, returns or errors. The IQR rule is not proof of invalid data.",
                "suggested_reviews":[
                    "Inspect every flagged source record and confirm the measurement unit and valid domain.",
                    "Compare flagged values with business rules, other columns and original values.",
                    "Keep unusual but legitimate values; do not automatically delete or cap them."
                ]}
    present=series.dropna()
    unique=int(present.nunique())
    sampled=present.astype(str).str.slice(0,120).value_counts().head(MAX_TOP_GROUPS)
    return {**common,"affected_row_numbers":[int(i)+1 for i in frame.index[:MAX_EXAMPLE_ROWS]],
            "shown_row_numbers":min(total,MAX_EXAMPLE_ROWS),
            "statistical_method":"Distinct-value and identifier-name heuristic, not an enforced key constraint",
            "statistics":{
                "non_missing":int(series.notna().sum()),"missing":int(series.isna().sum()),
                "distinct":unique,
                "unique_pct":round(100*unique/len(present),2) if len(present) else 0.,
                "example_frequency":[{"label":str(k),"count":int(v)} for k,v in sampled.items()]
            },
            "warning":"A likely identifier is not necessarily erroneous. Uniqueness does not prove it is a primary key or safe to exclude.",
            "suggested_reviews":[
                "Check leading zeros, duplicates, blank values and whether identifiers encode a business entity.",
                "Determine whether this field creates target leakage or unhelpful memorisation in modelling.",
                "Preserve identifying fields for joins or traceability where appropriate; exclude only with review."
            ]}
