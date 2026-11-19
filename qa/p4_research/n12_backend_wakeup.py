"""Observe the existing asyncio wake-up sockets inside the hosted QA backend."""
import asyncio
import json
import os
from pathlib import Path

from qa.p4_native.n12_etw_probe import utc_ticks
from qa.p4_native.n12_trace import local_disposable_path


WITNESS_NAME = "private-backend-wakeup.json"


def loop_wakeup_sockets(loop):
    sockets = []
    for key in ("_ssock", "_csock"):
        sock = getattr(loop, key, None)
        if sock is None:
            return []
        try:
            local = sock.getsockname()
            remote = sock.getpeername()
        except OSError:
            return []
        if not all(isinstance(endpoint, tuple) and len(endpoint) >= 2 for endpoint in (local, remote)):
            return []
        sockets.append({"local_address": local[0], "local_port": local[1],
                        "remote_address": remote[0], "remote_port": remote[1]})
    return sockets


async def app(scope, receive, send):
    from backend.main import app as backend_app

    if scope["type"] == "lifespan":
        try:
            sockets = loop_wakeup_sockets(asyncio.get_running_loop())
            if sockets:
                path = local_disposable_path(Path(os.environ["PILOTODIN_HOME"]) / WITNESS_NAME,
                                             runner_temp_only=True)
                with path.open("x", encoding="utf-8") as stream:
                    json.dump({"pid": os.getpid(), "observed_ticks": utc_ticks(), "sockets": sockets}, stream)
        except (OSError, ValueError, KeyError):
            pass  # An unavailable diagnostic leaves the QA backend usable.
    await backend_app(scope, receive, send)
