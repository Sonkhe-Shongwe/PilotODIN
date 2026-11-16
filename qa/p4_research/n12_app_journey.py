"""Capture two launches of one approved, already-staged PilotODIN Windows build."""
import argparse
from collections import Counter
from contextlib import ExitStack
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import time
from urllib.error import URLError
from urllib.request import ProxyHandler, build_opener
from uuid import uuid4

from qa.p4_native import n12_etw_probe as etw
from qa.p4_native import n12_trace as trace
from qa.p4_research import n12_app_build as build
from qa.p4_research.n12_journey_diagnostics import OutsidePaths, network_summary


NATIVE = build.REPO / "qa" / "p4_native"
FRONTEND = build.REPO / "frontend"
HELPER = Path(__file__).with_name("Invoke_N12_Journey_Evidence.ps1")
PROBE = FRONTEND / "e2e" / "p4-71-native-webview-qa.mjs"
PORTS = (5173, 8000, 9331)
HTTP = build_opener(ProxyHandler({}))
CAPTURE_CONSENT = "I_APPROVE_ONE_N12_APP_JOURNEY"
DRIVER_TEMP_DIR = "driver-temp"
INITIAL_FIXTURE_LEAD_IN_SECONDS = 0.05
INITIAL_SYSMON_RETRYABLE = {
    "channel-window-empty", "parent-birth-missing", "child-birth-missing",
    "process-exit-missing", "child-loopback-tcp-or-udp-missing",
}


def timestamp_from_ticks(ticks):
    return datetime(1, 1, 1, tzinfo=timezone.utc) + timedelta(microseconds=ticks // 10)


def now():
    return timestamp_from_ticks(etw.utc_ticks())


def mark(manifest, label):
    manifest["markers"][label] = now().isoformat()


def report_file(path, value):
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, indent=2)


def quiet(command, *, timeout=30, cwd=build.REPO, env=None):
    return subprocess.run(command, check=True, timeout=timeout, cwd=cwd, env=env,
                          stdout=subprocess.PIPE, stderr=subprocess.DEVNULL).stdout


def powershell(*args, timeout=30):
    return quiet(["pwsh", "-NoProfile", "-NonInteractive", "-File", *map(str, args)], timeout=timeout)


def sysmon_tail(*, timeout=30):
    return int(powershell(HELPER, "sysmon-tail", timeout=timeout))


def export_sysmon(first, last, path, *, timeout=180):
    trace.require(1 <= first <= last, "invalid Sysmon record window")
    powershell(NATIVE / "Export_P4_N12_Sysmon_Trace.ps1", first, last, path, timeout=timeout)


def snapshots(manifest):
    return {group: {label: trace.fingerprint(Path(path)) for label, path in manifest[f"{group}_roots"].items()}
            for group in ("protected", "observed")}


def start_capture(root, session, logman):
    providers = root / "providers.txt"
    providers.write_text(
        "Microsoft-Windows-Kernel-File 0x1ff0 4\nMicrosoft-Windows-Kernel-Process 0x30 4\n",
        encoding="ascii",
    )
    quiet([logman, "create", "trace", session, "-pf", str(providers), "-o", str(root / "journey.etl"),
           "-max", "512", "-bs", "64", "-nb", "16", "128", "-ets"])


def cleanup_process(process):
    if process.poll() is None:
        process.kill()
        process.wait(timeout=15)


def spawn(stack, manifest, role, command, env, cwd, log):
    with log.open("xb") as stream:
        process = subprocess.Popen(command, cwd=cwd, env=env, stdout=stream, stderr=subprocess.STDOUT)
    stack.callback(cleanup_process, process)
    manifest["processes"].append({"role": role, "pid": process.pid, "image": str(command[0])})
    return process


def http_ready(port, route, check=None):
    try:
        with HTTP.open(f"http://127.0.0.1:{port}{route}", timeout=1) as response:
            return response.status == 200 and (check is None or check(json.load(response)))
    except (URLError, OSError, ValueError):
        return False


def listening(port):
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=0.5):
            return True
    except OSError:
        return False


def wait_for(check, seconds, message, process=None):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        trace.require(process is None or process.poll() is None, message)
        if check():
            return
        time.sleep(0.5)
    raise trace.EvidenceValidationError(message)


def calibrate(directory, manifest):
    data = quiet([sys.executable, "-B", str(NATIVE / "n12_calibration.py"), str(directory)])
    record = json.loads(data)
    manifest["processes"].append(record)
    manifest["loopback_ports"].append(record["port"])
    return record


def initial_sysmon_issues(path, first, last, start, end, record, *, precision=False):
    # An outside-window birth explains a rejection. It never enters the process map.
    image = trace.windows_path(record["image"])
    outside = set()
    outside_ticks = []
    outside_connections = []
    unparsed_outside_connections = 0

    def outside_birth(stamp, fields, record_id):
        if (fields.get("ProcessId") == str(record["pid"])
                and trace.sysmon_image(fields.get("Image"), 1, record_id) == image):
            outside.add("parent-birth-before-window" if stamp < start else "parent-birth-after-window")
            outside_ticks.append(trace.utc_ticks(stamp))

    def outside_connection(stamp, fields):
        nonlocal unparsed_outside_connections
        try:
            connection = trace.sysmon_connection(stamp, fields)
        except (KeyError, ValueError, AttributeError):
            # Out-of-window evidence stays diagnostic, even when malformed.
            unparsed_outside_connections += 1
            return
        outside_connections.append(connection)

    with trace.evidence_stage("initial Sysmon XML"):
        processes, connections, issues, actual_first, actual_last = trace.sysmon_events(
            path, start, end, outside_birth=outside_birth,
            outside_connection=outside_connection,
            precision_fixture=record if precision else None,
        )
    trace.require((first, last) == (actual_first, actual_last), "initial Sysmon record boundaries differ")
    if outside_ticks:
        start_ticks, end_ticks = trace.utc_ticks(start), trace.utc_ticks(end)
        created = record.get("parent_created_utc_ticks")
        available = type(created) is int and created > 0
        reference = created if available else start_ticks
        nearest = min(outside_ticks, key=lambda ticks: (abs(ticks - reference), ticks))
        same_millisecond = (sum(ticks // 10_000 == created // 10_000 for ticks in outside_ticks)
                            if available else None)
        print("N12 initial Sysmon calibration birth diagnostics: " + json.dumps({
            "outside_candidate_count": len(outside_ticks),
            "nearest_event_minus_start_ticks": nearest - start_ticks,
            "nearest_event_minus_end_ticks": nearest - end_ticks,
            "creation_minus_start_ticks": created - start_ticks if available else None,
            "nearest_event_minus_creation_ticks": nearest - created if available else None,
            "same_creation_millisecond_count": same_millisecond,
        }), flush=True)
    candidates = [process for process in processes.values() if process.pid == record["pid"]]
    matching = [process for process in candidates if process.image == image]
    if len(matching) > 1:
        return issues | {"parent-birth-ambiguous"}
    if not matching:
        if candidates:
            issues.add("parent-image-mismatch")
        elif not outside:
            issues.add("parent-birth-missing")
        return issues | outside

    roles, bindings = trace.bind_processes([record], processes, issues)
    parent = bindings[0][1]
    children = [process for process in processes.values() if process.parent == parent.guid]
    if not children:
        return issues | {"child-birth-missing"}
    if len(children) != 1 or children[0].pid != record["child_pid"]:
        return issues | {"child-identity-mismatch"}
    child = children[0]
    if not parent.sha256 or child.sha256 != parent.sha256 or child.image != parent.image:
        issues.add("child-image-or-hash-mismatch")
    if parent.end and child.end:
        if not parent.start <= child.start <= child.end <= parent.end:
            issues.add("fixture-lifetime-inconsistent")
        protocols = {connection.protocol for connection in connections
                     if connection.guid == child.guid and connection.initiated
                     and child.start <= connection.timestamp <= child.end
                     and connection.address.is_loopback and connection.port == record["port"]}
        if protocols != {"tcp", "udp"}:
            issues.add("child-loopback-tcp-or-udp-missing")
            counts = {protocol: Counter() for protocol in ("tcp", "udp")}
            rejected = {protocol: Counter() for protocol in ("tcp", "udp")}
            udp_at_fixture = Counter()
            udp_sender_port = record.get("udp_sender_port")
            for connection in (*connections, *outside_connections):
                if (connection.protocol == "udp" and connection.port == record["port"]
                        and connection.address.is_loopback and connection.guid != child.guid):
                    actor = "parent" if connection.guid == parent.guid else "other-process"
                    direction = "outbound" if connection.initiated else "inbound"
                    if type(udp_sender_port) is not int or not 1 <= udp_sender_port <= 65535:
                        source = "sender-port-unavailable"
                    else:
                        source = ("fixture-sender-port" if connection.source_port == udp_sender_port
                                  else "different-source-port")
                    window = "in-window" if start <= connection.timestamp <= end else "outside-window"
                    udp_at_fixture[f"{actor}:{direction}:{source}:{window}"] += 1
                if connection.guid != child.guid:
                    label = ("other-process-at-fixture-port" if connection.port == record["port"]
                             else "other-process")
                elif not connection.initiated:
                    label = "not-initiated"
                elif not connection.address.is_loopback:
                    label = "non-loopback-destination"
                elif connection.port != record["port"]:
                    label = "wrong-destination-port"
                else:
                    if not start <= connection.timestamp <= end:
                        label = "outside-read-window"
                    elif connection.timestamp < child.start:
                        label = "before-child-birth"
                    elif connection.timestamp > child.end:
                        label = "after-child-exit"
                    else:
                        label = "in-child-lifetime"
                    counts[connection.protocol][label] += 1
                    continue
                rejected[connection.protocol][label] += 1
            print("N12 initial Sysmon calibration protocol diagnostics: " + json.dumps({
                "missing_in_child_lifetime": sorted({"tcp", "udp"} - protocols),
                "matching_markers": counts,
                "rejected_records": rejected,
                "unparsed_outside_window": unparsed_outside_connections,
                "udp_other_at_fixture_port": udp_at_fixture,
            }), flush=True)
    trace.verify_connection_lifetimes(connections, processes, roles, issues)
    _, unexpected, _ = trace.scoped_network(connections, roles, {record["port"]})
    if unexpected:
        issues.add("calibration-unexpected-connection")
    if parent.fixture_birth_adjusted and not issues:
        print("N12 initial Sysmon calibration matched fixture birth at Windows creation time", flush=True)
    return issues


def verify_initial_sysmon(root, manifest, record):
    # Give pending channel writes one more chance. The fixture and event window stay fixed.
    start, end = trace.utc_time(manifest["start_utc"]), now()
    first = manifest["sysmon_first_record"]
    previous_last = first - 1
    for attempt in (1, 2):
        time.sleep(3)
        try:
            last = sysmon_tail(timeout=15)
            trace.require(last >= previous_last, "initial Sysmon channel record ID regressed")
            previous_last = last
            issues = {"channel-window-empty"}
            if last >= first:
                path = root / f"initial-sysmon-{attempt}.xml"
                export_sysmon(first, last, path, timeout=15)
                issues = initial_sysmon_issues(path, first, last, start, end, record,
                                               precision=manifest.get("collector_fixture_precision") is True)
        except subprocess.SubprocessError as exc:
            raise trace.EvidenceValidationError("initial Sysmon channel read or export failed") from exc
        if not issues:
            print(f"N12 initial Sysmon calibration passed on read {attempt}", flush=True)
            return last
        reason = ", ".join(sorted(issues))
        if attempt == 2 or not issues <= INITIAL_SYSMON_RETRYABLE:
            raise trace.EvidenceValidationError(f"initial Sysmon calibration blocked on read {attempt}: {reason}")
        print("N12 initial Sysmon calibration waiting for channel evidence: " + reason, flush=True)


def run_driver(stack, manifest, node, root, env, relaunch):
    command = [node, str(PROBE)]
    label = "relaunch" if relaunch else "first"
    if relaunch:
        command.append("--verify-relaunch")
    # Playwright creates CDP scratch files under Node's OS temp directory.
    driver_temp = str(root / DRIVER_TEMP_DIR)
    driver_env = {**env, "TEMP": driver_temp, "TMP": driver_temp}
    process = spawn(stack, manifest, "driver", command, driver_env, FRONTEND, root / f"driver-{label}.log")
    trace.require(process.wait(timeout=240) == 0, f"{label} native interaction probe failed")


def run_apps(stack, manifest, root, staged, source, expected_hash, node, env, profile, backend, vite):
    binary = build.executable(staged)
    title = json.loads(build.isolated_config())["app"]["windows"][0]["title"]
    first_pid = None
    for relaunch in (False, True):
        label = "relaunch" if relaunch else "first"
        trace.require(backend.poll() is None and vite.poll() is None, "loopback service exited during journey")
        print(f"N12 journey stage {label} launch", flush=True)
        build.verify(staged, source, expected_hash)
        mark(manifest, "reopen" if relaunch else "launch")
        app_env = {**env, "WEBVIEW2_USER_DATA_FOLDER": str(profile),
                   "WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS":
                       '--remote-debugging-port=9331 --net-log-capture-mode=Default '
                       f'--log-net-log="{profile / f"netlog-{label}.json"}"'}
        app = spawn(stack, manifest, "app", [binary], app_env, binary.parent, root / f"app-{label}.log")
        trace.require(app.pid != first_pid, "relaunch must have a distinct app PID")
        first_pid = app.pid
        wait_for(lambda: http_ready(9331, "/json/version", lambda status: bool(status.get("webSocketDebuggerUrl"))),
                 45, f"{label} WebView debugger did not become ready", app)
        if not relaunch:
            mark(manifest, "quality")
        run_driver(stack, manifest, node, root, {**env, "P4_NATIVE_QA_APP_PID": str(app.pid)}, relaunch)
        mark(manifest, "exit" if relaunch else "close")
        powershell(HELPER, "close", "-AppProcessId", app.pid, "-AppPath", binary, "-AppTitle", title)
        trace.require(app.wait(timeout=5) == 0, "app did not exit normally")
        wait_for(lambda: not listening(9331) and int(powershell(
            HELPER, "profile-active", "-ProfilePath", profile, timeout=10,
        )) == 0, 25, "WebView processes did not exit for the disposable profile")


def prepare_journey(root, source, expected_hash):
    protected = {
        f"{location}-{label}": str(trace.local_disposable_path(Path(os.environ[variable]) / identifier))
        for location, variable in (("local", "LOCALAPPDATA"), ("roaming", "APPDATA"))
        for label, identifier in zip(("original", "old-qa"), build.PROTECTED_IDS)
    }
    trace.require(not any(os.path.lexists(path) for path in protected.values()),
                  "a protected application directory already exists")
    qa_roots = [trace.local_disposable_path(Path(os.environ[key]) / build.QA_ID)
                for key in ("LOCALAPPDATA", "APPDATA")]
    trace.require(not any(os.path.lexists(path) for path in qa_roots), "the isolated QA identity already exists")
    home = root / f'P4-71-only-home-{os.environ["GITHUB_RUN_ID"]}'
    profile = root / "webview"
    source_fixture = root / "quality-source.csv"
    calibration = [root / name for name in ("calibration-first", "calibration-last")]
    manifest = {
        "schema_version": 1, "disposable": True, "source_sha": source, "executable_sha256": expected_hash,
        "markers": {}, "processes": [], "loopback_ports": list(PORTS), "protected_roots": protected,
        "observed_roots": {"quality-source": str(source_fixture), "qa-home": str(home),
                           "qa-webview": str(profile), "qa-local": str(qa_roots[0]),
                           "qa-roaming": str(qa_roots[1])},
        "immutable_observed": ["quality-source"],
        "permitted_writes": {"app": [*map(str, qa_roots), str(profile)],
                             "webview": [str(profile)], "webview-network": [str(profile)],
                             "helper": [str(profile)], "backend": [str(home)],
                             "driver": [str(home), str(FRONTEND / "node_modules" / ".vite"),
                                        str(root / DRIVER_TEMP_DIR)],
                             "calibration": list(map(str, calibration))},
    }
    trace.scope(manifest)
    root.mkdir(exist_ok=False)
    home.mkdir()
    profile.mkdir()
    (root / DRIVER_TEMP_DIR).mkdir()
    return manifest, home, profile, source_fixture, calibration


def diagnostic_paths(root, staged, manifest):
    roots = [
        ("qa-home", manifest["observed_roots"]["qa-home"]),
        ("qa-webview-profile", manifest["observed_roots"]["qa-webview"]),
        ("qa-local-profile", manifest["observed_roots"]["qa-local"]),
        ("qa-roaming-profile", manifest["observed_roots"]["qa-roaming"]),
        ("qa-driver-temp", root / DRIVER_TEMP_DIR),
        ("frontend-vite-cache", FRONTEND / "node_modules" / ".vite"),
        ("frontend-dependencies", FRONTEND / "node_modules"),
        ("source-checkout", build.REPO),
        ("staged-build", staged),
        ("capture-workspace", root),
    ]
    roots.extend((label, os.environ[key]) for label, key in (
        ("runner-temp", "RUNNER_TEMP"), ("user-temp", "TEMP"), ("user-local", "LOCALAPPDATA"),
        ("user-roaming", "APPDATA"), ("windows-system", "SystemRoot"),
    ) if os.environ.get(key))
    return OutsidePaths(roots)


def process_bookend():
    try:
        entries = json.loads(powershell(HELPER, "process-bookend"))
        # Validate the snapshot before passing it to the audit. One bad
        # snapshot leaves the original audit available without bookend data.
        trace.require(isinstance(entries, list) and entries, "process bookend is empty")
        trace.stable_process_bookend_records({"before": entries, "after": []}, 0, set())
        return entries
    except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError):
        return None


def capture(root, staged, source, expected_hash, node):
    manifest, home, profile, fixture, calibration = prepare_journey(root, source, expected_hash)
    env = {**os.environ, "CI": "true", "PILOTODIN_HOME": str(home), "PYTHONDONTWRITEBYTECODE": "1",
           "VITE_PILOTODIN_NATIVE_SMOKE": "1", "PILOTODIN_N12_QUALITY_FIXTURE": str(fixture)}
    require_fixture = (
        "import {p4QualityFixture} from './e2e/p4-quality-version-transition.mjs';"
        "process.stdout.write(p4QualityFixture);"
    )
    fixture_bytes = quiet([node, "--input-type=module", "-e", require_fixture], cwd=FRONTEND)
    trace.require(bool(fixture_bytes), "the generated Quality fixture is empty")
    with fixture.open("xb") as stream:
        stream.write(fixture_bytes)
    before = snapshots(manifest)
    report_file(root / "before.json", before)
    devices = etw.volume_devices()
    session = f"PilotODIN-N12-App-{uuid4().hex}"
    logman = str(Path(os.environ["SystemRoot"]) / "System32" / "logman.exe")
    first_processes = process_bookend()
    manifest["sysmon_first_record"] = sysmon_tail() + 1
    capture_start = now()
    print("N12 journey stage collector start", flush=True)
    try:
        start_capture(root, session, logman)
    except subprocess.TimeoutExpired:
        # A timed-out start can still have registered this uniquely named session.
        quiet([logman, "stop", session, "-ets"])
        raise
    try:
        manifest["start_utc"] = now().isoformat()
        # Leave room for Sysmon's millisecond birth timestamp at the audit boundary.
        time.sleep(INITIAL_FIXTURE_LEAD_IN_SECONDS)
        print("N12 journey stage initial calibration", flush=True)
        record = calibrate(calibration[0], manifest)
        verify_initial_sysmon(root, manifest, record)
        mark(manifest, "idle")
        time.sleep(3)
        with ExitStack() as stack:
            backend = spawn(stack, manifest, "backend", [sys.executable, "-B", "-m", "uvicorn",
                "backend.main:app", "--host", "127.0.0.1", "--port", "8000", "--no-access-log"],
                env, build.REPO, root / "backend.log")
            vite = spawn(stack, manifest, "driver", [node, str(FRONTEND / "node_modules/vite/bin/vite.js"),
                "--host", "127.0.0.1", "--port", "5173", "--strictPort"], env, FRONTEND, root / "vite.log")
            wait_for(lambda: http_ready(8000, "/api/health", lambda status:
                                       status.get("status") == "ok" and status.get("cloud_ai") is False),
                     60, "loopback backend did not become ready with cloud AI off", backend)
            wait_for(lambda: http_ready(5173, "/"), 60, "Vite did not become ready", vite)
            run_apps(stack, manifest, root, staged, source, expected_hash, node, env, profile, backend, vite)
        print("N12 journey stage final calibration", flush=True)
        calibrate(calibration[1], manifest)
        manifest["end_utc"] = now().isoformat()
    finally:
        counters = etw.stop_trace(session)
        capture_end = now()
        # Preserve completed checkpoints on a failed journey, without claiming a full audit.
        report_file(root / "trace-checkpoint.json", {
            "manifest": manifest, "etw_start_utc": capture_start.isoformat(),
            "etw_end_utc": capture_end.isoformat(), "counters": counters, "volume_devices": devices,
        })
    print("N12 journey stage export and audit", flush=True)
    last_processes = process_bookend()
    bookends = ({"before": first_processes, "after": last_processes}
                if first_processes is not None and last_processes is not None else None)
    if bookends is not None:
        report_file(root / "private-process-bookends.json", bookends)
    time.sleep(3)
    with trace.evidence_stage("protected endpoint snapshot"):
        after = snapshots(manifest)
        report_file(root / "after.json", after)
        comparison, issues = trace.compare_snapshots(before, after, manifest)
    print("N12 protected endpoint snapshots " + json.dumps({
        "source_sha": source,
        "executable_sha256": expected_hash,
        **comparison,
        "snapshot_issues": sorted(issues),
    }), flush=True)
    manifest["sysmon_last_record"] = sysmon_tail()
    sysmon = root / "sysmon.xml"
    export_sysmon(manifest["sysmon_first_record"], manifest["sysmon_last_record"], sysmon)
    powershell(HELPER, "etw-export", "-CaptureRoot", root, timeout=600)
    events = root / "etw.jsonl"
    manifest["etw"] = {"schema_version": 1, "start_utc": capture_start.isoformat(),
                       "end_utc": capture_end.isoformat(), "counters": counters,
                       "volume_devices": devices, "events_sha256": build.digest(events)}
    report_file(root / "manifest.json", manifest)
    endpoints, launches = [], {}
    paths = diagnostic_paths(root, staged, manifest)
    rejected_sysmon_exits = []
    try:
        result = trace.audit(manifest, sysmon, events, before, after, etw=True, private_endpoints=endpoints,
                             record_outside_writer=paths.record, private_app_launches=launches,
                             journey_bookends=bookends, describe_path_gaps=True,
                             rejected_sysmon_exits=rejected_sysmon_exits)
    finally:
        if rejected_sysmon_exits:
            print("N12 rejected Sysmon exits " + json.dumps(rejected_sysmon_exits), flush=True)
    report_file(root / "private-endpoints.json", endpoints)
    log_paths = {label: profile / f"netlog-{label}.json" for label in ("first", "relaunch")}
    result["journey_diagnostics"] = {
        "outside_scope_paths": paths.summary(),
        "outside_scope_writers": paths.writer_summary(),
        "process_bookends": {"before": "available" if first_processes is not None else "unavailable",
                            "after": "available" if last_processes is not None else "unavailable"},
        "network": network_summary(endpoints, launches, log_paths),
    }
    result["journey"] = "completed"
    report_file(root / "audit.json", result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True)
    parser.add_argument("--expected-exe-sha256", required=True)
    args = parser.parse_args()
    try:
        staged = build.stage_root(args.source)
        trace.require(os.environ.get("PILOTODIN_N12_APP_JOURNEY_CONSENT") == CAPTURE_CONSENT,
                      "separate one-run N12 journey consent is required")
        trace.require(not any(value and (key.upper().startswith("WEBVIEW2_") or key.upper() in {
            "PILOTODIN_HOME", "PILOTODIN_DESKTOP_SESSION", "PILOTODIN_DESKTOP_TOKEN", "TAURI_CONFIG",
        }) for key, value in os.environ.items()), "inherited application configuration is present")
        build.verify(staged, args.source, args.expected_exe_sha256)
        trace.require(not any(map(listening, PORTS)), "a required loopback port is in use")
        node = shutil.which("node.exe")
        trace.require(node is not None, "Node is required for the existing native driver")
        with trace.evidence_stage("configured Sysmon preflight"):
            try:
                trace.require(sysmon_tail() >= 1, "invalid channel record ID")
            except subprocess.SubprocessError as exc:
                raise trace.EvidenceValidationError("enabled operational channel required") from exc
        root = trace.local_disposable_path(staged.with_name(f'{staged.name}-journey'), runner_temp_only=True)
        result = capture(root, staged, args.source, args.expected_exe_sha256, node)
        print(json.dumps(result))
        return 0 if result["network"] == result["filesystem"] == "PASS_SCOPED" else 2
    except trace.EvidenceValidationError as exc:
        print(f"N12 journey blocked: {exc}.", file=sys.stderr)
    except (KeyError, OSError, RuntimeError, ValueError, subprocess.SubprocessError) as exc:
        print(f"N12 journey blocked: {type(exc).__name__}. See private runner evidence.", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
