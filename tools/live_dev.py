"""Safe, installer-free PilotODIN development launcher for Windows.

Only the isolated .pilotodin-dev-data directory is used for runtime data.
The installed Tauri application's data directory is never read or modified.
"""
from __future__ import annotations

import hashlib
import os
import re
import shutil
import secrets
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VENV = ROOT / ".venv-live"
CACHE = ROOT / ".pilotodin-dev-cache"
DEV_HOME = ROOT / ".pilotodin-dev-data"
FRONTEND = ROOT / "frontend"
API_URL = "http://127.0.0.1:8000/api/health"
PREVIEW_URL = "http://127.0.0.1:5173/"


def announce(stage: int, message: str) -> None:
    print(f"[{stage}/5] {message}", flush=True)


def fingerprint(*paths: Path) -> str:
    """Retain the historical stamp format; missing files never count as inputs."""
    digest = hashlib.sha256()
    for path in paths:
        if not path.is_file():
            raise RuntimeError("C5_DEV_INPUT_MISSING: separate reviewed setup required")
        digest.update(path.read_bytes())
    return digest.hexdigest()


def require_prepared_files(root: Path, venv: Path, cache: Path, frontend: Path) -> Path:
    """Read-only legacy readiness check, not a complete installed-byte lock."""
    python = venv / "Scripts" / "python.exe"
    requirements = root / "backend" / "requirements.txt"
    manifest = frontend / "package.json"
    lockfile = frontend / "package-lock.json"
    vite_cmd = frontend / "node_modules" / ".bin" / "vite.cmd"
    py_stamp = cache / "python-requirements.sha256"
    js_stamp = cache / "frontend-requirements.sha256"
    for required in (python, requirements, manifest, lockfile, vite_cmd, py_stamp, js_stamp):
        if not required.is_file():
            raise RuntimeError("C5_DEV_INPUT_MISSING: separate reviewed setup required; nothing installed")
    if (py_stamp.read_text(encoding="utf-8").strip() != fingerprint(requirements) or
            js_stamp.read_text(encoding="utf-8").strip() != fingerprint(manifest, lockfile)):
        raise RuntimeError("C5_DEV_INPUT_CHANGED: separate reviewed setup required; nothing installed")
    return python


def verify_python_environment(python: Path, venv: Path, requirements: Path) -> None:
    """Check existing interpreter identity, direct distributions and dependency consistency."""
    names = []
    for line in requirements.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        match = re.fullmatch(r"([A-Za-z0-9_.-]+)(?:\[[A-Za-z0-9_,.-]+\])?[<>=!~][A-Za-z0-9.,<>=!~+*_-]+", line.strip())
        if not match:
            raise RuntimeError("C5_DEV_REQUIREMENT_FORMAT_UNREVIEWED")
        names.append(match.group(1))
    if not names:
        raise RuntimeError("C5_DEV_REQUIREMENTS_EMPTY")
    env = {k: v for k, v in os.environ.items()
           if not k.upper().startswith("PIP_") and k.upper() not in ("PYTHONPATH", "PYTHONHOME")}
    env["PIP_CONFIG_FILE"] = os.devnull
    env["PIP_NO_INDEX"] = "1"
    probe = (
        "import sys,pathlib,importlib.metadata as m;"
        "p=pathlib.Path(sys.argv[1]).resolve();"
        "assert pathlib.Path(sys.prefix).resolve()==p and sys.version_info >= (3,11);"
        "assert all(pathlib.Path(m.distribution(n).locate_file('')).resolve().is_relative_to(p) "
        "for n in sys.argv[2:])"
    )
    subprocess.run([str(python), "-I", "-B", "-c", probe, str(venv), *names],
                   check=True, timeout=30, env=env)
    subprocess.run([str(python), "-I", "-B", "-m", "pip", "--isolated",
                    "--disable-pip-version-check", "--no-input", "check"],
                   check=True, timeout=30, env=env)


def is_listening(port: int) -> bool:
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=0.3):
            return True
    except OSError:
        return False


def is_healthy(url: str, capability: str | None = None) -> bool:
    if capability is not None and url != API_URL:
        raise ValueError("Private capability is limited to backend readiness")
    headers = {"X-PilotODIN-Dev-Capability": capability} if capability is not None else {}
    # Disable proxy routing and redirects for the private readiness probe.
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            return None
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
    try:
        with opener.open(urllib.request.Request(url, headers=headers), timeout=1.2) as response:
            return response.status == 200
    except (OSError, urllib.error.URLError):
        return False


def wait_for(label: str, url: str, *, seconds: int = 60, capability: str | None = None) -> None:
    started = time.monotonic()
    last_notice = -1
    while time.monotonic() - started < seconds:
        if is_healthy(url, capability):
            print(f"    {label}: ready after {round(time.monotonic() - started)} seconds.", flush=True)
            return
        elapsed = int(time.monotonic() - started)
        if elapsed // 5 != last_notice:
            print(f"    {label}: starting... {elapsed}s elapsed", flush=True)
            last_notice = elapsed // 5
        time.sleep(0.6)
    raise RuntimeError(f"{label} did not become ready within {seconds}s. Check its PowerShell window for errors.")


def main() -> int:
    if os.name != "nt":
        print("This one-click launcher is for Windows. See docs/LIVE_DEVELOPMENT.md.")
        return 2
    if sys.version_info < (3, 11):
        print(f"Python 3.11+ is required; found {sys.version.split()[0]}.")
        return 2

    announce(1, "Checking existing dependency inputs and developer tools")
    python = require_prepared_files(ROOT, VENV, CACHE, FRONTEND)
    if not shutil.which("node") or not shutil.which("npm.cmd"):
        print("Install Node.js 20+ once (including npm), then reopen this launcher.")
        return 2
    node_version = subprocess.check_output(["node", "--version"], text=True).strip()
    try:
        node_major = int(node_version.lstrip("v").split(".")[0])
    except ValueError:
        print(f"Could not parse Node.js version: {node_version}")
        return 2
    if node_major < 20:
        print(f"Node.js 20+ required; found {node_version}.")
        return 2
    subprocess.run(["node", str(FRONTEND / "scripts" / "verify-npm-lock.mjs"), "--installed"],
                   check=True, timeout=30)
    for port, label in ((8000, "Python backend"), (5173, "Vite frontend")):
        if is_listening(port):
            print(f"Port {port} ({label}) is occupied. Close the previous DEV console or another server.")
            print("No running process was stopped or overwritten.")
            return 2

    announce(2, "Checking existing isolated Python environment")
    verify_python_environment(python, VENV, ROOT / "backend" / "requirements.txt")
    announce(3, "Existing React/Vite dependency metadata ready; no setup performed")
    # The owned ASGI factory validates and creates the final data directory.

    announce(4, "Launching two live-reloading consoles")
    env = dict(os.environ)
    env.update(npm_config_offline="true", npm_config_audit="false")
    env["PILOTODIN_HOME"] = str(DEV_HOME)
    for key in ("PILOTODIN_DESKTOP_SESSION", "PILOTODIN_DESKTOP_PORT",
                "PILOTODIN_DESKTOP_WATCH_STDIN", "PILOTODIN_CONTROL_MODE",
                "PILOTODIN_CONTROL_GENERATION", "PILOTODIN_CONTROL_CAPABILITY",
                "PILOTODIN_BUNDLED_LLM_PORT", "PILOTODIN_BUNDLED_LLM_TOKEN",
                "PILOTODIN_DATASET_EXPORT_KEY"):
        env.pop(key, None)
    capability = secrets.token_hex(32)
    env.update(PILOTODIN_SERVER_MODE="dev", PILOTODIN_DESKTOP_ALLOW_DEV="0",
               PILOTODIN_DEV_CAPABILITY=capability, PILOTODIN_DEV_PORT="8000",
               PILOTODIN_DEV_ORIGIN=PREVIEW_URL.rstrip("/"),
               VITE_PILOTODIN_AUTH_DEV="1")
    powershell = shutil.which("powershell.exe") or "powershell.exe"
    for path in ("run_live_backend.ps1", "run_live_frontend.ps1"):
        script = ROOT / "tools" / path
        subprocess.Popen(
            [powershell, "-NoLogo", "-NoExit", "-ExecutionPolicy", "Bypass", "-File", str(script)],
            cwd=ROOT,
            env=env,
            creationflags=subprocess.CREATE_NEW_CONSOLE,
        )
    announce(5, "Waiting for real HTTP readiness checks")
    wait_for("Python analytics", API_URL, capability=capability)
    wait_for("Vite UI", PREVIEW_URL)
    print("\nREADY: " + PREVIEW_URL)
    print("DATA:  " + str(DEV_HOME))
    print("Edit frontend/src for instant style/layout updates; edit backend for auto-restart.")
    print("Close the two PowerShell consoles to stop. No installer was generated.\n")
    webbrowser.open(PREVIEW_URL)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (RuntimeError, OSError, UnicodeError, subprocess.SubprocessError) as exc:
        print(f"\nERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
