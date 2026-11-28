"""R02.5 G1 source-only seam: a candidate must never clear strict FileIO gaps.

All identities and paths in this test are synthetic. No native collector, app,
original file handle or protected owner data is involved.
"""
import unittest
from collections import Counter

from qa.p4_native.n12_etw_correlate import correlate_requests
from qa.p4_research.n12_no_cdp_fileio_review import _fixed_report
from qa.p4_research.n12_fileio_pair_contract import (
    PrivateOriginalFilePair, PrivateWriteIdentity, PrivateWriterSpan,
    index_private_kernel_file_events, review_private_write_pair,
)
from qa.p4_research.n12_physical_destination import Corroboration, PrivateHandlePath


PATH = r"C:\QA\UDF\Network\synthetic.tmp"
ROOT = PrivateHandlePath(r"C:\QA\UDF", 123, "permitted_root_handle")
TARGET = PrivateHandlePath(PATH, 123, "original_file_handle")
CLAIMED = Corroboration(True, True, True, True, True, True, True, True, True)


def fixture():
    # Opening parent PID 100 and writing network PID 200 use the same synthetic
    # FileObject. The parent and child do not share PID-keyed opened state.
    return [
        {"id": 12, "pid": 100, "ticks": 120, "data": {
            "FileObject": 700, "FileKey": 800, "Irp": 6, "FileName": PATH}},
        {"id": 24, "pid": 4, "ticks": 130, "data": {
            "Irp": 6, "Status": 0, "ExtraInformation": 1}},
        {"id": 16, "pid": 200, "ticks": 300, "data": {
            "Irp": 9, "FileObject": 700, "FileKey": 800,
            "IssuingThreadId": 220}},
        {"id": 24, "pid": 4, "ticks": 400, "data": {
            "Irp": 9, "Status": 0}},
    ]


def private_candidate(events):
    index = index_private_kernel_file_events(events, start_tick=100, end_tick=1000)
    return review_private_write_pair(
        index=index,
        write=PrivateWriteIdentity(9, 700, 800, 200, 220, 300, 400),
        writer=PrivateWriterSpan(200, 110, 900, 220, 140, 850),
        original_pair=PrivateOriginalFilePair(700, 800, 200),
        write_target=TARGET, permitted_roots=(ROOT,),
        request_time_path=PATH, corroboration=CLAIMED,
    )


class StrictReducerIsolationTests(unittest.TestCase):
    def test_candidate_does_not_resolve_the_original_strict_cross_process_gap(self):
        events = fixture()
        synthetic_claim = private_candidate(events)
        self.assertEqual(synthetic_claim.status, "CONTAINED_CANDIDATE_ONLY")
        self.assertEqual(synthetic_claim.public_receipt()["file_mutation_acceptance"],
                         "NOT_EVALUATED")

        emitted = []
        def actor(pid, birth, _ticks):
            if pid == 100:
                return ("webview", "synthetic-parent")
            if pid == 200:
                return ("webview-network", "synthetic-child")
            return ("unattributed", None)

        unresolved = correlate_requests(
            events, lambda value: value or None, actor,
            lambda _path: False, lambda *args: emitted.append(args),
            strict=True, initial_process_births={100: 110, 200: 110},
        )
        self.assertGreaterEqual(unresolved.get("webview-network:write:path-missing", 0), 1)
        self.assertFalse(any(row[0] == "webview-network" and row[2] == "write"
                             and row[3] == PATH and row[-1] is True for row in emitted))

    def test_prohibited_candidate_does_not_change_original_report(self):
        outside = PrivateHandlePath(r"C:\Windows\Temp\bad.tmp", 123, "original_file_handle")
        events = fixture()
        index = index_private_kernel_file_events(events, start_tick=100, end_tick=1000)
        result = review_private_write_pair(
            index=index, write=PrivateWriteIdentity(9, 700, 800, 200, 220, 300, 400),
            writer=PrivateWriterSpan(200, 110, 900, 220, 140, 850),
            original_pair=PrivateOriginalFilePair(700, 800, 200),
            write_target=outside, permitted_roots=(ROOT,),
            request_time_path=outside.final_path, corroboration=CLAIMED,
        )
        self.assertEqual(result.status, "OUTSIDE_CANDIDATE_ONLY")
        strict = _fixed_report(blocker="observed-prohibited-fileio-operations",
                               violations=Counter({"outside-scope:webview-network:write": 1}),
                               gaps=Counter({"webview-network:write:path-missing": 1}))
        self.assertEqual(strict["status"], "BLOCKED")
        self.assertEqual(strict["observed_prohibited_operations"], 1)
        self.assertEqual(strict["missing_mutation_path_credits"], 1)
        self.assertEqual(strict["native_N12_acceptance"], "NOT_EVALUATED")
        self.assertEqual(strict["file_mutation_acceptance"], "NOT_EVALUATED")

    def test_unknown_event_and_reused_irp_block_private_candidate(self):
        events = fixture()
        events.insert(3, {"id": 99, "pid": 100, "ticks": 350, "data": {
            "FileObject": 700, "FileKey": 800, "Irp": 777}})
        self.assertEqual(private_candidate(events).status, "BLOCKED")
        events = fixture()
        events.insert(3, {"id": 16, "pid": 200, "ticks": 350, "data": {
            "FileObject": 700, "FileKey": 800, "Irp": 9, "IssuingThreadId": 220}})
        self.assertEqual(private_candidate(events).status, "BLOCKED")


if __name__ == "__main__":
    unittest.main()
