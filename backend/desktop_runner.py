"""Entry point for the bundled PilotODIN desktop analytics sidecar.

Run with Python while developing or package with PyInstaller. Only Rust/Tauri
sets the private session token and persistent user-data location in production.
"""
from __future__ import annotations

import os
import sys


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
    # Import only after confirming PILOTODIN_HOME so storage cannot accidentally
    # initialise a database inside the installed application directory.
    import uvicorn
    from backend.main import app

    uvicorn.run(app, host="127.0.0.1", port=port, access_log=False,
                log_level="warning", server_header=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
