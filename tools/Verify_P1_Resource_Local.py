#!/usr/bin/env python3
"""Focused P1 resource-settings verification: no full P0 replay or AI inference."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    report = Path(tempfile.mkdtemp(prefix="pilotodin-p1-resource-"))
    home = report / "isolated-home"
    home.mkdir()
    env = os.environ.copy()
    env["PILOTODIN_HOME"] = str(home)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    npm = shutil.which("npm.cmd") or shutil.which("npm")
    node = shutil.which("node.exe") or shutil.which("node")
    phases = [
        ("backend-resource-policy", [sys.executable, "-m", "pytest", "-q",
                                     "tests/test_p1_resource_policy.py"], ROOT),
        ("frontend-resource-controls", [node, "--test",
                                        "tests/p1-resource-settings.test.cjs"], ROOT / "frontend"),
        ("frontend-typescript-vite", [npm, "run", "build"], ROOT / "frontend"),
    ]
    checks = []
    for name, command, cwd in phases:
        started = time.monotonic()
        log = report / (name + ".log")
        if not command[0]:
            log.write_text("Runtime tool not available.\n", encoding="utf-8")
            code = -1
        else:
            try:
                with log.open("w", encoding="utf-8", errors="replace") as out:
                    run = subprocess.run(command, cwd=cwd, env=env, stdout=out,
                                         stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                                         check=False, timeout=360)
                code = run.returncode
            except (OSError, subprocess.TimeoutExpired) as exc:
                log.write_text(type(exc).__name__ + ": " + str(exc),
                               encoding="utf-8", errors="replace")
                code = -1
        checks.append({"phase": name, "result": "PASS" if code == 0 else "FAIL",
                       "exit_code": code, "elapsed_seconds": round(time.monotonic() - started, 1),
                       "log": log.name})
        print(f"{name}: {checks[-1]['result']}", flush=True)
        if code != 0:
            print("\n".join(log.read_text(encoding="utf-8", errors="replace").splitlines()[-18:]))
    result = {
        "purpose": "P1 resource preference/physical RAM read-only settings",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "phases": checks,
        "status": "PASS" if all(c["result"] == "PASS" for c in checks) else "FAIL",
        "owner_dataset": "NOT_ACCESSED",
        "p0_a4_full_regressions": "NOT_RERUN",
        "resource_preflight_and_heavy_task_scheduler": "NOT_IMPLEMENTED",
        "offline_qwen_and_real_8gb_combined_load": "NOT_TESTED",
    }
    (report / "result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    archive = report.with_suffix(".zip")
    with ZipFile(archive, "w", compression=ZIP_DEFLATED) as zipfile:
        for path in sorted(report.glob("*.log")) + [report / "result.json"]:
            zipfile.write(path, arcname=path.name)
    print("P1 Resource-Aware Settings status:", result["status"])
    print("No AI model was loaded; existing datasets were not modified.")
    print("Diagnostics ZIP (review logs for local paths):", archive)
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
