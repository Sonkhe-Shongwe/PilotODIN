import React from 'react';
import {createRoot} from 'react-dom/client';
import {ReportWorkspace} from './ReportWorkspace';
import {isDesktop} from './desktopBootstrap';

/** Dev-only UI: real ReportWorkspace, real HTTP, real Rust Save As, no mocks. */
const port=Number(import.meta.env.VITE_P2_CHAIN_API_PORT);
const projectId=String(import.meta.env.VITE_P2_CHAIN_PROJECT_ID??'');
const reportId=String(import.meta.env.VITE_P2_CHAIN_REPORT_ID??'');
const expectedHtml=String(import.meta.env.VITE_P2_CHAIN_HTML_NAME??'');
const expectedPdf=String(import.meta.env.VITE_P2_CHAIN_PDF_NAME??'');
const status=document.getElementById('qa-status');
const htmlResult=document.getElementById('qa-html');
const pdfResult=document.getElementById('qa-pdf');
const ready=document.getElementById('qa-ready');
const mount=document.getElementById('report-mount');
const valid=import.meta.env.DEV&&
  Number.isInteger(port)&&port>=1024&&port<=65535&&
  /^[a-f0-9]{32}$/.test(projectId)&&/^[a-f0-9]{32}$/.test(reportId)&&
  expectedHtml===`pilotodin_report_${reportId.slice(0,12)}_rev2.html`&&
  expectedPdf===`pilotodin_report_${reportId.slice(0,12)}_rev2.pdf`&&
  !!status&&!!mount&&!!htmlResult&&!!pdfResult&&!!ready&&isDesktop();
if(!valid)throw new Error('Test-only Tauri environment or synthetic fixture identity is invalid.');

const original=window.fetch.bind(window);
window.fetch=((resource:RequestInfo|URL,init?:RequestInit)=>{
  const url=new URL(String(resource),location.href);
  if(url.hostname!=='127.0.0.1'||url.port!=='8000'||!url.pathname.startsWith('/api/')){
    return Promise.reject(new Error('P2 synthetic native chain blocked unexpected fetch destination.'));
  }
  url.port=String(port);
  return original(url.toString(),init);
}) as typeof fetch;

status!.textContent='Synthetic report is loading from isolated FastAPI. No real user data is accessed.';
createRoot(mount!).render(<ReportWorkspace projectId={projectId} defaultTitle="Synthetic Native Chain QA"/>);

const observed={html:false,pdf:false};
const observer=new MutationObserver(()=>{
  const exportButtons=[...mount!.querySelectorAll<HTMLButtonElement>('button')]
    .filter(x=>x.textContent?.includes('Export HTML')||x.textContent?.includes('Export PDF'));
  const savedRevision=mount!.textContent?.includes('Saved revision 2')??false;
  const enabled=exportButtons.length===2&&exportButtons.every(x=>!x.disabled);
  if(savedRevision&&enabled)ready!.textContent='PASS: Actual persisted revision 2 loaded; both Export buttons ready.';
  const notice=mount!.querySelector<HTMLElement>('.pd-report-notice')?.textContent??'';
  if(notice.includes('Saved report revision 2 to '+expectedHtml+' using Windows Save As')){
     observed.html=true;htmlResult!.textContent='PASS: ReportWorkspace HTML export invoked native Save As.';
  }
  if(notice.includes('Saved report revision 2 to '+expectedPdf+' using Windows Save As')){
     observed.pdf=true;pdfResult!.textContent='PASS: ReportWorkspace PDF export invoked native Save As.';
  }
  const error=mount!.querySelector<HTMLElement>('.pd-report-error')?.textContent;
  if(error)status!.textContent='Error in actual ReportWorkspace: '+error;
  if(observed.html&&observed.pdf)status!.textContent='PASS: Both report exports completed native Save As. Close this window and finish terminal checks.';
});
observer.observe(mount!,{childList:true,subtree:true,characterData:true});
