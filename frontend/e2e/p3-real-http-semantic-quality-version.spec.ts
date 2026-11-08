import {test,expect} from '@playwright/test';
import type {BrowserContext,Route} from '@playwright/test';
import {Buffer} from 'node:buffer';
import {startDisposableBackend,stopDisposableBackend} from './p1-real-http-backend';
import type {DisposableBackend} from './p1-real-http-backend';

// P3-04 W5 precursor: actual browser approval and fresh Your data semantics.
// Runs ONLY in trusted CI with the already audited disposable Uvicorn owner.
// This is NOT an owner native Tauri WebView2 test or a release acceptance.
const API='http://127.0.0.1:8000';
const UI='http://127.0.0.1:5178';
const DOMAIN='Synthetic claim records, owner-described for version zero';
const GRAIN='One synthetic submitted insurance claim per data row';
const MEANING='Synthetic requested insurance claim amount, owner-described';
const SOURCE=[
 'claim_id,claim_amount,policy_number,Region',
 ...Array.from({length:36},(_,i)=>
  'W5'+String(i+1).padStart(3,'0')+','+String(100+i)+',P'+String(i%4)+','+
  (i===1||i===2?' Mpumalanga ':i%2===0?'Mpumalanga':'Gauteng'))
].join('\n')+'\n';

type Receipt={
 project_id:string;operation:string;expected_version:number;
 proposal_id:string;proposal_hash:string;changed_cells:number;
};
type Audit={proposals:number;commits:number;blocked:string[];remote:string[]};

async function scopeBrowser(context:BrowserContext,pid:string,issueId:string){
 const audit:Audit={proposals:0,commits:0,blocked:[],remote:[]};
 let approvedReceipt:Receipt|null=null;
 let permitCommit=false;
 await context.route('**/*',async(route:Route)=>{
  const r=route.request(),url=new URL(r.url()),method=r.method();
  if(url.origin===UI){
   if(method==='GET'||method==='HEAD'){await route.continue();return;}
   audit.blocked.push('UI '+method);await route.fulfill({status:403,json:{detail:'Blocked UI write'}});return;
  }
  if(method==='GET'&&url.origin==='https://fonts.googleapis.com'&&url.pathname==='/css2'){
   await route.fulfill({status:200,contentType:'text/css',body:'/* CI local font stub */'});return;
  }
  if(url.origin!==API||!url.pathname.startsWith('/api/')){
   audit.remote.push(method+' '+url.origin);await route.abort('blockedbyclient');return;
  }
  const p=url.pathname.slice(4);
  const base='/projects/'+pid;
  const simpleRead=method==='GET'&&url.search===''&&[
   '/projects','/ai/settings',base,base+'/live-profile',base+'/columns/overview',
   base+'/quality',base+'/quality/history',base+'/quality/preview',
  ].includes(p);
  const previewRead=method==='GET'&&p===base+'/quality/preview'&&
   [...url.searchParams.keys()].every(k=>['offset','limit','expected_version','issue_id'].includes(k))&&
   (url.searchParams.get('expected_version')===null||
    ['0','1'].includes(url.searchParams.get('expected_version')??''))&&
   (url.searchParams.get('issue_id')===null||url.searchParams.get('issue_id')===issueId);
  const semanticsRead=method==='GET'&&p===base+'/semantics'&&
   [...url.searchParams.keys()].length===1&&
   ['0','1'].includes(url.searchParams.get('expected_version')??'');
  const ownerReviewRead=method==='GET'&&p===base+'/semantic-reviews'&&
   [...url.searchParams.keys()].length===1&&
   ['0','1'].includes(url.searchParams.get('expected_version')??'');
  const detailRead=method==='GET'&&p===base+'/columns/detail'&&
   [...url.searchParams.keys()].sort().join(',')==='expected_version,name'&&
   ['0','1'].includes(url.searchParams.get('expected_version')??'')&&
   ['claim_id','claim_amount','policy_number','Region'].includes(url.searchParams.get('name')??'');
  if(simpleRead||previewRead||semanticsRead||ownerReviewRead||detailRead){
   await route.continue();return;
  }
  if(method==='POST'&&url.search===''&&p===base+'/quality/proposals'&&audit.proposals===0){
   let body:unknown;
   try{body=r.postDataJSON()}catch{body=null}
   const data=body as Record<string,unknown>|null;
   if(data&&!Array.isArray(data)&&Object.keys(data).sort().join(',')==='expected_version,issue_id,operation'&&
      data.operation==='approve'&&data.expected_version===0&&data.issue_id===issueId){
    audit.proposals++;await route.continue();return;
   }
  }
  if(method==='POST'&&url.search===''&&p===base+'/quality/commit'&&permitCommit&&
     approvedReceipt&&audit.commits===0){
   let body:unknown;
   try{body=r.postDataJSON()}catch{body=null}
   const data=body as Record<string,unknown>|null;
   if(data&&Object.keys(data).sort().join(',')==='proposal_hash,proposal_id'&&
      data.proposal_hash===approvedReceipt.proposal_hash&&
      data.proposal_id===approvedReceipt.proposal_id){
    audit.commits++;permitCommit=false;await route.continue();return;
   }
  }
  audit.blocked.push(method+' '+p+url.search);
  await route.fulfill({status:403,json:{detail:'Unreviewed synthetic W5 browser operation refused'}});
 });
 return {
  audit,
  allowReviewedReceipt:(receipt:Receipt)=>{
   if(audit.proposals!==1||approvedReceipt!==null||permitCommit||
      receipt.project_id!==pid||receipt.operation!=='approve'||
      receipt.expected_version!==0||receipt.changed_cells!==2||
      !/^[a-f0-9]{32,64}$/.test(receipt.proposal_id)||
      !/^[a-f0-9]{64}$/.test(receipt.proposal_hash))
    throw Error('Unreviewed receipt cannot authorise W5 Quality commit');
   approvedReceipt=receipt;permitCommit=true;
  },
  noPending:()=>!permitCommit,
 };
}

let owned:DisposableBackend|null=null;
test.beforeEach(async()=>{owned=await startDisposableBackend()});
test.afterEach(async()=>{if(owned){const old=owned;owned=null;await stopDisposableBackend(old)}});

test('P3 W5: actual Quality UI approval advances v0 to v1 without inheriting saved semantic notes',
 async({page,context,request})=>{
  if(process.env.CI!=='true'||process.env.GITHUB_ACTIONS!=='true'||
     process.env.P1_REAL_HTTP_E2E!=='1'||!process.env.PILOTODIN_HOME)
   throw Error('W5 test requires trusted CI disposable workspace');

  // The sole dataset is a generated 36-row CSV, imported only into test HOME.
  const imported=await request.post(API+'/api/projects',{multipart:{
   file:{name:'p3_w5_disposable_only.csv',mimeType:'text/csv',buffer:Buffer.from(SOURCE)},
  }});
  expect(imported.status(),await imported.text()).toBe(201);
  const pid=(await imported.json()).id as string;
  expect(pid).toMatch(/^[a-f0-9]{32}$/);
  const q0r=await request.get(API+'/api/projects/'+pid+'/quality');
  expect(q0r.status()).toBe(200);
  const q0=await q0r.json() as {
   version:number;issues:{id:string;kind:string;column:string|null}[];
  };
  expect(q0.version).toBe(0);
  const issue=q0.issues.find(i=>i.kind==='whitespace'&&i.column==='Region');
  expect(issue).toBeDefined();
  const issueId=issue!.id;

  // Prepare bounded owner-described v0 metadata. No arbitrary mutation is
  // permitted from the browser until the human reviews the exact Quality fix.
  const note=await request.post(API+'/api/projects/'+pid+'/semantic-business-context',{
   data:{expected_version:0,domain_description:DOMAIN,
    record_grain_description:GRAIN,
    field_definitions:[{column:'claim_amount',meaning:MEANING}]},
  });
  expect(note.status(),await note.text()).toBe(200);
  const initialSem=await request.get(API+'/api/projects/'+pid+'/semantics?expected_version=0');
  expect(initialSem.status()).toBe(200);
  const origin=await initialSem.json();
  expect(origin.user_context.domain_description).toBe(DOMAIN);

  const guard=await scopeBrowser(context,pid,issueId);
  await page.addInitScript((id:string)=>{
   localStorage.setItem('pilotodin-current',id);
   localStorage.setItem('pilotodin-workspace-tabs-v1-'+id,JSON.stringify(['understand','quality']));
   localStorage.setItem('pilotodin-workspace-active-v1-'+id,'understand');
  },pid);
  await page.goto('/#/studio/understand');
  const semantic=page.getByRole('region',{name:'Business context hypotheses'});
  await expect(semantic.getByRole('region',{name:'Owner-described business context'}))
   .toContainText(DOMAIN);
  await expect(semantic.getByText('UNVERIFIED',{exact:true})).toBeVisible();

  // The real Quality interface requests a specific reviewed receipt.
  await page.getByRole('navigation',{name:'Workspace navigation'})
   .getByRole('button',{name:'Quality'}).click();
  const pane=page.locator('.po-primary-pane');
  await expect(pane.getByText('WORKING VERSION 0',{exact:true})).toBeVisible();
  const finding=pane.locator('.quality-issue')
   .filter({hasText:'Surrounding whitespace'}).filter({hasText:'Region'});
  await finding.click();
  const proposalResponse=page.waitForResponse(r=>r.request().method()==='POST'&&
   r.url()===API+'/api/projects/'+pid+'/quality/proposals');
  await pane.getByRole('button',{name:'Review this correction'}).click();
  const received=await proposalResponse;
  expect(received.status(),await received.text()).toBe(200);
  const receipt=await received.json() as Receipt;
  const modal=pane.getByRole('dialog',{name:'Review exact dataset change'});
  await expect(modal).toContainText('Working version: v0');
  await expect(modal).toContainText('Region');
  guard.allowReviewedReceipt(receipt);

  const commitResponse=page.waitForResponse(r=>r.request().method()==='POST'&&
   r.url()===API+'/api/projects/'+pid+'/quality/commit');
  await modal.getByRole('button',{name:'Approve these changes'}).click();
  const committed=await commitResponse;
  expect(committed.status(),await committed.text()).toBe(200);
  expect((await committed.json()).version).toBe(1);
  await expect(pane.getByText('WORKING VERSION 1',{exact:true})).toBeVisible();

  // The currently approved version changed, and neither UI nor API may
  // silently treat version-zero human notes as belonging to version one.
  await page.getByRole('navigation',{name:'Workspace navigation'})
   .getByRole('button',{name:'Your data'}).click();
  await expect(page.getByRole('region',{name:'Data dictionary and field investigation'}))
   .toContainText('WORKING VERSION 1');
  await expect(semantic.getByText('Optional: describe what this dataset means')).toBeVisible();
  await expect(semantic.getByRole('region',{name:'Owner-described business context'})).toHaveCount(0);
  await expect(semantic.getByText(DOMAIN)).toHaveCount(0);
  const v1=await request.get(API+'/api/projects/'+pid+'/semantics?expected_version=1');
  expect(v1.status(),await v1.text()).toBe(200);
  const now=await v1.json();
  expect(now.user_context).toBeNull();
  expect(now.version).toBe(1);
  const staleRead=await request.get(API+'/api/projects/'+pid+'/semantics?expected_version=0');
  expect(staleRead.status()).toBe(409);
  const staleWrite=await request.post(API+'/api/projects/'+pid+'/semantic-business-context',{
   data:{expected_version:0,domain_description:'Do not migrate stale semantic notes'},
  });
  expect(staleWrite.status()).toBe(409);

  // Actual original source bytes remain unchanged. The approved correction
  // lives in the Quality working version and requires explicit consent.
  const originalPreview=await request.get(
   API+'/api/projects/'+pid+'/quality/preview?offset=0&limit=10&expected_version=1');
  expect(originalPreview.status()).toBe(200);
  const rows=(await originalPreview.json()).rows as
   {original:{Region:string};working:{Region:string}}[];
  expect(rows[1].original.Region).toBe(' Mpumalanga ');
  expect(rows[1].working.Region).toBe('Mpumalanga');
  const history=await request.get(API+'/api/projects/'+pid+'/quality/history');
  expect(history.status()).toBe(200);
  const recorded=await history.json();
  expect(recorded.current_version).toBe(1);
  expect(recorded.versions.map((v:{version:number})=>v.version)).toEqual([0,1]);
  expect(guard.audit).toEqual({proposals:1,commits:1,blocked:[],remote:[]});
  expect(guard.noPending()).toBe(true);
 });
