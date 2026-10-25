"""A4 visual regression: keep headings and small tables together in mixed reports.

Fixtures are synthetic aggregate evidence. Reproduces the structure (9 Quality
findings, 16 ML metrics, seven chart categories) of a real three-exhibit export
without embedding any uploaded insurance-claim data.
"""
from __future__ import annotations

import fitz
from backend import reports


def _artifact(kind: str, label: str, result: dict) -> dict:
    return {
        "id": ({"quality_audit": "a", "model_evaluation": "b",
                "explore_snapshot": "c"}[kind]) * 32,
        "operation": kind, "objective": label, "dataset_version": 0,
        "tool_version": "synthetic-report-test-v1",
        "computed_at": "2026-10-25T09:11:32+00:00",
        "params": {"source_snapshot_sha256": "d" * 64},
        "result": result,
    }


def _report() -> dict:
    quality = _artifact("quality_audit", "Quality audit of dataset v0", {
        "summary": {
            "Approved working corrections active": 0,
            "Columns in approved dataset": 39,
            "Findings shown": 9,
            "Quality findings detected": 9,
            "Rows in approved dataset": 1000,
            "Source original SHA-256": "d" * 64,
            "Version event": "original",
        },
        "findings": [
            {"title": "Ambiguous date formats",
             "detail": (f"Review ambiguous day/month ordering before conversion. | "
                        f"Column: synthetic_date_{i} | Affected rows: {413-i} | "
                        "Decision: pending")}
            for i in range(9)
        ],
        "note": "Read-only audit. Screening findings are not confirmed errors.",
        "limitations": ["No original row-level values are embedded."],
    })
    model = _artifact("model_evaluation", "Evaluate synthetic_target", {
        "summary": {
            "Baseline metric": "Macro F1",
            "Development CV baseline": 0.42938,
            "Development CV score": 0.76505,
            "Held-out ROC AUC": 0.81619,
            "Held-out accuracy (fraction)": 0.82,
            "Held-out macro F1": 0.73776,
            "Held-out macro precision": 0.7619,
            "Held-out macro recall": 0.72226,
            "Held-out observations": 200,
            "Held-out simple baseline": 0.4302,
            "Outperforms held-out baseline": True,
            "Prediction target": "synthetic_target",
            "Reliability assessment": "Preliminary. Validate independently.",
            "Selected model": "logistic_regression",
            "Task": "Classification",
            "Validation split": "random",
        },
        "data": [
            {"label": "N", "precision": 0.85, "recall": 0.91, "f1": 0.88, "support": 151},
            {"label": "Y", "precision": 0.66, "recall": 0.53, "f1": 0.59, "support": 49},
        ],
    })
    groups = [
        {"label": f"Group {i}", "value": float(60540-900*i)}
        for i in range(7)
    ]
    explore = _artifact("explore_snapshot", "Saved synthetic chart", {
        "summary": {
            "Chart groups truncated": False,
            "Chart type": "bar",
            "Displayed chart rows": 7,
            "Matching exact duplicates": 0,
            "Matching missing cells": 91,
            "Plotted sample": False,
            "Rows matching saved filters": 1000,
            "Source snapshot SHA-256": "c" * 64,
            "Total dataset rows": 1000,
        },
        "data": groups,
        "visual": {
            "type": "bar", "x": "synthetic_group", "y": "synthetic_amount",
            "aggregation": "median", "data": groups,
            "limited": False, "note": "Descriptive, not causal.",
        },
    })
    return {
        "id": "e" * 32, "revision": 3, "title": "Synthetic Combined Investigation",
        "narrative": "User-reviewed evidence and limitations, without raw records.",
        "content_sha256": "f" * 64,
        "dataset_versions": [0],
        "evidence": [quality, model, explore],
        "limitations": ["Statistics are descriptive unless independently validated."],
    }


def test_combined_three_exhibit_pdf_has_no_orphaned_evidence_headings():
    blob=reports.render_pdf(_report())
    pages=fitz.open(stream=blob,filetype="pdf")
    assert 3 <= len(pages) <= 7
    texts=[page.get_text() for page in pages]
    assert sum(text.count("Model Evaluation") for text in texts)>=1
    assert sum(text.count("Explore Snapshot") for text in texts)>=1
    assert "Median of synthetic_amount by synthetic_group" in " ".join(texts)

    for txt in texts:
        if "Model Evaluation" in txt:
            assert "Held-out accuracy (fraction)" in txt
        if "Explore Snapshot" in txt:
            assert "Chart type" in txt
        if "Verified observations" in txt:
            assert ("Ambiguous date formats" in txt or
                    "N" in txt and "0.91" in txt or
                    "Group 0" in txt)
    assert sum(txt.count("Ambiguous date formats") for txt in texts)==9
    assert sum(txt.count("Group 6") for txt in texts)>=1


def test_combined_three_exhibit_html_and_pdf_share_measure_semantics():
    sample=_report()
    html=reports.render_html(sample).decode("utf-8")
    pdf=" ".join(page.get_text() for page in fitz.open(
        stream=reports.render_pdf(sample),filetype="pdf"
    ))
    for shared in ("Quality Audit", "Model Evaluation", "Explore Snapshot",
                   "0.76505", "0.82", "Median of synthetic_amount by synthetic_group"):
        assert shared in html and shared in pdf
    assert html.index("Quality Audit") < html.index("Model Evaluation") < html.index("Explore Snapshot")
