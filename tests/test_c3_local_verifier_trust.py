"""Source/synthetic C3 regressions; no native visual or frozen-engine launch."""
from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
from unittest.mock import Mock, patch

import pytest

from tools.qa_foundation import create_run

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "desktop" / "verify_packaged_engine.py"
SPEC = importlib.util.spec_from_file_location("c3_packaged_verifier", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
verifier = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(verifier)


def test_smoke_direct_loopback_ignores_ambient_proxy(monkeypatch):
    monkeypatch.setenv("HTTP_PROXY", "http://invalid.example:3128")
    monkeypatch.setenv("ALL_PROXY", "http://invalid.example:3128")
    monkeypatch.setenv("NO_PROXY", "")
    response = Mock(status=200)
    response.read.return_value = b'{"status":"ok"}'
    conn = Mock()
    conn.getresponse.return_value = response
    headers = {"X-PilotODIN-Session": "a" * 64, "Origin": "http://tauri.localhost"}
    with patch.object(verifier.http.client, "HTTPConnection", return_value=conn) as connect:
        assert verifier._request(18042, "/api/health", headers) == (200, {"status": "ok"})
    connect.assert_called_once_with("127.0.0.1", 18042, timeout=3)
    conn.request.assert_called_once_with("GET", "/api/health", headers=headers)
    conn.close.assert_called_once()


@pytest.mark.parametrize("status", (301, 302, 303, 307, 308))
def test_smoke_never_follows_redirect(status):
    response = Mock(status=status)
    response.getheader.return_value = "http://invalid.example/api/health"
    conn = Mock()
    conn.getresponse.return_value = response
    with patch.object(verifier.http.client, "HTTPConnection", return_value=conn) as connect:
        with pytest.raises(RuntimeError, match="redirect"):
            verifier._request(18042, "/api/health", {"X-PilotODIN-Session": "a" * 64})
    connect.assert_called_once()
    conn.request.assert_called_once()
    response.read.assert_not_called()
    conn.close.assert_called_once()


@pytest.mark.parametrize("port,path,headers", (
    (True, "/api/health", {}), (80, "/api/health", {}),
    (65536, "/api/health", {}), (18042, "http://invalid.example/api/health", {}),
    (18042, "//invalid.example/api/health", {}), (18042, "/api/health?x=1", {}),
    (18042, "/api/projects", {"Host": "invalid.example"}),
    (18042, "/api/health", {"X-PilotODIN-Dev-Capability": "a" * 64}),
))
def test_smoke_refuses_destination_and_header_overrides_before_connection(port, path, headers):
    with patch.object(verifier.http.client, "HTTPConnection") as connect:
        with pytest.raises(ValueError):
            verifier._request(port, path, headers)
    connect.assert_not_called()


@pytest.mark.parametrize("body,error", ((b"x" * (1024 * 1024 + 1), "limit"),
                                        (b"not JSON", "invalid smoke JSON")))
def test_smoke_refuses_unbounded_or_invalid_response(body, error):
    response = Mock(status=200)
    response.read.return_value = body
    conn = Mock()
    conn.getresponse.return_value = response
    with patch.object(verifier.http.client, "HTTPConnection", return_value=conn):
        with pytest.raises(RuntimeError, match=error):
            verifier._request(18042, "/api/projects")
    response.read.assert_called_once_with(1024 * 1024 + 1)
    conn.close.assert_called_once()


def test_smoke_preserves_negative_auth_status():
    response = Mock(status=401)
    response.read.return_value = b'{"detail":"denied"}'
    conn = Mock()
    conn.getresponse.return_value = response
    with patch.object(verifier.http.client, "HTTPConnection", return_value=conn):
        assert verifier._request(18042, "/api/health") == (401, {"detail": "denied"})
    conn.close.assert_called_once()


def test_smoke_child_configuration_excludes_inherited_application_flags(tmp_path):
    parent = {"PATH": "unchanged", "PILOTODIN_HOME": "unrelated",
              "pilotodin_dev_capability": "foreign", "PILOTODIN_SERVER_MODE": "dev",
              "PILOTODIN_CONTROL_MODE": "pod1", "PILOTODIN_CONTROL_CAPABILITY": "foreign",
              "PILOTODIN_BUNDLED_LLM_PORT": "18000", "PILOTODIN_BUNDLED_LLM_TOKEN": "foreign",
              "VITE_PILOTODIN_AUTH_DEV": "1", "PILOTODIN_DESKTOP_SESSION": "foreign"}
    original = parent.copy()
    assert verifier._smoke_environment(parent, tmp_path, 18042, "a" * 64) == {
        "PATH": "unchanged", "PILOTODIN_HOME": str(tmp_path),
        "PILOTODIN_DESKTOP_SESSION": "a" * 64, "PILOTODIN_DESKTOP_PORT": "18042",
        "PILOTODIN_DESKTOP_WATCH_STDIN": "1", "PILOTODIN_DESKTOP_ALLOW_DEV": "0",
    }
    assert parent == original


@pytest.mark.parametrize("dirty", (False, True))
def test_legacy_visual_helper_uses_owned_guard_without_running_owner_main(tmp_path, dirty):
    run, _ = create_run(tmp_path / "devqa", "P2-LEGACY-PDF-VISUAL", repo=ROOT)
    home = run / "workspace"
    if dirty:
        (home / "preserve.txt").write_bytes(b"untouched")
    env = {key: value for key, value in os.environ.items()
           if not key.upper().startswith(("PILOTODIN_", "VITE_PILOTODIN_"))}
    env["PILOTODIN_HOME"] = str(home)
    script = r"""
import sys
from pathlib import Path
from tools.Run_P2_Legacy_PDF_Visual_Local import _visual_client, CSV
from backend.workspace_boundary import WorkspaceBoundaryError
home = Path(sys.argv[1])
if sys.argv[2] == "dirty":
    try:
        _visual_client(home)
    except WorkspaceBoundaryError:
        assert "backend.main" not in sys.modules
        assert (home / "preserve.txt").read_bytes() == b"untouched"
        assert sorted(p.name for p in home.iterdir()) == ["preserve.txt"]
    else:
        raise AssertionError("dirty workspace accepted")
else:
    client = _visual_client(home)
    assert client.get("/api/health").status_code == 200
    assert client.get("/api/health", headers={"Origin": "http://127.0.0.1:5173"}).status_code == 403
    response = client.post("/api/projects", files={"file": ("synthetic.csv", CSV, "text/csv")})
    assert response.status_code == 201
    from backend import storage
    source = Path(storage.get_project(response.json()["id"])["dataset_path"]).resolve()
    assert source.is_relative_to(home.resolve() / "datasets") and source.read_bytes() == CSV
    del client.headers["X-PilotODIN-Dev-Capability"]
    assert client.get("/api/health").status_code == 401
    assert not any((home / "models").iterdir())
"""
    result = subprocess.run([sys.executable, "-B", "-c", script, str(home),
                             "dirty" if dirty else "fresh"], cwd=ROOT, env=env,
                            capture_output=True, text=True, timeout=45)
    assert result.returncode == 0, result.stdout + result.stderr
    assert not list((run / "exports").iterdir())
    assert not list((run / "diagnostics").iterdir())


def test_legacy_visual_owner_and_font_gates_are_preserved():
    source = (ROOT / "tools" / "Run_P2_Legacy_PDF_Visual_Local.py").read_text(encoding="utf-8")
    assert 'need(os.name == "nt", "Owner Windows is required")' in source
    assert 'not os.getenv("PILOTODIN_HOME") and not os.getenv("PILOTODIN_DESKTOP_SESSION")' in source
    assert 'RELEASE_APPROVAL_STATUS == "NOT_GRANTED"' in source
    assert 'RELEASE_PINNED_FILES == ()' in source
    assert 'RELEASE_APPROVAL_REFERENCE == ""' in source
    assert source.index("hold_fresh_fixture_workspace(str(home), canonical)") < source.index("from backend.main import app")
    assert source.index('RELEASE_APPROVAL_STATUS == "NOT_GRANTED"') < source.index('created = request(client')
    assert '"be_030_owner_visual": "PENDING"' in source
    assert 'os.startfile(pdf_path)' in source
    assert "TestClient(app)" not in source


# Only import definitions. Never run the real model diagnostic or asset verifier.
with patch.object(sys, "path", [str(ROOT / "desktop"), *sys.path]):
    import verify_live_bundled_inference as inference_verifier


@pytest.mark.parametrize("url,token,body", (
    ("http://example.invalid:18042/health", "a"*64, None),
    ("http://localhost:18042/health", "a"*64, None),
    ("http://127.0.0.1:08000/health", "a"*64, None),
    ("http://127.0.0.1:65536/health", "a"*64, None),
    ("http://127.0.0.1:80/health", "a"*64, None),
    ("http://127.0.0.1:18042/health?key=x", "a"*64, None),
    ("http://127.0.0.1:18042/execute", "a"*64, None),
    ("http://127.0.0.1:18042/health", None, None),
    ("http://127.0.0.1:18042/health", "a"*64, {}),
    ("http://127.0.0.1:18042/v1/chat/completions", "a"*64, None),
    ("http://127.0.0.1:18042/v1/chat/completions", "invalid", {}),
    ("http://127.0.0.1:18042/v1/chat/completions", "A"*64, {}),
))
def test_inference_diagnostic_refuses_invalid_configuration_before_connection(url, token, body):
    with patch.object(inference_verifier.http.client, "HTTPConnection") as connect:
        with pytest.raises(ValueError):
            inference_verifier.send(url, token, body)
    connect.assert_not_called()


@pytest.mark.parametrize("status", (301, 302, 303, 307, 308))
def test_inference_diagnostic_refuses_redirect_without_reading_response(status):
    response = Mock(status=status)
    conn = Mock()
    conn.getresponse.return_value = response
    with patch.object(inference_verifier.http.client, "HTTPConnection", return_value=conn) as connect:
        with pytest.raises(RuntimeError, match="redirect"):
            inference_verifier.send("http://127.0.0.1:18042/health", "a"*64)
    connect.assert_called_once_with("127.0.0.1", 18042, timeout=5)
    conn.request.assert_called_once_with("GET", "/health", body=None,
        headers={"Content-Type": "application/json", "Authorization": "Bearer " + "a"*64})
    response.read.assert_not_called()
    conn.close.assert_called_once()


@pytest.mark.parametrize("status,limit", ((200, 4*1024*1024), (401, 256*1024)))
def test_inference_diagnostic_bounded_response_and_negative_auth(status, limit, monkeypatch):
    monkeypatch.setenv("HTTP_PROXY", "http://invalid.example:3128")
    response = Mock(status=status)
    response.read.return_value = b'{"status":"synthetic"}'
    conn = Mock()
    conn.getresponse.return_value = response
    with patch.object(inference_verifier.http.client, "HTTPConnection", return_value=conn) as connect:
        assert inference_verifier.send("http://127.0.0.1:18042/v1/chat/completions", body={}) == (status, {"status": "synthetic"})
    connect.assert_called_once_with("127.0.0.1", 18042, timeout=5)
    conn.request.assert_called_once_with("POST", "/v1/chat/completions", body=b"{}",
        headers={"Content-Type": "application/json"})
    response.read.assert_called_once_with(limit+1)
    conn.close.assert_called_once()
    for raw, message in [(b"x"*(limit+1), "safety limit"), (b"not JSON", "Invalid local inference diagnostic JSON")]:
        response.read.return_value = raw
        with patch.object(inference_verifier.http.client, "HTTPConnection", return_value=conn):
            with pytest.raises(RuntimeError, match=message):
                inference_verifier.send("http://127.0.0.1:18042/v1/chat/completions", body={})


@pytest.mark.parametrize("status", (301, 302, 303, 307, 308, 401, 503))
def test_production_bundled_client_never_follows_worker_redirect_or_leaks_response(status, monkeypatch):
    # This is an inert, runner-owned loopback HTTP stub, not an inference worker.
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
    from threading import Thread
    import urllib.error
    from backend import bundled_inference

    hits = []
    class Stub(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_GET(self):
            hits.append((self.path, self.headers.get("Authorization")))
            if self.path != "/health":
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b'{"unexpected":true}')
                return
            self.send_response(status)
            self.send_header("Location", "/redirect-trap")
            self.end_headers()

    server = ThreadingHTTPServer(("127.0.0.1", 0), Stub)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        monkeypatch.setenv("PILOTODIN_DESKTOP_SESSION", "a"*64)
        monkeypatch.setenv("PILOTODIN_BUNDLED_LLM_PORT", str(server.server_port))
        monkeypatch.setenv("PILOTODIN_BUNDLED_LLM_TOKEN", "b"*64)
        monkeypatch.setenv("HTTP_PROXY", "http://invalid.example:3128")
        monkeypatch.setenv("ALL_PROXY", "http://invalid.example:3128")
        monkeypatch.setenv("NO_PROXY", "")
        with pytest.raises(urllib.error.HTTPError) as refused:
            bundled_inference._request("/health")
        assert refused.value.code == status
        assert refused.value.headers is None
        assert "redirect-trap" not in str(refused.value)
        assert hits == [("/health", "Bearer " + "b"*64)]
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)
