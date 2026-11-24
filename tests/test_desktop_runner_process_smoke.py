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
    home.mkdir()
    # The real Tauri sidecar now starts with this app-data directory as CWD.
    # Python -m still needs the absolute source location while testing; the
    # packaged PyInstaller executable resolves its own modules internally.
    python_path = str(root) + (os.pathsep + os.environ["PYTHONPATH"] if os.environ.get("PYTHONPATH") else "")
    env = {**os.environ, 'PYTHONPATH': python_path,
           'PILOTODIN_DESKTOP_SESSION': token, 'PILOTODIN_HOME': str(home),
           'PILOTODIN_DESKTOP_PORT': str(port), 'PILOTODIN_DESKTOP_ALLOW_DEV': '0'}
    env.pop('PILOTODIN_BUNDLED_LLM_PORT', None)
    env.pop('PILOTODIN_BUNDLED_LLM_TOKEN', None)
    env.pop('PILOTODIN_DESKTOP_WATCH_STDIN', None)
    process = subprocess.Popen([sys.executable, '-B', '-m', 'backend.desktop_runner'],
                               cwd=home, env=env, stdout=subprocess.DEVNULL,
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


def test_desktop_explicit_stop_drains_while_parent_pipe_stays_open(tmp_path):
    from backend.desktop_runner import SHUTDOWN_REQUEST
    from backend.workspace_boundary import engine_workspace
    root = Path(__file__).resolve().parents[1]
    home = tmp_path.resolve() / "stop-workspace"
    home.mkdir()
    port = _port()
    token = "stop-session-" + "a" * 64
    env = {**os.environ, "PYTHONPATH": str(root),
           "PILOTODIN_DESKTOP_SESSION": token, "PILOTODIN_HOME": str(home),
           "PILOTODIN_DESKTOP_PORT": str(port), "PILOTODIN_DESKTOP_ALLOW_DEV": "0",
           "PILOTODIN_DESKTOP_WATCH_STDIN": "1"}
    env.pop("PILOTODIN_BUNDLED_LLM_PORT", None)
    env.pop("PILOTODIN_BUNDLED_LLM_TOKEN", None)
    child = subprocess.Popen([sys.executable, "-B", "-m", "backend.desktop_runner"],
        cwd=home, env=env, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE)
    try:
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline:
            if child.poll() is not None:
                raise AssertionError("Engine exited before readiness")
            try:
                if _status(f"http://127.0.0.1:{port}/api/health",
                           {"X-PilotODIN-Session": token})[0] == 200:
                    break
            except (OSError, TimeoutError):
                pass
            time.sleep(.12)
        else:
            raise AssertionError("Engine readiness failed")
        child.stdin.write(SHUTDOWN_REQUEST)
        child.stdin.flush()
        assert child.wait(timeout=10) == 0
        assert not child.stdin.closed
        with engine_workspace(str(home)):
            assert (home / "pilotodin.sqlite3").is_file()
    finally:
        if child.poll() is None:
            child.kill()
        child.communicate(timeout=7)
