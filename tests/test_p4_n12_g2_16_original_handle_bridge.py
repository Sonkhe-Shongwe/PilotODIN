"""G2.18 safety correction of G2.16/17: do not duplicate WebView2 sockets.

All tests are injected, source-only. The G2.15 disposable self-process
Windows result remains historical evidence, NOT arbitrary WebView2 safety.
"""
import ast
import json
from pathlib import Path
import unittest

from qa.p4_research import n12_pss_win32_backend as p


class Fake:
    def __init__(self, rows=None):
        self.events = []
        self.rows = list(rows if rows is not None else [
            {"handle": 31, "type_name": "", "object_type": 0, "flags": 0},
            {"handle": 32, "type_name": "File", "object_type": 0, "flags": 1},
            {"handle": 33, "type_name": "Event", "object_type": 4, "flags": 1},
        ])
        self.offset = 0
        self.pid = 501
        self.birth = 300_000_000
        self.image = "msedgewebview2.exe"

    def open_process(self, pid):
        self.events.append(("open_process", pid))
        return 999

    def identity(self, process):
        self.events.append(("identity",))
        return self.pid, self.birth, self.image

    def close_process(self, process):
        self.events.append(("close_process",))

    def capture(self, process):
        self.events.append(("capture",))
        return p._PrivateSnapshot(400, 300_050_000)

    def free(self, snapshot):
        self.events.append(("free_snapshot",))

    def marker_open(self):
        self.events.append(("marker_open",))
        self.offset = 0
        return 500

    def walk_next(self, snapshot, marker):
        self.events.append(("walk_next",))
        if self.offset >= len(self.rows):
            return None
        result = self.rows[self.offset]
        self.offset += 1
        return result

    def marker_close(self, marker):
        self.events.append(("marker_close",))

    def duplicate(self, process, original):
        self.fail("unsafe foreign handle duplication called")

    def file_type(self, local):
        self.fail("unsafe foreign handle classification called")


class SocketSafeBoundaryTests(unittest.TestCase):
    def test_both_previous_entrypoints_refuse_before_any_native_activity(self):
        api = Fake()
        adapter = p.ScopedPssApiAdapter(api)
        with self.assertRaisesRegex(p.PssScopeError, "PSS_SOCKET_UNSAFE_DUPLICATION_BLOCKED"):
            adapter.collect_private_disk_candidates(pid=501, birth=300_000_000)
        with self.assertRaisesRegex(p.PssScopeError, "PSS_SOCKET_UNSAFE_DUPLICATION_BLOCKED"):
            adapter.collect_from_retained_original_process(
                process_handle=712, pid=501, birth=300_000_000,
                acquisition_rights=p.PROCESS_RIGHTS)
        self.assertEqual(api.events, [])

    def test_retained_query_only_or_bogus_rights_block_before_native_call(self):
        api = Fake()
        for rights in (0x1000, 0x40, 0xFFFF, True, None, "0x1040"):
            with self.subTest(rights=rights):
                with self.assertRaisesRegex(p.PssScopeError, "RETAINED_PROCESS_SCOPE"):
                    p.ScopedPssApiAdapter(api).collect_from_retained_original_process(
                        process_handle=712, pid=501, birth=300_000_000,
                        acquisition_rights=rights)
        self.assertEqual(api.events, [])

    def test_retained_invalid_original_process_values_block(self):
        for h, pid, birth in ((0, 501, 300_000_000),
                              (True, 501, 300_000_000),
                              (712, 0, 300_000_000),
                              (712, 501, True), (712, 501, 0)):
            api = Fake()
            with self.assertRaises(p.PssScopeError):
                p.ScopedPssApiAdapter(api).collect_from_retained_original_process(
                    process_handle=h, pid=pid, birth=birth,
                    acquisition_rights=p.PROCESS_RIGHTS)
            self.assertEqual(api.events, [])

    def test_passive_pss_inventory_never_classifies_file_as_safe_disk(self):
        api = Fake()
        adapter = p.ScopedPssApiAdapter(api)
        with adapter.open_verified_child(pid=501, birth=300_000_000) as proc:
            with adapter.snapshot(proc) as snap:
                inventory = adapter.inspect_private_pss_type_availability(snap)
        self.assertEqual(inventory.total_rows, 3)
        self.assertEqual(inventory.untyped_rows, 1)
        self.assertEqual(inventory.file_or_socket_ambiguous_rows, 1)
        self.assertEqual(inventory.known_nonfile_rows, 1)
        self.assertNotIn("31", repr(inventory))
        self.assertNotIn("32", str(inventory))
        self.assertFalse(hasattr(inventory, "handles"))
        self.assertEqual(api.events[-3:],
                         [("marker_close",), ("free_snapshot",),
                          ("close_process",)])

    def test_file_type_name_is_not_independent_regular_file_proof(self):
        api = Fake([{"handle": 31, "type_name": "File", "object_type": 0, "flags": 1}])
        adapter = p.ScopedPssApiAdapter(api)
        with adapter.open_verified_child(pid=501, birth=300_000_000) as proc:
            with adapter.snapshot(proc) as snap:
                inventory = adapter.inspect_private_pss_type_availability(snap)
        self.assertEqual(inventory.file_or_socket_ambiguous_rows, 1)
        self.assertFalse(hasattr(inventory, "disk_handles"))
        self.assertFalse(any(event[0] == "duplicate" for event in api.events))

    def test_minimal_pss_real_g214_untyped_shape_not_promoted(self):
        api = Fake([{"handle": 31, "type_name": "", "object_type": 0, "flags": 0}])
        adapter = p.ScopedPssApiAdapter(api)
        with adapter.open_verified_child(pid=501, birth=300_000_000) as proc:
            with adapter.snapshot(proc) as snap:
                inventory = adapter.inspect_private_pss_type_availability(snap)
        self.assertEqual(inventory.untyped_rows, 1)
        self.assertEqual(inventory.file_or_socket_ambiguous_rows, 0)
        self.assertFalse(hasattr(inventory, "handles"))

    def test_invalid_pss_rows_are_blocked_and_cleanup_still_runs(self):
        base = {"handle": 31, "type_name": "File", "object_type": 0, "flags": 1}
        bad = [
            [], [base, base], [dict(base, handle=True)], [dict(base, handle=0)],
            [dict(base, flags=2)], [dict(base, object_type=4)],
            [dict(base, flags=0)], [dict(base, flags=True)],
            [dict(base, object_name="private")],
            [dict(base, type_name="")],
            [dict(base, object_type=7)],
            [{"handle": i, "type_name": "", "object_type": 0, "flags": 0}
             for i in range(1, 258)],
        ]
        for rows in bad:
            with self.subTest(n=len(rows), example=str(rows[:1])[:50]):
                api = Fake(rows)
                adapter = p.ScopedPssApiAdapter(api)
                with self.assertRaises(p.PssScopeError):
                    with adapter.open_verified_child(pid=501, birth=300_000_000) as proc:
                        with adapter.snapshot(proc) as snap:
                            adapter.inspect_private_pss_type_availability(snap)
                self.assertEqual(api.events[-1], ("close_process",))
                self.assertIn(("free_snapshot",), api.events)

    def test_original_foreign_duplicate_api_no_longer_present(self):
        # Review the actual class AST, rather than comments containing names.
        source = Path(p.__file__).read_text(encoding="utf-8")
        tree = ast.parse(source)
        native = next(node for node in tree.body
                      if isinstance(node, ast.ClassDef) and node.name == "_Win32PssApi")
        methods = {node.name for node in native.body if isinstance(node, ast.FunctionDef)}
        self.assertNotIn("duplicate", methods)
        self.assertNotIn("file_type", methods)
        self.assertNotIn('"DuplicateHandle"', source)
        self.assertNotIn('"GetFileType"', source)
        self.assertFalse(hasattr(p._Win32PssApi, "duplicate"))

    def test_g215_generated_fixture_proof_remains_separate_from_original(self):
        root = Path(__file__).resolve().parents[1]
        code = (root / "qa/p4_native/g215_generated_duplicate_type.cpp").read_text(
            encoding="utf-8")
        workflow = (root / ".github/workflows/p4-r025-g215-generated-duplicate-type.yml"
                    ).read_text(encoding="utf-8")
        self.assertIn("GetCurrentProcess()", code)
        self.assertIn("FILE_FLAG_DELETE_ON_CLOSE", code)
        self.assertIn("    if: ${{ false }}", workflow)
        self.assertNotIn("    if: ${{ true }}", workflow)
        self.assertNotIn("OpenProcess(", code)

    def test_redacted_public_blocker_omits_private_handle_and_path(self):
        report = p.redacted_blocker("PSS_SOCKET_UNSAFE_DUPLICATION_BLOCKED")
        self.assertEqual(report["status"], "BLOCKED")
        self.assertEqual(report["blocker"], "PSS_SOCKET_UNSAFE_DUPLICATION_BLOCKED")
        self.assertEqual(report["native_N12_acceptance"], "NOT_EVALUATED")
        self.assertFalse(report["owner_native_execution_authorized"])
        payload = json.dumps(report)
        self.assertNotIn("31", payload)
        self.assertNotIn("501", payload)
        self.assertNotIn("C:/owner/", payload)

    def test_observer_stays_query_only_and_no_new_native_workflow(self):
        root = Path(__file__).resolve().parents[1]
        helper = (root / "qa/p4_native/n12_lifetime_control.py").read_text(
            encoding="utf-8")
        observer = (root / "qa/p4_research/n12_no_cdp_child_handles.py").read_text(
            encoding="utf-8")
        self.assertIn("open_process(0x1000, False, pid)", helper)
        self.assertIn("open_process_query_handle", observer)
        self.assertNotIn("open_process_query_dup_handle", observer)


if __name__ == "__main__":
    unittest.main()
