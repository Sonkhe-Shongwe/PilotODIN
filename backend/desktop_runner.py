"""Entry point for the bundled PilotODIN desktop analytics sidecar.

Run with Python while developing or package with PyInstaller. Only Rust/Tauri
sets the private session token and persistent user-data location in production.
"""
from __future__ import annotations

import os
import sys
from threading import Thread
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from uvicorn import Server


SHUTDOWN_REQUEST = b"PILOTODIN_STOP\n"
_CONTROL_FIELDS = ("PILOTODIN_CONTROL_GENERATION", "PILOTODIN_CONTROL_CAPABILITY")


def _control_mode(environ):
    """No implicit upgrade/downgrade from partial private host configuration."""
    import re
    mode = environ.get("PILOTODIN_CONTROL_MODE")
    fields = [environ.get(key) for key in _CONTROL_FIELDS]
    if mode in (None, "legacy") and all(key not in environ for key in _CONTROL_FIELDS):
        return "legacy"
    if (mode == "pod1" and environ.get("PILOTODIN_DESKTOP_WATCH_STDIN") == "1"
            and all(isinstance(v, str) and re.fullmatch(pattern, v)
                    for v, pattern in zip(fields, (r"[0-9a-f]{32}", r"[0-9a-f]{64}")))):
        return "pod1"
    raise ValueError("Invalid private desktop control configuration")


def _run_owned(bootstrap, port):
    # The caller has already isolated protocol stdout and acquired workspace.
    import uvicorn
    from backend.resource_session import compose_owned_desktop
    def build_server(app):
        return uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port,
                              access_log=False, log_level="warning", server_header=False))
    session = compose_owned_desktop(bootstrap, build_server)
    return 0 if session.run() is True else 3


def _watch_desktop_pipe(server: Server, descriptor: int) -> None:
    # A bounded fixed stop message over the already-owned stdin pipe.
    # EOF, malformed data or an unreadable pipe also stop the server.
    pending = b""
    try:
        while len(pending) < len(SHUTDOWN_REQUEST):
            chunk = os.read(descriptor, len(SHUTDOWN_REQUEST) - len(pending))
            if not chunk:
                break
            pending += chunk
            if not SHUTDOWN_REQUEST.startswith(pending):
                break
    except OSError:
        pass
    server.should_exit = True


def main() -> int:
    session = os.environ.get("PILOTODIN_DESKTOP_SESSION", "")
    home = os.environ.get("PILOTODIN_HOME", "")
    if len(session) < 32 or not home:
        print("Desktop session environment is missing; refusing to start.", file=sys.stderr)
        return 2
    try:
        port = int(os.environ.get("PILOTODIN_DESKTOP_PORT", ""))
    except ValueError:
        print("Invalid desktop port.", file=sys.stderr)
        return 2
    if not 1024 <= port <= 65535:
        print("Desktop port is outside the supported range.", file=sys.stderr)
        return 2
    try:
        mode = _control_mode(os.environ)
    except ValueError:
        print("Invalid private desktop control configuration; refusing to start.", file=sys.stderr)
        return 2
    owner_stdin = None
    if mode == "legacy" and os.environ.get("PILOTODIN_DESKTOP_WATCH_STDIN") == "1":
        try:
            owner_stdin = sys.stdin.fileno()
        except (AttributeError, ValueError, OSError):
            print("Desktop ownership pipe is missing; refusing to start.", file=sys.stderr)
            return 2
    # The writer lease must precede backend.main/storage import, schema
    # initialization and interrupted-experiment recovery, and outlive server.run.
    from backend.workspace_boundary import (
        WorkspaceBoundaryError, hold_process_workspace, configure_process_scratch,
    )
    try:
        owned_home = hold_process_workspace(home)
        configure_process_scratch(owned_home)
    except WorkspaceBoundaryError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    os.environ["PILOTODIN_HOME"] = str(owned_home)
    if mode == "pod1":
        try:
            from backend.resource_host import prepare_owned_control
            bootstrap = prepare_owned_control(os.environ, sys.stdin, sys.stdout, sys.stderr)
            os.environ.pop("PILOTODIN_CONTROL_MODE", None)
            return _run_owned(bootstrap, port)
        except Exception:
            # No raw exception text, no second app/server, no legacy watcher.
            # This single-use process exits on failed composition; bootstrap
            # owns its private descriptor until the process or pump closes it.
            print("Owned desktop control startup or session failed.", file=sys.stderr)
            return 3
    os.environ.pop("PILOTODIN_CONTROL_MODE", None)
    import uvicorn
    from backend.main import app

    options = dict(host="127.0.0.1", port=port, access_log=False,
                   log_level="warning", server_header=False)
    server = uvicorn.Server(uvicorn.Config(app, **options))
    if owner_stdin is not None:
        Thread(target=_watch_desktop_pipe, args=(server, owner_stdin),
               name="pilotodin-desktop-owner", daemon=True).start()
    server.run()
    if not server.started:
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
