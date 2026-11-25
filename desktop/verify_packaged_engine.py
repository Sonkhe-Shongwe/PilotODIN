"""Execute the real Windows desktop-engine binary and test its loopback boundary.

This gate must pass after PyInstaller and before any Windows installer is built.
It intentionally avoids loading an AI model or connecting to cloud services.
"""
from __future__ import annotations

import argparse
import http.client
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


def _unused_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(('127.0.0.1', 0))
        return int(sock.getsockname()[1])


def _request(port: int, path: str, headers: dict[str, str] | None = None) -> tuple[int, object]:
    """Send only the two smoke GETs directly to the selected literal loopback port.

    HTTPConnection neither consults proxy environment variables nor follows a
    redirect. No caller can override Host or supply another destination.
    """
    if type(port) is not int or not 1024 <= port <= 65535 or path not in (
            '/api/health', '/api/projects'):
        raise ValueError('Invalid desktop smoke destination')
    supplied = dict(headers or {})
    if set(supplied) - {'X-PilotODIN-Session', 'Origin'}:
        raise ValueError('Invalid desktop smoke headers')
    connection = http.client.HTTPConnection('127.0.0.1', port, timeout=3)
    try:
        connection.request('GET', path, headers=supplied)
        response = connection.getresponse()
        if 300 <= response.status < 400:
            raise RuntimeError('Desktop engine returned a redirect')
        limit = 1024 * 1024
        body = response.read(limit + 1)
        if len(body) > limit:
            raise RuntimeError('Desktop engine response exceeded smoke limit')
        try:
            return response.status, json.loads(body)
        except (ValueError, UnicodeError):
            raise RuntimeError('Desktop engine returned invalid smoke JSON') from None
    except http.client.RemoteDisconnected:
        raise
    except http.client.HTTPException:
        raise RuntimeError('Desktop engine returned invalid HTTP') from None
    finally:
        connection.close()


def _smoke_environment(environ, data_dir: Path, port: int, token: str) -> dict:
    """Build a clean, independent child contract without changing the parent."""
    env = {key: value for key, value in environ.items()
           if not key.upper().startswith(('PILOTODIN_', 'VITE_PILOTODIN_'))}
    env.update({
        'PILOTODIN_DESKTOP_PORT': str(port),
        'PILOTODIN_DESKTOP_SESSION': token,
        'PILOTODIN_DESKTOP_WATCH_STDIN': '1',
        'PILOTODIN_HOME': str(data_dir),
        'PILOTODIN_DESKTOP_ALLOW_DEV': '0',
    })
    return env


def _wait_for_database_unlock(db: Path, timeout_seconds: float = 25) -> None:
    """Wait for Windows to release the backend's SQLite handle after termination.

    taskkill /T waits for process termination, but the kernel or a child can
    briefly retain a handle. Do not report a successful packaging check while
    the test database remains locked. POSIX also supports this guard.
    """
    deadline = time.monotonic() + timeout_seconds
    probe = db.with_name(db.name + '.smoke-unlock-check')
    last_error: OSError | None = None
    while time.monotonic() < deadline:
        if not db.exists():
            return
        try:
            db.rename(probe)
            probe.rename(db)
            return
        except OSError as error:
            last_error = error
            # If the first rename succeeded but the second did not, restore
            # the original name rather than silently leaving stray test data.
            if probe.exists() and not db.exists():
                try:
                    probe.rename(db)
                except OSError:
                    pass
            time.sleep(0.3)
    raise RuntimeError(
        'Desktop engine has not released its temporary SQLite database after shutdown'
    ) from last_error


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
        env = _smoke_environment(os.environ, data_dir, port, token)
        creationflags = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
        child = subprocess.Popen(list(command), cwd=root, env=env,
                                 stdin=subprocess.PIPE, stdout=subprocess.DEVNULL,
                                 stderr=subprocess.DEVNULL, creationflags=creationflags)
        try:
            deadline = time.monotonic() + startup_seconds
            while True:
                if child.poll() is not None:
                    raise RuntimeError(f'Desktop engine stopped before health readiness (exit={child.returncode})')
                try:
                    code, _ = _request(port, '/api/health')
                    if code == 401:
                        break
                    if code == 200:
                        raise RuntimeError('Unauthenticated desktop engine health request succeeded')
                except (ConnectionError, TimeoutError, OSError):
                    pass
                if time.monotonic() >= deadline:
                    raise RuntimeError('Desktop engine did not become reachable in time')
                time.sleep(0.2)
            valid = {'X-PilotODIN-Session': token, 'Origin': 'http://tauri.localhost'}
            if _request(port, '/api/health', {'X-PilotODIN-Session': 'invalid'})[0] != 401:
                raise RuntimeError('Desktop session rejected wrong token incorrectly')
            status, health = _request(port, '/api/health', valid)
            if status != 200 or not isinstance(health, dict) or health.get('status') != 'ok':
                raise RuntimeError('Authenticated health check was not successful')
            if _request(port, '/api/health', {**valid, 'Origin': 'https://untrusted.example'})[0] != 403:
                raise RuntimeError('Desktop API incorrectly accepted untrusted origin')
            code, projects = _request(port, '/api/projects', valid)
            if code != 200 or not isinstance(projects, list):
                raise RuntimeError('Authenticated project listing failed')
            if not (data_dir / 'pilotodin.sqlite3').is_file() or not (data_dir / 'datasets').is_dir():
                raise RuntimeError('Persistent local user data was not initialized in the designated directory')
            if child.poll() is not None:
                raise RuntimeError('Desktop engine died after the health check')
            assert child.stdin is not None
            child.stdin.close()
            if child.wait(timeout=15) != 0:
                raise RuntimeError('Desktop engine did not exit cleanly after losing its owner')
            try:
                with socket.create_connection(('127.0.0.1', port), timeout=1):
                    raise RuntimeError('Desktop engine listener remained after its parent exited')
            except (ConnectionRefusedError, TimeoutError):
                pass
            return {'passed': True, 'auth_required': True, 'wrong_origin_rejected': True,
                    'user_storage_isolated': True, 'model_started': False,
                    'owner_disconnect_stops_engine': True}
        except subprocess.TimeoutExpired as error:
            raise RuntimeError('Packaged engine stayed alive after its owner pipe closed') from error
        except Exception as error:
            raise RuntimeError(f'Packaged engine smoke verification failed: {error}; '
                               f'check process startup and configuration') from error
        finally:
            if child.stdin is not None and not child.stdin.closed:
                child.stdin.close()
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
            # A successful API probe is not sufficient if the frozen
            # subprocess leaves SQLite handles behind. Wait for the file
            # to become renamable before TemporaryDirectory cleanup.
            _wait_for_database_unlock(data_dir / 'pilotodin.sqlite3')


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
    print('PACKAGED ENGINE CHECK PASSED: loopback authentication, origin guard, isolated local storage, and owner-disconnect shutdown')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
