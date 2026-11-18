"""Capture two launches of one approved, already-staged PilotODIN Windows build."""
import argparse
from collections import Counter
from contextlib import ExitStack, contextmanager
from datetime import datetime, timedelta, timezone
from ipaddress import IPv4Address
import json
import ntpath
import os
from pathlib import Path
import re
import shutil
import socket
import subprocess
import sys
import time
from urllib.error import URLError
from urllib.request import ProxyHandler, build_opener
from uuid import uuid4

from qa.p4_native import n12_etw_probe as etw
from qa.p4_native.n12_exit_corroboration import journey_lifetime_evidence
from qa.p4_native import n12_trace as trace
from qa.p4_research import n12_app_build as build
from qa.p4_research.n12_journey_diagnostics import OutsidePaths, address, backend_self_connections, network_summary
from qa.p4_research.n12_driver_handles import DriverHandles, driver_lifetime_evidence


NATIVE = build.REPO / "qa" / "p4_native"
FRONTEND = build.REPO / "frontend"
HELPER = Path(__file__).with_name("Invoke_N12_Journey_Evidence.ps1")
PROBE = FRONTEND / "e2e" / "p4-71-native-webview-qa.mjs"
PORTS = (5173, 8000, 9331)
HTTP = build_opener(ProxyHandler({}))
CAPTURE_CONSENT = "I_APPROVE_ONE_N12_APP_JOURNEY"
DRIVER_TEMP_DIR = "driver-temp"
INITIAL_FIXTURE_LEAD_IN_SECONDS = 0.05
FINAL_FIXTURE_CHILD_HOLD_SECONDS = 4
FIXTURE_ADDRESS = IPv4Address("127.0.0.1")
FIXTURE_SYSMON_RETRYABLE = {
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


def checkpoint(stage, status, source, executable_sha256):
    row = {"stage": stage, "status": status}
    if re.fullmatch(r"[0-9a-f]{40}", source):
        row["source_sha"] = source
    if re.fullmatch(r"[0-9a-f]{64}", executable_sha256):
        row["executable_sha256"] = executable_sha256
    print("N12 checkpoint " + json.dumps(row), flush=True)


@contextmanager
def checkpoint_stage(stage, source, executable_sha256):
    try:
        yield
    except BaseException:
        checkpoint(stage, "interrupted", source, executable_sha256)
        raise
    else:
        checkpoint(stage, "completed", source, executable_sha256)


@contextmanager
def journey_processes(source, executable_sha256):
    stack = ExitStack()
    try:
        yield stack
    except BaseException:
        try:
            with checkpoint_stage("process-cleanup", source, executable_sha256):
                stack.close()
        except Exception:
            pass  # Keep the journey error as the primary failure.
        raise
    else:
        with checkpoint_stage("process-cleanup", source, executable_sha256):
            stack.close()


def stop_capture(root, session, manifest, capture_start, devices):
    with checkpoint_stage("etw-stop", manifest["source_sha"], manifest["executable_sha256"]):
        counters = etw.stop_trace(session)
        capture_end = now()
        report_file(root / "trace-checkpoint.json", {
            "manifest": manifest, "etw_start_utc": capture_start.isoformat(),
            "etw_end_utc": capture_end.isoformat(), "counters": counters, "volume_devices": devices,
        })
    return counters, capture_end


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


def calibrate(directory, manifest, *, child_hold_seconds=0):
    command = [sys.executable, "-B", str(NATIVE / "n12_calibration.py"), str(directory)]
    if child_hold_seconds:
        command.extend(("--child-hold-seconds", str(child_hold_seconds)))
    data = quiet(command)
    record = json.loads(data)
    manifest["processes"].append(record)
    manifest["loopback_ports"].append(record["port"])
    return record


def fixture_sysmon_issues(path, first, last, start, end, record, *, phase, precision=False):
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

    with trace.evidence_stage(f"{phase} Sysmon XML"):
        processes, connections, issues, actual_first, actual_last = trace.sysmon_events(
            path, start, end, outside_birth=outside_birth,
            outside_connection=outside_connection,
            precision_fixture=record if precision else None,
        )
    trace.require((first, last) == (actual_first, actual_last), f"{phase} Sysmon record boundaries differ")
    prefix = f"N12 {phase} Sysmon calibration"
    if outside_ticks:
        start_ticks, end_ticks = trace.utc_ticks(start), trace.utc_ticks(end)
        created = record.get("parent_created_utc_ticks")
        available = type(created) is int and created > 0
        reference = created if available else start_ticks
        nearest = min(outside_ticks, key=lambda ticks: (abs(ticks - reference), ticks))
        same_millisecond = (sum(ticks // 10_000 == created // 10_000 for ticks in outside_ticks)
                            if available else None)
        print(f"{prefix} birth diagnostics: " + json.dumps({
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
                     if connection.guid == child.guid and connection.pid == child.pid and connection.initiated
                     and child.start <= connection.timestamp <= child.end
                     and connection.address == FIXTURE_ADDRESS and connection.port == record["port"]}
        if protocols != {"tcp", "udp"}:
            issues.add("child-loopback-tcp-or-udp-missing")
            counts = {protocol: Counter() for protocol in ("tcp", "udp")}
            rejected = {protocol: Counter() for protocol in ("tcp", "udp")}
            udp_at_fixture = Counter()
            fixture_sockets = {protocol: Counter() for protocol in ("tcp", "udp")}
            sender_ports = {protocol: record.get(f"{protocol}_sender_port") for protocol in fixture_sockets}
            fixture_guids = {parent.guid: "parent", child.guid: "child"}
            fixture_pids = {parent.pid: "parent", child.pid: "child", 0: "zero", 4: "system"}
            udp_sender_port = sender_ports["udp"]
            for connection in (*connections, *outside_connections):
                source_port = sender_ports[connection.protocol]
                if (type(source_port) is int and 1 <= source_port <= 65535
                        and connection.source_port == source_port and connection.address == FIXTURE_ADDRESS
                        and connection.port == record["port"]):
                    guid_role = fixture_guids.get(connection.guid, "other")
                    pid_role = fixture_pids.get(connection.pid, "other")
                    direction = "outbound" if connection.initiated else "inbound"
                    if not start <= connection.timestamp <= end:
                        timing = "outside-window"
                    elif connection.timestamp < child.start:
                        timing = "before-child"
                    elif connection.timestamp > child.end:
                        timing = "after-child"
                    else:
                        timing = "in-child-lifetime"
                    fixture_sockets[connection.protocol][
                        f"guid-{guid_role}:pid-{pid_role}:{direction}:{timing}"
                    ] += 1
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
            print(f"{prefix} protocol diagnostics: " + json.dumps({
                "missing_in_child_lifetime": sorted({"tcp", "udp"} - protocols),
                "matching_markers": counts,
                "rejected_records": rejected,
                "unparsed_outside_window": unparsed_outside_connections,
                "udp_other_at_fixture_port": udp_at_fixture,
            }), flush=True)
            print(f"{prefix} socket identity diagnostics: " + json.dumps(
                fixture_sockets), flush=True)
    trace.verify_connection_lifetimes(connections, processes, roles, issues)
    allowed = trace.calibration_destinations(record, parent, processes)
    _, unexpected, _ = trace.scoped_network(connections, roles, allowed)
    if unexpected:
        issues.add("calibration-unexpected-connection")
    if parent.fixture_birth_adjusted and not issues:
        print(f"{prefix} matched fixture birth at Windows creation time", flush=True)
    return issues


def verify_fixture_sysmon(root, first, start, end, record, *, phase, precision=False):
    # Give pending channel writes one more chance. The fixture and event window stay fixed.
    previous_last = first - 1
    for attempt in (1, 2):
        time.sleep(3)
        try:
            with trace.evidence_stage(f"{phase} Sysmon channel"):
                last = sysmon_tail(timeout=15)
            trace.require(last >= previous_last, f"{phase} Sysmon channel record ID regressed")
            previous_last = last
            issues = {"channel-window-empty"}
            if last >= first:
                path = root / f"{phase}-sysmon-{attempt}.xml"
                with trace.evidence_stage(f"{phase} Sysmon export"):
                    export_sysmon(first, last, path, timeout=15)
                issues = fixture_sysmon_issues(path, first, last, start, end, record,
                                               phase=phase, precision=precision)
        except subprocess.SubprocessError as exc:
            raise trace.EvidenceValidationError(f"{phase} Sysmon channel read or export failed") from exc
        if not issues:
            print(f"N12 {phase} Sysmon calibration passed on read {attempt}", flush=True)
            return last
        reason = ", ".join(sorted(issues))
        if attempt == 2 or not issues <= FIXTURE_SYSMON_RETRYABLE:
            raise trace.EvidenceValidationError(f"{phase} Sysmon calibration blocked on read {attempt}: {reason}")
        print(f"N12 {phase} Sysmon calibration waiting for channel evidence: {reason}", flush=True)


def verify_initial_sysmon(root, manifest, record):
    return verify_fixture_sysmon(
        root, manifest["sysmon_first_record"], trace.utc_time(manifest["start_utc"]), now(), record,
        phase="initial", precision=manifest.get("collector_fixture_precision") is True,
    )


def request_graceful_close(app, binary, title):
    try:
        powershell(HELPER, "close", "-AppProcessId", app.pid,
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


def driver_environment(env, root):
    # Vite and Playwright are separate Node roots in the trace. Both inherit
    # only the existing, scoped QA scratch directory for temporary files.
    scratch = str(root / DRIVER_TEMP_DIR)
    return {**env, "TEMP": scratch, "TMP": scratch, "TMPDIR": scratch}


def driver_failure(log, label, return_code):
    checkpoint = "probe-start"
    failure = "unclassified"
    with log.open("rb") as stream:
        for raw in stream:
            line = raw.strip()
            if line == b"ACTUAL Tauri WebView2 reached, local URL only":
                checkpoint = "webview-connected"
            elif line == b"N12 native close listener ready":
                checkpoint = "close-listener-ready"
            elif line.endswith(b": PASS") and re.match(rb"^N(?:[1-9]|1[012]) ", line):
                checkpoint = line.split(b" ", 1)[0].decode("ascii")
            if line.startswith(b"NATIVE INTERACTIONS BLOCKED:"):
                failure = "webview-discovery-or-connection"
            elif line.startswith(b"NATIVE PROJECT SWITCH BLOCKED:"):
                failure = "native-project-switch"
            elif failure == "unclassified" and (b"TimeoutError:" in line or b"Timeout:" in line):
                failure = "interaction-timeout"
    return {"launch": label, "return_code": return_code, "last_checkpoint": checkpoint, "failure": failure}


def run_driver(stack, manifest, node, root, env, relaunch, handles):
    command = [node, str(PROBE)]
    label = "relaunch" if relaunch else "first"
    if relaunch:
        command.append("--verify-relaunch")
    log = root / f"driver-{label}.log"
    process = spawn(stack, manifest, "driver", command, driver_environment(env, root), FRONTEND, log)
    handles.watch(process, label)
    return_code = process.wait(timeout=240)
    if return_code != 0:
        print("N12 native driver failure " + json.dumps(driver_failure(log, label, return_code)), flush=True)
        raise trace.EvidenceValidationError(f"{label} native interaction probe failed")
    with log.open("rb") as stream:
        ready = any(line.rstrip(b"\r\n") == b"N12 native close listener ready" for line in stream)
    trace.require(ready, f"{label} native close listener was not verified")


def webview_child_handles(stack, app_pid):
    from qa.p4_native.n12_lifetime_control import open_process_query_handle, process_images

    try:
        rows = json.loads(powershell(HELPER, "webview-children", "-AppProcessId", app_pid, timeout=10))
        trace.require(isinstance(rows, list) and len(rows) <= 64, "invalid WebView child inventory")
        identities = {row["pid"]: row["birth_ticks"] for row in rows}
        trace.require(len(identities) == len(rows) and all(
            type(pid) is int and pid > 0 and pid != app_pid and type(birth) is int and birth > 0
            for pid, birth in identities.items()
        ), "invalid WebView child identity")
    except (KeyError, TypeError, ValueError, OSError, subprocess.SubprocessError):
        return []
    children = []
    for pid, birth in identities.items():
        try:
            child = stack.enter_context(open_process_query_handle(pid))
            images = process_images(child)
            trace.require(ntpath.basename(images["image_dos"]).casefold() == "msedgewebview2.exe",
                          "WebView child image changed")
        except (OSError, trace.EvidenceValidationError):
            continue
        children.append((child, birth, images))
    return children


def finish_webview_child_witnesses(children):
    from qa.p4_native.n12_lifetime_control import process_times

    witnesses = {}
    for child, observed_birth, images in children:
        try:
            times = process_times(child)
            # CIM exposes microseconds. The retained handle preserves all
            # 100 ns ticks for the later exact ETW join.
            trace.require(abs(times["birth"] - observed_birth) < 10, "WebView child birth changed")
        except (OSError, trace.EvidenceValidationError):
            continue
        witnesses[child.pid] = times | images
    return witnesses


def run_apps(stack, manifest, root, staged, source, expected_hash, node, env, profile, backend, vite, handles):
    from qa.p4_native.n12_lifetime_control import process_images, process_times

    binary = build.executable(staged)
    title = json.loads(build.isolated_config())["app"]["windows"][0]["title"]
    first_pid = None
    witnesses = {}
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
        run_driver(stack, manifest, node, root, {**env, "P4_NATIVE_QA_APP_PID": str(app.pid)}, relaunch, handles)
        with ExitStack() as child_stack:
            children = webview_child_handles(child_stack, app.pid)
            mark(manifest, "exit" if relaunch else "close")
            try:
                images = process_images(app)
            except (OSError, trace.EvidenceValidationError):
                images = None
            request_graceful_close(app, binary, title)
            trace.require(app.wait(timeout=5) == 0, "app did not exit normally")
            wait_for(lambda: not listening(9331) and int(powershell(
                HELPER, "profile-active", "-ProfilePath", profile, timeout=10,
            )) == 0, 25, "WebView processes did not exit for the disposable profile")
            try:
                witnesses[label] = process_times(app) | images if images is not None else None
            except (OSError, trace.EvidenceValidationError):
                witnesses[label] = None
            if witnesses[label] is not None:
                witnesses[label]["children"] = finish_webview_child_witnesses(children)
        checkpoint(label + "-launch-and-exit", "completed", source, expected_hash)
    return witnesses


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
        ("backend-stdout-log", root / "backend.log"),
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
        ("python-installation", Path(sys.base_prefix)),
    ]
    roots.extend((label, os.environ[key]) for label, key in (
        ("runner-temp", "RUNNER_TEMP"), ("user-temp", "TEMP"), ("user-local", "LOCALAPPDATA"),
        ("user-roaming", "APPDATA"), ("runner-tool-cache", "RUNNER_TOOL_CACHE"),
        ("shared-application-data", "ProgramData"), ("user-profile", "USERPROFILE"),
        ("windows-system", "SystemRoot"),
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


def backend_socket_snapshot(backend):
    try:
        snapshot = json.loads(powershell(HELPER, "backend-tcp", "-BackendProcessId", backend.pid, timeout=15))
        birth, observed = snapshot["birth_ticks"], snapshot["observed_ticks"]
        trace.require(type(snapshot["pid"]) is int and snapshot["pid"] == backend.pid
                      and type(birth) is int and type(observed) is int and 0 < birth <= observed,
                      "invalid backend socket snapshot identity")
        sockets = snapshot["sockets"]
        trace.require(isinstance(sockets, list), "invalid backend socket snapshot")
        for row in sockets:
            for end in ("local", "remote"):
                host, port = row[f"{end}_address"], row[f"{end}_port"]
                trace.require(isinstance(host, str) and type(port) is int and 1 <= port <= 65535,
                              "invalid backend socket endpoint")
                address(host)
        return snapshot
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
        with checkpoint_stage("etw-start", source, expected_hash):
            start_capture(root, session, logman)
    except subprocess.TimeoutExpired:
        # A timed-out start can still have registered this uniquely named session.
        try:
            with checkpoint_stage("etw-start-cleanup", source, expected_hash):
                quiet([logman, "stop", session, "-ets"])
        except Exception:
            pass
        raise
    driver_handles = DriverHandles()
    try:
        manifest["start_utc"] = now().isoformat()
        # Leave room for Sysmon's millisecond birth timestamp at the audit boundary.
        time.sleep(INITIAL_FIXTURE_LEAD_IN_SECONDS)
        print("N12 journey stage initial calibration", flush=True)
        with checkpoint_stage("initial-calibration", source, expected_hash):
            record = calibrate(calibration[0], manifest)
            verify_initial_sysmon(root, manifest, record)
        mark(manifest, "idle")
        time.sleep(3)
        with driver_handles, journey_processes(source, expected_hash) as stack:
            backend = spawn(stack, manifest, "backend", [sys.executable, "-B", "-m", "uvicorn",
                "backend.main:app", "--host", "127.0.0.1", "--port", "8000", "--no-access-log"],
                env, build.REPO, root / "backend.log")
            vite = spawn(stack, manifest, "driver", [node, str(FRONTEND / "node_modules/vite/bin/vite.js"),
                "--host", "127.0.0.1", "--port", "5173", "--strictPort"],
                driver_environment(env, root), FRONTEND, root / "vite.log")
            driver_handles.watch(vite, "vite")
            wait_for(lambda: http_ready(8000, "/api/health", lambda status:
                                       status.get("status") == "ok" and status.get("cloud_ai") is False),
                     60, "loopback backend did not become ready with cloud AI off", backend)
            backend_snapshot = backend_socket_snapshot(backend)
            wait_for(lambda: http_ready(5173, "/"), 60, "Vite did not become ready", vite)
            with checkpoint_stage("app-journey", source, expected_hash):
                app_witnesses = run_apps(stack, manifest, root, staged, source, expected_hash, node,
                                         env, profile, backend, vite, driver_handles)
        print("N12 journey stage final calibration", flush=True)
        with checkpoint_stage("final-fixture", source, expected_hash):
            final_start = now()
            time.sleep(INITIAL_FIXTURE_LEAD_IN_SECONDS)
            # Sysmon can associate a late socket event with the wrong GUID
            # if the short-lived final child exits before attribution.
            final_record = calibrate(
                calibration[1], manifest, child_hold_seconds=FINAL_FIXTURE_CHILD_HOLD_SECONDS,
            )
            final_end = now()
            manifest["end_utc"] = final_end.isoformat()
    except BaseException:
        checkpoint("capture", "interrupted", source, expected_hash)
        print("N12 interrupted driver handle inventory " + json.dumps(driver_handles.inventory()), flush=True)
        try:
            stop_capture(root, session, manifest, capture_start, devices)
        except Exception:
            # The capture error remains primary, even when ETW cleanup also fails.
            pass
        raise
    counters, capture_end = stop_capture(root, session, manifest, capture_start, devices)
    print("N12 journey stage export and audit", flush=True)
    last_processes = process_bookend()
    bookends = ({"before": first_processes, "after": last_processes}
                if first_processes is not None and last_processes is not None else None)
    if bookends is not None:
        report_file(root / "private-process-bookends.json", bookends)
    time.sleep(3)
    with checkpoint_stage("protected-endpoints", source, expected_hash), trace.evidence_stage("protected endpoint snapshot"):
        after = snapshots(manifest)
        report_file(root / "after.json", after)
        comparison, issues = trace.compare_snapshots(before, after, manifest)
    print("N12 protected endpoint snapshots " + json.dumps({
        "source_sha": source,
        "executable_sha256": expected_hash,
        **comparison,
        "snapshot_issues": sorted(issues),
    }), flush=True)
    final_verified_through = None
    try:
        final_verified_through = verify_fixture_sysmon(
            root, manifest["sysmon_first_record"], final_start, final_end, final_record, phase="final",
        )
        final_calibration = {"status": "PASS"}
    except trace.EvidenceValidationError as exc:
        # Keep the app evidence available when the final fixture check is blocked.
        final_calibration = {"status": "BLOCKED", "reason": str(exc)}
    print("N12 final Sysmon fixture check " + json.dumps(final_calibration), flush=True)
    sysmon = root / "sysmon.xml"
    with checkpoint_stage("sysmon-export", source, expected_hash):
        manifest["sysmon_last_record"] = sysmon_tail()
        trace.require(final_verified_through is None or manifest["sysmon_last_record"] >= final_verified_through,
                      "Sysmon channel record ID regressed after final fixture verification")
        export_sysmon(manifest["sysmon_first_record"], manifest["sysmon_last_record"], sysmon)
    endpoints, launches = [], {}
    rejected_sysmon_exits = []
    try:
        with checkpoint_stage("sysmon-reduction", source, expected_hash):
            observed = trace.inspect_journey_sysmon(manifest, sysmon, etw=True, private_endpoints=endpoints,
                                                    private_app_launches=launches,
                                                    rejected_sysmon_exits=rejected_sysmon_exits)
    finally:
        if rejected_sysmon_exits:
            print("N12 rejected Sysmon exits " + json.dumps(rejected_sysmon_exits), flush=True)
    report_file(root / "private-endpoints.json", endpoints)
    if backend_snapshot is not None:
        report_file(root / "private-backend-sockets.json", backend_snapshot)
    backend_pairs = backend_self_connections(endpoints, observed, backend_snapshot)
    log_paths = {label: profile / f"netlog-{label}.json" for label in ("first", "relaunch")}
    network_diagnostics = network_summary(endpoints, launches, log_paths, backend_pairs=backend_pairs)
    network_diagnostics["backend_socket_snapshot"] = "available" if backend_snapshot is not None else "unavailable"
    print("N12 network observations " + json.dumps({
        "source_sha": source,
        "executable_sha256": expected_hash,
        "scope": "diagnostic-only-before-combined-audit",
        "sysmon_and_lifecycle_issues": sorted(observed.issues),
        "connections": observed.network_counts,
        "unexpected_connections": observed.unexpected_connections,
        "network_diagnostics": network_diagnostics,
    }), flush=True)
    with checkpoint_stage("etw-export", source, expected_hash):
        powershell(HELPER, "etw-export", "-CaptureRoot", root, timeout=600)
    events = root / "etw.jsonl"
    manifest["etw"] = {"schema_version": 1, "start_utc": capture_start.isoformat(),
                       "end_utc": capture_end.isoformat(), "counters": counters,
                       "volume_devices": devices, "events_sha256": build.digest(events)}
    report_file(root / "manifest.json", manifest)
    paths = diagnostic_paths(root, staged, manifest)
    app_lifetimes = {}
    driver_lifetimes = {}

    def observe_lifetimes(events, devices, window, issues):
        app_lifetimes.update(journey_lifetime_evidence(
            events, devices, window, observed, app_witnesses, expected_hash, issues))
        print("N12 app lifetime observations " + json.dumps({
            "source_sha": source, "executable_sha256": expected_hash, **app_lifetimes,
        }), flush=True)
        driver_lifetimes.update(driver_lifetime_evidence(events, devices, window, observed, driver_handles, issues))
        print("N12 driver lifetime observations " + json.dumps(driver_lifetimes), flush=True)

    with checkpoint_stage("combined-reduction", source, expected_hash):
        result = trace.complete_journey_audit(manifest, observed, events, before, after, etw=True,
                                              record_outside_writer=paths.record, journey_bookends=bookends,
                                              describe_path_gaps=True, observe_lifetimes=observe_lifetimes)
    result["journey_diagnostics"] = {
        "app_lifetimes": app_lifetimes,
        "driver_lifetimes": driver_lifetimes,
        "outside_scope_paths": paths.summary(),
        "outside_scope_writers": paths.writer_summary(),
        "backend_outside_scope_targets": paths.backend_target_summary(),
        "final_sysmon_calibration": final_calibration,
        "process_bookends": {"before": "available" if first_processes is not None else "unavailable",
                            "after": "available" if last_processes is not None else "unavailable"},
        "network": network_diagnostics,
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
        with checkpoint_stage("preflight", args.source, args.expected_exe_sha256):
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
