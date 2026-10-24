"""Non-AI correctness acceptance."""
import pandas as pd
import pytest
from backend import engine
from fastapi.testclient import TestClient
from backend.main import app


class Dummy:
    named_steps={"model": object()}
    def predict(self, rows):
        return ["Yes"]


def test_predicted_clock_hour_and_count_domains():
    schema=[{"name":"HourOfDay","kind":"number","min":0,"max":23},
            {"name":"TransactionsInLastHour","kind":"number","min":0,"max":11}]
    for h in (25,-1,9.25):
        with pytest.raises(ValueError,match="HourOfDay"):
            engine.predict_one(Dummy(),schema,{"HourOfDay":h,"TransactionsInLastHour":3})
    for count in (-1,2.75):
        with pytest.raises(ValueError,match="TransactionsInLastHour"):
            engine.predict_one(Dummy(),schema,{"HourOfDay":9,"TransactionsInLastHour":count})
    assert engine.predict_one(Dummy(),schema,{"HourOfDay":9,"TransactionsInLastHour":13})["prediction"]=="Yes"


def test_outlier_preview_shows_outliers_not_all_rows():
    client=TestClient(app)
    data=pd.DataFrame({"RecordID":[f"REC{i:03d}" for i in range(30)],"Amount":[float(10+i%7) for i in range(29)]+[2000.0]})
    response=client.post("/api/projects",files={"file":("outliers.csv",data.to_csv(index=False).encode(),"text/csv")})
    assert response.status_code==201,response.text
    pid=response.json()["id"]
    state=client.get(f"/api/projects/{pid}/quality").json()
    item=next(q for q in state["issues"] if q["kind"]=="outliers" and q["column"]=="Amount")
    preview=client.get(f"/api/projects/{pid}/quality/preview",params={"issue_id":item["id"]}).json()
    assert preview["total_matching_rows"]==1
    assert preview["rows"][0]["working"]["Amount"]==2000.0
