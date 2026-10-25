import {useEffect,useState} from 'react';
import {Gauge,RefreshCw,Save,ShieldCheck} from 'lucide-react';
import {get,put} from './api';

export type ResourceMode='adaptive'|'low_memory'|'performance';
type ResourceStatus={
 policy:{mode:ResourceMode;source:'default'|'saved'|'fallback';warning:string|null};
 memory:{status:'observed'|'unavailable';total_gib:number|null;available_gib:number|null;source:string;measured_at_utc:string;note:string};
 policy_effect:string;offline_8gb_ai_feasibility:string;
};

const DESCRIPTIONS:Record<ResourceMode,string>={
 adaptive:'Use measured memory as input to future workload decisions (recommended).',
 low_memory:'Prioritize responsiveness and serial heavy jobs when scheduling is enabled.',
 performance:'Favor throughput when hardware permits. Hard safety limits always remain.',
};

export function ResourceSettings(){
 const [status,setStatus]=useState<ResourceStatus|null>(null);
 const [draft,setDraft]=useState<ResourceMode>('adaptive');
 const [busy,setBusy]=useState<'load'|'refresh'|'save'|''>('load');
 const [error,setError]=useState('');
 const [notice,setNotice]=useState('');
 useEffect(()=>{
  let active=true;
  get<ResourceStatus>('/resource/status').then(result=>{
   if(!active)return;setStatus(result);setDraft(result.policy.mode);setBusy('');
  }).catch(e=>{if(active){setError((e as Error).message);setBusy('')}});
  return()=>{active=false};
 },[]);
 async function refresh(){
  if(busy)return;
  setBusy('refresh');setError('');setNotice('');
  try{
   const current=await get<ResourceStatus>('/resource/status');
   setStatus(current);
   // Preserve unsaved selection when refreshing the hardware reading.
  }catch(e){setError((e as Error).message)}
  finally{setBusy('')}
 }
 async function save(){
  if(busy||!status)return;
  setBusy('save');setError('');setNotice('');
  try{
   const current=await put<ResourceStatus>('/resource/policy',{mode:draft});
   setStatus(current);setDraft(current.policy.mode);
   setNotice('Resource preference saved on this device. Heavy-work scheduling is not enabled in this P1 release.');
  }catch(e){setError((e as Error).message)}
  finally{setBusy('')}
 }
 const memory=status?.memory;
 return <section className="panel ai-settings-panel" aria-labelledby="resource-settings-heading">
  <div className="panel-title"><Gauge size={19}/><h2 id="resource-settings-heading">Resource-Aware Mode</h2></div>
  <p className="body-muted">Read-only memory status and a saved preference for this device. Modes are advisory in P1: they do not yet throttle training, load Qwen, or change resource limits.</p>
  {error&&<div className="alert-error" role="alert">{error}</div>}
  {notice&&<div className="ai-notice" role="status"><ShieldCheck size={16}/>{notice}</div>}
  {status?.policy.warning&&<div className="alert-error" role="alert">{status.policy.warning} Select a mode and save to replace invalid settings.</div>}
  <div className="ai-settings-actions">
   <label>Resource policy
    <select className="input" aria-label="Resource policy" value={draft} disabled={!status||Boolean(busy)}
     onChange={e=>setDraft(e.target.value as ResourceMode)}>
     <option value="adaptive">Adaptive (recommended)</option>
     <option value="low_memory">Low-memory</option>
     <option value="performance">Performance</option>
    </select>
   </label>
   <button className="btn primary" type="button" disabled={!status||Boolean(busy)||status.policy.mode===draft}
    onClick={()=>void save()}><Save size={14}/> {busy==='save'?'Saving…':'Save resource preference'}</button>
  </div>
  <p className="muted-caption">{DESCRIPTIONS[draft]} {status&&<span>Saved mode: {status.policy.mode.replace('_',' ')} ({status.policy.source}).</span>}</p>
  <div className="ai-settings-actions">
   <div role="status" aria-live="polite" className="body-muted">
    {busy==='load'?'Measuring local memory…':memory?.status==='observed'&&memory.total_gib!==null&&memory.available_gib!==null
      ?<><strong>Available RAM: {memory.available_gib.toFixed(2)} GiB</strong> of {memory.total_gib.toFixed(2)} GiB physical RAM.</>
      :'RAM reading unavailable. No capacity is assumed.'}
   </div>
   <button type="button" className="btn" disabled={Boolean(busy)} onClick={()=>void refresh()}>
    <RefreshCw size={14}/> {busy==='refresh'?'Refreshing…':'Refresh memory'}
   </button>
  </div>
  <p className="muted-caption">{memory?.note??'Status uses local read-only measurements.'} No processes are inspected or stopped. Offline Qwen/8 GB concurrent workload remains unverified.</p>
 </section>;
}
