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
    owner_stdin = None
    if os.environ.get("PILOTODIN_DESKTOP_WATCH_STDIN") == "1":
        try:
            owner_stdin = sys.stdin.fileno()
        except (AttributeError, ValueError, OSError):
            print("Desktop ownership pipe is missing; refusing to start.", file=sys.stderr)
            return 2
    # The writer lease must precede backend.main/storage import, schema
    # initialization and interrupted-experiment recovery, and outlive server.run.
    from backend.workspace_boundary import WorkspaceBoundaryError, hold_process_workspace
    try:
        owned_home = hold_process_workspace(home)
    except WorkspaceBoundaryError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    os.environ["PILOTODIN_HOME"] = str(owned_home)
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
