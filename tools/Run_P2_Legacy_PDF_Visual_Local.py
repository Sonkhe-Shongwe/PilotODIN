#!/usr/bin/env python3
"""P2 BE-030: one disposable saved report through the NORMAL legacy PDF API.

Windows owner visual-review fixture only. Never uses owner projects, changes
production data, approves Unicode fonts, installs models or builds an installer.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import traceback
import zipfile

ROOT = Path(__file__).resolve().parents[1]
PHASE = "P2-LEGACY-PDF-VISUAL"
CSV = (
    b"OrderID,Region,Revenue\n"
    b"001,North,120\n002,South,220\n003,East,140\n004,West,310\n"
    b"005,North,260\n006,South,185\n007,East,170\n008,West,400\n"
)
TITLE = "Synthetic Regional Revenue Review"
NARRATIVE = (
    "Purpose and decision: Review only eight disposable order records.\n"
    "Verified findings: Read the frozen aggregates and chart in this report.\n"
    "Limitations: These example values do not establish real-world causation.\n"
    "Next steps: Request an independently validated dataset before decisions."
)


def need(condition: bool, description: str) -> None:
    if not condition:
        raise RuntimeError(description)


def request(client, method: str, path: str, *, expected: int, **kwargs):
    response = client.request(method, path, **kwargs)
    need(response.status_code == expected,
         f"Synthetic local API {method} {path} returned HTTP {response.status_code}: "
         + response.text[:280])
    return response


def main() -> int:
    need(os.name == "nt", "Owner Windows is required")
    need(not os.getenv("PILOTODIN_HOME") and not os.getenv("PILOTODIN_DESKTOP_SESSION"),
         "Refusing an existing PilotODIN user or desktop workspace")
    # Direct script execution starts with tools/ on sys.path, not repo root.
    # Add the verified checkout only, before importing the local backend.
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from qa_foundation import create_run, default_root
    git_head = "NOT_ATTESTED"
    try:
        branch = subprocess.run(["git", "-C", str(ROOT), "branch", "--show-current"],
                                capture_output=True, text=True, timeout=8, check=True).stdout.strip()
        need(branch == "feature/live-dev-workspace-20261023",
             "Wrong Git branch; use the authorised P2 feature branch")
        git_head = subprocess.run(["git", "-C", str(ROOT), "rev-parse", "HEAD"],
                                  capture_output=True, text=True, timeout=8, check=True).stdout.strip()
    except FileNotFoundError:
        print("WARNING: Git CLI unavailable; local commit cannot be attested.", flush=True)
    run, manifest = create_run(default_root(), PHASE, repo=ROOT)
    home = run / "workspace"
    outputs = run / "exports"
    outcome = {
        "phase": PHASE, "run_id": run.name, "state": "FAIL_OR_BLOCKED",
        "product_acceptance": "NOT_TESTED",
        "be_030_owner_visual": "PENDING",
        "source_head": git_head,
        "source_integrity": "NOT_CHECKED",
        "unicode_release": "NOT_GRANTED",
        "no_installer": True, "no_model": True,
    }
    pdf_path = outputs / "P2_BE030_SYNTHETIC_STANDARD_PDF_REVIEW.pdf"
    html_path = outputs / "P2_BE030_SYNTHETIC_STANDARD_HTML_REFERENCE.html"
    os.environ["PILOTODIN_HOME"] = str(home)
    try:
        from fastapi.testclient import TestClient
        from backend.main import app
        from backend import storage, pdf_release_font_loader
        import fitz

        need(pdf_release_font_loader.RELEASE_APPROVAL_STATUS == "NOT_GRANTED"
             and pdf_release_font_loader.RELEASE_PINNED_FILES == ()
             and pdf_release_font_loader.RELEASE_APPROVAL_REFERENCE == "",
             "Refusing changed/approved font release configuration in this legacy-only QA")
        client = TestClient(app)
        created = request(client, "POST", "/api/projects", expected=201,
                          files={"file": ("p2-be030-synthetic.csv", CSV, "text/csv")}).json()
        pid = created["id"]
        need(bool(re.fullmatch(r"[a-f0-9]{32}", pid)), "Unexpected project ID")
        source = Path(storage.get_project(pid)["dataset_path"]).resolve(strict=True)
        need(source.is_relative_to(home.resolve()) and source.read_bytes() == CSV,
             "Uploaded CSV did not remain intact in isolated DevQA home")
        original_sha = hashlib.sha256(CSV).hexdigest()
        evidence = []
        for operation, params in (
            ("overview", {}),
            ("compare", {"x": "Region", "y": "Revenue"}),
        ):
            inv = request(client, "POST", f"/api/projects/{pid}/investigations",
                          expected=201,
                          json={"objective": f"Synthetic {operation} report evidence"}).json()
            result = request(client, "POST", f"/api/investigations/{inv['id']}/runs",
                             expected=200, json={"operation": operation, "params": params,
                                                 "expected_version": inv["version"]}).json()
            eid = result["artifacts"][0]["id"]
            need(bool(re.fullmatch(r"[a-f0-9]{32}", eid)), "Unexpected investigation evidence")
            evidence.append(eid)

        chart = request(client, "POST", f"/api/projects/{pid}/explore/saved", expected=201,
                        json={"title": "Synthetic Regional Revenue Bar Chart",
                              "expected_version": 0, "x": "Region", "y": "Revenue",
                              "kind": "bar", "aggregation": "sum", "bins": 16,
                              "correlation_method": "pearson", "color_by": None,
                              "filters": []}).json()
        chart_id = chart["id"]
        need(bool(re.fullmatch(r"[a-f0-9]{32}", chart_id)), "Unexpected chart evidence")
        evidence.append(chart_id)

        options = request(client, "GET", f"/api/projects/{pid}/report-evidence",
                          expected=200).json()
        option_ids = {item["id"] for item in options}
        need(len(set(evidence)) == 3 and set(evidence).issubset(option_ids),
             "Not all three synthetic frozen evidence artifacts are selectable")
        report = request(client, "POST", f"/api/projects/{pid}/reports", expected=201,
                         json={"title": TITLE, "narrative": NARRATIVE,
                               "evidence_ids": evidence}).json()
        rid = report["id"]
        need(report["revision"] == 1 and len(report["evidence"]) == 3,
             "Synthetic immutable report revision did not save three exhibits")
        frozen = request(client, "GET", f"/api/reports/{rid}?revision=1",
                         expected=200).json()
        need(frozen["content_sha256"] == report["content_sha256"]
             and frozen["narrative"] == NARRATIVE
             and [art["id"] for art in frozen["evidence"]] == evidence,
             "Frozen saved report evidence or narrative changed")
        need(any(isinstance(art.get("result", {}).get("visual"), dict)
                 for art in frozen["evidence"]), "Frozen chart is not present in report")

        basename = f"pilotodin_report_{rid[:12]}_rev1"
        pdf = request(client, "GET", f"/api/reports/{rid}/export/pdf?revision=1", expected=200)
        html = request(client, "GET", f"/api/reports/{rid}/export/html?revision=1", expected=200)
        for response, kind, mime in (
            (pdf, "pdf", "application/pdf"), (html, "html", "text/html")
        ):
            need(response.headers["content-type"].lower().startswith(mime)
                 and basename + "." + kind in response.headers["content-disposition"],
                 f"Normal {kind} report response filename or MIME wrong")
        need(pdf.content.startswith(b"%PDF-") and
             b"Saved chart visualization" in html.content,
             "Unexpected normal PDF or missing HTML saved chart")
        need(b"<svg" in html.content and
             frozen["content_sha256"].encode("ascii") in html.content,
             "Saved HTML reference is missing SVG chart or immutable digest")

        pdf_path.write_bytes(pdf.content)
        html_path.write_bytes(html.content)
        with fitz.open(stream=pdf.content, filetype="pdf") as doc:
            pages = [page.get_text() for page in doc]
            need(1 <= len(pages) <= 12 and all(len(text.strip()) >= 35 for text in pages),
                 "Unexpected blank, oversized or unreadable standard PDF pages")
            combined = " ".join(pages).replace("\n", " ")
            for phrase in (TITLE, "Evidence register", "Saved chart visualization",
                           "Methodology and limitations", frozen["content_sha256"]):
                need(phrase in combined, f"Required legacy PDF content missing: {phrase}")
            page_count = len(pages)
            for index in range(min(page_count, 6)):
                view = doc[index].get_pixmap(matrix=fitz.Matrix(1.3, 1.3), alpha=False)
                view.save(str(outputs / f"P2_BE030_SYNTHETIC_PAGE_{index+1:02}.png"))

        need(source.read_bytes() == CSV
             and hashlib.sha256(source.read_bytes()).hexdigest() == original_sha,
             "Original synthetic CSV bytes changed during read-only report export")
        outcome.update({
            "state": "REVIEW_REQUIRED",
            "source_integrity": "PASS",
            "report_revision": 1, "verified_evidence_count": 3,
            "pdf_pages": page_count,
            "pdf_sha256": hashlib.sha256(pdf.content).hexdigest(),
            "html_sha256": hashlib.sha256(html.content).hexdigest(),
            "source_csv_sha256": original_sha,
            "be_030_owner_visual": "PENDING",
        })
        print("SYNTHETIC normal saved PDF and HTML HTTP export: SOURCE/EXTRACTION PASS")
        print(f"Actual standard PDF: {pdf_path}")
        print(f"Reference saved HTML: {html_path}")
        print(f"Rendered page PNGs: {min(page_count, 6)} under {outputs}")
        print(f"PDF page count: {page_count}. Owner visual quality acceptance remains PENDING.")
        print("Open the exact PDF/PNGs and review layout, charts, tables, source notes, page breaks.")
        try:
            os.startfile(pdf_path)
        except OSError:
            print("Default PDF viewer did not launch; open the printed local file manually.")
        return 0
    except Exception as exc:
        outcome["failure_category"] = f"{type(exc).__name__}: {str(exc)[:340]}"
        print("P2 BE-030 scoped synthetic QA FAILED/BLOCKED: " + outcome["failure_category"])
        return 1
    finally:
        result_path = run / "diagnostics" / "result.json"
        result_path.write_text(json.dumps(outcome, indent=2) + "\n", encoding="utf-8")
        archive = run.parent.parent / "archive" / (run.name + "-be030-status-only.zip")
        with zipfile.ZipFile(archive, "x", zipfile.ZIP_DEFLATED) as bundle:
            bundle.write(result_path, arcname="result.json")
            bundle.write(run / "manifest.json", arcname="manifest.json")
        print("Status-only QA ZIP (no report bytes, CSV or model): " + str(archive))
        os.environ.pop("PILOTODIN_HOME", None)


if __name__ == "__main__":
    raise SystemExit(main())
