"""Macro A2: read-only, dataset-version-pinned linked analytics filters."""
import pandas as pd
import pytest

from backend import analytics, explore_filters, main


def fixture_frame():
    return pd.DataFrame({
        "ClaimID": [f"C{i:02d}" for i in range(8)],
        "Region": ["North", "South", "North", "South", "North", "South", "North", None],
        "Status": ["Open", "Open", "Closed", "Closed", "Open", "Closed", "Open", "Closed"],
        "ClaimAmount": [10, 20, 30, 40, 50, 60, 70, None],
        "SettledAmount": [1, 2, 3, 4, 5, 6, 7, None],
    })


def test_catalog_is_bounded_and_excludes_identifier_and_rows():
    response = explore_filters.catalog(fixture_frame(), 7)
    assert response["version"] == 7
    assert "ClaimID" not in {c["name"] for c in response["columns"]}
    region = next(c for c in response["columns"] if c["name"] == "Region")
    assert set(region["options"]) == {"North", "South"}
    assert all("rows" not in c for c in response["columns"])


def test_multiple_filters_use_intersection_with_inclusive_numeric_bounds():
    frame = fixture_frame()
    selected = explore_filters.apply(frame, [
        {"column": "Region", "op": "eq", "value": "North"},
        {"column": "ClaimAmount", "op": "range", "min": 30, "max": 70},
    ])
    assert selected["ClaimAmount"].tolist() == [30, 50, 70]
    chart = analytics.chart(selected, 7, "Region", kind="bar", aggregation="count")
    assert chart["data"][0]["value"] == 3
    matrix = analytics.correlation(selected, 7)
    pair = next(c for c in matrix["cells"]
                if c["x"] == "ClaimAmount" and c["y"] == "SettledAmount")
    assert pair["n"] == 3 and pair["r"] == 1.0


@pytest.mark.parametrize("clauses", [
    [{"column": "ClaimID", "op": "eq", "value": "C01"}],
    [{"column": "Missing", "op": "eq", "value": "North"}],
    [{"column": "Region", "op": "eq", "value": "Not a region"}],
    [{"column": "Region", "op": "eq", "value": "North"}] * 2,
    [{"column": "ClaimAmount", "op": "range", "min": 4, "max": 1}],
    [{"column": "ClaimAmount", "op": "range", "min": float("inf"), "max": 10}],
    [{"column": "ClaimAmount", "op": "range", "min": True, "max": 10}],
    [{"column": "Region", "op": "eq", "value": "North"}] * 5,
])
def test_invalid_filters_fail_closed(clauses):
    with pytest.raises(ValueError):
        explore_filters.apply(fixture_frame(), clauses)


def test_empty_subset_returns_zero_without_changing_source():
    original = fixture_frame()
    chosen = explore_filters.apply(original, [
        {"column": "Region", "op": "eq", "value": "South"},
        {"column": "ClaimAmount", "op": "range", "min": 70, "max": 70},
    ])
    assert chosen.empty and len(original) == 8


def test_workbench_is_version_pinned_and_returns_linked_counts(monkeypatch):
    frame = fixture_frame()
    monkeypatch.setattr(main, "project_or_404", lambda _: {"id": "demo"})
    monkeypatch.setattr(main.quality, "current_data", lambda _: (frame, 7))
    request = main.ExploreWorkbenchRequest(
        expected_version=7, x="ClaimAmount", kind="histogram", bins=8,
        filters=[main.ExploreFilterClause(column="Region", op="eq", value="North")]
    )
    response = main.explore_workbench("demo", request)
    assert response["total_rows"] == 8
    assert response["filtered_rows"] == 4
    assert response["overview"]["rows"] == 4
    assert response["chart"]["valid_observations"] == 4
    assert sum(item["value"] for item in response["chart"]["data"]) == 4
    assert response["correlation"]["version"] == 7
    assert len(frame) == 8
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc:
        main.explore_workbench("demo", request.model_copy(update={"expected_version": 6}))
    assert exc.value.status_code == 409

@pytest.mark.parametrize("empty", [False, True])
def test_explore_bootstrap_materializes_once_and_matches_legacy_results(monkeypatch, empty):
    frame = fixture_frame()
    if empty:
        frame = frame.iloc[:0]
    before = frame.copy(deep=True)
    reads = []
    monkeypatch.setattr(main, "project_or_404", lambda pid: {"id": pid})

    def current_data(pid):
        reads.append(pid)
        return frame, 7

    monkeypatch.setattr(main.quality, "current_data", current_data)
    result = main.explore_bootstrap("demo", 7)
    assert reads == ["demo"]
    assert set(result) == {"project_id", "version", "overview", "insights", "recommended", "filter_catalog"}
    assert result["project_id"] == "demo" and result["version"] == 7
    assert result["overview"] == main.explore_overview("demo")
    assert result["insights"] == main.explore_insights("demo")
    assert result["recommended"] == main.recommended_exploration("demo")
    assert result["filter_catalog"] == main.explore_filter_options("demo")
    assert all(result[name]["version"] == 7 for name in
               ("overview", "insights", "recommended", "filter_catalog"))
    pd.testing.assert_frame_equal(frame, before)


def test_explore_bootstrap_refuses_stale_before_calculation(monkeypatch):
    from fastapi import HTTPException
    monkeypatch.setattr(main, "project_or_404", lambda pid: {"id": pid})
    monkeypatch.setattr(main.quality, "current_data", lambda _: (fixture_frame(), 8))
    def forbidden(*args):
        pytest.fail("stale snapshot must not calculate")
    monkeypatch.setattr(main.analytics, "describe", forbidden)
    with pytest.raises(HTTPException) as exc:
        main.explore_bootstrap("demo", 7)
    assert exc.value.status_code == 409


@pytest.mark.parametrize("error", [
    main.quality.QualityError("Original source changed", 409),
    main.quality.QualityArchivedError("Project archived", 409),
])
def test_explore_bootstrap_preserves_snapshot_refusal(monkeypatch, error):
    from fastapi import HTTPException
    monkeypatch.setattr(main, "project_or_404", lambda pid: {"id": pid})
    def refuse(pid):
        raise error
    monkeypatch.setattr(main.quality, "current_data", refuse)
    with pytest.raises(HTTPException) as exc:
        main.explore_bootstrap("demo", 7)
    assert exc.value.status_code == error.status and exc.value.detail == str(error)


def test_explore_bootstrap_missing_project_does_not_materialize(monkeypatch):
    from fastapi import HTTPException
    monkeypatch.setattr(main.storage, "get_project", lambda _: None)
    def forbidden(*args):
        pytest.fail("missing project must not materialize")
    monkeypatch.setattr(main.quality, "current_data", forbidden)
    with pytest.raises(HTTPException) as exc:
        main.explore_bootstrap("missing", 7)
    assert exc.value.status_code == 404
