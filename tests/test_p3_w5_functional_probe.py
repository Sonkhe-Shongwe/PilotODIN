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
