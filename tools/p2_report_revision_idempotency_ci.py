"""Run ONLY P2 report revision contract tests in a new disposable home.

Never imports PilotODIN storage before PILOTODIN_HOME is set, never uses
user project databases, installed apps, bundled fonts, models or installers.
"""
from __future__ import annotations

import os
from pathlib import Path
import sys
import tempfile


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    if not (root / "backend" / "reports.py").is_file():
        raise RuntimeError("Expected PilotODIN source tree")
    with tempfile.TemporaryDirectory(prefix="pilotodin-p2-report-idempotency-") as td:
        home = Path(td) / "synthetic-data-only"
        home.mkdir(mode=0o700)
        (home / ".pilotodin-p2-idempotency-synthetic").write_text(
            "disposable isolated P2 fixture", encoding="utf-8")
        os.environ["PILOTODIN_HOME"] = str(home.resolve())
        os.environ["PILOTODIN_P2_REPORT_IDEMPOTENCY_TEST"] = "1"
        os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
        os.chdir(root)
        import pytest
        return int(pytest.main([
            "-q", "-ra", "-p", "no:cacheprovider",
            "tests/test_p2_report_revision_idempotency.py",
            "tests/test_build_e_persistent_reports.py",
        ]))


if __name__ == "__main__":
    sys.exit(main())
