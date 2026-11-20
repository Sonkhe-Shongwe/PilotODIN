import csv
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from qa.p4_native import n12_trace as trace
from qa.p4_research import n12_procmon_environment_control as control
from qa.p4_research import n12_procmon_timing_control as timing


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


class SameSessionInputTests(unittest.TestCase):
    def setUp(self):
        folder = TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.root = Path(folder.name)
        self.run_id = {"source_sha": "1" * 40, "run_id": "21", "run_attempt": "1"}
        parent_image = r"C:\fixture\python.exe"
        native_image = r"\Device\HarddiskVolume3\fixture\python.exe"
        origin = trace.utc_ticks(WINDOW[0])
        second = 10_000_000
        parent = {"pid": 9, "birth": origin + second // 2, "exit": origin + 3 * second,
                  "image_dos": parent_image, "image_native": native_image}
        writer = {**parent, "pid": 10, "birth": origin + second, "exit": origin + 2 * second}
        at = trace.etw_payload_ticks("2026-11-20T00:00:01.1234568Z")

        def lifecycle(kind, handle, sequence, **fields):
            return {"id": kind, "pid": 0, "lifecycle": True, "version": 3,
                    "ticks": handle["birth" if kind == 1 else "exit"], "data": {
                        "ProcessID": str(handle["pid"]), "ProcessSequenceNumber": str(sequence),
                        "CreateTime": timing.journey.timestamp_from_ticks(handle["birth"]).isoformat(),
                        "ImageName": native_image, **fields,
                    }}

        self.events = [
            lifecycle(1, parent, 5, ParentProcessID="8", ParentProcessSequenceNumber="4"),
            lifecycle(1, writer, 6, ParentProcessID="9", ParentProcessSequenceNumber="5"),
            {"id": 12, "pid": 10, "lifecycle": False, "ticks": at,
             "data": {"FileObject": 3, "Irp": 4, "FileName": CHILD["target"]}},
            {"id": 24, "pid": 0, "lifecycle": False, "ticks": at + 1,
             "data": {"Irp": 4, "Status": 0, "ExtraInformation": 2}},
            lifecycle(2, writer, 6, ExitTime=timing.journey.timestamp_from_ticks(writer["exit"]).isoformat()),
            lifecycle(2, parent, 5, ExitTime=timing.journey.timestamp_from_ticks(parent["exit"]).isoformat()),
        ]
        self.capture = {"run": self.run_id.copy(), "parent": parent, "child": {
            **CHILD, "witness": writer, "clock": {"before": at, "after": at + 1},
        }, "etw": {
            "schema_version": 1, "start_utc": WINDOW[0].isoformat(), "end_utc": WINDOW[1].isoformat(),
            "volume_devices": {"C:": r"\Device\HarddiskVolume3"},
            "counters": {"events_lost": 0, "log_buffers_lost": 0, "realtime_buffers_lost": 0, "buffers_written": 1},
        }}
        self.etw_path = self.root / "etw.jsonl"
        self.write_etw()
        csv_path = self.root / "capture-utf8.csv"
        rows = [process_start(f"\tTMP={TMP}\tTEMP={TEMP}"), create()]
        with csv_path.open("w", encoding="utf-8", newline="") as stream:
            writer_csv = csv.DictWriter(stream, fieldnames=rows[0])
            writer_csv.writeheader()
            writer_csv.writerows(rows)
        self.window = {"run": self.run_id.copy(), "csv_sha256": timing.build.digest(csv_path),
                       "start_utc": WINDOW[0].isoformat(), "end_utc": WINDOW[1].isoformat(),
                       "clock_utc": True, "shutdown_verified": False}

    def write_etw(self):
        self.etw_path.write_text("".join(json.dumps(event) + "\n" for event in self.events), encoding="utf-8")
        self.capture["etw"]["events_sha256"] = timing.build.digest(self.etw_path)

    def reduce(self):
        return timing.reduce(self.root, self.run_id, self.capture, self.window)

    def test_joins_real_fixture_export_formats_and_preserves_shutdown_status(self):
        report = self.reduce()
        self.assertEqual(report["status"], "PASS")
        self.assertEqual(report["procmon_minus_etw_completion_ticks"], -1)
        self.assertFalse(report["procmon_shutdown_verified"])
        self.assertFalse(report["procmon_loss_reviewed"])
        self.assertNotIn("private-test", json.dumps(report))

    def test_blocks_changed_capture_provenance_and_digests(self):
        for values, key, value, reason in (
            (self.window["run"], "run_id", "22", "provenance mismatch"),
            (self.capture["run"], "source_sha", "2" * 40, "provenance mismatch"),
            (self.window, "csv_sha256", "0" * 64, "Procmon export digest mismatch"),
            (self.capture["etw"], "events_sha256", "0" * 64, "ETW export digest mismatch"),
        ):
            with self.subTest(reason=reason), patch.dict(values, {key: value}):
                with self.assertRaisesRegex(trace.EvidenceValidationError, reason):
                    self.reduce()

    def test_blocks_etw_loss_and_conflicting_parent_identity(self):
        with patch.dict(self.capture["etw"]["counters"], {"events_lost": 1}):
            with self.assertRaisesRegex(trace.EvidenceValidationError, "etw-event-or-buffer-loss"):
                self.reduce()
        self.events[1]["data"]["ParentProcessSequenceNumber"] = "7"
        self.write_etw()
        with self.assertRaisesRegex(trace.EvidenceValidationError, "ETW parent sequence unverified"):
            self.reduce()

    def test_failed_file_completion_cannot_supply_timing(self):
        self.events[3]["data"]["Status"] = 0xC0000035
        self.write_etw()
        self.assertEqual(self.reduce()["reason"], "etw-create-missing-or-ambiguous")

    @unittest.skipUnless(os.name == "nt", "requires the Windows clock and process handle")
    def test_windows_child_records_precise_clock_and_original_handle(self):
        child = control.capture(self.root, timed=True)
        witness, clock = child["witness"], child["clock"]
        self.assertEqual(witness["pid"], child["pid"])
        self.assertLessEqual(witness["birth"], clock["before"])
        self.assertLess(clock["before"], clock["after"])
        self.assertLessEqual(clock["after"], witness["exit"])


if __name__ == "__main__":
    unittest.main()
