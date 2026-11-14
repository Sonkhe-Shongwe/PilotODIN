"""Pairwise correlation is computed locally on eligible non-ID columns."""
import pandas as pd
from backend import analytics

def test_correlations_support_pearson_and_spearman():
    frame=pd.DataFrame({"TransactionID":["x1","x2","x3","x4","x5"],
                        "Amount":[1,2,3,4,5],"Units":[10,20,30,40,50],"Constant":[2]*5})
    for method in ("pearson","spearman"):
        result=analytics.correlation(frame,3,method)
        assert "TransactionID" not in result["columns"]
        assert result["version"]==3
        perfect=next(x for x in result["cells"] if x["x"]=="Amount" and x["y"]=="Units")
        assert perfect["r"]==1 and perfect["n"]==5
        constant=next(x for x in result["cells"] if x["x"]=="Amount" and x["y"]=="Constant")
        assert constant["r"] is None

def test_correlations_use_pairwise_valid_counts_and_reject_unknown_method():
    import pytest
    frame=pd.DataFrame({"A":[1,2,3,4],"B":[1,None,3,4]})
    result=analytics.correlation(frame,0,"pearson")
    point=next(x for x in result["cells"] if x["x"]=="A" and x["y"]=="B")
    assert point["n"]==3
    with pytest.raises(ValueError,match="Pearson"):
        analytics.correlation(frame,0,"malicious")
