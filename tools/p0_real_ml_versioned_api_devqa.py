#!/usr/bin/env python3
"""ONE isolated actual P0 ML API lifecycle acceptance, without user projects.

Runs a real logistic-regression training/evaluation/prediction twice (version
0 and approved version 1) on a tiny generated synthetic dataset. All imports
which initialize SQLite occur only in a disposable, marked child process.
No AI/LLM, external datasets, pip/network, font, frozen sidecar or installer.
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
PASS = "SCOPED_P0_REAL_ML_VERSIONED_API_JOURNEY_PASS"


def check() -> dict:
    if sys.platform != "win32":
        raise ValueError("Owner Windows-only real P0 acceptance")
    test = ROOT / "tests" / "test_p0_ml_persistence_version_journey.py"
    if not test.is_file() or not (ROOT / "backend" / "main.py").is_file():
        raise ValueError("P0 checkout source absent")

    with TemporaryDirectory(prefix="pilotodin-p0-ml-real-") as temp_dir:
        root = Path(temp_dir)
        home = root / "home"
        home.mkdir()
        (home / ".pilotodin-p0-real-devqa").write_text(
            "GENERATED_SYNTHETIC_LOCAL_ONLY", encoding="ascii"
        )
        env = dict(os.environ)
        for key in ("PILOTODIN_DESKTOP_SESSION",
                    "PILOTODIN_P2_EXPORT_ROUTE_DEVQA",
                    "PILOTODIN_P2_REAL_SIDECAR_DEVQA",
                    "PYTEST_ADDOPTS"):
            env.pop(key, None)
        env.update({
            "PILOTODIN_HOME": str(home),
            "PILOTODIN_P0_REAL_JOURNEY_DEVQA": "1",
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1",
            "PYTHONIOENCODING": "utf-8",
        })
        command = [
            sys.executable, "-B", "-m", "pytest", "-q",
            "-p", "no:cacheprovider",
            "--basetemp", str(root / "pytest"),
            str(test.relative_to(ROOT)),
        ]
        try:
            completed = subprocess.run(
                command, cwd=ROOT, env=env, capture_output=True,
                text=True, encoding="utf-8", errors="replace",
                timeout=240, check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise ValueError("Scoped P0 real training timed out") from exc

        # Never echo pytest stdout/stderr: it can contain private local paths,
        # stack traces or generated model/cell values. Exactly ONE selected
        # integration test must complete with no skips or xfails.
        printed = (completed.stdout or "") + "\n" + (completed.stderr or "")
        complete = re.search(r"\b1 passed(?:,\s*\d+ warnings?)?\s+in\s+[\d.]+s\b",
                             printed)
        if (completed.returncode != 0 or not complete or
                re.search(r"\b(skipped|failed|xfailed|xpassed|error)\b", printed, re.I)):
            raise ValueError("Actual P0 Prepare/ML/Quality journey did not pass")
    return {
        "state": PASS,
        "stage": "prepare_train_evaluate_predict_quality_retrain",
        "new_actual_api_journey_tests_passed": 1,
        "actual_scikit_learn_trainings": 2,
        "real_local_api_exercised": True,
        "synthetic_csv_only": True,
        "original_upload_immutability_checked": True,
        "quality_approval_receipt_version_bump_checked": True,
        "old_model_stale_prediction_denial_checked": True,
        "new_version_retraining_selection_prediction_checked": True,
        "project_isolation_checked": True,
        "temporary_home_cleaned": True,
        "previous_accepted_p2_tests_repeated": False,
        "interactive_windows_ui": "NOT_TESTED",
        "packaged_offline_installer": "NOT_TESTED",
        "actual_peak_ram": "NOT_MEASURED",
        "font_release_approval": "NOT_GRANTED",
    }


def main() -> int:
    try:
        status = check()
    except Exception as exc:
        status = {
            "state": "BLOCKED",
            "stage": "real_p0_versioned_ml_api",
            "failure_class": type(exc).__name__,
            "interactive_windows_ui": "NOT_TESTED",
            "packaged_offline_installer": "NOT_TESTED",
            "font_release_approval": "NOT_GRANTED",
        }
    print("P0 REAL PREPARE-TO-PREDICT DEVQA: " + status["state"])
    print(json.dumps(status, indent=2))
    return 0 if status["state"] == PASS else 2


if __name__ == "__main__":
    raise SystemExit(main())
