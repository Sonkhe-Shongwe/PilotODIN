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


@pytest.mark.parametrize(("scenario", "expected", "reads"), [
    ("ready", None, 1),
    ("late", None, 2),
    ("empty-first-read", None, 2),
    ("missing", "parent-birth-missing", 2),
    ("mismatched", "parent-image-mismatch", 1),
    ("ambiguous", "parent-birth-ambiguous", 1),
    ("early-event", "parent-birth-before-window", 1),
    ("late-event", "parent-birth-after-window", 2),
    ("gap", "sysmon-record-gap", 1),
    ("regressed", "channel record ID regressed", 2),
    ("collector-change", "sysmon-restart-config-change-or-error", 2),
])
def test_prelaunch_reports_sysmon_delivery_and_identity(tmp_path, monkeypatch, capsys, scenario, expected, reads):
    start = datetime(2026, 11, 14, 0, 0, 10, tzinfo=timezone.utc)
    cutoff = start + timedelta(seconds=8)
    image = r"C:\Private\python.exe"
    parent = {"ProcessGuid": "private-parent", "ParentProcessGuid": "launcher", "ProcessId": "412",
              "Image": image, "Hashes": "SHA256=" + EXE_SHA}
    child = dict(parent, ProcessGuid="private-child", ParentProcessGuid="private-parent", ProcessId="413")
    marker = {"role": "calibration", "pid": 412, "child_pid": 413, "image": image, "port": 23551}
    udp = {"ProcessGuid": "private-child", "Protocol": "udp", "Initiated": "true",
           "DestinationIp": "127.0.0.1", "DestinationPort": "23551", "SourcePort": "23552"}
    events = [(11, 2, 0, {})]
    event_time = {"early-event": -1, "late-event": 9}.get(scenario, 1)
    if scenario == "mismatched":
        parent["Image"] = r"C:\Private\wrong.exe"
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
    if scenario == "ambiguous":
        events.append((18, 1, 6, dict(parent, ProcessGuid="another-parent")))
    if scenario == "collector-change":
        events.append((18, 16, 9, {}))

    last = events[-1][0]
    tails = {"late": [11, last], "empty-first-read": [10, last], "late-event": [11, last],
             "collector-change": [11, last], "regressed": [11, 10]}.get(scenario, [last] * reads)
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
    if expected:
        with pytest.raises(journey.trace.EvidenceValidationError, match=expected) as error:
            journey.verify_initial_sysmon(tmp_path, manifest, marker)
        assert "private" not in str(error.value).lower()
    else:
        journey.verify_initial_sysmon(tmp_path, manifest, marker)
        assert f"passed on read {reads}" in capsys.readouterr().out
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
        assert manifest == {"start_utc": start.isoformat(), "sysmon_first_record": 45}
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


@pytest.mark.parametrize("fault", [None, "first-calibration", "changed-binary", "no-profile-exit"])
def test_capture_brackets_journey_and_reduces_exact_artifacts(tmp_path, monkeypatch, fault):
    events = []
    root = tmp_path / "capture"
    root.mkdir()
    staged, home, profile, fixture = [tmp_path / name for name in ("build", "home", "webview", "quality.csv")]
    calibrations = [root / "calibration-first", root / "calibration-last"]
    manifest = {"processes": [], "markers": {}, "source_sha": SOURCE,
                "executable_sha256": EXE_SHA, "loopback_ports": list(journey.PORTS)}
    sample = iter(range(30))
    monkeypatch.setattr(journey, "now", lambda: datetime(2026, 11, 14, tzinfo=timezone.utc)
                        + timedelta(seconds=next(sample)))
    monkeypatch.setenv("SystemRoot", str(tmp_path))
    monkeypatch.setattr(journey, "prepare_journey", lambda *args: (manifest, home, profile, fixture, calibrations))
    monkeypatch.setattr(journey, "quiet", lambda *a, **kw: b"churn,amount\nY,2\n")
    monkeypatch.setattr(journey, "snapshots", lambda m: {"snapshot": len(events)})
    monkeypatch.setattr(journey, "sysmon_tail", lambda: 10 if "etw-start" not in events else 60)
    monkeypatch.setattr(journey, "start_capture", lambda *a: events.append("etw-start"))
    monkeypatch.setattr(journey.etw, "volume_devices", lambda: {"C:": r"\Device\HarddiskVolume1"})
    monkeypatch.setattr(journey.etw, "stop_trace", lambda *a: events.append("etw-stop") or {"buffers_written": 4})
    monkeypatch.setattr(journey.time, "sleep", lambda seconds: events.append("drain" if "etw-stop" in events else "idle-observation"))

    def calibrate(directory, m):
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
               record_outside_scope, private_app_launches, journey_bookends, describe_path_gaps):
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
        record_outside_scope("driver", "write", (r"c:\private\driver.bin",))
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
        assert events == ["process-bookend-before", "etw-start", "calibration-first",
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
