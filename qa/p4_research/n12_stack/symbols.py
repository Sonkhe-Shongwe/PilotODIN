"""Resolve selected kernel frames against runner-local images and public PDBs."""
import json
import os
import re
import struct
import subprocess
import sys
from collections import defaultdict
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import urlopen
from uuid import UUID

MODULE_PATHS = {
    "ntoskrnl.exe": "ntoskrnl.exe",
    "ntkrnlmp.exe": "ntoskrnl.exe",
    "ntfs.sys": "drivers/ntfs.sys",
    "fltmgr.sys": "drivers/fltmgr.sys",
}
SYMBOL_SERVER = "https://msdl.microsoft.com/download/symbols"
PDB_NAME = re.compile(r"[A-Za-z0-9_.-]+\.pdb", re.ASCII | re.IGNORECASE)
SYMBOL_NAME = re.compile(r"[A-Za-z_?$@][A-Za-z0-9_?$@.]*", re.ASCII)
MAX_PDB_BYTES = 64 * 1024 * 1024


def pe_information(path):
    data = path.read_bytes()
    if data[:2] != b"MZ":
        raise ValueError("invalid DOS signature")
    pe, = struct.unpack_from("<I", data, 60)
    if data[pe:pe + 4] != b"PE\0\0":
        raise ValueError("invalid PE signature")
    machine, section_count, timestamp, _, _, opt_size, _ = struct.unpack_from("<HHIIIHH", data, pe + 4)
    opt = pe + 24
    if machine != 0x8664 or opt_size < 168 or struct.unpack_from("<H", data, opt)[0] != 0x20B:
        raise ValueError("expected x64 PE32+")
    size, _, checksum = struct.unpack_from("<III", data, opt + 56)
    directories, = struct.unpack_from("<I", data, opt + 108)
    if directories <= 6:
        raise ValueError("missing debug directory")
    debug_rva, debug_size = struct.unpack_from("<II", data, opt + 112 + 6 * 8)
    sections = []
    executable = []
    for index in range(section_count):
        section = opt + opt_size + 40 * index
        virtual_size, rva, raw_size, offset = struct.unpack_from("<IIII", data, section + 8)
        flags, = struct.unpack_from("<I", data, section + 36)
        sections.append((rva, raw_size, offset))
        if flags & 0x20000000:
            executable.append((rva, rva + max(virtual_size, raw_size)))
    starts = [offset + debug_rva - rva for rva, raw_size, offset in sections
              if rva <= debug_rva and debug_rva + debug_size <= rva + raw_size]
    if len(starts) != 1 or not debug_size or debug_size % 28:
        raise ValueError("invalid debug directory")
    pdbs = set()
    for offset in range(starts[0], starts[0] + debug_size, 28):
        kind, length, _, raw = struct.unpack_from("<IIII", data, offset + 12)
        if kind != 2 or length <= 24 or raw + length > len(data) or data[raw:raw + 4] != b"RSDS":
            continue
        guid = UUID(bytes_le=data[raw + 4:raw + 20])
        age, = struct.unpack_from("<I", data, raw + 20)
        pdb = data[raw + 24:raw + length].split(b"\0", 1)[0].decode("ascii").replace("\\", "/").rsplit("/", 1)[-1]
        if PDB_NAME.fullmatch(pdb):
            pdbs.add((pdb, f"{guid.hex.upper()}{age:X}"))
    if len(pdbs) != 1:
        raise ValueError("missing or ambiguous CodeView record")
    return (size, checksum, timestamp), pdbs.pop(), executable


def download_pdb(cache, name, key):
    cache.mkdir()
    path = cache / name
    try:
        with urlopen(f"{SYMBOL_SERVER}/{name}/{key}/{name}", timeout=20) as source, path.open("xb") as output:
            content_length = source.headers.get("Content-Length")
            if content_length is not None and int(content_length) > MAX_PDB_BYTES:
                return "pdb-size-limit"
            remaining = MAX_PDB_BYTES
            while chunk := source.read(65536):
                remaining -= len(chunk)
                if remaining < 0:
                    return "pdb-size-limit"
                output.write(chunk)
    except HTTPError as exc:
        return f"symbol-server-http-{exc.code}"
    except (OSError, URLError, ValueError):
        return "symbol-server-download-failed"
    return "downloaded"


def resolve_module(module, identity, rvas, work, resolver):
    path = Path(os.environ["SystemRoot"]) / "System32" / MODULE_PATHS[module]
    try:
        local, (name, key), executable = pe_information(path)
    except (OSError, ValueError, struct.error):
        return "local-image-unreadable", {}
    size, checksum, timestamp = identity
    if not (size and timestamp and local[0] == size and local[2] == timestamp
            and (not checksum or local[1] == checksum)):
        return "trace-image-mismatch", {}
    rvas = sorted(rva for rva in rvas if any(start <= rva < end for start, end in executable))
    if not rvas:
        return "no-executable-frame-addresses", {}
    cache = work / module
    status = download_pdb(cache, name, key)
    if status != "downloaded":
        return status, {}
    inputs = work / (module + ".input")
    output = work / (module + ".output")
    inputs.write_text("".join(f"{rva}\n" for rva in rvas), encoding="ascii")
    try:
        completed = subprocess.run([resolver, path, cache, inputs, output], timeout=30, check=False,
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if completed.returncode:
            return "local-resolver-rejected", {}
        allowed = set(rvas)
        symbols = {}
        for line in output.read_text(encoding="ascii").splitlines():
            value, symbol = line.split("\t", 1)
            rva = int(value)
            if rva in allowed and SYMBOL_NAME.fullmatch(symbol):
                symbols[rva] = symbol
    except (OSError, ValueError, subprocess.SubprocessError):
        return "local-resolver-unavailable", {}
    return ("resolved" if symbols else "matching-pdb-no-resolved-frames"), symbols


def report(targets, work, resolver):
    modules = defaultdict(lambda: defaultdict(set))
    for target in targets:
        for frame in target["frames"]:
            module = frame["module"]
            if module in MODULE_PATHS:
                identity = (frame["size"], frame["checksum"], frame["timestamp"])
                modules[module][identity].add(frame["rva"])
    statuses, symbols = {}, {}
    for module, versions in sorted(modules.items()):
        if len(versions) != 1:
            statuses[module] = "ambiguous-trace-image"
            continue
        identity, rvas = next(iter(versions.items()))
        statuses[module], symbols[module] = resolve_module(module, identity, rvas, work, resolver)

    stacks = []
    for target in targets:
        names = []
        for frame in target["frames"]:
            module = frame["module"]
            name = symbols.get(module, {}).get(frame["rva"])
            if name:
                names.append({"frame": frame["frame"], "function": f"{module}!{name}"})
        stacks.append({"control": target["control"], "operation": target["operation"],
                       "stack_frames": target["stack_frames"], "resolved_frames": len(names),
                       "functions": names})
    return {"modules": statuses, "stacks": stacks}


if __name__ == "__main__":
    try:
        targets = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
        work = Path(sys.argv[2])
        work.mkdir()
        result = report(targets, work, Path(sys.argv[3]))
        print("N12 kernel symbol resolution: " + json.dumps(result), flush=True)
        resolved = {stack["operation"] for stack in result["stacks"]
                    if stack["control"] == "protected" and stack["resolved_frames"]}
        if resolved != {"write", "resize"}:
            sys.exit("Protected write and resize symbol coverage is incomplete.")
    except (OSError, ValueError, KeyError, IndexError, TypeError):
        sys.exit("The N12 kernel symbol report could not be produced.")
