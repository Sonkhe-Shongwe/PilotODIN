"""Safe, installer-free PilotODIN development launcher for Windows.

Only the isolated .pilotodin-dev-data directory is used for runtime data.
The installed Tauri application's data directory is never read or modified.
"""
from __future__ import annotations

import hashlib
import os
import shutil
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


def run(command: list[str], *, directory: Path = ROOT) -> None:
    print("    Executing:", " ".join(command[:3]), flush=True)
    subprocess.run(command, cwd=directory, check=True)


def fingerprint(*paths: Path) -> str:
    digest = hashlib.sha256()
    for path in paths:
        if path.exists():
            digest.update(path.read_bytes())
        else:
            digest.update(b"<missing>")
    return digest.hexdigest()


def is_listening(port: int) -> bool:
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=0.3):
            return True
    except OSError:
        return False


def is_healthy(url: str) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=1.2) as response:
            return response.status == 200
    except (OSError, urllib.error.URLError):
        return False


def wait_for(label: str, url: str, *, seconds: int = 60) -> None:
    started = time.monotonic()
    last_notice = -1
    while time.monotonic() - started < seconds:
        if is_healthy(url):
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

    announce(1, "Checking developer tools and ports")
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
    for port, label in ((8000, "Python backend"), (5173, "Vite frontend")):
        if is_listening(port):
            print(f"Port {port} ({label}) is occupied. Close the previous DEV console or another server.")
            print("No running process was stopped or overwritten.")
            return 2

    announce(2, "Preparing isolated Python environment")
    DEV_HOME.mkdir(exist_ok=True)
    CACHE.mkdir(exist_ok=True)
    python = VENV / "Scripts" / "python.exe"
    if not python.is_file():
        run([sys.executable, "-m", "venv", str(VENV)])
    requirements = ROOT / "backend" / "requirements.txt"
    py_stamp = CACHE / "python-requirements.sha256"
    new_py_stamp = fingerprint(requirements)
    if not py_stamp.is_file() or py_stamp.read_text().strip() != new_py_stamp:
        print("    Installing/updating dependencies (first run or requirements changed).")
        run([str(python), "-m", "pip", "install", "-r", str(requirements)])
        py_stamp.write_text(new_py_stamp, encoding="utf-8")
    else:
        print("    Python dependencies unchanged; installation skipped.")

    announce(3, "Preparing React/Vite development dependencies")
    manifest = FRONTEND / "package.json"
    lockfile = FRONTEND / "package-lock.json"
    js_stamp = CACHE / "frontend-requirements.sha256"
    new_js_stamp = fingerprint(manifest, lockfile)
    vite_cmd = FRONTEND / "node_modules" / ".bin" / "vite.cmd"
    if not vite_cmd.exists() or not js_stamp.is_file() or js_stamp.read_text().strip() != new_js_stamp:
        npm_action = "ci" if lockfile.exists() else "install"
        print(f"    Running npm {npm_action} (first run or dependency changes).")
        run(["npm.cmd", npm_action, "--no-audit", "--no-fund"], directory=FRONTEND)
        # npm install can create a lockfile; fingerprint the installed state.
        js_stamp.write_text(fingerprint(manifest, lockfile), encoding="utf-8")
    else:
        print("    Frontend dependencies unchanged; installation skipped.")

    announce(4, "Launching two live-reloading consoles")
    env = dict(os.environ)
    env["PILOTODIN_HOME"] = str(DEV_HOME)
    env.pop("PILOTODIN_DESKTOP_SESSION", None)
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
    wait_for("Python analytics", API_URL)
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
    except (RuntimeError, OSError, subprocess.CalledProcessError) as exc:
        print(f"\nERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
