import {test,expect} from '@playwright/test';
import type {BrowserContext,Route} from '@playwright/test';
import {Buffer} from 'node:buffer';
import {startDisposableBackend,stopDisposableBackend} from './p1-real-http-backend';
import type {DisposableBackend} from './p1-real-http-backend';

// Scope: explicit human opinion about one *unverified* field role, never
// automated truth, data modification, target selection, or actual owner data.
const API='http://127.0.0.1:8000';
const UI='http://127.0.0.1:5178';
const source=(prefix:string)=>[
 'claim_id,claim_amount,policy_number',
 ...Array.from({length:20},(_,i)=>
  prefix+String(i+1).padStart(3,'0')+','+String(100+i)+',P'+String(i%4))
].join('\n')+'\n';

type BrowserAudit={posts:number;blocked:string[];remote:string[]};

async function guard(context:BrowserContext,one:string,two:string):Promise<BrowserAudit>{
 const audit:BrowserAudit={posts:0,blocked:[],remote:[]};
 await context.route('**/*',async(route:Route)=>{
  const req=route.request(),url=new URL(req.url()),method=req.method();
  if(url.origin===UI){
   if(method==='GET'||method==='HEAD'){await route.continue();return;}
   audit.blocked.push('UI '+method);await route.abort('blockedbyclient');return;
  }
  if(method==='GET'&&url.origin==='https://fonts.googleapis.com'&&url.pathname==='/css2'){
   await route.fulfill({status:200,contentType:'text/css',body:'/* synthetic CI stub */'});return;
  }
  if(url.origin!==API||!url.pathname.startsWith('/api/')){
   audit.remote.push(method+' '+url.origin);await route.abort('blockedbyclient');return;
  }
  const path=url.pathname.slice(4);
  const known=[one,two].some(id=>path===`/projects/${id}`||path.startsWith(`/projects/${id}/`));
  if(method==='GET'&&
     (known||['/projects','/ai/settings'].includes(path))){
   await route.continue();return;
  }
  if(method==='POST'&&path===`/projects/${one}/semantic-reviews`&&
     url.search===''&&audit.posts<2){
   let payload:Record<string,unknown>|null=null;
   try{payload=req.postDataJSON() as Record<string,unknown>}catch{}
   if(payload&&Object.keys(payload).sort().join(',')===
       'column,decision,expected_revision,expected_version,explanation,hypothesis_hash,role'&&
      payload.column==='claim_amount'&&
      payload.role==='possible_monetary_measure'&&
      payload.expected_version===0&&
      typeof payload.hypothesis_hash==='string'&&
      /^[a-f0-9]{64}$/.test(payload.hypothesis_hash)&&
      ((audit.posts===0&&payload.decision==='acceptable'&&payload.expected_revision===0)||
       (audit.posts===1&&payload.decision==='needs_correction'&&payload.expected_revision===1))){
    audit.posts++;await route.continue();return;
   }
  }
  audit.blocked.push(method+' '+path);
  await route.fulfill({status:403,json:{detail:'Synthetic human-review request refused'}});
 });
 return audit;
}

let backend:DisposableBackend|null=null;
test.beforeEach(async()=>{backend=await startDisposableBackend()});
test.afterEach(async()=>{if(backend){const owned=backend;backend=null;await stopDisposableBackend(owned)}});

test('P3-03 real HTTP: explicit owner review, discard, reload, edit and project isolation',
 async({page,context,request})=>{
  if(process.env.CI!=='true'||process.env.GITHUB_ACTIONS!=='true'||
     process.env.P1_REAL_HTTP_E2E!=='1'||!process.env.PILOTODIN_HOME)
   throw Error('Requires trusted CI disposable backend and synthetic-only project');

  const ids:string[]=[];
  for(const label of ['A','B']){
   const result=await request.post(API+'/api/projects',{multipart:{
    file:{name:'synthetic_review_'+label+'.csv',mimeType:'text/csv',
     buffer:Buffer.from(source(label))},
   }});
   expect(result.status(),await result.text()).toBe(201);
   ids.push((await result.json()).id as string);
  }
  const [one,two]=ids as [string,string];
  const initial=await request.get(`${API}/api/projects/${one}/semantic-reviews?expected_version=0`);
  expect(initial.status()).toBe(200);
  const candidate=(await initial.json()).candidates.find((x:{column:string;role:string})=>
   x.column==='claim_amount'&&x.role==='possible_monetary_measure');
  expect(candidate).toBeDefined();
  expect(candidate.review).toBeNull();

  const audit=await guard(context,one,two);
  await page.addInitScript((id:string)=>{
   localStorage.setItem('pilotodin-current',id);
   localStorage.setItem('pilotodin-workspace-tabs-v1-'+id,JSON.stringify(['understand']));
   localStorage.setItem('pilotodin-workspace-active-v1-'+id,'understand');
  },one);
  await page.goto('/#/studio/understand');
  const semantic=page.getByRole('region',{name:'Business context hypotheses'});
  await expect(semantic.getByText('UNVERIFIED',{exact:true})).toBeVisible();
  const panel=page.locator('details[aria-label="Owner interpretation review"]');
  await expect(panel.locator('summary')).toContainText('Review tentative field interpretations');
  await panel.locator('summary').click();
  await panel.getByLabel('Field hypothesis to review')
   .selectOption({label:'claim_amount · possible monetary measure'});
  await expect(panel.getByText('Human review only.',{exact:false})).toBeVisible();

  const choice=panel.getByLabel('Your assessment');
  const note=panel.getByLabel('Your explanation (required when correction is needed)');
  const save=panel.getByRole('button',{name:'Save owner review'});
  await expect(save).toBeDisabled();
  await choice.selectOption('needs_correction');
  await expect(save).toBeDisabled(); // No explanation, no write.
  await note.fill('I need to check the currency and applicable units.');
  await expect(save).toBeEnabled();
  await expect(panel.getByText('Unsaved interpretation review.',{exact:false})).toBeVisible();
  await panel.getByRole('button',{name:'Discard review edits'}).click();
  await expect(choice).toHaveValue('');
  await expect(save).toBeDisabled();
  expect(audit.posts).toBe(0);

  await choice.selectOption('acceptable');
  const firstResponse=page.waitForResponse(r=>r.url()===
   `${API}/api/projects/${one}/semantic-reviews`&&r.request().method()==='POST');
  await save.click();
  const first=await firstResponse;
  expect(first.status(),await first.text()).toBe(200);
  expect((await first.json()).revision).toBe(1);
  await expect(panel.getByText('Previously saved owner review:',{exact:false}))
   .toContainText('interpretation acceptable');
  await expect(panel.getByText('Unsaved interpretation review.',{exact:false})).toHaveCount(0);

  await page.reload();
  const reopened=page.locator('details[aria-label="Owner interpretation review"]');
  await reopened.locator('summary').click();
  await reopened.getByLabel('Field hypothesis to review')
   .selectOption({label:'claim_amount · possible monetary measure'});
  await expect(reopened.getByLabel('Your assessment')).toHaveValue('acceptable');
  await reopened.getByLabel('Your assessment').selectOption('needs_correction');
  await reopened.getByLabel('Your explanation (required when correction is needed)')
   .fill('The amount might be in cents, not the displayed currency.');
  const editResponse=page.waitForResponse(r=>r.url()===
   `${API}/api/projects/${one}/semantic-reviews`&&r.request().method()==='POST');
  await reopened.getByRole('button',{name:'Save owner review'}).click();
  const edited=await editResponse;
  expect(edited.status(),await edited.text()).toBe(200);
  expect((await edited.json()).revision).toBe(2);

  const current=await (await request.get(`${API}/api/projects/${one}/semantic-reviews?expected_version=0`)).json();
  const saved=current.candidates.find((x:{column:string;role:string})=>
   x.column==='claim_amount'&&x.role==='possible_monetary_measure');
  expect(saved.review.decision).toBe('needs_correction');
  expect(saved.review.revision).toBe(2);
  expect(saved.review.review_state).toBe('owner_attestation_not_independently_verified');
  const other=await (await request.get(`${API}/api/projects/${two}/semantic-reviews?expected_version=0`)).json();
  expect(other.candidates.every((x:{review:unknown})=>x.review===null)).toBe(true);

  const stale=await request.post(`${API}/api/projects/${one}/semantic-reviews`,{data:{
   expected_version:0,column:'claim_amount',role:'possible_monetary_measure',
   hypothesis_hash:candidate.hypothesis_hash,decision:'cannot_assess',
   explanation:'',expected_revision:1,
  }});
  expect(stale.status()).toBe(409);
  expect(audit).toEqual({posts:2,blocked:[],remote:[]});
  await expect(semantic.getByText('UNVERIFIED',{exact:true})).toBeVisible();
 });
