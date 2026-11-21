#!/usr/bin/env python3
"""Seed ONLY one disposable four-row CSV for the P2 native-shell consent QA.

No saved report, model, Quality mutation, PDF export or real user project.
The validated DevQA manifest and PILOTODIN_HOME identify the only writable run.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
PHASE = "P2-NATIVE-DELIVER-CONSENT"
CSV = b"OrderID,Region,Revenue\nQA001,North,120\nQA002,South,220\nQA003,North,310\nQA004,South,440\n"


def main() -> int:
    if len(sys.argv) != 2:
        raise RuntimeError("Expected one absolute synthetic manifest destination")
    explicit_home = os.environ.get("PILOTODIN_HOME")
    if not explicit_home:
        raise RuntimeError("PILOTODIN_HOME must identify a fresh isolated DevQA workspace")
    home = Path(explicit_home).resolve(strict=True)
    output = Path(sys.argv[1]).resolve()
    session = home.parent
    qa = json.loads((session / "manifest.json").read_text(encoding="utf-8-sig"))
    if (not home.is_dir() or home.name != "workspace"
            or output.parent != session / "fixtures"
            or output.name != "synthetic-consent-manifest.json"
            or qa.get("phase") != PHASE
            or qa.get("state") != "READY_NOT_TESTED"
            or qa.get("product_acceptance") != "NOT_TESTED"
            or output.exists()
            or any(home.iterdir())
            or os.environ.get("PILOTODIN_DESKTOP_SESSION")):
        raise RuntimeError("Refusing unverified or non-empty synthetic DevQA workspace")
    for node in (session, session / "manifest.json", home, output.parent):
        if node.is_symlink() or getattr(node, "is_junction", lambda: False)():
            raise RuntimeError("Refusing redirected DevQA path")
    sys.path.insert(0, str(ROOT))
    from fastapi.testclient import TestClient
    from backend.main import app
    from backend import storage

    response = TestClient(app).post(
        "/api/projects",
        files={"file": ("p2-native-consent-synthetic.csv", CSV, "text/csv")},
    )
    if response.status_code != 201:
        raise RuntimeError(f"Synthetic project creation failed: HTTP {response.status_code}")
    project_id = response.json()["id"]
    if not re.fullmatch(r"[a-f0-9]{32}", project_id):
        raise RuntimeError("Backend returned an invalid project identity")
    source = Path(storage.get_project(project_id)["dataset_path"]).resolve(strict=True)
    if (not source.is_relative_to((home / "datasets").resolve())
            or source.read_bytes() != CSV):
        raise RuntimeError("Source dataset not unchanged inside the isolated workspace")
    output.write_text(json.dumps({
        "phase": PHASE, "run_id": qa["run_id"],
        "project_id": project_id, "rows": 4,
        "synthetic_csv_sha256": hashlib.sha256(CSV).hexdigest(),
        "source_relative": str(source.relative_to(home)),
        "scope": "OWNER_NATIVE_DIALOG_OBSERVATION_NOT_ACCEPTANCE",
    }, indent=2) + "\n", encoding="utf-8")
    print("P2 synthetic native consent project seeded and source verified: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
