"""C5 disabled wheel acquisition protocol and synthetic receipt settlement.

Only inert HTTP response replay is callable. No live socket adapter, artifact
upload, installation, extraction, arbitrary CLI or activation from environment.
The fresh disposable receipt generation is not a physical ownership proof.
"""
from __future__ import annotations

if __name__ == '__main__':
    raise SystemExit('FRESH_APPROVAL_REQUIRED: wheel acquisition is disabled')

import hashlib
import http.client
import io
import json
import os
from pathlib import Path
import re
import tempfile

import wheel_archive_inspector as w
import wheel_notice_evidence as n

LIVE_ENABLED = False
MAX_REQUESTS = 68
MAX_BYTES = 225699980
CHUNK = 65536
REQUEST_TIMEOUT = 15
MAX_MANIFEST = 256 * 1024
MAX_RECORD = 8192
HOST = 'files.pythonhosted.org'
MEDIA = {'application/octet-stream', 'binary/octet-stream', 'application/zip'}
FAILURES = {'HTTP_STATUS','CONTENT_TYPE','CONTENT_ENCODING','FRAMING',
            'BODY_LENGTH','DUPLICATE_HEADER','HEADER_SYNTAX','INCOMPLETE_BODY',
            'BODY_HASH','TRANSPORT_ERROR','INSPECTION_REFUSED'}
SCOPE = 'SYNTHETIC_ONLY_DISABLED'


def need(ok, reason):
    w.require(ok, reason)


def live_connection(*args, **kwargs):
    # Deliberately no socket construction path in this revision.
    raise w.Blocked('FRESH_APPROVAL_REQUIRED')


def exact_url(row):
    fn = w.name(row['filename'])
    need('/' not in fn and fn.endswith('.whl'), 'WHEEL_FILENAME')
    url = row['url']
    need(type(url) is str and re.fullmatch(
        r'https://files\.pythonhosted\.org/packages/[a-f0-9]{2}/[a-f0-9]{2}/[a-f0-9]{60}/'
        + re.escape(fn), url), 'URL_SCOPE')
    return url


def plan_rows(rows):
    need(type(rows) is list and 0 < len(rows) <= MAX_REQUESTS, 'REQUEST_COUNT')
    urls = []
    total = 0
    for row in rows:
        urls.append(exact_url(row))
        need(type(row['bytes']) is int and 0 < row['bytes'] <= w.MAX_ARCHIVE
             and n.digest(row['sha256']), 'PLAN_ROW')
        total += row['bytes']
    need(len(set(urls)) == len(rows) and len({r['filename'] for r in rows}) == len(rows),
         'DUPLICATE_PLAN')
    need(total <= MAX_BYTES, 'TOTAL_BUDGET')
    return rows


def review_pinned_plan():
    rows = plan_rows(n.load_pinned_rows())
    need(len(rows) == MAX_REQUESTS and sum(r['bytes'] for r in rows) == MAX_BYTES,
         'PLAN_COUNTS')
    return {'scope':SCOPE,'plan_blob':n.PLAN_BLOB,'requests':len(rows),
            'expected_bytes':MAX_BYTES,'live_enabled':False}


def header(resp, key):
    values = [v for k,v in resp.getheaders() if k.lower() == key.lower()]
    need(len(values) <= 1, 'DUPLICATE_HEADER')
    if not values:
        return None
    val = values[0]
    need(type(val) is str and len(val) <= 256 and all(32 <= ord(c) <= 126 for c in val),
         'HEADER_SYNTAX')
    return val


class _MemorySocket:
    def __init__(self, raw):
        self.raw = raw
    def makefile(self, *args):
        return io.BytesIO(self.raw)


class Replay:
    """Exact synthetic response map, parsed by stdlib HTTPResponse."""
    def __init__(self, responses):
        self.responses = dict(responses)
        self.requests = []
    def get(self, url):
        self.requests.append({'method':'GET','url':url,'host':HOST,'timeout':REQUEST_TIMEOUT,
                              'accept_encoding':'identity'})
        need(url in self.responses, 'TRANSPORT_ERROR')
        raw = self.responses[url]
        if type(raw) is not bytes:
            raise OSError('inert transport failure')
        response = http.client.HTTPResponse(_MemorySocket(raw))
        response.begin()
        return response


def sync_dir(path):
    if os.name == 'posix':
        fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)


def file_identity(name, raw):
    return {'name':name,'bytes':len(raw),'sha256':w.sha(raw)}


class _Generation:
    """Fresh owned synthetic generation; append-only files, manifest last."""
    def __init__(self, parent):
        self.path = Path(tempfile.mkdtemp(prefix='c5-wheel-receipt-', dir=parent))
        self.files = []
        sync_dir(self.path.parent)
    def put(self, name, raw):
        need(re.fullmatch(r'(?:request-\d{3}-(?:intent|result)|wheel-\d{3}-evidence)\.json',
                          name) and type(raw) is bytes, 'EVIDENCE_NAME')
        limit = n.MAX_DOCUMENT if name.startswith('wheel-') else MAX_RECORD
        need(0 < len(raw) <= limit, 'EVIDENCE_SIZE')
        self._write(name, raw)
        self.files.append(file_identity(name, raw))
    def _write(self, name, raw):
        path = self.path / name
        with path.open('xb') as f:
            need(f.write(raw) == len(raw), 'EVIDENCE_SHORT_WRITE')
            f.flush()
            os.fsync(f.fileno())
        sync_dir(self.path)
    def finish(self, manifest):
        need('files' not in manifest, 'MANIFEST_FIELDS')
        raw = n.canonical({**manifest,'files':self.files})
        need(0 < len(raw) <= MAX_MANIFEST, 'MANIFEST_LIMIT')
        self._write('manifest.json', raw)
        return w.sha(raw)


def request_intent(row, i):
    return {'sequence':i,'method':'GET','url':exact_url(row),'filename':row['filename'],
            'expected_bytes':row['bytes'],'expected_sha256':row['sha256']}


def _receive(row, response, state, scratch):
    """Strict length framing; hash and bound bytes before ZIP inspection."""
    state['http_status'] = response.status
    need(response.status == 200, 'HTTP_STATUS')
    media = header(response, 'Content-Type')
    need(media is not None and media.lower() in MEDIA, 'CONTENT_TYPE')
    enc = header(response, 'Content-Encoding')
    need(enc is None or enc.lower() == 'identity', 'CONTENT_ENCODING')
    need(header(response,'Transfer-Encoding') is None, 'FRAMING')
    length = header(response,'Content-Length')
    need(length is not None and re.fullmatch(r'[0-9]{1,10}',length)
         and int(length) == row['bytes'], 'BODY_LENGTH')
    # TemporaryFile exclusively creates disposable bytes; no named wheel output.
    with tempfile.TemporaryFile(mode='w+b', dir=scratch) as f:
        while state['received_bytes'] < row['bytes']:
            room = row['bytes'] - state['received_bytes']
            data = response.read1(min(CHUNK, room))
            if not data:
                break
            need(type(data) is bytes and len(data) <= room, 'FRAMING')
            state['received_bytes'] += len(data)
            state['hash'].update(data)
            need(f.write(data) == len(data), 'TRANSPORT_ERROR')
        need(state['received_bytes'] == row['bytes'], 'INCOMPLETE_BODY')
        need(state['hash'].hexdigest() == row['sha256'], 'BODY_HASH')
        f.seek(0)
        raw = f.read(row['bytes'] + 1)
        need(len(raw) == row['bytes'] and w.sha(raw) == row['sha256'], 'BODY_HASH')
        return raw


def _run(rows, plan_blob, replay, parent):
    """Synthetic protocol only; never call arbitrary connection objects."""
    need(type(replay) is Replay and LIVE_ENABLED is False, 'OFFLINE_FIXTURE_ONLY')
    rows = plan_rows(rows)
    batch = n._EvidenceBatch(rows, plan_blob)
    store = _Generation(parent)
    total = verified = attempted = 0
    for i, row in enumerate(rows, 1):
        prefix = f'request-{i:03d}'
        intent = request_intent(row, i)
        # Before issuing the request, persist exact scope and consume sequence.
        store.put(prefix+'-intent.json', n.canonical(intent))
        attempted += 1
        state = {'http_status':None,'received_bytes':0,'hash':hashlib.sha256()}
        reason = None
        evidence = None
        response = None
        try:
            response = replay.get(intent['url'])
            raw = _receive(row, response, state, store.path)
        except w.Blocked as exc:
            reason = str(exc)
            need(reason in FAILURES, 'UNEXPECTED_REFUSAL')
        except (OSError, http.client.HTTPException):
            reason = 'TRANSPORT_ERROR'
        finally:
            if response is not None:
                response.close()
        total += state['received_bytes']
        need(total <= MAX_BYTES, 'TOTAL_BUDGET')
        if reason is None:
            try:
                doc, digest = batch.inspect(row['filename'], raw)
            except w.Blocked:
                reason = 'INSPECTION_REFUSED'
            else:
                evidence = f'wheel-{i:03d}-evidence.json'
                store.put(evidence, doc)
                need(w.sha(doc) == digest, 'EVIDENCE_HASH')
                verified += 1
            finally:
                del raw
        result = {'sequence':i,'http_status':state['http_status'],
                  'received_bytes':state['received_bytes'],
                  'received_sha256':state['hash'].hexdigest(),
                  'status':'VERIFIED' if reason is None else 'REFUSED',
                  'reason':reason,'evidence':evidence}
        store.put(prefix+'-result.json', n.canonical(result))
        if reason is not None:
            break
    manifest = {'schema_version':1,'scope':SCOPE,'plan_blob':plan_blob,
                'status':'CANDIDATE_EVIDENCE_RECORDED' if verified == len(rows) else 'BLOCKED',
                'expected_count':len(rows),'attempted_count':attempted,
                'verified_count':verified,'received_bytes':total,
                'missing':[r['filename'] for r in rows[verified:]],
                'license_reviewed':False,'production_ready':False}
    digest = store.finish(manifest)
    return store.path, digest


def read_bounded(path, limit):
    need(path.is_file() and not path.is_symlink(), 'EVIDENCE_PATH')
    with path.open('rb') as f:
        raw = f.read(limit + 1)
    need(0 < len(raw) <= limit, 'EVIDENCE_SIZE')
    return raw


def parse(raw):
    try:
        obj = json.loads(raw, object_pairs_hook=n.unique)
        need(type(obj) is dict and n.canonical(obj) == raw, 'EVIDENCE_CANONICAL')
        return obj
    except (UnicodeError, json.JSONDecodeError, RecursionError):
        raise w.Blocked('MALFORMED_EVIDENCE') from None


def verify_generation(path, manifest_sha, rows, plan_blob):
    """Independent read-only replay. Missing terminal manifest is unsettled."""
    rows = plan_rows(rows)
    path = Path(path)
    need(path.is_dir() and not path.is_symlink(), 'GENERATION_PATH')
    manifest_path = path/'manifest.json'
    need(manifest_path.is_file() and not manifest_path.is_symlink(), 'UNSETTLED_GENERATION')
    raw = read_bounded(manifest_path, MAX_MANIFEST)
    need(n.digest(manifest_sha) and w.sha(raw) == manifest_sha, 'MANIFEST_HASH')
    m = parse(raw)
    keys = {'schema_version','scope','plan_blob','status','expected_count',
            'attempted_count','verified_count','received_bytes','missing',
            'license_reviewed','production_ready','files'}
    need(set(m) == keys and type(m['schema_version']) is int and m['schema_version'] == 1
         and m['scope'] == SCOPE and m['plan_blob'] == plan_blob
         and m['license_reviewed'] is False and m['production_ready'] is False,
         'MANIFEST_IDENTITY')
    count = m['attempted_count']
    need(type(count) is int and 1 <= count <= len(rows)
         and type(m['expected_count']) is int and m['expected_count'] == len(rows),
         'MANIFEST_COUNTS')
    files = m['files']
    need(type(files) is list and 2*count <= len(files) <= 3*count, 'MANIFEST_FILES')
    filemap = {}
    for entry in files:
        need(type(entry) is dict and set(entry) == {'name','bytes','sha256'},'MANIFEST_FILE')
        name = entry['name']
        need(type(name) is str and re.fullmatch(
            r'(?:request-\d{3}-(?:intent|result)|wheel-\d{3}-evidence)\.json',name)
            and name not in filemap and n.digest(entry['sha256']), 'MANIFEST_FILE')
        limit = n.MAX_DOCUMENT if name.startswith('wheel-') else MAX_RECORD
        need(n.bounded_int(entry['bytes'],1,limit), 'MANIFEST_FILE')
        filemap[name] = entry
    actual = set()
    with os.scandir(path) as it:
        for item in it:
            need(len(actual) < 3*MAX_REQUESTS+1 and item.is_file(follow_symlinks=False),
                 'GENERATION_INVENTORY')
            actual.add(item.name)
    need(actual == set(filemap) | {'manifest.json'}, 'GENERATION_INVENTORY')
    used = []
    evidence_bytes = total = verified = 0
    stopped = False

    def get(name, limit):
        need(name in filemap and name not in used, 'MANIFEST_FILE')
        raw = read_bounded(path/name, limit)
        need(file_identity(name,raw) == filemap[name], 'RECEIPT_HASH')
        used.append(name)
        return raw

    for i,row in enumerate(rows[:count],1):
        need(not stopped,'REQUEST_AFTER_REFUSAL')
        prefix = f'request-{i:03d}'
        need(get(prefix+'-intent.json',MAX_RECORD) == n.canonical(request_intent(row,i)),
             'INTENT_IDENTITY')
        evidence_name = f'wheel-{i:03d}-evidence.json'
        # Read result via manifest without consuming its order yet.
        result_name = prefix+'-result.json'
        result_raw = read_bounded(path/result_name,MAX_RECORD)
        need(file_identity(result_name,result_raw) == filemap.get(result_name),'RECEIPT_HASH')
        result = parse(result_raw)
        need(set(result) == {'sequence','http_status','received_bytes','received_sha256',
                            'status','reason','evidence'} and
             type(result['sequence']) is int and result['sequence'] == i
             and n.bounded_int(result['received_bytes'],0,row['bytes'])
             and n.digest(result['received_sha256'])
             and (result['http_status'] is None or n.bounded_int(result['http_status'],100,599)),
             'RESULT_IDENTITY')
        if result['received_bytes'] == 0:
            need(result['received_sha256'] == w.sha(b''),'RESULT_IDENTITY')
        total += result['received_bytes']
        if result['status'] == 'VERIFIED':
            need(result['reason'] is None and result['http_status'] == 200
                 and result['received_bytes'] == row['bytes']
                 and result['received_sha256'] == row['sha256']
                 and result['evidence'] == evidence_name,'RESULT_IDENTITY')
            evidence_raw = get(evidence_name,n.MAX_DOCUMENT)
            evidence_bytes += len(evidence_raw)
            need(evidence_bytes <= n.MAX_EVIDENCE_BATCH,'EVIDENCE_BATCH_LIMIT')
            n.verify_evidence(evidence_raw,filemap[evidence_name]['sha256'],row,plan_blob)
            verified += 1
        else:
            need(result['status'] == 'REFUSED' and result['reason'] in FAILURES
                 and result['evidence'] is None,'RESULT_IDENTITY')
            stopped = True
        need(get(result_name,MAX_RECORD) == result_raw,'RECEIPT_HASH')
    need(used == [f['name'] for f in files],'MANIFEST_FILE_ORDER')
    need(type(m['verified_count']) is int and m['verified_count'] == verified
         and type(m['received_bytes']) is int and m['received_bytes'] == total <= MAX_BYTES
         and m['missing'] == [r['filename'] for r in rows[verified:]]
         and ((m['status'] == 'BLOCKED' and stopped and count == verified+1)
              or (m['status'] == 'CANDIDATE_EVIDENCE_RECORDED' and not stopped
                  and count == verified == len(rows))), 'MANIFEST_SETTLEMENT')
    return m
