"""Synthetic only: no original WebView2 file handle or actual ETW capture."""
import unittest
from dataclasses import replace

_DEFAULT = object()

from qa.p4_research.n12_fileio_pair_contract import (
    PrivateOriginalFilePair, PrivateWriteIdentity, PrivateWriterSpan,
    index_private_kernel_file_events, review_private_write_pair,
)
from qa.p4_research.n12_physical_destination import Corroboration, PrivateHandlePath

FULL = Corroboration(True, True, True, True, True, True, True, True, True)
ROOT = PrivateHandlePath(r"C:\QA\UDF", 123, "permitted_root_handle")
TARGET = PrivateHandlePath(r"C:\QA\UDF\Network\x.tmp", 123, "original_file_handle")
# Browser parent creates and then a distinct network child writes through an
# independently asserted shared FileObject. The real provenance is untested.
PARENT = {"id": 12, "pid": 100, "ticks": 120, "data": {
    "FileObject": 700, "FileKey": 800, "Irp": 6, "FileName": TARGET.final_path,
}}
REQUEST = {"id": 16, "pid": 200, "ticks": 300, "data": {
    "Irp": 9, "FileObject": 700, "FileKey": 800, "IssuingThreadId": 220,
}}
COMPLETE = {"id": 24, "pid": 4, "ticks": 400, "data": {
    "Irp": 9, "FileObject": 700, "FileKey": 800, "Status": 0,
}}
WRITER = PrivateWriterSpan(200, 110, 900, 220, 140, 850)
ORIGINAL = PrivateOriginalFilePair(700, 800, 200)
WRITE = PrivateWriteIdentity(9, 700, 800, 200, 220, 300, 400)


def record(kind, ticks, *, obj=700, key=800, irp=70, pid=100, status=None, tid=220):
    data = {"FileObject": obj, "FileKey": key, "Irp": irp, "IssuingThreadId": tid}
    if status is not None:
        data["Status"] = status
    return {"id": kind, "pid": pid, "ticks": ticks, "data": data}


def evaluate(*, events=_DEFAULT, writer=WRITER, original=ORIGINAL, write=WRITE,
             path=TARGET, proofs=FULL, roots=(ROOT,), request_path=None,
             start=100, end=1000):
    if events is _DEFAULT:
        events = [PARENT, REQUEST, COMPLETE]
    index = index_private_kernel_file_events(events, start_tick=start, end_tick=end)
    return review_private_write_pair(
        index=index, write=write, writer=writer, original_pair=original,
        write_target=path, permitted_roots=roots,
        request_time_path=path.final_path if request_path is None else request_path,
        corroboration=proofs,
    )


class PrivateFileIoPairContractTests(unittest.TestCase):
    def test_cross_process_opener_is_not_writer_identity(self):
        result = evaluate()
        self.assertEqual(result.status, "CONTAINED_CANDIDATE_ONLY")
        self.assertEqual(result.public_receipt()["native_N12_acceptance"], "NOT_EVALUATED")

    def test_outside_root_remains_outside_candidate(self):
        outside = PrivateHandlePath(r"C:\Windows\Temp\x.tmp", 123, "original_file_handle")
        self.assertEqual(evaluate(path=outside).status, "OUTSIDE_CANDIDATE_ONLY")

    def test_wrong_writer_pid_blocks(self):
        self.assertEqual(evaluate(write=replace(WRITE, writer_pid=100)).status, "BLOCKED")

    def test_wrong_independent_thread_blocks(self):
        self.assertEqual(evaluate(writer=replace(WRITER, issuing_tid=221)).status, "BLOCKED")

    def test_claimed_writer_and_request_header_mismatch_blocks(self):
        # Two forged witness records can agree with one another while the
        # actual indexed ETW request still identifies a different issuer.
        self.assertEqual(evaluate(
            writer=replace(WRITER, pid=100),
            write=replace(WRITE, writer_pid=100),
        ).status, "BLOCKED")

    def test_claimed_thread_and_request_thread_mismatch_blocks(self):
        self.assertEqual(evaluate(
            writer=replace(WRITER, issuing_tid=221),
            write=replace(WRITE, issuing_tid=221),
        ).status, "BLOCKED")

    def test_unverified_writer_process_birth_blocks(self):
        self.assertEqual(evaluate(writer=replace(WRITER, birth_tick=300)).status, "BLOCKED")

    def test_early_writer_exit_blocks(self):
        self.assertEqual(evaluate(writer=replace(WRITER, exit_tick=390)).status, "BLOCKED")

    def test_unverified_original_object_blocks(self):
        self.assertEqual(evaluate(original=replace(ORIGINAL, file_object=701)).status, "BLOCKED")

    def test_unverified_original_key_blocks(self):
        self.assertEqual(evaluate(original=replace(ORIGINAL, file_key=801)).status, "BLOCKED")

    def test_original_handle_observed_after_exit_blocks(self):
        self.assertEqual(evaluate(original=replace(ORIGINAL, handle_observed_tick=950)).status, "BLOCKED")

    def test_missing_request_blocks(self):
        self.assertEqual(evaluate(events=[PARENT, COMPLETE]).status, "BLOCKED")

    def test_missing_completion_blocks(self):
        self.assertEqual(evaluate(events=[PARENT, REQUEST]).status, "BLOCKED")

    def test_duplicate_request_blocks(self):
        self.assertEqual(evaluate(events=[PARENT, REQUEST, dict(REQUEST), COMPLETE]).status, "BLOCKED")

    def test_intervening_irp_reuse_blocks(self):
        self.assertEqual(evaluate(events=[PARENT, REQUEST, record(16, 350, irp=9), COMPLETE]).status, "BLOCKED")

    def test_completion_identity_conflict_blocks(self):
        changed = {**COMPLETE, "data": {**COMPLETE["data"], "FileKey": 801}}
        self.assertEqual(evaluate(events=[PARENT, REQUEST, changed]).status, "BLOCKED")

    def test_completion_fileobject_mismatch_blocks(self):
        changed = {**COMPLETE, "data": {**COMPLETE["data"], "FileObject": 701}}
        self.assertEqual(evaluate(events=[PARENT, REQUEST, changed]).status, "BLOCKED")

    def test_completed_write_requires_success_status(self):
        for status in (None, 1, 0xC0000001, True, "bad"):
            with self.subTest(status=status):
                event = {**COMPLETE, "data": {**COMPLETE["data"], "Status": status}}
                self.assertEqual(evaluate(events=[PARENT, REQUEST, event]).status, "BLOCKED")

    def test_completion_same_timestamp_blocks(self):
        event = {**COMPLETE, "ticks": 300}
        self.assertEqual(evaluate(events=[PARENT, REQUEST, event], write=replace(WRITE, completion_tick=300)).status, "BLOCKED")

    def test_namecreate_or_namedelete_during_handle_epoch_blocks(self):
        for event_id in (10, 11):
            with self.subTest(event_id=event_id):
                self.assertEqual(evaluate(events=[PARENT, REQUEST, COMPLETE, record(event_id, 350)]).status, "BLOCKED")

    def test_close_rename_setinfo_and_reparse_during_epoch_block(self):
        for event_id in (12, 13, 14, 17, 18, 19, 23, 26, 27, 28, 29):
            with self.subTest(event_id=event_id):
                self.assertEqual(evaluate(events=[PARENT, REQUEST, COMPLETE, record(event_id, 250)]).status, "BLOCKED")

    def test_close_at_same_timestamp_as_write_blocks(self):
        self.assertEqual(evaluate(events=[PARENT, REQUEST, COMPLETE, record(14, 300)]).status, "BLOCKED")

    def test_fileobject_reuse_on_different_filekey_blocks(self):
        self.assertEqual(evaluate(events=[PARENT, REQUEST, COMPLETE, record(16, 250, key=801)]).status, "BLOCKED")

    def test_filekey_reused_with_different_fileobject_blocks(self):
        self.assertEqual(evaluate(events=[PARENT, REQUEST, COMPLETE, record(16, 250, obj=701)]).status, "BLOCKED")

    def test_unrelated_file_mutation_does_not_shadow_join(self):
        self.assertEqual(evaluate(events=[PARENT, REQUEST, COMPLETE, record(14, 350, obj=555, key=666)]).status,
                         "CONTAINED_CANDIDATE_ONLY")

    def test_other_process_completion_context_is_allowed(self):
        self.assertEqual(evaluate().status, "CONTAINED_CANDIDATE_ONLY")

    def test_missing_independent_proof_blocks(self):
        for key in vars(FULL):
            with self.subTest(key=key):
                self.assertEqual(evaluate(proofs=replace(FULL, **{key: False})).status, "BLOCKED")

    def test_request_and_handle_final_path_disagreement_blocks(self):
        self.assertEqual(evaluate(request_path=r"C:\Windows\Temp\x.tmp").status, "BLOCKED")

    def test_unverified_original_handle_provenance_blocks(self):
        bad = PrivateHandlePath(TARGET.final_path, 123, "reopened_by_name")
        self.assertEqual(evaluate(path=bad).status, "BLOCKED")

    def test_malformed_event_envelopes_block_without_exceptions(self):
        for events in (None, {}, ["private path"], [PARENT, REQUEST, {**COMPLETE, "data": []}],
                       [PARENT, REQUEST, {**COMPLETE, "ticks": "invalid"}]):
            with self.subTest(case=str(type(events))):
                self.assertEqual(evaluate(events=events).status, "BLOCKED")

    def test_boolean_handle_or_irp_identifier_blocks(self):
        self.assertEqual(evaluate(write=replace(WRITE, irp=True)).status, "BLOCKED")
        self.assertEqual(evaluate(original=replace(ORIGINAL, file_object=True)).status, "BLOCKED")

    def test_unverified_loss_gate_blocks_even_with_consistent_trace(self):
        self.assertEqual(evaluate(proofs=replace(FULL, capture_loss_independently_clear=False)).status, "BLOCKED")

    def test_capture_boundaries_require_consistent_order(self):
        for start, end in ((1000, 100), (True, 1000), (0, 1000), (100, 350)):
            with self.subTest(start=start, end=end):
                self.assertEqual(evaluate(start=start, end=end).status, "BLOCKED")

    def test_public_receipts_never_include_private_path_or_handle(self):
        path = r"C:\QA\UDF\TopSecret\private-705.tmp"
        private = PrivateHandlePath(path, 123, "original_file_handle")
        result = evaluate(path=private)
        receipt = str(result.public_receipt())
        for needle in ("TopSecret", "705", "700", "800", "200"):
            self.assertNotIn(needle, receipt)
        self.assertNotIn("TopSecret", repr(result))

    def test_dense_same_fileobject_writes_use_indexed_epochs(self):
        # Stable file object can receive many successful writes. The bridge
        # must not treat them as renames, nor rescan 4K raw events per check.
        other_writes = [record(16, tick, irp=10000 + tick, pid=200)
                        for tick in range(402, 441)]
        extra_completions = [record(24, tick + 1, irp=10000 + tick, pid=4, status=0)
                             for tick in range(402, 441)]
        # All additional writes are after the selected witness-to-completion
        # epoch and do not change its identity.
        events = [PARENT, REQUEST, COMPLETE, *other_writes, *extra_completions]
        self.assertEqual(evaluate(events=events).status, "CONTAINED_CANDIDATE_ONLY")

    def test_unknown_fileio_event_with_same_identity_blocks(self):
        self.assertEqual(evaluate(events=[PARENT, REQUEST, COMPLETE,
                                          record(255, 350)]).status, "BLOCKED")

    def test_precanonicalized_casefolded_path_cannot_be_promoted(self):
        # Current strict N12 canonical_file_path() casefolds file names.
        # That transformed string is not sufficient physical-root evidence.
        self.assertEqual(evaluate(request_path=r"c:\qa\udf\network\x.tmp").status, "BLOCKED")

    def test_dense_benign_writes_during_witness_epoch_remain_indexed(self):
        # 4K unrelated IRPs on the same actual object/key. None changes
        # identity, so the witness-to-write epoch must not be rejected on
        # benign write volume alone. Query cost must not depend on rescanning
        # 4K individual writes for every selected IRP.
        events = [PARENT, REQUEST, COMPLETE]
        for n in range(4000):
            events.append(record(16, 250, irp=100000 + n, pid=200))
        index = index_private_kernel_file_events(events, start_tick=100, end_tick=1000)
        self.assertIsNone(index.build_issue)
        for _ in range(50):
            result = review_private_write_pair(
                index=index, write=WRITE, writer=WRITER, original_pair=ORIGINAL,
                write_target=TARGET, permitted_roots=(ROOT,),
                request_time_path=TARGET.final_path, corroboration=FULL,
            )
            self.assertEqual(result.status, "CONTAINED_CANDIDATE_ONLY")

    def test_numeric_etw_fields_support_decimal_or_hex(self):
        req = {**REQUEST, "data": {**REQUEST["data"], "FileObject": "0x2bc", "FileKey": "800", "Irp": "9"}}
        self.assertEqual(evaluate(events=[PARENT, req, COMPLETE]).status, "CONTAINED_CANDIDATE_ONLY")


if __name__ == "__main__":
    unittest.main()
