import {test,expect} from '@playwright/test';
import type {BrowserContext,Route} from '@playwright/test';
import {Buffer} from 'node:buffer';
import {startDisposableBackend,stopDisposableBackend} from './p1-real-http-backend';
import type {DisposableBackend} from './p1-real-http-backend';

// Only the isolated CI runner may mount the actual ReportWorkspace with new props.
// Browser can GET verified synthetic evidence, never save a report, edit Quality,
// fetch remote resources or invoke training.
const API='http://127.0.0.1:8000', UI='http://127.0.0.1:5178';
const csv=['OrderID,Region,Revenue','001,West,120','002,East,200','003,West,300'].join('\n')+'\n';
let backend:DisposableBackend|null=null;
test.beforeEach(async()=>{backend=await startDisposableBackend()});
test.afterEach(async()=>{if(backend){const old=backend;backend=null;await stopDisposableBackend(old)}});

async function protectBrowser(context:BrowserContext,projectId:string){
 const audit={unexpected:[] as string[],blockedWrites:[] as string[],remote:[] as string[],reads:[] as string[]};
 const allowed=new Set([
  `/api/projects/${projectId}/reports`,
  `/api/projects/${projectId}/report-evidence`,
 ]);
 await context.route('**/*',async(route:Route)=>{
  const req=route.request(),url=new URL(req.url()),method=req.method();
  if(url.origin===UI&&(method==='GET'||method==='HEAD')){
   await route.continue();return;
  }
  if(method==='GET'&&url.origin==='https://fonts.googleapis.com'&&url.pathname==='/css2'){
   await route.fulfill({status:200,contentType:'text/css',body:'/* CI system fonts */'});return;
  }
  if(url.origin===API&&method==='GET'&&url.search===''&&allowed.has(url.pathname)){
   audit.reads.push(url.pathname);await route.continue();return;
  }
  if(method!=='GET'&&method!=='HEAD'){
   audit.blockedWrites.push(method+' '+url.pathname);
   await route.fulfill({status:403,json:{detail:'CI browser writes denied'}});return;
  }
  if(url.origin!==UI&&url.origin!==API) {
   audit.remote.push(method+' '+url.origin+url.pathname);
   await route.abort('blockedbyclient');return;
  }
  audit.unexpected.push(method+' '+url.pathname+url.search);
  await route.fulfill({status:404,json:{detail:'Unexpected synthetic GET'}});return;
 });
 return audit;
}

test('P2 mounted Deliver incoming evidence requires explicit consent, keeps refused drafts and handles later verified handoff',
 async({page,context,request})=>{
  if(process.env.CI!=='true'||process.env.GITHUB_ACTIONS!=='true'||process.env.P1_REAL_HTTP_E2E!=='1')
   throw new Error('Real HTTP mounted handoff test requires isolated GitHub Actions.');

  const uploaded=await request.post(API+'/api/projects',{multipart:{
   file:{name:'P2_Disposable_Mounted_Handoff.csv',mimeType:'text/csv',buffer:Buffer.from(csv)}
  }});
  expect(uploaded.status(),await uploaded.text()).toBe(201);
  const pid=(await uploaded.json()).id as string;
  expect(pid).toMatch(/^[a-f0-9]{32}$/);

  const titles=['Synthetic Hand-off A','Synthetic Hand-off B'];
  const ids:string[]=[];
  for(const title of titles){
   const created=await request.post(API+`/api/projects/${pid}/explore/saved`,{data:{
    title,expected_version:0,x:'Region',y:'Revenue',kind:'bar',aggregation:'sum',
    bins:16,correlation_method:'pearson',color_by:null,filters:[]
   }});
   expect(created.status(),await created.text()).toBe(201);
   const id=(await created.json()).id as string;
   expect(id).toMatch(/^[a-f0-9]{32}$/);
   ids.push(id);
  }
  expect(new Set(ids).size).toBe(2);
  const unknown='f'.repeat(32);
  expect(ids).not.toContain(unknown);
  const beforeList=await (await request.get(API+`/api/projects/${pid}/reports`)).json();
  const beforeQuality=await (await request.get(API+`/api/projects/${pid}/quality/history`)).json();
  const audit=await protectBrowser(context,pid);

  await page.goto(`/p2_mounted_handoff_qa.html?project=${pid}&first=${ids[0]}&second=${ids[1]}&unknown=${unknown}`);
  await expect(page.getByRole('heading',{name:'Saved, evidence-backed reports'})).toBeVisible();
  const editor=page.locator('.pd-report-workspace');
  const title=editor.getByLabel('Report title');
  const note=editor.getByLabel('Interpretation and limitations');
  const options=editor.locator('.pd-report-evidence-row input[type=checkbox]');
  await expect(options).toHaveCount(2);
  const originalTitle='Synthetic analyst draft that must survive refusal';
  const originalNote='Unpublished human interpretation of a disposable CSV.';
  await title.fill(originalTitle);
  await note.fill(originalNote);
  await options.first().check();
  const chosenBefore=await editor.locator('.pd-report-evidence-row input:checked').count();
  expect(chosenBefore).toBe(1);
  await expect(page.getByLabel('Deliver draft state')).toHaveText('dirty');

  await page.getByRole('button',{name:'Request synthetic A'}).click();
  const discard=editor.getByRole('dialog',{name:'Discard unsaved report edits?'});
  await expect(discard).toBeVisible();
  await expect(discard).toContainText('Using a saved Explore analysis');
  await expect(discard.getByRole('button',{name:'Keep editing'})).toBeFocused();
  await discard.getByRole('button',{name:'Keep editing'}).click();
  await expect(discard).toHaveCount(0);
  await expect(title).toHaveValue(originalTitle);
  await expect(note).toHaveValue(originalNote);
  expect(await editor.locator('.pd-report-evidence-row input:checked').count()).toBe(chosenBefore);

  // An already-declined incoming ID cannot reapply merely because its
  // parent renders again while Deliver remains mounted and edited.
  await page.getByRole('button',{name:'Rerender unchanged request'}).click();
  await expect(page.getByLabel('Parent render count')).toHaveText('1');
  await expect(discard).toHaveCount(0);
  await expect(note).toHaveValue(originalNote);

  await page.getByRole('button',{name:'Request synthetic B'}).click();
  await expect(discard).toBeVisible();
  await page.keyboard.press('Escape');
  await expect(discard).toHaveCount(0);
  await expect(title).toHaveValue(originalTitle);
  await expect(note).toHaveValue(originalNote);

  // An external parent can revoke an offered handoff while its modal is open.
  // Use a programmatic QA-control click because the live modal correctly
  // prevents pointer interaction with the parent behind it.
  await page.getByRole('button',{name:'Request synthetic A'}).click();
  await expect(discard).toBeVisible();
  await page.evaluate(()=>{
   const withdraw=document.querySelector<HTMLButtonElement>('[data-qa-withdraw]');
   if(!withdraw)throw new Error('Missing synthetic parent withdrawal control');
   withdraw.click();
  });
  await expect(discard).toHaveCount(0);
  await expect(title).toHaveValue(originalTitle);
  await expect(note).toHaveValue(originalNote);
  // Reissuing A after withdrawal is a NEW request, not replay of the old modal.
  await page.getByRole('button',{name:'Request synthetic A'}).click();
  await expect(discard).toBeVisible();
  await discard.getByRole('button',{name:'Keep editing'}).click();
  await expect(note).toHaveValue(originalNote);

  // Unknown evidence must be refused before any discard consent or draft reset.
  await page.getByRole('button',{name:'Request nonexistent evidence'}).click();
  await expect(editor.getByRole('alert')).toContainText('not available as verified evidence');
  await expect(discard).toHaveCount(0);
  await expect(note).toHaveValue(originalNote);
  await expect(title).toHaveValue(originalTitle);

  // Replace an outstanding request while the modal is open. Approving it
  // must use ONLY the latest prop, never the previous pending evidence ID.
  await page.getByRole('button',{name:'Request synthetic B'}).click();
  await expect(discard).toBeVisible();
  await page.evaluate(()=>{
   const newer=[...document.querySelectorAll<HTMLButtonElement>('button')]
    .find(button=>button.textContent==='Request synthetic A');
   if(!newer)throw new Error('Missing synthetic replacement control');
   newer.click();
  });
  await expect(discard).toBeVisible();
  await discard.getByRole('button',{name:'Discard and continue'}).click();
  await expect(discard).toHaveCount(0);
  await expect(title).toHaveValue(titles[0]+' report');
  await expect(note).toHaveValue('');
  await expect(editor.locator('.pd-report-evidence-row')
   .filter({hasText:ids[0].slice(0,12)}).locator('input[type=checkbox]')).toBeChecked();

  // A later valid request on this same mounted component still needs explicit
  // consent once the user has written new text. No backend write is allowed.
  await note.fill('New human analysis that must not be replaced silently.');
  await page.getByRole('button',{name:'Request synthetic B'}).click();
  await expect(discard).toBeVisible();
  await discard.getByRole('button',{name:'Discard and continue'}).click();
  await expect(discard).toHaveCount(0);
  await expect(title).toHaveValue(titles[1]+' report');
  await expect(note).toHaveValue('');
  const selected=editor.locator('.pd-report-evidence-row').filter({hasText:ids[1].slice(0,12)}).locator('input[type=checkbox]');
  await expect(selected).toBeChecked();
  expect(await editor.locator('.pd-report-evidence-row input:checked').count()).toBe(1);
  await expect(page.getByLabel('Deliver draft state')).toHaveText('dirty');

  expect(audit.blockedWrites).toEqual([]);
  expect(audit.unexpected).toEqual([]);
  expect(audit.remote).toEqual([]);
  expect(audit.reads).toContain(`/api/projects/${pid}/report-evidence`);
  expect(await (await request.get(API+`/api/projects/${pid}/reports`)).json()).toEqual(beforeList);
  expect(await (await request.get(API+`/api/projects/${pid}/quality/history`)).json()).toEqual(beforeQuality);
 });
