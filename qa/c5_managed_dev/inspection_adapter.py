"""Disarmed C-D09 orchestration primitives; no production entrypoint or live wiring."""
import hashlib
import json
import os
import re
import selectors
import signal
import stat
import struct
import subprocess
import tempfile
import time
import zipfile
import zlib
from pathlib import Path

import inspection_core as c

EOCD = struct.Struct('<4s4H2IH')
LOCAL = struct.Struct('<4s5H3I2H')
CENTRAL = struct.Struct('<4s6H3I5H2I')
MAX_GETS = 42
MAX_BODY = 214328914
OUTER_SECONDS = 1800


def strict_zip(raw):
    """Classic ZIP only: contiguous local records, exact central directory and CRC."""
    c.need(len(raw) >= EOCD.size, 'ZIP_END')
    end = len(raw) - EOCD.size
    sig, disk, cd_disk, n_disk, count, size, offset, comment = EOCD.unpack_from(raw, end)
    c.need(sig == b'PK\x05\x06' and disk == cd_disk == comment == 0 and n_disk == count
           and 0 < count <= c.MAX_MEMBERS and offset + size == end, 'ZIP_END')
    cursor = offset
    rows = []
    paths = c.Paths()
    for _ in range(count):
        c.need(cursor + CENTRAL.size <= end, 'ZIP_CENTRAL_BOUNDS')
        sig, made, ver, flags, method, tm, dt, crc, packed, expanded, nl, el, cl, disk, internal, attrs, loc = CENTRAL.unpack_from(raw, cursor)
        cursor += CENTRAL.size
        c.need(sig == b'PK\x01\x02' and made >> 8 in (0, 3) and ver <= 20 and flags in (0, 2, 4, 6, 0x800, 0x802, 0x804, 0x806)
               and method in (0, 8) and (method != 0 or flags in (0, 0x800)) and el == cl == disk == 0
               and 0 < nl <= 1024 and cursor + nl <= end and (method != 0 or packed == expanded), 'ZIP_CENTRAL_FORMAT')
        name = raw[cursor:cursor + nl]; cursor += nl
        directory = name.endswith(b'/'); mode = stat.S_IFMT(attrs >> 16)
        c.need(not attrs & 0x448 and mode in (0, stat.S_IFDIR if directory else stat.S_IFREG)
               and not (attrs & 0x10 and not directory) and (not directory or expanded == crc == 0), 'ZIP_MODE')
        paths.add(name.decode('ascii'), expanded, directory)
        rows.append((loc, ver, flags, method, tm, dt, crc, packed, expanded, name))
    c.need(cursor == end, 'ZIP_CENTRAL_LAYOUT')
    cursor = 0
    for loc, ver, flags, method, tm, dt, crc, packed, expanded, name in sorted(rows):
        c.need(loc == cursor and loc + LOCAL.size <= offset, 'ZIP_LOCAL_LAYOUT')
        sig, lv, lf, lm, lt, ld, lc, lp, le, nl, el = LOCAL.unpack_from(raw, loc)
        start = loc + LOCAL.size
        c.need(sig == b'PK\x03\x04' and (lv, lf, lm, lt, ld, lc, lp, le) == (ver, flags, method, tm, dt, crc, packed, expanded)
               and el == 0 and nl == len(name) and raw[start:start + nl] == name, 'ZIP_LOCAL_MISMATCH')
        start += nl; cursor = start + packed
        c.need(cursor <= offset, 'ZIP_LOCAL_BOUNDS')
        checksum = observed = 0
        stream = zlib.decompressobj(-15) if method == 8 else None
        for pos in range(start, cursor, c.CHUNK):
            chunk = raw[pos:min(pos + c.CHUNK, cursor)]
            while chunk:
                out = stream.decompress(chunk, min(c.CHUNK, expanded - observed + 1)) if stream else chunk
                observed += len(out); checksum = zlib.crc32(out, checksum)
                c.need(observed <= expanded, 'ZIP_EXPANSION')
                if not stream:
                    break
                c.need(not stream.unused_data, 'ZIP_DEFLATE_TRAILING')
                tail = stream.unconsumed_tail
                c.need(len(tail) < len(chunk) or bool(out), 'ZIP_DEFLATE_STALLED')
                chunk = tail
        c.need((not stream or stream.eof) and observed == expanded and checksum == crc, 'ZIP_CRC_SIZE')
    c.need(cursor == offset, 'ZIP_LOCAL_LAYOUT')


def verified_inspect(raw, row):
    algo = c.validate_row(row)
    c.need(len(raw) == row['bytes'] and c.digest(raw, algo) == row[algo], 'ARCHIVE_IDENTITY')
    if row['kind'] != 'npm':
        strict_zip(raw)
    return c.inspect(raw, row)


def stage_member(raw, row, item, scratch):
    """Re-read verified immutable archive; stage one member under a generated name."""
    facts = verified_inspect(raw, row)
    c.need(item in facts['native'] and item['format'] in ('PE', 'ELF'), 'NATIVE_SCOPE')
    target = Path(scratch) / 'native-member.bin'
    found = False
    def consume(reader, name, size, directory):
        nonlocal found
        if name != item['path']:
            for pos in range(0, size, c.CHUNK):
                c.exact(reader, min(c.CHUNK, size - pos))
            return
        c.need(not found and not directory and size == item['bytes'], 'NATIVE_IDENTITY')
        h = hashlib.sha256()
        fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, 'wb') as out:
            for pos in range(0, size, c.CHUNK):
                chunk = c.exact(reader, min(c.CHUNK, size - pos)); h.update(chunk); out.write(chunk)
        c.need(h.hexdigest() == item['sha256'], 'NATIVE_HASH')
        found = True
    c.members(raw, row['kind'], c.Paths(), consume)
    c.need(found, 'NATIVE_MISSING')
    return target


def bounded_process(argv, scratch, deadline, cap):
    """Linux-only capture; retain the group leader until group cleanup is issued."""
    started = time.monotonic()
    c.need(0 < cap <= c.MAX_TOOL_OUTPUT and started < deadline, 'PROCESS_BOUNDS')
    c.need(signal.getsignal(signal.SIGCHLD) == signal.SIG_DFL, 'PROCESS_REAPER')
    env = {'PATH': '/usr/bin:/bin', 'HOME': str(scratch), 'TMPDIR': str(scratch), 'LC_ALL': 'C'}
    c.need(os.path.isabs(argv[0]), 'TOOL_PATH')
    # Reserve part of the caller's existing deadline for kill and bounded reaping.
    work_deadline = deadline - min(0.5, (deadline - started) / 2)
    child = subprocess.Popen(argv, cwd=scratch, env=env, stdin=subprocess.DEVNULL,
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True)
    buffers = [bytearray(), bytearray()]; total = 0
    try:
        with selectors.DefaultSelector() as sel:
            for i, pipe in enumerate((child.stdout, child.stderr)):
                sel.register(pipe, selectors.EVENT_READ, i)
            while sel.get_map():
                remaining = work_deadline - time.monotonic()
                c.need(remaining > 0, 'PROCESS_TIMEOUT')
                events = sel.select(remaining)
                c.need(bool(events), 'PROCESS_TIMEOUT')
                for key, _ in events:
                    chunk = os.read(key.fd, min(c.CHUNK, cap - total + 1))
                    if not chunk:
                        sel.unregister(key.fileobj); continue
                    total += len(chunk)
                    c.need(total <= cap, 'PROCESS_OUTPUT_CAP')
                    buffers[key.data].extend(chunk)
        # Observe exit without reaping: no poll()/wait() before killpg().
        while True:
            remaining = work_deadline - time.monotonic()
            c.need(remaining > 0, 'PROCESS_TIMEOUT')
            if os.waitid(os.P_PID, child.pid, os.WEXITED | os.WNOHANG | os.WNOWAIT) is not None:
                break
            time.sleep(min(0.01, remaining))
    finally:
        try:
            # ECHILD means ownership is lost; never signal a potentially reused ID.
            try:
                os.waitid(os.P_PID, child.pid, os.WEXITED | os.WNOHANG | os.WNOWAIT)
            except ChildProcessError:
                raise c.Refused('PROCESS_REAPER') from None
            try:
                os.killpg(child.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            try:
                child.wait(timeout=max(0, deadline - time.monotonic()))
            except subprocess.TimeoutExpired:
                raise c.Refused('PROCESS_SETTLEMENT') from None
        finally:
            child.stdout.close(); child.stderr.close()
    c.need(time.monotonic() < deadline, 'PROCESS_SETTLEMENT')
    return child.returncode, bytes(buffers[0]), bytes(buffers[1])


def linkage(fmt, code, stdout, stderr):
    """Project only finite safe labels, not raw tool output or licence conclusions."""
    fingerprint = c.tool_result(code, stdout, stderr)
    text = stdout.decode('ascii', 'strict')
    if fmt == 'ELF':
        machines = re.findall(r'^\s*Machine:\s*(.+)$', text, re.M)
        libs = re.findall(r'\(NEEDED\)\s+Shared library: \[([^\]]+)\]', text)
        versions = re.findall(r'\bName:\s+(\S+)\s+Flags:', text)
    elif fmt == 'PE':
        machines = re.findall(r'file format (\S+)', text)
        libs = re.findall(r'^\s*DLL Name:\s*(\S+)\s*$', text, re.M)
        versions = []
    else:
        raise c.Refused('UNSUPPORTED_NATIVE_FORMAT')
    c.need(len(machines) == 1 and machines[0] in ('Advanced Micro Devices X86-64', 'pei-x86-64', 'pe-x86-64'), 'NATIVE_ARCH')
    c.need(len(libs) + len(versions) <= 1024 and all(re.fullmatch(r'[A-Za-z0-9_.+-]{1,128}', s) for s in libs + versions), 'LINKAGE_LABEL')
    return {'architecture': machines[0], 'imports': sorted(set(libs)), 'versions': sorted(set(versions)), 'output_sha256': fingerprint, 'status': 'UNRESOLVED_STATIC_COMPONENTS'}


class Receipt:
    def __init__(self, now=time.monotonic):
        self.now = now; self.deadline = now() + OUTER_SECONDS
        self.attempts = 0; self.reserved = 0; self.seen = set(); self.rows = []
        self.terminal = 'INCOMPLETE'

    def reserve(self, row):
        c.validate_row(row)
        c.need(self.terminal == 'INCOMPLETE' and self.now() < self.deadline, 'BATCH_STATE_OR_TIME')
        c.need(row['url'] not in self.seen and self.attempts < MAX_GETS and self.reserved + row['bytes'] <= MAX_BODY, 'BATCH_SCOPE')
        self.seen.add(row['url']); self.attempts += 1; self.reserved += row['bytes']

    def append(self, facts):
        c.need(self.terminal == 'INCOMPLETE' and self.now() < self.deadline and len(self.rows) < self.attempts, 'BATCH_STATE_OR_TIME')
        candidate = self.rows + [facts]
        c.need(len(json.dumps(candidate, ensure_ascii=True).encode()) <= c.MAX_OUTPUT - 1024, 'BATCH_RECEIPT_CAP')
        self.rows = candidate

    def refuse(self):
        self.terminal = 'REFUSED_UNRESOLVED'

    def snapshot(self):
        return {'attempts': self.attempts, 'reserved_bytes': self.reserved, 'rows': self.rows, 'status': self.terminal}


if __name__ == '__main__':
    raise SystemExit('DISARMED_ADAPTER_ONLY')
