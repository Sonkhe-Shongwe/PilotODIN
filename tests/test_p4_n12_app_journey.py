"""Exercise the N12 journey order and refusal paths without running Windows."""
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
import hashlib
import ipaddress
import json
import os
import subprocess
import sys
from types import SimpleNamespace
from xml.etree import ElementTree as ET

import pytest

from qa.p4_native import n12_calibration, n12_lifetime_control
from qa.p4_research import n12_app_journey as journey
from qa.p4_research import n12_journey_diagnostics


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


@pytest.mark.parametrize(("filesystem", "network", "comparison", "exit_code"), [
    ("PASS_SCOPED", "PASS_SCOPED", "completed", 0),
    ("FAIL", "PASS_SCOPED", "completed", 2),
    ("PASS_SCOPED", "BLOCKED", "completed", 2),
    ("PASS_SCOPED", "PASS_SCOPED", "blocked", 2),
])
def test_hosted_journey_exit_checks_ordinary_results_and_comparison_completion(
    tmp_path, monkeypatch, capsys, filesystem, network, comparison, exit_code,
):
    staged = tmp_path / "build"
    report = {"filesystem": filesystem, "network": network, "webview_credit_comparison": {"status": comparison}}
    monkeypatch.setattr(sys, "argv", ["n12_app_journey", "--source", SOURCE, "--expected-exe-sha256", EXE_SHA])
    monkeypatch.setattr(os, "environ", {"PILOTODIN_N12_APP_JOURNEY_CONSENT": journey.CAPTURE_CONSENT})
    monkeypatch.setattr(journey.build, "stage_root", lambda _: staged)
    monkeypatch.setattr(journey.build, "verify", lambda *_: None)
    monkeypatch.setattr(journey, "listening", lambda _: False)
    monkeypatch.setattr(journey.shutil, "which", lambda _: "node.exe")
    monkeypatch.setattr(journey, "sysmon_tail", lambda: 1)
    monkeypatch.setattr(journey.trace, "local_disposable_path", lambda path, **_: path)

    def capture(root, build_root, source, executable, node):
        assert (root, build_root, source, executable, node) == (
            tmp_path / "build-journey", staged, SOURCE, EXE_SHA, "node.exe",
        )
        return report

    monkeypatch.setattr(journey, "capture", capture)
    assert journey.main() == exit_code
    assert json.loads(capsys.readouterr().out.splitlines()[-1]) == report


def test_calibration_existing_fixture_reports_fixed_stage_without_path(tmp_path):
    with pytest.raises(n12_calibration.CalibrationFailure, match=r"^N12 calibration failed at fixture-directory\.$"):
        n12_calibration.calibrate(tmp_path)
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize(("stderr", "stages"), [
    (b"N12 calibration failed at child-fixture-writes.\r\n"
     b"N12 calibration failed at tcp-marker.\r\n"
     b"N12 calibration failed at tcp-marker.\r\n"
     b"private/path\r\n", "child-fixture-writes, tcp-marker"),
    (b"N12 calibration failed at private/path.\n", "unclassified"),
])
def test_calibration_subprocess_preserves_only_fixed_failure_stages(tmp_path, monkeypatch, stderr, stages):
    def fail(command, **kwargs):
        assert kwargs["capture_output"] and kwargs["check"]
        raise subprocess.CalledProcessError(1, command, stderr=stderr)

    monkeypatch.setattr(journey.subprocess, "run", fail)
    manifest = {"processes": [], "loopback_ports": []}
    with pytest.raises(journey.trace.EvidenceValidationError) as caught:
        journey.calibrate(tmp_path / "calibration", manifest)
    assert str(caught.value) == f"calibration fixture subprocess failed at {stages}"
    assert manifest == {"processes": [], "loopback_ports": []}


@pytest.mark.parametrize("fault", [None, "fixture", "etw-loss"])
def test_initial_fixture_control_uses_journey_gate_and_stops_etw(tmp_path, monkeypatch, capsys, fault):
    root = tmp_path / "pilotodin-n12-build-123-journey"
    started = []
    steps = []
    monkeypatch.setenv("SystemRoot", str(tmp_path))
    monkeypatch.setattr(journey, "sysmon_tail", lambda: 25)
    monkeypatch.setattr(journey, "now", lambda: datetime(2026, 11, 18, tzinfo=timezone.utc))
    monkeypatch.setattr(journey.time, "sleep", lambda _: steps.append("lead-in"))

    def start_capture(capture_root, session, _logman):
        assert capture_root == root
        started.append(session)
        steps.append("etw-start")
        (root / "journey.etl").write_bytes(b"generated ETL")

    def calibrate(directory, manifest, *, child_hold_seconds):
        assert directory == root / "calibration-first"
        assert child_hold_seconds == 4
        assert manifest["sysmon_first_record"] == 26
        steps.append("fixture")
        if fault == "fixture":
            raise journey.trace.EvidenceValidationError("calibration fixture subprocess failed at udp-listener")
        return {"role": "calibration"}

    def verify(capture_root, manifest, record):
        assert capture_root == root and manifest["start_utc"] == "2026-11-18T00:00:00+00:00"
        assert record == {"role": "calibration"}
        steps.append("sysmon")

    def stop_capture(session):
        assert started == [session]
        steps.append("etw-stop")
        return {"events_lost": int(fault == "etw-loss"), "realtime_buffers_lost": 0,
                "log_buffers_lost": 0, "buffers_written": 1}

    monkeypatch.setattr(journey, "start_capture", start_capture)
    monkeypatch.setattr(journey, "calibrate", calibrate)
    monkeypatch.setattr(journey, "verify_initial_sysmon", verify)
    monkeypatch.setattr(journey.etw, "stop_trace", stop_capture)
    if fault:
        reason = "udp-listener" if fault == "fixture" else "lossy capture"
        with pytest.raises(journey.trace.EvidenceValidationError, match=reason):
            journey.capture_initial_fixture(root, SOURCE)
    else:
        journey.capture_initial_fixture(root, SOURCE)
    expected = ["etw-start", "lead-in", "fixture"]
    if fault != "fixture":
        expected.append("sysmon")
    assert steps == [*expected, "etw-stop"]
    output = capsys.readouterr().out
    assert ('"status": "PASS"' in output) == (fault is None)
    assert "executable_sha256" not in output


@pytest.mark.parametrize("approved,helper_fails", [(False, False), (True, False), (True, True)])
def test_prebuild_calibration_uses_separate_scratch_and_preserves_errors(
    tmp_path, monkeypatch, capsys, approved, helper_fails,
):
    staged = tmp_path / "pilotodin-n12-build-123"
    monkeypatch.setattr(journey.build, "stage_root", lambda _: staged)
    monkeypatch.setenv("PILOTODIN_N12_APP_JOURNEY_CONSENT", journey.CAPTURE_CONSENT if approved else "")
    checks = []

    def validate_path(path, *, runner_temp_only):
        assert runner_temp_only
        assert path == staged.with_name(f"{staged.name}-prebuild-calibration")
        return path

    def calibrate(directory, manifest):
        assert manifest == {"processes": [], "loopback_ports": []}
        checks.append(directory)
        if helper_fails:
            raise journey.trace.EvidenceValidationError("calibration fixture subprocess failed at udp-listener")

    monkeypatch.setattr(journey.trace, "local_disposable_path", validate_path)
    monkeypatch.setattr(journey, "calibrate", calibrate)
    if not approved or helper_fails:
        reason = "one-run N12 journey consent" if not approved else "udp-listener"
        with pytest.raises(journey.trace.EvidenceValidationError, match=reason):
            journey.run_prebuild_fixture(SOURCE)
    else:
        journey.run_prebuild_fixture(SOURCE)
    assert len(checks) == int(approved)
    assert ('"status": "PASS"' in capsys.readouterr().out) == (approved and not helper_fails)
    assert not staged.exists()


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
        journey.trace.Connection("child", 13, stamp(3), protocol, True, 2201, ipaddress.ip_address("127.0.0.1"), 2231)
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
    "udp-parent-inbound": ("child-loopback-tcp-or-udp-missing", 2, ("udp",),
                           {"other-process-at-fixture-port": 1}, 0),
    "udp-other-sender": ("child-loopback-tcp-or-udp-missing", 2, ("udp",),
                         {"other-process-at-fixture-port": 1}, 0),
    "udp-parent-inbound-outside": ("child-loopback-tcp-or-udp-missing", 2, ("udp",),
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
    ("socket-identity-conflicts", "connection-guid-unresolved-for-scoped-pid", 1),
    ("initial-socket-identity-conflicts", "connection-guid-unresolved-for-scoped-pid", 1),
    ("udp-before-birth", "connection-outside-process-lifetime", 1),
    ("udp-after-exit", "connection-outside-process-lifetime", 1),
    ("udp-outside-window", "child-loopback-tcp-or-udp-missing", 2),
    ("udp-delivered-on-second-read", None, 2),
    ("final-udp-delivered-on-second-read", None, 2),
    ("final-tcp-absent", "child-loopback-tcp-or-udp-missing", 2),
    ("final-udp-outside-window", "child-loopback-tcp-or-udp-missing", 2),
    ("final-socket-identity-conflicts", "connection-guid-unresolved-for-scoped-pid", 1),
    *((scenario, values[0], values[1]) for scenario, values in NETWORK_DIAGNOSTIC_CASES.items()),
])
def test_prelaunch_reports_sysmon_delivery_and_identity(tmp_path, monkeypatch, capsys, scenario, expected, reads):
    phase = "final" if scenario.startswith("final-") else "initial"
    scenario = scenario.removeprefix("final-")
    start = datetime(2026, 11, 14, 0, 0, 10, 500, tzinfo=timezone.utc)
    cutoff = start + timedelta(seconds=8)
    image = r"C:\Private\python.exe"
    parent = {"ProcessGuid": "private-parent", "ParentProcessGuid": "launcher", "ProcessId": "412",
              "Image": image, "Hashes": "SHA256=" + EXE_SHA}
    child = dict(parent, ProcessGuid="private-child", ParentProcessGuid="private-parent", ProcessId="413")
    marker = {"role": "calibration", "pid": 412, "child_pid": 413, "image": image, "port": 23551}
    udp = {"ProcessGuid": "private-child", "ProcessId": "413", "Protocol": "udp", "Initiated": "true",
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
    if scenario == "socket-identity-conflicts":
        marker.update(tcp_sender_port=23553, udp_sender_port=23552)
        events[3] = (birth_id + 2, 3, 3, dict(udp, Protocol="tcp", SourcePort="23553",
                                              ProcessGuid="private-system-guid", ProcessId="4"))
        events[4] = (birth_id + 3, 3, 3, dict(udp, ProcessGuid="private-unrelated"))
    if scenario == "initial-socket-identity-conflicts":
        marker.update(tcp_sender_port=23553, udp_sender_port=23552)
        events[3] = (birth_id + 2, 3, 3, dict(udp, Protocol="tcp", SourcePort="23553",
                                              ProcessGuid="private-unrelated"))
        events[4] = (birth_id + 3, 3, 5, dict(udp, ProcessGuid="private-unrelated"))
    udp_changes = {
        "udp-other-process": {"ProcessGuid": "private-unrelated", "ProcessId": "999"},
        "udp-parent-inbound": {"ProcessGuid": "private-parent", "ProcessId": "412", "Initiated": "false"},
        "udp-other-sender": {"ProcessGuid": "private-unrelated", "ProcessId": "999", "SourcePort": "23553"},
        "udp-parent-inbound-outside": {"ProcessGuid": "private-parent", "ProcessId": "412", "Initiated": "false"},
        "udp-unrelated": {"ProcessGuid": "private-unrelated", "ProcessId": "999", "DestinationPort": "23553"},
        "udp-not-initiated": {"Initiated": "false"},
        "udp-off-loopback": {"DestinationIp": "192.0.2.21"},
        "udp-wrong-port": {"DestinationPort": "23553"},
        "udp-unparsed-outside": {"DestinationIp": "private-invalid-address"},
    }
    if scenario in {"udp-parent-inbound", "udp-other-sender", "udp-parent-inbound-outside"}:
        marker["udp_sender_port"] = 23552
    if scenario in udp_changes:
        offset = 9 if scenario in {"udp-unparsed-outside", "udp-parent-inbound-outside"} else 3
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

    def verify():
        if phase == "initial":
            return journey.verify_initial_sysmon(tmp_path, manifest, marker)
        return journey.verify_fixture_sysmon(tmp_path, 11, start, cutoff, marker, phase="final")

    if expected:
        with pytest.raises(journey.trace.EvidenceValidationError, match=expected) as error:
            verify()
        assert "private" not in str(error.value).lower()
        if scenario in {"socket-identity-conflicts", "initial-socket-identity-conflicts"}:
            stdout = capsys.readouterr().out
            details = [json.loads(line.split("socket identity diagnostics: ", 1)[1])
                       for line in stdout.splitlines() if "socket identity diagnostics: " in line]
            expected_details = {
                "tcp": {"guid-other:pid-system:outbound:in-child-lifetime": 1},
                "udp": {"guid-other:pid-child:outbound:in-child-lifetime": 1},
            } if scenario == "socket-identity-conflicts" else {
                "tcp": {"guid-other:pid-child:outbound:in-child-lifetime": 1},
                "udp": {"guid-other:pid-child:outbound:after-child": 1},
            }
            assert details == [expected_details]
            assert "child-loopback-tcp-or-udp-missing" in str(error.value)
            for private_field in ("private", "23551", "23552", "23553", "127.0.0.1", "413"):
                assert private_field not in stdout.lower()
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
                                "unparsed_outside_window": 0,
                                "udp_other_at_fixture_port": {}}] * reads
        if scenario in NETWORK_DIAGNOSTIC_CASES:
            _, _, missing, rejected, unparsed = NETWORK_DIAGNOSTIC_CASES[scenario]
            stdout = capsys.readouterr().out
            details = [json.loads(line.split("protocol diagnostics: ", 1)[1])
                       for line in stdout.splitlines() if "protocol diagnostics: " in line]
            udp_at_fixture = {
                "udp-other-process": "other-process:outbound:sender-port-unavailable:in-window",
                "udp-parent-inbound": "parent:inbound:fixture-sender-port:in-window",
                "udp-other-sender": "other-process:outbound:different-source-port:in-window",
                "udp-parent-inbound-outside": "parent:inbound:fixture-sender-port:outside-window",
            }.get(scenario)
            assert details == [{
                "missing_in_child_lifetime": list(missing),
                "matching_markers": {"tcp": {} if "tcp" in missing else {"in-child-lifetime": 1}, "udp": {}},
                "rejected_records": {"tcp": {}, "udp": rejected},
                "unparsed_outside_window": unparsed,
                "udp_other_at_fixture_port": {udp_at_fixture: 1} if udp_at_fixture else {},
            }] * reads
            for private_field in ("private", "23551", "23552", "23553", "127.0.0.1", "192.0.2.21", "413"):
                assert private_field not in stdout.lower()
    else:
        assert verify() == last
        output = capsys.readouterr().out
        assert f"N12 {phase} Sysmon calibration passed on read {reads}" in output
        if precision:
            assert "matched fixture birth at Windows creation time" in output
        if scenario == "udp-delivered-on-second-read":
            assert output.count("protocol diagnostics:") == 1
            assert '"missing_in_child_lifetime": ["udp"]' in output
    assert len(calls) == reads and timestamps == ([cutoff] if phase == "initial" else [])
    assert len(set(exports)) == len(exports)
    assert all(path.startswith(f"{phase}-sysmon-") for path in exports)


@pytest.mark.parametrize("approved", [False, True])
@pytest.mark.parametrize("rundown", [False, True])
def test_collector_rehearsal_reuses_prelaunch_gate(tmp_path, monkeypatch, approved, rundown):
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

    @contextmanager
    def fileio_rundown(capture_root):
        assert capture_root == root
        events.append("rundown-start")
        yield lambda: events.append("rundown-stop")

    def fixture_capture(capture_root, *, calibration_only, thread_context, verify_fixture, before_stop=None):
        assert capture_root == root and calibration_only and not thread_context
        assert (root / "synthetic-protected").is_dir()
        events.append("fixture")
        records = verify_fixture(marker, journey.trace.utc_ticks(start))
        if before_stop is not None:
            before_stop()
        events.append("etw-stop")
        return {"fixture": marker, "sysmon": records}

    monkeypatch.setattr(journey, "sysmon_tail", channel_tail)
    monkeypatch.setattr(journey, "verify_initial_sysmon", verify)
    monkeypatch.setattr(journey.etw, "capture_fixture", fixture_capture)
    monkeypatch.setattr(journey.etw, "collect_fileio_rundown", fileio_rundown)
    if not approved:
        with pytest.raises(journey.trace.EvidenceValidationError, match="separate first-run consent"):
            journey.etw.collector_rehearsal(root, rundown=rundown)
        assert not events and not root.exists()
        return
    capture = journey.etw.collector_rehearsal(root, rundown=rundown)
    assert capture["sysmon"] == {"first_record": 45, "prelaunch_last_record": 52}
    expected = ["record-floor", "fixture", "shared-guard", "etw-stop"]
    if rundown:
        expected[1:1] = ["rundown-start"]
        expected[-1:-1] = ["rundown-stop"]
    assert events == expected


class Process:
    def __init__(self, pid):
        self.pid = pid

    def poll(self):
        return None

    def wait(self, timeout):
        return 0


def test_failed_driver_log_reports_a_fixed_checkpoint_and_category(tmp_path):
    log = tmp_path / "driver.log"
    log.write_bytes(b"N1 private input: PASS\nNATIVE PROJECT SWITCH BLOCKED: private path\n")
    assert journey.driver_failure(log, "first", 3) == {
        "launch": "first", "return_code": 3, "last_checkpoint": "N1", "failure": "native-project-switch",
    }


def test_prepare_creates_disposable_app_and_driver_scratch(tmp_path, monkeypatch):
    root = tmp_path / "capture"
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "local"))
    monkeypatch.setenv("APPDATA", str(tmp_path / "roaming"))
    monkeypatch.setenv("GITHUB_RUN_ID", "123")
    monkeypatch.setattr(journey.trace, "local_disposable_path", lambda path: path)
    # Windows path parsing is covered by the trace reducer tests.
    monkeypatch.setattr(journey.trace, "scope", lambda manifest: None)

    manifest, _, profile, *_ = journey.prepare_journey(root, SOURCE, EXE_SHA)

    scratch = root / journey.DRIVER_TEMP_DIR
    assert scratch.is_dir()
    assert [role for role, paths in manifest["permitted_writes"].items() if str(scratch) in paths] == ["driver"]
    assert (profile / journey.APP_TEMP_DIR).is_dir()
    assert manifest["permitted_writes"]["webview"] == [str(profile)]


@pytest.mark.parametrize("fault", [None, "first-calibration", "changed-binary", "no-profile-exit",
                                    "sysmon-export", "sysmon-parse", "changed-protected", "absent-fixture",
                                    "etw-export", "etw-reduce", "backend-snapshot-unavailable",
                                    "app-and-cleanup", "etw-stop", "driver-readiness-missing",
                                    "final-calibration", "final-export-regressed",
                                    "credit-reduce", "credit-reconcile", "fileio", "fileio-stop-failed"])
def test_capture_brackets_journey_and_reduces_exact_artifacts(tmp_path, monkeypatch, capsys, fault):
    events = []
    root = tmp_path / "capture"
    root.mkdir()
    staged, home, profile, fixture = [tmp_path / name for name in ("build", "home", "webview", "quality.csv")]
    calibrations = [root / "calibration-first", root / "calibration-last"]
    user_temp = str(tmp_path / "user-temp")
    user_cache = str(tmp_path / "user-cache")
    manifest = {"processes": [], "markers": {}, "source_sha": SOURCE,
                "executable_sha256": EXE_SHA, "loopback_ports": list(journey.PORTS),
                "protected_roots": {"local-original": r"c:\private\original"},
                "observed_roots": {"quality-source": r"c:\private\fixture.csv",
                                   "qa-home": r"c:\private\qa-home"},
                "immutable_observed": ["quality-source"]}
    sample = iter(range(30))
    monkeypatch.setattr(journey, "now", lambda: datetime(2026, 11, 14, tzinfo=timezone.utc)
                        + timedelta(seconds=next(sample)))
    monkeypatch.setenv("SystemRoot", str(tmp_path))
    monkeypatch.setenv("TEMP", user_temp)
    monkeypatch.setenv("TMP", user_temp)
    monkeypatch.setenv("PSMODULEANALYSISCACHEPATH", user_cache)
    monkeypatch.setattr(journey, "prepare_journey", lambda *args: (manifest, home, profile, fixture, calibrations))
    monkeypatch.setattr(journey, "quiet", lambda *a, **kw: b"churn,amount\nY,2\n")
    monkeypatch.setattr(n12_lifetime_control, "process_images", lambda _: {
        "image_dos": r"c:\private\app.exe", "image_native": r"\Device\HarddiskVolume1\private\app.exe",
    })
    monkeypatch.setattr(n12_lifetime_control, "process_times",
                        lambda process: {"pid": process.pid, "birth": 170, "exit": 200})
    def endpoint_snapshots(m):
        after = "snapshot-after-start" in m["markers"]
        assert "etw-start" in events and "etw-stop" not in events
        assert ("snapshot-before-start" in m["markers"]) and ("snapshot-before-end" in m["markers"]) == after
        states = {"quality-source": "absent" if fault == "absent-fixture" else "file",
                  "qa-home": "directory" if after else "absent",
                  "local-original": "directory" if after and fault == "changed-protected" else "absent"}
        digests = {"absent": "a" * 64, "file": "b" * 64, "directory": "c" * 64}
        return {group: {label: {"root_id": hashlib.sha256(journey.trace.windows_path(path).encode()).hexdigest(),
                                "state": states[label], "digest": digests[states[label]]}
                        for label, path in m[f"{group}_roots"].items()}
                for group in ("protected", "observed")}

    monkeypatch.setattr(journey, "snapshots", endpoint_snapshots)
    def sysmon_tail():
        if fault == "final-export-regressed" and "sysmon-final-check" in events:
            return 59
        return 10 if "etw-start" not in events else 60

    monkeypatch.setattr(journey, "sysmon_tail", sysmon_tail)
    monkeypatch.setattr(journey, "start_capture", lambda *a: events.append("etw-start"))
    monkeypatch.setattr(journey.etw, "volume_devices", lambda: {"C:": r"\Device\HarddiskVolume1"})
    fileio = fault in {"fileio", "fileio-stop-failed"}
    if fileio:
        monkeypatch.setenv("PILOTODIN_N12_APP_RUNDOWN_CONSENT", "I_APPROVE_ONE_N12_APP_RUNDOWN")

        @contextmanager
        def recorder(directory):
            assert directory == root and events[-1] == "etw-start"
            events.append("fileio-start")
            def stop():
                assert "end_utc" in manifest and events[-1] == "calibration-last"
                events.append("fileio-stop")
                if fault == "fileio-stop-failed":
                    raise RuntimeError("private-recorder-error")
                return journey.trace.utc_ticks(journey.now())
            yield stop

        def compare(directory, m, observed, file_trace, bookends, baseline, window):
            assert events[-1] == "credit-reducer"
            events.append("fileio-comparison")
            assert directory == root and file_trace == root / "etw.jsonl"
            assert journey.trace.utc_time(m["end_utc"]) < window[0] <= window[1] <= journey.trace.utc_time(
                m["etw"]["end_utc"])
            assert "webview_credit_comparison" in baseline and bookends["threads_before"] == bookends["threads_after"]
            return {"status": "completed"}

        monkeypatch.setattr(journey.etw, "collect_fileio_rundown", recorder)
        monkeypatch.setattr(journey, "compare_background_paths", compare)
    def stop_trace(session):
        events.append("etw-stop")
        if fault in {"app-and-cleanup", "etw-stop"}:
            raise RuntimeError("private-etw-stop-value")
        return {"buffers_written": 4}

    monkeypatch.setattr(journey.etw, "stop_trace", stop_trace)
    def sleep(seconds):
        if "calibration-first" not in events:
            assert events[-1] == ("fileio-start" if fileio else "etw-start")
            assert manifest["start_utc"] == "2026-11-14T00:00:01+00:00"
            assert 0.001 < seconds <= 0.1
            events.append("initial-fixture-lead-in")
        elif events[-1] == "cleanup-backend":
            assert 0.001 < seconds <= 0.1
            events.append("final-fixture-lead-in")
        else:
            events.append("drain" if "etw-stop" in events else "idle-observation")

    monkeypatch.setattr(journey.time, "sleep", sleep)

    def calibrate(directory, m, *, child_hold_seconds=0):
        if directory == calibrations[0]:
            assert events[-1] == "initial-fixture-lead-in"
        else:
            assert directory == calibrations[1]
            assert events[-1] == "final-fixture-lead-in"
        assert child_hold_seconds == 4
        events.append(directory.name)
        record = {"role": "calibration", "pid": len(events), "port": 20000 + len(events)}
        m["processes"].append(record)
        m["loopback_ports"].append(record["port"])
        return record

    def first_check(*args):
        events.append("sysmon-prelaunch-check")
        if fault == "first-calibration":
            raise journey.trace.EvidenceValidationError("fixture coverage blocked")

    def final_check(path, first, start, end, record, *, phase):
        assert path == root and first == 11 and phase == "final"
        assert events[-2:] == ["process-bookend-after", "drain"]
        assert journey.trace.utc_time(manifest["markers"]["exit"]) < start < end
        assert end < journey.trace.utc_time(manifest["end_utc"])
        assert record is manifest["processes"][-1] and record["role"] == "calibration"
        events.append("sysmon-final-check")
        if fault == "final-calibration":
            raise journey.trace.EvidenceValidationError("final fixture TCP or UDP evidence missing")
        return 60

    def spawn(stack, m, role, command, env, cwd, log):
        events.append(log.stem)
        process = Process(len(events))
        if role == "app":
            assert env["WEBVIEW2_USER_DATA_FOLDER"] == str(profile)
            assert f"netlog-{log.stem.removeprefix('app-')}.json" in env["WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS"]
            assert env["TEMP"] == env["TMP"] == env["TMPDIR"] == str(profile / journey.APP_TEMP_DIR)
            assert env["PSMODULEANALYSISCACHEPATH"] == user_cache
        elif role == "driver":
            scratch = root / journey.DRIVER_TEMP_DIR
            assert env["TEMP"] == env["TMP"] == env["TMPDIR"] == str(scratch)
            assert env["PSMODULEANALYSISCACHEPATH"] == str(scratch / "powershell-module-analysis-cache")
        else:
            assert env["TEMP"] == env["TMP"] == user_temp
            assert env["PSMODULEANALYSISCACHEPATH"] == user_cache
        if log.stem == "vite":
            assert command[-2:] == ["--configLoader", "runner"]
        if log.stem.startswith("driver-"):
            assert env["PILOTODIN_N12_QUALITY_FIXTURE"] == str(fixture)
            assert (command[-1] == "--verify-relaunch") == (log.stem == "driver-relaunch")
            log.write_text("earlier probe output\n" if fault == "driver-readiness-missing"
                           else "N12 native close listener ready\n", encoding="utf-8")
        m["processes"].append({"role": role, "pid": process.pid, "image": str(command[0])})
        stack.callback(events.append, f"cleanup-{log.stem}")
        if fault == "app-and-cleanup" and log.stem == "backend":
            def fail_cleanup():
                raise RuntimeError("private-process-cleanup-value")
            stack.callback(fail_cleanup)
        return process

    def reverify(*args):
        if fault in {"changed-binary", "app-and-cleanup"} and "verify-binary" in events:
            raise journey.trace.EvidenceValidationError("executable changed")
        events.append("verify-binary")

    def powershell(path, *args, **kwargs):
        if args[0] == "process-bookend":
            assert len(args) == 1
            label = "process-bookend-after" if "etw-stop" in events else "process-bookend-before"
            events.append(label)
            return b'{"processes":[{"pid":702,"birth_ticks":170}],"threads":[{"pid":702,"tid":703,"birth_ticks":180}]}'
        if args[0] == "backend-tcp":
            assert args == ("backend-tcp", "-BackendProcessId", events.index("backend") + 1)
            events.append("backend-snapshot")
            if fault == "backend-snapshot-unavailable":
                return b'{"pid": 999, "birth_ticks": 170, "observed_ticks": 200, "sockets": []}'
            return json.dumps({"pid": args[-1], "birth_ticks": 170,
                               "observed_ticks": 200, "sockets": []}).encode()
        if args[0] == "close":
            assert args[-1] == "-ReportCloseStatus"
            events.append("graceful-close")
        elif args[0] == "webview-children":
            assert args[1] == "-AppProcessId"
            return b"[]"
        elif args[0] == "profile-active":
            events.append("profile-exit")
            return b"1" if fault == "no-profile-exit" else b"0"
        elif args[0] == "etw-export":
            events.append("etw-export")
            if fault == "etw-export":
                raise subprocess.CalledProcessError(1, "etw-export")
            (root / "etw.jsonl").write_bytes(b"evidence\n")
        else:
            pytest.fail(f"unexpected PowerShell call {args[0]}")

    def inspect_sysmon(m, sysmon, *, etw, private_endpoints, private_app_launches, rejected_sysmon_exits):
        events.append("sysmon-reducer")
        assert sysmon.read_bytes() == b"record-bounded evidence"
        assert etw and "etw-export" not in events
        assert m["sysmon_first_record"] == 11 and m["sysmon_last_record"] == 60
        assert [name for name in m["markers"] if name in journey.trace.MINIMUM_MARKERS] == list(
            journey.trace.MINIMUM_MARKERS)
        assert all(name in m["markers"] for name in (
            "snapshot-before-start", "snapshot-before-end",
            "snapshot-after-start", "snapshot-after-end"))
        assert list(m["markers"].values()) == sorted(m["markers"].values())
        assert [p["role"] for p in m["processes"]].count("app") == 2
        if fault in {"sysmon-parse", "changed-protected", "absent-fixture"}:
            rejected_sysmon_exits.append({"record": 159, "category": "text-placeholder"})
            raise journey.trace.EvidenceValidationError("Sysmon XML: unsupported exit image form")
        private_endpoints.append({"role": "backend", "raw": "private-value"})
        return observed

    observed = SimpleNamespace(
        issues={"sysmon-exit-time-unverified"}, network_counts={"backend:tcp:unexpected-loopback": 1},
        unexpected_connections=[{"role": "backend", "protocol": "tcp", "kind": "unexpected-loopback"}],
        bindings=[], processes={}, roles={},
    )

    def lifetime_report(etw_records, devices, window, sysmon_observed, witnesses, digest, issues):
        assert sysmon_observed is observed and digest == EXE_SHA and isinstance(issues, frozenset)
        assert witnesses["first"]["pid"] != witnesses["relaunch"]["pid"]
        assert witnesses["first"]["image_dos"] == r"c:\private\app.exe"
        return {"scope": "diagnostic-only-before-file-correlation", "launches": {
            "first": {"handle": "MATCH"}, "relaunch": {"handle": "MATCH"},
        }}

    monkeypatch.setattr(journey, "journey_lifetime_evidence", lifetime_report)

    write_gap = "webview-network:write:path-missing"
    unrelated_gap = "backend:write:path-missing"

    def reduce(m, sysmon_observed, file_trace, before, after, *, etw, journey_bookends, describe_path_gaps,
               webview_dominant_writes, record_outside_writer=None, observe_lifetimes=None,
               credit_verified_webview_writes=False):
        assert sysmon_observed is observed
        assert etw and m["etw"]["events_sha256"] == journey.build.digest(file_trace)
        assert before != after
        assert describe_path_gaps and webview_dominant_writes
        assert journey_bookends == {"before": [{"pid": 702, "birth_ticks": 170}],
                                    "after": [{"pid": 702, "birth_ticks": 170}],
                                    "threads_before": [{"pid": 702, "tid": 703, "birth_ticks": 180}],
                                    "threads_after": [{"pid": 702, "tid": 703, "birth_ticks": 180}]}
        findings = {"coverage": "BLOCKED", "network": "BLOCKED", "filesystem": "BLOCKED",
                    "coverage_issues": ["etw-mutation-coverage-unresolved"],
                    "file_events": {}, "file_violations": {"outside-scope:driver:write": 1},
                    "etw_unresolved_mutations": {write_gap: 3, unrelated_gap: 1}}
        if credit_verified_webview_writes:
            events.append("credit-reducer")
            assert observe_lifetimes is None
            assert file_trace == root / "etw.jsonl"
            assert json.loads((root / "audit.json").read_text())["etw_unresolved_mutations"] == {
                write_gap: 3, unrelated_gap: 1,
            }
            if fault == "credit-reduce":
                raise ValueError("private-credit-reducer-value")
            record_outside_writer("driver", "write", (r"c:\private\driver.bin",), "node.exe")
            record_outside_writer("webview-network", "write", (r"c:\private\webview.cache",), "msedgewebview2.exe")
            findings["file_violations"]["outside-scope:webview-network:write"] = 1
            findings["etw_unresolved_mutations"][write_gap] = 1
            findings["etw_webview_write_credit"] = {
                "status": "compared", "credited_paths": {"permitted": 1, "outside-scope": 1},
                "remaining_path_gaps": 0 if fault == "credit-reconcile" else 1,
            }
            return findings
        events.append("reducer")
        observe_lifetimes([], {}, (0, 1), frozenset(observed.issues))
        if fault == "etw-reduce":
            raise journey.trace.EvidenceValidationError("invalid ETW evidence")
        record_outside_writer("driver", "write", (r"c:\private\driver.bin",), "node.exe")
        return findings

    monkeypatch.setattr(journey, "calibrate", calibrate)
    monkeypatch.setattr(journey, "verify_initial_sysmon", first_check)
    monkeypatch.setattr(journey, "verify_fixture_sysmon", final_check)
    monkeypatch.setattr(journey, "spawn", spawn)
    monkeypatch.setattr(journey.build, "verify", reverify)
    monkeypatch.setattr(journey, "http_ready", lambda *args: True)
    monkeypatch.setattr(journey, "listening", lambda port: False)
    monkeypatch.setattr(journey, "wait_for", lambda check, seconds, message, process=None:
                        journey.trace.require(check(), message))
    monkeypatch.setattr(journey, "powershell", powershell)
    def export_sysmon(first, last, path):
        if fault == "sysmon-export":
            raise journey.trace.EvidenceValidationError("Sysmon export failed")
        path.write_bytes(b"record-bounded evidence")

    monkeypatch.setattr(journey, "export_sysmon", export_sysmon)
    monkeypatch.setattr(journey.trace, "inspect_journey_sysmon", inspect_sysmon)
    monkeypatch.setattr(journey.trace, "complete_journey_audit", reduce)
    monkeypatch.setattr(journey, "diagnostic_paths", lambda *args: journey.OutsidePaths([]))
    monkeypatch.setattr(n12_journey_diagnostics, "local_disposable_path", lambda path, **options: path)

    if fault in {"first-calibration", "changed-binary", "no-profile-exit", "app-and-cleanup", "etw-stop",
                 "driver-readiness-missing"}:
        if fault == "etw-stop":
            with pytest.raises(RuntimeError, match="private-etw-stop-value"):
                journey.capture(root, staged, SOURCE, EXE_SHA, "node.exe")
        else:
            with pytest.raises(journey.trace.EvidenceValidationError, match={
                "first-calibration": "fixture coverage", "changed-binary": "executable changed",
                "no-profile-exit": "WebView processes did not exit", "app-and-cleanup": "executable changed",
                "driver-readiness-missing": "first native close listener was not verified",
            }[fault]):
                journey.capture(root, staged, SOURCE, EXE_SHA, "node.exe")
        assert events[-1] == "etw-stop"
        assert ("app-relaunch" in events) == (fault == "etw-stop")
        assert (("app-first" not in events) == (fault == "first-calibration"))
        assert not (root / "audit.json").exists()
        output = capsys.readouterr().out
        assert "N12 protected endpoint snapshots" not in output
        assert "private-process-cleanup-value" not in output and "private-etw-stop-value" not in output
        records = [json.loads(line.removeprefix("N12 checkpoint ")) for line in output.splitlines()
                   if line.startswith("N12 checkpoint ")]
        assert records[0] == {"stage": "etw-start", "status": "completed",
                              "source_sha": SOURCE, "executable_sha256": EXE_SHA}
        stages = [(record["stage"], record["status"]) for record in records]
        if fault == "app-and-cleanup":
            assert stages[-4:] == [("app-journey", "interrupted"), ("process-cleanup", "interrupted"),
                                   ("capture", "interrupted"), ("etw-stop", "interrupted")]
        if fault == "etw-stop":
            assert stages[-2:] == [("protected-after-scan", "completed"), ("etw-stop", "interrupted")]
        return

    comparison_faults = {"credit-reduce": "ValueError", "credit-reconcile": "EvidenceValidationError"}
    completed_baseline = {None, "backend-snapshot-unavailable", "final-calibration",
                          "fileio", "fileio-stop-failed", *comparison_faults}
    if fault not in completed_baseline:
        error, message = {
            "sysmon-export": (journey.trace.EvidenceValidationError, "Sysmon export failed"),
            "final-export-regressed": (journey.trace.EvidenceValidationError, "record ID regressed after final fixture"),
            "etw-export": (subprocess.CalledProcessError, "etw-export"),
            "etw-reduce": (journey.trace.EvidenceValidationError, "invalid ETW evidence"),
        }.get(fault, (journey.trace.EvidenceValidationError, "unsupported exit image form"))
        with pytest.raises(error, match=message):
            journey.capture(root, staged, SOURCE, EXE_SHA, "node.exe")
        assert not (root / "audit.json").exists()
    else:
        report = journey.capture(root, staged, SOURCE, EXE_SHA, "node.exe")
        assert report["coverage"] == "BLOCKED"
        assert events == ["process-bookend-before", "etw-start", *(["fileio-start"] if fileio else []),
                          "initial-fixture-lead-in", "calibration-first",
                          "sysmon-prelaunch-check", "idle-observation",
                          "backend", "vite", "backend-snapshot", "verify-binary", "app-first", "driver-first", "graceful-close",
                          "profile-exit", "verify-binary", "app-relaunch", "driver-relaunch", "graceful-close",
                          "profile-exit", "cleanup-driver-relaunch", "cleanup-app-relaunch",
                          "cleanup-driver-first", "cleanup-app-first", "cleanup-vite", "cleanup-backend",
                          "final-fixture-lead-in", "calibration-last", *(["fileio-stop"] if fileio else []),
                          "etw-stop", "process-bookend-after", "drain",
                          "sysmon-final-check", "sysmon-reducer",
                          "etw-export", "reducer", "credit-reducer",
                          *(["fileio-comparison"] if fault == "fileio" else [])]
        if fileio:
            assert report["background_rundown_comparison"] == (
                {"status": "completed"} if fault == "fileio" else
                {"status": "blocked", "error": "recorder-stop-failed"})
        public = (root / "audit.json").read_text()
        assert "private-value" not in public and "702" not in public
        assert "webview_credit_comparison" not in json.loads(public)
        assert report["etw_unresolved_mutations"] == {write_gap: 3, unrelated_gap: 1}
        comparison = report["webview_credit_comparison"]
        comparison_path = root / "webview-credit-comparison.json"
        assert comparison["etw_events_sha256"] == manifest["etw"]["events_sha256"]
        assert comparison["baseline_webview_write_path_gaps"] == 3
        if fault in comparison_faults:
            assert comparison["status"] == "blocked" and comparison["error"] == comparison_faults[fault]
            assert "private-credit-reducer-value" not in json.dumps(report)
            assert not comparison_path.exists()
        else:
            assert json.loads(comparison_path.read_text()) == comparison
            assert comparison["status"] == "completed"
            assert comparison["etw_unresolved_mutations"] == {write_gap: 1, unrelated_gap: 1}
            assert comparison["file_violations"] == {
                **report["file_violations"], "outside-scope:webview-network:write": 1,
            }
            assert comparison["outside_scope_webview_writes"] == [{
                "role": "webview-network", "operation": "write", "path_categories": ["other-path"],
                "writer": "webview2", "count": 1,
            }]
            assert "private" not in json.dumps(comparison["outside_scope_webview_writes"])
            assert comparison["network"] == report["network"]
        assert json.loads((root / "private-process-bookends.json").read_text())["before"] == [
            {"pid": 702, "birth_ticks": 170},
        ]
        assert json.loads((root / "private-endpoints.json").read_text()) == [{"role": "backend", "raw": "private-value"}]
        socket_path = root / "private-backend-sockets.json"
        if fault == "backend-snapshot-unavailable":
            assert not socket_path.exists()
        else:
            assert json.loads(socket_path.read_text())["observed_ticks"] == 200
        assert report["journey_diagnostics"]["app_lifetimes"]["launches"]["relaunch"]["handle"] == "MATCH"
        assert report["journey_diagnostics"]["snapshot_capture"] == {
            "status": "PASS", "before_in_capture": True, "after_in_capture": True,
            "before_in_audit": True, "after_in_audit": True,
        }
        assert report["journey_diagnostics"]["webview_storage"] == {
            "ambient_temp_creates": 0, "user_local_targets": [],
        }
        assert report["journey_diagnostics"]["final_sysmon_calibration"] == (
            {"status": "BLOCKED", "reason": "final fixture TCP or UDP evidence missing"}
            if fault == "final-calibration" else {"status": "PASS"}
        )
        assert report["journey_diagnostics"]["outside_scope_paths"] == [
            {"role": "driver", "operation": "write", "path_categories": ["other-path"], "count": 1},
        ]
        assert report["journey_diagnostics"]["outside_scope_writers"] == [
            {"role": "driver", "operation": "write", "path_categories": ["other-path"],
             "writer": "node", "count": 1},
        ]

    lines = capsys.readouterr().out.splitlines()
    records = [json.loads(line.removeprefix("N12 checkpoint ")) for line in lines if line.startswith("N12 checkpoint ")]
    if fault in {"sysmon-export", "sysmon-parse", "etw-export", "etw-reduce", "final-export-regressed"}:
        stage = {"sysmon-export": "sysmon-export", "final-export-regressed": "sysmon-export",
                 "sysmon-parse": "sysmon-reduction",
                 "etw-export": "etw-export", "etw-reduce": "combined-reduction"}[fault]
        assert records[-1]["stage"] == stage and records[-1]["status"] == "interrupted"
    if fault in completed_baseline:
        assert records[-1]["stage"] == "webview-credit-comparison"
        assert records[-1]["status"] == ("interrupted" if fault in comparison_faults else "completed")
        ordinary, = [line for line in lines if line.startswith("N12 ordinary audit ")]
        assert json.loads(ordinary.removeprefix("N12 ordinary audit "))["etw_unresolved_mutations"] == {
            write_gap: 3, unrelated_gap: 1,
        }
        assert lines.index(ordinary) < next(
            index for index, line in enumerate(lines) if '"stage": "webview-credit-comparison"' in line
        )
    lifetime_lines = [line for line in lines if line.startswith("N12 app lifetime observations ")]
    if fault in completed_baseline or fault == "etw-reduce":
        lifetime_line, = lifetime_lines
        assert "private" not in lifetime_line
        assert json.loads(lifetime_line.removeprefix("N12 app lifetime observations "))["launches"] == {
            "first": {"handle": "MATCH"}, "relaunch": {"handle": "MATCH"},
        }
    else:
        assert not lifetime_lines
    network_lines = [line.removeprefix("N12 network observations ") for line in lines
                     if line.startswith("N12 network observations ")]
    if fault in completed_baseline or fault in {"etw-export", "etw-reduce"}:
        observation, = network_lines
        assert "private-value" not in observation and "702" not in observation
        assert json.loads(observation) == {
            "source_sha": SOURCE, "executable_sha256": EXE_SHA,
            "scope": "diagnostic-only-before-combined-audit",
            "sysmon_and_lifecycle_issues": ["sysmon-exit-time-unverified"],
            "connections": observed.network_counts,
            "unexpected_connections": observed.unexpected_connections,
            "network_diagnostics": {
                "logs": {"first": "missing", "relaunch": "missing"},
                "backend_socket_snapshot": "unavailable" if fault == "backend-snapshot-unavailable" else "available",
                "observations": [{"observation": 1, "socket_status": "outside-webview",
                                  "request_category": "unattributed"}],
            },
        }
    else:
        assert not network_lines
    diagnostic = "N12 rejected Sysmon exits " + json.dumps(
        [{"record": 159, "category": "text-placeholder"}])
    assert (diagnostic in lines) == (fault in {"sysmon-parse", "changed-protected", "absent-fixture"})
    summary, = [line.removeprefix("N12 protected endpoint snapshots ") for line in lines
                if line.startswith("N12 protected endpoint snapshots ")]
    assert json.loads(summary) == {
        "source_sha": SOURCE,
        "executable_sha256": EXE_SHA,
        "protected_snapshot_comparison": {"changed-protected": "CHANGED", "absent-fixture": "BLOCKED"}.get(
            fault, "MATCH"),
        "snapshot_changes": {"protected:local-original": fault == "changed-protected",
                             "observed:quality-source": False, "observed:qa-home": True},
        "unexpected_snapshot_changes": ["protected:local-original"] if fault == "changed-protected" else [],
        "snapshot_issues": ["immutable-fixture-missing-at-baseline"] if fault == "absent-fixture" else [],
    }
