"""Disarmed preservation of the five previously replayed notice documents.

The approved future operation may retrieve only the original receipt ZIP.
No wheel requests, installation, execution, or artifact upload. Publication
of the five exact canonical evidence documents requires explicit authority.
"""
from __future__ import annotations
import base64
import binascii
import io
import json
import os
from pathlib import Path
import sys
import tempfile
from contextlib import nullcontext
import zipfile

ARMED=False
ROOT=Path(__file__).resolve().parents[2]
DIR='qa/c5_wheel_metadata/'
SELF=DIR+'wheel_prior_notice_preservation.py'
WORKFLOW='.github/workflows/c5-wheel-prior-notice-preservation.yml'
OP='C5-PRIOR-NOTICE-PRESERVATION-ONCE-20261126'
MESSAGE=OP+' owner approved five prior notice documents only'
MARKER=DIR+'APPROVAL_WHEEL_PRIOR_NOTICE_PRESERVATION_20261126.txt'
MARKER_BYTES=(OP+'\nArtifact 15076022558; 20475 ZIP bytes; five evidence documents only; no wheels or retries.\n').encode('ascii')
DIAGNOSIS_PIN='4cb3a27f3879d64637a5c239cc253fb0de0e077b'
DIAGNOSIS_RECORD_PIN='1dd2627eafba1f4695f972c1d23fac68340d05ee'
PRESERVED=DIR+'wheel_prior_notice_preservation_45729307962.json'
CAP=32768
EVIDENCE_BYTES=10909
NOTICE_BYTES=5241


def need(ok,reason):
    if not ok: raise ValueError(reason)


def modules():
    sys.path.insert(0,str(ROOT/DIR))
    import wheel_receipt_diagnosis as q
    d,mods,historic=q.modules()
    a,w,h,n,g,t=mods
    need(not q.ARMED and d.git_blob(d.read_file(ROOT/(DIR+'wheel_receipt_diagnosis.py')))==DIAGNOSIS_PIN,
         'DIAGNOSIS_PIN')
    prior=n.pinned_json(ROOT/(DIR+'wheel_receipt_diagnosis_45753813079.json'),DIAGNOSIS_RECORD_PIN)
    need(prior['status']=='REPLAY_PASS' and prior['settlement']==historic['settlement']
         and prior['identity']==historic['identity'] and prior['zip_sha256']==q.ZIP_SHA
         and prior['artifact_id']==q.ARTIFACT and len(prior['records'])==6
         and prior['records'][-1]['result']['status']=='REFUSED','DIAGNOSIS_IDENTITY')
    rows=a.plan_rows(n.load_pinned_rows())
    need(len(rows)==68,'PLAN_COUNTS')
    return q,d,mods,historic,prior,rows


def authorize(d, n):
    need(ARMED is True,'FRESH_APPROVAL_REQUIRED')
    e=os.environ
    need(e.get('GITHUB_ACTIONS')=='true' and e.get('GITHUB_EVENT_NAME')=='push'
         and e.get('GITHUB_REPOSITORY')==d.REPO and e.get('GITHUB_REF')=='refs/heads/feature/live-dev-workspace-20261023'
         and e.get('GITHUB_WORKFLOW')=='C5 prior notice preservation once'
         and e.get('GITHUB_JOB')=='preserve-notices' and e.get('GITHUB_RUN_ATTEMPT')=='1'
         and e.get('GITHUB_WORKSPACE')==str(ROOT) and e.get('C5_APPROVED_ONCE')==OP
         and d.RUN.fullmatch(e.get('GITHUB_RUN_ID','')) and d.SHA1.fullmatch(e.get('C5_DRIVER_BLOB','')),
         'PRESERVATION_CONTEXT')
    head=d.git(ROOT,'rev-parse','HEAD').decode().strip()
    parents=d.git(ROOT,'show','-s','--format=%P','HEAD').decode().split()
    event=json.loads(d.read_file(Path(e['GITHUB_EVENT_PATH'])),object_pairs_hook=n.unique)
    need(len(parents)==1 and head==e['GITHUB_SHA']==event.get('after')
         and parents[0]==event.get('before') and event.get('ref')==e['GITHUB_REF']
         and event.get('forced') is False and event.get('created') is False and event.get('deleted') is False
         and event.get('repository',{}).get('full_name')==d.REPO
         and event.get('head_commit',{}).get('id')==head
         and event.get('head_commit',{}).get('message')==MESSAGE,'PRESERVATION_EVENT')
    need(d.git(ROOT,'diff-tree','--no-commit-id','--name-status','--no-renames','-r','HEAD')
         ==('A\t'+MARKER+'\n').encode('ascii')
         and d.git(ROOT,'show','-s','--format=%B','HEAD').decode().rstrip('\n')==MESSAGE
         and d.read_file(ROOT/MARKER,1024)==MARKER_BYTES,'PRESERVATION_MARKER')
    for path in (SELF,WORKFLOW,MARKER):
        blob=d.git_blob(d.read_file(ROOT/path))
        need(blob==d.git(ROOT,'rev-parse','HEAD:'+path).decode().strip(),'CHECKOUT_PIN')
        if path==SELF: need(blob==e['C5_DRIVER_BLOB'],'SELF_PIN')
    runner=Path(e['RUNNER_TEMP'])
    need(runner.is_dir() and not runner.is_symlink(),'RUNNER_TEMP')
    with (runner/('c5-preservation-'+e['GITHUB_RUN_ID']+'.claim')).open('xb') as f:
        f.write(MARKER_BYTES); f.flush(); os.fsync(f.fileno())
    return runner



def collect_documents(dest,m,rows,prior,plan,mods):
    a,w,h,n,g,t=mods
    need(m['status']=='BLOCKED' and m['verified_count']==len(prior)
         and m['attempted_count']==len(prior)+1,'PRIOR_COUNTS')
    files={x['name']:x for x in m['files']}
    out=[]
    for i,(row,entry) in enumerate(zip(rows,prior),1):
        name=f'wheel-{i:03d}-evidence.json'
        need(entry['filename']==row['filename'] and entry['result']['status']=='VERIFIED'
             and entry['result']['evidence']==name,'PRIOR_IDENTITY')
        raw=a.read_bounded(dest/name,CAP)
        need(a.file_identity(name,raw)==files[name]
             and len(raw)==entry['evidence_bytes'] and w.sha(raw)==entry['evidence_sha256'],'PRIOR_HASH')
        receipt=n.verify_evidence(raw,entry['evidence_sha256'],row,plan)
        need(receipt==entry['inspection_receipt'],'PRIOR_RECEIPT')
        out.append({'filename':row['filename'],'bytes':len(raw),'sha256':w.sha(raw),
                    'evidence_base64':base64.b64encode(raw).decode('ascii')})
    return out


def verify_documents(documents,rows,prior,plan,mods):
    a,w,h,n,g,t=mods
    need(type(documents) is list and len(documents)==len(prior),'DOCUMENT_COUNT')
    evidence_bytes=notice_bytes=0
    for record,row,entry in zip(documents,rows,prior):
        need(type(record) is dict and set(record)=={'filename','bytes','sha256','evidence_base64'}
             and record['filename']==row['filename']==entry['filename']
             and type(record['bytes']) is int and record['bytes']==entry['evidence_bytes']
             and record['sha256']==entry['evidence_sha256'],'DOCUMENT_IDENTITY')
        val=record['evidence_base64']
        need(type(val) is str and len(val)==4*((record['bytes']+2)//3) and len(val)<=CAP,'DOCUMENT_LENGTH')
        try:
            raw=base64.b64decode(val,validate=True)
        except (ValueError,binascii.Error):
            raise ValueError('DOCUMENT_ENCODING') from None
        need(base64.b64encode(raw).decode('ascii')==val and len(raw)==record['bytes'],'DOCUMENT_ENCODING')
        receipt=n.verify_evidence(raw,record['sha256'],row,plan)
        need(receipt==entry['inspection_receipt'],'DOCUMENT_RECEIPT')
        evidence_bytes+=len(raw)
        notice_bytes+=receipt['notice_bytes']
    return evidence_bytes,notice_bytes


def envelope(documents,q,mods,rows,prior):
    a,w,h,n,g,t=mods
    totals=verify_documents(documents,rows[:5],prior['records'][:5],n.PLAN_BLOB,mods)
    need(totals==(EVIDENCE_BYTES,NOTICE_BYTES),'PRESERVATION_TOTALS')
    return {'schema_version':1,'scope':'PRIOR_NOTICE_EVIDENCE_ONLY','artifact_id':q.ARTIFACT,
            'original_run':q.RUN,'original_source':q.SOURCE,'zip_sha256':q.ZIP_SHA,
            'diagnosis_blob':DIAGNOSIS_RECORD_PIN,'documents':documents,
            'evidence_bytes':EVIDENCE_BYTES,'notice_bytes':NOTICE_BYTES,
            'license_reviewed':False,'production_ready':False}


def verify_preserved():
    q,d,mods,historic,prior,rows=modules()
    a,w,h,n,g,t=mods
    raw=a.read_bounded(ROOT/PRESERVED,CAP)
    data=json.loads(raw,object_pairs_hook=n.unique)
    need(raw==n.canonical(data) and data==envelope(data['documents'],q,mods,rows,prior),
         'PRESERVED_IDENTITY')
    print('C5_PRIOR_NOTICE_PERSISTED '+json.dumps({'status':'PASS','documents':5,'evidence_bytes':EVIDENCE_BYTES,
          'notice_bytes':NOTICE_BYTES,'sha256':w.sha(raw),'license_reviewed':False},sort_keys=True),flush=True)


def retrieve():
    need(ARMED,'FRESH_APPROVAL_REQUIRED')
    q,d,mods,historic,prior,rows=modules()
    a,w,h,n,g,t=mods
    runner=authorize(d,n)
    raw,meta=q.download(mods,historic['identity'],os.environ['GH_TOKEN'])
    with tempfile.TemporaryDirectory(dir=runner) as tmp:
        dest,m=g.replay_artifact(raw,meta,historic['identity'],q.RUN,q.SOURCE,rows,n.PLAN_BLOB,Path(tmp),scope=a.HOSTED_SCOPE)
        need(d.summary(m)==historic['settlement'],'HISTORICAL_SETTLEMENT')
        documents=collect_documents(dest,m,rows[:5],prior['records'][:5],n.PLAN_BLOB,mods)
        data=envelope(documents,q,mods,rows,prior)
        encoded=n.canonical(data)
        need(len(encoded)<=CAP,'PRESERVATION_CAP')
        # Only exact verified canonical documents, encoded to avoid arbitrary
        # control characters, paths, secrets or log workflow commands.
        for i,item in enumerate(documents,1):
            print('C5_PRIOR_NOTICE_DOCUMENT '+json.dumps({'sequence':i,**item},sort_keys=True),flush=True)
        print('C5_PRIOR_NOTICE_RESULT '+json.dumps({'status':'REPLAY_PASS','documents':5,
              'evidence_bytes':EVIDENCE_BYTES,'notice_bytes':NOTICE_BYTES,'envelope_bytes':len(encoded),
              'envelope_sha256':w.sha(encoded),'artifact_id':q.ARTIFACT,'retrievals':1,'wheel_requests':0,
              'license_reviewed':False},sort_keys=True),flush=True)


if __name__=='__main__':
    if not ARMED and sys.argv[1:]==['--retrieve']:
        raise SystemExit('FRESH_APPROVAL_REQUIRED: prior notice preservation disabled')
    try:
        if sys.argv[1:]==['--retrieve']: retrieve()
        elif sys.argv[1:]==['--verify-preserved']: verify_preserved()
        else: raise ValueError('COMMAND_REFUSED')
    except Exception as exc:
        print('C5_PRIOR_NOTICE_REFUSAL '+type(exc).__name__,flush=True)
        raise SystemExit(2)
