import {test,expect} from '@playwright/test';
import type {BrowserContext,Locator,Route} from '@playwright/test';
import {Buffer} from 'node:buffer';
import {mkdtemp,rm} from 'node:fs/promises';
import {join} from 'node:path';
import {openP4FixtureWorkspace} from './p4-open-fixture-workspace.mjs';
import {p4PreparationRequestUrl} from './p4-preparation-request.mjs';
import {p4QualityFixture,verifyP4QualityAfterRelaunch,verifyP4QualityTransition} from './p4-quality-version-transition.mjs';
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

async function readOnlyBrowserGuard(context:BrowserContext,projectId:string,allowedContextWrites?:string[],extraProjectIds:string[]=[],qualityWrites?:string[]){
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
   const expected=[projectId,...extraProjectIds].some(id=>
    p===`/projects/${id}`||p.startsWith(`/projects/${id}/`))
    ||p==='/projects'||p==='/ai/settings';
   if(expected){await route.continue();return}
  }
  if(allowedContextWrites&&url.origin===API&&method==='POST'&&
     url.pathname===`/api/projects/${projectId}/target-business-context`){
   allowedContextWrites.push(url.pathname);
   await route.continue();return;
  }
  if(qualityWrites&&url.origin===API&&method==='POST'&&
     ['/proposals','/commit'].some(suffix=>url.pathname===`/api/projects/${projectId}/quality${suffix}`)){
   qualityWrites.push(url.pathname);
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

  // Match the native probe: the shell initially loads an empty catalogue.
  const [initialCatalogue]=await Promise.all([
   page.waitForResponse(response=>response.url()===API+'/api/projects'&&response.ok()),
   page.goto('/'),
  ]);
  expect(await initialCatalogue.json()).toEqual([]);
  await expect(page.getByRole('option',{name:'No projects imported yet'})).toBeAttached();

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
  await openP4FixtureWorkspace(page,UI,projectId);
  await expect(page.getByRole('combobox',{name:'Switch project'})).toHaveValue(projectId);
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
  await expect(checkpoint).toContainText('No supported outcome-name clue');
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


test('P4-09 real HTTP: project switch resets target review state',async({page,context,request})=>{
 if(process.env.CI!=='true'||process.env.GITHUB_ACTIONS!=='true'||
    process.env.P1_REAL_HTTP_E2E!=='1'||!process.env.PILOTODIN_HOME)
  throw Error('Only trusted disposable GitHub browser tests may execute');
 async function create(name:string,body:string){
  const response=await request.post(API+'/api/projects',{multipart:{
   file:{name,mimeType:'text/csv',buffer:Buffer.from(body)},
  }});
  expect(response.status(),await response.text()).toBe(201);
  return (await response.json()).id as string;
 }
 const regressionCsv=[
  'account_id,future_cost,feature',
  ...Array.from({length:80},(_,i)=>[
   'COST-'+Math.floor(i/2),120+i,i%9,
  ].join(',')),
 ].join('\n')+'\n';
 const unrelatedCsv=[
  'row_id,generic_measure,feature',
  ...Array.from({length:80},(_,i)=>['NEUTRAL-'+i,i*3,i%7].join(',')),
 ].join('\n')+'\n';
 const a=await create('p4_09_classification.csv',csv);
 const b=await create('p4_09_regression.csv',regressionCsv);
 const c=await create('p4_09_unrelated.csv',unrelatedCsv);
 for(const id of [a,b,c]){
  const stale=await request.get(
   `${API}/api/projects/${id}/target-opportunities?expected_version=1`);
  expect(stale.status()).toBe(409);
 }
 const blocked=await readOnlyBrowserGuard(context,a,undefined,[b,c]);
 await page.addInitScript((id:string)=>{
  localStorage.setItem('pilotodin-current',id);
  localStorage.setItem('pilotodin-workspace-tabs-v1-'+id,JSON.stringify(['prepare']));
  localStorage.setItem('pilotodin-workspace-active-v1-'+id,'prepare');
 },a);
 await page.goto('/#/studio/prepare');
 const section=page.getByRole('region',{name:'Potential prediction opportunities'});
 const chooser=page.getByRole('combobox',{name:'Switch project'});
 await expect(section).toBeVisible();
 await expect(chooser).toHaveValue(a);
 const original=section.locator('article.model-choice').first();
 await original.getByRole('button',{name:'Defer target in this review'}).click();
 await expect(original.getByText('Deferred for this review only.',{exact:false})).toBeVisible();
 page.on('dialog',dialog=>void dialog.accept());
 await chooser.selectOption(b);
 await expect(chooser).toHaveValue(b);
 await expect(page.getByLabel('TARGET VARIABLE')).toHaveValue('');
 await expect(section.locator('article.model-choice').first()).toContainText('future_cost');
 await expect(section.getByText('Deferred for this review only.',{exact:false})).toHaveCount(0);
 await section.getByRole('button',{name:'Review this target'}).first().click();
 await expect(section.getByRole('group',{name:'Selected target suitability checkpoint'}))
  .toContainText('future_cost');
 await chooser.selectOption(c);
 await expect(chooser).toHaveValue(c);
 await expect(page.getByLabel('TARGET VARIABLE')).toHaveValue('');
 await expect(section).toContainText(
  'No named outcome with sufficient technically supported labels was found');
 await expect(section.locator('article.model-choice')).toHaveCount(0);
 await section.getByRole('button',{name:'No prediction objective right now'}).click();
 await expect(section.getByText('No prediction target selected in this review.',{exact:false}))
  .toBeVisible();
 await chooser.selectOption(a);
 await expect(chooser).toHaveValue(a);
 await expect(page.getByLabel('TARGET VARIABLE')).toHaveValue('');
 await expect(section.getByText('Deferred for this review only.',{exact:false})).toHaveCount(0);
 await expect(section.getByRole('button',{name:'Review this target'}).first()).toBeVisible();
 for(const id of [a,b,c]){
  const response=await request.get(`${API}/api/projects/${id}`);
  expect(response.status()).toBe(200);
  expect((await response.json()).experiments).toEqual([]);
 }
 expect(blocked).toEqual([]);
});


test('P4-11 real HTTP: manual blocked target shows exact structural reasons',
 async({page,context,request})=>{
  if(process.env.CI!=='true'||process.env.GITHUB_ACTIONS!=='true'||
     process.env.P1_REAL_HTTP_E2E!=='1'||!process.env.PILOTODIN_HOME)
   throw Error('Only trusted disposable GitHub browser tests may execute');
  const rareCsv=[
   'account_id,churn,feature',
   ...Array.from({length:80},(_,i)=>[
    'P4-RARE-'+Math.floor(i/2),i<76?'Y':'N',i%8,
   ].join(',')),
  ].join('\n')+'\n';
  const upload=await request.post(API+'/api/projects',{multipart:{
   file:{name:'p4_11_rare.csv',mimeType:'text/csv',buffer:Buffer.from(rareCsv)},
  }});
  expect(upload.status(),await upload.text()).toBe(201);
  const projectId=(await upload.json()).id as string;
  const check=await request.get(
   `${API}/api/projects/${projectId}/target-opportunities?expected_version=0`);
  expect(check.status(),await check.text()).toBe(200);
  const result=await check.json();
  expect(result.abstained).toBe(true);
  expect(result.blocked_examples[0].column).toBe('churn');
  expect(result.blocked_examples[0].blockers.join(' ')).toContain('at least 6');
  const blocked=await readOnlyBrowserGuard(context,projectId);
  await page.addInitScript((id:string)=>{
   localStorage.setItem('pilotodin-current',id);
   localStorage.setItem('pilotodin-workspace-tabs-v1-'+id,JSON.stringify(['prepare']));
   localStorage.setItem('pilotodin-workspace-active-v1-'+id,'prepare');
  },projectId);
  await page.goto('/#/studio/prepare');
  const section=page.getByRole('region',{name:'Potential prediction opportunities'});
  await expect(section).toContainText('No named outcome with sufficient technically supported labels');
  await expect(section.locator('article.model-choice')).toHaveCount(0);
  const target=page.getByLabel('TARGET VARIABLE');
  await target.selectOption('churn'); // Explicit manual choice, not P4 approval.
  const checkpoint=section.getByRole('group',{name:'Selected target suitability checkpoint'});
  const structural=checkpoint.getByRole('alert',{name:'Selected target structural blockers'});
  await expect(structural).toContainText('Structurally blocked target');
  await expect(structural).toContainText('at least 6 labelled rows');
  await expect(checkpoint).toContainText('Technical screening: blocked');
  await checkpoint.getByRole('button',{name:'Clear selected target and preparation'}).click();
  await expect(target).toHaveValue('');
  await expect(checkpoint).toHaveCount(0);
  await target.selectOption('account_id'); // No screened outcome hint.
  await expect(checkpoint).toContainText('No supported outcome-name clue');
  await expect(checkpoint).toContainText('not recommended or approved for training');
  await checkpoint.getByRole('button',{name:'Clear selected target and preparation'}).click();
  expect(blocked).toEqual([]);
  const project=await request.get(`${API}/api/projects/${projectId}`);
  expect(project.status()).toBe(200);
  expect((await project.json()).experiments).toEqual([]);
 });


test('P4-12 real HTTP: out-of-cap manual target inspection and no writes',
 async({page,context,request})=>{
  if(process.env.CI!=='true'||process.env.GITHUB_ACTIONS!=='true'||
     process.env.P1_REAL_HTTP_E2E!=='1'||!process.env.PILOTODIN_HOME)
   throw Error('Only trusted disposable GitHub browser tests may execute');
  const headers=[
   'account_id','feature',
   ...Array.from({length:22},(_,i)=>'outcome_'+String(i).padStart(2,'0')),
   ...Array.from({length:6},(_,i)=>'rare_outcome_'+String(i).padStart(2,'0')),
  ];
  const rows=Array.from({length:80},(_,i)=>[
   'PRIVATE-SYNTH-'+Math.floor(i/2),String(i%9),
   ...Array.from({length:22},()=>i%2?'Y':'N'),
   ...Array.from({length:6},()=>i<76?'Y':'N'),
  ].join(','));
  const csvBody=[headers.join(','),...rows].join('\n')+'\n';
  const uploaded=await request.post(API+'/api/projects',{multipart:{
   file:{name:'p4_12_overflow.csv',mimeType:'text/csv',buffer:Buffer.from(csvBody)},
  }});
  expect(uploaded.status(),await uploaded.text()).toBe(201);
  const projectId=(await uploaded.json()).id as string;
  const normal=await request.get(
   `${API}/api/projects/${projectId}/target-opportunities?expected_version=0`);
  expect(normal.status(),await normal.text()).toBe(200);
  const ranked=await normal.json();
  expect(ranked.omitted_reviewable_count).toBe(7);
  expect(ranked.blocked_count).toBe(6);
  expect(ranked.blocked_examples.length).toBe(5);
  expect(ranked.suggestions.some((x:{column:string})=>x.column==='outcome_21')).toBe(false);
  const read=async(column:string)=>request.get(
   `${API}/api/projects/${projectId}/target-opportunities/inspect?expected_version=0&column=${column}`);
  expect((await read('outcome_21')).status()).toBe(200);
  expect((await read('rare_outcome_05')).status()).toBe(200);
  expect((await read('account_id')).status()).toBe(200);
  expect((await request.get(
   `${API}/api/projects/${projectId}/target-opportunities/inspect?expected_version=1&column=outcome_21`))
   .status()).toBe(409);
  const blocked=await readOnlyBrowserGuard(context,projectId);
  await page.addInitScript((id:string)=>{
   localStorage.setItem('pilotodin-current',id);
   localStorage.setItem('pilotodin-workspace-tabs-v1-'+id,JSON.stringify(['prepare']));
   localStorage.setItem('pilotodin-workspace-active-v1-'+id,'prepare');
  },projectId);
  await page.goto('/#/studio/prepare');
  const section=page.getByRole('region',{name:'Potential prediction opportunities'});
  await expect(section).toBeVisible();
  const choice=page.getByLabel('TARGET VARIABLE');
  const checkpoint=section.getByRole('group',{name:'Selected target suitability checkpoint'});
  await choice.selectOption('outcome_21');
  await expect(checkpoint).toContainText('On-demand single-column review');
  await expect(checkpoint).toContainText('Technical screening: reviewable');
  await expect(checkpoint.getByText('Structurally reviewable, not independently validated'))
   .toBeVisible();
  await checkpoint.locator('details[aria-label="On-demand selected target evidence"] summary').click();
  await expect(checkpoint.getByLabel('Decision usefulness evidence'))
   .toContainText('Decision usefulness: not established');
  await choice.selectOption('rare_outcome_05');
  await expect(checkpoint.getByRole('alert',{name:'Selected target structural blockers'}))
   .toContainText('at least 6 labelled rows');
  await choice.selectOption('account_id');
  await expect(checkpoint.getByRole('alert',{name:'Selected target structural blockers'}))
   .toContainText('No supported outcome-name clue');
  await expect(checkpoint.getByRole('alert',{name:'Selected target structural blockers'}))
   .toContainText('identifier');
  await checkpoint.getByRole('button',{name:'Clear selected target and preparation'}).click();
  await expect(choice).toHaveValue('');
  await expect(checkpoint).toHaveCount(0);
  expect(blocked).toEqual([]);
  const project=await request.get(`${API}/api/projects/${projectId}`);
  expect(project.status()).toBe(200);
  expect((await project.json()).experiments).toEqual([]);
 });


test('P4-13 real HTTP: wide target inspection displays bounded incomplete status',
 async({page,context,request})=>{
  if(process.env.CI!=='true'||process.env.GITHUB_ACTIONS!=='true'||
     process.env.P1_REAL_HTTP_E2E!=='1'||!process.env.PILOTODIN_HOME)
   throw Error('Trusted synthetic CI only');
  const headers=[
   'account_id',
   ...Array.from({length:36},(_,i)=>'feature_'+String(i).padStart(2,'0')),
   ...Array.from({length:17},(_,i)=>'outcome_'+String(i).padStart(2,'0')),
   'outcome_99',
  ];
  const rows=Array.from({length:80},(_,i)=>[
   'ID-'+Math.floor(i/2),
   ...Array.from({length:36},(_,j)=>String((i+j)%13)),
   ...Array.from({length:17},()=>i%2?'Y':'N'),
   i%2?'Y':'N',
  ].join(','));
  const upload=await request.post(API+'/api/projects',{multipart:{
   file:{name:'p4_13_synthetic_wide.csv',mimeType:'text/csv',
    buffer:Buffer.from([headers.join(','),...rows].join('\n')+'\n')},
  }});
  expect(upload.status(),await upload.text()).toBe(201);
  const projectId=(await upload.json()).id as string;
  const response=await request.get(
   `${API}/api/projects/${projectId}/target-opportunities?expected_version=0`);
  expect(response.status(),await response.text()).toBe(200);
  const shortlist=await response.json();
  expect(shortlist.omitted_reviewable_count).toBe(3);
  const detail=await request.get(
   `${API}/api/projects/${projectId}/target-opportunities/inspect?expected_version=0&column=outcome_99`);
  expect(detail.status(),await detail.text()).toBe(200);
  const inspected=await detail.json();
  expect(inspected.resource_review.truncated).toBe(true);
  expect(inspected.resource_review.rows_examined).toBe(80);
  expect(inspected.resource_review.total_rows).toBe(80);
  expect(inspected.resource_review.columns_examined).toBe(33);
  expect(inspected.resource_review.total_columns).toBe(55);
  expect(inspected.resource_review.predictor_columns_examined).toBe(32);
  expect(inspected.resource_review.total_predictor_columns).toBe(54);
  expect(inspected.candidate.technical_status).toBe('blocked');
  expect(inspected.training_authorised).toBe(false);
  const blocked=await readOnlyBrowserGuard(context,projectId);
  await page.addInitScript((id:string)=>{
   localStorage.setItem('pilotodin-current',id);
   localStorage.setItem('pilotodin-workspace-tabs-v1-'+id,JSON.stringify(['prepare']));
   localStorage.setItem('pilotodin-workspace-active-v1-'+id,'prepare');
  },projectId);
  await page.goto('/#/studio/prepare');
  const section=page.getByRole('region',{name:'Potential prediction opportunities'});
  await expect(section).toBeVisible();
  await page.getByLabel('TARGET VARIABLE').selectOption('outcome_99');
  const checkpoint=section.getByRole('group',{name:'Selected target suitability checkpoint'});
  const coverage=checkpoint.getByRole('note',{name:'Bounded manual screening coverage'});
  await expect(coverage).toContainText('Incomplete structural scan: not approved');
  await expect(coverage).toContainText('other columns checked: 32 of 54');
  await expect(coverage).toContainText('Label counts below are sample-only');
  await expect(checkpoint.getByRole('alert',{name:'Selected target structural blockers'}))
   .toContainText('truncated by its row or predictor-column budget');
  await checkpoint.getByRole('button',{name:'Clear selected target and preparation'}).click();
  await expect(checkpoint).toHaveCount(0);
  expect(blocked).toEqual([]);
  const project=await request.get(`${API}/api/projects/${projectId}`);
  expect(project.status()).toBe(200);
  expect((await project.json()).experiments).toEqual([]);
 });


test('P4-14 real HTTP: incomplete wide queue abstains without recommending',
 async({page,context,request})=>{
  if(process.env.CI!=='true'||process.env.GITHUB_ACTIONS!=='true'||
     process.env.P1_REAL_HTTP_E2E!=='1'||!process.env.PILOTODIN_HOME)
   throw Error('Only trusted disposable GitHub browser tests may execute');
  const header=[
   'account_id','churn',
   ...Array.from({length:70},(_,i)=>'feature_'+String(i).padStart(2,'0')),
  ];
  const rows=Array.from({length:80},(_,i)=>[
   'PRIVATE-TEST-'+Math.floor(i/2),i%2?'Y':'N',
   ...Array.from({length:70},(_,j)=>String((i+j)%11)),
  ].join(','));
  const csvBody=[header.join(','),...rows].join('\n')+'\n';
  const uploaded=await request.post(API+'/api/projects',{multipart:{
   file:{name:'p4_14_wide_queue.csv',mimeType:'text/csv',buffer:Buffer.from(csvBody)},
  }});
  expect(uploaded.status(),await uploaded.text()).toBe(201);
  const projectId=(await uploaded.json()).id as string;
  const reply=await request.get(
   `${API}/api/projects/${projectId}/target-opportunities?expected_version=0`);
  expect(reply.status(),await reply.text()).toBe(200);
  const ranking=await reply.json();
  expect(ranking.abstained).toBe(true);
  expect(ranking.suggestions).toEqual([]);
  expect(ranking.other_reviewable).toEqual([]);
  expect(ranking.queue_resource_review.truncated).toBe(true);
  expect(ranking.queue_resource_review.incomplete_reasons).toContain('predictors');
  expect(ranking.queue_resource_review.rows_examined).toBe(80);
  expect(ranking.queue_resource_review.headers_examined).toBe(72);
  expect(ranking.queue_resource_review.candidate_columns_examined).toBe(1);
  expect(ranking.blocked_examples[0].technical_status).toBe('blocked');
  const blocked=await readOnlyBrowserGuard(context,projectId);
  await page.addInitScript((id:string)=>{
   localStorage.setItem('pilotodin-current',id);
   localStorage.setItem('pilotodin-workspace-tabs-v1-'+id,JSON.stringify(['prepare']));
   localStorage.setItem('pilotodin-workspace-active-v1-'+id,'prepare');
  },projectId);
  await page.goto('/#/studio/prepare');
  const section=page.getByRole('region',{name:'Potential prediction opportunities'});
  const banner=section.getByRole('alert',{name:'Incomplete target recommendation screening'});
  await expect(banner).toContainText('Incomplete target screening: no recommended target');
  await expect(banner).toContainText('headers examined: 72 of 72');
  await expect(section.locator('article.model-choice')).toHaveCount(0);
  await page.getByLabel('TARGET VARIABLE').selectOption('churn');
  const checkpoint=section.getByRole('group',{name:'Selected target suitability checkpoint'});
  await expect(checkpoint.getByRole('alert',{name:'Selected target structural blockers'}))
   .toContainText('Main target review queue scan was truncated');
  await checkpoint.getByRole('button',{name:'Clear selected target and preparation'}).click();
  await expect(checkpoint).toHaveCount(0);
  expect(blocked).toEqual([]);
  const project=await request.get(`${API}/api/projects/${projectId}`);
  expect(project.status()).toBe(200);
  expect((await project.json()).experiments).toEqual([]);
 });


test('P4-15 real HTTP: consolidated incomplete-queue and project isolation',
 async({page,context,request})=>{
  if(process.env.CI!=='true'||process.env.GITHUB_ACTIONS!=='true'||
     process.env.P1_REAL_HTTP_E2E!=='1'||!process.env.PILOTODIN_HOME)
   throw Error('Only trusted disposable GitHub browser tests may execute');
  async function upload(name:string,body:string){
   const res=await request.post(API+'/api/projects',{multipart:{
    file:{name,mimeType:'text/csv',buffer:Buffer.from(body)},
   }});
   expect(res.status(),await res.text()).toBe(201);
   return (await res.json()).id as string;
  }
  const wideHeaders=[
   'account_id','churn',
   ...Array.from({length:70},(_,i)=>'feature_'+String(i).padStart(2,'0')),
  ];
  const wideCsv=[
   wideHeaders.join(','),
   ...Array.from({length:80},(_,i)=>[
    'SYNTH-P415-'+Math.floor(i/2),i%2?'Y':'N',
    ...Array.from({length:70},(_,j)=>String((i+j)%11)),
   ].join(',')),
  ].join('\n')+'\n';
  const regressionCsv=[
   'account_id,future_cost,feature',
   ...Array.from({length:80},(_,i)=>[
    'SYNTH-COST-'+Math.floor(i/2),100+i,i%7,
   ].join(',')),
  ].join('\n')+'\n';
  const a=await upload('p4_15_wide_only.csv',wideCsv);
  const b=await upload('p4_15_regression_only.csv',regressionCsv);
  const reviewA=await request.get(
   `${API}/api/projects/${a}/target-opportunities?expected_version=0`);
  expect(reviewA.status(),await reviewA.text()).toBe(200);
  expect((await reviewA.json()).queue_resource_review.truncated).toBe(true);
  const reviewB=await request.get(
   `${API}/api/projects/${b}/target-opportunities?expected_version=0`);
  expect(reviewB.status(),await reviewB.text()).toBe(200);
  const bInfo=await reviewB.json();
  expect(bInfo.queue_resource_review.truncated).toBe(false);
  expect(bInfo.suggestions[0].column).toBe('future_cost');
  const stale=await request.get(
   `${API}/api/projects/${b}/target-opportunities/inspect?expected_version=1&column=future_cost`);
  expect(stale.status()).toBe(409);
  const foreign=await request.get(
   `${API}/api/projects/${a}/target-opportunities/inspect?expected_version=0&column=churn`,
   {headers:{Origin:'https://external.example'}});
  expect(foreign.status()).toBe(403);
  const blocked=await readOnlyBrowserGuard(context,a,undefined,[b]);
  await page.addInitScript((id:string)=>{
   localStorage.setItem('pilotodin-current',id);
   localStorage.setItem('pilotodin-workspace-tabs-v1-'+id,JSON.stringify(['prepare']));
   localStorage.setItem('pilotodin-workspace-active-v1-'+id,'prepare');
  },a);
  await page.goto('/#/studio/prepare');
  const chooser=page.getByRole('combobox',{name:'Switch project'});
  const section=page.getByRole('region',{name:'Potential prediction opportunities'});
  const checkpoint=section.getByRole('group',{name:'Selected target suitability checkpoint'});
  const target=page.getByLabel('TARGET VARIABLE');
  await expect(chooser).toHaveValue(a);
  await expect(section.getByRole('alert',{name:'Incomplete target recommendation screening'}))
   .toContainText('no recommended target');
  await expect(section.locator('article.model-choice')).toHaveCount(0);
  await target.selectOption('churn');
  await expect(checkpoint.getByRole('alert',{name:'Selected target structural blockers'}))
   .toContainText('Main target review queue scan was truncated');
  page.on('dialog',dialog=>void dialog.accept());
  await chooser.selectOption(b);
  await expect(chooser).toHaveValue(b);
  await expect(target).toHaveValue('');
  await expect(checkpoint).toHaveCount(0);
  await expect(section.getByRole('alert',{name:'Incomplete target recommendation screening'}))
   .toHaveCount(0);
  await expect(section.locator('article.model-choice').first()).toContainText('future_cost');
  await section.getByRole('button',{name:'Review this target'}).first().click();
  await expect(checkpoint).toContainText('future_cost');
  await section.getByRole('button',{name:'No prediction objective right now'}).click();
  await expect(target).toHaveValue('');
  await chooser.selectOption(a);
  await expect(chooser).toHaveValue(a);
  await expect(target).toHaveValue('');
  await expect(checkpoint).toHaveCount(0);
  await expect(section.getByRole('alert',{name:'Incomplete target recommendation screening'}))
   .toContainText('no recommended target');
  expect(blocked).toEqual([]);
  for(const id of [a,b]){
   const project=await request.get(`${API}/api/projects/${id}`);
   expect(project.status()).toBe(200);
   expect((await project.json()).experiments).toEqual([]);
  }
 });

test('P4 N10 real HTTP: no-named-target manual review remains vertically readable and blocked',
 async({page,context,request})=>{
  if(process.env.CI!=='true'||process.env.GITHUB_ACTIONS!=='true'||
     process.env.P1_REAL_HTTP_E2E!=='1'||!process.env.PILOTODIN_HOME)
   throw Error('Only trusted disposable GitHub browser tests may execute');
  const synthetic=[
   'account_id,feature,generic_measure',
   ...Array.from({length:80},(_,i)=>[
    'SYNTH-N10-'+Math.floor(i/2),i%9,i*3,
   ].join(',')),
  ].join('\n')+'\n';
  const res=await request.post(API+'/api/projects',{multipart:{
   file:{name:'p4_n10_disposable.csv',mimeType:'text/csv',buffer:Buffer.from(synthetic)},
  }});
  expect(res.status(),await res.text()).toBe(201);
  const projectId=(await res.json()).id as string;
  const blocked=await readOnlyBrowserGuard(context,projectId);
  await page.addInitScript((id:string)=>{
   localStorage.setItem('pilotodin-current',id);
   localStorage.setItem('pilotodin-workspace-tabs-v1-'+id,JSON.stringify(['prepare']));
   localStorage.setItem('pilotodin-workspace-active-v1-'+id,'prepare');
  },projectId);
  await page.goto('/#/studio/prepare');
  const section=page.getByRole('region',{name:'Potential prediction opportunities'});
  const checkpoint=section.getByRole('group',{name:'Selected target suitability checkpoint'});
  await expect(section).toContainText(
   'No named outcome with sufficient technically supported labels was found');
  await expect(checkpoint).toHaveCount(0);
  await section.getByRole('button',{name:'No prediction objective right now'}).click();
  await expect(section).toContainText('Preparation is cleared');
  await page.getByLabel('TARGET VARIABLE').selectOption('generic_measure');
  await expect(checkpoint).toBeVisible();
  const coverage=checkpoint.getByRole('note',{name:'Bounded manual screening coverage'});
  const warning=checkpoint.getByRole('alert',{name:'Selected target structural blockers'});
  await expect(coverage).toContainText('Full structural scan');
  await expect(warning).toContainText(
   'Structurally blocked target: not recommended or approved for training');
  await expect(checkpoint).toHaveCSS('display','block');
  for(const width of [1440,1100]){
   await page.setViewportSize({width,height:900});
   await expect(checkpoint).toBeVisible();
   const layout=await checkpoint.evaluate((node)=>{
    const selected=[
     node.querySelector(':scope > p'),
     node.querySelector(':scope > [role="note"]'),
     node.querySelector(':scope > [role="alert"]'),
     node.querySelector(':scope > button'),
    ];
    if(selected.some(item=>!item))return {valid:false,vertical:false,overflow:true};
    const boxes=selected.map(item=>item!.getBoundingClientRect());
    return {
     valid:true,
     vertical:boxes.slice(1).every((box,i)=>box.top>=boxes[i].bottom-2),
     overflow:node.scrollWidth>node.clientWidth+2,
    };
   });
   expect(layout.valid).toBe(true);
   expect(layout.vertical).toBe(true);
   expect(layout.overflow).toBe(false);
  }
  await checkpoint.getByRole('button',{name:'Clear selected target and preparation'}).click();
  await expect(checkpoint).toHaveCount(0);
  expect(blocked).toEqual([]);
  const project=await request.get(`${API}/api/projects/${projectId}`);
  expect(project.status()).toBe(200);
  expect((await project.json()).experiments).toEqual([]);
 });
 
test('P4-62 real HTTP: high-risk Prepare suggestions preview, cancel and additive apply',
 async({page,context,request})=>{
  if(process.env.CI!=='true'||process.env.GITHUB_ACTIONS!=='true'||
     process.env.P1_REAL_HTTP_E2E!=='1'||!process.env.PILOTODIN_HOME)
    throw Error('Only trusted disposable GitHub browser tests may execute');
  const fixture=[
    'TransactionID,churn,event_type,amount',
    ...Array.from({length:80},(_,i)=>[
      'SYNTH-'+String(i).padStart(3,'0'),i%2?'Y':'N',
      i===1?'':i%3?'service':'retail',100+i,
    ].join(',')),
  ].join('\n')+'\n';
  const uploaded=await request.post(API+'/api/projects',{multipart:{
    file:{name:'p4_62_exclusion_review.csv',mimeType:'text/csv',buffer:Buffer.from(fixture)}
  }});
  expect(uploaded.status(),await uploaded.text()).toBe(201);
  const projectId=(await uploaded.json()).id as string;
  const blocked=await readOnlyBrowserGuard(context,projectId);
  await page.addInitScript((id:string)=>{
    localStorage.setItem('pilotodin-current',id);
    localStorage.setItem('pilotodin-workspace-tabs-v1-'+id,JSON.stringify(['prepare']));
    localStorage.setItem('pilotodin-workspace-active-v1-'+id,'prepare');
  },projectId);
  await page.goto('/#/studio/prepare');
  await page.getByLabel('TARGET VARIABLE').selectOption('churn');
  const risk=page.locator('.feature-chip').filter({hasText:'TransactionID'}).getByRole('checkbox');
  const manual=page.locator('.feature-chip').filter({hasText:'event_type'}).getByRole('checkbox');
  await expect(risk).toBeVisible();
  await expect(risk).not.toBeChecked();
  const resource=page.locator('.po-ml-resource-plan');
  await expect(resource).toContainText('28 estimated encoded columns');
  // P4-74: the version-pinned backend plan must agree with the visible audit
  // before and after user choices. No model fit or writable project endpoints.
  const plan=await request.get(p4PreparationRequestUrl(API+'/api',projectId,'churn',0));
  expect(plan.status(),await plan.text()).toBe(200);
  const planJson=await plan.json();
  expect(planJson.quality_version).toBe(0);
  expect(planJson.target).toBe('churn');
  expect(planJson.feature_audit.find((entry:{column:string})=>entry.column==='TransactionID')).toMatchObject({risk:'high',category_examples:[]});
  expect(planJson.feature_audit.find((entry:{column:string})=>entry.column==='event_type')?.category_examples).toEqual(['retail','service']);
  const advice=await request.get(`${API}/api/projects/${projectId}/features?target=churn&expected_version=0`);
  expect(advice.status(),await advice.text()).toBe(200);
  const adviceJson=await advice.json();
  expect(adviceJson.version).toBe(0);
  expect(adviceJson.features.find((entry:{column:string})=>entry.column==='TransactionID')?.risk).toBe('high');
  const mismatchedPlan=await request.get(p4PreparationRequestUrl(API+'/api',projectId,'churn',1));
  expect(mismatchedPlan.status(),await mismatchedPlan.text()).toBe(409);
  const staleAdvice=await request.get(`${API}/api/projects/${projectId}/features?target=churn&expected_version=1`);
  expect(staleAdvice.status(),await staleAdvice.text()).toBe(409);
  const audit=page.locator('.po-ml-feature-audit tbody');
  const transactionRow=audit.locator('tr').filter({hasText:'TransactionID'});
  const eventRow=audit.locator('tr').filter({hasText:'event_type'});
  const amountRow=audit.locator('tr').filter({hasText:'amount'});
  await expect(page.getByRole('heading',{name:'Feature-by-feature preparation audit'})).toBeVisible();
  await expect(transactionRow).toContainText('Included predictor');
  await expect(transactionRow).toContainText('High — review required');
  await expect(transactionRow).toContainText('Categorical: mode imputation');
  await expect(transactionRow).toContainText('Examples hidden for high-risk fields');
  await expect(transactionRow).not.toContainText('SYNTH-000');
  await expect(eventRow).toContainText('Observed examples (2 of 2) "retail", "service"');
  await expect(amountRow).not.toContainText('Observed examples');
  const width = (row: Locator) => row.locator('.po-ml-encoded-width');
  await expect(width(transactionRow)).toHaveText('Estimated encoded columns: 25');
  await expect(width(eventRow)).toHaveText('Estimated encoded columns: 2');
  await expect(width(amountRow)).toHaveText('Estimated encoded columns: 1');
   const categoricalStrategy=page.getByLabel('Categorical imputation method');
   await expect(categoricalStrategy).toHaveValue('most_frequent');
   await categoricalStrategy.selectOption('constant');
   await expect(transactionRow).toContainText('Categorical: missing-marker imputation');
   await expect(width(eventRow)).toHaveText('Estimated encoded columns: 3');
   await expect(resource).toContainText('29 estimated encoded columns');
   await expect(page.locator('.panel.insight').filter({hasText:'Automatic preprocessing plan'}))
     .toContainText('Categorical: training-fold missing-marker imputation');
   await categoricalStrategy.selectOption('most_frequent');
   await expect(transactionRow).toContainText('Categorical: mode imputation');
   await expect(width(eventRow)).toHaveText('Estimated encoded columns: 2');
   await expect(resource).toContainText('28 estimated encoded columns');
  await expect(eventRow).toContainText('Included predictor');
  await expect(amountRow).toContainText('Numeric: median imputation');
  const numericStrategy=page.getByLabel('Numeric imputation method');
  await expect(numericStrategy).toHaveValue('median');
  await numericStrategy.selectOption('mean');
  await expect(amountRow).toContainText('Numeric: mean imputation');
  await expect(page.locator('.panel.insight').filter({hasText:'Automatic preprocessing plan'}))
    .toContainText('Numeric: training-fold mean imputation');
  await numericStrategy.selectOption('median');
  await expect(amountRow).toContainText('Numeric: median imputation');
  await manual.check();
  await expect(resource).toContainText('26 estimated encoded columns');
  await expect(eventRow).toContainText('Excluded by user');
  await expect(eventRow).toContainText('No training transform');
  await expect(width(eventRow)).toHaveText('Estimated encoded columns: 0');
  await expect(transactionRow).toContainText('Included predictor');
  const reviewButton=page.getByRole('button',{name:'Review high-risk exclusion suggestions'});
  await reviewButton.click();
  const preview=page.getByRole('group',{name:'Review proposed high-risk exclusions'});
  await expect(preview).toContainText('Will additionally exclude (1): TransactionID');
  await expect(preview).toContainText('Already excluded, kept unchanged (1): event_type');
  await expect(preview).toContainText('Included predictors: 2 before, 1 after');
  await expect(risk).not.toBeChecked();
  await preview.getByRole('button',{name:'Cancel exclusion review'}).click();
  await expect(preview).toHaveCount(0);
  await expect(manual).toBeChecked();
  await expect(risk).not.toBeChecked();
  await reviewButton.click();
  await preview.getByRole('button',{name:'Apply reviewed exclusions'}).click();
  await expect(preview).toHaveCount(0);
  await expect(risk).toBeChecked();
  await expect(manual).toBeChecked();
  await expect(resource).toContainText('1 estimated encoded columns');
  await expect(transactionRow).toContainText('Excluded by user');
  await expect(transactionRow).toContainText('No training transform');
  await expect(width(transactionRow)).toHaveText('Estimated encoded columns: 0');
  await expect(eventRow).toContainText('Excluded by user');
  await expect(amountRow).toContainText('Included predictor');
  await expect(amountRow).toContainText('Numeric: median imputation');
  const included=page.locator('.mini-info').filter({hasText:'candidate predictors'});
  await expect(included).toContainText('3 candidate predictors');
  await expect(included).toContainText('1 currently included');
  await expect(included).toContainText('0 included high-risk predictors');
  expect(blocked).toEqual([]);
  const p=await request.get(API+'/api/projects/'+projectId);
  expect(p.status()).toBe(200);
  expect((await p.json()).experiments).toEqual([]);
 });


test('P4-79 real HTTP: reopened experiment settings are read from saved record, never Prepare draft',
 async({page,context,request})=>{
  if(process.env.CI!=='true'||process.env.GITHUB_ACTIONS!=='true'||
     process.env.P1_REAL_HTTP_E2E!=='1'||!process.env.PILOTODIN_HOME)
    throw Error('Only trusted disposable GitHub browser tests may execute');

  // Create only a disposable project. The apparent experiment records below
  // are GET-only route fixtures; do not queue, fit or persist ANY model.
  const uploaded=await request.post(API+'/api/projects',{multipart:{
    file:{name:'p4_79_history_read_only.csv',mimeType:'text/csv',buffer:Buffer.from(csv)}
  }});
  expect(uploaded.status(),await uploaded.text()).toBe(201);
  const projectId=(await uploaded.json()).id as string;
  const chosenId='a'.repeat(32),legacyId='b'.repeat(32);
  const fakeHistory=[
    {id:chosenId,status:'completed',selected_model:'logistic_regression',created_at:'2026-11-12T12:00:00Z'},
    {id:legacyId,status:'failed',selected_model:null,created_at:'2026-11-11T12:00:00Z'}
  ];
  const saved={
    id:chosenId,project_id:projectId,status:'completed',
    config:{target:'churn',task:'classification',excluded:[],models:['logistic_regression'],
      quality_version:0,split_strategy:'random',split_column:null,
      numeric_imputation:'mean',categorical_imputation:'constant'},
    results:{task:'classification',target:'churn',features:['feature'],excluded_features:[],
      labelled_rows:80,train_rows:64,test_rows:16,folds:5,
      primary_metric:'F1 macro',baseline_cv:0.5,beats_baseline:true,
      models:[{key:'logistic_regression',name:'Logistic Regression',
        cv_metric:0.75,cv_std:0.02,status:'ready'}],
      input_schema:[{name:'feature',kind:'number',required:false}],
      warning:'Synthetic display fixture only'},
    error:null,selected_model:'logistic_regression',final_results:null,is_stale:false
  };
  const legacy={
    id:legacyId,project_id:projectId,status:'failed',
    config:{target:'churn',task:'classification',excluded:[],models:['logistic_regression'],
      quality_version:0,split_strategy:'random',split_column:null},
    results:null,error:'Synthetic no-fit test record',selected_model:null,
    final_results:null,is_stale:false
  };
  const intercepted:string[]=[];
  const blocked=await readOnlyBrowserGuard(context,projectId);
  // Last registered Playwright handler runs first. Pass all unrelated requests
  // through the strict browser read-only allowlist above.
  await context.route('**/api/**',async route=>{
    const req=route.request(),url=new URL(req.url());
    if(req.method()!=='GET'||url.origin!==API){await route.fallback();return}
    if(url.pathname===`/api/projects/${projectId}`){
      const actual=await route.fetch();
      expect(actual.status()).toBe(200);
      const genuine=await actual.json();
      intercepted.push('project-list');
      await route.fulfill({response:actual,json:{...genuine,experiments:fakeHistory}});
      return;
    }
    if(url.pathname===`/api/experiments/${chosenId}`||
       url.pathname===`/api/experiments/${legacyId}`){
      intercepted.push(url.pathname.endsWith(chosenId)?'explicit-record':'legacy-record');
      await route.fulfill({status:200,contentType:'application/json',
        body:JSON.stringify(url.pathname.endsWith(chosenId)?saved:legacy)});
      return;
    }
    await route.fallback();
  });
  await page.addInitScript((id:string)=>{
    localStorage.setItem('pilotodin-current',id);
    localStorage.setItem('pilotodin-workspace-tabs-v1-'+id,JSON.stringify(['evaluate']));
    localStorage.setItem('pilotodin-workspace-active-v1-'+id,'evaluate');
  },projectId);
  await page.goto('/#/studio/evaluate');
  const history=page.locator('button.mini-experiment');
  await expect(history).toHaveCount(2);
  // A historical failed attempt does not imply any model was fitted.
  await history.nth(1).click();
  const audit=page.getByRole('region',{name:'Recorded experiment preprocessing'});
  await expect(audit).toContainText('Median (legacy default; not recorded)');
  await expect(audit).toContainText('Mode (legacy default; not recorded)');
  await expect(audit).toContainText('working data version v0');
  await expect(audit).toContainText('not the current Prepare draft or independent proof');
  await expect(page.getByRole('heading',{name:'Training failed'})).toBeVisible();

  // Reload Evaluate to start a fresh read-only session, then reopen the
  // explicitly configured record from the saved-history list. This avoids
  // depending on a shell navigation control outside the targeted P4 view.
  await page.reload();
  await expect(history).toHaveCount(2);
  await history.first().click();
  await expect(audit).toContainText('Numeric missing values: Mean');
  await expect(audit).toContainText('Categorical missing values: Reserved missing marker');
  await expect(audit).not.toContainText('legacy default');
  await page.getByRole('button',{name:'Open Predict Studio'}).click();
  await expect(audit).toContainText('Numeric missing values: Mean');
  await expect(audit).toContainText('Categorical missing values: Reserved missing marker');
  // No prediction or fit action is ever invoked in this display-only check.
  expect(intercepted).toContain('project-list');
  expect(intercepted).toContain('legacy-record');
  expect(intercepted).toContain('explicit-record');
  expect(blocked).toEqual([]);
  const realProject=await request.get(`${API}/api/projects/${projectId}`);
  expect(realProject.status(),await realProject.text()).toBe(200);
  expect((await realProject.json()).experiments).toEqual([]);
 });

test('P4 N11 real HTTP: Quality approval refreshes Prepare and survives a browser restart',async({playwright,request})=>{
  if(process.env.CI!=='true'||process.env.GITHUB_ACTIONS!=='true'||
     process.env.P1_REAL_HTTP_E2E!=='1'||!process.env.PILOTODIN_HOME)
    throw Error('Trusted synthetic CI only');

  const initial=await request.post(API+'/api/projects',{multipart:{
    file:{name:'p4_n11_initial.csv',mimeType:'text/csv',buffer:Buffer.from(csv)},
  }});
  expect(initial.status(),await initial.text()).toBe(201);
  const {id:initialId}=await initial.json();
  const uploaded=await request.post(API+'/api/projects',{multipart:{
    file:{name:'p4_n11_disposable.csv',mimeType:'text/csv',buffer:Buffer.from(p4QualityFixture)},
  }});
  expect(uploaded.status(),await uploaded.text()).toBe(201);
  const {id:projectId}=await uploaded.json();
  const writes:string[]=[];
  const profile=await mkdtemp(join(process.env.RUNNER_TEMP!,'pilotodin-p4-n11-chromium-'));
  const launch=()=>playwright.chromium.launchPersistentContext(profile,{
    baseURL:UI,serviceWorkers:'block',viewport:{width:1440,height:900},
  });
  try{
    const context=await launch();
    try{
      const blocked=await readOnlyBrowserGuard(context,projectId,undefined,[initialId],writes);
      const [page]=context.pages();
      await page.goto('/');
      await openP4FixtureWorkspace(page,UI,initialId);
      const chooser=page.getByRole('combobox',{name:'Switch project'});
      await expect(chooser).toHaveValue(initialId);
      await expect(page.getByRole('region',{name:'Potential prediction opportunities'})).toContainText('churn');
      await chooser.selectOption(projectId);
      await verifyP4QualityTransition(page,API+'/api',projectId,async(url:string)=>{
        const response=await request.get(url);
        return {status:response.status(),json:()=>response.json()};
      });
      expect(writes).toEqual([
        `/api/projects/${projectId}/quality/proposals`,
        `/api/projects/${projectId}/quality/commit`,
      ]);
      expect(blocked).toEqual([]);
    }finally{await context.close()}

    const reopened=await launch();
    try{
      const blocked=await readOnlyBrowserGuard(reopened,projectId,undefined,[initialId]);
      const [page]=reopened.pages();
      // Start from the desktop's root URL without seeding the project's saved state.
      await page.goto('/');
      await verifyP4QualityAfterRelaunch(page,API+'/api',projectId);
      expect(blocked).toEqual([]);
      const project=await request.get(`${API}/api/projects/${projectId}`);
      expect(project.status()).toBe(200);
      expect((await project.json()).experiments).toEqual([]);
    }finally{await reopened.close()}
  }finally{await rm(profile,{recursive:true,force:true})}
});
