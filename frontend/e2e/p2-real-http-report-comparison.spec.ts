import {test,expect} from '@playwright/test';
import type {BrowserContext,Route} from '@playwright/test';
import {Buffer} from 'node:buffer';
import {startDisposableBackend,stopDisposableBackend} from './p1-real-http-backend';
import type {DisposableBackend} from './p1-real-http-backend';

// One owned, temporary Uvicorn on CI :8000, dedicated Vite :5178.
// All source CSV/report revisions are synthetic and only CI-runner-local.
// Browser can READ the reviewed report paths but cannot mutate API state.
const API='http://127.0.0.1:8000';
const UI='http://127.0.0.1:5178';
const csv=[
 'OrderID,Region,Revenue',
 '0001,West,120.00',
 '0002,East,220.00',
 '0003,West,140.00',
 '0004,North,180.00',
 '0005,East,230.00',
].join('\n')+'\n';

type ReadAudit={reads:string[];readOnlyCalculations:number;unexpected:string[];blockedWrites:string[];remote:string[]};
async function protectBrowser(context:BrowserContext,pid:string,rid:string,evidenceIds:string[]):Promise<ReadAudit>{
 const audit:ReadAudit={reads:[],readOnlyCalculations:0,unexpected:[],blockedWrites:[],remote:[]};
 await context.route('**/*',async(route:Route)=>{
  const request=route.request(),url=new URL(request.url()),method=request.method();
  if(url.origin===UI){
   if(method==='GET'||method==='HEAD'){await route.continue();return;}
   audit.blockedWrites.push(method+' '+url.pathname+' [UI]');
   await route.fulfill({status:403,json:{detail:'Unapproved browser write'}});return;
  }
  if(method==='GET'&&url.origin==='https://fonts.googleapis.com'&&url.pathname==='/css2'){
   // No remote font downloads or page-origin credential propagation in CI.
   await route.fulfill({status:200,contentType:'text/css',body:'/* local system font substitute */'});return;
  }
  if(url.origin!==API||!url.pathname.startsWith('/api/')){
   audit.remote.push(method+' '+url.origin+url.pathname);
   await route.abort('blockedbyclient');return;
  }
  const path=url.pathname.slice(4),query=[...url.searchParams.entries()];
  // This POST is a strictly read-only analytical workbench computation on
  // the disposable project, never a saved report/evidence mutation.
  if(method==='POST'&&url.search===''&&path===`/projects/${pid}/explore/workbench`){
   const body=request.postDataJSON();
   if(body&&body.expected_version===0&&Array.isArray(body.filters)&&body.filters.length<=4&&
       typeof body.x==='string'&&body.x.length<=256&&typeof body.kind==='string'){
    audit.readOnlyCalculations++;
    await route.continue();return;
   }
   audit.blockedWrites.push('Unapproved workbench calculation');
   await route.fulfill({status:403,json:{detail:'Unapproved calculation'}});return;
  }
  const read=method==='GET'&&(
   (url.pathname.startsWith(`/api/projects/${pid}/explore/`)||
   (url.search===''&&['/projects','/ai/settings',
      `/projects/${pid}`,`/projects/${pid}/live-profile`,
      `/projects/${pid}/reports`,`/projects/${pid}/report-evidence`,
      `/reports/${rid}`,...evidenceIds.map(id=>`/projects/${pid}/report-evidence/${id}/preview`)].includes(path))||
   (path===`/reports/${rid}`&&query.length===1&&
      query[0][0]==='revision'&&['1','2'].includes(query[0][1]))));
  if(read){
   audit.reads.push(path+url.search);
   await route.continue();return;
  }
  if(method==='GET'){
   audit.unexpected.push(path+url.search);
   await route.fulfill({status:404,json:{detail:'Unreviewed synthetic GET'}});return;
  }
  audit.blockedWrites.push(method+' '+path);
  await route.fulfill({status:403,json:{detail:'All browser writes denied'}});return;
 });
 return audit;
}
let backend:DisposableBackend|null=null;
test.beforeEach(async()=>{backend=await startDisposableBackend()});
test.afterEach(async()=>{if(backend){const old=backend;backend=null;await stopDisposableBackend(old)}});

test('P2 real HTTP Deliver shows immutable v1-v2 differences without browser writes or source mutations',
 async({page,context,request})=>{
  if(process.env.CI!=='true'||process.env.GITHUB_ACTIONS!=='true'||process.env.P1_REAL_HTTP_E2E!=='1')
   throw new Error('Only the isolated GitHub CI disposable backend may run this test.');

  // Browser-independent, explicitly allowed synthetic seed writes.
  const upload=await request.post(API+'/api/projects',{multipart:{
   file:{name:'PilotODIN_P2_Disposable_Revision_Compare.csv',mimeType:'text/csv',buffer:Buffer.from(csv)}
  }});
  expect(upload.status(),await upload.text()).toBe(201);
  const pid=(await upload.json()).id as string;
  expect(pid).toMatch(/^[a-f0-9]{32}$/);

  const evidenceIds:string[]=[];
  // Each synthetic investigation has one completed artifact. Do not assume
  // the first element of a reused investigation's history is the newest run.
  for(const [operation,params] of [
   ['overview',{}],['compare',{x:'Region',y:'Revenue'}]
  ] as const){
   const investigation=await request.post(API+`/api/projects/${pid}/investigations`,{
    data:{objective:'Synthetic '+operation+' report evidence for revision comparison'}
   });
   expect(investigation.status(),await investigation.text()).toBe(201);
   const inv=await investigation.json() as {id:string;version:number};
   const run=await request.post(API+`/api/investigations/${inv.id}/runs`,{
    data:{operation,params,expected_version:inv.version}
   });
   expect(run.status(),await run.text()).toBe(200);
   evidenceIds.push((await run.json()).artifacts[0].id);
  }
  expect(new Set(evidenceIds).size).toBe(2);

  // This snapshot is synthetic and project-scoped. It exercises the real
  // Explore saved-analysis to Deliver handoff without browser write approval.
  const savedExploreTitle='Synthetic Saved Regional View';
  const savedExplore=await request.post(API+`/api/projects/${pid}/explore/saved`,{
   data:{title:savedExploreTitle,expected_version:0,x:'Region',y:'Revenue',
    kind:'bar',aggregation:'sum',bins:16,correlation_method:'pearson',color_by:null,filters:[]}
  });
  expect(savedExplore.status(),await savedExplore.text()).toBe(201);
  const savedExploreId=(await savedExplore.json()).id as string;
  expect(savedExploreId).toMatch(/^[a-f0-9]{32}$/);

  const originalTitle='Synthetic Regional Overview';
  const updatedTitle='Synthetic Regional Revenue Reviewed';
  const oldNarrative='Original synthetic interpretation (not an inference).';
  const newNarrative='Updated analyst interpretation. <script>window.p2Executed=true</script>';
  const created=await request.post(API+`/api/projects/${pid}/reports`,{
   data:{title:originalTitle,narrative:oldNarrative,evidence_ids:[evidenceIds[0]]}
  });
  expect(created.status(),await created.text()).toBe(201);
  const first=await created.json() as {id:string;revision:number;content_sha256:string};
  expect(first.revision).toBe(1);
  const rid=first.id;
  const revised=await request.post(API+`/api/reports/${rid}/revisions`,{
   data:{title:updatedTitle,narrative:newNarrative,evidence_ids:[evidenceIds[1],evidenceIds[0]]}
  });
  expect(revised.status(),await revised.text()).toBe(201);
  const second=await revised.json() as {revision:number;content_sha256:string};
  expect(second.revision).toBe(2);
  expect(first.content_sha256).not.toBe(second.content_sha256);

  const initialList=await (await request.get(API+`/api/projects/${pid}/reports`)).json();
  const q0=await (await request.get(API+`/api/projects/${pid}/quality/history`)).json();
  const audit=await protectBrowser(context,pid,rid,evidenceIds);
  await page.addInitScript((id:string)=>{
   localStorage.setItem('pilotodin-current',id);
   localStorage.setItem('pilotodin-workspace-tabs-v1-'+id,JSON.stringify(['deliver']));
   localStorage.setItem('pilotodin-workspace-active-v1-'+id,'deliver');
  },pid);
  await page.goto('/#/studio/deliver');
  const primary=page.locator('.po-primary-pane');
  await expect(primary.getByRole('heading',{name:'Saved, evidence-backed reports'})).toBeVisible();
  await expect(primary.getByText('Saved revision 2')).toBeVisible();
  await expect(primary.getByRole('button',{name:'Compare with previous saved revision'})).toBeVisible();
  // The inspector fetches a verified summary but never mutates a selection.
  const checkedBefore=await primary.locator('.pd-report-evidence-row input:checked').count();
  const inspectRead=page.waitForResponse(res=>res.url()===
   API+`/api/projects/${pid}/report-evidence/${evidenceIds[0]}/preview`&&
   res.request().method()==='GET');
  await primary.getByRole('button',{
   name:`Inspect verified overview evidence ${evidenceIds[0].slice(0,12)}`
  }).click();
  expect((await inspectRead).status()).toBe(200);
  const facts=primary.getByRole('region',{name:'Verified evidence facts'});
  await expect(facts).toBeVisible();
  await expect(facts).toContainText('dataset v0');
  await expect(facts).toContainText(evidenceIds[0].slice(0,12));
  await expect(facts).toContainText('Only bounded verified aggregate facts');
  expect(await primary.locator('.pd-report-evidence-row input:checked').count()).toBe(checkedBefore);
  await facts.getByRole('button',{name:'Close evidence facts'}).click();
  await expect(facts).toHaveCount(0);

  const comparisonRequest=page.waitForResponse(res=>res.url()===
   API+`/api/reports/${rid}?revision=1`&&res.request().method()==='GET');
  await primary.getByRole('button',{name:'Compare with previous saved revision'}).click();
  const priorResponse=await comparisonRequest;
  expect(priorResponse.status()).toBe(200);
  const compare=primary.getByRole('region',{name:'Saved report revision differences'});
  await expect(compare).toBeVisible();
  await expect(compare).toContainText('Revision 1 compared with revision 2');
  await expect(compare).toContainText('Title changed');
  await expect(compare).toContainText(originalTitle);
  await expect(compare).toContainText(updatedTitle);
  await expect(compare).toContainText('Interpretation changed');
  await expect(compare).toContainText(oldNarrative);
  await expect(compare).toContainText(newNarrative);
  await expect(compare).toContainText('New evidence');
  await expect(compare).toContainText(evidenceIds[1].slice(0,12));
  await expect(compare).toContainText('Previous SHA-256: '+first.content_sha256.slice(0,16));
  await expect(compare).toContainText('Selected SHA-256: '+second.content_sha256.slice(0,16));
  expect(await page.evaluate(()=>(window as Window&{p2Executed?:boolean}).p2Executed)).toBeUndefined();
  expect(await compare.locator('script').count()).toBe(0);

  // Selecting the earlier revision replaces the currently visible content.
  await primary.getByLabel('Open saved revision').selectOption('1');
  await expect(primary.getByText('Saved revision 1')).toBeVisible();
  await expect(compare).toHaveCount(0);
  await expect(primary.getByRole('button',{name:'Compare with previous saved revision'})).toHaveCount(0);
  await primary.getByLabel('Open saved revision').selectOption('2');
  await expect(primary.getByText('Saved revision 2')).toBeVisible();
  await expect(primary.getByRole('button',{name:'Compare with previous saved revision'})).toBeVisible();

  // Browser was strictly GET-only, and immutable backend bytes/history did not change.
  expect(audit.blockedWrites).toEqual([]);
  expect(audit.unexpected).toEqual([]);
  expect(audit.remote).toEqual([]);
  expect(audit.reads).toContain(`/reports/${rid}?revision=1`);
  expect(audit.reads).toContain(`/projects/${pid}/report-evidence/${evidenceIds[0]}/preview`);
  const afterList=await (await request.get(API+`/api/projects/${pid}/reports`)).json();
  const afterHistory=await (await request.get(API+`/api/projects/${pid}/quality/history`)).json();
  const stillFirst=await (await request.get(API+`/api/reports/${rid}?revision=1`)).json();
  const stillSecond=await (await request.get(API+`/api/reports/${rid}?revision=2`)).json();
  expect(afterList).toEqual(initialList);
  expect(afterHistory).toEqual(q0);
  expect(stillFirst.content_sha256).toBe(first.content_sha256);
  expect(stillSecond.content_sha256).toBe(second.content_sha256);

  // Guided drafting is user-authored and never writes until explicit Save.
  // Keep the browser GET-only so a mistaken implicit POST fails this contract.
  await expect(primary.getByRole('button',{name:'Use General analysis outline'})).toBeDisabled();
  await primary.getByRole('button',{name:'New report'}).click();
  await primary.getByRole('button',{name:'Use General analysis outline'}).click();
  const outline=primary.locator('.pd-report-outline-progress');
  const narrativeArea=primary.getByLabel('Interpretation and limitations');
  await expect(outline).toContainText('0 of 4 sections complete');
  await expect(primary.getByRole('button',{name:'Save report'})).toBeDisabled();
  await expect(primary.getByRole('button',{name:'Use General analysis outline'})).toBeDisabled();
  const firstDraft=await narrativeArea.inputValue();
  expect(firstDraft).toContain('Verified evidence interpretation');
  expect(firstDraft).not.toContain('Accuracy: 99');

  await narrativeArea.fill(
   'Purpose and decision\n\nReview the synthetic project for a human decision.\n\n'+
   'Verified evidence interpretation\n\nOnly figures verified in the chosen exhibit may be asserted.\n\n'+
   'Limitations and uncertainty\n\nThis analysis does not prove causation.\n\n'+
   'Recommendations and next steps\n\nReview source quality before deciding next actions.\n'
  );
  await expect(outline).toContainText('4 of 4 sections complete');
  await primary.locator('.pd-report-evidence-row input').first().check();
  await expect(primary.getByRole('button',{name:'Save report'})).toBeEnabled();
  const writtenText=await narrativeArea.inputValue();
  await primary.getByRole('button',{name:'Use freeform writing (keep my text)'}).click();
  await expect(outline).toHaveCount(0);
  expect(await narrativeArea.inputValue()).toBe(writtenText);

  // Browser checks both unsaved NEW drafts and edited SAVED report drafts.
  // Escape and Keep leave the authored text and selected evidence unchanged.
  await primary.getByRole('button',{name:'New report'}).click();
  const discard=primary.getByRole('dialog',{name:'Discard unsaved report edits?'});
  await expect(discard).toBeVisible();
  await expect(discard.getByRole('button',{name:'Keep editing'})).toBeFocused();
  await page.keyboard.press('Escape');
  await expect(discard).toHaveCount(0);
  expect(await narrativeArea.inputValue()).toBe(writtenText);
  expect(await primary.locator('.pd-report-evidence-row input:checked').count()).toBe(1);

  const savedChoice=primary.locator('.pd-report-library > button').first();
  await savedChoice.click();
  await expect(discard).toBeVisible();
  await discard.getByRole('button',{name:'Keep editing'}).click();
  await expect(discard).toHaveCount(0);
  expect(await narrativeArea.inputValue()).toBe(writtenText);

  await savedChoice.click();
  await expect(discard).toBeVisible();
  await discard.getByRole('button',{name:'Discard and continue'}).click();
  await expect(discard).toHaveCount(0);
  await expect(primary.getByLabel('Report title')).toHaveValue(updatedTitle);
  await expect(primary.getByLabel('Interpretation and limitations')).toHaveValue(newNarrative);

  const changedSaved=newNarrative+' Additional unsaved human note.';
  await primary.getByLabel('Interpretation and limitations').fill(changedSaved);
  await primary.getByRole('button',{name:'New report'}).click();
  await expect(discard).toBeVisible();
  await discard.getByRole('button',{name:'Keep editing'}).click();
  await expect(primary.getByLabel('Interpretation and limitations')).toHaveValue(changedSaved);
  await primary.getByRole('button',{name:'New report'}).click();
  await discard.getByRole('button',{name:'Discard and continue'}).click();
  await expect(discard).toHaveCount(0);
  await expect(primary.getByLabel('Interpretation and limitations')).toHaveValue('');

  // An accepted primary Studio New dataset action must actually show import.
  // Previously go('overview') immediately cleared the uploadOpen flag.
  await page.locator('button.new-project').click();
  await expect(primary.getByRole('button',{name:'Cancel upload'})).toBeVisible();
  await expect(primary.locator('.landing .upload-card')).toBeVisible();
  await primary.getByRole('button',{name:'Cancel upload'}).click();
  await page.locator('button.po-nav-item[aria-label="Deliver"]').click();
  await expect(primary.getByRole('heading',{name:'Saved, evidence-backed reports'})).toBeVisible();

  // A dirty Deliver primary view must not unmount when the shell rail selects
  // Explore and the user denies the browser/native-compatible confirmation.
  const draftLeavingDeliver='Unfinished analyst interpretation for this synthetic report.';
  await primary.getByLabel('Interpretation and limitations').fill(draftLeavingDeliver);

  // A rejected New dataset request must NOT hide the report or open an
  // importer. The shell's separate New project control must not arm a
  // deferred import that appears on a later ordinary Home visit.
  for(const trigger of [
   () => page.locator('button.new-project').click(),
   () => page.getByRole('button',{name:'New project: import dataset'}).click()
  ]){
   let prompted=false;
   page.once('dialog',async dialog=>{
    prompted=true;
    expect(dialog.message()).toContain('Your Deliver report contains unsaved changes');
    await dialog.dismiss();
   });
   await trigger();
   expect(prompted).toBe(true);
   await expect(primary.getByRole('heading',{name:'Saved, evidence-backed reports'})).toBeVisible();
   await expect(primary.getByLabel('Interpretation and limitations')).toHaveValue(draftLeavingDeliver);
   await expect(primary.locator('.landing')).toHaveCount(0);
   expect(page.url()).toContain('/studio/deliver');
  }
  let sawExitPrompt=false;
  page.once('dialog',async dialog=>{
   sawExitPrompt=true;
   expect(dialog.message()).toContain('Your Deliver report contains unsaved changes');
   await dialog.dismiss();
  });
  await page.locator('button.po-nav-item[aria-label="Explore"]').click();
  expect(sawExitPrompt).toBe(true);
  await expect(primary.getByRole('heading',{name:'Saved, evidence-backed reports'})).toBeVisible();
  await expect(primary.getByLabel('Interpretation and limitations')).toHaveValue(draftLeavingDeliver);
  expect(page.url()).toContain('/studio/deliver');

  // Explicitly discard the disposable note before switching workspaces.
  await primary.getByRole('button',{name:'New report'}).click();
  const leaveDialog=primary.getByRole('dialog',{name:'Discard unsaved report edits?'});
  await leaveDialog.getByRole('button',{name:'Discard and continue'}).click();
  await expect(primary.getByLabel('Interpretation and limitations')).toHaveValue('');
  await page.locator('button.po-nav-item[aria-label="Home"]').click();
  // A previously refused shell New project must not show a delayed importer.
  await expect(primary.locator('.landing')).toHaveCount(0);
  await page.locator('button.po-nav-item[aria-label="Explore"]').click();
  const savedArea=primary.getByRole('region',{name:'Saved analytical investigations'});
  await expect(savedArea).toBeVisible();
  await savedArea.getByRole('button',{name:`Open ${savedExploreTitle} and jump to saved history`}).click();
  await expect(savedArea.getByRole('button',{name:'Use verified evidence in Deliver'})).toBeVisible();
  await savedArea.getByRole('button',{name:'Use verified evidence in Deliver'}).click();
  await expect(primary.getByRole('heading',{name:'Saved, evidence-backed reports'})).toBeVisible();
  await expect(primary.getByLabel('Report title')).toHaveValue(savedExploreTitle+' report');
  const incoming=primary.locator('.pd-report-evidence-row').filter({hasText:savedExploreId.slice(0,12)});
  await expect(incoming).toHaveCount(1);
  await expect(incoming.locator('input[type=checkbox]')).toBeChecked();
  await expect(primary.getByLabel('Interpretation and limitations')).toHaveValue('');
  expect(audit.readOnlyCalculations).toBeGreaterThan(0);
  expect(audit.blockedWrites).toEqual([]);
  expect(audit.unexpected).toEqual([]);
  expect(audit.remote).toEqual([]);
  expect((await (await request.get(API+`/api/projects/${pid}/reports`)).json())).toEqual(initialList);
 });
