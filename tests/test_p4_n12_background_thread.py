"""Exercise the N12 background writer control with generated evidence."""
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch

from qa.p4_native import n12_background_thread as control, n12_trace as trace
from qa.p4_research import n12_app_journey as journey


class TestBackgroundThread(TestCase):
    def setUp(self):
        folder = TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.export = Path(folder.name) / "events.jsonl"
        start, end = "2026-11-19T00:00:00Z", "2026-11-19T00:00:02Z"
        base = trace.utc_ticks(trace.utc_time(start))
        self.manifest = {
            "schema_version": 1, "disposable": True, "start_utc": start, "end_utc": end,
            "etw": {"schema_version": 1, "start_utc": start, "end_utc": end,
                    "volume_devices": {"C:": r"\Device\HarddiskVolume3"},
                    "counters": dict(events_lost=0, log_buffers_lost=0,
                                     realtime_buffers_lost=0, buffers_written=1)},
        }
        snapshots = [{"pid": 51, "birth_ticks": base - 100}]
        threads = [{"pid": 51, "tid": 55, "birth_ticks": base - 50}]
        self.control = {
            "pid": 51, "tid": 55, "start": base + 50, "end": base + 100,
            "bookends": {"before": snapshots, "after": copy.deepcopy(snapshots),
                         "threads_before": threads, "threads_after": copy.deepcopy(threads)},
        }
        self.events = [
            dict(id=16, pid=51, ticks=base + 60, lifecycle=False,
                 data=dict(IOSize=len(control.PAYLOAD), ByteOffset=0, Irp=77,
                           IssuingThreadId=55, FileObject=11, FileKey=12)),
            dict(id=24, pid=0, ticks=base + 70, lifecycle=False, data=dict(Irp=77, Status=0)),
        ]

    def export_events(self):
        self.export.write_text("".join(json.dumps(row) + "\n" for row in self.events), encoding="utf-8")
        self.manifest["etw"]["events_sha256"] = hashlib.sha256(self.export.read_bytes()).hexdigest()

    def reduce(self):
        self.export_events()
        return control.reduce_control(self.manifest, self.control, self.export)

    def test_strict_rundown_checks_completion_before_resolving_preopened_writes(self):
        outside = trace.windows_path(r"C:\qa\outside\generated.bin")
        protected_root = trace.windows_path(r"C:\qa\protected")
        protected = protected_root + r"\generated.bin"
        request, completion = self.events
        key = request["data"]["FileKey"]
        obj = request["data"]["FileObject"]
        cases = [
            ("outside", [outside], dict(FileKey=key, FileObject=obj), {}, {}, {key}),
            ("protected", [protected], {}, {"protected:other:write": 1}, {}, {key}),
            ("ambiguous", [outside, protected], {}, {}, {"other:write:path-missing": 1}, set()),
            ("wrong-key", [outside], dict(FileKey=99), {},
             {"other:write:completion-file-identity-conflict": 1}, set()),
            ("wrong-object", [outside], dict(FileObject=99), {},
             {"other:write:completion-file-identity-conflict": 1}, set()),
            ("protected-wrong-key", [protected], dict(FileKey=99), {},
             {"other:write:completion-file-identity-conflict": 1}, set()),
        ]
        start, end = (trace.utc_time(self.manifest[field]) for field in ("start_utc", "end_utc"))
        for label, names, fields, expected_violations, expected_gaps, expected_keys in cases:
            with self.subTest(case=label):
                name_events = [
                    dict(id=10, pid=0, lifecycle=False, ticks=request["ticks"] - 10 + n,
                         data=dict(FileKey=key, FileName=name))
                    for n, name in enumerate(names)
                ]
                self.events = [*name_events, request, dict(completion, data={**completion["data"], **fields})]
                self.export_events()
                issues, recovered_keys = set(), set()
                _, violations, _, unresolved = trace.inspect_etw_files(
                    self.manifest, self.export, start, end, {}, {}, [protected_root], {}, issues,
                    background_bookends=self.control["bookends"],
                    rundown=[{"key": key, "path": names[0]}], rundown_recovered_keys=recovered_keys,
                )
                self.assertEqual(violations, expected_violations)
                self.assertEqual(unresolved, expected_gaps)
                self.assertEqual(recovered_keys, expected_keys)
                self.assertEqual(issues, {"etw-mutation-coverage-unresolved"} if expected_gaps else set())

    def test_matches_known_completed_write(self):
        self.assertEqual(self.reduce(), {
            "control_status": "PASS", "known_completed_writes": 1,
            "issuing_thread": "bookend-header-agrees", "validated_etw_events": 2,
            "scope": "background writer thread identity",
        })

    def test_app_comparison_verifies_same_capture_paths_without_changing_baseline(self):
        outside = trace.windows_path(r"C:\qa\outside\generated.bin")
        protected_root = trace.windows_path(r"C:\qa\protected")
        protected = protected_root + r"\generated.bin"
        self.manifest.update(protected_roots={"protected": protected_root},
                             observed_roots={"fixture": r"C:\qa\fixture.csv"},
                             immutable_observed=["fixture"], permitted_writes={})
        start, end = (trace.utc_time(self.manifest[field]) for field in ("start_utc", "end_utc"))
        first, last = map(trace.utc_time, ("2026-11-19T00:00:03Z", "2026-11-19T00:00:04Z"))
        self.manifest["etw"]["end_utc"] = last.isoformat()
        observed = SimpleNamespace(start=start, end=end, processes={}, roles={})
        request, completion = self.events
        key = request["data"]["FileKey"]
        obj = request["data"]["FileObject"]
        names_file = self.export.with_name("rundown.jsonl")
        comparison_manifest = self.export.with_name("background-rundown-manifest.json")
        for label, name, rundown_name, expected in (
            ("outside", outside, outside, {"outside-tracked": 1}),
            ("protected", protected, protected, {"protected": 1}),
            ("name conflict", protected, outside, {}),
            ("completion conflict", outside, outside, {}),
            ("thread unavailable", outside, outside, {}),
            ("closed before rundown", outside, outside, {}),
        ):
            with self.subTest(case=label):
                issuer = 99 if label == "thread unavailable" else self.control["tid"]
                fields = {"FileObject": 99} if label == "completion conflict" else {}
                self.events = [
                    dict(id=10, pid=0, lifecycle=False, ticks=request["ticks"] - 10,
                         data=dict(FileKey=key, FileName=name)),
                    dict(request, data={**request["data"], "IssuingThreadId": issuer}),
                    dict(completion, data={**completion["data"], **fields}),
                ]
                if label == "closed before rundown":
                    self.events.append(dict(id=14, pid=request["pid"], lifecycle=False,
                                            ticks=trace.utc_ticks(end) + 10,
                                            data=dict(FileKey=key, FileObject=obj)))
                self.export_events()
                names_file.write_text(json.dumps({"key": key, "path": rundown_name, "decoder": "tdh"}) + "\n",
                                      encoding="utf-8")
                _, violations, _, gaps = trace.inspect_etw_files(
                    self.manifest, self.export, start, end, {}, {}, [protected_root], {}, set(),
                    background_bookends=self.control["bookends"],
                )
                baseline = {"file_violations": violations, "etw_unresolved_mutations": gaps}
                with patch.object(journey, "powershell") as export:
                    report = journey.compare_background_paths(self.export.parent, self.manifest, observed,
                                                              self.export, self.control["bookends"],
                                                              baseline, (first, last))
                    export.assert_called_once()
                comparison_manifest.unlink()
                self.assertEqual(baseline, {"file_violations": {}, "etw_unresolved_mutations": {
                    "other:write:path-missing": 1}})
                self.assertEqual(report["verified_paths"], expected)
                self.assertEqual(report["remaining_write_path_gaps"], 1 - sum(expected.values()))
                self.assertNotIn("generated.bin", json.dumps(report))

        with patch.object(journey, "powershell"):
            with self.assertRaisesRegex(trace.EvidenceValidationError, "follow the audit"):
                journey.compare_background_paths(self.export.parent, self.manifest, observed, self.export,
                                                 self.control["bookends"], baseline, (end, last))
            comparison_manifest.unlink()
            self.manifest["etw"]["counters"]["events_lost"] = 1
            with self.assertRaisesRegex(trace.EvidenceValidationError, "loss-free ETW"):
                journey.compare_background_paths(self.export.parent, self.manifest, observed, self.export,
                                                 self.control["bookends"], baseline, (first, last))

    def test_generated_writer_stays_alive_across_the_write(self):
        root = self.export.parent
        script = (
            "from pathlib import Path\nimport sys\n"
            "from qa.p4_native import n12_background_thread as control\n"
            "control.probe.verify_handle_path = lambda stream, path: None\n"
            "control.write_once(Path(sys.argv[1]))"
        )
        with subprocess.Popen([sys.executable, "-B", "-c", script, str(root)],
                              stdin=subprocess.PIPE) as writer:
            try:
                control.wait_for_marker(writer, root / "ready")
                self.assertGreater(int((root / "ready").read_text(encoding="ascii")), 0)
                self.assertEqual((root / "background.bin").stat().st_size, 0)
                writer.stdin.write(b"w")
                writer.stdin.flush()
                control.wait_for_marker(writer, root / "done")
                self.assertIsNone(writer.poll())
                writer.stdin.close()
                self.assertEqual(writer.wait(timeout=10), 0)
                self.assertEqual((root / "background.bin").read_bytes(), control.PAYLOAD)
            finally:
                if writer.poll() is None:
                    writer.kill()

    def test_reused_thread_id_blocks(self):
        self.control["bookends"]["threads_after"][0]["birth_ticks"] += 1
        with self.assertRaisesRegex(trace.EvidenceValidationError, "paired snapshots"):
            self.reduce()

    def test_thread_lifecycle_event_blocks_even_with_matching_snapshots(self):
        self.events.append(dict(id=4, pid=0, ticks=self.events[-1]["ticks"] + 1,
                                lifecycle=True, data=dict(ThreadID=55)))
        with self.assertRaisesRegex(trace.EvidenceValidationError, "paired snapshots"):
            self.reduce()

    def test_wrong_issuer_blocks(self):
        self.events[0]["data"]["IssuingThreadId"] = 56
        with self.assertRaisesRegex(trace.EvidenceValidationError, "expected issuing thread"):
            self.reduce()

    def test_ambiguous_write_blocks(self):
        self.events.append(dict(self.events[0], ticks=self.events[0]["ticks"] + 1))
        with self.assertRaisesRegex(trace.EvidenceValidationError, "one matching write"):
            self.reduce()

    def test_failed_completion_blocks(self):
        self.events[1]["data"]["Status"] = "0xc0000022"
        with self.assertRaisesRegex(trace.EvidenceValidationError, "successful completion"):
            self.reduce()

    def test_conflicting_completion_blocks(self):
        self.events[1]["data"]["FileObject"] = 12
        with self.assertRaisesRegex(trace.EvidenceValidationError, "completion file identity"):
            self.reduce()

    def test_trace_loss_blocks(self):
        self.manifest["etw"]["counters"]["events_lost"] = 1
        with self.assertRaisesRegex(trace.EvidenceValidationError, "event or buffer loss"):
            self.reduce()

    def test_tampered_export_blocks(self):
        self.reduce()
        with self.export.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(self.events[1]) + "\n")
        with self.assertRaisesRegex(trace.EvidenceValidationError, "export digest mismatch"):
            control.reduce_control(self.manifest, self.control, self.export)
