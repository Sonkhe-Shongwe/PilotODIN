import React from 'react';
import {createRoot} from 'react-dom/client';
import {ReportWorkspace} from './ReportWorkspace';

/** Test-only: real FastAPI on a temporary loopback port with synthetic SQLite. */
const query=new URLSearchParams(location.search);
const backendPort=Number(query.get('backend_port'));
const projectA=query.get('project_a')||'';
const projectB=query.get('project_b')||'';
const reportId=query.get('report_id')||'';
const auditId=query.get('audit_id')||'';
const result=document.getElementById('p2-live-result');
if(!result||!Number.isInteger(backendPort)||backendPort<1024||backendPort>65535||
   !/^[a-f0-9]{32}$/.test(projectA)||!/^[a-f0-9]{32}$/.test(projectB)||
   !/^[a-f0-9]{32}$/.test(reportId)||!/^[a-f0-9]{32}$/.test(auditId))
 throw new Error('Invalid isolated full-stack fixture parameters');

const directFetch=window.fetch.bind(window);
const networkTrace:string[]=[];
window.fetch=((resource:RequestInfo|URL,init?:RequestInit)=>{
 const target=new URL(String(resource),location.href);
 if(target.hostname!=='127.0.0.1'||target.port!=='8000'||!target.pathname.startsWith('/api/'))
  return Promise.reject(new Error('Unexpected API destination blocked by P2 integration harness'));
 target.port=String(backendPort);
 const method=init?.method??'GET';
 const label=method+' '+target.pathname.replace(/\/[a-f0-9]{32}(?=\/|$)/g,'/{synthetic-id}')+target.search;
 return directFetch(target.toString(),init).then(response=>{
   networkTrace.push(label+' => HTTP '+response.status+' / '+(response.headers.get('content-type')??'no-content-type'));
   return response;
 },error=>{
   const reason=error instanceof Error?error.message:String(error);
   networkTrace.push(label+' => NETWORK ERROR '+reason);
   throw new Error(label+' failed: '+reason);
 });
}) as typeof fetch;

function expect(value:unknown,message:string):asserts value {if(!value)throw new Error(message)}
const sleep=(ms=40)=>new Promise<void>(r=>setTimeout(r,ms));
async function until<T>(check:()=>T|null|undefined|false,message:string):Promise<T>{
 const start=Date.now();
 while(Date.now()-start<5000){
  const found=check();
  if(found)return found as T;
  await sleep();
 }
 throw new Error('Timed out: '+message);
}
const host=document.getElementById('mount');
expect(host,'mount host missing');
const root=createRoot(host);
const title=()=>document.querySelector<HTMLInputElement>('#mount .pd-report-editor input:not([type=checkbox])');
const narrative=()=>document.querySelector<HTMLTextAreaElement>('#mount textarea');
const findButton=(label:string)=>[...document.querySelectorAll<HTMLButtonElement>('#mount button')].find(b=>b.textContent?.includes(label));
function setInput(el:HTMLInputElement|HTMLTextAreaElement,value:string){
 const proto=el instanceof HTMLTextAreaElement?HTMLTextAreaElement.prototype:HTMLInputElement.prototype;
 const setter=Object.getOwnPropertyDescriptor(proto,'value')?.set;
 expect(setter,'native input setter missing');
 setter.call(el,value);
 el.dispatchEvent(new Event('input',{bubbles:true}));
 el.dispatchEvent(new Event('change',{bubbles:true}));
}
async function readJSON(path:string){
 const r=await fetch('http://127.0.0.1:8000/api'+path);
 expect(r.ok,'Real backend rejected GET '+path+' '+r.status);
 return r.json();
}
const cases:{name:string;status:'PASS'|'FAIL';detail?:string}[]=[];
async function trial(name:string,fn:()=>Promise<void>){
 try{await fn();cases.push({name,status:'PASS'})}
 catch(e){cases.push({name,status:'FAIL',detail:String(e instanceof Error?e.message:e)})}
}
root.render(<ReportWorkspace projectId={projectA} defaultTitle="Synthetic empty composer"/>);
await trial('Real FastAPI report revision hydrates in mounted React',async()=>{
 await until(()=>title()?.value==='Synthetic Baseline Report','real persisted report hydrate');
 const saved=await readJSON('/reports/'+reportId+'?revision=1');
 expect(saved.project_id===projectA,'report project mismatch');
 expect(saved.evidence.some((e:{id:string})=>e.id===auditId),'preseed audit not present in saved report');
 expect(narrative()?.value==='Only synthetic audit findings are included.','saved narrative not hydrated');
 expect(!!findButton('Export PDF'),'real report export control absent');
});
await trial('Mounted React writes a revision; old PDF/HTML evidence remains frozen',async()=>{
 let stage='waiting for baseline';
 try {
 await until(()=>title()?.value==='Synthetic Baseline Report','baseline before revision');
 const input=title(),note=narrative();
 expect(input&&note,'editor elements missing');
 setInput(input,'Synthetic Revision Two');
 setInput(note,'Updated interpretation based only on a synthetic quality audit.');
 await until(()=>{const b=findButton('Save new revision');return b&&!b.disabled?b:null},'Save revision enabled');
 stage='save revision 2 through mounted UI';
 findButton('Save new revision')!.click();
 await until(()=>document.querySelector('#mount .pd-report-notice')?.textContent?.includes('Saved revision 2'),'UI save completion');
 stage='GET persisted revision 1';
 const old=await readJSON('/reports/'+reportId+'?revision=1');
 stage='GET persisted revision 2';
 const revised=await readJSON('/reports/'+reportId+'?revision=2');
 expect(old.title==='Synthetic Baseline Report','revision 1 overwritten');
 expect(revised.title==='Synthetic Revision Two','revision 2 title incorrect');
 expect(old.content_sha256!==revised.content_sha256,'saved digest did not change');
 expect(revised.evidence[0].id===auditId,'frozen evidence ID changed');
 for(const revision of [1,2]){
  stage='GET HTML export revision '+revision;
  const html=await fetch('http://127.0.0.1:8000/api/reports/'+reportId+'/export/html?revision='+revision);
  stage='GET PDF export revision '+revision;
  const pdf=await fetch('http://127.0.0.1:8000/api/reports/'+reportId+'/export/pdf?revision='+revision);
  stage='validate export HTTP response for revision '+revision;
  expect(html.status===200&&pdf.status===200,'report export failed');
  stage='read HTML export body for revision '+revision;
  expect((await html.text()).includes(revision===1?'Synthetic Baseline Report':'Synthetic Revision Two'),'HTML wrong revision');
  stage='read PDF export body for revision '+revision;
  const pdfBytes=new Uint8Array(await (await pdf.blob()).arrayBuffer());
  stage='validate PDF signature and filename for revision '+revision;
  expect(new TextDecoder().decode(pdfBytes.slice(0,5))==='%PDF-','PDF signature invalid');
  expect(pdf.headers.get('content-disposition')?.includes('_rev'+revision+'.pdf'),'PDF export filename revision wrong');
 }
 }catch(error){
  throw new Error('Revision/export stage ['+stage+']: '+(error instanceof Error?error.message:String(error)));
 }
});
await trial('Project switching excludes foreign report evidence and permits isolated audit',async()=>{
 root.render(<ReportWorkspace projectId={projectB} defaultTitle="Synthetic other project"/>);
 await until(()=>title()?.value==='Synthetic other project','project B mounted');
 await until(()=>document.querySelector('#mount .pd-report-library')?.textContent?.includes('No reports saved in this project yet'),'project B library empty');
 expect(!document.querySelector('#mount .pd-report-library')?.textContent?.includes('Synthetic Revision Two'),'project A report leaked into project B library');
 const otherReports=await readJSON('/projects/'+projectB+'/reports');
 expect(Array.isArray(otherReports)&&otherReports.length===0,'project B reports are not empty');
 const options=await readJSON('/projects/'+projectB+'/report-evidence');
 expect(!options.some((e:{id:string})=>e.id===auditId),'project A evidence appeared in B');
 const capture=findButton('Capture current Quality audit');
 expect(capture&&!capture.disabled,'B audit capture unavailable');
 capture.click();
 await until(()=>document.querySelector('#mount .pd-report-notice')?.textContent?.includes('Captured read-only Quality audit v0'),'B audit capture result');
 const newOptions=await readJSON('/projects/'+projectB+'/report-evidence');
 expect(newOptions.some((e:{source:string})=>e.source==='saved_quality_audit'),'new B audit not stored by backend');
 const stillA=await readJSON('/reports/'+reportId+'?revision=1');
 expect(stillA.title==='Synthetic Baseline Report','switch changed project A revision');
});
const passed=cases.filter(c=>c.status==='PASS').length;
const resultData={overall:passed===cases.length?'PASS':'FAIL',passed,total:cases.length,results:cases,
 network_trace:networkTrace.slice(-65)};
result!.setAttribute('data-status',resultData.overall);
result!.textContent=JSON.stringify(resultData,null,2);
