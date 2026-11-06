#!/usr/bin/env python3
"""Seed exactly two read-only test projects in one fresh disposable DevQA home.

No existing app workspace, real CSV, saved report, model or Quality data is read.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
PHASE = "P2-NATIVE-TWO-WINDOW-DELIVER"
SOURCES = (
    ("p2-two-window-A-synthetic.csv", b"OrderID,Region,Revenue\nA001,North,10\nA002,South,20\nA003,North,30\nA004,South,40\n"),
    ("p2-two-window-B-synthetic.csv", b"OrderID,Region,Revenue\nB001,East,100\nB002,West,200\nB003,East,300\nB004,West,400\n"),
)


def main() -> int:
    if len(sys.argv) != 2:
        raise RuntimeError("Expected one absolute fixture-manifest path")
    raw_home = os.environ.get("PILOTODIN_HOME")
    if not raw_home:
        raise RuntimeError("PILOTODIN_HOME required for disposable DevQA")
    home = Path(raw_home).resolve(strict=True)
    run_dir = home.parent
    fixture = Path(sys.argv[1]).resolve()
    qa = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8-sig"))
    if (home.name != "workspace" or not home.is_dir() or any(home.iterdir())
            or fixture != run_dir / "fixtures" / "two-window-manifest.json"
            or fixture.exists() or qa.get("phase") != PHASE
            or qa.get("state") != "READY_NOT_TESTED"
            or qa.get("product_acceptance") != "NOT_TESTED"
            or os.environ.get("PILOTODIN_DESKTOP_SESSION")):
        raise RuntimeError("Refusing non-empty or non-authorised DevQA workspace")
    for node in (run_dir, run_dir / "manifest.json", home, fixture.parent):
        if node.is_symlink() or getattr(node, "is_junction", lambda: False)():
            raise RuntimeError("Refusing redirected QA location")
    sys.path.insert(0, str(ROOT))
    from fastapi.testclient import TestClient
    from backend.main import app
    from backend import storage
    client = TestClient(app)
    projects = []
    for filename, csv in SOURCES:
        response = client.post("/api/projects", files={"file": (filename, csv, "text/csv")})
        if response.status_code != 201:
            raise RuntimeError(f"Synthetic project setup failed: HTTP {response.status_code}")
        project_id = response.json()["id"]
        if not re.fullmatch(r"[a-f0-9]{32}", project_id):
            raise RuntimeError("Unrecognised synthetic project identity")
        source = Path(storage.get_project(project_id)["dataset_path"]).resolve(strict=True)
        if (not source.is_relative_to((home / "datasets").resolve())
                or source.read_bytes() != csv):
            raise RuntimeError("Synthetic source is outside QA home or mutated")
        projects.append({
            "id": project_id,
            "rows": 4,
            "source_relative": str(source.relative_to(home)),
            "sha256": hashlib.sha256(csv).hexdigest(),
        })
    if projects[0]["id"] == projects[1]["id"]:
        raise RuntimeError("Two different projects were not seeded")
    fixture.write_text(json.dumps({
        "phase": PHASE, "run_id": qa["run_id"],
        "projects": projects, "scope": "SYNTHETIC_TWO_WINDOW_OWNER_VISUAL_NOT_RELEASE",
    }, indent=2) + "\n", encoding="utf-8")
    print("Isolated native two-window A/B synthetic project seeds: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
