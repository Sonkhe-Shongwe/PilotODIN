"""Execute the real Windows desktop-engine binary and test its loopback boundary.

This gate must pass after PyInstaller and before any Windows installer is built.
It intentionally avoids loading an AI model or connecting to cloud services.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import secrets
import socket
import subprocess
import sys
import tempfile
import time
from typing import Sequence
import urllib.error
import urllib.request


def _unused_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(('127.0.0.1', 0))
        return int(sock.getsockname()[1])


def _request(url: str, headers: dict[str, str] | None = None) -> tuple[int, object]:
    request = urllib.request.Request(url, headers=headers or {})
    try:
        with urllib.request.urlopen(request, timeout=3) as response:
            return response.status, json.loads(response.read(1024 * 1024))
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read(1024 * 1024))


def smoke_test_engine(command: Sequence[str], root: Path, startup_seconds: float = 90) -> dict:
    """Return nonsecret observations or raise if a packaged/local runner misbehaves."""
    if not command or not all(isinstance(arg, str) and arg for arg in command):
        raise ValueError('Executable command must be specified')
    if not root.is_dir():
        raise ValueError('Source root not found')
    with tempfile.TemporaryDirectory(prefix='pilotodin-engine-smoke-') as sandbox:
        tmp = Path(sandbox)
        data_dir = tmp / 'isolated-user-data'
        port = _unused_port()
        token = secrets.token_hex(32)
        env = os.environ.copy()
        env.update({
            'PILOTODIN_DESKTOP_PORT': str(port),
            'PILOTODIN_DESKTOP_SESSION': token,
            'PILOTODIN_HOME': str(data_dir),
            'PILOTODIN_DESKTOP_ALLOW_DEV': '0',
        })
        for key in ('PILOTODIN_BUNDLED_LLM_PORT', 'PILOTODIN_BUNDLED_LLM_TOKEN'):
            env.pop(key, None)
        url = f'http://127.0.0.1:{port}'
        creationflags = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
        child = subprocess.Popen(list(command), cwd=root, env=env,
                                 stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                 stderr=subprocess.DEVNULL, creationflags=creationflags)
        try:
            deadline = time.monotonic() + startup_seconds
            while True:
                if child.poll() is not None:
                    raise RuntimeError(f'Desktop engine stopped before health readiness (exit={child.returncode})')
                try:
                    code, _ = _request(url + '/api/health')
                    if code == 401:
                        break
                    if code == 200:
                        raise RuntimeError('Unauthenticated desktop engine health request succeeded')
                except (ConnectionError, TimeoutError, OSError, urllib.error.URLError):
                    pass
                if time.monotonic() >= deadline:
                    raise RuntimeError('Desktop engine did not become reachable in time')
                time.sleep(0.2)
            valid = {'X-PilotODIN-Session': token, 'Origin': 'http://tauri.localhost'}
            if _request(url + '/api/health', {'X-PilotODIN-Session': 'invalid'})[0] != 401:
                raise RuntimeError('Desktop session rejected wrong token incorrectly')
            status, health = _request(url + '/api/health', valid)
            if status != 200 or not isinstance(health, dict) or health.get('status') != 'ok':
                raise RuntimeError('Authenticated health check was not successful')
            if _request(url + '/api/health', {**valid, 'Origin': 'https://untrusted.example'})[0] != 403:
                raise RuntimeError('Desktop API incorrectly accepted untrusted origin')
            code, projects = _request(url + '/api/projects', valid)
            if code != 200 or not isinstance(projects, list):
                raise RuntimeError('Authenticated project listing failed')
            if not (data_dir / 'pilotodin.sqlite3').is_file() or not (data_dir / 'datasets').is_dir():
                raise RuntimeError('Persistent local user data was not initialized in the designated directory')
            if child.poll() is not None:
                raise RuntimeError('Desktop engine died after the health check')
            return {'passed': True, 'auth_required': True, 'wrong_origin_rejected': True,
                    'user_storage_isolated': True, 'model_started': False}
        except Exception as error:
            raise RuntimeError(f'Packaged engine smoke verification failed: {error}; '
                               f'check process startup and configuration') from error
        finally:
            # PyInstaller --onefile starts a child process on Windows. Killing
            # only the bootloader parent can leave that child running.
            # Terminate the entire tree before deleting sandbox data.
            if os.name == 'nt' and child.poll() is None:
                subprocess.run(['taskkill', '/PID', str(child.pid), '/T', '/F'],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                               timeout=15, check=False,
                               creationflags=subprocess.CREATE_NO_WINDOW)
            if child.poll() is None:
                child.terminate()
            try:
                child.wait(timeout=8)
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait(timeout=8)


def main() -> int:
    parser = argparse.ArgumentParser(description='Prove real desktop analytics engine can launch offline')
    parser.add_argument('--exe', required=True, type=Path)
    parser.add_argument('--startup-seconds', type=float, default=90)
    parser.add_argument('--result-json', type=Path)
    args = parser.parse_args()
    if not args.exe.is_file():
        parser.error(f'Packaged executable does not exist: {args.exe}')
    if not 5 <= args.startup_seconds <= 240:
        parser.error('startup-seconds must be between 5 and 240')
    root = Path(__file__).resolve().parents[1]
    try:
        observed = smoke_test_engine([str(args.exe.resolve())], root, args.startup_seconds)
    except (OSError, ValueError, RuntimeError) as exc:
        print(f'PACKAGED ENGINE CHECK FAILED: {exc}', file=sys.stderr)
        return 1
    if args.result_json:
        args.result_json.parent.mkdir(parents=True, exist_ok=True)
        args.result_json.write_text(json.dumps(observed, indent=2), encoding='utf-8')
    print('PACKAGED ENGINE CHECK PASSED: loopback authentication, origin guard, isolated local storage, and local API readiness')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
