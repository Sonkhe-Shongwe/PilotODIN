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


def _watch_desktop_pipe(server: Server, descriptor: int) -> None:
    # The desktop holds the only write end. EOF also arrives if Windows
    # terminates the desktop before it can run the normal exit callback.
    try:
        while os.read(descriptor, 4096):
            pass
    except OSError:
        # An unreadable ownership channel cannot establish a live owner.
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
    from backend.workspace_boundary import WorkspaceBoundaryError, engine_workspace
    try:
        with engine_workspace(home) as owned_home:
            os.environ["PILOTODIN_HOME"] = str(owned_home)
            import uvicorn
            from backend.main import app

            options = dict(host="127.0.0.1", port=port, access_log=False,
                           log_level="warning", server_header=False)
            if owner_stdin is None:
                uvicorn.run(app, **options)
            else:
                server = uvicorn.Server(uvicorn.Config(app, **options))
                Thread(target=_watch_desktop_pipe, args=(server, owner_stdin),
                       name="pilotodin-desktop-owner", daemon=True).start()
                server.run()
                if not server.started:
                    return 3  # Uvicorn's startup-failure exit status.
            return 0
    except WorkspaceBoundaryError as exc:
        print(str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
