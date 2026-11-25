"""C5 hosted wheel acquisition proposal, DISABLED pending fresh owner approval.

No workflow activation or upload is included. Only the separately gated
collector can construct a real socket; tests use generated memory responses.
Portable bundles contain receipts/notices only, never wheel archives.
"""
from __future__ import annotations

if __name__ == '__main__':
    raise SystemExit('FRESH_APPROVAL_REQUIRED: hosted wheel acquisition is disabled')

from contextlib import contextmanager
import hashlib
import http.client
import io
import os
from pathlib import Path
import re
import signal
import ssl
import struct
import tempfile
import threading

import wheel_acquisition_offline as a
import wheel_archive_inspector as w
import wheel_notice_evidence as n

LIVE_ENABLED = False
OP = 'C5-WHEEL-HOSTED-ONCE-20261126'
BRANCH = 'refs/heads/feature/live-dev-workspace-20261023'
WORKFLOW = 'C5 wheel hosted one-use acquisition'
MARKER = n.ROOT / (n.DIR+'APPROVAL_WHEEL_HOSTED_20261126.txt')
MARKER_BYTES = (OP+'\n68 exact wheel GETs; 225699980 body bytes; zero redirects or retries.\n').encode('ascii')
MAGIC = b'ODIN-C5-EVIDENCE-V1\n'
FRAME = struct.Struct('>HQ')
MAX_FILES = 3*a.MAX_REQUESTS+1
MAX_BUNDLE = n.MAX_EVIDENCE_BATCH+2*a.MAX_REQUESTS*a.MAX_RECORD+a.MAX_MANIFEST+65536
FILENAME = re.compile(r'(?:manifest|request-\d{3}-(?:intent|result)|wheel-\d{3}-evidence)\.json')


def need(ok, reason):
    w.require(ok, reason)


def authorize():
    need(LIVE_ENABLED is True, 'FRESH_APPROVAL_REQUIRED')
    env = os.environ
    need(os.name == 'posix' and threading.current_thread() is threading.main_thread()
         and env.get('GITHUB_ACTIONS') == 'true' and env.get('GITHUB_EVENT_NAME') == 'push'
         and env.get('GITHUB_REF') == BRANCH and env.get('GITHUB_WORKFLOW') == WORKFLOW
         and env.get('GITHUB_RUN_ATTEMPT') == '1' and env.get('C5_APPROVED_ONCE') == OP
         and re.fullmatch(r'[0-9a-f]{40}',env.get('GITHUB_SHA',''))
         and env.get('GITHUB_SHA') == env.get('C5_EXPECTED_SOURCE_SHA')
         and re.fullmatch(r'[0-9]{1,20}',env.get('GITHUB_RUN_ID','')),
         'ONE_USE_CONTEXT')
    need(MARKER.is_file() and not MARKER.is_symlink()
         and MARKER.stat().st_size == len(MARKER_BYTES)
         and MARKER.read_bytes() == MARKER_BYTES, 'APPROVAL_MARKER')
    # Exact activated source/blob and direct-child marker-only push must also
    # be asserted in a separately reviewed workflow. Not implemented here.


@contextmanager
def deadline():
    """Absolute POSIX timer covers connect/DNS, headers, body and close."""
    need(hasattr(signal,'setitimer') and threading.current_thread() is threading.main_thread(),
         'DEADLINE_UNAVAILABLE')
    need(signal.getitimer(signal.ITIMER_REAL) == (0.0,0.0), 'DEADLINE_BUSY')
    def expired(*_):
        raise w.Blocked('REQUEST_DEADLINE')
    previous = signal.signal(signal.SIGALRM,expired)
    try:
        signal.setitimer(signal.ITIMER_REAL,a.REQUEST_TIMEOUT)
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL,0)
        signal.signal(signal.SIGALRM,previous)


def request_parts(row):
    url = a.exact_url(row)
    path = url[len('https://'+a.HOST):]
    return a.HOST,443,path,{'Accept':'application/octet-stream, application/zip, binary/octet-stream',
                            'Accept-Encoding':'identity','Connection':'close',
                            'User-Agent':'PilotODIN-C5-wheel-candidate/1'}


class _Response:
    def __init__(self, connection, response):
        self.connection = connection
        self.response = response
        self.status = response.status
    def getheaders(self):
        return self.response.getheaders()
    def read1(self, size):
        return self.response.read1(size)
    def close(self):
        try:
            self.response.close()
        finally:
            self.connection.close()


def _request(row, factory):
    """Internal transport seam; production caller must authorize first."""
    host,port,path,headers = request_parts(row)
    tls = ssl.create_default_context()
    need(tls.check_hostname and tls.verify_mode == ssl.CERT_REQUIRED,'TLS_POLICY')
    conn = factory(host,port,timeout=a.REQUEST_TIMEOUT,context=tls)
    try:
        conn.request('GET',path,headers=headers)
        return _Response(conn,conn.getresponse())
    except BaseException:
        conn.close()
        raise


def collect():
    """Disabled; future one-use workflow must supply independent source pin."""
    authorize()
    rows = a.plan_rows(n.load_pinned_rows())
    need(len(rows)==a.MAX_REQUESTS and sum(r['bytes'] for r in rows)==a.MAX_BYTES,'PLAN_COUNTS')
    by_url = {a.exact_url(r):r for r in rows}
    runner = Path(os.environ['RUNNER_TEMP'])
    need(runner.is_dir() and not runner.is_symlink(),'RUNNER_TEMP')
    return a._run_core(rows,n.PLAN_BLOB,
        lambda url:_request(by_url[url],http.client.HTTPSConnection),
        runner,deadline,a.HOSTED_SCOPE)


def limit_for(name):
    need(type(name) is str and FILENAME.fullmatch(name),'BUNDLE_NAME')
    return a.MAX_MANIFEST if name=='manifest.json' else (
        n.MAX_DOCUMENT if name.startswith('wheel-') else a.MAX_RECORD)


def _frame(name, raw):
    name_bytes = name.encode('ascii')
    need(0 < len(raw) <= limit_for(name),'BUNDLE_FILE_SIZE')
    return FRAME.pack(len(name_bytes),len(raw))+name_bytes+raw


def export_generation(path, manifest_sha, rows, plan_blob, parent, *, scope=a.SCOPE):
    """Verify before packaging; exclusive file in fresh disposable directory."""
    m = a.verify_generation(path,manifest_sha,rows,plan_blob,scope=scope)
    names = sorted([x['name'] for x in m['files']]+['manifest.json'])
    need(len(names)<=MAX_FILES,'BUNDLE_COUNT')
    expected = {f['name']:f for f in m['files']}
    dest = Path(tempfile.mkdtemp(prefix='c5-wheel-export-',dir=parent))/'receipts.odin'
    digest = hashlib.sha256()
    size = 0
    with dest.open('xb') as out:
        def write(raw):
            nonlocal size
            size += len(raw)
            need(size <= MAX_BUNDLE,'BUNDLE_LIMIT')
            need(out.write(raw)==len(raw),'BUNDLE_SHORT_WRITE')
            digest.update(raw)
        write(MAGIC+struct.pack('>H',len(names)))
        for name in names:
            raw = a.read_bounded(Path(path)/name,limit_for(name))
            need(w.sha(raw)==manifest_sha if name=='manifest.json' else
                 a.file_identity(name,raw)==expected[name],'EXPORT_CHANGED')
            write(_frame(name,raw))
        out.flush()
        os.fsync(out.fileno())
    a.sync_dir(dest.parent)
    a.sync_dir(dest.parent.parent)
    return dest,{'bytes':size,'sha256':digest.hexdigest(),'manifest_sha256':manifest_sha}


def import_generation(bundle, identity, rows, plan_blob, parent, *, scope=a.SCOPE):
    """Verify exact bundle snapshot against separately retained identity, then replay."""
    need(type(identity) is dict and set(identity)=={'bytes','sha256','manifest_sha256'}
         and n.bounded_int(identity['bytes'],len(MAGIC)+2,MAX_BUNDLE)
         and n.digest(identity['sha256']) and n.digest(identity['manifest_sha256']),
         'BUNDLE_IDENTITY')
    raw = a.read_bounded(Path(bundle),MAX_BUNDLE)
    need(len(raw)==identity['bytes'] and w.sha(raw)==identity['sha256'],'BUNDLE_HASH')
    stream = io.BytesIO(raw)
    need(stream.read(len(MAGIC))==MAGIC,'BUNDLE_MAGIC')
    count_raw=stream.read(2)
    need(len(count_raw)==2,'BUNDLE_HEADER')
    count=struct.unpack('>H',count_raw)[0]
    need(3<=count<=MAX_FILES,'BUNDLE_COUNT')
    dest=Path(tempfile.mkdtemp(prefix='c5-wheel-import-',dir=parent))
    seen=[]
    evidence_bytes=0
    for _ in range(count):
        hdr=stream.read(FRAME.size)
        need(len(hdr)==FRAME.size,'BUNDLE_TRUNCATED')
        name_len,size=FRAME.unpack(hdr)
        need(1<=name_len<=64,'BUNDLE_NAME')
        try:
            name=stream.read(name_len).decode('ascii')
        except UnicodeError:
            raise w.Blocked('BUNDLE_NAME') from None
        need(len(name)==name_len and (not seen or seen[-1]<name),'BUNDLE_ORDER')
        need(0<size<=limit_for(name),'BUNDLE_FILE_SIZE')
        if name.startswith('wheel-'):
            evidence_bytes+=size
            need(evidence_bytes<=n.MAX_EVIDENCE_BATCH,'EVIDENCE_BATCH_LIMIT')
        data=stream.read(size)
        need(len(data)==size,'BUNDLE_TRUNCATED')
        with (dest/name).open('xb') as out:
            need(out.write(data)==len(data),'BUNDLE_SHORT_WRITE')
            out.flush()
            os.fsync(out.fileno())
        seen.append(name)
    need(not stream.read(1),'BUNDLE_TRAILING')
    a.sync_dir(dest)
    a.sync_dir(dest.parent)
    m=a.verify_generation(dest,identity['manifest_sha256'],rows,plan_blob,scope=scope)
    return dest,m
