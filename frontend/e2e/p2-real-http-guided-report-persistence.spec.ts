import {test,expect} from '@playwright/test';
import type {BrowserContext,Route} from '@playwright/test';
import {Buffer} from 'node:buffer';
import {spawnSync} from 'node:child_process';
import {startDisposableBackend,stopDisposableBackend} from './p1-real-http-backend';
import type {DisposableBackend} from './p1-real-http-backend';

// Only GitHub's owned, temporary Uvicorn + Vite services are available.
// Browser mutation is limited to ONE validated synthetic report creation.
const API='http://127.0.0.1:8000';
const UI='http://127.0.0.1:5178';
const csv='RecordID,Region,Revenue\n0001,West,120.00\n0002,East,240.00\n0003,West,180.00\n';
const title='Synthetic Human-Authored Evidence Report';
const narrative=[
 'Purpose and decision','Review a disposable project for a human decision.',
 'Verified evidence interpretation','The analyst selected a verified overview exhibit.',
 'Limitations and uncertainty','These synthetic records cannot establish causation.',
 'Recommendations and next steps','Validate dataset quality before applying any decision.',
].join('\n\n')+'\n';

function assertCI():void{
 if(process.env.CI!=='true'||process.env.GITHUB_ACTIONS!=='true'||
    process.env.P1_REAL_HTTP_E2E!=='1'||!process.env.PILOTODIN_HOME){
  throw new Error('Only the owned disposable GitHub CI backend may run this test.');
 }
}
type Audit={allowedPosts:number;blocked:string[];remote:string[];reads:string[]};
async function guardBrowser(context:BrowserContext,pid:string,evidenceId:string):Promise<Audit>{
 const audit:Audit={allowedPosts:0,blocked:[],remote:[],reads:[]};
 await context.route('**/*',async(route:Route)=>{
  const req=route.request(),url=new URL(req.url()),method=req.method();
  if(url.origin===UI){
   if(method==='GET'||method==='HEAD'){await route.continue();return;}
   audit.blocked.push(method+' unapproved UI operation');await route.abort('blockedbyclient');return;
  }
  if(method==='GET'&&url.origin==='https://fonts.googleapis.com'&&url.pathname==='/css2'){
   await route.fulfill({status:200,contentType:'text/css',body:'/* fonts not loaded */'});return;
  }
  if(url.origin!==API||!url.pathname.startsWith('/api/')){
   audit.remote.push(method+' unexpected remote origin');await route.abort('blockedbyclient');return;
  }
  const path=url.pathname.slice(4);
  if(method==='POST'&&url.search===''&&path===`/projects/${pid}/reports`){
   const expected={title,narrative,evidence_ids:[evidenceId]};
   let submitted:unknown;
   try{submitted=req.postDataJSON();}catch{submitted=null;}
   if(audit.allowedPosts!==0||JSON.stringify(submitted)!==JSON.stringify(expected)){
    audit.blocked.push('unapproved or repeated report POST');
    await route.fulfill({status:403,json:{detail:'Unapproved synthetic write'}});return;
   }
   audit.allowedPosts++;
   await route.continue();return;
  }
  const read=method==='GET'&&url.search===''&&[
   '/projects','/ai/settings',`/projects/${pid}`,
   `/projects/${pid}/live-profile`,`/projects/${pid}/reports`,
   `/projects/${pid}/report-evidence`,
  ].includes(path);
  if(read){audit.reads.push(path);await route.continue();return;}
  // Report reads after the Save are validated independently via APIRequestContext.
  audit.blocked.push(method+' '+path+url.search);
  await route.fulfill({status:403,json:{detail:'Unreviewed request'}});return;
 });
 return audit;
}
let backend:DisposableBackend|null=null;
test.beforeEach(async()=>{assertCI();backend=await startDisposableBackend()});
test.afterEach(async()=>{if(backend){const child=backend;backend=null;await stopDisposableBackend(child)}});

test('P2 guided report saves once, persists immutable narrative and exports same authored content',
 async({page,context,request})=>{
  assertCI();
  // Synthetic fixture writes use the runner's independent API client, not the browser.
  const uploaded=await request.post(API+'/api/projects',{multipart:{
   file:{name:'P2_Guided_Reports_Synthetic_Only.csv',
    mimeType:'text/csv',buffer:Buffer.from(csv)},
  }});
  expect(uploaded.status(),await uploaded.text()).toBe(201);
  const pid=(await uploaded.json()).id as string;
  expect(pid).toMatch(/^[a-f0-9]{32}$/);
  const createdInv=await request.post(API+`/api/projects/${pid}/investigations`,{
   data:{objective:'A disposable overview for saved report acceptance'},
  });
  expect(createdInv.status(),await createdInv.text()).toBe(201);
  const investigation=await createdInv.json() as {id:string;version:number};
  const completed=await request.post(API+`/api/investigations/${investigation.id}/runs`,{
   data:{operation:'overview',params:{},expected_version:investigation.version},
  });
  expect(completed.status(),await completed.text()).toBe(200);
  const eid=(await completed.json()).artifacts[0].id as string;
  expect(eid).toMatch(/^[a-f0-9]{32}$/);
  const beforeQuality=await (await request.get(API+`/api/projects/${pid}/quality/history`)).json();
  const beforeReports=await (await request.get(API+`/api/projects/${pid}/reports`)).json();
  expect(beforeReports).toEqual([]);

  const audit=await guardBrowser(context,pid,eid);
  await page.addInitScript((id:string)=>{
   localStorage.setItem('pilotodin-current',id);
   localStorage.setItem('pilotodin-workspace-tabs-v1-'+id,JSON.stringify(['deliver']));
   localStorage.setItem('pilotodin-workspace-active-v1-'+id,'deliver');
  },pid);
  await page.goto('/#/studio/deliver');
  const primary=page.locator('.po-primary-pane');
  await expect(primary.getByRole('heading',{name:'Saved, evidence-backed reports'})).toBeVisible();
  await primary.getByRole('button',{name:'Use General analysis outline'}).click();
  const progress=primary.locator('.pd-report-outline-progress');
  await expect(progress).toContainText('0 of 4 sections complete');
  await expect(primary.getByRole('button',{name:'Save report'})).toBeDisabled();
  await primary.getByLabel('Report title').fill(title);
  await primary.getByLabel('Interpretation and limitations').fill(narrative);
  await expect(progress).toContainText('4 of 4 sections complete');
  await expect(primary.getByRole('button',{name:'Save report'})).toBeDisabled();
  const choice=primary.locator('.pd-report-evidence-row').filter({hasText:eid.slice(0,12)});
  await expect(choice).toHaveCount(1);
  await choice.locator('input[type=checkbox]').check();
  await expect(primary.getByRole('button',{name:'Save report'})).toBeEnabled();

  const saving=page.waitForResponse(r=>
   r.url()===API+`/api/projects/${pid}/reports`&&r.request().method()==='POST');
  await primary.getByRole('button',{name:'Save report'}).click();
  const savedReply=await saving;
  expect(savedReply.status(),await savedReply.text()).toBe(201);
  const saved=await savedReply.json() as {
   id:string;revision:number;revision_id:string;title:string;narrative:string;
   content_sha256:string;evidence:{id:string}[];
  };
  expect(saved.revision).toBe(1);
  expect(saved.title).toBe(title);
  expect(saved.narrative).toBe(narrative);
  expect(saved.evidence.map(e=>e.id)).toEqual([eid]);
  expect(saved.content_sha256).toMatch(/^[a-f0-9]{64}$/);
  await expect(primary.getByText('Saved revision 1',{exact:false}).first()).toBeVisible();
  await expect(primary.getByRole('button',{name:'Save new revision'})).toBeDisabled();
  expect(audit.allowedPosts).toBe(1);
  expect(audit.blocked).toEqual([]);
  expect(audit.remote).toEqual([]);

  const original=await request.get(API+`/api/reports/${saved.id}?revision=1`);
  expect(original.status(),await original.text()).toBe(200);
  const frozen=await original.json();
  expect(frozen.narrative).toBe(narrative);
  expect(frozen.content_sha256).toBe(saved.content_sha256);
  expect(frozen.revisions).toEqual([1]);

  // Normal authenticated-compatible API route. Legacy ASCII export is tested;
  // no Unicode font distribution, new font registration or OS Save As.
  const basename=`pilotodin_report_${saved.id.slice(0,12)}_rev1`;
  const htmlRes=await request.get(API+`/api/reports/${saved.id}/export/html?revision=1`);
  expect(htmlRes.status(),await htmlRes.text()).toBe(200);
  expect(htmlRes.headers()['content-disposition']).toContain(basename+'.html');
  const html=await htmlRes.text();
  for(const phrase of [
   'Purpose and decision','Verified evidence interpretation',
   'Limitations and uncertainty','Recommendations and next steps',
   'The analyst selected a verified overview exhibit.',
  ])expect(html).toContain(phrase);
  expect(html).toContain(saved.content_sha256);

  const pdfRes=await request.get(API+`/api/reports/${saved.id}/export/pdf?revision=1`);
  expect(pdfRes.status(),await pdfRes.text()).toBe(200);
  expect(pdfRes.headers()['content-disposition']).toContain(basename+'.pdf');
  const pdf=await pdfRes.body();
  expect(pdf.subarray(0,5).toString('ascii')).toBe('%PDF-');
  const script='import fitz,sys; d=fitz.open(stream=sys.stdin.buffer.read(),filetype="pdf"); print("\\n".join(p.get_text() for p in d))';
  const extracted=spawnSync('python',['-c',script],{
   input:pdf,encoding:'utf8',maxBuffer:1024*1024,timeout:12000,
  });
  expect(extracted.status,extracted.stderr).toBe(0);
  const pdfText=extracted.stdout.replace(/\s+/g,' ');
  for(const phrase of [
   'Purpose and decision','Verified evidence interpretation',
   'Limitations and uncertainty','Recommendations and next steps',
   'These synthetic records cannot establish causation.',
  ])expect(pdfText).toContain(phrase);
  expect(pdfText).toContain(saved.content_sha256);

  // Reload genuinely asks the backend to restore the immutable saved revision.
  // Browser GET allowlist for the exact newly created report is extended here.
  await context.route(`**/api/reports/${saved.id}`,async route=>{
   if(route.request().method()==='GET'){await route.continue();return;}
   audit.blocked.push('unapproved report write');await route.abort('blockedbyclient');
  });
  await page.reload();
  await expect(primary.getByLabel('Report title')).toHaveValue(title);
  await expect(primary.getByLabel('Interpretation and limitations')).toHaveValue(narrative);
  await expect(primary.getByText('Saved revision 1',{exact:false}).first()).toBeVisible();
  await expect(primary.getByRole('button',{name:'Use General analysis outline'})).toBeDisabled();
  expect(audit.allowedPosts).toBe(1);
  expect(audit.blocked).toEqual([]);
  expect(audit.remote).toEqual([]);

  const afterReports=await (await request.get(API+`/api/projects/${pid}/reports`)).json();
  const afterQuality=await (await request.get(API+`/api/projects/${pid}/quality/history`)).json();
  expect(afterReports).toHaveLength(1);
  expect(afterReports[0].id).toBe(saved.id);
  expect(afterReports[0].revision).toBe(1);
  expect(afterQuality).toEqual(beforeQuality);
  const finalSaved=await (await request.get(API+`/api/reports/${saved.id}?revision=1`)).json();
  expect(finalSaved.revision_id).toBe(saved.revision_id);
  expect(finalSaved.content_sha256).toBe(saved.content_sha256);
 });
