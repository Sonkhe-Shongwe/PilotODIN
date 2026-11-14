"""Macro A2: chart-to-record inspection uses visible marks and a pinned snapshot."""
from __future__ import annotations

import pandas as pd
import pytest
from fastapi import HTTPException

from backend import analytics, explore_inspector, explore_filters, main


def data():
    return pd.DataFrame({
        "ClaimID": ["A1", "A2", "A3", "A4", "A5", "A6", "A7"],
        "Region": ["North", "North", "South", "North", "South", None, "North"],
        "Amount": [10, 20, 30, 40, 50, None, 70],
        "Settled": [1, None, 3, 4, 5, None, 7],
    })


def inspect(df, *, x="Region", y=None, kind="bar", aggregation="count",
            selection=None, bins=4, offset=0, limit=12):
    return explore_inspector.inspect(
        df, 3, x=x, y=y, kind=kind, aggregation=aggregation,
        bins=bins, selection=selection or {"kind": "category", "label": "North"},
        offset=offset, limit=limit
    )


def test_category_inspection_matches_visible_group_and_returns_bounded_rows():
    frame = data()
    result = inspect(frame, limit=2)
    assert result["matched_rows"] == 4
    assert len(result["rows"]) == 2
    assert result["columns"][:2] == ["Region", "ClaimID"]
    assert result["rows"][0]["filtered_row_number"] == 1
    assert result["rows"][1]["filtered_row_number"] == 2
    page = inspect(frame, offset=2, limit=2)
    assert [r["filtered_row_number"] for r in page["rows"]] == [4, 7]
    assert len(frame) == 7


def test_category_with_count_measure_explains_all_rows_vs_valid_values():
    response = inspect(data(), x="Region", y="Settled", kind="bar")
    assert response["matched_rows"] == 4
    assert response["measure_rows"] == 3
    graph = analytics.chart(data(), 3, "Region", "Settled", "bar", "count")
    north = next(item for item in graph["data"] if item["label"] == "North")
    assert int(north["value"]) == response["measure_rows"]


def test_histogram_bin_matches_chart_count_including_last_right_edge():
    frame = data()
    plot = analytics.chart(frame, 3, "Amount", kind="histogram", bins=4)
    seen = []
    for i, group in enumerate(plot["data"]):
        records = inspect(frame, x="Amount", kind="histogram", bins=4,
                          selection={"kind": "bin", "bin_index": i})
        assert records["matched_rows"] == group["value"]
        seen.extend(row["filtered_row_number"] for row in records["rows"])
    assert sorted(seen) == [1, 2, 3, 4, 5, 7]


def test_only_rendered_sampled_scatter_points_have_inspectable_row_refs():
    frame = pd.DataFrame({"X": list(range(550)), "Y": list(range(550))})
    scatter = analytics.chart(frame, 2, "X", "Y", "scatter")
    assert scatter["sampled"] and len(scatter["data"]) == 500
    chosen = scatter["data"][0]
    response = explore_inspector.inspect(frame, 2, x="X", y="Y", kind="scatter",
               aggregation="mean", bins=8,
               selection={"kind": "point", "row_ref": chosen["row_ref"]})
    assert response["matched_rows"] == 1
    assert response["rows"][0]["cells"][:2] == [chosen["x"], chosen["y"]]
    absent = next(ref for ref in range(550) if ref not in {p["row_ref"] for p in scatter["data"]})
    with pytest.raises(ValueError, match="visible scatter point"):
        explore_inspector.inspect(frame, 2, x="X", y="Y", kind="scatter",
              aggregation="mean", bins=8,
              selection={"kind": "point", "row_ref": absent})


@pytest.mark.parametrize("kind,x,y,choice", [
    ("bar", "Region", None, {"kind": "category", "label": "Nonexistent"}),
    ("histogram", "Amount", None, {"kind": "bin", "bin_index": 1000}),
    ("bar", "Region", None, {"kind": "point", "row_ref": 1}),
    ("scatter", "Amount", "Settled", {"kind": "point", "row_ref": -2}),
    ("histogram", "Amount", None, {"kind": "bin", "bin_index": True}),
])
def test_invalid_or_incompatible_selections_fail_closed(kind, x, y, choice):
    with pytest.raises(ValueError):
        inspect(data(), kind=kind, x=x, y=y, selection=choice)


def test_api_rejects_stale_version_and_validates_filters_before_inspection(monkeypatch):
    frame = data()
    monkeypatch.setattr(main, "project_or_404", lambda _: {"id": "test"})
    monkeypatch.setattr(main.quality, "current_data", lambda _: (frame, 3))
    req = main.ExploreInspectRequest(
        expected_version=3, x="Amount", kind="histogram", bins=4,
        selection=main.ExploreInspectSelection(kind="bin", bin_index=0),
        filters=[main.ExploreFilterClause(column="Region", op="eq", value="North")]
    )
    value = main.explore_inspect("test", req)
    assert value["version"] == 3 and value["total_filtered_rows"] == 4
    assert value["matched_rows"] <= 4
    assert frame.shape == (7, 4)
    with pytest.raises(HTTPException) as e:
        main.explore_inspect("test", req.model_copy(update={"expected_version": 2}))
    assert e.value.status_code == 409
    bad = req.model_copy(update={
        "filters": [main.ExploreFilterClause(column="ClaimID", op="eq", value="A1")]
    })
    with pytest.raises(HTTPException) as e:
        main.explore_inspect("test", bad)
    assert e.value.status_code == 422


def test_cell_content_is_bounded_and_missing_values_are_explicit():
    frame = pd.DataFrame({"Category": ["A"], "Message": ["x" * 300],
                          "Value": [float("inf")]})
    result = inspect(frame, x="Category", selection={"kind": "category", "label": "A"})
    assert len(result["rows"][0]["cells"][2]) <= explore_inspector.MAX_CELL_CHARS if isinstance(result["rows"][0]["cells"][2], str) else True
    assert result["rows"][0]["cells"][1] == "x" * explore_inspector.MAX_CELL_CHARS
    assert result["rows"][0]["cells"][2] is None
