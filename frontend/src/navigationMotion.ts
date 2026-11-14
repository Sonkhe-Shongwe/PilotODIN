/** Coordinated and interruptible route animation. Never duplicates mounted workspaces. */
import {flushSync} from 'react-dom';
let animation:Animation|null=null;
let sequence=0;
const clear=()=>{animation?.cancel();animation=null;document.documentElement.classList.remove('po-route-animating')};
function commit(hash:string,cb?:()=>void){flushSync(()=>{location.hash=hash;cb?.();window.dispatchEvent(new Event('pilotodin:route-commit'))})}
function ms(name:string,fall:number){const v=parseFloat(getComputedStyle(document.documentElement).getPropertyValue(name));return Number.isFinite(v)?v:fall}
export function navigateHashSmoothly(hash:string,cb?:()=>void){
 if(location.hash===hash){cb?.();return}
 const id=++sequence;
 clear();
 const el=document.querySelector<HTMLElement>('.po-primary-pane');
 const reduced=window.matchMedia?.('(prefers-reduced-motion: reduce)').matches??false;
 if(!el||!el.animate||reduced){commit(hash,cb);return}
 document.documentElement.classList.add('po-route-animating');
 try{
  const out=el.animate([{opacity:1,transform:'translateY(0)'},{opacity:.25,transform:'translateY(-7px)'}],{duration:ms('--po-motion-exit',220),easing:'ease-in',fill:'forwards'});
  animation=out;
  void out.finished.then(()=>{
   if(id!==sequence)return;
   out.cancel();
   commit(hash,cb);
   if(id!==sequence)return;
   const target=document.querySelector<HTMLElement>('.po-primary-pane');
   if(!target){clear();return}
   const incoming=target.animate([{opacity:.2,transform:'translateY(16px) scale(.994)'},{opacity:1,transform:'translateY(0) scale(1)'}],{duration:ms('--po-motion-stage',500),easing:'cubic-bezier(.16,1,.3,1)',fill:'forwards'});
   animation=incoming;
   void incoming.finished.catch(()=>{}).finally(()=>{if(id===sequence)clear()});
  }).catch(()=>{if(id===sequence){clear();commit(hash,cb)}});
 }catch{if(id===sequence){clear();commit(hash,cb)}}
}
