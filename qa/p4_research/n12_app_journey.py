"""Capture two launches of one approved, already-staged PilotODIN Windows build."""
import argparse
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


NATIVE = build.REPO / "qa" / "p4_native"
FRONTEND = build.REPO / "frontend"
HELPER = Path(__file__).with_name("Invoke_N12_Journey_Evidence.ps1")
PROBE = FRONTEND / "e2e" / "p4-71-native-webview-qa.mjs"
PORTS = (5173, 8000, 9331)
HTTP = build_opener(ProxyHandler({}))
CAPTURE_CONSENT = "I_APPROVE_ONE_N12_APP_JOURNEY"


def now():
    return datetime(1, 1, 1, tzinfo=timezone.utc) + timedelta(microseconds=etw.utc_ticks() // 10)


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


def sysmon_tail():
    return int(powershell(HELPER, "sysmon-tail"))


def export_sysmon(first, last, path):
    trace.require(1 <= first <= last, "invalid Sysmon record window")
    powershell(NATIVE / "Export_P4_N12_Sysmon_Trace.ps1", first, last, path, timeout=180)


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


def verify_initial_sysmon(root, manifest, record):
    # A known TCP/UDP child and both process exits must reach Sysmon before the app starts.
    # The final audit checks both bookends against the continuous ETW export as well.
    end = now()
    time.sleep(3)
    last = sysmon_tail()
    path = root / "initial-sysmon.xml"
    first = manifest["sysmon_first_record"]
    export_sysmon(first, last, path)
    with trace.evidence_stage("initial Sysmon XML"):
        processes, connections, issues, actual_first, actual_last = trace.sysmon_events(
            path, trace.utc_time(manifest["start_utc"]), end,
        )
    trace.require((first, last) == (actual_first, actual_last), "initial Sysmon record boundaries differ")
    roles, bindings = trace.bind_processes([record], processes, issues)
    if bindings:
        parent = bindings[0][1]
        children = [p for p in processes.values() if p.parent == parent.guid]
        trace.require(len(children) == 1 and children[0].pid == record["child_pid"],
                      "initial Sysmon calibration is missing the fixture child")
        child = children[0]
        trace.require(parent.sha256 and child.sha256 == parent.sha256 and child.image == parent.image
                      and parent.end and child.end and parent.start <= child.start <= child.end <= parent.end,
                      "initial Sysmon calibration is missing the verified fixture lifetimes")
        protocols = {connection.protocol for connection in connections
                     if connection.guid == child.guid and connection.initiated
                     and child.start <= connection.timestamp <= child.end
                     and connection.address.is_loopback and connection.port == record["port"]}
        trace.require(protocols == {"tcp", "udp"}, "initial Sysmon calibration is missing loopback TCP or UDP")
    trace.verify_connection_lifetimes(connections, processes, roles, issues)
    _, unexpected, _ = trace.scoped_network(connections, roles, {record["port"]})
    if unexpected:
        issues.add("calibration-unexpected-connection")
    trace.require(not issues, "initial Sysmon calibration blocked: " + ", ".join(sorted(issues)))


def run_driver(stack, manifest, node, root, env, relaunch):
    command = [node, str(PROBE)]
    label = "relaunch" if relaunch else "first"
    if relaunch:
        command.append("--verify-relaunch")
    process = spawn(stack, manifest, "driver", command, env, FRONTEND, root / f"driver-{label}.log")
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
                             "driver": [str(home), str(FRONTEND / "node_modules" / ".vite")],
                             "calibration": list(map(str, calibration))},
    }
    trace.scope(manifest)
    root.mkdir(exist_ok=False)
    home.mkdir()
    profile.mkdir()
    return manifest, home, profile, source_fixture, calibration


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
    time.sleep(3)
    after = snapshots(manifest)
    report_file(root / "after.json", after)
    manifest["sysmon_last_record"] = sysmon_tail()
    sysmon = root / "sysmon.xml"
    export_sysmon(manifest["sysmon_first_record"], manifest["sysmon_last_record"], sysmon)
    powershell(HELPER, "etw-export", "-CaptureRoot", root, timeout=600)
    events = root / "etw.jsonl"
    manifest["etw"] = {"schema_version": 1, "start_utc": capture_start.isoformat(),
                       "end_utc": capture_end.isoformat(), "counters": counters,
                       "volume_devices": devices, "events_sha256": build.digest(events)}
    report_file(root / "manifest.json", manifest)
    endpoints = []
    result = trace.audit(manifest, sysmon, events, before, after, etw=True, private_endpoints=endpoints)
    report_file(root / "private-endpoints.json", endpoints)
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
