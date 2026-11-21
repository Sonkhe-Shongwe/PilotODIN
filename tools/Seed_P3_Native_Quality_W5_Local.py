#!/usr/bin/env python3
"""Create an isolated, deterministic W5 Quality v0 fixture and unverified owner notes.

Only invoked with an empty PilotODIN DevQA run. Never opens user projects.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
PHASE = "P3-NATIVE-QUALITY-W5"
DOMAIN = "Synthetic claim records, owner-described for version zero"
GRAIN = "One synthetic submitted insurance claim per data row"
MEANING = "Synthetic requested insurance claim amount, owner-described"


def source_bytes() -> bytes:
    lines = ["claim_id,claim_amount,policy_number,Region"]
    for i in range(36):
        region = " Mpumalanga " if i in (1, 2) else ("Mpumalanga" if i % 2 == 0 else "Gauteng")
        lines.append(f"W5{i + 1:03d},{100 + i},P{i % 4},{region}")
    return ("\n".join(lines) + "\n").encode("utf-8")


def main() -> int:
    if len(sys.argv) != 2 or not os.environ.get("PILOTODIN_HOME"):
        raise RuntimeError("Require a W5 manifest destination and disposable PILOTODIN_HOME")
    workspace = Path(os.environ["PILOTODIN_HOME"]).resolve(strict=True)
    run = workspace.parent
    output = Path(sys.argv[1]).resolve()
    metadata = json.loads((run / "manifest.json").read_text(encoding="utf-8-sig"))
    if (
        workspace.name != "workspace"
        or not workspace.is_dir()
        or any(workspace.iterdir())
        or output != run / "fixtures" / "p3-native-w5-manifest.json"
        or output.exists()
        or metadata.get("phase") != PHASE
        or metadata.get("state") != "READY_NOT_TESTED"
        or metadata.get("product_acceptance") != "NOT_TESTED"
        or os.environ.get("PILOTODIN_DESKTOP_SESSION")
    ):
        raise RuntimeError("Refusing unapproved or nonempty W5 QA workspace")
    for path in (run, run / "manifest.json", workspace, output.parent):
        if path.is_symlink() or getattr(path, "is_junction", lambda: False)():
            raise RuntimeError("Refusing redirected W5 QA paths")

    sys.path.insert(0, str(ROOT))
    from fastapi.testclient import TestClient
    from backend import storage
    from backend.main import app

    source = source_bytes()
    client = TestClient(app)
    created = client.post(
        "/api/projects",
        files={"file": ("p3_w5_disposable_only.csv", source, "text/csv")},
    )
    if created.status_code != 201:
        raise RuntimeError(f"Isolated synthetic import failed: HTTP {created.status_code}")
    pid = created.json()["id"]
    if not re.fullmatch(r"[a-f0-9]{32}", pid):
        raise RuntimeError("Unexpected project identity")
    stored = Path(storage.get_project(pid)["dataset_path"]).resolve(strict=True)
    if not stored.is_relative_to(workspace / "datasets") or stored.read_bytes() != source:
        raise RuntimeError("Synthetic original source bytes differ or escaped QA workspace")

    snapshot = client.get(f"/api/projects/{pid}/quality")
    if snapshot.status_code != 200:
        raise RuntimeError("Cannot read initial Quality snapshot")
    q = snapshot.json()
    if q["version"] != 0 or q["rows"] != 36:
        raise RuntimeError("W5 must begin on 36-row working version 0")
    issues = [item for item in q["issues"] if item["kind"] == "whitespace"
              and item["column"] == "Region" and item["affected_rows"] == 2
              and item.get("proposal", {}).get("kind") == "trim_whitespace"]
    if len(issues) != 1:
        raise RuntimeError("W5 must have exactly one eligible two-cell Region finding")

    notes = client.post(
        f"/api/projects/{pid}/semantic-business-context",
        json={"expected_version": 0, "domain_description": DOMAIN,
              "record_grain_description": GRAIN,
              "field_definitions": [{"column": "claim_amount", "meaning": MEANING}]},
    )
    if notes.status_code != 200:
        raise RuntimeError(f"Initial synthetic semantic context failed: HTTP {notes.status_code}")
    initial = client.get(f"/api/projects/{pid}/semantics?expected_version=0")
    if initial.status_code != 200 or initial.json()["user_context"]["domain_description"] != DOMAIN:
        raise RuntimeError("W5 original unverified semantic note was not persisted")

    output.write_text(json.dumps({
        "phase": PHASE,
        "run_id": metadata["run_id"],
        "project_id": pid,
        "issue_id": issues[0]["id"],
        "source_relative": str(stored.relative_to(workspace)),
        "original_sha256": hashlib.sha256(source).hexdigest(),
        "original_bytes": len(source),
        "rows": 36,
        "expected_changed_cells": 2,
        "version": 0,
        "scope": "ONE_SYNTHETIC_QUALITY_PROPOSAL_AND_ONE_EXPLICIT_UI_COMMIT",
    }, indent=2) + "\n", encoding="utf-8")
    print("P3 W5: fresh synthetic 36-row project and unverified v0 notes verified")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
