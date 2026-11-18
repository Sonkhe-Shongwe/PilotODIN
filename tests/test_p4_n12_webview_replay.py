"""Replay generated WebView2 write completions without starting a live trace."""

import hashlib
import json
from collections import Counter
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


def dominant_pair_events(pair_sizes, *, repeat_path_evidence=False, unnamed_key=None):
    ticks = count(1)
    yield event(next(ticks), 1, ProcessID=7)
    yield event(next(ticks), 3, ProcessID=7, ThreadID=71)
    for key, writes in pair_sizes:
        if key != unnamed_key:
            yield event(next(ticks), 10, FileKey=key, FileName=PERMITTED_PATH)
        for index in range(writes):
            if key != unnamed_key and repeat_path_evidence and index % 64 == 0:
                yield event(next(ticks), 10, FileKey=key, FileName=PERMITTED_PATH)
                yield event(next(ticks), 15, FileKey=key, FileObject=key + 1)
            # The same IRP is reusable once its previous write has completed.
            yield event(next(ticks), 16, FileKey=key, FileObject=key + 1, Irp=500, IssuingThreadId=71)
            yield event(next(ticks), 24, Irp=500, Status=0, FileKey=key, FileObject=key + 1)


class WebViewWriteReplayTests(unittest.TestCase):
    def reduce_pairs(self, rows, credit=None):
        report = {}
        unresolved = reduce_io.correlate_requests(
            rows, lambda path: path or None,
            lambda *_: (ROLE, "generated-process"), lambda path: path == PROTECTED_PATH,
            lambda *_: self.fail("The diagnostic changed the strict file findings"),
            strict=True, webview_write_candidates=report, webview_dominant_writes=True,
            credit_webview_path=credit,
            classify_webview_path=lambda path: "candidate-permitted" if path == PERMITTED_PATH
            else "candidate-outside-scope",
        )
        return report, unresolved

    def test_dominant_pairs_check_every_generated_completion(self):
        credited = Counter()

        def credit(identity, path, requested, completed):
            self.assertEqual((identity, path), ("generated-process", PERMITTED_PATH))
            self.assertLess(requested, completed)
            credited[path] += 1
            return True

        pair_sizes = [(100, 121_256), (200, 78_686), (300, 121), (400, 14)]
        report, unresolved = self.reduce_pairs(
            dominant_pair_events(pair_sizes, repeat_path_evidence=True, unnamed_key=400), credit,
        )
        self.assertEqual(credited, {PERMITTED_PATH: 199_942})
        self.assertEqual(unresolved, {f"{ROLE}:write:path-missing": 135})
        self.assertEqual((report["eligible"], report["sampled"], report["eligible_outside_sample"]),
                         (200_063, 3, 0))
        self.assertEqual([pair["checked"] for pair in report["pairs"]], [16, 16, 16])
        dominant = report["dominant"]
        self.assertEqual(dominant["status"], "complete")
        self.assertEqual(dominant["eligible_outside_selected_pairs"], 121)
        for pair, writes in zip(dominant["pairs"], (121_256, 78_686), strict=True):
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
        for _ in range(100):
            emit(10, FileKey=100, FileName=PERMITTED_PATH)
            emit(15, FileKey=100, FileObject=101)
        write(100, 101, 500)
        complete(500)
        rows.append(event(rows[-1]["ticks"] + 1, 3, ProcessID=7, ThreadID=71))
        write(100, 101, 505)  # Issuer birth ties the write timestamp.
        complete(505)
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
        emit(10, FileKey=400, FileName=PROTECTED_PATH)
        write(400, 401, 406)
        complete(406)
        write(400, 401, 407)
        emit(24, Irp=407, Status=0, FileObject=999)
        write(400, 401, 408)
        emit(24, Irp=408, Status=0xC0000022)
        write(400, 401, 409)  # No completion observed.

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
        }, "source_sha": "1" * 40, "executable_sha256": "2" * 64,
            "protected_roots": {"original": PROTECTED},
            "observed_roots": {"fixture": r"c:\qa\source.csv"}, "immutable_observed": ["fixture"],
            "permitted_writes": {ROLE: [PROFILE]}}
        processes = {"webview": trace.Process("webview", "app", 7, "msedgewebview2.exe", None, start, "")}
        snapshot = {kind: {label: {"root_id": hashlib.sha256(value.encode()).hexdigest(),
                                   "state": "file", "digest": "3" * 64}
                           for label, value in manifest[f"{kind}_roots"].items()}
                    for kind in ("protected", "observed")}
        unexpected = {"role": ROLE, "kind": "unexpected-loopback", "protocol": "tcp"}
        observed = trace.JourneySysmon(
            start=start, end=end, markers={}, processes=processes, roles={"webview": ROLE},
            bindings=[], issues=set(), connections=[],
            network_counts=Counter({f"{ROLE}:tcp:unexpected-loopback": 1}),
            unexpected_connections=[unexpected],
        )
        report, replay_issues, baseline_issues = {}, set(), set()
        with TemporaryDirectory() as folder:
            path = Path(folder) / "generated-etw.jsonl"
            path.write_bytes(payload)
            args = (manifest, path, start, end, processes, {"webview": ROLE}, [PROTECTED], {ROLE: [PROFILE]})
            baseline = trace.inspect_etw_files(*args, baseline_issues)
            replay = trace.inspect_etw_files(*args, replay_issues, webview_write_candidates=report,
                                             webview_dominant_writes=True)
            journey = trace.complete_journey_audit(
                manifest, observed, path, snapshot, snapshot, etw=True, describe_path_gaps=True,
                webview_dominant_writes=True, credit_verified_webview_writes=True,
            )
            manifest["etw"]["counters"]["log_buffers_lost"] = 1
            loss = trace.complete_journey_audit(
                manifest, observed, path, snapshot, snapshot, etw=True, describe_path_gaps=True,
                webview_dominant_writes=True, credit_verified_webview_writes=True,
            )

        self.assertEqual(replay, baseline)
        self.assertEqual(replay_issues, baseline_issues)
        self.assertEqual(replay_issues, {"etw-mutation-coverage-unresolved"})
        self.assertEqual(replay[1][f"protected:{ROLE}:write"], 1)
        self.assertEqual(replay[1][f"outside-scope:{ROLE}:write"], 2)
        self.assertEqual(replay[3], {
            f"{ROLE}:write:path-missing": 9, f"{ROLE}:write:completion-missing": 1,
            f"{ROLE}:rename:path-missing": 1,
        })
        self.assertEqual(report["pairs"][0], {
            "eligible": 6, "checked": 6, "supported": 3, "blocked": 3, "unchecked": 0,
            "outcomes": {
                f"{ROLE}:write:request-time:candidate-permitted": 2,
                f"{ROLE}:write:request-time:conflicting-object-file-key": 1,
                f"{ROLE}:write:request-time:candidate-outside-scope": 1,
                f"{ROLE}:write:request-time:request-completion-unverified": 1,
                f"{ROLE}:write:request-time:possible-name-change": 1,
            },
        })
        self.assertEqual(report["dominant"]["pairs"], [p | {"unchecked_by_reason": {}} for p in report["pairs"]])
        self.assertEqual(journey["etw_webview_write_path_candidates"], report)
        self.assertEqual(journey["etw_webview_write_credit"], {
            "status": "compared", "credited_paths": {"permitted": 1, "outside-scope": 1, "protected": 1},
            "remaining_path_gaps": 6,
        })
        self.assertEqual(journey["etw_unresolved_mutations"], {
            f"{ROLE}:write:path-missing": 6, f"{ROLE}:write:completion-missing": 1,
            f"{ROLE}:rename:path-missing": 1,
        })
        self.assertEqual(journey["file_violations"][f"protected:{ROLE}:write"], 2)
        self.assertEqual(journey["file_violations"][f"outside-scope:{ROLE}:write"], 4)
        self.assertEqual(journey["file_events"][f"{ROLE}:write"], 5)
        self.assertEqual(journey["unexpected_connections"], [unexpected])
        self.assertEqual((journey["filesystem"], journey["network"], journey["coverage"]), ("FAIL", "FAIL", "BLOCKED"))
        self.assertEqual(loss["etw_webview_write_credit"], {
            "status": "blocked-etw-loss", "credited_paths": {}, "remaining_path_gaps": 9,
        })
        self.assertIn("etw-event-or-buffer-loss", loss["coverage_issues"])
        self.assertEqual(loss["etw_unresolved_mutations"], replay[3])
        self.assertEqual(loss["file_violations"], replay[1])
        self.assertNotIn("private-", json.dumps(journey["etw_webview_write_credit"]))

    def test_indexed_history_preserves_tied_events_and_lifetime_boundaries(self):
        anchor = event(10, 10, FileKey=100, FileName=PERMITTED_PATH)
        write = event(30, 16, FileKey=100, FileObject=101, Irp=500)
        completion = event(50, 24, Irp=500, Status=0)
        cases = (
            ([event(20, 10, FileKey=100, FileName=PERMITTED_PATH)], "candidate-permitted"),
            ([event(30, 10, FileKey=100, FileName=PERMITTED_PATH)], "ambiguous-event-order"),
            ([event(40, 10, FileKey=100, FileName=OUTSIDE_PATH)], "conflicting-or-unmapped-name"),
            ([event(40, 11, FileKey=100), event(40, 10, FileKey=100, FileName=OUTSIDE_PATH)],
             "possible-name-change"),
            ([event(40, 14, FileKey=100, FileObject=101)], "file-object-lifetime-changed"),
            ([event(50, 14, FileKey=100, FileObject=101)], "ambiguous-event-order"),
            ([event(20, 11, FileKey=100), event(20, 10, FileKey=100, FileName=OUTSIDE_PATH)],
             "ambiguous-event-order"),
        )
        for changes, expected in cases:
            with self.subTest(expected=expected, changes=changes):
                key_events = [anchor, *changes]
                object_events = [row for row in changes if row["data"].get("FileObject") == 101]
                irp_events = [write, completion]

                def resolve_path(path):
                    return path or None

                def classify_path(path):
                    return "candidate-permitted" if path == PERMITTED_PATH else "candidate-outside-scope"

                old = reduce_io.request_time_file_key_evidence(
                    write, 50, object_events, key_events, irp_events, resolve_path, classify_path,
                )
                history = reduce_io.RequestPathHistory(100, 101, object_events, key_events, resolve_path)
                self.assertEqual(old, expected)
                issue, path = history.resolve(write, 50, irp_events)
                self.assertEqual(issue or classify_path(path), old)
