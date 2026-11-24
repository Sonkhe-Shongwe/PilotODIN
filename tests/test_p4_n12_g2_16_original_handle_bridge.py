"""G2.16 source-only verified WebView2 process plus private disk-handle bridge.

Only injected Win32 callbacks are used. No real process is opened or captured.
"""
from contextlib import contextmanager
import ctypes
import json
import unittest
from unittest.mock import patch

from qa.p4_research import n12_pss_win32_backend as p


class Fake:
    def __init__(self):
        self.events = []
        self.pid = 501
        self.birth = 300_000_000
        self.image = "msedgewebview2.exe"
        self.rows = [
            {"handle": 31, "type_name": "", "object_type": 0, "flags": 0},
            {"handle": 32, "type_name": "", "object_type": 0, "flags": 0},
        ]
        self.kinds = {31: (p.FILE_TYPE_DISK, 0),
                      32: (p.FILE_TYPE_UNKNOWN, 6)}
        self.fail_duplicate = None
        self.fail_close = False
        self.offset = 0

    def open_process(self, pid):
        self.events.append(("open_process", pid))
        return 999

    def identity(self, process):
        self.events.append(("identity",))
        return self.pid, self.birth, self.image

    def close_process(self, process):
        self.events.append(("close_process",))
        if self.fail_close:
            raise p.PssScopeError("TARGET_PROCESS_CLOSE_UNVERIFIED")

    def capture(self, process):
        self.events.append(("capture",))
        return p._PrivateSnapshot(400, self.birth + 50_000)

    def free(self, snapshot):
        self.events.append(("free_snapshot",))
        if self.fail_close:
            raise p.PssScopeError("PSS_SNAPSHOT_CLEANUP_UNVERIFIED")

    def marker_open(self):
        self.events.append(("marker_open",))
        self.offset = 0
        return 500

    def walk_next(self, snapshot, marker):
        self.events.append(("walk_next",))
        if self.offset >= len(self.rows):
            return None
        row = self.rows[self.offset]
        self.offset += 1
        return row

    def marker_close(self, marker):
        self.events.append(("marker_close",))
        if self.fail_close:
            raise p.PssScopeError("PSS_WALK_MARKER_CLEANUP_UNVERIFIED")

    @contextmanager
    def duplicate(self, process, original):
        self.events.append(("duplicate", original))
        if original == self.fail_duplicate:
            raise p.PssScopeError("DUPLICATE_HANDLE_UNAVAILABLE")
        try:
            yield original + 100
        finally:
            self.events.append(("close_duplicate", original))
            if self.fail_close:
                raise p.PssScopeError("DUPLICATE_HANDLE_CLEANUP_UNVERIFIED")

    def file_type(self, local):
        self.events.append(("file_type", local))
        return self.kinds.get(local - 100, (p.FILE_TYPE_UNKNOWN, 6))


class G216NativeSourceTests(unittest.TestCase):
    def test_untyped_pss_handle_is_classifiable_only_as_private_disk_candidate(self):
        api = Fake()
        result = p.ScopedPssApiAdapter(api).collect_private_disk_candidates(
            pid=501, birth=300_000_000)
        self.assertIs(type(result), p._PrivateDiskCandidates)
        self.assertEqual(result.handles, (31,))
        self.assertEqual(result.total_rows, 2)
        self.assertEqual(result.unclassified_rows, 1)
        self.assertNotIn("31", repr(result))
        self.assertNotIn("31", str(result))
        self.assertEqual([event for event in api.events
                          if event[0] == "close_duplicate"],
                         [("close_duplicate", 31), ("close_duplicate", 32)])
        self.assertEqual(api.events[-3:],
                         [("marker_close",), ("free_snapshot",),
                          ("close_process",)])

    def test_process_birth_and_image_mismatch_refused_before_snapshot(self):
        for field, value in (("pid", 500), ("birth", 300_000_001),
                             ("image", "not-webview.exe")):
            api = Fake()
            setattr(api, field, value)
            with self.assertRaises(p.PssScopeError):
                p.ScopedPssApiAdapter(api).collect_private_disk_candidates(
                    pid=501, birth=300_000_000)
            self.assertNotIn(("capture",), api.events)
            self.assertEqual(api.events[-1], ("close_process",))

    def test_invalid_target_process_id_or_birth_cannot_open(self):
        for pid, birth in ((0, 100), (501, True),
                           ("501", 100), (501, -5)):
            api = Fake()
            with self.assertRaises(p.PssScopeError):
                p.ScopedPssApiAdapter(api).collect_private_disk_candidates(
                    pid=pid, birth=birth)
            self.assertEqual(api.events, [])

    def test_duplicate_handle_values_partial_and_overflow_fail_closed(self):
        for rows in (
            [], [dict(Fake().rows[0]), dict(Fake().rows[0])],
            [{"handle": 0, "type_name": "", "object_type": 0, "flags": 0}],
            [{"handle": True, "type_name": "", "object_type": 0, "flags": 0}],
            [{"handle": 33, "type_name": "", "object_type": 0, "flags": 2}],
            [{"handle": 33, "type_name": "", "object_type": 0,
              "flags": 0, "object_name": "secret"}],
            [{"handle": i, "type_name": "", "object_type": 0, "flags": 0}
             for i in range(1, 258)],
        ):
            api = Fake()
            api.rows = rows
            with self.assertRaises(p.PssScopeError):
                p.ScopedPssApiAdapter(api).collect_private_disk_candidates(
                    pid=501, birth=300_000_000)
            self.assertEqual(api.events[-1], ("close_process",))
            self.assertIn(("free_snapshot",), api.events)

    def test_duplicate_failure_and_cleanup_refuse_partial_results(self):
        for failure in ("duplicate", "cleanup"):
            api = Fake()
            if failure == "duplicate":
                api.fail_duplicate = 32
            else:
                api.fail_close = True
            with self.assertRaises(p.PssScopeError):
                p.ScopedPssApiAdapter(api).collect_private_disk_candidates(
                    pid=501, birth=300_000_000)
            self.assertEqual(api.events[-1], ("close_process",))

    def test_error_or_unexpected_type_never_credited(self):
        for value in ((p.FILE_TYPE_DISK, 5), (14, 0), ("1", 0),
                      (p.FILE_TYPE_PIPE, 5)):
            api = Fake()
            api.kinds[31] = value
            with self.assertRaises(p.PssScopeError):
                p.ScopedPssApiAdapter(api).collect_private_disk_candidates(
                    pid=501, birth=300_000_000)
            self.assertEqual(api.events[-3:],
                             [("marker_close",), ("free_snapshot",),
                              ("close_process",)])

    def test_empty_or_nonfile_types_do_not_create_disk_candidate(self):
        api = Fake()
        api.kinds = {31: (p.FILE_TYPE_PIPE, 0),
                     32: (p.FILE_TYPE_CHAR, 0)}
        result = p.ScopedPssApiAdapter(api).collect_private_disk_candidates(
            pid=501, birth=300_000_000)
        self.assertEqual(result.handles, ())
        self.assertEqual(result.unclassified_rows, 0)

    def test_native_duplicate_writes_only_destination_and_always_closes(self):
        api = object.__new__(p._Win32PssApi)
        out_values = []
        closed = []
        api.get_current_process_fn = lambda: 777
        api.close_handle_fn = lambda handle: closed.append(handle) or 1
        def stub(source, original, current, out, access, inherit, flags):
            out_values.append((source, original, current, access, inherit, flags))
            ctypes.cast(out, ctypes.POINTER(ctypes.c_void_p))[0] = 200
            return 1
        api.duplicate_fn = stub
        with api.duplicate(100, 31) as local:
            self.assertEqual(local, 200)
        self.assertEqual(out_values, [(100, 31, 777, 0, 0, p.DUPLICATE_SAME_ACCESS)])
        self.assertEqual(closed, [200])
        self.assertNotIn(31, closed)

    def test_partial_duplicate_failure_closes_local_handle_even_on_error(self):
        api = object.__new__(p._Win32PssApi)
        closed = []
        api.get_current_process_fn = lambda: 777
        api.close_handle_fn = lambda handle: closed.append(handle) or 1
        def partial(source, original, current, out, access, inherit, flags):
            ctypes.cast(out, ctypes.POINTER(ctypes.c_void_p))[0] = 300
            return 0
        api.duplicate_fn = partial
        with self.assertRaises(p.PssScopeError):
            with api.duplicate(100, 31):
                self.fail("failed duplicate must never yield")
        self.assertEqual(closed, [300])

    def test_ctypes_file_type_unknown_error_captured_and_not_native_invoked(self):
        api = object.__new__(p._Win32PssApi)
        api.file_type_fn = lambda h: p.FILE_TYPE_DISK
        with patch.object(p.ctypes, "set_last_error", create=True) as setter, patch.object(
                p.ctypes, "get_last_error", return_value=0, create=True) as getter:
            self.assertEqual(api.file_type(200), (p.FILE_TYPE_DISK, 0))
            setter.assert_called_once_with(0)
            getter.assert_called_once_with()
        with self.assertRaises(p.PssScopeError):
            api.file_type(0)

    def test_public_error_receipt_never_prints_private_handle(self):
        for text in ("C:/private/example", "31", "owner PID 501"):
            receipt = p.redacted_blocker(text)
            self.assertNotIn(text, json.dumps(receipt))
            self.assertEqual(receipt["native_N12_acceptance"], "NOT_EVALUATED")
        self.assertEqual(p.PSS_FLAGS, 0x14)
        self.assertEqual(p.PROCESS_RIGHTS, 0x1040)
        self.assertEqual(p.DUPLICATE_SAME_ACCESS, 0x2)
        self.assertNotIn("DUPLICATE_CLOSE_SOURCE",
                         __import__("inspect").getsource(p._Win32PssApi.duplicate))


if __name__ == "__main__":
    unittest.main()
