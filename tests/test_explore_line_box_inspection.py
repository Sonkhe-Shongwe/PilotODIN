"""Source-linked line/box marks: finite-value counts and fail-closed inspection.

No raw row IDs are persisted; inspected records refer to the current filtered,
approved dataset version. Choosing a hidden group or non-rendered outlier fails.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from fastapi import HTTPException

from backend import analytics, explore_inspector, main


def inspect(df, *, x, y=None, kind, choice, aggregation="mean"):
    return explore_inspector.inspect(
        df, 7, x=x, y=y, kind=kind, aggregation=aggregation,
        bins=12, selection=choice, limit=12, offset=0
    )


def test_line_chart_discloses_finite_measure_denominator_and_keeps_missing_x_group():
    frame=pd.DataFrame({
        "Region":["North","North","South",None,"South",None],
        "Amount":[10.0,float("inf"),20.0,30.0,np.nan,float("-inf")],
        "ClaimID":["A","B","C","D","E","F"],
    })
    chart=analytics.chart(frame,7,"Region","Amount","line","sum")
    assert chart["valid_observations"]==3
    assert chart["excluded_observations"]==3
    assert {p["label"]:p["value"] for p in chart["data"]}=={
        "(Missing)":30.0,"North":10.0,"South":20.0
    }
    for point in chart["data"]:
        result=inspect(frame,x="Region",y="Amount",kind="line",
                       choice={"kind":"line_category","label":point["label"]},
                       aggregation="sum")
        assert result["matched_rows"]==1
        assert result["measure_rows"]==1
        assert result["rows"][0]["cells"][1]==point["value"]
    assert sum(inspect(frame,x="Region",y="Amount",kind="line",
           choice={"kind":"line_category","label":p["label"]},aggregation="sum")["matched_rows"]
           for p in chart["data"])==chart["valid_observations"]


def test_tukey_outlier_marks_and_inlier_actions_match_actual_record_counts():
    frame=pd.DataFrame({
        "Amount":[float(100+i%7) for i in range(35)]+[800.0,800.0,np.nan,float("inf")],
        "CustomerID":[f"C-{i}" for i in range(39)]
    })
    original=frame.copy(deep=True)
    chart=analytics.chart(frame,7,"Amount",kind="box")
    point=chart["data"][0]
    assert point["outliers_total"]==2 and point["outliers"]==[800.,800.]
    all_out=inspect(frame,x="Amount",kind="box",choice={"kind":"box_outliers"})
    one_out=inspect(frame,x="Amount",kind="box",
                    choice={"kind":"box_outlier","value":point["outliers"][0]})
    inliers=inspect(frame,x="Amount",kind="box",choice={"kind":"box_inliers"})
    assert all_out["matched_rows"]==one_out["matched_rows"]==2
    assert [row["filtered_row_number"] for row in all_out["rows"]]==[36,37]
    assert len(inliers["rows"])==12 and inliers["matched_rows"]==35
    assert all_out["matched_rows"]+inliers["matched_rows"]==37
    assert original.equals(frame)


def test_ineligible_chart_selections_fail_closed():
    frame=pd.DataFrame({"Region":["A","A","B"],"Amount":[10.,20.,30.]})
    with pytest.raises(ValueError,match="visible line-chart group"):
        inspect(frame,x="Region",y="Amount",kind="line",
                choice={"kind":"line_category","label":"NOT_VISIBLE"})
    with pytest.raises(ValueError):
        inspect(frame,x="Region",y="Amount",kind="line",
                choice={"kind":"box_outliers"})
    with pytest.raises(ValueError):
        inspect(frame,x="Amount",kind="box",
                choice={"kind":"box_outlier","value":12345.})
    with pytest.raises(ValueError):
        inspect(frame,x="Amount",kind="box",
                choice={"kind":"box_outlier","value":float("inf")})


def test_line_group_limit_prevents_unseen_group_inspection():
    frame=pd.DataFrame({"Group":[f"G{i:03d}" for i in range(120)],
                        "Value":list(range(120))})
    chart=analytics.chart(frame,7,"Group","Value","line","count")
    assert chart["sampled"] and len(chart["data"])==80
    unseen=next(name for name in frame["Group"] if name not in {row["label"] for row in chart["data"]})
    with pytest.raises(ValueError,match="visible line-chart group"):
        inspect(frame,x="Group",y="Value",kind="line",
                choice={"kind":"line_category","label":unseen},aggregation="count")


def test_api_enforces_current_dataset_version_and_valid_selection(monkeypatch):
    frame=pd.DataFrame({"Region":["A","B"],"Amount":[2.,3.]})
    monkeypatch.setattr(main,"project_or_404",lambda _:{"id":"local"})
    monkeypatch.setattr(main.quality,"current_data",lambda _: (frame,7))
    req=main.ExploreInspectRequest(
        expected_version=7,x="Region",y="Amount",kind="line",
        selection=main.ExploreInspectSelection(kind="line_category",label="A")
    )
    assert main.explore_inspect("local",req)["matched_rows"]==1
    with pytest.raises(HTTPException) as exc:
        main.explore_inspect("local",req.model_copy(update={"expected_version":6}))
    assert exc.value.status_code==409
    rejected=req.model_copy(update={"selection":main.ExploreInspectSelection(kind="line_category",label="Z")})
    with pytest.raises(HTTPException) as exc:
        main.explore_inspect("local",rejected)
    assert exc.value.status_code==422
