#!/usr/bin/env python3
"""P2 mounted React browser integration using synthetic API, no new dependencies.

Runs local TypeScript/Vite, a temporary loopback-only Vite server and Chrome/Edge
headless with a new temporary profile. This never contacts the real API service.
"""
from __future__ import annotations

import html.parser
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend"

class OutcomeParser(html.parser.HTMLParser):
    def __init__(self):
        super().__init__()
        self.capture = False
        self.status = None
        self.text = []
    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        if tag == "pre" and attributes.get("id") == "p2-result":
            self.capture = True
            self.status = attributes.get("data-status")
    def handle_endtag(self, tag):
        if tag == "pre" and self.capture:
            self.capture = False
    def handle_data(self, data):
        if self.capture:
            self.text.append(data)

def browser_path() -> Path | None:
    candidates = []
    for label in ("PROGRAMFILES", "PROGRAMFILES(X86)", "LOCALAPPDATA"):
        root = os.environ.get(label)
        if root:
            candidates.extend((
                Path(root) / "Google" / "Chrome" / "Application" / "chrome.exe",
                Path(root) / "Microsoft" / "Edge" / "Application" / "msedge.exe",
            ))
    for name in ("chrome.exe", "msedge.exe", "chrome", "chromium", "msedge"):
        path = shutil.which(name)
        if path:
            candidates.append(Path(path))
    return next((p for p in candidates if p.is_file()), None)

def find_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]

def poll(url: str, timeout: float = 40) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=1.0) as response:
                if response.status == 200:
                    return
        except (OSError, urllib.error.URLError):
            pass
        time.sleep(0.3)
    raise RuntimeError("Isolated Vite server did not become reachable within 40 seconds.")

def main() -> int:
    output = Path(tempfile.mkdtemp(prefix="pilotodin-p2-mounted-react-"))
    home = output / "isolated-pilotodin-home"
    home.mkdir()
    env = os.environ.copy()
    env["PILOTODIN_HOME"] = str(home)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env.pop("PILOTODIN_DESKTOP_SESSION", None)
    logs = []
    phases = []
    def record(name: str, status: str, logfile: Path, elapsed: float, detail: str = "") -> None:
        phases.append({
            "phase": name, "status": status, "elapsed_seconds": round(elapsed, 2),
            "log": logfile.name, "detail": detail[:400],
        })
        print(name + ": " + status, flush=True)
        logs.append(logfile)

    npm = shutil.which("npm.cmd") or shutil.which("npm")
    node = shutil.which("node.exe") or shutil.which("node")
    buildlog = output / "frontend-typescript-vite.log"
    begin = time.monotonic()
    if not npm:
        buildlog.write_text("Missing local npm.\n", encoding="utf-8")
        build_rc = -1
    else:
        try:
            with buildlog.open("w", encoding="utf-8", errors="replace") as log:
                build_rc = subprocess.run(
                    [npm, "run", "build"], cwd=FRONTEND, env=env, stdin=subprocess.DEVNULL,
                    stdout=log, stderr=subprocess.STDOUT, timeout=240, check=False
                ).returncode
        except (OSError, subprocess.TimeoutExpired) as exc:
            buildlog.write_text(str(exc), encoding="utf-8")
            build_rc = -1
    record("frontend-typescript-vite", "PASS" if build_rc == 0 else "FAIL",
           buildlog, time.monotonic() - begin)
    vite_log = output / "isolated-vite.log"
    browser_log = output / "mounted-react-browser.log"
    browser_dom = output / "mounted-react-dom.txt"
    browser_status = "FAIL"
    browser_detail = ""
    vite = None
    vite_stream = None
    start = time.monotonic()
    try:
        if build_rc != 0:
            raise RuntimeError("TypeScript/Vite build failed. Browser phase not started.")
        if not node:
            raise RuntimeError("Node is unavailable; browser fixture cannot start.")
        binary = browser_path()
        if binary is None:
            raise RuntimeError("Chrome or Edge browser binary was not found; no DOM PASS is claimed.")
        vite_entry = FRONTEND / "node_modules" / "vite" / "bin" / "vite.js"
        if not vite_entry.is_file():
            raise RuntimeError("Existing node_modules/Vite is missing. No dependency installation performed.")
        port = find_port()
        vite_stream = vite_log.open("w", encoding="utf-8", errors="replace")
        vite = subprocess.Popen(
            [node, str(vite_entry), "--host", "127.0.0.1", "--port", str(port), "--strictPort"],
            cwd=FRONTEND, env=env, stdin=subprocess.DEVNULL,
            stdout=vite_stream, stderr=subprocess.STDOUT,
        )
        url = f"http://127.0.0.1:{port}/p2_report_dom_test.html"
        poll(url)
        # Each browser invocation uses its own temporary profile; never open the
        # owner's actual Chrome/Edge profile or external URLs.
        cmd = [
            str(binary), "--headless=new", "--disable-gpu",
            "--disable-extensions", "--disable-background-networking",
            "--disable-sync", "--no-first-run", "--no-default-browser-check",
            "--no-proxy-server", "--user-data-dir=" + str(output / "browser-profile"),
            "--virtual-time-budget=25000", "--dump-dom", url,
        ]
        with browser_log.open("w", encoding="utf-8", errors="replace") as log:
            try:
                result = subprocess.run(
                    cmd, cwd=FRONTEND, env=env, stdin=subprocess.DEVNULL,
                    capture_output=True, text=True, errors="replace",
                    timeout=120, check=False,
                )
                browser_dom.write_text(result.stdout[-120000:], encoding="utf-8", errors="replace")
                log.write("Browser process exit: " + str(result.returncode) + "\n")
                log.write("Browser stderr (tail):\n" + result.stderr[-7000:] + "\n")
                parsed = OutcomeParser()
                parsed.feed(result.stdout)
                text = "".join(parsed.text)
                log.write("Fixture result:\n" + text[-14000:] + "\n")
                if parsed.status != "PASS":
                    raise RuntimeError("Mounted React browser fixture status: " + str(parsed.status))
                data = json.loads(text)
                if data.get("overall") != "PASS" or data.get("passed") != 5 or data.get("total") != 5:
                    raise RuntimeError("Fixture did not report 5/5 successful real DOM scenarios.")
                if result.returncode != 0:
                    raise RuntimeError("Browser returned nonzero exit code despite fixture output.")
                browser_status = "PASS"
                browser_detail = "5/5 mounted React DOM scenarios PASS"
            except subprocess.TimeoutExpired as exc:
                raise RuntimeError("Headless browser timed out without a reliable DOM result.") from exc
    except Exception as exc:
        browser_detail = str(exc)
        with browser_log.open("a", encoding="utf-8") as log:
            log.write("TEST FAILURE: " + browser_detail + "\n")
    finally:
        if vite is not None:
            vite.terminate()
            try:
                vite.wait(timeout=6)
            except subprocess.TimeoutExpired:
                vite.kill()
                vite.wait(timeout=6)
        if vite_stream is not None:
            vite_stream.close()
        if not vite_log.exists():
            vite_log.write_text("Vite did not start.\n", encoding="utf-8")
        if not browser_dom.exists():
            browser_dom.write_text("No browser DOM result.\n", encoding="utf-8")
        record("p2-mounted-react-dom", browser_status, browser_log,
               time.monotonic() - start, browser_detail)
    summary = {
        "scope": "P2 mounted React reporting interactions against synthetic mocked API",
        "utc": datetime.now(timezone.utc).isoformat(),
        "overall": "PASS" if all(x["status"] == "PASS" for x in phases) else "FAIL",
        "phases": phases,
        "browser_scenarios": 5,
        "mounted_react_dom": browser_status,
        "real_backend_or_user_projects": "NOT_STARTED_OR_ACCESSED",
        "native_tauri_windows_save_as": "NOT_TESTED",
        "offline_ai_e2_8gb": "NOT_TESTED",
        "historical_p0_p1_p3_p4_p5_suites": "NOT_RERUN",
    }
    (output / "result.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    archive = output.with_suffix(".zip")
    with ZipFile(archive, "w", ZIP_DEFLATED) as zipped:
        for item in [buildlog, vite_log, browser_log, browser_dom, output / "result.json"]:
            zipped.write(item, arcname=item.name)
    print("P2 mounted React integration gate:", summary["overall"], flush=True)
    print("Diagnostic ZIP (may contain local paths):", archive, flush=True)
    return 0 if summary["overall"] == "PASS" else 1

if __name__ == "__main__":
    raise SystemExit(main())
