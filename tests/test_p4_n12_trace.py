"""Synthetic N12 evidence tests. Never launch PilotODIN or change Windows auditing."""
from __future__ import annotations

import csv
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from xml.etree import ElementTree as ET

import pytest

from qa.p4_native import n12_calibration, n12_trace as trace
from qa.p4_native.n12_etw_correlate import correlate


def test_etw_failed_open_and_reused_pid_and_file_object():
    capture = {
        "fixture": {"child_pid": 12, "start_window": [1, 3],
                    "fixture": r"D:\qa\original", "renamed_fixture": r"D:\qa\renamed"},
        "second_writer": {"pid": 20, "start_window": [4, 6],
                          "source": r"D:\qa\source", "destination": r"D:\qa\destination"},
        "device": r"\Device\HarddiskVolume3", "protected_root": r"D:\qa\protected",
    }
    rows = []

    def event(event_id, pid, *, lifecycle=False, **data):
        rows.append({"id": event_id, "pid": pid, "ticks": len(rows) + 1,
                     "lifecycle": lifecycle, "data": data})

    event(1, 0, lifecycle=True, ProcessID=12)
    event(12, 12, FileObject=8, Irp=11, FileName=r"D:\qa\original")
    event(24, 0, Irp=11, Status=0, ExtraInformation=2)
    event(2, 0, lifecycle=True, ProcessID=12)
    event(1, 0, lifecycle=True, ProcessID=20)
    event(12, 20, FileObject=8, Irp=11, FileName=r"D:\qa\source")
    event(24, 0, Irp=11, Status="0xc0000035", ExtraInformation=2)
    event(1, 0, lifecycle=True, ProcessID=12)
    event(16, 12, FileObject=8, Irp=11)
    event(24, 0, Irp=11, Status=0)
    # A process already running when the trace starts can open an existing file.
    event(12, 99, FileObject=9, Irp=13, FileName=r"D:\qa\protected\private-file")
    event(24, 0, Irp=13, Status=0, ExtraInformation=1)
    event(12, 12, FileObject=8, Irp=11,
          FileName=r"\Device\HarddiskVolume3\qa\protected\private-file")
    event(24, 0, Irp=11, Status=0, ExtraInformation=2)
    event(16, 12, FileObject=8, Irp=11)
    event(24, 0, Irp=11, Status=0)
    event(14, 12, FileObject=8)
    event(16, 12, FileObject=8, Irp=11)
    event(24, 0, Irp=11, Status=0)
    # A new open also invalidates an old object mapping if its close was absent.
    event(12, 12, FileObject=8, Irp=11, FileName=r"D:\qa\protected\private-file")
    event(24, 0, Irp=11, Status=0, ExtraInformation=1)
    event(12, 12, FileObject=8, Irp=11, FileName=r"D:\qa\untracked")
    event(24, 0, Irp=11, Status=0, ExtraInformation=1)
    event(16, 12, FileObject=8, Irp=11)
    event(24, 0, Irp=11, Status=0)

    assert correlate(capture, rows) == {
        "operations": {"fixture:create:original": 1, "other:create:protected": 1,
                       "other:write:protected": 1},
        "failed": {"second-writer:open:source": 1},
        "unresolved": {},
        "protected_writes": 2,
    }

    # Two overlapping requests cannot share a success completion.
    event(12, 12, FileObject=9, Irp=15, FileName=r"D:\qa\protected\private-file")
    event(12, 12, FileObject=10, Irp=15, FileName=r"D:\qa\untracked")
    event(24, 0, Irp=15, Status=0, ExtraInformation=2)
    report = correlate(capture, rows)
    assert report["protected_writes"] == 2
    assert report["unresolved"] == {"other:open:irp-reused-before-completion": 1}

    # Overwriting through an open still requires writer attribution.
    event(12, 99, FileObject=9, Irp=16, FileName=r"D:\qa\protected\private-file")
    event(24, 0, Irp=16, Status=0, ExtraInformation=3)
    report = correlate(capture, rows)
    assert report["protected_writes"] == 3
    assert report["operations"]["other:overwrite:protected"] == 1
    assert report["unresolved"]["other:open:process-lifetime-missing"] == 1

    # The smaller combined rehearsal fixture has no second writer.
    capture["second_writer"] = None
    report = correlate(capture, rows[:4])
    assert report == {"operations": {"fixture:create:original": 1}, "failed": {},
                      "unresolved": {}, "protected_writes": 0}
    assert correlate(capture, rows[1:4])["unresolved"] == {
        "fixture:process-start-missing-or-ambiguous": 1,
        "other:open:process-lifetime-missing": 1,
    }

BASE = "2026-11-13"
PYTHON = r"C:\Runtime\python.exe"
APP = r"C:\Build\pilotodin-desktop.exe"
WEBVIEW = r"C:\Runtime\msedgewebview2.exe"
FIXTURE = r"C:\QA\fixture.csv"
PROTECTED = r"C:\Original\PilotODIN"
FIELDNAMES = ["Time of Day", "PID", "Operation", "Path", "Result", "Detail", "Process Name"]


def instant(second):
    return f"{BASE}T00:00:{second:02}+00:00"


@pytest.mark.parametrize(("fault", "reason"), [
    (None, "N12 ETW export passed validation: 1 events."),
    ("digest", "ETW export digest mismatch"),
    ("outside-capture", "ETW event timestamp outside capture"),
    ("wrong-timestamp-type", "ETW event timestamp outside capture"),
    ("wrong-envelope", "invalid ETW event envelope"),
    ("truncated", "ETW event stream: JSONDecodeError"),
    ("empty", "ETW event export is empty"),
    ("lost", "ETW reported event or buffer loss"),
    ("missing-device", "ETW volume mappings are missing"),
])
def test_windows_etw_export_preflight(tmp_path, fault, reason):
    event = {"ticks": trace.utc_ticks(trace.utc_time(instant(1))),
             "id": 24, "pid": None, "lifecycle": False, "data": {"Status": "0x0"}}
    if fault == "outside-capture":
        event["ticks"] = trace.utc_ticks(trace.utc_time(instant(3)))
    if fault == "wrong-timestamp-type":
        event["ticks"] = str(event["ticks"])
    if fault == "wrong-envelope":
        event["data"] = "private-event-field"
    payload = (json.dumps(event) + "\n").encode()
    if fault == "truncated":
        payload = b'{"private-event-field":'
    if fault == "empty":
        payload = b""
    events = tmp_path / "private-etw.jsonl"
    events.write_bytes(payload)
    start, end = (instant(second).replace("+00:00", ".0000000Z") for second in (0, 2))
    manifest = {
        "start_utc": start, "end_utc": end,
        "etw": {"schema_version": 1, "start_utc": start, "end_utc": end,
                "events_sha256": "0" * 64 if fault == "digest" else hashlib.sha256(payload).hexdigest(),
                "volume_devices": {} if fault == "missing-device" else {"C:": r"\Device\HarddiskVolume3"},
                "counters": {"events_lost": int(fault == "lost"), "log_buffers_lost": 0,
                             "realtime_buffers_lost": 0, "buffers_written": 1}},
    }
    source = tmp_path / "private-manifest.json"
    source.write_text(json.dumps(manifest), encoding="utf-8-sig")
    result = subprocess.run([sys.executable, trace.__file__, "check-etw-export", str(source), str(events)],
                            capture_output=True, text=True, check=False)
    if fault is None:
        assert result.returncode == 0, result.stderr
        assert result.stdout.strip() == reason
    else:
        assert result.returncode == 2
        assert not result.stdout
        assert reason in result.stderr
        assert "private-" not in result.stderr


class Evidence:
    def __init__(self):
        self.events = []
        self.files = []
        self.manifest = {
            "schema_version": 1, "disposable": True,
            "source_sha": "f" * 40, "executable_sha256": "e" * 64,
            "start_utc": instant(0), "end_utc": instant(59),
            "markers": dict(zip(trace.MINIMUM_MARKERS, map(instant, [13, 18, 25, 30, 36, 45]))),
            "sysmon_first_record": 100,
            "procmon_all_events": True, "procmon_loss_reviewed": True, "procmon_clock_utc": True,
            "loopback_ports": [8000, 9001, 9002],
            "protected_roots": {"original": PROTECTED},
            "observed_roots": {"fixture": FIXTURE, "test-home": r"C:\QA\home"},
            "immutable_observed": ["fixture"],
            "permitted_writes": {
                "app": [r"C:\QA\home"], "backend": [r"C:\QA\home"],
                "webview": [r"C:\QA\home"], "webview-network": [r"C:\QA\home"],
                "calibration": [r"C:\QA\calibration"],
            },
            "processes": [{"role": role, "pid": pid, "image": image} for role, pid, image in (
                ("app", 1, APP), ("app", 2, APP), ("backend", 10, PYTHON), ("driver", 20, PYTHON))],
        }
        self.before = {
            key: {label: {"root_id": hashlib.sha256(trace.windows_path(path).encode()).hexdigest(),
                          "state": "file" if label == "fixture" else "directory", "digest": "1" * 64}
                  for label, path in self.manifest[f"{key}_roots"].items()}
            for key in ("protected", "observed")
        }
        self.after = json.loads(json.dumps(self.before))
        self.birth(14, 10, "backend", PYTHON)
        self.birth(19, 1, "app1", APP)
        self.birth(20, 3, "web1", WEBVIEW, "app1")
        self.birth(21, 4, "net1", WEBVIEW, "web1",
                   command="msedgewebview2.exe --utility-sub-type=network.mojom.NetworkService")
        self.birth(24, 20, "driver", PYTHON)
        self.end(29, "driver")
        self.end(31, "net1")
        self.end(32, "web1")
        self.end(33, "app1")
        self.birth(37, 2, "app2", APP)
        self.birth(38, 3, "web2", WEBVIEW, "app2")
        self.birth(39, 4, "net2", WEBVIEW, "web2",
                   command="msedgewebview2.exe --utility-sub-type=network.mojom.NetworkService")
        self.end(46, "net2")
        self.end(47, "web2")
        self.end(48, "app2")
        self.end(49, "backend")
        self.connect(23, "net1", "127.0.0.1", 8000)
        self.write(27, 3, "WriteFile", r"C:\QA\home\wv-cache", exe="msedgewebview2.exe")
        self.write(28, 10, "WriteFile", r"C:\QA\home\data.sqlite")
        self.calibration(1, 30, 9001)
        self.calibration(50, 40, 9002)

    def birth(self, second, pid, guid, image, parent="", command=""):
        self.events.append((second, 1, {"ProcessGuid": guid, "ParentProcessGuid": parent,
                                        "ProcessId": str(pid), "Image": image, "CommandLine": command,
                                        "Hashes": "SHA256=" + "E" * 64}))

    def end(self, second, guid):
        self.events.append((second, 5, {"ProcessGuid": guid}))

    def connect(self, second, guid, ip, port, protocol="tcp", initiated=True):
        self.events.append((second, 3, {"ProcessGuid": guid, "Protocol": protocol,
                                        "Initiated": str(initiated).lower(), "DestinationIp": ip,
                                        "DestinationPort": str(port), "SourcePort": "53000"}))

    def write(self, second, pid, operation, path, detail="", exe="python.exe", result="SUCCESS"):
        self.files.append([f"00:00:{second:02}.1234567", str(pid), operation, path, result, detail, exe])

    def calibration(self, second, pid, port):
        parent, child = f"parent{pid}", f"child{pid}"
        original, renamed = rf"C:\QA\calibration\{pid}\marker", rf"C:\QA\calibration\{pid}\renamed"
        self.manifest["processes"].append({"role": "calibration", "pid": pid, "image": PYTHON,
                                           "fixture": original, "renamed_fixture": renamed, "port": port})
        self.birth(second, pid, parent, PYTHON)
        self.birth(second + 1, pid + 1, child, PYTHON, parent)
        self.write(second + 2, pid + 1, "CreateFile", original, "OpenResult: Created")
        self.write(second + 2, pid + 1, "WriteFile", original)
        self.write(second + 2, pid + 1, "SetEndOfFileInformationFile", original)
        self.write(second + 2, pid + 1, "SetRenameInformationFile", original, f"FileName: {renamed}")
        self.write(second + 2, pid + 1, "SetDispositionInformationFile", renamed, "Delete: True")
        self.connect(second + 3, child, "127.0.0.1", port)
        self.connect(second + 3, child, "::ffff:127.0.0.1", port, "udp")
        self.end(second + 4, child)
        self.end(second + 5, parent)

    def save(self, path, *, omit_record=None):
        sysmon = path / "sysmon.xml"
        procmon = path / "procmon.csv"
        root = ET.Element("Events")
        for record, (second, kind, fields) in enumerate(sorted(self.events, key=lambda e: e[0]), 100):
            if record == omit_record:
                continue
            event = ET.SubElement(root, trace.EVENT_NS + "Event")
            system = ET.SubElement(event, trace.EVENT_NS + "System")
            ET.SubElement(system, trace.EVENT_NS + "EventID").text = str(kind)
            ET.SubElement(system, trace.EVENT_NS + "EventRecordID").text = str(record)
            ET.SubElement(system, trace.EVENT_NS + "TimeCreated", SystemTime=instant(second))
            data = ET.SubElement(event, trace.EVENT_NS + "EventData")
            fields = {"UtcTime": f"{BASE} 00:00:{second:02}.000", **fields}
            for key, value in fields.items():
                ET.SubElement(data, trace.EVENT_NS + "Data", Name=key).text = value
        ET.ElementTree(root).write(sysmon, encoding="utf-8")
        self.manifest["sysmon_last_record"] = record
        with procmon.open("w", encoding="utf-8-sig", newline="") as stream:
            writer = csv.writer(stream)
            writer.writerow(FIELDNAMES)
            writer.writerows(self.files)
        return sysmon, procmon

    def report(self, path, **kwargs):
        return trace.audit(self.manifest, *self.save(path, **kwargs), self.before, self.after)


def test_calibrated_trace_reports_scoped_results_and_keeps_history(tmp_path):
    report = Evidence().report(tmp_path)
    assert report["coverage"] == "CALIBRATED"
    assert report["network"] == report["filesystem"] == "PASS_SCOPED"
    assert report["historical_port_443_disposition"] == "UNATTRIBUTED"
    assert report["native_n12_accepted"] is False
    assert report["process_roles"]["webview-network"] == 2
    assert report["file_events"]["calibration:resize"] == 2
    assert report["unresolved_file_paths"] == []


def test_etw_audit_combines_sysmon_and_filesystem_evidence(tmp_path):
    evidence = Evidence()
    evidence.manifest.pop("procmon_loss_reviewed")
    sysmon, _ = evidence.save(tmp_path)
    etw_path = tmp_path / "etw.jsonl"
    rows = []
    request = 0

    def emit(second, pid, event_id, *, lifecycle=False, **data):
        rows.append(dict(ticks=trace.utc_ticks(trace.utc_time(instant(second))) + len(rows),
                         pid=pid, id=event_id, lifecycle=lifecycle, data=data))

    def mutation(second, pid, obj, kind, **fields):
        nonlocal request
        request += 1
        destination = fields.pop("Destination", None)
        outcome = fields.pop("Outcome", None)
        emit(second, pid, kind, FileObject=obj, Irp=request, **fields)
        if destination:
            emit(second, pid, 27, FileObject=obj, Irp=request, FilePath=destination)
        completion = {} if outcome is None else {"ExtraInformation": outcome}
        emit(second, 0, 24, Irp=request, Status=0, **completion)

    for pid, second in ((31, 2), (41, 51)):
        root = next(p for p in evidence.manifest["processes"] if p.get("pid") == pid - 1)
        emit(second, 0, 1, lifecycle=True, ProcessID=pid)
        mutation(second + 1, pid, 8, 12, FileName="\\??\\" + root["fixture"], Outcome=2)
        mutation(second + 1, pid, 8, 16)
        mutation(second + 1, pid, 8, 17, InfoClass=20)
        mutation(second + 1, pid, 8, 19,
                 Destination=r"\Device\HarddiskVolume3" + root["renamed_fixture"][2:])
        mutation(second + 1, pid, 8, 18)
        emit(second + 2, 0, 2, lifecycle=True, ProcessID=pid)

    emit(14, 0, 1, lifecycle=True, ProcessID=10)
    mutation(27, 10, 3, 12, FileName=r"\\?\C:\QA\home\data.sqlite", Outcome=1)
    mutation(28, 10, 3, 16)
    evidence.manifest["etw"] = {
        "schema_version": 1, "start_utc": instant(0), "end_utc": instant(59),
        "volume_devices": {"C:": r"\Device\HarddiskVolume3"},
        "counters": {"events_lost": 0, "log_buffers_lost": 0,
                     "realtime_buffers_lost": 0, "buffers_written": 1},
    }

    def report():
        etw_path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
        evidence.manifest["etw"]["events_sha256"] = hashlib.sha256(etw_path.read_bytes()).hexdigest()
        return trace.audit(evidence.manifest, sysmon, etw_path, evidence.before, evidence.after, etw=True)

    clean = report()
    assert clean["coverage"] == "CALIBRATED"
    assert clean["network"] == clean["filesystem"] == "PASS_SCOPED"
    assert clean["file_events"]["backend:write"] == 1
    assert clean["native_n12_accepted"] is False
    cli_inputs = []
    for name, value in (("manifest", evidence.manifest), ("before", evidence.before),
                        ("after", evidence.after)):
        input_path = tmp_path / f"{name}.json"
        input_path.write_text(json.dumps(value), encoding="utf-8")
        cli_inputs.append(input_path)
    manifest_path, before_path, after_path = cli_inputs
    output = tmp_path / "audit.json"
    result = subprocess.run([sys.executable, str(Path(trace.__file__)), "audit-etw",
                             *map(str, (manifest_path, sysmon, etw_path, before_path, after_path, output))],
                            capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stderr
    assert json.loads(output.read_text(encoding="utf-8")) == clean

    calibration_manifest = dict(evidence.manifest, calibration=next(
        root for root in evidence.manifest["processes"] if root["role"] == "calibration"
    ))
    manifest_path.write_text(json.dumps(calibration_manifest), encoding="utf-8")
    calibration_output = tmp_path / "calibration.json"
    result = subprocess.run([sys.executable, str(Path(trace.__file__)), "check-calibration-etw",
                             *map(str, (manifest_path, sysmon, etw_path, calibration_output))],
                            capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stderr
    assert json.loads(calibration_output.read_text(encoding="utf-8"))["coverage"] == "CALIBRATED"

    blocked_output = tmp_path / "blocked.json"
    command = [sys.executable, trace.__file__, "check-calibration-etw",
               *map(str, (manifest_path, sysmon, etw_path, blocked_output))]
    saved_etw = etw_path.read_bytes()
    etw_path.write_bytes(b" " + saved_etw)
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    assert result.returncode == 2
    assert result.stderr.strip() == "N12 BLOCKED: ETW event stream: ETW export digest mismatch."
    assert not blocked_output.exists()
    etw_path.write_bytes(saved_etw)

    saved_sysmon = sysmon.read_bytes()
    sysmon_tree = ET.parse(sysmon)
    sysmon_tree.find(f".//{trace.EVENT_NS}EventRecordID").text = "private-record"
    sysmon_tree.write(sysmon, encoding="utf-8")
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    assert result.returncode == 2
    assert result.stderr.strip() == "N12 BLOCKED: Sysmon XML: ValueError."
    assert not blocked_output.exists()
    sysmon.write_bytes(saved_sysmon)

    mutation(29, 10, 5, 16)  # Pre-opened handle with no captured path.
    mutation(30, 10, 6, 12, FileName=r"\Device\UnmappedVolume\private.bin", Outcome=2)
    mutation(30, 10, 3, 17, InfoClass=4)  # Unhandled metadata operation.
    unresolved = report()
    assert unresolved["filesystem"] == "BLOCKED"
    assert unresolved["etw_unresolved_mutations"] == {
        "backend:write:path-missing": 1,
        "backend:create:path-missing": 1,
        "backend:unsupported-file-operation": 1,
    }

    # PID 99 was already running at capture start. Its observed rename into
    # the protected root must still fail even though attribution is incomplete.
    mutation(31, 99, 9, 12, FileName=r"C:\QA\scratch\private.bin", Outcome=1)
    mutation(32, 99, 9, 19, Destination=r"\Device\HarddiskVolume3\Original\PilotODIN\private.bin")
    mutation(33, 99, 9, 16)
    bad = report()
    assert bad["filesystem"] == "FAIL"
    assert bad["file_violations"] == {"protected:other:rename": 1, "protected:other:write": 1}
    assert "etw-mutation-coverage-unresolved" in bad["coverage_issues"]
    assert "private.bin" not in json.dumps(bad)
    calibration_manifest["etw"] = evidence.manifest["etw"]
    rehearsal = trace.check_calibration(calibration_manifest, sysmon, etw_path, etw=True)
    assert "calibration-protected-mutation" in rehearsal["coverage_issues"]

    evidence.manifest["etw"]["counters"]["events_lost"] = 1
    assert "etw-event-or-buffer-loss" in report()["coverage_issues"]
    # A valid JSONL payload with different bytes must fail the digest check.
    etw_path.write_bytes(b" " + etw_path.read_bytes())
    with pytest.raises(ValueError, match="ETW export digest mismatch"):
        trace.audit(evidence.manifest, sysmon, etw_path, evidence.before, evidence.after, etw=True)


def standalone_capture(tmp_path, evidence, **kwargs):
    sysmon, procmon = evidence.save(tmp_path, **kwargs)
    keys = ("schema_version", "disposable", "start_utc", "end_utc", "sysmon_first_record",
            "sysmon_last_record", "procmon_all_events", "procmon_loss_reviewed", "procmon_clock_utc")
    manifest = {key: evidence.manifest[key] for key in keys}
    manifest["calibration"] = next(root for root in evidence.manifest["processes"]
                                   if root["role"] == "calibration")
    return manifest, sysmon, procmon


def test_unresolved_paths_are_counted_and_redacted_in_both_modes(tmp_path):
    evidence = Evidence()
    for _ in range(2):
        evidence.write(4, 31, "WriteFile", r"\Device\NamedPipe\private-pipe")
    evidence.write(4, 31, "WriteFile", r"\\?\Volume{private-id}\private-file")
    evidence.write(4, 555, "SetRenameInformationFile", r"C:\QA\unknown",
                   "ReplaceIfExists: True", exe="private-process.exe")
    evidence.write(4, 555, "SetLinkInformationFile", r"C:\QA\unknown",
                   r"FileName: \\private-server\private-share", exe="private-process.exe")
    evidence.write(4, 555, "SetRenameInformationFile", r"\Device\private-volume\private-file")
    evidence.write(4, 555, "WriteFile", r"\Device\NamedPipe\private-ignored-pipe")

    expected = [
        ("calibration", "write", "source", "device-or-extended", 1),
        ("calibration", "write", "source", "named-pipe", 2),
        ("other", "link", "destination", "unc", 1),
        ("other", "rename", "destination", "destination-field-missing", 1),
        ("other", "rename", "source", "device-or-extended", 1),
    ]
    for report in (trace.check_calibration(*standalone_capture(tmp_path, evidence)),
                   evidence.report(tmp_path)):
        assert report["coverage"] == "BLOCKED"
        assert "file-mutation-path-unresolved" in report["coverage_issues"]
        assert report["unresolved_file_paths"] == [
            dict(role=role, operation=operation, field=field, kind=kind, count=count)
            for role, operation, field, kind, count in expected
        ]
        assert "private-" not in json.dumps(report)


def test_standalone_calibration_cli_requires_no_app_journey(tmp_path):
    evidence = Evidence()
    evidence.events.clear()
    evidence.files.clear()
    evidence.manifest["processes"].clear()
    evidence.calibration(1, 30, 9001)
    manifest, sysmon, procmon = standalone_capture(tmp_path, evidence)
    input_path = tmp_path / "calibration.json"
    output_path = tmp_path / "summary.json"
    input_path.write_text(json.dumps(manifest), encoding="utf-8")
    command = [sys.executable, trace.__file__, "check-calibration",
               *map(str, (input_path, sysmon, procmon, output_path))]
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stderr
    summary = json.loads(output_path.read_text(encoding="utf-8"))
    assert summary["coverage"] == "CALIBRATED"
    assert summary["file_events"]["calibration:rename"] == 1
    assert summary["native_n12_accepted"] is False
    assert r"C:\\QA" not in json.dumps(summary)
    assert subprocess.run(command, capture_output=True, check=False).returncode == 2


def test_standalone_calibration_blocks_missing_udp_and_record_gap(tmp_path):
    evidence = Evidence()
    evidence.events = [event for event in evidence.events if not
                       (event[2].get("ProcessGuid") == "child30" and event[2].get("Protocol") == "udp")]
    evidence.manifest["procmon_loss_reviewed"] = False
    report = trace.check_calibration(*standalone_capture(tmp_path, evidence, omit_record=110))
    assert report["coverage"] == "BLOCKED"
    assert {"calibration-tcp-or-udp-missing", "sysmon-record-gap",
            "procmon-coverage-not-confirmed"} <= set(report["coverage_issues"])


def test_wrong_calibration_rename_destination_blocks_both_modes(tmp_path):
    evidence = Evidence()
    row = next(row for row in evidence.files if row[1] == "31" and row[2] == "SetRenameInformationFile")
    row[5] = r"FileName: C:\QA\calibration\30\wrong"
    standalone = trace.check_calibration(*standalone_capture(tmp_path, evidence))
    journey = evidence.report(tmp_path)
    for report in (standalone, journey):
        assert report["coverage"] == "BLOCKED"
        assert "calibration-file-events-missing" in report["coverage_issues"]


def test_calibration_blocks_missing_executable_hash_and_out_of_scope_effects(tmp_path):
    evidence = Evidence()
    next(fields for _, kind, fields in evidence.events
         if kind == 1 and fields["ProcessGuid"] == "child30").pop("Hashes")
    evidence.write(4, 31, "WriteFile", r"C:\QA\other.txt")
    evidence.connect(4, "child30", "203.0.113.23", 443)
    report = trace.check_calibration(*standalone_capture(tmp_path, evidence))
    assert report["coverage"] == "BLOCKED"
    assert {"calibration-image-identity-missing-or-mismatched", "calibration-writes-outside-fixture",
            "calibration-unexpected-connection"} <= set(report["coverage_issues"])


def test_external_webview_connection_is_unattributed_and_report_is_redacted(tmp_path):
    evidence = Evidence()
    evidence.connect(40, "net2", "203.0.113.23", 443, "udp")
    report = evidence.report(tmp_path)
    assert report["network"] == "PARTIAL"
    assert report["unexpected_connections"] == [
        {"role": "webview-network", "utc": instant(40), "protocol": "udp",
         "port": 443, "kind": "non-loopback", "purpose": "unattributed"}
    ]
    assert "203.0.113.23" not in json.dumps(report)
    assert "Original" not in json.dumps(report)


def test_loopback_wrong_port_fails_and_inbound_does_not_count_as_outbound(tmp_path):
    evidence = Evidence()
    evidence.connect(41, "net2", "::1", 9033)
    evidence.connect(41, "backend", "203.0.113.1", 8000, initiated=False)
    report = evidence.report(tmp_path)
    assert report["network"] == "FAIL"
    assert report["connections"]["backend:tcp:inbound"] == 1


def test_pid_reuse_and_protected_write_from_unrelated_process(tmp_path):
    evidence = Evidence()
    evidence.birth(34, 4, "unrelated", WEBVIEW)
    evidence.end(36, "unrelated")
    evidence.connect(35, "unrelated", "203.0.113.23", 443)
    evidence.write(35, 4, "WriteFile", PROTECTED + r"\temporary", exe="msedgewebview2.exe")
    evidence.write(35, 4, "SetDispositionInformationFile", PROTECTED + r"\temporary",
                   exe="msedgewebview2.exe", detail="Delete: True")
    report = evidence.report(tmp_path)
    assert report["network"] == "PASS_SCOPED"
    assert report["filesystem"] == "FAIL"
    assert report["unexpected_snapshot_changes"] == []
    assert report["file_violations"] == {"protected:other:write": 1, "protected:other:delete": 1}


def test_rename_destination_and_prefix_collision(tmp_path):
    evidence = Evidence()
    evidence.write(27, 10, "SetRenameInformationFile", r"C:\QA\home\move",
                   rf"FileName: {PROTECTED}\target")
    evidence.write(27, 10, "WriteFile", r"C:\QA\home-extra\not-allowed")
    report = evidence.report(tmp_path)
    assert report["file_violations"] == {
        "outside-scope:backend:rename": 1, "protected:backend:rename": 1,
        "outside-scope:backend:write": 1,
    }


def test_create_open_and_failed_write_are_not_mutations(tmp_path):
    evidence = Evidence()
    evidence.write(27, 10, "CreateFile", FIXTURE, "OpenResult: Opened")
    evidence.write(27, 10, "WriteFile", FIXTURE, result="ACCESS DENIED")
    report = evidence.report(tmp_path)
    assert report["filesystem"] == "PASS_SCOPED"


def test_immutable_fixture_hash_difference_fails(tmp_path):
    evidence = Evidence()
    evidence.after["observed"]["fixture"]["digest"] = "2" * 64
    report = evidence.report(tmp_path)
    assert report["filesystem"] == "FAIL"
    assert report["unexpected_snapshot_changes"] == ["observed:fixture"]


def test_missing_records_and_calibration_block_a_clean_result(tmp_path):
    evidence = Evidence()
    evidence.files = [row for row in evidence.files if not (row[1] == "41" and row[2] == "WriteFile")]
    report = evidence.report(tmp_path, omit_record=110)
    assert report["coverage"] == report["network"] == report["filesystem"] == "BLOCKED"
    assert {"sysmon-record-gap", "calibration-file-events-missing"} <= set(report["coverage_issues"])


def test_missing_exit_blocks_coverage(tmp_path):
    evidence = Evidence()
    evidence.events.remove((48, 5, {"ProcessGuid": "app2"}))
    report = evidence.report(tmp_path)
    assert "process-exit-missing" in report["coverage_issues"]
    assert "app-lifecycle-does-not-match-journey" in report["coverage_issues"]


def test_lost_procmon_coverage_and_unresolved_rename_block(tmp_path):
    evidence = Evidence()
    evidence.manifest["procmon_loss_reviewed"] = False
    evidence.write(25, 999, "SetRenameInformationFile", r"C:\QA\scratch")
    report = evidence.report(tmp_path)
    assert {"procmon-coverage-not-confirmed", "file-mutation-path-unresolved"} <= set(
        report["coverage_issues"])


def test_snapshot_refuses_overlap_and_path_aliases():
    evidence = Evidence()
    evidence.manifest["permitted_writes"]["app"] = [r"C:\Original\temp\.."]
    with pytest.raises(ValueError, match="overlap"):
        trace.scope(evidence.manifest)


def test_calibration_sends_actual_tcp_udp_and_leaves_no_files(monkeypatch, tmp_path):
    # CLI launches are guarded. Redirect only the child factory for this
    # portable local unit test so it uses exactly the same loopback operation.
    popen = subprocess.Popen

    def spawn(command):
        code = ("import sys; from pathlib import Path; "
                "from qa.p4_native.n12_calibration import calibrate_child; "
                "d=Path(sys.argv[1]); calibrate_child(d/'n12-marker.bin', "
                "d/'n12-renamed.bin', int(sys.argv[2]))")
        return popen([command[0], "-c", code, *command[-2:]])

    monkeypatch.setattr(n12_calibration.subprocess, "Popen", spawn)
    directory = tmp_path / "calibration"
    outcome = n12_calibration.calibrate(directory)
    assert outcome["port"] > 0
    assert outcome["child_pid"] > 0 and outcome["child_pid"] != outcome["pid"]
    assert outcome["role"] == "calibration"
    assert list(directory.iterdir()) == []


def test_cli_refuses_owner_snapshot_and_audit_output_overwrite(tmp_path, monkeypatch):
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    module = Path(trace.__file__)
    absent = tmp_path / "absent.json"
    result = subprocess.run([sys.executable, str(module), "snapshot", str(absent), str(absent)],
                            capture_output=True, text=True, check=False)
    assert result.returncode == 2
    assert not absent.exists()
    evidence = Evidence()
    sysmon, procmon = evidence.save(tmp_path)
    files = []
    for name, payload in (("manifest", evidence.manifest), ("before", evidence.before),
                          ("after", evidence.after)):
        path = tmp_path / f"{name}.json"
        path.write_text(json.dumps(payload), encoding="utf-8")
        files.append(path)
    command = [sys.executable, str(module), "audit",
               *map(str, (files[0], sysmon, procmon, files[1], files[2], absent))]
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stderr
    saved = absent.read_bytes()
    assert subprocess.run(command, capture_output=True, check=False).returncode == 2
    assert absent.read_bytes() == saved


def test_procmon_time_requires_utc_clock_and_24_hour_format():
    start = datetime(2026, 11, 13, tzinfo=timezone.utc)
    assert trace.capture_time("14:12:01.0123456", start).microsecond == 12345
    with pytest.raises(ValueError):
        trace.capture_time("2:12:01 PM", start)


def test_exact_executable_identity_is_required(tmp_path):
    evidence = Evidence()
    evidence.manifest["executable_sha256"] = "f" * 64
    report = evidence.report(tmp_path)
    assert "app-sha256-missing-or-mismatched" in report["coverage_issues"]
    assert report["coverage"] == "BLOCKED"


def test_private_endpoints_include_matching_fields_only_when_requested(tmp_path):
    evidence = Evidence()
    evidence.connect(40, "net2", "203.0.113.23", 443)
    endpoints = []
    report = trace.audit(evidence.manifest, *evidence.save(tmp_path), evidence.before,
                         evidence.after, private_endpoints=endpoints)
    assert endpoints[0]["address"] == "203.0.113.23"
    assert endpoints[0]["source_port"] == 53000
    assert endpoints[0]["process_guid"] == "net2"
    assert "203.0.113.23" not in json.dumps(report)
