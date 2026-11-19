"""Exercise the N12 background writer control with generated evidence."""
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
from unittest import TestCase

from qa.p4_native import n12_background_thread as control, n12_trace as trace


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

    def reduce(self):
        self.export.write_text("".join(json.dumps(row) + "\n" for row in self.events), encoding="utf-8")
        self.manifest["etw"]["events_sha256"] = hashlib.sha256(self.export.read_bytes()).hexdigest()
        return control.reduce_control(self.manifest, self.control, self.export)

    def test_matches_known_completed_write(self):
        self.assertEqual(self.reduce(), {
            "control_status": "PASS", "known_completed_writes": 1,
            "issuing_thread": "bookend-header-agrees", "validated_etw_events": 2,
            "scope": "background writer thread identity",
        })

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
