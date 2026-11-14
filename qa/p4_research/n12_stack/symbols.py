"""Resolve selected kernel frames against runner-local images and public PDBs."""
import json
import os
import re
import struct
import sys
from bisect import bisect_right
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
    exception_rva, exception_size = struct.unpack_from("<II", data, opt + 112 + 3 * 8)
    sections = []
    executable = {}
    for index in range(section_count):
        section = opt + opt_size + 40 * index
        virtual_size, rva, raw_size, offset = struct.unpack_from("<IIII", data, section + 8)
        flags, = struct.unpack_from("<I", data, section + 36)
        sections.append((rva, raw_size, offset))
        if flags & 0x20000000:
            executable[index + 1] = (rva, rva + max(virtual_size, raw_size))
    def file_offset(address, length):
        starts = [offset + address - rva for rva, raw_size, offset in sections
                  if rva <= address and address + length <= rva + raw_size]
        if len(starts) != 1 or starts[0] + length > len(data):
            raise ValueError("unmapped PE data directory")
        return starts[0]

    if not debug_size or debug_size % 28 or exception_size % 12:
        raise ValueError("invalid PE directory length")
    debug_offset = file_offset(debug_rva, debug_size)
    pdbs = set()
    for offset in range(debug_offset, debug_offset + debug_size, 28):
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
    ranges = []
    if exception_size:
        begin = file_offset(exception_rva, exception_size)
        for start, end, _ in struct.iter_unpack("<III", data[begin:begin + exception_size]):
            if start < end <= size:
                ranges.append((start, end))
    return (size, checksum, timestamp), pdbs.pop(), executable, sorted(set(ranges))


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



def pdb_public_functions(path, key, executable):
    data = path.read_bytes()
    if data[:32] != b"Microsoft C/C++ MSF 7.00\r\n\x1aDS\0\0\0":
        raise ValueError("unsupported MSF header")
    block, _, blocks, directory_size, _, directory_map = struct.unpack_from("<6I", data, 32)
    if block not in {512, 1024, 2048, 4096, 8192, 16384, 32768} or blocks * block != len(data):
        raise ValueError("invalid MSF block size")
    count = (directory_size + block - 1) // block
    if count * 4 > block or directory_map >= blocks:
        raise ValueError("unsupported MSF directory map")

    def read_blocks(indices, length):
        if any(index >= blocks for index in indices):
            raise ValueError("MSF block outside file")
        return b"".join(data[index * block:(index + 1) * block] for index in indices)[:length]

    indices = struct.unpack_from(f"<{count}I", data, directory_map * block)
    directory = read_blocks(indices, directory_size)
    streams, = struct.unpack_from("<I", directory)
    sizes = struct.unpack_from(f"<{streams}I", directory, 4)
    position = 4 + streams * 4
    locations = []
    for size in sizes:
        locations.append(position)
        if size != 0xFFFFFFFF:
            position += ((size + block - 1) // block) * 4
    if position != len(directory):
        raise ValueError("invalid MSF stream directory")

    def stream(index):
        size = sizes[index]
        if size == 0xFFFFFFFF or size > len(data):
            raise ValueError("PDB stream absent")
        total = (size + block - 1) // block
        return read_blocks(struct.unpack_from(f"<{total}I", directory, locations[index]), size)

    info = stream(1)
    age, = struct.unpack_from("<I", info, 8)
    guid = UUID(bytes_le=info[12:28])
    if f"{guid.hex.upper()}{age:X}" != key:
        raise ValueError("PDB GUID or age differs from PE CodeView")
    dbi = stream(3)
    signature, _, dbi_age = struct.unpack_from("<iII", dbi)
    if signature != -1 or dbi_age != age:
        raise ValueError("unsupported DBI stream header")
    symbol_index, = struct.unpack_from("<H", dbi, 20)
    # Refuse address remapping unless the PDB uses ordinary image sections.
    substreams = struct.unpack_from("<5i", dbi, 24)
    optional, ec = struct.unpack_from("<2i", dbi, 48)
    if min(*substreams, optional, ec) < 0:
        raise ValueError("invalid DBI substream size")
    offset = 64 + sum(substreams) + ec
    if offset + optional > len(dbi):
        raise ValueError("invalid DBI optional header")
    if optional >= 10 and struct.unpack_from("<H", dbi, offset + 8)[0] != 0xFFFF:
        raise ValueError("unsupported OMAP address translation")

    symbols = stream(symbol_index)
    names = defaultdict(set)
    offset = 0
    while offset < len(symbols):
        length, kind = struct.unpack_from("<HH", symbols, offset)
        end = offset + 2 + length
        if length < 2 or end > len(symbols):
            raise ValueError("invalid CodeView record length")
        if kind == 0x110E and length >= 13:  # S_PUB32
            flags, displacement, segment = struct.unpack_from("<IIH", symbols, offset + 4)
            if flags & 3 and segment in executable:
                start, stop = executable[segment]
                name = symbols[offset + 14:end].split(b"\0", 1)[0].decode("ascii", errors="replace")
                if start + displacement < stop and SYMBOL_NAME.fullmatch(name):
                    names[start + displacement].add(name)
        offset = end
    return names


def resolve_frames(rvas, names, ranges):
    starts = [start for start, _ in ranges]
    result = {}
    for rva in rvas:
        if rva in names:
            result[rva] = sorted(names[rva])
            continue
        index = bisect_right(starts, rva) - 1
        if index >= 0:
            start, end = ranges[index]
            # Require an unwind range containing the frame and a public
            # function symbol at its start. A nearby symbol is insufficient.
            if rva < end and start in names and (index == 0 or ranges[index - 1][1] <= rva):
                result[rva] = sorted(names[start])
    return result


def resolve_module(module, identity, rvas, work):
    path = Path(os.environ["SystemRoot"]) / "System32" / MODULE_PATHS[module]
    try:
        local, (name, key), executable, ranges = pe_information(path)
    except (OSError, ValueError, struct.error):
        return "local-image-unreadable", {}
    size, checksum, timestamp = identity
    if not (size and timestamp and local[0] == size and local[2] == timestamp
            and (not checksum or local[1] == checksum)):
        return "trace-image-mismatch", {}
    rvas = sorted(rva for rva in rvas if any(start <= rva < end for start, end in executable.values()))
    if not rvas:
        return "no-executable-frame-addresses", {}
    cache = work / module
    status = download_pdb(cache, name, key)
    if status != "downloaded":
        return status, {}
    try:
        names = pdb_public_functions(cache / name, key, executable)
    except (OSError, ValueError, IndexError, struct.error):
        return "pdb-identity-or-format-rejected", {}
    resolved = resolve_frames(rvas, names, ranges)
    return ("resolved" if resolved else "matching-pdb-no-resolved-frames"), resolved


def report(targets, work):
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
        statuses[module], symbols[module] = resolve_module(module, identity, rvas, work)

    stacks = []
    for target in targets:
        names = []
        for frame in target["frames"]:
            module = frame["module"]
            aliases = symbols.get(module, {}).get(frame["rva"], ())
            if aliases:
                names.append({"frame": frame["frame"],
                              "functions": [f"{module}!{name}" for name in aliases]})
        stacks.append({"control": target["control"], "operation": target["operation"],
                       "stack_frames": target["stack_frames"], "resolved_frames": len(names),
                       "functions": names})
    return {"modules": statuses, "stacks": stacks}


if __name__ == "__main__":
    try:
        targets = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
        work = Path(sys.argv[2])
        work.mkdir()
        result = report(targets, work)
        print("N12 kernel symbol resolution: " + json.dumps(result), flush=True)
        resolved = {stack["operation"] for stack in result["stacks"]
                    if stack["control"] == "protected" and stack["resolved_frames"]}
        if resolved != {"write", "resize"}:
            sys.exit("Protected write and resize symbol coverage is incomplete.")
    except (OSError, ValueError, KeyError, IndexError, TypeError):
        sys.exit("The N12 kernel symbol report could not be produced.")
