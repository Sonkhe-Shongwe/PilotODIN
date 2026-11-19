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
from qa.p4_research.n12_journey_diagnostics import OutsidePaths


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
        self.assertEqual(credited, {PERMITTED_PATH: 200_063})
        self.assertEqual(unresolved, {f"{ROLE}:write:path-missing": 14})
        self.assertEqual((report["eligible"], report["sampled"], report["eligible_outside_sample"]),
                         (200_063, 3, 0))
        self.assertEqual([pair["checked"] for pair in report["pairs"]], [16, 16, 16])
        dominant = report["dominant"]
        self.assertEqual(dominant["status"], "complete")
        self.assertEqual(dominant["eligible_outside_selected_pairs"], 121)
        self.assertEqual(dominant["smaller_pairs"], {
            "eligible": 121, "checked": 121, "supported": 121, "credited": 121,
            "blocked": 0, "unchecked": 0, "unchecked_by_reason": {},
            "outcomes": {f"{ROLE}:write:request-time:candidate-permitted": 121},
        })
        for pair, writes in zip(dominant["pairs"], (121_256, 78_686), strict=True):
            self.assertEqual(pair, {
                "eligible": writes, "checked": writes, "supported": writes,
                "blocked": 0, "unchecked": 0, "unchecked_by_reason": {},
                "outcomes": {f"{ROLE}:write:request-time:candidate-permitted": writes},
            })
        self.assertNotIn("private-", json.dumps(report))

    def test_comparison_rechecks_smaller_pairs_without_crediting_conflicts_or_invalidated_names(self):
        ticks = count(1)
        rows = [event(next(ticks), 1, ProcessID=7), event(next(ticks), 3, ProcessID=7, ThreadID=71)]
        for key, writes, path in ((100, 105, PERMITTED_PATH), (200, 103, PERMITTED_PATH),
                                  (300, 102, OUTSIDE_PATH), (400, 15, OUTSIDE_PATH),
                                  (500, 9, PERMITTED_PATH), (600, 1, PERMITTED_PATH),
                                  (700, 14, PERMITTED_PATH)):
            rows.append(event(next(ticks), 10, FileKey=key, FileName=path))
            if key == 500:
                rows.append(event(next(ticks), 15, FileKey=501, FileObject=key + 1))
            if key == 700:
                rows.append(event(next(ticks), 13, FileKey=key, FileObject=key + 2))
            for _ in range(writes):
                rows.append(event(next(ticks), 16, FileKey=key, FileObject=key + 1, Irp=20, IssuingThreadId=71))
                rows.append(event(next(ticks), 24, Irp=20, Status=0, FileKey=key, FileObject=key + 1))

        baseline, unresolved = self.reduce_pairs(rows)
        self.assertEqual(unresolved, {f"{ROLE}:write:path-missing": 349})
        self.assertEqual(baseline["dominant"]["eligible_outside_selected_pairs"], 127)
        self.assertNotIn("smaller_pairs", baseline["dominant"])

        credited = Counter()

        def credit(identity, path, requested, completed):
            credited[path] += 1
            return True

        compared, unresolved = self.reduce_pairs(rows, credit)
        self.assertEqual(compared["dominant"]["pairs"], baseline["dominant"]["pairs"])
        self.assertEqual(credited, {PERMITTED_PATH: 209, OUTSIDE_PATH: 117})
        self.assertEqual(unresolved, {f"{ROLE}:write:path-missing": 23})
        self.assertEqual(compared["dominant"]["smaller_pairs"], {
            "eligible": 127, "checked": 127, "supported": 118, "credited": 118,
            "blocked": 9, "unchecked": 0, "unchecked_by_reason": {},
            "outcomes": {
                f"{ROLE}:write:request-time:candidate-outside-scope": 117,
                f"{ROLE}:write:request-time:candidate-permitted": 1,
                f"{ROLE}:write:request-time:conflicting-object-file-key": 9,
            },
        })
        self.assertNotIn("private-", json.dumps(compared))

        with patch.object(reduce_io, "WEBVIEW_DOMINANT_WRITE_LIMIT", 230):
            limited, unresolved = self.reduce_pairs(rows, lambda *_: True)
        remainder = limited["dominant"]["smaller_pairs"]
        self.assertEqual(remainder["unchecked_by_reason"], {"retention-limit": 105})
        self.assertEqual(remainder["credited"], 22)
        self.assertEqual(unresolved, {f"{ROLE}:write:path-missing": 119})

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

    def test_cleanup_name_gaps_report_open_evidence_without_changing_findings(self):
        start, end = map(trace.utc_time, ("2026-11-18T00:00:00Z", "2026-11-18T00:00:01Z"))
        ticks = count(trace.utc_ticks(start) + 1)
        rows = []

        def emit(kind, *, pid=7, **data):
            rows.append(event(next(ticks), kind, **data) | {"pid": pid})

        emit(1, ProcessID=7)
        emit(3, ProcessID=7, ThreadID=71)
        emit(1, pid=8, ProcessID=8)
        cases = (
            ("permitted", PERMITTED_PATH), ("protected", PROTECTED_PATH), ("outside", OUTSIDE_PATH),
            ("no-open", PERMITTED_PATH), ("no-open", PERMITTED_PATH),
            ("failed-open", PERMITTED_PATH), ("missing-open-completion", PERMITTED_PATH),
            ("late-open-completion", PERMITTED_PATH), ("tied-open-completion", PERMITTED_PATH),
            ("intervening-irp-event", PERMITTED_PATH), ("missing-open-irp", PERMITTED_PATH),
            ("missing-open-status", PERMITTED_PATH), ("nonzero-open-status", PERMITTED_PATH),
            ("name-conflict", PERMITTED_PATH),
            ("same-object-cleanup", PERMITTED_PATH), ("key-conflict", PERMITTED_PATH),
            ("open-completion-conflict", PERMITTED_PATH), ("open-key-conflict", PERMITTED_PATH),
            ("write-completion-conflict", PERMITTED_PATH),
            ("tied-completion", PERMITTED_PATH), ("missing-thread", PERMITTED_PATH),
            ("opener-exited", PERMITTED_PATH), ("failed-write", PERMITTED_PATH),
            ("no-cleanup", PERMITTED_PATH),
        )
        open_statuses = {"failed-open": 0xC0000022, "missing-open-status": None, "nonzero-open-status": 1}
        for key, (case, path) in enumerate(cases, start=100):
            obj = key + 1_000
            open_irp = 0 if case == "missing-open-irp" else key + 2_000
            if case != "no-open":
                # The opener has a separate ETW lifetime from the writer.
                emit(12, pid=8, FileObject=obj, Irp=open_irp, FileName=path)
                if case == "intervening-irp-event":
                    emit(15, pid=8, FileObject=obj + 1, Irp=open_irp)
                if case not in {"missing-open-completion", "late-open-completion", "missing-open-irp"}:
                    emit(24, pid=8, Irp=open_irp, Status=open_statuses.get(case, 0), ExtraInformation=1,
                         FileObject=999 if case == "open-completion-conflict" else obj,
                         FileKey=9_999 if case == "open-key-conflict" else key)
                    if case == "tied-open-completion":
                        rows.append(dict(rows[-1]))
            emit(10, FileKey=key, FileName=path)
            if case != "no-cleanup":
                emit(13, pid=8, FileKey=key, FileObject=obj + 1_000)
            if case == "name-conflict":
                emit(10, FileKey=key, FileName=OUTSIDE_PATH)
            if case == "same-object-cleanup":
                emit(13, pid=8, FileKey=key, FileObject=obj)
            if case == "key-conflict":
                emit(15, pid=8, FileKey=9_999, FileObject=obj)
            if case == "opener-exited":
                emit(2, pid=8, ProcessID=8)
                rows[-1]["lifecycle"] = True
            emit(16, FileObject=obj, FileKey=key, Irp=20, IssuingThreadId=0 if case == "missing-thread" else 71)
            if case == "late-open-completion":
                emit(24, pid=8, Irp=open_irp, Status=0, ExtraInformation=1, FileObject=obj)
            emit(24, Irp=20, Status=0xC0000022 if case == "failed-write" else 0,
                 FileObject=999 if case == "write-completion-conflict" else obj)
            if case == "tied-completion":
                rows.append(dict(rows[-1]))

        payload = "".join(json.dumps(row) + "\n" for row in rows).encode()
        manifest = {"etw": {
            "schema_version": 1, "start_utc": start.isoformat(), "end_utc": end.isoformat(),
            "events_sha256": hashlib.sha256(payload).hexdigest(),
            "volume_devices": {"C:": r"\Device\HarddiskVolume3"},
            "counters": {"events_lost": 0, "log_buffers_lost": 0,
                         "realtime_buffers_lost": 0, "buffers_written": 1},
        }}
        processes = {"webview": trace.Process("webview", "app", 7, "msedgewebview2.exe", None, start, "")}
        report, lost = {}, {}
        with TemporaryDirectory() as folder:
            path = Path(folder) / "generated-etw.jsonl"
            path.write_bytes(payload)
            args = (manifest, path, start, end, processes, {"webview": ROLE}, [PROTECTED], {ROLE: [PROFILE]})
            baseline_issues, reported_issues, lost_issues = set(), set(), set()
            baseline = trace.inspect_etw_files(*args, baseline_issues)
            observed = trace.inspect_etw_files(*args, reported_issues, webview_write_candidates=report)
            manifest["etw"]["counters"]["log_buffers_lost"] = 1
            trace.inspect_etw_files(*args, lost_issues, webview_write_candidates=lost)

        self.assertEqual(observed, baseline)
        self.assertEqual(reported_issues, baseline_issues)
        self.assertEqual(observed[1], {})
        self.assertEqual(observed[3], {f"{ROLE}:write:path-missing": 23})
        self.assertEqual(report["cleanup_open_evidence"], {
            "status": "evaluated", "eligible": 22,
            "outcomes": {
                "candidate-permitted": 1, "candidate-protected": 1, "candidate-outside-scope": 1,
                "no-observed-open": 2, "open-completion-failed": 1,
                "open-completion-missing-before-boundary": 2, "open-completion-ambiguous-order": 1,
                "open-completion-intervening-request-event": 1, "open-completion-request-id-missing": 1,
                "open-completion-status-missing": 1, "open-completion-status-nonzero": 1,
                "conflicting-or-unmapped-name": 1, "file-object-lifetime-changed": 1,
                "same-object-file-key-conflict:event-15": 1, "open-completion-file-key-conflict": 1,
                "open-completion-file-identity-conflict": 1,
                "completion-file-identity-conflict": 1, "write-completion-unverified": 1,
                "write-identity-unverified": 1, "open-process-lifetime-unverified": 1,
            },
        })
        self.assertEqual(lost["cleanup_open_evidence"], {"status": "blocked-etw-loss"})
        self.assertIn("etw-event-or-buffer-loss", lost_issues)
        self.assertNotIn("private-", json.dumps(report))

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
        emit(10, FileKey=600, FileName=OUTSIDE_PATH)
        write(600, 601, 610)
        complete(610)

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
        outside_paths = OutsidePaths([("generated-outside", OUTSIDE), ("generated-protected", PROTECTED)])
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
                record_outside_writer=outside_paths.record,
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
            f"{ROLE}:write:path-missing": 10, f"{ROLE}:write:completion-missing": 1,
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
        self.assertEqual(report["dominant"]["pairs"], [p | {"unchecked_by_reason": {}} for p in report["pairs"][:2]])
        compared_paths = journey["etw_webview_write_path_candidates"]
        smaller = {"eligible": 1, "checked": 1, "supported": 1, "credited": 1,
                   "blocked": 0, "unchecked": 0, "unchecked_by_reason": {},
                   "outcomes": {f"{ROLE}:write:request-time:candidate-outside-scope": 1}}
        self.assertEqual(compared_paths["dominant"]["smaller_pairs"], smaller)
        self.assertEqual(journey["etw_webview_write_credit"], {
            "status": "compared", "credited_paths": {"permitted": 1, "outside-scope": 2, "protected": 1},
            "remaining_path_gaps": 6, "smaller_pairs": smaller,
        })
        self.assertEqual(journey["etw_unresolved_mutations"], {
            f"{ROLE}:write:path-missing": 6, f"{ROLE}:write:completion-missing": 1,
            f"{ROLE}:rename:path-missing": 1,
        })
        self.assertEqual(journey["file_violations"][f"protected:{ROLE}:write"], 2)
        self.assertEqual(journey["file_violations"][f"outside-scope:{ROLE}:write"], 5)
        self.assertEqual(outside_paths.writer_summary(), [
            {"role": ROLE, "operation": "rename", "path_categories": ["generated-protected"],
             "writer": "webview2", "count": 1},
            {"role": ROLE, "operation": "write", "path_categories": ["generated-outside"],
             "writer": "webview2", "count": 3},
            {"role": ROLE, "operation": "write", "path_categories": ["generated-protected"],
             "writer": "webview2", "count": 2},
        ])
        self.assertEqual(journey["file_events"][f"{ROLE}:write"], 6)
        self.assertEqual(journey["unexpected_connections"], [unexpected])
        self.assertEqual((journey["filesystem"], journey["network"], journey["coverage"]), ("FAIL", "FAIL", "BLOCKED"))
        self.assertEqual(loss["etw_webview_write_credit"], {
            "status": "blocked-etw-loss", "credited_paths": {}, "remaining_path_gaps": 10,
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
