"""Final disarmed hosted policy-v3 collector and receipt retriever.

One scope-aware successor to the pinned settlement/transfer algorithms.
Real collection and retrieval require a separately reviewed source arm,
independently provisioned exact expectation and marker-only activation.
No test or environment variable arms this checked-in revision.
"""
from __future__ import annotations

import copy
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
import threading
from urllib.error import HTTPError
from urllib.parse import urlsplit
from urllib.request import build_opener, HTTPSHandler, ProxyHandler
import zipfile
import zlib

ARMED=False
if __name__=='__main__' and ARMED is not True:
    raise SystemExit('FRESH_APPROVAL_REQUIRED: final hosted driver disabled')

import wheel_acquisition_offline as a
import wheel_archive_inspector as w
import wheel_notice_evidence_v2 as n
import wheel_license_policy as p
import wheel_settlement_core as c
import wheel_hosted_proposal as h
import wheel_hosted_policy_v3 as m
import wheel_hosted_runtime as rt
import wheel_diagnostic_offline as diagnostic
import synthetic_receipt_transfer as t

ROOT=n.ROOT
DIR=n.DIR
SELF=DIR+'wheel_hosted_final.py'
WORKFLOW='.github/workflows/c5-wheel-hosted-final-review.yml'
FIXTURE_SCOPE=c.FIXTURE_SCOPE
HOSTED_SCOPE=m.HOSTED_SCOPE
ARTIFACT_PREFIX='c5-final-policy-v3-receipts-'
REPO=m.REPO
MARKER=m.MARKER
need=a.need
InspectionLedger=c.InspectionLedger
safe_inspection_reason=c.safe_inspection_reason
INSPECTION_REASONS=c.INSPECTION_REASONS
MAX_MANIFEST=c.MAX_MANIFEST
MAX_REQUESTS=c.MAX_REQUESTS
MAX_RECORD=c.MAX_RECORD
FAILURES=c.FAILURES
_Generation=c._Generation
_receive=c._receive
request_intent=c.request_intent
file_identity=c.file_identity
read_bounded=c.read_bounded
parse=c.parse
bundle_cap=m.bundle_cap
RUN=m.RUN
SHA1=m.SHA1
BRANCH=m.BRANCH
EXTRA_PINS={
    rt.SELF:'e20cc3f4f11c2d5a4659e9537d565687687a2f49',
    rt.WORKFLOW:'6841fe32a484245b437fa6f07cf6ada88dd042cd',
    DIR+'synthetic_receipt_transfer.py':'9dd872b7b1d9caf4b930ff4fcc115fef27f3281d',
}

def prepare(rows,plan_blob,bindings,caps,scope):
    need(scope in (FIXTURE_SCOPE,HOSTED_SCOPE),'SCOPE')
    rows,bindings,caps,policy_sha=c.prepare(rows,plan_blob,bindings,caps,FIXTURE_SCOPE)
    need(len(rows)<=63,'REMAINING_COUNT')
    if scope==HOSTED_SCOPE:
        exact_rows,exact_bindings,exact_caps=c.remaining_inputs()
        need(plan_blob==diagnostic.MISSING_PLAN_BLOB
             and n.canonical(rows)==n.canonical(exact_rows)
             and n.canonical(bindings)==n.canonical(exact_bindings)
             and n.canonical(caps)==n.canonical(exact_caps),'HOSTED_INPUT_IDENTITY')
    return rows,bindings,caps,policy_sha

def _json(raw):
    try:
        return json.loads(raw,object_pairs_hook=n.unique)
    except (UnicodeError,json.JSONDecodeError,RecursionError):
        raise w.Blocked('RUNTIME_JSON') from None

def _env_json(name,cap):
    raw=os.environ.get(name,'').encode('utf-8')
    need(0<len(raw)<=cap,'RUNTIME_JSON_LIMIT')
    return _json(raw)

def review_checkout(root,event,context,expected,phase):
    """Purely read-only gate; caller must supply independent expectation."""
    observed=rt.observe_checkout(root)
    for path,pin in EXTRA_PINS.items():
        need(rt.checkout_blob(root,path)==pin,'SOURCE_PIN')
    observed['driver_blob']=rt.checkout_blob(root,SELF)
    observed['workflow_blob']=rt.checkout_blob(root,WORKFLOW)
    return rt.activation_contract(event,context,observed,expected,phase,rt.input_identity())

class _Grant:
    """Private process-local claim, not a security boundary against Python code."""
    def __init__(self,runner,claim,path):
        self.runner=runner
        self.claim=claim
        self.path=path

def authorize(phase):
    need(ARMED is True,'FRESH_APPROVAL_REQUIRED')
    need(os.name=='posix' and threading.current_thread() is threading.main_thread(),'HOSTED_PLATFORM')
    env=os.environ
    need(env.get('GITHUB_WORKSPACE')==str(ROOT) and phase in ('collect-once','retrieve-once'),
         'RUNTIME_CONTEXT')
    # Future arm must provision this expectation independently of the push
    # payload and checkout, after reviewing the exact unpublished child SHA.
    expected=_env_json('C5_REVIEWED_EXPECTATION',16384)
    event_path=Path(env.get('GITHUB_EVENT_PATH',''))
    event=_json(read_bounded(event_path,rt.EVENT_CAP))
    claim=review_checkout(ROOT,event,dict(env),expected,phase)
    need(claim['scope']==m.TRANSFER_SCOPE,'GATE_SCOPE')
    runner=Path(env.get('RUNNER_TEMP',''))
    need(runner.is_absolute() and runner.is_dir() and not runner.is_symlink()
         and not runner.resolve().is_relative_to(ROOT.resolve()),'RUNNER_TEMP')
    claim={**claim,'scope':HOSTED_SCOPE}
    path=runner/('c5-final-policy-v3-'+claim['run']+'-'+phase+'.claim')
    try:
        with path.open('xb') as out:
            raw=n.canonical(claim)
            need(out.write(raw)==len(raw),'CLAIM_WRITE')
            out.flush()
            os.fsync(out.fileno())
    except FileExistsError:
        raise w.Blocked('ONE_USE_CLAIM_CONSUMED') from None
    a.sync_dir(runner)
    return _Grant(runner,claim,path)

def _check_grant(grant,phase):
    need(ARMED is True,'FRESH_APPROVAL_REQUIRED')
    need(type(grant) is _Grant and grant.claim['scope']==HOSTED_SCOPE
         and grant.claim['phase']==phase and os.environ.get('GITHUB_JOB')==phase
         and grant.claim['run']==os.environ.get('GITHUB_RUN_ID')
         and grant.claim['source_sha']==os.environ.get('GITHUB_SHA')
         and read_bounded(grant.path,2048)==n.canonical(grant.claim),'LIVE_SCOPE')

def _live_fetch(grant,rows):
    _check_grant(grant,'collect-once')
    exact,_,_=c.remaining_inputs()
    need(n.canonical(rows)==n.canonical(exact),'HOSTED_INPUT_IDENTITY')
    sequence=iter(copy.deepcopy(exact))
    stopped=False
    def fetch(url):
        nonlocal stopped
        _check_grant(grant,'collect-once')
        need(not stopped,'TRANSPORT_STOPPED')
        row=next(sequence,None)
        if row is None or url!=a.exact_url(row):
            stopped=True
            raise w.Blocked('URL_SCOPE')
        host,port,path,headers=h.request_parts(row)
        tls=ssl.create_default_context()
        need(tls.check_hostname and tls.verify_mode==ssl.CERT_REQUIRED,'TLS_POLICY')
        conn=http.client.HTTPSConnection(host,port,timeout=a.REQUEST_TIMEOUT,context=tls)
        try:
            conn.request('GET',path,headers=headers)
            response=h._Response(conn,conn.getresponse())
            if response.status!=200: stopped=True
            return response
        except BaseException:
            stopped=True
            conn.close()
            raise
    return fetch

def _collect(rows, plan_blob, bindings, caps, scope, fetch, deadline, parent):
    rows,bindings,caps,policy_sha=prepare(rows,plan_blob,bindings,caps,scope)
    batch=InspectionLedger(caps)
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
                doc, digest = batch.inspect(raw,row,bindings[row['filename']],plan_blob)
            except w.Blocked as exc:
                reason = 'INSPECTION_REFUSED'
                inspection_reason = safe_inspection_reason(exc)
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
    manifest = {'schema_version':3,'scope':scope,'plan_blob':plan_blob,
                'status':'CANDIDATE_EVIDENCE_RECORDED' if verified == len(rows) else 'BLOCKED',
                'expected_count':len(rows),'attempted_count':attempted,
                'verified_count':verified,'received_bytes':total,
                'missing':[r['filename'] for r in rows[verified:]],
                'license_reviewed':False,'production_ready':False,
                'policy_sha256':policy_sha,'caps':caps,'accepted_totals':batch.accepted.copy()}
    digest = store.finish(manifest)
    return store.path, digest




def verify_generation(path, manifest_sha, rows, plan_blob, *, scope, caps, bindings):
    """Independent read-only replay. Missing terminal manifest is unsettled."""
    rows,bindings,caps,policy_sha=prepare(rows,plan_blob,bindings,caps,scope)
    path = Path(path)
    need(path.is_dir() and not path.is_symlink(), 'GENERATION_PATH')
    manifest_path = path/'manifest.json'
    need(manifest_path.is_file() and not manifest_path.is_symlink(), 'UNSETTLED_GENERATION')
    raw = read_bounded(manifest_path, MAX_MANIFEST)
    need(n.digest(manifest_sha) and w.sha(raw) == manifest_sha, 'MANIFEST_HASH')
    m = parse(raw)
    keys = {'schema_version','scope','plan_blob','status','expected_count',
            'attempted_count','verified_count','received_bytes','missing',
            'license_reviewed','production_ready','files','policy_sha256','caps','accepted_totals'}
    need(set(m) == keys and type(m['schema_version']) is int and m['schema_version'] == 3
         and m['scope'] == scope and m['plan_blob'] == plan_blob
         and m['license_reviewed'] is False and m['production_ready'] is False,
         'MANIFEST_IDENTITY')
    need(m['policy_sha256']==policy_sha and n.canonical(m['caps'])==n.canonical(caps),'MANIFEST_POLICY_IDENTITY')
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
            need(type(detail) is str and detail in INSPECTION_REASONS
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
            receipt=p.verify_evidence(evidence_raw,filemap[evidence_name]['sha256'],row,plan_blob,bindings[row['filename']])
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
    need(n.canonical(m['accepted_totals'])==n.canonical({'expanded':expanded,'notice':notices,'evidence':evidence_bytes}),
         'MANIFEST_RESOURCE_TOTALS')
    return m


def artifact_record(run,source,bundle,rows,plan_blob,*,bindings,caps,scope):
    rows,bindings,caps,policy_sha=prepare(rows,plan_blob,bindings,caps,scope)
    need(len(rows)<=63,'REMAINING_COUNT')
    need(type(run) is str and RUN.fullmatch(run) and type(source) is str and SHA1.fullmatch(source),
         'RECEIPT_CONTEXT')
    need(type(bundle) is dict and set(bundle)=={'bytes','sha256','manifest_sha256'}
         and n.bounded_int(bundle['bytes'],len(h.MAGIC)+2,bundle_cap(caps))
         and n.digest(bundle['sha256']) and n.digest(bundle['manifest_sha256']),'BUNDLE_IDENTITY')
    return {'schema_version':2,'scope':scope,'run_id':run,'run_attempt':1,
            'source_sha':source,'artifact_name':ARTIFACT_PREFIX+run+'-1',
            'plan_blob':plan_blob,'rows_sha256':w.sha(n.canonical(rows)),
            'policy_sha256':policy_sha,'caps':caps,'bundle':copy.deepcopy(bundle)}

def verify_artifact_metadata(meta,record,expected_run,expected_sha,expected_id,upload_sha,
                             rows,plan_blob,*,bindings,caps,scope):
    need(type(record) is dict and 'bundle' in record,'RECEIPT_CONTEXT')
    reviewed=artifact_record(expected_run,expected_sha,record['bundle'],rows,plan_blob,bindings=bindings,caps=caps,scope=scope)
    need(n.canonical(record)==n.canonical(reviewed),'RECEIPT_CONTEXT')
    need(type(meta) is dict and n.bounded_int(expected_id,1,2**63-1)
         and type(meta.get('id')) is int and meta['id']==expected_id
         and meta.get('name')==reviewed['artifact_name'] and meta.get('expired') is False
         and n.bounded_int(meta.get('size_in_bytes'),1,bundle_cap(caps)+1024*1024),'ARTIFACT_IDENTITY')
    workflow=meta.get('workflow_run')
    need(type(workflow) is dict and type(workflow.get('id')) is int
         and str(workflow['id'])==expected_run and workflow.get('head_sha')==expected_sha
         and workflow.get('head_branch')==BRANCH.removeprefix('refs/heads/'),'ARTIFACT_RUN')
    need(n.digest(upload_sha) and meta.get('digest')=='sha256:'+upload_sha,'ARTIFACT_UPLOAD_IDENTITY')
    return {'id':expected_id,'bytes':meta['size_in_bytes'],'sha256':upload_sha}

def export_generation(path, manifest_sha, rows, plan_blob, parent, *, bindings, caps, scope):
    """Verify before packaging; exclusive file in fresh disposable directory."""
    need(len(rows)<=63,'REMAINING_COUNT')
    m = verify_generation(path,manifest_sha,rows,plan_blob,bindings=bindings,caps=caps,scope=scope)
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


def import_generation(bundle, identity, rows, plan_blob, parent, *, bindings, caps, scope):
    """Verify exact bundle snapshot against separately retained identity, then replay."""
    prepare(rows,plan_blob,bindings,caps,scope)
    need(len(rows)<=63,'REMAINING_COUNT')
    need(type(identity) is dict and set(identity)=={'bytes','sha256','manifest_sha256'}
         and n.bounded_int(identity['bytes'],len(h.MAGIC)+2,bundle_cap(caps))
         and n.digest(identity['sha256']) and n.digest(identity['manifest_sha256']),
         'BUNDLE_IDENTITY')
    raw = a.read_bounded(Path(bundle),bundle_cap(caps))
    need(len(raw)==identity['bytes'] and w.sha(raw)==identity['sha256'],'BUNDLE_HASH')
    stream = io.BytesIO(raw)
    need(stream.read(len(h.MAGIC))==h.MAGIC,'BUNDLE_MAGIC')
    count_raw=stream.read(2)
    need(len(count_raw)==2,'BUNDLE_HEADER')
    count=struct.unpack('>H',count_raw)[0]
    need(3<=count<=3*len(rows)+1,'BUNDLE_COUNT')
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
    m=verify_generation(dest,identity['manifest_sha256'],rows,plan_blob,bindings=bindings,caps=caps,scope=scope)
    return dest,m


def replay_artifact(raw, meta, record, expected_run, expected_sha, expected_id, upload_sha,
                    rows, plan_blob, parent,
                    *, bindings, caps, scope):
    """Read exact bounded artifact ZIP; never extract arbitrary archive paths."""
    ident = verify_artifact_metadata(meta,record,expected_run,expected_sha,expected_id,upload_sha,
                                     rows,plan_blob,bindings=bindings,caps=caps,scope=scope)
    need(type(raw) is bytes and len(raw)==ident['bytes']<=bundle_cap(caps)+1024*1024 and w.sha(raw)==ident['sha256'],
         'ARTIFACT_HASH')
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as z:
            infos=z.infolist()
            need(len(infos)==1 and not z.comment,'ARTIFACT_INVENTORY')
            item=infos[0]
            need(item.filename==item.orig_filename=='receipts.odin' and not item.is_dir()
                 and not item.flag_bits & 1 and item.compress_type in (0,8)
                 and not item.external_attr & (0x400 | 0x08 | 0x10 | 0x40)
                 and not (item.external_attr>>16) & (stat.S_ISUID|stat.S_ISGID|stat.S_ISVTX)
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
        return import_generation(dest,bundle,rows,plan_blob,parent,bindings=bindings,caps=caps,scope=scope)
    except (zipfile.BadZipFile,NotImplementedError,RuntimeError,EOFError,zlib.error):
        raise w.Blocked('ARTIFACT_ZIP_REFUSED') from None



def _download_exact(grant,record,run,sha,artifact_id,upload_digest,token,opener,rows,plan_blob,*,bindings,caps,scope):
    _check_grant(grant,'retrieve-once')
    need(scope==HOSTED_SCOPE,'LIVE_SCOPE')
    limit=bundle_cap(caps)+1024*1024
    need(type(record) is dict and 'bundle' in record,'RECEIPT_CONTEXT')
    reviewed=artifact_record(run,sha,record['bundle'],rows,plan_blob,bindings=bindings,caps=caps,scope=scope)
    need(n.canonical(record)==n.canonical(reviewed),'RECEIPT_CONTEXT')
    need(record['bundle']['bytes']<=bundle_cap(caps),'BUNDLE_LIMIT')
    need(RUN.fullmatch(artifact_id) and n.digest(upload_digest),'UPLOAD_OUTPUT')
    need(bool(token),'ARTIFACT_TOKEN')
    url='https://api.github.com/repos/'+REPO+'/actions/artifacts/'+artifact_id
    # Read exactly the associated artifact metadata; never enumerate other artifacts.
    with t.deadline():
        with opener.open(t.get_request(url,token),timeout=15) as resp:
            meta=_json(t.read_metadata(resp))
    ident=verify_artifact_metadata(meta,record,run,sha,int(artifact_id),upload_digest,rows,plan_blob,
                                  bindings=bindings,caps=caps,scope=scope)
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




def _settlement(path,manifest,sha,rows):
    return rt.settlement(path,manifest,sha,rows)

def _produce(rows,bindings,caps,scope,plan_blob,fetch,deadline,parent,run,source):
    path,sha=_collect(rows,plan_blob,bindings,caps,scope,fetch,deadline,parent)
    manifest=verify_generation(path,sha,rows,plan_blob,scope=scope,bindings=bindings,caps=caps)
    bundle,ident=export_generation(path,sha,rows,plan_blob,parent,scope=scope,bindings=bindings,caps=caps)
    record=artifact_record(run,source,ident,rows,plan_blob,scope=scope,bindings=bindings,caps=caps)
    return bundle,record,_settlement(path,manifest,sha,rows)

def _replay(raw,meta,record,expected,run,source,artifact_id,digest,rows,plan_blob,parent,*,bindings,caps,scope):
    path,manifest=replay_artifact(raw,meta,record,run,source,artifact_id,digest,rows,plan_blob,parent,
                                 bindings=bindings,caps=caps,scope=scope)
    observed=_settlement(path,manifest,record['bundle']['manifest_sha256'],rows)
    need(type(expected) is dict and n.canonical(observed)==n.canonical(expected),'PRODUCER_VERIFIER_SETTLEMENT')
    return observed

def produce():
    grant=authorize('collect-once')
    rows,bindings,caps=c.remaining_inputs()
    bundle,record,result=_produce(rows,bindings,caps,HOSTED_SCOPE,diagnostic.MISSING_PLAN_BLOB,
                                  _live_fetch(grant,rows),h.deadline,grant.runner,
                                  grant.claim['run'],grant.claim['source_sha'])
    _check_grant(grant,'collect-once')
    print('C5_FINAL_PRODUCER '+json.dumps({'identity':record,'settlement':result},sort_keys=True),flush=True)
    with open(os.environ['GITHUB_OUTPUT'],'a',encoding='utf-8') as out:
        out.write('receipt_bundle='+str(bundle)+'\nrecord='+json.dumps(record,separators=(',',':'))+
                  '\nsettlement='+json.dumps(result,separators=(',',':'))+'\n')

def retrieve():
    grant=authorize('retrieve-once')
    rows,bindings,caps=c.remaining_inputs()
    record=_env_json('C5_BUNDLE_RECORD',16384)
    expected=_env_json('C5_PRODUCER_SETTLEMENT',65536)
    artifact=os.environ.get('C5_ARTIFACT_ID','')
    digest=os.environ.get('C5_UPLOAD_DIGEST','').removeprefix('sha256:')
    _check_grant(grant,'retrieve-once')
    tls=ssl.create_default_context()
    need(tls.check_hostname and tls.verify_mode==ssl.CERT_REQUIRED,'TLS_POLICY')
    opener=build_opener(ProxyHandler({}),t.NoRedirect(),HTTPSHandler(context=tls))
    run,source=grant.claim['run'],grant.claim['source_sha']
    raw,meta=_download_exact(grant,record,run,source,artifact,digest,os.environ.get('GH_TOKEN',''),opener,
                             rows,diagnostic.MISSING_PLAN_BLOB,bindings=bindings,caps=caps,scope=HOSTED_SCOPE)
    with tempfile.TemporaryDirectory(dir=grant.runner) as tmp:
        observed=_replay(raw,meta,record,expected,run,source,int(artifact),digest,
                         rows,diagnostic.MISSING_PLAN_BLOB,Path(tmp),bindings=bindings,caps=caps,scope=HOSTED_SCOPE)
    print('C5_FINAL_VERIFIER '+json.dumps({'identity':record,'settlement':observed,'artifact_id':artifact,
          'zip_bytes':len(raw),'zip_sha256':w.sha(raw),'status':'REPLAY_PASS','retrievals':1},sort_keys=True),flush=True)
    return 0 if observed['verified_count']==63 else 2

if __name__=='__main__':
    try:
        if sys.argv[1:]==['--collect']: produce()
        elif sys.argv[1:]==['--retrieve']: raise SystemExit(retrieve())
        else: raise w.Blocked('COMMAND_REFUSED')
    except Exception:
        print('C5_FINAL_REFUSAL TRANSPORT_OR_EVIDENCE_REFUSED',flush=True)
        raise SystemExit(2)
