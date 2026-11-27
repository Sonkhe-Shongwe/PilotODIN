"""Single inspection-only driver candidate. CLI and live gate remain disarmed."""
import contextlib
import hashlib
import json
import os
import re
import shutil
import signal
import stat
import sys
import tempfile
import time
from pathlib import Path

import inspection_core as c
import inspection_adapter as a

TOOLS = {'curl': '/usr/bin/curl', 'objdump': '/usr/bin/objdump', 'readelf': '/usr/bin/readelf'}
IMAGE = None  # no reviewed patched managed image selected; USN-9214-1
PACKAGE_PINS = {'curl': '8.5.0-2ubuntu10.16', 'binutils': '2.42-4ubuntu2.11',
                'binutils-x86-64-linux-gnu': '2.42-4ubuntu2.11'}
FLOOR = 2 * 1024**3
LIVE_ENABLED = False


def file_identity(path, size, algorithm):
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, 'rb') as inp:
        st = os.fstat(inp.fileno())
        c.need(stat.S_ISREG(st.st_mode) and st.st_nlink == 1 and st.st_size == size, 'STAGED_SIZE')
        h = hashlib.new(algorithm); total = 0
        while total < size:
            chunk = c.exact(inp, min(c.CHUNK, size - total)); total += len(chunk); h.update(chunk)
        c.need(not inp.read(1), 'STAGED_OVERRUN')
        return h.hexdigest()


@contextlib.contextmanager
def outer_limit(seconds):
    c.need(signal.getitimer(signal.ITIMER_REAL) == (0.0, 0.0), 'AMBIENT_TIMER')
    old = signal.getsignal(signal.SIGALRM)
    def expire(*_):
        raise c.Refused('OUTER_DEADLINE')
    signal.signal(signal.SIGALRM, expire)
    signal.setitimer(signal.ITIMER_REAL, seconds)
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, old)


def run_command(argv, scratch, deadline, seconds, cap=c.MAX_TOOL_OUTPUT):
    return a.bounded_process(argv, scratch, min(deadline, time.monotonic() + seconds), cap)


def observed_tools(scratch, deadline):
    """Historical exact candidates only; refuse changed image or version."""
    c.need(IMAGE is not None and os.environ.get('ImageOS') == 'ubuntu24' and os.environ.get('ImageVersion') == IMAGE, 'RUNNER_IMAGE')
    c.need(sys.implementation.name == 'cpython' and sys.version_info[:3] == (3, 12, 3)
           and os.uname().machine == 'x86_64' and Path(sys.executable).resolve() == Path('/usr/bin/python3.12'), 'PYTHON_TOOL')
    result = {}
    for package, version in PACKAGE_PINS.items():
        code, out, err = run_command(['/usr/bin/dpkg-query', '-W', '-f=${Status} ${Version}', package], scratch, deadline, 10, 4096)
        c.need(code == 0 and not err and out == ('install ok installed ' + version).encode(), 'TOOL_PACKAGE_VERSION')
    result['packages'] = PACKAGE_PINS.copy()
    for name, path in TOOLS.items():
        code, out, err = run_command([path, '-q', '--version'] if name == 'curl' else [path, '--version'], scratch, deadline, 10)
        c.tool_result(code, out, err)
        first = out.splitlines()[0].decode('ascii', 'strict')
        pattern = r'curl 8\.5\.0(?: |$)' if name == 'curl' else r'GNU (?:objdump|readelf) \(GNU Binutils for Ubuntu\) 2\.42(?: |$)'
        c.need(re.match(pattern, first), 'TOOL_VERSION')
        resolved = Path(path).resolve(strict=True)
        c.need(resolved.parent == Path('/usr/bin'), 'TOOL_ORIGIN')
        result[name] = {'path': path, 'resolved': str(resolved), 'version': first, 'sha256': file_identity(resolved, resolved.stat().st_size, 'sha256')}
    return result


def transfer(row, scratch, deadline):
    path = Path(scratch) / 'archive.bin'
    c.need(not path.exists(), 'DESTINATION_EXISTS')
    code, out, err = run_command(c.curl_command(TOOLS['curl'], row, path), scratch, deadline, 31, 4096)
    c.need(not err, 'TRANSFER_STDERR')
    algo = c.validate_row(row)
    c.need(file_identity(path, row['bytes'], algo) == row[algo], 'ARCHIVE_IDENTITY')
    with path.open('rb') as inp:
        raw = inp.read(row['bytes'] + 1)
    c.transfer_result(code, out, raw, row)
    return raw


def inspect_native(raw, row, item, scratch, deadline, command):
    path = a.stage_member(raw, row, item, scratch)
    try:
        c.need(file_identity(path, item['bytes'], 'sha256') == item['sha256'], 'NATIVE_HASH')
        exe = TOOLS['objdump' if item['format'] == 'PE' else 'readelf']
        code, out, err = command(c.tool_command(exe, item['format'], path), scratch, deadline, 10)
        return a.linkage(item['format'], code, out, err)
    finally:
        path.unlink()


def notice_and_lifecycle(raw, row, notices):
    result = []; notice_facts = []
    paths = {item['path']: item for item in notices}
    labels = {b'apache license': 'Apache notice title', b'gnu general public license': 'GPL notice title',
              b'gnu lesser general public license': 'LGPL notice title', b'mozilla public license': 'MPL notice title',
              b'mit license': 'MIT notice title', b'sil open font license': 'OFL notice title',
              b'bsd license': 'BSD notice title', b'permission is hereby granted': 'Permission grant phrase'}
    def consume(reader, name, size, directory):
        if row['kind'] == 'npm' and name == 'package/package.json':
            c.need(size <= c.MAX_META, 'METADATA_CAP')
            data = b''.join(c.exact(reader, min(c.CHUNK, size - p)) for p in range(0, size, c.CHUNK))
            scripts = c.strict_json(data).get('scripts', {})
            for key in ('preinstall', 'install', 'postinstall', 'prepare', 'prepublish', 'prepack', 'postpack'):
                if key in scripts:
                    result.append({'event': key, 'sha256': c.digest(scripts[key].encode())})
        elif name in paths:
            c.need(size == paths[name]['bytes'] and size <= c.MAX_NOTICES, 'NOTICE_SIZE')
            data = b''.join(c.exact(reader, min(c.CHUNK, size - p)) for p in range(0, size, c.CHUNK))
            c.need(c.digest(data) == paths[name]['sha256'], 'NOTICE_HASH')
            low = data.lower()
            notice_facts.append({'path': name, 'indicators': [value for key, value in labels.items() if key in low]})
        elif not directory:
            for p in range(0, size, c.CHUNK):
                c.exact(reader, min(c.CHUNK, size - p))
    c.members(raw, row['kind'], c.Paths(), consume)
    return result, notice_facts


def _collect(rows, root, acquire, command, observe, seconds=a.OUTER_SECONDS):
    """Internal fixture seam. Live caller must use the independently approved entrypoint."""
    receipt = a.Receipt(); receipt.deadline = time.monotonic() + seconds
    actual = 0; current = None; tools = {}; failure = None
    try:
        with outer_limit(seconds):
            c.need(shutil.disk_usage(root).free >= FLOOR, 'SCRATCH_FLOOR')
            with tempfile.TemporaryDirectory(prefix='pilotodin-inspect-', dir=root) as scratch:
                c.need(stat.S_IMODE(os.stat(scratch).st_mode) == 0o700, 'SCRATCH_MODE')
                tools = observe(scratch, receipt.deadline)
                for index, row in enumerate(rows):
                    current = index
                    receipt.reserve(row)
                    with tempfile.TemporaryDirectory(prefix='row-', dir=scratch) as stage:
                        raw = acquire(row, stage, receipt.deadline)
                        algo = c.validate_row(row)
                        c.need(len(raw) == row['bytes'] and c.digest(raw, algo) == row[algo], 'ARCHIVE_IDENTITY')
                        actual += len(raw)
                        facts = a.verified_inspect(raw, row)
                        facts['archive'] = {'index': index, 'bytes': row['bytes'], algo: row[algo]}
                        facts['lifecycle'], facts['notice_indicators'] = notice_and_lifecycle(raw, row, facts['notices'])
                        # Do not publish arbitrary unpinned licence declaration text.
                        metadata = facts['metadata']
                        for field in ('license', 'license_expression'):
                            if metadata.get(field) is not None:
                                metadata[field + '_sha256'] = c.digest(json.dumps(metadata.pop(field), ensure_ascii=True).encode())
                        # Publish validated archive facts before native probing; preserve on refusal.
                        c.need(len(json.dumps(receipt.rows + [facts], ensure_ascii=True).encode()) <= c.MAX_OUTPUT - 4096, 'BATCH_RECEIPT_CAP')
                        receipt.append(facts)
                        for item in facts['native']:
                            result = inspect_native(raw, row, item, stage, receipt.deadline, command)
                            candidate = {**item, 'linkage': result}
                            old = facts['native']; new = [candidate if x is item else x for x in old]
                            updated = {**facts, 'native': new}
                            proposed = receipt.rows[:-1] + [updated]
                            c.need(len(json.dumps(proposed, ensure_ascii=True).encode()) <= c.MAX_OUTPUT - 4096, 'BATCH_RECEIPT_CAP')
                            facts['native'] = new
                    c.need(time.monotonic() < receipt.deadline, 'OUTER_DEADLINE')
            receipt.terminal = 'INSPECTED_UNRESOLVED_USE_RIGHTS'
    except Exception as exc:
        receipt.refuse()
        reason = str(exc) if type(exc) is c.Refused else ''
        failure = reason if re.fullmatch(r'[A-Z][A-Z0-9_]{0,63}', reason) else 'INSPECTION_REFUSED'
    result = {**receipt.snapshot(), 'verified_body_bytes': actual, 'current_index': current, 'failure': failure, 'tools': tools}
    if len(json.dumps(result, ensure_ascii=True).encode()) > c.MAX_OUTPUT:
        # Keep prior factual rows, not an oversize unstructured output.
        result['tools'] = {}; result['status'] = 'REFUSED_UNRESOLVED'; result['failure'] = 'BATCH_RECEIPT_CAP'
    c.need(len(json.dumps(result, ensure_ascii=True).encode()) <= c.MAX_OUTPUT, 'BATCH_RECEIPT_CAP')
    return result


def run_live(manifest, root):
    c.need(LIVE_ENABLED, 'DISARMED')
    return _collect(c.projection(manifest), root, transfer, run_command, observed_tools)


if __name__ == '__main__':
    raise SystemExit('DISARMED_INSPECTION_DRIVER_ONLY')
