"""A4 regression: project-scoped selected-model metrics become report evidence safely.

Synthetic stored results mirror the existing A3 schema. No model job, bundled
inference or external user project is required. Report snapshots must contain
verified aggregate diagnostics but never individual holdout predictions.
"""
from __future__ import annotations

import json

from fastapi.testclient import TestClient
import fitz

from backend.main import app
from backend import storage

client = TestClient(app)
SECRET = "ROW_PRIVATE_CANARY_NEVER_REPORT"


def project(name: str) -> str:
    dataset = b"OrderID,Revenue,Flagged\n0001,20,Y\n0002,35,N\n0003,40,N\n"
    response = client.post("/api/projects", files={
        "file": (name, dataset, "text/csv")
    })
    assert response.status_code == 201, response.text
    return response.json()["id"]


def seeded_evaluation(pid: str, task: str = "classification",
                      selected: bool = True) -> str:
    config = {
        "target": "Flagged" if task == "classification" else "Revenue",
        "task": task, "excluded": ["OrderID"],
        "models": ["logistic" if task == "classification" else "ridge"],
        "quality_version": 0, "split_strategy": "random", "split_column": None,
    }
    eid = storage.new_experiment(pid, config)
    model = config["models"][0]
    storage.mark(eid, "completed", {
        "task": task, "models": [{"key": model, "status": "ready", "cv_metric": 0.7}],
        "test_rows": 30, "baseline_cv": 0.4,
    })
    if selected:
        final = {
            "target": config["target"], "sample_count": 30,
            "baseline_test_metric": 0.42,
            "baseline_test_label": "Macro F1" if task == "classification" else "MAE",
            "evaluation_rows": [{"actual": SECRET, "predicted": SECRET}],
            "reliability": {"level": "warning", "message": "Review before deployment.",
                            "issues": ["Review validation and deployment setting."]},
        }
        if task == "classification":
            final.update({
                "accuracy": 0.82, "f1_macro": 0.73,
                "precision_macro": 0.76, "recall_macro": 0.72,
                "class_report": [{"label": "Y", "precision": 0.61,
                                  "recall": 0.53, "f1": 0.57, "support": 12}],
                "confusion_matrix": [[12, 3], [7, 8]],
            })
        else:
            final.update({"mae": 5.25, "rmse": 7.75, "r2": -0.2})
        assert storage.select_model(eid, model, final)
    return eid


def save(pid: str, ids: list[str]):
    return client.post(f"/api/projects/{pid}/reports", json={
        "title": "Selected Model Performance",
        "narrative": "Interpret the holdout findings conservatively.",
        "evidence_ids": ids,
    })


def test_model_evaluation_is_available_only_after_selection_and_reported_without_rows():
    pid = project("model-report.csv")
    unfinished = seeded_evaluation(pid, selected=False)
    eid = seeded_evaluation(pid)
    options = client.get(f"/api/projects/{pid}/report-evidence")
    assert options.status_code == 200, options.text
    assert any(o["id"] == eid and o["operation"] == "model_evaluation" for o in options.json())
    assert not any(o["id"] == unfinished for o in options.json())
    assert save(pid, [unfinished]).status_code == 403

    reply = save(pid, [eid])
    assert reply.status_code == 201, reply.text
    report = reply.json()
    assert report["dataset_versions"] == [0]
    evidence = report["evidence"][0]
    assert evidence["id"] == eid
    assert evidence["operation"] == "model_evaluation"
    assert evidence["result"]["summary"]["Held-out accuracy (fraction)"] == 0.82
    assert evidence["result"]["data"][0]["support"] == 12
    assert SECRET not in json.dumps(report)
    assert "evaluation_rows" not in json.dumps(report)
    assert "confusion_matrix" not in json.dumps(report)
    assert "Review validation" in json.dumps(report)

    html = client.get(f"/api/reports/{report['id']}/export/html")
    pdf = client.get(f"/api/reports/{report['id']}/export/pdf")
    assert html.status_code == 200 and pdf.status_code == 200
    pdf_text = " ".join(page.get_text() for page in fitz.open(
        stream=pdf.content, filetype="pdf"))
    for visible in ("Selected Model Performance", "0.82", "0.73", "0.53"):
        assert visible in html.text and visible in pdf_text
    assert SECRET not in html.text and SECRET not in pdf_text
    assert "evaluation_rows" not in html.text and "evaluation_rows" not in pdf_text


def test_saved_model_report_snapshot_survives_later_source_mutation():
    pid = project("frozen-model-report.csv")
    eid = seeded_evaluation(pid)
    saved = save(pid, [eid]).json()
    url = f"/api/reports/{saved['id']}/export/html?revision=1"
    original_bytes = client.get(url).content
    with storage.connect() as con:
        con.execute("UPDATE experiments SET final_results=? WHERE id=?", (
            json.dumps({"target": "Flagged", "f1_macro": 0.01}), eid))
    again = client.get(f"/api/reports/{saved['id']}?revision=1").json()
    assert again["content_sha256"] == saved["content_sha256"]
    assert again["evidence"] == saved["evidence"]
    assert client.get(url).content == original_bytes


def test_model_evidence_never_crosses_project_boundary():
    first = project("model-project-A.csv")
    second = project("model-project-B.csv")
    eid = seeded_evaluation(first)
    assert save(second, [eid]).status_code == 403
    options = client.get(f"/api/projects/{second}/report-evidence").json()
    assert not any(o["id"] == eid for o in options)


def test_regression_metrics_have_correct_meaning():
    pid = project("regression-model-report.csv")
    eid = seeded_evaluation(pid, "regression")
    report = save(pid, [eid])
    assert report.status_code == 201, report.text
    summary = report.json()["evidence"][0]["result"]["summary"]
    assert summary["Held-out MAE (target units)"] == 5.25
    assert summary["Held-out RMSE (target units)"] == 7.75
    assert summary["Held-out R²"] == -0.2
    assert "Held-out accuracy (fraction)" not in summary
    html = client.get(f"/api/reports/{report.json()['id']}/export/html").text
    assert "Held-out R²" in html
    assert SECRET not in html
