"""Fail-closed source-only FileIO writer/handle/path evidence contract.

The synthetic witness fields are NOT independent Windows observation. Even
REVIEWABLE_ONLY never authorizes a native run or earns N12/R02.5 acceptance.
No native process, token, filesystem or ETW collector action is performed.
"""
import ast
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[2]
SCOPE = "n12-fileio-writer-lifetime-path-join-v1"
SOURCES = {
    "strict": "qa/p4_native/n12_trace.py",
    "correlator": "qa/p4_native/n12_etw_correlate.py",
    "independent_lifetime": "qa/p4_native/n12_exit_corroboration.py",
}
PATH_EVIDENCE = {"same-original-open-handle", "same-epoch-request-time-name"}
SCOPES = {"permitted", "outside-scope", "protected"}
FIELDS = {
    "capture": {
        "start_ticks", "end_ticks", "digest_verified", "zero_etw_loss",
        "positive_transient_write_observed",
    },
    "process": {
        "pid", "birth_ticks", "exit_ticks", "etw_birth_ticks", "etw_exit_ticks",
        "original_handle_birth_ticks", "original_handle_exit_ticks",
        "original_handle_retained", "exact_image_verified",
        "unique_etw_sequence", "parent_sequence_verified", "sysmon_guid_verified",
    },
    "write": {
        "pid", "birth_ticks", "request_ticks", "completion_ticks",
        "request_event_id", "completion_event_id", "irp", "completion_irp",
        "file_object", "file_key", "thread_owner_verified", "unique_completion",
        "completion_identity_verified", "completion_success",
        "path_evidence", "name_epoch_unchanged", "destination_scope",
    },
}
CAPTURE_TRUES = (
    "digest_verified", "zero_etw_loss", "positive_transient_write_observed",
)
PROCESS_TRUES = (
    "original_handle_retained", "exact_image_verified", "unique_etw_sequence",
    "parent_sequence_verified", "sysmon_guid_verified",
)
WRITE_TRUES = (
    "thread_owner_verified", "unique_completion", "completion_identity_verified",
    "completion_success", "name_epoch_unchanged",
)


def _result(issues, scope="UNVERIFIED"):
    return {
        "scope": SCOPE,
        "join_status": "BLOCKED" if issues else "REVIEWABLE_ONLY",
        "issues": sorted(set(issues)),
        "destination_scope": scope,
        "process_to_write_provenance_verified": False,
        "fileio_capture_completeness_certified": False,
        "evidence_origin": "UNVERIFIED_INPUT",
        "historical_strict_reducer": "UNCHANGED",
        "native_N12_acceptance": "NOT_EVALUATED",
        "file_mutation_acceptance": "NOT_EVALUATED",
        "owner_native_execution_authorized": False,
    }


def review_candidate(witness):
    """Review ordering/shape only, never native truth or real writer attribution."""
    if type(witness) is not dict or set(witness) != {"scope", "source_sha", *FIELDS}:
        return _result(["witness-schema-invalid"])
    if witness["scope"] != SCOPE or type(witness["source_sha"]) is not str or not re.fullmatch(
            r"[a-f0-9]{40}", witness["source_sha"]):
        return _result(["source-identity-unverified"])
    if any(type(witness[k]) is not dict or set(witness[k]) != expected
           for k, expected in FIELDS.items()):
        return _result(["witness-schema-invalid"])
    c, p, w = (witness[k] for k in ("capture", "process", "write"))
    numeric_groups = (
        (c, ("start_ticks", "end_ticks")),
        (p, ("pid", "birth_ticks", "exit_ticks", "etw_birth_ticks", "etw_exit_ticks",
             "original_handle_birth_ticks", "original_handle_exit_ticks")),
        (w, ("pid", "birth_ticks", "request_ticks", "completion_ticks",
             "request_event_id", "completion_event_id", "irp", "completion_irp",
             "file_object", "file_key")),
    )
    if any(type(row[field]) is not int or row[field] <= 0
           for row, keys in numeric_groups for field in keys):
        return _result(["numeric-identity-invalid"])
    issues = []
    if any(c[k] is not True for k in CAPTURE_TRUES) or c["start_ticks"] >= c["end_ticks"]:
        issues.append("collector-or-positive-control-unverified")
    if any(p[k] is not True for k in PROCESS_TRUES):
        issues.append("original-process-identity-unverified")
    if not (p["birth_ticks"] == p["etw_birth_ticks"] == p["original_handle_birth_ticks"]
            and p["exit_ticks"] == p["etw_exit_ticks"] == p["original_handle_exit_ticks"]
            and c["start_ticks"] <= p["birth_ticks"] < p["exit_ticks"] <= c["end_ticks"]):
        issues.append("original-handle-etw-lifetime-disagrees")
    if any(w[k] is not True for k in WRITE_TRUES):
        issues.append("fileio-request-completion-evidence-unverified")
    if (w["request_event_id"], w["completion_event_id"]) != (16, 24) or w["irp"] != w["completion_irp"]:
        issues.append("fileio-operation-or-irp-unverified")
    if w["pid"] != p["pid"] or w["birth_ticks"] != p["birth_ticks"]:
        issues.append("fileio-pid-birth-identity-disagrees")
    if not (c["start_ticks"] <= p["birth_ticks"] < w["request_ticks"]
            < w["completion_ticks"] < p["exit_ticks"] <= c["end_ticks"]):
        issues.append("fileio-completion-outside-original-process-lifetime")
    if w["path_evidence"] not in PATH_EVIDENCE:
        issues.append("request-time-path-provenance-unverified")
    destination = w["destination_scope"] if w["destination_scope"] in SCOPES else "UNVERIFIED"
    if destination == "UNVERIFIED":
        issues.append("destination-scope-unverified")
    return _result(issues, destination if not issues else "UNVERIFIED")


def source_contract(root=ROOT):
    """Verify named source seams exist, without interpreting current runtime."""
    try:
        sources = {k: (root / p).read_text(encoding="utf-8") for k, p in SOURCES.items()}
        found = {}
        for key, text in sources.items():
            tree = ast.parse(text)
            found[key] = {n.name for n in tree.body if isinstance(n, (ast.FunctionDef, ast.ClassDef))}
    except (OSError, UnicodeError, ValueError, SyntaxError, RecursionError):
        return {"status": "SOURCE_DRIFT_BLOCKED", "issues": ["source-read-or-parse-invalid"],
                "native_N12_acceptance": "NOT_EVALUATED"}
    required = {
        "strict": {"inspect_etw_files", "etw_capture_contract", "etw_events"},
        "correlator": {"correlate_requests"},
        "independent_lifetime": {"EtwLifetimes", "read_lifecycle"},
    }
    issues = []
    for key, functions in required.items():
        if not functions <= found[key]:
            issues.append(f"{key}-evidence-function-missing")
    predicates = {
        "strict": ("def classify_process(pid, birth, ticks):", "tolerance = 100_000",
                   "etw-mutation-coverage-unresolved", "credit_webview_path"),
        "correlator": ("def completion_identity_issue(", "active.get(owner_pid) != owner_birth",
                       "completion_file_identity_conflicts(", "def verified_webview_write_identity(",
                       "initial_process_births", "name_transition_ticks", "rundown_unsafe_keys"),
        "independent_lifetime": ("start.sequence == stop.sequence", "exact-path-match"),
    }
    for key, tokens in predicates.items():
        if not all(token in sources[key] for token in tokens):
            issues.append(f"{key}-join-predicate-source-drift")
    return {
        "status": "SOURCE_MATCH" if not issues else "SOURCE_DRIFT_BLOCKED",
        "issues": sorted(issues),
        "actual_original_webview_handle_evidence": "NOT_COLLECTED",
        "known-path-completion-lifetime_proven": False,
        "native_N12_acceptance": "NOT_EVALUATED",
    }


def main():
    import json
    print(json.dumps(source_contract(), sort_keys=True))
    return 0 if source_contract()["status"] == "SOURCE_MATCH" else 2


if __name__ == "__main__":
    raise SystemExit(main())
