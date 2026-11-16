"""Exercise the lifetime ETW reducer with generated provider-shaped evidence."""
from contextlib import redirect_stdout
from datetime import datetime, timedelta, timezone
import io
import json
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from qa.p4_native import n12_lifetime_control as control
from qa.p4_native import n12_lifetime_etw as etw


IMAGE = r"C:\private\Python\python.exe"
OBSERVER = 501
BASE = datetime(2026, 11, 16, tzinfo=timezone.utc)
TICKS = control.trace.utc_ticks(BASE)
COUNTERS = dict.fromkeys(etw.COUNTERS, 0) | {"buffers_written": 3}


def event_time(ticks):
    time = BASE + timedelta(microseconds=(ticks - TICKS) // 10)
    return time.strftime("%Y-%m-%dT%H:%M:%S.%f") + str(ticks % 10) + "Z"


def generate():
    witnesses, sysmon, events = {}, [], []
    for index, pair in enumerate(control.PAIRS):
        birth = TICKS + (index + 1) * 100_000
        parent_pid = 7000 + 2 * index
        parent = {"pid": parent_pid, "birth": birth, "exit": birth + 60_003}
        child = {"pid": parent_pid + 1, "birth": birth + 15_001, "exit": birth + 40_007}
        witnesses[pair] = {"parent": parent, "child": child}
        for process, kind in ((parent, 1), (child, 1), (child, 2), (parent, 2)):
            pid = process["pid"]
            parent_id = OBSERVER if pid == parent_pid else parent_pid
            stamp = process["birth"] if kind == 1 else process["exit"]
            data = {"ProcessID": str(pid), "ProcessSequenceNumber": str(pid + 2000),
                    "CreateTime": event_time(process["birth"]), "ImageName": r"C:\private\image.exe"}
            if kind == 1:
                data.update(ParentProcessID=str(parent_id), ParentProcessSequenceNumber=str(parent_id + 2000))
            else:
                data["ExitTime"] = event_time(process["exit"])
            events.append({"id": kind, "pid": 9999, "ticks": stamp + 500,
                           "version": 3 if kind == 1 else 2, "data": data})
            sysmon.append({"kind": 1 if kind == 1 else 5, "pid": pid, "guid": str(pid),
                           "parent": str(parent_id), "image": IMAGE, "ticks": stamp, "record": len(sysmon) + 1})
    return witnesses, sysmon, events


class LifetimeEtwTests(unittest.TestCase):
    def setUp(self):
        temp = TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.path = Path(temp.name) / "etw.jsonl"
        self.witnesses, self.sysmon, self.events = generate()

    def packet(self, counters=COUNTERS):
        self.path.write_text("".join(json.dumps(r) + "\n" for r in self.events), encoding="utf-8")
        pids = {w["pid"] for group in self.witnesses.values() for w in group.values()}
        records = etw.read_process_events(self.path, pids, TICKS, TICKS + 400_000)
        return {"schema_version": 3, "sysmon": control.redact(self.witnesses, self.sysmon, [], IMAGE),
                "etw": etw.redact(self.witnesses, records, counters, OBSERVER)}

    def test_cli_replays_exact_payload_precision_and_uses_payload_pid(self):
        self.events[2]["ticks"] += 20_000
        packet = self.packet()
        row = packet["etw"]["cases"][1]
        self.assertEqual(row["exit_delta_ticks"], 0)
        self.assertEqual(row["stop_event_delta_ticks"], 20_500)
        self.assertEqual(etw.payload_ticks(event_time(TICKS + 7)), TICKS + 7)
        self.assertEqual(control.replay(packet)["verdict"], "PASS")
        self.path.write_text(json.dumps(packet), encoding="utf-8")
        run = subprocess.run([sys.executable, "-B", "-m", control.__name__, "--replay", str(self.path)],
                             capture_output=True, text=True)
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertEqual(json.loads(run.stdout), control.replay(packet))

    def test_isolates_a_sysmon_timing_difference(self):
        self.sysmon[2]["ticks"] -= 18_000
        packet = self.packet()
        result = control.replay(packet)
        self.assertEqual(result["verdict"], "BLOCKED")
        self.assertEqual(result["comparisons"]["fast-child"], "etw-and-handles-agree-sysmon-time-differs")
        self.assertEqual(result["etw_findings"]["fast-child"], [])
        for private in ("private", "7001", "9001", "9999", event_time(TICKS + 140_007)):
            self.assertNotIn(private, json.dumps(packet))

    def test_etw_evidence_gaps_block_comparison(self):
        cases = (
            ("missing", lambda rows: rows.pop(2), "stop-missing-or-ambiguous"),
            ("duplicate", lambda rows: rows.insert(2, rows[2].copy()), "stop-missing-or-ambiguous"),
            ("wrong_pid", lambda rows: rows[2]["data"].update(ProcessID="8000"), "identity-matches-unverified"),
            ("wrong_sequence", lambda rows: rows[2]["data"].update(ProcessSequenceNumber="2"),
             "identity-matches-unverified"),
            ("wrong_parent", lambda rows: rows[1]["data"].update(ParentProcessID="8000"),
             "parent-matches-unverified"),
            ("wrong_parent_sequence", lambda rows: rows[1]["data"].update(ParentProcessSequenceNumber="2"),
             "parent-matches-unverified"),
            ("unordered", lambda rows: rows.insert(1, rows.pop(2)), "ordered-unverified"),
            ("outside_window", lambda rows: rows[2].update(ticks=TICKS + 401_000), "stop-in-window-unverified"),
            ("wrong_exit", lambda rows: rows[2]["data"].update(ExitTime=event_time(TICKS + 120_003)),
             "exit-disagrees-with-windows"),
        )
        for name, change, finding in cases:
            with self.subTest(name=name):
                self.witnesses, self.sysmon, self.events = generate()
                change(self.events)
                result = control.replay(self.packet())
                self.assertEqual(result["verdict"], "BLOCKED")
                self.assertIn(finding, result["etw_findings"]["fast-child"])
                self.assertEqual(result["comparisons"]["fast-child"], "etw-unverified")

    def test_etw_loss_takes_precedence_over_timing_attribution(self):
        self.sysmon[2]["ticks"] -= 18_000
        result = control.replay(self.packet(COUNTERS | {"events_lost": 1}))
        self.assertEqual(result["comparisons"]["fast-child"], "etw-unverified")
        self.assertEqual(result["etw_issues"], ["etw-event-or-buffer-loss"])

    def test_checks_direct_cross_collector_delta(self):
        self.sysmon[2]["ticks"] -= 7500
        self.events[2]["data"]["ExitTime"] = event_time(TICKS + 147_507)
        result = control.replay(self.packet())
        self.assertEqual(result["verdict"], "BLOCKED")
        self.assertEqual(result["etw_findings"]["fast-child"], [])
        self.assertEqual(result["comparisons"]["fast-child"], "collectors-differ-within-handle-bound")

    def test_etw_between_sysmon_and_handle_is_inconclusive(self):
        self.sysmon[2]["ticks"] -= 11_000
        self.events[2]["data"]["ExitTime"] = event_time(TICKS + 131_007)
        result = control.replay(self.packet())
        self.assertEqual(result["verdict"], "BLOCKED")
        self.assertEqual(result["comparisons"]["fast-child"], "sysmon-and-etw-timing-inconclusive")

    def test_rejects_a_missing_sequence_on_the_new_provider_schema(self):
        self.events[2]["data"].pop("ProcessSequenceNumber")
        with self.assertRaisesRegex(control.trace.EvidenceValidationError, "lifetime-etw-invalid-record"):
            self.packet()

    def test_legacy_provider_schema_matches_by_pid_and_creation_time(self):
        for row in self.events:
            row["version"] = 2 if row["id"] == 1 else 1
            row["data"].pop("ProcessSequenceNumber", None)
            row["data"].pop("ParentProcessSequenceNumber", None)
        self.assertEqual(control.replay(self.packet())["verdict"], "PASS")
        self.events[2]["data"]["CreateTime"] = event_time(TICKS + 115_000)
        verdict = control.replay(self.packet())
        self.assertIn("identity-matches-unverified", verdict["etw_findings"]["fast-child"])

    def test_sysmon_join_failure_cannot_be_labelled_as_a_timing_difference(self):
        self.sysmon[2]["ticks"] -= 18_000
        self.sysmon[2]["guid"] = "private-other-process"
        result = control.replay(self.packet())
        self.assertEqual(result["comparisons"]["fast-child"], "sysmon-identity-or-coverage-unverified")

    def test_etw_capture_cli_rejects_unapproved_host(self):
        run = subprocess.run([sys.executable, "-B", "-m", control.__name__, "--capture-etw", str(self.path.parent)],
                             capture_output=True, text=True,
                             env={**os.environ, "PILOTODIN_N12_LIFETIME_CONTROL_CONSENT": control.CONSENT})
        self.assertEqual(run.returncode, 2, run.stdout)
        self.assertIn("lifetime-control-requires-approved-hosted-windows", run.stderr)
        self.assertEqual(list(self.path.parent.iterdir()), [])

    def test_session_preserves_fixture_failure_even_when_cleanup_fails(self):
        class FixtureFailure(Exception):
            pass

        root = self.path.parent
        with (patch.dict(os.environ, {"SystemRoot": r"C:\Windows"}),
              patch.object(etw.etw, "utc_ticks", return_value=TICKS),
              patch.object(etw.etw, "stop_trace", side_effect=OSError("private")),
              patch.object(etw.journey, "quiet", side_effect=[b"", OSError("private")]) as run,
              redirect_stdout(io.StringIO()) as log):
            with self.assertRaises(FixtureFailure):
                with etw.process_session(root, "a" * 40):
                    raise FixtureFailure()
        self.assertIn("Microsoft-Windows-Kernel-Process", run.call_args_list[0].args[0])
        self.assertNotIn("Microsoft-Windows-Kernel-File", run.call_args_list[0].args[0])
        self.assertEqual(run.call_args_list[1].args[0][1], "stop")
        self.assertIn("lifetime-etw-stop-fallback", log.getvalue())
        self.assertNotIn("private", log.getvalue())

    def test_capture_emits_and_writes_the_replay_packet(self):
        root = self.path.parent
        self.packet()
        self.path.rename(root / "lifetime-etw.jsonl")
        pids = {w["pid"] for group in self.witnesses.values() for w in group.values()}
        with (patch.object(control.journey, "sysmon_tail", side_effect=[1, 10]),
              patch.object(control.sys, "executable", IMAGE),
              patch.object(control.time, "sleep"),
              patch.object(control.journey, "export_sysmon"),
              patch.object(control, "gather_witnesses", return_value=(self.witnesses, pids)),
              patch.object(control, "read_records", return_value=(self.sysmon, [])),
              patch.object(control.etw, "process_session") as capture,
              patch.object(control.journey, "powershell"),
              patch.object(control.os, "getpid", return_value=OBSERVER),
              redirect_stdout(io.StringIO()) as log):
            capture.return_value.__enter__.return_value = {
                "start": TICKS, "end": TICKS + 400_000, "counters": COUNTERS,
            }
            self.assertEqual(control.capture(root, "a" * 40, with_etw=True), 0)
        lines = log.getvalue().splitlines()
        replay_line = next(line for line in lines if line.startswith("N12 lifetime ETW replay "))
        packet = json.loads(replay_line.removeprefix("N12 lifetime ETW replay "))
        self.assertEqual(packet, json.loads((root / "lifetime-replay.json").read_text(encoding="utf-8")))
        self.assertEqual(control.replay(packet)["verdict"], "PASS")

    def test_etw_failure_preserves_sysmon_replay_in_job_log(self):
        root = self.path.parent
        with (patch.object(control.journey, "sysmon_tail", side_effect=[1, 10]),
              patch.object(control.sys, "executable", IMAGE),
              patch.object(control.time, "sleep"),
              patch.object(control.journey, "export_sysmon"),
              patch.object(control, "gather_witnesses", return_value=(self.witnesses, set())),
              patch.object(control, "read_records", return_value=(self.sysmon, [])),
              patch.object(control.etw, "process_session"),
              patch.object(control.journey, "powershell", side_effect=OSError("private")),
              redirect_stdout(io.StringIO()) as log):
            with self.assertRaises(OSError):
                control.capture(root, "a" * 40, with_etw=True)
        self.assertIn("N12 lifetime replay ", log.getvalue())
        self.assertIn('"stage": "lifetime-etw-export", "status": "interrupted"', log.getvalue())
        self.assertNotIn("N12 lifetime ETW replay ", log.getvalue())


if __name__ == "__main__":
    unittest.main()
