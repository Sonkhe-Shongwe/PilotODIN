"""Generate local TCP/UDP and file-operation markers for N12 calibration."""
from __future__ import annotations

import argparse
import ipaddress
import json
import os
import socket
import subprocess
import sys
from pathlib import Path


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
    with original.open("xb") as fixture:
        fixture.write(b"n12 calibration fixture\n")
    with original.open("r+b") as fixture:
        fixture.write(b"probe")
        fixture.flush()
        fixture.truncate(5)
    original.rename(renamed)
    renamed.unlink()
    with socket.create_connection(("127.0.0.1", port), timeout=5) as client:
        client.sendall(b"tcp")
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as client:
        client.sendto(b"udp", ("127.0.0.1", port))


def calibrate(directory: Path) -> dict:
    directory.mkdir()
    original, renamed = directory / "n12-marker.bin", directory / "n12-renamed.bin"
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as tcp, socket.socket(
        socket.AF_INET, socket.SOCK_DGRAM
    ) as udp:
        tcp.bind(("127.0.0.1", 0))
        tcp.listen(1)
        tcp.settimeout(5)
        address = tcp.getsockname()
        udp.bind(address)
        udp.settimeout(5)
        child = subprocess.Popen([sys.executable, __file__, "--child", str(directory), str(address[1])])
        try:
            with tcp.accept()[0] as peer, peer.makefile("rb") as stream:
                peer.settimeout(5)
                if stream.read(3) != b"tcp":
                    raise RuntimeError("TCP marker not received")
            payload, sender = udp.recvfrom(3)
            if payload != b"udp" or not ipaddress.ip_address(sender[0]).is_loopback:
                raise RuntimeError("UDP marker not received from loopback")
            if child.wait(timeout=5) != 0 or original.exists() or renamed.exists():
                raise RuntimeError("calibration child did not finish or left fixture files")
        finally:
            if child.poll() is None:
                child.kill()
                child.wait()
    return {"role": "calibration", "pid": os.getpid(), "image": sys.executable, "child_pid": child.pid,
            "fixture": str(original), "renamed_fixture": str(renamed), "port": address[1],
            "parent_created_utc_ticks": parent_creation_ticks()}


def main():
    from n12_trace import local_disposable_path

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    parser.add_argument("port", type=int, nargs="?")
    parser.add_argument("--child", action="store_true")
    args = parser.parse_args()
    try:
        directory = local_disposable_path(args.directory, runner_temp_only=True)
        if args.child:
            if args.port is None or not 1 <= args.port <= 65535:
                raise ValueError("invalid calibration port")
            calibrate_child(directory / "n12-marker.bin", directory / "n12-renamed.bin", args.port)
        else:
            print(json.dumps(calibrate(directory)))
    except (ValueError, OSError, RuntimeError, subprocess.SubprocessError):
        print("N12 calibration blocked or failed.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
