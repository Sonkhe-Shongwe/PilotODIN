"""Compare two independently approved, redacted WebView2 storage receipts.

This is source-only diagnostic analysis. A comparison never awards N12 acceptance
or authorizes native capture, installation, firewall changes or owner-data access.
"""
import argparse
from collections import Counter
import json
from pathlib import Path
import re
import sys


VARIANTS = ("debug-only", "debug-netlog")
OUTSIDE_FAMILIES = frozenset({
    "user-temp", "runner-temp", "direct3d-cache", "edge-webview", "edge-update",
    "edge", "windows-internet-cache", "windows-web-cache", "crash-dumps",
    "other-user-local",
})
ALL_FAMILIES = OUTSIDE_FAMILIES | {"startup-tmp", "qa-app-temp"}
COMPONENTS = frozenset({"browser", "renderer", "network-service", "gpu-process", "utility", "unclassified"})
OPERATIONS = frozenset({"create", "overwrite", "write"})
STAGES = frozenset({"startup", "ready-probe", "close", "after-profile-exit"})
FILE_TYPES = frozenset({"database", "data", "metadata", "log", "python-bytecode", "temporary",
                        "other-extension", "no-extension"})
REPORT_KEYS = ("destination_family", "operation", "component", "stage", "file_type")


def _valid_hex(value, length):
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{" + str(length) + r"}", value) is not None


def _verify(report, variant):
    """Return fixed diagnostic labels and validated out-of-profile event counts."""
    problems = set()
    counts = Counter()
    if not isinstance(report, dict):
        return {"report-invalid"}, counts
    if report.get("scope") != "one-startup-and-close-storage-diagnostic":
        problems.add("capture-scope-invalid")
    if report.get("storage_diagnostic_variant") != variant:
        problems.add("variant-label-unverified")
    run = report.get("storage_capture_run_id")
    if not isinstance(run, str) or re.fullmatch(r"[1-9][0-9]{0,18}", run) is None or (
        type(report.get("storage_capture_attempt")) is not int
        or report["storage_capture_attempt"] != 1
    ):
        problems.add("capture-identity-unverified")
    if not _valid_hex(report.get("source_sha"), 40) or not _valid_hex(report.get("executable_sha256"), 64):
        problems.add("source-provenance-unverified")
    versions = report.get("webview_runtime_versions")
    if not isinstance(versions, list) or len(versions) != 1 or not isinstance(versions[0], str) or (
        re.fullmatch(r"[0-9]+(?:\.[0-9]+){3}", versions[0]) is None
    ):
        problems.add("runtime-version-unverified")
    if report.get("verdict") not in {"REPRODUCED", "INCONCLUSIVE"} or report.get("issues") != []:
        problems.add("storage-reducer-not-clean")
    if report.get("file_coverage_issues") != [] or report.get("unresolved_file_events") != []:
        problems.add("file-attribution-incomplete")
    if (report.get("procmon_shutdown_verified") is not True
            or report.get("procmon_loss_reviewed") is not True):
        problems.add("collector-coverage-unverified")
    if (report.get("protected_snapshot_comparison") != "MATCH"
            or report.get("protected_operations") != []
            or report.get("protected_operation_details") != []):
        problems.add("protected-data-evidence-unverified")
    controls = report.get("known_create_controls")
    if not isinstance(controls, dict) or controls.get("scratch") is not True or controls.get("user-temp") is not True:
        problems.add("positive-controls-incomplete")
    if report.get("startup_tmp_probe") is not True or report.get("startup_tmp_control_verified") is not True or (
        report.get("browser_startup_tmp") != "expected-tmp"
    ):
        problems.add("browser-tmp-control-unverified")
    flags = report.get("browser_launch_flags")
    expected_netlog = "present" if variant == "debug-netlog" else "absent"
    if (report.get("browser_variant_corroboration") != "agrees"
            or not isinstance(flags, dict)
            or flags.get("status") != "environment-observed"
            or flags.get("remote_debugging") != "present"
            or flags.get("netlog") != expected_netlog):
        problems.add("observed-browser-flags-disagree")
    context = report.get("browser_storage_context")
    if (not isinstance(context, dict)
            or any(context.get(k) != v for k, v in {
                "receipt": "environment-observed", "temp": "declared-app-temp",
                "tmp": "startup-tmp", "udf": "declared-profile",
            }.items())):
        problems.add("browser-storage-boundary-unverified")
    if report.get("storage_context_is_acceptance_evidence") is not False:
        problems.add("acceptance-scope-invalid")

    events = report.get("storage_events")
    writers = report.get("writer_storage_context")
    writer_counts = Counter()
    if not isinstance(events, list) or not isinstance(writers, list):
        problems.add("event-summary-invalid")
        return problems, counts
    for event in events:
        if (not isinstance(event, dict) or
            event.get("destination_family") not in ALL_FAMILIES or
            event.get("operation") not in OPERATIONS or
            event.get("component") not in COMPONENTS or
            event.get("stage") not in STAGES or
            event.get("file_type") not in FILE_TYPES or
            type(event.get("count")) is not int or not 0 < event["count"] <= 10_000_000):
            problems.add("event-summary-invalid")
            continue
        key = tuple(event[name] for name in REPORT_KEYS[:-1])
        if event["destination_family"] in OUTSIDE_FAMILIES:
            counts[key] += event["count"]
    for writer in writers:
        if (not isinstance(writer, dict)
                or writer.get("destination_family") not in ALL_FAMILIES
                or writer.get("operation") not in OPERATIONS
                or writer.get("component") not in COMPONENTS
                or writer.get("stage") not in STAGES
                or type(writer.get("count")) is not int
                or not 0 < writer["count"] <= 10_000_000):
            problems.add("writer-summary-invalid")
            continue
        if (writer.get("receipt") != "environment-observed"
                or writer.get("udf") != "declared-profile"
                or writer.get("temp") != "declared-app-temp"
                or writer.get("tmp") != "startup-tmp"):
            problems.add("writer-storage-boundary-unverified")
        if writer["destination_family"] in OUTSIDE_FAMILIES:
            writer_counts[tuple(writer[name] for name in REPORT_KEYS[:-1])] += writer["count"]
    if counts != writer_counts:
        problems.add("writer-event-summaries-disagree")
    if (type(report.get("ambient_temp_creates")) is not int or
            report.get("ambient_temp_creates") != sum(
                count for (family, operation, _, _), count in counts.items()
                if family in {"user-temp", "runner-temp"} and operation == "create"
            )):
        problems.add("ambient-create-count-mismatch")
    return problems, counts


def compare_pair(first, second):
    """A single pair can identify differences, never establish their cause."""
    reports = [first, second]
    labelled = {r.get("storage_diagnostic_variant"): r for r in reports if isinstance(r, dict)}
    problems = set()
    if len(labelled) != 2 or set(labelled) != set(VARIANTS):
        problems.add("distinct-variants-required")
    for variant in VARIANTS:
        report = labelled.get(variant)
        issues, _ = _verify(report, variant)
        problems.update(issues)
    if not problems:
        only, netlog = (labelled[v] for v in VARIANTS)
        if only["storage_capture_run_id"] == netlog["storage_capture_run_id"]:
            problems.add("independent-captures-required")
        if only["source_sha"] != netlog["source_sha"]:
            problems.add("source-revision-mismatch")
        if only["executable_sha256"] != netlog["executable_sha256"]:
            problems.add("executable-digest-mismatch")
        if only["webview_runtime_versions"] != netlog["webview_runtime_versions"]:
            problems.add("runtime-version-mismatch")
    result = {
        "scope": "webview-storage-single-pair-diagnostic-only",
        "verdict": "BLOCKED" if problems else "COMPARABLE_DIAGNOSTIC",
        "issues": sorted(problems),
        "native_N12_acceptance": "NOT_EVALUATED",
        "causality_proven": False,
    }
    if problems:
        return result
    baseline = _verify(labelled["debug-only"], "debug-only")[1]
    netlog = _verify(labelled["debug-netlog"], "debug-netlog")[1]
    baseline_total, netlog_total = sum(baseline.values()), sum(netlog.values())
    signal = ("outside-operations-in-both" if baseline_total and netlog_total
              else "observed-only-with-netlog" if netlog_total
              else "observed-only-without-netlog" if baseline_total
              else "no-observed-outside-operations-in-pair")
    result["signal"] = signal
    result["outside_profile_operation_counts"] = {
        "debug-only": baseline_total, "debug-netlog": netlog_total,
    }
    result["group_differences"] = [
        {"destination_family": family, "operation": op, "component": component,
         "stage": stage, "debug_only": baseline[family, op, component, stage],
         "debug_netlog": netlog[family, op, component, stage]}
        for family, op, component, stage in sorted(set(baseline) | set(netlog))
        if baseline[family, op, component, stage] != netlog[family, op, component, stage]
    ]
    result["interpretation_limit"] = (
        "One independent diagnostic pair is not causal proof or a complete filesystem audit."
    )
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("first", type=Path, help="First private redacted receipt JSON")
    parser.add_argument("second", type=Path, help="Second private redacted receipt JSON")
    args = parser.parse_args(argv)
    try:
        reports = [json.loads(p.read_text(encoding="utf-8")) for p in (args.first, args.second)]
        result = compare_pair(*reports)
    except (OSError, UnicodeError, ValueError, TypeError):
        result = {"scope": "webview-storage-single-pair-diagnostic-only", "verdict": "BLOCKED",
                  "issues": ["input-read-or-schema-invalid"], "native_N12_acceptance": "NOT_EVALUATED",
                  "causality_proven": False}
    print(json.dumps(result, sort_keys=True))
    return 2 if result["verdict"] == "BLOCKED" else 0


if __name__ == "__main__":
    sys.exit(main())
