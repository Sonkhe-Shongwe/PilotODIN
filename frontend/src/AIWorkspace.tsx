import {useEffect,useLayoutEffect,useRef,useState,useSyncExternalStore} from 'react';
import {beginCloudSettingsOperation,finishCloudSettingsOperation,cloudConsentSnapshot,subscribeCloudConsent,cloudConsentIsCurrent,canTestCloud} from './cloudConsentSession';
import {createInsightRequestFence} from './insightRequestFence';
import {BrainCircuit,CheckCircle2,Cloud,KeyRound,LoaderCircle,LockKeyhole,RefreshCw,ShieldCheck,Sparkles,WifiOff} from 'lucide-react';
import {get,post,put,usesOwnedInference} from './api';
import {RichText} from './RichText';
import {ResourceSettings} from './ResourceSettings';

type ProviderId='gemini'|'groq'|'openrouter';
type ProviderState={id:ProviderId;connected:boolean;verified?:boolean;health?:{status:string;latency_ms?:number;tested_at_utc?:string;message?:string;http_status?:number};routine_model:string;deep_model:string};
type Settings={intelligence_mode:'hybrid'|'local'|'cloud';local_model:string;local_model_enabled:boolean;local_timeout_seconds:number;local_ai?:{status:string;model:string;runtime?:string;installed_models?:string[]};cloud_enabled:boolean;share_aggregates:boolean;auto_insights:boolean;provider_order:ProviderId[];timeout_seconds:number;preferred_provider?:string;workspace_preferences?:Record<string,string>;providers:ProviderState[];secret_storage:string;privacy_note:string;credential_warning?:string|null;settings_warning?:string|null};
type Analysis={answer:string;source:string;provider:string;model:string;fallback:boolean;reason?:string;incomplete?:boolean;finish_reason?:string;attempts:{provider:string;status:string}[];dataset_version:number;scope:string;investigation?:Record<string,unknown>};

const names:Record<ProviderId,string>={gemini:'Google Gemini',groq:'GroqCloud',openrouter:'OpenRouter'};

export function AISettings(){
  const [settings,setSettings]=useState<Settings|null>(null);const [keys,setKeys]=useState<Record<string,string>>({});
  const [busy,setBusy]=useState('');const [error,setError]=useState('');const [notice,setNotice]=useState('');
  const [elapsed,setElapsed]=useState(0);const [localStatus,setLocalStatus]=useState<{status:string;model:string;runtime?:string;installed_models?:string[]}|null>(null);
  const session=useSyncExternalStore(subscribeCloudConsent,cloudConsentSnapshot);
  const [confirmed,setConfirmed]=useState<Settings|null>(null);
  const [confirmedAt,setConfirmedAt]=useState(-1);
  const fresh=confirmed!==null&&confirmedAt===session.generation&&!session.pending;
  const dirty=settings!==confirmed;
  useEffect(()=>{
    let live=true;
    const start=cloudConsentSnapshot();
    if(!start.pending)get<Settings>('/ai/settings').then(value=>{
      if(live&&cloudConsentIsCurrent(start.generation)){
        setSettings(value);setConfirmed(value);setConfirmedAt(start.generation);
      }
    }).catch(e=>{if(live)setError(e.message)});
    return()=>{live=false};
  },[]);
  useEffect(()=>{if(!busy){setElapsed(0);return;}const start=Date.now();const t=window.setInterval(()=>setElapsed(Math.floor((Date.now()-start)/1000)),1000);return()=>window.clearInterval(t)},[busy]);
  async function settingsOperation(label:string,operation:()=>Promise<{value:Settings;notice:string}>){
    const ticket=beginCloudSettingsOperation(session.generation);
    if(!ticket)return;
    setBusy(label);setError('');setNotice('');
    let result:{value:Settings;notice:string}|null=null;
    try{result=await operation()}
    catch(e){setConfirmed(null);setConfirmedAt(-1);setError((e as Error).message)}
    finally{
      const settled=finishCloudSettingsOperation(ticket);
      if(settled&&result){
        setSettings(result.value);setConfirmed(result.value);setConfirmedAt(settled.generation);
        setNotice(result.notice);
      }
      setBusy('');
    }
  }
  async function reloadSettings(){
    if(busy||session.pending)return;
    await settingsOperation('refresh',async()=>({value:await get<Settings>('/ai/settings'),
      notice:'Saved settings refreshed. Unsaved edits were discarded.'}));
  }
  async function testProvider(provider:ProviderId){
    if(busy||!fresh||dirty||!canTestCloud(confirmed,provider))return;
    await settingsOperation('test:'+provider,async()=>{
      // Refresh the authoritative saved permission; draft flags never authorize.
      const saved=await get<Settings>('/ai/settings');
      if(!canTestCloud(saved,provider))return {value:saved,notice:'Connection test not sent: saved permission or credential unavailable.'};
      const r=await post<{status:string}>(`/ai/test/${provider}`,{cloud_intent:true});
      const value=await get<Settings>('/ai/settings');
      return {value,notice:`${names[provider]}: ${r.status==='connected'?'Connection verified by explicit test.':r.status==='busy'?'Another cloud operation is in progress.':r.status==='not_configured'?'Saved permission or credential unavailable.':'Connection not verified.'}`};
    });
  }
  async function testLocal(){setBusy('test:ollama');setError('');setNotice('');try{const result=await get<{status:string;model:string;runtime?:string;installed_models?:string[]}>('/ai/local/status');setLocalStatus(result);if(result.status==='ready')setNotice(`Local model server is responding: ${result.model}. This status check does not verify generation.`);else if(result.status==='model_missing')setError('The configured model is missing. A real generation request cannot succeed until its assets are available.');}catch(e){setError((e as Error).message)}finally{setBusy('')}}
  async function saveSettings(){
    if(!settings||!fresh||busy)return;
    const draft=settings;
    await settingsOperation('settings',async()=>{
      const value=await put<Settings>('/ai/settings',{cloud_enabled:draft.cloud_enabled,share_aggregates:draft.share_aggregates,auto_insights:draft.auto_insights,provider_order:draft.provider_order,timeout_seconds:draft.timeout_seconds,preferred_provider:draft.preferred_provider??'auto',workspace_preferences:draft.workspace_preferences??{},intelligence_mode:draft.intelligence_mode,local_model:draft.local_model,local_model_enabled:draft.local_model_enabled,local_timeout_seconds:draft.local_timeout_seconds});
      return {value,notice:'AI preferences saved. Cloud permission '+(value.cloud_enabled&&value.share_aggregates?'enabled for explicit requests.':'disabled.')};
    });
  }
  async function saveKey(p:ProviderId,remove=false){
    if(busy||!fresh||dirty)return;
    const key=keys[p];
    await settingsOperation(p,async()=>{
      const value=await put<Settings>('/ai/key',{provider:p,key:remove?null:key,remove});
      setKeys(x=>({...x,[p]:''}));
      return {value,notice:remove?`${names[p]} credential removed.`:`${names[p]} key saved. Connection not tested.`};
    });
  }
  function move(p:ProviderId,direction:number){if(!settings)return;const list=[...settings.provider_order];const i=list.indexOf(p),j=i+direction;if(j<0||j>=list.length)return;[list[i],list[j]]=[list[j],list[i]];setSettings({...settings,provider_order:list})}
  return <section className="ai-settings-page">
    <section className="quality-banner"><div><div className="eyebrow">ODIN INTELLIGENCE · SETTINGS</div><h2>Local-first ODIN intelligence</h2><p>Use bundled local intelligence on Windows desktop, or Ollama during development. Cloud AI is optional and requires a separate explicit request. Calculations stay in the verified local engine.</p></div><BrainCircuit size={42}/></section>
    {error&&<div className="alert-error">{error}</div>}{busy&&<div role="status" className="ai-working"><LoaderCircle size={18} className="spin"/><span><strong>{busy==='test:ollama'?'Checking local model server status (no generation)…':busy.startsWith('test:')?'Contacting provider and verifying connection…':busy==='settings'?'Saving preferences securely…':busy==='refresh'?'Reading saved preferences…':'Saving or removing credential…'}</strong><small>{elapsed}s elapsed · waiting for the local service</small></span></div>}{notice&&<div className="ai-notice"><CheckCircle2 size={16}/>{notice}</div>}
    <ResourceSettings/>
    <div className="ai-settings-actions"><button className="btn small" disabled={Boolean(busy)||session.pending} onClick={()=>void reloadSettings()}><RefreshCw size={14}/> Reload saved settings</button>{!fresh&&!session.pending&&<span className="muted-caption">Saved settings are not confirmed for this view. Reload before saving or testing.</span>}{fresh&&dirty&&<span className="muted-caption">Unsaved edits. Save preferences before changing credentials or testing.</span>}</div>
    {(confirmed?.credential_warning||confirmed?.settings_warning)&&<div className="alert-error" role="status">{confirmed.credential_warning||confirmed.settings_warning}</div>}
    {!settings?<div className="panel">Saved AI settings not loaded.</div>:<fieldset disabled={Boolean(busy)||session.pending||!fresh} style={{display:'contents'}}>
    <section className="panel ai-settings-panel"><div className="panel-title"><BrainCircuit size={19}/><h2>ODIN intelligence routing</h2></div>
      <p className="body-muted">Smart Auto uses the bundled offline model on desktop (or development Ollama), then verified local rules. It never escalates to a cloud provider automatically. Cloud reasoning requires a separate explicit request. No autonomous execution or dataset changes are performed.</p>
      <div className="ai-settings-actions"><label>Operating mode <select className="input" value={settings.intelligence_mode} onChange={e=>setSettings({...settings,intelligence_mode:e.target.value as Settings['intelligence_mode']})}><option value="hybrid">Hybrid: offline intelligence and optional explicit cloud</option><option value="local">Offline: bundled desktop AI / development Ollama, then verified local rules</option><option value="cloud">Cloud mode: explicit provider requests or verified local rules</option></select></label>
      <label>Local model <input className="input" aria-label="Development Ollama model identifier (bundled desktop model is fixed)" maxLength={80} value={settings.local_model} onChange={e=>setSettings({...settings,local_model:e.target.value})} placeholder="qwen3:1.7b"/></label>
      <label>Local timeout <select className="input" value={settings.local_timeout_seconds} onChange={e=>setSettings({...settings,local_timeout_seconds:Number(e.target.value)})}>{[30,45,60,90,120,180].map(v=><option key={v} value={v}>{v}s</option>)}</select></label></div>
      <label className="ai-toggle"><input type="checkbox" checked={settings.local_model_enabled} onChange={e=>setSettings({...settings,local_model_enabled:e.target.checked})}/><span><strong>Allow offline AI model inference</strong><small>Desktop: bundled Qwen3 on an authenticated local port. Development: Ollama at http://127.0.0.1:11434. Neither route needs the internet.</small></span></label>
      <div className="ai-settings-actions"><button className="btn" disabled={Boolean(busy)} onClick={()=>void testLocal()}>{busy==='test:ollama'?<LoaderCircle size={14} className="spin"/>:<RefreshCw size={14}/>} Check local model status</button><span className="muted-caption">{localStatus?`Status: ${localStatus.status} (${localStatus.model}, ${localStatus.runtime??'Ollama'})`:'This is a status probe, not an actual generation test.'}</span></div>
      {localStatus?.runtime==='bundled'&&localStatus.status==='idle'&&<p className="muted-caption">Idle means the desktop model server has not responded to this probe. It does not prove that generation will fail. Run an Ask ODIN question to launch Qwen3, then inspect the answer source and any local failure code.</p>}
       {localStatus&&localStatus.runtime!=='bundled'&&localStatus.status!=='ready'&&<p className="muted-caption">Development Ollama only: install the Ollama app, then run <code>ollama pull qwen3:1.7b</code> in PowerShell. The installed desktop should not require Ollama.</p>}
      <p className="muted-caption">The bundled model releases memory after 30 seconds without an inference request. The next question may take longer while the model reloads. Local analytics remain available.</p>
    </section>
    <section className="panel ai-settings-panel"><div className="panel-title"><ShieldCheck size={19}/><h2>Optional cloud access and privacy</h2></div>
      <label className="ai-toggle"><input type="checkbox" checked={settings.share_aggregates} onChange={e=>setSettings({...settings,share_aggregates:e.target.checked,cloud_enabled:e.target.checked?settings.cloud_enabled:false})}/><span><strong>I permit sending bounded dataset summaries for explicit cloud requests</strong><small>May include column names, row counts, supported numeric aggregates, quality issue categories, aggregate model metrics and your typed question. These summaries are not guaranteed anonymous. Do not type private information. Uploaded rows, local paths, individual prediction inputs and previous answers are excluded from the cloud payload.</small></span></label>
      <label className="ai-toggle"><input type="checkbox" checked={settings.cloud_enabled} disabled={!settings.share_aggregates} onChange={e=>setSettings({...settings,cloud_enabled:e.target.checked})}/><span><strong>Enable cloud reasoning</strong><small>Saved permission does not send data. A separate explicit request is required; disabling and saving revokes future cloud dispatch, but cannot recall bytes already sent.</small></span></label>
      <label className="ai-toggle"><input type="checkbox" checked={settings.auto_insights} onChange={e=>setSettings({...settings,auto_insights:e.target.checked})}/><span><strong>Generate workspace insights automatically</strong><small>Optional offline workspace insights only. Switching workspaces must never send cloud requests.</small></span></label>
      <div className="ai-settings-actions"><label>Preferred intelligence <select className="input" value={settings.preferred_provider??'auto'} onChange={e=>setSettings({...settings,preferred_provider:e.target.value})}><option value="auto">Smart Auto (local only)</option><option value="ollama">Ollama only</option><option value="gemini">Google Gemini (saved preference only)</option><option value="groq">GroqCloud (saved preference only)</option><option value="openrouter">OpenRouter (saved preference only)</option><option value="local">Local analytics only</option></select></label><label>Provider timeout <select className="input" value={settings.timeout_seconds} onChange={e=>setSettings({...settings,timeout_seconds:Number(e.target.value)})}>{[9,15,20,25,30,45].map(v=><option key={v} value={v}>{v} seconds</option>)}</select></label><button className="btn primary" onClick={()=>void saveSettings()} disabled={Boolean(busy)}>Save AI preferences</button></div>
      <p className="muted-caption"><LockKeyhole size={13}/> {settings.secret_storage==='windows_dpapi'?'Keys are encrypted with Windows DPAPI for your Windows user account.':'Non-Windows testing stores entered keys in memory only.'} Free API providers may retain prompts according to their policies.</p>
    </section>
    <section className="panel ai-settings-panel"><div className="panel-title"><Cloud size={19}/><h2>Provider preferences and credentials</h2></div>
      <p className="body-muted">Saving a key never contacts a provider. Test connection sends only a fixed Say READY handshake to the named provider, with the saved key, after saved cloud permission is confirmed. It may consume a request. OpenRouter may route this handshake downstream; project-data sharing through OpenRouter is disabled. No automatic provider or model retry. Ollama never requires an API key.</p>
      {settings.provider_order.map((p,index)=>{const state=settings.providers.find(x=>x.id===p);return <div className="ai-provider-row" key={p}>
        <div className="ai-provider-details"><b>{index+1}. {names[p]}</b><small>{state?.routine_model} · {state?.connected?'Key saved':'No key'}</small><span className={'health-status status-'+(state?.health?.status??'unverified')}>{!fresh||dirty?'Saved status not current':state?.verified===true&&state?.health?.status==='connected'?'Previously verified by explicit test':state?.health?.status==='not_configured'?'No key configured':state?.health?.status==='unavailable'?'Connection not verified':'Not tested'}</span></div>
        <div className="ai-provider-priority"><button className="btn small" disabled={index===0} aria-label={`Move ${names[p]} up`} onClick={()=>move(p,-1)}>↑</button><button className="btn small" disabled={index===settings.provider_order.length-1} aria-label={`Move ${names[p]} down`} onClick={()=>move(p,1)}>↓</button></div>
        <div className="ai-provider-secret"><input className="input" type="password" autoComplete="new-password" value={keys[p]??''} placeholder={state?.connected?'•••••••• (saved)':'Paste private API key'} onChange={e=>setKeys({...keys,[p]:e.target.value})}/><button className="btn primary small" disabled={busy!==''||dirty||!fresh||!(keys[p]??'').trim()} onClick={()=>void saveKey(p)}><KeyRound size={14}/> Save</button>{state?.connected&&<><button className="btn small" disabled={Boolean(busy)||dirty||!fresh||!canTestCloud(confirmed,p)} onClick={()=>void testProvider(p)}>{busy==='test:'+p?<LoaderCircle size={14} className="spin"/>:<RefreshCw size={14}/>} {busy==='test:'+p?'Connecting…':'Test connection'}</button><button className="btn small" disabled={Boolean(busy)||dirty||!fresh} onClick={()=>void saveKey(p,true)}>Remove</button></>}</div>
      </div>})}
    </section>
    </fieldset>}
  </section>
}

const labels:Record<string,string>={overview:'Dataset briefing',understand:'Understanding your data',quality:'Cleaning intelligence',explore:'Exploratory investigation',prepare:'Feature recommendations',model:'Model strategy',evaluate:'Evaluation interpretation',predict:'Prediction interpretation'};
const questions:Record<string,string>={overview:'What should I investigate first in this dataset and why?',understand:'Explain the key risks and what the available dataset summary tells us.',quality:'Which data quality issues should I prioritize, what might they distort, and what should I do safely?',explore:'What are the most meaningful patterns and which chart or statistical comparison should I try next?',prepare:'What are the important feature and leakage concerns for this target?',model:'Which modelling approaches and validation risks should I consider?',evaluate:'What can we conclude from the computed experiment results, and what should I test next?',predict:'What does this prediction mean for the named target, and what are its limitations?'};
const insightCache=new Map<string,Analysis>();
const insightTimestamps=new Map<string,number>();
function cachedInsight(key:string):Analysis|null{
  const value=insightCache.get(key);
  if(!value)return null;
  // Failed provider requests must not remain frozen as "local fallback" forever.
  const ttl=value.fallback?45_000:10*60_000;
  return Date.now()-(insightTimestamps.get(key)??0)<ttl?value:null;
}
const pendingInsights=new Map<string,Promise<Analysis>>();

export function AIInsight({projectId,scope,version,target,experimentId,prediction,onOpenSettings}:{projectId:string;scope:string;version:number;target?:string;experimentId?:string;prediction?:{prediction:string|number;probabilities?:{class:string|number;probability:number}[]}|null;onOpenSettings:()=>void}){
  const [result,setResult]=useState<Analysis|null>(null);const [busy,setBusy]=useState(false);const [error,setError]=useState('');
  const [investigation,setInvestigation]=useState('');const [investigationResult,setInvestigationResult]=useState('');
  const [auto,setAuto]=useState(false);const [selectedProvider,setSelectedProvider]=useState('auto');const fence=useRef(createInsightRequestFence()).current;const [elapsed,setElapsed]=useState(0);
  const fingerprint=JSON.stringify([projectId,scope,version,target,experimentId,prediction??null,selectedProvider]);
  useLayoutEffect(()=>fence.enter(),[fence,fingerprint]);
  useEffect(()=>{let live=true;get<Settings>('/ai/settings').then(r=>{if(live){setAuto(r.auto_insights&&(r.local_model_enabled||r.cloud_enabled&&r.share_aggregates));setSelectedProvider(localStorage.getItem('pilotodin-ai-provider-'+scope)??r.workspace_preferences?.[scope]??r.preferred_provider??'auto')}}).catch(()=>{});return()=>{live=false}},[fingerprint]);
  useLayoutEffect(()=>{setResult(cachedInsight(fingerprint));setError('');setInvestigationResult('');},[fingerprint]);
  useEffect(()=>{if(!busy){setElapsed(0);return;}const start=Date.now();const t=window.setInterval(()=>setElapsed(Math.floor((Date.now()-start)/1000)),1000);return()=>window.clearInterval(t)},[busy]);
  async function run(deep=false){if(busy)return;const ticket=fence.begin();if(!ticket)return;setBusy(true);setError('');try{
    const cacheKey=fingerprint+(deep?':deep':'');
    let call=pendingInsights.get(cacheKey);
    if(!call){call=post<Analysis>(`/projects/${projectId}/ai/insight`,{context:scope,question:questions[scope]??'',target:target||null,experiment_id:experimentId||null,prediction:prediction||null,deep,selected_provider:selectedProvider});pendingInsights.set(cacheKey,call)}
    let r:Analysis;
    try{r=await call}finally{if(pendingInsights.get(cacheKey)===call)pendingInsights.delete(cacheKey)}
    if(fence.isCurrent(ticket)){insightCache.set(fingerprint,r);insightTimestamps.set(fingerprint,Date.now());setResult(r)}
  }catch(e){if(fence.isCurrent(ticket))setError((e as Error).message)}finally{if(fence.finish(ticket))setBusy(false)}}
  useEffect(()=>{if(auto&&!cachedInsight(fingerprint))void run(false)},[auto,fingerprint]);
  async function continueInsight(){if(!result||busy)return;const ticket=fence.begin();if(!ticket)return;setBusy(true);setError('');try{
    const continuationProvider = result.source === 'local_llm' ? 'ollama' : selectedProvider;
    const r=await post<Analysis>(`/projects/${projectId}/ai/insight`,{context:scope,question:'Continue the previous explanation.',target:target||null,experiment_id:experimentId||null,deep:true,selected_provider:continuationProvider,continuation_text:result.answer});
    if(fence.isCurrent(ticket))setResult({...r,answer:result.answer+'\n\n'+r.answer});
  }catch(e){if(fence.isCurrent(ticket))setError((e as Error).message)}finally{if(fence.finish(ticket))setBusy(false)}}
  async function investigate(){if(!investigation||busy)return;const ticket=fence.begin();if(!ticket)return;setBusy(true);setError('');try{const outcome=await post<Record<string,unknown>>(`/projects/${projectId}/investigate`,{operation:investigation});if(fence.isCurrent(ticket))setInvestigationResult(JSON.stringify(outcome,null,2))}catch(e){if(fence.isCurrent(ticket))setError((e as Error).message)}finally{if(fence.finish(ticket))setBusy(false)}}
  if(!labels[scope])return null;
  return <section className="panel ai-intelligence-panel"><div className="panel-title"><BrainCircuit size={20}/><h2>ODIN Intelligence · {labels[scope]}</h2><span className="pill">{result?(result.fallback?'VERIFIED LOCAL RULES':`${result.provider.toUpperCase()} · ${result.model}`):'READY'}</span></div>
    {!result&&<p className="body-muted">AI recommendations grounded in current dataset calculations. Click to investigate; no cleaning or training is executed automatically.</p>}
    {result&&<div className="ai-answer"><RichText text={result.answer}/>{result.incomplete&&<div className="ai-incomplete"><span>Response limit reached; this explanation may be incomplete.</span><button className="btn small" disabled={busy} onClick={()=>void continueInsight()}>Continue answer →</button></div>}</div>}
    {result?.fallback&&<p className="muted-caption"><WifiOff size={14}/> Local fallback: {result.attempts?.some(a=>a.status.includes('503'))?'Cloud capacity temporarily unavailable (503). Retrying later may succeed.':result.reason}</p>}
    {busy&&<div className="ai-working" role="status" aria-live="polite"><LoaderCircle size={18} className="spin"/><span><strong>{selectedProvider==='local'?'Computing verified local analysis…':usesOwnedInference()&&selectedProvider==='auto'?'Preparing context and requesting offline resource admission…':`Requesting ${selectedProvider==='auto'?'Hybrid intelligence':selectedProvider}…`}</strong><small>{elapsed}s elapsed · {usesOwnedInference()?'waiting for the selected route; verified fallback will be labelled if used':'automatic fallback may be attempted'} · no dataset rows are sent</small></span></div>}
    {error&&<div className="alert-error">{error}</div>}
    <div className="ai-choice"><label htmlFor={'odin-provider-'+scope}>Intelligence</label><select id={'odin-provider-'+scope} className="input" value={selectedProvider} disabled={busy} onChange={e=>{setSelectedProvider(e.target.value);localStorage.setItem('pilotodin-ai-provider-'+scope,e.target.value);setResult(null)}}><option value="auto">{usesOwnedInference()?"Smart Auto (local only)":"Hybrid routing (default)"}</option><option value="ollama">Ollama only</option><option value="gemini">Gemini first</option><option value="groq">GroqCloud (saved preference only)</option><option value="openrouter">OpenRouter (saved preference only)</option><option value="local">Verified local analytics (no LLM)</option></select></div>
    <div className="ai-panel-actions"><button className="btn primary" disabled={busy} onClick={()=>void run(false)}>{busy?<LoaderCircle className="spin" size={16}/>:<Sparkles size={16}/>} {result?'Refresh analysis':'Investigate with ODIN'}</button><button className="btn" disabled={busy} onClick={()=>void run(true)}>Deeper reasoning</button><button className="btn" onClick={onOpenSettings}><RefreshCw size={15}/> AI Settings</button></div>
    <details className="odin-toolbox"><summary>Verified local investigations · no AI code execution</summary><div className="ai-choice"><select className="input" value={investigation} disabled={busy} onChange={e=>setInvestigation(e.target.value)} aria-label="Choose analytical investigation"><option value="">Choose investigation…</option><option value="overview">Dataset facts</option><option value="quality_summary">Quality and outlier warnings</option><option value="recommend_charts">Recommended charts</option></select><button className="btn" disabled={!investigation||busy} onClick={()=>void investigate()}>Run investigation</button></div>{investigationResult&&<pre className="investigation-output">{investigationResult}</pre>}</details>
    <p className="muted-caption">Ollama runs on this device. Consented cloud requests include bounded statistics and your typed question. AI explanations are suggestions, never verified computations or authorisation to change data.</p>
  </section>
}
