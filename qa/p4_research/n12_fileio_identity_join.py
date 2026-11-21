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


# Generated Windows ETW capture: independent original Popen process HANDLE and
# the Kernel-Process + Kernel-File providers from the same disposable fixture.
# These are genuine Windows observations on CI but NEVER PilotODIN proof.
def generated_original_handle_fileio_join(capture, events):
    """Correlate generated writer's original HANDLE, ETW process birth/exit and FileIO.

    Fails closed; returns labels only. Does not inspect/modify files or Windows,
    and never emits any supplied PID, image, timestamp, path, IRP or payload.
    """
    import ntpath
    from qa.p4_native import n12_trace as trace
    from qa.p4_native.n12_etw_correlate import canonical_file_path, number

    def result(issues):
        return {
            "scope": "n12-generated-windows-original-handle-etw-fileio-join",
            "status": "GENERATED_JOIN_CORROBORATED" if not issues else "BLOCKED",
            "issues": sorted(set(issues)),
            "evidence_kind": "HOSTED_WINDOWS_SYNTHETIC_ONLY",
            "sysmon_original_webview_identity": "NOT_COLLECTED",
            "product_file_mutation_containment": "NOT_EVALUATED",
            "native_N12_acceptance": "NOT_EVALUATED",
            "file_mutation_acceptance": "NOT_EVALUATED",
        }

    if type(capture) is not dict or type(events) is not list:
        return result(["fixture-envelope-invalid"])
    control = capture.get("file_lifetime")
    counters = capture.get("counters")
    devices = capture.get("volume_devices")
    if type(control) is not dict or type(counters) is not dict or type(devices) is not dict:
        return result(["fixture-envelope-invalid"])
    handle = control.get("original_handle")
    keys = ("pid", "birth_ticks", "exit_ticks")
    if type(handle) is not dict or set(handle) != set(keys):
        return result(["original-process-handle-unavailable"])
    if any(type(handle.get(k)) is not int or handle[k] <= 0 for k in keys):
        return result(["original-process-handle-invalid"])
    if type(control.get("pid")) is not int or control["pid"] != handle["pid"]:
        return result(["original-process-handle-pid-conflict"])
    if (type(control.get("start")) is not int or type(control.get("end")) is not int
            or not control["start"] < handle["birth_ticks"] < handle["exit_ticks"] < control["end"]
            or control.get("size") != 97 or control.get("two_handles") is not True):
        return result(["generated-control-window-or-handle-invalid"])
    issues = []
    names = ("events_lost", "log_buffers_lost", "realtime_buffers_lost")
    if any(type(counters.get(key)) is not int or counters[key] != 0 for key in names):
        issues.append("etw-event-or-buffer-loss-unverified")
    if type(counters.get("buffers_written")) is not int or counters["buffers_written"] <= 0:
        issues.append("etw-no-buffers-written")
    if type(control.get("path")) is not str or not control["path"]:
        return result(["generated-control-path-invalid"])
    volume_aliases = {}
    for dos, device in devices.items():
        if not (type(dos) is str and type(device) is str and len(dos) == 2
                and dos[1] == ":" and device.casefold().startswith("\\device\\")):
            return result(["device-alias-unverified"])
        volume_aliases[device.casefold()] = dos.casefold()
    try:
        expected_path = trace.windows_path(control["path"])
    except (ValueError, trace.EvidenceValidationError):
        return result(["generated-control-path-invalid"])
    pid = handle["pid"]
    process_rows = [
        e for e in events if type(e) is dict and e.get("lifecycle") is True
        and e.get("id") in (1, 2) and type(e.get("data")) is dict
        and number(e["data"].get("ProcessID")) == pid
    ]
    starts = [e for e in process_rows if e["id"] == 1]
    stops = [e for e in process_rows if e["id"] == 2]
    if len(starts) != 1 or len(stops) != 1:
        issues.append("etw-process-birth-exit-missing-or-ambiguous")
    else:
        try:
            start_data, stop_data = starts[0]["data"], stops[0]["data"]
            start_creation = trace.etw_payload_ticks(start_data["CreateTime"])
            stop_creation = trace.etw_payload_ticks(stop_data["CreateTime"])
            stop_exit = trace.etw_payload_ticks(stop_data["ExitTime"])
            a, b = number(start_data.get("ProcessSequenceNumber")), number(stop_data.get("ProcessSequenceNumber"))
            if (start_creation != handle["birth_ticks"]
                    or stop_creation != start_creation or stop_exit != handle["exit_ticks"]
                    or a is None or b is None or a <= 0 or a != b):
                issues.append("etw-process-sequence-or-original-handle-time-disagrees")
        except (KeyError, TypeError, ValueError, trace.EvidenceValidationError):
            issues.append("etw-process-sequence-or-original-handle-time-unavailable")

    def matching_file_path(e):
        if type(e) is not dict or e.get("lifecycle") is not False or e.get("id") != 12:
            return False
        name = e.get("data", {}).get("FileName")
        return (isinstance(name, str) and
                canonical_file_path(name, volume_aliases) == expected_path)

    writes = [
        e for e in events if type(e) is dict and e.get("lifecycle") is False
        and e.get("id") == 16 and e.get("pid") == pid
        and type(e.get("ticks")) is int and control["start"] <= e["ticks"] <= control["end"]
        and number(e.get("data", {}).get("IOSize")) == 97
    ]
    if len(writes) != 1:
        issues.append("writer-fileio-write-not-unique")
    else:
        write = writes[0]
        data = write["data"]
        obj, irp = number(data.get("FileObject")), number(data.get("Irp"))
        if not (obj and irp and handle["birth_ticks"] < write["ticks"] < handle["exit_ticks"]):
            issues.append("writer-fileio-request-object-or-lifetime-invalid")
        same_obj_opens = [
            e for e in events if matching_file_path(e)
            and number(e["data"].get("FileObject")) == obj
            and e["pid"] == pid and e["ticks"] < write["ticks"]
        ]
        if not same_obj_opens:
            issues.append("writer-fileio-same-object-open-not-observed")
        else:
            # The most recent matching open must be completed successfully,
            # and no close/reuse may have invalidated its FileObject.
            opened = max(same_obj_opens, key=lambda e: e["ticks"])
            old_irp = number(opened["data"].get("Irp"))
            open_completions = [
                e for e in events if e.get("lifecycle") is False
                and e["id"] == 24 and number(e.get("data", {}).get("Irp")) == old_irp
                and opened["ticks"] < e["ticks"] < write["ticks"]
                and number(e["data"].get("Status")) == 0
            ] if old_irp else []
            invalidators = [
                e for e in events if e.get("lifecycle") is False
                and e["id"] in (12, 13, 14, 18, 19, 26, 27, 28, 29)
                and number(e.get("data", {}).get("FileObject")) == obj
                and opened["ticks"] < e["ticks"] < write["ticks"]
            ]
            if len(open_completions) != 1 or invalidators:
                issues.append("writer-fileio-open-object-lifetime-unverified")
        matching_completions = [
            e for e in events if e.get("lifecycle") is False and e["id"] == 24
            and number(e.get("data", {}).get("Irp")) == irp and e["ticks"] > write["ticks"]
        ] if irp else []
        duplicate_requests = [
            e for e in events if e is not write and e.get("lifecycle") is False
            and e["id"] in (12, 16, 17, 18, 19, 23, 29)
            and number(e.get("data", {}).get("Irp")) == irp
            and write["ticks"] <= e["ticks"] <= control["end"]
        ] if irp else []
        if (len(matching_completions) != 1 or duplicate_requests
                or number(matching_completions[0]["data"].get("Status")) != 0
                if len(matching_completions) == 1 else True):
            issues.append("writer-fileio-unique-success-completion-unverified")
        elif not write["ticks"] < matching_completions[0]["ticks"] < handle["exit_ticks"]:
            issues.append("writer-fileio-completion-outside-original-lifetime")
    return result(issues)


def main():
    import json
    import sys
    if len(sys.argv) == 4 and sys.argv[1] == "--generated-windows-join":
        from qa.p4_native import n12_trace as trace
        try:
            fixture = json.loads(Path(sys.argv[2]).read_text(encoding="utf-8-sig"))
            rows = [json.loads(line) for line in Path(sys.argv[3]).read_text(
                encoding="utf-8-sig").splitlines()]
            report = generated_original_handle_fileio_join(fixture, rows)
        except (OSError, UnicodeError, ValueError, KeyError, TypeError, trace.EvidenceValidationError):
            report = {"scope": "n12-generated-windows-original-handle-etw-fileio-join",
                      "status": "BLOCKED", "issues": ["fixture-input-unavailable"],
                      "evidence_kind": "HOSTED_WINDOWS_SYNTHETIC_ONLY",
                      "native_N12_acceptance": "NOT_EVALUATED",
                      "file_mutation_acceptance": "NOT_EVALUATED"}
        print(json.dumps(report, sort_keys=True))
        return 0 if report["status"] == "GENERATED_JOIN_CORROBORATED" else 2
    if len(sys.argv) != 1:
        print(json.dumps({"status": "BLOCKED", "issues": ["unsupported-arguments"],
                          "native_N12_acceptance": "NOT_EVALUATED"}, sort_keys=True))
        return 2
    report = source_contract()
    print(json.dumps(report, sort_keys=True))
    return 0 if report["status"] == "SOURCE_MATCH" else 2


if __name__ == "__main__":
    raise SystemExit(main())
