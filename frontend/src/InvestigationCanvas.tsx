/** PilotODIN / a new investigation-first experience.
 * Separate opt-in entry. Uses existing local authenticated API for data reads,
 * and persists investigations/evidence with the bounded backend contracts.
 */
import {useEffect, useMemo, useRef, useState} from 'react';
import type {ReactNode,PointerEvent as ReactPointerEvent,KeyboardEvent as ReactKeyboardEvent,CSSProperties} from 'react';
import {
  Activity, AlertCircle, ArrowLeft, ArrowRight, BarChart3, Bookmark, UploadCloud, FileDown, FileText, Home, FlaskConical, Settings2, Eye, Pin, Download, Compass, Send,
  Check, CheckCircle2, ChevronDown, ChevronRight, CircleDashed, Database,
  FileSearch, FolderClosed, History, Layers3, LayoutGrid,
  LockKeyhole, Menu, PanelRightClose, PanelRightOpen,
  Plus, RefreshCw, SearchCheck, ShieldCheck, Sparkles, WandSparkles, X,
} from 'lucide-react';
import type {Profile} from './api';
import {get,post,upload} from './api';
import {ReportWorkspace} from './ReportWorkspace';
import './investigation-canvas.css';

type ProjectRow={id:string;name:string;filename:string;created_at:string};
type CanvasArtifact={id:string;operation:string;params:Record<string,unknown>;result:Record<string,unknown>;
  version:number;status:string;stale:boolean;tool_version:string;created_at:string};
type CanvasInvestigation={id:string;project_id:string;objective:string;version:number;current_version:number;
  stale:boolean;status:string;created_at:string;updated_at:string;artifacts:CanvasArtifact[]};
type AutonomousRun={id:string;status:string;max_steps:number;stop_reason:string|null;last_error:string|null;stale:boolean;
  steps:{id:string;ordinal:number;status:string;evidence_id:string|null;proposal:{intent:string;tool:string;columns:string[];reason:string}}[]};
type HistoryItem={id:string;project_id:string;objective:string;version:number;status:string;stale:boolean;
  evidence_count:number;created_at:string;updated_at:string};
type Snapshot={version:number;profile:Profile};
type Overview={version:number;rows:number;missing_cells:number;exact_duplicates:number;columns:{name:string;kind:string;missing:number;unique:number}[]};
type Recommendation={title:string;x:string;y:string|null;kind:string;aggregation:string;reason:string};
type Comparerow={label:string;value:number};
const fixedFormat=(value:unknown)=>typeof value==='number'&&Number.isFinite(value)?new Intl.NumberFormat('en-ZA',{maximumFractionDigits:2}).format(value):'–';
const clock=(value:string)=>{try{return new Date(value).toLocaleDateString(undefined,{day:'numeric',month:'short'});}catch{return 'Recent';}};
const nice=(s:string)=>s.replaceAll('_',' ').replace(/\b\w/g,m=>m.toUpperCase());
function downloadText(name:string,body:string,mime='text/plain;charset=utf-8'){
 const url=URL.createObjectURL(new Blob([body],{type:mime}));const a=document.createElement('a');a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),2000);
}

function SoftIcon({children,tone='iris'}: {children:ReactNode;tone?:string}) {return <span className={`ud-soft-icon ${tone==='teal'?'ud-teal':''}`}>{children}</span>}
function EmptyEvidence({onRun}:{onRun:()=>void}){return <div className="ud-empty-result"><div className="ud-empty-graphic"><BarChart3 size={34}/></div><h3>Start with real evidence</h3><p>Run your first verified calculation. Charts and findings appear here only after successful local computation.</p><button className="ud-btn ud-btn-primary" onClick={onRun}>Analyse dataset <ArrowRight size={16}/></button></div>}
function ComparisonChart({rows,metric}:{rows:Comparerow[];metric:string}){
 const signed=rows.some(r=>r.value<0);const shown=rows.slice(0,7);const highest=Math.max(0,...shown.map(r=>r.value));const max=highest>0?highest:1;
 if(!shown.length)return <div className="ud-chart-empty">No valid comparison groups were returned for this selection.</div>;
 if(signed)return <div className="ud-signed-note"><p>Signed values are shown in a table to avoid misleading positive-only bars.</p>{shown.map((r,i)=><div key={i}><span>{r.label}</span><b>{fixedFormat(r.value)}</b></div>)}</div>;
 return <div className="ud-chart-area" role="img" aria-label={`Verified median ${metric} by group, bars scaled to the highest displayed value`}><div className="ud-chart-lines"><span>100%</span><span>75%</span><span>50%</span><span>25%</span><span>0%</span></div><div className="ud-plot">{shown.map((r,i)=><div className="ud-column" key={`${r.label}-${i}`} title={`${r.label}: ${fixedFormat(r.value)}`}><b>{fixedFormat(r.value)}</b><div className={`ud-bar ${i===shown.findIndex(x=>x.value===max)?'ud-bar-leading':''}`} style={{height:`${Math.max(2,Math.min(100,r.value/max*100))}%`}}/><span>{r.label}</span></div>)}</div></div>
}
function EvidenceCard({artifact,expanded,onInspect,onDownload,pinned,onPin}:{artifact:CanvasArtifact;expanded:boolean;onInspect:()=>void;onDownload:()=>void;pinned:boolean;onPin:()=>void}){
 const r=artifact.result;const chartData=Array.isArray(r.data)?r.data.filter((p):p is Comparerow=>typeof p==='object'&&p!==null&&typeof (p as Comparerow).value==='number'&&typeof (p as Comparerow).label==='string'):[];
 const label=artifact.operation==='compare'?`${String(artifact.params.y)} by ${String(artifact.params.x)}`:artifact.operation==='missingness'?`Missing values · ${String(artifact.params.column)}`:artifact.operation==='distribution'?`Distribution · ${String(artifact.params.column)}`:'Dataset snapshot';
 const method=artifact.operation==='compare'?'Median per category':artifact.operation==='missingness'?'Column null diagnostics':artifact.operation==='distribution'?'Distribution and IQR analysis':'Dataset profile and duplicate check';
 return <article className={`ud-artifact ud-artifact-${artifact.operation} ${artifact.stale?'ud-artifact-stale':''}`}>
 <div className="ud-artifact-head"><div><div className="ud-artifact-kind"><SoftIcon tone={artifact.operation==='compare'?'iris':'teal'}>{artifact.operation==='compare'?<BarChart3 size={17}/>:artifact.operation==='missingness'?<ShieldCheck size={17}/>:artifact.operation==='distribution'?<Activity size={17}/>:<Database size={17}/>}</SoftIcon><span>{artifact.operation==='compare'?'ANALYTICAL COMPARISON':artifact.operation==='missingness'?'QUALITY EVIDENCE':artifact.operation==='distribution'?'DISTRIBUTION':'PROFILE EVIDENCE'}</span></div><h3>{label}</h3><p>{method} · Dataset v{artifact.version}</p></div><div className="ud-artifact-tools"><span className={`ud-pill ${artifact.stale?'ud-pill-warn':'ud-pill-teal'}`}><CheckCircle2 size={13}/>{artifact.stale?'Historical version':'Verified local'}</span><button title={pinned?'Unpin artifact':'Pin artifact'} aria-label={pinned?'Unpin artifact':'Pin artifact'} className={pinned?'ud-icon-pressed':''} onClick={onPin}><Pin size={15}/></button><button title="Download evidence JSON" aria-label="Download evidence JSON" onClick={onDownload}><Download size={15}/></button></div></div>
 {artifact.operation==='compare'&&<><ComparisonChart rows={chartData} metric={String(artifact.params.y)}/><div className="ud-chart-caveat">{r.truncated?'Showing the first returned categories; additional groups were truncated. ':''}Comparisons are descriptive, not causal. Values are medians from valid groups; chart bars are scaled to the highest displayed value.</div></>}
 {artifact.operation==='overview'&&<div className="ud-evidence-metrics">{([['Rows',(r.summary as Record<string,unknown>|undefined)?.rows],['Columns',(r.summary as Record<string,unknown>|undefined)?.columns_count],['Missing cells',(r.summary as Record<string,unknown>|undefined)?.missing_cells],['Duplicate rows',(r.summary as Record<string,unknown>|undefined)?.exact_duplicates]] as const).map(x=><div key={x[0]}><strong>{fixedFormat(x[1])}</strong><span>{x[0]}</span></div>)}</div>}
 {artifact.operation==='missingness'&&<div className="ud-missing-callout"><strong>{fixedFormat(r.missing_rows)}</strong><span>missing records out of {fixedFormat(r.total_rows)} ({fixedFormat(r.missing_pct)}%)</span><p>{String(r.caution||'No missingness mechanism has been inferred.')}</p></div>}
 {artifact.operation==='distribution'&&<div className="ud-evidence-metrics">{([['Mean',r.mean],['Median',r.median],['IQR outliers',r.outliers_by_iqr]] as const).map(x=><div key={x[0]}><strong>{fixedFormat(x[1])}</strong><span>{x[0]}</span></div>)}<p>Outliers may be valid observations.</p></div>}
 <div className="ud-evidence-bottom"><span><Layers3 size={14}/> Evidence ID {artifact.id.slice(0,10)}</span><button onClick={onInspect} aria-expanded={expanded}>{expanded?'Hide provenance':'Inspect provenance'} <ChevronDown size={14}/></button></div>
 {expanded&&<div className="ud-evidence-details"><div><span>Full evidence ID</span><code>{artifact.id}</code></div><div><span>Dataset version</span><code>{artifact.version}</code></div><div><span>Tool implementation</span><code>{artifact.tool_version}</code></div><div><span>Parameters</span><code>{JSON.stringify(artifact.params)}</code></div><p>Result is {artifact.stale?'historical, because the dataset was subsequently changed.':'linked to this dataset version.'}</p></div>}
 </article>;
}
export function InvestigationCanvas(){
 const [projects,setProjects]=useState<ProjectRow[]>([]);
 const [projectId,setProjectId]=useState(localStorage.getItem('pilotodin-current')||'');
 const fileInput=useRef<HTMLInputElement>(null);
 const [activeTab,setActiveTab]=useState<'investigate'|'quality'|'deliver'>('investigate');
 const [pinnedIds,setPinnedIds]=useState<string[]>([]);
 const [ollama,setOllama]=useState<{status:string;model?:string}|null>(null);
 const [snapshot,setSnapshot]=useState<Snapshot|null>(null);
 const [overview,setOverview]=useState<Overview|null>(null);
 const [recommendations,setRecommendations]=useState<Recommendation[]>([]);
 const [history,setHistory]=useState<HistoryItem[]>([]);
 const [investigation,setInvestigation]=useState<CanvasInvestigation|null>(null);
 const [draft,setDraft]=useState('');
 const [navOpen,setNavOpen]=useState(false);
 const [odinOpen,setOdinOpen]=useState(()=>window.innerWidth>880);
 const [odinWidth,setOdinWidth]=useState(()=>{const n=Number(localStorage.getItem('pilotodin-odin-width'));return Number.isFinite(n)&&n>=265&&n<=490?n:335;});
 const [expanded,setExpanded]=useState<Record<string,boolean>>({});
 const [busy,setBusy]=useState('');
 const [error,setError]=useState('');
 const [warning,setWarning]=useState('');
 const [retryKey,setRetryKey]=useState(0);
 const [showAll,setShowAll]=useState(false);
 const [aiQuestion,setAiQuestion]=useState('');
 const [aiBusy,setAiBusy]=useState(false);
 const aiRunId=useRef(0);
 const [aiError,setAiError]=useState('');
 const [aiAnswer,setAiAnswer]=useState<{answer:string;provider:string;model:string;fallback:boolean;dataset_version:number;reason?:string}|null>(null);
 const [autonomous,setAutonomous]=useState<AutonomousRun|null>(null);
 const [autonomyBusy,setAutonomyBusy]=useState(false);
 const [autonomyError,setAutonomyError]=useState('');
 const lastAutonomyEvidence=useRef(-1);
 useEffect(()=>{aiRunId.current+=1;setAiAnswer(null);setAiError('');setAiBusy(false)},[projectId,investigation?.id]);
 useEffect(()=>{localStorage.setItem('pilotodin-odin-width',String(odinWidth))},[odinWidth]);
 function startResize(event:ReactPointerEvent<HTMLDivElement>){
   if(window.innerWidth<920)return;event.preventDefault();
   const move=(e:PointerEvent)=>setOdinWidth(Math.max(265,Math.min(490,window.innerWidth-e.clientX)));
   const end=()=>{window.removeEventListener('pointermove',move);window.removeEventListener('pointerup',end)};
   window.addEventListener('pointermove',move);window.addEventListener('pointerup',end);
 }
 function resizeByKey(event:ReactKeyboardEvent<HTMLDivElement>){if(event.key==='ArrowLeft'||event.key==='ArrowRight'){event.preventDefault();setOdinWidth(v=>Math.min(490,Math.max(265,v+(event.key==='ArrowLeft'?18:-18))))}}
 useEffect(()=>{get<{status:string;model?:string}>('/ai/local/status').then(setOllama).catch(()=>setOllama({status:'unavailable'}))},[]);
 useEffect(()=>{const key=investigation?.id;if(!key){setPinnedIds([]);return;}try{const raw=JSON.parse(localStorage.getItem('pilotodin-pins-'+key)||'[]');setPinnedIds(Array.isArray(raw)?raw.filter((x:unknown):x is string=>typeof x==='string'):[])}catch{setPinnedIds([])}},[investigation?.id]);
 useEffect(()=>{
  const id=investigation?.id;
  setAutonomous(null);setAutonomyError('');lastAutonomyEvidence.current=-1;
  if(!id)return;
  let active=true;
  const update=async()=>{
   try{
    const state=await get<AutonomousRun|null>(`/investigations/${id}/autonomy`);
    if(!active)return;
    setAutonomous(state);
    const count=state?.steps.filter(s=>s.evidence_id).length??0;
    if(count!==lastAutonomyEvidence.current){
      lastAutonomyEvidence.current=count;
      if(count>0){
       const updated=await get<CanvasInvestigation>(`/investigations/${id}`);
       if(active&&updated.project_id===projectId)setInvestigation(updated);
      }
    }
   }catch(e){if(active)setAutonomyError((e as Error).message)}
  };
  void update();const timer=window.setInterval(()=>void update(),1600);
  return()=>{active=false;window.clearInterval(timer)};
 },[investigation?.id,projectId]);

 const [selectedCategory,setSelectedCategory]=useState('');
 const [selectedMetric,setSelectedMetric]=useState('');
 const [selectedColumn,setSelectedColumn]=useState('');
 const [selectedTool,setSelectedTool]=useState<'overview'|'compare'|'missingness'|'distribution'>('compare');
 const project=projects.find(p=>p.id===projectId);
 const colData=overview?.columns||[];
 const categorical=colData.filter(c=>c.kind==='categorical'&&c.unique>1&&c.unique<=50);
 const numeric=colData.filter(c=>c.kind==='numeric');
 const withMissing=colData.filter(c=>c.missing>0);
 const defaultCategory=categorical[0]?.name||'';
 const defaultMetric=numeric.find(c=>/price|revenue|sales|profit|cost|amount/i.test(c.name))?.name||numeric[0]?.name||'';
 const category=selectedCategory&&categorical.some(c=>c.name===selectedCategory)?selectedCategory:defaultCategory;
 const metric=selectedMetric&&numeric.some(c=>c.name===selectedMetric)?selectedMetric:defaultMetric;
 const missingCol=selectedColumn&&withMissing.some(c=>c.name===selectedColumn)?selectedColumn:withMissing[0]?.name||'';
 const distributionCol=selectedColumn&&numeric.some(c=>c.name===selectedColumn)?selectedColumn:defaultMetric;
 const dynamicObjective=category&&metric?`How does ${metric} vary across ${category}?`:'What patterns and data-quality issues deserve investigation?';
 const stale=!!investigation?.stale;
 const artifacts=investigation?.artifacts||[];
 const sortedArtifacts=useMemo(()=>[...artifacts].reverse(),[artifacts]);
 const latestCompare=sortedArtifacts.find(a=>a.operation==='compare');
 const otherCards=sortedArtifacts.filter(a=>a!==latestCompare);
 const displayCards=showAll?otherCards:otherCards.slice(0,5);

 useEffect(()=>{const update=()=>{const id=localStorage.getItem('pilotodin-current')||'';if(id&&id!==projectId)setProjectId(id)};window.addEventListener('pilotodin:project-changed',update);return()=>window.removeEventListener('pilotodin:project-changed',update)},[projectId]);
 useEffect(()=>{let current=true;get<ProjectRow[]>('/projects').then(rows=>{if(current){setProjects(rows);if(rows.length&&!rows.some(r=>r.id===projectId))setProjectId(rows[0].id)}}).catch(e=>{if(current)setError((e as Error).message)});return()=>{current=false}},[]);
 useEffect(()=>{
  if(!projectId){setSnapshot(null);setOverview(null);setHistory([]);setInvestigation(null);setWarning('');return;}
  const controller=new AbortController();let current=true;
  setSnapshot(null);setOverview(null);setHistory([]);setInvestigation(null);setError('');setWarning('');setExpanded({});
  const services:[string,Promise<unknown>][]=[
   ['Dataset profile',get<Snapshot>(`/projects/${encodeURIComponent(projectId)}/live-profile`,{signal:controller.signal})],
   ['Data overview',get<Overview>(`/projects/${encodeURIComponent(projectId)}/explore/overview`,{signal:controller.signal})],
   ['Investigations',get<HistoryItem[]>(`/projects/${encodeURIComponent(projectId)}/investigations`,{signal:controller.signal})],
   ['Recommendations',get<{recommendations:Recommendation[]}>(`/projects/${encodeURIComponent(projectId)}/explore/recommended`,{signal:controller.signal})],
  ];
  void Promise.allSettled(services.map(([,promise])=>promise)).then(async(results)=>{
   if(!current)return;
   const failed:string[]=[];
   for(let i=0;i<results.length;i++){
    const result=results[i];
    if(result.status==='rejected'){
      if((result.reason as Error)?.name!=='AbortError')failed.push(`${services[i][0]}: ${(result.reason as Error)?.message||'Request failed'}`);
      continue;
    }
    if(i===0)setSnapshot(result.value as Snapshot);
    if(i===1)setOverview(result.value as Overview);
    if(i===2)setHistory(result.value as HistoryItem[]);
    if(i===3)setRecommendations((result.value as {recommendations:Recommendation[]}).recommendations);
   }
   const historyResult=results[2];
   if(historyResult.status==='fulfilled'){
     const rows=historyResult.value as HistoryItem[];
     const last=localStorage.getItem('pilotodin-canvas-last-'+projectId);
     const chosen=rows.find(i=>i.id===last)||rows[0];
     if(chosen){
       try {const loaded=await get<CanvasInvestigation>(`/investigations/${chosen.id}`,{signal:controller.signal});if(current)setInvestigation(loaded);}
       catch(e){if(current&&(e as Error)?.name!=='AbortError')failed.push('Restore investigation: '+(e as Error).message)}
     }
   }
   if(current&&failed.length){
     const critical=results[0].status==='rejected'||results[1].status==='rejected';
     const message=failed.join(' | ');
     if(critical)setError(message);else setWarning('Some optional project information is unavailable. '+message);
   }
  });
  localStorage.setItem('pilotodin-current',projectId);window.dispatchEvent(new Event('pilotodin:project-changed'));
  return()=>{current=false;controller.abort()};
 },[projectId,retryKey]);
 useEffect(()=>{setDraft(dynamicObjective)},[projectId,defaultCategory,defaultMetric]);
 useEffect(()=>{const k=(event:KeyboardEvent)=>{if(event.key==='Escape')setNavOpen(false);if((event.metaKey||event.ctrlKey)&&event.key==='\\'){event.preventDefault();setOdinOpen(v=>!v);}};window.addEventListener('keydown',k);return()=>window.removeEventListener('keydown',k)},[]);
 async function refresh(){if(!projectId)return;setError('');try{const [s,o,h]=await Promise.all([get<Snapshot>(`/projects/${projectId}/live-profile`),get<Overview>(`/projects/${projectId}/explore/overview`),get<HistoryItem[]>(`/projects/${projectId}/investigations`)]);setSnapshot(s);setOverview(o);setHistory(h);if(investigation)setInvestigation(await get(`/investigations/${investigation.id}`))}catch(e){setError((e as Error).message)}}
 // A change in a docked Quality pane invalidates displayed version-bound investigation data.
 useEffect(()=>{
  const onDatasetChange=(event:Event)=>{
   if((event as CustomEvent<{projectId:string}>).detail?.projectId===projectId)void refresh();
  };
  window.addEventListener('pilotodin:dataset-changed',onDatasetChange);
  return()=>window.removeEventListener('pilotodin:dataset-changed',onDatasetChange);
 },[projectId,investigation?.id]);
 async function askOdin(){
  if(!projectId||!investigation||stale||aiBusy)return;
  const currentRun=++aiRunId.current;
  setAiBusy(true);setAiError('');setAiAnswer(null);
  try{
   const response=await post<{answer:string;provider:string;model:string;fallback:boolean;dataset_version:number;reason?:string}>(`/projects/${projectId}/ai/insight`,{
     context:'assistant',question:(aiQuestion.trim()||investigation.objective).slice(0,900),selected_provider:'auto'
   });
   if(response.dataset_version!==investigation.version)throw new Error('Dataset version changed. Refresh before interpreting this answer.');
   if(currentRun===aiRunId.current)setAiAnswer(response);
  }catch(e){if(currentRun===aiRunId.current)setAiError((e as Error).message)}finally{if(currentRun===aiRunId.current)setAiBusy(false)}
 }
 async function controlAutonomy(action:'start'|'resume'|'cancel'){
  if(!investigation||autonomyBusy||stale)return;
  setAutonomyBusy(true);setAutonomyError('');
  try{
   const state=await post<AutonomousRun>(`/investigations/${investigation.id}/autonomy/${action}`,
      action==='start'?{max_steps:5}:{});
   setAutonomous(state);
  }catch(e){setAutonomyError((e as Error).message)}finally{setAutonomyBusy(false)}
 }
 async function pick(id:string){setBusy('opening');setError('');try{const i=await get<CanvasInvestigation>(`/investigations/${id}`);if(i.project_id!==projectId)throw new Error('Investigation does not belong to the active project');setInvestigation(i);setAiAnswer(null);setAiError('');setAiQuestion('');localStorage.setItem('pilotodin-canvas-last-'+projectId,i.id);setExpanded({});setNavOpen(false);}catch(e){setError((e as Error).message)}finally{setBusy('')}}
 async function create(){if(!projectId||draft.trim().length<8)return;setBusy('creating');setError('');try{const i=await post<CanvasInvestigation>(`/projects/${projectId}/investigations`,{objective:draft.trim()});setInvestigation(i);setAiAnswer(null);setAiError('');setAiQuestion('');localStorage.setItem('pilotodin-canvas-last-'+projectId,i.id);setHistory(await get(`/projects/${projectId}/investigations`));setActiveTab('investigate');try{const first=await post<CanvasInvestigation>(`/investigations/${i.id}/runs`,{operation:'overview',params:{},expected_version:i.version});setInvestigation(first);setHistory(await get(`/projects/${projectId}/investigations`));}catch(snapshotError){setError('Investigation was saved, but the starting dataset snapshot could not be computed: '+(snapshotError as Error).message)}}catch(e){setError((e as Error).message)}finally{setBusy('')}}
 async function run(op:typeof selectedTool){if(!investigation)return;const params:Record<string,string>={};if(op==='compare'){if(!category||!metric){setError('Choose a categorical dimension and a numeric measure');return}params.x=category;params.y=metric;}
  if(op==='missingness'){if(!missingCol){setError('There are no columns with missing values');return}params.column=missingCol;}
  if(op==='distribution'){if(!distributionCol){setError('There are no numeric columns');return}params.column=distributionCol;}
  setBusy(op);setError('');try{const updated=await post<CanvasInvestigation>(`/investigations/${investigation.id}/runs`,{operation:op,params,expected_version:investigation.version});setInvestigation(updated);setHistory(await get(`/projects/${projectId}/investigations`));setActiveTab('investigate');}catch(e){setError((e as Error).message);void refresh();}finally{setBusy('')}}
 async function importFile(file:File|undefined){if(!file)return;setError('');if(!/\.(csv|xlsx)$/i.test(file.name)){setError('Select a CSV or XLSX dataset.');return;}if(file.size>40*1024*1024){setError('The import limit is 40 MB.');return;}setBusy('importing');try{const loaded=await upload(file);const rows=await get<ProjectRow[]>('/projects');setProjects(rows);setProjectId(loaded.id);setInvestigation(null);setActiveTab('investigate');}catch(e){setError((e as Error).message)}finally{setBusy('')}}
 function openStudio(stage='overview'){location.hash='#/studio/'+stage;}
 function togglePin(id:string){if(!investigation)return;setPinnedIds(current=>{const next=current.includes(id)?current.filter(x=>x!==id):[id,...current];localStorage.setItem('pilotodin-pins-'+investigation.id,JSON.stringify(next));return next});}
 function downloadEvidence(a:CanvasArtifact){downloadText(`pilotodin-evidence-${a.id.slice(0,12)}.json`,JSON.stringify({artifact_id:a.id,investigation_id:investigation?.id,objective:investigation?.objective,project_id:projectId,dataset_version:a.version,stale:a.stale,operation:a.operation,params:a.params,tool_version:a.tool_version,created_at:a.created_at,result:a.result},null,2),'application/json')}
 const selectedCanRun=selectedTool==='overview'||selectedTool==='compare'&&!!category&&!!metric||selectedTool==='missingness'&&!!missingCol||selectedTool==='distribution'&&!!distributionCol;
 const primaryComparison=sortedArtifacts.find(a=>a.operation==='compare');
 const series=Array.isArray(primaryComparison?.result.data)?(primaryComparison.result.data as unknown[]).filter((x):x is Comparerow=>typeof x==='object'&&x!==null&&typeof (x as Comparerow).value==='number'&&typeof (x as Comparerow).label==='string'):[];
 const positive=series.filter(x=>Number.isFinite(x.value));
 const winner=[...positive].sort((a,b)=>b.value-a.value)[0];
 const evidenceSorted=[...sortedArtifacts].sort((a,b)=>Number(pinnedIds.includes(b.id))-Number(pinnedIds.includes(a.id)));
 const supportingEvidence=showAll?evidenceSorted:evidenceSorted.slice(0,6);
 const currentProfile=snapshot?.profile;
 const ready=ollama?.status==='ready';
 return <div className={`ud-app ${odinOpen?'':'ud-odin-hidden'}`}>
   <input ref={fileInput} type="file" accept=".csv,.xlsx" hidden aria-label="Import dataset" onChange={e=>{const file=e.currentTarget.files?.[0];void importFile(file);e.currentTarget.value=''}}/>
   <aside className={`ud-sidebar ${navOpen?'ud-sidebar-open':''}`} aria-label="Primary navigation">
     <div className="ud-brand" role="banner"><div className="ud-brand-icon"><img src="/pilotodin-symbol.svg" alt="" /></div><div><strong><span className="ud-wordmark-pilot">pilot</span><span className="ud-wordmark-odin">ODIN</span></strong><small>INTELLIGENCE STUDIO</small></div><button className="ud-side-close" title="Close menu" onClick={()=>setNavOpen(false)}><X size={17}/></button></div>
     <div className="ud-side-scroll">
      <p className="ud-nav-caption">WORKSPACE</p>
      <nav className="ud-nav">
       <button onClick={()=>openStudio('overview')}><Home size={18}/> Home</button>
       <button onClick={()=>setNavOpen(x=>!x)}><FolderClosed size={18}/> Projects <ChevronDown size={14}/></button>
       <button className="ud-active" aria-current="page" onClick={()=>{setActiveTab('investigate');setNavOpen(false)}}><Sparkles size={18}/> Investigation <span className="ud-nav-pin"/></button>
       <button onClick={()=>{setActiveTab('quality');setNavOpen(false)}}><ShieldCheck size={18}/> Data Quality</button>
       <button onClick={()=>{setActiveTab('investigate');setSelectedTool('compare');setOdinOpen(true);setNavOpen(false)}}><BarChart3 size={18}/> Explore</button>
       <button onClick={()=>openStudio('model')}><FlaskConical size={18}/> Model &amp; Predict</button>
       <button onClick={()=>{setActiveTab('deliver');setNavOpen(false)}}><FileText size={18}/> Deliver</button>
      </nav>
      <p className="ud-nav-caption ud-nav-later">PROJECT CONTEXT</p>
      <label className="ud-project-select"><Database size={15}/><select aria-label="Select a project" value={projectId} onChange={e=>setProjectId(e.target.value)}><option value="">Choose project</option>{projects.map(p=><option key={p.id} value={p.id}>{p.name}</option>)}</select><ChevronDown size={15}/></label>
      <button className="ud-import-link" onClick={()=>fileInput.current?.click()} disabled={busy==='importing'}><Plus size={15}/>{busy==='importing'?'Importing dataset…':'Import a dataset'}</button>
      <div className="ud-section-heading"><span>RECENT INVESTIGATIONS</span><button title="New investigation" aria-label="New investigation" disabled={!projectId} onClick={()=>{setInvestigation(null);setActiveTab('investigate')}}><Plus size={17}/></button></div>
      <div className="ud-investigation-list">{history.slice(0,8).map(i=><button key={i.id} onClick={()=>void pick(i.id)} className={investigation?.id===i.id?'ud-investigation-active':''}><span className="ud-thread-dot"/><span><b>{i.objective}</b><small>{i.evidence_count} verified artifacts · v{i.version}{i.stale?' · historical':''}</small></span></button>)}{history.length===0&&<p>Investigations you create will appear here and can be resumed later.</p>}</div>
     </div>
     <div className="ud-sidebar-bottom"><button onClick={()=>openStudio('ai_settings')}><Settings2 size={18}/> Settings</button><div className="ud-project-summary"><span><span className="ud-green-dot"/> ACTIVE PROJECT</span><strong title={project?.name}>{project?nice(project.name):'No project selected'}</strong><small title={project?.filename}>{project?`File: ${project.filename}`:'Choose or import a project'}</small>{snapshot&&<small>{fixedFormat(snapshot.profile.rows)} rows · Dataset v{snapshot.version}</small>}</div></div>
   </aside>
   {navOpen&&<button className="ud-side-scrim" aria-label="Close navigation" onClick={()=>setNavOpen(false)}/>}
   <div className="ud-workspace">
    <header className="ud-topbar"><div className="ud-crumbs"><button className="ud-menu" aria-label="Open navigation" onClick={()=>setNavOpen(true)}><Menu size={19}/></button><span>Projects</span><ChevronRight size={14}/><strong>{project?nice(project.name):'Start a project'}</strong><ChevronRight size={14}/><span>Investigation</span></div><div className="ud-top-actions"><span className="ud-cloud-badge"><span className="ud-green-dot"/>{ready?'Local AI ready':'Local analytics ready'}</span><button title="Refresh active project" aria-label="Refresh active project" onClick={()=>void refresh()} disabled={!projectId}><RefreshCw size={17}/></button><button className="ud-btn ud-ask-top" onClick={()=>setOdinOpen(x=>!x)}><Sparkles size={16}/> {odinOpen?'Hide ODIN':'Ask ODIN'}</button></div></header>
    <div className="ud-scroll"><div className="ud-body">
     <div className="ud-heading"><div><div className="ud-eyebrow"><span className="ud-eyebrow-dot"/> INVESTIGATION WORKSPACE {investigation&&<span className="ud-pill ud-pill-teal">● SAVED LOCALLY</span>}</div><h1>{investigation?investigation.objective:projectId?'Every answer starts with a question.':'Turn raw data into clear decisions.'}</h1><p>{investigation?'A connected view of your verified calculations, evidence and next analytical steps.':projectId?'Create a question-led investigation using the dataset already on your device.':'Import your dataset, explore its structure and build an evidence-backed investigation.'}</p></div><div className="ud-heading-actions">{projectId&&<button className="ud-btn ud-btn-quiet" onClick={()=>{setInvestigation(null);setActiveTab('investigate')}}><Plus size={16}/> New investigation</button>}{!projectId&&<button className="ud-btn ud-btn-primary" onClick={()=>fileInput.current?.click()}><UploadCloud size={17}/> Import data</button>}</div></div>
     {error&&<div className="ud-alert" role="alert"><AlertCircle size={19}/><span>{error}</span><button className="ud-alert-retry" onClick={()=>setRetryKey(k=>k+1)} disabled={!projectId}><RefreshCw size={15}/> Retry</button><button onClick={()=>setError('')} aria-label="Dismiss error"><X size={16}/></button></div>}{warning&&<div className="ud-alert ud-alert-warning" role="status"><AlertCircle size={19}/><span>{warning}</span><button className="ud-alert-retry" onClick={()=>setRetryKey(k=>k+1)}><RefreshCw size={15}/> Retry</button><button onClick={()=>setWarning('')} aria-label="Dismiss warning"><X size={16}/></button></div>}
     {!projectId&&<div className="ud-start-card"><span className="ud-start-icon"><UploadCloud size={30}/></span><h2>Start with your dataset</h2><p>CSV and Excel files up to 40 MB. Your original data remains on this computer, and analysis runs through the local Python engine.</p><button className="ud-btn ud-btn-primary" onClick={()=>fileInput.current?.click()} disabled={busy==='importing'}>{busy==='importing'?'Preparing your data…':'Choose a dataset'} <ArrowRight size={17}/></button><small>Have a project already? Select it from the sidebar.</small></div>}
     {projectId&&<>
       <div className="ud-mode-tabs" role="tablist" aria-label="Investigation views"><button role="tab" aria-selected={activeTab==='investigate'} className={activeTab==='investigate'?'ud-tab-active':''} onClick={()=>setActiveTab('investigate')}>Overview &amp; Analysis</button><button role="tab" aria-selected={activeTab==='quality'} className={activeTab==='quality'?'ud-tab-active':''} onClick={()=>setActiveTab('quality')}>Data Quality</button><button role="tab" aria-selected={activeTab==='deliver'} className={activeTab==='deliver'?'ud-tab-active':''} onClick={()=>setActiveTab('deliver')}>Report</button><span/><button className="ud-tab-external" onClick={()=>openStudio('prepare')}>Prepare <ArrowRight size={13}/></button><button className="ud-tab-external" onClick={()=>openStudio('model')}>Model Lab <ArrowRight size={13}/></button></div>
       {stale&&<div className="ud-stale"><AlertCircle size={19}/><div><strong>These findings belong to an earlier dataset version.</strong><p>Investigation v{investigation?.version} · Current v{investigation?.current_version}. Prior evidence is preserved but cannot be presented as current.</p></div><button className="ud-btn ud-btn-quiet" onClick={()=>{setInvestigation(null);setActiveTab('investigate')}}>Start new investigation</button></div>}
       {!investigation&&activeTab==='investigate'&&<div className="ud-question-card"><div className="ud-question-symbol"><Sparkles size={24}/></div><div><span className="ud-card-label">START AN INVESTIGATION</span><h2>What do you want to understand?</h2><p>Frame the question. We'll save your investigation and run a read-only dataset snapshot to begin building evidence.</p><label htmlFor="ud-objective">Investigation objective</label><textarea id="ud-objective" maxLength={400} value={draft} onChange={e=>setDraft(e.target.value)} placeholder="e.g. How does revenue vary by region?"/><div className="ud-question-actions"><small><ShieldCheck size={14}/> Linked to dataset version {snapshot?.version||'…'}</small><button className="ud-btn ud-btn-primary" disabled={busy!==''||draft.trim().length<8||!snapshot} onClick={()=>void create()}>{busy==='creating'?'Setting up your investigation…':'Start investigation'} <ArrowRight size={16}/></button></div></div></div>}
       {investigation&&activeTab==='investigate'&&<>
        <div className="ud-metrics">{([['Dataset rows',snapshot?.profile.rows,<Database size={18}/>],['Data fields',snapshot?.profile.columns_count,<Layers3 size={18}/>],['Missing cells',snapshot?.profile.missing_cells,<AlertCircle size={18}/>],['Evidence artifacts',artifacts.length,<CheckCircle2 size={18}/>]] as const).map(([name,n,icon])=><div className="ud-metric" key={name}><span className="ud-metric-icon">{icon}</span><small>{name}</small><strong>{fixedFormat(n)}</strong><span className="ud-metric-detail">{name==='Evidence artifacts'?'Persisted to this investigation':'Current dataset profile'}</span></div>)}</div>
        <div className="ud-feature-grid"><section className="ud-panel ud-feature-chart"><div className="ud-panel-header"><div><span className="ud-card-label">EXPLORATORY ANALYSIS</span><h2>{primaryComparison?`${String(primaryComparison.params.y)} by ${String(primaryComparison.params.x)}`:'Visualise a comparison'}</h2><p>{primaryComparison?'Verified grouped medians · read-only local calculation':'Choose a category and numeric measure to compare groups.'}</p></div><button className="ud-icon-action" title="Configure comparison" aria-label="Configure comparison" onClick={()=>{setSelectedTool('compare');setOdinOpen(true)}}><BarChart3 size={18}/></button></div>{primaryComparison?<><ComparisonChart rows={series} metric={String(primaryComparison.params.y)}/><div className="ud-chart-footer"><span><ShieldCheck size={14}/> Dataset v{primaryComparison.version} · {series.length} groups shown</span><button onClick={()=>downloadEvidence(primaryComparison)}><FileDown size={14}/> Evidence JSON</button></div></>:<div className="ud-empty-chart"><BarChart3 size={32}/><p>No comparison computed yet.</p><button className="ud-btn ud-btn-primary" disabled={!category||!metric||busy!==''||stale} onClick={()=>void run('compare')}>Compare {category||'groups'} <ArrowRight size={15}/></button></div>}</section>
        <section className="ud-panel ud-finding"><div className="ud-panel-header"><div><span className="ud-card-label">KEY FINDING</span><h2>What the evidence shows</h2></div><SoftIcon><Sparkles size={19}/></SoftIcon></div>{primaryComparison&&winner?<div className="ud-finding-body"><div className="ud-finding-index">01</div><strong>{winner.label} has the highest displayed group median.</strong><p>The observed median is {fixedFormat(winner.value)} for {String(primaryComparison.params.y)}. This description uses the current chart's returned groups only.</p><span className="ud-pill ud-pill-warn">Human interpretation required</span><div className="ud-finding-foot">Group size, missing values and other features can influence comparisons. No causal claim has been established.</div></div>:<div className="ud-finding-pending"><Compass size={28}/><strong>No finding inferred yet</strong><p>Run a group comparison to create a grounded descriptive result.</p></div>}</section></div>
        <div className="ud-evidence-section"><div className="ud-section-head"><div><span className="ud-card-label">EVIDENCE LIBRARY</span><h2>Every result has a source.</h2></div><div><span>{artifacts.length} verified tool {artifacts.length===1?'run':'runs'}</span><button onClick={()=>setShowAll(x=>!x)}>{showAll?'Show fewer':'View all'} <ChevronRight size={15}/></button></div></div>{!artifacts.length?<EmptyEvidence onRun={()=>void run('overview')}/>:<div className="ud-evidence-grid">{supportingEvidence.map(a=><EvidenceCard key={a.id} artifact={a} pinned={pinnedIds.includes(a.id)} onPin={()=>togglePin(a.id)} expanded={!!expanded[a.id]} onInspect={()=>setExpanded(s=>({...s,[a.id]:!s[a.id]}))} onDownload={()=>downloadEvidence(a)}/>)}</div>}</div>
        <div className="ud-next-cta"><div><SoftIcon tone="teal"><SearchCheck size={19}/></SoftIcon><span><strong>Continue your investigation</strong><small>Compare variables, inspect missingness or ask ODIN to explain supported findings.</small></span></div><button className="ud-btn ud-btn-quiet" disabled={busy!==''||stale} onClick={()=>{setSelectedTool('compare');setOdinOpen(true)}}>Choose analysis <ArrowRight size={15}/></button></div>
       </>}
       {activeTab==='quality'&&<div className="ud-section-screen"><div className="ud-section-head"><div><span className="ud-card-label">DATA QUALITY</span><h2>Understand issues before changing data.</h2></div><button className="ud-btn ud-btn-quiet" onClick={()=>openStudio('quality')}>Open full cleaning workspace <ArrowRight size={15}/></button></div><div className="ud-quality-grid"><div className="ud-panel"><h3>Dataset quality summary</h3><div className="ud-evidence-metrics"><div><strong>{fixedFormat(overview?.missing_cells??snapshot?.profile.missing_cells)}</strong><span>Missing cells</span></div><div><strong>{fixedFormat(overview?.exact_duplicates??snapshot?.profile.duplicate_rows)}</strong><span>Duplicate rows</span></div><div><strong>{fixedFormat(withMissing.length)}</strong><span>Fields with missing values</span></div></div><p>Numbers are from the current local dataset profile. No values are changed in this Canvas.</p><label>Inspect a field<select value={missingCol} onChange={e=>setSelectedColumn(e.target.value)}>{withMissing.length?withMissing.map(c=><option key={c.name} value={c.name}>{c.name} · {c.missing} missing</option>):<option value="">No missing-value fields</option>}</select></label><button className="ud-btn ud-btn-primary" disabled={!investigation||!missingCol||stale||busy!==''} onClick={()=>void run('missingness')}><ShieldCheck size={16}/> Run verified missingness check</button></div><div className="ud-panel ud-quality-aside"><SoftIcon tone="teal"><LockKeyhole size={19}/></SoftIcon><h3>Safe by design</h3><p>Quality checks here are read-only. Corrections, imputation, undo and version history remain available in the existing Studio's Quality workspace while we unify those interactions.</p><button onClick={()=>openStudio('quality')} className="ud-text-link">Review change approvals <ArrowRight size={15}/></button></div></div><div className="ud-evidence-grid">{sortedArtifacts.filter(a=>a.operation==='missingness').map(a=><EvidenceCard key={a.id} artifact={a} expanded={!!expanded[a.id]} onInspect={()=>setExpanded(v=>({...v,[a.id]:!v[a.id]}))} onDownload={()=>downloadEvidence(a)} pinned={pinnedIds.includes(a.id)} onPin={()=>togglePin(a.id)}/>)}</div></div>}
       {activeTab==='deliver'&&<ReportWorkspace key={projectId} projectId={projectId} defaultTitle={investigation?.objective||'Investigation findings'} availableEvidence={artifacts.map(a=>({id:a.id,operation:a.operation,version:a.version,params:a.params}))}/>}
       <div className="ud-footer"><ShieldCheck size={15}/> Local computation · Version-linked evidence · AI interpretations are advisory, not verified calculations.</div>
     </>}
    </div></div>
   </div>
   {odinOpen&&<aside className="ud-odin" aria-label="ODIN analytical assistant" style={{"--po-odin-width":`${odinWidth}px`} as CSSProperties}><div className="po-dock-resizer" role="separator" aria-label="Resize ODIN dock" aria-orientation="vertical" aria-valuemin={265} aria-valuemax={490} aria-valuenow={odinWidth} tabIndex={0} onPointerDown={startResize} onKeyDown={resizeByKey}/><div className="ud-odin-head"><div className="ud-odin-brand"><span><Sparkles size={20}/></span><div><strong>ODIN</strong><small>Your analytical co-investigator</small></div></div><button title="Close ODIN" aria-label="Close ODIN" onClick={()=>setOdinOpen(false)}><X size={17}/></button></div><div className="ud-odin-scroller"><div className="ud-odin-status"><span className="ud-green-dot"/>{ready?`LOCAL MODEL · ${ollama?.model||'READY'}`:'LOCAL TOOLS AVAILABLE'}<small>Cloud is opt-in only</small></div><div className="ud-odin-intro"><h2>Investigate with intent.</h2><p>I'll help explain the evidence. Verified calculations are performed by the local analytics engine, not invented by AI.</p></div>{investigation&&<div className="ud-odin-context"><span>ACTIVE INVESTIGATION</span><b>{investigation.objective}</b><small>Dataset v{investigation.version} · {artifacts.length} evidence artifacts</small></div>}
    {investigation&&<div className="ud-autonomy"><div className="ud-autonomy-head"><strong>Autonomous investigation</strong><span>LOCAL · READ ONLY</span></div><p>ODIN plans each step. Python validates and saves the evidence. Data changes require separate approval.</p>{autonomous&&<div className="ud-autonomy-status" role="status"><b>{nice(autonomous.status)}</b><small>{autonomous.steps.filter(s=>!!s.evidence_id).length} verified steps / {autonomous.max_steps} maximum</small>{autonomous.stop_reason&&<p>{autonomous.stop_reason}</p>}{autonomous.last_error&&<p className="ud-ai-error">{autonomous.last_error}</p>}{autonomous.steps.length>0&&<ol>{autonomous.steps.map(s=><li key={s.id}><span>{nice(s.proposal.tool==='none'?s.proposal.intent:s.proposal.tool)}</span><small>{s.evidence_id?'Evidence saved':nice(s.status)}</small></li>)}</ol>}</div>}{autonomyError&&<p className="ud-ai-error" role="alert">{autonomyError}</p>}<div className="ud-autonomy-actions">{!autonomous?<button className="ud-btn ud-btn-primary" disabled={autonomyBusy||busy!==''||stale} onClick={()=>void controlAutonomy('start')}>Investigate automatically <ArrowRight size={15}/></button>:<>{['interrupted','failed','needs_review'].includes(autonomous.status)&&<button className="ud-btn ud-btn-primary" disabled={autonomyBusy||stale} onClick={()=>void controlAutonomy('resume')}>Resume investigation</button>}{['queued','running','waiting_for_resources'].includes(autonomous.status)&&<button className="ud-btn ud-btn-quiet" disabled={autonomyBusy} onClick={()=>void controlAutonomy('cancel')}>Cancel analysis</button>}</>}</div><small>AI suggestions are not verified findings. Review the computed evidence before accepting conclusions.</small></div>}
    <div className="ud-odin-prompt"><label htmlFor="ud-ai-prompt">ASK ODIN</label>{aiAnswer&&<div className="ud-ai-answer"><span>{aiAnswer.fallback?'Verified local guidance':`AI interpretation · ${aiAnswer.provider}`}</span><p>{aiAnswer.answer}</p><small>Dataset v{aiAnswer.dataset_version} · Interpretive text, not computed evidence</small></div>}{aiError&&<p className="ud-ai-error" role="alert">{aiError}</p>}<textarea id="ud-ai-prompt" value={aiQuestion} onChange={e=>setAiQuestion(e.target.value)} rows={3} placeholder="Ask a follow-up question about your data…" maxLength={900}/><button className="ud-btn ud-btn-primary" disabled={!investigation||aiBusy||!!busy||stale} onClick={()=>void askOdin()}>{aiBusy?'Working on your answer…':'Ask ODIN'} <Send size={16}/></button><small>Cloud requests require explicit consent in AI Settings. Review prompts for sensitive information.</small></div>
    <div className="ud-odin-subhead">SUGGESTED ANALYSES</div><div className="ud-action-list"><button onClick={()=>setSelectedTool('compare')} className={selectedTool==='compare'?'ud-action-selected':''}><SoftIcon><BarChart3 size={16}/></SoftIcon><span><b>Compare groups</b><small>Median values by category</small></span><ChevronRight size={15}/></button><button onClick={()=>setSelectedTool('missingness')} className={selectedTool==='missingness'?'ud-action-selected':''}><SoftIcon tone="teal"><ShieldCheck size={16}/></SoftIcon><span><b>Inspect missing values</b><small>Column completeness</small></span><ChevronRight size={15}/></button><button onClick={()=>setSelectedTool('distribution')} className={selectedTool==='distribution'?'ud-action-selected':''}><SoftIcon><Activity size={16}/></SoftIcon><span><b>Explore distribution</b><small>Mean, median, IQR</small></span><ChevronRight size={15}/></button><button onClick={()=>setSelectedTool('overview')} className={selectedTool==='overview'?'ud-action-selected':''}><SoftIcon tone="teal"><Database size={16}/></SoftIcon><span><b>Profile dataset</b><small>Rows, columns and quality</small></span><ChevronRight size={15}/></button></div>
    <div className="ud-tool-config">{selectedTool==='compare'&&<><label>Group by<select value={category} onChange={e=>setSelectedCategory(e.target.value)}>{categorical.length?categorical.map(c=><option key={c.name} value={c.name}>{c.name}</option>):<option value="">No categorical fields</option>}</select></label><label>Numeric measure<select value={metric} onChange={e=>setSelectedMetric(e.target.value)}>{numeric.length?numeric.map(c=><option key={c.name} value={c.name}>{c.name}</option>):<option value="">No numeric fields</option>}</select></label></>}{selectedTool==='missingness'&&<label>Field<select value={missingCol} onChange={e=>setSelectedColumn(e.target.value)}>{withMissing.length?withMissing.map(c=><option value={c.name} key={c.name}>{c.name} · {c.missing} missing</option>):<option value="">No missing-value fields</option>}</select></label>}{selectedTool==='distribution'&&<label>Numeric field<select value={distributionCol} onChange={e=>setSelectedColumn(e.target.value)}>{numeric.length?numeric.map(c=><option key={c.name} value={c.name}>{c.name}</option>):<option value="">No numeric fields</option>}</select></label>}</div>
    <button className="ud-btn ud-btn-run" disabled={!investigation||busy!==''||stale||!selectedCanRun} onClick={()=>void run(selectedTool)}>{busy===selectedTool?'Computing verified evidence…':'Run '+({overview:'snapshot',compare:'comparison',missingness:'missingness check',distribution:'distribution'}[selectedTool])}<ArrowRight size={16}/></button>
    <div className="ud-odin-subhead">EVIDENCE ACTIVITY</div><div className="ud-tool-history">{sortedArtifacts.slice(0,4).map(a=><div key={a.id}><CheckCircle2 size={14}/><span>{nice(a.operation)}<small>Dataset v{a.version} · {a.id.slice(0,8)}</small></span></div>)}{!artifacts.length&&<p>No successful tool runs yet.</p>}</div>
    <div className="ud-ai-boundary"><LockKeyhole size={16}/><span>AI cannot directly edit data, run arbitrary scripts or mark uncomputed findings as verified.</span></div>
   </div></aside>}
  </div>;
}
