"""C5 actual-wheel acquisition driver. Disarmed by default.

A reviewed arm commit and a separate exact marker-only child are necessary.
Only receipts/notices may be uploaded; wheels stay disposable and unexecuted.
The separate verifier consumes only the exact artifact from the producing job.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import ssl
import subprocess
import sys
import tempfile
from urllib.error import HTTPError
from urllib.parse import urlsplit
from urllib.request import build_opener, HTTPSHandler, ProxyHandler

ARMED=False
ROOT=Path(__file__).resolve().parents[2]
DIR='qa/c5_wheel_metadata/'
SELF=DIR+'wheel_acquisition_driver.py'
WORKFLOW_PATH='.github/workflows/c5-wheel-hosted-one-use.yml'
REPO='Sonkhe-Shongwe/PilotODIN'
OP='C5-WHEEL-HOSTED-ONCE-20261126'
MESSAGE=OP+' owner approved exact wheel acquisition'
MARKER=DIR+'APPROVAL_WHEEL_HOSTED_20261126.txt'
MARKER_BYTES=(OP+'\n68 exact wheel GETs; 225699980 body bytes; zero redirects or retries.\n').encode('ascii')
PINS={
    'wheel_archive_inspector.py':'aa5ab610d711fb8f9bc1fce1020c4999e53f3571',
    'wheel_notice_evidence.py':'141f069706d0c597214829eea90a48197c381e2c',
    'wheel_acquisition_offline.py':'dc3f8ed48517ff796980ae766a4d4613c1471ef5',
    'wheel_hosted_proposal.py':'7d49568ebbcdf6209688973ab2a49a905d2125b7',
    'review_input_proposals.py':'092b806e11badc9ad8d559cf1a2d1660ef95de07',
    'wheel_acquisition_plan_20261125.json':'1aa96a7172508f94b2cdc4b7aabd65e3b8f21f89',
    'platform_lock_candidates_45703125465.json':'6b27407f4b24942c385179bb253f692370f21df7',
    'production_graph_receipt_45705552265.json':'70cdac979b732aadfad0c51d7e159a60840cc1ef',
    'wheel_one_use_review.py':'5d42c9201a6c36b4b3a2f6467ce28dec4a717dd8',
    'synthetic_receipt_transfer.py':'9dd872b7b1d9caf4b930ff4fcc115fef27f3281d',
    'collect_remaining_checksums.py':'5f65d13d657ea2455e9fcc8239b68eacb4c53d43',
    'test_wheel_acquisition_offline.py':'63c3ed987e8884cb4cd0b8b1ce71d14489233930',
    'test_wheel_archive_inspector.py':'58bd7724e2e47307e90bdfe6fb17864203d804dc',
}
SHA1=re.compile(r'[0-9a-f]{40}')
RUN=re.compile(r'[1-9][0-9]{0,19}')
MAX_BUNDLE=68550656
MAX_ZIP=69599232


class Refused(ValueError): pass


def need(ok,reason):
    if not ok: raise Refused(reason)


def read_file(path,cap=2*1024*1024):
    need(path.is_file() and not path.is_symlink(),'SOURCE_PATH')
    with path.open('rb') as f: raw=f.read(cap+1)
    need(0<len(raw)<=cap,'SOURCE_SIZE')
    return raw


def git_blob(raw):
    return hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()


def verify_sources(root=None):
    root=ROOT if root is None else root
    for name,pin in PINS.items():
        raw=read_file(root/DIR/name)
        need(git_blob(raw)==pin,'SOURCE_PIN')
    return True


def git(root,*args):
    # Fixed read-only Git commands, no fetch or shell. The checkout is owned CI.
    return subprocess.run(['git','--no-replace-objects','-C',str(root),*args],
                          check=True,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,
                          timeout=10).stdout


def checkout_identity(root):
    head=git(root,'rev-parse','HEAD').decode('ascii').strip()
    parents=git(root,'show','-s','--format=%P','HEAD').decode('ascii').split()
    need(len(parents)==1 and SHA1.fullmatch(head) and SHA1.fullmatch(parents[0]),'DIRECT_CHILD')
    changes=git(root,'diff-tree','--no-commit-id','--name-status','--no-renames','-r','HEAD')
    need(changes==('A\t'+MARKER+'\n').encode('ascii'),'MARKER_ONLY_DIFF')
    msg=git(root,'show','-s','--format=%B','HEAD').decode('utf-8').rstrip('\n')
    need(msg==MESSAGE,'ACTIVATION_MESSAGE')
    marker=read_file(root/MARKER,1024)
    need(marker==MARKER_BYTES,'MARKER_BYTES')
    need(git(root,'rev-parse','HEAD:'+MARKER).decode('ascii').strip()==git_blob(marker),'MARKER_CHECKOUT')
    return head,parents[0],msg,marker


def claim(root,run,phase):
    need(root.is_dir() and not root.is_symlink() and RUN.fullmatch(run)
         and phase in ('collect-once','retrieve-once'),'CLAIM_SCOPE')
    p=root/('pilotodin-c5-wheel-'+run+'-'+phase+'.claim')
    try:
        with p.open('xb') as f:
            f.write((OP+'\n'+run+'\n'+phase+'\n').encode('ascii'))
            f.flush(); os.fsync(f.fileno())
    except FileExistsError:
        raise Refused('ONE_USE_CLAIM_CONSUMED') from None


def load_modules():
    sys.path.insert(0,str(ROOT/DIR))
    import wheel_acquisition_offline as a
    import wheel_archive_inspector as w
    import wheel_hosted_proposal as h
    import wheel_notice_evidence as n
    import wheel_one_use_review as g
    import synthetic_receipt_transfer as t
    return a,w,h,n,g,t


def authorize(phase):
    need(ARMED is True,'FRESH_APPROVAL_REQUIRED')
    e=os.environ
    need(e.get('GITHUB_REPOSITORY')==REPO and e.get('GITHUB_JOB')==phase
         and e.get('GITHUB_WORKSPACE')==str(ROOT)
         and RUN.fullmatch(e.get('GITHUB_RUN_ID',''))
         and SHA1.fullmatch(e.get('C5_DRIVER_BLOB','')),'DRIVER_CONTEXT')
    verify_sources()
    self_raw=read_file(ROOT/SELF)
    need(git_blob(self_raw)==e['C5_DRIVER_BLOB']
         and git(ROOT,'rev-parse','HEAD:'+SELF).decode('ascii').strip()==e['C5_DRIVER_BLOB'],
         'DRIVER_PIN')
    # Workflow must be the tracked file from the exact marker-only child.
    wf=read_file(ROOT/WORKFLOW_PATH)
    need(git_blob(wf)==git(ROOT,'rev-parse','HEAD:'+WORKFLOW_PATH).decode('ascii').strip(),
         'WORKFLOW_CHECKOUT')
    head,parent,msg,marker=checkout_identity(ROOT)
    a,w,h,n,g,t=load_modules()
    event=json.loads(read_file(Path(e['GITHUB_EVENT_PATH'])),object_pairs_hook=n.unique)
    need(event.get('repository',{}).get('full_name')==REPO
         and event.get('head_commit',{}).get('id')==head
         and event.get('head_commit',{}).get('message')==msg,'EVENT_IDENTITY')
    g.activation_contract(event,e,head=head,parent=parent,changes=[('A',MARKER)],
                          message=msg,marker=marker)
    need(h.LIVE_ENABLED is False and a.LIVE_ENABLED is False and g.ENABLED is False
         and t.ENABLED is False,'EXCLUSIVE_ARM')
    rows=a.plan_rows(n.load_pinned_rows())
    need(len(rows)==68 and sum(x['bytes'] for x in rows)==225699980,'PLAN_COUNTS')
    need(h.MAX_BUNDLE==MAX_BUNDLE and g.MAX_ZIP==MAX_ZIP,'TRANSFER_CAPS')
    runner=Path(e['RUNNER_TEMP'])
    claim(runner,e['GITHUB_RUN_ID'],phase)
    return a,w,h,n,g,t,rows,runner,e['GITHUB_RUN_ID'],head


def summary(manifest):
    return {k:manifest[k] for k in ('status','expected_count','attempted_count',
             'verified_count','received_bytes','missing','license_reviewed','production_ready')}


def prepare_receipt(path,manifest_sha,rows,plan,runner,run,sha,mods):
    a,w,h,n,g,t=mods
    manifest=a.verify_generation(path,manifest_sha,rows,plan,scope=a.HOSTED_SCOPE)
    bundle,ident=h.export_generation(path,manifest_sha,rows,plan,runner,scope=a.HOSTED_SCOPE)
    need(bundle.name=='receipts.odin' and ident['bytes']<=MAX_BUNDLE,'BUNDLE_SCOPE')
    return bundle,g.identity(run,sha,ident),summary(manifest)


def collect_after_authorization(adapter):
    # Only the exact driver calls this private seam after authorize and claim.
    # The adapter source never arms on disk; restore even on abnormal refusal.
    need(adapter.LIVE_ENABLED is False,'ADAPTER_ALREADY_ENABLED')
    adapter.LIVE_ENABLED=True
    try:
        return adapter.collect()
    finally:
        adapter.LIVE_ENABLED=False


def produce():
    a,w,h,n,g,t,rows,runner,run,sha=authorize('collect-once')
    path,manifest_sha=collect_after_authorization(h)
    bundle,record,settlement=prepare_receipt(path,manifest_sha,rows,n.PLAN_BLOB,runner,
                                            run,sha,(a,w,h,n,g,t))
    print('C5_WHEEL_PRODUCER '+json.dumps({'identity':record,'settlement':settlement},sort_keys=True),flush=True)
    # Expected partial/refused settlements are uploaded too; verifier decides
    # terminal success. Unexpected interruption has no terminal manifest.
    with open(os.environ['GITHUB_OUTPUT'],'a',encoding='utf-8') as out:
        out.write('receipt_bundle='+str(bundle)+'\nrecord='+json.dumps(record,separators=(',',':'))+'\n'
                  +'settlement='+json.dumps(settlement,separators=(',',':'))+'\n')


def download_exact(record,run,sha,artifact_id,upload_digest,token,opener,mods):
    a,w,h,n,g,t=mods
    g.verify_identity(record,run,sha)
    need(g.RUN.fullmatch(artifact_id) and n.digest(upload_digest),'UPLOAD_OUTPUT')
    need(bool(token),'ARTIFACT_TOKEN')
    url='https://api.github.com/repos/'+REPO+'/actions/artifacts/'+artifact_id
    # Read exactly the associated artifact metadata; never enumerate other artifacts.
    with t.deadline():
        with opener.open(t.get_request(url,token),timeout=15) as resp:
            meta=json.loads(t.read_metadata(resp),object_pairs_hook=n.unique)
    ident=g.verify_artifact_metadata(meta,record,run,sha)
    need(str(ident['id'])==artifact_id and ident['sha256']==upload_digest
         and ident['bytes']<=69599232,'ARTIFACT_UPLOAD_IDENTITY')
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
                raw=t.read_response(storage,69599232,exact=ident['bytes'])
        else:
            with resp:
                raw=t.read_response(resp,69599232,exact=ident['bytes'])
    return raw,meta


def replay_transfer(raw,meta,record,run,sha,rows,plan,runner,expected,mods):
    a,w,h,n,g,t=mods
    _,manifest=g.replay_artifact(raw,meta,record,run,sha,rows,plan,runner,scope=a.HOSTED_SCOPE)
    actual=summary(manifest)
    need(actual==expected,'PRODUCER_VERIFIER_SETTLEMENT')
    need(actual['license_reviewed'] is False and actual['production_ready'] is False,
         'CANDIDATE_ONLY')
    return actual


def retrieve():
    a,w,h,n,g,t,rows,runner,run,sha=authorize('retrieve-once')
    mods=(a,w,h,n,g,t)
    record=json.loads(os.environ['C5_BUNDLE_RECORD'],object_pairs_hook=n.unique)
    expected=json.loads(os.environ['C5_PRODUCER_SETTLEMENT'],object_pairs_hook=n.unique)
    artifact_id=os.environ['C5_ARTIFACT_ID']
    upload_digest=os.environ['C5_UPLOAD_DIGEST'].removeprefix('sha256:')
    opener=build_opener(ProxyHandler({}),t.NoRedirect(),HTTPSHandler(context=ssl.create_default_context()))
    raw,meta=download_exact(record,run,sha,artifact_id,upload_digest,os.environ['GH_TOKEN'],opener,mods)
    with tempfile.TemporaryDirectory(dir=runner) as d:
        settlement=replay_transfer(raw,meta,record,run,sha,rows,n.PLAN_BLOB,Path(d),expected,mods)
    print('C5_WHEEL_VERIFIER '+json.dumps({'status':'REPLAY_PASS','run_id':run,'source_sha':sha,
          'artifact_id':artifact_id,'zip_bytes':len(raw),'zip_sha256':w.sha(raw),
          'identity':record,'settlement':settlement,'retrievals':1},sort_keys=True),flush=True)
    return 0 if settlement['status']=='CANDIDATE_EVIDENCE_RECORDED' and settlement['verified_count']==68 else 2


if __name__=='__main__':
    if not ARMED:
        print('C5_WHEEL_DRIVER_REFUSAL FRESH_APPROVAL_REQUIRED',flush=True)
        raise SystemExit(2)
    try:
        if sys.argv[1:]==['--collect']: produce()
        elif sys.argv[1:]==['--retrieve']: raise SystemExit(retrieve())
        else: raise Refused('COMMAND_REFUSED')
    except Refused as exc:
        print('C5_WHEEL_DRIVER_REFUSAL '+str(exc),flush=True)
        raise SystemExit(2)
    except (OSError,ValueError,KeyError,HTTPError,subprocess.SubprocessError):
        # Never log exception strings that could contain signed URLs or tokens.
        print('C5_WHEEL_DRIVER_REFUSAL TRANSPORT_OR_EVIDENCE_REFUSED',flush=True)
        raise SystemExit(2)
