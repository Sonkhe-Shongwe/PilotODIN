#!/usr/bin/env python3
"""PilotODIN P1 automated acceptance macro; owner-safe, isolated, no release claims.

No installation, background server, external HTTP test, model inference,
existing-process termination, file deletion or modification of user projects.
The GitHub-only real-HTTP suite is deliberately not run on a local desktop.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

ROOT = Path(__file__).resolve().parents[1]
BRANCH = "feature/live-dev-workspace-20261023"
BROWSER_GREP = ("keyboard Tab Shift-Tab|keyboard dock resize|simulated 150 percent|"
                "primary Studio dirty Prepare cannot enter Investigation|"
                "isolated import Quality and failed project switch")
MANUAL_GATES = [
    "P1-N1_native_full_recovery", "WIN-S1_original_scale", "WIN-S2_125_percent",
    "WIN-S3_150_percent", "WIN-S4_Windows_Snap",
    "WIN-A1_reduced_motion", "WIN-A2_Narrator",
    "P1-R1_real_UI_Ram", "P1-C1_closure"
]


def command_capture(args: list[str], cwd: Path = ROOT, timeout: int = 20):
    return subprocess.run(args, cwd=cwd, input="", stdout=subprocess.PIPE,
                          stderr=subprocess.STDOUT, encoding="utf-8",
                          errors="replace", timeout=timeout, check=False)


def git_preflight(root: Path) -> dict:
    results = {}
    for name, args in [
        ("root", ["git", "rev-parse", "--show-toplevel"]),
        ("branch", ["git", "branch", "--show-current"]),
        ("head", ["git", "rev-parse", "HEAD"]),
        ("dirty", ["git", "status", "--porcelain", "--untracked-files=no"]),
    ]:
        try:
            result = command_capture(args, root)
        except (OSError, subprocess.TimeoutExpired):
            return {"status": "BLOCKED", "reason": "Git is unavailable"}
        if result.returncode:
            return {"status": "BLOCKED", "reason": "Git preflight failed: " + name}
        results[name] = result.stdout.strip()
    report = {
        "branch": results["branch"], "sha": results["head"],
        "tracked_changes": bool(results["dirty"]), "status": "PASS"
    }
    if Path(results["root"]).resolve() != root.resolve():
        report.update(status="BLOCKED", reason="Incorrect Git root")
    elif results["branch"] != BRANCH:
        report.update(status="BLOCKED", reason="Wrong development branch")
    elif results["dirty"]:
        report.update(status="BLOCKED", reason="Tracked local changes require review")
    return report


def occupied_ports() -> dict:
    """No connection is made to any backend; netstat is read-only."""
    result = {str(p): "UNKNOWN" for p in (8000, 5174, 5187)}
    try:
        snapshot = command_capture(["netstat", "-ano", "-p", "TCP"], timeout=12)
    except (OSError, subprocess.TimeoutExpired):
        return result
    if snapshot.returncode:
        return result
    for port in result:
        pattern = re.compile(r"^\s*TCP\s+\S+:" + port + r"\s+\S+\s+LISTENING\b", re.I)
        result[port] = ("IN_USE" if any(pattern.search(line) for line in
                                      snapshot.stdout.splitlines()) else "FREE")
    return result


def phase(name: str, args: list[str] | None, cwd: Path, home: Path,
          directory: Path, block: str | None = None, timeout: int = 360) -> dict:
    log = directory / (name + ".log")
    if block or not args:
        reason = block or "Required developer tool missing; no install attempted"
        log.write_text(reason + "\n", encoding="utf-8")
        print(f"  {name}: BLOCKED ({reason})", flush=True)
        return {"gate": name, "status": "BLOCKED", "reason": reason, "log": log.name}
    env = os.environ.copy()
    env["PILOTODIN_HOME"] = str(home)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    started = time.monotonic()
    try:
        with log.open("w", encoding="utf-8", errors="replace") as stream:
            completed = subprocess.run(args, cwd=cwd, env=env, stdin=subprocess.DEVNULL,
                                       stdout=stream, stderr=subprocess.STDOUT,
                                       timeout=timeout, check=False)
        code = completed.returncode
        outcome = "PASS" if code == 0 else "FAIL"
    except subprocess.TimeoutExpired:
        code, outcome = None, "FAIL"
        with log.open("a", encoding="utf-8") as stream:
            stream.write("\nTest timed out. Only macro-owned subprocess may be stopped.\n")
    except OSError as exc:
        code, outcome = None, "BLOCKED"
        with log.open("a", encoding="utf-8") as stream:
            stream.write("\nCould not launch: " + type(exc).__name__ + "\n")
    duration = round(time.monotonic() - started, 1)
    print(f"  {name}: {outcome} ({duration}s)", flush=True)
    return {"gate": name, "status": outcome, "exit_code": code,
            "duration_sec": duration, "log": log.name}


def overall(phases: list[dict]) -> str:
    if any(x["status"] == "FAIL" for x in phases):
        return "AUTOMATED_FAILURE_REQUIRES_REVIEW"
    if any(x["status"] == "BLOCKED" for x in phases):
        return "AUTOMATED_PARTIAL_WITH_BLOCKERS"
    return "AUTOMATED_SUBSET_PASS_NOT_P1_CLOSURE"


def main_run(root: Path = ROOT, parent: Path | None = None,
             with_browser: bool = True, require_windows: bool = True) -> tuple[Path, dict]:
    if require_windows and os.name != "nt":
        raise RuntimeError("Only execute full macro on Windows; unit tests are cross-platform")
    directory = (parent or Path(tempfile.gettempdir())) / (
        "pilotodin-p1-macro-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        + "-" + uuid.uuid4().hex[:8])
    directory.mkdir(parents=True)
    home = directory / "synthetic-only-home"
    home.mkdir()
    git = git_preflight(root)
    ports = occupied_ports()
    output = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "source": git, "pre_existing_listeners": ports,
        "owner_backend_contacted": False, "owner_projects_modified": False,
        "temporary_data_only": True, "ci_real_http": "NOT_RUN_LOCAL_CI_ONLY",
        "native_webview2": "NOT_RUN_BY_MACRO",
        "physical_display_and_narrator": "NOT_RUN_BY_MACRO",
        "offline_ai_ml_8gb": "NOT_TESTED",
        "p1_closure": "OPEN_REQUIRES_OWNER_DECISION",
        "native_manual_gates": {name: "NOT_RUN" for name in MANUAL_GATES},
        "checks": [],
    }
    checks = []
    if git["status"] != "PASS":
        checks.append(phase("safety-preflight", None, root, home, directory,
                            block=git.get("reason", "Git blocked")))
    else:
        python = root / ".venv-live" / "Scripts" / "python.exe"
        python = str(python) if python.is_file() else None
        node = shutil.which("node.exe") or shutil.which("node")
        npm = shutil.which("npm.cmd") or shutil.which("npm")
        frontend = root / "frontend"
        browser = frontend / "node_modules" / ".bin" / "playwright.cmd"
        if not browser.is_file():
            browser = frontend / "node_modules" / ".bin" / "playwright"
        print("Running isolated P1 macro; existing servers will be left alone...", flush=True)
        checks.append(phase("project-recovery-backend",
                            [python, "-B", "-m", "pytest", "-q", "-p", "no:cacheprovider",
                             "tests/test_p1_real_api_failed_switch.py"] if python else None,
                            root, home, directory, block=None if python else "Missing .venv-live Python"))
        checks.append(phase("resource-policy-backend",
                            [python, "-B", "-m", "pytest", "-q", "-p", "no:cacheprovider",
                             "tests/test_p1_resource_policy.py",
                             "tests/test_p1_resource_admission.py"] if python else None,
                            root, home, directory, block=None if python else "Missing .venv-live Python"))
        tests = ["tests/p1-external-project-transition-guard.test.cjs",
                 "tests/p1-project-switch-generation.test.cjs",
                 "tests/p1-primary-project-load-approval.test.cjs",
                 "tests/p1-resource-settings.test.cjs"]
        checks.append(phase("frontend-project-and-resource",
                            [node, "--test", *tests] if node else None,
                            frontend, home, directory, block=None if node else "Node missing"))
        checks.append(phase("frontend-typescript-and-build",
                            [npm, "run", "build"] if npm else None,
                            frontend, home, directory, block=None if npm else "npm missing"))
        if not with_browser:
            browser_block = "Explicitly skipped browser phase"
        elif ports["5187"] != "FREE":
            browser_block = "Isolated port 5187 not FREE; no listener was stopped"
        elif not browser.is_file():
            browser_block = "Local Playwright binary missing; no download attempted"
        else:
            browser_block = None
        checks.append(phase("chromium-isolated-five-cases",
                            [str(browser), "test", "--config=playwright.config.ts",
                             "-g", BROWSER_GREP] if browser.is_file() else None,
                            frontend, home, directory, block=browser_block))
        ps = shutil.which("powershell.exe") or shutil.which("powershell")
        probe = root / "tools" / "Probe_E2_8GB_Offline_Inventory.ps1"
        if os.name == "nt":
            checks.append(phase("windows-read-only-memory-inventory",
                                [ps, "-NoProfile", "-ExecutionPolicy", "Bypass",
                                 "-File", str(probe), "-OutputPath",
                                 str(directory / "resource_inventory.json")]
                                if ps and probe.is_file() else None,
                                root, home, directory, timeout=60,
                                block=None if ps and probe.is_file() else "PowerShell/probe missing"))
    output["checks"] = checks
    output["status"] = overall(checks)
    guide = root / "docs" / "P1_MACRO_NATIVE_CHECKLIST.md"
    checklist = (guide.read_text(encoding="utf-8") if guide.is_file()
                 else "Manual checklist missing: keep all native gates NOT RUN.\n")
    (directory / "manual_checklist.md").write_text(checklist, encoding="utf-8")
    (directory / "result.json").write_text(json.dumps(output, indent=2) + "\n",
                                            encoding="utf-8")
    (directory / "README.txt").write_text(
        "Evidence is scoped to executed isolated tests. Manual/native gates remain NOT_RUN.\n"
        "Logs can expose local system paths: review before sharing. No release proof.\n",
        encoding="utf-8")
    archive = directory.with_suffix(".zip")
    with ZipFile(archive, "w", compression=ZIP_DEFLATED) as z:
        for path in sorted(directory.iterdir()):
            if path.is_file():
                z.write(path, arcname=path.name)
    print("\nP1 AUTOMATED RESULT: " + output["status"], flush=True)
    print("One evidence ZIP: " + str(archive), flush=True)
    print("Check manual_checklist.md inside it for remaining actual Windows gates.", flush=True)
    print("No native signoff, model-stress or release certification is implied.", flush=True)
    return archive, output


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--skip-browser", action="store_true")
    a = p.parse_args()
    _, evidence = main_run(with_browser=not a.skip_browser)
    sys.exit(0 if evidence["status"] == "AUTOMATED_SUBSET_PASS_NOT_P1_CLOSURE" else 1)
