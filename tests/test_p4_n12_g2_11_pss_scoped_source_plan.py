"""G2.11 tests: synthetic process-scoped snapshot orchestration only."""
from contextlib import contextmanager
import json
import unittest
from pathlib import Path
from unittest.mock import patch

from qa.p4_research import n12_pss_scoped_source_plan as plan

T = 100_000_000
FILE = {"handle": 32, "type_name": "File", "object_type": 0, "flags": 1}


def sample():
    return {
        "process": {
            "pid": 500, "birth": T, "exit": T + 80_000_000,
            "original_process_handle_verified": True,
            "etw_sequence_verified": True, "image_verified": True,
            "disposable_qa_verified": True,
        },
        "write": {
            "pid": 500, "birth": T, "handle": 32,
            "request": T + 20_000_000, "completion": T + 21_000_000,
        },
    }


class FakeBackend:
    synthetic_only = True

    def __init__(self):
        self.calls = []
        self.rows = [[dict(FILE)], [dict(FILE)]]
        self.times = [T + 10_000_000, T + 30_000_000]
        self.image = "msedgewebview2.exe"
        self.error_at = None
        self.wrong_birth = False
        self._index = -1

    @contextmanager
    def open_process(self, pid, *, access):
        self.calls.append(("open_process", pid, access))
        if self.error_at == "open":
            raise RuntimeError("C:/owner/private/process")
        try:
            yield "synthetic process handle"
        finally:
            self.calls.append(("close_process",))

    def identity(self, handle):
        self.calls.append(("identity",))
        return {
            "pid": 500, "birth": T + (1 if self.wrong_birth else 0),
            "image": self.image, "disposable_qa": True,
        }

    @contextmanager
    def capture(self, handle, *, flags, context_flags):
        self._index += 1
        which = self._index
        self.calls.append(("capture", which, flags, context_flags))
        try:
            if self.error_at == "capture" and which == 1:
                raise RuntimeError("C:/owner/private/snapshot")
            yield which
        finally:
            self.calls.append(("close_snapshot", which))

    def tick(self, snapshot):
        self.calls.append(("tick", snapshot))
        return self.times[snapshot]

    def walk(self, snapshot, walk_class):
        self.calls.append(("walk", snapshot, walk_class))
        if self.error_at == "walk" and snapshot == 1:
            raise RuntimeError("C:/owner/private/walk")
        return iter(self.rows[snapshot])


class G211InjectedPlanTests(unittest.TestCase):
    def test_best_case_is_only_a_candidate_and_all_handles_close(self):
        fake = FakeBackend()
        result = plan.review_injected_pair(**sample(), backend=fake)
        self.assertEqual(result["status"], "CANDIDATE_ONLY")
        self.assertEqual(result["native_N12_acceptance"], "NOT_EVALUATED")
        self.assertEqual(result["kernel_fileobject_etw_join"], "NOT_ESTABLISHED")
        self.assertFalse(result["owner_native_execution_authorized"])
        self.assertEqual(fake.calls[-1], ("close_process",))
        self.assertEqual([s for s in fake.calls if s[0] == "close_snapshot"],
                         [("close_snapshot", 0), ("close_snapshot", 1)])

    def test_minimal_flags_do_not_capture_names_or_va_clones(self):
        fake = FakeBackend()
        plan.review_injected_pair(**sample(), backend=fake)
        flags = [row[2] for row in fake.calls if row[0] == "capture"]
        self.assertEqual(flags, [0x14, 0x14])
        self.assertTrue(all((value & (0x08 | 0x01 | 0x40 | 0x20)) == 0
                            for value in flags))
        self.assertEqual([row[3] for row in fake.calls if row[0] == "capture"],
                         [0, 0])
        self.assertEqual([row[2] for row in fake.calls if row[0] == "walk"], [2, 2])

    def test_requires_exact_target_identity_before_capture(self):
        for issue in ("wrong_birth", "wrong_image"):
            with self.subTest(issue=issue):
                fake = FakeBackend()
                if issue == "wrong_birth":
                    fake.wrong_birth = True
                else:
                    fake.image = "unrelated.exe"
                result = plan.review_injected_pair(**sample(), backend=fake)
                self.assertEqual(result["blocker"], "PROCESS_IDENTITY_UNVERIFIED")
                self.assertEqual([call[0] for call in fake.calls].count("capture"), 0)
                self.assertEqual(fake.calls[-1], ("close_process",))

    def test_bad_scope_blocks_before_backend(self):
        for key, value in (
            ("pid", -1), ("birth", True),
            ("disposable_qa_verified", "true"), ("image_verified", False),
        ):
            with self.subTest(key=key):
                params = sample()
                params["process"][key] = value
                fake = FakeBackend()
                result = plan.review_injected_pair(**params, backend=fake)
                self.assertEqual(result["blocker"], "SOURCE_SCOPE_INVALID")
                self.assertEqual(fake.calls, [])

    def test_wrong_write_pid_or_birth_refuses_before_backend(self):
        for key in ("pid", "birth"):
            params = sample()
            params["write"][key] += 1
            fake = FakeBackend()
            self.assertEqual(plan.review_injected_pair(
                **params, backend=fake)["blocker"], "SOURCE_SCOPE_INVALID")
            self.assertEqual(fake.calls, [])

    def test_mock_marker_missing_blocks_without_calls(self):
        fake = FakeBackend()
        fake.synthetic_only = False
        self.assertEqual(plan.review_injected_pair(
            **sample(), backend=fake)["blocker"], "SOURCE_SCOPE_INVALID")
        self.assertEqual(fake.calls, [])

    def test_windows_always_blocks_before_mock_or_os_calls(self):
        fake = FakeBackend()
        with patch.object(plan.os, "name", "nt"):
            result = plan.review_injected_pair(**sample(), backend=fake)
        self.assertEqual(result["blocker"], "NATIVE_EXECUTION_DISALLOWED")
        self.assertEqual(fake.calls, [])

    def test_table_overflow_is_not_silently_truncated(self):
        fake = FakeBackend()
        fake.rows[0] = [dict(FILE, handle=n + 1) for n in range(257)]
        result = plan.review_injected_pair(**sample(), backend=fake)
        self.assertEqual(result["status"], "BLOCKED")
        self.assertEqual(result["blocker"], "MOCK_BACKEND_OR_CLEANUP_FAILED")
        self.assertEqual(fake.calls[-1], ("close_process",))
        self.assertIn(("close_snapshot", 0), fake.calls)

    def test_path_field_rejected_and_not_exposed(self):
        fake = FakeBackend()
        fake.rows[0][0]["object_name"] = "C:/owner/private/secret.txt"
        result = plan.review_injected_pair(**sample(), backend=fake)
        self.assertEqual(result["status"], "BLOCKED")
        self.assertNotIn("secret", json.dumps(result))
        self.assertNotIn("C:/owner", json.dumps(result))
        self.assertEqual(fake.calls[-1], ("close_process",))

    def test_partial_capture_failure_cleans_up_every_resource(self):
        for step in ("walk", "capture"):
            with self.subTest(step=step):
                fake = FakeBackend()
                fake.error_at = step
                result = plan.review_injected_pair(**sample(), backend=fake)
                self.assertEqual(result["blocker"], "MOCK_BACKEND_OR_CLEANUP_FAILED")
                self.assertEqual(fake.calls[-1], ("close_process",))
                self.assertEqual([x[1] for x in fake.calls if x[0] == "close_snapshot"],
                                 [0, 1])
                self.assertNotIn("private", json.dumps(result))

    def test_duplicate_handle_rows_stay_blocked_and_close(self):
        fake = FakeBackend()
        fake.rows[1].append(dict(FILE))
        result = plan.review_injected_pair(**sample(), backend=fake)
        self.assertEqual(result["status"], "BLOCKED")
        self.assertEqual(result["blocker"], "TABLE")
        self.assertEqual(fake.calls[-1], ("close_process",))

    def test_reused_handle_does_not_infer_file_object(self):
        fake = FakeBackend()
        fake.rows[1][0]["object_type"] = 5
        result = plan.review_injected_pair(**sample(), backend=fake)
        self.assertEqual(result["blocker"], "TYPE")
        self.assertEqual(result["same_object_at_write"], "NOT_ESTABLISHED")

    def test_unordered_clock_fails_after_cleanup(self):
        fake = FakeBackend()
        fake.times[1] = fake.times[0] - 1
        result = plan.review_injected_pair(**sample(), backend=fake)
        self.assertEqual(result["blocker"], "CLOCK")
        self.assertEqual(fake.calls[-1], ("close_process",))

    def test_module_does_not_include_a_native_api_or_external_export(self):
        source = Path(plan.__file__).read_text(encoding="utf-8")
        for name in ("ctypes.WinDLL(", "OpenProcess(", "PssCaptureSnapshot(",
                     "PssWalkSnapshot(", "DuplicateHandle(",
                     "NtQuerySystemInformation(", "subprocess.Popen(",
                     "requests.post(", "upload_artifact("):
            with self.subTest(name=name):
                self.assertNotIn(name, source)


if __name__ == "__main__":
    unittest.main()
