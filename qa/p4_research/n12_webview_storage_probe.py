"""Attribute WebView2 storage in one approved startup and close capture."""
import argparse
from collections import Counter
import json
import ntpath
import os
from pathlib import Path
import re
import subprocess
import sys
from tempfile import TemporaryDirectory

from qa.p4_native import n12_trace as trace
from qa.p4_research import n12_app_journey as journey
from qa.p4_research import n12_app_lifetime as lifetime
from qa.p4_research.n12_journey_diagnostics import FILE_TYPES, WEBVIEW_ROLES


PROBE_DIR = "storage"
STAGES = ("launch", "ready", "close", "profile-exit")
CONTROL = (
    "from pathlib import Path; import sys, time; "
    "time.sleep(0.5); "
    "f = Path(sys.argv[1]).open('xb'); f.write(b'PilotODIN control'); f.close(); "
    "time.sleep(0.5)"
)


def file_control(manifest, label, path, *, env=None):
    with subprocess.Popen([sys.executable, "-B", "-c", CONTROL, str(path)],
                          env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) as child:
        try:
            trace.require(child.wait(timeout=10) == 0 and path.read_bytes() == b"PilotODIN control",
                          "generated file control did not write its expected bytes")
        finally:
            journey.cleanup_process(child)
        manifest["processes"].append({"role": "calibration", "pid": child.pid, "image": sys.executable,
                                      "label": label, "target": str(path)})


def runner_control_temp(env):
    inherited = Path(env["TEMP"])
    trace.require(inherited.is_absolute() and ".." not in inherited.parts,
                  "inherited temp is not an absolute local directory")
    ambient = inherited.resolve(strict=True)
    if os.name == "nt":
        trace.windows_path(str(ambient))
    user_temp = Path(env["LOCALAPPDATA"]).resolve(strict=True) / "Temp"
    runner_temp = Path(env["RUNNER_TEMP"]).resolve(strict=True)
    trace.require(ambient.is_dir(), "inherited temp does not resolve to a directory")
    trace.require(ambient.is_relative_to(user_temp) or ambient.is_relative_to(runner_temp),
                  "resolved temp is outside the hosted user-temp and runner-temp roots")
    return ambient


def capture(root, staged, node, source, expected_hash):
    ambient = runner_control_temp(os.environ)
    manifest, _, profile, fixture, _ = journey.prepare_journey(root, source, expected_hash)
    tmp_witness = profile / journey.APP_TEMP_DIR / lifetime.STORAGE_TMP_DIR
    tmp_witness.mkdir()
    manifest["probe_user_temp"] = str(ambient)
    manifest["startup_tmp_probe"] = True
    fixture.write_text("fixture,value\nwebview-storage,1\n", encoding="utf-8")
    before = journey.snapshots(manifest)
    journey.mark(manifest, "fixture-ready")
    file_control(manifest, "scratch", profile / journey.APP_TEMP_DIR / "storage-control.tmp",
                 env={**os.environ, "TMP": str(tmp_witness)})
    lifetime.launch_and_close(root, staged, node, source, expected_hash, storage_manifest=manifest)
    with TemporaryDirectory(prefix="pilotodin-storage-control-", dir=ambient) as folder:
        file_control(manifest, "user-temp", Path(folder) / "storage-control.tmp")
    snapshot, issues = trace.compare_snapshots(before, journey.snapshots(manifest), manifest)
    manifest["protected_snapshot_comparison"] = snapshot["protected_snapshot_comparison"]
    manifest["snapshot_issues"] = sorted(issues)
    journey.report_file(root / "private-storage-capture.json", manifest)


def component(process, role, browser_guid):
    if process.guid == browser_guid:
        return "browser"
    if role == "webview-network":
        return "network-service"
    matches = re.findall(r"(?:^|\s)--type=([a-z-]+)(?=\s|$)", process.command)
    return matches[0] if len(matches) == 1 and matches[0] in {"renderer", "gpu-process", "utility"} else "unclassified"


def process_start_environment(detail, parent_pid, command):
    """Bind the exported environment to a known parent and command."""
    match = re.fullmatch(
        r"Parent PID: (\d+), Command line: (.*?), Current directory: (.*)", detail, re.S,
    )
    if match is None:
        return "start-detail-unrecognized", None
    if (parent_pid is None or int(match[1]) != parent_pid
            or not command.strip() or match[2].strip() != command.strip()):
        return "start-identity-mismatch", None
    _, separator, environment = match[3].partition(", Environment:")
    if not separator:
        return "environment-field-unobserved", None
    return "environment-observed", environment


def process_start_path(environment, key):
    values = re.findall(rf"(?:^| ; |\r?\n)[ \t]*{re.escape(key)}=([^\r\n]*?)(?= ; |\r?\n|$)",
                        environment, re.I)
    label = key.casefold()
    if not values:
        return f"{label}-not-observed", None
    if len(values) > 1:
        return f"{label}-ambiguous", None
    try:
        return f"{label}-observed", trace.windows_path(values[0])
    except ValueError:
        return f"{label}-path-invalid", None


def process_start_tmp(detail, process, parent):
    status, environment = process_start_environment(detail, parent.pid if parent else None, process.command)
    return (status, None) if environment is None else process_start_path(environment, "TMP")


def reduce(root, staged, manifest, sysmon, procmon):
    start, end, processes, _, issues = trace.load_capture(manifest, sysmon)
    # This is a direct-path diagnosis. Track the existing capture-loss limitation separately.
    loss_reviewed = "procmon-coverage-not-confirmed" not in issues
    issues.discard("procmon-coverage-not-confirmed")
    shutdown_verified = manifest.get("procmon_shutdown_verified") is True
    if not shutdown_verified:
        issues.add("procmon-shutdown-unverified")
    if not manifest["procmon_all_events"] or not manifest["procmon_clock_utc"]:
        issues.add("procmon-capture-configuration-unverified")
    protected, permitted = trace.scope(manifest)
    immutable = [trace.windows_path(manifest["observed_roots"][key]) for key in manifest["immutable_observed"]]
    protected.extend(immutable)
    declared = [item for item in manifest["processes"] if item["role"] in {"app", "calibration"}]
    roles, bindings = trace.bind_processes(declared, processes, issues)
    apps = [process for binding, process in bindings if binding["role"] == "app"]
    app_verified = len(apps) == 1 and apps[0].sha256 == manifest["executable_sha256"]
    if not app_verified:
        issues.add("app-source-identity-unverified")
    webviews = [process for guid, process in processes.items() if roles.get(guid) in WEBVIEW_ROLES]
    if not webviews:
        issues.add("webview-process-lifetime-unverified")
    runtime_dirs = {ntpath.basename(ntpath.dirname(process.image)) for process in webviews}
    versions = {version for version in runtime_dirs if re.fullmatch(r"\d+\.\d+\.\d+\.\d+", version)}
    if len(versions) != 1 or versions != runtime_dirs:
        issues.add("webview-runtime-version-unverified")
    launch, ready, close, exited = (trace.utc_time(manifest["markers"][name]) for name in STAGES)
    fixture_ready = trace.utc_time(manifest["markers"]["fixture-ready"])
    trace.require(start <= fixture_ready < launch < ready <= close < exited <= end,
                  "storage probe stages out of order")
    browser_pid = manifest.get("cdp_browser_pid")
    browser_guid = None
    if app_verified and type(browser_pid) is int and browser_pid > 0:
        candidates = [p for p in processes.values() if p.pid == browser_pid and p.start <= close
                      and (p.end is None or p.end >= ready)]
        if len(candidates) == 1:
            candidate = candidates[0]
            if (roles.get(candidate.guid) == "webview" and candidate.start <= ready
                    and candidate.end is not None and candidate.end >= close
                    and not re.search(r"(?:^|\s)--type(?:[=\s]|$)", candidate.command)):
                browser_guid = candidate.guid
    expected = {binding["label"]: (process.guid, trace.windows_path(binding["target"]))
                for binding, process in bindings if binding["role"] == "calibration"}
    control_creates = {}
    diagnostics = Counter()
    paths = journey.diagnostic_paths(root, staged, manifest, user_temp=manifest.get("probe_user_temp"))
    app_temp = tmp_witness = None
    if manifest.get("startup_tmp_probe") is True:
        profile = trace.windows_path(manifest["observed_roots"]["qa-webview"])
        app_temp = ntpath.join(profile, journey.APP_TEMP_DIR)
        tmp_witness = ntpath.join(app_temp, lifetime.STORAGE_TMP_DIR)
    startup_candidates = {}
    if tmp_witness is not None:
        scratch = next((process for binding, process in bindings if binding.get("label") == "scratch"), None)
        pid_counts = Counter(process.pid for process in processes.values())
        for label, process, first, last in (
            ("scratch", scratch, fixture_ready, launch),
            ("browser", processes.get(browser_guid), launch, ready),
        ):
            if process is not None and pid_counts[process.pid] == 1:
                startup_candidates[str(process.pid)] = (label, process, first, last)
    startup_values = {"scratch": [], "browser": []}
    first_browser_tmp_create = None
    protected_details = Counter()

    def observe_protected(role, operation, targets, identity):
        families = {"immutable-input" if any(trace.inside(target, path) for path in immutable)
                    else "protected-app-data" for target in targets}
        for family in families:
            protected_details[role, operation, family, identity] += 1

    def observe_process_start(row):
        candidate = startup_candidates.get(row["PID"])
        if candidate is None or row["Result"] != "SUCCESS":
            return
        label, process, first, last = candidate
        if row["Process Name"].casefold() != ntpath.basename(process.image):
            return
        try:
            stamp = trace.capture_time(row["Time of Day"], start)
        except (ValueError, trace.EvidenceValidationError):
            return
        if first <= stamp < last:
            status, value = process_start_tmp(row["Detail"], process, processes.get(process.parent))
            startup_values[label].append((stamp, status, value))

    def observe(stamp, process, role, operation, path):
        nonlocal first_browser_tmp_create
        if operation == "create" and role == "calibration":
            for label, identity in expected.items():
                if identity == (process.guid, path) and (
                    (label == "scratch" and stamp < launch) or (label == "user-temp" and exited < stamp)
                ):
                    control_creates[label] = min(control_creates.get(label, stamp), stamp)
        if role not in WEBVIEW_ROLES or operation not in {"create", "overwrite", "write"}:
            return
        stage = ("startup" if stamp < ready else "ready-probe" if stamp < close else
                 "close" if stamp <= exited else "after-profile-exit")
        extension = ntpath.splitext(path)[1]
        if process.guid == browser_guid and stage == "startup" and operation == "create" and extension == ".tmp":
            first_browser_tmp_create = min(first_browser_tmp_create or stamp, stamp)
        category = next((label for label, base in paths.roots if trace.inside(path, base)), None)
        if (app_temp is not None and stage == "startup" and operation == "create"
                and extension == ".tmp" and trace.inside(path, app_temp)):
            family = "startup-tmp" if trace.inside(path, tmp_witness) else "qa-app-temp"
        elif category in {"user-temp", "runner-temp"}:
            if operation != "create":
                return
            family = category
        elif category == "user-local":
            family = next((label for label, base in paths.webview_local_families if trace.inside(path, base)),
                          "other-user-local")
        else:
            return
        file_type = FILE_TYPES.get(extension, "other-extension" if extension else "no-extension")
        diagnostics[family, operation, component(process, role, browser_guid), stage, file_type] += 1

    file_coverage_issues = set()
    _, violations, _, unresolved_files = trace.inspect_files(
        procmon, fixture_ready, end, processes, roles, protected, permitted, file_coverage_issues, observe=observe,
        observe_process_start=observe_process_start if startup_candidates else None,
        observe_protected=observe_protected,
    )
    protected_operations = []
    for key, count in sorted(violations.items()):
        if key.startswith("protected:"):
            _, role, operation = key.split(":")
            protected_operations.append({"role": role, "operation": operation, "count": count})
    controls = {name: name in control_creates for name in ("scratch", "user-temp")}
    if not all(controls.values()):
        issues.add("known-create-controls-unverified")
    startup_receipts = {}
    # Compare timestamps within the Procmon export. Equal times cannot prove order.
    first_creates = {"scratch": control_creates.get("scratch"), "browser": first_browser_tmp_create}
    for label, records in startup_values.items():
        if len(records) == 1:
            stamp, status, _ = records[0]
            first_create = first_creates[label]
            startup_receipts[label] = (
                "start-order-unverified" if status == "tmp-observed" and first_create is not None
                and stamp >= first_create else status
            )
        elif records:
            startup_receipts[label] = "start-record-ambiguous"
        elif any(candidate[0] == label for candidate in startup_candidates.values()):
            startup_receipts[label] = "start-record-unobserved"
        else:
            startup_receipts[label] = "start-identity-unverified"
    scratch_record = startup_values["scratch"]
    scratch_matches = (startup_receipts["scratch"] == "tmp-observed"
                       and tmp_witness is not None and scratch_record[0][2] == tmp_witness)
    if scratch_matches:
        startup_receipts["scratch"] = "expected-tmp" if controls["scratch"] else "file-control-unverified"
    elif startup_receipts["scratch"] == "tmp-observed":
        startup_receipts["scratch"] = "tmp-value-mismatch"
    tmp_control_verified = scratch_matches and controls["scratch"]
    browser_startup_tmp = "unverified"
    if tmp_control_verified and startup_receipts["browser"] == "tmp-observed":
        _, _, observed = startup_values["browser"][0]
        if observed is not None:
            ambient = manifest.get("probe_user_temp")
            labels = {tmp_witness: "expected-tmp", app_temp: "app-temp"}
            if ambient is not None:
                labels[trace.windows_path(ambient)] = "ambient-temp"
            browser_startup_tmp = labels.get(observed, "different")
    if "file-event-process-ambiguous" in file_coverage_issues:
        issues.add("file-event-process-ambiguous")
    if (manifest["protected_snapshot_comparison"] != "MATCH" or
            "protected-create-result-unresolved" in file_coverage_issues or
            protected_operations):
        issues.add("protected-files-changed-or-unverified")
    rows = [{"destination_family": family, "operation": operation, "component": kind,
             "stage": stage, "file_type": file_type, "count": count}
            for (family, operation, kind, stage, file_type), count in sorted(diagnostics.items())]
    ambient_creates = sum(row["count"] for row in rows if row["destination_family"] in {"user-temp", "runner-temp"})
    if any(row["stage"] == "after-profile-exit" for row in rows):
        issues.add("webview-writes-after-profile-exit")
    return {"scope": "one-startup-and-close-storage-diagnostic", "source_sha": manifest["source_sha"],
            "executable_sha256": manifest["executable_sha256"],
            "verdict": "BLOCKED" if issues else "REPRODUCED" if ambient_creates else "INCONCLUSIVE",
            "issues": sorted(issues), "procmon_shutdown_verified": shutdown_verified,
            "procmon_loss_reviewed": loss_reviewed,
            "file_coverage_issues": sorted(file_coverage_issues),
            "protected_snapshot_comparison": manifest["protected_snapshot_comparison"],
            "protected_operations": protected_operations, "unresolved_file_events": unresolved_files,
            "protected_operation_details": [
                {"role": role, "operation": operation, "target": family, "identity": identity, "count": count}
                for (role, operation, family, identity), count in sorted(protected_details.items())
            ],
            "startup_tmp_probe": manifest.get("startup_tmp_probe") is True,
            "startup_tmp_control_verified": tmp_control_verified,
            "startup_tmp_receipts": startup_receipts,
            "browser_startup_tmp": browser_startup_tmp,
            "browser_process_corroborated": browser_guid is not None,
            "webview_runtime_versions": sorted(versions), "known_create_controls": controls,
            "ambient_temp_creates": ambient_creates, "storage_events": rows}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("capture", "reduce"))
    parser.add_argument("capture_root", type=Path)
    parser.add_argument("--source", required=True)
    parser.add_argument("--expected-exe-sha256", required=True)
    args = parser.parse_args()
    try:
        trace.require(os.environ.get("GITHUB_RUN_ATTEMPT") == "1"
                      and args.source == os.environ.get("PILOTODIN_N12_APPROVED_SOURCE"),
                      "the storage diagnostic requires its first source-pinned run")
        _, staged, _, node = lifetime.preflight(args.source, args.expected_exe_sha256, storage=True)
        base = trace.local_disposable_path(args.capture_root, runner_temp_only=True)
        root = base / PROBE_DIR
        if args.action == "capture":
            with journey.checkpoint_stage("webview-storage-launch-and-controls", args.source, args.expected_exe_sha256):
                capture(root, staged, node, args.source, args.expected_exe_sha256)
            return 0
        manifest = trace.read_json(root / "private-storage-capture.json")
        trace.require(manifest["source_sha"] == args.source and manifest["executable_sha256"] == args.expected_exe_sha256,
                      "storage capture provenance mismatch")
        window = trace.read_json(base / "storage-window.json")
        manifest.update({key: window[key] for key in (
            "schema_version", "disposable", "start_utc", "end_utc", "sysmon_first_record",
            "sysmon_last_record", "procmon_all_events", "procmon_loss_reviewed", "procmon_clock_utc",
        )})
        manifest["procmon_shutdown_verified"] = window.get("procmon_shutdown_verified")
        with journey.checkpoint_stage("webview-storage-reduction", args.source, args.expected_exe_sha256):
            report = reduce(root, staged, manifest, base / "sysmon.xml", base / "capture-utf8.csv")
        print("N12 WebView storage " + json.dumps(report), flush=True)
        return 2 if report["verdict"] == "BLOCKED" else 0
    except trace.EvidenceValidationError as exc:
        print(f"N12 WebView storage blocked: {exc}", file=sys.stderr)
    except (*trace.EVIDENCE_ERRORS, RuntimeError, subprocess.SubprocessError) as exc:
        print(f"N12 WebView storage blocked: {type(exc).__name__}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
