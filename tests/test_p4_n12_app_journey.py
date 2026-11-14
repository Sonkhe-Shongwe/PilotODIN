"""Exercise the N12 journey order and refusal paths without running Windows."""
from datetime import datetime, timedelta, timezone
import ipaddress
import json
import os
import subprocess
import sys

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
    monkeypatch.setattr(journey, "sysmon_tail", lambda: 20)
    monkeypatch.setattr(journey, "export_sysmon", lambda first, last, path: None)
    monkeypatch.setattr(journey.trace, "sysmon_events", lambda *args: (processes, connections, issues, 11, 20))
    if fault:
        with pytest.raises(journey.trace.EvidenceValidationError, match={
            "no-udp": "loopback TCP or UDP", "wrong-child": "fixture child", "gap": "sysmon-record-gap",
        }[fault]):
            journey.verify_initial_sysmon(tmp_path, manifest, record)
    else:
        journey.verify_initial_sysmon(tmp_path, manifest, record)


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
    monkeypatch.setattr(journey, "sysmon_tail", lambda: 10 if not events else 60)
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

    def reduce(m, sysmon, file_trace, before, after, *, etw, private_endpoints):
        events.append("reducer")
        assert sysmon.read_bytes() == b"record-bounded evidence"
        assert etw and m["etw"]["events_sha256"] == journey.build.digest(file_trace)
        assert m["sysmon_first_record"] == 11 and m["sysmon_last_record"] == 60
        assert list(m["markers"]) == list(journey.trace.MINIMUM_MARKERS)
        assert list(m["markers"].values()) == sorted(m["markers"].values())
        assert before != after
        assert [p["role"] for p in m["processes"]].count("app") == 2
        private_endpoints.append({"raw": "private-value"})
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
        assert events == ["etw-start", "calibration-first", "sysmon-prelaunch-check", "idle-observation",
                          "backend", "vite", "verify-binary", "app-first", "driver-first", "graceful-close",
                          "profile-exit", "verify-binary", "app-relaunch", "driver-relaunch", "graceful-close",
                          "profile-exit", "cleanup-driver-relaunch", "cleanup-app-relaunch",
                          "cleanup-driver-first", "cleanup-app-first", "cleanup-vite", "cleanup-backend",
                          "calibration-last", "etw-stop", "drain", "etw-export", "reducer"]
        assert "private-value" not in (root / "audit.json").read_text()
        assert json.loads((root / "private-endpoints.json").read_text()) == [{"raw": "private-value"}]
