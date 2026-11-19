import csv
from datetime import datetime, timedelta, timezone
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
            "protected_roots": {"original": PROTECTED}, "observed_roots": {"quality-source": CSV},
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

    def reduce(self, rows):
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
            return probe.reduce(None, None, self.manifest, None, path)

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


if __name__ == "__main__":
    unittest.main()
