"""G2.15 process-scoped handle-type candidate: mock-only negative tests."""
from contextlib import contextmanager
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from qa.p4_research import n12_duplicate_handle_type as target


class Backend:
    synthetic_only = True
    def __init__(self):
        self.events = []
        self.kind = {10: 1, 20: 3}
        self.error = 0
        self.fail_duplicate = None
        self.fail_close = False
        self.identity_value = (500, 100, "msedgewebview2.exe")

    @contextmanager
    def open_process(self, pid, *, access):
        assert access == target.PROCESS_RIGHTS
        self.events.append(("open", pid))
        try:
            yield "scoped-process"
        finally:
            self.events.append(("close_process",))

    def identity(self, process):
        self.events.append(("identity",))
        return self.identity_value

    @contextmanager
    def duplicate(self, process, original, *, desired_access, inherit, options):
        assert (desired_access, inherit, options) == (
            0, False, target.DUPLICATE_SAME_ACCESS)
        self.events.append(("duplicate", original))
        if self.fail_duplicate == original:
            raise RuntimeError("C:/private/secret")
        try:
            yield original
        finally:
            self.events.append(("close_duplicate", original))
            if self.fail_close:
                raise RuntimeError("private cleanup failure")

    def file_type(self, local):
        self.events.append(("get_file_type", local))
        return (self.kind.get(local, 0), self.error)


def sample():
    return {
        "process": {
            "pid": 500, "birth": 100, "exit": 400,
            "original_process_handle_verified": True,
            "etw_sequence_verified": True, "image_verified": True,
            "disposable_qa_verified": True,
        },
        "snapshot": {
            "source": target.PSS_SOURCE, "pid": 500, "birth": 100,
            "tick": 200, "complete": True, "handles": [10, 20],
        },
        "backend": Backend(),
    }


class G215CandidateTests(unittest.TestCase):
    def test_disk_type_alone_never_earns_native_or_original_writer_credit(self):
        args = sample()
        result = target.review_injected(**args)
        self.assertEqual(result["status"], "CANDIDATE_ONLY")
        self.assertEqual(result["disk_handle_classification"], "CANDIDATE_ONLY")
        self.assertEqual(result["original_writer_file_handle"], "NOT_VERIFIED")
        self.assertEqual(result["kernel_fileobject_etw_join"], "NOT_ESTABLISHED")
        self.assertFalse(result["handle_reuse_excluded"])
        self.assertEqual(result["native_N12_acceptance"], "NOT_EVALUATED")
        self.assertFalse(result["owner_native_execution_authorized"])
        self.assertEqual(args["backend"].events[-1], ("close_process",))
        self.assertEqual(
            [v for v in args["backend"].events if v[0] == "close_duplicate"],
            [("close_duplicate", 10), ("close_duplicate", 20)])

    def test_non_disk_only_is_blocked(self):
        args = sample()
        args["backend"].kind = {10: 3, 20: 2}
        self.assertEqual(target.review_injected(**args)["blocker"], "NO_DISK")

    def test_unknown_or_error_never_credited(self):
        for kind, error in ((0, 0), (0, 5), (1, 5), (8, 0)):
            with self.subTest(kind=kind, error=error):
                args = sample()
                args["backend"].kind[10] = kind
                args["backend"].error = error
                self.assertEqual(
                    target.review_injected(**args)["status"], "BLOCKED")
                self.assertEqual(args["backend"].events[-1],
                                 ("close_process",))

    def test_both_actual_pss_missing_type_shapes_are_irrelevant(self):
        # No PSS TypeName is consulted or changed to 'File'.
        args = sample()
        args["snapshot"]["private_type_name"] = ""
        self.assertEqual(target.review_injected(**args)["blocker"], "SNAPSHOT")

    def test_scoped_process_requires_identity_and_lifetime(self):
        for key, value in (("pid", 501), ("birth", 105), ("exit", 50),
                           ("image_verified", "true"),
                           ("disposable_qa_verified", False)):
            args = sample()
            args["process"][key] = value
            self.assertEqual(target.review_injected(**args)["status"], "BLOCKED")
        args = sample()
        args["backend"].identity_value = (500, 100, "other.exe")
        self.assertEqual(target.review_injected(**args)["blocker"], "IDENTITY")
        self.assertEqual(args["backend"].events[-1], ("close_process",))

    def test_snapshot_rejects_identity_mismatch_and_partial_coverage(self):
        for key, value in (("source", "SYSTEM_SCAN"), ("pid", 501),
                           ("birth", 101), ("tick", 450),
                           ("complete", False)):
            args = sample()
            args["snapshot"][key] = value
            self.assertEqual(target.review_injected(**args)["status"], "BLOCKED")
            self.assertEqual(args["backend"].events, [])

    def test_duplicate_invalid_overflow_and_empty_handles_are_blocked(self):
        for handles in ([10, 10], [], [True], [-1], ["10"],
                        list(range(1, 258))):
            args = sample()
            args["snapshot"]["handles"] = handles
            self.assertEqual(target.review_injected(**args)["blocker"], "HANDLES")
            self.assertEqual(args["backend"].events, [])

    def test_duplicate_error_or_cleanup_failure_is_redacted(self):
        for failure in ("duplicate", "close"):
            args = sample()
            if failure == "duplicate":
                args["backend"].fail_duplicate = 20
            else:
                args["backend"].fail_close = True
            r = target.review_injected(**args)
            self.assertEqual(r["status"], "BLOCKED")
            self.assertEqual(args["backend"].events[-1], ("close_process",))
            self.assertNotIn("private", json.dumps(r))
            self.assertNotIn("500", json.dumps(r))
            self.assertNotIn("10", json.dumps(r))

    def test_no_actual_windows_api_or_app_capture_in_this_module(self):
        source = Path(target.__file__).read_text(encoding="utf-8")
        for forbidden in ("WinDLL(", "PssCaptureSnapshot(",
                          "NtQuerySystemInformation(", "subprocess.Popen(",
                          "GetFileName", "GetFinalPathNameByHandle"):
            self.assertNotIn(forbidden, source)
        with patch.object(target.os, "name", "nt"):
            args = sample()
            self.assertEqual(target.review_injected(**args)["blocker"], "SCOPE")
            self.assertEqual(args["backend"].events, [])


if __name__ == "__main__":
    unittest.main()
