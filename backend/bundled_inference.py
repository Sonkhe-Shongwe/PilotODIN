"""Authenticated, loopback-only client for PilotODIN's bundled local inference worker.

No user-provided URL is accepted. Desktop/Rust injects the port and per-launch
secret, and only the desktop supervisor may start or stop the worker. This
module never downloads models or executes model-produced instructions.
"""
from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from typing import Any


MODEL_ALIAS = "pilotodin-qwen3-1.7b"


def is_configured() -> bool:
    """A signed desktop session, worker port and separate API key are mandatory."""
    return bool(os.environ.get("PILOTODIN_DESKTOP_SESSION") and
                os.environ.get("PILOTODIN_BUNDLED_LLM_PORT") and
                os.environ.get("PILOTODIN_BUNDLED_LLM_TOKEN"))


def _configuration() -> tuple[str, str]:
    if not is_configured():
        raise RuntimeError("Bundled offline model is not configured")
    port_string = os.environ["PILOTODIN_BUNDLED_LLM_PORT"]
    if not port_string.isascii() or not port_string.isdecimal():
        raise RuntimeError("Invalid bundled inference port")
    port = int(port_string)
    secret = os.environ["PILOTODIN_BUNDLED_LLM_TOKEN"]
    if not (1024 <= port <= 65535 and len(secret) >= 32):
        raise RuntimeError("Invalid bundled inference session")
    return f"http://127.0.0.1:{port}", secret


def _request(path: str, payload: dict[str, Any] | None = None, timeout: float = 3) -> dict[str, Any]:
    if path not in ("/health", "/v1/models", "/v1/chat/completions"):
        raise ValueError("Unsupported bundled inference API path")
    base, secret = _configuration()
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8") if payload is not None else None
    request = urllib.request.Request(
        base + path, data=data,
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {secret}",
                 "User-Agent": "PilotODIN/bundled-inference"},
        method="POST" if payload is not None else "GET",
    )
    # Never obey HTTP(S)_PROXY for local AI requests.
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open(request, timeout=timeout) as response:
        raw = response.read(256_001)
    if len(raw) > 256_000:
        raise ValueError("Bundled inference response exceeds safety limit")
    result = json.loads(raw)
    if not isinstance(result, dict):
        raise ValueError("Invalid bundled inference response")
    return result


def status() -> dict[str, Any]:
    if not is_configured():
        return {"status": "not_configured", "model": MODEL_ALIAS, "runtime": "bundled"}
    try:
        health = _request("/health", timeout=1.2)
        if health.get("status") != "ok":
            return {"status": "loading", "model": MODEL_ALIAS, "runtime": "bundled"}
        models = _request("/v1/models", timeout=1.5).get("data", [])
        if not isinstance(models, list):
            return {"status": "unavailable", "model": MODEL_ALIAS, "runtime": "bundled"}
        available = any(isinstance(m, dict) and m.get("id") == MODEL_ALIAS for m in models)
        return {"status": "ready" if available else "model_missing", "model": MODEL_ALIAS,
                "runtime": "bundled"}
    except urllib.error.HTTPError as exc:
        return {"status": "loading" if exc.code == 503 else "unavailable",
                "model": MODEL_ALIAS, "runtime": "bundled"}
    except (OSError, ValueError, RuntimeError, json.JSONDecodeError):
        # A configured desktop model is intentionally not loaded during health probes.
        return {"status": "idle", "model": MODEL_ALIAS, "runtime": "bundled"}


def generate(system: str, user: str, timeout: int) -> tuple[str, bool, str]:
    if not isinstance(system, str) or not isinstance(user, str):
        raise ValueError("Invalid local inference messages")
    # The worker loads on demand. Wait for the model, not indefinitely.
    deadline = time.monotonic() + min(max(timeout, 5), 180)
    while True:
        state = status()["status"]
        if state == "ready":
            break
        if state in ("model_missing", "not_configured", "unavailable"):
            raise RuntimeError("Bundled offline AI is unavailable")
        if time.monotonic() >= deadline:
            raise TimeoutError("Timed out loading bundled offline model")
        time.sleep(min(0.25, max(0, deadline - time.monotonic())))
    remaining = max(1, deadline - time.monotonic())
    response = _request("/v1/chat/completions", {
        "model": MODEL_ALIAS,
        "messages": [{"role": "system", "content": system[:5000]},
                     {"role": "user", "content": user[:9000]}],
        "stream": False, "temperature": 0.2, "max_tokens": 850,
    }, timeout=remaining)
    choices = response.get("choices")
    if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
        raise RuntimeError("Bundled model returned no choices")
    choice = choices[0]
    message = choice.get("message")
    content = message.get("content") if isinstance(message, dict) else None
    if not isinstance(content, str) or not content.strip():
        raise RuntimeError("Bundled model returned no usable text")
    reason = str(choice.get("finish_reason") or "unknown")
    return content.strip()[:16000], reason in ("length", "max_tokens") or len(content) > 16000, reason
