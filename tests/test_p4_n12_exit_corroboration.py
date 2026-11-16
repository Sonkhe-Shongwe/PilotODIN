"""Generated Windows app lifetimes for the N12 disputed-exit diagnostic."""
from collections import Counter
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from xml.etree import ElementTree as ET

from qa.p4_native import n12_exit_corroboration as diagnostic
from qa.p4_native import n12_trace as trace


BASE = datetime(2026, 11, 16, tzinfo=timezone.utc)
ORIGIN = trace.utc_ticks(BASE)
PARENT_IMAGE = r"c:\qa\private\pilotodin.exe"
CHILD_IMAGE = r"c:\qa\private\msedgewebview2.exe"
DEVICES = {r"\device\harddiskvolume3": "c:"}


def stamp(offset):
    return BASE + timedelta(microseconds=offset // 10)


def payload(offset):
    return stamp(offset).strftime("%Y-%m-%dT%H:%M:%S.%f") + str(offset % 10) + "Z"


def event(kind, pid, sequence, birth, emission, image, *, parent=1, parent_sequence=10, exit=None):
    data = {"ProcessID": str(pid), "ProcessSequenceNumber": str(sequence),
            "CreateTime": payload(birth), "ImageName": image}
    if kind == 1:
        data.update(ParentProcessID=str(parent), ParentProcessSequenceNumber=str(parent_sequence))
    else:
        data["ExitTime"] = payload(exit)
    return {"id": kind, "version": 3 if kind == 1 else 2, "pid": 990,
            "lifecycle": True, "ticks": ORIGIN + emission, "data": data}


class DisputedExitTests(unittest.TestCase):
    def setUp(self):
        self.parent = trace.Process("private-parent", "", 700, PARENT_IMAGE, None, stamp(50_000), "", stamp(320_000))
        self.child = trace.Process("private-child", self.parent.guid, 701, CHILD_IMAGE, None, stamp(110_000), "")
        self.child.disputed_exit = trace.DisputedExit(155, stamp(90_000), True, True)
        self.processes = {p.guid: p for p in (self.parent, self.child)}
        self.roles = {self.parent.guid: "app", self.child.guid: "webview-network"}
        self.events = [
            event(1, 700, 31, 54_001, 54_023, PARENT_IMAGE),
            event(1, 701, 32, 115_001, 115_300,
                  r"\Device\HarddiskVolume3\qa\private\msedgewebview2.exe", parent=700, parent_sequence=31),
            event(2, 701, 32, 115_001, 245_800, "msedgewebview2.exe", exit=245_727),
            event(2, 700, 31, 54_001, 320_800, "pilotodin.exe", exit=320_001),
        ]

    def report(self, issues=()):
        return diagnostic.corroborate_exits(self.events, self.processes, self.roles, DEVICES,
                                            (ORIGIN, ORIGIN + 500_000), set(issues))[0]

    def test_corroborates_both_original_conflicts_without_changing_sysmon(self):
        original = self.child.disputed_exit
        row = self.report()
        self.assertEqual(row, {
            "record": 155, "role": "webview-network", "status": "CORROBORATED_DIAGNOSTIC",
            "sysmon_time_conflict": True, "sysmon_image_unverified": True,
            "sysmon_exit_minus_birth_ticks": -20_000, "etw_birth_minus_sysmon_birth_ticks": 5001,
            "etw_exit_minus_sysmon_exit_ticks": 155727, "etw_duration_ticks": 130726,
        })
        self.assertIs(self.child.disputed_exit, original)
        self.assertIsNone(self.child.end)
        for private in ("private", "msedgewebview2", "701", "HarddiskVolume", "990"):
            self.assertNotIn(private, json.dumps(row))

    def test_accepts_distinct_later_pid_reuse(self):
        self.events += [
            event(1, 701, 47, 350_001, 350_033, CHILD_IMAGE),
            event(2, 701, 47, 350_001, 450_059, "msedgewebview2.exe", exit=450_001),
        ]
        self.processes["private-later"] = trace.Process(
            "private-later", "", 701, CHILD_IMAGE, None, stamp(350_000), "", stamp(450_000))
        self.assertEqual(self.report()["status"], "CORROBORATED_DIAGNOSTIC")

    def test_rejects_overlapping_pid_reuse(self):
        self.events.append(event(1, 701, 46, 200_001, 200_033, CHILD_IMAGE))
        self.assertEqual(self.report()["issues"], ["overlapping-etw-pid-lifetimes"])

    def test_rejects_a_competing_sysmon_birth(self):
        self.processes["private-competing"] = trace.Process(
            "private-competing", "", 701, CHILD_IMAGE, None, stamp(117_000), "")
        self.assertEqual(self.report()["issues"], ["competing-sysmon-process-births"])

    def test_blocks_on_identity_time_or_collection_conflicts(self):
        cases = (
            ("missing-stop", lambda rows: rows.pop(2), "etw-stop-missing-or-ambiguous"),
            ("duplicate-stop", lambda rows: rows.append(rows[2]), "etw-stop-missing-or-ambiguous"),
            ("wrong-sequence", lambda rows: rows[2]["data"].update(ProcessSequenceNumber="31"),
             "etw-sequence-conflict"),
            ("conflicting-sequence-owner", lambda rows: rows.append(
                event(1, 702, 32, 350_001, 350_033, CHILD_IMAGE)), "etw-sequence-conflict"),
            ("wrong-parent", lambda rows: rows[1]["data"].update(ParentProcessID="799"),
             "etw-parent-identity-unverified"),
            ("wrong-parent-sequence", lambda rows: rows[1]["data"].update(ParentProcessSequenceNumber="43"),
             "etw-parent-lifetime-unverified"),
            ("parent-ended-early", lambda rows: rows[3]["data"].update(ExitTime=payload(90_000)),
             "etw-parent-lifetime-unverified"),
            ("new-start-after-exit", lambda rows: rows[2]["data"].update(ExitTime=payload(114_000)),
             "etw-lifetime-order-unverified"),
            ("exit-emitted-before-start", lambda rows: rows[2].update(ticks=ORIGIN + 115_200),
             "etw-lifetime-order-unverified"),
            ("exit-outside-window", lambda rows: rows[2].update(ticks=ORIGIN + 500_001),
             "etw-lifetime-order-unverified"),
            ("image-mismatch", lambda rows: rows[1]["data"].update(ImageName=PARENT_IMAGE),
             "etw-start-image-unverified"),
            ("stop-image-conflict", lambda rows: rows[2]["data"].update(ImageName="private-other.exe"),
             "etw-stop-image-conflict"),
            ("ambiguous-payload", lambda rows: rows[2].update(lifecycle_fields_ambiguous=True),
             "etw-process-payload-unverified"),
        )
        original = json.dumps(self.events)
        for label, corrupt, reason in cases:
            with self.subTest(label=label):
                self.events = json.loads(original)
                corrupt(self.events)
                row = self.report()
                self.assertEqual(row["status"], "BLOCKED")
                self.assertEqual(row["issues"], [reason])
        for issue in sorted(diagnostic.SOURCE_COVERAGE_ISSUES):
            with self.subTest(issue=issue):
                self.events = json.loads(original)
                self.assertEqual(self.report([issue])["issues"], [issue])

    def test_combined_audit_leaves_original_failures_in_place(self):
        issues = {"sysmon-exit-time-unverified", "sysmon-exit-image-unverified", "process-exit-missing"}
        observed = trace.JourneySysmon(
            BASE, stamp(500_000), {}, self.processes, self.roles, [], issues, [], Counter(), [],
        )
        manifest = {"source_sha": "a" * 40, "executable_sha256": "b" * 64,
                    "observed_roots": {}, "immutable_observed": []}
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "events.jsonl"
            path.write_text("".join(json.dumps(row) + "\n" for row in self.events), encoding="utf-8")
            manifest["etw"] = {"events_sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
            with (patch.object(trace, "etw_capture_contract", return_value=((ORIGIN, ORIGIN + 500_000), DEVICES)),
                  patch.object(trace, "scope", return_value=([], {})),
                  patch.object(trace, "verify_calibrations"),
                  patch.object(trace, "compare_snapshots", return_value=({"unexpected_snapshot_changes": []}, []))):
                report = trace.complete_journey_audit(manifest, observed, path, {}, {}, etw=True)
        self.assertEqual(report["etw_exit_corroboration"][0]["status"], "CORROBORATED_DIAGNOSTIC")
        self.assertEqual([report[k] for k in ("coverage", "network", "filesystem")], ["BLOCKED"] * 3)
        self.assertEqual(report["coverage_issues"], sorted(issues))
        self.assertEqual(report["trace_verdict_scope"], "diagnostic-only-unverified-sysmon-exit")

    def test_sysmon_reducer_retains_original_timing_and_image_disputes(self):
        root = ET.Element("Events")
        for index, (kind, fields) in enumerate([
            (1, {"ProcessGuid": self.parent.guid, "ParentProcessGuid": "", "ProcessId": "700",
                 "Image": PARENT_IMAGE, "UtcTime": "2026-11-16 00:00:00.005"}),
            (1, {"ProcessGuid": self.child.guid, "ParentProcessGuid": self.parent.guid, "ProcessId": "701",
                 "Image": CHILD_IMAGE, "UtcTime": "2026-11-16 00:00:00.011"}),
            (5, {"ProcessGuid": self.child.guid, "ProcessId": "701",
                 "Image": "unreadable private image", "UtcTime": "2026-11-16 00:00:00.009"}),
        ], start=153):
            row = ET.SubElement(root, trace.EVENT_NS + "Event")
            system = ET.SubElement(row, trace.EVENT_NS + "System")
            ET.SubElement(system, trace.EVENT_NS + "EventID").text = str(kind)
            ET.SubElement(system, trace.EVENT_NS + "EventRecordID").text = str(index)
            ET.SubElement(system, trace.EVENT_NS + "TimeCreated", SystemTime=payload(400_000))
            data = ET.SubElement(row, trace.EVENT_NS + "EventData")
            for key, value in fields.items():
                ET.SubElement(data, trace.EVENT_NS + "Data", Name=key).text = value
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "sysmon.xml"
            ET.ElementTree(root).write(path, encoding="utf-8")
            processes, _, issues, _, _ = trace.sysmon_events(path, BASE, stamp(500_000), rejected_sysmon_exits=[])
        self.assertEqual(issues, {"sysmon-exit-time-unverified", "sysmon-exit-image-unverified"})
        self.assertEqual(processes[self.child.guid].disputed_exit, self.child.disputed_exit)
        self.assertIsNone(processes[self.child.guid].end)
