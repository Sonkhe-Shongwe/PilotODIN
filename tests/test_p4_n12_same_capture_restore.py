"""Replay generated ETW evidence for the in-journey write-and-restore control."""

import hashlib
import inspect
import json
import unittest
from datetime import datetime, timedelta, timezone

from qa.p4_native import n12_protected_restore as restore
from qa.p4_research import n12_app_journey as journey


TARGET = r"C:\QA\write-restore-control.bin"
DEVICES = {r"\device\harddiskvolume3": "c:"}
WINDOW = (100, 500)


def control_and_events():
    original = hashlib.sha256(restore.ORIGINAL).hexdigest()
    control = {"path": TARGET, "before": original, "after": original, "stages": {}}
    events = []

    def emit(kind, pid, tick, *, lifecycle=False, **data):
        events.append({"id": kind, "pid": pid, "ticks": tick, "lifecycle": lifecycle, "data": data})

    for stage, payload, pid, start in (("mutate", restore.MODIFIED, 21, 200),
                                       ("restore", restore.ORIGINAL, 22, 300)):
        control["stages"][stage] = {"pid": pid, "start": start, "end": start + 20, "size": len(payload),
                                     "digest": hashlib.sha256(payload).hexdigest()}
        emit(1, 0, start + 1, lifecycle=True, ProcessID=pid)
        emit(12, pid, start + 2, FileObject=pid, Irp=pid * 2, FileName=TARGET)
        emit(24, 0, start + 3, Irp=pid * 2, Status=0, ExtraInformation=1)
        emit(16, pid, start + 4, FileObject=pid, FileKey=7, Irp=pid * 2 + 1, IOSize=len(payload), ByteOffset=0)
        emit(24, 0, start + 5, Irp=pid * 2 + 1, Status=0)
        emit(13, pid, start + 11, FileObject=pid, FileKey=7)
        emit(14, pid, start + 12, FileObject=pid, FileKey=7)
        emit(2, 0, start + 15, lifecycle=True, ProcessID=pid)
    return control, events


class SameCaptureRestoreTests(unittest.TestCase):
    def test_restored_bytes_still_require_two_attributed_writes(self):
        control, events = control_and_events()
        result = journey.same_capture_restore_evidence(control, TARGET, events, DEVICES, WINDOW, frozenset())
        self.assertEqual(result["status"], "PASS")
        self.assertTrue(result["endpoint_match"])
        self.assertEqual(result["write_path_verified"], {"mutate": True, "restore": True})
        self.assertNotIn("write-restore-control.bin", json.dumps(result))

    def test_untrustworthy_write_evidence_blocks(self):
        for fault in ("missing", "wrong-writer", "wrong-path", "prior-conflicting-name", "failed-completion", "extra-write"):
            with self.subTest(fault=fault):
                control, events = control_and_events()
                opening, write, completion = events[9], events[11], events[12]
                if fault == "missing":
                    events.remove(write)
                    events.remove(completion)
                elif fault == "wrong-writer":
                    write["pid"] = 90
                elif fault == "wrong-path":
                    opening["data"]["FileName"] = r"C:\QA\other.bin"
                elif fault == "prior-conflicting-name":
                    events.insert(8, dict(opening, id=10, ticks=290,
                                          data={"FileKey": 7, "FileName": r"C:\QA\other.bin"}))
                elif fault == "failed-completion":
                    completion["data"]["Status"] = 5
                else:
                    events[13:13] = [
                        dict(write, ticks=306, data={**write["data"], "Irp": 100, "IOSize": 1}),
                        dict(completion, ticks=307, data={"Irp": 100, "Status": 0}),
                    ]
                result = journey.same_capture_restore_evidence(control, TARGET, events, DEVICES, WINDOW, frozenset())
                self.assertEqual(result["status"], "BLOCKED")
                self.assertTrue(result["endpoint_match"])
                self.assertEqual(result["write_path_verified"], {"mutate": True, "restore": False})
                self.assertIn("restore", result["write_issues"])
                if fault == "extra-write":
                    self.assertEqual(result["write_issues"]["restore"], "extra-write-on-control-handle")

    def test_wrong_target_out_of_window_and_unverified_lifetime_block(self):
        for fault in ("wrong-target", "out-of-window", "duplicate-lifetime", "changed-endpoint"):
            with self.subTest(fault=fault):
                control, events = control_and_events()
                window = WINDOW
                if fault == "wrong-target":
                    control["path"] = r"C:\QA\other.bin"
                elif fault == "out-of-window":
                    window = (100, 319)
                elif fault == "duplicate-lifetime":
                    events.insert(9, dict(events[8]))
                else:
                    control["after"] = control["stages"]["mutate"]["digest"]
                result = journey.same_capture_restore_evidence(control, TARGET, events, DEVICES, window, frozenset())
                self.assertEqual(result["status"], "BLOCKED")
                self.assertIn("reason", result)
                self.assertNotIn("other.bin", json.dumps(result))

    def test_capture_loss_blocks_even_when_both_writes_are_identified(self):
        control, events = control_and_events()
        result = journey.same_capture_restore_evidence(
            control, TARGET, events, DEVICES, WINDOW, frozenset({"etw-event-or-buffer-loss"}),
        )
        self.assertEqual(result["status"], "BLOCKED")
        self.assertTrue(result["etw_reported_loss"])
        self.assertEqual(result["write_path_verified"], {"mutate": True, "restore": True})

    def test_scoped_control_cannot_override_existing_findings(self):
        prior = {"coverage": "BLOCKED", "filesystem": "FAIL", "network": "PARTIAL",
                 "coverage_issues": ["etw-mutation-coverage-unresolved"],
                 "etw_unresolved_mutations": {"webview:write:path-missing": 1},
                 "file_violations": {"protected:backend:write": 1}}
        result = {**prior}
        journey.require_same_capture_restore(result, {"status": "PASS"})
        self.assertEqual(result, prior)
        journey.require_same_capture_restore(result, {"status": "BLOCKED"})
        self.assertEqual((result["filesystem"], result["network"]), ("FAIL", "PARTIAL"))
        self.assertEqual(result["etw_unresolved_mutations"], prior["etw_unresolved_mutations"])
        self.assertEqual(result["file_violations"], prior["file_violations"])
        self.assertIn("etw-same-capture-restore-unverified", result["coverage_issues"])

    def test_missing_control_cannot_allow_clean_app_verdicts(self):
        result = {"coverage": "CALIBRATED", "filesystem": "PASS_SCOPED", "network": "PASS_SCOPED",
                  "coverage_issues": []}
        journey.require_same_capture_restore(result, {"status": "BLOCKED", "reason": "restore-evidence-missing"})
        self.assertEqual(result, {"coverage": "BLOCKED", "filesystem": "BLOCKED", "network": "BLOCKED",
                                  "coverage_issues": ["etw-same-capture-restore-unverified"]})

class SnapshotCaptureOrderingTests(unittest.TestCase):
    def test_both_complete_fingerprints_must_be_within_one_capture(self):
        start = datetime(2026, 11, 20, tzinfo=timezone.utc)
        end = start + timedelta(seconds=20)
        def iso(seconds):
            return (start + timedelta(seconds=seconds)).isoformat()
        markers = {
            "snapshot-before-start": iso(1),
            "snapshot-before-end": iso(2),
            "snapshot-after-start": iso(17),
            "snapshot-after-end": iso(18),
        }
        self.assertEqual(journey.snapshot_capture_evidence({"markers": markers}, start, end),
                         {"status": "PASS", "before_in_capture": True, "after_in_capture": True})
        for name, stamp in (("snapshot-before-start", iso(-1)),
                            ("snapshot-before-end", iso(22)),
                            ("snapshot-after-start", iso(1)),
                            ("snapshot-after-end", iso(21))):
            with self.subTest(name=name):
                with self.assertRaisesRegex(Exception, "snapshot-capture-unbracketed"):
                    journey.snapshot_capture_evidence({"markers": dict(markers, **{name: stamp})}, start, end)
        for name in markers:
            with self.subTest(missing=name):
                changed = dict(markers)
                changed.pop(name)
                with self.assertRaisesRegex(Exception, "snapshot-capture-markers-missing"):
                    journey.snapshot_capture_evidence({"markers": changed}, start, end)

    def test_capture_source_scans_under_live_etw_before_rundown_stop(self):
        source = inspect.getsource(journey.capture)
        self.assertLess(source.index("start_journey_etw("), source.index('mark(manifest, "snapshot-before-start")'))
        self.assertLess(source.index("before = snapshots(manifest)"), source.index("run_initial_calibration("))
        self.assertLess(source.index('manifest["end_utc"] = final_end.isoformat()'),
                        source.index('mark(manifest, "snapshot-after-start")'))
        self.assertLess(source.index("after = snapshots(manifest)"), source.index("stop_rundown()"))
        self.assertLess(source.index("after = snapshots(manifest)"),
                        source.index("counters, capture_end = stop_capture("))
        self.assertLess(source.index("counters, capture_end = stop_capture("),
                        source.index("snapshot_capture_evidence("))
