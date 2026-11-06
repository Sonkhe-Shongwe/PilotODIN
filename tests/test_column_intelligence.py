"""Current-version Data Dictionary and read-only column investigation gates."""
import pandas as pd
import numpy as np
import pytest
from fastapi import HTTPException
from backend import column_intelligence, main


def frame():
    return pd.DataFrame({
        "ClaimID": ["C-1", "C-2", "C-3", "C-4", "C-5"],
        "Amount": [10.0, -5.0, 0.0, float("inf"), np.nan],
        "Status": ["Open", "Closed", "Open", "Open", None],
        "ClaimDate": ["2026-01-01", "2026-01-02", "2026-01-03", "2026-01-04", None],
        "AmountText": ["100", "200", "300", "400", None],
        "TrueDate": pd.to_datetime(["2026-01-01","2026-01-02","2026-01-03","2026-01-04",None]),
        "Boolean": [True, False, True, False, False],
    })


def test_complete_data_dictionary_reports_real_storage_types_and_assumptions():
    result=column_intelligence.overview(frame(), 4)
    assert result["version"] == 4 and result["column_count"]==7
    mapping={c["name"]:c for c in result["columns"]}
    assert mapping["Amount"]["dtype"].startswith("float")
    assert mapping["Amount"]["role"]=="numeric"
    assert mapping["Status"]["role"]=="categorical"
    assert mapping["ClaimDate"]["role"]=="date-like text"
    assert mapping["AmountText"]["role"]=="numeric-like text"
    assert mapping["TrueDate"]["role"]=="datetime"
    assert mapping["Boolean"]["role"]=="boolean"
    assert mapping["ClaimID"]["identifier_candidate"]
    assert "not been parsed" in " ".join(mapping["ClaimDate"]["warnings"])


def test_numeric_details_are_finite_correct_and_non_mutating():
    df=frame()
    original=df["Amount"].copy()
    result=column_intelligence.detail(df, 4, "Amount")
    assert result["rows"]==5 and result["non_null"]==4
    assert result["invalid_or_nonfinite"]==1
    stats=result["statistics"]
    assert stats["count"]==3 and stats["min"]==-5.0 and stats["max"]==10.0
    assert stats["negative_count"]==1 and stats["zero_count"]==1
    assert stats["median"]==0
    assert result["sample_rows"][3]["value"] is None
    assert result["sample_rows"][4]["missing"] is True
    assert df["Amount"].equals(original)


def test_categorical_frequency_counts_exclude_missing_and_are_bounded():
    result=column_intelligence.detail(frame(), 4, "Status")
    assert result["missing"]==1
    assert result["distribution"][0]["value"]=="Open"
    assert result["distribution"][0]["count"]==3
    assert result["distribution"][0]["pct"]==75.0
    assert len(result["examples"])<=8
    assert len(result["sample_rows"])<=12


def test_all_missing_and_empty_frame_do_not_divide_by_zero():
    result=column_intelligence.detail(pd.DataFrame({"Empty":[None,None]}), 0, "Empty")
    assert result["role"]=="unknown" and result["missing_pct"]==100
    no_rows=column_intelligence.overview(pd.DataFrame({"Nothing":pd.Series([],dtype="object")}), 2)
    assert no_rows["rows"]==0 and no_rows["columns"][0]["missing_pct"]==0


def test_values_are_truncated_and_no_unrelated_row_fields_leak():
    df=pd.DataFrame({"Sensitive":["x"*300], "Other":["SECRET"]})
    detail=column_intelligence.detail(df,1,"Sensitive")
    assert detail["examples"]==["x"*160]
    assert detail["sample_rows"][0]["value"]=="x"*160
    assert "SECRET" not in str(detail)


def test_current_version_endpoint_refuses_stale_column_requests(monkeypatch):
    monkeypatch.setattr(main,"project_or_404",lambda _: {"id":"p"})
    monkeypatch.setattr(main.quality,"current_data",lambda _: (frame(), 4))
    overview=main.column_investigation_overview("p")
    assert overview["version"]==4
    selected=main.column_investigation_detail("p",name="Amount",expected_version=4)
    assert selected["version"]==4 and selected["name"]=="Amount"
    with pytest.raises(HTTPException) as exc:
        main.column_investigation_detail("p",name="Amount",expected_version=3)
    assert exc.value.status_code==409
    with pytest.raises(HTTPException) as exc:
        main.column_investigation_detail("p",name="MadeUp",expected_version=4)
    assert exc.value.status_code==422
