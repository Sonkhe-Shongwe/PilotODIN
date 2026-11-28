"""Disarmed exact SciPy ordinary-member policy, derived from pinned V2.
No transport or extraction. Internal parser, not an acquisition frontdoor.
Only inert fixtures are tested here. All other paths retain V2 rules.
"""
from __future__ import annotations

if __name__ == '__main__':
    raise SystemExit('DISARMED: exact SciPy parser has no acquisition CLI')

from dataclasses import dataclass

import base64
import csv
from email import policy
from email.parser import BytesParser
import hashlib
import io
import re
import stat
import struct
import zlib

BASELINE_BLOB = '9bf91fb983bd354f0b6db20dbb4eec32c447f369'
TARGET = 'scipy/io/tests/data/Transparent Busy.ani'
REAL_POLICY = 'C5_EXACT_SCIPY_MEMBER_V1'
FIXTURE_POLICY = 'C5_EXACT_SCIPY_MEMBER_FIXTURE_V1'
REAL_IDENTITY = ('scipy-1.17.1-cp311-cp311-manylinux_2_27_x86_64.manylinux_2_28_x86_64.whl',
                 35349300, '43af8d1f3bea642559019edfe64e9b11192a8978efbd1539d7bc2aaa23d92de4',
                 '7cdd5544eb610b86e000b6f0a21e86f84423faf0aacbb99990f3d41f25e1f314')
FIXTURE_IDENTITIES = (
    ('demo_pkg-1.2-py3-none-any.whl', 1768, 'e58c81fe38aa95a7acd20d8c2bbcb34346131fc8d6b62c1f395b2ec197be3d55',
     'a2921c016ac6278b536f3f8570dee36206af3e67b35ebef7746bf3bafcf07bf6'),
    ('demo_pkg-1.2-py3-none-any.whl', 1803, '47c4a1a92be4e7387ef8a7a78115a0e86568770e18281c7ce0ecd1e5bca095c8',
     'a2921c016ac6278b536f3f8570dee36206af3e67b35ebef7746bf3bafcf07bf6'),
)

@dataclass(frozen=True)
class _Permit:
    scope: str
    identity: tuple
    policy_blob: str

MAX_ARCHIVE = 36_607_512
MAX_MEMBERS = 50_000
MAX_MEMBER = 536_870_912
MAX_WHEEL = 1_073_741_824
MAX_TOTAL = 4_294_967_296
MAX_NOTICE = 1_048_576
MAX_NOTICES = 33_554_432
MAX_CONTROL = 16 * 1024 * 1024
MAX_PATH_BYTES = 16 * 1024 * 1024
MAX_DIRECTORIES = 50_000
CHUNK = 64 * 1024
EOCD = struct.Struct('<4s4H2IH')
CENTRAL = struct.Struct('<4s6H3I5H2I')
LOCAL = struct.Struct('<4s5H3I2H')
HEX = re.compile(r'[0-9a-f]{64}')
COMPONENT = re.compile(r'[A-Za-z0-9_.+!@=-]{1,255}', re.ASCII)
DEVICE = re.compile(r'(?:con|prn|aux|nul|com[1-9]|lpt[1-9])(?:\.|$)', re.I)
NOTICE = re.compile(r'(?:licen[cs]e|copying|notice|copyright|third[-_ ]?party|authors)(?:[._-].*)?$', re.I)
NATIVE = re.compile(r'\.(?:dll|pyd|so(?:\.[0-9]+)*|dylib|exe|lib|a|node)$', re.I)


class Blocked(ValueError):
    pass


def require(ok, reason):
    if not ok:
        raise Blocked(reason)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def name(raw):
    try:
        text = raw.decode('ascii') if isinstance(raw, bytes) else raw
    except UnicodeError:
        raise Blocked('UNSAFE_PATH') from None
    require(type(text) is str and 0 < len(text) <= 1024, 'UNSAFE_PATH')
    parts = text.split('/')
    require(len(parts) <= 32 and all(COMPONENT.fullmatch(p) and p not in ('.', '..')
            and not p.endswith('.') and not DEVICE.match(p) for p in parts), 'UNSAFE_PATH')
    return text


def _permit_identity(expected):
    return tuple(expected.get(k) for k in ('filename','bytes','sha256','metadata_sha256'))


def _validate_permit(permit, expected):
    require(type(permit) is _Permit and type(permit.policy_blob) is str
            and re.fullmatch(r'[0-9a-f]{40}', permit.policy_blob)
            and permit.identity == _permit_identity(expected), 'EXACT_POLICY_IDENTITY')
    require((permit.scope == REAL_POLICY and permit.identity == REAL_IDENTITY)
            or (permit.scope == FIXTURE_POLICY and permit.identity in FIXTURE_IDENTITIES),
            'EXACT_POLICY_IDENTITY')


def _member_name(raw, permit, *, regular):
    if (regular and type(permit) is _Permit
            and ((permit.scope == REAL_POLICY and permit.identity == REAL_IDENTITY)
                 or (permit.scope == FIXTURE_POLICY and permit.identity in FIXTURE_IDENTITIES))
            and (raw == TARGET or raw == TARGET.encode('ascii'))):
        return TARGET
    return name(raw)


def norm(value):
    require(type(value) is str and re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]*', value), 'DIST_NAME')
    return re.sub(r'[-_.]+', '-', value).lower()


def header(fmt, raw, offset, end):
    require(0 <= offset and offset + fmt.size <= end <= len(raw), 'HEADER_BOUNDS')
    return fmt.unpack_from(raw, offset)


def identities(raw, expected):
    require(type(raw) is bytes and type(expected) is dict, 'EXPECTED_INPUT')
    size = expected.get('bytes')
    digest = expected.get('sha256')
    md_digest = expected.get('metadata_sha256')
    require(type(size) is int and EOCD.size < size <= MAX_ARCHIVE and len(raw) == size,
            'ARCHIVE_SIZE')
    require(type(digest) is str and HEX.fullmatch(digest) and sha(raw) == digest,
            'ARCHIVE_HASH')
    require(type(md_digest) is str and HEX.fullmatch(md_digest), 'METADATA_EXPECTATION')
    fn = name(expected.get('filename'))
    require('/' not in fn and fn.endswith('.whl'), 'WHEEL_FILENAME')
    parts = fn[:-4].split('-')
    require(len(parts) in (5, 6), 'WHEEL_FILENAME')
    dist, version = parts[:2]
    require(norm(dist) == norm(expected.get('name')) and version == expected.get('version'),
            'WHEEL_IDENTITY')
    if len(parts) == 6:
        require(re.fullmatch(r'[0-9][A-Za-z0-9_]*', parts[2]), 'WHEEL_BUILD_TAG')
    tags = [p.split('.') for p in parts[-3:]]
    require(all(0 < len(group) <= 32 and len(group) == len(set(group))
                and all(re.fullmatch(r'[A-Za-z0-9_]+', t) for t in group) for group in tags), 'WHEEL_TAG')
    tagset = {f'{p}-{a}-{t}' for p in tags[0] for a in tags[1] for t in tags[2]}
    return fn, dist + '-' + version + '.dist-info', tagset


def classify_entry(raw_name, attrs, permit):
    """Distinguish safe directory records from regular and forbidden members."""
    mode = attrs >> 16
    kind = stat.S_IFMT(mode)
    require(not attrs & 0x400, 'ZIP_REPARSE_ATTRIBUTE')
    require(not attrs & (0x08 | 0x40), 'ZIP_SPECIAL_ATTRIBUTE')
    require(kind != stat.S_IFLNK, 'ZIP_SYMLINK')
    require(kind in (0, stat.S_IFREG, stat.S_IFDIR), 'ZIP_SPECIAL_MODE')
    slash = raw_name.endswith(b'/')
    directory_flag = bool(attrs & 0x10)
    if slash:
        require(0 < len(raw_name) <= 1024, 'UNSAFE_PATH')
        require(kind != stat.S_IFREG and (kind == stat.S_IFDIR or directory_flag)
                and not mode & (stat.S_ISUID | stat.S_ISGID | stat.S_ISVTX),
                'ZIP_DIRECTORY_ATTRIBUTES')
        return name(raw_name[:-1]) + '/', True
    require(not directory_flag and kind != stat.S_IFDIR, 'ZIP_DIRECTORY_ATTRIBUTES')
    return _member_name(raw_name, permit, regular=kind == stat.S_IFREG), False


def central(raw, permit):
    end = len(raw) - EOCD.size
    sig, disk, cd_disk, disk_count, count, size, offset, comment = header(EOCD, raw, end, len(raw))
    require(sig == b'PK\x05\x06' and disk == cd_disk == comment == 0 and disk_count == count
            and 0 < count <= MAX_MEMBERS and offset + size == end, 'ZIP_END')
    rows = []
    seen = set()
    files = set()
    dirs = {}
    total = path_bytes = 0
    pos = offset
    for _ in range(count):
        (sig, made, needed, flags, method, tm, date, crc, packed, expanded,
         nl, el, cl, start_disk, internal, attrs, local) = header(CENTRAL, raw, pos, end)
        require(sig == b'PK\x01\x02' and made >> 8 in (0, 3) and needed <= 20
                and flags in (0, 0x800, 2, 4, 6, 0x802, 0x804, 0x806)
                and method in (0, 8) and (method == 8 or flags in (0, 0x800))
                and el == cl == start_disk == 0 and 0 < nl <= 1024, 'ZIP_UNSUPPORTED')
        start = pos + CENTRAL.size
        pos = start + nl
        require(pos <= end and local < offset and packed <= offset and expanded <= MAX_MEMBER
                and (method != 0 or packed == expanded), 'ZIP_BOUNDS')
        path, directory = classify_entry(raw[start:pos], attrs, permit)
        canonical = path[:-1] if directory else path
        key = canonical.casefold()
        if directory:
            require(expanded == crc == 0, 'ZIP_DIRECTORY_PAYLOAD')
        else:
            files.add(key)
        path_bytes += len(path)
        require(path_bytes <= MAX_PATH_BYTES, 'ZIP_PATH_BUDGET')
        require(key not in seen, 'ZIP_DUPLICATE')
        seen.add(key)
        parts = canonical.split('/')
        for i in range(1, len(parts) + int(directory)):
            prefix = '/'.join(parts[:i]); lower = prefix.casefold()
            require(lower not in dirs or dirs[lower] == prefix, 'ZIP_DIRECTORY_CASE')
            dirs[lower] = prefix
            require(len(dirs) <= MAX_DIRECTORIES, 'ZIP_DIRECTORY_LIMIT')
        total += expanded
        require(total <= MAX_WHEEL, 'ZIP_WHEEL_EXPANSION')
        rows.append((path, needed, flags, method, tm, date, crc, packed, expanded, local))
    require(pos == end and not files.intersection(dirs), 'ZIP_CENTRAL_LAYOUT')
    return offset, rows, total


def member(raw, start, packed, method, expanded, crc, capture):
    hashes = {a: hashlib.new(a) for a in ('sha256', 'sha384', 'sha512')}
    size = checksum = 0
    collected = bytearray() if capture else None
    def consume(chunk):
        nonlocal size, checksum
        size += len(chunk)
        require(size <= expanded, 'ZIP_OBSERVED_EXPANSION')
        checksum = zlib.crc32(chunk, checksum)
        for h in hashes.values():
            h.update(chunk)
        if collected is not None:
            collected.extend(chunk)
    end = start + packed
    if method == 0:
        for pos in range(start, end, CHUNK):
            consume(raw[pos:min(pos + CHUNK, end)])
    else:
        stream = zlib.decompressobj(-zlib.MAX_WBITS)
        for pos in range(start, end, CHUNK):
            require(not stream.eof, 'ZIP_DEFLATE_TRAILING')
            data = raw[pos:min(pos + CHUNK, end)]
            while data:
                out = stream.decompress(data, min(CHUNK, expanded - size + 1))
                consume(out)
                require(not stream.unused_data, 'ZIP_DEFLATE_TRAILING')
                tail = stream.unconsumed_tail
                require(len(tail) < len(data) or bool(out), 'ZIP_DEFLATE_STALLED')
                data = tail
        require(stream.eof and not stream.unused_data and not stream.unconsumed_tail, 'ZIP_DEFLATE_INCOMPLETE')
    require(size == expanded and checksum & 0xffffffff == crc, 'ZIP_CRC_SIZE')
    return {'bytes': size, 'sha256': hashes['sha256'].hexdigest()}, {
        a: base64.urlsafe_b64encode(h.digest()).decode('ascii').rstrip('=') for a,h in hashes.items()
    }, bytes(collected) if collected is not None else None


def message(raw):
    require(b'\x00' not in raw, 'HEADER_NUL')
    obj = BytesParser(policy=policy.default).parsebytes(raw)
    require(not obj.defects and not obj.is_multipart(), 'HEADER_DEFECT')
    for _, value in obj.items():
        require(not getattr(value, 'defects', ()), 'HEADER_DEFECT')
    return obj


def single(msg, key, required=True):
    values = msg.get_all(key, [])
    require(len(values) == 1 or (not required and not values), 'HEADER_CARDINALITY')
    return str(values[0]) if values else None


def verify_record(raw, record, observed, permit):
    seen = set()
    for row in csv.reader(io.StringIO(raw.decode('utf-8', 'strict'), newline=''), strict=True):
        require(len(row) == 3, 'RECORD_ROW')
        path, digest, size = row
        _member_name(path, permit, regular=True)
        require(path in observed and path not in seen, 'RECORD_INVENTORY')
        seen.add(path)
        if path == record:
            require(digest == size == '', 'RECORD_SELF')
            continue
        m = re.fullmatch(r'(sha256|sha384|sha512)=([A-Za-z0-9_-]+)', digest)
        ident, hashes = observed[path]
        require(m is not None and size == str(ident['bytes']) and hashes[m[1]] == m[2], 'RECORD_DIGEST_SIZE')
    require(seen == set(observed), 'RECORD_INVENTORY')
    count = sum(path == TARGET for path in seen)
    require(count == 1, 'EXACT_MEMBER_ABSENT')
    return count


class _ExactBudget:
    """One candidate batch; reserve declared expansion before any decompression.

    Failed attempts consume reservations; create a new budget only for a new
    reviewed batch, not a retry. No acquisition or execution authority here.
    """
    def __init__(self):
        self.expanded = 0
        self.notices = 0
        self.seen = set()
        self.stopped = False

    def inspect(self, raw, expected, permit, *, capture_notices=False):
        require(not self.stopped, 'BATCH_STOPPED')
        try:
            require(type(capture_notices) is bool, 'NOTICE_CAPTURE_FLAG')
            return self._inspect(raw, expected, permit, capture_notices)
        except (UnicodeError, csv.Error, struct.error, zlib.error, RecursionError):
            self.stopped = True
            raise Blocked('MALFORMED_WHEEL') from None
        except BaseException:
            self.stopped = True
            raise

    def _inspect(self, raw, expected, permit, capture_notices):
        fn, distinfo, tagset = identities(raw, expected)
        _validate_permit(permit, expected)
        require(fn not in self.seen, 'BATCH_DUPLICATE')
        self.seen.add(fn)
        cd, rows, total = central(raw, permit)
        directories = sorted(r[0] for r in rows if r[0].endswith('/'))
        all_paths = {r[0] for r in rows}
        paths = all_paths - set(directories)
        central_count = sum(row[0] == TARGET for row in rows)
        require(central_count == 1 and TARGET in paths, 'EXACT_MEMBER_ABSENT')
        controls = {distinfo + '/' + x for x in ('METADATA', 'WHEEL', 'RECORD')}
        require(controls <= paths and all(not any(part.lower().endswith('.dist-info')
                for part in p.split('/')[1:]) and (not p.split('/')[0].lower().endswith('.dist-info')
                or p.startswith(distinfo + '/')) for p in all_paths), 'DIST_INFO_IDENTITY')
        require(not any(p in paths for p in (distinfo+'/RECORD.jws', distinfo+'/RECORD.p7s')), 'RECORD_SIGNATURE_UNSUPPORTED')
        declared = expected.get('license_files')
        require(type(declared) is list and all(type(x) is str for x in declared) and len(declared) == len(set(declared)), 'NOTICE_EXPECTATION')
        notices = {p for p in paths if NOTICE.fullmatch(p.rsplit('/', 1)[-1]) or p.startswith(distinfo+'/licenses/')}
        for item in declared:
            item = name(item)
            candidates = {distinfo+'/licenses/'+item, distinfo+'/'+item} & paths
            require(len(candidates) == 1, 'DECLARED_NOTICE_MISSING_OR_AMBIGUOUS')
            notices.update(candidates)
        require(TARGET not in notices and TARGET not in controls and not NATIVE.search(TARGET),
                'EXACT_MEMBER_ROLE')
        notice_size = 0
        for path, *_, expanded, local in rows:
            if path in notices:
                require(expanded <= MAX_NOTICE, 'NOTICE_FILE_LIMIT')
                notice_size += expanded
            if path in controls:
                require(expanded <= MAX_CONTROL, 'CONTROL_FILE_LIMIT')
        require(self.expanded + total <= MAX_TOTAL and self.notices + notice_size <= MAX_NOTICES,
                'BATCH_EXPANSION_LIMIT')
        self.expanded += total
        self.notices += notice_size
        observed = {}; contents = {}; notice_contents = {}; next_offset = 0
        for path, needed, flags, method, tm, date, crc, packed, expanded, local in sorted(rows, key=lambda r:r[-1]):
            require(local == next_offset, 'ZIP_LOCAL_LAYOUT')
            sig,n,f,m,t,d,c,p,e,nl,el = header(LOCAL, raw, local, cd)
            require(sig == b'PK\x03\x04' and (n,f,m,t,d,c,p,e)==(needed,flags,method,tm,date,crc,packed,expanded)
                    and el == 0 and 0 < nl <= 1024, 'ZIP_LOCAL_MISMATCH')
            start = local + LOCAL.size
            data_start = start + nl
            next_offset = data_start + packed
            require(next_offset <= cd and raw[start:data_start] == path.encode('ascii'), 'ZIP_LOCAL_NAME')
            ident, hashes, payload = member(raw, data_start, packed, method, expanded, crc, path in controls or (capture_notices and path in notices))
            if path.endswith('/'):
                # The local header, compressed stream and zero-byte CRC have been checked.
                require(ident['bytes'] == 0, 'ZIP_DIRECTORY_PAYLOAD')
                continue
            observed[path] = (ident, hashes)
            if path in controls:
                contents[path] = payload
            if capture_notices and path in notices:
                notice_contents[path] = payload
        require(next_offset == cd, 'ZIP_LOCAL_LAYOUT')
        meta = contents[distinfo+'/METADATA']
        require(sha(meta) == expected['metadata_sha256'], 'METADATA_DIGEST')
        md = message(meta)
        require(norm(single(md,'Name')) == norm(expected['name']) and single(md,'Version') == expected['version'], 'METADATA_IDENTITY')
        require([str(v) for v in md.get_all('License-File', [])] == declared
                and single(md,'License-Expression',False) == expected.get('license_expression')
                and single(md,'Requires-Python',False) == expected.get('requires_python'), 'METADATA_DECLARATIONS')
        wh = message(contents[distinfo+'/WHEEL'])
        require(single(wh,'Wheel-Version') == '1.0' and single(wh,'Root-Is-Purelib') in ('true','false'), 'WHEEL_HEADER')
        actual_tags = [str(v) for v in wh.get_all('Tag', [])]
        require(len(actual_tags) == len(set(actual_tags)) and set(actual_tags) == tagset, 'WHEEL_TAG_MISMATCH')
        record_count = verify_record(contents[distinfo+'/RECORD'], distinfo+'/RECORD', observed, permit)
        receipt = {'inspector_schema':2, 'directory_entries':len(directories),
                'directory_inventory_sha256':sha(('\n'.join(directories) + ('\n' if directories else '')).encode('ascii')),
                'filename':fn, 'bytes':len(raw), 'sha256':sha(raw), 'metadata_sha256':sha(meta),
                'tags':sorted(tagset), 'members':len(observed), 'expanded_bytes':total,
                'notice_bytes':notice_size, 'notices':[{'path':p,**observed[p][0]} for p in sorted(notices)],
                'native_candidates':[{'path':p,**observed[p][0]} for p in sorted(paths) if NATIVE.search(p)],
                'declared_license_files':declared.copy(), 'license_expression':expected.get('license_expression'),
                'license_reviewed':False, 'status':'CANDIDATE_INTEGRITY_ONLY'}
        member_identity = {'path_sha256':sha(TARGET.encode('ascii')),
                'central_occurrences':central_count, 'record_occurrences':record_count,
                **observed[TARGET][0]}
        return receipt, notice_contents, member_identity


