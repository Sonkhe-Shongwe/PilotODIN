"""Redacted N12 FileIO decision from already-reduced, same-capture evidence.

Never confers native acceptance. Does not launch apps, change files or read raw ETW.
"""
from qa.p4_native import n12_trace as trace

WEBVIEW_GAP = "webview-network:write:path-missing"
OTHER_GAP = "other:write:path-missing"
OUTSIDE_WEBVIEW = "outside-scope:webview-network:write"


def _counts(value):
    trace.require(type(value) is dict and all(
        type(key) is str and type(n) is int and n >= 0
        for key, n in value.items()), "mutation-triage-counts-invalid")
    return value


def _blocked(reason):
    return {"scope": "file-mutation-triage-only", "comparison": "BLOCKED",
            "blockers": [reason], "native_N12_acceptance": "NOT_EVALUATED",
            "file_mutation_acceptance": "NOT_EVALUATED"}


def summarize(result):
    """Fail closed on mismatched or incomplete credit, including hidden violations."""
    trace.require(type(result) is dict, "mutation-triage-audit-invalid")
    before = _counts(result.get("etw_unresolved_mutations"))
    violations = _counts(result.get("file_violations"))
    comparison = result.get("webview_credit_comparison")
    if type(comparison) is not dict or comparison.get("status") != "completed":
        return _blocked("webview-comparison-not-completed")
    credit = comparison.get("etw_webview_write_credit")
    if type(credit) is not dict or credit.get("status") != "compared":
        return _blocked("webview-credit-not-reviewed")
    after = _counts(comparison.get("etw_unresolved_mutations"))
    changed = _counts(comparison.get("file_violations"))
    supported = _counts(credit.get("credited_paths"))
    trace.require(set(supported) <= {"permitted", "outside-scope"}
                  and type(comparison.get("baseline_webview_write_path_gaps")) is int
                  and comparison["baseline_webview_write_path_gaps"] == before.get(WEBVIEW_GAP, 0)
                  and type(credit.get("remaining_path_gaps")) is int
                  and credit["remaining_path_gaps"] == after.get(WEBVIEW_GAP, 0)
                  and before.get(WEBVIEW_GAP, 0) == after.get(WEBVIEW_GAP, 0) + sum(supported.values())
                  and all(after.get(k, 0) == v for k, v in before.items() if k != WEBVIEW_GAP)
                  and all(k in before or n == 0 for k, n in after.items()),
                  "mutation-triage-credit-inconsistent")
    trace.require(all(changed.get(k, 0) >= n for k, n in violations.items())
                  and changed.get(OUTSIDE_WEBVIEW, 0) == (
                      violations.get(OUTSIDE_WEBVIEW, 0) + supported.get("outside-scope", 0)
                  ), "mutation-triage-violations-concealed")
    background = result.get("background_rundown_comparison")
    if type(background) is not dict or background.get("status") != "completed":
        return _blocked("background-rundown-not-completed")
    background_credit = _counts(background.get("verified_paths"))
    digest = comparison.get("etw_events_sha256")
    trace.require(type(digest) is str and len(digest) == 64
                  and all(c in "0123456789abcdef" for c in digest)
                  and digest == background.get("etw_events_sha256")
                  and type(background.get("baseline_write_path_gaps")) is int
                  and background["baseline_write_path_gaps"] == before.get(OTHER_GAP, 0)
                  and type(background.get("remaining_write_path_gaps")) is int
                  and background["remaining_write_path_gaps"] >= 0
                  and background["remaining_write_path_gaps"] + sum(background_credit.values())
                  == before.get(OTHER_GAP, 0), "mutation-triage-background-inconsistent")
    trace.require(result.get("file_evidence_source") == "etw"
                  and result.get("coverage") in {"BLOCKED", "CALIBRATED"}
                  and result.get("filesystem") in {"BLOCKED", "FAIL", "PASS_SCOPED"}
                  and comparison.get("coverage") in {"BLOCKED", "CALIBRATED"}
                  and comparison.get("filesystem") in {"BLOCKED", "FAIL", "PASS_SCOPED"},
                  "mutation-triage-scope-unverified")
    # Reconcile numeric evidence, not process paths or private event payloads.
    blockers = []
    if changed:
        blockers.append("out-of-scope-file-operations")
    if after:
        blockers.append("unresolved-fileio-mutations")
    if result["coverage"] != "CALIBRATED" or comparison["coverage"] != "CALIBRATED":
        blockers.append("incomplete-native-collector-coverage")
    if result["filesystem"] != "PASS_SCOPED" or comparison["filesystem"] != "PASS_SCOPED":
        blockers.append("filesystem-verdict-not-pass")
    return {
        "scope": "file-mutation-triage-only", "comparison": "RECONCILED",
        "webview_network_write_paths": {
            "ordinary_unresolved": before.get(WEBVIEW_GAP, 0),
            "credited_permitted": supported.get("permitted", 0),
            "credited_outside_scope": supported.get("outside-scope", 0),
            "remaining_unresolved": after.get(WEBVIEW_GAP, 0)},
        "background_write_paths": {
            "ordinary_unresolved": before.get(OTHER_GAP, 0),
            "credited": sum(background_credit.values()),
            "remaining_unresolved": background["remaining_write_path_gaps"]},
        "remaining_other_unresolved_events": sum(
            n for k, n in after.items() if k != WEBVIEW_GAP),
        "confirmed_outside_scope_categories": sum(n > 0 for n in changed.values()),
        "blockers": blockers, "native_N12_acceptance": "NOT_EVALUATED",
        "file_mutation_acceptance": "NOT_EVALUATED",
    }
