import {test,expect} from '@playwright/test';
import type {BrowserContext,Route} from '@playwright/test';
import {Buffer} from 'node:buffer';
import {startDisposableBackend,stopDisposableBackend} from './p1-real-http-backend';
import type {DisposableBackend} from './p1-real-http-backend';

const API='http://127.0.0.1:8000';
const UI='http://127.0.0.1:5178';
const csv=[
 'row_id,churn,fraud_reported,outcome,failure_flag,future_cost,feature',
 ...Array.from({length:80},(_,i)=>[
  'P4-'+String(Math.floor(i/2)).padStart(3,'0'),
  i%2?'Y':'N',
  i%3?'Y':'N',
  i%2?'done':'pending',
  i%4?'no':'yes',
  110+i, i%7,
 ].join(','))
].join('\n')+'\n';

let backend:DisposableBackend|null=null;
test.beforeEach(async()=>{backend=await startDisposableBackend()});
test.afterEach(async()=>{
 if(backend){const owned=backend;backend=null;await stopDisposableBackend(owned)}
});

async function readOnlyBrowserGuard(context:BrowserContext,projectId:string,allowedContextWrites?:string[]){
 const blocked:string[]=[];
 await context.route('**/*',async(route:Route)=>{
  const request=route.request(),url=new URL(request.url()),method=request.method();
  if(url.origin===UI&&(method==='GET'||method==='HEAD')){
   await route.continue();return;
  }
  if(url.origin==='https://fonts.googleapis.com'&&method==='GET'&&url.pathname==='/css2'){
   await route.fulfill({status:200,contentType:'text/css',body:'/* CI-only */'});
   return;
  }
  if(url.origin===API&&method==='GET'&&url.pathname.startsWith('/api/')){
   const p=url.pathname.slice('/api'.length);
   const expected=p===`/projects/${projectId}`||
    p.startsWith(`/projects/${projectId}/`)||p==='/projects'||p==='/ai/settings';
   if(expected){await route.continue();return}
  }
  if(allowedContextWrites&&url.origin===API&&method==='POST'&&
     url.pathname===`/api/projects/${projectId}/target-business-context`){
   allowedContextWrites.push(url.pathname);
   await route.continue();return;
  }
  blocked.push(method+' '+url.origin+url.pathname);
  await route.abort('blockedbyclient');
 });
 return blocked;
}

test('P4-05 real HTTP: review ordering, other targets and explicit selection only',
 async({page,context,request})=>{
  if(process.env.CI!=='true'||process.env.GITHUB_ACTIONS!=='true'||
     process.env.P1_REAL_HTTP_E2E!=='1'||!process.env.PILOTODIN_HOME)
   throw Error('Only trusted disposable GitHub browser tests may execute');

  // This pre-test fixture upload happens through Playwright's isolated API
  // client before the page's strict read-only request allowlist starts.
  const res=await request.post(API+'/api/projects',{multipart:{
   file:{name:'p4_05_disposable.csv',mimeType:'text/csv',buffer:Buffer.from(csv)},
  }});
  expect(res.status(),await res.text()).toBe(201);
  const projectId=(await res.json()).id as string;
  const status=await request.get(
   `${API}/api/projects/${projectId}/target-opportunities?expected_version=0`);
  expect(status.status(),await status.text()).toBe(200);
  const data=await status.json();
  expect(data.eligible_count).toBeGreaterThan(3);
  expect(data.ranking_contract.business_value_verified).toBe(false);
  expect(data.other_reviewable.length).toBeGreaterThan(0);

  const blocked=await readOnlyBrowserGuard(context,projectId);
  await page.addInitScript((id:string)=>{
   localStorage.setItem('pilotodin-current',id);
   localStorage.setItem('pilotodin-workspace-tabs-v1-'+id,JSON.stringify(['prepare']));
   localStorage.setItem('pilotodin-workspace-active-v1-'+id,'prepare');
  },projectId);
  await page.goto('/#/studio/prepare');
  const section=page.getByRole('region',{name:'Potential prediction opportunities'});
  await expect(section).toBeVisible();
  await expect(section.getByText('Review order, not an estimated business-value ranking.',{
   exact:false,
  })).toBeVisible();
  await expect(section.getByText('Evidence needed before selecting this target')).toHaveCount(3);
  const evidenceTop=section.locator('article.model-choice').first()
   .locator('details[aria-label^="Evidence needed for"]');
  await evidenceTop.locator(':scope > summary').click();
  const utility=evidenceTop.getByLabel('Decision usefulness evidence');
  await expect(utility).toContainText('Decision usefulness: not established');
  await expect(utility).toContainText('40 additional occurrences beyond the first');
  await expect(utility).toContainText('Comparison with the existing process');
  const other=section.locator('details[aria-label="Additional reviewable target alternatives"]');
  await expect(other.locator(':scope > summary')).toContainText('More structurally reviewable targets');
  await other.locator(':scope > summary').click();
  const firstRow=other.locator('.warning-line').first();
  const evidence=firstRow.locator('details[aria-label^="Review evidence for alternative"]');
  await expect(evidence.locator('summary')).toHaveText('Inspect evidence and unresolved risks');
  await evidence.locator('summary').click();
  await expect(evidence.getByText('Business value and target safety remain unverified.',{exact:false})).toBeVisible();
  await expect(evidence.getByLabel('Decision usefulness evidence')).toContainText(
   '40 additional occurrences beyond the first');
  expect(await evidence.locator('li').count()).toBeGreaterThanOrEqual(4);
  await expect(firstRow.locator('details.po-context-editor summary')).toBeVisible();
  const alternative=other.getByRole('button',{name:'Review this alternative target'}).first();
  await expect(alternative).toBeVisible();
  await expect(alternative).toHaveAttribute('aria-pressed','false');
  await alternative.click(); // Only sets the local user's Prepare target draft.
  const pressed=other.locator('button[aria-pressed="true"]');
  await expect(pressed).toHaveCount(1);
  await expect(pressed).toHaveText('Chosen for preparation review');
  const checkpoint=section.getByRole('group',{name:'Selected target suitability checkpoint'});
  await expect(checkpoint).toContainText('independent decision');
  await expect(checkpoint).toContainText('This selection is not evidence of suitability');
  await firstRow.getByRole('button',{name:'Defer target in this review'}).click();
  await expect(page.getByLabel('TARGET VARIABLE')).toHaveValue('');
  await expect(checkpoint).toHaveCount(0);
  await expect(firstRow.getByText('Deferred for this review only.',{exact:false})).toBeVisible();
  await firstRow.getByRole('button',{name:'Review this alternative target'}).click();
  await expect(checkpoint).toBeVisible();
  await firstRow.getByRole('button',{name:'Decline target in this review'}).click();
  await expect(page.getByLabel('TARGET VARIABLE')).toHaveValue('');
  await expect(firstRow.getByText('Declined for this review only.',{exact:false})).toBeVisible();
  // The owner's manual choice still works and is not misrepresented as a
  // verified P4 suitability finding when outside the bounded queue.
  await page.getByLabel('TARGET VARIABLE').selectOption('feature');
  await expect(checkpoint).toContainText('not in the bounded P4 review queue');
  await checkpoint.getByRole('button',{name:'Clear selected target and preparation'}).click();
  await expect(page.getByLabel('TARGET VARIABLE')).toHaveValue('');
  await firstRow.getByRole('button',{name:'Review this alternative target'}).click();
  await section.getByRole('button',{name:'No prediction objective right now'}).click();
  await expect(page.getByLabel('TARGET VARIABLE')).toHaveValue('');
  await expect(section.getByText('No prediction target selected in this review.',{exact:false})).toBeVisible();
  await expect(checkpoint).toHaveCount(0);

  // No target automatically fit, no server-side train or mutation from this UI.
  expect(blocked).toEqual([]);
  const project=await request.get(`${API}/api/projects/${projectId}`);
  expect(project.status()).toBe(200);
  expect((await project.json()).experiments).toEqual([]);
 });

test('P4-06 real HTTP: explicit alternative business-context save promotes review only',async({page,context,request})=>{
 if(process.env.CI!=='true'||process.env.GITHUB_ACTIONS!=='true'||
    process.env.P1_REAL_HTTP_E2E!=='1'||!process.env.PILOTODIN_HOME)
  throw Error('Only trusted disposable GitHub browser tests may execute');
 const res=await request.post(API+'/api/projects',{multipart:{
  file:{name:'p4_06_disposable.csv',mimeType:'text/csv',buffer:Buffer.from(csv)},
 }});
 expect(res.status(),await res.text()).toBe(201);
 const projectId=(await res.json()).id as string;
 const permittedWrites:string[]=[];
 const blocked=await readOnlyBrowserGuard(context,projectId,permittedWrites);
 await page.addInitScript((id:string)=>{
  localStorage.setItem('pilotodin-current',id);
  localStorage.setItem('pilotodin-workspace-tabs-v1-'+id,JSON.stringify(['prepare']));
  localStorage.setItem('pilotodin-workspace-active-v1-'+id,'prepare');
 },projectId);
 await page.goto('/#/studio/prepare');
 const section=page.getByRole('region',{name:'Potential prediction opportunities'});
 await expect(section).toBeVisible();
 const other=section.locator('details[aria-label="Additional reviewable target alternatives"]');
 await other.locator(':scope > summary').click();
 const firstRow=other.locator('.warning-line').first();
 const column=(await firstRow.locator('strong').first().textContent())?.trim();
 expect(column).toBeTruthy();
 const editor=firstRow.locator('details.po-context-editor');
 await editor.locator('summary').click();
 const answers=editor.locator('textarea');
 await answers.nth(0).fill('The actual future expense for this synthetic operational record.');
 await answers.nth(1).fill('Support a human cost planning decision prior to final billing.');
 await answers.nth(2).fill('Before the eventual cost is recorded at the end of the period.');
 await answers.nth(3).fill('A simulated internal accounting ledger maintained by the business.');
 await editor.getByRole('button',{name:'Save user description'}).click();
 await expect(section.locator('article.model-choice').first()).toContainText(column!);
 const saved=await request.get(`${API}/api/projects/${projectId}/target-opportunities?expected_version=0`);
 expect(saved.status(),await saved.text()).toBe(200);
 const result=await saved.json();
 expect(result.suggestions[0].column).toBe(column);
 expect(result.suggestions[0].user_context.verification_state).toBe('user_described_not_independently_verified');
 expect(result.suggestions[0].safe_to_train_automatically).toBe(false);
 expect(permittedWrites).toEqual([`/api/projects/${projectId}/target-business-context`]);
 expect(blocked).toEqual([]);
 const project=await request.get(`${API}/api/projects/${projectId}`);
 expect((await project.json()).experiments).toEqual([]);
});
