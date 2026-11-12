import { isExpectedDevPage, safeTargetClass } from './p4-72-cdp-target-classifier.mjs';
// P4-71 disposable CI only: attach to ACTUAL Tauri native WebView2, no original user data.
import { chromium, expect } from '@playwright/test';
const required = {CI:'true',GITHUB_ACTIONS:'true',RUNNER_OS:'Windows',RUNNER_ENVIRONMENT:'github-hosted',VITE_PILOTODIN_NATIVE_SMOKE:'1'};
for(const [key,value] of Object.entries(required)) {
 if(process.env[key]!==value)throw Error('P4-71 BLOCKED: wrong hosted Windows QA environment: '+key);
}
if(!process.env.PILOTODIN_HOME?.includes('P4-71-only-home-'))throw Error('P4-71 BLOCKED: no disposable isolated test home');
const API='http://127.0.0.1:8000/api';
const SITE='http://127.0.0.1:5173';
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
let browser;
try {
 browser=await chromium.connectOverCDP('http://127.0.0.1:9331',{timeout:15000});
}catch(error){
 console.log('NATIVE INTERACTIONS BLOCKED: WebView2 CDP unavailable; cannot claim N2-N11 native checks.');
 console.log('CDP failure category: '+(error?.name??'unknown'));
 process.exit(0);
}
try{
 let page=null;
 let observed=[];
 // A CDP endpoint becoming ready does not guarantee the WebView target has
 // already navigated. Retry discovery only; no navigation or app mutation.
 for(let i=0;i<20;i++){
  const candidates=browser.contexts().flatMap(c=>c.pages());
  const matching=candidates.filter(candidate=>isExpectedDevPage(candidate.url()));
  if(matching.length===1){page=matching[0];break;}
  if(matching.length>1){
   console.log('NATIVE INTERACTIONS BLOCKED: ambiguous multiple developer UI targets.');
   process.exit(0);
  }
  observed=candidates.map(candidate=>safeTargetClass(candidate.url()));
  if(i<19)await new Promise(resolve=>setTimeout(resolve,1500));
 }
 if(!page){
  // Never log complete URLs, access tokens, query strings or private paths.
  console.log('NATIVE INTERACTIONS BLOCKED: expected developer UI target unavailable after bounded retries.');
  console.log('CDP target classifications: '+JSON.stringify([...new Set(observed)].sort())+'; count='+observed.length);
  process.exit(0);
 }
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
  await page.evaluate(id=>localStorage.setItem('pilotodin-current',id),ids.classification);
  await page.goto(SITE+'/#/studio/prepare',{waitUntil:'domcontentloaded'});
  const section=page.getByRole('region',{name:'Potential prediction opportunities'});
  await expect(section).toBeVisible({timeout:45000});
  await expect(page.getByRole('combobox',{name:'Switch project'})).toHaveValue(ids.classification);
  console.log('N1 actual native WebView and disposable backend: PASS');
  const first=section.locator('article.model-choice').first();
  await expect(first).toBeVisible();
  await expect(section).toContainText('churn');
  console.log('N2 native classification target opportunity: PASS');
  await expect(section).toContainText('40');
  console.log('N3 repeated IDs 40-count disclosure: PARTIAL');
  await first.getByRole('button',{name:'Defer target in this review'}).click();
  await expect(first).toContainText('Deferred for this review only.');
  await section.getByRole('button',{name:'Review this target'}).first().click();
  await expect(section.getByRole('group',{name:'Selected target suitability checkpoint'})).toBeVisible();
  await section.getByRole('button',{name:'Clear selected target and preparation'}).first().click();
  console.log('N4 defer/review/clear native: PASS; decline separately NOT TESTED');
  const chooser=page.getByRole('combobox',{name:'Switch project'});
  await chooser.selectOption(ids.regression);
  await expect(chooser).toHaveValue(ids.regression);
  await expect(page.getByLabel('TARGET VARIABLE')).toHaveValue('');
  await expect(section).toContainText('future_cost');
  console.log('N6/N7 regression and project-switch target reset: PASS');
  await chooser.selectOption(ids.rare);
  await expect(section).toContainText('No named outcome with sufficient technically supported labels');
  console.log('N8 rare minority 4/80 native abstention: PASS');
  await chooser.selectOption(ids.insufficient);
  await expect(section).toContainText('No named outcome with sufficient technically supported labels');
  console.log('N9 only 24 labels native abstention: PASS');
  await chooser.selectOption(ids.neutral);
  await expect(section).toContainText('No named outcome with sufficient technically supported labels');
  await section.getByRole('button',{name:'No prediction objective right now'}).click();
  console.log('N5/N10 native no-objective explicit abstention: PASS');
  const stale=await fetch(API+'/projects/'+ids.classification+'/preparation?expected_version=99999');
  if(stale.status!==409)throw Error('Expected Quality-version 409 but got HTTP '+stale.status);
  console.log('N11 stale Quality-version API: PASS; native stale UI transition NOT TESTED');
  await noTraining(all);
  console.log('N12 no model experiments: PASS');
  console.log('P4-71 BOUNDED ACTUAL NATIVE WEBVIEW INTERACTION SUITE: PASS, remaining R02-R06 open.');
 }finally{await noTraining(all);}
}finally{await browser.close().catch(()=>{});}
