import { diagnoseDevPage, discoverUniqueDevPage } from './p4-73-cdp-target-discovery.mjs';
import { openP4FixtureWorkspace } from './p4-open-fixture-workspace.mjs';
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
  const reason=error.stderr?.trim()||error.message;
  console.log('NATIVE PROJECT SWITCH BLOCKED: '+reason);
  process.exitCode=3;
  return false;
 }
 await expect(chooser).toBeEnabled({timeout:10000});
 return true;
}
function csvFor(kind){
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
 form.append('file',new Blob([csvFor(kind)],{type:'text/csv'}),'p4-71-'+kind+'-synthetic.csv');
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
  console.log('NATIVE INTERACTIONS BLOCKED: '+discovered.status+' after '+discovered.attempts+' polls. No QA projects created.');
  if(discovered.classes)console.log('CDP target classes: '+JSON.stringify(discovered.classes)+'; count='+discovered.count);
  await reportBlockedDiscovery();
  return;
 }
 const page=discovered.page;
 const context=page.context();
 await context.route('**/*',async route=>{
  const u=new URL(route.request().url());
  const allowed=(u.hostname==='127.0.0.1'&&['8000','5173'].includes(u.port))
   ||u.hostname==='ipc.localhost'||['tauri:','data:','blob:'].includes(u.protocol);
  if(allowed)await route.continue();
  else await route.abort('blockedbyclient');
 });
 console.log('ACTUAL Tauri WebView2 reached, local URL only');
 const ids={};
 for(const kind of ['classification','regression','rare','insufficient','neutral'])ids[kind]=await create(kind);
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
  const stale=await fetch(API+'/projects/'+ids.classification+'/preparation?expected_version=99999');
  if(stale.status!==409)throw Error('Expected Quality-version 409 but got HTTP '+stale.status);
  console.log('N11 stale Quality-version API: PASS; native stale UI transition NOT TESTED');
  await noTraining(all);
  console.log('N12 disposable projects contain no model experiments: PASS for experiment count');
  console.log('Native probe checks completed. Quality version transition, R04 layout and R05 Prepare controls require separate evidence.');
 }finally{await noTraining(all);}
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
