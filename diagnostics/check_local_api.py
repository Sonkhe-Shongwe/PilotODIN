"""Read-only diagnostics through the existing paired Live Dev frontdoor.

No private capability, service launch, data mutation, model generation, or
direct backend fallback. The existing separate Ollama inventory remains local.
"""
from __future__ import annotations

import http.client
import json
import re

FRONTDOOR_PORT = 5173
OLLAMA_PORT = 11434
MAX_RESPONSE = 4 * 1024 * 1024
_ORIGIN = "http://127.0.0.1:5173"
_PROJECT_ROUTE = re.compile(
    r"/api/projects/[0-9a-f]{32}/(?:live-profile|explore/overview|investigations|explore/recommended)"
)
_PROJECT_ID = re.compile(r"[0-9a-f]{32}")


class DiagnosticRefused(RuntimeError):
    pass


def read_local(port: int, path: str):
    """Perform one exact GET without proxy or redirect support."""
    if type(port) is not int or not isinstance(path, str):
        raise DiagnosticRefused("Unexpected diagnostic destination")
    if port == FRONTDOOR_PORT and (
        path in ("/api/health", "/api/projects") or _PROJECT_ROUTE.fullmatch(path)
    ):
        headers = {"Origin": _ORIGIN, "X-PilotODIN-Dev-Request": "1"}
    elif port == OLLAMA_PORT and path == "/api/tags":
        headers = {}
    else:
        raise DiagnosticRefused("Unexpected diagnostic destination")

    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=8)
    try:
        conn.request("GET", path, headers=headers)
        response = conn.getresponse()
        if response.status != 200:
            raise DiagnosticRefused(f"HTTP {response.status}")
        raw = response.read(MAX_RESPONSE + 1)
        if len(raw) > MAX_RESPONSE:
            raise DiagnosticRefused("Response exceeds diagnostic limit")
        try:
            return json.loads(raw)
        except (ValueError, UnicodeError):
            raise DiagnosticRefused("Invalid diagnostic JSON") from None
    except (OSError, http.client.HTTPException):
        raise DiagnosticRefused("Local service unavailable") from None
    finally:
        conn.close()


def main() -> int:
    print("PilotODIN isolated Live Dev diagnostics (read-only, no cloud requests)")
    failed = False

    def check(label, port, path, expected):
        nonlocal failed
        try:
            result = read_local(port, path)
            if not isinstance(result, expected):
                raise DiagnosticRefused("Unexpected response shape")
        except DiagnosticRefused as exc:
            failed = True
            print(f"[FAIL] {label}: {exc}")
            return None
        print(f"[OK] {label}")
        return result

    health = check("Analytics engine /health", FRONTDOOR_PORT, "/api/health", dict)
    if health is None or health.get("status") != "ok":
        print("Paired Live Dev health not confirmed. Start both Live Dev consoles; no further requests made.")
        return 1
    projects = check("Project listing /projects", FRONTDOOR_PORT, "/api/projects", list)
    if projects is not None:
        print(f"Projects returned: {len(projects)}")
        if not all(isinstance(p, dict) and isinstance(p.get("id"), str)
                   and _PROJECT_ID.fullmatch(p["id"]) for p in projects):
            print("[FAIL] Unexpected project identity; project route checks refused.")
            failed = True
        elif projects:
            selected = next((p for p in projects if p.get("name") == "missingness"), projects[0])
            prefix = "/api/projects/" + selected["id"]
            for label, suffix, expected in (
                ("Dataset profile", "/live-profile", (dict,)),
                ("Data overview", "/explore/overview", (dict,)),
                ("Investigation history", "/investigations", (dict, list)),
                ("Recommendations", "/explore/recommended", (dict, list)),
            ):
                check(label, FRONTDOOR_PORT, prefix + suffix, expected)
        else:
            print("No projects found in the isolated Live Dev workspace.")
    check("Local Ollama model inventory", OLLAMA_PORT, "/api/tags", dict)
    print("Only local service availability and route status were checked; no dataset records displayed or uploaded.")
    return int(failed)


if __name__ == "__main__":
    raise SystemExit(main())
