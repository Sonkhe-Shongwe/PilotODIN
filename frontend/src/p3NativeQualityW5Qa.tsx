import React from 'react';
import {createRoot} from 'react-dom/client';
import {UnifiedShell} from './UnifiedShell';
import {isDesktop} from './desktopBootstrap';
import './styles.css';
import './studio.css';
import './design-tokens.css';
import './finish-polish.css';

// Standalone Windows WebView2 W5 acceptance harness. Does not replace W1-W4.
// Never loaded in a production build or in the installed product's profile.
const pid=String(import.meta.env.VITE_P3_NATIVE_W5_PROJECT??'');
const issueId=String(import.meta.env.VITE_P3_NATIVE_W5_ISSUE??'');
const API='http://127.0.0.1:8000';
const allowed=import.meta.env.DEV&&
  import.meta.env.VITE_PILOTODIN_NATIVE_SMOKE==='1'&&
  import.meta.env.VITE_P3_NATIVE_QUALITY_W5_QA==='1'&&
  location.origin==='http://127.0.0.1:5178'&&
  /^[a-f0-9]{32}$/.test(pid)&&issueId.length>0&&issueId.length<=128&&
  isDesktop()&&!!document.getElementById('root');
if(!allowed)throw new Error('P3 W5 requires a fresh synthetic native Tauri QA window.');

const nativeFetch=window.fetch.bind(window);
const key='pilotodin-p3-native-w5-write-budget';
type Budget={proposals:number;commits:number};
let budget:Budget;
try{
  const stored=JSON.parse(sessionStorage.getItem(key)??'{"proposals":0,"commits":0}') as Budget;
  if(!stored||typeof stored!=='object'||Array.isArray(stored)||
     Object.keys(stored).sort().join(',')!=='commits,proposals'||
     !Number.isInteger(stored.proposals)||!Number.isInteger(stored.commits)||
     stored.proposals<0||stored.proposals>1||stored.commits<0||stored.commits>1||
     stored.commits>stored.proposals)throw new Error('Invalid budget');
  budget=stored;
}catch{throw new Error('P3 native W5 guarded write budget is invalid; begin a fresh isolated QA run.');}

type Receipt={project_id:string;operation:string;expected_version:number;
  proposal_id:string;proposal_hash:string;changed_cells:number};
let receipt:Receipt|null=null;
function refuse(message:string):Promise<Response>{
  return Promise.resolve(new Response(JSON.stringify({detail:message}),{
    status:403,headers:{'Content-Type':'application/json'},
  }));
}
function saveBudget(){sessionStorage.setItem(key,JSON.stringify(budget));}
function jsonBody(init?:RequestInit):Record<string,unknown>|null{
  if(typeof init?.body!=='string')return null;
  try{
    const parsed:unknown=JSON.parse(init.body);
    return parsed&&typeof parsed==='object'&&!Array.isArray(parsed)
      ?parsed as Record<string,unknown>:null;
  }catch{return null;}
}
window.fetch=((input:RequestInfo|URL,init?:RequestInit):Promise<Response>=>{
  const raw=input instanceof Request?input.url:String(input);
  const url=new URL(raw,location.href);
  const method=(init?.method??(input instanceof Request?input.method:'GET')).toUpperCase();
  if(url.origin===location.origin&&(method==='GET'||method==='HEAD'))
    return nativeFetch(input,init);
  if(url.origin!==API||!url.pathname.startsWith('/api/'))
    return refuse('P3 W5 native QA blocked an external or unrelated request.');
  if(method==='GET'||method==='HEAD'){
    const scope='/api/projects/'+pid;
    const readable=url.pathname===scope||url.pathname.startsWith(scope+'/')||
      ['/api/projects','/api/projects/manage','/api/ai/settings'].includes(url.pathname);
    return readable?nativeFetch(input,init):refuse('W5 blocked a read outside the synthetic project.');
  }
  const body=jsonBody(init);
  if(method==='POST'&&url.search===''&&
     url.pathname==='/api/projects/'+pid+'/quality/proposals'&&
     budget.proposals===0&&budget.commits===0&&body&&
     Object.keys(body).sort().join(',')==='expected_version,issue_id,operation'&&
     body.operation==='approve'&&body.expected_version===0&&body.issue_id===issueId){
    budget.proposals=1;saveBudget(); // Reserve before sending; no retry after failure.
    return nativeFetch(input,init).then(async response=>{
      if(response.ok){
        try{
          const r=await response.clone().json() as Receipt;
          if(r.project_id===pid&&r.operation==='approve'&&r.expected_version===0&&
             r.changed_cells===2&&/^[a-f0-9]{32,64}$/.test(r.proposal_id)&&
             /^[a-f0-9]{64}$/.test(r.proposal_hash))receipt=r;
        }catch{/* Refuse the follow-up commit if receipt parsing failed. */}
      }
      return response;
    });
  }
  if(method==='POST'&&url.search===''&&
     url.pathname==='/api/projects/'+pid+'/quality/commit'&&
     budget.proposals===1&&budget.commits===0&&receipt&&body&&
     Object.keys(body).sort().join(',')==='proposal_hash,proposal_id'&&
     body.proposal_id===receipt.proposal_id&&body.proposal_hash===receipt.proposal_hash){
    budget.commits=1;saveBudget(); // Explicit human UI click is still required.
    receipt=null;
    return nativeFetch(input,init);
  }
  return refuse('W5 refused an unreviewed, repeated or out-of-scope write. No API request was sent.');
}) as typeof fetch;

// Isolated Tauri identity owns its own browser storage. No user project is loaded.
localStorage.setItem('pilotodin-current',pid);
localStorage.setItem('pilotodin-workspace-tabs-v1-'+pid,JSON.stringify(['quality','understand']));
localStorage.setItem('pilotodin-workspace-active-v1-'+pid,'quality');
if(location.hash!=='#/studio/quality')location.hash='#/studio/quality';

const banner=document.createElement('aside');
banner.setAttribute('role','status');
banner.setAttribute('aria-label','Synthetic native P3 W5 acceptance scope');
banner.style.cssText='position:fixed;z-index:99999;bottom:8px;left:12px;padding:6px 10px;background:#fff8e5;border:2px solid #a36e1e;border-radius:6px;font:600 11px system-ui;color:#473008;pointer-events:none';
banner.textContent='P3 W5 SYNTHETIC QA - ONE REVIEWED REGION CORRECTION ONLY';
document.body.appendChild(banner);
createRoot(document.getElementById('root')!).render(<React.StrictMode><UnifiedShell/></React.StrictMode>);
