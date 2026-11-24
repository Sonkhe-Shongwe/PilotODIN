"""Inert Windows owned-host integration peer. No HTTP, ML, model or owner files.

Invoked only by the ignored Rust library fixture with a fresh runner-owned root.
All markers are generated, fixed names and exclusive creates. No secrets logged.
"""
import os
import re
from pathlib import Path
import subprocess
import sys
import time
from threading import Thread
from types import SimpleNamespace

LIMIT = 90.0


def require_root(value):
    if (os.name != "nt" or os.environ.get("GITHUB_ACTIONS") != "true"
            or os.environ.get("GITHUB_RUN_ATTEMPT") != "1"
            or os.environ.get("PILOTODIN_C1_C2_FIXTURE_APPROVAL") != "OWNED_HOST_SYNTHETIC_ONCE"):
        raise RuntimeError("Fixture not authorized")
    root = Path(value)
    allowed = Path(os.environ["PILOTODIN_C1_C2_FIXTURE_ROOT"])
    runner = Path(os.environ["RUNNER_TEMP"])
    for path in (root, allowed, runner):
        if (not path.is_absolute() or not re.fullmatch(r"[A-Za-z]:", path.drive)
                or ".." in path.parts):
            raise RuntimeError("Fixture path spelling refused")
    root_id, allowed_id, runner_id = (p.resolve(strict=True) for p in (root, allowed, runner))
    if (root.parent != allowed or allowed.parent != runner
            or root_id.parent != allowed_id or allowed_id.parent != runner_id
            or not re.fullmatch(r"owned-host-[0-9a-f-]{36}", root.name)
            or not all(p.is_dir() for p in (root_id, allowed_id, runner_id))
            or not root.samefile(root_id)):
        raise RuntimeError("Fixture root not isolated")
    # Keep normal drive spelling; never strip an unchecked verbatim prefix.
    return root


def mark(root, name):
    with (root / name).open("xb") as out:
        out.write(b"fixture\n")


def wait(root, name, limit=25):
    end = time.monotonic() + limit
    while not (root / name).is_file():
        if time.monotonic() >= end:
            raise RuntimeError("Synthetic barrier expired")
        time.sleep(.02)


def child_worker(root):
    # Both this leader and its own descendant must be in the same shell job.
    # The descendant is inert and bounded even if test cleanup faults.
    child = subprocess.Popen([sys.executable, "-I", "-B", str(Path(__file__).resolve()),
                              "descendant", str(root)], stdin=subprocess.DEVNULL,
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    wait(root, "descendant-ready")
    mark(root, "worker-ready")
    child.wait(timeout=LIMIT)


def engine(root):
    # Import only existing lightweight production resource components.
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from backend.workspace_boundary import hold_process_workspace
    from backend.resource_host import InferenceDemand, prepare_owned_control
    from backend.resource_session import DesktopResourceSession
    from backend.resource_admission import Operation, GIB
    home = root / "engine-home"
    home.mkdir()
    hold_process_workspace(str(home))
    bootstrap = prepare_owned_control(os.environ, sys.stdin, sys.stdout, sys.stderr)
    demand = InferenceDemand()
    # Exercise real private descriptor isolation; diagnostic stdout must
    # never be parsed as POD1 by the Rust host.
    print("synthetic diagnostic (not POD1)", flush=True)

    class Autonomy:
        def __init__(self, coordinator):
            self.stages = SimpleNamespace(coordinator=coordinator)
            self.task = None

        def stop_admission(self):
            pass

        def drain(self, timeout):
            if self.task is None:
                return True
            self.task.join(timeout)
            return not self.task.is_alive()

    class Server:
        def __init__(self, binding):
            self.binding = binding
            self.started = False
            self.should_exit = False
            self.error = None

        def probe(self, op):
            c = self.binding.stages.coordinator
            assert c.status()["operation"] == op.value and c.status()["active"]
            for other in Operation:
                assert c.try_acquire(other).code == "resource_busy"

        def callback(self):
            wait(root, "worker-ready")
            self.probe(Operation.LOCAL_INFERENCE)
            mark(root, "callback-entered")
            wait(root, "callback-return")
            self.probe(Operation.LOCAL_INFERENCE)
            return "inert-result"

        def request(self):
            try:
                assert demand.run(self.callback, timeout=50) == "inert-result"
                c = self.binding.stages.coordinator
                lease = c.try_acquire(Operation.DATA).lease
                assert lease is not None and c.start(lease) and c.release(lease)
                mark(root, "demand-complete")
            except BaseException:
                self.error = True

        def run(self):
            self.started = True
            end = time.monotonic() + LIMIT
            done = set()
            while not self.should_exit:
                if self.error or time.monotonic() >= end:
                    raise RuntimeError("Synthetic server failed")
                for trigger, op in (("report-probe", Operation.REPORT),
                                    ("export-probe", Operation.EXPORT)):
                    if trigger not in done and (root / trigger).is_file():
                        self.probe(op)
                        mark(root, trigger + "-confirmed")
                        done.add(trigger)
                if self.binding.task is None and (root / "request-demand").is_file():
                    self.binding.task = Thread(target=self.request, daemon=False)
                    self.binding.task.start()
                if "stop-seen" not in done and self.binding.stages.coordinator.status()["stopping"]:
                    assert self.binding.stages.coordinator.status()["active"]
                    mark(root, "stop-seen")
                    done.add("stop-seen")
                time.sleep(.02)
            assert not self.error and "stop-seen" in done

    session = DesktopResourceSession(bootstrap, lambda: "adaptive", lambda: 3 * GIB,
                                     build_autonomy=Autonomy,
                                     build_app=lambda c, a: a, build_server=Server, demand=demand)
    assert session.run() is True
    assert not session.coordinator.status()["active"]
    mark(root, "engine-settled")


def main():
    if len(sys.argv) != 3:
        raise RuntimeError("Invalid fixture role")
    role, value = sys.argv[1:]
    root = require_root(value)
    if role == "engine":
        engine(root)
    elif role == "worker":
        child_worker(root)
    elif role == "descendant":
        mark(root, "descendant-ready")
        time.sleep(LIMIT)
    else:
        raise RuntimeError("Invalid fixture role")


if __name__ == "__main__":
    main()
