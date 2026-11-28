"""Read-only runtime gate and inert ordered transport rehearsal.

No real acquisition authority: both hosted entrypoints hard refuse. Git
observation and claims below are exercised only in disposable fixture checkouts.
An approved future arm needs a separately pinned parent/child and hosted scope.
"""
from __future__ import annotations

if __name__=='__main__':
    raise SystemExit('FRESH_APPROVAL_REQUIRED: hosted runtime disabled')

from contextlib import nullcontext
import copy
import http.client
import json
import os
from pathlib import Path
import ssl
import subprocess

import wheel_acquisition_offline as a
import wheel_archive_inspector as w
import wheel_notice_evidence_v2 as n
import wheel_license_policy as p
import wheel_settlement_core as c
import wheel_hosted_proposal as h
import wheel_hosted_policy_v3 as m
import wheel_diagnostic_offline as diagnostic

ROOT=n.ROOT
DIR=n.DIR
SELF=DIR+'wheel_hosted_runtime.py'
WORKFLOW='.github/workflows/c5-wheel-hosted-runtime-review.yml'
REPO=m.REPO
BRANCH=m.BRANCH
WORKFLOW_NAME=m.WORKFLOW_NAME
OP=m.OP
MESSAGE=m.MESSAGE
MARKER=m.MARKER
TRANSFER_SCOPE=m.TRANSFER_SCOPE
SHA1=m.SHA1
RUN=m.RUN
marker_bytes=m.marker_bytes
git_blob=m.git_blob
need=a.need
RUNTIME_PINS={
    **m.SOURCE_PINS,
    m.SELF:'939bb94802311a45a7f8e3f23183100c857df3be',
    m.WORKFLOW:'d5bbe7c9f637163b758120caefe1243af3ee8644',
    DIR+'wheel_acquisition_plan_20261125.json':n.PLAN_BLOB,
    DIR+'platform_lock_candidates_45703125465.json':n.TEST_BLOB,
    DIR+'production_graph_receipt_45705552265.json':n.PROD_BLOB,
    DIR+'wheel_missing_plan_20261126.json':diagnostic.MISSING_PLAN_BLOB,
    DIR+'wheel_receipt_diagnosis_45753813079.json':diagnostic.DIAGNOSIS_BLOB,
    DIR+p.FREEZER:p.FREEZER_BLOB,
}
EVENT_CAP=1024*1024

def input_identity():
    # Independent pinned plan and preserved receipts; deliberately no current
    # marker-absence dependency in the pure activation expectation.
    rows,bindings,caps=c.remaining_inputs()
    return {'plan_blob':diagnostic.MISSING_PLAN_BLOB,'rows_sha256':w.sha(n.canonical(rows)),
            'policy_sha256':w.sha(n.canonical(bindings)),'caps':caps,
            'count':len(rows),'redirects':0,'retries':0}

def git(root,*args):
    try:
        proc=subprocess.run(['git','--no-replace-objects','--no-optional-locks','-C',str(root),*args],
                            check=True,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,timeout=10)
        return proc.stdout
    except (OSError,subprocess.SubprocessError):
        raise w.Blocked('RUNTIME_GIT') from None

def checkout_blob(root,path):
    raw=git(root,'rev-parse','HEAD:'+path).decode('ascii').strip()
    need(SHA1.fullmatch(raw),'CHECKOUT_BLOB')
    p.pinned_text(root/path,raw)
    return raw

def observe_checkout(root):
    """Read exact Git identity and pinned checkout bytes; no Git mutation."""
    root=Path(root)
    need(root.is_dir() and not root.is_symlink(),'RUNTIME_ROOT')
    top=Path(os.fsdecode(git(root,'rev-parse','--show-toplevel')).strip()).resolve()
    need(top==root.resolve(),'RUNTIME_ROOT')
    head=git(root,'rev-parse','HEAD').decode('ascii').strip()
    parents=git(root,'show','-s','--format=%P','HEAD').decode('ascii').split()
    need(SHA1.fullmatch(head) and len(parents)==1 and SHA1.fullmatch(parents[0]),'DIRECT_CHILD')
    need(git(root,'status','--porcelain=v1','--untracked-files=all')==b'','DIRTY_CHECKOUT')
    changes=git(root,'diff-tree','--no-commit-id','--name-status','--no-renames','-r','-z','HEAD')
    need(changes==b'A\0'+MARKER.encode('ascii')+b'\0','MARKER_ONLY_DIFF')
    message=git(root,'show','-s','--format=%B','HEAD').decode('utf-8').rstrip('\n')
    for path,pin in RUNTIME_PINS.items():
        need(checkout_blob(root,path)==pin,'SOURCE_PIN')
    for path in m.LEGACY_MARKERS:
        item=root/path
        need(not item.exists() and not item.is_symlink(),'LEGACY_MARKER')
    marker_blob=checkout_blob(root,MARKER)
    marker=p.pinned_text(root/MARKER,marker_blob)
    return {'head':head,'parents':parents,'message':message,'changes':[('A',MARKER)],
            'marker':marker,'marker_blob':marker_blob,'driver_blob':checkout_blob(root,SELF),
            'workflow_blob':checkout_blob(root,WORKFLOW),'legacy_markers_absent':True}

def activation_contract(event, context, checkout, expected, phase, inputs):
    """Pure gate review using separately observed inputs and independent expectation.

    No environment read, Git call, network, file mutation or live capability.
    The independently reviewed future parent/child and source/workflow blobs
    must be fixed before a marker-only push; the current proposal is disarmed.
    """
    need(phase in ('collect-once','retrieve-once'),'GATE_PHASE')
    keys={'parent','head','driver_blob','workflow_blob','inputs'}
    need(type(expected) is dict and set(expected)==keys
         and all(type(expected[k]) is str and SHA1.fullmatch(expected[k])
                 for k in ('parent','head','driver_blob','workflow_blob'))
         and expected['head']!=expected['parent']
         and n.canonical(expected['inputs'])==n.canonical(inputs),'GATE_EXPECTATION')
    need(type(context) is dict and context.get('GITHUB_ACTIONS')=='true'
         and context.get('GITHUB_EVENT_NAME')=='push'
         and context.get('GITHUB_REPOSITORY')==REPO and context.get('GITHUB_REF')==BRANCH
         and context.get('GITHUB_WORKFLOW')==WORKFLOW_NAME
         and context.get('GITHUB_JOB')==phase and context.get('GITHUB_RUN_ATTEMPT')=='1'
         and context.get('C5_APPROVED_ONCE')==OP and context.get('GITHUB_SHA')==expected['head']
         and context.get('C5_DRIVER_BLOB')==expected['driver_blob']
         and context.get('C5_WORKFLOW_BLOB')==expected['workflow_blob']
         and type(context.get('GITHUB_RUN_ID')) is str and RUN.fullmatch(context['GITHUB_RUN_ID']),
         'GATE_CONTEXT')
    need(type(event) is dict and event.get('ref')==BRANCH and event.get('before')==expected['parent']
         and event.get('after')==expected['head'] and event.get('forced') is False
         and event.get('created') is False and event.get('deleted') is False
         and type(event.get('repository')) is dict and event['repository'].get('full_name')==REPO
         and type(event.get('head_commit')) is dict and event['head_commit'].get('id')==expected['head']
         and event['head_commit'].get('message')==MESSAGE,'GATE_EVENT')
    need(type(checkout) is dict and checkout.get('head')==expected['head']
         and checkout.get('parents')==[expected['parent']] and checkout.get('message')==MESSAGE
         and checkout.get('changes')==[('A',MARKER)] and checkout.get('marker')==marker_bytes(expected['inputs'])
         and checkout.get('driver_blob')==expected['driver_blob']
         and checkout.get('workflow_blob')==expected['workflow_blob']
         and checkout.get('marker_blob')==git_blob(marker_bytes(expected['inputs']))
         and checkout.get('legacy_markers_absent') is True,'GATE_CHECKOUT')
    return {'scope':TRANSFER_SCOPE,'run':context['GITHUB_RUN_ID'],'phase':phase,
            'source_sha':expected['head'],'inputs_sha256':w.sha(n.canonical(expected['inputs']))}


def review_fixture_checkout(root,event_path,context,expected,phase):
    """Observe Git and bounded event in a disposable fixture; no live claim."""
    need(type(context) is dict and type(context.get('GITHUB_WORKSPACE')) is str
         and Path(context['GITHUB_WORKSPACE']).resolve()==Path(root).resolve(),'RUNTIME_CONTEXT')
    event_path=Path(event_path)
    raw=a.read_bounded(event_path,EVENT_CAP)
    try:
        event=json.loads(raw,object_pairs_hook=n.unique)
    except (UnicodeError,json.JSONDecodeError,RecursionError):
        raise w.Blocked('RUNTIME_EVENT') from None
    return activation_contract(event,context,observe_checkout(root),expected,phase,input_identity())

def fixture_claim(parent,root,event_path,context,expected,phase):
    claim=review_fixture_checkout(root,event_path,context,expected,phase)
    parent=Path(parent)
    need(parent.is_dir() and not parent.is_symlink(),'CLAIM_SCOPE')
    dest=parent/('runtime-fixture-'+claim['run']+'-'+phase+'.claim')
    try:
        with dest.open('xb') as out:
            raw=n.canonical(claim)
            need(out.write(raw)==len(raw),'CLAIM_WRITE')
            out.flush()
            os.fsync(out.fileno())
    except FileExistsError:
        raise w.Blocked('ONE_USE_CLAIM_CONSUMED') from None
    a.sync_dir(parent)
    return claim

def authorize(*args,**kwargs):
    # No env variable, marker or fixture claim may enable this revision.
    raise w.Blocked('FRESH_APPROVAL_REQUIRED')

def produce():
    authorize()

def retrieve():
    authorize()

class _MemoryConnection:
    """Inert HTTPS-like connection; no sockets or DNS."""
    def __init__(self,factory,host,port,timeout,context):
        self.factory=factory
        need(host==a.HOST and port==443 and timeout==a.REQUEST_TIMEOUT
             and context.check_hostname and context.verify_mode==ssl.CERT_REQUIRED,'TLS_POLICY')
        self.url=None
        self.closed=False
        factory.connections.append(self)
    def request(self,method,path,headers):
        need(not self.closed and self.url is None and method=='GET'
             and headers==h.request_parts({'url':'https://'+a.HOST+path,
                                            'filename':path.rsplit('/',1)[-1]})[3],'REQUEST_SCOPE')
        self.url='https://'+a.HOST+path
        self.factory.requests.append(self.url)
    def getresponse(self):
        need(self.url is not None and self.url in self.factory.responses,'TRANSPORT_ERROR')
        raw=self.factory.responses[self.url]
        if type(raw) is not bytes:
            raise OSError('inert connection failure')
        response=http.client.HTTPResponse(a._MemorySocket(raw))
        response.begin()
        return response
    def close(self):
        self.closed=True

class FixtureHTTPS:
    def __init__(self,responses):
        self.responses=dict(responses)
        self.requests=[]
        self.connections=[]
    def __call__(self,host,port,*,timeout,context):
        return _MemoryConnection(self,host,port,timeout,context)

class _OrderedFetch:
    """Consume each exact sequence once before constructing the connection."""
    def __init__(self,rows,factory):
        need(type(factory) is FixtureHTTPS,'OFFLINE_FIXTURE_ONLY')
        self.rows=copy.deepcopy(a.plan_rows(rows))
        self.factory=factory
        self.index=0
        self.closed=False
    def get(self,url):
        need(not self.closed and self.index<len(self.rows),'TRANSPORT_STOPPED')
        row=self.rows[self.index]
        if url!=a.exact_url(row):
            self.closed=True
            raise w.Blocked('URL_SCOPE')
        self.index+=1
        try:
            response=h._request(row,self.factory)
            if response.status!=200:
                self.closed=True
            return response
        except BaseException:
            self.closed=True
            raise

def collect_fixture(rows,plan_blob,factory,parent,*,bindings,caps):
    rows,bindings,caps,_=c.prepare(rows,plan_blob,bindings,caps,c.FIXTURE_SCOPE)
    need(len(rows)<=63,'REMAINING_COUNT')
    fetch=_OrderedFetch(rows,factory)
    try:
        return c._collect(rows,plan_blob,bindings,caps,c.FIXTURE_SCOPE,fetch.get,nullcontext,parent)
    finally:
        fetch.closed=True

def settlement(path,manifest,manifest_sha,rows):
    count=manifest['attempted_count']
    last=a.parse(a.read_bounded(Path(path)/f'request-{count:03d}-result.json',a.MAX_RECORD))
    return {'manifest_sha256':manifest_sha,'status':manifest['status'],
            'expected_count':manifest['expected_count'],'attempted_count':count,
            'verified_count':manifest['verified_count'],'received_bytes':manifest['received_bytes'],
            'missing':manifest['missing'],'policy_sha256':manifest['policy_sha256'],
            'caps':manifest['caps'],'accepted_totals':manifest['accepted_totals'],
            'last_filename':rows[count-1]['filename'],'last_result':last,
            'license_reviewed':False,'production_ready':False}

def produce_fixture(rows,plan_blob,factory,parent,run,source,*,bindings,caps):
    path,sha=collect_fixture(rows,plan_blob,factory,parent,bindings=bindings,caps=caps)
    manifest=m.verify_generation(path,sha,rows,plan_blob,bindings=bindings,caps=caps)
    bundle,ident=m.export_generation(path,sha,rows,plan_blob,parent,bindings=bindings,caps=caps)
    record=m.artifact_record(run,source,ident,rows,plan_blob,bindings=bindings,caps=caps)
    return bundle,record,settlement(path,manifest,sha,rows)

def retrieve_fixture(raw,meta,record,expected,run,source,artifact_id,upload_sha,
                     rows,plan_blob,parent,*,bindings,caps):
    path,manifest=m.replay_artifact(raw,meta,record,run,source,artifact_id,upload_sha,
                                   rows,plan_blob,parent,bindings=bindings,caps=caps)
    observed=settlement(path,manifest,record['bundle']['manifest_sha256'],rows)
    need(type(expected) is dict and n.canonical(observed)==n.canonical(expected),
         'PRODUCER_VERIFIER_SETTLEMENT')
    return observed
