"""G2.19 passive same-capture write pairing: redacted source-only tests."""
from dataclasses import replace
import json
from pathlib import Path
import time
import unittest

from qa.p4_research.n12_fileio_pair_contract import (
    PrivateWriterEpoch, index_private_kernel_file_events,
    passive_webview_write_coverage,
)

START, END = 100, 1000
WEB = PrivateWriterEpoch(300, 110, 900, "webview")
NET = PrivateWriterEpoch(400, 115, 901, "webview-network")


def event(kind, tick, *, pid=300, irp=7, obj=21, key=22, tid=31,
          status=None, private_path=None):
    data = {"FileObject": obj, "FileKey": key, "IssuingThreadId": tid}
    if irp is not None:
        data["Irp"] = irp
    if status is not None:
        data["Status"] = status
    if private_path is not None:
        data["FileName"] = private_path
    return {"id": kind, "ticks": tick, "pid": pid,
            "lifecycle": False, "data": data}


def run(rows, epochs=(WEB,)):
    idx = index_private_kernel_file_events(rows, start_tick=START, end_tick=END)
    return passive_webview_write_coverage(index=idx, writer_epochs=epochs)


class PassiveFileioCoverageTests(unittest.TestCase):
    def test_unique_success_completion_is_only_shape_not_writer_or_path(self):
        r = run([
            event(16, 200, private_path=r"C:\Owner\Important\private.txt"),
            event(24, 250, pid=4, status=0, private_path=r"C:\Owner\Important\private.txt"),
        ])
        self.assertEqual(r["status"], "SHAPES_REVIEWABLE_ONLY")
        self.assertEqual(r["counts_by_claimed_role"]["webview"]["write_requests"], 1)
        self.assertEqual(r["counts_by_claimed_role"]["webview"]["pair_shape_only"], 1)
        self.assertEqual(r["original_webview_writer_file_handle"], "NOT_VERIFIED")
        self.assertEqual(r["kernel_fileobject_handle_join"], "NOT_ESTABLISHED")
        self.assertEqual(r["request_time_physical_destination"], "NOT_VERIFIED")
        self.assertEqual(r["native_N12_acceptance"], "NOT_EVALUATED")
        self.assertNotIn("300", json.dumps(r))
        self.assertNotIn("private.txt", json.dumps(r))

    def test_missing_irp_write_is_counted_as_gap_not_disappeared(self):
        r = run([event(16, 200, irp=None)])
        role = r["counts_by_claimed_role"]["webview"]
        self.assertEqual((role["write_requests"], role["pair_shape_only"]), (1, 0))
        self.assertEqual(role["missing_or_conflicting_identity"], 1)
        self.assertEqual(r["blocker"], "UNRESOLVED_FILEIO_REQUEST_SHAPES")

    def test_zero_irp_and_missing_fileobject_cannot_count(self):
        for key, value in (("irp", 0), ("obj", 0), ("key", None), ("tid", None)):
            kw = {key: value}
            r = run([event(16, 200, **kw)])
            self.assertEqual(r["counts_by_claimed_role"]["webview"][
                "missing_or_conflicting_identity"], 1)

    def test_reused_irp_extra_write_or_unknown_event_blocks(self):
        for contaminant in (event(16, 240, irp=7),
                            event(12, 150, irp=7),
                            event(255, 275, irp=7)):
            r = run([event(16, 200), event(24, 250, pid=4, status=0),
                     contaminant])
            self.assertEqual(r["status"], "BLOCKED")
            self.assertEqual(r["counts_by_claimed_role"]["webview"][
                "missing_or_ambiguous_irp"], 1 + (contaminant["id"] == 16))

    def test_completion_missing_late_or_same_tick_never_counts(self):
        for writes in (
            [event(16, 200)],
            [event(16, 200), event(24, 200, pid=4, status=0)],
            [event(16, 200), event(24, 900, pid=4, status=0)],
            [event(16, 200), event(24, 950, pid=4, status=0)],
        ):
            r = run(writes)
            self.assertEqual(r["counts_by_claimed_role"]["webview"][
                "missing_or_ambiguous_irp"], 1)

    def test_unsuccessful_or_unknown_status_never_counts(self):
        for status in (None, 5, 0xC0000022):
            r = run([event(16, 200), event(24, 250, pid=4, status=status)])
            self.assertEqual(r["counts_by_claimed_role"]["webview"][
                "unsuccessful_or_unknown_completion"], 1)

    def test_conflicting_completion_object_or_filekey_never_counts(self):
        for field, value in (("obj", 999), ("key", 999)):
            r = run([event(16, 200), event(24, 250, pid=4, status=0, **{field: value})])
            self.assertEqual(r["counts_by_claimed_role"]["webview"][
                "missing_or_conflicting_identity"], 1)

    def test_completion_may_omit_optional_object_fields_without_proving_them(self):
        r = run([event(16, 200), event(24, 250, pid=4, status=0, obj=None, key=None)])
        self.assertEqual(r["counts_by_claimed_role"]["webview"]["pair_shape_only"], 1)
        self.assertEqual(r["kernel_fileobject_handle_join"], "NOT_ESTABLISHED")

    def test_writer_lifetime_is_caller_supplied_only(self):
        r = run([event(16, 100), event(24, 250, pid=4, status=0)])
        self.assertEqual(r["counts_by_claimed_role"]["webview"][
            "outside_claimed_process_lifetime"], 1)
        self.assertEqual(r["input_process_roles_and_lifetimes"], "NOT_AUTHENTICATED")

    def test_duplicate_pid_epoch_or_role_is_blocked(self):
        r = run([event(16, 200), event(24, 250, pid=4, status=0)],
                epochs=(WEB, replace(WEB, role="webview-network")))
        self.assertEqual(r["blocker"], "PID_REUSE_OR_ROLE_AMBIGUOUS")
        self.assertEqual(r["counts_by_claimed_role"]["webview"]["write_requests"], 0)

    def test_invalid_source_epoch_and_lossy_index_block(self):
        for epochs in ((), [WEB], (replace(WEB, pid=True),),
                       (replace(WEB, role="browser"),),
                       (replace(WEB, birth_tick=1000),),
                       tuple(replace(WEB, pid=5000+i) for i in range(97))):
            with self.subTest(kind=str(type(epochs))):
                r = run([event(16, 200)], epochs=epochs)
                self.assertEqual(r["blocker"], "WRITER_EPOCH_ENVELOPE_INVALID")
        bad = run([{"id": 16, "pid": 300, "ticks": "bad", "data": {}}])
        self.assertEqual(bad["blocker"], "ETW_INDEX_UNVERIFIED")

    def test_roles_are_separate_but_not_authenticated(self):
        r = run([event(16, 200), event(24, 250, pid=4, status=0),
                 event(16, 300, pid=400, irp=9, obj=70, key=80),
                 event(24, 350, pid=4, irp=9, obj=70, key=80, status=0)],
                epochs=(WEB, NET))
        self.assertEqual(r["status"], "SHAPES_REVIEWABLE_ONLY")
        self.assertEqual(r["counts_by_claimed_role"]["webview"]["pair_shape_only"], 1)
        self.assertEqual(r["counts_by_claimed_role"]["webview-network"]["pair_shape_only"], 1)
        self.assertEqual(r["etw_capture_loss_and_completeness"], "NOT_VERIFIED")

    def test_missing_selected_writer_events_cannot_appear_clean(self):
        r = run([event(16, 200, pid=111)], epochs=(WEB,))
        self.assertEqual(r["blocker"], "NO_SELECTED_WRITE_REQUESTS")

    def test_large_single_object_burst_uses_linear_private_index(self):
        # Dense same-object traffic seen historically. Group by IRP only;
        # repeated requests must not be interpreted as path proof.
        n = 15000
        rows = []
        for i in range(n):
            rows.append(event(16, 150 + i // 1000, irp=1000+i))
            rows.append(event(24, 200 + i // 1000, irp=1000+i,
                              pid=4, status=0))
        idx = index_private_kernel_file_events(rows, start_tick=START, end_tick=END)
        r = passive_webview_write_coverage(index=idx, writer_epochs=(WEB,))
        self.assertEqual(r["counts_by_claimed_role"]["webview"]["pair_shape_only"], n)
        self.assertEqual(r["status"], "SHAPES_REVIEWABLE_ONLY")

    def test_all_receipts_fixed_and_no_path_query_or_windows_call(self):
        source = (Path(__file__).resolve().parents[1] /
                  "qa/p4_research/n12_fileio_pair_contract.py").read_text(
                      encoding="utf-8")
        self.assertNotIn("DuplicateHandle(", source)
        self.assertNotIn("GetFinalPathNameByHandle(", source)
        self.assertNotIn("OpenProcess(", source)
        r = run([event(16, 200, private_path=r"C:\Private\User\abc.dat")])
        self.assertNotIn("abc.dat", json.dumps(r))
        self.assertFalse(r["owner_native_execution_authorized"])


if __name__ == "__main__":
    unittest.main()
