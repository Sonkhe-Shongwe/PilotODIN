"""G2.10 process-scoped PSS candidate tests, pure Linux synthetic."""
import json
import unittest
from pathlib import Path
from qa.p4_research import n12_pss_file_handle_candidates as gate

T = 100_000_000
FILE_ROW = {"handle": 32, "type_name": "File", "object_type": 0, "flags": 1}


def sample():
    return {
        "process": {"pid": 500, "birth": T, "exit": T + 80_000_000,
                    "original_process_handle_verified": True, "etw_sequence_verified": True,
                    "image_verified": True, "disposable_qa_verified": True},
        "before": {"source": gate.SOURCE, "pid": 500, "birth": T,
                   "tick": T + 10_000_000, "complete": True, "rows": [FILE_ROW.copy()]},
        "after": {"source": gate.SOURCE, "pid": 500, "birth": T,
                  "tick": T + 30_000_000, "complete": True, "rows": [FILE_ROW.copy()]},
        "write": {"pid": 500, "birth": T, "handle": 32,
                  "request": T + 20_000_000, "completion": T + 21_000_000},
    }


class G210PssCandidateTests(unittest.TestCase):
    def test_best_case_stays_candidate_only(self):
        result = gate.review_candidate(**sample())
        self.assertEqual(result["status"], "CANDIDATE_ONLY")
        self.assertFalse(result["handle_reuse_excluded"])
        self.assertEqual(result["kernel_fileobject_etw_join"], "NOT_ESTABLISHED")
        self.assertEqual(result["original_file_handle_provenance"], "NOT_VERIFIED")
        self.assertEqual(result["native_N12_acceptance"], "NOT_EVALUATED")
        self.assertFalse(result["owner_native_execution_authorized"])

    def test_wrong_process_or_birth(self):
        for where, key, value in (("process", "pid", 501), ("before", "pid", 501),
                                  ("after", "birth", T + 1), ("write", "birth", T + 1)):
            with self.subTest(where=where, key=key):
                f = sample()
                f[where][key] = value
                self.assertEqual(gate.review_candidate(**f)["status"], "BLOCKED")

    def test_claimed_process_identity_requires_literal_true(self):
        for key in ("original_process_handle_verified", "etw_sequence_verified",
                    "image_verified", "disposable_qa_verified"):
            f = sample()
            f["process"][key] = "true"
            self.assertEqual(gate.review_candidate(**f)["blocker"], "PROCESS")

    def test_systemwide_source_or_partial_snapshot_refused(self):
        for key, value in (("source", "SYSTEM_HANDLE_SCAN"),
                           ("source", "NtQuerySystemInformation"),
                           ("complete", False)):
            f = sample()
            f["before"][key] = value
            self.assertEqual(gate.review_candidate(**f)["blocker"], "SCOPE")

    def test_out_of_order_or_bool_clock(self):
        for value in (True, -1, T + 50_000_000):
            f = sample()
            f["before"]["tick"] = value
            self.assertEqual(gate.review_candidate(**f)["blocker"], "CLOCK")

    def test_excessive_snapshot_span(self):
        f = sample()
        f["after"]["tick"] = f["before"]["tick"] + gate.MAX_TICKS + 1
        f["process"]["exit"] = f["after"]["tick"] + 1
        self.assertEqual(gate.review_candidate(**f)["blocker"], "CLOCK")

    def test_handle_overflow_cannot_be_silently_truncated(self):
        f = sample()
        f["before"]["rows"] = [dict(FILE_ROW, handle=i + 1)
                               for i in range(gate.MAX_HANDLES + 1)]
        self.assertEqual(gate.review_candidate(**f)["blocker"], "TABLE")

    def test_duplicate_handle_row_refused(self):
        f = sample()
        f["before"]["rows"].append(FILE_ROW.copy())
        self.assertEqual(gate.review_candidate(**f)["blocker"], "TABLE")

    def test_not_seen_at_final_snapshot(self):
        f = sample()
        f["after"]["rows"] = []
        self.assertEqual(gate.review_candidate(**f)["blocker"], "HANDLE")

    def test_unreliable_type_label_or_flags(self):
        for group, key, value in (("before", "type_name", "Section"),
                                  ("after", "object_type", 5), ("before", "flags", 0)):
            f = sample()
            f[group]["rows"][0][key] = value
            self.assertEqual(gate.review_candidate(**f)["blocker"], "TYPE")

    def test_noninteger_or_reused_unknown_handle_does_not_pass(self):
        for h in (True, "32", 0, -1, 999):
            f = sample()
            f["write"]["handle"] = h
            self.assertEqual(gate.review_candidate(**f)["status"], "BLOCKED")

    def test_untrusted_path_never_in_public_receipt(self):
        f = sample()
        f["before"]["private_path"] = "C:/owner/secret"
        result = gate.review_candidate(**f)
        self.assertEqual(result["blocker"], "SCHEMA")
        self.assertNotIn("secret", json.dumps(result))
        self.assertNotIn("500", json.dumps(result))

    def test_source_has_no_actual_windows_calls(self):
        source = Path(gate.__file__).read_text(encoding="utf-8")
        for forbidden in ("ctypes.WinDLL(", "PssCaptureSnapshot(", "NtQuerySystemInformation(",
                          "DuplicateHandle(", "subprocess.Popen("):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
