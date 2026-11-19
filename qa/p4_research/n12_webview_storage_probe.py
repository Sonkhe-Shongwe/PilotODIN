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


def file_control(manifest, label, path):
    with subprocess.Popen([sys.executable, "-B", "-c", CONTROL, str(path)],
                          stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) as child:
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
    manifest["probe_user_temp"] = str(ambient)
    fixture.write_text("fixture,value\nwebview-storage,1\n", encoding="utf-8")
    before = journey.snapshots(manifest)
    journey.mark(manifest, "fixture-ready")
    file_control(manifest, "scratch", profile / journey.APP_TEMP_DIR / "storage-control.tmp")
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
    protected.extend(trace.windows_path(manifest["observed_roots"][key]) for key in manifest["immutable_observed"])
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
    observed_controls = set()
    diagnostics = Counter()
    paths = journey.diagnostic_paths(root, staged, manifest, user_temp=manifest.get("probe_user_temp"))

    def observe(stamp, process, role, operation, path):
        if operation == "create" and role == "calibration":
            for label, identity in expected.items():
                if identity == (process.guid, path) and (
                    (label == "scratch" and stamp < launch) or (label == "user-temp" and exited < stamp)
                ):
                    observed_controls.add(label)
        if role not in WEBVIEW_ROLES or operation not in {"create", "overwrite", "write"}:
            return
        category = next((label for label, base in paths.roots if trace.inside(path, base)), None)
        if category in {"user-temp", "runner-temp"}:
            if operation != "create":
                return
            family = category
        elif category == "user-local":
            family = next((label for label, base in paths.webview_local_families if trace.inside(path, base)),
                          "other-user-local")
        else:
            return
        stage = ("startup" if stamp < ready else "ready-probe" if stamp < close else
                 "close" if stamp <= exited else "after-profile-exit")
        extension = ntpath.splitext(path)[1]
        file_type = FILE_TYPES.get(extension, "other-extension" if extension else "no-extension")
        diagnostics[family, operation, component(process, role, browser_guid), stage, file_type] += 1

    file_coverage_issues = set()
    _, violations, _, unresolved_files = trace.inspect_files(
        procmon, fixture_ready, end, processes, roles, protected, permitted, file_coverage_issues, observe=observe,
    )
    protected_operations = []
    for key, count in sorted(violations.items()):
        if key.startswith("protected:"):
            _, role, operation = key.split(":")
            protected_operations.append({"role": role, "operation": operation, "count": count})
    controls = {name: name in observed_controls for name in ("scratch", "user-temp")}
    if not all(controls.values()):
        issues.add("known-create-controls-unverified")
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
