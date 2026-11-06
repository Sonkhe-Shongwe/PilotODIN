import React from 'react';
import {createRoot} from 'react-dom/client';
import {UnifiedShell} from './UnifiedShell';
import {isDesktop} from './desktopBootstrap';
import './styles.css';
import './studio.css';
import './design-tokens.css';
import './finish-polish.css';

// Development-only real Tauri WebView2 shell. The isolated Tauri identifier
// is NOT the installed product, and no bundled engine or AI worker is spawned.
const aid=String(import.meta.env.VITE_P3_NATIVE_QA_PROJECT_A??'');
const bid=String(import.meta.env.VITE_P3_NATIVE_QA_PROJECT_B??'');
const allowed=import.meta.env.DEV&&
  import.meta.env.VITE_PILOTODIN_NATIVE_SMOKE==='1'&&
  import.meta.env.VITE_P3_NATIVE_SEMANTIC_QA==='1'&&
  location.origin==='http://127.0.0.1:5181'&&
  /^[a-f0-9]{32}$/.test(aid)&&/^[a-f0-9]{32}$/.test(bid)&&aid!==bid&&
  isDesktop()&&!!document.getElementById('root');
if(!allowed)throw new Error('P3 native QA requires an isolated synthetic Tauri window.');

const originalFetch=window.fetch.bind(window);
// Session storage retains only a synthetic POST counter across W2 reloads,
// never a business description or real user data. Invalid counters fail closed.
const saveCountKey='pilotodin-p3-native-qa-save-count';
const previousSaves=sessionStorage.getItem(saveCountKey);
let approvedSaves=previousSaves===null?0:Number(previousSaves);
if(!Number.isSafeInteger(approvedSaves)||approvedSaves<0||approvedSaves>2){
  throw new Error('Invalid synthetic P3 native save counter.');
}
window.fetch=((input:RequestInfo|URL,init?:RequestInit)=>{
  const raw=input instanceof Request?input.url:String(input);
  const url=new URL(raw,location.href);
  const method=(init?.method??(input instanceof Request?input.method:'GET')).toUpperCase();
  if(url.origin==='http://127.0.0.1:8000'&&url.pathname.startsWith('/api/')){
    if(method==='GET'||method==='HEAD')return originalFetch(input,init);
    // W1/W2: only two explicit owner-description POSTs on synthetic project A,
    // version 0. The server still validates the same payload and local origin.
    if(method==='POST'&&url.pathname==='/api/projects/'+aid+'/semantic-business-context'&&
       url.search===''&&approvedSaves<2&&typeof init?.body==='string'){
      let body:unknown=null;
      try{body=JSON.parse(init.body)}catch{return Promise.reject(new Error('Invalid QA save body.'))}
      if(body&&typeof body==='object'&&!Array.isArray(body)){
        const obj=body as Record<string,unknown>;
        const keys=Object.keys(obj).sort().join(',');
        const fields=obj.field_definitions;
        const valid=keys==='domain_description,expected_version,field_definitions,record_grain_description'&&
          obj.expected_version===0&&
          typeof obj.domain_description==='string'&&obj.domain_description.trim().length>=10&&
          obj.domain_description.length<=300&&
          typeof obj.record_grain_description==='string'&&obj.record_grain_description.trim().length>=10&&
          obj.record_grain_description.length<=300&&
          Array.isArray(fields)&&fields.length===1&&fields[0]?.column==='claim_amount'&&
          typeof fields[0]?.meaning==='string'&&fields[0].meaning.trim().length>=10&&
          fields[0].meaning.length<=300;
        if(valid){
          // Reserve the allowance before network activity. Failed saves require
          // a fresh isolated QA run rather than an unlimited retry bypass.
          approvedSaves++;
          sessionStorage.setItem(saveCountKey,String(approvedSaves));
          return originalFetch(input,init);
        }
      }
    }
  }
  return Promise.reject(new Error('Synthetic P3 native QA blocks all other writes and remote requests.'));
}) as typeof fetch;

// The app's native QA identity has an isolated localStorage profile.
localStorage.setItem('pilotodin-current',aid);
localStorage.setItem('pilotodin-workspace-tabs-v1-'+aid,JSON.stringify(['understand']));
localStorage.setItem('pilotodin-workspace-active-v1-'+aid,'understand');
if(location.hash!=='#/studio/understand')location.hash='#/studio/understand';

const banner=document.createElement('aside');
banner.setAttribute('role','status');
banner.setAttribute('aria-label','Synthetic native P3 acceptance scope');
banner.style.cssText='position:fixed;z-index:99999;bottom:8px;left:12px;padding:6px 10px;background:#fff8e5;border:2px solid #a36e1e;border-radius:6px;font:600 11px system-ui;color:#473008;pointer-events:none';
banner.textContent='P3 NATIVE SYNTHETIC QA - ONLY 2 BUSINESS-DESCRIPTION SAVES';
document.body.appendChild(banner);
createRoot(document.getElementById('root')!).render(<React.StrictMode><UnifiedShell/></React.StrictMode>);
