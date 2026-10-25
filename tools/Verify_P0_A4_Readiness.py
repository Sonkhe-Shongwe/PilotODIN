#!/usr/bin/env python3
"""One local, offline, non-release P0 -> A4 readiness run.

Runs each frontend gate once and a deduplicated union of A2/A3 plus critical
report/export regression files in a fresh temporary PILOTODIN_HOME.
Does NOT install dependencies, launch an installer, contact GitHub, or certify
interactive Windows behaviour.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
import xml.etree.ElementTree as ET
from zipfile import ZIP_DEFLATED, ZipFile

ROOT = Path(__file__).resolve().parents[1]
BRANCH = "feature/live-dev-workspace-20261023"

# Sourced from Verify_Macro_A2_Local.ps1 and Verify_Macro_A3_Local.ps1.
# Keep their original scripts for focused debugging; never run both complete
# scripts here, which would duplicate frontend compilation and shared tests.
A2 = (
    "test_non_ai_correctness_gates.py",
    "test_explore_chart_quality.py",
    "test_scatter_interactions.py",
    "test_explore_linked_filters.py",
    "test_explore_null_category_identity.py",
    "test_explore_record_inspector.py",
    "test_explore_line_box_inspection.py",
    "test_column_intelligence.py",
    "test_p3_semantic_profile.py",
    "test_p4_target_opportunities.py",
    "test_saved_explore_analyses.py",
    "test_explore_to_report_evidence.py",
    "test_correlation_matrix.py",
    "test_chart_counts_semantics.py",
    "test_quality_increment1.py",
    "test_quality_deep_investigations.py",
    "test_report_exhibit_render.py",
    "test_build_e_persistent_reports.py",
)
A3 = (
    "test_ml_a3_preparation_and_split_safety.py",
    "test_ml_a3_baseline_and_prediction_warnings.py",
    "test_ml_a3_memory_and_explainability.py",
    "test_ml_a3_group_and_model_caps.py",
    "test_model_library_expansion.py",
    "test_non_ai_correctness_gates.py",
    "test_build_d_unified_journey.py",
    "test_p0_ml_persistence_version_journey.py",
)
A4_READINESS = (
    "test_a4_model_evidence_reports.py",
    "test_a4_frozen_chart_visuals.py",
    "test_a4_quality_audit_reporting.py",
    "test_a4_mixed_report_pagination.py",
    "test_build_e_cleaned_exports.py",
    "test_build_e_approval_receipts.py",
    "test_p1_import_recovery.py",
    "test_p1_resource_policy.py",
    "test_p1_resource_admission.py",
    "test_p5_ml_training_slot.py",
    "test_p5_training_progress.py",
    "test_p5_training_cancellation.py",
)
TEST_FILES = list(dict.fromkeys((*A2, *A3, *A4_READINESS)))


def git_value(*arguments: str) -> str | None:
    try:
        result = subprocess.run(
            ["git", "-C", str(ROOT), *arguments],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            encoding="utf-8", errors="replace", timeout=10, check=False,
        )
        return result.stdout.strip() if result.returncode == 0 else None
    except (OSError, subprocess.TimeoutExpired):
        return None


def tail_of_log(path: Path, max_lines: int = 18) -> str:
    try:
        return "\n".join(path.read_text(encoding="utf-8", errors="replace").splitlines()[-max_lines:])
    except OSError:
        return "(Log unavailable.)"


def run_phase(name: str, command: list[str], cwd: Path, home: Path, report: Path, index: int) -> dict:
    log = report / f"{index:02d}-{name.lower().replace(' ', '-')}.log"
    env = os.environ.copy()
    env["PILOTODIN_HOME"] = str(home)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    home.mkdir(parents=True, exist_ok=True)
    print(f"\n[{index}/4] {name} ...", flush=True)
    started = time.monotonic()
    error = None
    rc = -1
    try:
        with log.open("w", encoding="utf-8", errors="replace") as out:
            proc = subprocess.run(
                command, cwd=str(cwd), env=env, stdout=out,
                stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                check=False, timeout=900,
            )
        rc = proc.returncode
    except subprocess.TimeoutExpired:
        error = "Timed out after 900 seconds"
    except OSError as exc:
        error = f"Could not start process: {exc}"
    elapsed = round(time.monotonic() - started, 1)
    status = "PASS" if rc == 0 and not error else "FAIL"
    print(f"    {status} ({elapsed}s) | {log.name}", flush=True)
    if status == "FAIL":
        print("    " + (error or f"Exit code {rc}"), flush=True)
        print(tail_of_log(log), flush=True)
    return {"name": name, "status": status, "exit_code": rc,
            "seconds": elapsed, "log": log.name, "error": error}



def package_results(report: Path, result: dict) -> Path:
    """Bundle diagnostics only. Never include the isolated test projects or models."""
    summary = report / "result.json"
    summary.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    archive = report.with_suffix(".zip")
    files = sorted(report.glob("*.log"))
    files += [file for file in (summary, report / "backend-junit.xml") if file.is_file()]
    with ZipFile(archive, "w", compression=ZIP_DEFLATED) as bundle:
        bundle.writestr(
            "README.txt",
            "PilotODIN automated A2/A3/A4 verification diagnostics.\n"
            "The archive intentionally excludes isolated synthetic project data, model files "
            "and raw datasets.\n"
            "Review logs for local machine paths before sharing.\n"
            "PASS here does not certify the desktop UI, native Save As or offline installer.\n"
        )
        for file in files:
            bundle.write(file, arcname=file.name)
    print(f"Shareable diagnostics ZIP: {archive}", flush=True)
    return archive


def main() -> int:
    report = Path(tempfile.mkdtemp(prefix="pilotodin-p0-a4-readiness-"))
    home = report / "isolated-app-data"
    report_json = report / "result.json"
    branch = git_value("rev-parse", "--abbrev-ref", "HEAD")
    commit = git_value("rev-parse", "HEAD")
    dirty = git_value("status", "--porcelain")
    print("PilotODIN P0 -> A4 consolidated readiness validation")
    print(f"Repository branch: {branch or 'unavailable'}")
    print(f"Commit: {commit or 'unavailable'}")
    print(f"Local report directory: {report}")
    print("No hosted Actions, cloud calls, installer builds, or production project edits.")
    print("The local test result is NOT an A3 visual or A4 release sign-off.\n")

    expected_python = ROOT / ".venv-live" / "Scripts" / "python.exe"
    npm = shutil.which("npm.cmd") or shutil.which("npm")
    missing = [str(ROOT / "tests" / filename) for filename in TEST_FILES
               if not (ROOT / "tests" / filename).is_file()]
    blockers = []
    if branch != BRANCH:
        blockers.append(f"Wrong or unavailable branch: expected {BRANCH}, found {branch!r}")
    if not expected_python.is_file() or Path(sys.executable).resolve() != expected_python.resolve():
        blockers.append("Use the isolated .venv-live Python via Run_PilotODIN_P0_A4_Verification.bat")
    if not npm:
        blockers.append("npm.cmd/npm not found. Use the existing Windows dev environment.")
    if not (ROOT / "frontend" / "node_modules").is_dir():
        blockers.append("frontend/node_modules missing. Existing dev dependencies must be installed.")
    if missing:
        blockers.append("Required test files missing: " + ", ".join(missing))

    result = {
        "purpose": "P0 A2/A3 baseline regressions and A4-1/A4-2/A4-3 integration gate",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "branch": branch, "commit": commit, "uncommitted_changes": bool(dirty),
        "dataset_home": "isolated temporary folder (never production)",
        "test_modules": TEST_FILES, "phases": [], "preflight_blockers": blockers,
        "manual_acceptance": "PENDING",
        "offline_8gb_native_release": "NOT TESTED",
    }
    if dirty:
        print("NOTE: Local checkout has uncommitted changes; record the exact tested tree.")
    if blockers:
        for reason in blockers:
            print(f"PRECHECK FAILED: {reason}")
        result["automated_status"] = "FAIL"
        package_results(report, result)
        print(f"Summary: {report_json}")
        return 1

    phases = [
        ("Frontend behaviour", [npm, "run", "test:workspace"], ROOT / "frontend"),
        ("Frontend TypeScript and Vite build", [npm, "run", "build"], ROOT / "frontend"),
        ("Backend syntax", [sys.executable, "-m", "compileall", "-q", "backend"], ROOT),
        ("A2 A3 A4 backend regressions",
         [sys.executable, "-m", "pytest", "-q",
          f"--junitxml={report / 'backend-junit.xml'}",
          *[str(Path("tests") / filename) for filename in TEST_FILES]], ROOT),
    ]
    for index, (name, command, cwd) in enumerate(phases, start=1):
        result["phases"].append(run_phase(name, command, cwd, home, report, index))

    junit = report / "backend-junit.xml"
    if junit.exists():
        try:
            tree = ET.parse(junit)
            suite = tree.getroot().find("testsuite") if tree.getroot().tag == "testsuites" else tree.getroot()
            if suite is not None:
                result["pytest_counts"] = {
                    key: int(suite.attrib.get(key, "0"))
                    for key in ("tests", "failures", "errors", "skipped")
                }
        except (ET.ParseError, ValueError):
            result["pytest_counts"] = {"warning": "Could not parse junit results"}

    passed = all(phase["status"] == "PASS" for phase in result["phases"])
    result["automated_status"] = "PASS" if passed else "FAIL"
    package_results(report, result)
    print("\n" + "=" * 66)
    print(f"AUTOMATED P0/A4 READINESS: {result['automated_status']}")
    if "pytest_counts" in result:
        print(f"Backend pytest counts: {result['pytest_counts']}")
    print("Manual Windows journey, A4 visual/native export, and 8 GB/offline installer: NOT signed off")
    print("No QA issue or GitHub status was automatically changed.")
    print(f"Result JSON and phase logs: {report}")
    print("=" * 66)
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
