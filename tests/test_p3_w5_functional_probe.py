"""Known-good and intentionally bad W5 functional probe cases.

This is not physical WebView2 acceptance. It proves the functional classifier
can distinguish the exact expected data transition from incorrect results,
independently of how a desktop window exits.
"""
from __future__ import annotations

from copy import deepcopy

import pytest

from tools.P3_W5_Functional_Probe import (
    PASS_FIELDS, ProbeFailure, assess_functional_snapshot, check_write_audit,
)


def good_snapshots():
    quality = {"version": 1}
    history = {"current_version": 1, "versions": [{"version": 0}, {"version": 1}]}
    current = {"version": 1, "user_context": None}
    preview = {"version": 1, "rows": [
        {"original": {"Region": "Gauteng"}, "working": {"Region": "Gauteng"}},
        {"original": {"Region": " Mpumalanga "}, "working": {"Region": "Mpumalanga"}},
        {"original": {"Region": " Mpumalanga "}, "working": {"Region": "Mpumalanga"}},
    ]}
    return quality, history, current, preview


def test_known_good_transition_is_accepted_without_any_window_exit():
    assess_functional_snapshot(*good_snapshots())
    assert PASS_FIELDS["quality_version"] == "PASS_V0_TO_V1"


@pytest.mark.parametrize("mutation,category", [
    (lambda q, h, s, p: q.update(version=0), "QUALITY_VERSION_NOT_ONE"),
    (lambda q, h, s, p: h.update(versions=[{"version": 1}]), "HISTORY_NOT_EXACTLY_V0_V1"),
    (lambda q, h, s, p: s.update(user_context={"domain_description": "stale"}), "V1_CONTEXT_NOT_EMPTY"),
    (lambda q, h, s, p: p["rows"][2]["working"].update(Region=" Mpumalanga "), "REGION_CORRECTION_NOT_EXACT"),
    (lambda q, h, s, p: p.update(version=0), "V1_PREVIEW_UNEXPECTED"),
])
def test_deliberately_bad_snapshots_are_rejected_independently_of_exit(mutation, category):
    values = list(deepcopy(good_snapshots()))
    mutation(*values)
    with pytest.raises(ProbeFailure, match=category):
        assess_functional_snapshot(*values)


def test_write_audit_accepts_only_two_approved_actions_and_one_rejected_stale_post():
    pid = "1" * 32
    log = "".join(
        f'127.0.0.1:1234 - "POST /api/projects/{pid}/{action} HTTP/1.1" {status} OK\n'
        for action, status in [
            ("quality/proposals", 200), ("quality/commit", 200),
            ("semantic-business-context", 409),
        ]
    )
    check_write_audit(log, pid)
    with pytest.raises(ProbeFailure, match="UNEXPECTED_BACKEND_WRITE_COUNT"):
        check_write_audit(log + f'127.0.0.1 - "DELETE /api/projects/{pid} HTTP/1.1" 200\n', pid)
    with pytest.raises(ProbeFailure, match="UNEXPECTED_BACKEND_WRITE_ORDER"):
        check_write_audit(log.replace("quality/proposals", "quality/commit", 1), pid)


def test_only_expected_pass_states_can_be_exposed_to_runner():
    assert set(PASS_FIELDS) == {
        "quality_version", "version_history", "current_semantic_context",
        "historical_semantic_context", "stale_semantic_get",
        "stale_semantic_post", "original_sha256", "request_audit",
    }


def _seed_real_backend(tmp_path, monkeypatch):
    """Create only a disposable DevQA workspace with real APIs and SQLite."""
    import json
    import os
    from pathlib import Path
    import subprocess
    import sys

    from fastapi.testclient import TestClient
    from tools import qa_foundation
    from backend import main, storage
    from tools.Seed_P3_Native_Quality_W5_Local import PHASE

    repo=Path(__file__).resolve().parents[1]
    run,_=qa_foundation.create_run(tmp_path/"w5-probe-fixtures", PHASE, repo=repo)
    workspace=run/"workspace"
    fixture=run/"fixtures"/"p3-native-w5-manifest.json"
    env=os.environ.copy()
    env["PILOTODIN_HOME"]=str(workspace)
    env.pop("PILOTODIN_DESKTOP_SESSION", None)
    seeded=subprocess.run(
        [sys.executable, "-B", str(repo/"tools/Seed_P3_Native_Quality_W5_Local.py"), str(fixture)],
        cwd=repo,env=env,text=True,capture_output=True,timeout=45,check=False
    )
    assert seeded.returncode == 0, seeded.stderr
    meta=json.loads(fixture.read_text(encoding="utf-8"))
    monkeypatch.setattr(storage,"HOME",workspace)
    monkeypatch.setattr(storage,"DB_PATH",workspace/"pilotodin.sqlite3")
    storage.init()
    client=TestClient(main.app)
    return workspace,meta,client


def _approve_exact_synthetic_correction(workspace, meta, client):
    pid=meta["project_id"]
    proposed=client.post(f"/api/projects/{pid}/quality/proposals",json={
        "issue_id":meta["issue_id"],"operation":"approve","expected_version":0,
    })
    assert proposed.status_code == 200, proposed.text
    receipt=proposed.json()
    assert receipt["changed_cells"] == 2
    committed=client.post(f"/api/projects/{pid}/quality/commit",json={
        "proposal_id":receipt["proposal_id"],"proposal_hash":receipt["proposal_hash"],
    })
    assert committed.status_code == 200, committed.text
    log=workspace.parent/"logs"/"backend-stdout.log"
    log.write_text(
        f'127.0.0.1:1234 - "POST /api/projects/{pid}/quality/proposals HTTP/1.1" 200 OK\n'
        f'127.0.0.1:1234 - "POST /api/projects/{pid}/quality/commit HTTP/1.1" 200 OK\n',
        encoding="utf-8"
    )


def _redirect_probe_to_real_local_test_client(monkeypatch, workspace, client):
    from tools import P3_W5_Functional_Probe as probe
    from pathlib import Path

    def local_request(path, *, payload=None):
        response=(client.get if payload is None else client.post)(
            "/api"+path, **({} if payload is None else {"json":payload})
        )
        if payload is not None:
            log=workspace.parent/"logs"/"backend-stdout.log"
            with log.open("a", encoding="utf-8") as handle:
                handle.write(
                    f'127.0.0.1:1234 - "POST /api{path} HTTP/1.1" {response.status_code} OK\n'
                )
        return response.status_code, response.json()
    monkeypatch.setattr(probe,"request_json",local_request)
    return probe


def test_real_disposable_backend_accepts_functional_checks_without_window_exit(tmp_path,monkeypatch):
    workspace,meta,client=_seed_real_backend(tmp_path,monkeypatch)
    _approve_exact_synthetic_correction(workspace,meta,client)
    probe=_redirect_probe_to_real_local_test_client(monkeypatch,workspace,client)
    assert probe.observe(workspace) == 0
    report=__import__("json").loads(
        (workspace.parent/"diagnostics"/"functional-result.json").read_text(encoding="utf-8")
    )
    assert report["functional_state"] == "PASS"
    assert report["native_shutdown"] == "INDEPENDENT_NOT_TESTED"
    assert all(report["checks"][key] == value for key,value in probe.PASS_FIELDS.items())


def test_real_backend_rejects_inherited_v1_description_as_invalid(tmp_path,monkeypatch):
    workspace,meta,client=_seed_real_backend(tmp_path,monkeypatch)
    _approve_exact_synthetic_correction(workspace,meta,client)
    pid=meta["project_id"]
    # Deliberately add semantic descriptions in the current version, which
    # violates W5's no-inheritance acceptance rule. This is test-only data.
    changed=client.post(f"/api/projects/{pid}/semantic-business-context",json={
        "expected_version":1,"domain_description":"Deliberate invalid v1 note",
        "record_grain_description":"A test-only invalid grain","field_definitions":[],
    })
    assert changed.status_code == 200, changed.text
    probe=_redirect_probe_to_real_local_test_client(monkeypatch,workspace,client)
    with pytest.raises(ProbeFailure,match="V1_CONTEXT_NOT_EMPTY"):
        probe.observe(workspace)
