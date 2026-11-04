import {test,expect} from '@playwright/test';
import type {BrowserContext,Route,APIRequestContext,Page} from '@playwright/test';
import {Buffer} from 'node:buffer';
import {startDisposableBackend,stopDisposableBackend} from './p1-real-http-backend';
import type {DisposableBackend} from './p1-real-http-backend';

// One independent, generated project; never the A/B recovery fixtures or owner data.
// The browser is allowed only bounded v0->v1->v2->v3 review/commit traffic.
const API='http://127.0.0.1:8000';
const UI='http://127.0.0.1:5178';
const C_FILENAME='pilotodin_p1_http_approval_C.csv';
const source=[
  'OrderID,Segment,Amount',
  ...Array.from({length:24},(_,i)=>
    'C'+String(i+1).padStart(4,'0')+','+
    (i===2?' North ':i%2===0?'North':'South')+','+(i+1)*7),
].join('\n')+'\n';
type Proposal={operation:'approve'|'undo'|'restore';expected_version:number;issue_id?:string;action_id?:string;target_version?:number};
type Receipt={proposal_id:string;proposal_hash:string;project_id:string;expected_version:number;changed_cells:number;operation:string};
type Audit={proposals:Proposal[];commits:{proposal_id:string;proposal_hash:string}[];unexpectedReads:string[];blockedWrites:string[];blockedOrigins:string[]};
function samePayload(a:unknown,b:unknown):boolean{
  if(!a||!b||typeof a!=='object'||typeof b!=='object'||Array.isArray(a)||Array.isArray(b))return false;
  const x=a as Record<string,unknown>,y=b as Record<string,unknown>;
  return Object.keys(x).sort().join('|')===Object.keys(y).sort().join('|')&&
    Object.keys(x).every(k=>x[k]===y[k]);
}
async function limitBrowserToSyntheticConsent(context:BrowserContext,pid:string){
  const audit:Audit={proposals:[],commits:[],unexpectedReads:[],blockedWrites:[],blockedOrigins:[]};
  let nextProposal:Proposal|null=null;
  let nextReceipt:{proposal_id:string;proposal_hash:string}|null=null;
  await context.route('**/*',async(route:Route)=>{
    const request=route.request(),url=new URL(request.url()),method=request.method();
    if(url.origin===UI){
      if(method==='GET'||method==='HEAD'){await route.continue();return;}
      audit.blockedWrites.push(method+' '+url.pathname+' [UI]');
      await route.fulfill({status:403,json:{detail:'UI writes blocked'}});return;
    }
    const families=url.searchParams.getAll('family');
    if(method==='GET'&&url.origin==='https://fonts.googleapis.com'&&url.pathname==='/css2'
      &&families.length===2
      &&families[0]==='Inter:wght@400;450;500;550;600;650;700;750;800'
      &&families[1]==='Manrope:wght@500;600;650;700;750;800'
      &&url.searchParams.get('display')==='swap'
      &&[...url.searchParams.keys()].length===3){
      await route.fulfill({status:200,contentType:'text/css',body:'/* isolated system fonts */'});return;
    }
    if(url.origin!==API||!url.pathname.startsWith('/api/')){
      audit.blockedOrigins.push(method+' '+url.origin+url.pathname);
      await route.abort('blockedbyclient');return;
    }
    const path=url.pathname.slice(4);
    const read=path==='/projects'||path==='/ai/settings'||new RegExp(
      '^/projects/'+pid+'(?:/(?:live-profile|quality|quality/history|quality/preview|preparation|features|target-opportunities))?$'
    ).test(path);
    if(method==='GET'&&read){
      await route.continue();return;
    }
    if(method==='POST'&&url.search===''&&path===`/projects/${pid}/quality/proposals`
      &&nextProposal){
      let body:unknown;
      try{body=JSON.parse(request.postData()??'')}catch{body=null}
      if(samePayload(body,nextProposal)){
        audit.proposals.push(nextProposal);nextProposal=null;
        await route.continue();return;
      }
    }
    if(method==='POST'&&url.search===''&&path===`/projects/${pid}/quality/commit`
      &&nextReceipt){
      let body:unknown;
      try{body=JSON.parse(request.postData()??'')}catch{body=null}
      if(samePayload(body,nextReceipt)){
        audit.commits.push(nextReceipt);nextReceipt=null;
        await route.continue();return;
      }
    }
    if(method==='GET'){
      audit.unexpectedReads.push(path);
      await route.fulfill({status:404,json:{detail:'Unreviewed GET refused'}});return;
    }
    audit.blockedWrites.push(method+' '+path);
    await route.fulfill({status:403,json:{detail:'Unreviewed write refused'}});
  });
  return {
    audit,
    allowProposal:(proposal:Proposal)=>{if(nextProposal||nextReceipt)throw Error('Previous browser consent capability unused');nextProposal=proposal;},
    allowCommit:(receipt:Receipt)=>{if(nextProposal||nextReceipt)throw Error('Unexpected pending consent capability');
      if(receipt.project_id!==pid||!/^([a-f0-9]{32,64})$/.test(receipt.proposal_id)
        ||!/^[a-f0-9]{64}$/.test(receipt.proposal_hash)||receipt.changed_cells!==1)
        throw Error('Untrusted receipt identity, project or changed-cell count');
      nextReceipt={proposal_id:receipt.proposal_id,proposal_hash:receipt.proposal_hash};
    },
    outstanding:()=>({proposal:nextProposal,receipt:nextReceipt}),
  };
}
async function history(request:APIRequestContext,pid:string){
  const response=await request.get(`${API}/api/projects/${pid}/quality/history`);
  expect(response.status()).toBe(200);
  return response.json();
}
async function preview(request:APIRequestContext,pid:string,version:number){
  const response=await request.get(`${API}/api/projects/${pid}/quality/preview?offset=0&limit=10&expected_version=${version}`);
  expect(response.status()).toBe(200);
  return response.json();
}
async function reviewedProposal(page:Page,pid:string,click:()=>Promise<void>,expected:Proposal){
  const wait=page.waitForResponse(response=>response.request().method()==='POST'
    &&response.url()===`${API}/api/projects/${pid}/quality/proposals`);
  await click();
  const response=await wait;
  expect(response.status()).toBe(200);
  const receipt=await response.json() as Receipt;
  expect(receipt.operation).toBe(expected.operation);
  expect(receipt.expected_version).toBe(expected.expected_version);
  expect(receipt.changed_cells).toBe(1);
  return receipt;
}
let owned:DisposableBackend|null=null;
test.beforeEach(async()=>{owned=await startDisposableBackend()});
test.afterEach(async()=>{if(owned){const old=owned;owned=null;await stopDisposableBackend(old)}});

test('real HTTP Quality approval, keyboard consent, undo, restore and restart preserve synthetic original',async({page,context,request})=>{
  if(process.env.CI!=='true'||process.env.P1_REAL_HTTP_E2E!=='1')
    throw Error('Refuse non-isolated Quality write acceptance');
  // Seed an exact disposable source via the request fixture, outside the browser
  // interception. All browser writes below are project, operation and receipt scoped.
  expect((await request.get(API+'/api/projects')).status()).toBe(200);
  const seed=await request.post(API+'/api/projects',{multipart:{
    file:{name:C_FILENAME,mimeType:'text/csv',buffer:Buffer.from(source)}
  }});
  expect(seed.status()).toBe(201);
  const pid=(await seed.json()).id as string;
  expect(pid).toMatch(/^[a-f0-9]{32}$/);
  const c=await request.get(API+'/api/projects/'+pid+'/quality');
  expect(c.status()).toBe(200);
  const q0=await c.json() as {project_id:string;version:number;issues:{id:string;kind:string;column:string|null}[]};
  expect(q0.project_id).toBe(pid);expect(q0.version).toBe(0);
  const candidate=q0.issues.find(x=>x.kind==='whitespace'&&x.column==='Segment');
  expect(candidate).toBeDefined();
  const issueId=candidate!.id;
  const baseline=await preview(request,pid,0);
  expect(baseline.rows[2].original.Segment).toBe(' North ');
  expect(baseline.rows[2].working.Segment).toBe(' North ');
  expect((await history(request,pid)).actions).toEqual([]);

  const gate=await limitBrowserToSyntheticConsent(context,pid);
  await page.addInitScript((id:string)=>{
    localStorage.setItem('pilotodin-current',id);
    localStorage.setItem('pilotodin-workspace-tabs-v1-'+id,JSON.stringify(['overview','quality']));
  },pid);
  await page.goto('/#/studio/overview');
  await expect(page.getByRole('combobox',{name:'Switch project'})).toHaveValue(pid);
  await page.getByRole('navigation',{name:'Workspace navigation'}).getByRole('button',{name:'Quality'}).click();
  const primary=page.locator('.po-primary-pane');
  await expect(primary.getByText('WORKING VERSION 0',{exact:true})).toBeVisible();
  const finding=primary.locator('.quality-issue').filter({hasText:'Surrounding whitespace'})
    .filter({hasText:'Segment'});
  await finding.click();
  const review=primary.getByRole('button',{name:'Review this correction'});
  const dialog=primary.getByRole('dialog',{name:'Review exact dataset change'});
  const toApprove:Proposal={operation:'approve',expected_version:0,issue_id:issueId};
  gate.allowProposal(toApprove);
  await reviewedProposal(page,pid,()=>review.click(),toApprove);
  await expect(dialog).toBeVisible();
  const cancel=dialog.getByRole('button',{name:'Cancel approval'});
  const approve=dialog.getByRole('button',{name:'Approve these changes'});
  await expect(cancel).toBeFocused();
  await approve.focus();
  await page.keyboard.press('Tab');
  await expect(cancel).toBeFocused();
  await page.keyboard.press('Shift+Tab');
  await expect(approve).toBeFocused();
  await page.keyboard.press('Escape');
  await expect(dialog).toHaveCount(0);
  await expect(review).toBeFocused();
  expect((await history(request,pid)).current_version).toBe(0);
  expect(gate.audit.commits).toHaveLength(0);

  // Reopen explicit consent. Only this second verified receipt can mutate v0.
  gate.allowProposal(toApprove);
  const approvedReceipt=await reviewedProposal(page,pid,()=>review.click(),toApprove);
  gate.allowCommit(approvedReceipt);
  await expect(dialog).toBeVisible();
  await expect(dialog).toContainText('Working version: v0');
  const committed=page.waitForResponse(response=>response.request().method()==='POST'
    &&response.url()===`${API}/api/projects/${pid}/quality/commit`);
  await dialog.getByRole('button',{name:'Approve these changes'}).click();
  expect((await committed).status()).toBe(200);
  await expect(primary.getByText('WORKING VERSION 1',{exact:true})).toBeVisible();
  const v1=await preview(request,pid,1);
  expect(v1.rows[2].original.Segment).toBe(' North ');
  expect(v1.rows[2].working.Segment).toBe('North');
  const h1=await history(request,pid);
  expect(h1.current_version).toBe(1);
  expect(h1.actions).toHaveLength(1);
  expect(h1.actions[0]).toMatchObject({kind:'trim_whitespace',active:true,affected_rows:1});
  const actionId=h1.actions[0].id as string;

  // Replay is always refused by the real backend; no second version is created.
  const replay=await request.post(`${API}/api/projects/${pid}/quality/commit`,{
    data:{proposal_id:approvedReceipt.proposal_id,proposal_hash:approvedReceipt.proposal_hash}
  });
  expect(replay.status()).toBe(409);
  expect((await history(request,pid)).current_version).toBe(1);

  // Undo and restore through the mounted Quality UI, never a direct blind write.
  await primary.getByRole('button',{name:'History'}).click();
  const undo:Proposal={operation:'undo',expected_version:1,action_id:actionId};
  gate.allowProposal(undo);
  const undoReceipt=await reviewedProposal(page,pid,
    ()=>primary.getByRole('button',{name:'Undo'}).click(),undo);
  gate.allowCommit(undoReceipt);
  await expect(dialog).toContainText('Working version: v1');
  const undoCommit=page.waitForResponse(r=>r.request().method()==='POST'
    &&r.url()===`${API}/api/projects/${pid}/quality/commit`);
  await dialog.getByRole('button',{name:'Approve these changes'}).click();
  expect((await undoCommit).status()).toBe(200);
  await expect(primary.getByText('WORKING VERSION 2',{exact:true})).toBeVisible();
  const v2=await preview(request,pid,2);
  expect(v2.rows[2].working.Segment).toBe(' North ');
  const h2=await history(request,pid);
  expect(h2.current_version).toBe(2);
  expect(h2.actions[0].active).toBe(false);

  const restore:Proposal={operation:'restore',expected_version:2,target_version:1};
  gate.allowProposal(restore);
  const restoredReceipt=await reviewedProposal(page,pid,
    ()=>primary.locator('.history-entry').filter({hasText:'Version 1'})
      .getByRole('button',{name:'Restore'}).click(),restore);
  gate.allowCommit(restoredReceipt);
  await expect(dialog).toContainText('Working version: v2');
  const restoreCommit=page.waitForResponse(r=>r.request().method()==='POST'
    &&r.url()===`${API}/api/projects/${pid}/quality/commit`);
  await dialog.getByRole('button',{name:'Approve these changes'}).click();
  expect((await restoreCommit).status()).toBe(200);
  await expect(primary.getByText('WORKING VERSION 3',{exact:true})).toBeVisible();
  const v3=await preview(request,pid,3);
  expect(v3.rows[2].original.Segment).toBe(' North ');
  expect(v3.rows[2].working.Segment).toBe('North');
  const h3=await history(request,pid);
  expect(h3.current_version).toBe(3);
  expect(h3.versions.map((x:{version:number;event:string})=>[x.version,x.event])).toEqual([
    [0,'original'],[1,'apply'],[2,'undo'],[3,'restore']
  ]);
  expect(h3.actions).toHaveLength(1);
  expect(h3.actions[0].active).toBe(true);
  expect(gate.audit.proposals.map(p=>p.operation)).toEqual(['approve','approve','undo','restore']);
  expect(gate.audit.commits).toHaveLength(3);
  expect(gate.audit.blockedWrites).toEqual([]);
  expect(gate.audit.unexpectedReads).toEqual([]);
  expect(gate.audit.blockedOrigins).toEqual([]);
  expect(gate.outstanding()).toEqual({proposal:null,receipt:null});

  // A new actual backend process must recover the approval log and each immutable
  // version. Restart only the child owned by this disposable test.
  if(!owned)throw Error('Missing owned backend process');
  const prior=owned;await stopDisposableBackend(prior);owned=null;
  owned=await startDisposableBackend();
  expect(owned.pid).not.toBe(prior.pid);
  const h4=await history(request,pid);
  expect(h4).toEqual(h3);
  const after=await preview(request,pid,3);
  expect(after.rows[2].original.Segment).toBe(' North ');
  expect(after.rows[2].working.Segment).toBe('North');
  const v0=await request.get(`${API}/api/projects/${pid}/quality/preview?offset=0&limit=10&expected_version=0`);
  expect(v0.status()).toBe(409); // Preview protects the active working version.
  const qRestart=await request.get(`${API}/api/projects/${pid}/quality`);
  expect(qRestart.status()).toBe(200);
  expect((await qRestart.json()).version).toBe(3);
});
