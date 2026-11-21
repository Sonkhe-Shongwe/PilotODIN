#!/usr/bin/env python3
"""Seed only two repository-owned synthetic P3 projects in a fresh DevQA home."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
PHASE = "P3-NATIVE-SEMANTIC-CONTEXT"
SOURCES = (
    "p3_semantic_owner_A.csv",
    "p3_semantic_owner_B.csv",
)


def main() -> int:
    if len(sys.argv) != 2 or not os.environ.get("PILOTODIN_HOME"):
        raise RuntimeError("Require one fixture manifest and a disposable PILOTODIN_HOME")
    workspace = Path(os.environ["PILOTODIN_HOME"]).resolve(strict=True)
    run = workspace.parent
    output = Path(sys.argv[1]).resolve()
    manifest = json.loads((run / "manifest.json").read_text(encoding="utf-8-sig"))
    if (
        workspace.name != "workspace"
        or not workspace.is_dir()
        or any(workspace.iterdir())
        or output != run / "fixtures" / "p3-native-semantic-manifest.json"
        or output.exists()
        or manifest.get("phase") != PHASE
        or manifest.get("state") != "READY_NOT_TESTED"
        or manifest.get("product_acceptance") != "NOT_TESTED"
        or os.environ.get("PILOTODIN_DESKTOP_SESSION")
    ):
        raise RuntimeError("Refusing nonempty or nonauthorised QA workspace")
    for path in (run, run / "manifest.json", workspace, output.parent):
        if path.is_symlink() or getattr(path, "is_junction", lambda: False)():
            raise RuntimeError("Refusing redirected QA paths")

    # Import only after the confirmed isolated env is in effect.
    sys.path.insert(0, str(ROOT))
    from fastapi.testclient import TestClient
    from backend import storage
    from backend.main import app

    projects = []
    client = TestClient(app)
    for filename in SOURCES:
        source = ROOT / "tests" / "fixtures" / filename
        if source.is_symlink() or not source.is_file():
            raise RuntimeError("Missing committed synthetic CSV: " + filename)
        payload = source.read_bytes()
        lines = payload.decode("utf-8").splitlines()
        if len(lines) != 21 or lines[0] != "claim_id,claim_amount,policy_number":
            raise RuntimeError("Unexpected fixture schema or row count")
        created = client.post(
            "/api/projects", files={"file": (filename, payload, "text/csv")}
        )
        if created.status_code != 201:
            raise RuntimeError(f"Synthetic import failed: HTTP {created.status_code}")
        pid = created.json()["id"]
        if not re.fullmatch(r"[a-f0-9]{32}", pid):
            raise RuntimeError("Invalid synthetic project ID")
        stored = Path(storage.get_project(pid)["dataset_path"]).resolve(strict=True)
        if not stored.is_relative_to(workspace / "datasets") or stored.read_bytes() != payload:
            raise RuntimeError("Fixture escaped workspace or changed during import")
        projects.append({
            "id": pid,
            "source_relative": str(stored.relative_to(workspace)),
            "sha256": hashlib.sha256(payload).hexdigest(),
            "rows": 20,
        })
    if projects[0]["id"] == projects[1]["id"]:
        raise RuntimeError("Expected separate synthetic projects")
    output.write_text(json.dumps({
        "phase": PHASE, "run_id": manifest["run_id"],
        "projects": projects,
        "scope": "SYNTHETIC_NATIVE_P3_SEMANTIC_EDITOR_OWNER_VISUAL_QA_ONLY",
    }, indent=2) + "\n", encoding="utf-8")
    print("P3 native QA: two isolated 20-row synthetic projects created")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
