"""A4-2 frozen Explore chart visualization: HTML/PDF parity and scope.

Charts may only be drawn from already-approved version-bound saved aggregate
snapshots. Tests use local disposable fixtures; no external inference or data.
"""
from __future__ import annotations

import json
import re

import fitz
import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend import quality, report_charts

client = TestClient(app)


def project():
    csv = (b"OrderID,Region,Revenue,Loss\n"
           b"0001,North,120,20\n0002,South,180,30\n"
           b"0003,North,240,40\n0004,South,280,55\n"
           b"0005,North,320,85\n0006,South,110,15\n")
    response = client.post("/api/projects", files={
        "file": ("chart-export.csv", csv, "text/csv")
    })
    assert response.status_code == 201, response.text
    return response.json()["id"]


def saved_explore(pid, kind, x, y, agg):
    reply = client.post(f"/api/projects/{pid}/explore/saved", json={
        "title": f"Verified saved {kind} chart",
        "expected_version": quality.current_version(pid),
        "x": x, "y": y, "kind": kind, "aggregation": agg,
        "bins": 5, "correlation_method": "pearson", "filters": [],
    })
    assert reply.status_code == 201, reply.text
    return reply.json()


def report(pid, evidence_id):
    reply = client.post(f"/api/projects/{pid}/reports", json={
        "title": "Report with frozen chart",
        "narrative": "Descriptive visualization from verified frozen evidence.",
        "evidence_ids": [evidence_id],
    })
    assert reply.status_code == 201, reply.text
    return reply.json()


@pytest.mark.parametrize("kind,x,y,agg", [
    ("bar", "Region", "Revenue", "sum"),
    ("histogram", "Revenue", None, "count"),
    ("line", "Region", "Revenue", "sum"),
])
def test_html_and_pdf_show_same_saved_aggregate_chart(kind, x, y, agg):
    pid = project()
    saved = saved_explore(pid, kind, x, y, agg)
    source = saved["snapshot"]["chart"]
    r = report(pid, saved["id"])
    exhibit = r["evidence"][0]
    assert exhibit["dataset_version"] == 0
    visual = exhibit["result"]["visual"]
    assert visual["type"] == kind
    assert visual["data"] == [
        {"label": p["label"], "value": float(p["value"])}
        for p in source["data"][:len(visual["data"])]
    ]
    html = client.get(f"/api/reports/{r['id']}/export/html?revision=1")
    pdf = client.get(f"/api/reports/{r['id']}/export/pdf?revision=1")
    assert html.status_code == 200 and pdf.status_code == 200
    text = " ".join(page.get_text() for page in fitz.open(
        stream=pdf.content, filetype="pdf"))
    assert html.text.count('<figure class="verified-chart">') == 1
    assert html.text.count('<svg') == 1
    assert "Saved chart visualization" in html.text
    assert "Saved chart visualization" in text
    assert "Static visualization of saved aggregate values" in html.text
    assert "Chart limitations:" in text
    assert "Frequency" in html.text if kind == "histogram" else True
    for point in visual["data"][:3]:
        # The verified chart's source data remains in report evidence and in
        # the observations table. PDF contains the original source labels.
        assert point["label"] in html.text
        assert point["label"] in text


def test_svg_never_interprets_untrusted_category_as_html():
    source = {
        "type": "bar", "x": "<script>alert(1)</script>",
        "y": "Revenue", "aggregation": "sum",
        "data": [{"label": '<img src=x onerror="attack()">', "value": 100}],
        "note": "<svg onload=evil()>", "truncated": False,
    }
    spec = report_charts.visual_spec(source)
    rendered = report_charts.html_chart(spec)
    assert "<script>" not in rendered and "<img " not in rendered
    assert "<svg onload" not in rendered
    assert "&lt;img" in rendered
    assert "&lt;script&gt;" in rendered
    assert "&lt;svg" in rendered


def test_visuals_abstain_on_scatter_raw_points_or_invalid_numbers():
    assert report_charts.visual_spec({
        "type": "scatter", "data": [{"x": 1, "y": 2}]
    }) is None
    assert report_charts.visual_spec({
        "type": "bar", "data": [{"label": "A", "value": float("nan")}]
    }) is None
    assert report_charts.visual_spec({
        "type": "bar", "data": [{"label": "A", "value": True}]
    }) is None
    assert report_charts.visual_spec({
        "type": "bar", "data": [{"label": "A", "value": "123"}]
    }) is None


def test_bounded_truncated_visuals_are_flagged_not_described_as_complete():
    source = {
        "type": "bar", "x": "Region", "y": "Revenue", "aggregation": "sum",
        "data": [{"label": f"Group {i}", "value": i - 9.0} for i in range(21)],
        "truncated": True,
    }
    spec = report_charts.visual_spec(source)
    assert len(spec["data"]) == 12
    assert spec["limited"]
    assert "bounded subset" in spec["note"]
    markup = report_charts.html_chart(spec)
    assert "bounded subset" in markup
    assert "Group 20" not in markup
    drawing = report_charts.pdf_chart(spec, width=480)
    assert drawing.width == 480
    assert len(drawing.contents) > 10


def test_a_saved_report_does_not_recalculate_visual_after_source_change():
    pid = project()
    saved = saved_explore(pid, "bar", "Region", "Revenue", "sum")
    r = report(pid, saved["id"])
    original = r["evidence"][0]["result"]["visual"]
    original_html = client.get(f"/api/reports/{r['id']}/export/html?revision=1").content
    with __import__("backend.storage", fromlist=["connect"]).connect() as con:
        con.execute("UPDATE explore_snapshots_v1 SET snapshot_json=? WHERE id=?",
                    (json.dumps({"chart": {"type": "bar", "data": [
                        {"label": "tampered", "value": 999999}]} }), saved["id"]))
    historical = client.get(f"/api/reports/{r['id']}?revision=1").json()
    assert historical["evidence"][0]["result"]["visual"] == original
    assert client.get(f"/api/reports/{r['id']}/export/html?revision=1").content == original_html
