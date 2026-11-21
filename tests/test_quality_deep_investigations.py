"""Quality investigations: affected-row alignment, non-finite values and version safety."""
from pathlib import Path

import pandas as pd
from fastapi.testclient import TestClient

from backend.main import app
from backend import quality, storage

client=TestClient(app)


def make_project(name="quality_deep.csv"):
    df=pd.DataFrame({
        "CustomerID": [f"{i:06d}" for i in range(35)]+[None],
        "Amount": [float(100+i%7) for i in range(35)]+[1200.0],
        "Segment": ["Retail" if i%2 else "Business" for i in range(36)]
    })
    raw=df.to_csv(index=False).encode("utf-8")
    response=client.post("/api/projects",files={"file":(name,raw,"text/csv")})
    assert response.status_code==201,response.text
    return response.json()["id"],raw


def finding(pid,kind):
    response=client.get(f"/api/projects/{pid}/quality")
    assert response.status_code==200,response.text
    return next(item for item in response.json()["issues"] if item["kind"]==kind)


def test_outlier_diagnostics_and_paginated_preview_reference_exact_same_rows():
    pid,original=make_project()
    issue=finding(pid,"outliers")
    assert issue["column"]=="Amount" and issue["affected_rows"]==1
    response=client.get(f"/api/projects/{pid}/quality/investigate",
                        params={"issue_id":issue["id"],"expected_version":0})
    assert response.status_code==200,response.text
    details=response.json()
    assert details["kind"]=="outliers" and details["affected_rows"]==1
    assert details["affected_row_numbers"]==[36]
    assert details["statistics"]["above_upper_fence"]==1
    assert details["statistics"]["below_lower_fence"]==0
    preview=client.get(f"/api/projects/{pid}/quality/preview",
                       params={"issue_id":issue["id"],"offset":0,"limit":12,"expected_version":0})
    assert preview.status_code==200,preview.text
    view=preview.json()
    assert view["total_matching_rows"]==issue["affected_rows"]==1
    assert [row["row_number"] for row in view["rows"]]==details["affected_row_numbers"]
    assert view["rows"][0]["working"]["Amount"]==1200.
    assert view["rows"][0]["original"]["Amount"]==1200.
    assert Path(storage.get_project(pid)["dataset_path"]).read_bytes()==original
    empty_page=client.get(f"/api/projects/{pid}/quality/preview",
         params={"issue_id":issue["id"],"offset":12,"limit":12,"expected_version":0})
    assert empty_page.status_code==200
    assert empty_page.json()["total_matching_rows"]==1 and not empty_page.json()["rows"]


def test_identifier_investigation_includes_blank_keys_and_preserves_leading_zeros():
    pid,raw=make_project("identifiers.csv")
    issue=finding(pid,"identifier")
    assert issue["column"]=="CustomerID"
    response=client.get(f"/api/projects/{pid}/quality/investigate",
                        params={"issue_id":issue["id"],"expected_version":0})
    assert response.status_code==200,response.text
    result=response.json()
    assert result["kind"]=="identifier" and result["affected_rows"]==36
    assert result["statistics"]["missing"]==1
    assert result["statistics"]["non_missing"]==35
    assert result["statistics"]["distinct"]==35
    assert result["affected_row_numbers"][:3]==[1,2,3]
    prev=client.get(f"/api/projects/{pid}/quality/preview",
                    params={"issue_id":issue["id"],"offset":24,"limit":12,"expected_version":0})
    assert prev.status_code==200,prev.text
    assert prev.json()["total_matching_rows"]==issue["affected_rows"]==36
    assert prev.json()["rows"][0]["working"]["CustomerID"]=="000024"
    assert prev.json()["rows"][-1]["working"]["CustomerID"] is None
    assert Path(storage.get_project(pid)["dataset_path"]).read_bytes()==raw


def test_nonfinite_outlier_threshold_rule_and_counts_are_consistent():
    values=[float(100+i%7) for i in range(35)]+[float("inf"),1200.0]
    df=pd.DataFrame({"Amount":values})
    profile=quality._outlier_profile(df["Amount"])
    assert profile is not None and profile["outliers"]==1
    assert profile["excluded_count"]==1
    assert profile["finite_count"]==36
    assert df.index[profile["mask"]].tolist()==[36]
    issue=next(x for x in quality._issues(df) if x["kind"]=="outliers")
    assert issue["affected_rows"]==int(profile["mask"].sum())==1
    assert issue["evidence"]["excluded_nonfinite"]==1
    assert pd.api.types.is_numeric_dtype(df["Amount"])


def test_stale_or_unknown_finding_is_refused_not_recalculated():
    pid,_=make_project("stale-version.csv")
    issue=finding(pid,"outliers")
    base=f"/api/projects/{pid}/quality"
    for endpoint in [f"{base}/investigate?issue_id={issue['id']}&expected_version=1",
                     f"{base}/preview?issue_id={issue['id']}&expected_version=1"]:
        response=client.get(endpoint)
        assert response.status_code==409,response.text
    missing=client.get(f"{base}/investigate?issue_id=not-a-finding&expected_version=0")
    assert missing.status_code==404
    unknown=client.get(f"{base}/preview?issue_id=not-a-finding&expected_version=0")
    assert unknown.status_code==404
