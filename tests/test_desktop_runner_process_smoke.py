"""Run the real analytical engine as a separate process and validate its loopback API."""
from __future__ import annotations
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request

def _port():
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        return sock.getsockname()[1]

def _status(url, headers=None):
    request = urllib.request.Request(url, headers=headers or {})
    try:
        with urllib.request.urlopen(request, timeout=1.5) as response:
            return response.status, response.read(1024)
    except urllib.error.HTTPError as error:
        return error.code, error.read(1024)

def test_desktop_runner_process_local_token_and_isolated_storage(tmp_path):
    root = Path(__file__).resolve().parents[1]
    port = _port()
    token = 'pilotodin-session-' + '5' * 64
    home = tmp_path / 'personal-workspace'
    env = {**os.environ, 'PILOTODIN_DESKTOP_SESSION': token, 'PILOTODIN_HOME': str(home),
           'PILOTODIN_DESKTOP_PORT': str(port), 'PILOTODIN_DESKTOP_ALLOW_DEV': '0'}
    env.pop('PILOTODIN_BUNDLED_LLM_PORT', None)
    env.pop('PILOTODIN_BUNDLED_LLM_TOKEN', None)
    process = subprocess.Popen([sys.executable, '-m', 'backend.desktop_runner'],
                               cwd=root, env=env, stdout=subprocess.DEVNULL,
                               stderr=subprocess.PIPE)
    url = f'http://127.0.0.1:{port}/api/health'
    try:
        deadline = time.monotonic() + 18
        while time.monotonic() < deadline:
            if process.poll() is not None:
                raise AssertionError(f'Engine exited with code {process.returncode}')
            try:
                status, _ = _status(url)
                if status == 401:
                    break
            except (OSError, TimeoutError):
                pass
            time.sleep(0.12)
        else:
            raise AssertionError('Desktop engine failed to listen on loopback')
        assert _status(url)[0] == 401
        assert _status(url, {'X-PilotODIN-Session': 'wrong'})[0] == 401
        authorised = {'X-PilotODIN-Session': token, 'Origin': 'http://tauri.localhost'}
        assert _status(url, authorised)[0] == 200
        assert _status(url, {**authorised, 'Origin': 'https://untrusted.example'})[0] == 403
        assert _status(f'http://127.0.0.1:{port}/api/projects', authorised)[0] == 200
        assert home.joinpath('pilotodin.sqlite3').exists()
        assert home.joinpath('datasets').is_dir()
    finally:
        process.terminate()
        try:
            process.communicate(timeout=7)
        except subprocess.TimeoutExpired:
            process.kill()
            process.communicate(timeout=7)
