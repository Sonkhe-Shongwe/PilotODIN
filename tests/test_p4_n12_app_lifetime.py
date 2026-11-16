"""Generated evidence for the single-launch N12 lifetime control."""
from copy import deepcopy
import json
import ntpath
import re
from pathlib import Path
from types import SimpleNamespace
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from xml.etree import ElementTree as ET

from qa.p4_native import n12_trace as trace
from qa.p4_research import n12_app_lifetime as lifetime
from tests.test_p4_n12_exit_corroboration import ORIGIN, event, payload, stamp


APP = r"c:\qa\build\pilotodin-desktop.exe"
PYTHON = r"c:\qa\python\python.exe"
WEBVIEW = r"c:\qa\msedgewebview2.exe"
SOURCE = "a" * 40
HASH = "b" * 64


class AppLifetimeTests(unittest.TestCase):
    def setUp(self):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        self.sysmon, self.etw = root / "sysmon.xml", root / "etw.jsonl"
        self.manifest = {"schema_version": 1, "disposable": True, "source_sha": SOURCE, "executable_sha256": HASH,
                         "start_utc": stamp(0).isoformat(), "end_utc": stamp(900_000).isoformat()}
        self.session = {"start": ORIGIN, "end": ORIGIN + 900_000,
                        "counters": dict.fromkeys(lifetime.etw.COUNTERS, 0) | {"buffers_written": 4}}
        # The capture probe supplies drive -> NT volume with its original casing.
        self.volume_devices = {"C:": r"\Device\HarddiskVolume3"}
        self.rows, self.events = [], []
        self.process(700, PYTHON, 50_000, 800_000, 1)
        self.app = self.process(701, APP, 130_000, 520_000, 700)
        self.process(702, WEBVIEW, 210_000, 650_000, 701)
        self.process(703, WEBVIEW, 320_000, 690_000, 702,
                     "--utility-sub-type=network.mojom.NetworkService")
        self.worker = {"pid": 700, "birth": ORIGIN + 50_000, "exit": ORIGIN + 800_000}

    def process(self, pid, image, birth, exit, parent, command=""):
        fields = {"ProcessId": str(pid), "ProcessGuid": f"private-{pid}", "Image": image}
        self.rows.extend([
            (birth, 1, {**fields, "UtcTime": payload(birth)[:-1], "ParentProcessGuid": f"private-{parent}",
                        "Hashes": f"SHA256={HASH}", "CommandLine": command}),
            (exit, 5, {**fields, "UtcTime": payload(exit)[:-1]}),
        ])
        self.events.extend([
            event(1, pid, pid, birth, birth + 100, image, parent=parent, parent_sequence=parent),
            event(2, pid, pid, birth, exit + 100, image, exit=exit),
        ])
        return {"pid": pid, "birth": ORIGIN + birth, "exit": ORIGIN + exit}

    def reduce(self):
        root = ET.Element("Events")
        for record, (offset, kind, fields) in enumerate(sorted(self.rows), 150):
            row = ET.SubElement(root, trace.EVENT_NS + "Event")
            system = ET.SubElement(row, trace.EVENT_NS + "System")
            ET.SubElement(system, trace.EVENT_NS + "EventID").text = str(kind)
            ET.SubElement(system, trace.EVENT_NS + "EventRecordID").text = str(record)
            ET.SubElement(system, trace.EVENT_NS + "TimeCreated", SystemTime=payload(offset + 100))
            data = ET.SubElement(row, trace.EVENT_NS + "EventData")
            for key, value in fields.items():
                ET.SubElement(data, trace.EVENT_NS + "Data", Name=key).text = value
        ET.ElementTree(root).write(self.sysmon, encoding="utf-8")
        self.etw.write_text("".join(json.dumps(row) + "\n" for row in self.events), encoding="utf-8")
        self.manifest.update(sysmon_first_record=150, sysmon_last_record=149 + len(self.rows),
                             events_sha256=lifetime.build.digest(self.etw))
        with patch.object(lifetime.sys, "executable", PYTHON):
            return lifetime.reduction(self.manifest, self.sysmon, self.etw, self.volume_devices,
                                      self.session, self.app, self.worker, APP)

    def test_clean_lifetime_matches_both_original_handles(self):
        report = self.reduce()
        self.assertEqual(report["verdict"], "PASS")
        self.assertEqual(report["handle_comparison"], {"app": "MATCH", "launcher": "MATCH"})
        self.assertEqual(report["app_roles"], {"app": 1, "webview": 1, "webview-network": 1})
        self.assertEqual(report["disputed_exits"], [])
        self.assertEqual(report["etw_start_image_comparisons"], {
            role: {"exact-path-match": 1} for role in ("app", "launcher", "webview", "webview-network")
        })
        self.assertEqual(len(report["timing_comparisons"]), 4)
        self.assertTrue(all(row["etw_minus_sysmon_exit_ticks"] == 0 for row in report["timing_comparisons"]))

    def test_capture_volume_map_resolves_native_images_for_every_scoped_role(self):
        for row in self.events:
            drive, suffix = ntpath.splitdrive(row["data"]["ImageName"])
            row["data"]["ImageName"] = self.volume_devices[drive.upper()] + suffix
        report = self.reduce()
        self.assertEqual(report["verdict"], "PASS")
        self.assertEqual(report["handle_comparison"], {"app": "MATCH", "launcher": "MATCH"})
        self.assertEqual(report["etw_start_image_comparisons"], {
            role: {"exact-path-match": 1} for role in ("app", "launcher", "webview", "webview-network")
        })
        self.assertEqual(len(report["timing_comparisons"]), 4)

    def test_missing_and_ambiguous_capture_volume_maps_fail_closed(self):
        volume = self.volume_devices["C:"]
        for mapping, issue in (
            ({}, "ETW volume mappings are missing"),
            ({"C:": volume, "D:": volume.lower()}, "invalid or ambiguous ETW volume mapping"),
        ):
            with self.subTest(issue=issue):
                self.volume_devices = mapping
                with self.assertRaisesRegex(trace.EvidenceValidationError, f"^{issue}$"):
                    self.reduce()

    def test_ordering_report_identifies_a_launcher_clock_conflict_without_weakening_the_gate(self):
        self.events[0]["ticks"] -= 101
        report = self.reduce()
        self.assertEqual(report["verdict"], "BLOCKED")
        self.assertIn("etw-lifetime-order-unverified", report["issues"])
        self.assertEqual(report["handle_comparison"], {"app": "BLOCKED", "launcher": "BLOCKED"})
        self.assertEqual(report["timing_comparisons"], [])
        launcher = report["etw_handle_order_comparison"]["launcher"]
        self.assertEqual(launcher["start_emission_minus_creation_ticks"], -1)
        self.assertEqual(launcher["etw_payload_creation_minus_handle_ticks"], 0)
        self.assertEqual(launcher["etw_payload_exit_minus_handle_ticks"], 0)
        self.assertGreater(report["etw_handle_order_comparison"]["app"]["start_emission_minus_creation_ticks"], 0)
        for private in ("pilotodin-desktop", "python.exe", "private", str(ORIGIN + 50_000)):
            self.assertNotIn(private, json.dumps(report["etw_handle_order_comparison"]))

    def test_ordering_report_preserves_ambiguous_or_missing_pair_outcomes(self):
        self.events.append(deepcopy(self.events[0]))
        self.events.pop(3)
        report = self.reduce()
        self.assertEqual(report["verdict"], "BLOCKED")
        self.assertEqual(report["etw_handle_order_comparison"], {
            "launcher": {"issue": "etw-start-missing-or-ambiguous"},
            "app": {"issue": "etw-stop-missing-or-ambiguous"},
        })

    def test_image_failures_are_reported_by_role_after_launcher_blocks(self):
        del self.events[0]["data"]["ImageName"]
        self.events[2]["data"]["ImageName"] = r"\Device\HarddiskVolume99\private\pilotodin-desktop.exe"
        self.events[4]["data"]["ImageName"] = r"c:\private\other-image.exe"
        self.events[6]["data"]["ImageName"] = r"c:\private\msedgewebview2.exe"
        report = self.reduce()
        self.assertEqual(report["verdict"], "BLOCKED")
        self.assertEqual(report["handle_comparison"], {"app": "BLOCKED", "launcher": "BLOCKED"})
        self.assertEqual(report["timing_comparisons"], [])
        self.assertIn("etw-start-image-unverified", report["issues"])
        self.assertEqual(report["etw_start_image_comparisons"], {
            "launcher": {"missing-image": 1},
            "app": {"unmapped-device-path": 1},
            "webview": {"different-executable-name": 1},
            "webview-network": {"different-path-same-basename": 1},
        })
        for private in ("private", "HarddiskVolume99", "pilotodin-desktop", "other-image", "msedgewebview2", "700"):
            self.assertNotIn(private, json.dumps(report))

    def test_basename_and_unrecognised_image_values_stay_blocked(self):
        cases = (
            ("", "missing-image"),
            (123, "invalid-image-type"),
            ("python.exe", "basename-only"),
            (r"private\python.exe", "unsupported-path-form"),
            (r"\\?\Device\HarddiskVolume99\python.exe", "unsupported-path-form"),
            (r"\\?\GLOBALROOT\Device\HarddiskVolume99\python.exe", "unmapped-device-path"),
        )
        for image, reason in cases:
            with self.subTest(reason=reason):
                self.events[0]["data"]["ImageName"] = image
                report = self.reduce()
                self.assertEqual(report["verdict"], "BLOCKED")
                self.assertIn("etw-start-image-unverified", report["issues"])
                self.assertEqual(report["etw_start_image_comparisons"]["launcher"], {reason: 1})

    def test_ambiguous_start_does_not_report_a_path_match(self):
        self.events.append(deepcopy(self.events[0]))
        report = self.reduce()
        self.assertEqual(report["verdict"], "BLOCKED")
        self.assertIn("etw-start-missing-or-ambiguous", report["issues"])
        self.assertEqual(report["etw_start_image_comparisons"]["launcher"], {"start-missing-or-ambiguous": 1})

    def test_corroborated_app_exit_retains_blocked_sysmon_result(self):
        exit_fields = next(fields for _, kind, fields in self.rows
                           if kind == 5 and fields["ProcessId"] == "701")
        exit_fields.update(Image="private-opaque-image", UtcTime=payload(110_000)[:-1])
        report = self.reduce()
        self.assertEqual(report["verdict"], "BLOCKED")
        self.assertIn("sysmon-exit-image-unverified", report["issues"])
        self.assertIn("sysmon-exit-time-unverified", report["issues"])
        self.assertEqual(report["disputed_exits"][0]["status"], "CORROBORATED_DIAGNOSTIC")
        self.assertEqual(report["handle_comparison"]["app"], "MATCH")
        for private in ("private", "pilotodin-desktop", "msedgewebview2"):
            self.assertNotIn(private, json.dumps(report))

    def test_lost_events_and_disagreeing_handles_cannot_pass(self):
        self.session["counters"]["events_lost"] = 1
        report = self.reduce()
        self.assertEqual(report["verdict"], "BLOCKED")
        self.assertIn("etw-event-or-buffer-loss", report["issues"])
        self.assertEqual(report["etw_start_image_comparisons"], {})
        self.assertEqual(report["etw_handle_order_comparison"], {})
        self.session["counters"]["events_lost"] = 0
        self.app["exit"] += 1
        report = self.reduce()
        self.assertEqual(report["verdict"], "BLOCKED")
        self.assertIn("etw-and-windows-handle-timestamps-differ", report["issues"])

    def test_tree_parent_and_missing_profile_fail_closed(self):
        original = deepcopy(self.events)
        self.events[6]["data"]["ParentProcessSequenceNumber"] = "700"
        self.assertIn("app-tree-etw-parent-lifetime-unverified", self.reduce()["issues"])
        self.events = original
        self.rows = [row for row in self.rows if row[2]["ProcessId"] != "703"]
        self.assertIn("app-profile-lifetime-missing", self.reduce()["issues"])

    def test_only_etw_observing_a_scoped_child_blocks(self):
        self.events.extend([
            event(1, 704, 704, 350_000, 350_100, WEBVIEW, parent=702, parent_sequence=702),
            event(2, 704, 704, 350_000, 420_100, WEBVIEW, exit=420_000),
        ])
        report = self.reduce()
        self.assertEqual(report["verdict"], "BLOCKED")
        self.assertIn("app-tree-etw-child-missing-from-sysmon", report["issues"])

    def test_graceful_close_preserves_only_fixed_status(self):
        app = SimpleNamespace(pid=23)
        for raw, expected in (
            (b"n12-close-process-timeout\r\n", "window-process-exit-timeout"),
            (b"n12-close-identity-mismatch\r\n", "window-identity-mismatch"),
            (b"private runner output", "window-close-helper-failed"),
        ):
            error = subprocess.CalledProcessError(1, "private command", output=raw)
            with self.subTest(expected=expected), patch.object(lifetime.journey, "powershell", side_effect=error):
                with self.assertRaisesRegex(trace.EvidenceValidationError, f"^{expected}$"):
                    lifetime.request_graceful_close(app, APP, "PilotODIN QA")

    def test_cli_and_workflow_enforce_separate_lifetime_approval(self):
        with patch.dict(lifetime.os.environ, {"PILOTODIN_N12_APP_LIFETIME_CONSENT": "other"}):
            run = subprocess.run([sys.executable, "-B", "-m", lifetime.__name__, "--source", SOURCE,
                "--expected-exe-sha256", HASH, "--worker"], capture_output=True, text=True)
        self.assertEqual(run.returncode, 2)
        self.assertIn("separate one-run N12 app lifetime consent is required", run.stderr)
        workflow = (lifetime.build.REPO / ".github/workflows/p4-n12-app-lifetime.yml").read_text(encoding="utf-8")
        marker_path = "qa/p4_research/N12_APP_LIFETIME_EVENT_ORDER_RETEST_APPROVAL.txt"
        self.assertIn(f"      - {marker_path}", workflow)
        self.assertIn("scope=n12-one-build-one-app-lifetime", workflow)
        self.assertIn("-WithEtw -AppLifetime", workflow)
        self.assertIn("$parents[1] -cne $source", workflow)
        self.assertIn("$changed.Count -ne 2", workflow)
        self.assertIn("$added[0] -cne $marker", workflow)
        gate = re.search(r"(?m)^    if: (.+?)(?: #.*)?$", workflow)
        self.assertIsNotNone(gate)
        if gate[1] == "${{ false }}":
            return  # The consumed approval marker may be retained as evidence.

        self.assertEqual(gate[1], "${{ github.run_attempt == 1 && github.event_name == 'push' }}")
        approval = (lifetime.build.REPO / marker_path).read_text(encoding="utf-8").splitlines()
        self.assertEqual(len(approval), 2)
        self.assertRegex(approval[0], r"^reviewed_source=[0-9a-f]{40}$")
        self.assertEqual(approval[1], "scope=n12-one-build-one-app-lifetime")
        source = approval[0].split("=", 1)[1]
        self.assertEqual(lifetime.build.git("rev-parse", "HEAD^"), source)
        self.assertEqual(set(lifetime.build.git("diff", "--name-only", source, "HEAD").splitlines()),
                         {marker_path, ".github/workflows/p4-n12-app-lifetime.yml"})
        self.assertEqual(lifetime.build.git("diff", "--name-only", "--diff-filter=A", source, "HEAD", "--", marker_path),
                         marker_path)


if __name__ == "__main__":
    unittest.main()
