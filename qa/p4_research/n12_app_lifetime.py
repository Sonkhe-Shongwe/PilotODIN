"""Capture one approved hosted PilotODIN startup and graceful shutdown."""
from __future__ import annotations

import argparse
from collections import Counter
from contextlib import nullcontext
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
from qa.p4_native.n12_lifetime_control import process_images, process_times
from qa.p4_research import n12_app_build as build
from qa.p4_research import n12_app_journey as journey
from qa.p4_research import n12_no_cdp_native_path as no_cdp_path
from qa.p4_research import n12_no_cdp_browser_identity as browser_identity
from qa.p4_research import n12_no_cdp_child_handles as child_handles
from qa.p4_research import n12_private_child_pipe as child_pipe
from qa.p4_research import n12_no_cdp_fileio_review as fileio_review


CONSENT = "I_APPROVE_ONE_N12_APP_LIFETIME"
FILEIO_CONSENT = "I_APPROVE_ONE_N12_NO_CDP_FILEIO"
READY_PROBE = journey.FRONTEND / "e2e" / "p4-n12-app-lifetime-ready.mjs"
STORAGE_TMP_DIR = "startup-tmp"
STORAGE_DIAGNOSTIC_VARIANTS = ("debug-netlog", "debug-only")


def readiness_command(node, *, storage):
    return [node, str(READY_PROBE), "webview-storage" if storage else "lifetime"]


def storage_app_environment(env, profile, *, variant="debug-netlog"):
    """Compare netlog presence without changing startup debugging or storage roots."""
    trace.require(variant in STORAGE_DIAGNOSTIC_VARIANTS,
                  "unknown WebView storage diagnostic variant")
    settings = journey.app_environment(env, profile, "first")
    settings["TMP"] = str(profile / journey.APP_TEMP_DIR / STORAGE_TMP_DIR)
    if variant == "debug-only":
        # The CDP readiness and close driver still requires this single switch.
        settings["WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS"] = "--remote-debugging-port=9331"
    return settings


def backend_launch_context(env, home):
    """Keep the focused storage probe's backend identical to the full N12 QA.

    Previously the focused WebView storage capture retained inherited host
    TEMP/TMP/TMPDIR even after the full journey and product worker received
    app-local scratch. This made backend ambient writes a confounder in an
    otherwise WebView-focused experiment. Require already prepared dedicated
    scratch: no host-temp fallback and no change to allowed filesystem roots.
    """
    trace.require(home.is_dir(), "isolated QA backend data home is missing")
    return journey.backend_environment(env, home), home


def preflight(source, expected_hash, *, storage=False):
    if storage:
        trace.require(os.environ.get("PILOTODIN_N12_WEBVIEW_STORAGE_CONSENT") == "I_APPROVE_ONE_N12_WEBVIEW_STORAGE",
                      "separate one-run N12 WebView storage consent is required")
    else:
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


def launch_and_close(root, staged, node, source, expected_hash, *, storage_manifest=None, no_cdp=False):
    """Run in a short-lived worker so the app parent is also captured through exit."""
    trace.require(no_cdp is False or (no_cdp is True and storage_manifest is None
                  and os.environ.get("PILOTODIN_N12_NO_CDP_STORAGE_CONSENT")
                  == no_cdp_path.lifecycle.NATIVE_ACK_CONSENT),
                  "no-cdp-distinct-native-consent-missing")
    if storage_manifest is None:
        trace.require((root / "lifetime-launch.json").is_file(), "app lifetime capture has not opened")
        journey.report_file(root / "lifetime-worker-started.json", {"source_sha": source})
    home = root / f'P4-71-only-home-{os.environ["GITHUB_RUN_ID"]}'
    profile = root / "webview"
    binary = build.executable(staged)
    title = json.loads(build.isolated_config())["app"]["windows"][0]["title"]
    # Private child-witness authentication remains confined to this Python
    # worker. Never hand pipe credentials to app, backend or Vite children.
    transport_env = dict(os.environ) if no_cdp else None
    env = {**{k: v for k, v in os.environ.items()
              if k not in (child_pipe.PIPE_ENV, child_pipe.KEY_ENV,
                           "PILOTODIN_N12_CHILD_HANDLE_CONSENT")},
           "CI": "true", "PILOTODIN_HOME": str(home),
           "VITE_PILOTODIN_NATIVE_SMOKE": "1", "PYTHONDONTWRITEBYTECODE": "1"}
    manifest = {"processes": [], "markers": {}} if storage_manifest is None else storage_manifest
    if no_cdp:
        vite_env, no_cdp_app_env = no_cdp_path.no_cdp_environments(env, profile)
    else:
        vite_env = env
    with journey.journey_processes(source, expected_hash) as stack:
        with journey.checkpoint_stage("app-lifetime-services", source, expected_hash):
            backend_env, backend_cwd = backend_launch_context(env, home)
            backend = journey.spawn(stack, manifest, "backend", [
                sys.executable, "-B", "-m", "uvicorn", "backend.main:app",
                "--host", "127.0.0.1", "--port", "8000", "--no-access-log",
            ], backend_env, backend_cwd, root / "backend.log")
            vite = journey.spawn(stack, manifest, "driver", [
                node, str(journey.FRONTEND / "node_modules/vite/bin/vite.js"),
                "--host", "127.0.0.1", "--port", "5173", "--strictPort",
            ], vite_env, journey.FRONTEND, root / "vite.log")
            journey.wait_for(lambda: journey.http_ready(8000, "/api/health", lambda status:
                            status.get("status") == "ok" and status.get("cloud_ai") is False),
                            60, "isolated backend did not become ready with cloud AI off", backend)
            journey.wait_for(lambda: journey.http_ready(5173, "/"), 60, "Vite did not become ready", vite)

        with journey.checkpoint_stage("app-lifetime-ready", source, expected_hash):
            build.verify(staged, source, expected_hash)
            if no_cdp:
                no_cdp_path.run_one_no_cdp_app(
                    stack=stack, manifest=manifest, root=root, binary=binary,
                    title=title, source=source, expected_hash=expected_hash,
                    app_env=no_cdp_app_env, profile=profile,
                    transport_env=transport_env,
                )
                return
            app_env = {**env, "WEBVIEW2_USER_DATA_FOLDER": str(profile),
                       "WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS": "--remote-debugging-port=9331"}
            if storage_manifest is not None:
                app_env = storage_app_environment(
                    env, profile, variant=manifest.get("storage_diagnostic_variant", "debug-netlog"),
                )
                journey.mark(manifest, "launch")
            app = journey.spawn(stack, manifest, "app", [binary], app_env, binary.parent, root / "app.log")
            journey.wait_for(lambda: journey.http_ready(9331, "/json/version",
                             lambda status: bool(status.get("webSocketDebuggerUrl"))),
                             45, "WebView debugger did not become ready", app)
            if storage_manifest is not None:
                journey.mark(manifest, "ready")
            ready = journey.quiet(readiness_command(node, storage=storage_manifest is not None), cwd=journey.FRONTEND,
                                  env={**env, "TEMP": str(root / journey.DRIVER_TEMP_DIR),
                                       "TMP": str(root / journey.DRIVER_TEMP_DIR)}, timeout=115)
            if storage_manifest is not None:
                receipt = json.loads(ready)
                trace.require(isinstance(receipt, dict) and receipt.get("closeReady") is True,
                              "native close listener readiness and QA peer close were not verified")
                manifest["cdp_browser_pid"] = receipt.get("browserPid")
            else:
                trace.require(ready.strip() == b"N12 app lifetime native close listener ready and peer closed",
                              "native close listener readiness and QA peer close were not verified")
        with journey.checkpoint_stage("app-lifetime-graceful-close", source, expected_hash):
            trace.require(app.poll() is None and backend.poll() is None and vite.poll() is None,
                          "app or local service exited before verified close")
            app_images = process_images(app)
            if storage_manifest is not None:
                journey.mark(manifest, "close")
            journey.request_graceful_close(app, binary, title)
        with journey.checkpoint_stage("app-lifetime-handle-exit", source, expected_hash):
            trace.require(app.wait(timeout=5) == 0, "app did not exit normally")
            app_times = process_times(app) | app_images
        with journey.checkpoint_stage("app-lifetime-profile-exit", source, expected_hash):
            journey.wait_for(lambda: not journey.listening(9331) and int(journey.powershell(
                journey.HELPER, "profile-active", "-ProfilePath", profile, timeout=10,
            )) == 0, 25, "WebView processes did not exit for the disposable profile")
            if storage_manifest is not None:
                journey.mark(manifest, "profile-exit")
    journey.report_file(root / "private-app-handle.json", app_times)


def launch_worker(root, source, expected_hash, *, no_cdp=False):
    journey.report_file(root / "lifetime-launch.json", {"source_sha": source})
    command = [sys.executable, "-B", "-m", "qa.p4_research.n12_app_lifetime",
               "--source", source, "--expected-exe-sha256", expected_hash, "--worker"]
    if no_cdp:
        command.append("--no-cdp")
    enabled = no_cdp and child_pipe.requested(os.environ)
    pipe_context = (child_pipe.hosted_channel(os.environ, source, expected_hash)
                    if enabled else nullcontext(None))
    with pipe_context as receiver:
        # The independent receiver is armed *before* the worker launches;
        # missing, tampered or oversized frames fail closed.
        private_env = receiver.worker_environment(os.environ) if receiver else None
        with subprocess.Popen(command, cwd=build.REPO, env=private_env) as worker:
            try:
                trace.require(worker.wait(timeout=300) == 0,
                              "app lifetime worker did not complete")
                times = process_times(worker)
            finally:
                journey.cleanup_process(worker)
        child_evidence = receiver.take() if receiver else None
    return times, trace.read_json(root / "private-app-handle.json"), child_evidence


def reduction(manifest, sysmon, events, volume_devices, session, app_witness, worker_witness, binary, *,
              no_cdp_profile=False, child_handle_evidence=None):
    # The independent child-handle bundle is never available in default N12.
    trace.require(no_cdp_profile or child_handle_evidence is None,
                  "child-handle-shadow-only-in-no-cdp-profile")
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
    stop_images = {}
    handle_order = {}
    child_order = []
    shadow_review = {"scope": "no-cdp-original-handle-witness-design-only",
                     "status": "NOT_EVALUATED",
                     "native_N12_acceptance": "NOT_EVALUATED"} if no_cdp_profile else None
    child_join = {"scope": "no-cdp-private-child-handle-reducer-diagnostic-only",
                  "status": "NOT_EVALUATED", "native_N12_acceptance": "NOT_EVALUATED"} if no_cdp_profile else None
    # Redacted source-comparison diagnostics only. These cannot grant a PASS,
    # override coverage issues or silently waive an unavailable ETW pair.
    sysmon_reasons = {"status": "NOT_EVALUATED",
                      "reason": "lifetime-source-or-coverage-unverified"} if no_cdp_profile else None
    lifetimes = None
    if bindings and not issues & corroboration.SOURCE_COVERAGE_ISSUES:
        app = bindings[0][1]
        worker = processes.get(app.parent)
        try:
            trace.require(app.sha256 == manifest["executable_sha256"], "app-sysmon-executable-hash-unverified")
            trace.require(worker is not None and worker.pid == worker_witness["pid"]
                          and worker.image == trace.windows_path(sys.executable),
                          "launcher-sysmon-identity-unverified")
            with trace.evidence_stage("app lifetime ETW payload"):
                lifetimes = corroboration.EtwLifetimes(
                    stream, devices, window,
                    no_cdp_sysmon_corroboration=no_cdp_profile,
                )
            # Record each scoped comparison before the strict join stops at the first failure.
            by_role = {"launcher": Counter({lifetimes.start_image_comparison(worker): 1})}
            for guid, process in scoped.items():
                by_role.setdefault(roles[guid], Counter())[lifetimes.start_image_comparison(process)] += 1
            start_images = {role: dict(sorted(counts.items())) for role, counts in sorted(by_role.items())}
            stop_by_role = {"launcher": Counter({lifetimes.stop_image_comparison(worker): 1})}
            for guid, process in scoped.items():
                stop_by_role.setdefault(roles[guid], Counter())[lifetimes.stop_image_comparison(process)] += 1
            stop_images = {role: dict(sorted(counts.items())) for role, counts in sorted(stop_by_role.items())}
            handle_order = {
                "launcher": lifetimes.order_comparison(worker, worker_witness),
                "app": lifetimes.order_comparison(app, app_witness),
            }
            child_order = [
                {"role": roles[guid], **lifetimes.order_comparison(process)}
                for guid, process in scoped.items() if guid != app.guid
            ]
            if no_cdp_profile:
                # Record before find() can fail on its FIRST disputed role.
                # No GUID, PID, raw path, image or absolute clock is serialized.
                child_totals = {}
                for role in sorted(set(roles.values()) - {"app"}):
                    receipts = [lifetimes.no_cdp_sysmon_diagnostic(process)
                                for guid, process in scoped.items() if roles[guid] == role]
                    failed_counts = Counter(label for row in receipts for label in row["failed_checks"])
                    child_totals[role] = {
                        "count": len(receipts),
                        "checks_match_count": sum(row["status"] == "CHECKS_MATCH" for row in receipts),
                        "failed_checks": dict(sorted(failed_counts.items())),
                    }
                sysmon_reasons = {
                    "scope": "no-cdp-independent-sysmon-diagnostic-only",
                    "launcher": lifetimes.no_cdp_sysmon_diagnostic(worker, handle_witness=worker_witness),
                    "app": lifetimes.no_cdp_sysmon_diagnostic(app, handle_witness=app_witness),
                    "children_by_role": child_totals,
                    "native_N12_acceptance": "NOT_EVALUATED",
                }
            if no_cdp_profile:
                # Shadow design only. No output from this review is ever fed
                # into the original find() gate, marker gate, or acceptance.
                shadow_children = {}
                for role in sorted(set(roles.values()) - {"app"}):
                    reviews = [
                        lifetimes.shadow_handle_exit_review(
                            process, parent=processes.get(process.parent), require_parent=True)
                        for guid, process in scoped.items() if roles[guid] == role
                    ]
                    shadow_children[role] = {
                        "count": len(reviews),
                        "retained_handle_witness_count": sum(
                            row["status"] == "REVIEWABLE_ONLY" for row in reviews),
                        "failed_checks": dict(sorted(Counter(
                            label for row in reviews for label in row["failed_checks"]).items())),
                    }
                shadow_review = {
                    "scope": "no-cdp-original-handle-witness-design-only",
                    "launcher": lifetimes.shadow_handle_exit_review(worker, witness=worker_witness),
                    "app": lifetimes.shadow_handle_exit_review(
                        app, witness=app_witness, parent=worker, require_parent=True),
                    "children_by_role": shadow_children,
                    "native_N12_acceptance": "NOT_EVALUATED",
                }
            if no_cdp_profile:
                # This diagnostic consumes only PRIVATE in-memory handle evidence.
                # It must be measured before the first strict find() failure.
                # It is NEVER used as a native acceptance or profile witness.
                child_join = child_handles.private_child_handle_diagnostic(
                    evidence=child_handle_evidence, manifest=manifest,
                    processes=processes, roles=roles, app_guid=app.guid,
                    app_witness=app_witness, lifetimes=lifetimes,
                    source_issues=set(issues),
                    capture_start=window[0], capture_end=window[1],
                )
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
    no_cdp_receipt = None
    if no_cdp_profile:
        no_cdp_receipt = {"scope": "no-cdp-os-profile-lifetime-only",
                          "status": "BLOCKED", "native_N12_acceptance": "NOT_EVALUATED",
                          "file_event_coverage": "NOT_EVALUATED",
                          "network_isolation": "NOT_EVALUATED"}
        try:
            trace.require(not issues and lifetimes is not None and len(bindings) == 1,
                          "no-cdp-prior-lifetime-evidence-unverified")
            marks = manifest.get("markers")
            trace.require(type(marks) is dict and all(
                type(marks.get(label)) is str
                for label in ("launch", "ready", "close", "profile-exit")),
                "no-cdp-os-stage-markers-unverified")
            times = [trace.utc_time(marks[label]) for label in
                     ("launch", "ready", "close", "profile-exit")]
            trace.require(start < times[0] < times[1] < times[2] < times[3] < end,
                          "no-cdp-os-stage-order-unverified")
            # Source and Sysmon capture must be complete before the reviewer
            # derives this Boolean; it is never supplied by the QA operator.
            trace.require(all(session["counters"][k] == 0 for k in etw.COUNTERS[:-1])
                          and session["counters"]["buffers_written"] > 0,
                          "no-cdp-os-etw-loss-unverified")
            verified = browser_identity.verify_profile_shutdown(
                processes=processes, roles=roles, app_guid=bindings[0][1].guid,
                expected_app_image=str(binary),
                expected_app_sha256=manifest["executable_sha256"],
                disposable_profile=manifest["observed_roots"]["qa-webview"],
                launch=times[0], ready=times[1], close=times[2],
                profile_exit=times[3], capture_end=end,
                app_handle_witness=app_witness, etw_lifetimes=lifetimes,
                capture_loss_reviewed=True, capture_issues=set(issues),
            )
            no_cdp_receipt = {**verified.redacted_receipt(), "status": "SOURCE_OS_CORROBORATED"}
        except (trace.EvidenceValidationError, KeyError, ValueError, TypeError) as exc:
            reason = str(exc) if isinstance(exc, trace.EvidenceValidationError) else "no-cdp-os-evidence-invalid"
            issues.add(reason)
            no_cdp_receipt["reason"] = reason
    return {"scope": "one-native-startup-and-graceful-close", "source_sha": manifest["source_sha"],
            "executable_sha256": manifest["executable_sha256"],
            "verdict": "BLOCKED" if issues else "PASS", "issues": sorted(issues),
            "app_roles": dict(sorted(counts.items())), "etw_start_image_comparisons": start_images,
            "etw_stop_image_comparisons": stop_images, "handle_comparison": witnesses, "etw_handle_order_comparison": handle_order,
            "etw_child_order_comparisons": child_order,
            "collector_counters": session["counters"], "timing_comparisons": timing,
            "disputed_exits": disputed,
            **({"no_cdp_profile_identity": no_cdp_receipt,
                "no_cdp_sysmon_diagnostic": sysmon_reasons,
                "no_cdp_shadow_handle_witness_review": shadow_review,
                "no_cdp_private_child_handle_diagnostic": child_join} if no_cdp_profile else {}),
            "native_N12_acceptance": "NOT_EVALUATED"}


def endpoint_evidence(manifest, before):
    source, expected_hash = manifest["source_sha"], manifest["executable_sha256"]
    with journey.checkpoint_stage("app-lifetime-endpoints", source, expected_hash):
        snapshot, issues = trace.compare_snapshots(before, journey.snapshots(manifest), manifest)
        print("N12 app lifetime endpoints " + json.dumps({
            "source_sha": source, "executable_sha256": expected_hash, **snapshot,
        }), flush=True)
        return snapshot, issues


def capture(root, staged, provenance, *, no_cdp=False, fileio=False):
    # The full app and FileIO path is dormant without a NEW one-use approval.
    if fileio:
        trace.require(no_cdp is True
                      and os.environ.get("PILOTODIN_N12_NO_CDP_FILEIO_CONSENT") == FILEIO_CONSENT
                      and os.environ.get("PILOTODIN_N12_NO_CDP_STORAGE_CONSENT")
                      == no_cdp_path.lifecycle.NATIVE_ACK_CONSENT
                      and os.environ.get("PILOTODIN_N12_APP_LIFETIME_CONSENT") == CONSENT
                      and os.environ.get("GITHUB_ACTIONS") == "true"
                      and os.environ.get("RUNNER_ENVIRONMENT") == "github-hosted"
                      and os.environ.get("RUNNER_OS") == "Windows"
                      and os.environ.get("GITHUB_RUN_ATTEMPT") == "1"
                      and os.environ.get("PILOTODIN_N12_APPROVED_SOURCE") == provenance.get("source_sha"),
                      "no-cdp-fileio-new-one-use-approval-required")
    source, expected_hash = provenance["source_sha"], provenance["executable_sha256"]
    manifest, _, _, fixture, _ = journey.prepare_journey(root, source, expected_hash)
    fixture.write_text("fixture,value\nstartup-close,1\n", encoding="utf-8")
    # Keep ordinary process-only lifetime snapshots unchanged. Full FileIO
    # places BOTH complete snapshots under the same live Kernel-File session.
    before = None if fileio else journey.snapshots(manifest)
    after = None
    volume_devices = n12_etw_probe.volume_devices()
    with journey.checkpoint_stage("app-lifetime-window-open", source, expected_hash):
        manifest["sysmon_first_record"] = journey.sysmon_tail() + 1
    try:
        collector = etw.fileio_process_session if fileio else etw.process_session
        with collector(root, source, expected_hash) as session:
            manifest["start_utc"] = journey.now().isoformat()
            if fileio:
                journey.mark(manifest, "snapshot-before-start")
                before = journey.snapshots(manifest)
                journey.mark(manifest, "snapshot-before-end")
            time.sleep(journey.INITIAL_FIXTURE_LEAD_IN_SECONDS)
            with journey.checkpoint_stage("app-lifetime-worker", source, expected_hash):
                worker, app, private_children = launch_worker(
                    root, source, expected_hash, no_cdp=no_cdp)
                if no_cdp:
                    child = trace.read_json(root / "no-cdp-private-stage.json")
                    trace.require(child.get("source_sha") == source
                                  and child.get("executable_sha256") == expected_hash
                                  and type(child.get("markers")) is dict,
                                  "no-cdp-child-stage-provenance-unverified")
                    if fileio:
                        manifest["markers"].update(child["markers"])
                    else:
                        manifest["markers"] = child["markers"]
            if fileio:
                journey.mark(manifest, "snapshot-after-start")
                after = journey.snapshots(manifest)
                journey.mark(manifest, "snapshot-after-end")
                manifest["end_utc"] = journey.now().isoformat()
    except Exception:
        try:
            if before is not None:
                endpoint_evidence(manifest, before)
        except Exception:
            pass  # Preserve the startup or capture failure.
        raise
    if fileio:
        journey.snapshot_capture_evidence(
            manifest, journey.timestamp_from_ticks(session["start"]),
            journey.timestamp_from_ticks(session["end"]))
        snapshot, snapshot_issues = trace.compare_snapshots(before, after, manifest)
    else:
        manifest["end_utc"] = journey.timestamp_from_ticks(session["end"]).isoformat()
        snapshot, snapshot_issues = endpoint_evidence(manifest, before)
    sysmon = root / "lifetime-sysmon.xml"
    with journey.checkpoint_stage("app-lifetime-sysmon-export", source, expected_hash):
        time.sleep(3)
        manifest["sysmon_last_record"] = journey.sysmon_tail()
        journey.export_sysmon(manifest["sysmon_first_record"], manifest["sysmon_last_record"], sysmon)
    with journey.checkpoint_stage("app-lifetime-etw-export", source, expected_hash):
        journey.powershell(
            journey.HELPER, "etw-export" if fileio else "etw-app-lifetime-export",
            "-CaptureRoot", root, timeout=600 if fileio else 90)
    with journey.checkpoint_stage("app-lifetime-reduction", source, expected_hash):
        events = root / ("etw.jsonl" if fileio else "lifetime-etw.jsonl")
        manifest["events_sha256"] = build.digest(events)
        if fileio:
            manifest["etw"] = {
                "schema_version": 1,
                "start_utc": journey.timestamp_from_ticks(session["start"]).isoformat(),
                "end_utc": journey.timestamp_from_ticks(session["end"]).isoformat(),
                "counters": session["counters"], "volume_devices": volume_devices,
                "events_sha256": manifest["events_sha256"],
            }
        report = reduction(manifest, sysmon, events, volume_devices, session, app, worker,
                           build.executable(staged), no_cdp_profile=no_cdp,
                           child_handle_evidence=private_children)
        if fileio:
            # Same digest-verified ETW export, original strict FileIO reducer.
            # Retain every prohibited and unclassified operation. Diagnostic
            # status never promotes lifecycle PASS to N12 filesystem acceptance.
            report["no_cdp_fileio"] = fileio_review.reduce(
                manifest, sysmon, events, app, build.executable(staged),
                lifetime_report=report, snapshot=snapshot)
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
    parser.add_argument("--no-cdp", action="store_true",
                        help="Separately consent-gated, no-debugger lifecycle only; NOT FileIO acceptance")
    parser.add_argument("--fileio", action="store_true",
                        help="No-CDP only, new one-use approval, full FileIO diagnostic NOT N12 acceptance")
    args = parser.parse_args()
    try:
        trace.require(not args.fileio or args.no_cdp, "no-cdp-fileio-requires-no-cdp")
        if args.fileio:
            trace.require(os.environ.get("PILOTODIN_N12_NO_CDP_FILEIO_CONSENT") == FILEIO_CONSENT,
                          "no-cdp-fileio-new-one-use-approval-required")
        if args.no_cdp:
            trace.require(
                os.environ.get("PILOTODIN_N12_NO_CDP_STORAGE_CONSENT")
                == no_cdp_path.lifecycle.NATIVE_ACK_CONSENT
                and os.environ.get("PILOTODIN_N12_APP_LIFETIME_CONSENT") == CONSENT
                and os.environ.get("GITHUB_ACTIONS") == "true"
                and os.environ.get("RUNNER_ENVIRONMENT") == "github-hosted"
                and os.environ.get("RUNNER_OS") == "Windows"
                and os.environ.get("GITHUB_RUN_ATTEMPT") == "1"
                and os.environ.get("PILOTODIN_N12_APPROVED_SOURCE") == args.source,
                "no-cdp-separately-approved-native-run-required",
            )
        with journey.checkpoint_stage("app-lifetime-preflight", args.source, args.expected_exe_sha256):
            root, staged, provenance, node = preflight(args.source, args.expected_exe_sha256)
        if args.worker:
            launch_and_close(root, staged, node, args.source, args.expected_exe_sha256,
                             no_cdp=args.no_cdp)
            return 0
        print("N12 app lifetime provenance " + json.dumps({
            key: provenance[key] for key in ("source_sha", "executable_sha256", "cargo_lock_sha256")
        }), flush=True)
        return 0 if capture(root, staged, provenance, no_cdp=args.no_cdp,
                            fileio=args.fileio)["verdict"] == "PASS" else 2
    except trace.EvidenceValidationError as exc:
        print(f"N12 app lifetime blocked: {exc}.", file=sys.stderr)
    except (KeyError, OSError, RuntimeError, ValueError, subprocess.SubprocessError) as exc:
        print(f"N12 app lifetime blocked: {type(exc).__name__}.", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
