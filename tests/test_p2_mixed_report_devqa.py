"""P2 four-source report DevQA: synthetic-only, no training or user-data access.

Run ONLY in a fresh isolated PILOTODIN_HOME allocated by the DevQA launcher.
Tests exercise real local FastAPI report APIs, selected stored synthetic evaluation,
canonical snapshots and both HTML/PDF renderers. No native Tauri launch.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import unittest

import fitz
from fastapi.testclient import TestClient
from backend import reports, storage, quality, report_charts
from backend.main import app

CANARY = "PRIVATE_ROW_CANARY_DO_NOT_EXPORT_42"
HOLDOUT = "SYNTHETIC_HOLDOUT_ROW_NEVER_EXPORT"
ROWS = (("0001", "North", 120, "Y"), ("0002", "South", 180, "N"),
        ("0003", "North", 240, "N"), ("0004", "South", 280, "Y"),
        ("0005", "North", 40, "N"), ("0006", "South", 80, "Y"))
client = TestClient(app)


def oracle():
    totals = {}
    for _, region, revenue, _ in ROWS:
        totals[region] = totals.get(region, 0) + revenue
    assert len(ROWS) == 6 and totals == {"North": 400, "South": 540}
    assert sum(totals.values()) == 940
    return totals


def expect(reply, code):
    if reply.status_code != code:
        raise AssertionError("Unexpected synthetic API status for " +
                             reply.request.url.path + ": " + str(reply.status_code))
    return reply.json()


def dataset():
    header = "OrderID,Region,Revenue,Flagged,OptionalPrivateNote"
    lines = [header]
    for identifier, region, revenue, flag in ROWS:
        # Synthetic private value exists in source rows but is not selected
        # as a dimension, output metric, narrative, or model feature.
        lines.append(",".join((identifier, region, str(revenue), flag, CANARY)))
    return ("\n".join(lines) + "\n").encode("utf-8")


def new_project(filename, content):
    return expect(client.post("/api/projects", files={"file": (filename, content, "text/csv")}), 201)["id"]


def synthetic_selected_model(pid):
    config = {"target": "Flagged", "task": "classification",
              "excluded": ["OrderID", "OptionalPrivateNote"],
              "models": ["logistic"], "quality_version": 0,
              "split_strategy": "random", "split_column": None}
    eid = storage.new_experiment(pid, config)
    storage.mark(eid, "completed", {
        "task": "classification", "models": [{"key": "logistic", "status": "ready",
                                               "cv_metric": .71}],
        "test_rows": 30, "baseline_cv": .4})
    final = {"target": "Flagged", "sample_count": 30,
             "accuracy": .82, "f1_macro": .73, "precision_macro": .76,
             "recall_macro": .72, "baseline_test_metric": .42,
             "baseline_test_label": "Macro F1",
             "class_report": [{"label": "Y", "precision": .61, "recall": .53,
                               "f1": .57, "support": 12}],
             "evaluation_rows": [{"actual": HOLDOUT, "predicted": HOLDOUT}],
             "reliability": {"level": "warning",
                             "message": "Test-only seeded evaluation. Review deployment.",
                             "issues": ["Synthetic held-out metrics are not business guarantees."]}}
    if not storage.select_model(eid, "logistic", final):
        raise AssertionError("Synthetic selected-model evidence was not accepted")
    return eid


def save(pid, evidence, report_id=None, title="Four-source synthetic evidence",
         narrative="User-authored interpretation, not independently validated."):
    body = {"title": title, "narrative": narrative, "evidence_ids": evidence}
    path = (f"/api/reports/{report_id}/revisions" if report_id else
            f"/api/projects/{pid}/reports")
    return client.post(path, json=body)


def exports(rid, revision):
    html = client.get(f"/api/reports/{rid}/export/html?revision={revision}")
    pdf = client.get(f"/api/reports/{rid}/export/pdf?revision={revision}")
    if html.status_code != 200 or pdf.status_code != 200 or not pdf.content.startswith(b"%PDF"):
        raise AssertionError("Synthetic report exports did not return valid HTML and PDF")
    with fitz.open(stream=pdf.content, filetype="pdf") as doc:
        text = "\n".join(page.get_text() for page in doc)
        bounds = [(page.rect.width, page.rect.height) for page in doc]
    return html.text, text, bounds


class MixedReportContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        home = os.environ.get("PILOTODIN_HOME", "")
        run = os.environ.get("PILOTODIN_DEVQA_RUN", "")
        if not home or not run or not Path(home).is_absolute() or not Path(run).is_absolute():
            raise RuntimeError("Missing absolute isolated DevQA test workspace")
        root = Path(run).resolve()
        if Path(home).resolve() != root / "workspace" or not (root / "manifest.json").is_file():
            raise RuntimeError("Refusing non-DevQA or non-current test home")
        manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
        if (manifest.get("phase") != "P2-MIXED-REPORT" or
                manifest.get("state") != "READY_NOT_TESTED" or
                manifest.get("product_acceptance") != "NOT_TESTED"):
            raise RuntimeError("DevQA run manifest is not fresh")
        cls.expected = oracle()
        cls.raw = dataset()
        cls.original_sha = hashlib.sha256(cls.raw).hexdigest()
        cls.project_id = new_project("mixed-evidence-fixture.csv", cls.raw)
        cls.foreign_project = new_project("foreign-evidence-fixture.csv",
                                          b"OrderID,Region,Revenue\n7777,Outside,3\n")
        source = Path(storage.get_project(cls.project_id)["dataset_path"])
        cls.source_path = source
        if hashlib.sha256(source.read_bytes()).hexdigest() != cls.original_sha:
            raise RuntimeError("Imported synthetic fixture differs from independent source oracle")
        version = quality.current_version(cls.project_id)
        if version != 0:
            raise RuntimeError("Fresh synthetic project did not start at approved version 0")
        audit = expect(client.post(f"/api/projects/{cls.project_id}/report-quality",
                                   json={"expected_version": version}), 201)
        explore = expect(client.post(f"/api/projects/{cls.project_id}/explore/saved",
                            json={"title": "Revenue by synthetic region", "expected_version": version,
                                  "x": "Region", "y": "Revenue", "kind": "bar",
                                  "aggregation": "sum", "bins": 12,
                                  "correlation_method": "pearson", "filters": []}), 201)
        investigation = expect(client.post(f"/api/projects/{cls.project_id}/investigations",
                       json={"objective": "Read-only synthetic revenue overview"}), 201)
        overview = expect(client.post(f"/api/investigations/{investigation['id']}/runs",
                       json={"operation": "overview", "params": {},
                             "expected_version": investigation["version"]}), 200)
        cls.quality_id, cls.explore_id = audit["id"], explore["id"]
        cls.investigation_id = overview["artifacts"][0]["id"]
        cls.model_id = synthetic_selected_model(cls.project_id)
        cls.ids = [cls.quality_id, cls.explore_id, cls.investigation_id, cls.model_id]
        options = expect(client.get(f"/api/projects/{cls.project_id}/report-evidence"), 200)
        eligible = {entry["id"] for entry in options}
        if not set(cls.ids).issubset(eligible):
            raise RuntimeError("Four expected evidence IDs not offered by canonical report API")
        cls.revision1 = expect(save(cls.project_id, cls.ids), 201)
        cls.report_id = cls.revision1["id"]
        cls.rev1_html, cls.rev1_pdf, cls.rev1_pages = exports(cls.report_id, 1)
        cls.revision2 = expect(save(cls.project_id, list(reversed(cls.ids)), cls.report_id,
                                    narrative="<img src=x onerror=alert(1)> synthetic review"), 201)

    def test_mr01_four_frozen_sources_and_independent_oracle(self):
        report = self.revision1
        self.assertEqual(report["revision"], 1)
        self.assertEqual([art["id"] for art in report["evidence"]], self.ids)
        self.assertEqual([art["operation"] for art in report["evidence"]],
                         ["quality_audit", "explore_snapshot", "overview", "model_evaluation"])
        self.assertEqual(report["dataset_versions"], [0])
        explore = report["evidence"][1]
        groups = {item["label"]: item["value"] for item in explore["result"]["data"]}
        self.assertEqual(groups, self.expected)
        self.assertEqual(sum(groups.values()), 940)
        self.assertEqual(hashlib.sha256(self.source_path.read_bytes()).hexdigest(),
                         self.original_sha)

    def test_mr02_rev1_immutable_after_rev2(self):
        old = expect(client.get(f"/api/reports/{self.report_id}?revision=1"), 200)
        self.assertEqual(old["content_sha256"], self.revision1["content_sha256"])
        self.assertEqual(old["evidence"], self.revision1["evidence"])
        self.assertEqual(old["revision"], 1)
        self.assertEqual(self.revision2["revision"], 2)
        self.assertEqual([art["id"] for art in self.revision2["evidence"]],
                         list(reversed(self.ids)))
        self.assertNotEqual(self.revision2["content_sha256"], old["content_sha256"])
        self.assertEqual(exports(self.report_id, 1)[:2],
                         (self.rev1_html, self.rev1_pdf))

    def test_mr03_html_pdf_semantic_parity(self):
        html, pdf = self.rev1_html, self.rev1_pdf
        for term in ("Four-source synthetic evidence", "Quality Audit",
                     "Explore Snapshot", "Overview", "Model Evaluation",
                     "400", "540", "0.82", "0.73", "0.53",
                     "Held-out accuracy (fraction)", "Interpretation"):
            with self.subTest(term=term):
                self.assertIn(term, html)
                self.assertIn(term, pdf)
        for eid in self.ids:
            self.assertIn(eid, html)
            self.assertIn(eid, pdf)
        self.assertIn("not independently verified", html)
        self.assertIn("not independently verified", pdf)

    def test_mr04_privacy_and_escaped_user_narrative(self):
        rev2 = self.revision2
        html2, pdf2, _ = exports(self.report_id, 2)
        for text in (json.dumps(self.revision1), json.dumps(rev2),
                     self.rev1_html, self.rev1_pdf, html2, pdf2):
            self.assertNotIn(CANARY, text)
            self.assertNotIn(HOLDOUT, text)
        self.assertNotIn("<img src=x onerror=alert(1)>", html2)
        self.assertIn("&lt;img src=x onerror=alert(1)&gt;", html2)
        self.assertNotIn("<img ", html2)

    def test_mr05_reject_foreign_and_unselected_evidence(self):
        before = expect(client.get(f"/api/projects/{self.project_id}/reports"), 200)
        other_inv = expect(client.post(f"/api/projects/{self.foreign_project}/investigations",
                                json={"objective": "Other owner overview"}), 201)
        other_run = expect(client.post(f"/api/investigations/{other_inv['id']}/runs",
                         json={"operation": "overview", "params": {},
                               "expected_version": other_inv["version"]}), 200)
        foreign_id = other_run["artifacts"][0]["id"]
        self.assertEqual(save(self.project_id, [foreign_id]).status_code, 403)
        self.assertEqual(save(self.project_id, [self.ids[0], "f"*32]).status_code, 403)
        self.assertEqual(save(self.project_id, [self.ids[0], self.ids[0]]).status_code, 422)
        unselected = storage.new_experiment(self.project_id, {
            "task": "classification", "target": "Flagged",
            "quality_version": 0, "models": ["logistic"]})
        self.assertEqual(save(self.project_id, [unselected]).status_code, 403)
        after = expect(client.get(f"/api/projects/{self.project_id}/reports"), 200)
        self.assertEqual(before, after)
        self.assertEqual(expect(client.get(f"/api/reports/{self.report_id}"), 200)["revision"], 2)

    def test_mr06_bounded_visual_not_invented(self):
        self.assertIsNone(report_charts.visual_spec({
            "type": "scatter", "data": [{"x": 1, "y": 2}]}))
        self.assertIsNone(report_charts.visual_spec({
            "type": "bar", "data": [{"label": "A", "value": float("nan")}]}))
        rows = [{"label": "Group " + str(i), "value": float(i)} for i in range(45)]
        facts, headings, shown = reports._exhibit({"result": {"data": rows}})
        self.assertEqual(len(shown), 40)
        chart = report_charts.visual_spec({
            "type": "bar", "x": "Region", "y": "Revenue", "aggregation": "sum",
            "data": rows[:20], "truncated": True})
        self.assertIsNotNone(chart)
        self.assertTrue(chart["limited"])
        self.assertEqual(len(chart["data"]), 12)
        self.assertIn("bounded subset", chart["note"])
        # This validates caps, NOT reader-facing disclosure of the 5 omitted rows.

    def test_mr07_pdf_pages_and_source_stability(self):
        with fitz.open(stream=client.get(
                f"/api/reports/{self.report_id}/export/pdf?revision=1").content,
                filetype="pdf") as document:
            self.assertGreaterEqual(len(document), 1)
            for page in document:
                self.assertAlmostEqual(page.rect.width, 595.276, delta=1)
                self.assertAlmostEqual(page.rect.height, 841.89, delta=1)
            joined = "\n".join(page.get_text() for page in document)
        for term in ("Quality Audit", "Explore Snapshot",
                     "Overview", "Model Evaluation", "540"):
            self.assertIn(term, joined)
        self.assertEqual(hashlib.sha256(self.source_path.read_bytes()).hexdigest(),
                         self.original_sha)

if __name__ == "__main__":
    unittest.main()
