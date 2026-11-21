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

    def reduce(self, **mode):
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
                                      self.session, self.app, self.worker, APP, **mode)

    def test_no_cdp_sysmon_per_clause_positive_is_only_diagnostic(self):
        report = self.reduce(no_cdp_profile=True)
        self.assertEqual(report["verdict"], "BLOCKED")  # no OS markers in fixture
        diagnostic = report["no_cdp_sysmon_diagnostic"]
        self.assertEqual(diagnostic["scope"], "no-cdp-independent-sysmon-diagnostic-only")
        for role in ("launcher", "app"):
            self.assertEqual(diagnostic[role]["status"], "CHECKS_MATCH")
            self.assertEqual(diagnostic[role]["failed_checks"], [])
            self.assertEqual(diagnostic[role]["etw_exit_minus_sysmon_exit_ticks"], 0)
            self.assertEqual(diagnostic[role]["sysmon_birth_minus_handle_ticks"], 0)
            self.assertEqual(diagnostic[role]["sysmon_exit_minus_handle_ticks"], 0)
        self.assertEqual(diagnostic["children_by_role"]["webview"]["checks_match_count"], 1)
        self.assertEqual(diagnostic["children_by_role"]["webview-network"]["checks_match_count"], 1)
        self.assertEqual(diagnostic["native_N12_acceptance"], "NOT_EVALUATED")
        rendered = json.dumps(diagnostic)
        for private in ("private", "pilotodin-desktop.exe", "msedgewebview2.exe",
                        str(ORIGIN), '"pid"', '"guid"'):
            self.assertNotIn(private, rendered)

    def test_no_cdp_sysmon_diagnostic_identifies_missing_and_mismatched_exit(self):
        original = deepcopy(self.rows)
        for case, expected, delta in (
            ("missing", "sysmon-exit-present", None),
            ("mismatch", "etw-exit-exactly-matches-sysmon", -10),
        ):
            with self.subTest(case=case):
                self.rows = deepcopy(original)
                if case == "missing":
                    self.rows = [row for row in self.rows
                                 if not (row[1] == 5 and row[2]["ProcessId"] == "702")]
                else:
                    for _, kind, fields in self.rows:
                        if kind == 5 and fields["ProcessId"] == "702":
                            fields["UtcTime"] = payload(650_010)[:-1]
                report = self.reduce(no_cdp_profile=True)
                self.assertEqual(report["verdict"], "BLOCKED")
                self.assertIn("no-cdp-sysmon-lifetime-unverified", report["issues"])
                child = report["no_cdp_sysmon_diagnostic"]["children_by_role"]["webview"]
                self.assertEqual(child["count"], 1)
                self.assertEqual(child["checks_match_count"], 0)
                self.assertEqual(child["failed_checks"].get(expected), 1)
                self.assertEqual(report["native_N12_acceptance"], "NOT_EVALUATED")
        self.rows = original

    def test_no_cdp_sysmon_diagnostic_reports_app_sysmon_exit_difference_from_handle(self):
        for _, kind, fields in self.rows:
            if kind == 5 and fields["ProcessId"] == "701":
                fields["UtcTime"] = payload(520_020)[:-1]
        report = self.reduce(no_cdp_profile=True)
        self.assertEqual(report["verdict"], "BLOCKED")
        diagnostic = report["no_cdp_sysmon_diagnostic"]["app"]
        self.assertIn("etw-exit-exactly-matches-sysmon", diagnostic["failed_checks"])
        self.assertEqual(diagnostic["etw_exit_minus_sysmon_exit_ticks"], -20)
        self.assertEqual(diagnostic["sysmon_exit_minus_handle_ticks"], 20)
        self.assertEqual(report["handle_comparison"]["app"], "BLOCKED")

    def test_no_cdp_sysmon_diagnostic_refuses_etw_pair_or_loss(self):
        self.events.pop(3)  # app stop missing
        report = self.reduce(no_cdp_profile=True)
        self.assertEqual(report["no_cdp_sysmon_diagnostic"]["app"]["failed_checks"],
                         ["etw-stop-missing-or-ambiguous"])
        self.assertEqual(report["verdict"], "BLOCKED")
        self.session["counters"]["events_lost"] = 1
        report = self.reduce(no_cdp_profile=True)
        self.assertEqual(report["verdict"], "BLOCKED")
        self.assertEqual(report["no_cdp_sysmon_diagnostic"]["status"], "NOT_EVALUATED")

    def test_no_cdp_sysmon_diagnostic_reports_sequence_image_and_window_failures(self):
        original = deepcopy(self.events)
        for case, expected in (
            ("wrong-sequence", "etw-sequence-conflict"),
            ("wrong-image", "etw-start-exact-image"),
            ("payload-outside-window", "etw-lifetime-payload-within-window"),
        ):
            with self.subTest(case=case):
                self.events = deepcopy(original)
                if case == "wrong-sequence":
                    self.events[3]["data"]["ProcessSequenceNumber"] = "999"
                elif case == "wrong-image":
                    self.events[2]["data"]["ImageName"] = r"c:\unknown\pilotodin-desktop.exe"
                else:
                    self.events[3]["data"]["ExitTime"] = payload(920_000)
                report = self.reduce(no_cdp_profile=True)
                self.assertEqual(report["verdict"], "BLOCKED")
                diagnostic = report["no_cdp_sysmon_diagnostic"]["app"]
                self.assertEqual(diagnostic["status"], "BLOCKED")
                self.assertIn(expected, diagnostic["failed_checks"])
                self.assertNotIn("pilotodin-desktop.exe", json.dumps(diagnostic))
        self.events = original

    def test_no_cdp_sysmon_diagnostic_reports_disputed_sysmon_exit(self):
        for _, kind, fields in self.rows:
            if kind == 5 and fields["ProcessId"] == "701":
                fields["Image"] = "private-opaque-image"
        report = self.reduce(no_cdp_profile=True)
        self.assertEqual(report["verdict"], "BLOCKED")
        diagnostic = report["no_cdp_sysmon_diagnostic"]["app"]
        self.assertIn("sysmon-exit-present", diagnostic["failed_checks"])
        self.assertIn("sysmon-exit-not-disputed", diagnostic["failed_checks"])
        self.assertEqual(diagnostic["etw_exit_minus_sysmon_exit_ticks"], None)

    def test_no_cdp_sysmon_diagnostic_is_absent_in_default_strict_mode(self):
        report = self.reduce()
        self.assertNotIn("no_cdp_sysmon_diagnostic", report)
        self.assertEqual(report["verdict"], "PASS")

    def test_shadow_design_retains_strict_exit_equality_block_on_observed_clock_offsets(self):
        # Use microsecond-representable reconstructions, not private trace.
        # 1 tick = 100 ns. These are not new acceptance thresholds.
        for _, kind, fields in self.rows:
            if kind == 5 and fields["ProcessId"] == "700":
                fields["UtcTime"] = payload(800_000 - 32_930)[:-1]
            if kind == 5 and fields["ProcessId"] == "701":
                fields["UtcTime"] = payload(520_000 - 77_620)[:-1]
        report = self.reduce(no_cdp_profile=True)
        self.assertEqual(report["verdict"], "BLOCKED")
        self.assertIn("no-cdp-sysmon-lifetime-unverified", report["issues"])
        reviewer = report["no_cdp_shadow_handle_witness_review"]
        self.assertEqual(reviewer["launcher"]["status"], "REVIEWABLE_ONLY")
        self.assertEqual(reviewer["app"]["status"], "REVIEWABLE_ONLY")
        self.assertEqual(reviewer["launcher"]["failed_checks"], [])
        self.assertEqual(reviewer["app"]["failed_checks"], [])
        self.assertEqual(reviewer["children_by_role"]["webview"]["retained_handle_witness_count"], 0)
        self.assertEqual(reviewer["children_by_role"]["webview-network"]["retained_handle_witness_count"], 0)
        self.assertEqual(reviewer["children_by_role"]["webview"]["failed_checks"],
                         {"retained-original-handle-unavailable": 1})
        self.assertEqual(reviewer["native_N12_acceptance"], "NOT_EVALUATED")
        rendered = json.dumps(reviewer)
        for private in ("private", "pilotodin-desktop.exe", "msedgewebview2.exe",
                        "guid", '"pid"', str(ORIGIN)):
            self.assertNotIn(private, rendered)

    def test_shadow_design_bad_handle_and_wrong_parent_are_never_reviewable(self):
        from qa.p4_native import n12_exit_corroboration as correlate
        with self.subTest("wrong handle pid"):
            events = [correlate.read_lifecycle(row) for row in self.events]
            lifetimes = correlate.EtwLifetimes(self.events, trace.etw_device_aliases(
                self.volume_devices), (ORIGIN, ORIGIN + 900_000),
                no_cdp_sysmon_corroboration=True)
            worker = SimpleNamespace(pid=700, start=stamp(50_000), end=stamp(800_000),
                                     disputed_exit=None, image=PYTHON)
            app = SimpleNamespace(pid=701, start=stamp(130_000), end=stamp(520_000),
                                  disputed_exit=None, image=APP)
            wrong = dict(self.app, pid=999)
            report = lifetimes.shadow_handle_exit_review(
                app, witness=wrong, parent=worker, require_parent=True)
            self.assertEqual(report["status"], "BLOCKED")
            self.assertIn("etw-original-handle-identity-or-clock-conflict", report["failed_checks"])
            self.assertEqual(report["native_N12_acceptance"], "NOT_EVALUATED")
        with self.subTest("parent sequence conflict"):
            self.events[2]["data"]["ParentProcessSequenceNumber"] = "999"
            lifetimes = correlate.EtwLifetimes(self.events, trace.etw_device_aliases(
                self.volume_devices), (ORIGIN, ORIGIN + 900_000),
                no_cdp_sysmon_corroboration=True)
            report = lifetimes.shadow_handle_exit_review(
                app, witness=self.app, parent=worker, require_parent=True)
            self.assertEqual(report["status"], "BLOCKED")
            self.assertIn("independent-etw-parent-identity-unverified", report["failed_checks"])

    def test_shadow_design_missing_child_handle_short_stop_and_bad_image_fail_closed(self):
        from qa.p4_native import n12_exit_corroboration as correlate
        devices = trace.etw_device_aliases(self.volume_devices)
        proc = SimpleNamespace(pid=702, start=stamp(210_000), end=stamp(650_000),
                               disputed_exit=None, image=WEBVIEW)
        parent = SimpleNamespace(pid=701, start=stamp(130_000), end=stamp(520_000),
                                 disputed_exit=None, image=APP)
        self.events[5]["data"]["ImageName"] = "msedgewebview2"  # observed 14-byte stop prefix
        lifetimes = correlate.EtwLifetimes(
            self.events, devices, (ORIGIN, ORIGIN + 900_000),
            no_cdp_sysmon_corroboration=True)
        without_handle = lifetimes.shadow_handle_exit_review(
            proc, parent=parent, require_parent=True)
        self.assertEqual(without_handle["status"], "BLOCKED")
        self.assertIn("retained-original-handle-unavailable", without_handle["failed_checks"])
        fake_handle = {"pid": 702, "birth": ORIGIN + 210_000,
                       "exit": ORIGIN + 650_000,
                       "image_dos": WEBVIEW, "image_native": WEBVIEW}
        with_handle = lifetimes.shadow_handle_exit_review(
            proc, witness=fake_handle, parent=parent, require_parent=True)
        self.assertEqual(with_handle["status"], "REVIEWABLE_ONLY")
        wrong_image = {**fake_handle, "image_native": APP}
        bad = lifetimes.shadow_handle_exit_review(
            proc, witness=wrong_image, parent=parent, require_parent=True)
        self.assertEqual(bad["status"], "BLOCKED")
        self.assertIn("short-stop-original-handle-images-unverified", bad["failed_checks"])
        self.assertEqual(bad["native_N12_acceptance"], "NOT_EVALUATED")

    def test_shadow_design_pid_reuse_sequence_and_missing_exit_fail_closed(self):
        from qa.p4_native import n12_exit_corroboration as correlate
        devices = trace.etw_device_aliases(self.volume_devices)
        proc = SimpleNamespace(pid=702, start=stamp(210_000), end=stamp(650_000),
                               disputed_exit=None, image=WEBVIEW)
        parent = SimpleNamespace(pid=701, start=stamp(130_000), end=stamp(520_000),
                                 disputed_exit=None, image=APP)
        handle = {"pid": 702, "birth": ORIGIN + 210_000,
                  "exit": ORIGIN + 650_000}
        for case, expected in (
            ("missing-exit", "sysmon-exit-present"),
            ("pid-reuse-ambiguous", "etw-start-missing-or-ambiguous"),
            ("duplicate-sequence", "etw-sequence-conflict"),
            ("wrong-image", "etw-start-exact-image"),
            ("bad-chronology", "etw-event-order-unverified"),
        ):
            with self.subTest(case=case):
                original = deepcopy(self.events)
                changed = deepcopy(original)
                observed = SimpleNamespace(**vars(proc))
                if case == "missing-exit":
                    observed.end = None
                elif case == "pid-reuse-ambiguous":
                    changed.append(deepcopy(changed[4]))
                elif case == "duplicate-sequence":
                    changed[5]["data"]["ProcessSequenceNumber"] = "999"
                elif case == "wrong-image":
                    changed[4]["data"]["ImageName"] = APP
                else:
                    changed[5]["ticks"] = changed[4]["ticks"]
                lifetimes = correlate.EtwLifetimes(
                    changed, devices, (ORIGIN, ORIGIN + 900_000),
                    no_cdp_sysmon_corroboration=True)
                report = lifetimes.shadow_handle_exit_review(
                    observed, witness=handle, parent=parent, require_parent=True)
                self.assertEqual(report["status"], "BLOCKED")
                self.assertIn(expected, report["failed_checks"])
                self.assertEqual(report["native_N12_acceptance"], "NOT_EVALUATED")
        self.assertEqual(self.reduce()["verdict"], "PASS")

    def test_shadow_design_never_appears_in_default_strict_reduction(self):
        report = self.reduce()
        self.assertNotIn("no_cdp_shadow_handle_witness_review", report)
        self.assertEqual(report["verdict"], "PASS")

    def test_no_cdp_missing_stage_markers_remains_blocked(self):
        report = self.reduce(no_cdp_profile=True)
        self.assertEqual(report["verdict"], "BLOCKED")
        self.assertEqual(report["native_N12_acceptance"], "NOT_EVALUATED")
        self.assertIn("no-cdp-os-stage-markers-unverified", report["issues"])
        self.assertEqual(report["no_cdp_profile_identity"]["file_event_coverage"], "NOT_EVALUATED")

    def test_no_cdp_etw_loss_blocks_before_identity_claim(self):
        self.session["counters"]["events_lost"] = 1
        with patch.object(lifetime.browser_identity, "verify_profile_shutdown") as verify:
            report = self.reduce(no_cdp_profile=True)
        self.assertEqual(report["verdict"], "BLOCKED")
        self.assertIn("etw-event-or-buffer-loss", report["issues"])
        verify.assert_not_called()

    def test_no_cdp_profile_verifier_invoked_only_with_reviewed_capture(self):
        from tests.test_p4_n12_exit_corroboration import stamp as moment
        self.manifest["markers"] = {k: moment(n).isoformat() for k, n in (
            ("launch", 150_000), ("ready", 250_000), ("close", 450_000),
            ("profile-exit", 750_000),
        )}
        self.manifest["observed_roots"] = {"qa-webview": "c:/qa/profile"}
        positive = SimpleNamespace(redacted_receipt=lambda: {
            "scope": "no-cdp-profile-shutdown-source-only",
            "native_N12_acceptance": "NOT_EVALUATED",
            "file_event_coverage": "NOT_EVALUATED",
            "network_isolation": "NOT_EVALUATED",
        })
        with patch.object(lifetime.browser_identity, "verify_profile_shutdown",
                          return_value=positive) as verify:
            report = self.reduce(no_cdp_profile=True)
        self.assertEqual(report["verdict"], "PASS")
        self.assertEqual(report["native_N12_acceptance"], "NOT_EVALUATED")
        self.assertEqual(report["no_cdp_profile_identity"]["status"], "SOURCE_OS_CORROBORATED")
        self.assertTrue(verify.call_args.kwargs["capture_loss_reviewed"])

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

    def test_no_cdp_native_header_shape_with_independent_sysmon_and_short_stop(self):
        # Synthetic reconstruction of observed header-offset categories,
        # not a replay of the actual private native trace.
        self.events[2]["ticks"] = ORIGIN + 130_000 - 237
        self.events[4]["ticks"] = ORIGIN + 210_000 - 1816
        self.events[5]["ticks"] = ORIGIN + 650_000 - 3584
        self.events[5]["data"]["ImageName"] = "msedgewebview2"
        self.events[6]["ticks"] = ORIGIN + 320_000 - 1282
        self.events[7]["ticks"] = ORIGIN + 690_000 - 3325
        self.events[7]["data"]["ImageName"] = "msedgewebview2"
        ordinary = self.reduce()
        self.assertEqual(ordinary["verdict"], "BLOCKED")
        self.assertIn("etw-lifetime-order-unverified", ordinary["issues"])
        scoped = self.reduce(no_cdp_profile=True)
        self.assertEqual(scoped["handle_comparison"], {"app": "MATCH", "launcher": "MATCH"})
        self.assertEqual(len(scoped["timing_comparisons"]), 4)
        self.assertNotIn("etw-lifetime-order-unverified", scoped["issues"])
        self.assertNotIn("etw-stop-image-conflict", scoped["issues"])
        self.assertEqual(scoped["verdict"], "BLOCKED")
        self.assertIn("no-cdp-os-stage-markers-unverified", scoped["issues"])
        self.assertEqual(scoped["native_N12_acceptance"], "NOT_EVALUATED")

    def test_no_cdp_missing_or_mismatched_independent_exit_blocks(self):
        self.events[4]["ticks"] = ORIGIN + 210_000 - 1816
        self.events[5]["ticks"] = ORIGIN + 650_000 - 3584
        self.events[5]["data"]["ImageName"] = "msedgewebview2"
        original_rows = deepcopy(self.rows)
        for case in ("missing", "wrong-exit"):
            with self.subTest(case=case):
                self.rows = deepcopy(original_rows)
                if case == "missing":
                    self.rows = [row for row in self.rows
                                 if not (row[1] == 5 and row[2]["ProcessId"] == "702")]
                else:
                    for _, kind, fields in self.rows:
                        if kind == 5 and fields["ProcessId"] == "702":
                            fields["UtcTime"] = payload(650_010)[:-1]
                result = self.reduce(no_cdp_profile=True)
                self.assertEqual(result["verdict"], "BLOCKED")
                self.assertIn("no-cdp-sysmon-lifetime-unverified", result["issues"])
        self.rows = original_rows

    def test_no_cdp_wrong_stop_name_and_sequence_still_block(self):
        for case in ("wrong-name", "wrong-sequence"):
            with self.subTest(case=case):
                original = deepcopy(self.events)
                self.events[4]["ticks"] = ORIGIN + 210_000 - 1816
                self.events[5]["ticks"] = ORIGIN + 650_000 - 3584
                if case == "wrong-name":
                    self.events[5]["data"]["ImageName"] = "otherwebview2"
                else:
                    self.events[5]["data"]["ProcessSequenceNumber"] = "999"
                result = self.reduce(no_cdp_profile=True)
                self.assertEqual(result["verdict"], "BLOCKED")
                self.assertTrue(any(issue in result["issues"] for issue in
                                    ("etw-stop-image-conflict", "etw-sequence-conflict")))
                self.events = original

    def test_exact_original_handles_corroborate_observed_early_stop_headers(self):
        self.events[1]["ticks"] = self.worker["exit"] - 1041
        self.events[3]["ticks"] = self.app["exit"] - 935
        report = self.reduce()
        self.assertEqual(report["verdict"], "PASS")
        self.assertEqual(report["handle_comparison"], {"app": "MATCH", "launcher": "MATCH"})
        self.assertEqual(len(report["timing_comparisons"]), 4)
        for role, expected in (("launcher", -1041), ("app", -935)):
            observed = report["etw_handle_order_comparison"][role]
            self.assertEqual(observed["stop_emission_minus_exit_ticks"], expected)
            self.assertEqual(observed["etw_payload_exit_minus_handle_ticks"], 0)

    def test_early_stop_header_for_a_child_without_an_original_handle_still_blocks(self):
        self.events[5]["ticks"] -= 101
        report = self.reduce()
        self.assertEqual(report["verdict"], "BLOCKED")
        self.assertIn("etw-lifetime-order-unverified", report["issues"])
        self.assertEqual(report["handle_comparison"], {"app": "MATCH", "launcher": "MATCH"})
        rows = report["etw_child_order_comparisons"]
        self.assertIn(("webview", -1), [(row["role"], row["stop_emission_minus_exit_ticks"]) for row in rows])

    def test_matching_handle_exit_outside_the_capture_window_still_blocks(self):
        self.worker["exit"] = ORIGIN + 900_010
        self.events[1]["data"]["ExitTime"] = payload(900_010)
        report = self.reduce()
        self.assertEqual(report["verdict"], "BLOCKED")
        self.assertIn("etw-lifetime-order-unverified", report["issues"])

    def test_ordering_report_preserves_ambiguous_or_missing_pair_outcomes(self):
        self.events.append(deepcopy(self.events[0]))
        self.events.pop(3)
        report = self.reduce()
        self.assertEqual(report["verdict"], "BLOCKED")
        self.assertEqual(report["etw_handle_order_comparison"], {
            "launcher": {"issue": "etw-start-missing-or-ambiguous"},
            "app": {"issue": "etw-stop-missing-or-ambiguous"},
        })

    def test_truncated_stop_basename_is_described_and_still_blocks(self):
        self.events[1]["data"]["ImageName"] = "python.exe"
        self.events[3]["data"]["ImageName"] = "pilotodin-desk"
        self.events[5]["data"]["ImageName"] = r"c:\other\msedgewebview2.exe"
        report = self.reduce()
        self.assertEqual(report["verdict"], "BLOCKED")
        self.assertIn("etw-stop-image-conflict", report["issues"])
        self.assertEqual(report["handle_comparison"], {"app": "BLOCKED", "launcher": "MATCH"})
        self.assertEqual(report["etw_stop_image_comparisons"], {
            "launcher": {"exact-basename-match": 1},
            "app": {"short-basename-prefix": 1},
            "webview": {"different-path-same-basename": 1},
            "webview-network": {"exact-path-match": 1},
        })
        rendered = json.dumps(report)
        for private in ("pilotodin-desk", "msedgewebview2.exe", "python.exe"):
            self.assertNotIn(private, rendered)

    def test_observed_length_stop_prefix_requires_two_exact_original_handle_paths(self):
        self.app.update(image_dos=APP, image_native=r"\Device\HarddiskVolume3\qa\build\pilotodin-desktop.exe")
        self.events[3]["data"]["ImageName"] = "pilotodin-desk"
        report = self.reduce()
        self.assertEqual(report["verdict"], "PASS")
        self.assertEqual(report["handle_comparison"], {"app": "MATCH", "launcher": "MATCH"})
        self.assertEqual(report["etw_stop_image_comparisons"]["app"], {"short-basename-prefix": 1})
        self.assertNotIn("pilotodin-desk", json.dumps(report))
        for wrong_stop in ("pilotodin-deskt", "pilotodin-des", r"c:\other\pilotodin-desktop.exe"):
            with self.subTest(wrong_stop=wrong_stop):
                self.events[3]["data"]["ImageName"] = wrong_stop
                self.assertIn("etw-stop-image-conflict", self.reduce()["issues"])
        self.events[3]["data"]["ImageName"] = "pilotodin-desk"
        self.app["image_native"] = r"\Device\HarddiskVolume3\other\pilotodin-desktop.exe"
        self.assertIn("etw-stop-image-conflict", self.reduce()["issues"])

    def test_short_stop_name_of_a_child_without_original_handle_still_blocks(self):
        self.events[5]["data"]["ImageName"] = "msedgewebview2"
        report = self.reduce()
        self.assertEqual(report["handle_comparison"], {"app": "MATCH", "launcher": "MATCH"})
        self.assertIn("etw-stop-image-conflict", report["issues"])

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
        rendered = json.dumps(report)
        for private in ("private", "HarddiskVolume99", "pilotodin-desktop", "other-image", "msedgewebview2", '"700"'):
            self.assertNotIn(private, rendered)
        self.assertNotRegex(rendered, r'"(?:\w+_)?(?:pid|guid|process_id|sequence)"\s*:')

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
                    lifetime.journey.request_graceful_close(app, APP, "PilotODIN QA")

    def test_cli_and_workflow_enforce_separate_lifetime_approval(self):
        with patch.dict(lifetime.os.environ, {"PILOTODIN_N12_APP_LIFETIME_CONSENT": "other"}):
            run = subprocess.run([sys.executable, "-B", "-m", lifetime.__name__, "--source", SOURCE,
                "--expected-exe-sha256", HASH, "--worker"], capture_output=True, text=True)
        self.assertEqual(run.returncode, 2)
        self.assertIn("separate one-run N12 app lifetime consent is required", run.stderr)
        workflow = (lifetime.build.REPO / ".github/workflows/p4-n12-app-lifetime.yml").read_text(encoding="utf-8")
        marker_path = "qa/p4_research/N12_APP_LIFETIME_STOP_PREFIX_RETEST_APPROVAL.txt"
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
