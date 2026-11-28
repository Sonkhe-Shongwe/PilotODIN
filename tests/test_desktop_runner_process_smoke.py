"""Run the real analytical engine as a separate process and validate its loopback API."""
from __future__ import annotations
import http.client
import os
from pathlib import Path
import secrets
import socket
import subprocess
import sys
import time

def _port():
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        return sock.getsockname()[1]

def _status(port, path='/api/health', headers=None):
    # Keep intentional invalid Host/forwarded/mixed-header probes, but never
    # let the transport select a proxy, redirect or alternate destination.
    if type(port) is not int or not 1024 <= port <= 65535 or path not in (
            '/api/health', '/api/projects'):
        raise ValueError('Invalid process smoke destination')
    connection = http.client.HTTPConnection('127.0.0.1', port, timeout=1.5)
    try:
        connection.request('GET', path, headers=headers or {})
        response = connection.getresponse()
        assert not 300 <= response.status < 400, 'Unexpected process smoke redirect'
        return response.status, response.read(1024)
    finally:
        connection.close()


def _child_environment():
    return {key: value for key, value in os.environ.items()
            if not key.upper().startswith(('PILOTODIN_', 'VITE_PILOTODIN_'))}

def test_desktop_runner_process_local_token_and_isolated_storage(tmp_path):
    root = Path(__file__).resolve().parents[1]
    port = _port()
    token = secrets.token_hex(32)
    home = tmp_path / 'personal-workspace'
    home.mkdir()
    # The real Tauri sidecar now starts with this app-data directory as CWD.
    # Python -m still needs the absolute source location while testing; the
    # packaged PyInstaller executable resolves its own modules internally.
    python_path = str(root) + (os.pathsep + os.environ["PYTHONPATH"] if os.environ.get("PYTHONPATH") else "")
    env = {**_child_environment(), 'PYTHONPATH': python_path,
           'PILOTODIN_DESKTOP_SESSION': token, 'PILOTODIN_HOME': str(home),
           'PILOTODIN_DESKTOP_PORT': str(port), 'PILOTODIN_DESKTOP_ALLOW_DEV': '0'}
    process = subprocess.Popen([sys.executable, '-B', '-m', 'backend.desktop_runner'],
                               cwd=home, env=env, stdout=subprocess.DEVNULL,
                               stderr=subprocess.PIPE)
    try:
        deadline = time.monotonic() + 18
        while time.monotonic() < deadline:
            if process.poll() is not None:
                raise AssertionError(f'Engine exited with code {process.returncode}')
            try:
                status, _ = _status(port)
                if status == 401:
                    break
            except (OSError, TimeoutError):
                pass
            time.sleep(0.12)
        else:
            raise AssertionError('Desktop engine failed to listen on loopback')
        assert _status(port)[0] == 401
        assert _status(port, headers={'X-PilotODIN-Session': 'wrong'})[0] == 401
        authorised = {'X-PilotODIN-Session': token, 'Origin': 'http://tauri.localhost'}
        assert _status(port, headers=authorised)[0] == 200
        assert _status(port, headers={**authorised, 'Origin': 'https://untrusted.example'})[0] == 403
        assert _status(port, '/api/projects', authorised)[0] == 200
        assert _status(port, headers={**authorised, 'Origin': 'http://127.0.0.1:5173'})[0] == 403
        assert _status(port, headers={**authorised, 'Host': 'testserver'})[0] == 403
        assert _status(port, headers={**authorised, 'X-Forwarded-For': '127.0.0.1'})[0] == 403
        assert _status(port, headers={**authorised, 'X-PilotODIN-Dev-Capability': 'b'*64})[0] == 401
        # Preserve duplicate raw headers, unlike a header mapping.
        def raw(method, headers, path='/api/health'):
            con = http.client.HTTPConnection('127.0.0.1', port, timeout=3)
            try:
                con.putrequest(method, path, skip_accept_encoding=True)
                for name, value in headers:
                    con.putheader(name, value)
                con.endheaders()
                response = con.getresponse()
                body = response.read()
                return response.status, dict(response.getheaders()), body
            finally:
                con.close()
        session = [('X-PilotODIN-Session', token)]
        assert raw('GET', session+session)[0] == 400
        assert raw('POST', [], '/api/projects')[0] == 401
        cors = [('Origin', 'http://tauri.localhost'),
                ('Access-Control-Request-Method', 'POST'),
                ('Access-Control-Request-Headers', 'content-type,x-pilotodin-session')]
        status, headers, body = raw('OPTIONS', cors, '/api/projects')
        assert status == 204 and not body
        assert headers['access-control-allow-origin'] == 'http://tauri.localhost'
        assert raw('OPTIONS', cors[:-1], '/api/projects')[0] == 403
        assert raw('POST', cors, '/api/projects')[0] == 400
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
    token = secrets.token_hex(32)
    env = {**_child_environment(), "PYTHONPATH": str(root),
           "PILOTODIN_DESKTOP_SESSION": token, "PILOTODIN_HOME": str(home),
           "PILOTODIN_DESKTOP_PORT": str(port), "PILOTODIN_DESKTOP_ALLOW_DEV": "0",
           "PILOTODIN_DESKTOP_WATCH_STDIN": "1"}
    child = subprocess.Popen([sys.executable, "-B", "-m", "backend.desktop_runner"],
        cwd=home, env=env, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE)
    try:
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline:
            if child.poll() is not None:
                raise AssertionError("Engine exited before readiness")
            try:
                if _status(port, headers={"X-PilotODIN-Session": token})[0] == 200:
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
