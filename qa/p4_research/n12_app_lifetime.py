"""Capture one approved hosted PilotODIN startup and graceful shutdown."""
from __future__ import annotations

import argparse
from collections import Counter
import json
import os
import shutil
import subprocess
import sys
import time

from qa.p4_native import n12_etw_probe
from qa.p4_native import n12_exit_corroboration as corroboration
from qa.p4_native import n12_lifetime_etw as etw
from qa.p4_native import n12_trace as trace
from qa.p4_native.n12_lifetime_control import process_times
from qa.p4_research import n12_app_build as build
from qa.p4_research import n12_app_journey as journey


CONSENT = "I_APPROVE_ONE_N12_APP_LIFETIME"
READY_PROBE = journey.FRONTEND / "e2e" / "p4-n12-app-lifetime-ready.mjs"


def preflight(source, expected_hash):
    trace.require(os.environ.get("PILOTODIN_N12_APP_LIFETIME_CONSENT") == CONSENT,
                  "separate one-run N12 app lifetime consent is required")
    trace.require(not any(value and (key.upper().startswith("WEBVIEW2_") or key.upper() in {
        "PILOTODIN_HOME", "PILOTODIN_DESKTOP_SESSION", "PILOTODIN_DESKTOP_TOKEN", "TAURI_CONFIG",
    }) for key, value in os.environ.items()), "inherited application configuration is present")
    staged = build.stage_root(source)
    provenance = build.verify(staged, source, expected_hash)
    trace.require(not any(map(journey.listening, journey.PORTS)), "a required loopback port is in use")
    node = shutil.which("node.exe")
    trace.require(node is not None, "Node is required for native bridge readiness")
    root = trace.local_disposable_path(staged.with_name(staged.name + "-lifetime"), runner_temp_only=True)
    return root, staged, provenance, node


def launch_and_close(root, staged, node, source, expected_hash):
    """Run in a short-lived worker so the app parent is also captured through exit."""
    trace.require((root / "lifetime-launch.json").is_file(), "app lifetime capture has not opened")
    journey.report_file(root / "lifetime-worker-started.json", {"source_sha": source})
    home = root / f'P4-71-only-home-{os.environ["GITHUB_RUN_ID"]}'
    profile = root / "webview"
    binary = build.executable(staged)
    title = json.loads(build.isolated_config())["app"]["windows"][0]["title"]
    env = {**os.environ, "CI": "true", "PILOTODIN_HOME": str(home),
           "VITE_PILOTODIN_NATIVE_SMOKE": "1", "PYTHONDONTWRITEBYTECODE": "1"}
    manifest = {"processes": []}
    with journey.journey_processes(source, expected_hash) as stack:
        with journey.checkpoint_stage("app-lifetime-services", source, expected_hash):
            backend = journey.spawn(stack, manifest, "backend", [
                sys.executable, "-B", "-m", "uvicorn", "backend.main:app",
                "--host", "127.0.0.1", "--port", "8000", "--no-access-log",
            ], env, build.REPO, root / "backend.log")
            vite = journey.spawn(stack, manifest, "driver", [
                node, str(journey.FRONTEND / "node_modules/vite/bin/vite.js"),
                "--host", "127.0.0.1", "--port", "5173", "--strictPort",
            ], env, journey.FRONTEND, root / "vite.log")
            journey.wait_for(lambda: journey.http_ready(8000, "/api/health", lambda status:
                            status.get("status") == "ok" and status.get("cloud_ai") is False),
                            60, "isolated backend did not become ready with cloud AI off", backend)
            journey.wait_for(lambda: journey.http_ready(5173, "/"), 60, "Vite did not become ready", vite)

        with journey.checkpoint_stage("app-lifetime-ready", source, expected_hash):
            build.verify(staged, source, expected_hash)
            app_env = {**env, "WEBVIEW2_USER_DATA_FOLDER": str(profile),
                       "WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS": "--remote-debugging-port=9331"}
            app = journey.spawn(stack, manifest, "app", [binary], app_env, binary.parent, root / "app.log")
            journey.wait_for(lambda: journey.http_ready(9331, "/json/version",
                             lambda status: bool(status.get("webSocketDebuggerUrl"))),
                             45, "WebView debugger did not become ready", app)
            ready = journey.quiet([node, str(READY_PROBE)], cwd=journey.FRONTEND,
                                  env={**env, "TEMP": str(root / journey.DRIVER_TEMP_DIR),
                                       "TMP": str(root / journey.DRIVER_TEMP_DIR)}, timeout=115)
            trace.require(ready.strip() == b"N12 app lifetime native close listener ready and peer closed",
                          "native close listener readiness and QA peer close were not verified")
        with journey.checkpoint_stage("app-lifetime-graceful-close", source, expected_hash):
            trace.require(app.poll() is None and backend.poll() is None and vite.poll() is None,
                          "app or local service exited before verified close")
            request_graceful_close(app, binary, title)
        with journey.checkpoint_stage("app-lifetime-handle-exit", source, expected_hash):
            trace.require(app.wait(timeout=5) == 0, "app did not exit normally")
            app_times = process_times(app)
        with journey.checkpoint_stage("app-lifetime-profile-exit", source, expected_hash):
            journey.wait_for(lambda: not journey.listening(9331) and int(journey.powershell(
                journey.HELPER, "profile-active", "-ProfilePath", profile, timeout=10,
            )) == 0, 25, "WebView processes did not exit for the disposable profile")
    journey.report_file(root / "private-app-handle.json", app_times)


def request_graceful_close(app, binary, title):
    try:
        journey.powershell(journey.HELPER, "close", "-AppProcessId", app.pid,
                           "-AppPath", binary, "-AppTitle", title, "-ReportCloseStatus", timeout=25)
    except subprocess.CalledProcessError as exc:
        category = {
            b"n12-close-handle-unavailable": "window-handle-unavailable",
            b"n12-close-identity-mismatch": "window-identity-mismatch",
            b"n12-close-request-rejected": "window-close-message-rejected",
            b"n12-close-process-timeout": "window-process-exit-timeout",
            b"n12-close-exit-nonzero": "window-process-exit-nonzero",
        }.get((exc.stdout or b"").strip(), "window-close-helper-failed")
        raise trace.EvidenceValidationError(category) from exc


def launch_worker(root, source, expected_hash):
    journey.report_file(root / "lifetime-launch.json", {"source_sha": source})
    command = [sys.executable, "-B", "-m", "qa.p4_research.n12_app_lifetime",
               "--source", source, "--expected-exe-sha256", expected_hash, "--worker"]
    with subprocess.Popen(command, cwd=build.REPO) as worker:
        try:
            trace.require(worker.wait(timeout=300) == 0, "app lifetime worker did not complete")
            times = process_times(worker)
        finally:
            journey.cleanup_process(worker)
    return times, trace.read_json(root / "private-app-handle.json")


def reduction(manifest, sysmon, events, volume_devices, session, app_witness, worker_witness, binary):
    devices = trace.etw_device_aliases(volume_devices)
    start, end, processes, _, issues = trace.load_capture(
        manifest, sysmon, etw=True, rejected_sysmon_exits=[])
    roles, bindings = trace.bind_processes([{"pid": app_witness["pid"], "role": "app",
                                            "image": str(binary)}], processes, issues)
    scoped = {guid: processes[guid] for guid in roles}
    counts = Counter(roles.values())
    if not counts["webview"] or not counts["webview-network"]:
        issues.add("app-profile-lifetime-missing")
    if any(session["counters"][key] for key in etw.COUNTERS[:-1]):
        issues.add("etw-event-or-buffer-loss")
    if not session["counters"]["buffers_written"]:
        issues.add("etw-no-buffers-written")
    window = trace.utc_ticks(start), trace.utc_ticks(end)
    stream = list(trace.etw_events(events, (session["start"], session["end"]), manifest["events_sha256"]))
    witnesses = {"app": "BLOCKED", "launcher": "BLOCKED"}
    timing = []
    start_images = {}
    handle_order = {}
    child_order = []
    if bindings and not issues & corroboration.SOURCE_COVERAGE_ISSUES:
        app = bindings[0][1]
        worker = processes.get(app.parent)
        try:
            trace.require(app.sha256 == manifest["executable_sha256"], "app-sysmon-executable-hash-unverified")
            trace.require(worker is not None and worker.pid == worker_witness["pid"]
                          and worker.image == trace.windows_path(sys.executable),
                          "launcher-sysmon-identity-unverified")
            with trace.evidence_stage("app lifetime ETW payload"):
                lifetimes = corroboration.EtwLifetimes(stream, devices, window)
            # Record each scoped comparison before the strict join stops at the first failure.
            by_role = {"launcher": Counter({lifetimes.start_image_comparison(worker): 1})}
            for guid, process in scoped.items():
                by_role.setdefault(roles[guid], Counter())[lifetimes.start_image_comparison(process)] += 1
            start_images = {role: dict(sorted(counts.items())) for role, counts in sorted(by_role.items())}
            handle_order = {
                "launcher": lifetimes.order_comparison(worker, worker_witness),
                "app": lifetimes.order_comparison(app, app_witness),
            }
            child_order = [
                {"role": roles[guid], **lifetimes.order_comparison(process)}
                for guid, process in scoped.items() if guid != app.guid
            ]
            launcher_lifetime = lifetimes.find(worker, handle_witness=worker_witness)
            launcher_start, launcher_stop = launcher_lifetime
            witnesses["launcher"] = "MATCH"
            app_start, app_stop = lifetimes.find(app, handle_witness=app_witness)
            trace.require(app_start.parent == launcher_start.pid
                          and app_start.parent_sequence == launcher_start.sequence
                          and launcher_start.creation <= app_start.creation
                          <= app_witness["exit"] <= launcher_stop.exit,
                          "app-etw-launcher-lifetime-unverified")
            witnesses["app"] = "MATCH"
            matched = {app.guid: (app_start, app_stop)}
            matched.update({guid: lifetimes.find(process) for guid, process in scoped.items() if guid != app.guid})
            for guid, (child_start, _) in matched.items():
                if guid == app.guid:
                    continue
                parent_start, parent_stop = matched[scoped[guid].parent]
                trace.require(child_start.parent == parent_start.pid
                              and child_start.parent_sequence == parent_start.sequence
                              and parent_start.creation <= child_start.creation <= parent_stop.exit,
                              "app-tree-etw-parent-lifetime-unverified")
            matched_births = {birth for birth, _ in matched.values()}
            for births in lifetimes.starts.values():
                for birth in births:
                    if birth in matched_births:
                        continue
                    if any(birth.parent == parent.pid and birth.parent_sequence == parent.sequence
                           and parent.creation <= birth.creation <= stop.exit
                           for parent, stop in matched.values()):
                        issues.add("app-tree-etw-child-missing-from-sysmon")
            pairs = [(worker, "launcher", launcher_lifetime)]
            pairs.extend((scoped[guid], roles[guid], pair) for guid, pair in matched.items())
            for process, role, (birth, stop) in pairs:
                recorded_exit = process.disputed_exit.stamp if process.disputed_exit else process.end
                exit_delta = stop.exit - trace.utc_ticks(recorded_exit) if recorded_exit is not None else None
                timing.append({"role": role, "etw_minus_sysmon_birth_ticks": birth.creation - trace.utc_ticks(process.start),
                               "etw_minus_sysmon_exit_ticks": exit_delta})
        except trace.EvidenceValidationError as exc:
            issues.add(str(exc))
    disputed = [row for row in corroboration.corroborate_exits(
        stream, processes, roles, devices, window, issues
    ) if row["role"] in {"app", "webview", "webview-network", "helper"}]
    if "BLOCKED" in witnesses.values():
        issues.add("app-or-launcher-handle-unverified")
    return {"scope": "one-native-startup-and-graceful-close", "source_sha": manifest["source_sha"],
            "executable_sha256": manifest["executable_sha256"],
            "verdict": "BLOCKED" if issues else "PASS", "issues": sorted(issues),
            "app_roles": dict(sorted(counts.items())), "etw_start_image_comparisons": start_images,
            "handle_comparison": witnesses, "etw_handle_order_comparison": handle_order,
            "etw_child_order_comparisons": child_order,
            "collector_counters": session["counters"], "timing_comparisons": timing,
            "disputed_exits": disputed}


def endpoint_evidence(manifest, before):
    source, expected_hash = manifest["source_sha"], manifest["executable_sha256"]
    with journey.checkpoint_stage("app-lifetime-endpoints", source, expected_hash):
        snapshot, issues = trace.compare_snapshots(before, journey.snapshots(manifest), manifest)
        print("N12 app lifetime endpoints " + json.dumps({
            "source_sha": source, "executable_sha256": expected_hash, **snapshot,
        }), flush=True)
        return snapshot, issues


def capture(root, staged, provenance):
    source, expected_hash = provenance["source_sha"], provenance["executable_sha256"]
    manifest, _, _, fixture, _ = journey.prepare_journey(root, source, expected_hash)
    fixture.write_text("fixture,value\nstartup-close,1\n", encoding="utf-8")
    before = journey.snapshots(manifest)
    volume_devices = n12_etw_probe.volume_devices()
    with journey.checkpoint_stage("app-lifetime-window-open", source, expected_hash):
        manifest["sysmon_first_record"] = journey.sysmon_tail() + 1
    try:
        with etw.process_session(root, source, expected_hash) as session:
            manifest["start_utc"] = journey.now().isoformat()
            time.sleep(journey.INITIAL_FIXTURE_LEAD_IN_SECONDS)
            with journey.checkpoint_stage("app-lifetime-worker", source, expected_hash):
                worker, app = launch_worker(root, source, expected_hash)
    except Exception:
        try:
            endpoint_evidence(manifest, before)
        except Exception:
            pass  # Preserve the startup or capture failure.
        raise
    manifest["end_utc"] = journey.timestamp_from_ticks(session["end"]).isoformat()
    snapshot, snapshot_issues = endpoint_evidence(manifest, before)
    sysmon = root / "lifetime-sysmon.xml"
    with journey.checkpoint_stage("app-lifetime-sysmon-export", source, expected_hash):
        time.sleep(3)
        manifest["sysmon_last_record"] = journey.sysmon_tail()
        journey.export_sysmon(manifest["sysmon_first_record"], manifest["sysmon_last_record"], sysmon)
    with journey.checkpoint_stage("app-lifetime-etw-export", source, expected_hash):
        journey.powershell(journey.HELPER, "etw-app-lifetime-export", "-CaptureRoot", root, timeout=90)
    with journey.checkpoint_stage("app-lifetime-reduction", source, expected_hash):
        events = root / "lifetime-etw.jsonl"
        manifest["events_sha256"] = build.digest(events)
        report = reduction(manifest, sysmon, events, volume_devices, session, app, worker,
                           build.executable(staged))
        report["cargo_lock_sha256"] = provenance["cargo_lock_sha256"]
        report["protected_snapshot_comparison"] = snapshot["protected_snapshot_comparison"]
        if snapshot["protected_snapshot_comparison"] != "MATCH":
            report["verdict"] = "BLOCKED"
            report["issues"] = sorted(set(report["issues"]) | snapshot_issues | {"protected-endpoints-unverified"})
        print("N12 app lifetime result " + json.dumps(report), flush=True)
        journey.report_file(root / "lifetime-report.json", report)
        return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True)
    parser.add_argument("--expected-exe-sha256", required=True)
    parser.add_argument("--worker", action="store_true")
    args = parser.parse_args()
    try:
        with journey.checkpoint_stage("app-lifetime-preflight", args.source, args.expected_exe_sha256):
            root, staged, provenance, node = preflight(args.source, args.expected_exe_sha256)
        if args.worker:
            launch_and_close(root, staged, node, args.source, args.expected_exe_sha256)
            return 0
        print("N12 app lifetime provenance " + json.dumps({
            key: provenance[key] for key in ("source_sha", "executable_sha256", "cargo_lock_sha256")
        }), flush=True)
        return 0 if capture(root, staged, provenance)["verdict"] == "PASS" else 2
    except trace.EvidenceValidationError as exc:
        print(f"N12 app lifetime blocked: {exc}.", file=sys.stderr)
    except (KeyError, OSError, RuntimeError, ValueError, subprocess.SubprocessError) as exc:
        print(f"N12 app lifetime blocked: {type(exc).__name__}.", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
