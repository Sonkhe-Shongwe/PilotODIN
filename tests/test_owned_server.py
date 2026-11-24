"""Owned server admission and fixed shutdown protocol on generated fixtures."""
from pathlib import Path
import os
import subprocess
import sys
import tempfile
from threading import Thread
from types import SimpleNamespace
import unittest

from backend.desktop_runner import SHUTDOWN_REQUEST, _watch_desktop_pipe
from backend.server_entry import ROOT, admitted_home
from backend.workspace_boundary import WorkspaceBoundaryError, engine_workspace


class OwnedServerTests(unittest.TestCase):
    def test_dev_home_is_exact_and_explicit(self):
        env = {"PILOTODIN_SERVER_MODE": "dev",
               "PILOTODIN_HOME": str(ROOT / ".pilotodin-dev-data")}
        self.assertEqual(admitted_home(env), ROOT / ".pilotodin-dev-data")
        for changes in ({"PILOTODIN_HOME": str(ROOT / "data")},
                        {"PILOTODIN_SERVER_MODE": ""},
                        {"PILOTODIN_DESKTOP_SESSION": "secret"}):
            with self.assertRaises(WorkspaceBoundaryError):
                admitted_home({**env, **changes})

    def test_hosted_home_scope_and_competing_writer_before_import(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            home = root / "pilotodin-p1-real-http-123"
            env = {**os.environ, "PILOTODIN_SERVER_MODE": "hosted-fixture",
                   "PILOTODIN_HOME": str(home), "PILOTODIN_DESKTOP_SESSION": "",
                   "CI": "true", "GITHUB_ACTIONS": "true", "GITHUB_RUN_ID": "123",
                   "RUNNER_TEMP": str(root)}
            self.assertEqual(admitted_home(env), home)
            for invalid in ({"GITHUB_RUN_ID": "456"}, {"CI": "false"},
                            {"PILOTODIN_HOME": str(root / "other")}):
                with self.assertRaises(WorkspaceBoundaryError):
                    admitted_home({**env, **invalid})
            with engine_workspace(str(home)):
                code = ("from backend.server_entry import owned_app; "
                        "owned_app()")
                result = subprocess.run([sys.executable, "-B", "-c", code],
                    cwd=ROOT, env=env, capture_output=True, text=True, timeout=10)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("Workspace already in use", result.stderr)
                self.assertFalse((home / "pilotodin.sqlite3").exists())
                self.assertFalse((home / "datasets").exists())

    def test_local_devqa_seed_to_owned_app_and_competing_writer(self):
        from tools.qa_foundation import create_run
        from backend.server_entry import LOCAL_FIXTURES
        from backend.workspace_boundary import LOCK_NAME
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp).resolve()
            phase = "P3-NATIVE-SEMANTIC-CONTEXT"
            run, _ = create_run(base / "PilotODIN" / "DevQA", phase, repo=ROOT)
            home = run / "workspace"
            filename, _, _ = LOCAL_FIXTURES[phase]
            seed = run / "fixtures" / filename
            env = {**os.environ, "LOCALAPPDATA": str(base),
                   "PILOTODIN_SERVER_MODE": "local-devqa",
                   "PILOTODIN_HOME": str(home), "PILOTODIN_DESKTOP_SESSION": ""}
            # The allocator alone must not admit a server before seeding.
            with self.assertRaises(WorkspaceBoundaryError):
                admitted_home(env)
            result = subprocess.run(
                [sys.executable, "-B", str(ROOT / "tools" / "Seed_P3_Native_Semantic_Context_Local.py"), str(seed)],
                cwd=ROOT, env=env, capture_output=True, text=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(admitted_home(env), home)
            self.assertTrue((home / LOCK_NAME).is_file())
            for invalid in ({"LOCALAPPDATA": str(base / "other")},
                            {"PILOTODIN_HOME": str(run / "fixtures")},
                            {"PILOTODIN_DESKTOP_SESSION": "secret"}):
                with self.assertRaises(WorkspaceBoundaryError):
                    admitted_home({**env, **invalid})
            code = ("from backend.server_entry import owned_app; "
                    "owned_app(); from backend import storage; "
                    "assert len(storage.list_projects()) == 2")
            with engine_workspace(str(home)):
                result = subprocess.run([sys.executable, "-B", "-c", code],
                    cwd=ROOT, env=env, capture_output=True, text=True, timeout=20)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("Workspace already in use", result.stderr)
            result = subprocess.run([sys.executable, "-B", "-c", code],
                cwd=ROOT, env=env, capture_output=True, text=True, timeout=20)
            self.assertEqual(result.returncode, 0, result.stderr)
            seed.write_text("{}", encoding="utf-8")
            with self.assertRaises(WorkspaceBoundaryError):
                admitted_home(env)

    def test_local_qa_launchers_use_owned_factory_and_restore_mode(self):
        for name in ("Run_P2_Native_Deliver_Consent_Local.ps1",
                     "Run_P2_Native_Two_Window_Local.ps1",
                     "Run_P3_Native_Semantic_QA_Local.ps1",
                     "Run_P3_Native_Quality_W5_QA_Local.ps1"):
            with self.subTest(name=name):
                source = (ROOT / "tools" / name).read_text(encoding="utf-8")
                self.assertIn("'PILOTODIN_SERVER_MODE'", source)
                self.assertIn("$env:PILOTODIN_SERVER_MODE='local-devqa'", source)
                self.assertIn("'backend.server_entry:owned_app','--factory'", source)
                self.assertNotIn("'backend.main:app'", source)

    def test_managed_report_chain_seed_and_owned_server_handoff(self):
        import json
        from tools.qa_foundation import create_run
        from backend.server_entry import report_chain_seed_home
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp).resolve()
            run, _ = create_run(base / "PilotODIN" / "DevQA", "P2-NATIVE-CHAIN", repo=ROOT)
            home = run / "workspace"
            manifest = home / "synthetic-manifest.json"
            env = {**os.environ, "LOCALAPPDATA": str(base),
                   "PILOTODIN_SERVER_MODE": "local-devqa", "RL_invariant": "1",
                   "PILOTODIN_HOME": str(home), "PILOTODIN_DESKTOP_SESSION": ""}
            self.assertEqual(report_chain_seed_home(env), home)
            with self.assertRaises(WorkspaceBoundaryError):
                admitted_home(env)
            for change in ({"PILOTODIN_HOME": str(base)}, {"RL_invariant": ""},
                           {"PILOTODIN_SERVER_MODE": ""}):
                with self.assertRaises(WorkspaceBoundaryError):
                    report_chain_seed_home({**env, **change})
            command = [sys.executable, "-B", str(ROOT / "tools" / "Seed_P2_Native_Live_Chain_Local.py")]
            result = subprocess.run(command + [str(base / "wrong.json")], cwd=ROOT,
                env=env, capture_output=True, text=True, timeout=30)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(list(home.iterdir()), [])
            result = subprocess.run(command + [str(manifest)], cwd=ROOT,
                env=env, capture_output=True, text=True, timeout=45)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual(admitted_home(env), home)
            record = json.loads(manifest.read_text(encoding="utf-8"))
            code = ("from backend.server_entry import owned_app; "
                    "from fastapi.testclient import TestClient; "
                    "import sys; client=TestClient(owned_app()); "
                    "assert client.get('/api/reports/'+sys.argv[1]+'?revision=2').status_code == 200")
            result = subprocess.run([sys.executable, "-B", "-c", code, record["report_id"]],
                cwd=ROOT, env=env, capture_output=True, text=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stderr)
            record["run_id"] = "other"
            manifest.write_text(json.dumps(record), encoding="utf-8")
            with self.assertRaises(WorkspaceBoundaryError):
                admitted_home(env)

    def test_retired_migration_and_unmanaged_launcher_fail_closed(self):
        from Migrate_From_Old_PilotODIN import migrate
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with self.assertRaisesRegex(ValueError, "retired"):
                migrate(root / "old", root / "new")
            self.assertEqual(list(root.iterdir()), [])
        legacy = (ROOT / "tools" / "Verify_P2_Native_Live_Report_Local.ps1").read_text(encoding="utf-8")
        self.assertNotIn("Start-Process", legacy)
        self.assertNotIn("backend.main:app", legacy)
        self.assertIn("exit 2", legacy)
        managed = (ROOT / "tools" / "Verify_P2_DevQA_Native_Chain_Local.ps1").read_text(encoding="utf-8")
        self.assertIn("'backend.server_entry:owned_app','--factory'", managed)
        self.assertIn("'PILOTODIN_SERVER_MODE'", managed)
        self.assertIn("$env:PILOTODIN_SERVER_MODE='local-devqa'", managed)
        self.assertNotIn("'backend.main:app'", managed)

    def test_legacy_desktop_migration_refuses_before_any_io(self):
        from desktop.Migrate_Existing_Workspace import migrate, main
        from contextlib import redirect_stderr
        from io import StringIO
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "old"
            target = root / "new"
            target.mkdir()
            marker = target / "keep.txt"
            marker.write_bytes(b"preserve")
            # Both entrypoints must refuse even without inspecting the paths.
            with patch.object(Path, "resolve", side_effect=AssertionError("unexpected path inspection")), \
                 patch.object(Path, "exists", side_effect=AssertionError("unexpected path inspection")):
                with self.assertRaisesRegex(ValueError, "suspended"):
                    migrate(source, target)
                with redirect_stderr(StringIO()):
                    self.assertEqual(main(), 2)
            self.assertEqual(marker.read_bytes(), b"preserve")
            self.assertFalse(source.exists())
            self.assertEqual(list(target.iterdir()), [marker])

    def test_owned_pipe_accepts_fragmented_stop_without_eof(self):
        server = SimpleNamespace(should_exit=False)
        rd, wr = os.pipe()
        thread = Thread(target=_watch_desktop_pipe, args=(server, rd), daemon=True)
        try:
            thread.start()
            os.write(wr, SHUTDOWN_REQUEST[:4])
            os.write(wr, SHUTDOWN_REQUEST[4:])
            thread.join(2)
            self.assertFalse(thread.is_alive())
            self.assertTrue(server.should_exit)
        finally:
            os.close(wr)
            thread.join(2)
            os.close(rd)

    def test_eof_or_invalid_pipe_is_fail_closed(self):
        for message in (b"", b"unexpected"):
            server = SimpleNamespace(should_exit=False)
            rd, wr = os.pipe()
            try:
                if message:
                    os.write(wr, message)
                os.close(wr)
                _watch_desktop_pipe(server, rd)
                self.assertTrue(server.should_exit)
            finally:
                os.close(rd)



class C3RequestTrustTests(unittest.TestCase):
    """Pure transport/header fixtures; no actual server, model or owner files."""

    def setUp(self):
        from backend.request_auth import RequestTrust
        self.secret = "a" * 64
        self.desktop = RequestTrust("desktop", 9012, self.secret)
        self.dev = RequestTrust("dev", 8000, "b" * 64, "http://127.0.0.1:5173")

    def scope(self, trust=None, method="GET", origin=None):
        trust = trust or self.desktop
        headers = [(b"host", f"127.0.0.1:{trust.port}".encode()),
                   (trust.header, trust.secret.encode())]
        if origin is not None:
            headers.append((b"origin", origin.encode()))
        return {"type": "http", "scheme": "http", "method": method,
                "client": ("127.0.0.1", 50000), "server": ("127.0.0.1", trust.port),
                "headers": headers}

    def test_c3_contract_is_explicit_immutable_and_secret_not_repr(self):
        from dataclasses import FrozenInstanceError
        from backend.request_auth import RequestTrust, authorize
        self.assertNotIn(self.secret, repr(self.desktop))
        with self.assertRaises(FrozenInstanceError):
            self.desktop.secret = "c" * 64
        for mode, port, secret, origin in (
                ("", 9012, self.secret, None), ("test", 9012, self.secret, None),
                ("desktop", 9012, "", None), ("desktop", 9012, "x" * 64, None),
                ("desktop", 9012, self.secret, "http://127.0.0.1:5173"),
                ("desktop", True, self.secret, None),
                ("dev", 8000, self.secret, None),
                ("dev", 8000, self.secret, "https://evil.example")):
            with self.subTest(mode=mode, port=port, origin=origin):
                with self.assertRaises(ValueError):
                    RequestTrust(mode, port, secret, origin)
        self.assertEqual(authorize(self.scope(), None).status, 503)

    def test_c3_transport_and_exact_origin(self):
        from backend.request_auth import authorize
        for origin in (None, "http://tauri.localhost", "https://tauri.localhost", "tauri://localhost"):
            self.assertTrue(authorize(self.scope(origin=origin), self.desktop).allowed)
        for changes in ({"client": ("192.0.2.1", 50000)},
                        {"client": ("testclient", 50000)}, {"client": None},
                        {"server": ("0.0.0.0", 9012)}, {"server": ("127.0.0.1", 8000)},
                        {"server": ("testserver", 80)}, {"scheme": "https"},
                        {"type": "websocket"}):
            with self.subTest(changes=changes):
                self.assertEqual(authorize({**self.scope(), **changes}, self.desktop).status, 403)
        for origin in ("null", "https://evil.example", "http://127.0.0.1:5173"):
            self.assertEqual(authorize(self.scope(origin=origin), self.desktop).status, 403)
        self.assertTrue(authorize(self.scope(self.dev, origin=self.dev.dev_origin), self.dev).allowed)
        self.assertEqual(authorize(self.scope(self.dev, origin="http://127.0.0.1:5174"), self.dev).status, 403)
        self.assertEqual(authorize(self.scope(self.dev, origin="http://tauri.localhost"), self.dev).status, 403)

    def test_c3_missing_wrong_duplicate_and_malformed_credentials(self):
        from backend.request_auth import authorize
        original = self.scope()
        host, token = original["headers"]
        for headers, status in (
                ([host], 401), ([host, (token[0], b"b"*64)], 401),
                ([host, (token[0], b"")], 401), ([host, (token[0], b"\xff")], 400),
                ([host, (token[0], b" "+token[1])], 400),
                ([host, (token[0], b"a"*257)], 400), ([host, token, token], 400),
                ([host, token, (b"X-PilotODIN-Session", token[1])], 400),
                ([host, token, (b"x-pilotodin-dev-capability", b"b"*64)], 401),
                ([token], 403), ([host, host, token], 400),
                ([(b"host", b"testserver"), token], 403),
                ([(b"host", b"127.0.0.1:8000"), token], 403),
                ([(b"host", b"localhost.evil:9012"), token], 403),
                ([host, token, (b"origin", b"http://tauri.localhost"),
                  (b"origin", b"http://tauri.localhost")], 400),
                ([host, token, (b"x-forwarded-for", b"127.0.0.1")], 403),
                ([host, token, (b"forwarded", b"for=127.0.0.1")], 403)):
            with self.subTest(status=status):
                self.assertEqual(authorize({**original, "headers": headers}, self.desktop).status, status)

    def test_c3_preflight_is_only_bounded_cors_negotiation(self):
        from backend.request_auth import authorize
        for trust, origin in ((self.desktop, "http://tauri.localhost"),
                              (self.dev, self.dev.dev_origin)):
            raw = self.scope(trust, "OPTIONS", origin)
            raw["headers"] = [pair for pair in raw["headers"] if pair[0] != trust.header]
            raw["headers"] += [(b"access-control-request-method", b"POST"),
                               (b"access-control-request-headers", b"content-type, "+trust.header)]
            decision = authorize(raw, trust)
            self.assertTrue(decision.allowed)
            self.assertTrue(decision.preflight)
            self.assertFalse(authorize({**raw, "method": "POST"}, trust).allowed)
            for headers in (
                    raw["headers"][:-1],
                    raw["headers"][:-1] + [(b"access-control-request-headers", b"content-type")],
                    raw["headers"][:-1] + [(b"access-control-request-headers", trust.header+b", x-extra")],
                    raw["headers"][:-1] + [(b"access-control-request-headers", trust.header+b", "+trust.header)],
                    raw["headers"][:-2] + [(b"access-control-request-method", b"CONNECT"), raw["headers"][-1]],
                    raw["headers"] + [(trust.header, trust.secret.encode())],
                    [pair for pair in raw["headers"] if pair[0] != b"origin"]):
                self.assertFalse(authorize({**raw, "headers": headers}, trust).allowed)

    def test_c3_all_actual_methods_require_capability(self):
        from backend.request_auth import RequestTrust, authorize
        for mode in ("dev", "hosted-fixture", "local-devqa"):
            trust = RequestTrust(mode, 8000, "b"*64, "http://127.0.0.1:5178")
            for method in ("GET", "POST", "PUT", "PATCH", "DELETE", "HEAD"):
                scope = self.scope(trust, method, trust.dev_origin)
                with self.subTest(mode=mode, method=method):
                    self.assertTrue(authorize(scope, trust).allowed)
                    self.assertEqual(authorize({**scope, "headers": [scope["headers"][0], scope["headers"][2]]}, trust).status, 401)


if __name__ == "__main__":
    unittest.main()
