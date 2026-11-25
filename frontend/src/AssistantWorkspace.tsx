import {useEffect,useLayoutEffect,useRef,useState,useSyncExternalStore} from 'react';
import {cloudConsentSnapshot,subscribeCloudConsent,cloudConsentIsCurrent,isLocalPanelProvider,localPanelProvider,projectCloudProviderName,projectCloudHold,projectCloudDisclosure,localPanelRequest,localPanelMayContinue} from './cloudConsentSession';
import {createInsightRequestFence} from './insightRequestFence';
import {BrainCircuit, Send, ShieldCheck, Sparkles, LoaderCircle} from 'lucide-react';
import {usesOwnedInference,post} from './api';
import {RichText} from './RichText';
type MissingReport={column:string;missing_rows:number;missing_pct:number;row_numbers:number[];numeric_comparisons:{column:string;missing_group_median:number;other_group_median:number}[];categorical_comparisons:{column:string;groups:{label:string;missing_count:number;total_count:number}[]}[];caution:string};
type GroupStat={group:string|null;matching_rows:number}&(
  {missing_rows:number;percent:number|null}|{usable_rows:number;excluded_rows:number;value:number|null});
type LocalFacts={groups?:GroupStat[];blank_group?:GroupStat};
type LocalFollowUp={project_id:string;dataset_version:number;question:string};
type Msg={role:'user'|'assistant';content:string;source?:string;answerSource?:string;incomplete?:boolean;investigation?:MissingReport;diagnostic?:string;facts?:LocalFacts;version?:number};

const starters=['What is the dataset overview?','Which columns have missing values and why does it matter?','What quality issues could distort my analysis?','What features and validation concerns should I investigate?'];
const localQuestions=['What is the dataset overview?', 'Has training started?'];
const localTemplates=[
  {label:'Ask about missing values',question:'Why are values missing in "Column name"?',fields:['Column name'],
    hint:'Replace Column name with a column from your dataset, keeping the double quotes.'},
  {label:'Calculate a labelled rate',question:'Positive rate for "Outcome column" = "Positive value"',fields:['Outcome column','Positive value'],
    hint:'Replace Outcome column and Positive value with the exact column and label from your dataset. Keep both pairs of double quotes.'},
  {label:'Compare missingness by group',question:'Show missing "Measure column" by "Group column"',fields:['Measure column','Group column'],
    hint:'Replace Measure column and Group column with exact names from your dataset. Keep both pairs of double quotes.'},
  {label:'Summarise a filtered group',question:'Median "Measure column" where "Filter column" = "Filter value"',fields:['Measure column','Filter column','Filter value'],
    hint:'Replace the measure, filter column and filter value with names and a value from your dataset. Keep the double quotes.'},
];

function groupResult(group:GroupStat){
  if('missing_rows' in group){
    return `${group.missing_rows.toLocaleString()} of ${group.matching_rows.toLocaleString()} missing${group.percent===null?'':` (${group.percent.toLocaleString(undefined,{maximumFractionDigits:4})}%)`}`;
  }
  const value=group.value?.toLocaleString(undefined,{maximumSignificantDigits:12})??'Unavailable';
  return `${value} from ${group.usable_rows.toLocaleString()} usable values across ${group.matching_rows.toLocaleString()} matching rows (${group.excluded_rows.toLocaleString()} excluded)`;
}

function LocalResult({facts,version}:{facts:LocalFacts;version?:number}){
  const groups=facts.groups??[];
  const blank=facts.blank_group;
  return <>
    {facts.groups&&<ul>
      {groups.map(group=><li key={group.group}><strong>{group.group}</strong>{' · '}{groupResult(group)}</li>)}
      {blank&&blank.matching_rows>0&&<li><strong>Blank group</strong>{' · '}{groupResult(blank)}</li>}
    </ul>}
    {version!==undefined&&<small>Working dataset v{version}</small>}
  </>;
}
export function AssistantWorkspace({projectId,onSettings}:{projectId:string;onSettings:()=>void}){
  const [messages,setMessages]=useState<Msg[]>([{role:'assistant',content:'Choose Local analytics for verified facts. Smart Auto uses offline reasoning only. Cloud project requests require a separate explicit action and saved permission.',source:'READY'}]);
  const [question,setQuestion]=useState('');const [busy,setBusy]=useState(false);const [elapsed,setElapsed]=useState(0);
  const [template,setTemplate]=useState<(typeof localTemplates)[number]|null>(null);
  const questionInput=useRef<HTMLInputElement>(null);
  const localFollowUp=useRef<LocalFollowUp|null>(null);
  const fence=useRef(createInsightRequestFence()).current;
  const session=useSyncExternalStore(subscribeCloudConsent,cloudConsentSnapshot);
  useLayoutEffect(()=>fence.enter(),[fence,projectId,session.generation]);
  const templateIncomplete=template?.fields.some(field=>question.includes(`"${field}"`))??false;
  function fillTemplate(next:(typeof localTemplates)[number]){
    setTemplate(next);
    setQuestion(next.question);
    const first=next.fields[0];
    const start=next.question.indexOf(first);
    requestAnimationFrame(()=>{
      const input=questionInput.current;
      if(input?.value===next.question){input.focus();input.setSelectionRange(start,start+first.length)}
    });
  }
  useEffect(()=>{if(!busy){setElapsed(0);return}const started=Date.now();const timer=window.setInterval(()=>setElapsed(Math.floor((Date.now()-started)/1000)),1000);return()=>window.clearInterval(timer)},[busy]);
  const [provider,setProvider]=useState<string>(()=>localPanelProvider(localStorage.getItem('pilotodin-ai-provider-assistant')));
  const cloudName=projectCloudProviderName(provider);
  const routeAvailable=isLocalPanelProvider(provider);
  async function ask(q:string,continuation?:string){
    const last=messages[messages.length-1];
    if(continuation&&(!last||last.role!=='assistant'||!localPanelMayContinue(last.answerSource)||last.content!==continuation))return;
    const route=routeAvailable?localPanelRequest(continuation?'ollama':provider):null;
    if(busy||!route||!cloudConsentIsCurrent(session.generation)||(!q.trim()&&!continuation))return;
    const ticket=fence.begin();if(!ticket)return;
    setBusy(true);if(!continuation){setQuestion('');setTemplate(null);setMessages(a=>[...a,{role:'user',content:q}])}
    try{
      const r=await post<{answer:string;source?:string;provider:string;model:string;fallback:boolean;reason:string;local_status?:string;local_startup_issue?:string;incomplete?:boolean;finish_reason?:string;investigation?:MissingReport;facts?:LocalFacts;dataset_version?:number;follow_up?:LocalFollowUp|null}>(`/projects/${projectId}/ai/insight`,
        {context:'assistant',question:q||'Continue the previous explanation.',...route,continuation_text:continuation??null,
          ...(route.selected_provider==='local'&&localFollowUp.current?{local_follow_up:localFollowUp.current}:{})});
      if(!fence.isCurrent(ticket))return;
      if(!cloudConsentIsCurrent(session.generation)||r.source==='cloud_llm')return;
      localFollowUp.current=route.selected_provider==='local'?r.follow_up??null:null;
      const diagnostic=r.fallback&&provider!=='local'
        ? 'No language-model answer was generated. PilotODIN used verified local rules instead. '+(r.local_startup_issue?'Desktop startup: '+r.local_startup_issue+'. ':r.local_status&&r.local_status!=='not_requested'?'Local inference: '+r.local_status+'. ':'')+(r.reason??'')
        : undefined;
      setMessages(a=>{
        if(continuation&&a.length&&a[a.length-1].role==='assistant'){
          const last=a[a.length-1];return [...a.slice(0,-1),{...last,content:last.content+'\n\n'+r.answer,
            incomplete:r.incomplete,answerSource:r.source,source:r.fallback?'VERIFIED RULES · NO LLM':`${r.provider.toUpperCase()} · ${r.model}`,diagnostic}];
        }
        return [...a,{role:'assistant',content:r.answer,source:r.fallback?'VERIFIED RULES · NO LLM':`${r.provider.toUpperCase()} · ${r.model}`,
          incomplete:r.incomplete,answerSource:r.source,investigation:r.investigation,diagnostic,facts:r.facts,version:r.dataset_version}];
      });
    }catch(e){if(fence.isCurrent(ticket)&&cloudConsentIsCurrent(session.generation)){localFollowUp.current=null;setMessages(a=>[...a,{role:'assistant',content:(e as Error).message,source:'ERROR'}])}}
    finally{if(fence.finish(ticket))setBusy(false)}
  }
  return <div className="assistant-page"><section className="quality-banner"><div><div className="eyebrow">DATA SCIENCE COPILOT · HYBRID AI</div><h2>Ask your dataset</h2><p>Choose a local route for verified analysis. Smart Auto never sends data to cloud providers.</p></div><BrainCircuit size={43}/></section>
    <div className="panel chat-panel"><div className="ai-choice"><label htmlFor="assistant-provider">Choose intelligence</label><select id="assistant-provider" className="input" value={provider} disabled={busy} onChange={e=>{localFollowUp.current=null;setProvider(e.target.value);if(isLocalPanelProvider(e.target.value))localStorage.setItem('pilotodin-ai-provider-assistant',e.target.value)}}><option value="auto">Smart Auto (local only)</option><option value="ollama">Offline Qwen3 (desktop) / Ollama (dev)</option><option value="gemini">Google Gemini (cloud)</option><option value="groq">GroqCloud (cloud)</option><option value="openrouter">OpenRouter (project sharing disabled)</option><option value="local">Local analytics</option></select></div>{cloudName&&<div className="ai-incomplete" role="status"><strong>Selected destination: {cloudName}</strong><p>{projectCloudDisclosure}</p><p>{projectCloudHold(provider)}</p></div>}<div className="chat-messages">{messages.map((m,i)=><div key={i} className={'chat-message '+m.role}><span className="chat-role">{m.role==='assistant'?<Sparkles size={15}/>:null}{m.role==='assistant'?'PilotODIN':'You'} {m.source&&<small>· {m.source}</small>}</span><div className="chat-body">{m.role==='user'||m.facts?<p>{m.content}</p>:<RichText text={m.content}/>}
        {m.facts&&<LocalResult facts={m.facts} version={m.version}/>}
        {m.investigation&&<div className="verified-investigation"><strong>Verified investigation · {m.investigation.column}</strong><p>{m.investigation.missing_rows} missing ({m.investigation.missing_pct}%). Local row numbers: {m.investigation.row_numbers.slice(0,30).join(', ')}.</p>
          {m.investigation.numeric_comparisons.map(c=><p key={c.column}><b>{c.column}:</b> median for missing rows {c.missing_group_median.toLocaleString()} vs other rows {c.other_group_median.toLocaleString()}.</p>)}
          {m.investigation.categorical_comparisons.map(c=><div key={c.column}><b>{c.column}</b><ul>{c.groups.map(g=><li key={g.label}>{g.label}: {g.missing_count} missing / {g.total_count} records</li>)}</ul></div>)}
          <small>{m.investigation.caution}</small></div>}
        {m.diagnostic&&<div className="ai-incomplete" role="status"><span>{m.diagnostic}</span> <button className="btn small" onClick={onSettings}>AI Settings</button></div>}
        {m.incomplete&&<div className="ai-incomplete"><span>ODIN reached the provider response limit. The explanation may be unfinished.</span>{i===messages.length-1&&localPanelMayContinue(m.answerSource)&&<button className="btn small" disabled={busy||!routeAvailable||session.pending} onClick={()=>void ask('Continue the previous explanation.',m.content)}>Continue answer →</button>}</div>}
        </div></div>)}</div>
      {busy&&<div role="status" className="ai-working"><LoaderCircle size={17} className="spin"/><span><strong>{provider==='local'?'Calculating on your working dataset…':usesOwnedInference()?'Preparing context and requesting offline resource admission…':'Preparing local reasoning…'}</strong><small>{elapsed}s elapsed{provider!=='local'&&' · model loading can be slow · fallback will be labelled if used'}</small></span></div>}
      <div className="chat-starters">{(provider==='local'?localQuestions:starters).map(s=><button key={s} onClick={()=>void ask(s)} disabled={busy||!routeAvailable||session.pending}>{s}</button>)}
        {provider==='local'&&localTemplates.map(next=><button key={next.label} onClick={()=>fillTemplate(next)} disabled={busy}>{next.label}</button>)}</div>
      {templateIncomplete&&template&&<p id="assistant-template-hint" className="muted-caption" role="status">{template.hint}</p>}
      <form className="chat-form" onSubmit={e=>{e.preventDefault();if(!templateIncomplete)void ask(question)}}><input ref={questionInput} className="input" value={question} maxLength={900} onChange={e=>{setQuestion(e.target.value);if(!e.target.value)setTemplate(null)}} placeholder="Ask about your data, cleaning decisions, insights or modelling…" aria-label="Dataset question" aria-describedby={templateIncomplete?'assistant-template-hint':undefined}/><button className="btn primary" disabled={busy||!routeAvailable||session.pending||!question.trim()||templateIncomplete} type="submit"><Send size={16}/> {busy?'Thinking…':cloudName?'Send to '+cloudName:'Ask'}</button></form><p className="muted-caption"><ShieldCheck size={13}/> Local analysis does not send data to cloud providers. Project-data cloud requests require separate explicit permission. <button className="text-action" onClick={onSettings}>Configure AI providers</button></p></div>
  </div>;
}
