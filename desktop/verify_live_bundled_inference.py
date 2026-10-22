"""Run the real pinned Windows llama.cpp/Qwen3 runtime without any network access.

This check is invoked only on the Windows release builder after asset staging.
It validates the localhost API, session authentication, model load and a real
chat completion. It does NOT certify long-session use or 8 GB performance.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import secrets
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request

from verify_inference_assets import verify


def port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(('127.0.0.1', 0))
        return int(sock.getsockname()[1])


def send(url: str, token: str | None = None, body: dict | None = None, timeout: float = 5):
    headers = {'Content-Type': 'application/json'}
    if token:
        headers['Authorization'] = f'Bearer {token}'
    payload = json.dumps(body).encode('utf-8') if body is not None else None
    request = urllib.request.Request(url, data=payload, headers=headers,
                                     method='POST' if body is not None else 'GET')
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status, json.loads(response.read(4 * 1024 * 1024))
    except urllib.error.HTTPError as err:
        return err.code, json.loads(err.read(256 * 1024))


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    verify(root)
    tauri = root / 'frontend' / 'src-tauri'
    model = tauri / 'resources' / 'models' / 'qwen3-1.7b-q4_k_m.gguf'
    runtime = tauri / 'binaries' / 'pilotodin-inference-x86_64-pc-windows-msvc.exe'
    dlls = tauri / 'resources' / 'llama-runtime'
    listen_port = port()
    token = secrets.token_hex(32)
    env = os.environ.copy()
    env['LLAMA_API_KEY'] = token
    env['PATH'] = os.pathsep.join((str(dlls), env.get('PATH', '')))
    args = [str(runtime), '--model', str(model), '--alias', 'pilotodin-qwen3-1.7b',
            '--host', '127.0.0.1', '--port', str(listen_port), '--ctx-size', '2048',
            '--threads', '2', '--parallel', '1', '--gpu-layers', '0',
            '--no-webui', '--no-agent']
    flags = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
    proc = subprocess.Popen(args, cwd=root, env=env, stdin=subprocess.DEVNULL,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                            creationflags=flags)
    base = f'http://127.0.0.1:{listen_port}'
    try:
        deadline = time.monotonic() + 150
        while time.monotonic() < deadline:
            if proc.poll() is not None:
                raise RuntimeError(f'Qwen3 server exited during model load ({proc.returncode})')
            try:
                code, result = send(base + '/health', token, timeout=3)
                if code == 200 and isinstance(result, dict) and result.get('status') == 'ok':
                    break
            except (OSError, TimeoutError, ValueError):
                pass
            time.sleep(0.6)
        else:
            raise RuntimeError('Local GGUF did not become healthy within 150 seconds')
        unauthenticated_probe = {
            'model': 'pilotodin-qwen3-1.7b',
            'messages': [{'role': 'user', 'content': 'Ping'}],
            'max_tokens': 1, 'stream': False,
        }
        if send(base + '/v1/chat/completions', body=unauthenticated_probe, timeout=5)[0] != 401:
            raise RuntimeError('Local inference API failed to reject unauthenticated generation')
        status, result = send(base + '/v1/chat/completions', token,
                              {'model': 'pilotodin-qwen3-1.7b',
                               'messages': [{'role': 'user', 'content': 'Respond with READY.'}],
                               'max_tokens': 24, 'temperature': 0, 'stream': False}, timeout=110)
        if status != 200 or not isinstance(result, dict) or not result.get('choices'):
            raise RuntimeError(f'Bundled Qwen3 failed authenticated text generation: HTTP {status}')
        print('LIVE OFFLINE AI CHECK PASSED: Qwen3 GGUF loaded, llama.cpp served locally, authentication enforced, completion returned')
        return 0
    except (OSError, ValueError, RuntimeError) as exc:
        print(f'LIVE OFFLINE AI CHECK FAILED: {exc}', file=sys.stderr)
        return 1
    finally:
        if os.name == 'nt' and proc.poll() is None:
            subprocess.run(['taskkill', '/PID', str(proc.pid), '/T', '/F'],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                           creationflags=subprocess.CREATE_NO_WINDOW, timeout=15, check=False)
        if proc.poll() is None:
            proc.terminate()
        try:
            proc.wait(timeout=8)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=8)


if __name__ == '__main__':
    raise SystemExit(main())
