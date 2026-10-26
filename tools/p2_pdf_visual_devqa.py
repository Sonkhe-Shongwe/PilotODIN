#!/usr/bin/env python3
"""P2 synthetic PDF visual-preview gate. No user projects, servers, ML or installs.

Creates three bounded PDFs and representative page PNGs in a fresh DevQA run.
The diagnostic ZIP remains status-only; a SEPARATE clearly synthetic preview ZIP
exists solely for voluntary offline visual inspection.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from qa_foundation import create_run, default_root, scan_files

PHASE = "P2-PDF-VISUAL"
SCENARIOS = ("standard", "dense", "unicode")
MAX_PAGES = 64
MAX_PDF_BYTES = 8_000_000
MAX_PREVIEW_BYTES = 30_000_000
PDF_NAMES = {name: name + ".pdf" for name in SCENARIOS}
PREVIEW_PATTERN = re.compile(
    r"^(?:standard|dense|unicode)(?:\.pdf|-p[0-9]{2}\.png)$"
)


def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as inp:
        for block in iter(lambda: inp.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def is_link(path):
    return path.is_symlink() or getattr(path, "is_junction", lambda: False)()


def verified_home(run, home):
    if home != run / "workspace" or not (run / "manifest.json").is_file():
        raise RuntimeError("Isolated DevQA workspace mismatch")
    if any(is_link(run / p) for p in ("workspace", "exports", "diagnostics", "manifest.json")):
        raise RuntimeError("Linked run paths are prohibited")
    info = json.loads((run / "manifest.json").read_text(encoding="utf-8"))
    if (info.get("phase") != PHASE or info.get("state") != "READY_NOT_TESTED" or
            info.get("product_acceptance") != "NOT_TESTED"):
        raise RuntimeError("Unverified or reused DevQA manifest")


def build_reports():
    # Import after PILOTODIN_HOME validation, never at parent-module scope.
    sys.path.insert(0, str(ROOT))
    sys.path.insert(0, str(ROOT / "tests"))
    from test_p2_report_display_disclosure import report_fixture
    standard = report_fixture()
    standard["title"] = "SYNTHETIC P2 VISUAL DEVQA - Standard exhibits"
    standard["narrative"] = (
        "Synthetic-only report. Examine summary fact and row omission notices, "
        "chart axes, chart limitations, Quality findings, table breaks and footer."
    )
    dense = copy.deepcopy(standard)
    dense["title"] = "SYNTHETIC P2 VISUAL DEVQA - Dense multipage"
    dense["narrative"] = "Dense synthetic evidence, no user data. " * 35
    dense["evidence"] = []
    for _ in range(3):
        for original in standard["evidence"]:
            entry = copy.deepcopy(original)
            entry["id"] = format(len(dense["evidence"]) + 1, "032x")
            entry["objective"] = "Bounded synthetic objective - " * 5
            dense["evidence"].append(entry)
    if len(dense["evidence"]) != 12:
        raise AssertionError("Dense synthetic evidence count changed")
    unusual = copy.deepcopy(standard)
    unusual["title"] = "SYNTHETIC P2 VISUAL DEVQA - Long text and Unicode"
    unusual["narrative"] = (
        "VISUAL GLYPH CHECK: Cafe with accent: café; naïve; São Paulo; "
        "R²; Greek Δ Ω; Cyrillic Москва; CJK 漢字; currency ₹; emoji 📈. "
        "Some characters may need an embedded Unicode font. "
        "This preview makes gaps visible; no glyph-support PASS is inferred. "
    ) * 4
    unusual["evidence"] = unusual["evidence"][:3]
    unusual["evidence"][0]["objective"] = (
        "Synthetic extremely long report section " * 7
    )[:240]
    unusual["evidence"][0]["result"]["summary"] = {
        "Synthetic long identifier " + ("LONGSEGMENT" * 9): "ABCD" * 65,
        "Café São Paulo | R² | Δ Ω | Москва | 漢字 | ₹ | 📈": (
            "Check Unicode glyphs visually and compare against this fixture description"
        ),
        **{"Synthetic metric " + str(i): i for i in range(18)},
    }
    unusual["evidence"][1]["objective"] = "Wide chart and observation preview " * 6
    unusual["evidence"][2]["result"]["findings"] = [
        {"title": "Long synthetic finding " + str(i),
         "detail": "Potential PDF text wrap and dense table quality. " * 4}
        for i in range(24)
    ]
    return {"standard": standard, "dense": dense, "unicode": unusual}


def status_file(run):
    return run / "diagnostics" / "worker-visual.json"


def child_worker():
    run = None
    stage = "workspace_check"
    output = {"state": "BLOCKED", "phase": stage, "cases": [], "files": []}
    try:
        run = Path(os.environ["PILOTODIN_DEVQA_RUN"]).resolve()
        home = Path(os.environ["PILOTODIN_HOME"]).resolve()
        verified_home(run, home)
        stage = "fixture_import"
        import fitz
        from backend import reports
        fixture = build_reports()
        if set(fixture) != set(SCENARIOS):
            raise RuntimeError("Scenario fixture set mismatch")
        stage = "render_and_page_scan"
        outputs = []
        cases = []
        for name in SCENARIOS:
            report = fixture[name]
            original = copy.deepcopy(report)
            filename = PDF_NAMES[name]
            try:
                pdf = reports.render_pdf(report)
                if not pdf.startswith(b"%PDF") or len(pdf) > MAX_PDF_BYTES:
                    raise AssertionError("Invalid or oversized synthetic PDF")
                target = run / "exports" / filename
                with target.open("xb") as out:
                    out.write(pdf)
                with fitz.open(stream=pdf, filetype="pdf") as document:
                    n = len(document)
                    if n < 1 or n > MAX_PAGES:
                        raise AssertionError("Unexpected PDF page count")
                    if name == "dense" and n < 3:
                        raise AssertionError("Dense report did not paginate")
                    outside = 0
                    extracted = []
                    for page in document:
                        if abs(page.rect.width - 595.276) > 1 or abs(page.rect.height - 841.89) > 1:
                            raise AssertionError("A4 geometry mismatch")
                        extracted.append(page.get_text())
                        for block in page.get_text("blocks"):
                            if len(block) > 6 and block[6] != 0:
                                continue
                            x0, y0, x1, y1 = block[:4]
                            if (x0 < -1 or y0 < -1 or
                                    x1 > page.rect.width + 1 or y1 > page.rect.height + 1):
                                outside += 1
                    if outside:
                        raise AssertionError("Extracted text extends beyond page bounds")
                    full_text = "\n".join(extracted)
                    for marker in ("Display limits", "Evidence register"):
                        if marker not in full_text:
                            raise AssertionError("Expected evidence or disclosure absent")
                    glyph_checks = {}
                    if name == "unicode":
                        # An absence is a REVIEW signal, not a reason to claim
                        # successful unsupported font substitution.
                        for marker in ("café", "São Paulo", "R²", "Δ", "Москва", "漢字", "₹", "📈"):
                            glyph_checks[marker] = marker in full_text
                    chosen = sorted({0, n // 2, n - 1})
                    for index in chosen:
                        png_name = name + "-p" + format(index + 1, "02d") + ".png"
                        pix = document[index].get_pixmap(matrix=fitz.Matrix(1.5, 1.5),
                                                         alpha=False)
                        pix.save(str(run / "exports" / png_name))
                        outputs.append(png_name)
                if report != original:
                    raise AssertionError("Report renderer mutated the synthetic fixture")
                outputs.append(filename)
                cases.append({"scenario": name, "state": "STRUCTURAL_PASS", "pages": n,
                              "pdf_sha256": digest(target), "unicode_preserved": glyph_checks})
            except Exception as exc:
                cases.append({"scenario": name, "state": "FAIL",
                              "failure_class": type(exc).__name__})
                break
        success = (len(cases) == len(SCENARIOS) and
                   all(case["state"] == "STRUCTURAL_PASS" for case in cases))
        output = {"state": "READY_FOR_VISUAL_REVIEW" if success else "FAIL",
                  "phase": stage, "cases": cases, "files": outputs if success else []}
    except Exception as exc:
        output = {"state": "BLOCKED", "phase": stage,
                  "reason_class": type(exc).__name__, "cases": [], "files": []}
    if run is not None:
        try:
            status_file(run).write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n",
                                        encoding="utf-8")
        except (OSError, ValueError):
            return 2
    return 0 if output["state"] == "READY_FOR_VISUAL_REVIEW" else 2


def preview_zip(run, child, destination):
    names = child.get("files", [])
    if (not isinstance(names, list) or len(names) < 6 or len(names) > 12 or
            len(set(names)) != len(names) or
            any(not isinstance(n, str) or not PREVIEW_PATTERN.fullmatch(n) for n in names) or
            any(pdf not in names for pdf in PDF_NAMES.values())):
        raise ValueError("Unrecognized synthetic preview file manifest")
    exports = run / "exports"
    if is_link(exports):
        raise ValueError("Refusing linked preview exports directory")
    total = 0
    for name in names:
        path = exports / name
        if (is_link(path) or not path.is_file() or
                not path.resolve().is_relative_to(exports.resolve())):
            raise ValueError("Invalid preview artifact path")
        total += path.stat().st_size
    if total > MAX_PREVIEW_BYTES:
        raise ValueError("Synthetic preview package is larger than safe size limit")
    preview_manifest = {
        "source": "SYNTHETIC_P2_PDF_VISUAL_ONLY",
        "run_id": run.name,
        "files": [{"name": n, "sha256": digest(exports / n)} for n in sorted(names)],
        "scenarios": child["cases"],
        "visual_acceptance": "PENDING_HUMAN_REVIEW",
    }
    instructions = (
        "SYNTHETIC-ONLY PilotODIN P2 PDF visual preview, no customer data.\n"
        "Open all three PDFs. Use PNGs as a quick first/middle/last page index.\n"
        "Examine dense tables, page breaks, chart labels, page footer, display-limit\n"
        "notices and clipping. Examine unicode.pdf for missing/incorrect glyphs.\n"
        "An intact PDF and extracted text DO NOT prove that characters look right.\n"
        "This preview is not an installed-app or native Save As acceptance.\n"
    )
    partial = destination.with_suffix(".partial")
    try:
        with zipfile.ZipFile(partial, "x", zipfile.ZIP_DEFLATED) as bundle:
            bundle.writestr("REVIEW_INSTRUCTIONS.txt", instructions)
            bundle.writestr("preview-manifest.json",
                            json.dumps(preview_manifest, ensure_ascii=False, indent=2) + "\n")
            for name in sorted(names):
                bundle.write(exports / name, arcname=name)
        with zipfile.ZipFile(partial) as verify:
            if verify.testzip() is not None:
                raise ValueError("Preview archive integrity failed")
        partial.replace(destination)
    except Exception:
        try:
            partial.unlink(missing_ok=True)
        except OSError:
            pass
        raise
    return preview_manifest


def execute():
    run = None
    result = {"schema": 1, "state": "BLOCKED", "product_acceptance": "NOT_TESTED",
              "visual_acceptance": "NOT_REVIEWED",
              "scope": "Three isolated synthetic PDF visual previews",
              "unverified": ["glyph-level overlap/clipping, typography and human print legibility",
                             "native installed app, arbitrary real projects or ML model correctness"]}
    try:
        if os.name != "nt" or not os.environ.get("LOCALAPPDATA"):
            raise RuntimeError("Windows LOCALAPPDATA required")
        root = default_root()
        for candidate in (root, root / "runs", root / "archive"):
            if candidate.exists() and is_link(candidate):
                raise RuntimeError("Redirected DevQA path")
        run, _ = create_run(root, PHASE, ROOT)
        if is_link(run / "exports") or is_link(run / "workspace"):
            raise RuntimeError("Linked run directory")
        result["run_id"] = run.name
        source = ["backend/reports.py", "backend/report_charts.py",
                  "tests/test_p2_report_display_disclosure.py",
                  "tools/p2_pdf_visual_devqa.py",
                  "Run_PilotODIN_P2_PDF_Visual_DevQA.bat"]
        findings, blockers = scan_files(ROOT, source)
        result["preflight"] = {"blockers": blockers, "findings": findings,
                               "source_sha256": {p: digest(ROOT / p) for p in source}}
        if blockers:
            raise RuntimeError("Source preflight blocked")
        env = os.environ.copy()
        env["PILOTODIN_HOME"] = str(run / "workspace")
        env["PILOTODIN_DEVQA_RUN"] = str(run)
        env.pop("PILOTODIN_DESKTOP_SESSION", None)
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        env["PYTHONPATH"] = str(ROOT)
        proc = subprocess.run([sys.executable, "-B", str(Path(__file__).resolve()),
                               "--worker"], cwd=ROOT, env=env, capture_output=True,
                              text=True, timeout=240, check=False)
        result["worker_returncode"] = proc.returncode
        try:
            child = json.loads(status_file(run).read_text(encoding="utf-8"))
        except (OSError, UnicodeError, ValueError):
            child = {}
        if not isinstance(child, dict):
            child = {}
        cases = child.get("cases")
        if not isinstance(cases, list) or any(not isinstance(c, dict) for c in cases):
            cases = []
        # Keep the status archive bounded and exclude unexpected worker fields.
        result["cases"] = cases[:len(SCENARIOS)]
        result["worker_phase"] = str(child.get("phase", "no_status"))[:50]
        if (child.get("state") == "READY_FOR_VISUAL_REVIEW" and proc.returncode == 0 and
                len(cases) == len(SCENARIOS) and
                [c.get("scenario") for c in cases] == list(SCENARIOS) and
                all(c.get("state") == "STRUCTURAL_PASS" for c in cases)):
            preview = run.parent.parent / "archive" / (run.name + "-visual-preview.zip")
            info = preview_zip(run, child, preview)
            result["preview_zip"] = str(preview)
            result["preview_sha256"] = digest(preview)
            result["preview_pages"] = {c["scenario"]: c["pages"] for c in child["cases"]}
            result["unicode_preserved"] = child["cases"][-1].get("unicode_preserved", {})
            result["state"] = "REVIEW_REQUIRED"
        elif child.get("state") == "FAIL" and proc.returncode == 2:
            result["state"] = "FAIL"
        else:
            result["state"] = "BLOCKED"
    except subprocess.TimeoutExpired:
        result["state"] = "BLOCKED"
        result["reason"] = "worker_timeout"
    except (OSError, ValueError, RuntimeError, zipfile.BadZipFile) as exc:
        result["state"] = "BLOCKED"
        result["setup_or_preview_error"] = type(exc).__name__
    finally:
        if run is not None:
            archive = run.parent.parent / "archive" / (run.name + ".zip")
            partial = archive.with_suffix(".partial")
            def persist():
                manifest_path = run / "manifest.json"
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                manifest["state"] = result["state"]
                manifest["product_acceptance"] = "NOT_TESTED"
                manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
                status = run / "diagnostics" / "result.json"
                status.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n",
                                  encoding="utf-8")
                return status, manifest_path
            try:
                status, manifest = persist()
                with zipfile.ZipFile(partial, "x", zipfile.ZIP_DEFLATED) as zipout:
                    zipout.write(status, "result.json")
                    zipout.write(manifest, "manifest.json")
                with zipfile.ZipFile(partial) as zipped:
                    if zipped.testzip() is not None:
                        raise ValueError("Status archive integrity failed")
                partial.replace(archive)
                result["diagnostic_zip"] = str(archive)
            except (OSError, ValueError, RuntimeError, zipfile.BadZipFile) as exc:
                result["state"] = "BLOCKED"
                result["diagnostic_failure"] = type(exc).__name__
                try:
                    partial.unlink(missing_ok=True)
                except OSError:
                    result["diagnostic_cleanup_error"] = True
                try:
                    persist()
                except (OSError, ValueError, RuntimeError):
                    result["status_persist_error"] = True
            print("P2 PDF VISUAL DEVQA: " + result["state"])
            print("RUN: " + str(run))
            if result.get("diagnostic_zip"):
                print("STATUS-ONLY DIAGNOSTIC ZIP: " + result["diagnostic_zip"])
            if result.get("preview_zip"):
                print("SYNTHETIC VISUAL PREVIEW ZIP: " + result["preview_zip"])
            for case in result.get("cases", []):
                print(str(case["scenario"]).upper() + ": " + case["state"] +
                      (" (" + str(case["pages"]) + " pages)" if "pages" in case else ""))
            if result["state"] == "REVIEW_REQUIRED":
                print("PDFs generated; VISUAL ACCEPTANCE IS NOT YET COMPLETE.")
                print("Upload the synthetic VISUAL PREVIEW ZIP for page-by-page inspection.")
        else:
            print("P2 PDF VISUAL DEVQA: BLOCKED before run allocation")
    return 0 if result["state"] == "REVIEW_REQUIRED" else 2


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--worker", action="store_true")
    args = parser.parse_args()
    raise SystemExit(child_worker() if args.worker else execute())
