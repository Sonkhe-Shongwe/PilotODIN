"""Read-only C5 candidate ZIP validation. No extraction or production gate.

Conservative classic ZIP subset, only independently reviewed regular file
members, stored or raw DEFLATE. Unknown archive forms refuse. Bounds are
review limits, not claims about actual upstream member sizes or RAM headroom.
The caller must establish independent expected identities and owned paths.
"""
from __future__ import annotations

import hashlib
from pathlib import Path
import re
import stat
import struct
import zlib

from tools.build_input_preflight import (
    Blocked, DEVICE, HEX64, fields, read_exact, require,
)

MAX_ARCHIVE = 32 * 1024 * 1024
MAX_MEMBER = 128 * 1024 * 1024
MAX_EXPANDED = 256 * 1024 * 1024
MAX_ENTRIES = 512
CHUNK = 64 * 1024
EOCD = struct.Struct("<4s4H2IH")
CENTRAL = struct.Struct("<4s6H3I5H2I")
LOCAL = struct.Struct("<4s5H3I2H")
COMPONENT = re.compile(r"[A-Za-z0-9_][A-Za-z0-9_.-]{0,119}", re.ASCII)


def safe_name(name):
    require(type(name) is str and 0 < len(name) <= 240,
            "UNSAFE_ZIP_NAME")
    parts = name.split("/")
    require(len(parts) <= 12 and all(
        COMPONENT.fullmatch(p) and not p.endswith(".") and not DEVICE.match(p)
        for p in parts), "UNSAFE_ZIP_NAME")
    return name


def safe_inventory(names):
    require(0 < len(names) <= MAX_ENTRIES, "ZIP_ENTRY_LIMIT")
    folded = set()
    directories = {}
    for name in names:
        safe_name(name)
        key = name.casefold()
        require(key not in folded, "ZIP_DUPLICATE_NAME")
        folded.add(key)
        parts = name.split("/")
        for i in range(1, len(parts)):
            prefix = "/".join(parts[:i])
            lower = prefix.casefold()
            require(lower not in directories or directories[lower] == prefix,
                    "ZIP_DIRECTORY_CASE_COLLISION")
            directories[lower] = prefix
    require(not folded.intersection(directories), "ZIP_FILE_DIRECTORY_COLLISION")


def expected_inventory(expected):
    fields(expected, {"bytes", "sha256", "members"})
    require(type(expected["bytes"]) is int and EOCD.size < expected["bytes"] <= MAX_ARCHIVE
            and type(expected["sha256"]) is str and HEX64.fullmatch(expected["sha256"]),
            "ZIP_EXPECTED_ARCHIVE_IDENTITY")
    members = expected["members"]
    require(type(members) is dict, "ZIP_EXPECTED_MEMBERS")
    safe_inventory(list(members))
    total = 0
    for row in members.values():
        fields(row, {"bytes", "sha256"})
        require(type(row["bytes"]) is int and 0 <= row["bytes"] <= MAX_MEMBER
                and type(row["sha256"]) is str and HEX64.fullmatch(row["sha256"]),
                "ZIP_EXPECTED_MEMBER_IDENTITY")
        total += row["bytes"]
    require(total <= MAX_EXPANDED, "ZIP_EXPANDED_LIMIT")
    return members


def _name(raw):
    try:
        return safe_name(raw.decode("ascii"))
    except UnicodeError:
        raise Blocked("UNSAFE_ZIP_NAME") from None


def _unpack(fmt, raw, offset, limit):
    require(0 <= offset and offset + fmt.size <= limit <= len(raw),
            "ZIP_HEADER_BOUNDS")
    return fmt.unpack_from(raw, offset)


def _central(raw, members):
    end = len(raw) - EOCD.size
    sig, disk, cd_disk, entries_disk, entries, size, offset, comment = _unpack(
        EOCD, raw, end, len(raw))
    require(sig == b"PK\x05\x06" and disk == cd_disk == comment == 0
            and entries_disk == entries == len(members)
            and 0 < entries <= MAX_ENTRIES and offset + size == end,
            "ZIP_END_LAYOUT")
    pos = offset
    rows = []
    for _ in range(entries):
        (sig, made, needed, flags, method, time, date, crc, packed, expanded,
         name_len, extra_len, comment_len, start_disk, internal, attrs,
         local_offset) = _unpack(CENTRAL, raw, pos, end)
        require(sig == b"PK\x01\x02" and start_disk == 0
                and extra_len == comment_len == 0 and 0 < name_len <= 240
                and needed <= 20 and flags in (0, 0x800)
                and method in (0, 8), "ZIP_UNSUPPORTED_CENTRAL")
        require(made >> 8 in (0, 3), "ZIP_UNSUPPORTED_CREATOR")
        # Windows directory, volume-label, device and reparse bits; UNIX file
        # type must be regular or unspecified (permission-only mode).
        require(not attrs & (0x10 | 0x08 | 0x40 | 0x400)
                and stat.S_IFMT(attrs >> 16) in (0, stat.S_IFREG),
                "ZIP_NONREGULAR_MEMBER")
        start = pos + CENTRAL.size
        pos = start + name_len
        require(pos <= end and local_offset < offset and packed <= offset
                and expanded <= MAX_MEMBER, "ZIP_MEMBER_BOUNDS")
        name = _name(raw[start:pos])
        require(name in members and expanded == members[name]["bytes"],
                "ZIP_MEMBER_NOT_EXPECTED")
        require(method != 0 or packed == expanded, "ZIP_STORED_SIZE")
        rows.append((name, needed, flags, method, time, date, crc, packed,
                     expanded, local_offset))
    require(pos == end, "ZIP_CENTRAL_LENGTH")
    names = [row[0] for row in rows]
    safe_inventory(names)
    require(set(names) == set(members), "ZIP_MEMBER_INVENTORY")
    return offset, rows


def _member_bytes(raw, start, packed, method, expanded, crc, expected_sha):
    """Hash decompressed bytes in bounded chunks; enforce EOF, size and CRC."""
    h = hashlib.sha256()
    checksum = 0
    count = 0

    def consume(chunk):
        nonlocal checksum, count
        count += len(chunk)
        require(count <= expanded, "ZIP_EXPANDED_SIZE")
        h.update(chunk)
        checksum = zlib.crc32(chunk, checksum)

    end = start + packed
    if method == 0:
        for pos in range(start, end, CHUNK):
            consume(raw[pos:min(pos + CHUNK, end)])
    else:
        stream = zlib.decompressobj(-zlib.MAX_WBITS)
        for pos in range(start, end, CHUNK):
            require(not stream.eof, "ZIP_DEFLATE_TRAILING")
            data = raw[pos:min(pos + CHUNK, end)]
            while data:
                out = stream.decompress(data, min(CHUNK, expanded - count + 1))
                consume(out)
                require(not stream.unused_data, "ZIP_DEFLATE_TRAILING")
                tail = stream.unconsumed_tail
                require(len(tail) < len(data) or bool(out), "ZIP_DEFLATE_STALLED")
                data = tail
        require(stream.eof and not stream.unconsumed_tail and not stream.unused_data,
                "ZIP_DEFLATE_INCOMPLETE")
    require(count == expanded and checksum & 0xffffffff == crc
            and h.hexdigest() == expected_sha, "ZIP_MEMBER_DIGEST")


def verify_candidate_archive(path: Path, expected) -> None:
    """Validate exact reviewed archive and all members, never extract.

    Use the same captured, hash-verified byte snapshot for all parsing. This
    is not a proof of physical ancestor ownership or later atomic consumption.
    A caller-supplied expectation is not independently authenticated here.
    """
    members = expected_inventory(expected)
    try:
        digest, raw = read_exact(Path(path), size=expected["bytes"],
                                 collect=True, limit=MAX_ARCHIVE)
        require(digest == expected["sha256"], "ZIP_ARCHIVE_DIGEST")
        cd_offset, rows = _central(raw, members)
        # Strict contiguous local layout rejects overlapping, duplicate,
        # hidden or orphan records, preambles and gaps.
        next_offset = 0
        for (name, needed, flags, method, time, date, crc, packed, expanded,
             offset) in sorted(rows, key=lambda row: row[-1]):
            require(offset == next_offset, "ZIP_LOCAL_LAYOUT")
            (sig, n, f, m, t, d, c, p, e, name_len, extra_len) = _unpack(
                LOCAL, raw, offset, cd_offset)
            require(sig == b"PK\x03\x04" and
                    (n, f, m, t, d, c, p, e) ==
                    (needed, flags, method, time, date, crc, packed, expanded)
                    and extra_len == 0 and 0 < name_len <= 240,
                    "ZIP_LOCAL_CENTRAL_MISMATCH")
            start = offset + LOCAL.size
            data_start = start + name_len
            next_offset = data_start + packed
            require(next_offset <= cd_offset and _name(raw[start:data_start]) == name,
                    "ZIP_LOCAL_NAME_OR_BOUNDS")
            _member_bytes(raw, data_start, packed, method, expanded, crc,
                          members[name]["sha256"])
        require(next_offset == cd_offset, "ZIP_LOCAL_LAYOUT")
    except (OSError, struct.error, zlib.error):
        raise Blocked("ZIP_UNREADABLE_OR_MALFORMED") from None
