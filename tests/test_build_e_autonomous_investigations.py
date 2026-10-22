"""Build E real read-only autonomous loop with an explicitly stubbed planner.

No model accuracy claim: these test persistence, tool validation, approvals,
restart recovery, and versioned evidence; live Qwen3 remains unverified.
"""
from pathlib import Path
import threading
import time

import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend import autonomy, investigations, storage, quality

client=TestClient(app)
RAW=b'Region,Revenue,Profit,CustomerSegment\nNorth,100,25,Consumer\nSouth,200,80,\nNorth,300,120,Enterprise\nSouth,400,175,\n'


def new_inv(objective='Compare median Revenue by Region and inspect missing CustomerSegment values.'):
    response=client.post('/api/projects',files={'file':('test_retail.csv',RAW,'text/csv')})
    assert response.status_code==201,response.text
    pid=response.json()['id']
    r=client.post(f'/api/projects/{pid}/investigations',json={'objective':objective})
    assert r.status_code==201,r.text
    return pid,r.json()['id']


def propose(tool='overview',columns=None,intent='run_tool'):
    return {'intent':intent,'tool':tool if intent=='run_tool' else 'none',
            'columns':columns or [],'reason':'A read-only inspection is needed.'}


def await_done(inv_id,timeout=6):
    limit=time.monotonic()+timeout
    while time.monotonic()<limit:
        state=autonomy.for_investigation(inv_id)
        if state and state['status'] not in ('queued','running','waiting_for_resources'):
            return state
        time.sleep(.05)
    raise AssertionError('Worker did not finish')


def test_multiple_real_tools_save_evidence_and_never_touch_original_file():
    pid,inv_id=new_inv()
    raw_path=Path(storage.get_project(pid)['dataset_path'])
    before=raw_path.read_bytes()
    def planner(ctx):
        if len(ctx['verified_evidence'])==0:return propose('compare',['Region','Revenue'])
        if len(ctx['verified_evidence'])==1:return propose('missingness',['CustomerSegment'])
        return propose(intent='suggest_finish')
    initial=autonomy.start(inv_id,planner=planner)
    assert initial['status'] in ('queued','running','waiting_for_resources')
    state=await_done(inv_id)
    assert state['status']=='ready_for_review',state
    assert [s['status'] for s in state['steps']]==['completed','completed','recorded']
    inv=investigations.load(inv_id)
    assert [e['operation'] for e in inv['artifacts']]==['compare','missingness']
    assert {v['label']:v['value'] for v in inv['artifacts'][0]['result']['data']}=={'North':200.0,'South':300.0}
    assert inv['artifacts'][1]['result']['missing_rows']==2
    assert raw_path.read_bytes()==before
    assert all(s['evidence_id'] for s in state['steps'][:2])


def test_receipt_deduplicates_even_after_same_step_retries():
    _,inv_id=new_inv()
    key=storage.uid()+':0'
    first=investigations.run(inv_id,'compare',{'x':'Region','y':'Revenue'},0,execution_key=key)
    second=investigations.run(inv_id,'compare',{'x':'Region','y':'Revenue'},0,execution_key=key)
    assert len(first['artifacts'])==1==len(second['artifacts'])
    with pytest.raises(RuntimeError,match='receipt'):
        investigations.run(inv_id,'missingness',{'column':'Revenue'},0,execution_key=key)


def test_resume_after_disconnection_replays_a_pending_step_once():
    _,inv_id=new_inv()
    starter={'n':0}
    def planner(ctx):
        starter['n']+=1
        if not ctx['verified_evidence']:return propose('overview')
        return propose(intent='suggest_finish')
    # The first step exists but the worker died before writing its evidence.
    with pytest.MonkeyPatch.context() as m:
        # Inject no thread to simulate an interrupted OS process.
        m.setattr(autonomy,'_launch',lambda *a,**k:None)
        first=autonomy.start(inv_id,planner=planner)
    run_id=first['id']
    proposal=propose('overview')
    autonomy._claim_step(run_id,0,proposal)
    autonomy._set(run_id,'interrupted')
    autonomy.resume(inv_id,planner=planner)
    state=await_done(inv_id)
    assert state['status']=='ready_for_review',state
    assert [s['status'] for s in state['steps']]==['completed','recorded']
    assert len(investigations.load(inv_id)['artifacts'])==1


def test_resume_reconciles_existing_receipt_without_duplicate():
    _,inv_id=new_inv()
    with pytest.MonkeyPatch.context() as m:
        m.setattr(autonomy,'_launch',lambda *a,**k:None)
        first=autonomy.start(inv_id)
    run_id=first['id']
    sid=autonomy._claim_step(run_id,0,propose('overview'))
    investigations.run(inv_id,'overview',{},0,execution_key=sid)
    autonomy._set(run_id,'interrupted')
    autonomy.resume(inv_id,planner=lambda ctx:propose(intent='suggest_finish'))
    state=await_done(inv_id)
    assert state['status']=='ready_for_review',state
    assert len(investigations.load(inv_id)['artifacts'])==1
    assert state['steps'][0]['evidence_id']==investigations.load(inv_id)['artifacts'][0]['id']


def test_resume_pending_final_step_respects_single_step_budget():
    _,inv_id=new_inv()
    with pytest.MonkeyPatch.context() as m:
        m.setattr(autonomy,'_launch',lambda *a,**k:None)
        first=autonomy.start(inv_id,max_steps=1)
    autonomy._claim_step(first['id'],0,propose('overview'))
    autonomy._set(first['id'],'interrupted')
    autonomy.resume(inv_id,planner=lambda ctx:pytest.fail('Pending step must be recovered, not replanned'))
    state=await_done(inv_id)
    assert state['status']=='needs_review'
    assert len(investigations.load(inv_id)['artifacts'])==1
    assert state['steps'][0]['status']=='completed'


def test_model_cannot_modify_data_with_change_objective():
    _,inv_id=new_inv('Fill missing Revenue values with the median and permanently save it.')
    with pytest.raises(PermissionError):autonomy.start(inv_id,planner=lambda ctx:propose('missingness',['Revenue']))
    assert autonomy.for_investigation(inv_id) is None
    assert investigations.load(inv_id)['artifacts']==[]


def test_model_cannot_invent_tools_or_columns_or_parameters():
    context={'schema':[{'name':'Region','type':'categorical'},{'name':'Revenue','type':'numeric'}]}
    invalid=[propose('execute_python',[]),propose('compare',['Revenue','Region']),
             propose('distribution',['Region']),propose('missingness',['Unknown']),
             {'intent':'suggest_finish','tool':'overview','columns':[],'reason':'done'},
             {'intent':'run_tool','tool':'overview','columns':[],'reason':'okay','execute':'delete all'}]
    for p in invalid:
        with pytest.raises(ValueError):autonomy.validate(p,context)
    assert autonomy.validate(propose('compare',['Region','Revenue']),context)[1]=={'x':'Region','y':'Revenue'}


def test_duplicate_plan_does_not_run_forever():
    _,inv_id=new_inv()
    autonomy.start(inv_id,max_steps=5,planner=lambda ctx:propose('overview'))
    state=await_done(inv_id)
    assert state['status']=='needs_review'
    assert len(investigations.load(inv_id)['artifacts'])==1


def test_changing_dataset_version_stops_the_investigation():
    pid,inv_id=new_inv()
    first=threading.Event();continue_planning=threading.Event()
    def planner(ctx):
        first.set()
        if not continue_planning.wait(5): raise RuntimeError('Test timed out waiting for version change')
        return propose('overview')
    autonomy.start(inv_id,planner=planner)
    assert first.wait(5)
    changed=quality.restore(pid,0,0)
    assert changed['version']==1
    continue_planning.set()
    result=await_done(inv_id)
    assert result['stale']
    assert result['status'] in ('failed','stale')
    assert not investigations.load(inv_id)['artifacts']


def test_no_model_is_a_reported_failure_not_fabricated_evidence():
    _,inv_id=new_inv()
    def unavailable(ctx):raise RuntimeError('Offline model unavailable')
    autonomy.start(inv_id,planner=unavailable)
    result=await_done(inv_id)
    assert result['status']=='failed'
    assert 'unavailable' in result['last_error']
    assert investigations.load(inv_id)['artifacts']==[]


def test_cancel_during_planning_does_not_execute_tools():
    _,inv_id=new_inv()
    entered=threading.Event();unblock=threading.Event()
    def slow(ctx):
        entered.set()
        assert unblock.wait(5)
        return propose('overview')
    autonomy.start(inv_id,planner=slow)
    assert entered.wait(5)
    assert autonomy.cancel(inv_id)['status']=='cancelled'
    unblock.set()
    for _ in range(80):
        if not autonomy._ACTIVE.get(autonomy.for_investigation(inv_id)['id']):break
        time.sleep(.02)
    assert autonomy.for_investigation(inv_id)['status']=='cancelled'
    assert not investigations.load(inv_id)['artifacts']


def test_public_api_endpoints(monkeypatch):
    _,inv_id=new_inv()
    monkeypatch.setattr(autonomy,'default_planner',lambda ctx:propose('overview') if not ctx['verified_evidence'] else propose(intent='suggest_finish'))
    r=client.get(f'/api/investigations/{inv_id}/autonomy')
    assert r.status_code==200 and r.json() is None
    start=client.post(f'/api/investigations/{inv_id}/autonomy/start',json={'max_steps':3})
    assert start.status_code==202,start.text
    assert await_done(inv_id)['status']=='ready_for_review'
    assert client.get(f'/api/investigations/{inv_id}/autonomy').json()['steps'][0]['evidence_id']
    repeat=client.post(f'/api/investigations/{inv_id}/autonomy/start',json={'max_steps':3})
    assert repeat.status_code==409
    bad=client.post(f'/api/investigations/{inv_id}/autonomy/start',json={'max_steps':900})
    assert bad.status_code==422


def test_autonomy_api_requires_authenticated_desktop_session(monkeypatch):
    _,inv_id=new_inv()
    monkeypatch.setenv('PILOTODIN_DESKTOP_SESSION','local-secret-'+'b'*60)
    route=f'/api/investigations/{inv_id}/autonomy'
    assert client.get(route).status_code==401
    assert client.get(route,headers={'Origin':'https://unknown.example',
          'X-PilotODIN-Session':'local-secret-'+'b'*60}).status_code==403
    assert client.get(route,headers={'Origin':'http://tauri.localhost',
          'X-PilotODIN-Session':'local-secret-'+'b'*60}).status_code==200
