import React from 'react';
import {createRoot,Root} from 'react-dom/client';
import {ReportWorkspace} from './ReportWorkspace';

/** Development-only mounted React test surface. No real backend, storage or network. */
type FetchHandler=(path:string,method:string,body:unknown)=>Promise<Response>|Response;
type Report={
 id:string;title:string;narrative:string;revision:number;revisions:number[];
 dataset_versions:number[];current_dataset_version:number;has_historical_evidence:boolean;
 content_sha256:string;evidence:{id:string;operation:string;dataset_version:number;tool_version:string;
 params:Record<string,unknown>;result:Record<string,unknown>}[];
};
const fixtureEvidence=[
 {id:'ev-existing',operation:'quality_audit',version:0,params:{},objective:'Synthetic audit'},
 {id:'ev-extra',operation:'explore_snapshot',version:0,params:{},objective:'Synthetic review'},
];
const auditEvidence={id:'ev-new-audit',operation:'quality_audit',version:0,params:{},objective:'Synthetic captured audit'};
function saved(title='Original report'):Report {
 return {id:'synthetic-report',title,narrative:'A synthetic report with no user data.',revision:1,revisions:[1],
 dataset_versions:[0],current_dataset_version:0,has_historical_evidence:false,
 content_sha256:'a'.repeat(64),evidence:[{
 id:'ev-existing',operation:'quality_audit',dataset_version:0,tool_version:'test',
 params:{},result:{}}
 ]};
}
function json(data:unknown,status=200):Response {
 return new Response(JSON.stringify(data),{status,headers:{'Content-Type':'application/json'}});
}
function deferred<T>(){
 let resolve!:(value:T)=>void;
 const promise=new Promise<T>(yes=>{resolve=yes});
 return {promise,resolve};
}
function expect(value:unknown,message:string):asserts value {
 if(!value)throw new Error(message);
}
function tick(ms=35){return new Promise<void>(resolve=>setTimeout(resolve,ms))}
async function until<T>(check:()=>T|undefined|null|false,desc:string,timeout=3200):Promise<T>{
 const start=Date.now();
 while(Date.now()-start<timeout){
  const found=check();
  if(found)return found as T;
  await tick();
 }
 throw new Error('Timed out: '+desc);
}
function findButton(text:string):HTMLButtonElement|undefined {
 return Array.from(document.querySelectorAll<HTMLButtonElement>('#mount button'))
  .find(button=>button.textContent?.includes(text));
}
function titleInput():HTMLInputElement {
 const input=document.querySelector<HTMLInputElement>('#mount .pd-report-editor input:not([type=checkbox])');
 expect(input,'report title input not mounted');
 return input;
}
function edit(input:HTMLInputElement,value:string){
 const setter=Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value')?.set;
 expect(setter,'native input setter missing');
 setter.call(input,value);
 input.dispatchEvent(new Event('input',{bubbles:true}));
 input.dispatchEvent(new Event('change',{bubbles:true}));
}
function evidenceCheckbox(id:string):HTMLInputElement|undefined {
 return Array.from(document.querySelectorAll<HTMLInputElement>('#mount .pd-report-evidence input[type=checkbox]'))
 .find(el=>el.closest('label')?.textContent?.includes(id.slice(0,12)));
}
let root:Root|null=null;
function mount(projectId:string,handler:FetchHandler){
 const original=window.fetch;
 window.fetch=(async (resource:RequestInfo|URL,init?:RequestInit)=>{
  const url=new URL(String(resource),window.location.href);
  // Fail closed if any unexpected local/remote request escapes the fake backend.
  if(url.hostname!=='127.0.0.1'||url.port!=='8000'||!url.pathname.startsWith('/api/'))
   throw new Error('Unexpected request blocked by synthetic P2 harness: '+url.origin);
  const body=init?.body?JSON.parse(String(init.body)):null;
  return await handler(url.pathname.slice(4)+url.search,init?.method??'GET',body);
 }) as typeof fetch;
 const host=document.getElementById('mount');
 expect(host,'harness mount root missing');
 root=createRoot(host);
 root.render(<ReportWorkspace projectId={projectId} defaultTitle="Synthetic report title"/>);
 return {
  render:(nextProject:string)=>root?.render(<ReportWorkspace projectId={nextProject} defaultTitle="Synthetic report title"/>),
  close:()=>{root?.unmount();root=null;window.fetch=original},
 };
}
function common(path:string,method:string):Response{
 if(method==='GET'&&path.endsWith('/report-evidence'))return json(fixtureEvidence);
 if(method==='GET'&&path.endsWith('/reports'))return json([]);
 throw new Error('Unexpected mock API: '+method+' '+path);
}

async function testEditingWhileOpen(){
 const old=deferred<Response>();
 let reportRequests=0;
 const fixture=mount('synthetic-project',(path,method)=>{
  if(method==='GET'&&path==='/projects/synthetic-project/reports')
   return json([{id:'synthetic-report',title:'Original report',revision:1,updated_at:'2026-10-25T00:00:00'}]);
  if(method==='GET'&&path==='/projects/synthetic-project/report-evidence')return json(fixtureEvidence);
  if(method==='GET'&&path==='/reports/synthetic-report'){
   reportRequests++;
   return reportRequests===1?json(saved()):old.promise;
  }
  throw new Error('Unexpected mock API: '+method+' '+path);
 });
 try{
  // React mounts asynchronously: poll for existence before reading the title.
  // Do not throw on a transient empty DOM before the component has committed.
  await until(()=>document.querySelector<HTMLInputElement>('#mount .pd-report-editor input:not([type=checkbox])')?.value==='Original report','initial saved report hydrated');
  const button=await until(()=>findButton('Original report'),'saved report button visible');
  button.click();
  await until(()=>reportRequests===2,'second Open GET initiated');
  edit(titleInput(),'Edited while opening');
  await until(()=>titleInput().value==='Edited while opening','draft edit reflected');
  old.resolve(json(saved('Stale server title')));
  await tick(90);
  expect(titleInput().value==='Edited while opening','stale report Open replaced newer title');
 }finally{fixture.close()}
}

async function testSaveAfterEditsAndRefreshError(){
 const post=deferred<Response>();
 let submitted:{title:string;narrative:string;evidence_ids:string[]}|null=null;
 let completed=false;
 const fixture=mount('synthetic-project',(path,method,body)=>{
  if(path==='/projects/synthetic-project/reports'&&method==='GET')
   return completed?json({detail:'Synthetic report-list unavailable'},503):json([]);
  if(path==='/projects/synthetic-project/report-evidence'&&method==='GET')return json(fixtureEvidence);
  if(path==='/projects/synthetic-project/reports'&&method==='POST'){
   submitted=body as typeof submitted;
   return post.promise;
  }
  throw new Error('Unexpected mock API: '+method+' '+path);
 });
 try{
  await until(()=>evidenceCheckbox('ev-existing'),'synthetic evidence loaded');
  edit(titleInput(),'Submitted report title');
  evidenceCheckbox('ev-existing')!.click();
  await until(()=>findButton('Save report')&&!findButton('Save report')!.disabled,'Save report enabled');
  findButton('Save report')!.click();
  await until(()=>submitted!==null,'Save POST received frozen payload');
  edit(titleInput(),'Newer unsaved report title');
  completed=true;
  post.resolve(json(saved('Submitted report title')));
  await until(()=>document.querySelector('#mount .pd-report-error')?.textContent?.includes('was saved, but the report library could not refresh'),'post-commit refresh error');
  expect(titleInput().value==='Newer unsaved report title','Save response removed later user edit');
  expect(submitted!.title==='Submitted report title','Save payload mutated after submission');
  expect(document.querySelector('#mount .pd-report-notice')?.textContent?.includes('Newer draft edits were NOT included'),'missing factual snapshot warning');
 }finally{fixture.close()}
}

async function testQualityAfterSelectionEdit(){
 const captured=deferred<Response>();
 let started=false;
 const fixture=mount('synthetic-project',(path,method)=>{
  if(path==='/projects/synthetic-project/reports')return json([]);
  if(path==='/projects/synthetic-project/report-evidence')return json([...fixtureEvidence,auditEvidence]);
  if(path==='/projects/synthetic-project/quality'&&method==='GET')return json({version:0});
  if(path==='/projects/synthetic-project/report-quality'&&method==='POST'){
   started=true;
   return captured.promise;
  }
  throw new Error('Unexpected mock API: '+method+' '+path);
 });
 try{
  await until(()=>evidenceCheckbox('ev-existing'),'initial evidence available');
  findButton('Capture current Quality audit')!.click();
  await until(()=>started,'Quality capture POST initiated');
  evidenceCheckbox('ev-existing')!.click();
  captured.resolve(json({id:'ev-new-audit',dataset_version:0,findings_total:2}));
  await until(()=>document.querySelector('#mount .pd-report-notice')?.textContent?.includes('newer draft selection was not changed'),'audit update explains newer choice');
  expect(evidenceCheckbox('ev-existing')?.checked===true,'manual evidence choice was removed');
  expect(evidenceCheckbox('ev-new-audit')?.checked===false,'late audit silently added to newer selection');
 }finally{fixture.close()}
}

async function testStaleEvidenceList(){
 const first=deferred<Response>();
 let evidenceReads=0;
 const fixture=mount('synthetic-project',(path,method)=>{
  if(path==='/projects/synthetic-project/reports')return json([]);
  if(path==='/projects/synthetic-project/report-evidence'){
   evidenceReads++;
   return evidenceReads===1?first.promise:json([...fixtureEvidence,auditEvidence]);
  }
  if(path==='/projects/synthetic-project/quality'&&method==='GET')return json({version:0});
  if(path==='/projects/synthetic-project/report-quality'&&method==='POST')
   return json({id:'ev-new-audit',dataset_version:0,findings_total:1});
  throw new Error('Unexpected mock API: '+method+' '+path);
 });
 try{
  await until(()=>evidenceReads===1,'first initial evidence request');
  findButton('Capture current Quality audit')!.click();
  await until(()=>evidenceReads===2,'newer captured evidence refresh');
  await until(()=>evidenceCheckbox('ev-new-audit'),'fresh captured audit listed');
  first.resolve(json(fixtureEvidence));
  await tick(90);
  expect(!!evidenceCheckbox('ev-new-audit'),'old initial evidence replaced newer audit list');
 }finally{fixture.close()}
}

async function testExportAfterProjectSwitch(){
 const exported=deferred<Response>();
 let reportRequests=0;
 let exportStarted=false;
 const originalClick=HTMLAnchorElement.prototype.click;
 let downloads=0;
 HTMLAnchorElement.prototype.click=function(){downloads++};
 const fixture=mount('synthetic-project',(path,method)=>{
  if(path==='/projects/synthetic-project/reports')return json([{id:'synthetic-report',title:'Original report',revision:1,updated_at:'2026-10-25T00:00:00'}]);
  if(path==='/projects/synthetic-other/reports')return json([]);
  if(path.endsWith('/report-evidence'))return json(fixtureEvidence);
  if(path==='/reports/synthetic-report'){reportRequests++;return json(saved())}
  if(path==='/reports/synthetic-report/export/html?revision=1'){
   exportStarted=true;return exported.promise;
  }
  throw new Error('Unexpected mock API: '+method+' '+path);
 });
 try{
  await until(()=>reportRequests>=1&&!!findButton('Export HTML')&&!findButton('Export HTML')!.disabled,'saved report ready to export');
  findButton('Export HTML')!.click();
  await until(()=>exportStarted,'export download GET started');
  fixture.render('synthetic-other');
  await until(()=>titleInput().value==='Synthetic report title','project switch rendered fresh draft');
  exported.resolve(new Response('<!doctype html><html><body>Synthetic only</body></html>',{
   status:200,headers:{'Content-Type':'text/html','Content-Disposition':'attachment; filename="synthetic_report.html"'}
  }));
  await tick(110);
  expect(downloads===0,'stale export launched a download after project switch');
 }finally{fixture.close();HTMLAnchorElement.prototype.click=originalClick}
}

const cases:[string,()=>Promise<void>][]=[
 ['Editing while older Open is pending',testEditingWhileOpen],
 ['Save after draft edits and failed list refresh',testSaveAfterEditsAndRefreshError],
 ['Quality capture after evidence selection edits',testQualityAfterSelectionEdit],
 ['Older initial evidence list cannot replace newer captured list',testStaleEvidenceList],
 ['Export response after project change causes no download',testExportAfterProjectSwitch],
];
const results:{name:string;status:'PASS'|'FAIL';detail?:string}[]=[];
async function run(){
 const result=document.getElementById('p2-result');
 if(!result)return;
 for(const [name,fn] of cases){
  try{await fn();results.push({name,status:'PASS'})}
  catch(e){
   results.push({name,status:'FAIL',detail:e instanceof Error?e.message:String(e)});
   if(root){root.unmount();root=null}
  }
  await tick(40);
 }
 const passed=results.filter(r=>r.status==='PASS').length;
 const status=passed===results.length?'PASS':'FAIL';
 result.dataset.status=status;
 result.textContent=JSON.stringify({overall:status,passed,total:results.length,results},null,2);
}
window.addEventListener('error',event=>{
 const result=document.getElementById('p2-result');
 if(result&&result.dataset.status==='PENDING'){
  result.dataset.status='FAIL';
  result.textContent=JSON.stringify({overall:'FAIL',error:event.message});
 }
});
void run();
