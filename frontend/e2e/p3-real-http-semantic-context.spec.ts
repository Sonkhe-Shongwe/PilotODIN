import {test,expect} from '@playwright/test';
import type {BrowserContext,Route} from '@playwright/test';
import {Buffer} from 'node:buffer';
import {startDisposableBackend,stopDisposableBackend} from './p1-real-http-backend';
import type {DisposableBackend} from './p1-real-http-backend';

const API='http://127.0.0.1:8000';
const UI='http://127.0.0.1:5178';
const firstDomain='Owner-described insurance claim processing dataset';
const revisedDomain='Owner-described synthetic insurance cases, revised locally';
const rowMeaning='Each synthetic row represents one individual submitted case';
const fieldMeaning='Requested claim amount, as described by this fixture owner';
const source=(tag:string)=>[
 'claim_id,claim_amount,policy_number',
 ...Array.from({length:20},(_,i)=>
  tag+String(i+1).padStart(3,'0')+','+String((i+1)*21)+',P'+String((i%4)+1))
].join('\n')+'\n';

type Audit={saved:number;blocked:string[];remote:string[];reads:string[]};
async function protectBrowser(context:BrowserContext,ids:[string,string]):Promise<Audit>{
 const audit:Audit={saved:0,blocked:[],remote:[],reads:[]};
 await context.route('**/*',async(route:Route)=>{
  const req=route.request(),url=new URL(req.url()),method=req.method();
  if(url.origin===UI){
   if(method==='GET'||method==='HEAD'){await route.continue();return;}
   audit.blocked.push('UI '+method);await route.abort('blockedbyclient');return;
  }
  if(method==='GET'&&url.origin==='https://fonts.googleapis.com'&&url.pathname==='/css2'){
   await route.fulfill({status:200,contentType:'text/css',body:'/* no external fonts */'});return;
  }
  if(url.origin!==API||!url.pathname.startsWith('/api/')){
   audit.remote.push(method+' unexpected '+url.origin);await route.abort('blockedbyclient');return;
  }
  const path=url.pathname.slice(4);
  const approved=ids.some(id=>path.startsWith('/projects/'+id+'/')||path==='/projects/'+id);
  const simpleRead=method==='GET'&&url.search===''&&[
   '/projects','/ai/settings',...ids.map(id=>'/projects/'+id),
   ...ids.map(id=>'/projects/'+id+'/live-profile'),
   ...ids.map(id=>'/projects/'+id+'/columns/overview'),
   ...ids.map(id=>'/projects/'+id+'/quality'),
   ...ids.map(id=>'/projects/'+id+'/quality/history'),
  ].includes(path);
  const semanticsRead=method==='GET'&&ids.some(id=>path==='/projects/'+id+'/semantics')&&
   [...url.searchParams.keys()].length===1&&url.searchParams.get('expected_version')==='0';
  const detailRead=method==='GET'&&ids.some(id=>path==='/projects/'+id+'/columns/detail')&&
   [...url.searchParams.keys()].sort().join(',')==='expected_version,name'&&
   url.searchParams.get('expected_version')==='0'&&
   ['claim_id','claim_amount','policy_number'].includes(url.searchParams.get('name')??'');
  if(simpleRead||semanticsRead||detailRead){audit.reads.push(path);await route.continue();return;}
  if(method==='POST'&&path==='/projects/'+ids[0]+'/semantic-business-context'&&url.search===''&&audit.saved<2){
   let body:unknown;
   try{body=req.postDataJSON()}catch{body=null}
   const object=body as Record<string,unknown>|null;
   const fields=object?.field_definitions;
   const domain=object?.domain_description;
   const valid=object&&Object.keys(object).sort().join(',')===
     'domain_description,expected_version,field_definitions,record_grain_description'&&
     object.expected_version===0&&
     [firstDomain,revisedDomain].includes(String(domain))&&
     object.record_grain_description===rowMeaning&&
     Array.isArray(fields)&&fields.length===1&&
     fields[0].column==='claim_amount'&&fields[0].meaning===fieldMeaning;
   if(valid){
    audit.saved++;await route.continue();return;
   }
  }
  audit.blocked.push(method+' '+path+url.search+(approved?' scoped':' unknown'));
  await route.fulfill({status:403,json:{detail:'Unreviewed browser operation'}});return;
 });
 return audit;
}

let backend:DisposableBackend|null=null;
test.beforeEach(async()=>{backend=await startDisposableBackend()});
test.afterEach(async()=>{if(backend){const owned=backend;backend=null;await stopDisposableBackend(owned)}});

test('P3 real HTTP semantic descriptions save, reopen, edit and stay project/version isolated',
 async({page,context,request})=>{
  if(process.env.CI!=='true'||process.env.GITHUB_ACTIONS!=='true'||
     process.env.P1_REAL_HTTP_E2E!=='1'||!process.env.PILOTODIN_HOME)
    throw Error('P3 real HTTP test requires runner-owned synthetic workspace');

  const ids:string[]=[];
  for(const name of ['A','B']){
   const r=await request.post(API+'/api/projects',{multipart:{
    file:{name:'P3_Semantic_Synthetic_'+name+'.csv',
     mimeType:'text/csv',buffer:Buffer.from(source(name))}
   }});
   expect(r.status(),await r.text()).toBe(201);
   const project=(await r.json()) as {id:string};
   expect(project.id).toMatch(/^[a-f0-9]{32}$/);
   ids.push(project.id);
  }
  const [aid,bid]=ids as [string,string];
  const beforeA=await (await request.get(API+'/api/projects/'+aid+'/quality/history')).json();
  const beforeB=await (await request.get(API+'/api/projects/'+bid+'/quality/history')).json();
  const initial=await request.get(API+'/api/projects/'+aid+'/semantics?expected_version=0');
  expect(initial.status()).toBe(200);
  const original=await initial.json() as {domain:unknown;grain:unknown;user_context:unknown};
  expect(original.user_context).toBeNull();

  const audit=await protectBrowser(context,[aid,bid]);
  await page.addInitScript((id:string)=>{
   localStorage.setItem('pilotodin-current',id);
   localStorage.setItem('pilotodin-workspace-tabs-v1-'+id,JSON.stringify(['understand']));
   localStorage.setItem('pilotodin-workspace-active-v1-'+id,'understand');
  },aid);
  await page.goto('/#/studio/understand');
  const semantic=page.getByRole('region',{name:'Business context hypotheses'});
  await expect(semantic.getByRole('heading',{name:'Business meaning hypotheses'})).toBeVisible();
  await expect(semantic.getByText('UNVERIFIED',{exact:true})).toBeVisible();
  await expect(semantic.getByText('Optional: describe what this dataset means')).toBeVisible();
  const editorDisclosure=semantic.getByText('Optional: describe what this dataset means');
  await editorDisclosure.focus();
  await page.keyboard.press('Enter');
  await expect(semantic.getByLabel('What business area does this dataset describe?')).toBeVisible();
  const domainEditor=semantic.getByLabel('What business area does this dataset describe?');
  await domainEditor.fill('short');
  await expect(semantic.getByRole('button',{name:'Save business descriptions'})).toBeDisabled();
  await domainEditor.fill(firstDomain);
  await semantic.getByLabel('What does one row represent?').fill(rowMeaning);
  await semantic.getByRole('button',{name:'Add field definition'}).click();
  await semantic.getByLabel('Field 1').selectOption('claim_amount');
  await semantic.getByLabel('Owner-described meaning').fill('tiny');
  await expect(semantic.getByRole('button',{name:'Save business descriptions'})).toBeDisabled();
  await semantic.getByLabel('Owner-described meaning').fill(fieldMeaning);
  await expect(semantic.getByText('Unsaved business descriptions.',{exact:false})).toBeVisible();
  const switcherBeforeSave=page.getByRole('combobox',{name:'Switch project'});
  let declinedMessage='';
  page.once('dialog',async dialog=>{
   declinedMessage=dialog.message();
   await dialog.dismiss();
  });
  await switcherBeforeSave.selectOption(bid);
  await expect(switcherBeforeSave).toHaveValue(aid);
  await expect(domainEditor).toHaveValue(firstDomain);
  expect(declinedMessage).toMatch(/unsaved|changed fields|discard/i);
  // Save through keyboard activation after declining navigation.

  const savedResponse=page.waitForResponse(r=>
   r.url()===API+'/api/projects/'+aid+'/semantic-business-context'&&
   r.request().method()==='POST');
  const saveByKey=semantic.getByRole('button',{name:'Save business descriptions'});
  await saveByKey.focus();
  await expect(saveByKey).toBeFocused();
  await page.keyboard.press('Enter');
  const saved=await savedResponse;
  expect(saved.status(),await saved.text()).toBe(200);
  await expect(semantic.getByText('Saved for this dataset version as user-provided',{exact:false})).toBeVisible();
  await expect(semantic.getByText('Unsaved business descriptions.',{exact:false})).toHaveCount(0);
  await expect(semantic.getByRole('region',{name:'Owner-described business context'})).toContainText(firstDomain);
  const domainReview=semantic.getByRole('group',{name:'Compare unverified domain statements'});
  await expect(domainReview).toContainText(firstDomain);
  await expect(domainReview).toContainText('No automatic equivalence or disagreement finding');
  await expect(domainReview).toContainText('Human review status: Not assessed');
  await expect(semantic.getByRole('group',{name:'Compare record-key and row-meaning statements'}))
   .toContainText('A unique row key does not independently establish');
  await semantic.locator('details').filter({hasText:'Inspect tentative field meanings'}).locator('summary').click();
  await expect(semantic.getByRole('columnheader',{name:'USER DESCRIPTION (UNVERIFIED)'})).toBeVisible();
  await expect(semantic.getByRole('columnheader',{name:'HUMAN REVIEW STATUS'})).toBeVisible();
  await expect(semantic.getByRole('row').filter({hasText:'claim_amount'}).getByRole('cell').last())
   .toContainText('Not assessed: the system hint and user description are both unverified.');
  await expect(semantic.getByRole('row').filter({hasText:'policy_number'}).getByRole('cell').last())
   .toContainText('No user description; comparison unavailable.');
  // USER DESCRIPTION stays in column 5; column 6 now exposes the review status.
  await expect(semantic.getByRole('row').filter({hasText:'claim_amount'}).getByRole('cell').nth(4))
   .toContainText(fieldMeaning+' (user-described, not independently verified)');
  const savedBody=await (await request.get(API+'/api/projects/'+aid+'/semantics?expected_version=0')).json();
  expect(savedBody.user_context.domain_description).toBe(firstDomain);
  expect(savedBody.domain).toEqual(original.domain);
  expect(savedBody.grain).toEqual(original.grain);

  await page.reload();
  await expect(semantic.getByText('Review or revise your business descriptions')).toBeVisible();
  await semantic.getByText('Review or revise your business descriptions').click();
  await expect(semantic.getByLabel('What business area does this dataset describe?')).toHaveValue(firstDomain);
  await expect(semantic.getByLabel('What does one row represent?')).toHaveValue(rowMeaning);
  await expect(semantic.getByLabel('Owner-described meaning')).toHaveValue(fieldMeaning);
  await semantic.getByLabel('What business area does this dataset describe?').fill(revisedDomain);
  const editResponse=page.waitForResponse(r=>
   r.url()===API+'/api/projects/'+aid+'/semantic-business-context'&&
   r.request().method()==='POST');
  await semantic.getByRole('button',{name:'Save business descriptions'}).click();
  expect((await editResponse).status()).toBe(200);
  await expect(semantic.getByRole('region',{name:'Owner-described business context'})).toContainText(revisedDomain);

  const switcher=page.getByRole('combobox',{name:'Switch project'});
  await expect(switcher).toHaveValue(aid);
  await switcher.selectOption(bid);
  await expect(switcher).toHaveValue(bid);
  await expect(semantic.getByText('Optional: describe what this dataset means')).toBeVisible();
  await expect(semantic.getByText(revisedDomain)).toHaveCount(0);
  const empty=await (await request.get(API+'/api/projects/'+bid+'/semantics?expected_version=0')).json();
  expect(empty.user_context).toBeNull();

  await switcher.selectOption(aid);
  await expect(semantic.getByRole('region',{name:'Owner-described business context'})).toContainText(revisedDomain);
  expect((await request.get(API+'/api/projects/'+aid+'/semantics?expected_version=1')).status()).toBe(409);
  const stale=await request.post(API+'/api/projects/'+aid+'/semantic-business-context',{
   data:{expected_version:1,domain_description:'Should never be saved for stale version'},
  });
  expect(stale.status()).toBe(409);
  const final=await (await request.get(API+'/api/projects/'+aid+'/semantics?expected_version=0')).json();
  expect(final.user_context.domain_description).toBe(revisedDomain);
  expect(final.domain).toEqual(original.domain);
  expect(final.grain).toEqual(original.grain);
  expect(await (await request.get(API+'/api/projects/'+aid+'/quality/history')).json()).toEqual(beforeA);
  expect(await (await request.get(API+'/api/projects/'+bid+'/quality/history')).json()).toEqual(beforeB);
  expect(audit.saved).toBe(2);
  expect(audit.blocked).toEqual([]);
  expect(audit.remote).toEqual([]);
 });
