"""C5 remaining-only hosted proposal; all external operations disabled.

Historical source and receipts are immutable. The new schema-2 receipt carries
a specific allowlisted refusal code. No wheel file is persisted or uploaded.
"""
from __future__ import annotations
import hashlib
import http.client
import io
import json
import os
from pathlib import Path
import re
import ssl
import stat
import struct
import sys
import tempfile
import zipfile
import zlib
from contextlib import nullcontext
from urllib.request import build_opener, HTTPSHandler, ProxyHandler
from urllib.error import HTTPError
from urllib.parse import urlsplit

ARMED=False
if __name__=='__main__' and not ARMED:
    raise SystemExit('FRESH_APPROVAL_REQUIRED: missing-only hosted driver disabled')

sys.path.insert(0,str(Path(__file__).resolve().parent))
import wheel_acquisition_driver as d
import wheel_acquisition_offline as a
import wheel_archive_inspector as w
import wheel_notice_evidence as n
import wheel_hosted_proposal as h
import wheel_one_use_review as g
import synthetic_receipt_transfer as t
import wheel_diagnostic_offline as diagnostic

ROOT=n.ROOT
DIR=n.DIR
SELF=DIR+'wheel_missing_hosted.py'
WORKFLOW='.github/workflows/c5-wheel-missing-hosted.yml'
WORKFLOW_NAME='C5 missing wheels hosted once'
OP='C5-WHEEL-MISSING-HOSTED-ONCE-20261126'
MESSAGE=OP+' owner approved exact remaining wheel acquisition'
MARKER=DIR+'APPROVAL_WHEEL_MISSING_HOSTED_20261126.txt'
MARKER_BYTES=(OP+'\n63 exact wheel GETs; 225397605 body bytes; no redirects or retries.\n').encode('ascii')
FIXTURE_SCOPE='SYNTHETIC_MISSING_V2_DISABLED'
HOSTED_SCOPE='HOSTED_MISSING_V2_CANDIDATE_ONLY'
MAX_BYTES=a.MAX_BYTES
MAX_MANIFEST=a.MAX_MANIFEST
MAX_REQUESTS=a.MAX_REQUESTS
MAX_RECORD=a.MAX_RECORD
FAILURES=a.FAILURES
need=a.need
plan_rows=a.plan_rows
_Generation=a._Generation
_receive=a._receive
request_intent=a.request_intent
file_identity=a.file_identity
read_bounded=a.read_bounded
parse=a.parse
EXTRA_PINS={
    'wheel_acquisition_driver.py':'e888774ce5cabc5737c413ee47f3da64781443c2',
    'wheel_diagnostic_offline.py':'6aa10f588e24e582d7edf6226635adc6a591faad',
    'wheel_missing_plan_20261126.json':'9938c0f8cc5be3e118dec2eff953cae94f4b5a76',
    'wheel_receipt_diagnosis_45753813079.json':'1dd2627eafba1f4695f972c1d23fac68340d05ee',
}
MODS=(a,w,h,n,g,t)


def check_caps(caps):
    limits={'body':a.MAX_BYTES,'expanded':w.MAX_TOTAL,'notice':w.MAX_NOTICES,'evidence':n.MAX_EVIDENCE_BATCH}
    need(type(caps) is dict and set(caps)==set(limits)
         and all(n.bounded_int(caps[k],0,v) for k,v in limits.items()),'RESIDUAL_CAPS')


def bundle_cap(caps):
    check_caps(caps)
    return caps['evidence']+2*63*a.MAX_RECORD+a.MAX_MANIFEST+65536


def plan():
    d.verify_sources()
    for name,pin in EXTRA_PINS.items():
        need(d.git_blob(d.read_file(ROOT/DIR/name))==pin,'SOURCE_PIN')
    need(not d.ARMED and not a.LIVE_ENABLED and not h.LIVE_ENABLED
         and not g.ENABLED and not t.ENABLED and not diagnostic.LIVE_ENABLED,'LEGACY_GATES')
    p=diagnostic.review_missing_plan()
    caps={'body':p['remaining_bytes'],'expanded':p['max_expanded_remaining'],
          'notice':p['max_notice_remaining'],'evidence':p['max_evidence_remaining']}
    check_caps(caps)
    need(caps=={'body':225397605,'expanded':4294072708,'notice':33549191,'evidence':67097955}
         and len(p['wheels'])==63,'PINNED_CAPS')
    return p['wheels'],caps


def authorize(phase):
    need(ARMED is True,'FRESH_APPROVAL_REQUIRED')
    need(os.name=='posix','HOSTED_PLATFORM')
    e=os.environ
    need(e.get('GITHUB_ACTIONS')=='true' and e.get('GITHUB_EVENT_NAME')=='push'
         and e.get('GITHUB_REPOSITORY')==d.REPO and e.get('GITHUB_REF')=='refs/heads/feature/live-dev-workspace-20261023'
         and e.get('GITHUB_WORKFLOW')==WORKFLOW_NAME
         and e.get('GITHUB_JOB')==phase and phase in ('collect-once','retrieve-once') and e.get('GITHUB_RUN_ATTEMPT')=='1'
         and e.get('GITHUB_WORKSPACE')==str(ROOT) and e.get('C5_APPROVED_ONCE')==OP
         and d.RUN.fullmatch(e.get('GITHUB_RUN_ID','')) and d.SHA1.fullmatch(e.get('C5_DRIVER_BLOB','')),
         'MISSING_CONTEXT')
    head=d.git(ROOT,'rev-parse','HEAD').decode().strip()
    parents=d.git(ROOT,'show','-s','--format=%P','HEAD').decode().split()
    event=json.loads(d.read_file(Path(e['GITHUB_EVENT_PATH'])),object_pairs_hook=n.unique)
    need(len(parents)==1 and head==e['GITHUB_SHA']==event.get('after')
         and parents[0]==event.get('before') and event.get('ref')==e['GITHUB_REF']
         and event.get('forced') is False and event.get('created') is False and event.get('deleted') is False
         and event.get('repository',{}).get('full_name')==d.REPO
         and event.get('head_commit',{}).get('id')==head
         and event.get('head_commit',{}).get('message')==MESSAGE,'MISSING_EVENT')
    need(d.git(ROOT,'diff-tree','--no-commit-id','--name-status','--no-renames','-r','HEAD')
         ==('A\t'+MARKER+'\n').encode('ascii')
         and d.git(ROOT,'show','-s','--format=%B','HEAD').decode().rstrip('\n')==MESSAGE
         and d.read_file(ROOT/MARKER,1024)==MARKER_BYTES,'MISSING_MARKER')
    for path in (SELF,WORKFLOW,MARKER):
        blob=d.git_blob(d.read_file(ROOT/path))
        need(blob==d.git(ROOT,'rev-parse','HEAD:'+path).decode().strip(),'CHECKOUT_PIN')
        if path==SELF: need(blob==e['C5_DRIVER_BLOB'],'SELF_PIN')
    runner=Path(e['RUNNER_TEMP'])
    need(runner.is_dir() and not runner.is_symlink(),'RUNNER_TEMP')
    try:
        with (runner/('c5-missing-'+e['GITHUB_RUN_ID']+'-'+phase+'.claim')).open('xb') as f:
            f.write(MARKER_BYTES); f.flush(); os.fsync(f.fileno())
    except FileExistsError:
        raise w.Blocked('ONE_USE_CLAIM_CONSUMED') from None
    return runner,e['GITHUB_RUN_ID'],head



def _collect_core(rows, plan_blob, fetch, parent, deadline, scope, caps):
    check_caps(caps)
    need(scope in (FIXTURE_SCOPE, HOSTED_SCOPE),'SCOPE')
    need(sum(row['bytes'] for row in rows)<=caps['body'],'RESIDUAL_BODY_LIMIT')
    rows = plan_rows(rows)
    batch = n._EvidenceBatch(rows, plan_blob)
    batch._budget.expanded=w.MAX_TOTAL-caps['expanded']
    batch._budget.notices=w.MAX_NOTICES-caps['notice']
    batch._persisted_bytes=n.MAX_EVIDENCE_BATCH-caps['evidence']
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
        inspection_reason = None
        evidence = None
        response = None
        try:
            with deadline():
                try:
                    response = fetch(intent['url'])
                    raw = _receive(row, response, state, store.path)
                finally:
                    if response is not None:
                        response.close()
                        response = None
        except w.Blocked as exc:
            reason = str(exc)
            need(reason in FAILURES, 'UNEXPECTED_REFUSAL')
        except (OSError, http.client.HTTPException):
            reason = 'TRANSPORT_ERROR'
        finally:
            if response is not None:
                response.close()
        total += state['received_bytes']
        need(total <= caps['body'], 'TOTAL_BUDGET')
        if reason is None:
            try:
                doc, digest = batch.inspect(row['filename'], raw)
            except w.Blocked as exc:
                reason = 'INSPECTION_REFUSED'
                inspection_reason = diagnostic.safe_inspection_reason(exc)
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
                  'reason':reason,'inspection_reason':inspection_reason,'evidence':evidence}
        store.put(prefix+'-result.json', n.canonical(result))
        if reason is not None:
            break
    manifest = {'schema_version':2,'scope':scope,'plan_blob':plan_blob,
                'status':'CANDIDATE_EVIDENCE_RECORDED' if verified == len(rows) else 'BLOCKED',
                'expected_count':len(rows),'attempted_count':attempted,
                'verified_count':verified,'received_bytes':total,
                'missing':[r['filename'] for r in rows[verified:]],
                'license_reviewed':False,'production_ready':False}
    digest = store.finish(manifest)
    return store.path, digest




def verify_generation(path, manifest_sha, rows, plan_blob, *, scope, caps):
    """Independent read-only replay. Missing terminal manifest is unsettled."""
    check_caps(caps)
    need(scope in (FIXTURE_SCOPE,HOSTED_SCOPE),'SCOPE')
    rows = plan_rows(rows)
    need(sum(row['bytes'] for row in rows)<=caps['body'],'RESIDUAL_BODY_LIMIT')
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
    need(set(m) == keys and type(m['schema_version']) is int and m['schema_version'] == 2
         and m['scope'] == scope and m['plan_blob'] == plan_blob
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
    evidence_bytes = total = verified = expanded = notices = 0
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
                            'status','reason','inspection_reason','evidence'} and
             type(result['sequence']) is int and result['sequence'] == i
             and n.bounded_int(result['received_bytes'],0,row['bytes'])
             and n.digest(result['received_sha256'])
             and (result['http_status'] is None or n.bounded_int(result['http_status'],100,599)),
             'RESULT_IDENTITY')
        detail=result['inspection_reason']
        if result['reason']=='INSPECTION_REFUSED':
            need(type(detail) is str and detail in diagnostic.INSPECTION_REASONS
                 and result['status']=='REFUSED' and result['http_status']==200
                 and result['received_bytes']==row['bytes'] and result['received_sha256']==row['sha256'],
                 'INSPECTION_DETAIL_IDENTITY')
        else:
            need(detail is None,'INSPECTION_DETAIL_IDENTITY')
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
            need(evidence_bytes <= caps['evidence'],'EVIDENCE_BATCH_LIMIT')
            receipt=n.verify_evidence(evidence_raw,filemap[evidence_name]['sha256'],row,plan_blob)
            expanded+=receipt['expanded_bytes']; notices+=receipt['notice_bytes']
            need(expanded<=caps['expanded'] and notices<=caps['notice'],'BATCH_EXPANSION_LIMIT')
            verified += 1
        else:
            need(result['status'] == 'REFUSED' and type(result['reason']) is str and result['reason'] in FAILURES
                 and result['evidence'] is None,'RESULT_IDENTITY')
            stopped = True
        need(get(result_name,MAX_RECORD) == result_raw,'RECEIPT_HASH')
    need(used == [f['name'] for f in files],'MANIFEST_FILE_ORDER')
    need(type(m['verified_count']) is int and m['verified_count'] == verified
         and type(m['received_bytes']) is int and m['received_bytes'] == total <= caps['body']
         and m['missing'] == [r['filename'] for r in rows[verified:]]
         and ((m['status'] == 'BLOCKED' and stopped and count == verified+1)
              or (m['status'] == 'CANDIDATE_EVIDENCE_RECORDED' and not stopped
                  and count == verified == len(rows))), 'MANIFEST_SETTLEMENT')
    return m


def export_generation(path, manifest_sha, rows, plan_blob, parent, *, scope, caps):
    """Verify before packaging; exclusive file in fresh disposable directory."""
    m = verify_generation(path,manifest_sha,rows,plan_blob,scope=scope,caps=caps)
    names = sorted([x['name'] for x in m['files']]+['manifest.json'])
    need(len(names)<=h.MAX_FILES,'BUNDLE_COUNT')
    expected = {f['name']:f for f in m['files']}
    dest = Path(tempfile.mkdtemp(prefix='c5-wheel-export-',dir=parent))/'receipts.odin'
    digest = hashlib.sha256()
    size = 0
    with dest.open('xb') as out:
        def write(raw):
            nonlocal size
            size += len(raw)
            need(size <= bundle_cap(caps),'BUNDLE_LIMIT')
            need(out.write(raw)==len(raw),'BUNDLE_SHORT_WRITE')
            digest.update(raw)
        write(h.MAGIC+struct.pack('>H',len(names)))
        for name in names:
            raw = a.read_bounded(Path(path)/name,h.limit_for(name))
            need(w.sha(raw)==manifest_sha if name=='manifest.json' else
                 a.file_identity(name,raw)==expected[name],'EXPORT_CHANGED')
            write(h._frame(name,raw))
        out.flush()
        os.fsync(out.fileno())
    a.sync_dir(dest.parent)
    a.sync_dir(dest.parent.parent)
    return dest,{'bytes':size,'sha256':digest.hexdigest(),'manifest_sha256':manifest_sha}


def import_generation(bundle, identity, rows, plan_blob, parent, *, scope, caps):
    """Verify exact bundle snapshot against separately retained identity, then replay."""
    need(type(identity) is dict and set(identity)=={'bytes','sha256','manifest_sha256'}
         and n.bounded_int(identity['bytes'],len(h.MAGIC)+2,bundle_cap(caps))
         and n.digest(identity['sha256']) and n.digest(identity['manifest_sha256']),
         'BUNDLE_IDENTITY')
    raw = a.read_bounded(Path(bundle),bundle_cap(caps))
    need(len(raw)==identity['bytes'] and w.sha(raw)==identity['sha256'],'BUNDLE_HASH')
    stream = io.BytesIO(raw)
    need(stream.read(len(h.MAGIC))==h.MAGIC,'BUNDLE_h.MAGIC')
    count_raw=stream.read(2)
    need(len(count_raw)==2,'BUNDLE_HEADER')
    count=struct.unpack('>H',count_raw)[0]
    need(3<=count<=h.MAX_FILES,'BUNDLE_COUNT')
    dest=Path(tempfile.mkdtemp(prefix='c5-wheel-import-',dir=parent))
    seen=[]
    evidence_bytes=0
    for _ in range(count):
        hdr=stream.read(h.FRAME.size)
        need(len(hdr)==h.FRAME.size,'BUNDLE_TRUNCATED')
        name_len,size=h.FRAME.unpack(hdr)
        need(1<=name_len<=64,'BUNDLE_NAME')
        try:
            name=stream.read(name_len).decode('ascii')
        except UnicodeError:
            raise w.Blocked('BUNDLE_NAME') from None
        need(len(name)==name_len and (not seen or seen[-1]<name),'BUNDLE_ORDER')
        need(0<size<=h.limit_for(name),'BUNDLE_FILE_SIZE')
        if name.startswith('wheel-'):
            evidence_bytes+=size
            need(evidence_bytes<=caps['evidence'],'EVIDENCE_BATCH_LIMIT')
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
    m=verify_generation(dest,identity['manifest_sha256'],rows,plan_blob,scope=scope,caps=caps)
    return dest,m


def replay_artifact(raw, meta, record, expected_run, expected_sha, rows, plan_blob, parent,
                    *, scope, caps):
    """Read exact bounded artifact ZIP; never extract arbitrary archive paths."""
    ident = g.verify_artifact_metadata(meta,record,expected_run,expected_sha)
    need(type(raw) is bytes and len(raw)==ident['bytes']<=bundle_cap(caps)+1024*1024 and w.sha(raw)==ident['sha256'],
         'ARTIFACT_HASH')
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as z:
            infos=z.infolist()
            need(len(infos)==1 and not z.comment,'ARTIFACT_INVENTORY')
            item=infos[0]
            need(item.filename==item.orig_filename=='receipts.odin' and not item.is_dir()
                 and not item.flag_bits & 1 and item.compress_type in (0,8)
                 and not item.external_attr & 0x400
                 and stat.S_IFMT(item.external_attr>>16) in (0,stat.S_IFREG),
                 'ARTIFACT_MEMBER')
            bundle=record['bundle']
            need(item.file_size==bundle['bytes'] and item.compress_size<=len(raw),
                 'ARTIFACT_MEMBER_SIZE')
            dest=Path(tempfile.mkdtemp(prefix='c5-artifact-replay-',dir=parent))/'receipts.odin'
            import hashlib
            sha=hashlib.sha256()
            total=0
            with z.open(item) as src, dest.open('xb') as out:
                while True:
                    chunk=src.read(min(a.CHUNK,bundle['bytes']-total+1))
                    if not chunk: break
                    total+=len(chunk)
                    need(total<=bundle['bytes'],'ARTIFACT_MEMBER_SIZE')
                    sha.update(chunk)
                    need(out.write(chunk)==len(chunk),'ARTIFACT_SHORT_WRITE')
                out.flush()
                os.fsync(out.fileno())
            need(total==bundle['bytes'] and sha.hexdigest()==bundle['sha256'],'BUNDLE_HASH')
        return import_generation(dest,bundle,rows,plan_blob,parent,scope=scope,caps=caps)
    except (zipfile.BadZipFile,NotImplementedError,RuntimeError,EOFError,zlib.error):
        raise w.Blocked('ARTIFACT_ZIP_REFUSED') from None



def run_fixture(rows,replay,parent,caps):
    need(not ARMED and type(replay) is a.Replay,'OFFLINE_FIXTURE_ONLY')
    return _collect_core(rows,'fixture',replay.get,parent,nullcontext,FIXTURE_SCOPE,caps)


def _live_fetch(rows, runner, run):
    # Only the authorized collector may create this sequenced transport.
    need(ARMED and os.environ.get('GITHUB_JOB')=='collect-once'
         and (runner/('c5-missing-'+run+'-collect-once.claim')).is_file(),'LIVE_SCOPE')
    iterator=iter(rows)
    def fetch(url):
        need(ARMED,'FRESH_APPROVAL_REQUIRED')
        row=next(iterator,None)
        need(row is not None and a.exact_url(row)==url,'URL_SCOPE')
        host,port,path,headers=h.request_parts(row)
        tls=ssl.create_default_context()
        need(tls.check_hostname and tls.verify_mode==ssl.CERT_REQUIRED,'TLS_POLICY')
        conn=http.client.HTTPSConnection(host,port,timeout=a.REQUEST_TIMEOUT,context=tls)
        try:
            conn.request('GET',path,headers=headers)
            return h._Response(conn,conn.getresponse())
        except BaseException:
            conn.close()
            raise
    return fetch


def settlement(path,m,rows):
    result=a.parse(a.read_bounded(Path(path)/f"request-{m['attempted_count']:03d}-result.json",a.MAX_RECORD))
    return {'summary':d.summary(m),'last_filename':rows[m['attempted_count']-1]['filename'],
            'last_result':result,'combined_verified':5+m['verified_count']}


def produce():
    need(ARMED,'FRESH_APPROVAL_REQUIRED')
    rows,caps=plan()
    runner,run,sha=authorize('collect-once')
    path,digest=_collect_core(rows,diagnostic.MISSING_PLAN_BLOB,_live_fetch(rows,runner,run),
                              runner,h.deadline,HOSTED_SCOPE,caps)
    m=verify_generation(path,digest,rows,diagnostic.MISSING_PLAN_BLOB,scope=HOSTED_SCOPE,caps=caps)
    bundle,ident=export_generation(path,digest,rows,diagnostic.MISSING_PLAN_BLOB,runner,scope=HOSTED_SCOPE,caps=caps)
    record=g.identity(run,sha,ident)
    result=settlement(path,m,rows)
    print('C5_MISSING_PRODUCER '+json.dumps({'identity':record,'settlement':result},sort_keys=True),flush=True)
    with open(os.environ['GITHUB_OUTPUT'],'a',encoding='utf-8') as f:
        f.write('receipt_bundle='+str(bundle)+'\nrecord='+json.dumps(record,separators=(',',':'))+'\nsettlement='+json.dumps(result,separators=(',',':'))+'\n')


def download_exact(record,run,sha,artifact_id,upload_digest,token,opener,caps):
    limit=bundle_cap(caps)+1024*1024
    g.verify_identity(record,run,sha)
    need(record['bundle']['bytes']<=bundle_cap(caps),'BUNDLE_LIMIT')
    need(g.RUN.fullmatch(artifact_id) and n.digest(upload_digest),'UPLOAD_OUTPUT')
    need(bool(token),'ARTIFACT_TOKEN')
    url='https://api.github.com/repos/'+d.REPO+'/actions/artifacts/'+artifact_id
    # Read exactly the associated artifact metadata; never enumerate other artifacts.
    with t.deadline():
        with opener.open(t.get_request(url,token),timeout=15) as resp:
            meta=json.loads(t.read_metadata(resp),object_pairs_hook=n.unique)
    ident=g.verify_artifact_metadata(meta,record,run,sha)
    need(str(ident['id'])==artifact_id and ident['sha256']==upload_digest
         and ident['bytes']<=limit,'ARTIFACT_UPLOAD_IDENTITY')
    # One retrieval. The authenticated API redirect is the authority for the
    # opaque short-lived storage URL. Do not forward the token or log Location.
    with t.deadline():
        try:
            resp=opener.open(t.get_request(url+'/zip',token),timeout=15)
        except HTTPError as exc:
            try:
                need(exc.code==302,'ARTIFACT_REDIRECT')
                values=exc.headers.get_all('Location',[])
                need(len(values)==1 and 0<len(values[0])<=8192,'ARTIFACT_REDIRECT')
                location=values[0]
            finally:
                exc.close()
            u=urlsplit(location)
            need(u.scheme=='https' and u.hostname and u.netloc==u.hostname
                 and (u.hostname.endswith('.blob.core.windows.net')
                      or u.hostname.endswith('.actions.githubusercontent.com')
                      or u.hostname.endswith('.githubusercontent.com'))
                 and u.path.startswith('/') and not u.fragment and bool(u.query),
                 'ARTIFACT_REDIRECT_ORIGIN')
            with opener.open(t.get_request(location),timeout=15) as storage:
                raw=t.read_response(storage,limit,exact=ident['bytes'])
        else:
            with resp:
                raw=t.read_response(resp,limit,exact=ident['bytes'])
    return raw,meta



def retrieve():
    need(ARMED,'FRESH_APPROVAL_REQUIRED')
    rows,caps=plan()
    runner,run,sha=authorize('retrieve-once')
    record=json.loads(os.environ['C5_BUNDLE_RECORD'],object_pairs_hook=n.unique)
    expected=json.loads(os.environ['C5_PRODUCER_SETTLEMENT'],object_pairs_hook=n.unique)
    artifact=os.environ['C5_ARTIFACT_ID']
    digest=os.environ['C5_UPLOAD_DIGEST'].removeprefix('sha256:')
    g.verify_identity(record,run,sha)
    need(record['bundle']['bytes']<=bundle_cap(caps),'BUNDLE_LIMIT')
    opener=build_opener(ProxyHandler({}),t.NoRedirect(),HTTPSHandler(context=ssl.create_default_context()))
    raw,meta=download_exact(record,run,sha,artifact,digest,os.environ['GH_TOKEN'],opener,caps)
    with tempfile.TemporaryDirectory(dir=runner) as temp:
        path,m=replay_artifact(raw,meta,record,run,sha,rows,diagnostic.MISSING_PLAN_BLOB,Path(temp),scope=HOSTED_SCOPE,caps=caps)
        result=settlement(path,m,rows)
        need(result==expected,'PRODUCER_VERIFIER_SETTLEMENT')
    print('C5_MISSING_VERIFIER '+json.dumps({'identity':record,'settlement':result,'artifact_id':artifact,
          'zip_bytes':len(raw),'zip_sha256':w.sha(raw),'status':'REPLAY_PASS','retrievals':1},sort_keys=True),flush=True)
    return 0 if m['verified_count']==63 else 2


if __name__=='__main__':
    try:
        if sys.argv[1:]==['--collect']: produce()
        elif sys.argv[1:]==['--retrieve']: raise SystemExit(retrieve())
        else: raise ValueError('COMMAND_REFUSED')
    except Exception:
        print('C5_MISSING_REFUSAL TRANSPORT_OR_EVIDENCE_REFUSED',flush=True)
        raise SystemExit(2)
