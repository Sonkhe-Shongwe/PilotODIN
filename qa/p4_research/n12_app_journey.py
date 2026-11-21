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

from qa.p4_native.n12_calibration import calibration_failure_stages
from qa.p4_native import n12_etw_probe as etw
from qa.p4_native.n12_exit_corroboration import journey_lifetime_evidence
from qa.p4_native import n12_protected_restore as restore
from qa.p4_native import n12_trace as trace
from qa.p4_research import n12_app_build as build
from qa.p4_research import n12_egress as egress
from qa.p4_research.n12_backend_wakeup import WITNESS_NAME
from qa.p4_research.n12_journey_diagnostics import (
    OutsidePaths, address, backend_self_connections, backend_wakeup_connections, network_summary,
)
from qa.p4_research.n12_driver_handles import DriverHandles, driver_lifetime_evidence


NATIVE = build.REPO / "qa" / "p4_native"
FRONTEND = build.REPO / "frontend"
HELPER = Path(__file__).with_name("Invoke_N12_Journey_Evidence.ps1")
PROBE = FRONTEND / "e2e" / "p4-71-native-webview-qa.mjs"
PORTS = (5173, 8000, 9331)
HTTP = build_opener(ProxyHandler({}))
CAPTURE_CONSENT = "I_APPROVE_ONE_N12_APP_JOURNEY"
SAME_CAPTURE_RESTORE = "PILOTODIN_N12_SAME_CAPTURE_RESTORE"
DRIVER_TEMP_DIR = "driver-temp"
APP_TEMP_DIR = "app-temp"
INITIAL_FIXTURE_LEAD_IN_SECONDS = 0.05
TRACED_FIXTURE_CHILD_HOLD_SECONDS = 4
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


def snapshot_capture_evidence(manifest, capture_start, capture_end):
    """Both complete protected/observed inventories must lie inside one ETW session."""
    names = ("snapshot-before-start", "snapshot-before-end",
             "snapshot-after-start", "snapshot-after-end")
    markers = manifest.get("markers")
    trace.require(isinstance(markers, dict) and all(type(markers.get(name)) is str for name in names),
                  "snapshot-capture-markers-missing")
    try:
        stamps = [trace.utc_time(markers[name]) for name in names]
    except (ValueError, TypeError, OverflowError):
        raise trace.EvidenceValidationError("snapshot-capture-markers-invalid") from None
    trace.require(all(type(manifest.get(k)) is str for k in ("start_utc", "end_utc")),
                  "snapshot-audit-bounds-missing")
    try:
        audit_start = trace.utc_time(manifest["start_utc"])
        audit_end = trace.utc_time(manifest["end_utc"])
    except (ValueError, TypeError, OverflowError):
        raise trace.EvidenceValidationError("snapshot-audit-bounds-invalid") from None
    trace.require(capture_start <= audit_start <= stamps[0] <= stamps[1] < stamps[2] <=
                  stamps[3] <= audit_end <= capture_end, "snapshot-capture-unbracketed")
    return {"status": "PASS", "before_in_capture": True, "after_in_capture": True,
            "before_in_audit": True, "after_in_audit": True}


def start_capture(root, session, logman):
    providers = root / "providers.txt"
    providers.write_text(
        "Microsoft-Windows-Kernel-File 0x1ff0 4\nMicrosoft-Windows-Kernel-Process 0x30 4\n",
        encoding="ascii",
    )
    quiet([logman, "create", "trace", session, "-pf", str(providers), "-o", str(root / "journey.etl"),
           "-max", "512", "-bs", "64", "-nb", "16", "128", "-ets"])


def start_journey_etw(root, session, source, expected_hash):
    logman = str(Path(os.environ["SystemRoot"]) / "System32" / "logman.exe")
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


def cleanup_process(process):
    if process.poll() is None:
        process.kill()
        process.wait(timeout=15)


def spawn(stack, manifest, role, command, env, cwd, log, *, prelaunch_log_hook=None):
    """Existing spawn unchanged unless a reviewed QA-only prelaunch hook is supplied.

    The hook runs after exclusive log creation but strictly before Popen, so
    the no-CDP reader can pin a new empty log without any stale-marker race.
    It must return the still-open PrelaunchLog, retained by its caller until
    after verified normal close. A failed verification never starts the app.
    """
    with log.open("xb") as stream:
        if prelaunch_log_hook is not None:
            from qa.p4_research.n12_no_cdp_log_witness import PrelaunchLog
            trace.require(role == "app" and callable(prelaunch_log_hook),
                          "no-cdp-prelaunch-hook-invalid")
            witness = prelaunch_log_hook(log)
            trace.require(isinstance(witness, PrelaunchLog)
                          and witness.path == log and not witness.handle.closed,
                          "no-cdp-prelaunch-witness-unverified")
            # Recheck the exact path and empty content immediately before
            # Popen; the held original descriptor defeats rapid inode reuse.
            status = log.stat()
            trace.require(not log.is_symlink() and status.st_dev == witness.device
                          and status.st_ino == witness.inode and status.st_size == 0,
                          "no-cdp-log-identity-changed")
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
    try:
        completed = subprocess.run(command, cwd=build.REPO, capture_output=True, check=True, timeout=30)
    except subprocess.CalledProcessError as exc:
        stages = calibration_failure_stages(exc.stderr)
        reason = ", ".join(stages) if stages else "unclassified"
        raise trace.EvidenceValidationError(f"calibration fixture subprocess failed at {reason}") from None
    record = json.loads(completed.stdout)
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


def run_initial_calibration(root, directory, manifest, source, expected_hash):
    # The representative journey's audit already starts before the first full
    # fingerprint. Standalone calibration still creates its own audit start.
    if "start_utc" not in manifest:
        manifest["start_utc"] = now().isoformat()
    # Leave room for Sysmon's millisecond birth timestamp at the audit boundary.
    time.sleep(INITIAL_FIXTURE_LEAD_IN_SECONDS)
    print("N12 journey stage initial calibration", flush=True)
    with checkpoint_stage("initial-calibration", source, expected_hash):
        # Give Sysmon the same time as the final fixture to attribute the
        # socket markers before the calibration child exits.
        record = calibrate(directory, manifest, child_hold_seconds=TRACED_FIXTURE_CHILD_HOLD_SECONDS)
        verify_initial_sysmon(root, manifest, record)


def capture_initial_fixture(root, source):
    root.mkdir(exist_ok=False)
    session = f"PilotODIN-N12-App-{uuid4().hex}"
    manifest = {"processes": [], "loopback_ports": list(PORTS), "sysmon_first_record": sysmon_tail() + 1}
    start_journey_etw(root, session, source, "")
    try:
        run_initial_calibration(root, root / "calibration-first", manifest, source, "")
    except BaseException:
        try:
            with checkpoint_stage("etw-stop", source, ""):
                etw.stop_trace(session)
        except Exception:
            pass  # Preserve the fixture failure; the checkpoint reports the stop failure.
        raise
    with checkpoint_stage("etw-stop", source, ""):
        counters = etw.stop_trace(session)
    print("N12 initial fixture ETW counters " + json.dumps(counters), flush=True)
    trace.require(counters["buffers_written"] > 0 and all(counters[key] == 0 for key in (
        "events_lost", "log_buffers_lost", "realtime_buffers_lost",
    )), "initial fixture ETW coverage blocked by empty or lossy capture")
    trace.require((root / "journey.etl").stat().st_size > 0, "initial fixture ETW file is empty")
    print("N12 initial journey fixture " + json.dumps({
        "source_sha": source, "status": "PASS", "scope": "initial-calibration-only",
    }), flush=True)



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


def temporary_environment(env, scratch):
    return {**env, "TEMP": str(scratch), "TMP": str(scratch), "TMPDIR": str(scratch)}


def backend_environment(env):
    """Import the QA server from source without making the checkout its CWD.

    The backend's data home is already runner-local. Its prior CWD was the
    repository, so relative library writes could mutate the source checkout.
    Never permit that path in the N12 filesystem policy.
    """
    existing = env.get("PYTHONPATH", "")
    return {**env, "PYTHONPATH": str(build.REPO) + (os.pathsep + existing if existing else "")}


def app_environment(env, profile, label):
    return {**temporary_environment(env, profile / APP_TEMP_DIR),
            "WEBVIEW2_USER_DATA_FOLDER": str(profile),
            "WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS":
                '--remote-debugging-port=9331 --net-log-capture-mode=Default '
                f'--log-net-log="{profile / f"netlog-{label}.json"}"'}


def driver_environment(env, root):
    scratch = root / DRIVER_TEMP_DIR
    # Keep disposable driver scratch and any inherited PowerShell cache scoped.
    return {**temporary_environment(env, scratch),
            "PSMODULEANALYSISCACHEPATH": str(scratch / "powershell-module-analysis-cache")}


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
    driver_env = driver_environment({**env, "PILOTODIN_N12_DIALOG_PYTHON": sys.executable}, root)
    process = spawn(stack, manifest, "driver", command, driver_env, FRONTEND, log)
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


def run_apps(stack, manifest, root, staged, source, expected_hash, node, env, profile, backend, vite, handles,
             egress_programs=None, *, restore_path=None):
    from qa.p4_native.n12_lifetime_control import process_images, process_times

    binary = build.executable(staged) if egress_programs is None else egress_programs["app"]
    title = json.loads(build.isolated_config())["app"]["windows"][0]["title"]
    first_pid = None
    witnesses = {}
    restore_control = None
    for relaunch in (False, True):
        label = "relaunch" if relaunch else "first"
        trace.require(backend.poll() is None and vite.poll() is None, "loopback service exited during journey")
        print(f"N12 journey stage {label} launch", flush=True)
        build.verify(staged, source, expected_hash)
        mark(manifest, "reopen" if relaunch else "launch")
        app_env = app_environment(env, profile, label)
        if egress_programs is not None:
            app_env["WEBVIEW2_BROWSER_EXECUTABLE_FOLDER"] = str(egress_programs["webview"].parent)
        app = spawn(stack, manifest, "app", [binary], app_env, binary.parent, root / f"app-{label}.log")
        trace.require(app.pid != first_pid, "relaunch must have a distinct app PID")
        first_pid = app.pid
        wait_for(lambda: http_ready(9331, "/json/version", lambda status: bool(status.get("webSocketDebuggerUrl"))),
                 45, f"{label} WebView debugger did not become ready", app)
        if not relaunch:
            mark(manifest, "quality")
        run_driver(stack, manifest, node, root, {**env, "P4_NATIVE_QA_APP_PID": str(app.pid)}, relaunch, handles)
        if not relaunch and restore_path is not None:
            with checkpoint_stage("same-capture-write-and-restore", source, expected_hash):
                target = trace.local_disposable_path(restore_path, runner_temp_only=True)
                restore_control = restore.exercise_restore(target)
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
    return witnesses, restore_control


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
    (profile / APP_TEMP_DIR).mkdir()
    (root / DRIVER_TEMP_DIR).mkdir()
    return manifest, home, profile, source_fixture, calibration


def diagnostic_paths(root, staged, manifest, *, user_temp=None):
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
    environment = os.environ if user_temp is None else {**os.environ, "TEMP": user_temp}
    roots.extend((label, environment[key]) for label, key in (
        ("runner-temp", "RUNNER_TEMP"), ("user-temp", "TEMP"), ("user-local", "LOCALAPPDATA"),
        ("user-roaming", "APPDATA"), ("runner-tool-cache", "RUNNER_TOOL_CACHE"),
        ("shared-application-data", "ProgramData"), ("user-profile", "USERPROFILE"),
        ("windows-system", "SystemRoot"),
    ) if environment.get(key))
    return OutsidePaths(roots)


def process_bookend():
    try:
        snapshot = json.loads(powershell(HELPER, "process-bookend"))
        entries = snapshot["processes"]
        # Validate the snapshot before passing it to the audit. One bad
        # snapshot leaves the original audit available without bookend data.
        trace.require(isinstance(entries, list) and entries, "process bookend is empty")
        trace.stable_process_bookend_records({"before": entries, "after": []}, 0, set())
    except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError):
        return None, None
    threads = snapshot.get("threads")
    try:
        trace.require(isinstance(threads, list) and threads, "thread bookend is empty")
        trace.stable_thread_bookends({"threads_before": threads}, 0, set(), set())
    except (ValueError, KeyError, TypeError):
        threads = None
    return entries, threads


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


def compare_background_paths(root, manifest, observed, events, bookends, baseline, rundown_window):
    trace.require(bookends and bookends.get("threads_before") and bookends.get("threads_after"),
                  "paired thread snapshots are required for background path comparison")
    powershell(HELPER, "fileio-rundown", "-CaptureRoot", root, timeout=300)
    names = root / "rundown.jsonl"
    first, last = rundown_window
    manifest = {**manifest, "etw": {**manifest["etw"], "rundown_start_utc": first.isoformat(),
                                    "rundown_stop_utc": last.isoformat(), "rundown_sha256": build.digest(names)}}
    report_file(root / "background-rundown-manifest.json", manifest)
    rundown = trace.read_rundown_file(names, manifest)
    protected, permitted = trace.scope(manifest)
    protected.extend(trace.windows_path(manifest["observed_roots"][label])
                     for label in manifest["immutable_observed"])
    verified = Counter()
    _, violations, _, unresolved = trace.inspect_etw_files(
        manifest, events, observed.start, observed.end, observed.processes, observed.roles,
        protected, permitted, set(), background_bookends=bookends, rundown=rundown,
        background_rundown=verified,
    )
    gap = "other:write:path-missing"
    protected_write = "protected:other:write"
    before = baseline["etw_unresolved_mutations"].get(gap, 0)
    remaining = unresolved.get(gap, 0)
    trace.require(before - remaining == sum(verified.values()) and verified["protected"] ==
                  violations.get(protected_write, 0) - baseline["file_violations"].get(protected_write, 0),
                  "background path comparison does not reconcile with the ordinary audit")
    return {"status": "completed", "etw_events_sha256": manifest["etw"]["events_sha256"],
            "rundown_sha256": manifest["etw"]["rundown_sha256"], "baseline_write_path_gaps": before,
            "verified_paths": dict(verified), "remaining_write_path_gaps": remaining,
            "unresolved_background_writes": {key: count for key, count in unresolved.items()
                                             if key.startswith("other:write:")}}


def same_capture_restore_evidence(control, expected_path, events, devices, window, capture_issues):
    try:
        _, _, verified, write_issues = restore.inspect_restore_writes(
            control, events, devices, window, expected_path, require_single_write=True,
        )
    except trace.EvidenceValidationError as exc:
        return {"status": "BLOCKED", "reason": str(exc)}
    return {
        "status": "PASS" if all(verified.values()) and "etw-event-or-buffer-loss" not in capture_issues else "BLOCKED",
        "endpoint_match": True, "destination": "generated-restore-fixture",
        "write_path_verified": verified, "write_issues": write_issues,
        "etw_reported_loss": "etw-event-or-buffer-loss" in capture_issues,
    }


def require_same_capture_restore(result, control_evidence):
    if control_evidence.get("status") != "PASS":
        result["coverage"] = "BLOCKED"
        result["coverage_issues"] = sorted({*result["coverage_issues"], "etw-same-capture-restore-unverified"})
        for verdict in ("filesystem", "network"):
            if result[verdict] == "PASS_SCOPED":
                result[verdict] = "BLOCKED"


def capture(root, staged, source, expected_hash, node, egress_programs=None):
    manifest, home, profile, fixture, calibration = prepare_journey(root, source, expected_hash)
    env = {**os.environ, "CI": "true", "PILOTODIN_HOME": str(home), "PYTHONDONTWRITEBYTECODE": "1",
           "VITE_PILOTODIN_NATIVE_SMOKE": "1", "PILOTODIN_N12_QUALITY_FIXTURE": str(fixture)}
    restore_path = None
    if env.get(SAME_CAPTURE_RESTORE) == "1":
        restore_path = trace.local_disposable_path(root / "write-restore-control.bin", runner_temp_only=True)
        with restore_path.open("xb") as stream:
            stream.write(restore.ORIGINAL)
        manifest["observed_roots"]["write-restore-control"] = str(restore_path)
    require_fixture = (
        "import {p4QualityFixture} from './e2e/p4-quality-version-transition.mjs';"
        "process.stdout.write(p4QualityFixture);"
    )
    fixture_bytes = quiet([node, "--input-type=module", "-e", require_fixture], cwd=FRONTEND)
    trace.require(bool(fixture_bytes), "the generated Quality fixture is empty")
    with fixture.open("xb") as stream:
        stream.write(fixture_bytes)
    devices = etw.volume_devices()
    session = f"PilotODIN-N12-App-{uuid4().hex}"
    first_processes, first_threads = process_bookend()
    manifest["sysmon_first_record"] = sysmon_tail() + 1
    capture_start = now()
    start_journey_etw(root, session, source, expected_hash)
    # Governed audit bounds must contain both fingerprints, not merely the
    # wider ETW session. Otherwise a temporary mutation during a scan could
    # disappear from the event reducer despite successful collector startup.
    manifest["start_utc"] = now().isoformat()
    driver_handles = DriverHandles()
    compare_fileio = os.environ.get("PILOTODIN_N12_APP_RUNDOWN_CONSENT") == "I_APPROVE_ONE_N12_APP_RUNDOWN"
    rundown_cleanup = ExitStack()
    stop_rundown = rundown_window = None
    rundown_error = "collector-unavailable"
    try:
        with checkpoint_stage("protected-before-scan", source, expected_hash):
            mark(manifest, "snapshot-before-start")
            before = snapshots(manifest)
            mark(manifest, "snapshot-before-end")
        if compare_fileio:
            try:
                stop_rundown = rundown_cleanup.enter_context(etw.collect_fileio_rundown(root))
            except (OSError, RuntimeError, subprocess.SubprocessError):
                rundown_error = "recorder-start-failed"
        run_initial_calibration(root, calibration[0], manifest, source, expected_hash)
        mark(manifest, "idle")
        time.sleep(3)
        with driver_handles, journey_processes(source, expected_hash) as stack:
            python = sys.executable if egress_programs is None else egress_programs["backend"]
            backend = spawn(stack, manifest, "backend", [python, "-B", "-m", "uvicorn",
                "qa.p4_research.n12_backend_wakeup:app", "--host", "127.0.0.1", "--port", "8000", "--no-access-log"],
                backend_environment(env), home, root / "backend.log")
            vite = spawn(stack, manifest, "driver", [node, str(FRONTEND / "node_modules/vite/bin/vite.js"),
                "--host", "127.0.0.1", "--port", "5173", "--strictPort", "--configLoader", "runner"],
                driver_environment(env, root), FRONTEND, root / "vite.log")
            driver_handles.watch(vite, "vite")
            wait_for(lambda: http_ready(8000, "/api/health", lambda status:
                                       status.get("status") == "ok" and status.get("cloud_ai") is False),
                     60, "loopback backend did not become ready with cloud AI off", backend)
            backend_snapshot = backend_socket_snapshot(backend)
            try:
                backend_wakeup = trace.read_json(home / WITNESS_NAME)
            except (OSError, ValueError):
                backend_wakeup = None
            wait_for(lambda: http_ready(5173, "/"), 60, "Vite did not become ready", vite)
            with checkpoint_stage("app-journey", source, expected_hash):
                app_witnesses, restore_control = run_apps(
                    stack, manifest, root, staged, source, expected_hash, node, env, profile, backend, vite,
                    driver_handles, egress_programs, restore_path=restore_path,
                )
        print("N12 journey stage final calibration", flush=True)
        with checkpoint_stage("final-fixture", source, expected_hash):
            final_start = now()
            time.sleep(INITIAL_FIXTURE_LEAD_IN_SECONDS)
            # Sysmon can associate a late socket event with the wrong GUID
            # if the short-lived final child exits before attribution.
            final_record = calibrate(
                calibration[1], manifest, child_hold_seconds=TRACED_FIXTURE_CHILD_HOLD_SECONDS,
            )
            final_end = now()
        with checkpoint_stage("protected-after-scan", source, expected_hash):
            mark(manifest, "snapshot-after-start")
            after = snapshots(manifest)
            mark(manifest, "snapshot-after-end")
        manifest["end_utc"] = now().isoformat()
        if stop_rundown is not None:
            first = now()
            try:
                rundown_window = first, timestamp_from_ticks(stop_rundown())
            except (OSError, RuntimeError, subprocess.SubprocessError):
                rundown_error = "recorder-stop-failed"
    except BaseException:
        checkpoint("capture", "interrupted", source, expected_hash)
        print("N12 interrupted driver handle inventory " + json.dumps(driver_handles.inventory()), flush=True)
        try:
            stop_capture(root, session, manifest, capture_start, devices)
        except Exception:
            # The capture error remains primary, even when ETW cleanup also fails.
            pass
        raise
    finally:
        try:
            rundown_cleanup.close()
        except (OSError, RuntimeError, subprocess.SubprocessError):
            rundown_window = None
            rundown_error = "recorder-cleanup-failed"
    counters, capture_end = stop_capture(root, session, manifest, capture_start, devices)
    print("N12 journey stage export and audit", flush=True)
    last_processes, last_threads = process_bookend()
    bookends = ({"before": first_processes, "after": last_processes}
                if first_processes is not None and last_processes is not None else None)
    if bookends is not None:
        if first_threads is not None and last_threads is not None:
            bookends.update(threads_before=first_threads, threads_after=last_threads)
        report_file(root / "private-process-bookends.json", bookends)
    time.sleep(3)
    with checkpoint_stage("protected-endpoints", source, expected_hash), trace.evidence_stage("protected endpoint snapshot"):
        capture_windows = snapshot_capture_evidence(manifest, capture_start, capture_end)
        report_file(root / "before.json", before)
        report_file(root / "after.json", after)
        comparison, issues = trace.compare_snapshots(before, after, manifest)
        if restore_control is not None:
            final_control = after["observed"]["write-restore-control"]
            restore_control["after"] = (build.digest(trace.local_disposable_path(restore_path, runner_temp_only=True))
                                        if final_control["state"] == "file" else None)
            report_file(root / "private-write-restore-control.json", restore_control)
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
    egress_images_verified = None
    try:
        with checkpoint_stage("sysmon-reduction", source, expected_hash):
            observed = trace.inspect_journey_sysmon(manifest, sysmon, etw=True, private_endpoints=endpoints,
                                                    private_app_launches=launches,
                                                    rejected_sysmon_exits=rejected_sysmon_exits)
            if egress_programs is not None:
                egress_images_verified = egress.journey_images_match(egress_programs, observed)
                if not egress_images_verified:
                    observed.issues.add("egress-program-image-unverified")
    finally:
        if rejected_sysmon_exits:
            print("N12 rejected Sysmon exits " + json.dumps(rejected_sysmon_exits), flush=True)
    report_file(root / "private-endpoints.json", endpoints)
    if backend_snapshot is not None:
        report_file(root / "private-backend-sockets.json", backend_snapshot)
    backend_pairs = backend_self_connections(endpoints, observed, backend_snapshot)
    wakeup_pairs = backend_wakeup_connections(endpoints, observed, backend_snapshot, backend_wakeup)
    log_paths = {label: profile / f"netlog-{label}.json" for label in ("first", "relaunch")}
    network_diagnostics = network_summary(endpoints, launches, log_paths,
                                          backend_pairs=backend_pairs, backend_wakeup_pairs=wakeup_pairs)
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
    with checkpoint_stage("etw-boundary-diagnostic", source, expected_hash):
        # This cannot change the reducer's strict timestamp bounds or a verdict.
        bounds = tuple(trace.utc_ticks(trace.utc_time(manifest["etw"][key]))
                       for key in ("start_utc", "end_utc"))
        boundary = trace.etw_timestamp_boundary_diagnostic(events, bounds, manifest["etw"]["events_sha256"])
        print("N12 ETW boundary diagnostic " + json.dumps({
            "source_sha": source, "executable_sha256": expected_hash, **boundary,
        }), flush=True)
    paths = diagnostic_paths(root, staged, manifest)
    app_lifetimes = {}
    driver_lifetimes = {}
    control_evidence = {"status": "BLOCKED", "reason": "restore-evidence-missing"}

    def observe_lifetimes(events, devices, window, issues):
        nonlocal control_evidence
        app_lifetimes.update(journey_lifetime_evidence(
            events, devices, window, observed, app_witnesses, expected_hash, issues))
        print("N12 app lifetime observations " + json.dumps({
            "source_sha": source, "executable_sha256": expected_hash, **app_lifetimes,
        }), flush=True)
        driver_lifetimes.update(driver_lifetime_evidence(events, devices, window, observed, driver_handles, issues))
        print("N12 driver lifetime observations " + json.dumps(driver_lifetimes), flush=True)
        if restore_control is not None:
            quality, close = (trace.utc_ticks(trace.utc_time(manifest["markers"][marker]))
                              for marker in ("quality", "close"))
            control_window = (max(window[0], quality), min(window[1], close))
            control_evidence = same_capture_restore_evidence(
                restore_control, restore_path, events, devices, control_window, issues,
            )
            print("N12 same-capture restore " + json.dumps(control_evidence), flush=True)

    with checkpoint_stage("combined-reduction", source, expected_hash):
        result = trace.complete_journey_audit(manifest, observed, events, before, after, etw=True,
                                              record_outside_writer=paths.record, journey_bookends=bookends,
                                              describe_path_gaps=True, observe_lifetimes=observe_lifetimes,
                                              webview_dominant_writes=True)
    if restore_path is not None:
        require_same_capture_restore(result, control_evidence)
    result["journey_diagnostics"] = {
        "app_lifetimes": app_lifetimes,
        "driver_lifetimes": driver_lifetimes,
        "outside_scope_paths": paths.summary(),
        "outside_scope_writers": paths.writer_summary(),
        "webview_storage": paths.webview_storage_summary(),
        "backend_outside_scope_targets": paths.backend_target_summary(),
        "final_sysmon_calibration": final_calibration,
        "snapshot_capture": capture_windows,
        "process_bookends": {"before": "available" if first_processes is not None else "unavailable",
                            "after": "available" if last_processes is not None else "unavailable"},
        "network": network_diagnostics,
    }
    if restore_path is not None:
        result["journey_diagnostics"]["same_capture_restore"] = control_evidence
    if egress_images_verified is not None:
        result["journey_diagnostics"]["egress_rule_images"] = "verified" if egress_images_verified else "unverified"
    result["journey"] = "completed"
    report_file(root / "audit.json", result)

    # Both reductions validate the digest of this one ETW export. Record the
    # ordinary result first so the comparison cannot replace its findings.
    evidence_sha = manifest["etw"]["events_sha256"]
    gap = "webview-network:write:path-missing"
    baseline_gaps = result["etw_unresolved_mutations"].get(gap, 0)
    print("N12 ordinary audit " + json.dumps({
        "source_sha": source, "executable_sha256": expected_hash, "etw_events_sha256": evidence_sha,
        "webview_storage": result["journey_diagnostics"]["webview_storage"],
        **{key: result[key] for key in (
            "coverage", "coverage_issues", "filesystem", "network", "file_violations", "etw_unresolved_mutations",
        )},
    }), flush=True)
    try:
        with checkpoint_stage("webview-credit-comparison", source, expected_hash):
            comparison_paths = diagnostic_paths(root, staged, manifest)
            trial = trace.complete_journey_audit(
                manifest, observed, events, before, after, etw=True, journey_bookends=bookends,
                describe_path_gaps=True, webview_dominant_writes=True, credit_verified_webview_writes=True,
                record_outside_writer=comparison_paths.record,
            )
            if restore_path is not None:
                require_same_capture_restore(trial, control_evidence)
            credit = trial["etw_webview_write_credit"]
            remaining = trial["etw_unresolved_mutations"].get(gap, 0)
            trace.require(remaining == credit["remaining_path_gaps"] and
                          baseline_gaps - remaining == sum(credit["credited_paths"].values()),
                          "WebView credit comparison does not reconcile with the ordinary audit")
            comparison = {"status": "completed", "etw_events_sha256": evidence_sha,
                          "baseline_webview_write_path_gaps": baseline_gaps,
                          "outside_scope_webview_writes": [
                              row for row in comparison_paths.writer_summary()
                              if row["role"] == "webview-network" and row["operation"] == "write"
                          ],
                          **{key: trial[key] for key in (
                              "coverage", "coverage_issues", "filesystem", "network", "file_events",
                              "file_violations", "etw_unresolved_mutations", "etw_webview_write_credit",
                          )}}
            report_file(root / "webview-credit-comparison.json", comparison)
    except (trace.EvidenceValidationError, KeyError, OSError, RuntimeError, ValueError) as exc:
        comparison = {"status": "blocked", "etw_events_sha256": evidence_sha,
                      "baseline_webview_write_path_gaps": baseline_gaps, "error": type(exc).__name__}
    result["webview_credit_comparison"] = comparison
    if compare_fileio:
        if rundown_window is None:
            background = {"status": "blocked", "error": rundown_error}
        else:
            try:
                background = compare_background_paths(root, manifest, observed, events, bookends,
                                                      result, rundown_window)
            except (*trace.EVIDENCE_ERRORS, RuntimeError, subprocess.SubprocessError) as exc:
                background = {"status": "blocked", "error": type(exc).__name__}
        result["background_rundown_comparison"] = background
        print("N12 background FileIO comparison " + json.dumps(background), flush=True)
    return result


def initial_fixture_root(source):
    env = os.environ
    run_id = env.get("GITHUB_RUN_ID", "")
    trace.require(env.get("GITHUB_EVENT_NAME") == "push" and env.get("GITHUB_REF_NAME") == build.BRANCH
                  and env.get("GITHUB_RUN_ATTEMPT") == "1" and re.fullmatch(r"[0-9]+", run_id)
                  and env.get("PILOTODIN_N12_COLLECTOR_REHEARSAL_CONSENT") == "I_APPROVE_ONE_N12_COLLECTOR_REHEARSAL"
                  and re.fullmatch(r"[0-9a-f]{40}", source)
                  and env.get("PILOTODIN_N12_INITIAL_FIXTURE_SOURCE") == source,
                  "initial fixture requires an approved source-pinned first hosted push")
    root = trace.local_disposable_path(Path(env["RUNNER_TEMP"]) / f"pilotodin-n12-build-{run_id}-journey",
                                       runner_temp_only=True)
    trace.require(build.git("rev-parse", "HEAD") == source and not build.git("status", "--porcelain", "--untracked-files=no"),
                  "checkout differs from the approved clean source")
    return root


def run_prebuild_fixture(source):
    staged = build.stage_root(source)
    trace.require(os.environ.get("PILOTODIN_N12_APP_JOURNEY_CONSENT") == CAPTURE_CONSENT,
                  "separate one-run N12 journey consent is required")
    directory = trace.local_disposable_path(staged.with_name(f'{staged.name}-prebuild-calibration'),
                                           runner_temp_only=True)
    calibrate(directory, {"processes": [], "loopback_ports": []})
    print("N12 pre-build fixture " + json.dumps({"source_sha": source, "status": "PASS"}), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True)
    parser.add_argument("--webview-runtime-directory", type=Path)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--expected-exe-sha256")
    mode.add_argument("--initial-fixture-only", action="store_true")
    mode.add_argument("--prebuild-fixture", action="store_true")
    args = parser.parse_args()
    if args.webview_runtime_directory is not None and args.expected_exe_sha256 is None:
        parser.error("--webview-runtime-directory requires --expected-exe-sha256")
    try:
        if args.prebuild_fixture:
            with checkpoint_stage("pre-build-calibration", args.source, ""):
                run_prebuild_fixture(args.source)
            return 0
        if args.initial_fixture_only:
            with checkpoint_stage("fixture-preflight", args.source, ""):
                root = initial_fixture_root(args.source)
            capture_initial_fixture(root, args.source)
            return 0
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
        if args.webview_runtime_directory is None:
            result = capture(root, staged, args.source, args.expected_exe_sha256, node)
        else:
            with ExitStack() as stack:
                with checkpoint_stage("egress-setup", args.source, args.expected_exe_sha256):
                    programs = egress.journey_programs(build.executable(staged), Path(sys.executable),
                                                       args.webview_runtime_directory)
                    stack.enter_context(egress.journey_blocks(programs))
                result = capture(root, staged, args.source, args.expected_exe_sha256, node, programs)
            print("N12 journey egress rules removed and cleanup verified", flush=True)
        print(json.dumps(result))
        return 0 if (result["network"] == result["filesystem"] == "PASS_SCOPED" and
                     result["webview_credit_comparison"]["status"] == "completed" and
                     result.get("background_rundown_comparison", {"status": "completed"})["status"] ==
                     "completed") else 2
    except trace.EvidenceValidationError as exc:
        print(f"N12 journey blocked: {exc}.", file=sys.stderr)
    except (KeyError, OSError, RuntimeError, ValueError, subprocess.SubprocessError) as exc:
        print(f"N12 journey blocked: {type(exc).__name__}. See private runner evidence.", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
