import csv
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from qa.p4_native import n12_trace as trace
from qa.p4_research import n12_app_lifetime as lifetime
from qa.p4_research import n12_webview_storage_probe as probe
from qa.p4_research import n12_webview_storage_compare as comparison
from qa.p4_research.n12_app_journey import APP_TEMP_DIR, app_environment
from qa.p4_research.n12_journey_diagnostics import OutsidePaths


START = datetime(2026, 11, 19, 10, tzinfo=timezone.utc)
APP = r"c:\fixture\pilotodin.exe"
PYTHON = r"c:\fixture\python.exe"
WEBVIEW = r"c:\fixture\1.2.3.4\msedgewebview2.exe"
SCRATCH = r"c:\fixture\scratch"
LOCAL = r"c:\private-user\local"
USER_TEMP = LOCAL + r"\temp"
PROTECTED = r"c:\protected-original"
CSV = r"c:\fixture\immutable.csv"
CONTROL_SCRATCH = SCRATCH + r"\distinct-scratch-control.tmp"
CONTROL_TEMP = USER_TEMP + r"\distinct-user-control.tmp"
TARGET = USER_TEMP + r"\private-filename.xyz"
SOURCE = "1" * 40
HASH = "2" * 64


def time_at(seconds):
    return START + timedelta(seconds=seconds)


def process(guid, parent, pid, image, start, end, command="", sha=None):
    return trace.Process(guid, parent, pid, image, sha, time_at(start), command, time_at(end))


def row(seconds, pid, image, path, *, detail="OpenResult: Created", result="SUCCESS", op="CreateFile"):
    return {"Time of Day":time_at(seconds).strftime("%H:%M:%S.%f"), "PID":pid,
            "Process Name":image, "Operation":op, "Path":path, "Result":result, "Detail":detail}


class StorageProbeTests(unittest.TestCase):
    def setUp(self):
        self.processes = {item.guid: item for item in (
            process("app", "parent", 100, APP, 5, 14, sha=HASH),
            process("renderer", "app", 101, WEBVIEW, 6, 13, command="--type=renderer"),
            process("control-one", "parent", 200, PYTHON, 2, 4),
            process("control-two", "parent", 201, PYTHON, 16, 18),
        )}
        self.manifest = {
            "source_sha": SOURCE, "executable_sha256": HASH,
            "protected_roots": {"original": PROTECTED},
            "observed_roots": {"quality-source": CSV, "qa-webview": SCRATCH},
            "immutable_observed": ["quality-source"], "permitted_writes": {"webview":[SCRATCH]},
            "protected_snapshot_comparison": "MATCH", "procmon_all_events": True, "procmon_clock_utc": True,
            "procmon_shutdown_verified": True,
            "markers": {key:time_at(at).isoformat() for key, at in (
                ("fixture-ready", 1), ("launch", 5), ("ready", 8), ("close", 10), ("profile-exit", 15),
            )},
            "processes": [
                {"role":"app", "pid":100, "image":APP},
                {"role":"calibration", "pid":200, "image":PYTHON, "label":"scratch", "target":CONTROL_SCRATCH},
                {"role":"calibration", "pid":201, "image":PYTHON, "label":"user-temp", "target":CONTROL_TEMP},
            ],
        }
        self.controls = [row(3, 200, "python.exe", CONTROL_SCRATCH), row(17, 201, "python.exe", CONTROL_TEMP)]

    def reduce(self, rows, *, etw_events=None, etw_loss=0, wrong_digest=False):
        categories = OutsidePaths([("qa-webview-profile", SCRATCH), ("user-temp", USER_TEMP), ("user-local", LOCAL)])
        with TemporaryDirectory() as folder, patch.object(
            probe.trace, "load_capture",
            return_value=(START, time_at(20), self.processes, [], {"procmon-coverage-not-confirmed"}),
        ), patch.object(probe.journey, "diagnostic_paths", return_value=categories):
            path = Path(folder) / "procmon.csv"
            with path.open("w", newline="", encoding="utf-8") as stream:
                writer = csv.DictWriter(stream, fieldnames=self.controls[0])
                writer.writeheader()
                writer.writerows(rows)
            manifest = self.manifest.copy()
            etw = None
            if etw_events is not None:
                etw = Path(folder) / "etw.jsonl"
                encoded = "".join(json.dumps(event) + "\n" for event in etw_events).encode()
                etw.write_bytes(encoded)
                manifest["etw"] = {
                    "schema_version": 1, "start_utc": START.isoformat(), "end_utc": time_at(20).isoformat(),
                    "events_sha256": "0" * 64 if wrong_digest else hashlib.sha256(encoded).hexdigest(),
                    "volume_devices": {"C:": r"\Device\HarddiskVolume3"},
                    "counters": {"events_lost": etw_loss, "log_buffers_lost": 0,
                                 "realtime_buffers_lost": 0, "buffers_written": 1},
                }
            return probe.reduce(None, None, manifest, None, path, replay_etw=etw)

    def test_reproduced_rows_keep_component_and_stage_and_hide_private_values(self):
        rows = self.controls + [
            row(0, 101, "msedgewebview2.exe", CSV),
            row(7, 101, "msedgewebview2.exe", TARGET),
            row(11, 101, "msedgewebview2.exe", LOCAL + r"\Microsoft\EdgeWebView\private.xyz", op="WriteFile"),
        ]
        report = self.reduce(rows)
        self.assertEqual(report["verdict"], "REPRODUCED")
        self.assertEqual(report["known_create_controls"], {"scratch":True, "user-temp":True})
        self.assertEqual(report["ambient_temp_creates"], 1)
        self.assertEqual(report["webview_runtime_versions"], ["1.2.3.4"])
        self.assertEqual(report["storage_events"], [
            {"destination_family":"edge-webview", "operation":"write", "component":"renderer",
             "stage":"close", "file_type":"other-extension", "count":1},
            {"destination_family":"user-temp", "operation":"create", "component":"renderer",
             "stage":"startup", "file_type":"other-extension", "count":1},
        ])
        self.assertFalse(report["procmon_loss_reviewed"])
        self.assertTrue(report["procmon_shutdown_verified"])
        self.assertNotIn("private", json.dumps(report))
        self.assertNotIn("distinct-user-control", json.dumps(report))

    def test_zero_target_events_is_inconclusive_when_both_controls_are_valid(self):
        rows = self.controls + [row(9, 101, "msedgewebview2.exe", TARGET, detail="OpenResult: Opened")]
        report = self.reduce(rows)
        self.assertEqual(report["verdict"], "INCONCLUSIVE")
        self.assertEqual(report["ambient_temp_creates"], 0)

    def test_focused_launch_changes_only_tmp(self):
        profile = Path("webview-fixture")
        baseline = app_environment({}, profile, "first")
        self.assertEqual(lifetime.storage_app_environment({}, profile),
                         {**baseline, "TMP": str(profile / APP_TEMP_DIR / lifetime.STORAGE_TMP_DIR)})

    def test_focused_backend_uses_existing_generated_home_and_import_only_source(self):
        with TemporaryDirectory() as folder:
            home = Path(folder) / "qa-home"
            environment = {"PILOTODIN_HOME": str(home), "PYTHONPATH": "generated-extra"}
            with self.assertRaisesRegex(trace.EvidenceValidationError, "data home is missing"):
                lifetime.backend_launch_context(environment, home)
            home.mkdir()
            backend_env, backend_cwd = lifetime.backend_launch_context(environment, home)
            self.assertEqual(backend_cwd, home)
            self.assertEqual(backend_env["PILOTODIN_HOME"], str(home))
            self.assertEqual(backend_env["PYTHONPATH"].split(os.pathsep)[0], str(lifetime.build.REPO))
            self.assertIn("generated-extra", backend_env["PYTHONPATH"])
            self.assertEqual(environment["PYTHONPATH"], "generated-extra")
            self.assertNotEqual(backend_cwd, lifetime.build.REPO)

    def test_debug_variant_changes_only_netlog_not_storage_or_readiness(self):
        profile = Path("webview-fixture")
        baseline = lifetime.storage_app_environment({}, profile, variant="debug-netlog")
        debug_only = lifetime.storage_app_environment({}, profile, variant="debug-only")
        self.assertEqual(baseline["WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS"],
                         app_environment({}, profile, "first")["WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS"])
        self.assertEqual(debug_only["WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS"],
                         "--remote-debugging-port=9331")
        self.assertEqual({key: value for key, value in baseline.items()
                          if key != "WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS"},
                         {key: value for key, value in debug_only.items()
                          if key != "WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS"})
        self.assertEqual(lifetime.readiness_command("node", storage=True),
                         ["node", str(lifetime.READY_PROBE), "webview-storage"])
        with self.assertRaisesRegex(trace.EvidenceValidationError, "unknown WebView"):
            lifetime.storage_app_environment({}, profile, variant="no-debugger")

    def test_startup_tmp_probe_distinguishes_launch_tmp_scratch_and_ambient(self):
        self.manifest["startup_tmp_probe"] = True
        self.manifest["observed_roots"]["qa-webview"] = SCRATCH
        app_temp = SCRATCH + "\\" + APP_TEMP_DIR
        tmp_witness = app_temp + "\\" + lifetime.STORAGE_TMP_DIR
        rows = self.controls + [
            row(7, 101, "msedgewebview2.exe", tmp_witness + r"\private-test.tmp"),
            row(7, 101, "msedgewebview2.exe", app_temp + r"\private-sibling.tmp"),
            row(7, 101, "msedgewebview2.exe", USER_TEMP + r"\private-ambient.tmp"),
            row(9, 101, "msedgewebview2.exe", tmp_witness + r"\ignored-after-startup.tmp"),
        ]
        report = self.reduce(rows)
        self.assertTrue(report["startup_tmp_probe"])
        self.assertEqual(report["ambient_temp_creates"], 1)
        self.assertEqual({r["destination_family"]: (r["stage"], r["count"]) for r in report["storage_events"]},
                         {family: ("startup", 1) for family in ("startup-tmp", "qa-app-temp", "user-temp")})
        self.assertNotIn("private-test", json.dumps(report))

    def test_unverified_shutdown_blocks_but_retains_corroborated_observations(self):
        for shutdown_verified in (False, None, "true"):
            with self.subTest(shutdown_verified=shutdown_verified):
                self.manifest["procmon_shutdown_verified"] = shutdown_verified
                report = self.reduce(self.controls + [row(7, 101, "msedgewebview2.exe", TARGET)])
                self.assertEqual(report["verdict"], "BLOCKED")
                self.assertEqual(report["issues"], ["procmon-shutdown-unverified"])
                self.assertFalse(report["procmon_shutdown_verified"])
                self.assertEqual(report["known_create_controls"], {"scratch":True, "user-temp":True})
                self.assertEqual(report["ambient_temp_creates"], 1)
                self.assertEqual(report["storage_events"][0]["component"], "renderer")
                self.assertNotIn("private", json.dumps(report))

    def test_wrong_writer_or_failed_create_blocks_despite_a_reproduced_target(self):
        for invalid in (row(3, 201, "python.exe", CONTROL_SCRATCH),
                        row(3, 200, "python.exe", CONTROL_SCRATCH, result="ACCESS DENIED")):
            with self.subTest(invalid=invalid):
                report = self.reduce([invalid, self.controls[1], row(7, 101, "msedgewebview2.exe", TARGET)])
                self.assertEqual(report["verdict"], "BLOCKED")
                self.assertIn("known-create-controls-unverified", report["issues"])

    def test_ambiguous_pid_does_not_attribute_the_create(self):
        self.processes["overlap"] = process("overlap", "unrelated", 101, WEBVIEW, 6, 12)
        report = self.reduce(self.controls + [row(7, 101, "msedgewebview2.exe", TARGET)])
        self.assertEqual(report["ambient_temp_creates"], 0)
        self.assertEqual(report["verdict"], "BLOCKED")
        self.assertIn("file-event-process-ambiguous", report["file_coverage_issues"])

    def test_cdp_browser_pid_attributes_events_on_both_sides_of_readiness(self):
        browser = process("browser", "app", 102, WEBVIEW, 6, 13)
        self.processes[browser.guid] = browser
        self.manifest["cdp_browser_pid"] = browser.pid
        report = self.reduce(self.controls + [row(at, browser.pid, "msedgewebview2.exe", TARGET) for at in (7, 9)])
        self.assertTrue(report["browser_process_corroborated"])
        self.assertEqual({item["stage"]:item["component"] for item in report["storage_events"]},
                         {"startup":"browser", "ready-probe":"browser"})
        self.assertNotIn("cdp_browser_pid", report)

    def test_startup_tmp_requires_replayable_control_and_matching_browser_start(self):
        self.manifest.update(startup_tmp_probe=True, cdp_browser_pid=102, probe_user_temp=USER_TEMP)
        self.manifest["observed_roots"]["qa-webview"] = SCRATCH
        tmp_witness = SCRATCH + "\\" + APP_TEMP_DIR + "\\" + lifetime.STORAGE_TMP_DIR
        launcher = process("launcher", "other", 99, PYTHON, 1, 19)
        browser = process("browser", "app", 102, WEBVIEW, 6, 13, command="generated-browser-command")
        self.processes.update(launcher=launcher, browser=browser)
        scratch = self.processes["control-one"]
        scratch.parent = launcher.guid
        scratch.command = "generated-control-command"

        def start_row(at, child, parent, environment):
            detail = (f"Parent PID: {parent.pid}, Command line: {child.command} , "
                      f"Current directory: c:\\fixture, Environment:{environment}")
            return row(at, child.pid, child.image.rsplit("\\", 1)[1], "", op="Process Start", detail=detail)

        scratch_start = start_row(2, scratch, launcher, f" ; TMP={tmp_witness} ; PRIVATE=secret-control")
        browser_start = start_row(6, browser, self.processes["app"], f"\r\nTMP={USER_TEMP}\r\nPRIVATE=secret-browser")
        report = self.reduce(self.controls + [scratch_start, browser_start])
        self.assertTrue(report["startup_tmp_control_verified"])
        self.assertEqual(report["browser_startup_tmp"], "ambient-temp")
        self.assertEqual(report["startup_tmp_receipts"], {"scratch": "expected-tmp", "browser": "tmp-observed"})
        self.assertNotIn("secret-", json.dumps(report))
        self.assertNotIn("generated-browser-command", json.dumps(report))

        expected = start_row(6, browser, self.processes["app"], f" ; Tmp={tmp_witness} ; TEMP={USER_TEMP}")
        report = self.reduce(self.controls + [scratch_start, expected])
        self.assertEqual(report["browser_startup_tmp"], "expected-tmp")

        wrong_parent = start_row(6, browser, launcher, f" ; TMP={tmp_witness}")
        duplicate_tmp = start_row(6, browser, self.processes["app"], f" ; TMP={tmp_witness} ; Tmp={USER_TEMP}")
        for starts, reasons in (
            ([expected], ("start-record-unobserved", "tmp-observed")),
            ([scratch_start, wrong_parent], ("expected-tmp", "start-identity-mismatch")),
            ([scratch_start, duplicate_tmp], ("expected-tmp", "tmp-ambiguous")),
            ([scratch_start, expected, browser_start], ("expected-tmp", "start-record-ambiguous")),
        ):
            with self.subTest(reasons=reasons):
                report = self.reduce(self.controls + starts)
                self.assertEqual(report["browser_startup_tmp"], "unverified")
                self.assertEqual(report["startup_tmp_receipts"], dict(zip(("scratch", "browser"), reasons)))

        browser_create = row(7, browser.pid, "msedgewebview2.exe", USER_TEMP + r"\private-first.tmp")
        later_create = row(7.75, browser.pid, "msedgewebview2.exe", USER_TEMP + r"\private-later.tmp")
        for receipt_at, expected in ((6, "expected-tmp"), (7, "unverified"), (7.5, "unverified")):
            with self.subTest(browser_receipt=receipt_at):
                receipt = start_row(receipt_at, browser, self.processes["app"], f" ; TMP={tmp_witness}")
                report = self.reduce(self.controls + [later_create, receipt, scratch_start, browser_create])
                self.assertEqual(report["browser_startup_tmp"], expected)
                if expected == "unverified":
                    self.assertEqual(report["startup_tmp_receipts"]["browser"], "start-order-unverified")
                self.assertEqual(report["ambient_temp_creates"], 2)

        for receipt_at in (3, 4):
            with self.subTest(scratch_receipt=receipt_at):
                late_scratch = start_row(receipt_at, scratch, launcher, f" ; TMP={tmp_witness}")
                report = self.reduce(self.controls + [late_scratch, browser_start])
                self.assertEqual(report["browser_startup_tmp"], "unverified")
                self.assertFalse(report["startup_tmp_control_verified"])
                self.assertEqual(report["startup_tmp_receipts"]["scratch"], "start-order-unverified")

    def test_generated_procmon_receipt_joins_only_verified_etw_startup_creates(self):
        self.manifest.update(startup_tmp_probe=True, cdp_browser_pid=102, probe_user_temp=USER_TEMP,
                             procmon_shutdown_verified=False)
        self.manifest["observed_roots"]["qa-webview"] = SCRATCH
        witness = SCRATCH + "\\" + APP_TEMP_DIR + "\\" + lifetime.STORAGE_TMP_DIR
        self.processes["browser"] = process("browser", "app", 102, WEBVIEW, 6, 13, command="browser-command")
        self.processes["parent"] = process("parent", "other", 99, PYTHON, 0, 19)
        self.processes["control-one"].command = "control-command"

        def start_row(at, pid, image, parent, command):
            detail = (f"Parent PID: {parent}, Command line: {command}, Current directory: {SCRATCH},"
                      f" Environment:\tTMP={witness}")
            return row(at, pid, image, "", op="Process Start", detail=detail)

        scratch = start_row(2, 200, "python.exe", 99, "control-command")
        browser = start_row(6.1, 102, "msedgewebview2.exe", 100, "browser-command")
        rows = self.controls + [scratch, browser]

        def event(at, kind, pid, *, lifecycle=False, **data):
            return {"ticks": trace.utc_ticks(time_at(at)), "id": kind, "pid": pid,
                    "version": 3, "lifecycle": lifecycle, "data": data}

        def start(at, pid, parent, image, sequence, parent_sequence):
            return event(at, 1, 0, lifecycle=True, ProcessID=str(pid), ParentProcessID=str(parent),
                         CreateTime=time_at(at).isoformat(), ImageName=image,
                         ProcessSequenceNumber=str(sequence), ParentProcessSequenceNumber=str(parent_sequence))

        app_birth = start(5, 100, 99, APP, 10, 9)
        browser_birth = start(6, 102, 100, WEBVIEW, 11, 10)
        target = USER_TEMP + r"\private-browser-create.tmp"
        request = event(7, 12, 102, FileObject=21, Irp=31, FileName=target)
        completion = event(7.1, 24, 0, Irp=31, Status=0, ExtraInformation=2)
        etw = [app_birth, browser_birth, request, completion]
        report = self.reduce(rows, etw_events=etw)
        self.assertEqual(report["startup_tmp_etw"], {
            "status": "matched", "launch_tmp": "expected-tmp", "destination_families": ["user-temp"],
        })
        self.assertEqual(report["ambient_temp_creates"], 0)
        self.assertEqual(report["issues"], ["procmon-shutdown-unverified"])
        self.assertEqual(report["verdict"], "BLOCKED")
        self.assertNotIn("private-", json.dumps(report))
        self.assertNotIn("browser-command", json.dumps(report))

        for inputs, records, reason in (
            (rows[:-1], etw, "procmon-tmp-receipt-unverified"),
            (rows + [browser], etw, "procmon-tmp-receipt-unverified"),
            (rows[:-1] + [start_row(6.1, 102, "msedgewebview2.exe", 99, "browser-command")],
             etw, "procmon-tmp-receipt-unverified"),
            (rows, [app_birth, request, completion], "etw-browser-lifetime-unverified"),
            (rows, etw + [browser_birth], "etw-browser-lifetime-unverified"),
            (rows, etw + [event(7.05, 2, 0, lifecycle=True, ProcessID="102", ProcessSequenceNumber="11",
                                CreateTime=time_at(6).isoformat(), ExitTime=time_at(7.05).isoformat())],
             "etw-browser-lifetime-unverified"),
            (rows, [app_birth, start(6, 102, 100, WEBVIEW, 11, 9), request, completion],
             "etw-parent-sequence-conflict"),
            (rows, [app_birth, start(6, 102, 100, WEBVIEW.replace("fixture", "different"), 11, 10),
                    request, completion], "etw-child-birth-image-unverified"),
            (rows, [app_birth, browser_birth, {**request, "pid": 101}, completion],
             "no-matched-etw-startup-create"),
            (rows, etw[:-1], "no-matched-etw-startup-create"),
            (rows, etw[:-1] + [event(7.1, 24, 0, Irp=31, Status=0, ExtraInformation=2, FileObject=99)],
             "no-matched-etw-startup-create"),
            (rows, etw[:-1] + [event(7.1, 24, 0, Irp=31, Status=0xC0000035, ExtraInformation=2)],
             "no-matched-etw-startup-create"),
            (rows, [app_birth, browser_birth, event(6.1, 12, 102, FileObject=21, Irp=31, FileName=target),
                    completion], "no-matched-etw-startup-create"),
            (rows, etw[:-1] + [event(8, 24, 0, Irp=31, Status=0, ExtraInformation=2)],
             "no-matched-etw-startup-create"),
        ):
            with self.subTest(reason=reason):
                self.assertEqual(self.reduce(inputs, etw_events=records)["startup_tmp_etw"], {"status": reason})
        for options, reason in (({"etw_loss": 1}, "etw-event-or-buffer-loss"),
                                ({"wrong_digest": True}, "etw-evidence-invalid")):
            with self.subTest(reason=reason):
                self.assertEqual(self.reduce(rows, etw_events=etw, **options)["startup_tmp_etw"],
                                 {"status": reason})

    def test_cdp_browser_pid_cannot_override_conflicting_lifetime_or_process_type(self):
        browser = process("browser", "app", 102, WEBVIEW, 6, 13)
        self.processes[browser.guid] = browser
        self.manifest["cdp_browser_pid"] = browser.pid
        self.processes["reused"] = process("reused", "unrelated", 102, PYTHON, 9, 13)
        rows = self.controls + [row(7, browser.pid, "msedgewebview2.exe", TARGET)]
        report = self.reduce(rows)
        self.assertFalse(report["browser_process_corroborated"])
        self.assertEqual(report["storage_events"][0]["component"], "unclassified")

        del self.processes["reused"]
        self.manifest["cdp_browser_pid"] = 101
        report = self.reduce(self.controls + [row(7, 101, "msedgewebview2.exe", TARGET)])
        self.assertFalse(report["browser_process_corroborated"])
        self.assertEqual(report["storage_events"][0]["component"], "renderer")

    def test_protected_write_blocks_even_with_matching_endpoints(self):
        report = self.reduce(self.controls + [
            row(7, 101, "msedgewebview2.exe", TARGET),
            row(8, 101, "msedgewebview2.exe", CSV, op="WriteFile"),
            row(8, 244, "private-background.exe", PROTECTED + r"\private-file", op="WriteFile"),
        ])
        self.assertEqual(report["verdict"], "BLOCKED")
        self.assertIn("protected-files-changed-or-unverified", report["issues"])
        self.assertEqual(report["protected_operations"], [
            {"role":"other", "operation":"write", "count":1},
            {"role":"webview", "operation":"write", "count":1},
        ])
        self.assertEqual(report["protected_operation_details"], [
            {"role":"other", "operation":"write", "target":"protected-app-data", "identity":"unmatched", "count":1},
            {"role":"webview", "operation":"write", "target":"immutable-input", "identity":"matched", "count":1},
        ])
        self.assertNotIn("immutable.csv", json.dumps(report))
        self.assertNotIn("private-background", json.dumps(report))

    def test_wrong_app_digest_blocks(self):
        self.processes["app"].sha256 = "3" * 64
        report = self.reduce(self.controls + [row(7, 101, "msedgewebview2.exe", TARGET)])
        self.assertEqual(report["verdict"], "BLOCKED")
        self.assertIn("app-source-identity-unverified", report["issues"])

    def test_writer_storage_context_correlates_process_start_without_private_paths(self):
        browser = process("browser", "app", 102, WEBVIEW, 6, 13,
                          command="--remote-debugging-port=9331 --log-net-log=c:\\private\\secret.json")
        self.processes[browser.guid] = browser
        self.manifest.update(cdp_browser_pid=102, probe_user_temp=USER_TEMP)
        env = (f" ; TEMP={SCRATCH}\\app-temp ; TMP={USER_TEMP} ; "
               f"WEBVIEW2_USER_DATA_FOLDER={SCRATCH} ; SECRET=private-token")

        def started(child):
            parent = self.processes[child.parent]
            detail = (f"Parent PID: {parent.pid}, Command line: {child.command}, "
                      f"Current directory: c:\\fixture, Environment:{env}")
            return row(6, child.pid, "msedgewebview2.exe", "", detail=detail, op="Process Start")

        report = self.reduce(self.controls + [
            started(browser), started(self.processes["renderer"]),
            row(7, 102, "msedgewebview2.exe", USER_TEMP + r"\\private-browser.tmp"),
            row(7, 101, "msedgewebview2.exe", USER_TEMP + r"\\private-renderer.tmp"),
        ])
        self.assertFalse(report["storage_context_is_acceptance_evidence"])
        self.assertEqual(report["storage_diagnostic_variant"], "debug-netlog")
        self.assertEqual(report["browser_variant_corroboration"], "agrees")
        self.assertEqual(report["browser_launch_flags"], {
            "status": "environment-observed", "remote_debugging": "present", "netlog": "present",
        })
        contexts = report["writer_storage_context"]
        self.assertEqual({item["component"] for item in contexts}, {"browser", "renderer"})
        for item in contexts:
            self.assertEqual(item["receipt"], "environment-observed")
            self.assertEqual((item["temp"], item["tmp"], item["udf"]),
                             ("declared-app-temp", "ambient-temp", "declared-profile"))
            self.assertEqual((item["destination_family"], item["operation"], item["count"]),
                             ("user-temp", "create", 1))
        rendered = json.dumps(report)
        for secret in ("private-token", "private-browser", "private-renderer", "secret.json"):
            self.assertNotIn(secret, rendered)
        self.assertEqual(report["verdict"], "REPRODUCED")

    def test_variant_comparison_is_descriptive_not_an_acceptance_override(self):
        browser = process("browser", "app", 102, WEBVIEW, 6, 13,
                          command="--remote-debugging-port=9331")
        self.processes[browser.guid] = browser
        self.manifest.update(cdp_browser_pid=102, probe_user_temp=USER_TEMP,
                             storage_diagnostic_variant="debug-only")
        parent = self.processes["app"]
        start = row(6, 102, "msedgewebview2.exe", "", op="Process Start",
                    detail=(f"Parent PID: {parent.pid}, Command line: {browser.command}, "
                            f"Current directory: c:\\fixture, Environment: "
                            f" ; TEMP={SCRATCH}\\app-temp ; TMP={SCRATCH}\\app-temp "
                            f" ; WEBVIEW2_USER_DATA_FOLDER={SCRATCH}"))
        rows = self.controls + [start, row(7, 102, "msedgewebview2.exe", TARGET)]
        report = self.reduce(rows)
        self.assertEqual(report["storage_diagnostic_variant"], "debug-only")
        self.assertEqual(report["browser_variant_corroboration"], "agrees")
        self.assertEqual(report["ambient_temp_creates"], 1)
        self.assertEqual(report["verdict"], "REPRODUCED")
        self.assertFalse(report["storage_context_is_acceptance_evidence"])

        self.manifest["storage_diagnostic_variant"] = "debug-netlog"
        self.assertEqual(self.reduce(rows)["browser_variant_corroboration"], "disagrees")
        self.manifest["cdp_browser_pid"] = 999
        self.assertEqual(self.reduce(rows)["browser_variant_corroboration"], "unverified")
        self.manifest["storage_diagnostic_variant"] = "invalid-variant"
        with self.assertRaisesRegex(trace.EvidenceValidationError, "unknown WebView"):
            self.reduce(rows)

    def test_writer_context_rejects_wrong_parent_and_duplicate_start_receipts(self):
        child = self.processes["renderer"]
        detail = (f"Parent PID: 999, Command line: {child.command}, "
                  f"Current directory: c:\\fixture, Environment: ; TMP={SCRATCH}\\app-temp")
        start = row(6, child.pid, "msedgewebview2.exe", "", detail=detail, op="Process Start")
        write = row(7, child.pid, "msedgewebview2.exe", TARGET)
        report = self.reduce(self.controls + [start, write])
        context = report["writer_storage_context"][0]
        self.assertEqual(context["receipt"], "start-identity-mismatch")
        self.assertEqual((context["temp"], context["tmp"], context["udf"]),
                         ("unverified", "unverified", "unverified"))
        report = self.reduce(self.controls + [start, start, write])
        self.assertEqual(report["writer_storage_context"][0]["receipt"], "start-record-ambiguous")
        self.assertEqual(report["verdict"], "REPRODUCED")

    def test_storage_context_reports_duplicate_and_invalid_environment_values(self):
        child = self.processes["renderer"]
        parent = self.processes["app"]
        detail = (f"Parent PID: {parent.pid}, Command line: {child.command}, "
                  f"Current directory: c:\\fixture, Environment: ; TEMP=relative ; "
                  f"TMP={SCRATCH}\\app-temp ; Tmp={USER_TEMP} ; WEBVIEW2_USER_DATA_FOLDER={SCRATCH}")
        context = probe.storage_environment_context(
            detail, child, parent, SCRATCH, SCRATCH + r"\\app-temp", USER_TEMP, None,
        )
        self.assertEqual(context, {
            "receipt": "environment-observed", "temp": "temp-path-invalid",
            "tmp": "tmp-ambiguous", "udf": "declared-profile",
        })
        self.assertNotIn("relative", json.dumps(context))

    def test_variant_cli_rejects_unknown_variant_before_native_preflight(self):
        run = subprocess.run([sys.executable, "-B", "-m", probe.__name__, "capture", ".",
                              "--source", SOURCE, "--expected-exe-sha256", HASH,
                              "--diagnostic-variant", "disable-everything"],
                             capture_output=True, text=True, timeout=10)
        self.assertEqual(run.returncode, 2)
        self.assertIn("invalid choice", run.stderr)

    def test_capture_refuses_absent_one_use_approval(self):
        run = subprocess.run([sys.executable, "-B", "-m", probe.__name__, "capture", ".",
                              "--source", SOURCE, "--expected-exe-sha256", HASH],
                             env={**os.environ, "GITHUB_RUN_ATTEMPT":"1", "PILOTODIN_N12_APPROVED_SOURCE":SOURCE,
                                  "PILOTODIN_N12_WEBVIEW_STORAGE_CONSENT":""},
                             capture_output=True, text=True, timeout=10)
        self.assertEqual(run.returncode, 2)
        self.assertIn("separate one-run N12 WebView storage consent is required", run.stderr)

    def test_runner_temp_accepts_nested_and_canonical_user_temp(self):
        with TemporaryDirectory() as folder:
            root = Path(folder).resolve()
            local = root / "local-app-data"
            runner = root / "runner-temp"
            ambient = local / "Temp" / "interactive-session"
            ambient.mkdir(parents=True)
            runner.mkdir()
            env = {"LOCALAPPDATA": str(local), "RUNNER_TEMP": str(runner), "TEMP": str(ambient)}
            self.assertEqual(probe.runner_control_temp(env), ambient)
            self.assertEqual(probe.runner_control_temp({**env, "TEMP": str(runner)}), runner)
            alias = root / "short-alias"
            original_resolve = Path.resolve
            with patch.object(Path, "resolve", autospec=True, side_effect=lambda path, **kwargs:
                              ambient if path == alias else original_resolve(path, **kwargs)):
                self.assertEqual(probe.runner_control_temp({**env, "TEMP": str(alias)}), ambient)

    def test_runner_temp_rejects_resolved_paths_outside_the_two_roots(self):
        with TemporaryDirectory() as folder:
            root = Path(folder).resolve()
            local = root / "local-app-data"
            runner = root / "runner-temp"
            unrelated = local / "Temp-backup"
            unrelated.mkdir(parents=True)
            runner.mkdir()
            with self.assertRaisesRegex(trace.EvidenceValidationError, "outside the hosted"):
                probe.runner_control_temp({"LOCALAPPDATA": str(local), "RUNNER_TEMP": str(runner),
                                           "TEMP": str(unrelated)})



class StorageVariantComparisonTests(unittest.TestCase):
    """Synthetic receipts only: no native process or live monitoring."""

    def receipt(self, variant, run_id, outside_count=0):
        events = [] if not outside_count else [{
            "destination_family": "user-temp", "operation": "create",
            "component": "browser", "stage": "startup", "file_type": "temporary",
            "count": outside_count,
        }]
        writers = [] if not outside_count else [{
            "destination_family": "user-temp", "operation": "create",
            "component": "browser", "stage": "startup", "count": outside_count,
            "receipt": "environment-observed", "temp": "declared-app-temp",
            "tmp": "startup-tmp", "udf": "declared-profile",
        }]
        return {
            "scope": "one-startup-and-close-storage-diagnostic",
            "source_sha": SOURCE, "executable_sha256": HASH,
            "storage_capture_run_id": run_id, "storage_capture_attempt": 1,
            "storage_diagnostic_variant": variant, "browser_variant_corroboration": "agrees",
            "verdict": "REPRODUCED" if outside_count else "INCONCLUSIVE",
            "issues": [], "file_coverage_issues": [], "unresolved_file_events": [],
            "procmon_shutdown_verified": True, "procmon_loss_reviewed": True,
            "protected_snapshot_comparison": "MATCH", "protected_operations": [],
            "protected_operation_details": [], "known_create_controls": {"scratch": True, "user-temp": True},
            "startup_tmp_probe": True, "startup_tmp_control_verified": True,
            "browser_startup_tmp": "expected-tmp",
            "browser_launch_flags": {"status": "environment-observed",
                                     "remote_debugging": "present",
                                     "netlog": "present" if variant == "debug-netlog" else "absent"},
            "browser_storage_context": {"receipt": "environment-observed",
                                        "temp": "declared-app-temp", "tmp": "startup-tmp",
                                        "udf": "declared-profile"},
            "storage_context_is_acceptance_evidence": False,
            "webview_runtime_versions": ["1.2.3.4"],
            "storage_events": events, "writer_storage_context": writers,
            "ambient_temp_creates": outside_count,
        }

    def compare(self, netlog=2, debug_only=0):
        return comparison.compare_pair(
            self.receipt("debug-netlog", "901", netlog),
            self.receipt("debug-only", "902", debug_only),
        )

    def test_one_pair_reports_candidate_without_claiming_cause_or_acceptance(self):
        result = self.compare(netlog=2, debug_only=0)
        self.assertEqual(result["verdict"], "COMPARABLE_DIAGNOSTIC")
        self.assertEqual(result["signal"], "observed-only-with-netlog")
        self.assertEqual(result["outside_profile_operation_counts"],
                         {"debug-only": 0, "debug-netlog": 2})
        self.assertEqual(result["group_differences"][0], {
            "destination_family": "user-temp", "operation": "create",
            "component": "browser", "stage": "startup", "debug_only": 0, "debug_netlog": 2,
        })
        self.assertFalse(result["causality_proven"])
        self.assertEqual(result["native_N12_acceptance"], "NOT_EVALUATED")

    def test_persistent_ambient_and_zero_ambient_remain_diagnostic_only(self):
        result = self.compare(netlog=3, debug_only=1)
        self.assertEqual(result["signal"], "outside-operations-in-both")
        result = self.compare(netlog=0, debug_only=0)
        self.assertEqual(result["signal"], "no-observed-outside-operations-in-pair")
        self.assertEqual(result["verdict"], "COMPARABLE_DIAGNOSTIC")
        self.assertFalse(result["causality_proven"])

    def test_provenance_runtime_and_capture_identity_reject_confounded_pairs(self):
        variants = (
            ("source_sha", "3" * 40, "source-revision-mismatch"),
            ("executable_sha256", "4" * 64, "executable-digest-mismatch"),
            ("webview_runtime_versions", ["2.3.4.5"], "runtime-version-mismatch"),
            ("storage_capture_run_id", "901", "independent-captures-required"),
            ("storage_capture_attempt", 2, "capture-identity-unverified"),
        )
        for key, value, expected in variants:
            with self.subTest(field=key):
                first = self.receipt("debug-netlog", "901", 2)
                second = self.receipt("debug-only", "902", 0)
                second[key] = value
                result = comparison.compare_pair(first, second)
                self.assertEqual(result["verdict"], "BLOCKED")
                self.assertIn(expected, result["issues"])
                self.assertNotIn("signal", result)

    def test_capture_evidence_and_control_failures_never_compare(self):
        changes = (
            ("procmon_shutdown_verified", False, "collector-coverage-unverified"),
            ("procmon_loss_reviewed", False, "collector-coverage-unverified"),
            ("protected_snapshot_comparison", "DIFFERENT", "protected-data-evidence-unverified"),
            ("protected_operations", [{"role": "webview", "operation": "write", "count": 1}],
             "protected-data-evidence-unverified"),
            ("known_create_controls", {"scratch": True}, "positive-controls-incomplete"),
            ("browser_startup_tmp", "ambient-temp", "browser-tmp-control-unverified"),
            ("browser_variant_corroboration", "unverified", "observed-browser-flags-disagree"),
            ("unresolved_file_events", [{"kind": "private"}], "file-attribution-incomplete"),
            ("issues", ["procmon-capture-configuration-unverified"], "storage-reducer-not-clean"),
            ("verdict", "BLOCKED", "storage-reducer-not-clean"),
        )
        for key, value, expected in changes:
            with self.subTest(field=key):
                first = self.receipt("debug-netlog", "901", 2)
                second = self.receipt("debug-only", "902", 0)
                first[key] = value
                result = comparison.compare_pair(first, second)
                self.assertEqual(result["verdict"], "BLOCKED")
                self.assertIn(expected, result["issues"])

    def test_writer_environment_mismatch_and_event_tampering_block(self):
        baseline = self.receipt("debug-only", "902", 1)
        netlog = self.receipt("debug-netlog", "901", 2)
        baseline["writer_storage_context"][0]["tmp"] = "ambient-temp"
        self.assertIn("writer-storage-boundary-unverified",
                      comparison.compare_pair(netlog, baseline)["issues"])
        baseline = self.receipt("debug-only", "902", 1)
        baseline["storage_events"][0]["count"] = 10
        self.assertIn("writer-event-summaries-disagree",
                      comparison.compare_pair(netlog, baseline)["issues"])
        baseline = self.receipt("debug-only", "902", 1)
        baseline["storage_events"][0]["destination_family"] = "C:\\private\\secret-filename"
        result = comparison.compare_pair(netlog, baseline)
        self.assertIn("event-summary-invalid", result["issues"])
        self.assertNotIn("private", json.dumps(result))
        self.assertNotIn("secret-filename", json.dumps(result))

    def test_no_duplicate_or_unlabeled_variants(self):
        first = self.receipt("debug-only", "901", 0)
        second = self.receipt("debug-only", "902", 3)
        result = comparison.compare_pair(first, second)
        self.assertEqual(result["verdict"], "BLOCKED")
        self.assertIn("distinct-variants-required", result["issues"])

    def test_comparison_cli_is_offline_and_fails_closed_on_bad_files(self):
        with TemporaryDirectory() as folder:
            left, right = Path(folder) / "first.json", Path(folder) / "second.json"
            left.write_text(json.dumps(self.receipt("debug-only", "901", 0)), encoding="utf-8")
            right.write_text(json.dumps(self.receipt("debug-netlog", "902", 2)), encoding="utf-8")
            command = [sys.executable, "-B", "-m", comparison.__name__, str(left), str(right)]
            result = subprocess.run(command, capture_output=True, text=True, timeout=10)
            self.assertEqual(result.returncode, 0)
            report = json.loads(result.stdout)
            self.assertEqual(report["verdict"], "COMPARABLE_DIAGNOSTIC")
            right.write_text('{"some-secret":"do-not-print"', encoding="utf-8")
            result = subprocess.run(command, capture_output=True, text=True, timeout=10)
            self.assertEqual(result.returncode, 2)
            self.assertEqual(json.loads(result.stdout)["verdict"], "BLOCKED")
            self.assertNotIn("do-not-print", result.stdout)


if __name__ == "__main__":
    unittest.main()
