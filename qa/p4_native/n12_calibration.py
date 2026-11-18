"""Generate local TCP/UDP and file-operation markers for N12 calibration."""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from enum import Enum
import ipaddress
import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path


class CalibrationStage(Enum):
    RUNNER_TEMP = "runner-temp-validation"
    DIRECTORY = "fixture-directory"
    SOCKETS = "socket-setup"
    TCP_BIND = "tcp-listener"
    UDP_BIND = "udp-listener"
    CHILD_START = "child-start"
    TCP_RECEIVE = "tcp-marker"
    UDP_RECEIVE = "udp-marker"
    CHILD_EXIT = "child-exit"
    CHILD_FILES = "child-fixture-writes"
    CHILD_TCP = "child-tcp-send"
    CHILD_UDP = "child-udp-send"
    PARENT_CLOCK = "parent-clock"

    def failure_message(self) -> str:
        return f"N12 calibration failed at {self.value}."


class CalibrationFailure(Exception):
    """A fixture failure identified by a fixed stage label."""


@contextmanager
def calibration_stage(stage: CalibrationStage):
    try:
        yield
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as exc:
        raise CalibrationFailure(stage.failure_message()) from exc


def calibration_failure_stages(stderr: bytes) -> list[str]:
    labels = {stage.failure_message().encode("ascii"): stage.value for stage in CalibrationStage}
    return list(dict.fromkeys(labels[line] for line in stderr.splitlines() if line in labels))


def parent_creation_ticks() -> int | None:
    if os.name != "nt":
        return None
    import ctypes
    from ctypes import wintypes

    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    current = kernel.GetCurrentProcess
    current.argtypes = ()
    current.restype = wintypes.HANDLE
    get_times = kernel.GetProcessTimes
    get_times.argtypes = (wintypes.HANDLE,) + (ctypes.POINTER(wintypes.FILETIME),) * 4
    get_times.restype = wintypes.BOOL
    created, exited, kernel_time, user_time = (wintypes.FILETIME() for _ in range(4))
    if not get_times(current(), ctypes.byref(created), ctypes.byref(exited),
                     ctypes.byref(kernel_time), ctypes.byref(user_time)):
        return None
    filetime = created.dwHighDateTime << 32 | created.dwLowDateTime
    # Convert the Windows FILETIME epoch to the UTC ticks used in the capture.
    return filetime + 504911232000000000 if filetime else None


def calibrate_child(original: Path, renamed: Path, port: int) -> None:
    with calibration_stage(CalibrationStage.CHILD_FILES):
        with original.open("xb") as fixture:
            fixture.write(b"n12 calibration fixture\n")
        with original.open("r+b") as fixture:
            fixture.write(b"probe")
            fixture.flush()
            fixture.truncate(5)
        original.rename(renamed)
        renamed.unlink()
    with (
        calibration_stage(CalibrationStage.CHILD_TCP),
        socket.create_connection(("127.0.0.1", port), timeout=5) as client,
    ):
        client.sendall(b"tcp")
    with calibration_stage(CalibrationStage.CHILD_UDP), socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as client:
        client.connect(("127.0.0.1", port))
        if client.send(b"udp") != 3:
            raise RuntimeError("UDP marker was not sent in full")


def calibrate(directory: Path, child_hold_seconds: int = 0) -> dict:
    if child_hold_seconds not in (0, 4):
        raise ValueError("unsupported calibration child lifetime")
    with calibration_stage(CalibrationStage.DIRECTORY):
        directory.mkdir()
    original, renamed = directory / "n12-marker.bin", directory / "n12-renamed.bin"
    with (
        calibration_stage(CalibrationStage.SOCKETS),
        socket.socket(socket.AF_INET, socket.SOCK_STREAM) as tcp,
        socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as udp,
    ):
        with calibration_stage(CalibrationStage.TCP_BIND):
            tcp.bind(("127.0.0.1", 0))
            tcp.listen(1)
            tcp.settimeout(5)
            address = tcp.getsockname()
        with calibration_stage(CalibrationStage.UDP_BIND):
            udp.bind(address)
            udp.settimeout(5)
        command = [sys.executable, __file__, "--child", str(directory), str(address[1])]
        if child_hold_seconds:
            command.extend(("--child-hold-seconds", str(child_hold_seconds)))
        with calibration_stage(CalibrationStage.CHILD_START):
            child = subprocess.Popen(command)
        try:
            with (
                calibration_stage(CalibrationStage.TCP_RECEIVE),
                tcp.accept()[0] as peer,
                peer.makefile("rb") as stream,
            ):
                peer.settimeout(5)
                if stream.read(3) != b"tcp":
                    raise RuntimeError("TCP marker not received")
                tcp_sender_port = peer.getpeername()[1]
            with calibration_stage(CalibrationStage.UDP_RECEIVE):
                payload, sender = udp.recvfrom(3)
                if payload != b"udp" or not ipaddress.ip_address(sender[0]).is_loopback:
                    raise RuntimeError("UDP marker not received from loopback")
            with calibration_stage(CalibrationStage.CHILD_EXIT):
                if child.wait(timeout=5 + child_hold_seconds) != 0 or original.exists() or renamed.exists():
                    raise RuntimeError("calibration child did not finish or left fixture files")
        finally:
            with calibration_stage(CalibrationStage.CHILD_EXIT):
                if child.poll() is None:
                    child.kill()
                    child.wait()
    with calibration_stage(CalibrationStage.PARENT_CLOCK):
        created_ticks = parent_creation_ticks()
    return {"role": "calibration", "pid": os.getpid(), "image": sys.executable, "child_pid": child.pid,
            "fixture": str(original), "renamed_fixture": str(renamed), "port": address[1],
            "tcp_sender_port": tcp_sender_port, "udp_sender_port": sender[1],
            "parent_created_utc_ticks": created_ticks}


def main():
    from n12_trace import local_disposable_path

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    parser.add_argument("port", type=int, nargs="?")
    parser.add_argument("--child", action="store_true")
    parser.add_argument("--child-hold-seconds", type=int, choices=(0, 4), default=0)
    args = parser.parse_args()
    try:
        with calibration_stage(CalibrationStage.RUNNER_TEMP):
            directory = local_disposable_path(args.directory, runner_temp_only=True)
        if args.child:
            if args.port is None or not 1 <= args.port <= 65535:
                raise ValueError("invalid calibration port")
            calibrate_child(directory / "n12-marker.bin", directory / "n12-renamed.bin", args.port)
            if args.child_hold_seconds:
                time.sleep(args.child_hold_seconds)
        else:
            print(json.dumps(calibrate(directory, args.child_hold_seconds)))
    except CalibrationFailure as exc:
        print(exc, file=sys.stderr)
        return 1
    except (ValueError, OSError, RuntimeError, subprocess.SubprocessError):
        print("N12 calibration blocked or failed.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
