"""No-CDP WebView2 Kernel-File strict reduction: redacted, non-acceptance view.

Only a newly approved hosted-Windows application collector may call this with
real evidence. This reducer does not launch anything, change FileIO policies,
weaken path-missing blockers, or certify mutation containment.
"""
from collections import Counter

from qa.p4_native import n12_trace as trace


ROLES = ("webview", "webview-network", "backend", "app", "helper",
         "driver", "calibration", "unattributed", "other")


def _fixed_report(*, blocker, violations=None, gaps=None, counts=None, source_issues=0,
                  scoped_roles=None, snapshot_state="NOT_EVALUATED", app_identity="NOT_VERIFIED",
                  capture_loss="NOT_EVALUATED"):
    violations = Counter(violations or {})
    gaps = Counter(gaps or {})
    counts = Counter(counts or {})
    # Fixed labels only. Never serialize a raw process ID, GUID, path, event
    # payload, original user folder, thread, source data or arbitrary dict key.
    return {
        "scope": "no-cdp-kernel-file-observation-not-acceptance",
        "status": "BLOCKED",
        "blocker": blocker,
        "observed_prohibited_operations": sum(violations.values()),
        "prohibited_by_role": {
            role: sum(n for key, n in violations.items()
                      if key.startswith(("outside-scope:" + role + ":",
                                         "protected:" + role + ":")))
            for role in ROLES
        },
        "known_scoped_operations": sum(counts.values()),
        "missing_mutation_path_credits": sum(gaps.values()),
        "remaining_webview_network_write_path_gaps": gaps.get(
            "webview-network:write:path-missing", 0),
        "reducer_issue_count": source_issues,
        "scoped_role_count": scoped_roles,
        "protected_endpoints": snapshot_state,
        "original_app_handle_join": app_identity,
        "etw_loss_counters": capture_loss,
        "calibration_and_transient_write_proof": "NOT_COLLECTED",
        "effective_webview_user_data_folder": "NOT_VERIFIED",
        "full_product_tree_mutation_containment": "NOT_DEMONSTRATED",
        "native_N12_acceptance": "NOT_EVALUATED",
        "file_mutation_acceptance": "NOT_EVALUATED",
        "owner_native_execution_authorized": False,
    }


def reduce(manifest, sysmon, events, app_witness, binary, *, lifetime_report, snapshot):
    """Reuse the governing strict ETW FileIO reducer on the same exported bytes.

    Missing loss, mutation path, actor, coverage or snapshot evidence never
    turns this focused diagnostic into a clean filesystem verdict.
    """
    if not (type(manifest) is dict and type(app_witness) is dict
            and type(app_witness.get("pid")) is int and app_witness["pid"] > 0
            and type(lifetime_report) is dict and type(snapshot) is dict
            and manifest.get("etw", {}).get("schema_version") == 1):
        return _fixed_report(blocker="incomplete-fileio-review-envelope")
    try:
        start, end, processes, _, issues = trace.load_capture(manifest, sysmon, etw=True)
        roles, bindings = trace.bind_processes(
            [{"pid": app_witness["pid"], "role": "app", "image": str(binary)}],
            processes, issues)
        protected, permitted = trace.scope(manifest)
        protected.extend(trace.windows_path(manifest["observed_roots"][name])
                         for name in manifest["immutable_observed"])
        file_counts, violations, _events, gaps = trace.inspect_etw_files(
            manifest, events, start, end, processes, roles,
            protected, permitted, issues)
        full_role_count = sum(1 for role in roles.values()
                              if role in {"webview", "webview-network"})
        app_identity = (
            "MATCH" if lifetime_report.get("verdict") == "PASS"
            and lifetime_report.get("handle_comparison", {}).get("app") == "MATCH"
            and len(bindings) == 1 else "NOT_VERIFIED"
        )
        if not full_role_count:
            issues.add("no-cdp-webview-process-tree-missing")
        if not bindings:
            issues.add("no-cdp-original-app-handle-unbound")
        state = snapshot.get("protected_snapshot_comparison")
        if state not in {"MATCH", "CHANGED", "BLOCKED"}:
            state = "NOT_EVALUATED"
        etw_loss = manifest["etw"]["counters"]
        loss = ("ZERO_REPORTED_NOT_FULL_COMPLETENESS"
                if all(type(etw_loss.get(k)) is int and etw_loss[k] == 0
                       for k in ("events_lost", "log_buffers_lost", "realtime_buffers_lost"))
                else "LOSS_OR_UNVERIFIED")
        # Even zero observed violations cannot prove the absence of other
        # writes without the complete N12 calibration and write/restore arm.
        if violations:
            reason = "observed-prohibited-fileio-operations"
        elif gaps or issues or full_role_count == 0 or app_identity != "MATCH":
            reason = "fileio-evidence-or-original-process-identity-unresolved"
        else:
            reason = "full-n12-calibration-and-transient-write-control-not-collected"
        return _fixed_report(
            blocker=reason, violations=violations, gaps=gaps, counts=file_counts,
            source_issues=len(issues), scoped_roles=full_role_count,
            snapshot_state=state, app_identity=app_identity, capture_loss=loss,
        )
    except (trace.EvidenceValidationError, KeyError, ValueError, TypeError, OSError,
            UnicodeError):
        return _fixed_report(blocker="strict-fileio-reducer-or-evidence-invalid")


