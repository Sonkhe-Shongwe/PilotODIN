"""Replay generated WebView2 write completions without starting a live trace."""

import hashlib
import json
from itertools import count
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from qa.p4_native import n12_etw_correlate as reduce_io, n12_trace as trace


ROLE = "webview-network"
PROFILE = r"c:\qa\profile"
PROTECTED = r"c:\qa\protected"
OUTSIDE = r"c:\qa\profile-sibling"
PERMITTED_PATH = PROFILE + r"\private-cache.bin"
PROTECTED_PATH = PROTECTED + r"\private-control.bin"
OUTSIDE_PATH = OUTSIDE + r"\private-control.bin"


def event(ticks, kind, **data):
    return {"ticks": ticks, "id": kind, "pid": 7, "lifecycle": kind in {1, 3}, "data": data}


def dominant_pair_events(pair_sizes=((100, 121_122), (200, 78_040))):
    ticks = count(1)
    yield event(next(ticks), 1, ProcessID=7)
    yield event(next(ticks), 3, ProcessID=7, ThreadID=71)
    for key, writes in pair_sizes:
        yield event(next(ticks), 10, FileKey=key, FileName=PERMITTED_PATH)
        for _ in range(writes):
            # The same IRP is reusable once its previous write has completed.
            yield event(next(ticks), 16, FileKey=key, FileObject=key + 1, Irp=500, IssuingThreadId=71)
            yield event(next(ticks), 24, Irp=500, Status=0, FileKey=key, FileObject=key + 1)


class WebViewWriteReplayTests(unittest.TestCase):
    def reduce_pairs(self, rows):
        report = {}
        unresolved = reduce_io.correlate_requests(
            rows, lambda path: path or None,
            lambda *_: (ROLE, "generated-process"), lambda path: path == PROTECTED_PATH,
            lambda *_: self.fail("The diagnostic changed the strict file findings"),
            strict=True, webview_write_candidates=report, webview_dominant_writes=True,
            classify_webview_path=lambda path: "candidate-permitted" if path == PERMITTED_PATH
            else "candidate-outside-scope",
        )
        return report, unresolved

    def test_dominant_pairs_check_every_generated_completion(self):
        checked_writes = 199_162
        report, unresolved = self.reduce_pairs(dominant_pair_events())
        self.assertEqual(unresolved, {f"{ROLE}:write:path-missing": checked_writes})
        self.assertEqual((report["eligible"], report["sampled"], report["eligible_outside_sample"]),
                         (checked_writes, 2, 0))
        self.assertEqual([pair["checked"] for pair in report["pairs"]], [16, 16])
        dominant = report["dominant"]
        self.assertEqual(dominant["status"], "complete")
        self.assertEqual(dominant["eligible_outside_selected_pairs"], 0)
        for pair, writes in zip(dominant["pairs"], (121_122, 78_040), strict=True):
            self.assertEqual(pair, {
                "eligible": writes, "checked": writes, "supported": writes,
                "blocked": 0, "unchecked": 0, "unchecked_by_reason": {},
                "outcomes": {f"{ROLE}:write:request-time:candidate-permitted": writes},
            })
        self.assertNotIn("private-", json.dumps(report))

    def test_ranks_pairs_after_the_initial_sample_and_accounts_for_retention(self):
        pair_sizes = [(key, 1) for key in range(1, 66)] + [(100, 25), (200, 30)]
        # The smaller pairs finish first. Count all pairs even after retention runs out.
        with patch.object(reduce_io, "WEBVIEW_DOMINANT_WRITE_LIMIT", 93):
            report, _ = self.reduce_pairs(dominant_pair_events(pair_sizes))
        dominant = report["dominant"]
        self.assertEqual(dominant["status"], "partial")
        self.assertEqual(dominant["eligible_outside_selected_pairs"], 65)
        self.assertEqual([(p["eligible"], p["checked"], p["unchecked_by_reason"]) for p in dominant["pairs"]],
                         [(30, 3, {"retention-limit": 27}), (25, 25, {})])
        self.assertEqual(report["eligible_outside_sample"], 56)

        with patch.object(reduce_io, "WEBVIEW_DOMINANT_PAIR_LIMIT", 66):
            report, _ = self.reduce_pairs(dominant_pair_events(pair_sizes))
        self.assertEqual(report["dominant"], {
            "status": "pair-limit-reached", "eligible": 120, "pairs": [],
            "eligible_outside_selected_pairs": None,
        })

    def test_replay_preserves_conflicts_and_strict_protected_and_outside_findings(self):
        start, end = map(trace.utc_time, ("2026-11-18T00:00:00Z", "2026-11-18T00:00:01Z"))
        ticks = count(trace.utc_ticks(start) + 1)
        rows = []

        def emit(kind, **data):
            rows.append(event(next(ticks), kind, **data))

        def write(key, obj, irp):
            emit(16, FileKey=key, FileObject=obj, Irp=irp, IssuingThreadId=71)

        def complete(irp):
            emit(24, Irp=irp, Status=0)

        emit(1, ProcessID=7)
        emit(3, ProcessID=7, ThreadID=71)
        emit(10, FileKey=100, FileName=PERMITTED_PATH)
        write(100, 101, 500)
        complete(500)
        write(100, 101, 500)
        write(99, 101, 501)  # Same object, conflicting key, with no known name of its own.
        complete(501)
        complete(500)
        emit(11, FileKey=100)
        emit(10, FileKey=100, FileName=OUTSIDE_PATH)
        write(100, 101, 500)
        complete(500)
        write(100, 101, 500)
        complete(500)
        rows.append(dict(rows[-1]))  # Duplicate completion at the same timestamp.
        write(100, 101, 500)
        emit(19, FileKey=100, FileObject=101, Irp=504)
        emit(27, FileObject=101, Irp=504, FilePath=PROTECTED_PATH)
        complete(504)
        complete(500)

        for key, path in ((200, PROTECTED_PATH), (300, OUTSIDE_PATH)):
            emit(12, FileObject=key + 1, Irp=key, FileName=path)
            emit(24, Irp=key, Status=0, ExtraInformation=1)
            write(key, key + 1, key + 10)
            complete(key + 10)

        payload = "".join(json.dumps(row) + "\n" for row in rows).encode()
        manifest = {"etw": {
            "schema_version": 1, "start_utc": start.isoformat(), "end_utc": end.isoformat(),
            "events_sha256": hashlib.sha256(payload).hexdigest(),
            "volume_devices": {"C:": r"\Device\HarddiskVolume3"},
            "counters": {"events_lost": 0, "log_buffers_lost": 0,
                         "realtime_buffers_lost": 0, "buffers_written": 1},
        }}
        processes = {"webview": trace.Process("webview", "app", 7, "msedgewebview2.exe", None, start, "")}
        report, replay_issues, baseline_issues = {}, set(), set()
        with TemporaryDirectory() as folder:
            path = Path(folder) / "generated-etw.jsonl"
            path.write_bytes(payload)
            args = (manifest, path, start, end, processes, {"webview": ROLE}, [PROTECTED], {ROLE: [PROFILE]})
            baseline = trace.inspect_etw_files(*args, baseline_issues)
            replay = trace.inspect_etw_files(*args, replay_issues, webview_write_candidates=report,
                                             webview_dominant_writes=True)
            limited = {}
            with patch.object(reduce_io, "WEBVIEW_DOMINANT_HISTORY_LIMIT", 1):
                trace.inspect_etw_files(*args, set(), webview_write_candidates=limited, webview_dominant_writes=True)

        self.assertEqual(replay, baseline)
        self.assertEqual(replay_issues, baseline_issues)
        self.assertEqual(replay_issues, {"etw-mutation-coverage-unresolved"})
        self.assertEqual(replay[1][f"protected:{ROLE}:write"], 1)
        self.assertEqual(replay[1][f"outside-scope:{ROLE}:write"], 2)
        self.assertEqual(replay[3][f"{ROLE}:write:path-missing"], 6)
        self.assertEqual(report["pairs"], [{
            "eligible": 5, "checked": 5, "supported": 2, "blocked": 3, "unchecked": 0,
            "outcomes": {
                f"{ROLE}:write:request-time:candidate-permitted": 1,
                f"{ROLE}:write:request-time:conflicting-object-file-key": 1,
                f"{ROLE}:write:request-time:candidate-outside-scope": 1,
                f"{ROLE}:write:request-time:request-completion-unverified": 1,
                f"{ROLE}:write:request-time:possible-name-change": 1,
            },
        }])
        self.assertEqual(report["dominant"]["pairs"], [report["pairs"][0] | {"unchecked_by_reason": {}}])
        self.assertEqual(limited["dominant"]["status"], "partial")
        self.assertEqual(limited["dominant"]["pairs"][0]["unchecked_by_reason"], {"path-history-limit": 5})
