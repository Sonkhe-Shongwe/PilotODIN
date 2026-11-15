"""Exercise the N12 journey order and refusal paths without running Windows."""
from datetime import datetime, timedelta, timezone
import ipaddress
import json
import os
import subprocess
import sys
from xml.etree import ElementTree as ET

import pytest

from qa.p4_research import n12_app_journey as journey


SOURCE = "a" * 40
EXE_SHA = "b" * 64


def test_linux_cli_refuses_before_collecting(tmp_path):
    env = {**os.environ, "GITHUB_ACTIONS": "false", "GITHUB_EVENT_NAME": "push",
           "GITHUB_REF_NAME": journey.build.BRANCH, "GITHUB_RUN_ATTEMPT": "1",
           "GITHUB_RUN_ID": "123", "RUNNER_TEMP": str(tmp_path), "PILOTODIN_N12_APPROVED_SOURCE": SOURCE,
           "PILOTODIN_P4_UNPACKAGED_NATIVE_DEV_CONSENT": journey.build.CONSENT,
           "PILOTODIN_N12_APP_JOURNEY_CONSENT": journey.CAPTURE_CONSENT}
    result = subprocess.run([sys.executable, "-B", "-m", "qa.p4_research.n12_app_journey",
                             "--source", SOURCE, "--expected-exe-sha256", EXE_SHA],
                            cwd=journey.build.REPO, env=env, capture_output=True, text=True, timeout=15)
    assert result.returncode == 2
    assert "requires disposable hosted Windows" in result.stderr
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize("fault", [None, "no-udp", "wrong-child", "gap"])
def test_prelaunch_gate_checks_fixture_processes_and_network(tmp_path, monkeypatch, fault):
    start = datetime(2026, 11, 14, tzinfo=timezone.utc)
    stamp = lambda seconds: start + timedelta(seconds=seconds)
    image = r"c:\python\python.exe"
    manifest = {"start_utc": start.isoformat(), "sysmon_first_record": 11}
    processes = {
        "parent": journey.trace.Process("parent", "root", 12, image, EXE_SHA, stamp(1), "", stamp(5)),
        "child": journey.trace.Process("child", "parent", 13, image, EXE_SHA, stamp(2), "", stamp(4)),
    }
    connections = [
        journey.trace.Connection("child", stamp(3), protocol, True, 2201, ipaddress.ip_address("127.0.0.1"), 2231)
        for protocol in ("tcp", "udp") if not (protocol == "udp" and fault == "no-udp")
    ]
    issues = {"sysmon-record-gap"} if fault == "gap" else set()
    record = {"pid": 12, "role": "calibration", "image": image,
              "port": 2231, "child_pid": 14 if fault == "wrong-child" else 13}
    monkeypatch.setattr(journey, "now", lambda: stamp(6))
    monkeypatch.setattr(journey.time, "sleep", lambda seconds: None)
    monkeypatch.setattr(journey, "sysmon_tail", lambda **kw: 20)
    monkeypatch.setattr(journey, "export_sysmon", lambda *args, **kw: None)
    monkeypatch.setattr(journey.trace, "sysmon_events", lambda *args, **kw: (processes, connections, issues, 11, 20))
    if fault:
        with pytest.raises(journey.trace.EvidenceValidationError, match={
            "no-udp": "child-loopback-tcp-or-udp-missing", "wrong-child": "child-identity-mismatch",
            "gap": "sysmon-record-gap",
        }[fault]):
            journey.verify_initial_sysmon(tmp_path, manifest, record)
    else:
        journey.verify_initial_sysmon(tmp_path, manifest, record)


NETWORK_DIAGNOSTIC_CASES = {
    "both-absent": ("child-loopback-tcp-or-udp-missing", 2, ("tcp", "udp"), {}, 0),
    "udp-other-process": ("child-loopback-tcp-or-udp-missing", 2, ("udp",),
                          {"other-process-at-fixture-port": 1}, 0),
    "udp-unrelated": ("child-loopback-tcp-or-udp-missing", 2, ("udp",), {"other-process": 1}, 0),
    "udp-not-initiated": ("child-loopback-tcp-or-udp-missing", 2, ("udp",), {"not-initiated": 1}, 0),
    "udp-off-loopback": ("calibration-unexpected-connection", 1, ("udp",),
                         {"non-loopback-destination": 1}, 0),
    "udp-wrong-port": ("calibration-unexpected-connection", 1, ("udp",), {"wrong-destination-port": 1}, 0),
    "udp-unparsed-outside": ("child-loopback-tcp-or-udp-missing", 2, ("udp",), {}, 1),
}


@pytest.mark.parametrize(("scenario", "expected", "reads"), [
    ("ready", None, 1),
    ("late", None, 2),
    ("empty-first-read", None, 2),
    ("missing", "parent-birth-missing", 2),
    ("mismatched", "parent-image-mismatch", 1),
    ("ambiguous", "parent-birth-ambiguous", 1),
    ("early-event", "parent-birth-before-window", 1),
    ("early-drive-alias", "parent-birth-before-window", 1),
    ("late-event", "parent-birth-after-window", 2),
    ("same-millisecond", "parent-birth-before-window", 1),
    ("collector-precision", None, 1),
    ("collector-drive-alias", None, 1),
    ("collector-stale", "parent-birth-before-window", 1),
    ("collector-competing", "precision-fixture-birth-ambiguous", 1),
    ("collector-wrong-child", "child-identity-mismatch", 1),
    ("pid-reuse", "parent-birth-before-window", 1),
    ("missing-creation-time", "parent-birth-before-window", 1),
    ("gap", "sysmon-record-gap", 1),
    ("regressed", "channel record ID regressed", 2),
    ("collector-change", "sysmon-restart-config-change-or-error", 2),
    ("udp-absent", "child-loopback-tcp-or-udp-missing", 2),
    ("tcp-absent", "child-loopback-tcp-or-udp-missing", 2),
    ("udp-before-birth", "connection-outside-process-lifetime", 1),
    ("udp-after-exit", "connection-outside-process-lifetime", 1),
    ("udp-outside-window", "child-loopback-tcp-or-udp-missing", 2),
    ("udp-delivered-on-second-read", None, 2),
    *((scenario, values[0], values[1]) for scenario, values in NETWORK_DIAGNOSTIC_CASES.items()),
])
def test_prelaunch_reports_sysmon_delivery_and_identity(tmp_path, monkeypatch, capsys, scenario, expected, reads):
    start = datetime(2026, 11, 14, 0, 0, 10, 500, tzinfo=timezone.utc)
    cutoff = start + timedelta(seconds=8)
    image = r"C:\Private\python.exe"
    parent = {"ProcessGuid": "private-parent", "ParentProcessGuid": "launcher", "ProcessId": "412",
              "Image": image, "Hashes": "SHA256=" + EXE_SHA}
    child = dict(parent, ProcessGuid="private-child", ParentProcessGuid="private-parent", ProcessId="413")
    marker = {"role": "calibration", "pid": 412, "child_pid": 413, "image": image, "port": 23551}
    udp = {"ProcessGuid": "private-child", "Protocol": "udp", "Initiated": "true",
           "DestinationIp": "127.0.0.1", "DestinationPort": "23551", "SourcePort": "23552"}
    events = [(11, 2, 0, {})]
    precision = scenario.startswith("collector-") and scenario != "collector-change"
    event_time = {"early-event": -1, "early-drive-alias": -1, "late-event": 9, "same-millisecond": 0,
                  "pid-reuse": -2, "missing-creation-time": -1,
                  "collector-stale": -2}.get(scenario, 0 if precision else 1)
    if scenario in {"same-millisecond", "pid-reuse"}:
        marker["parent_created_utc_ticks"] = journey.trace.utc_ticks(start) + 1000
    if precision:
        marker["parent_created_utc_ticks"] = journey.trace.utc_ticks(start) + 1000
        marker["start_window"] = [journey.trace.utc_ticks(start), journey.trace.utc_ticks(cutoff)]
    if scenario == "collector-wrong-child":
        marker["child_pid"] = 414
    if scenario == "mismatched":
        parent["Image"] = r"C:\Private\wrong.exe"
    if scenario in {"early-drive-alias", "collector-drive-alias"}:
        parent["Image"] = "\\\\?\\" + image
    birth_id = 13 if scenario == "gap" else 12
    if scenario not in {"missing", "regressed"}:
        events.extend([
            (birth_id, 1, event_time, parent.copy()),
            (birth_id + 1, 1, 2, child),
            (birth_id + 2, 3, 3, dict(udp, Protocol="tcp")),
            (birth_id + 3, 3, 3, udp),
            (birth_id + 4, 5, 4, {"ProcessGuid": "private-child", "ProcessId": "413"}),
            (birth_id + 5, 5, 5, {"ProcessGuid": "private-parent", "ProcessId": "412"}),
        ])
    protocol = "tcp" if scenario == "tcp-absent" else "udp"
    if scenario in {"tcp-absent", "udp-absent"}:
        events = [(rid, 2, offset, {}) if kind == 3 and fields["Protocol"] == protocol
                  else (rid, kind, offset, fields) for rid, kind, offset, fields in events]
    if scenario == "both-absent":
        events = [(rid, 2, offset, {}) if kind == 3 else (rid, kind, offset, fields)
                  for rid, kind, offset, fields in events]
    udp_changes = {
        "udp-other-process": {"ProcessGuid": "private-unrelated"},
        "udp-unrelated": {"ProcessGuid": "private-unrelated", "DestinationPort": "23553"},
        "udp-not-initiated": {"Initiated": "false"},
        "udp-off-loopback": {"DestinationIp": "192.0.2.21"},
        "udp-wrong-port": {"DestinationPort": "23553"},
        "udp-unparsed-outside": {"DestinationIp": "private-invalid-address"},
    }
    if scenario in udp_changes:
        offset = 9 if scenario == "udp-unparsed-outside" else 3
        events[4] = (birth_id + 3, 3, offset, {**udp, **udp_changes[scenario]})
    if scenario in {"udp-before-birth", "udp-after-exit", "udp-outside-window"}:
        offset = {"udp-before-birth": 1, "udp-after-exit": 5, "udp-outside-window": 9}[scenario]
        events[4] = (birth_id + 3, 3, offset, udp)
    if scenario == "udp-delivered-on-second-read":
        late_udp = events.pop(4)
        events = [(rid, *event[1:]) for rid, event in enumerate([*events, late_udp], 11)]
    if scenario == "ambiguous":
        events.append((18, 1, 6, dict(parent, ProcessGuid="another-parent")))
    if scenario == "collector-competing":
        events.append((18, 1, -1, dict(parent, ProcessGuid="another-parent")))
    if scenario == "collector-change":
        events.append((18, 16, 9, {}))

    last = events[-1][0]
    tails = {"late": [11, last], "empty-first-read": [10, last], "late-event": [11, last],
             "collector-change": [11, last], "regressed": [11, 10],
             "udp-delivered-on-second-read": [last - 1, last]}.get(scenario, [last] * reads)
    calls = []
    exports = []

    def tail(*, timeout):
        assert timeout == 15
        calls.append(tails[len(calls)])
        return calls[-1]

    def export(first, end, path, *, timeout):
        assert first == 11 and timeout == 15
        exports.append(path.name)
        ns = journey.trace.EVENT_NS
        root = ET.Element("Events")
        for rid, kind, offset, fields in events:
            if rid > end:
                break
            event = ET.SubElement(root, ns + "Event")
            system = ET.SubElement(event, ns + "System")
            ET.SubElement(system, ns + "EventID").text = str(kind)
            ET.SubElement(system, ns + "EventRecordID").text = str(rid)
            # Channel write time is after the frozen fixture window.
            ET.SubElement(system, ns + "TimeCreated", SystemTime=(cutoff + timedelta(seconds=1)).isoformat())
            data = ET.SubElement(event, ns + "EventData")
            fields = dict(fields, UtcTime=(start + timedelta(seconds=offset)).strftime("%Y-%m-%d %H:%M:%S.000"))
            for key, value in fields.items():
                ET.SubElement(data, ns + "Data", Name=key).text = value
        ET.ElementTree(root).write(path, encoding="utf-8")

    timestamps = []
    monkeypatch.setattr(journey, "now", lambda: timestamps.append(cutoff) or cutoff)
    monkeypatch.setattr(journey.time, "sleep", lambda _: None)
    monkeypatch.setattr(journey, "sysmon_tail", tail)
    monkeypatch.setattr(journey, "export_sysmon", export)
    manifest = {"start_utc": start.isoformat(), "sysmon_first_record": 11}
    if precision:
        manifest["collector_fixture_precision"] = True
    if expected:
        with pytest.raises(journey.trace.EvidenceValidationError, match=expected) as error:
            journey.verify_initial_sysmon(tmp_path, manifest, marker)
        assert "private" not in str(error.value).lower()
        if scenario in {"same-millisecond", "pid-reuse", "missing-creation-time"}:
            stdout = capsys.readouterr().out
            assert "private" not in stdout.lower()
            diagnostics = json.loads(stdout.split("birth diagnostics: ", 1)[1])
            expected_deltas = {
                "same-millisecond": (-5000, -6000, 1),
                "pid-reuse": (-20_005_000, -20_006_000, 0),
                "missing-creation-time": (-10_005_000, None, None),
            }
            start_delta, creation_delta, millisecond_matches = expected_deltas[scenario]
            assert diagnostics == {
                "outside_candidate_count": 1,
                "nearest_event_minus_start_ticks": start_delta,
                "nearest_event_minus_end_ticks": start_delta - 80_000_000,
                "creation_minus_start_ticks": 1000 if creation_delta is not None else None,
                "nearest_event_minus_creation_ticks": creation_delta,
                "same_creation_millisecond_count": millisecond_matches,
            }
        if scenario in {"tcp-absent", "udp-absent", "udp-before-birth", "udp-after-exit", "udp-outside-window"}:
            marker_state = {"udp-before-birth": {"before-child-birth": 1},
                            "udp-after-exit": {"after-child-exit": 1},
                            "udp-outside-window": {"outside-read-window": 1}}.get(scenario, {})
            counterpart = "udp" if protocol == "tcp" else "tcp"
            stdout = capsys.readouterr().out
            for private_field in ("private", "23551", "23552", "127.0.0.1", "413"):
                assert private_field not in stdout.lower()
            details = [json.loads(line.split("protocol diagnostics: ", 1)[1])
                       for line in stdout.splitlines() if "protocol diagnostics: " in line]
            assert details == [{"missing_in_child_lifetime": [protocol],
                                "matching_markers": {protocol: marker_state,
                                                     counterpart: {"in-child-lifetime": 1}},
                                "rejected_records": {"tcp": {}, "udp": {}},
                                "unparsed_outside_window": 0}] * reads
        if scenario in NETWORK_DIAGNOSTIC_CASES:
            _, _, missing, rejected, unparsed = NETWORK_DIAGNOSTIC_CASES[scenario]
            stdout = capsys.readouterr().out
            details = [json.loads(line.split("protocol diagnostics: ", 1)[1])
                       for line in stdout.splitlines() if "protocol diagnostics: " in line]
            assert details == [{
                "missing_in_child_lifetime": list(missing),
                "matching_markers": {"tcp": {} if "tcp" in missing else {"in-child-lifetime": 1}, "udp": {}},
                "rejected_records": {"tcp": {}, "udp": rejected},
                "unparsed_outside_window": unparsed,
            }] * reads
            for private_field in ("private", "23551", "23552", "23553", "127.0.0.1", "192.0.2.21", "413"):
                assert private_field not in stdout.lower()
    else:
        journey.verify_initial_sysmon(tmp_path, manifest, marker)
        output = capsys.readouterr().out
        assert f"passed on read {reads}" in output
        if precision:
            assert "matched fixture birth at Windows creation time" in output
        if scenario == "udp-delivered-on-second-read":
            assert output.count("protocol diagnostics:") == 1
            assert '"missing_in_child_lifetime": ["udp"]' in output
    assert len(calls) == reads and timestamps == [cutoff]
    assert len(set(exports)) == len(exports)


@pytest.mark.parametrize("approved", [False, True])
def test_collector_rehearsal_reuses_prelaunch_gate(tmp_path, monkeypatch, approved):
    root = tmp_path / "generated-rehearsal"
    monkeypatch.setenv("GITHUB_RUN_ATTEMPT", "1")
    monkeypatch.setenv("PILOTODIN_N12_COLLECTOR_REHEARSAL_CONSENT",
                       "I_APPROVE_ONE_N12_COLLECTOR_REHEARSAL" if approved else "")
    marker = {"pid": 23, "child_pid": 24, "port": 9030}
    start = datetime(2026, 11, 15, tzinfo=timezone.utc)
    events = []

    def channel_tail(*, timeout):
        assert timeout == 15
        events.append("record-floor")
        return 44

    def verify(first_root, manifest, fixture):
        assert first_root == root
        assert manifest == {"start_utc": start.isoformat(), "sysmon_first_record": 45,
                            "collector_fixture_precision": True}
        assert fixture is marker
        events.append("shared-guard")
        return 52

    def fixture_capture(capture_root, *, calibration_only, thread_context, verify_fixture):
        assert capture_root == root and calibration_only and not thread_context
        assert (root / "synthetic-protected").is_dir()
        events.append("fixture")
        records = verify_fixture(marker, journey.trace.utc_ticks(start))
        events.append("etw-stop")
        return {"fixture": marker, "sysmon": records}

    monkeypatch.setattr(journey, "sysmon_tail", channel_tail)
    monkeypatch.setattr(journey, "verify_initial_sysmon", verify)
    monkeypatch.setattr(journey.etw, "capture_fixture", fixture_capture)
    if not approved:
        with pytest.raises(journey.trace.EvidenceValidationError, match="separate first-run consent"):
            journey.etw.collector_rehearsal(root)
        assert not events and not root.exists()
        return
    capture = journey.etw.collector_rehearsal(root)
    assert capture["sysmon"] == {"first_record": 45, "prelaunch_last_record": 52}
    assert events == ["record-floor", "fixture", "shared-guard", "etw-stop"]


class Process:
    def __init__(self, pid):
        self.pid = pid

    def poll(self):
        return None

    def wait(self, timeout):
        return 0


def test_prepare_creates_scratch_only_in_the_driver_scope(tmp_path, monkeypatch):
    root = tmp_path / "capture"
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "local"))
    monkeypatch.setenv("APPDATA", str(tmp_path / "roaming"))
    monkeypatch.setenv("GITHUB_RUN_ID", "123")
    monkeypatch.setattr(journey.trace, "local_disposable_path", lambda path: path)
    # Windows path parsing is covered by the trace reducer tests.
    monkeypatch.setattr(journey.trace, "scope", lambda manifest: None)

    manifest, *_ = journey.prepare_journey(root, SOURCE, EXE_SHA)

    scratch = root / journey.DRIVER_TEMP_DIR
    assert scratch.is_dir()
    assert [role for role, paths in manifest["permitted_writes"].items() if str(scratch) in paths] == ["driver"]


@pytest.mark.parametrize("fault", [None, "first-calibration", "changed-binary", "no-profile-exit"])
def test_capture_brackets_journey_and_reduces_exact_artifacts(tmp_path, monkeypatch, fault):
    events = []
    root = tmp_path / "capture"
    root.mkdir()
    staged, home, profile, fixture = [tmp_path / name for name in ("build", "home", "webview", "quality.csv")]
    calibrations = [root / "calibration-first", root / "calibration-last"]
    user_temp = str(tmp_path / "user-temp")
    manifest = {"processes": [], "markers": {}, "source_sha": SOURCE,
                "executable_sha256": EXE_SHA, "loopback_ports": list(journey.PORTS)}
    sample = iter(range(30))
    monkeypatch.setattr(journey, "now", lambda: datetime(2026, 11, 14, tzinfo=timezone.utc)
                        + timedelta(seconds=next(sample)))
    monkeypatch.setenv("SystemRoot", str(tmp_path))
    monkeypatch.setenv("TEMP", user_temp)
    monkeypatch.setenv("TMP", user_temp)
    monkeypatch.setattr(journey, "prepare_journey", lambda *args: (manifest, home, profile, fixture, calibrations))
    monkeypatch.setattr(journey, "quiet", lambda *a, **kw: b"churn,amount\nY,2\n")
    monkeypatch.setattr(journey, "snapshots", lambda m: {"snapshot": len(events)})
    monkeypatch.setattr(journey, "sysmon_tail", lambda: 10 if "etw-start" not in events else 60)
    monkeypatch.setattr(journey, "start_capture", lambda *a: events.append("etw-start"))
    monkeypatch.setattr(journey.etw, "volume_devices", lambda: {"C:": r"\Device\HarddiskVolume1"})
    monkeypatch.setattr(journey.etw, "stop_trace", lambda *a: events.append("etw-stop") or {"buffers_written": 4})
    def sleep(seconds):
        if "calibration-first" not in events:
            assert events[-1] == "etw-start"
            assert manifest["start_utc"] == "2026-11-14T00:00:01+00:00"
            assert 0.001 < seconds <= 0.1
            events.append("initial-fixture-lead-in")
        else:
            events.append("drain" if "etw-stop" in events else "idle-observation")

    monkeypatch.setattr(journey.time, "sleep", sleep)

    def calibrate(directory, m):
        if directory == calibrations[0]:
            assert events[-1] == "initial-fixture-lead-in"
        events.append(directory.name)
        record = {"role": "calibration", "pid": len(events), "port": 20000 + len(events)}
        m["processes"].append(record)
        m["loopback_ports"].append(record["port"])
        return record

    def first_check(*args):
        events.append("sysmon-prelaunch-check")
        if fault == "first-calibration":
            raise journey.trace.EvidenceValidationError("fixture coverage blocked")

    def spawn(stack, m, role, command, env, cwd, log):
        events.append(log.stem)
        process = Process(len(events))
        if role == "app":
            assert env["WEBVIEW2_USER_DATA_FOLDER"] == str(profile)
            assert f"netlog-{log.stem.removeprefix('app-')}.json" in env["WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS"]
        if log.stem.startswith("driver-"):
            assert env["PILOTODIN_N12_QUALITY_FIXTURE"] == str(fixture)
            assert (command[-1] == "--verify-relaunch") == (log.stem == "driver-relaunch")
            assert env["TEMP"] == env["TMP"] == str(root / journey.DRIVER_TEMP_DIR)
        else:
            assert env["TEMP"] == env["TMP"] == user_temp
        m["processes"].append({"role": role, "pid": process.pid, "image": str(command[0])})
        stack.callback(events.append, f"cleanup-{log.stem}")
        return process

    def reverify(*args):
        if fault == "changed-binary" and "verify-binary" in events:
            raise journey.trace.EvidenceValidationError("executable changed")
        events.append("verify-binary")

    def powershell(path, *args, **kwargs):
        if args[0] == "process-bookend":
            assert len(args) == 1
            label = "process-bookend-after" if "etw-stop" in events else "process-bookend-before"
            events.append(label)
            return b'[{"pid": 702, "birth_ticks": 170}]'
        if args[0] == "close":
            events.append("graceful-close")
        elif args[0] == "profile-active":
            events.append("profile-exit")
            return b"1" if fault == "no-profile-exit" else b"0"
        elif args[0] == "etw-export":
            events.append("etw-export")
            (root / "etw.jsonl").write_bytes(b"evidence\n")
        else:
            pytest.fail(f"unexpected PowerShell call {args[0]}")

    def reduce(m, sysmon, file_trace, before, after, *, etw, private_endpoints,
               record_outside_writer, private_app_launches, journey_bookends, describe_path_gaps):
        events.append("reducer")
        assert sysmon.read_bytes() == b"record-bounded evidence"
        assert etw and m["etw"]["events_sha256"] == journey.build.digest(file_trace)
        assert m["sysmon_first_record"] == 11 and m["sysmon_last_record"] == 60
        assert list(m["markers"]) == list(journey.trace.MINIMUM_MARKERS)
        assert list(m["markers"].values()) == sorted(m["markers"].values())
        assert before != after
        assert describe_path_gaps
        assert journey_bookends == {"before": [{"pid": 702, "birth_ticks": 170}],
                                    "after": [{"pid": 702, "birth_ticks": 170}]}
        assert [p["role"] for p in m["processes"]].count("app") == 2
        private_endpoints.append({"role": "backend", "raw": "private-value"})
        record_outside_writer("driver", "write", (r"c:\private\driver.bin",), "node.exe")
        return {"coverage": "BLOCKED", "network": "BLOCKED", "filesystem": "BLOCKED"}

    monkeypatch.setattr(journey, "calibrate", calibrate)
    monkeypatch.setattr(journey, "verify_initial_sysmon", first_check)
    monkeypatch.setattr(journey, "spawn", spawn)
    monkeypatch.setattr(journey.build, "verify", reverify)
    monkeypatch.setattr(journey, "http_ready", lambda *args: True)
    monkeypatch.setattr(journey, "listening", lambda port: False)
    monkeypatch.setattr(journey, "wait_for", lambda check, seconds, message, process=None:
                        journey.trace.require(check(), message))
    monkeypatch.setattr(journey, "powershell", powershell)
    monkeypatch.setattr(journey, "export_sysmon", lambda first, last, path: path.write_bytes(b"record-bounded evidence"))
    monkeypatch.setattr(journey.trace, "audit", reduce)
    monkeypatch.setattr(journey, "diagnostic_paths", lambda *args: journey.OutsidePaths([]))

    if fault:
        with pytest.raises(journey.trace.EvidenceValidationError, match={
            "first-calibration": "fixture coverage", "changed-binary": "executable changed",
            "no-profile-exit": "WebView processes did not exit",
        }[fault]):
            journey.capture(root, staged, SOURCE, EXE_SHA, "node.exe")
        assert events[-1] == "etw-stop"
        assert "app-relaunch" not in events
        assert (("app-first" not in events) == (fault == "first-calibration"))
        assert not (root / "audit.json").exists()
    else:
        report = journey.capture(root, staged, SOURCE, EXE_SHA, "node.exe")
        assert report["coverage"] == "BLOCKED"
        assert events == ["process-bookend-before", "etw-start", "initial-fixture-lead-in", "calibration-first",
                          "sysmon-prelaunch-check", "idle-observation",
                          "backend", "vite", "verify-binary", "app-first", "driver-first", "graceful-close",
                          "profile-exit", "verify-binary", "app-relaunch", "driver-relaunch", "graceful-close",
                          "profile-exit", "cleanup-driver-relaunch", "cleanup-app-relaunch",
                          "cleanup-driver-first", "cleanup-app-first", "cleanup-vite", "cleanup-backend",
                          "calibration-last", "etw-stop", "process-bookend-after", "drain", "etw-export", "reducer"]
        public = (root / "audit.json").read_text()
        assert "private-value" not in public and "702" not in public
        assert json.loads((root / "private-process-bookends.json").read_text())["before"] == [
            {"pid": 702, "birth_ticks": 170},
        ]
        assert json.loads((root / "private-endpoints.json").read_text()) == [{"role": "backend", "raw": "private-value"}]
        assert report["journey_diagnostics"]["outside_scope_paths"] == [
            {"role": "driver", "operation": "write", "path_categories": ["other-path"], "count": 1},
        ]
        assert report["journey_diagnostics"]["outside_scope_writers"] == [
            {"role": "driver", "operation": "write", "path_categories": ["other-path"],
             "writer": "node", "count": 1},
        ]
