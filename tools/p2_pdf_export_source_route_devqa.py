#!/usr/bin/env python3
"""One consolidated source-only P2 PDF export integration check on Windows.

Uses existing interpreter, no dependency installation, font assets, network,
real projects, real PDF, sidecar build or saved persistent QA file. All backend
imports occur in child processes with isolated PILOTODIN_HOME set BEFORE
backend.storage initializes its database. Only safe final JSON is printed.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import subprocess
import sys
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[1]
SUITES = (
    ("offline_source", "test_p2_pdf_release_export_gate.py", 14),
    ("actual_http_route", "test_p2_pdf_export_route_integration.py", 9),
)
TEST_TIMEOUT_SECONDS = 90
_COUNT = re.compile(r"\bRan\s+(\d+)\s+tests?\s+in\b")
_SKIPS = re.compile(r"\bskipped\s*=\s*\d+", re.I)


def run() -> dict:
    if sys.platform != "win32":
        raise ValueError("Windows-only scoped owner API acceptance")
    if not (ROOT / "backend" / "pdf_release_font_loader.py").is_file():
        raise ValueError("Missing source-checkout export loader")
    evidence = []
    with TemporaryDirectory(prefix="pilotodin-p2-export-isolated-") as location:
        home = Path(location) / "home"
        home.mkdir()
        (home / ".pilotodin-p2-export-route-devqa").write_text(
            "SYNTHETIC_TEMP_ONLY", encoding="ascii")
        env = dict(os.environ)
        for key in (
            "PILOTODIN_DESKTOP_SESSION", "PILOTODIN_DESKTOP_ALLOW_DEV",
            "PILOTODIN_P2_REAL_SIDECAR_DEVQA",
            "PILOTODIN_P2_DEVQA_ATTESTATION",
        ):
            env.pop(key, None)
        env["PILOTODIN_HOME"] = str(home)
        env["PILOTODIN_P2_EXPORT_ROUTE_DEVQA"] = "1"
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        env["PYTHONIOENCODING"] = "utf-8"
        for name, pattern, expected in SUITES:
            try:
                result = subprocess.run(
                    [sys.executable, "-B", "-m", "unittest", "discover",
                     "-s", "tests", "-p", pattern, "-v"],
                    cwd=str(ROOT), env=env, capture_output=True,
                    text=True, encoding="utf-8", errors="replace",
                    timeout=TEST_TIMEOUT_SECONDS, check=False,
                )
            except subprocess.TimeoutExpired as exc:
                raise ValueError("Focused suite timed out: " + name) from exc
            output = (result.stdout or "") + "\n" + (result.stderr or "")
            matches = _COUNT.findall(output)
            if (result.returncode != 0 or not matches or
                    int(matches[-1]) != expected or
                    _SKIPS.search(output) or
                    not re.search(r"(?m)^OK\s*$", output)):
                # Do NOT print potentially private exception traces or paths.
                raise ValueError("Focused source suite blocked: " + name)
            evidence.append({"suite": name, "new_tests_passed": expected})

    return {
        "state": "SCOPED_OFFLINE_EXPORT_ROUTE_SOURCE_PASS",
        "stage": "existing_authenticated_report_endpoint",
        "new_tests_passed": sum(x["new_tests_passed"] for x in evidence),
        "source_suites": evidence,
        "api_exercised_in_process": True,
        "test_report_data": "SYNTHETIC_OR_MOCK_ONLY",
        "real_user_data_accessed": False,
        "old_p2_gates_repeated": False,
        "fonts_distributed": False,
        "release_approval": "NOT_GRANTED",
        "end_user_unicode_pdf": "NOT_ACCEPTED",
        "native_installer": "NOT_TESTED",
        "real_concurrent_export": "NOT_TESTED",
    }


def main() -> int:
    try:
        status = run()
    except Exception as exc:
        status = {
            "state": "BLOCKED",
            "stage": "offline_export_source_and_http_route",
            "failure_class": type(exc).__name__,
            "release_approval": "NOT_GRANTED",
            "end_user_unicode_pdf": "NOT_ACCEPTED",
            "native_installer": "NOT_TESTED",
        }
    print("P2 INTEGRATED PDF EXPORT SOURCE DEVQA: " + status["state"])
    print(json.dumps(status, indent=2))
    return 0 if status["state"] == "SCOPED_OFFLINE_EXPORT_ROUTE_SOURCE_PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
