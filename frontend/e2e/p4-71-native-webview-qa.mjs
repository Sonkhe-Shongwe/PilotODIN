import { diagnoseDevPage, discoverUniqueDevPage } from './p4-73-cdp-target-discovery.mjs';
import { openP4FixtureWorkspace } from './p4-open-fixture-workspace.mjs';
import { p4QualityFixture, reloadP4SyntheticWorkspace, verifyP4QualityAfterRelaunch, verifyP4QualityTransition } from './p4-quality-version-transition.mjs';
import { p4PreparationRequestUrl } from './p4-preparation-request.mjs';
import { readFile, writeFile } from 'node:fs/promises';
import { join } from 'node:path';
import { execFile } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { promisify } from 'node:util';
// P4-71 disposable CI only: attach to ACTUAL Tauri native WebView2, no original user data.
import { chromium, expect } from '@playwright/test';
const required = {CI:'true',GITHUB_ACTIONS:'true',RUNNER_OS:'Windows',RUNNER_ENVIRONMENT:'github-hosted',VITE_PILOTODIN_NATIVE_SMOKE:'1'};
for(const [key,value] of Object.entries(required)) {
 if(process.env[key]!==value)throw Error('P4-71 BLOCKED: wrong hosted Windows QA environment: '+key);
}
if(!process.env.PILOTODIN_HOME?.includes('P4-71-only-home-'))throw Error('P4-71 BLOCKED: no disposable isolated test home');
const API='http://127.0.0.1:8000/api';
const SITE='http://127.0.0.1:5173';
const relaunch=process.argv[2]==='--verify-relaunch';
const receiptPath=join(process.env.PILOTODIN_HOME,'p4-synthetic-projects.json');
const captureDir=join(process.env.PILOTODIN_HOME,'captures');
if(process.argv.length!== (relaunch ? 3 : 2))throw Error('Unexpected QA probe arguments');
const invokeDialog=fileURLToPath(new URL('../../qa/p4_native/Invoke_P4_Native_Project_Switch_Dialog.ps1',import.meta.url));
const execFileAsync=promisify(execFile);

async function chooseNativeDialogAction(chooser, destination, action) {
 await chooser.selectOption(destination);
 await expect(chooser).toBeDisabled();
 try {
  const {stdout}=await execFileAsync('powershell.exe',[
   '-NoProfile','-NonInteractive','-STA','-File',invokeDialog,'-Action',action,
  ],{timeout:20000,windowsHide:true});
  console.log(stdout.trim());
 } catch (error) {
  const detail=error.stderr?.trim()||error.stdout?.trim();
  const reason=error.killed
   ? 'Windows dialog driver exceeded its 20-second process timeout'+(detail?'\n'+detail:'')
   : detail||error.message;
  console.log('NATIVE PROJECT SWITCH BLOCKED: '+reason);
  process.exitCode=3;
  return false;
 }
 await expect(chooser).toBeEnabled({timeout:10000});
 return true;
}
function csvFor(kind){
 if(kind==='prepare')return ['TransactionID,churn,event_type,amount',
  ...Array.from({length:80},(_,i)=>['SYNTH-'+String(i).padStart(3,'0'),i%2?'Y':'N',i%3?'service':'retail',100+i].join(',')),
 ].join('\n')+'\n';
 const heads=['account_id','feature'];
 if(kind==='classification')heads.push('churn','fraud_reported','failure_flag','outcome','future_cost');
 else if(kind==='regression')heads.push('future_cost');
 else if(kind==='rare'||kind==='insufficient')heads.push('churn');
 else if(kind==='neutral')heads.push('generic_measure');
 else throw Error('Unexpected synthetic fixture');
 const rows=[heads.join(',')];
 for(let i=0;i<80;i++){
  const x=['P4-71-SYNTH-'+String(Math.floor(i/2)).padStart(3,'0'),i%9];
  if(kind==='classification')x.push(i%2?'Y':'N',i%3?'Y':'N',i%4?'no':'yes',i%2?'done':'pending',110+i);
  if(kind==='regression')x.push(110+i);
  if(kind==='rare')x.push(i<76?'Y':'N');
  if(kind==='insufficient')x.push(i<24?(i%2?'Y':'N'):'');
  if(kind==='neutral')x.push(i*3);
  rows.push(x.join(','));
 }
 return rows.join('\n')+'\n';
}
async function create(kind){
 const form=new FormData();
 form.append('file',new Blob([kind==='quality'?p4QualityFixture:csvFor(kind)],{type:'text/csv'}),'p4-71-'+kind+'-synthetic.csv');
 const resp=await fetch(API+'/projects',{method:'POST',body:form});
 if(resp.status!==201)throw Error('Synthetic project '+kind+' failed, HTTP '+resp.status);
 return (await resp.json()).id;
}
async function noTraining(ids){
 for(const id of ids){
  const resp=await fetch(API+'/projects/'+id);
  if(!resp.ok)throw Error('Cannot inspect a disposable QA project');
  if((await resp.json()).experiments?.length!==0)throw Error('STOP: unexpected model experiment in disposable project');
 }
}

async function verifyWindowsLayout(page) {
 const navigation=page.getByRole('navigation',{name:'Workspace navigation'});
 const primary=page.locator('.po-primary-pane');
 const checkpoint=primary.getByRole('group',{name:'Selected target suitability checkpoint'});
 const nativeViewport=await page.evaluate(()=>({width:innerWidth,height:innerHeight,scale:devicePixelRatio}));
 console.log('R04 native WebView viewport '+JSON.stringify(nativeViewport));
 const session=await page.context().newCDPSession(page);
 try {
  for(const width of [1440,1100]){
   await session.send('Emulation.setDeviceMetricsOverride',{width,height:900,deviceScaleFactor:0,mobile:false});
   await expect(primary.getByRole('heading',{name:'Prepare',exact:true})).toBeVisible();
   await expect(checkpoint).toBeVisible();
   await expect(checkpoint).toHaveCSS('display','block');
   expect(await checkpoint.evaluate(node=>node.scrollWidth<=node.clientWidth+2)).toBe(true);
   await expect(page.locator('.po-shell-warning')).toHaveCount(0);
   await checkpoint.screenshot({path:join(captureDir,'prepare-review-'+width+'.png'),animations:'disabled',timeout:15000});
  }
  console.log('R04 target checkpoint and archive warning at two WebView widths: PASS');
  await session.send('Emulation.setDeviceMetricsOverride',{width:1440,height:900,deviceScaleFactor:0,mobile:false});
  await navigation.getByRole('button',{name:'Your data',exact:true}).click();
  await navigation.getByRole('button',{name:'Prepare',exact:true}).click();
  const dataTab=page.locator('.po-tab').filter({has:page.locator('#po-workspace-tab-understand')});
  const dock=page.getByRole('region',{name:'Docked Your data workspace'});
  await dataTab.dragTo(primary);
  await expect(dock.getByRole('combobox',{name:'Docked analytical component'})).toHaveValue('understand');
  await dock.getByRole('button',{name:'Close docked pane'}).click();
  await expect(dock).toBeHidden();
  await page.getByRole('button',{name:'Dock Your data beside current view'}).click();
  await expect(dock).toBeVisible();
  await session.send('Emulation.setDeviceMetricsOverride',{width:730,height:900,deviceScaleFactor:0,mobile:false});
  await expect(dock).toBeHidden();
  await expect(page.locator('.po-dock-narrow-notice')).toBeVisible();
  await session.send('Emulation.setDeviceMetricsOverride',{width:1440,height:900,deviceScaleFactor:0,mobile:false});
  await expect(dock).toBeVisible();
  await dock.getByRole('button',{name:'Close docked pane'}).click();
  console.log('R04 docking drag, close, reopen and narrow WebView pause/restore: PASS');
 }finally{
  await session.send('Emulation.clearDeviceMetricsOverride');
  await session.detach();
 }
}

async function verifyWindowsPrepare(page,projectId){
 await openP4FixtureWorkspace(page,SITE,projectId);
 await expect(page.getByRole('combobox',{name:'Switch project'})).toHaveValue(projectId);
 const target=page.getByLabel('TARGET VARIABLE');
 await target.selectOption('churn');
 const audit=page.locator('.po-ml-feature-audit tbody');
 const amount=audit.getByRole('row').filter({hasText:'amount'});
 const category=audit.getByRole('row').filter({hasText:'event_type'});
 const numeric=page.getByLabel('Numeric imputation method');
 const categorical=page.getByLabel('Categorical imputation method');
 await expect(numeric).toHaveValue('median');
 await expect(categorical).toHaveValue('most_frequent');
 await expect(amount).toContainText('Numeric: median imputation');
 await expect(category).toContainText('Categorical: mode imputation');
 await numeric.selectOption('mean');
 await categorical.selectOption('constant');
 await expect(amount).toContainText('Numeric: mean imputation');
 await expect(category).toContainText('Categorical: missing-marker imputation');
 const risk=page.locator('.feature-chip').filter({hasText:'TransactionID'}).getByRole('checkbox');
 const manual=page.locator('.feature-chip').filter({hasText:'event_type'}).getByRole('checkbox');
 await manual.check();
 const review=page.getByRole('button',{name:'Review high-risk exclusion suggestions'});
 const preview=page.getByRole('group',{name:'Review proposed high-risk exclusions'});
 await review.click();
 await expect(preview).toContainText('Will additionally exclude (1): TransactionID');
 await expect(preview).toContainText('Already excluded, kept unchanged (1): event_type');
 await preview.getByRole('button',{name:'Cancel exclusion review'}).click();
 await expect(manual).toBeChecked();
 await expect(risk).not.toBeChecked();
 await review.click();
 await preview.getByRole('button',{name:'Apply reviewed exclusions'}).click();
 await expect(manual).toBeChecked();
 await expect(risk).toBeChecked();
 await expect(page.locator('.mini-info').filter({hasText:'candidate predictors'})).toContainText('1 currently included');
 await expect(category).toContainText('Excluded by user');
 const plan=await fetch(p4PreparationRequestUrl(API,projectId,'churn',0));
 const advice=await fetch(`${API}/projects/${projectId}/features?target=churn&expected_version=0`);
 expect(plan.status).toBe(200);
 expect(advice.status).toBe(200);
 expect(await plan.json()).toMatchObject({quality_version:0,target:'churn'});
 expect(await advice.json()).toMatchObject({version:0});
 await target.selectOption('');
 await expect(numeric).toHaveCount(0);
 await target.selectOption('churn');
 await expect(numeric).toHaveValue('median');
 await expect(categorical).toHaveValue('most_frequent');
 console.log('R05 per-field audit, global strategies, cancel/apply additive exclusions, version and target reset: PASS');
}
async function reportBlockedDiscovery() {
 process.exitCode=2;
 console.log('NATIVE LOOPBACK DIAGNOSTICS: '+JSON.stringify(await diagnoseDevPage()));
}
async function runNativeProbe(browser) {
 // Require the development page and its callable Tauri bridge before creating fixtures.
 const discovered=await discoverUniqueDevPage(
  ()=>browser.contexts().flatMap(context=>context.pages()),
  ()=>new Promise(resolve=>setTimeout(resolve,1500)),
  20
 );
 if(discovered.status!=='FOUND'){
  // Diagnostic classes are deliberately fixed categories, never raw URLs.
  console.log('NATIVE INTERACTIONS BLOCKED: '+discovered.status+' after '+discovered.attempts+' polls.');
  if(discovered.classes)console.log('CDP target classes: '+JSON.stringify(discovered.classes)+'; count='+discovered.count);
  await reportBlockedDiscovery();
  return;
 }
 const page=discovered.page;
 const context=page.context();
 const ids={};
 const writes=[];
 const blocked={external:0,unexpectedLocal:0,font:0};
 const reportTraffic=()=>{
  console.log('N12 intercepted WebView traffic '+JSON.stringify({writes,blocked}));
  expect(blocked.unexpectedLocal).toBe(0);
  expect(blocked.external).toBe(0);
 };
 await context.route('**/*',async route=>{
  const u=new URL(route.request().url());
  const method=route.request().method();
  const qualityWrite=method==='POST'&&ids.quality&&
   ['/proposals','/commit'].some(suffix=>u.pathname==='/api/projects/'+ids.quality+'/quality'+suffix);
  const allowed=(u.origin===SITE&&['GET','HEAD'].includes(method))
   ||(u.origin==='http://127.0.0.1:8000'&&(['GET','OPTIONS'].includes(method)||qualityWrite))
   ||u.hostname==='ipc.localhost'||['tauri:','data:','blob:'].includes(u.protocol);
  if(qualityWrite)writes.push(u.pathname.split('/').at(-1));
  if(allowed)await route.continue();
  else{
   if(u.origin==='https://fonts.googleapis.com'&&method==='GET'&&u.pathname==='/css2')blocked.font++;
   else if(u.origin===SITE||u.origin==='http://127.0.0.1:8000')blocked.unexpectedLocal++;
   else blocked.external++;
   await route.abort('blockedbyclient');
  }
 });
 console.log('ACTUAL Tauri WebView2 reached, local URL only');
 if(relaunch){
  const saved=JSON.parse(await readFile(receiptPath,'utf8'));
  if(Object.keys(saved).length!==7||Object.values(saved).some(id=>typeof id!=='string'||!/^[0-9a-f]{32}$/.test(id)))throw Error('Invalid synthetic project receipt');
  const failures=[];
  try{
   await verifyP4QualityAfterRelaunch(page,API,saved.quality);
   console.log('N11 native process relaunch restores the synthetic project and Prepare version 1: PASS');
   try{await verifyWindowsLayout(page)}catch(error){failures.push('R04');console.error('R04 check stopped:',error.message)}
   try{await verifyWindowsPrepare(page,saved.prepare)}catch(error){failures.push('R05');console.error('R05 check stopped:',error.message)}
  }finally{
   await noTraining(Object.values(saved));
   console.log('N12 experiment count after relaunch: zero across all seven synthetic projects');
   reportTraffic();
  }
  if(failures.length)throw Error('Hosted Windows checks failed: '+failures.join(', '));
  return;
 }
 for(const kind of ['classification','regression','rare','insufficient','neutral','quality','prepare'])ids[kind]=await create(kind);
 const all=Object.values(ids);
 try{
  await openP4FixtureWorkspace(page,SITE,ids.classification);
  const section=page.getByRole('region',{name:'Potential prediction opportunities'});
  const chooser=page.getByRole('combobox',{name:'Switch project'});
  const target=page.getByLabel('TARGET VARIABLE');
  const checkpoint=section.getByRole('group',{name:'Selected target suitability checkpoint'});
  const blockers=checkpoint.getByRole('alert',{name:'Selected target structural blockers'});
  const reviewCards=section.locator('article.model-choice');
  await expect(chooser).toHaveValue(ids.classification,{timeout:45000});
  await expect(section).toBeVisible({timeout:45000});
  console.log('N1 actual native WebView and disposable backend: PASS');
  await expect(reviewCards).toHaveCount(3);
  await expect(section).toContainText('churn');
  const alternatives=section.locator('details[aria-label="Additional reviewable target alternatives"]');
  await alternatives.locator(':scope > summary').click();
  await expect(alternatives.getByRole('button',{name:'Review this alternative target'}).first()).toBeVisible();
  console.log('N2 three native classification review cards and alternatives: PASS');
  const first=reviewCards.first();
  const evidence=first.locator('details[aria-label^="Evidence needed for"]');
  await evidence.locator(':scope > summary').click();
  await expect(evidence.getByLabel('Decision usefulness evidence')).toContainText('40 additional occurrences beyond the first');
  console.log('N3 repeated IDs disclosure: PASS');
  const review=first.getByRole('button',{name:'Review this target'});
  await review.click();
  await expect(checkpoint).toBeVisible();
  await first.getByRole('button',{name:'Defer target in this review'}).click();
  await expect(first.getByRole('status')).toContainText('Deferred');
  await expect(target).toHaveValue('');
  await expect(checkpoint).toHaveCount(0);
  await review.click();
  await expect(checkpoint).toBeVisible();
  await first.getByRole('button',{name:'Decline target in this review'}).click();
  await expect(first.getByRole('status')).toContainText('Declined');
  await expect(target).toHaveValue('');
  await expect(checkpoint).toHaveCount(0);
  console.log('N4 selection, defer, reselect and decline clear native Prepare target: PASS');
  await review.click();
  await expect(checkpoint).toBeVisible();
  await section.getByRole('button',{name:'No prediction objective right now'}).click();
  await expect(section).toContainText('Preparation is cleared');
  await expect(target).toHaveValue('');
  await expect(checkpoint).toHaveCount(0);
  console.log('N5 explicit no-objective selection clears native Prepare target: PASS');

  // Give the actual Windows dialog a real dirty Prepare draft to guard.
  await target.selectOption('churn');
  await expect(checkpoint).toContainText('churn');
  if(!(await chooseNativeDialogAction(chooser,ids.regression,'Stay')))return;
  await expect(chooser).toHaveValue(ids.classification);
  await expect(target).toHaveValue('churn');
  await expect(checkpoint).toContainText('churn');
  console.log('N7 native Stay keeps the project and edited target: PASS');
  if(!(await chooseNativeDialogAction(chooser,ids.regression,'Switch project')))return;
  await expect(chooser).toHaveValue(ids.regression);
  await expect(target).toHaveValue('');
  await expect(checkpoint).toHaveCount(0);
  await expect(reviewCards.first()).toContainText('future_cost');
  await target.selectOption('future_cost');
  await expect(checkpoint).toContainText('future_cost');
  console.log('N6 native regression opportunity and manual target selection: PASS');
  if(!(await chooseNativeDialogAction(chooser,ids.classification,'Switch project')))return;
  await expect(chooser).toHaveValue(ids.classification);
  await expect(target).toHaveValue('');
  await expect(checkpoint).toHaveCount(0);
  await expect(section.getByText(/Declined for this\s+review only/)).toHaveCount(0);
  console.log('N7 native Switch project opens the destination and clears old Prepare review state: PASS');

  await chooser.selectOption(ids.rare);
  await expect(chooser).toHaveValue(ids.rare);
  await expect(section).toContainText('No named outcome with sufficient technically supported labels');
  await target.selectOption('churn');
  await expect(blockers).toContainText('at least 6 labelled rows');
  console.log('N8 rare minority 4/80 native abstention and blocker: PASS');
  if(!(await chooseNativeDialogAction(chooser,ids.insufficient,'Switch project')))return;
  await expect(chooser).toHaveValue(ids.insufficient);
  await expect(section).toContainText('No named outcome with sufficient technically supported labels');
  await target.selectOption('churn');
  await expect(blockers).toContainText('at least 30 labelled rows');
  console.log('N9 only 24 labels native abstention and blocker: PASS');
  if(!(await chooseNativeDialogAction(chooser,ids.neutral,'Switch project')))return;
  await expect(chooser).toHaveValue(ids.neutral);
  await expect(section).toContainText('No named outcome with sufficient technically supported labels');
  await target.selectOption('generic_measure');
  await expect(blockers).toContainText('Structurally blocked target');
  console.log('N10 unnamed outcome abstains and explains a blocked manual selection: PASS');
  if(!(await chooseNativeDialogAction(chooser,ids.quality,'Switch project')))return;
  await verifyP4QualityTransition(page,API,ids.quality,url=>fetch(url));
  console.log('N11 Quality approval, 409 for the previous version, Prepare refresh and WebView reload: PASS');
  await noTraining(all);
  console.log('N12 disposable projects contain no model experiments: PASS for experiment count');
  // Reopen the same WebView with the verified version and no edited draft
  // so the Windows close request can run through normal app shutdown.
  await reloadP4SyntheticWorkspace(page);
  await expect(chooser).toHaveValue(ids.quality);
  await expect(section).toContainText('Current approved dataset version: 1.');
  await expect(target).toHaveValue('');
  expect(writes).toEqual(['proposals','commit']);
  await writeFile(receiptPath,JSON.stringify(ids),{flag:'wx'});
  console.log('N11 ready for native close and relaunch');
 }finally{await noTraining(all);reportTraffic();}
}
async function main() {
 let browser;
 try {
  browser=await chromium.connectOverCDP('http://127.0.0.1:9331',{timeout:15000});
 } catch (error) {
  console.log('NATIVE INTERACTIONS BLOCKED: WebView2 CDP unavailable; cannot claim N2-N12 native checks.');
  console.log('CDP failure category: '+(error?.name??'unknown'));
  await reportBlockedDiscovery();
  return;
 }
 try {
  await runNativeProbe(browser);
 } finally {
  await browser.close().catch(()=>{});
 }
}
await main();
