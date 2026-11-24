"""G2.25 synthetic controls only; no Windows, trace or owner-file operations."""
import dataclasses
import json
from pathlib import Path
import unittest
from qa.p4_research.n12_obtrace_feasibility import (
    OBTRACE, CaptureClaims, SelfFileControl, decode_private_obtrace,
    review_generated_controls,
)
from qa.p4_research.n12_fileio_pair_contract import PrivateWriterSpan, PrivateWriteIdentity
from qa.p4_research.n12_physical_destination import PrivateHandlePath


def ob(op, tick, handle, obj, pid=77, width=8, **updates):
    props = {"Object": obj.to_bytes(width, "little"), "ObjectType": b"\x07\x00"}
    props.update({"SourceHandle": handle.to_bytes(4, "little"),
                  "TargetHandle": b"\x44\x00\x00\x00",
                  "TargetProcessId": b"\x4d\x00\x00\x00"} if op == 34 else
                 {"Handle": handle.to_bytes(4, "little")})
    row = dict(provider=OBTRACE, version=2, opcode=op, classic=True,
               header32=width == 4, header64=width == 8,
               tick=tick, pid=pid, tid=88, properties=props)
    row.update(updates)
    return row


def file_pair(w):
    return [
        dict(id=16, ticks=w.request_tick, pid=w.writer_pid, data={
            "Irp": w.irp, "FileObject": w.file_object, "FileKey": w.file_key,
            "IssuingThreadId": w.issuing_tid}),
        dict(id=24, ticks=w.completion_tick, pid=4, data={"Irp": w.irp, "Status": 0}),
    ]


class ObTraceFeasibilityTests(unittest.TestCase):
    def setUp(self):
        self.writer = PrivateWriterSpan(77, 10, 190, 88, 20, 180)
        self.path = PrivateHandlePath(r"C:\private\generated.bin", 123, "original_file_handle")
        self.a = SelfFileControl(16, 40, PrivateWriteIdentity(100, 0x100000001, 300, 77, 88, 60, 70), self.path)
        self.b = SelfFileControl(20, 50, PrivateWriteIdentity(200, 0x100000002, 300, 77, 88, 80, 90), self.path)
        self.rows = [ob(32, 25, 16, self.a.write.file_object),
                     ob(32, 30, 20, self.b.write.file_object),
                     ob(33, 100, 16, self.a.write.file_object),
                     ob(33, 110, 20, self.b.write.file_object)]
        self.events = file_pair(self.a.write) + file_pair(self.b.write)
        self.claims = CaptureClaims(True, True, True, True, True)

    def review(self, **kw):
        args = dict(obtrace_rows=self.rows, file_events=self.events,
                    writer=self.writer, controls=(self.a, self.b),
                    start_tick=1, end_tick=200, claims=self.claims)
        args.update(kw)
        return review_generated_controls(**args)

    def test_two_distinct_open_candidates_never_acceptance(self):
        r = self.review()
        self.assertEqual(r["reason"], "TWO_DISTINCT_SELF_FILE_JOINS")
        self.assertEqual(r["checked_controls"], 2)
        self.assertFalse(r["original_file_handle_verified"])
        self.assertFalse(r["physical_destination_verified"])
        self.assertEqual(r["strict_path_credit_awarded"], 0)
        self.assertEqual(r["native_N12_acceptance"], "NOT_EVALUATED")
        self.assertNotIn("generated.bin", json.dumps(r))
        self.assertNotIn("4294967297", repr(decode_private_obtrace(self.rows[0])))

    def test_width_and_schema_strict(self):
        self.assertEqual(decode_private_obtrace(ob(32, 25, 16, 400, width=4)).object_id, 400)
        self.assertEqual(decode_private_obtrace(self.rows[0]).object_id, 0x100000001)
        for change in ({"header32": True}, {"header64": False}, {"version": 3},
                       {"classic": False}, {"provider": "wrong"}, {"opcode": 35},
                       {"pid": True}, {"properties": {"Object": b"\x01"}}):
            with self.subTest(change=change):
                self.assertIsNone(decode_private_obtrace(dict(self.rows[0], **change)))

    def test_unverified_capture_claims_and_bounds(self):
        for field in vars(self.claims):
            self.assertEqual(self.review(claims=dataclasses.replace(self.claims, **{field: False}))["reason"],
                             "CAPTURE_CLAIMS_INCOMPLETE")
        self.assertEqual(self.review(start_tick=15)["reason"], "PRIVATE_CONTROL_ENVELOPE_INVALID")

    def test_unknown_or_missing_event_blocks(self):
        self.assertEqual(self.review(obtrace_rows=self.rows[:-1])["reason"], "HANDLE_EPOCH_REUSED_OR_UNCLOSED")
        self.assertEqual(self.review(obtrace_rows=self.rows + [dict(self.rows[0], opcode=35)])["reason"],
                         "OBJECT_EVENT_SCHEMA_OR_CLOCK_UNVERIFIED")

    def test_duplicate_and_foreign_object_block(self):
        obj = self.a.write.file_object
        self.assertEqual(self.review(obtrace_rows=self.rows + [ob(34, 45, 16, obj)])["reason"],
                         "DUPLICATE_PROVENANCE_UNSUPPORTED")
        self.assertEqual(self.review(obtrace_rows=self.rows + [ob(32, 45, 44, obj, pid=99)])["reason"],
                         "FOREIGN_OBJECT_OWNERSHIP_UNRESOLVED")

    def test_multiple_handles_same_object_block(self):
        obj = self.a.write.file_object
        rows = self.rows + [ob(32, 45, 44, obj), ob(33, 95, 44, obj)]
        self.assertEqual(self.review(obtrace_rows=rows)["reason"], "ORIGINAL_HANDLE_EPOCH_AMBIGUOUS")

    def test_reuse_close_and_tied_epoch_block(self):
        obj = self.a.write.file_object
        self.assertEqual(self.review(obtrace_rows=self.rows + [ob(32, 45, 16, obj)])["reason"],
                         "HANDLE_EPOCH_REUSED_OR_UNCLOSED")
        self.assertEqual(self.review(obtrace_rows=self.rows + [ob(33, 45, 44, obj)])["reason"],
                         "HANDLE_CLOSE_UNMATCHED")
        self.assertEqual(self.review(obtrace_rows=self.rows + [ob(32, 25, 44, obj)])["reason"],
                         "HANDLE_EPOCH_ORDER_AMBIGUOUS")

    def test_failed_or_ambiguous_fileio_and_name_transition(self):
        bad = self.events.copy()
        bad[1] = dict(bad[1], data={"Irp": 100, "Status": 5})
        self.assertEqual(self.review(file_events=bad)["reason"], "FILEIO_REQUEST_COMPLETION_UNVERIFIED")
        self.assertEqual(self.review(file_events=self.events + [self.events[1]])["reason"],
                         "FILEIO_IRP_AMBIGUOUS")
        extra = dict(id=19, ticks=55, pid=77,
                     data={"FileObject": self.a.write.file_object, "FileKey": 300})
        self.assertEqual(self.review(file_events=self.events + [extra])["reason"],
                         "FILEIO_OBJECT_OR_NAME_EPOCH_UNVERIFIED")

    def test_no_extra_writer_writes_or_reopened_path_claim(self):
        extra = dict(id=16, ticks=95, pid=77, data={})
        self.assertEqual(self.review(file_events=self.events + [extra])["reason"],
                         "WRITER_WRITE_INVENTORY_UNVERIFIED")
        b = dataclasses.replace(self.b, final_path=dataclasses.replace(self.path, acquisition="reopened"))
        self.assertEqual(self.review(controls=(self.a, b))["reason"], "SELF_FILE_WITNESS_INVALID")

    def test_native_source_dormant_and_no_name_or_foreign_handle_query(self):
        path = Path(__file__).resolve().parents[1] / "qa/p4_research/n12_obtrace_win32_session.cpp"
        source = path.read_text(encoding="utf-8")
        self.assertIn("constexpr bool kNativeExecutionEnabled = false;", source)
        self.assertLess(source.index("if (!kNativeExecutionEnabled)"), source.index("StartTraceW("))
        self.assertIn("EVENT_TRACE_SYSTEM_LOGGER_MODE", source)
        self.assertIn("SYSTEM_OBJECT_KW_HANDLE", source)
        self.assertIn("TdhGetPropertySize", source)
        self.assertNotIn("int main(", source)
        self.assertNotIn("DuplicateHandle(", source)
        self.assertNotIn("OpenProcess(", source)
        self.assertNotIn('L"ObjectName"', source)


if __name__ == "__main__":
    unittest.main()
