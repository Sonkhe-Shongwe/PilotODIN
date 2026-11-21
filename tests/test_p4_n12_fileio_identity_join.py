"""Adversarial ETW writer/known-path lifetime regressions; source-only data."""
import copy
import json
import unittest

from qa.p4_native.n12_etw_correlate import correlate_requests
from qa.p4_research import n12_fileio_identity_join as join


def synthetic_candidate():
    return {
        "scope": join.SCOPE,
        "source_sha": "a" * 40,
        "capture": {"start_ticks": 90, "end_ticks": 230,
                    "digest_verified": True, "zero_etw_loss": True,
                    "positive_transient_write_observed": True},
        "process": {"pid": 7, "birth_ticks": 100, "exit_ticks": 200,
                    "etw_birth_ticks": 100, "etw_exit_ticks": 200,
                    "original_handle_birth_ticks": 100, "original_handle_exit_ticks": 200,
                    "original_handle_retained": True, "exact_image_verified": True,
                    "unique_etw_sequence": True, "parent_sequence_verified": True,
                    "sysmon_guid_verified": True},
        "write": {"pid": 7, "birth_ticks": 100, "request_ticks": 140,
                  "completion_ticks": 150, "request_event_id": 16, "completion_event_id": 24,
                  "irp": 1002, "completion_irp": 1002,
                  "file_object": 400, "file_key": 40, "thread_owner_verified": True,
                  "unique_completion": True, "completion_identity_verified": True,
                  "completion_success": True, "path_evidence": "same-original-open-handle",
                  "name_epoch_unchanged": True, "destination_scope": "permitted"},
    }


def known_path_trace(*, early_exit=False, pid_reuse=False):
    """Only generated ETW IDs and a fake path. No native WebView2 process."""
    def row(kind, ticks, data, *, lifecycle=False, pid=7):
        return {"id": kind, "ticks": ticks, "data": data,
                "lifecycle": lifecycle, "pid": pid}
    file_path = r"C:\qa\permitted\synthetic.bin"
    rows = [
        row(1, 100, {"ProcessID": 7}, lifecycle=True),
        row(3, 110, {"ProcessID": 7, "ThreadID": 71}, lifecycle=True),
        row(12, 120, {"FileObject": 400, "Irp": 1001, "FileName": file_path}),
        row(24, 130, {"Irp": 1001, "Status": 0, "ExtraInformation": 1}, pid=0),
        row(16, 140, {"FileObject": 400, "FileKey": 40,
                      "Irp": 1002, "IssuingThreadId": 71}),
    ]
    if early_exit or pid_reuse:
        rows.append(row(2, 145, {"ProcessID": 7}, lifecycle=True, pid=0))
    if pid_reuse:
        rows.append(row(1, 147, {"ProcessID": 7}, lifecycle=True, pid=0))
    rows.append(row(24, 150, {"Irp": 1002, "Status": 0}, pid=0))
    if not early_exit and not pid_reuse:
        rows.append(row(2, 200, {"ProcessID": 7}, lifecycle=True, pid=0))
    if pid_reuse:
        rows.append(row(2, 210, {"ProcessID": 7}, lifecycle=True, pid=0))
    return rows, file_path


class FileIOJoinSourceTests(unittest.TestCase):
    def test_source_contract_names_actual_reducers_not_runtime_truth(self):
        result = join.source_contract()
        self.assertEqual(result["status"], "SOURCE_MATCH", result["issues"])
        self.assertEqual(result["actual_original_webview_handle_evidence"], "NOT_COLLECTED")
        self.assertFalse(result["known-path-completion-lifetime_proven"])
        self.assertEqual(result["native_N12_acceptance"], "NOT_EVALUATED")

    def test_synthetic_exact_join_is_reviewable_but_never_native_pass(self):
        result = join.review_candidate(synthetic_candidate())
        self.assertEqual(result["join_status"], "REVIEWABLE_ONLY", result["issues"])
        self.assertEqual(result["destination_scope"], "permitted")
        self.assertFalse(result["process_to_write_provenance_verified"])
        self.assertFalse(result["fileio_capture_completeness_certified"])
        self.assertEqual(result["native_N12_acceptance"], "NOT_EVALUATED")
        self.assertEqual(result["file_mutation_acceptance"], "NOT_EVALUATED")
        self.assertFalse(result["owner_native_execution_authorized"])

    def test_prohibited_path_is_still_reviewable_as_violation_not_permission(self):
        receipt = synthetic_candidate()
        receipt["write"]["destination_scope"] = "outside-scope"
        result = join.review_candidate(receipt)
        self.assertEqual(result["join_status"], "REVIEWABLE_ONLY")
        self.assertEqual(result["destination_scope"], "outside-scope")
        self.assertEqual(result["file_mutation_acceptance"], "NOT_EVALUATED")

    def test_early_exit_pid_reuse_and_tied_time_fail_closed(self):
        for change in (
            lambda r: r["process"].update(exit_ticks=145, etw_exit_ticks=145,
                                           original_handle_exit_ticks=145),
            lambda r: r["write"].update(birth_ticks=147),
            lambda r: r["write"].update(completion_ticks=200),
            lambda r: r["write"].update(request_ticks=100),
            lambda r: r["process"].update(etw_birth_ticks=102),
            lambda r: r["process"].update(original_handle_exit_ticks=201),
        ):
            with self.subTest(change=str(change.__code__.co_firstlineno)):
                row = synthetic_candidate()
                change(row)
                self.assertEqual(join.review_candidate(row)["join_status"], "BLOCKED")

    def test_irp_thread_path_epoch_and_completion_identity_are_independent(self):
        for category, alteration in (
            ("irp", {"completion_irp": 42}),
            ("event", {"completion_event_id": 16}),
            ("thread", {"thread_owner_verified": False}),
            ("completion", {"completion_identity_verified": False}),
            ("duplicate", {"unique_completion": False}),
            ("name", {"name_epoch_unchanged": False}),
            ("rundown-only", {"path_evidence": "stop-time-rundown-only"}),
            ("no-path", {"path_evidence": "NOT_COLLECTED"}),
            ("unmapped", {"destination_scope": "unknown"}),
        ):
            with self.subTest(category=category):
                row = synthetic_candidate()
                row["write"].update(alteration)
                report = join.review_candidate(row)
                self.assertEqual(report["join_status"], "BLOCKED")
                self.assertEqual(report["destination_scope"], "UNVERIFIED")

    def test_capture_loss_original_handles_and_positive_controls_all_required(self):
        edits = (
            ("capture", "zero_etw_loss"),
            ("capture", "positive_transient_write_observed"),
            ("capture", "digest_verified"),
            ("process", "original_handle_retained"),
            ("process", "exact_image_verified"),
            ("process", "parent_sequence_verified"),
            ("process", "sysmon_guid_verified"),
            ("process", "unique_etw_sequence"),
        )
        for category, key in edits:
            with self.subTest(field=key):
                row = synthetic_candidate()
                row[category][key] = False
                self.assertEqual(join.review_candidate(row)["join_status"], "BLOCKED")

    def test_unknown_fields_boolean_pids_and_private_paths_do_not_appear_in_report(self):
        rows = [
            None, {}, [], {"scope": join.SCOPE, "source_sha": "b" * 40},
            {**synthetic_candidate(), "private-file": "C:\\owner\\private.txt"},
        ]
        for row in rows:
            result = join.review_candidate(row)
            self.assertEqual(result["join_status"], "BLOCKED")
            self.assertNotIn("private", json.dumps(result))
        row = synthetic_candidate()
        row["process"]["pid"] = True
        self.assertEqual(join.review_candidate(row)["issues"], ["numeric-identity-invalid"])

    def test_actual_strict_known_path_reducer_can_emit_after_process_exit(self):
        rows, path = known_path_trace(early_exit=True)
        emitted = []
        unresolved = correlate_requests(
            rows, lambda name: name or None,
            lambda pid, birth, ticks: ("webview-network", "synthetic-writer")
            if birth == 100 else ("unattributed", None),
            lambda path: False, lambda *row: emitted.append(row),
            strict=True, initial_process_births={},
        )
        # Preserve the existing reducer, do not reclassify its original result:
        # a known opened path can be emitted after a request owner has exited.
        self.assertEqual(unresolved, {})
        self.assertIn(("webview-network", "synthetic-writer", "write",
                       path, None, 140, 150, True), emitted)
        fixture = synthetic_candidate()
        fixture["process"].update(exit_ticks=145, etw_exit_ticks=145,
                                  original_handle_exit_ticks=145)
        report = join.review_candidate(fixture)
        self.assertIn("fileio-completion-outside-original-process-lifetime", report["issues"])
        self.assertEqual(report["join_status"], "BLOCKED")

    def test_pid_reuse_before_completion_cannot_supply_same_original_process(self):
        rows, path = known_path_trace(pid_reuse=True)
        emitted = []
        unresolved = correlate_requests(
            rows, lambda name: name or None,
            lambda pid, birth, ticks: ("webview-network", "synthetic-writer"),
            lambda path: False, lambda *row: emitted.append(row),
            strict=True,
        )
        self.assertEqual(unresolved, {})
        self.assertIn(("webview-network", "synthetic-writer", "write",
                       path, None, 140, 150, True), emitted)
        fixture = synthetic_candidate()
        fixture["process"].update(exit_ticks=145, etw_exit_ticks=145,
                                  original_handle_exit_ticks=145)
        self.assertEqual(join.review_candidate(fixture)["join_status"], "BLOCKED")


def generated_original_windows_join_fixture():
    """Generated cross-provider records; not an actual Windows capture."""
    root = r"C:\qa"
    path = root + r"\file-lifetime.bin"
    handle = {"pid": 7001, "birth_ticks": 100, "exit_ticks": 190}
    capture = {
        "file_lifetime": {"pid": 7001, "path": path, "size": 97,
                          "start": 90, "end": 200, "two_handles": True,
                          "original_handle": handle},
        "counters": {"events_lost": 0, "log_buffers_lost": 0,
                     "realtime_buffers_lost": 0, "buffers_written": 2},
        "volume_devices": {"C:": r"\Device\HarddiskVolume3"},
    }
    def record(kind, ticks, data, *, pid=7001, lifecycle=False):
        return {"id": kind, "ticks": ticks, "data": data,
                "pid": pid, "lifecycle": lifecycle}
    # The ETW payload creation/exit values are FILETIME UTC strings. Real
    # Windows originals must independently match the retained HANDLE.
    # These generated strings map to known integers on a real date timeline;
    # shift all events to that date rather than fabricating a 1601 timestamp.
    from datetime import datetime, timezone
    from qa.p4_native import n12_trace as trace
    base = trace.utc_ticks(datetime(2026, 11, 21, tzinfo=timezone.utc))
    start, end = base + 100, base + 190
    capture["file_lifetime"]["start"] = base + 90
    capture["file_lifetime"]["end"] = base + 200
    handle.update(birth_ticks=start, exit_ticks=end)
    # Existing etw_payload_ticks returns UTC nanosecond/100ns based integers.
    def instant(ticks):
        dt = datetime(2026, 11, 21, tzinfo=timezone.utc)
        return dt.strftime("%Y-%m-%dT%H:%M:%S") + f".{ticks-base:07d}Z"
    etw = [
        record(1, base + 101, {"ProcessID": "7001", "ProcessSequenceNumber": "81",
                              "CreateTime": instant(start), "ParentProcessID": "7000"}, lifecycle=True, pid=0),
        record(12, base + 120, {"Irp": 33, "FileObject": 400, "FileName": path}),
        record(24, base + 128, {"Irp": 33, "Status": 0}, pid=0),
        record(16, base + 140, {"Irp": 35, "FileObject": 400,
                                "FileKey": 40, "IOSize": 97}),
        record(24, base + 150, {"Irp": 35, "Status": 0}, pid=0),
        record(14, base + 160, {"FileObject": 400}),
        record(2, base + 191, {"ProcessID": "7001", "ProcessSequenceNumber": "81",
                              "CreateTime": instant(start), "ExitTime": instant(end)}, lifecycle=True, pid=0),
    ]
    return capture, etw


class GeneratedOriginalHandleEtwJoinTests(unittest.TestCase):
    def test_generator_corroborates_handle_lifetime_etw_process_and_fileio(self):
        capture, rows = generated_original_windows_join_fixture()
        result = join.generated_original_handle_fileio_join(capture, rows)
        self.assertEqual(result["status"], "GENERATED_JOIN_CORROBORATED", result["issues"])
        self.assertEqual(result["native_N12_acceptance"], "NOT_EVALUATED")
        self.assertEqual(result["sysmon_original_webview_identity"], "NOT_COLLECTED")
        self.assertNotIn("7001", json.dumps(result))
        self.assertNotIn(r"C:\qa", json.dumps(result))

    def test_rejects_actor_reuse_late_completion_missing_status_and_path_reuse(self):
        for label, modify in (
            ("late-completion", lambda c, e: c["file_lifetime"]["original_handle"].update(exit_ticks=e[4]["ticks"]-1)),
            ("reuse", lambda c, e: e.append({**e[0], "ticks": e[3]["ticks"]+2,
                                            "data": {**e[0]["data"], "ProcessSequenceNumber": "82"}})),
            ("missing-open", lambda c, e: e.pop(1)),
            ("wrong-object", lambda c, e: e[3]["data"].update(FileObject=999)),
            ("lost-events", lambda c, e: c["counters"].update(events_lost=1)),
            ("bad-completion", lambda c, e: e[4]["data"].update(Status=0xC0000022)),
            ("reused-irp", lambda c, e: e.insert(4, {**e[3], "ticks": e[3]["ticks"]+1})),
            ("missing-sequence", lambda c, e: e[0]["data"].pop("ProcessSequenceNumber")),
            ("wrong-file", lambda c, e: e[1]["data"].update(FileName=r"C:\elsewhere\fake.bin")),
            ("name-reused", lambda c, e: e.insert(3, {
                "id": 14, "ticks": e[2]["ticks"]+1, "pid": 7001,
                "lifecycle": False, "data": {"FileObject": 400}})),
        ):
            with self.subTest(label=label):
                capture, rows = generated_original_windows_join_fixture()
                modify(capture, rows)
                report = join.generated_original_handle_fileio_join(capture, rows)
                self.assertEqual(report["status"], "BLOCKED", (label, report))

    def test_rejects_missing_original_process_and_boolean_pid(self):
        for mutate in (
            lambda c, e: c["file_lifetime"].pop("original_handle"),
            lambda c, e: c["file_lifetime"]["original_handle"].update(pid=True),
        ):
            capture, rows = generated_original_windows_join_fixture()
            mutate(capture, rows)
            self.assertEqual(join.generated_original_handle_fileio_join(capture, rows)["status"],
                             "BLOCKED")


if __name__ == "__main__":
    unittest.main()
