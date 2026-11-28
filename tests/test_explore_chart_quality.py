"""Truthful quantitative chart regression."""
import pandas as pd
from backend import analytics

def test_histogram_coordinates_counts_and_exclusions():
    plot=analytics.chart(pd.DataFrame({"Amount":[0,1,2,3,4,5,6,7,8,9,None]}),0,"Amount",kind="histogram",bins=8)
    assert sum(b["value"] for b in plot["data"])==10
    assert plot["valid_observations"]==10 and plot["excluded_observations"]==1
    assert all(x["start"]<=x["end"] for x in plot["data"])

def test_box_whiskers_exclude_true_outliers():
    plot=analytics.chart(pd.DataFrame({"Amount":[float(10+i%7) for i in range(30)]+[500]}),0,"Amount",kind="box")
    r=plot["data"][0]
    assert r["max"]==500 and r["whisker_high"]<500
    assert r["outliers_total"]==1 and r["outliers"]==[500]
