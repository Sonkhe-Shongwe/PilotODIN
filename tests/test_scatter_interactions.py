"""Macro A2 scatter: verified grouping, counts, sampling and record linkage."""
from collections import Counter
import pandas as pd
import pytest
from backend import analytics, explore_inspector


def sample():
    return pd.DataFrame({
        "Amount": [10.,20.,30.,40.,50.,60.,70.,float("nan")],
        "Loss": [1.,2.,3.,4.,5.,6.,7.,8.],
        "Segment": ["Retail","Enterprise","Retail",None,"Enterprise","Retail","Retail","Retail"],
        "ClaimID": [f"c{i}" for i in range(8)]
    })


def test_group_colors_only_non_identifier_categories_without_changing_paired_counts():
    df=sample()
    result=analytics.chart(df,2,"Amount","Loss","scatter",color_by="Segment")
    assert result["color_by"]=="Segment"
    assert result["valid_observations"]==7 and result["excluded_observations"]==1
    actual=Counter(p["group"] for p in result["data"])
    assert actual=={"Retail":4,"Enterprise":2,"(Missing)":1}
    assert {c["label"]:c["count"] for c in result["color_groups"]}==dict(actual)
    for point in result["data"]:
        response=explore_inspector.inspect(df,2,x="Amount",y="Loss",kind="scatter",aggregation="mean",bins=12,selection={"kind":"point","row_ref":point["row_ref"]})
        assert response["rows"][0]["cells"][:2]==[point["x"],point["y"]]


def test_scatter_group_500_sample_is_deterministic_and_counts_displayed_only():
    df=pd.DataFrame({"X":list(range(600)),"Y":list(range(600)),
        "Group":["A" if i%2 else "B" for i in range(600)]})
    one=analytics.chart(df,0,"X","Y","scatter",color_by="Group")
    two=analytics.chart(df,0,"X","Y","scatter",color_by="Group")
    assert one["sampled"] and one["valid_observations"]==600
    assert one["data"]==two["data"]
    assert len(one["data"])==500
    assert sum(q["count"] for q in one["color_groups"])==500


@pytest.mark.parametrize("field",["ClaimID","Amount","Loss","Unknown"])
def test_reject_inappropriate_scatter_colour_group(field):
    with pytest.raises(ValueError):
        analytics.chart(sample(),0,"Amount","Loss","scatter",color_by=field)


def test_reject_high_cardinality_group_and_colour_on_non_scatter():
    df=pd.DataFrame({"X":list(range(11)),"Y":list(range(11)),"Many":[f"value-{i}" for i in range(11)]})
    with pytest.raises(ValueError):
        analytics.chart(df,0,"X","Y","scatter",color_by="Many")
    with pytest.raises(ValueError):
        analytics.chart(sample(),0,"Segment",kind="bar",color_by="ClaimID")


def test_colouring_preserves_missing_group_from_valid_numeric_pairs():
    out=analytics.chart(sample(),0,"Amount","Loss","scatter",color_by="Segment")
    assert any(p["group"]=="(Missing)" for p in out["data"])
    assert out["note"].lower().find("causation")>=0
