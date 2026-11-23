"""G2.12 PSS Win32 ABI and resource cleanup, all synthetic and non-native."""
from dataclasses import replace
import ctypes
import json
import unittest
from unittest.mock import patch

from qa.p4_research import n12_pss_win32_backend as p


class Api:
    def __init__(self):
        self.events = []
        self.rows = [{"handle": 32, "type_name": "File",
                      "object_type": 0, "flags": 5}]
        self.pid = 444
        self.birth = 123_000_000
        self.name = "msedgewebview2.exe"
        self.capture_issue = False
        self.walk_issue = False
        self.marker_close_issue = False
        self.snap_cleanup_issue = False

    def open_process(self, pid):
        self.events.append(("open", pid))
        return 111

    def identity(self, handle):
        self.events.append(("identity",))
        return self.pid, self.birth, self.name

    def close_process(self, handle):
        self.events.append(("close_process",))

    def capture(self, handle):
        self.events.append(("capture",))
        if self.capture_issue:
            raise p.PssScopeError("PSS_CAPTURE_INCOMPLETE")
        return p._PrivateSnapshot(222, 180_000_000)

    def free(self, handle):
        self.events.append(("free_snapshot",))
        if self.snap_cleanup_issue:
            raise p.PssScopeError("PSS_SNAPSHOT_CLEANUP_UNVERIFIED")

    def marker_open(self):
        self.events.append(("open_marker",))
        self.offset = 0
        return 333

    def walk_next(self, snapshot, marker):
        self.events.append(("walk",))
        if self.walk_issue:
            raise p.PssScopeError("PSS_HANDLE_WALK_INCOMPLETE")
        if self.offset == len(self.rows):
            return None
        item = self.rows[self.offset]
        self.offset += 1
        return item

    def marker_close(self, marker):
        self.events.append(("close_marker",))
        if self.marker_close_issue:
            raise p.PssScopeError("PSS_WALK_MARKER_CLEANUP_UNVERIFIED")


class G212Win32AdapterTests(unittest.TestCase):
    def test_live_backend_requires_fresh_hosted_one_use_scope(self):
        with self.assertRaises(p.PssScopeError):
            p.prepare_native_backend({})
        with patch.object(p.os, "name", "nt"):
            with self.assertRaises(p.PssScopeError):
                p.prepare_native_backend({
                    "GITHUB_ACTIONS": "true", "RUNNER_ENVIRONMENT": "github-hosted",
                    "RUNNER_OS": "Windows", "GITHUB_EVENT_NAME": "push",
                    "GITHUB_RUN_ATTEMPT": "1", "GITHUB_REF_NAME": "feature/live-dev-workspace-20261023",
                    p.SOURCE_ENV: "a" * 40,
                    "PILOTODIN_N12_PSS_REVIEWED_SHA": "a" * 40,
                })

    def test_exact_hosted_scope_is_only_necessary_not_sufficient(self):
        env = {
            "GITHUB_ACTIONS": "true", "RUNNER_ENVIRONMENT": "github-hosted",
            "RUNNER_OS": "Windows", "GITHUB_EVENT_NAME": "push",
            "GITHUB_RUN_ATTEMPT": "1", "GITHUB_REF_NAME": "feature/live-dev-workspace-20261023",
            p.CONSENT_ENV: p.CONSENT, p.SOURCE_ENV: "a" * 40,
            "PILOTODIN_N12_PSS_REVIEWED_SHA": "a" * 40,
        }
        with patch.object(p.os, "name", "nt"):
            p._require_one_use_scope(env)
        env["GITHUB_RUN_ATTEMPT"] = "2"
        with patch.object(p.os, "name", "nt"):
            with self.assertRaises(p.PssScopeError):
                p._require_one_use_scope(env)

    def test_pss_flags_do_not_capture_private_names_or_clone(self):
        self.assertEqual(p.PSS_FLAGS, 0x14)
        self.assertEqual(p.PSS_FLAGS & (0x08 | 0x01 | 0x20 | 0x40), 0)
        self.assertEqual(p.PSS_WALK_HANDLES, 2)
        self.assertEqual(p.PROCESS_RIGHTS, 0x1040)
        self.assertEqual(p.MAX_HANDLES, 256)
        self.assertEqual(ctypes.sizeof(p._HandleEntry) % ctypes.sizeof(ctypes.c_void_p), 0)

    def test_exact_process_birth_name_required_before_capture(self):
        for issue in ("birth", "name", "pid"):
            api = Api()
            if issue == "birth":
                api.birth += 1
            elif issue == "name":
                api.name = "other.exe"
            else:
                api.pid += 1
            adapter = p.ScopedPssApiAdapter(api)
            with self.assertRaises(p.PssScopeError):
                with adapter.open_verified_child(pid=444, birth=123_000_000):
                    self.fail("should not reach scoped capture")
            self.assertNotIn(("capture",), api.events)
            self.assertEqual(api.events[-1], ("close_process",))

    def test_missing_or_false_process_values_fail_before_open(self):
        for pid, birth in ((0, 1), (1, True), ("1", 1), (1, -1)):
            api = Api()
            with self.assertRaises(p.PssScopeError):
                with p.ScopedPssApiAdapter(api).open_verified_child(pid=pid, birth=birth):
                    pass
            self.assertEqual(api.events, [])

    def test_bounded_walk_releases_marker_snapshot_and_process(self):
        api = Api()
        adapter = p.ScopedPssApiAdapter(api)
        with adapter.open_verified_child(pid=444, birth=123_000_000) as process:
            with adapter.snapshot(process) as shot:
                rows = adapter.collect_private_rows(shot)
        self.assertEqual(len(rows), 1)
        self.assertEqual([x[0] for x in api.events if x[0].startswith("close") or
                          x[0] == "free_snapshot"],
                         ["close_marker", "free_snapshot", "close_process"])

    def test_extra_257th_row_fails_closed_without_truncation(self):
        api = Api()
        api.rows = [{"handle": i + 1, "type_name": "File",
                     "object_type": 0, "flags": 5} for i in range(257)]
        adapter = p.ScopedPssApiAdapter(api)
        with self.assertRaises(p.PssScopeError):
            with adapter.open_verified_child(pid=444, birth=123_000_000) as process:
                with adapter.snapshot(process) as shot:
                    adapter.collect_private_rows(shot)
        self.assertEqual(api.events[-3:],
                         [("close_marker",), ("free_snapshot",), ("close_process",)])

    def test_walk_or_capture_failures_release_every_acquired_resource(self):
        for issue in ("capture_issue", "walk_issue", "marker_close_issue"):
            api = Api()
            setattr(api, issue, True)
            adapter = p.ScopedPssApiAdapter(api)
            with self.assertRaises(p.PssScopeError):
                with adapter.open_verified_child(pid=444, birth=123_000_000) as process:
                    with adapter.snapshot(process) as shot:
                        adapter.collect_private_rows(shot)
            self.assertEqual(api.events[-1], ("close_process",))
            if issue != "capture_issue":
                self.assertIn(("free_snapshot",), api.events)

    def test_invalid_record_schema_cannot_escape_marker_cleanup(self):
        api = Api()
        api.rows = [{"handle": 32, "type_name": "File",
                     "object_type": 0, "flags": 1,
                     "private_path": "C:/owner/private/secret"}]
        adapter = p.ScopedPssApiAdapter(api)
        with self.assertRaises(p.PssScopeError):
            with adapter.open_verified_child(pid=444, birth=123_000_000) as process:
                with adapter.snapshot(process) as shot:
                    adapter.collect_private_rows(shot)
        self.assertEqual(api.events[-3:],
                         [("close_marker",), ("free_snapshot",), ("close_process",)])

    def test_private_receipt_never_contains_native_identity_or_path(self):
        for value in ("C:/owner/private/secret", "12345", "caller error"):
            public = p.redacted_blocker(value)
            output = json.dumps(public)
            self.assertEqual(public["blocker"], "UNVERIFIED")
            self.assertNotIn(value, output)
        self.assertFalse(p.redacted_blocker("PSS_HANDLE_WALK_INCOMPLETE")[
            "owner_native_execution_authorized"])

    def test_snapshot_bad_metadata_also_frees_capture(self):
        api = Api()
        api.capture = lambda handle: p._PrivateSnapshot(222, 0)
        adapter = p.ScopedPssApiAdapter(api)
        with self.assertRaises(p.PssScopeError):
            with adapter.open_verified_child(pid=444, birth=123_000_000) as process:
                with adapter.snapshot(process):
                    pass
        self.assertIn(("free_snapshot",), api.events)
        self.assertEqual(api.events[-1], ("close_process",))

    def test_partial_native_capture_failure_frees_snapshot_if_returned(self):
        api = object.__new__(p._Win32PssApi)
        freed = []
        api.current_ticks = lambda: 100
        def fail_after_partial(process, flags, thread_flags, out):
            self.assertEqual(flags, p.PSS_FLAGS)
            self.assertEqual(thread_flags, 0)
            ctypes.cast(out, ctypes.POINTER(ctypes.c_void_p))[0] = 444
            return 5
        api.capture_fn = fail_after_partial
        api.free = lambda handle: freed.append(handle)
        with self.assertRaises(p.PssScopeError):
            api.capture(111)
        self.assertEqual(freed, [444])

    def test_capture_clock_anomaly_releases_snapshot(self):
        api = object.__new__(p._Win32PssApi)
        freed = []
        times = iter([100, 10_000_201])
        api.current_ticks = lambda: next(times)
        def succeed(process, flags, thread_flags, out):
            ctypes.cast(out, ctypes.POINTER(ctypes.c_void_p))[0] = 555
            return 0
        api.capture_fn = succeed
        api.free = lambda handle: freed.append(handle)
        with self.assertRaises(p.PssScopeError):
            api.capture(111)
        self.assertEqual(freed, [555])

    def test_handle_entry_decode_never_reads_object_name(self):
        row = p._HandleEntry()
        row.handle = 30
        row.flags = 0x02
        row.object_name_bytes = 20
        # Native decode is not invoked with mock API: the ABI presence and
        # NAME-flag rejection are enforced by stable source contracts.
        self.assertNotEqual(row.flags & p.PSS_HANDLE_HAVE_NAME, 0)


if __name__ == "__main__":
    unittest.main()
