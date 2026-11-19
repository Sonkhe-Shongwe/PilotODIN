import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from qa.p4_native import n12_trace as trace
from qa.p4_research import n12_procmon_environment_control as control


TMP = r"C:\private-test\tmp"
TEMP = r"C:\private-test\temp"
WINDOW = tuple(map(trace.utc_time, ("2026-11-20T00:00:00Z", "2026-11-20T00:00:15Z")))
CHILD = {"pid": 10, "parent_pid": 9, "image": "python.exe", "command": "python.exe child.py",
         "target": TMP + r"\known-create.tmp", "paths": {"TMP": TMP, "TEMP": TEMP}}


def row(operation, stamp, detail, *, pid=10, path="", result="SUCCESS"):
    return {"Operation": operation, "Time of Day": stamp, "Detail": detail, "PID": str(pid),
            "Process Name": "python.exe", "Path": path, "Result": result}


def process_start(environment, stamp="00:00:01.1234567", parent=9, command=CHILD["command"]):
    return row("Process Start", stamp,
               f"Parent PID: {parent}, Command line: {command}, Current directory: C:\\fixture, "
               f"Environment:{environment}")


def create(stamp="00:00:01.1234568", detail="OpenResult: Created", **settings):
    return row("CreateFile", stamp, detail, path=CHILD["target"], **settings)


class ProcmonEnvironmentControlTests(unittest.TestCase):
    def test_child_checks_both_values_and_writes_expected_bytes(self):
        with TemporaryDirectory() as folder, patch.dict(os.environ, {"FIXTURE_PARENT_ONLY": "synthetic"}), patch.object(
            control.subprocess, "Popen", wraps=control.subprocess.Popen,
        ) as launch:
            child = control.capture(Path(folder))
            self.assertNotEqual(child["paths"]["TMP"], child["paths"]["TEMP"])
            self.assertEqual(Path(child["target"]).read_bytes(), control.PAYLOAD)
            expected = dict(child["paths"])
            if os.name == "nt":
                expected["SystemRoot"] = os.environ["SystemRoot"]
            self.assertEqual(launch.call_args.kwargs["env"], expected)

    def test_both_environment_formats_prove_order_at_windows_tick_precision(self):
        for environment in (f" ; TMP={TMP} ; TEMP={TEMP} ; OTHER=private-value",
                            f"\r\nTMP={TMP}\r\nTEMP={TEMP}\r\nOTHER=private-value"):
            with self.subTest(environment_format=environment[:3]):
                report = control.inspect_rows([create(), process_start(environment)], CHILD, *WINDOW)
                self.assertEqual(report, {"process_start": "environment-observed", "tmp": "expected",
                                          "temp": "expected", "known_create": "observed",
                                          "environment_contents": "nonempty",
                                          "key_rendering": {"tmp": "recognized-assignment",
                                                            "temp": "recognized-assignment"},
                                          "start_before_create": True})
                self.assertNotIn("private", json.dumps(report))

    def test_rejects_identity_errors_and_ambiguous_start_records(self):
        env = f" ; TMP={TMP} ; TEMP={TEMP}"
        for rows, reason in (
            ([], "start-record-unobserved"),
            ([process_start(env, parent=50)], "start-identity-mismatch"),
            ([process_start(env, command="another-child.exe")], "start-identity-mismatch"),
            ([process_start(env), process_start(env)], "start-record-ambiguous"),
            ([row("Process Start", "00:00:01", "")], "start-detail-unrecognized"),
            ([row("Process Start", "00:00:01", "Parent PID: 9, Command line: python.exe child.py, "
                                               "Current directory: C:\\fixture")], "environment-field-unobserved"),
        ):
            with self.subTest(reason=reason):
                report = control.inspect_rows(rows + [create()], CHILD, *WINDOW)
                self.assertEqual(report["process_start"], reason)
                self.assertEqual((report["tmp"], report["temp"]), ("unverified", "unverified"))

    def test_reports_missing_duplicate_wrong_and_invalid_values(self):
        for environment, reason in (
            (f" ; TMP={TMP}", "temp-not-observed"),
            (f" ; TMP={TMP} ; TEMP={TEMP} ; Temp={TEMP}", "temp-ambiguous"),
            (f" ; TMP={TMP} ; TEMP={TMP}", "mismatch"),
            (f" ; TMP={TMP} ; TEMP=C:relative", "temp-path-invalid"),
        ):
            with self.subTest(reason=reason):
                report = control.inspect_rows([process_start(environment), create()], CHILD, *WINDOW)
                self.assertEqual((report["tmp"], report["temp"]), ("expected", reason))

    def test_reports_empty_field_and_assignment_shape_without_values(self):
        for environment, contents, rendering in (
            (" ; \r\n", "empty", "no-assignment-token"),
            (" ; OTHER=containsTMP=private-sample", "nonempty", "no-assignment-token"),
            (f" ;OTHER=fixture;TMP={TMP};TEMP={TEMP}", "nonempty", "assignment-like-token"),
        ):
            with self.subTest(contents=contents, rendering=rendering):
                report = control.inspect_rows([process_start(environment), create()], CHILD, *WINDOW)
                self.assertEqual(report["environment_contents"], contents)
                self.assertEqual(report["key_rendering"], dict.fromkeys(("tmp", "temp"), rendering))
                self.assertEqual((report["tmp"], report["temp"]), ("tmp-not-observed", "temp-not-observed"))
                self.assertNotIn("private", json.dumps(report))

    def test_wrong_writer_failed_open_tie_and_late_start_do_not_prove_order(self):
        env = f" ; TMP={TMP} ; TEMP={TEMP}"
        for target in (create(pid=99), create(result="ACCESS DENIED"), create(detail="OpenResult: Opened"),
                       create(stamp="00:00:01.1234567"), create(stamp="00:00:01.1234566")):
            with self.subTest(target=target):
                report = control.inspect_rows([process_start(env), target], CHILD, *WINDOW)
                self.assertFalse(report["start_before_create"])


if __name__ == "__main__":
    unittest.main()
