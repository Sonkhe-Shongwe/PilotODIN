"""One approved inert receipt transfer; never collect actual wheels.

Separate producer and verifier jobs use a deterministic synthetic fixture.
The verifier retrieves only the exact artifact ID from this run, checks
service and producer digests, and replays the original bounded receipt.
"""
from __future__ import annotations

import contextlib
import io
import json
import os
from pathlib import Path
import re
import signal
import ssl
import sys
import tempfile
from urllib.error import HTTPError
from urllib.parse import urlsplit
from urllib.request import build_opener, HTTPSHandler, HTTPRedirectHandler, ProxyHandler
from unittest.mock import patch
import zipfile

sys.path.insert(0,str(Path(__file__).resolve().parent))
import collect_remaining_checksums as checksums
import wheel_acquisition_offline as a
import wheel_archive_inspector as w
import wheel_hosted_proposal as h
import wheel_notice_evidence as n
import wheel_one_use_review as g
from test_wheel_acquisition_offline import candidate, wire
from test_wheel_archive_inspector import D

OP='C5-SYNTHETIC-RECEIPT-TRANSFER-ONCE-20261126'
WORKFLOW='C5 synthetic receipt transfer once'
REPO='Sonkhe-Shongwe/PilotODIN'
MARKER=n.ROOT/(n.DIR+'APPROVAL_SYNTHETIC_RECEIPT_TRANSFER_20261126.txt')
MARKER_BYTES=(OP+'\nOne inert receipt-only artifact upload and retrieval; no actual wheels or retries.\n').encode('ascii')
CHECKSUM_RECEIPT=n.ROOT/(n.DIR+'toolchain_remaining_checksum_receipt_45725150647.jsonl')
CHECKSUM_SHA='ab853994195f51e7f57dcf792298436dd55a98f28efbbe8f2a5207f7b851e53f'
CHECKSUM_BLOB='5c51fbf25b0b2a78cdc9a313758569aad9f53561'
ENABLED=False


def need(ok,reason):
    w.require(ok,reason)


def verify_checksums():
    raw=a.read_bounded(CHECKSUM_RECEIPT,2*1024*1024)
    need(w.sha(raw)==CHECKSUM_SHA and g.git_blob(raw)==CHECKSUM_BLOB,'CHECKSUM_RECEIPT_PIN')
    records=[json.loads(line,object_pairs_hook=n.unique) for line in raw.splitlines()]
    need(len(records)==156 and b''.join(checksums.canonical(x) for x in records)==raw,
         'CHECKSUM_RECEIPT_CANONICAL')
    m,docs,prior=checksums.load()
    result=checksums.verify_receipt(lambda d,raw:checksums.parse_document(m,d,raw),docs,records)
    need(result=={'artifact_requests':0,'failure':None,'fixture':False,'missing':[],
                 'requests':4,'response_bytes':898778,'status':'METADATA_ONLY_COMPLETE',
                 'verified':['python-linux','node','rust']},'CHECKSUM_RECEIPT_RESULT')
    need(checksums.LIVE_ENABLED is False,'CHECKSUM_DISARM')
    print('C5_CHECKSUM_INDEPENDENT_REPLAY '+json.dumps(result,sort_keys=True),flush=True)


def fixture():
    with patch('zipfile.time.localtime',return_value=(2020,1,1,0,0,0,2,1,-1)):
        return candidate(compress=0,changes={D+'licenses/LICENSE':b'Inert generated notice.\n\x00\xff'})


def make_bundle(parent,run,sha):
    raw,row=fixture()
    path,digest=a._run([row],'synthetic-transfer-v1',a.Replay({row['url']:wire(raw)}),parent)
    bundle,ident=h.export_generation(path,digest,[row],'synthetic-transfer-v1',parent)
    need(ident['bytes']<=68550656,'APPROVED_BUNDLE_CAP')
    return bundle,g.identity(run,sha,ident),[row]


def self_test():
    verify_checksums()
    g.verify_pins()
    first,row=fixture()
    need(fixture()==(first,row),'FIXTURE_NONDETERMINISTIC')
    with tempfile.TemporaryDirectory() as d:
        b,record,rows=make_bundle(Path(d),'12345','1'*40)
        z=io.BytesIO()
        with zipfile.ZipFile(z,'w',compression=zipfile.ZIP_STORED) as f:
            f.writestr('receipts.odin',b.read_bytes())
        raw=z.getvalue()
        meta={'id':123,'name':record['artifact_name'],'expired':False,'size_in_bytes':len(raw),
              'digest':'sha256:'+w.sha(raw),'workflow_run':{'id':12345,'head_sha':'1'*40,
              'head_branch':h.BRANCH.removeprefix('refs/heads/')}}
        _,receipt=g.replay_artifact(raw,meta,record,'12345','1'*40,rows,
                                   'synthetic-transfer-v1',Path(d),scope=a.SCOPE)
        need(receipt['verified_count']==1 and receipt['production_ready'] is False,'FIXTURE_REPLAY')
    if not ENABLED:
        try: authorize()
        except w.Blocked as exc: need(str(exc)=='FRESH_APPROVAL_REQUIRED','DISARM')
        else: raise w.Blocked('DISARM')
    print('C5_SYNTHETIC_PREFLIGHT PASS: pinned source, deterministic fixture, persisted checksum replay, artifact ZIP replay; no external calls',flush=True)


def authorize():
    need(ENABLED is True,'FRESH_APPROVAL_REQUIRED')
    e=os.environ
    need(e.get('GITHUB_ACTIONS')=='true' and e.get('GITHUB_EVENT_NAME')=='push'
         and e.get('GITHUB_REPOSITORY')==REPO and e.get('GITHUB_WORKFLOW')==WORKFLOW
         and e.get('GITHUB_REF')==h.BRANCH and e.get('GITHUB_RUN_ATTEMPT')=='1'
         and e.get('C5_APPROVED_ONCE')==OP and g.SHA1.fullmatch(e.get('GITHUB_SHA',''))
         and g.RUN.fullmatch(e.get('GITHUB_RUN_ID','')),'TRANSFER_CONTEXT')
    need(MARKER.is_file() and not MARKER.is_symlink()
         and MARKER.read_bytes()==MARKER_BYTES,'TRANSFER_MARKER')
    need(h.LIVE_ENABLED is False and g.ENABLED is False and a.LIVE_ENABLED is False,
         'REAL_WHEEL_DISABLED')
    return e['GITHUB_RUN_ID'],e['GITHUB_SHA']


def produce():
    run,sha=authorize()
    bundle,record,_=make_bundle(Path(os.environ['RUNNER_TEMP']),run,sha)
    print('C5_SYNTHETIC_BUNDLE '+json.dumps(record,sort_keys=True),flush=True)
    with open(os.environ['GITHUB_OUTPUT'],'a',encoding='utf-8') as out:
        out.write('bundle='+str(bundle)+'\nrecord='+json.dumps(record,separators=(',',':'))+'\n')


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):
        return None


@contextlib.contextmanager
def deadline():
    need(signal.getitimer(signal.ITIMER_REAL)==(0.,0.),'TIMER_BUSY')
    def expired(*_): raise w.Blocked('TRANSFER_DEADLINE')
    prior=signal.signal(signal.SIGALRM,expired)
    try:
        signal.setitimer(signal.ITIMER_REAL,60)
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL,0)
        signal.signal(signal.SIGALRM,prior)


def read_response(resp, cap, *, exact=None):
    need(resp.status==200,'ARTIFACT_HTTP_STATUS')
    lengths=resp.headers.get_all('Content-Length',[])
    need(len(lengths)==1 and re.fullmatch(r'[0-9]{1,10}',lengths[0]),'ARTIFACT_LENGTH')
    size=int(lengths[0])
    need(0<size<=cap and (exact is None or size==exact),'ARTIFACT_LENGTH')
    enc=resp.headers.get_all('Content-Encoding',[])
    need(not enc or enc==['identity'],'ARTIFACT_ENCODING')
    need(not resp.headers.get_all('Transfer-Encoding',[]),'ARTIFACT_FRAMING')
    raw=resp.read(size)
    need(len(raw)==size,'ARTIFACT_SHORT_READ')
    return raw


def read_metadata(resp):
    # GitHub API JSON may use chunked framing; only the small metadata
    # endpoint permits it. The actual artifact still requires exact length.
    need(resp.status==200,'ARTIFACT_HTTP_STATUS')
    enc=resp.headers.get_all('Content-Encoding',[])
    need(not enc or enc==['identity'],'ARTIFACT_ENCODING')
    transfer=resp.headers.get_all('Transfer-Encoding',[])
    lengths=resp.headers.get_all('Content-Length',[])
    if lengths:
        return read_response(resp,65536)
    need(not transfer or transfer==['chunked'],'ARTIFACT_FRAMING')
    raw=resp.read(65536)
    need(0<len(raw)<65536,'ARTIFACT_METADATA_LIMIT')
    return raw


def get_request(url,token=None):
    from urllib.request import Request
    headers={'Accept-Encoding':'identity','User-Agent':'PilotODIN-C5-synthetic-receipt/1'}
    if token is not None:
        headers.update(Authorization='Bearer '+token,Accept='application/vnd.github+json',
                       **{'X-GitHub-Api-Version':'2022-11-28'})
    return Request(url,headers=headers,method='GET')


def verify_transfer():
    run,sha=authorize()
    record=json.loads(os.environ['C5_BUNDLE_RECORD'],object_pairs_hook=n.unique)
    g.verify_identity(record,run,sha)
    artifact_id=os.environ['C5_ARTIFACT_ID']
    upload_digest=os.environ['C5_UPLOAD_DIGEST'].removeprefix('sha256:')
    need(g.RUN.fullmatch(artifact_id) and n.digest(upload_digest),'UPLOAD_OUTPUT')
    token=os.environ['GH_TOKEN']
    need(bool(token),'ARTIFACT_TOKEN')
    url='https://api.github.com/repos/'+REPO+'/actions/artifacts/'+artifact_id
    opener=build_opener(ProxyHandler({}),NoRedirect(),HTTPSHandler(context=ssl.create_default_context()))
    # Read exactly the associated artifact metadata; never enumerate other artifacts.
    with deadline():
        with opener.open(get_request(url,token),timeout=15) as resp:
            meta=json.loads(read_metadata(resp),object_pairs_hook=n.unique)
    ident=g.verify_artifact_metadata(meta,record,run,sha)
    need(str(ident['id'])==artifact_id and ident['sha256']==upload_digest
         and ident['bytes']<=69599232,'ARTIFACT_UPLOAD_IDENTITY')
    # One retrieval. The authenticated API redirect is the authority for the
    # opaque short-lived storage URL. Do not forward the token or log Location.
    with deadline():
        try:
            resp=opener.open(get_request(url+'/zip',token),timeout=15)
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
            with opener.open(get_request(location),timeout=15) as storage:
                raw=read_response(storage,69599232,exact=ident['bytes'])
        else:
            with resp:
                raw=read_response(resp,69599232,exact=ident['bytes'])
    _,row=fixture()
    with tempfile.TemporaryDirectory(dir=os.environ['RUNNER_TEMP']) as d:
        _,receipt=g.replay_artifact(raw,meta,record,run,sha,[row],
                                    'synthetic-transfer-v1',Path(d),scope=a.SCOPE)
    need(receipt['verified_count']==1 and receipt['status']=='CANDIDATE_EVIDENCE_RECORDED'
         and receipt['production_ready'] is False,'ARTIFACT_REPLAY')
    print('C5_SYNTHETIC_TRANSFER '+json.dumps({'status':'PASS','run_id':run,'source_sha':sha,
          'artifact_id':artifact_id,'zip_bytes':len(raw),'zip_sha256':w.sha(raw),
          'bundle':record['bundle'],'synthetic_wheels':1,'real_wheels':0,
          'retrievals':1,'license_reviewed':False},sort_keys=True),flush=True)


if __name__=='__main__':
    try:
        if sys.argv[1:]==['--self-test']: self_test()
        elif sys.argv[1:]==['--produce']: produce()
        elif sys.argv[1:]==['--retrieve']: verify_transfer()
        else: raise w.Blocked('COMMAND_REFUSED')
    except w.Blocked as exc:
        print('C5_SYNTHETIC_REFUSAL '+str(exc),flush=True)
        raise SystemExit(2)
    except (OSError,ValueError,KeyError,HTTPError):
        # No exception string: might contain signed storage URL or credentials.
        print('C5_SYNTHETIC_REFUSAL TRANSPORT_OR_EVIDENCE_REFUSED',flush=True)
        raise SystemExit(2)
