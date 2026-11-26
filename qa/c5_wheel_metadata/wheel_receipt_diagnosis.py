"""Exact existing C5 receipt diagnosis. No wheel collection or artifact upload."""
from __future__ import annotations
import io
import json
import os
from pathlib import Path
import ssl
import sys
import tempfile
from contextlib import nullcontext
from urllib.error import HTTPError
from urllib.parse import urlsplit
from urllib.request import build_opener, HTTPSHandler, ProxyHandler
import zipfile

ARMED=True
ROOT=Path(__file__).resolve().parents[2]
DIR='qa/c5_wheel_metadata/'
SELF=DIR+'wheel_receipt_diagnosis.py'
WORKFLOW='.github/workflows/c5-wheel-receipt-diagnosis.yml'
OP='C5-WHEEL-RECEIPT-DIAGNOSIS-ONCE-20261126'
MESSAGE=OP+' owner approved exact receipt retrieval only'
MARKER=DIR+'APPROVAL_WHEEL_RECEIPT_DIAGNOSIS_20261126.txt'
MARKER_BYTES=(OP+'\nArtifact 15076022558 only; 20475 ZIP bytes; no wheels or retries.\n').encode('ascii')
RUN='45729307962'
SOURCE='d66357e3a76d6b05ca3db5fcc0be94f8d17dd269'
ARTIFACT='15076022558'
ZIP_BYTES=20475
ZIP_SHA='efec26dd56725e3cf2619b9002037f37bdf118f98bac6c20c0f970fbbc39bdaf'
RECEIPT=DIR+'wheel_collection_receipt_45729307962.json'
RECEIPT_BLOB='8a742342059075d58570679c2b6ee0211a73892b'
DRIVER_BLOB='e888774ce5cabc5737c413ee47f3da64781443c2'


def need(ok,reason):
    if not ok: raise ValueError(reason)


def modules():
    sys.path.insert(0,str(ROOT/DIR))
    import wheel_acquisition_driver as d
    need(d.git_blob(d.read_file(ROOT/d.SELF))==DRIVER_BLOB,'DRIVER_PIN')
    d.verify_sources()
    a,w,h,n,g,t=d.load_modules()
    need(not d.ARMED and not a.LIVE_ENABLED and not h.LIVE_ENABLED
         and not g.ENABLED and not t.ENABLED,'WHEEL_GATES')
    raw=d.read_file(ROOT/RECEIPT)
    need(d.git_blob(raw)==RECEIPT_BLOB,'HISTORICAL_RECEIPT_PIN')
    historic=json.loads(raw,object_pairs_hook=n.unique)
    v=historic['verifier']; p=historic['producer']
    need(v['status']=='REPLAY_PASS' and v['artifact_id']==ARTIFACT and v['zip_bytes']==ZIP_BYTES
         and v['zip_sha256']==ZIP_SHA and v['identity']==p['identity']
         and v['settlement']==p['settlement'],'HISTORICAL_RECEIPT')
    g.verify_identity(v['identity'],RUN,SOURCE)
    return d,(a,w,h,n,g,t),v


def authorize(d, n):
    need(ARMED is True,'FRESH_APPROVAL_REQUIRED')
    e=os.environ
    need(e.get('GITHUB_ACTIONS')=='true' and e.get('GITHUB_EVENT_NAME')=='push'
         and e.get('GITHUB_REPOSITORY')==d.REPO and e.get('GITHUB_REF')=='refs/heads/feature/live-dev-workspace-20261023'
         and e.get('GITHUB_WORKFLOW')=='C5 wheel receipt diagnosis once'
         and e.get('GITHUB_JOB')=='retrieve-receipt' and e.get('GITHUB_RUN_ATTEMPT')=='1'
         and e.get('GITHUB_WORKSPACE')==str(ROOT) and e.get('C5_APPROVED_ONCE')==OP
         and d.RUN.fullmatch(e.get('GITHUB_RUN_ID','')) and d.SHA1.fullmatch(e.get('C5_DRIVER_BLOB','')),
         'DIAGNOSIS_CONTEXT')
    head=d.git(ROOT,'rev-parse','HEAD').decode().strip()
    parents=d.git(ROOT,'show','-s','--format=%P','HEAD').decode().split()
    event=json.loads(d.read_file(Path(e['GITHUB_EVENT_PATH'])),object_pairs_hook=n.unique)
    need(len(parents)==1 and head==e['GITHUB_SHA']==event.get('after')
         and parents[0]==event.get('before') and event.get('ref')==e['GITHUB_REF']
         and event.get('forced') is False and event.get('created') is False and event.get('deleted') is False
         and event.get('repository',{}).get('full_name')==d.REPO
         and event.get('head_commit',{}).get('id')==head
         and event.get('head_commit',{}).get('message')==MESSAGE,'DIAGNOSIS_EVENT')
    need(d.git(ROOT,'diff-tree','--no-commit-id','--name-status','--no-renames','-r','HEAD')
         ==('A\t'+MARKER+'\n').encode('ascii')
         and d.git(ROOT,'show','-s','--format=%B','HEAD').decode().rstrip('\n')==MESSAGE
         and d.read_file(ROOT/MARKER,1024)==MARKER_BYTES,'DIAGNOSIS_MARKER')
    for path in (SELF,WORKFLOW,MARKER):
        blob=d.git_blob(d.read_file(ROOT/path))
        need(blob==d.git(ROOT,'rev-parse','HEAD:'+path).decode().strip(),'CHECKOUT_PIN')
        if path==SELF: need(blob==e['C5_DRIVER_BLOB'],'SELF_PIN')
    runner=Path(e['RUNNER_TEMP'])
    need(runner.is_dir() and not runner.is_symlink(),'RUNNER_TEMP')
    with (runner/('c5-diagnosis-'+e['GITHUB_RUN_ID']+'.claim')).open('xb') as f:
        f.write(MARKER_BYTES); f.flush(); os.fsync(f.fileno())
    return runner


def inspect_zip(raw,meta,record,run,sha,rows,plan,expected,parent,mods):
    a,w,h,n,g,t=mods
    dest,m=g.replay_artifact(raw,meta,record,run,sha,rows,plan,parent,scope=a.HOSTED_SCOPE)
    actual={k:m[k] for k in expected}
    need(actual==expected and m['status']=='BLOCKED' and m['license_reviewed'] is False
         and m['production_ready'] is False,'SETTLEMENT_MISMATCH')
    filemap={x['name']:x for x in m['files']}
    records=[]
    for i,row in enumerate(rows[:m['attempted_count']],1):
        name=f'request-{i:03d}-result.json'
        result_raw=a.read_bounded(dest/name,a.MAX_RECORD)
        need(a.file_identity(name,result_raw)==filemap[name],'RESULT_HASH')
        result=a.parse(result_raw)
        entry={'filename':row['filename'],'expected_bytes':row['bytes'],
               'expected_sha256':row['sha256'],'result':result}
        if result['status']=='VERIFIED':
            name=result['evidence']
            data=a.read_bounded(dest/name,n.MAX_DOCUMENT)
            receipt=n.verify_evidence(data,filemap[name]['sha256'],row,plan)
            entry['evidence_sha256']=filemap[name]['sha256']
            entry['evidence_bytes']=len(data)
            entry['inspection_receipt']=receipt
        records.append(entry)
    need(len(records)==m['attempted_count'] and records[-1]['result']['status']=='REFUSED',
         'REFUSAL_MISSING')
    return records


def download(mods,record,token):
    a,w,h,n,g,t=mods
    need(bool(token),'ARTIFACT_TOKEN')
    url='https://api.github.com/repos/Sonkhe-Shongwe/PilotODIN/actions/artifacts/'+ARTIFACT
    opener=build_opener(ProxyHandler({}),t.NoRedirect(),HTTPSHandler(context=ssl.create_default_context()))
    with t.deadline():
        with opener.open(t.get_request(url,token),timeout=15) as resp:
            meta=json.loads(t.read_metadata(resp),object_pairs_hook=n.unique)
    ident=g.verify_artifact_metadata(meta,record,RUN,SOURCE)
    need(str(ident['id'])==ARTIFACT and ident['bytes']==ZIP_BYTES and ident['sha256']==ZIP_SHA,
         'EXACT_ARTIFACT_IDENTITY')
    with t.deadline():
        try:
            resp=opener.open(t.get_request(url+'/zip',token),timeout=15)
        except HTTPError as exc:
            try:
                need(exc.code==302,'ARTIFACT_REDIRECT')
                locs=exc.headers.get_all('Location',[])
                need(len(locs)==1 and 0<len(locs[0])<=8192,'ARTIFACT_REDIRECT')
                loc=locs[0]
            finally:
                exc.close()
            u=urlsplit(loc)
            need(u.scheme=='https' and u.hostname and u.netloc==u.hostname
                 and u.hostname.endswith(('.blob.core.windows.net','.actions.githubusercontent.com','.githubusercontent.com'))
                 and u.path.startswith('/') and not u.fragment and bool(u.query),'ARTIFACT_REDIRECT_ORIGIN')
            with opener.open(t.get_request(loc),timeout=15) as resp:
                raw=t.read_response(resp,ZIP_BYTES,exact=ZIP_BYTES)
        else:
            with resp:
                raw=t.read_response(resp,ZIP_BYTES,exact=ZIP_BYTES)
    need(w.sha(raw)==ZIP_SHA,'ZIP_DIGEST')
    return raw,meta


def self_test():
    d,mods,historic=modules()
    a,w,h,n,g,t=mods
    from test_wheel_acquisition_offline import candidate, wire
    raw,row=candidate()
    raw2,row2=candidate(build=2)
    rows=[row,row2]
    with tempfile.TemporaryDirectory() as tmp:
        parent=Path(tmp)
        replay=a.Replay({row['url']:wire(raw),row2['url']:wire(raw2,status=503)})
        p,sha=a._run_core(rows,'fixture-plan',replay.get,parent,nullcontext,a.HOSTED_SCOPE)
        bundle,ident=h.export_generation(p,sha,rows,'fixture-plan',parent,scope=a.HOSTED_SCOPE)
        record=g.identity('12345','1'*40,ident)
        stream=io.BytesIO()
        with zipfile.ZipFile(stream,'w',compression=zipfile.ZIP_STORED) as z:
            z.writestr('receipts.odin',bundle.read_bytes())
        data=stream.getvalue()
        meta={'id':123,'name':record['artifact_name'],'expired':False,'size_in_bytes':len(data),
              'digest':'sha256:'+w.sha(data),'workflow_run':{'id':12345,'head_sha':'1'*40,
              'head_branch':h.BRANCH.removeprefix('refs/heads/')}}
        expected=d.summary(a.verify_generation(p,sha,rows,'fixture-plan',scope=a.HOSTED_SCOPE))
        records=inspect_zip(data,meta,record,'12345','1'*40,rows,'fixture-plan',expected,parent,mods)
        need(len(records)==2 and records[0]['result']['status']=='VERIFIED'
             and records[1]['result']['reason']=='HTTP_STATUS'
             and 'notice_payloads' not in json.dumps(records),'FIXTURE_RESULT')
    need(not ARMED,'DISARM')
    print('C5_RECEIPT_DIAGNOSIS_SELF_TEST PASS: historical source pins and blocked synthetic ZIP replay; no network',flush=True)


def retrieve():
    need(ARMED is True,'FRESH_APPROVAL_REQUIRED')
    d,mods,historic=modules()
    a,w,h,n,g,t=mods
    runner=authorize(d,n)
    rows=a.plan_rows(n.load_pinned_rows())
    need(len(rows)==68,'PLAN_COUNTS')
    raw,meta=download(mods,historic['identity'],os.environ['GH_TOKEN'])
    with tempfile.TemporaryDirectory(dir=runner) as tmp:
        records=inspect_zip(raw,meta,historic['identity'],RUN,SOURCE,rows,n.PLAN_BLOB,
                            historic['settlement'],Path(tmp),mods)
    need(len(records)==6 and sum(x['result']['status']=='VERIFIED' for x in records)==5,
         'HISTORICAL_COUNTS')
    print('C5_RECEIPT_DIAGNOSIS '+json.dumps({'artifact_id':ARTIFACT,'original_run':RUN,
          'original_source':SOURCE,'zip_bytes':ZIP_BYTES,'zip_sha256':ZIP_SHA,
          'identity':historic['identity'],'settlement':historic['settlement'],
          'records':records,'status':'REPLAY_PASS','retrievals':1,'wheel_requests':0,
          'notice_payloads_republished':False},sort_keys=True),flush=True)


if __name__=='__main__':
    try:
        if sys.argv[1:]==['--self-test']: self_test()
        elif sys.argv[1:]==['--retrieve']:
            if not ARMED:
                print('C5_RECEIPT_DIAGNOSIS_REFUSAL FRESH_APPROVAL_REQUIRED',flush=True)
                raise SystemExit(2)
            retrieve()
        else: raise ValueError('COMMAND_REFUSED')
    except Exception as exc:
        # No arbitrary exception strings: signed storage URLs must never leak.
        print('C5_RECEIPT_DIAGNOSIS_REFUSAL '+type(exc).__name__,flush=True)
        raise SystemExit(2)
