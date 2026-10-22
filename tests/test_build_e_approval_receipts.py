"""New production mutation gate: no direct writes, exact version-bound receipt."""
import os,sys,tempfile
from pathlib import Path
os.environ.setdefault('PILOTODIN_HOME',tempfile.mkdtemp(prefix='pilotodin-approval-'))
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import pandas as pd
import pytest
from fastapi.testclient import TestClient
from backend.main import app
from backend import quality,storage

client=TestClient(app)

def make_project():
    n=36
    df=pd.DataFrame({'OrderID':[f'00{i:03}' for i in range(n)],
                     'Region':['Gauteng']*18 + [' Gauteng ']*3 + ['Mpumalanga']*15,
                     'Revenue':[float(i*10+10) for i in range(n-1)]+[None]})
    data=df.to_csv(index=False).encode()
    r=client.post('/api/projects',files={'file':('a.csv',data,'text/csv')})
    assert r.status_code==201,r.text
    return r.json()['id'],data

def propose(pid,operation,expected_version,**kwargs):
    return client.post(f'/api/projects/{pid}/quality/proposals',json={'operation':operation,'expected_version':expected_version,**kwargs})

def commit(pid,proposal):
    return client.post(f'/api/projects/{pid}/quality/commit',json={k:proposal[k] for k in ('proposal_id','proposal_hash')})

def test_old_endpoints_fail_closed_without_explicit_receipts():
    pid,_=make_project()
    issue=next(i for i in quality.snapshot(pid)['issues'] if i['proposal'])
    endpoints=[('/autopilot',{'expected_version':0}),('/decisions',{'expected_version':0,'issue_id':issue['id'],'decision':'approve'}),
               ('/impute',{'expected_version':0,'issue_id':issue['id'],'column':'Revenue'}),
               ('/undo',{'expected_version':0,'action_id':'x'}),('/restore',{'expected_version':0,'target_version':0})]
    for part,payload in endpoints:
        response=client.post(f'/api/projects/{pid}/quality{part}',json=payload)
        assert response.status_code==428,(part,response.text)
    assert quality.current_version(pid)==0


def test_explicit_review_commit_and_replay_rejected():
    pid,raw=make_project()
    issue=next(i for i in quality.snapshot(pid)['issues'] if i['kind']=='whitespace')
    proposal=propose(pid,'approve',0,issue_id=issue['id'])
    assert proposal.status_code==200,proposal.text
    proposal=proposal.json()
    assert proposal['changed_cells']>0 and proposal['preview']
    assert quality.current_version(pid)==0
    approved=commit(pid,proposal)
    assert approved.status_code==200,approved.text
    assert approved.json()['version']==1 and approved.json()['approved']
    assert commit(pid,proposal).status_code==409
    assert Path(storage.get_project(pid)['dataset_path']).read_bytes()==raw
    assert quality.current_version(pid)==1


def test_proposal_is_rejected_on_stale_version_without_consumption():
    pid,_=make_project()
    issue=next(i for i in quality.snapshot(pid)['issues'] if i['kind']=='whitespace')
    receipt=propose(pid,'approve',0,issue_id=issue['id']).json()
    # Simulate an independent user-initiated dataset-version change.
    quality.restore(pid,0,0)
    assert commit(pid,receipt).status_code==409
    assert quality.current_version(pid)==1


def test_project_isolation_and_forged_digest():
    pid,_=make_project(); other,_=make_project()
    issue=next(i for i in quality.snapshot(pid)['issues'] if i['kind']=='whitespace')
    rec=propose(pid,'approve',0,issue_id=issue['id']).json()
    assert commit(other,rec).status_code==403
    assert client.post(f'/api/projects/{pid}/quality/commit',json={
        'proposal_id':rec['proposal_id'],'proposal_hash':'0'*64}).status_code==403
    assert commit(pid,rec).status_code==200


def test_undo_and_restore_also_require_explicit_review():
    pid,_=make_project()
    issue=next(i for i in quality.snapshot(pid)['issues'] if i['kind']=='whitespace')
    action=commit(pid,propose(pid,'approve',0,issue_id=issue['id']).json()).json()['applied'][0]['id']
    undo=propose(pid,'undo',1,action_id=action)
    assert undo.status_code==200,undo.text
    res=commit(pid,undo.json())
    assert res.status_code==200,res.text
    assert res.json()['version']==2
    restore=propose(pid,'restore',2,target_version=1)
    assert restore.status_code==200,restore.text
    assert commit(pid,restore.json()).json()['version']==3


def test_median_imputation_approval_preserves_original():
    pid,original=make_project()
    issue=next(i for i in quality.snapshot(pid)['issues'] if i['kind']=='missing' and i['column']=='Revenue')
    prop=propose(pid,'impute',0,issue_id=issue['id'],column='Revenue')
    assert prop.status_code==200,prop.text
    body=prop.json()
    assert body['steps'][0]['proposal']['kind']=='impute_numeric_median'
    assert quality.current_version(pid)==0
    assert commit(pid,body).json()['version']==1
    assert quality.current_data(pid)[0]['Revenue'].isna().sum()==0
    assert Path(storage.get_project(pid)['dataset_path']).read_bytes()==original


def test_batch_approval_exact_and_no_auto_new_actions():
    pid,_=make_project()
    receipt=propose(pid,'autopilot',0)
    assert receipt.status_code==200,receipt.text
    prop=receipt.json()
    assert all(x['proposal']['kind']=='trim_whitespace' for x in prop['steps'])
    applied=commit(pid,prop)
    assert applied.status_code==200,applied.text
    assert applied.json()['count']==len(prop['steps'])
    assert quality.current_version(pid)==len(prop['steps'])
    assert propose(pid,'autopilot',quality.current_version(pid)).status_code==409


def test_reject_is_nonmodifying_and_remains_available():
    pid,_=make_project()
    issue=next(i for i in quality.snapshot(pid)['issues'] if i['proposal'])
    r=client.post(f'/api/projects/{pid}/quality/decisions',json={'expected_version':0,'issue_id':issue['id'],'decision':'reject'})
    assert r.status_code==200,r.text
    assert quality.current_version(pid)==0
