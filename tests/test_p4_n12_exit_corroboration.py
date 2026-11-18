"""Generated Windows app lifetimes for the N12 disputed-exit diagnostic."""
from collections import Counter
from datetime import datetime, timedelta, timezone
import hashlib
import json
import ntpath
import os
from pathlib import Path
import shutil
import subprocess
import sys
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from xml.etree import ElementTree as ET

from qa.p4_native import n12_exit_corroboration as diagnostic
from qa.p4_native import n12_lifetime_control as controls
from qa.p4_native import n12_trace as trace
from qa.p4_research.n12_app_journey import DRIVER_TEMP_DIR, driver_environment
from qa.p4_research.n12_driver_handles import DriverHandles, descendants, driver_lifetime_evidence


BASE = datetime(2026, 11, 16, tzinfo=timezone.utc)
ORIGIN = trace.utc_ticks(BASE)
PARENT_IMAGE = r"c:\qa\private\pilotodin.exe"
CHILD_IMAGE = r"c:\qa\private\msedgewebview2.exe"
DEVICES = {r"\device\harddiskvolume3": "c:"}


def stamp(offset):
    return BASE + timedelta(microseconds=offset // 10)


@unittest.skipUnless(sys.platform == "win32", "requires Windows process handles")
class WindowsQueryHandleTests(unittest.TestCase):
    def test_query_handle_agrees_with_original_on_image_and_exit(self):
        with subprocess.Popen([sys.executable, "-I", "-c", "import sys; sys.stdin.buffer.read()"],
                              stdin=subprocess.PIPE) as child:
            try:
                with controls.open_process_query_handle(child.pid) as query_handle:
                    images = controls.process_images(query_handle)
                    self.assertEqual(images, controls.process_images(child))
                    self.assertEqual(ntpath.basename(images["image_dos"]).casefold(),
                                     ntpath.basename(sys.executable).casefold())
                    child.communicate(timeout=15)
                    self.assertEqual(child.returncode, 0)
                    self.assertEqual(controls.process_times(query_handle), controls.process_times(child))
            finally:
                if child.poll() is None:
                    child.kill()
                    child.wait(timeout=5)


class DriverTempTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which("node"), "requires Node")
    def test_node_create_write_and_rename_stay_in_qa_scratch(self):
        script = (
            "const fs = require('node:fs'); const os = require('node:os');"
            "const path = require('node:path');"
            "const scratch = fs.mkdtempSync(path.join(os.tmpdir(), 'n12-node-'));"
            "const initial = path.join(scratch, 'writing.tmp');"
            "const final = path.join(scratch, 'written.txt');"
            "fs.writeFileSync(initial, 'generated'); fs.renameSync(initial, final);"
            "process.stdout.write(final);"
        )
        with TemporaryDirectory() as folder:
            root = Path(folder).resolve()
            scratch = root / DRIVER_TEMP_DIR
            scratch.mkdir()
            user_temp = root / "user-temp"
            user_temp.mkdir()
            env = driver_environment({"TEMP": str(user_temp), "TMP": str(user_temp)}, root)
            result = subprocess.run([shutil.which("node"), "-e", script], capture_output=True,
                                    env={**os.environ, **env}, check=True, timeout=15, text=True)
            final = Path(result.stdout).resolve()
            self.assertTrue(final.is_relative_to(scratch))
            self.assertEqual(final.read_text(encoding="utf-8"), "generated")
            self.assertEqual(list(user_temp.iterdir()), [])


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

    def test_driver_handles_bind_disputed_exit_to_exact_parent_and_keep_report_redacted(self):
        observed = SimpleNamespace(processes=self.processes, roles={p: "driver" for p in self.processes})
        witness = {"pid": 701, "birth": ORIGIN + 115_001, "exit": ORIGIN + 245_727,
                   "image_dos": CHILD_IMAGE, "image_native": self.events[1]["data"]["ImageName"],
                   "label": "descendant", "parent_pid": 700}
        handles = DriverHandles()
        handles.witnesses.append(witness)
        window = ORIGIN, ORIGIN + 500_000
        report = driver_lifetime_evidence(self.events, DEVICES, window, observed, handles, set())
        row = report["disputed"][0]
        self.assertEqual((row["status"], row["family"], row["parent_role"]), ("MATCH", "webview", "driver"))
        self.assertEqual(row["order"]["etw_payload_exit_minus_handle_ticks"], 0)
        self.assertEqual(report["retained_by_label"], {"descendant": 1})
        self.assertNotIn("private", json.dumps(report))
        self.assertIsNone(self.child.end)
        self.events[1]["data"]["ParentProcessSequenceNumber"] = "12345"
        report = driver_lifetime_evidence(self.events, DEVICES, window, observed, handles, set())
        self.assertEqual(report["disputed"][0]["status"], "driver-etw-parent-lifetime-unverified")

    def test_driver_snapshot_walk_stays_under_the_owned_roots(self):
        rows = [(4, 3, "conhost.exe"), (6, 8, "node.exe"), (3, 2, "powershell.exe"), (2, 4, "node.exe")]
        self.assertEqual(list(descendants(rows, {2})), [(3, 2, "powershell.exe"), (4, 3, "conhost.exe")])

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

    def test_integrated_journey_keeps_two_handle_verdicts_and_child_blocker_redacted(self):
        roots = [self.parent, trace.Process("private-relaunch", "", 702, PARENT_IMAGE, None,
                                            stamp(350_000), "", stamp(480_000))]
        for process in roots:
            process.sha256 = "b" * 64
        self.processes[roots[1].guid] = roots[1]
        observed = SimpleNamespace(bindings=[({"role": "app"}, process) for process in roots],
                                   processes=self.processes, roles=self.roles)
        self.events[2]["data"]["ImageName"] = "msedgewebview2"
        self.events += [
            event(1, 702, 33, 350_001, 350_100, PARENT_IMAGE),
            event(2, 702, 33, 350_001, 480_100, "pilotodin.exe", exit=480_001),
        ]
        image = {"image_dos": PARENT_IMAGE, "image_native": r"\Device\HarddiskVolume3\qa\private\pilotodin.exe"}
        witnesses = {
            "first": {**image, "pid": 700, "birth": ORIGIN + 54_001, "exit": ORIGIN + 320_001},
            "relaunch": {**image, "pid": 702, "birth": ORIGIN + 350_001, "exit": ORIGIN + 480_001},
        }
        issues = frozenset({"sysmon-exit-time-unverified"})
        report = diagnostic.journey_lifetime_evidence(
            self.events, DEVICES, (ORIGIN, ORIGIN + 500_000), observed, witnesses, "b" * 64, issues)
        self.assertEqual(report["scope"], "diagnostic-only-before-file-correlation")
        self.assertEqual(report["launches"]["first"]["handle"], "MATCH")
        self.assertEqual(report["launches"]["relaunch"]["handle"], "MATCH")
        self.assertEqual(report["launches"]["first"]["children"]["webview-network"]["lifetime"],
                         {"etw-stop-image-conflict": 1})
        self.assertEqual(report["launches"]["relaunch"]["children"], {})
        for private in ("private", "HarddiskVolume", "pilotodin.exe", str(ORIGIN)):
            self.assertNotIn(private, json.dumps(report))
        self.assertEqual(issues, frozenset({"sysmon-exit-time-unverified"}))

        child = {"pid": 701, "birth": ORIGIN + 115_001, "exit": ORIGIN + 245_727,
                 "image_dos": CHILD_IMAGE,
                 "image_native": r"\Device\HarddiskVolume3\qa\private\msedgewebview2.exe"}
        for changes, expected in (
            ({}, "MATCH"),
            ({"birth": child["birth"] + 1}, "etw-and-windows-handle-timestamps-differ"),
            ({"exit": child["exit"] + 1}, "etw-and-windows-handle-timestamps-differ"),
            ({"image_dos": PARENT_IMAGE}, "webview-handle-image-unverified"),
        ):
            with self.subTest(expected=expected):
                witnesses["first"]["children"] = {701: child | changes}
                report = diagnostic.journey_lifetime_evidence(
                    self.events, DEVICES, (ORIGIN, ORIGIN + 500_000), observed,
                    witnesses, "b" * 64, issues)
                self.assertEqual(report["launches"]["first"]["children"]["webview-network"]["lifetime"],
                                 {expected: 1})
                self.assertEqual(report["launches"]["relaunch"]["children"], {})
                self.assertNotIn("private", json.dumps(report))

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
