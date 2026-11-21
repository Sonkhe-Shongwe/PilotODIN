"""Explore must not merge null categories with real strings named '(Missing)'.

Group labels are presentation values, not source column values or permanent IDs.
The same local chart and inspector semantics apply across bar, line, and scatter.
"""
from __future__ import annotations

import pandas as pd

from backend import analytics, explore_inspector


def inspect(frame,kind,selection,*,y=None,aggregation="count",color_by=None):
    return explore_inspector.inspect(
        frame,4,x="Segment",y=y,kind=kind,aggregation=aggregation,
        bins=8,selection=selection,offset=0,limit=12
    )


def collision_frame():
    return pd.DataFrame({
        "Segment":[None,"(Missing)","Retail",None,"(Missing)","(Missing values)"],
        "Revenue":[5.,11.,13.,7.,17.,19.],
        "Profit":[1.,2.,3.,4.,5.,6.]
    })


def test_collision_avoids_all_observed_category_strings_deterministically():
    frame=collision_frame()
    labels=analytics.category_labels(frame["Segment"])
    synthetic=labels.iloc[0]
    assert synthetic==labels.iloc[3]
    assert synthetic not in {"(Missing)","(Missing values)"}
    assert labels.iloc[1]=="(Missing)" and labels.iloc[5]=="(Missing values)"
    assert analytics.category_labels(frame["Segment"]).equals(labels)


def test_category_counts_and_inspected_row_sets_remain_distinct():
    frame=collision_frame()
    plot=analytics.chart(frame,4,"Segment",kind="bar")
    counts={r["label"]:r["value"] for r in plot["data"]}
    null_label=analytics.category_labels(frame["Segment"]).iloc[0]
    assert counts[null_label]==2 and counts["(Missing)"]==2
    assert counts["(Missing values)"]==1 and counts["Retail"]==1
    rows={}
    for item in plot["data"]:
        result=inspect(frame,"bar",{"kind":"category","label":item["label"]})
        assert result["matched_rows"]==item["value"]
        rows[item["label"]]={r["filtered_row_number"] for r in result["rows"]}
    assert rows[null_label]=={1,4}
    assert rows["(Missing)"]=={2,5}
    assert rows["(Missing values)"]=={6}
    assert set.union(*rows.values())==set(range(1,7))


def test_line_group_and_inspection_use_identical_null_safe_labels():
    frame=collision_frame()
    plot=analytics.chart(frame,4,"Segment","Revenue","line","sum")
    null_label=analytics.category_labels(frame["Segment"]).iloc[0]
    observed={d["label"]:d["value"] for d in plot["data"]}
    assert observed[null_label]==12.
    assert observed["(Missing)"]==28.
    for item in plot["data"]:
        result=inspect(frame,"line",{"kind":"line_category","label":item["label"]},y="Revenue",aggregation="sum")
        amounts=[float(r["cells"][1]) for r in result["rows"]]
        assert sum(amounts)==item["value"]


def test_scatter_legends_disclose_missing_and_real_missing_label_separately():
    frame=collision_frame()
    plot=analytics.chart(frame,4,"Revenue","Profit","scatter",color_by="Segment")
    labels={d["group"] for d in plot["data"]}
    synthetic=analytics.category_labels(frame["Segment"]).iloc[0]
    assert synthetic in labels and "(Missing)" in labels and "(Missing values)" in labels
    assert sum(group["count"] for group in plot["color_groups"])==6
