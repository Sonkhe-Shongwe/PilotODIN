import {useEffect,useState} from 'react';
import {BrainCircuit, Send, ShieldCheck, Sparkles, LoaderCircle} from 'lucide-react';
import {post} from './api';
import {RichText} from './RichText';
type MissingReport={column:string;missing_rows:number;missing_pct:number;row_numbers:number[];numeric_comparisons:{column:string;missing_group_median:number;other_group_median:number}[];categorical_comparisons:{column:string;groups:{label:string;missing_count:number;total_count:number}[]}[];caution:string};
type Msg={role:'user'|'assistant';content:string;source?:string;incomplete?:boolean;investigation?:MissingReport;diagnostic?:string};

const starters=['What is the dataset overview?','Which columns have missing values and why does it matter?','What quality issues could distort my analysis?','What features and validation concerns should I investigate?'];
export function AssistantWorkspace({projectId,onSettings}:{projectId:string;onSettings:()=>void}){
  const [messages,setMessages]=useState<Msg[]>([{role:'assistant',content:'Ask ODIN about this dataset. The desktop first tries its bundled offline model; if that fails, a clearly identified local analytical fallback remains available. Cloud AI requires your consent.',source:'READY'}]);
  const [question,setQuestion]=useState('');const [busy,setBusy]=useState(false);const [elapsed,setElapsed]=useState(0);
  useEffect(()=>{if(!busy){setElapsed(0);return}const started=Date.now();const timer=window.setInterval(()=>setElapsed(Math.floor((Date.now()-started)/1000)),1000);return()=>window.clearInterval(timer)},[busy]);
  const [provider,setProvider]=useState(localStorage.getItem('pilotodin-ai-provider-assistant')??'auto');
  async function ask(q:string,continuation?:string){
    if(busy||(!q.trim()&&!continuation))return;
    setBusy(true);if(!continuation){setQuestion('');setMessages(a=>[...a,{role:'user',content:q}])}
    try{
      const r=await post<{answer:string;provider:string;model:string;fallback:boolean;reason:string;local_status?:string;local_startup_issue?:string;incomplete?:boolean;finish_reason?:string;investigation?:MissingReport}>(`/projects/${projectId}/ai/insight`,
        {context:'assistant',question:q||'Continue the previous explanation.',selected_provider:provider,continuation_text:continuation??null});
      const diagnostic=r.fallback
        ? (provider==='local'?'Rules-only mode was selected. No language-model generation was requested.'
          : 'No language-model answer was generated. PilotODIN used verified local rules instead. '+(r.local_startup_issue?'Desktop startup: '+r.local_startup_issue+'. ':r.local_status&&r.local_status!=='not_requested'?'Local inference: '+r.local_status+'. ':'')+(r.reason??''))
        : undefined;
      setMessages(a=>{
        if(continuation&&a.length&&a[a.length-1].role==='assistant'){
          const last=a[a.length-1];return [...a.slice(0,-1),{...last,content:last.content+'\n\n'+r.answer,
            incomplete:r.incomplete,source:r.fallback?'VERIFIED RULES · NO LLM':`${r.provider.toUpperCase()} · ${r.model}`,diagnostic}];
        }
        return [...a,{role:'assistant',content:r.answer,source:r.fallback?'VERIFIED RULES · NO LLM':`${r.provider.toUpperCase()} · ${r.model}`,
          incomplete:r.incomplete,investigation:r.investigation,diagnostic}];
      });
    }catch(e){setMessages(a=>[...a,{role:'assistant',content:(e as Error).message,source:'ERROR'}])}
    finally{setBusy(false)}
  }
  return <div className="assistant-page"><section className="quality-banner"><div><div className="eyebrow">DATA SCIENCE COPILOT · HYBRID AI</div><h2>Ask your dataset</h2><p>Opt-in cloud reasoning grounded in local computations, with automatic provider failover and offline analytics.</p></div><BrainCircuit size={43}/></section>
    <div className="panel chat-panel"><div className="ai-choice"><label>Choose intelligence</label><select className="input" value={provider} onChange={e=>{setProvider(e.target.value);localStorage.setItem('pilotodin-ai-provider-assistant',e.target.value)}}><option value="auto">Smart Auto</option><option value="ollama">Offline Qwen3 (desktop) / Ollama (dev)</option><option value="gemini">Gemini</option><option value="groq">GroqCloud</option><option value="openrouter">OpenRouter</option><option value="local">Local analytics</option></select></div><div className="chat-messages">{messages.map((m,i)=><div key={i} className={'chat-message '+m.role}><span className="chat-role">{m.role==='assistant'?<Sparkles size={15}/>:null}{m.role==='assistant'?'PilotODIN':'You'} {m.source&&<small>· {m.source}</small>}</span><div className="chat-body"><RichText text={m.content}/>
        {m.investigation&&<div className="verified-investigation"><strong>Verified investigation · {m.investigation.column}</strong><p>{m.investigation.missing_rows} missing ({m.investigation.missing_pct}%). Local row numbers: {m.investigation.row_numbers.slice(0,30).join(', ')}.</p>
          {m.investigation.numeric_comparisons.map(c=><p key={c.column}><b>{c.column}:</b> median for missing rows {c.missing_group_median.toLocaleString()} vs other rows {c.other_group_median.toLocaleString()}.</p>)}
          {m.investigation.categorical_comparisons.map(c=><div key={c.column}><b>{c.column}</b><ul>{c.groups.map(g=><li key={g.label}>{g.label}: {g.missing_count} missing / {g.total_count} records</li>)}</ul></div>)}
          <small>{m.investigation.caution}</small></div>}
        {m.diagnostic&&<div className="ai-incomplete" role="status"><span>{m.diagnostic}</span> <button className="btn small" onClick={onSettings}>AI Settings</button></div>}
        {m.incomplete&&<div className="ai-incomplete"><span>ODIN reached the provider response limit. The explanation may be unfinished.</span><button className="btn small" disabled={busy} onClick={()=>void ask('Continue the previous explanation.',m.content)}>Continue answer →</button></div>}
        </div></div>)}</div>
      {busy&&<div role="status" className="ai-working"><LoaderCircle size={17} className="spin"/><span><strong>{provider==='local'?'Running deterministic local rules…':'Starting local model or evaluating available providers…'}</strong><small>{elapsed}s elapsed · model loading can be slow · fallback will be labelled if used</small></span></div>}
      <div className="chat-starters">{starters.map(s=><button key={s} onClick={()=>void ask(s)} disabled={busy}>{s}</button>)}</div>
      <form className="chat-form" onSubmit={e=>{e.preventDefault();void ask(question)}}><input className="input" value={question} maxLength={900} onChange={e=>setQuestion(e.target.value)} placeholder="Ask about your data, cleaning decisions, insights or modelling…" aria-label="Dataset question"/><button className="btn primary" disabled={busy||!question.trim()} type="submit"><Send size={16}/> {busy?'Thinking…':'Ask'}</button></form><p className="muted-caption"><ShieldCheck size={13}/> Only column metadata, aggregated calculations and recorded issue categories may be shared after consent. No dataset rows. <button className="text-action" onClick={onSettings}>Configure AI providers</button></p></div>
  </div>;
}
