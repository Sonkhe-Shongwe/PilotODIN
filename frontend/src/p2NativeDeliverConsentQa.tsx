import React from 'react';
import {createRoot} from 'react-dom/client';
import {UnifiedShell} from './UnifiedShell';
import {isDesktop} from './desktopBootstrap';
import './styles.css';
import './studio.css';
import './design-tokens.css';
import './finish-polish.css';

// This development-only page mounts the unchanged real full UnifiedShell.
// It never launches a normal installed sidecar or authorises browser writes.
const id=String(import.meta.env.VITE_P2_NATIVE_DELIVER_PROJECT_ID??'');
const allowed=import.meta.env.DEV&&
  import.meta.env.VITE_P2_NATIVE_DELIVER_QA==='1'&&
  import.meta.env.VITE_PILOTODIN_NATIVE_SMOKE==='1'&&
  location.origin==='http://127.0.0.1:5177'&&
  /^[a-f0-9]{32}$/.test(id)&&isDesktop()&&!!document.getElementById('root');
if(!allowed)throw new Error('Refusing non-isolated full-shell native consent test.');

const originalFetch=window.fetch.bind(window);
window.fetch=((input:RequestInfo|URL,init?:RequestInit)=>{
  const raw=input instanceof Request?input.url:String(input);
  const url=new URL(raw,location.href);
  const method=(init?.method??(input instanceof Request?input.method:'GET')).toUpperCase();
  if(url.origin!=='http://127.0.0.1:8000'||!url.pathname.startsWith('/api/')||
     !['GET','HEAD'].includes(method)){
    return Promise.reject(new Error('Synthetic native consent QA blocks API mutations and remote requests.'));
  }
  return originalFetch(input,init);
}) as typeof fetch;

// Do not read localStorage from the owner's normal PilotODIN identifier.
// This standalone QA Tauri identifier gets its own disposable browser profile.
localStorage.setItem('pilotodin-current',id);
localStorage.setItem('pilotodin-workspace-tabs-v1-'+id,JSON.stringify(['deliver','explore','overview']));
localStorage.setItem('pilotodin-workspace-active-v1-'+id,'deliver');
if(location.hash!=='#/studio/deliver')location.hash='#/studio/deliver';

const banner=document.createElement('aside');
banner.setAttribute('role','status');
banner.setAttribute('aria-label','Synthetic native consent QA scope');
banner.style.cssText='position:fixed;z-index:99999;left:12px;bottom:8px;padding:5px 9px;background:#fff8e5;border:2px solid #a36e1e;border-radius:6px;font:600 11px/1.25 system-ui;color:#473008;pointer-events:none';
banner.textContent='SYNTHETIC QA - NO WRITES';
document.body.appendChild(banner);
createRoot(document.getElementById('root')!).render(<React.StrictMode><UnifiedShell/></React.StrictMode>);
