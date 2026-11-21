"""Disposable backend HTTP control for N12 Python bytecode attribution."""

from collections import Counter
import json
import os
from pathlib import Path
import re
import socket
import subprocess
import sys
import tempfile
from threading import Lock
import time
from urllib.error import HTTPError, URLError
from urllib.request import ProxyHandler, Request, build_opener


HTTP = build_opener(ProxyHandler({}))
REPO = Path(__file__).resolve().parents[2]
BYTECODE = re.compile(r"\.pyc(?:\.\d+)?$", re.I)
MODULE = re.compile(r"[a-zA-Z_][a-zA-Z_0-9]{0,63}")
WRITE = os.O_CREAT | os.O_TRUNC | os.O_APPEND | os.O_WRONLY | os.O_RDWR


def require(condition, stage):
    if not condition:
        raise RuntimeError(stage)


def bytecode_path(value):
    if isinstance(value, (str, bytes)):
        path = os.fsdecode(value)
        if BYTECODE.search(path):
            return os.path.normcase(os.path.abspath(path))
    return None


def snapshot(root):
    def on_error(error):
        raise error

    files = {}
    for directory, _, names in os.walk(root, onerror=on_error):
        for name in names:
            path = bytecode_path(os.path.join(directory, name))
            if path is not None:
                stat = os.stat(path)
                files[path] = stat.st_size, stat.st_mtime_ns, stat.st_ino
    return files


def audit_bytecode(stream):
    lock = Lock()

    def record(event, args):
        if event == "open" and args[2] & WRITE:
            paths = args[:1]
        elif event == "os.rename":
            paths = args[:2]
        else:
            return
        targets = sorted({target for value in paths if (target := bytecode_path(value))})
        if targets:
            stack = []
            frame = sys._getframe(1)
            while frame is not None and len(stack) < 5:
                root = frame.f_globals.get("__name__", "").partition(".")[0]
                if MODULE.fullmatch(root) and root != "__main__" and root not in stack:
                    stack.append(root)
                frame = frame.f_back
            # This file lives in the disposable workspace. The parent emits only counters.
            with lock:
                stream.write(json.dumps([event, targets, stack]) + "\n")
                stream.flush()

    sys.addaudithook(record)


def child(mode, observation, value):
    require(sys.dont_write_bytecode, "child bytecode suppression inactive")
    with Path(observation).open("x", encoding="utf-8") as stream:
        audit_bytecode(stream)
        if mode == "positive":
            import py_compile

            source = Path(value)
            py_compile.compile(str(source), cfile=str(source.with_suffix(".pyc")), doraise=True)
        else:
            import runpy

            sys.argv = ["uvicorn", *uvicorn_args(value)]
            runpy.run_module("uvicorn", run_name="__main__", alter_sys=True)


def uvicorn_args(port):
    return ["backend.main:app", "--host", "127.0.0.1", "--port", str(port), "--no-access-log"]


def request(base, path, body=None, *, status=200, upload=False):
    headers = {}
    if upload:
        headers["Content-Type"] = "multipart/form-data; boundary=fixture"
    elif body is not None:
        body = json.dumps(body).encode()
        headers["Content-Type"] = "application/json"
    try:
        with HTTP.open(Request(base + path, body, headers), timeout=20) as response:
            require(response.status == status, "unexpected backend response status")
            return json.load(response)
    except HTTPError as error:
        with error:
            require(error.code == status, "unexpected backend error status")
            return None


def exercise(base, process):
    deadline = time.monotonic() + 40
    while True:
        require(process.poll() is None and time.monotonic() < deadline, "backend startup")
        try:
            health = request(base, "/api/health")
        except URLError:
            time.sleep(0.25)
        else:
            break
    require(health["status"] == "ok" and health["cloud_ai"] is False, "isolated backend health")
    require(request(base, "/api/projects") == [], "expected a fresh synthetic workspace")
    rows = [f'{"Y" if i % 2 else "N"},{" retail " if not i else "retail" if i % 3 else "service"},{100 + i}'
            for i in range(80)]
    body = ('--fixture\r\nContent-Disposition: form-data; name="file"; filename="quality.csv"\r\n'
            'Content-Type: text/csv\r\n\r\nchurn,segment,amount\n' + '\n'.join(rows)
            + '\n\r\n--fixture--\r\n').encode()
    project = "/api/projects/" + request(base, "/api/projects", body, status=201, upload=True)["id"]
    prepare = project + "/preparation?target=churn&expected_version="
    require(request(base, prepare + "0")["quality_version"] == 0, "version zero preparation")

    def apply(operation, version, **fields):
        receipt = request(base, project + "/quality/proposals",
                          {"operation": operation, "expected_version": version, **fields})
        return request(base, project + "/quality/commit",
                       {key: receipt[key] for key in ("proposal_id", "proposal_hash")})

    require(apply("autopilot", 0)["version"] == 1, "apply synthetic quality change")
    request(base, prepare + "0", status=409)
    require(request(base, prepare + "1")["quality_version"] == 1, "version one preparation")
    require(apply("restore", 1, target_version=0)["version"] == 2, "restore synthetic quality version")
    require(request(base, project)["experiments"] == [], "zero training runs")


def observation_summary(observation, changed):
    leaders = Counter()
    witnessed = set()
    with observation.open(encoding="utf-8") as stream:
        for line in stream:
            operation, targets, stack = json.loads(line)
            leaders[operation, tuple(stack)] += 1
            witnessed.update(changed.intersection(targets))
    return {"snapshot_targets_with_audit_events": len(witnessed), "events": [
        {"operation": operation, "module_stack": list(stack), "count": count}
        for (operation, stack), count in sorted(leaders.items())
    ]}


def run_backend(mode, root):
    installation = Path(sys.base_prefix)
    before = snapshot(installation)
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
    observation = root / f"{mode}.jsonl"
    arguments = (["-m", __spec__.name, "observed", str(observation), str(port)] if mode == "observed"
                 else ["-m", "uvicorn", *uvicorn_args(port)])
    env = {**os.environ, "CI": "true", "PYTHONDONTWRITEBYTECODE": "1",
           "PILOTODIN_HOME": str(root / mode)}
    with (root / f"{mode}.log").open("xb") as log, subprocess.Popen(
        [sys.executable, "-B", *arguments], cwd=REPO, env=env, stdout=log, stderr=subprocess.STDOUT,
    ) as process:
        try:
            exercise(f"http://127.0.0.1:{port}", process)
        finally:
            if process.poll() is None:
                process.kill()
            process.wait(timeout=10)
    after = snapshot(installation)
    changed = {path for path in before.keys() | after.keys() if before.get(path) != after.get(path)}
    return {"mode": mode, "journey": "PASS", "installation_bytecode_changes": len(changed),
            "audit": observation_summary(observation, changed) if mode == "observed" else None}


def main():
    with tempfile.TemporaryDirectory(prefix="pilotodin-bytecode-", dir=os.environ.get("RUNNER_TEMP")) as directory:
        root = Path(directory)
        source, observation = root / "control.py", root / "control.jsonl"
        source.write_text("value = 1\n", encoding="utf-8")
        before = snapshot(root)
        completed = subprocess.run([sys.executable, "-B", "-m", __spec__.name,
                                    "positive", str(observation), str(source)], cwd=REPO,
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=20)
        require(completed.returncode == 0, "explicit bytecode control subprocess")
        changed = snapshot(root).keys() - before.keys()
        positive = observation_summary(observation, changed)
        require(len(changed) == positive["snapshot_targets_with_audit_events"] == 1
                and any("py_compile" in row["module_stack"] for row in positive["events"]),
                "explicit bytecode control detection")
        print("N12 backend bytecode control " + json.dumps(positive), flush=True)
        for mode in ("observed", "baseline"):
            print("N12 backend bytecode case " + json.dumps(run_backend(mode, root)), flush=True)


if __name__ == "__main__":
    if len(sys.argv) == 4 and sys.argv[1] in {"positive", "observed"}:
        child(*sys.argv[1:])
    else:
        main()
