"""C-D09 inspection-only preparation. No live transport, subprocess or CLI."""
import collections
import hashlib
import io
import json
import re
import stat
import tarfile
import zipfile
import zlib
from email import policy
from email.parser import BytesParser
from urllib.parse import urlsplit

PIN = '7d89ba820429b2005f7a70cc1b5ed1415f7b1161'
EXCLUDED = '7422df25243767b9877031a2248cb14d09ddac9beee846f4cef3d5c9191d488f'
MAX_ARCHIVE = 36607512
MAX_MEMBERS = 50000
MAX_MEMBER = 128 * 1024**2
MAX_EXPANDED = 512 * 1024**2
MAX_NOTICES = 8 * 1024**2
MAX_META = 2 * 1024**2
MAX_OUTPUT = 4 * 1024**2
MAX_TOOL_OUTPUT = 256 * 1024
CHUNK = 65536
NOTICE = re.compile(r'^(licen[cs]e|copying|notice|copyright|authors|third[-_ ]?party|ofl)([._-].*)?$', re.I)
NATIVE = re.compile(r'\.(dll|pyd|so(\.[0-9]+)*|dylib|exe|lib|a|node)$', re.I)


class Refused(ValueError):
    pass


def need(ok, reason):
    if not ok:
        raise Refused(reason)


def digest(raw, algorithm='sha256'):
    return hashlib.new(algorithm, raw).hexdigest()


def strict_json(raw):
    def pairs(items):
        out = {}
        for key, value in items:
            need(key not in out, 'JSON_DUPLICATE')
            out[key] = value
        return out
    return json.loads(raw, object_pairs_hook=pairs, parse_constant=lambda _: (_ for _ in ()).throw(Refused('JSON_CONSTANT')))


def validate_row(row):
    kind = row['kind']
    need(kind in ('wheel', 'pip', 'npm'), 'KIND')
    algo = 'sha512' if kind == 'npm' else 'sha256'
    need(re.fullmatch('[0-9a-f]{%d}' % (128 if kind == 'npm' else 64), row[algo]), 'DIGEST')
    need(type(row['bytes']) is int and 0 < row['bytes'] <= MAX_ARCHIVE, 'ARCHIVE_CAP')
    url = row['url']
    parts = urlsplit(url)
    host = 'registry.npmjs.org' if kind == 'npm' else 'files.pythonhosted.org'
    need(parts.scheme == 'https' and parts.netloc == host and not parts.query and not parts.fragment
         and re.fullmatch(r'/[A-Za-z0-9_./@+-]+', parts.path) and '..' not in parts.path.split('/'), 'URL')
    need(url == 'https://' + host + parts.path, 'URL_CANONICAL')
    if kind == 'npm':
        need(parts.path.endswith('.tgz'), 'URL_SUFFIX')
    else:
        need(parts.path.endswith('/' + row['filename']) and row['filename'].endswith('.whl'), 'URL_SUFFIX')
    return algo


def projection(raw):
    need(digest(b'blob ' + str(len(raw)).encode() + b'\0' + raw, 'sha1') == PIN, 'PLAN_PIN')
    doc = strict_json(raw)
    rows = doc['targeted_inspection']['unique_rows']
    removed = [r for r in rows if r['kind'] == 'wheel' and r['filename'] == 'certifi-2026.11.20-py3-none-any.whl' and r['sha256'] == EXCLUDED]
    need(len(rows) == 43 and len(removed) == 1, 'EXCLUSION')
    selected = [r for r in rows if r not in removed]
    need(collections.Counter(r['kind'] for r in selected) == {'wheel': 28, 'npm': 13, 'pip': 1}
         and len({r['url'] for r in selected}) == 42 and sum(r['bytes'] for r in selected) == 214328914, 'SCOPE')
    expected = {}
    for profile in doc['profiles']:
        for item in [*profile['wheels'], *profile['npm_archives'], profile['pip']]:
            prior = expected.setdefault(item['url'], item)
            need(prior == item, 'PROFILE_CONFLICT')
    result = []
    for row in selected:
        algo = validate_row(row)
        item = expected[row['url']]
        need(all(row[k] == item[k] for k in ('filename', 'bytes', algo)), 'PROFILE_PIN')
        result.append({**item, **row})
    return result


def curl_command(exe, row, path):
    validate_row(row)
    return [exe, '-q', '--silent', '--show-error', '--fail', '--noproxy', '*', '--http1.1',
            '--proto', '=https', '--proto-redir', '=https', '--max-redirs', '0', '--retry', '0',
            '--connect-timeout', '10', '--max-time', '30', '--max-filesize', str(row['bytes']),
            '--header', 'Accept-Encoding: identity', '--output', str(path), '--write-out',
            '%{http_code} %{size_download}', row['url']]


def transfer_result(code, stdout, raw, row):
    algo = validate_row(row)
    need(code == 0 and stdout.strip() == ('200 ' + str(row['bytes'])).encode(), 'TRANSFER_REFUSED')
    need(len(raw) == row['bytes'] and digest(raw, algo) == row[algo], 'ARCHIVE_IDENTITY')


class Paths:
    def __init__(self):
        self.seen = set()
        self.dirs = {}
        self.files = set()
        self.total = 0
        self.path_bytes = 0

    def add(self, name, size, directory):
        name = name[:-1] if directory and name.endswith('/') else name
        parts = name.split('/')
        need(0 < len(name) <= 1024 and len(parts) <= 32 and all(
            re.fullmatch(r'[A-Za-z0-9_ .+!@=(),-]{1,255}', p) and p not in ('.', '..')
            and not p.endswith(('.', ' ')) and not re.match(r'(con|prn|aux|nul|com[1-9]|lpt[1-9])([.]|$)', p, re.I)
            for p in parts), 'UNSAFE_PATH')
        key = name.casefold()
        need(key not in self.seen and len(self.seen) < MAX_MEMBERS, 'DUPLICATE_OR_COUNT')
        self.seen.add(key)
        self.path_bytes += len(name)
        need(self.path_bytes <= 16 * 1024**2, 'PATH_CAP')
        for i in range(1, len(parts) + int(directory)):
            prefix = '/'.join(parts[:i]); lower = prefix.casefold()
            need(lower not in self.files and self.dirs.get(lower, prefix) == prefix, 'PREFIX_COLLISION')
            self.dirs[lower] = prefix
            need(len(self.dirs) <= MAX_MEMBERS, 'DIRECTORY_CAP')
        if not directory:
            need(key not in self.dirs, 'PREFIX_COLLISION')
            self.files.add(key)
        need(type(size) is int and 0 <= size <= MAX_MEMBER and (not directory or size == 0), 'MEMBER_CAP')
        self.total += size
        need(self.total <= MAX_EXPANDED, 'EXPANDED_CAP')
        return name


class GzipStream:
    """Single gzip member, bounded decompression including TAR headers/padding."""
    def __init__(self, raw):
        self.raw = raw
        self.pos = 0
        self.tail = b''
        self.z = zlib.decompressobj(31)
        self.total = 0

    def read(self, count):
        need(0 <= count <= CHUNK, 'READ_CAP')
        out = bytearray()
        while len(out) < count and not self.z.eof:
            if not self.tail:
                self.tail = self.raw[self.pos:self.pos + CHUNK]
                self.pos += len(self.tail)
            need(bool(self.tail), 'GZIP_TRUNCATED')
            part = self.z.decompress(self.tail, min(count - len(out), MAX_EXPANDED - self.total + 1))
            self.tail = self.z.unconsumed_tail
            self.total += len(part)
            need(self.total <= MAX_EXPANDED, 'GZIP_CAP')
            out.extend(part)
        if self.z.eof:
            need(not self.z.unused_data and not self.tail and self.pos == len(self.raw), 'GZIP_TRAILING')
        return bytes(out)


def exact(reader, count):
    raw = reader.read(count)
    need(len(raw) == count, 'TRUNCATED_MEMBER')
    return raw


def members(raw, kind, paths, consume):
    if kind != 'npm':
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            entries = archive.infolist()
            need(0 < len(entries) <= MAX_MEMBERS, 'MEMBER_COUNT')
            prepared = []
            for entry in entries:
                mode = stat.S_IFMT(entry.external_attr >> 16)
                directory = entry.is_dir()
                need(entry.orig_filename == entry.filename and not entry.flag_bits & 1
                     and entry.compress_type in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED)
                     and not entry.external_attr & 0x448 and mode in (0, stat.S_IFDIR if directory else stat.S_IFREG)
                     and not (entry.external_attr & 0x10 and not directory), 'ZIP_MODE')
                name = paths.add(entry.filename, entry.file_size, directory)
                prepared.append((entry, name, directory))
            for entry, name, directory in prepared:
                with archive.open(entry) as reader:
                    consume(reader, name, entry.file_size, directory)
                    need(reader.read(1) == b'', 'ZIP_OVERRUN')
    else:
        reader = GzipStream(raw)
        while True:
            header = exact(reader, 512)
            if header == bytes(512):
                need(exact(reader, 512) == bytes(512), 'TAR_END')
                while True:
                    tail = reader.read(CHUNK)
                    if not tail:
                        return
                    need(not any(tail) and len(tail) % 512 == 0, 'TAR_TRAILING')
            entry = tarfile.TarInfo.frombuf(header, 'utf-8', 'strict')
            need(entry.type in (tarfile.REGTYPE, tarfile.AREGTYPE, tarfile.DIRTYPE) and not entry.linkname, 'TAR_MODE')
            name = paths.add(entry.name, entry.size, entry.isdir())
            consume(reader, name, entry.size, entry.isdir())
            padding = exact(reader, (-entry.size) % 512)
            need(not any(padding), 'TAR_PADDING')


def inspect(raw, row):
    """Return facts only. No member execution or extraction; no licence clearance."""
    algo = validate_row(row)
    need(len(raw) == row['bytes'] and digest(raw, algo) == row[algo], 'ARCHIVE_IDENTITY')
    paths = Paths()
    notices, native, metadata = [], [], []
    notice_total = 0
    def consume(reader, name, size, directory):
        nonlocal notice_total
        if directory:
            return
        basename = name.rsplit('/', 1)[-1]
        notice = bool(NOTICE.fullmatch(basename) or '.dist-info/licenses/' in name.lower())
        meta = name == 'package/package.json' if row['kind'] == 'npm' else name.endswith('.dist-info/METADATA')
        if notice:
            notice_total += size
            need(notice_total <= MAX_NOTICES, 'NOTICE_CAP')
        if meta:
            need(size <= MAX_META and not metadata, 'METADATA_CAP_OR_DUPLICATE')
        h = hashlib.sha256(); captured = bytearray(); prefix = b''; left = size
        while left:
            chunk = exact(reader, min(left, CHUNK)); left -= len(chunk); h.update(chunk)
            if not prefix:
                prefix = chunk[:8]
            if meta:
                captured.extend(chunk)
        item = {'path': name, 'bytes': size, 'sha256': h.hexdigest()}
        if notice:
            notices.append(item)
        if meta:
            metadata.append((name, bytes(captured)))
        if NATIVE.search(name) or prefix.startswith((b'MZ', b'\x7fELF', b'!<arch>\n')):
            native.append({**item, 'format': 'PE' if prefix.startswith(b'MZ') else 'ELF' if prefix.startswith(b'\x7fELF') else 'UNRESOLVED'})
    members(raw, row['kind'], paths, consume)
    need(len(metadata) == 1, 'METADATA_MISSING')
    name, payload = metadata[0]
    if row['kind'] == 'npm':
        meta = strict_json(payload)
        need(meta.get('name') == row['name'].removeprefix('node_modules/') and meta.get('version') == row['version'], 'METADATA_IDENTITY')
        need(meta.get('license') == row['declared_license'], 'LICENCE_DECLARATION')
        scripts = meta.get('scripts', {})
        need(isinstance(scripts, dict) and all(isinstance(v, str) for v in scripts.values()), 'SCRIPT_DECLARATION')
        facts = {'license': meta.get('license'), 'scripts_sha256': digest(json.dumps(scripts, sort_keys=True).encode())}
    else:
        meta = BytesParser(policy=policy.default).parsebytes(payload)
        norm = lambda x: re.sub(r'[-_.]+', '-', x).lower()
        expected_name = row['filename'].split('-')[0]
        need(name == '-'.join(row['filename'].split('-')[:2]) + '.dist-info/METADATA', 'METADATA_PATH')
        need(not meta.defects and len(meta.get_all('Name', [])) == len(meta.get_all('Version', [])) == 1
             and norm(str(meta['Name'])) == norm(expected_name) and str(meta['Version']) == row['version'], 'METADATA_IDENTITY')
        if 'metadata_sha256' in row:
            need(digest(payload) == row['metadata_sha256'], 'METADATA_HASH')
        declared = [str(x) for x in meta.get_all('License-File', [])]
        expression = meta.get_all('License-Expression', [])
        need(len(expression) <= 1, 'LICENCE_DECLARATION')
        if 'license_files' in row:
            need(sorted(declared) == sorted(row['license_files']), 'NOTICE_DECLARATION')
        if 'license_expression' in row:
            need((str(expression[0]) if expression else None) == row['license_expression'], 'LICENCE_DECLARATION')
        notice_paths = {x['path'] for x in notices}
        distinfo = name.rsplit('/', 1)[0]
        for item in declared:
            need(len({distinfo + '/licenses/' + item, distinfo + '/' + item} & notice_paths) == 1, 'DECLARED_NOTICE_MISSING')
        facts = {'license_expression': str(expression[0]) if expression else None, 'declared_notice_count': len(declared)}
    receipt = {'filename': row['filename'], 'members': len(paths.seen), 'expanded_bytes': paths.total,
               'notices': notices, 'native': native, 'metadata': facts, 'status': 'UNRESOLVED_USE_RIGHTS'}
    need(len(json.dumps(receipt, ensure_ascii=True).encode()) <= MAX_OUTPUT, 'RECEIPT_CAP')
    return receipt


def tool_command(exe, fmt, path):
    need(fmt in ('PE', 'ELF'), 'UNSUPPORTED_NATIVE_FORMAT')
    return [exe, '-p', str(path)] if fmt == 'PE' else [exe, '-h', '-d', '-V', str(path)]


def tool_result(code, stdout, stderr, timed_out=False):
    need(not timed_out and code == 0, 'TOOL_REFUSED')
    need(len(stdout) + len(stderr) <= MAX_TOOL_OUTPUT, 'TOOL_OUTPUT_CAP')
    need(not stderr, 'TOOL_STDERR')
    return digest(stdout)


if __name__ == '__main__':
    raise SystemExit('DISARMED_INSPECTION_CORE_ONLY')
