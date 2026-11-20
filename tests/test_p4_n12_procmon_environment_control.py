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

    def test_environment_formats_prove_order_at_windows_tick_precision(self):
        for environment in (f" ; TMP={TMP} ; TEMP={TEMP} ; OTHER=private-value",
                            f"\r\nTMP={TMP}\r\nTEMP={TEMP}\r\nOTHER=private-value",
                            f"SystemRoot=C:\\Windows\tTEMP={TEMP}\r\n\tTMP={TMP}",
                            f"\tTEMP={TEMP}\r\nSystemRoot=C:\\Windows\tTMP={TMP}"):
            with self.subTest(environment_format=environment[:3]):
                report = control.inspect_rows([create(), process_start(environment)], CHILD, *WINDOW)
                shapes = report.pop("assignment_shape")
                self.assertEqual(report, {"process_start": "environment-observed", "tmp": "expected",
                                          "temp": "expected", "known_create": "observed",
                                          "environment_contents": "nonempty",
                                          "key_rendering": {"tmp": "recognized-assignment",
                                                            "temp": "recognized-assignment"},
                                          "start_before_create": True})
                self.assertEqual([item["expected_value"] for item in shapes.values()],
                                 ["bounded-literal-match", "bounded-literal-match"])
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
            (f" ; TMP={TMP}\tTEMP={TEMP}\r\n\tTemp={TMP}", "temp-ambiguous"),
            (f" ; TMP={TMP} ; TEMP={TMP}", "mismatch"),
            (f" ; TMP={TMP} ; TEMP=C:relative", "temp-path-invalid"),
            (f" ; TMP={TMP}\tTEMP={TEMP}\0other", "temp-path-invalid"),
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

    def test_reports_delimiters_padded_operator_and_quoted_literal(self):
        environment = f'\r\nTMP : "{TMP}"\tTEMP : {TEMP};'
        report = control.inspect_rows([process_start(environment), create()], CHILD, *WINDOW)
        self.assertTrue(report["start_before_create"])
        self.assertEqual(report["assignment_shape"]["tmp"], {
            "token": "unique", "before_key": "crlf", "operator": "colon",
            "padding_before_operator": True, "padding_after_operator": True,
            "value_wrapper": "double-quote", "expected_value": "bounded-literal-match",
            "after_value": "tab",
        })
        self.assertEqual(report["assignment_shape"]["temp"]["before_key"], "tab")
        self.assertEqual(report["assignment_shape"]["temp"]["after_value"], "semicolon")
        self.assertEqual(report["assignment_shape"]["temp"]["expected_value"], "bounded-literal-match")
        self.assertEqual((report["tmp"], report["temp"]), ("tmp-not-observed", "temp-not-observed"))
        self.assertNotIn("private", json.dumps(report))

    def test_reports_padding_around_a_separator(self):
        shape = control.assignment_shape(f" ; TMP={TMP} ; TEMP={TEMP}", "TMP", TMP)
        self.assertEqual(shape["before_key"], "semicolon-space-before-space-after")
        self.assertEqual(shape["after_value"], "semicolon-space-before-space-after")

    def test_literal_matches_need_unique_tokens_and_known_boundaries(self):
        for environment, token, value in (
            (f"TMP={TMP}", "unique", "bounded-literal-match"),
            (f"TMP={TMP}-extra", "unique", "unbounded-literal"),
            (f"OTHER=prefix TMP={TMP}", "unique", "unbounded-literal"),
            (f"TMP={TEMP}", "unique", "not-found"),
            (f"TMP={TMP}; TMP={TEMP}", "ambiguous", None),
            (" ; OTHER=containsTMP=private-sample", "missing", None),
        ):
            with self.subTest(token=token, value=value):
                report = control.assignment_shape(environment, "TMP", TMP)
                self.assertEqual((report["token"], report.get("expected_value")), (token, value))
                self.assertNotIn("private", json.dumps(report))

    def test_wrong_writer_failed_open_tie_and_late_start_do_not_prove_order(self):
        env = f" ; TMP={TMP} ; TEMP={TEMP}"
        for target in (create(pid=99), create(result="ACCESS DENIED"), create(detail="OpenResult: Opened"),
                       create(stamp="00:00:01.1234567"), create(stamp="00:00:01.1234566")):
            with self.subTest(target=target):
                report = control.inspect_rows([process_start(env), target], CHILD, *WINDOW)
                self.assertFalse(report["start_before_create"])


class CreateTimingReplayTests(unittest.TestCase):
    def setUp(self):
        self.start = process_start(f"\tTMP={TMP}\tTEMP={TEMP}")
        self.begin = trace.etw_payload_ticks("2026-11-20T00:00:01.1234568Z")
        self.writer = "private-writer-guid"
        self.event = (self.writer, trace.windows_path(CHILD["target"]), self.begin, self.begin + 1)

    def replay(self, rows, **overrides):
        inputs = {"before": self.begin, "after": self.begin + 1,
                  "writer_guid": self.writer, "etw_creates": [self.event]}
        inputs.update(overrides)
        return control.replay_create_timing(rows, CHILD, *WINDOW, **inputs)

    def test_accepts_one_tick_order_and_inclusive_open_boundaries(self):
        report = self.replay([create(), self.start])
        self.assertEqual(report, {
            "status": "PASS",
            "procmon_minus_etw_request_ticks": 0,
            "procmon_minus_etw_completion_ticks": -1,
            "from_open_begin_ticks": {"procmon_create": 0, "etw_request": 0, "etw_completion": 1},
            "to_open_return_ticks": {"procmon_create": 1, "etw_request": 1, "etw_completion": 0},
        })
        self.assertNotIn("private-", json.dumps(report))

    def test_blocks_events_one_tick_outside_the_window(self):
        for rows, event, label, bound in (
            ([self.start, create(stamp="00:00:01.1234570")], self.event,
             "procmon_create", "to_open_return_ticks"),
            ([self.start, create()], (*self.event[:2], self.begin - 1, self.begin + 1),
             "etw_request", "from_open_begin_ticks"),
            ([self.start, create()], (*self.event[:2], self.begin, self.begin + 2),
             "etw_completion", "to_open_return_ticks"),
        ):
            with self.subTest(label=label):
                report = self.replay(rows, etw_creates=[event])
                self.assertEqual((report["status"], report["reason"]),
                                 ("BLOCKED", "create-timestamp-outside-window"))
                self.assertEqual(report[bound][label], -1)

    def test_blocks_true_ties_in_required_orderings(self):
        launch_at_create = process_start(f"\tTMP={TMP}\tTEMP={TEMP}", stamp="00:00:01.1234568")
        for start, event in ((launch_at_create, self.event),
                             (self.start, (*self.event[:3], self.begin))):
            with self.subTest(start=start["Time of Day"], completion=event[3]):
                report = self.replay([start, create()], etw_creates=[event])
                self.assertEqual((report["status"], report["reason"]), ("BLOCKED", "create-order-unverified"))

    def test_blocks_wrong_writer_wrong_target_and_duplicate_creates(self):
        writer, path, requested, completed = self.event
        for events in ([("wrong-writer", path, requested, completed)],
                       [(writer, path + ".different", requested, completed)],
                       [self.event, self.event]):
            with self.subTest(events=events):
                self.assertEqual(self.replay([self.start, create()], etw_creates=events),
                                 {"status": "BLOCKED", "reason": "etw-create-missing-or-ambiguous"})
        self.assertEqual(self.replay([self.start, create(pid=99)]),
                         {"status": "BLOCKED", "reason": "procmon-create-missing-or-ambiguous"})

    def test_blocks_invalid_window_and_unverified_source_fields(self):
        for options, reason in (({"after": self.begin}, "invalid-create-window"),
                                ({"writer_guid": None}, "etw-writer-unverified"),
                                ({"etw_creates": [(*self.event[:3], True)]}, "invalid-etw-timestamp")):
            with self.subTest(reason=reason):
                self.assertEqual(self.replay([self.start, create()], **options),
                                 {"status": "BLOCKED", "reason": reason})
        wrong_environment = process_start(f"\tTMP={TEMP}\tTEMP={TEMP}")
        self.assertEqual(self.replay([wrong_environment, create()]),
                         {"status": "BLOCKED", "reason": "procmon-start-unverified"})


if __name__ == "__main__":
    unittest.main()
