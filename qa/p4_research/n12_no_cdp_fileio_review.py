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
                  capture_loss="NOT_EVALUATED", child_handles="NOT_EVALUATED",
                  browser_profile="NOT_EVALUATED"):
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
        # These are independent *lifetime* diagnostic states derived from
        # the authenticated child pipe and browser Sysmon/ETW profile check.
        # Neither implies per-file IRP completion identity is independently
        # proven or that the browser's effective storage root was inspected.
        "original_webview_child_handle_lifetimes": child_handles,
        "browser_command_line_profile": browser_profile,
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
        # The *same* lifetime reduction already checks original held child
        # handles via private, authenticated pipe against Sysmon GUID, ETW
        # birth/exit, parent sequence, full native/DOS images, and sampler
        # coverage. Use only its fixed-label review; never accept a bare
        # user-supplied PID/count or relax the strict FileIO reducer.
        child_receipt = lifetime_report.get("no_cdp_private_child_handle_diagnostic")
        child_counts = Counter(role for role in roles.values()
                               if role in {"webview", "webview-network"})
        child_review = "NOT_EVALUATED"
        if type(child_receipt) is dict:
            expected = {key: child_counts[key]
                        for key in ("webview", "webview-network") if child_counts[key]}
            if (child_receipt.get("scope") == "no-cdp-private-child-handle-reducer-diagnostic-only"
                    and child_receipt.get("status") == "REVIEWABLE_ONLY"
                    and child_receipt.get("native_N12_acceptance") == "NOT_EVALUATED"
                    and type(child_receipt.get("failed_checks")) is dict
                    and not child_receipt["failed_checks"]
                    and type(child_receipt.get("child_role_counts")) is dict
                    and child_receipt["child_role_counts"] == expected
                    and type(child_receipt.get("verified_handle_counts")) is dict
                    and child_receipt["verified_handle_counts"] == expected
                    and child_counts["webview"] > 0
                    and child_counts["webview-network"] > 0
                    and lifetime_report.get("verdict") == "PASS"
                    and lifetime_report.get("source_sha") == manifest.get("source_sha")
                    and lifetime_report.get("executable_sha256") == manifest.get("executable_sha256")
                    and not lifetime_report.get("issues")):
                child_review = "PRIVATE_ORIGINAL_HANDLES_REVIEWABLE_ONLY"
            else:
                child_review = "UNVERIFIED_OR_INCOMPLETE"
        # Browser command line profile is independently checked against
        # the disposable UDF by Sysmon+ETW. This remains a *command-line*
        # witness, not a proof of effective filesystem write destinations.
        profile_report = lifetime_report.get("no_cdp_profile_identity")
        profile_review = "NOT_EVALUATED"
        if type(profile_report) is dict:
            if (profile_report.get("status") == "SOURCE_OS_CORROBORATED"
                    and profile_report.get("browser_process_identity")
                    == "UNIQUE_SYSMON_ETW_APP_PROFILE"
                    and profile_report.get("profile_process_lifetimes")
                    == "SYSMON_ETW_DESCENDANTS_EXITED"
                    and type(profile_report.get("webview_process_count")) is int
                    and profile_report["webview_process_count"] == full_role_count
                    and profile_report.get("native_N12_acceptance") == "NOT_EVALUATED"
                    and child_review == "PRIVATE_ORIGINAL_HANDLES_REVIEWABLE_ONLY"):
                profile_review = "SYSMON_ETW_BROWSER_PROFILE_COMMAND_LINE_REVIEWED"
            else:
                profile_review = "UNVERIFIED_OR_INCOMPLETE"
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
        elif gaps or issues or full_role_count == 0 or app_identity != "MATCH" or loss != "ZERO_REPORTED_NOT_FULL_COMPLETENESS":
            reason = "fileio-evidence-or-original-process-identity-unresolved"
        elif child_review != "PRIVATE_ORIGINAL_HANDLES_REVIEWABLE_ONLY":
            reason = "no-cdp-original-webview-child-handles-unverified"
        elif profile_review != "SYSMON_ETW_BROWSER_PROFILE_COMMAND_LINE_REVIEWED":
            reason = "no-cdp-browser-profile-command-line-unverified"
        else:
            reason = "full-n12-calibration-and-transient-write-control-not-collected"
        return _fixed_report(
            blocker=reason, violations=violations, gaps=gaps, counts=file_counts,
            source_issues=len(issues), scoped_roles=full_role_count,
            snapshot_state=state, app_identity=app_identity, capture_loss=loss,
            child_handles=child_review, browser_profile=profile_review,
        )
    except (trace.EvidenceValidationError, KeyError, ValueError, TypeError, OSError,
            UnicodeError):
        return _fixed_report(blocker="strict-fileio-reducer-or-evidence-invalid")


