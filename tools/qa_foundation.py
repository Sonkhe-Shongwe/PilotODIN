#!/usr/bin/env python3
"""PilotODIN DevQA v1. Isolated local runs and conservative source preflight.
Standard library only. No Tauri, FastAPI, ML, installers or user data access.
"""
from __future__ import annotations
import argparse
import datetime as dt
import hashlib
import io
import json
import os
from pathlib import Path
import re
import sys
import unittest
import uuid
import zipfile

ROOT = Path(__file__).resolve().parents[1]
PHASE_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_-]{1,39}$")
PS_RESERVED = re.compile(r"(?im)^\s*\$(home|host|pid|profile|input|matches|error)\s*(?:=|\+=|-=|\+\+|--)(?!=)")
RISKS = [
    ("PATH-01", "Verify the actual native Save As folder and exact output filenames"),
    ("PDF-01", "Control changing PDF metadata if hashing independently generated PDF renders"),
    ("HTTP-01", "Check browser-visible response headers across CORS boundaries, not just raw API headers"),
    ("ENV-01", "Check protected PowerShell variables and process environment cleanup"),
    ("EVID-01", "Collect diagnostics on early failure; never promote partial PASS"),
    ("DATA-01", "Isolate synthetic inputs, database and model directories from user projects"),
    ("RECOVERY-01", "Retry only the affected independent check where safe"),
]

def default_root(environ=None):
    env = os.environ if environ is None else environ
    base = env.get("LOCALAPPDATA")
    if not base or not Path(base).is_absolute():
        raise ValueError("Windows LOCALAPPDATA must be an absolute directory")
    return Path(base) / "PilotODIN" / "DevQA"

def safe_root(path, repo=ROOT, environ=None):
    env = os.environ if environ is None else environ
    if not path.is_absolute():
        raise ValueError("QA root must be an absolute folder")
    dest, checkout = path.resolve(), repo.resolve()
    if dest == checkout or dest.is_relative_to(checkout) or checkout.is_relative_to(dest):
        raise ValueError("QA workspace cannot overlap repository")
    if env.get("PILOTODIN_HOME"):
        live = Path(env["PILOTODIN_HOME"]).resolve()
        if dest == live or dest.is_relative_to(live) or live.is_relative_to(dest):
            raise ValueError("QA workspace cannot overlap product PILOTODIN_HOME")
    for node in (path, *path.parents):
        if node.exists() and (node.is_symlink() or getattr(os.path, "isjunction", lambda _: False)(node)):
            raise ValueError("QA workspace must not pass through a symlink or junction")
    return dest

def create_run(root, phase, repo=ROOT):
    if not PHASE_RE.fullmatch(phase):
        raise ValueError("Phase must use 2-40 ASCII letters/digits/_/- and start with a letter")
    root = safe_root(root, repo)
    (root / "runs").mkdir(parents=True, exist_ok=True)
    (root / "archive").mkdir(exist_ok=True)
    name = phase.upper() + "-" + dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:10]
    run = root / "runs" / name
    run.mkdir(exist_ok=False)
    for part in ("workspace", "fixtures", "exports", "logs", "diagnostics"):
        (run / part).mkdir()
    manifest = {
        "schema_version": 1, "run_id": name, "phase": phase,
        "created_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "state": "READY_NOT_TESTED", "product_acceptance": "NOT_TESTED",
        "risk_register": [{"id": code, "question": question, "status": "NOT_TESTED"} for code, question in RISKS],
        "relative_paths": {"backend": "workspace", "exports": "exports", "logs": "logs"},
        "rules": {"synthetic_only": True, "no_auto_delete": True, "no_model_or_installer": True},
    }
    with (run / "manifest.json").open("x", encoding="utf-8") as out:
        json.dump(manifest, out, indent=2)
        out.write("\n")
    return run, manifest

def preflight_text(path, source):
    """Conservative hints, NOT a complete PowerShell parser."""
    findings = []
    if path.suffix.lower() == ".ps1":
        for match in PS_RESERVED.finditer(source):
            line = source.count("\n", 0, match.start()) + 1
            findings.append({"id": "PS-RESERVED", "severity": "BLOCK",
                             "detail": "Possible reserved PowerShell variable assignment at line " + str(line) + ": " + match.group(1)})
        if "Read-Host" in source and "Test-Path" in source and not any(
            marker in source for marker in ("IsPathRooted", "GetFullPath", "Downloads'", 'Downloads"')
        ):
            findings.append({"id": "SAVE-PATH", "severity": "REVIEW",
                             "detail": "User-selected folder might be relative; verify full Save As path"})
        if "Get-FileHash" in source and "pdf" in source.lower() and "referenceHash" in source and "RL_invariant" not in source:
            findings.append({"id": "PDF-RENDER", "severity": "REVIEW",
                             "detail": "Cross-render PDF digests may change with timestamps and IDs"})
        if "Start-Process" in source and "finally" not in source:
            findings.append({"id": "CLEANUP", "severity": "REVIEW",
                             "detail": "No obvious finally cleanup for test-owned subprocess"})
    if path.suffix.lower() == ".py":
        try:
            compile(source, str(path), "exec", dont_inherit=True)
        except SyntaxError as exc:
            findings.append({"id": "PY-SYNTAX", "severity": "BLOCK",
                             "detail": "Line " + str(exc.lineno) + ": " + str(exc.msg)})
    return findings

def scan_files(repo, names):
    if not names:
        raise ValueError("Preflight needs explicitly selected repository-relative files")
    findings = []
    for name in names:
        source = (repo / name).resolve()
        if not source.is_relative_to(repo.resolve()):
            raise ValueError("Preflight cannot read outside repository")
        if not source.is_file() or source.suffix.lower() not in (".ps1", ".py", ".bat"):
            raise ValueError("Missing or unsupported source file: " + name)
        for issue in preflight_text(source, source.read_text(encoding="utf-8-sig")):
            findings.append({"file": name, **issue})
    return findings, sum(item["severity"] == "BLOCK" for item in findings)

def verify_existing(run, expectations):
    """Check only exact synthetic basenames in a known run's exports folder."""
    if not run.is_dir() or not (run / "manifest.json").is_file():
        raise ValueError("Valid existing QA run required")
    exports_path = run / "exports"
    is_link = lambda p: p.is_symlink() or getattr(p, "is_junction", lambda: False)()
    if is_link(run) or is_link(run / "manifest.json") or is_link(exports_path):
        raise ValueError("Refuse linked QA run, manifest or exports directory")
    base = exports_path.resolve()
    if not base.is_dir() or base.parent != run.resolve():
        raise ValueError("QA exports must be directly inside this run")
    results = []
    for name, expected in expectations.items():
        if Path(name).name != name or name in (".", "..") or not re.fullmatch(r"[a-fA-F0-9]{64}", expected):
            raise ValueError("Expected exact basename and SHA-256")
        target = base / name
        if is_link(target) or not target.is_file():
            results.append({"filename": name, "status": "MISSING"})
        else:
            hasher = hashlib.sha256()
            with target.open("rb") as stream:
                for block in iter(lambda: stream.read(1024 * 1024), b""):
                    hasher.update(block)
            results.append({"filename": name, "status": "PASS" if hasher.hexdigest() == expected.lower() else "SHA_MISMATCH"})
    return results

def check_setup(phase, root, repo=ROOT, scan=None):
    run, manifest = create_run(root, phase, repo)
    output = io.StringIO()
    count, test_ok = 0, False
    try:
        suite = unittest.defaultTestLoader.discover(str(repo / "tests"), pattern="test_qa_foundation.py")
        count = suite.countTestCases()
        if count:
            test_ok = unittest.TextTestRunner(stream=output, verbosity=2).run(suite).wasSuccessful()
        else:
            output.write("BLOCK: No foundation tests were found.\n")
    except Exception as exc:
        # A broken test loader is itself a failed test, not a missing diagnosis.
        output.write("BLOCK: Foundation test discovery/execution failed: " + repr(exc) + "\n")
    log = run / "logs" / "foundation-tests.txt"
    log.write_text(output.getvalue(), encoding="utf-8")
    selected = scan if scan is not None else ["tools/qa_foundation.py", "tools/Verify_P2_Native_Live_Report_Local.ps1"]
    try:
        issues, blockers = scan_files(repo, selected)
    except (ValueError, OSError) as exc:
        issues, blockers = [{"id": "PREFLIGHT-ERROR", "severity": "BLOCK", "detail": str(exc)}], 1
    state = "BLOCKED" if blockers or not test_ok else ("REVIEW_REQUIRED" if issues else "READY_FOR_SCOPED_TESTS")
    result = {"schema_version": 1, "run_id": manifest["run_id"], "state": state,
              "product_acceptance": "NOT_TESTED",
              "self_tests": {"count": count, "status": "PASS" if test_ok else "FAIL"},
              "preflight_files": selected, "findings": issues, "blockers": blockers,
              "note": "Static checks are risk prompts, not product or Windows native acceptance."}
    # Record test readiness while retaining explicit NOT_TESTED product acceptance.
    manifest["state"] = state
    (run / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    status = run / "diagnostics" / "result.json"
    status.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    archive = run.parent.parent / "archive" / (run.name + ".zip")
    with zipfile.ZipFile(archive, "x", zipfile.ZIP_DEFLATED) as bundle:
        bundle.write(status, arcname="result.json")
        bundle.write(log, arcname="foundation-tests.txt")
    result["diagnostic_zip"] = str(archive)
    return run, result

def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="action", required=True)
    p_init = sub.add_parser("init")
    p_init.add_argument("--phase", required=True)
    p_init.add_argument("--qa-root", type=Path)
    p_init.add_argument("--json", action="store_true", help="Print one machine-readable run-path JSON object")
    p_check = sub.add_parser("check")
    p_check.add_argument("--phase", default="FRAMEWORK-V1")
    p_check.add_argument("--qa-root", type=Path)
    p_check.add_argument("--scan", nargs="+")
    p_scan = sub.add_parser("preflight")
    p_scan.add_argument("files", nargs="+")
    args = parser.parse_args(argv)
    try:
        if args.action == "init":
            run, _ = create_run(args.qa_root or default_root(), args.phase)
            if args.json:
                print(json.dumps({
                    "status": "READY_NOT_TESTED",
                    "run_dir": str(run),
                    "exports_dir": str(run / "exports"),
                    "workspace_dir": str(run / "workspace"),
                    "logs_dir": str(run / "logs"),
                    "archive_dir": str(run.parent.parent / "archive"),
                    "product_acceptance": "NOT_TESTED"
                }))
            else:
                print("READY_NOT_TESTED: " + str(run))
                print("EXPORTS: " + str(run / "exports"))
            return 0
        if args.action == "check":
            run, result = check_setup(args.phase, args.qa_root or default_root(), scan=args.scan)
            print("QA FOUNDATION: " + result["state"] + " (product acceptance NOT_TESTED)")
            print("RUN: " + str(run))
            print("EXPORTS: " + str(run / "exports"))
            print("SELF TESTS: " + str(result["self_tests"]["count"]) + " " + result["self_tests"]["status"])
            for issue in result["findings"]:
                print(issue["severity"] + " " + issue["id"] + ": " + issue["detail"])
            print("DIAGNOSTIC ZIP (test-local paths possible): " + result["diagnostic_zip"])
            return 2 if result["state"] == "BLOCKED" else 0
        issues, blocked = scan_files(ROOT, args.files)
        print(json.dumps({"status": "BLOCKED" if blocked else "REVIEW_READY", "findings": issues}, indent=2))
        return 2 if blocked else 0
    except (ValueError, OSError) as exc:
        print("QA FOUNDATION FAIL: " + str(exc), file=sys.stderr)
        return 1

if __name__ == "__main__":
    raise SystemExit(main())
