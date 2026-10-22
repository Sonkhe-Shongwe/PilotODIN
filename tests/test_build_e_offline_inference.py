"""Build E: fail-closed bundled local AI adapter; no external AI or downloads."""
from __future__ import annotations

from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
from threading import Thread

import pytest

from backend import bundled_inference, ai_provider
from desktop.verify_inference_assets import verify


@contextmanager
def local_fake_inference():
    hits = []

    class Stub(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_GET(self):
            hits.append((self.path, self.headers.get('Authorization')))
            if self.headers.get('Authorization') != 'Bearer test-' + 't' * 60:
                self.send_response(401)
                self.end_headers()
                return
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            if self.path == '/health':
                self.wfile.write(b'{"status":"ok"}')
            elif self.path == '/v1/models':
                self.wfile.write(json.dumps({'data':[{'id': bundled_inference.MODEL_ALIAS}]}).encode())
            else:
                self.wfile.write(b'{}')

        def do_POST(self):
            hits.append((self.path, self.headers.get('Authorization')))
            data=json.loads(self.rfile.read(int(self.headers.get('Content-Length', 0))))
            assert self.path == '/v1/chat/completions'
            assert data['model'] == bundled_inference.MODEL_ALIAS
            assert len(data['messages']) == 2
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(b'{"choices":[{"message":{"content":"Local answer, based on supplied facts."},"finish_reason":"stop"}]}')

    server = ThreadingHTTPServer(('127.0.0.1', 0), Stub)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server.server_port, hits
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)


def test_bundled_runtime_requires_desktop_session(monkeypatch):
    monkeypatch.delenv('PILOTODIN_DESKTOP_SESSION', raising=False)
    monkeypatch.setenv('PILOTODIN_BUNDLED_LLM_PORT', '13456')
    monkeypatch.setenv('PILOTODIN_BUNDLED_LLM_TOKEN', 'abc' * 20)
    assert bundled_inference.status()['status'] == 'not_configured'
    with pytest.raises(RuntimeError):
        bundled_inference.generate('sys', 'user', 5)


def test_rejects_non_numeric_and_invalid_loopback_port(monkeypatch):
    monkeypatch.setenv('PILOTODIN_DESKTOP_SESSION', 'secret' * 10)
    monkeypatch.setenv('PILOTODIN_BUNDLED_LLM_TOKEN', 't' * 50)
    for bad in ['https://example.com', '-1', '0', '100000', ' 12345']:
        monkeypatch.setenv('PILOTODIN_BUNDLED_LLM_PORT', bad)
        with pytest.raises(RuntimeError):
            bundled_inference._configuration()


def test_rejects_remote_or_unsupported_inference_routes(monkeypatch):
    monkeypatch.setenv('PILOTODIN_DESKTOP_SESSION', 'session-' + 'a' * 64)
    monkeypatch.setenv('PILOTODIN_BUNDLED_LLM_PORT', '12345')
    monkeypatch.setenv('PILOTODIN_BUNDLED_LLM_TOKEN', 'test-' + 't' * 60)
    for route in ('http://evil.test/v1/models', '/execute', '/v1/../../admin', '/completion'):
        with pytest.raises(ValueError):
            bundled_inference._request(route)


def test_real_http_contract_requires_session_secret_and_correct_alias(monkeypatch):
    with local_fake_inference() as (port, calls):
        monkeypatch.setenv('PILOTODIN_DESKTOP_SESSION', 'a' * 64)
        monkeypatch.setenv('PILOTODIN_BUNDLED_LLM_PORT', str(port))
        monkeypatch.setenv('PILOTODIN_BUNDLED_LLM_TOKEN', 'test-' + 't' * 60)
        monkeypatch.setenv('HTTP_PROXY','http://127.0.0.1:1')
        assert bundled_inference.status()['status'] == 'ready'
        answer, incomplete, reason = bundled_inference.generate('sys', 'data', 10)
        assert answer == 'Local answer, based on supplied facts.'
        assert incomplete is False and reason == 'stop'
        assert [route for route,_ in calls] == ['/health','/v1/models','/health','/v1/models','/v1/chat/completions']
        assert all(header == 'Bearer test-' + 't' * 60 for _,header in calls)
        assert 'token' not in str(bundled_inference.status())


def test_production_ai_uses_bundle_not_installed_ollama(monkeypatch):
    with local_fake_inference() as (port, _):
        monkeypatch.setenv('PILOTODIN_DESKTOP_SESSION', 'b' * 64)
        monkeypatch.setenv('PILOTODIN_BUNDLED_LLM_PORT', str(port))
        monkeypatch.setenv('PILOTODIN_BUNDLED_LLM_TOKEN', 'test-' + 't' * 60)
        monkeypatch.setattr(ai_provider, '_read_config', lambda: {**ai_provider.DEFAULTS, 'intelligence_mode':'local'})
        def forbidden(*args,**kwargs):
            raise AssertionError('Desktop must never silently use an existing Ollama process')
        monkeypatch.setattr(ai_provider, '_call_ollama', forbidden)
        result = ai_provider.respond({'row_count':20},'assistant','What is the result?','fallback')
        assert result['provider'] == 'bundled' and result['source'] == 'local_llm'
        assert result['model'] == bundled_inference.MODEL_ALIAS


def test_missing_bundle_falls_back_to_deterministic_analysis_not_ollama(monkeypatch):
    monkeypatch.setenv('PILOTODIN_DESKTOP_SESSION', 'b' * 64)
    monkeypatch.delenv('PILOTODIN_BUNDLED_LLM_PORT', raising=False)
    monkeypatch.delenv('PILOTODIN_BUNDLED_LLM_TOKEN', raising=False)
    monkeypatch.setattr(ai_provider, '_read_config', lambda: {**ai_provider.DEFAULTS, 'intelligence_mode':'local'})
    monkeypatch.setattr(ai_provider, '_call_ollama', lambda *args: (_ for _ in ()).throw(AssertionError('No Ollama')))
    result=ai_provider.respond({},'assistant','question','verified fallback')
    assert result['answer']=='verified fallback'
    assert result['source']=='local_computed_rules'


def test_bundle_preflight_refuses_missing_model(tmp_path):
    with pytest.raises(ValueError, match='not staged'):
        verify(tmp_path)


def test_bundle_preflight_rejects_wrong_hashes(tmp_path):
    root=tmp_path / 'project'
    model_dir=root/'frontend'/'src-tauri'/'resources'/'models'
    model_dir.mkdir(parents=True)
    bin_dir=root/'frontend'/'src-tauri'/'binaries'
    bin_dir.mkdir(parents=True)
    (bin_dir/'pilotodin-inference-x86_64-pc-windows-msvc.exe').write_bytes(b'untrusted')
    (model_dir/'qwen3-1.7b-q4_k_m.gguf').write_bytes(b'fake-model')
    (model_dir/'model-manifest.json').write_text(json.dumps({
        'model_file':'qwen3-1.7b-q4_k_m.gguf','model_alias':'pilotodin-qwen3-1.7b',
        'model_sha256':'0'*64,'server_sha256':'0'*64,'runtime_dll_sha256':{}
    }))
    with pytest.raises(ValueError, match='small'):
        verify(root)


def test_bundle_preflight_accepts_verified_offline_assets(tmp_path):
    import hashlib
    root = tmp_path / 'pilotodin'
    root_model = root / 'frontend' / 'src-tauri' / 'resources' / 'models'
    root_binary = root / 'frontend' / 'src-tauri' / 'binaries'
    root_dlls = root / 'frontend' / 'src-tauri' / 'resources' / 'llama-runtime'
    for folder in (root_model, root_binary, root_dlls):
        folder.mkdir(parents=True)
    model = root_model / 'qwen3-1.7b-q4_k_m.gguf'
    # Sparse synthetic fixture is deliberately not a real redistributable model.
    with model.open('wb') as handle:
        handle.truncate(10_000_001)
    exe = root_binary / 'pilotodin-inference-x86_64-pc-windows-msvc.exe'
    exe.write_bytes(b'fake-inference')
    dll = root_dlls / 'mock.dll'
    dll.write_bytes(b'fake-dll')
    digest=lambda b: hashlib.sha256(b).hexdigest()
    model_digest=hashlib.sha256(model.read_bytes()).hexdigest()
    (root_model/'model-manifest.json').write_text(json.dumps({
        'model_file': 'qwen3-1.7b-q4_k_m.gguf',
        'model_alias': bundled_inference.MODEL_ALIAS,
        'model_sha256': model_digest,
        'server_sha256': digest(exe.read_bytes()),
        'runtime_dll_sha256': {'mock.dll': digest(dll.read_bytes())},
    }))
    verify(root)
    dll.write_bytes(b'corrupted')
    with pytest.raises(ValueError, match='DLL checksum'):
        verify(root)


def test_desktop_status_is_idle_without_loading_model(monkeypatch):
    monkeypatch.setenv('PILOTODIN_DESKTOP_SESSION', 'session-' + 'z'*55)
    monkeypatch.setenv('PILOTODIN_BUNDLED_LLM_PORT', '19391')
    monkeypatch.setenv('PILOTODIN_BUNDLED_LLM_TOKEN', 't'*64)
    def unreachable(*args,**kwargs):
        raise OSError('Worker intentionally not loaded')
    monkeypatch.setattr(bundled_inference,'_request',unreachable)
    assert bundled_inference.status()['status']=='idle'
    assert ai_provider.test_local_connection()['status']=='idle'
