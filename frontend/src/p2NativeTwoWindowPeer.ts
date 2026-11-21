import {isDesktop} from './desktopBootstrap';

// A second native WebView with the SAME localhost origin as full-shell A.
// No backend/API calls: one button updates only the shared project selector key.
const projectA=String(import.meta.env.VITE_P2_NATIVE_DELIVER_PROJECT_ID??'');
const projectB=String(import.meta.env.VITE_P2_NATIVE_TWO_WINDOW_PROJECT_B??'');
const root=document.getElementById('root');
const allowed=import.meta.env.DEV&&
 import.meta.env.VITE_P2_NATIVE_TWO_WINDOW_QA==='1'&&
 import.meta.env.VITE_P2_NATIVE_DELIVER_QA==='1'&&
 import.meta.env.VITE_PILOTODIN_NATIVE_SMOKE==='1'&&
 location.origin==='http://127.0.0.1:5177'&&
 isDesktop()&&!!root&&
 /^[a-f0-9]{32}$/.test(projectA)&&/^[a-f0-9]{32}$/.test(projectB)&&
 projectA!==projectB;
if(!allowed)throw new Error('Refusing non-isolated two-window QA peer');

const heading=document.createElement('h1');
heading.textContent='Synthetic project selection (window B)';
const instructions=document.createElement('p');
instructions.textContent='In window A, edit a disposable Deliver note first. Then click below to change only the shared project selection to B. Window A must retain the edited report and show a cross-window warning without a browser confirmation.';
const button=document.createElement('button');
button.type='button';
button.textContent='Select synthetic project B in this window';
const status=document.createElement('p');
status.setAttribute('role','status');
status.textContent='No selection change sent.';
button.addEventListener('click',()=>{
 localStorage.setItem('pilotodin-current',projectB);
 status.textContent='B selection written to this QA origin. Check window A for a warning and intact Deliver note. This does NOT prove cross-window delivery on its own.';
});
const reminder=document.createElement('p');
reminder.textContent='No uploads, saves, exports, models, AI or real project data. Close both QA windows after the test.';
root!.style.cssText='font:15px/1.55 system-ui,sans-serif;padding:22px;color:#20314c;max-width:510px';
button.style.cssText='padding:13px 16px;background:#eee9ff;border:1px solid #b3a8fb;border-radius:8px;cursor:pointer;font-weight:700';
root!.append(heading,instructions,button,status,reminder);
