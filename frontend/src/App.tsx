import {useEffect, useMemo, useRef, useState} from 'react';
import type {ReactNode} from 'react';
import {Activity, AlertCircle, ArrowDownRight, ArrowRight, BarChart3, BrainCircuit, Check, CheckCircle2, ChevronRight, CircleHelp, ClipboardCheck, Database, FileSpreadsheet, FlaskConical, FolderOpen, Layers, LoaderCircle, LockKeyhole, Play, Plus, RefreshCw, ShieldCheck, Sparkles, PanelLeftClose, PanelLeftOpen, Target, UploadCloud, WandSparkles, Search, Menu, X, Keyboard, Wifi, WifiOff, ChevronDown, Settings2, House, MessageSquareText} from 'lucide-react';
import {Experiment, Prep, Profile, Project, Field, get, post, upload} from './api';
import {QualityWorkspace} from './QualityWorkspace';
import {ExploreWorkspace} from './ExploreWorkspace';
import {AssistantWorkspace} from './AssistantWorkspace';
import {AISettings,AIInsight} from './AIWorkspace';
import {EvaluationDetails} from './EvaluationDetails';
import {ModelComparison} from './ModelComparison';
import {StudioHome} from './StudioHome';
import {StudioAssistant} from './StudioAssistant';
import {ReportWorkspace} from './ReportWorkspace';
import {isSecondaryView} from './workspaceLayout';
import {createProjectOperationGuard} from './projectOperationGuard';

type Stage = 'overview'|'understand'|'quality'|'explore'|'prepare'|'model'|'evaluate'|'predict'|'deliver'|'assistant'|'ai_settings';
function requestedStudioStage(): Stage {const match=location.hash.match(/^#\/studio\/(overview|understand|quality|explore|prepare|model|evaluate|predict|deliver|assistant|ai_settings)$/);return (match?.[1] as Stage)||'overview';}
const NAV: {id:Stage;name:string;sub:string;icon:typeof Database}[] = [
  {id:'overview',name:'Overview',sub:'Project workspace',icon:Layers},
  {id:'understand',name:'Understand',sub:'Dataset profiling',icon:Database},
  {id:'quality',name:'Data Quality',sub:'Clean · Review · Undo',icon:ShieldCheck},
  {id:'explore',name:'Explore',sub:'Charts and insights',icon:BarChart3},
  {id:'prepare',name:'Prepare',sub:'Feature review',icon:WandSparkles},
  {id:'model',name:'Model Lab',sub:'Train experiments',icon:FlaskConical},
  {id:'evaluate',name:'Evaluate',sub:'Compare performance',icon:BarChart3},
  {id:'predict',name:'Predict Studio',sub:'Generate predictions',icon:Target},
  {id:'deliver',name:'Deliver',sub:'Persistent reports and exports',icon:FileSpreadsheet},
  {id:'assistant',name:'Ask ODIN',sub:'Hybrid AI dataset copilot',icon:BrainCircuit},
  {id:'ai_settings',name:'AI Settings',sub:'Gemini · Groq · OpenRouter',icon:LockKeyhole}
];
const C_MODELS=[['logistic_regression','Logistic Regression'],['decision_tree','Decision Tree'],['random_forest','Random Forest'],['extra_trees','Extra Trees'],['gradient_boosting','Gradient Boosting']];
const R_MODELS=[['linear_regression','Linear Regression'],['ridge','Ridge Regression'],['decision_tree','Decision Tree'],['random_forest','Random Forest'],['gradient_boosting','Gradient Boosting']];
function fmt(n:number|null|undefined){return typeof n==='number'?n.toLocaleString(undefined,{maximumFractionDigits:4}):'—'}
function fmtPrediction(value:string|number,task:string|undefined){return typeof value==='number'?value.toLocaleString(undefined,{minimumFractionDigits:task==='regression'?2:0,maximumFractionDigits:task==='regression'?2:4}):String(value)}
function cls(...x:(string|false|undefined)[]){return x.filter(Boolean).join(' ')}

/** A second analytical pane receives an explicit stage and cannot control the global route. */
export function App({embeddedStage,embeddedProjectId,onEmbeddedNavigate}:{
  embeddedStage?: Stage;
  embeddedProjectId?: string;
  onEmbeddedNavigate?:(view:Stage)=>void;
}={}){
 const embedded=embeddedStage!==undefined;
  const [project,setProject]=useState<Project|null>(null);
  const [projects,setProjects]=useState<{id:string;name:string;filename:string}[]>([]);
  const [page,setPage]=useState<Stage>(()=>embeddedStage??requestedStudioStage());
  const [file,setFile]=useState<File|null>(null);
  const [loading,setLoading]=useState(false);
  const [error,setError]=useState('');
  const [target,setTarget]=useState('');
  const [prep,setPrep]=useState<Prep|null>(null);
  const [excluded,setExcluded]=useState<string[]>([]);
  const [models,setModels]=useState<string[]>(['logistic_regression','random_forest','extra_trees']);
  const [confirmSplit,setConfirmSplit]=useState(false);
  const [splitStrategy,setSplitStrategy]=useState<'random'|'group'|'time'>('random');
  const [splitColumn,setSplitColumn]=useState('');
  const [sidebarCollapsed,setSidebarCollapsed]=useState(false);
  const [experiment,setExperiment]=useState<Experiment|null>(null);
  const [predictVals,setPredictVals]=useState<Record<string,string>>({});
  const [prediction,setPrediction]=useState<{prediction:string|number;probabilities?:{class:string|number;probability:number}[];warning:string;input_warnings?:string[]}|null>(null);
  const [uploadOpen,setUploadOpen]=useState(false);
  const [busy,setBusy]=useState('');
  const [qualityVersion,setQualityVersion]=useState(0);
  const [featureHints,setFeatureHints]=useState<{column:string;risk:string;reasons:string[]}[]>([]);
  const latestProjectRequest=useRef(0);
  const projectOperations=useRef(createProjectOperationGuard());
  useEffect(()=>()=>projectOperations.current.invalidate(),[]);
  const [paletteOpen,setPaletteOpen]=useState(false);
  const [paletteQuery,setPaletteQuery]=useState('');
  const [mobileOpen,setMobileOpen]=useState(false);
  const [notice,setNotice]=useState('');
  const [cloudStatus,setCloudStatus]=useState<'checking'|'connected'|'local'>('local');
  const [odinOpen,setOdinOpen]=useState(false);
  const [visitedStages,setVisitedStages]=useState<Stage[]>(['overview']);
  const scrollRef=useRef<Record<string,number>>({});
  const mainRef=useRef<HTMLElement|null>(null);
  const previousPage=useRef<Stage>('overview');

  useEffect(()=>{if(embeddedStage!==undefined){setPage(embeddedStage);return;}
  const sync=()=>setPage(requestedStudioStage());
  window.addEventListener('hashchange',sync);return()=>window.removeEventListener('hashchange',sync)
 },[embeddedStage]);
  function go(next:Stage){
    scrollRef.current[page]=mainRef.current?.scrollTop??0;
    if(embedded){
      // Embedded views cannot navigate the main window or escape the dock registry.
      if(!isSecondaryView(next)){
        setNotice('Open this workspace in the primary navigation instead.');
        setPaletteOpen(false);
        return;
      }
      onEmbeddedNavigate?.(next);
      // Prop is authoritative: do not render an unapproved page while it updates.
    }else{
      if(location.hash!==`#/studio/${next}`)location.hash=`#/studio/${next}`;
      setPage(next);
    }
    setError('');setUploadOpen(false);setMobileOpen(false);setPaletteOpen(false);
    setPaletteQuery('');
  }
  useEffect(()=>{setVisitedStages(s=>s.includes(page)?s:[...s,page]);
    if(previousPage.current!==page){
      previousPage.current=page;
      const position=scrollRef.current[page]??0;
      requestAnimationFrame(()=>{if(mainRef.current)mainRef.current.scrollTop=position});
    }
  },[page]);
  useEffect(()=>{
    // Only the primary workspace owns global keyboard shortcuts.
    if(embedded)return;
    const handler=(event:KeyboardEvent)=>{
      if((event.ctrlKey||event.metaKey)&&event.key.toLowerCase()==='k'){event.preventDefault();setPaletteOpen(open=>!open)}
      if(event.key==='Escape'){setPaletteOpen(false);setMobileOpen(false);setOdinOpen(false)}
    };
    window.addEventListener('keydown',handler);
    return()=>window.removeEventListener('keydown',handler);
  },[embedded]);
  useEffect(()=>{if(!notice)return;const t=window.setTimeout(()=>setNotice(''),4500);return()=>window.clearTimeout(t)},[notice]);
  useEffect(()=>{
    // Docked views should not repeat potentially expensive cloud checks.
    if(embedded)return;
    let live=true;
    get<{cloud_enabled:boolean;share_aggregates:boolean;providers:{verified?:boolean}[]}>('/ai/settings').then(async cfg=>{
      if(!live)return;
      if(!cfg.cloud_enabled||!cfg.share_aggregates){setCloudStatus('local');return}
      setCloudStatus(cfg.providers.some(p=>p.verified)?'connected':'checking');
      try{const result=await post<{providers:{status:string}[]}>('/ai/verify-connected',{});
        if(live)setCloudStatus(result.providers.some(p=>p.status==='connected')?'connected':'local')
      }catch{if(live)setCloudStatus('local')}
    }).catch(()=>{if(live)setCloudStatus('local')});
    return()=>{live=false};
  },[embedded]);
  const availableCommands=NAV.filter(n=>!(!project&&n.id!=='ai_settings')&&`${n.name} ${n.sub}`.toLowerCase().includes(paletteQuery.toLowerCase()));

  async function refreshProjects(){try{setProjects(await get<{id:string;name:string;filename:string}[]>('/projects'))}catch{/* backend may not be running */}}
  useEffect(()=>{void refreshProjects();const pid=embeddedProjectId??localStorage.getItem('pilotodin-current');if(pid)void loadProject(pid);},[embeddedProjectId]);
  useEffect(()=>{if(embedded)return;const handler=()=>{const id=localStorage.getItem('pilotodin-current');if(id&&id!==project?.id)void loadProject(id)};window.addEventListener('pilotodin:project-changed',handler);return()=>window.removeEventListener('pilotodin:project-changed',handler)},[project?.id,embedded]);
  useEffect(()=>{if(!embedded&&project?.id)window.dispatchEvent(new Event('pilotodin:project-changed'))},[project?.id,embedded]);
  useEffect(()=>{if(!embedded&&!location.hash.startsWith('#/canvas')&&location.hash!==`#/studio/${page}`)location.hash=`#/studio/${page}`},[page,embedded]);
  async function loadProject(pid:string){
    // The global shell owns the project identity. Embedded panes cannot switch it.
    if(embedded && pid!==embeddedProjectId){
      setNotice('Change projects using the global project selector.');
      return;
    }
    const request=++latestProjectRequest.current;
    const generation=projectOperations.current.begin(pid);
    // Clear previous-project data immediately, including stale experiments and predictions.
    setProject(null);setPrep(null);setExperiment(null);setPrediction(null);setTarget('');
    try{const [p,q]=await Promise.all([get<Project>(`/projects/${pid}`),get<{version:number;profile?:Profile}>(`/projects/${pid}/live-profile`)]);if(request!==latestProjectRequest.current||!projectOperations.current.accepts(pid,generation))return;setQualityVersion(q.version);setFeatureHints([]);setProject(q.profile?{...p,profile:q.profile}:p);if(!embedded)localStorage.setItem('pilotodin-current',pid);setTarget('');setPrep(null);setExcluded([]);setExperiment(null);setPrediction(null);setPredictVals({});setConfirmSplit(false);setPage(embeddedStage??requestedStudioStage());setVisitedStages([embeddedStage??requestedStudioStage()]);scrollRef.current={};setUploadOpen(false);setError('');}catch(e){
      if(request!==latestProjectRequest.current||!projectOperations.current.accepts(pid,generation))return;
      setProject(null);
      setError(`Could not open project: ${(e as Error).message}`);
      // Never remove the user's selected project on a transient API failure.
    }}
  useEffect(()=>{if(!project||!target){setPrep(null);return;}let active=true;
    get<Prep>(`/projects/${project.id}/preparation?target=${encodeURIComponent(target)}`).then(p=>{
      if(!active)return;setPrep(p);setExcluded(p.recommend_exclude.filter(c=>c.reason.includes('constant')||c.reason.includes('all values')).map(c=>c.column));
      setModels(p.task==='classification'?['logistic_regression','random_forest','extra_trees']:['linear_regression','random_forest','gradient_boosting']);
    }).catch(e=>{if(active){setPrep(null);setError(e.message)}});
    return()=>{active=false};
  },[project?.id,target,qualityVersion]);
  useEffect(()=>{if(!project||!target){setFeatureHints([]);return;}let live=true;get<{features:{column:string;risk:string;reasons:string[]}[]}>(`/projects/${project.id}/features?target=${encodeURIComponent(target)}`).then(r=>{if(live)setFeatureHints(r.features)}).catch(()=>{if(live)setFeatureHints([])});return()=>{live=false};},[project?.id,target,qualityVersion]);
  useEffect(()=>{
    if(!experiment||!project||!['queued','running'].includes(experiment.status))return;
    const projectId=project.id, experimentId=experiment.id;
    const generation=projectOperations.current.snapshot(projectId);
    let live=true;
    const timer=setInterval(()=>{
      void get<Experiment>(`/experiments/${experimentId}`).then(result=>{
        if(live&&projectOperations.current.accepts(projectId,generation)&&result.project_id===projectId&&result.id===experimentId)
          setExperiment(current=>current?.id===experimentId?result:current);
      }).catch(e=>{if(live&&projectOperations.current.accepts(projectId,generation))setError(e.message)});
    },1200);
    return()=>{live=false;clearInterval(timer)};
  },[experiment?.id,experiment?.status,project?.id]);
  async function startUpload(){
    if(embedded){setError('Import a new dataset from the primary workspace.');return;}
    if(!file)return;setLoading(true);setError('');try{
    const data=await upload(file);await refreshProjects();await loadProject(data.id);setUploadOpen(false);setFile(null);setNotice("Dataset imported and profiled successfully");
  }catch(e){setError((e as Error).message)}finally{setLoading(false)}}
  async function startTrain(){
    if(!project||!prep)return;
    const projectId=project.id, generation=projectOperations.current.snapshot(projectId);
    setError('');setBusy('train');
    try{
      const d=await post<{id:string;status:string}>(`/projects/${projectId}/experiments`,{
        target,task:prep.task,excluded_features:excluded,models,
        acknowledge_random_split:splitStrategy==='random'?confirmSplit:false,
        split_strategy:splitStrategy,split_column:splitStrategy==='random'?null:splitColumn,
        expected_quality_version:qualityVersion
      });
      if(!projectOperations.current.accepts(projectId,generation))return;
      setExperiment({id:d.id,project_id:projectId,status:d.status,config:{target,task:prep.task,excluded,models,quality_version:qualityVersion,split_strategy:splitStrategy,split_column:splitColumn},results:null,error:null,selected_model:null,final_results:null});
      setProject(p=>p?.id===projectId?{...p,experiments:[{id:d.id,status:d.status,selected_model:null,created_at:new Date().toISOString()},...p.experiments]}:p);
      go('evaluate');setNotice('Experiment created. Training status will update automatically.');
    }catch(e){if(projectOperations.current.accepts(projectId,generation))setError((e as Error).message)}
    finally{if(projectOperations.current.accepts(projectId,generation))setBusy('')}
  }
  async function chooseModel(key:string){
    if(!experiment||!project||experiment.project_id!==project.id)return;
    const projectId=project.id, generation=projectOperations.current.snapshot(projectId), experimentId=experiment.id;
    setError('');setBusy('select');
    try{
      await post(`/experiments/${experimentId}/select`,{model_key:key});
      const result=await get<Experiment>(`/experiments/${experimentId}`);
      if(!projectOperations.current.accepts(projectId,generation)||result.project_id!==projectId)return;
      setExperiment(current=>current?.id===experimentId?result:current);
      setPredictVals({});setPrediction(null);go('predict');
      setNotice('Model selected. Predictions use its saved preprocessing pipeline.');
    }catch(e){if(projectOperations.current.accepts(projectId,generation))setError((e as Error).message)}
    finally{if(projectOperations.current.accepts(projectId,generation))setBusy('')}
  }
  async function runPrediction(){
    if(!experiment||!project||experiment.project_id!==project.id)return;
    const projectId=project.id, generation=projectOperations.current.snapshot(projectId), experimentId=experiment.id;
    setError('');setBusy('predict');
    try{
      const values=Object.fromEntries((experiment.results?.input_schema??[]).map(f=>[f.name,predictVals[f.name]??'']));
      const result=await post<{prediction:string|number;probabilities?:{class:string|number;probability:number}[];warning:string;input_warnings?:string[]}>(`/experiments/${experimentId}/predict`,{values});
      if(!projectOperations.current.accepts(projectId,generation))return;
      setPrediction(result);setNotice('Prediction computed using the selected model');
    }catch(e){if(projectOperations.current.accepts(projectId,generation))setError((e as Error).message)}
    finally{if(projectOperations.current.accepts(projectId,generation))setBusy('')}
  }
  async function reopenExperiment(id:string){
    if(!project)return;
    const projectId=project.id, generation=projectOperations.current.snapshot(projectId);
    setError('');
    try{
      const exp=await get<Experiment>(`/experiments/${id}`);
      if(!projectOperations.current.accepts(projectId,generation))return;
      if(exp.project_id!==projectId){setError('Experiment does not belong to the active project.');return;}
      setExperiment(exp);setTarget(exp.config.target);setPredictVals({});setPrediction(null);
      go(exp.selected_model?'predict':'evaluate');
    }catch(e){if(projectOperations.current.accepts(projectId,generation))setError((e as Error).message)}
  }
  useEffect(()=>{setPredictVals({});setPrediction(null)},[project?.id,experiment?.id,experiment?.selected_model]);
  useEffect(()=>{
   const onDataset=(event:Event)=>{
    if(!project||(event as CustomEvent<{projectId:string}>).detail?.projectId!==project.id)return;
    const currentProjectId=project.id;
    const generation=projectOperations.current.snapshot(currentProjectId);
    void get<{version:number;profile:Profile}>(`/projects/${currentProjectId}/live-profile`).then(next=>{
      if(!projectOperations.current.accepts(currentProjectId,generation))return;
      setQualityVersion(next.version);
      setProject(old=>old?.id===currentProjectId?{...old,profile:next.profile}:old);
      setPrediction(null);
    }).catch(()=>{/* Keep the last verified state until a successful refresh. */});
   };
   window.addEventListener('pilotodin:dataset-changed',onDataset);
   return()=>window.removeEventListener('pilotodin:dataset-changed',onDataset);
  },[project?.id]);
  const profile=project?.profile;
  const prepRisk=prep?.recommend_exclude??[];
  const available=prep?.task==='regression'?R_MODELS:C_MODELS;
  const ordered=useMemo(()=>[...((experiment?.results?.models??[]).filter(x=>x.status==='ready'))].sort((a,b)=> experiment?.results?.task==='regression'?(a.cv_metric??0)-(b.cv_metric??0):(b.cv_metric??0)-(a.cv_metric??0)),[experiment?.results]);
  const hasProject=!!project;
  const stale=!!experiment&&(experiment.is_stale||((experiment.config.quality_version??0)!==qualityVersion));
  async function qualityChanged(){
    if(!project)return;
    const projectId=project.id, generation=projectOperations.current.snapshot(projectId);
    try{
      const v=await get<{version:number;profile:Profile}>(`/projects/${projectId}/live-profile`);
      if(!projectOperations.current.accepts(projectId,generation))return;
      setQualityVersion(v.version);
      setProject(old=>old?.id===projectId?{...old,profile:v.profile}:old);
      if(experiment?.project_id===projectId){
        const updated=await get<Experiment>(`/experiments/${experiment.id}`);
        if(!projectOperations.current.accepts(projectId,generation))return;
        if(updated.project_id===projectId)setExperiment(current=>current?.id===updated.id?updated:current);
      }
      setPrediction(null);setNotice('Working dataset updated; dependent insights will refresh.');
    }catch(e){if(projectOperations.current.accepts(projectId,generation))setError((e as Error).message)}
  }
  return <div className={cls("app","studio-app",sidebarCollapsed&&"sidebar-collapsed",mobileOpen&&"mobile-open")}>
    {mobileOpen&&<button className="mobile-backdrop" aria-label="Close navigation" onClick={()=>setMobileOpen(false)}/>}
    <aside className="sidebar studio-sidebar">
      <div className="brand studio-brand"><div className="brand-mark"><img src="/pilotodin-symbol.svg" alt="" /></div><div><div className="brand-name"><span className="brand-pilot">pilot</span><span>ODIN</span></div><div className="brand-sub">INTELLIGENCE STUDIO</div></div></div>
      <button className="sidebar-collapse studio-collapse" aria-label={sidebarCollapsed?"Expand navigation":"Collapse navigation"} title={sidebarCollapsed?"Expand navigation":"Collapse navigation"} onClick={()=>setSidebarCollapsed(v=>!v)}>{sidebarCollapsed?<PanelLeftOpen size={17}/>:<><PanelLeftClose size={17}/> Minimise sidebar</>}</button>
      <div className="studio-nav-scroll">
        <div className="workspace-label">YOUR PROJECT</div>
        <div className="project-choose"><FolderOpen size={17}/><select aria-label="Choose project" value={project?.id??''} onChange={e=>void loadProject(e.target.value)}><option value="" disabled>Choose a project</option>{projects.map(p=><option key={p.id} value={p.id}>{p.name}</option>)}</select></div>
        <button className="new-project" disabled={embedded} onClick={()=>{if(!embedded){setUploadOpen(true);go('overview')}}}><Plus size={16}/> New dataset</button>
        <nav aria-label="Main navigation" className="studio-nav">
          <div className="workspace-label second">YOUR WORKSPACE</div>
          {NAV.filter(n=>['overview','understand','quality','explore'].includes(n.id)).map(n=>{const Icon=n.id==='overview'?House:n.icon;return <button key={n.id} className={cls('nav-item',page===n.id&&'active')} title={n.name} aria-label={n.name} aria-current={page===n.id?'page':undefined} disabled={!hasProject} onClick={()=>go(n.id)}><Icon size={18}/><span>{n.id==='overview'?'Home':n.id==='understand'?'Your data':n.name}</span>{page===n.id&&<span className="studio-active-pin"/>}</button>})}
          <div className="workspace-label second">MODEL & PREDICT</div>
          {NAV.filter(n=>['prepare','model','evaluate','predict','deliver'].includes(n.id)).map(n=>{const Icon=n.icon;return <button key={n.id} className={cls('nav-item',page===n.id&&'active')} title={n.name} aria-label={n.name} aria-current={page===n.id?'page':undefined} disabled={!hasProject} onClick={()=>go(n.id)}><Icon size={18}/><span>{n.id==='prepare'?'Preparation':n.id==='model'?'Model Lab':n.id==='evaluate'?'Evaluation':n.id==='deliver'?'Deliver':'Predictions'}</span>{page===n.id&&<span className="studio-active-pin"/>}</button>})}
          <div className="workspace-label second">INTELLIGENCE</div>
          {NAV.filter(n=>['assistant','ai_settings'].includes(n.id)).map(n=>{const Icon=n.icon;return <button key={n.id} className={cls('nav-item',page===n.id&&'active')} title={n.name} aria-label={n.name} aria-current={page===n.id?'page':undefined} disabled={!hasProject&&n.id!=='ai_settings'} onClick={()=>go(n.id)}><Icon size={18}/><span>{n.id==='assistant'?'Ask ODIN':'AI connections'}</span>{page===n.id&&<span className="studio-active-pin"/>}</button>})}
        </nav>
      </div>
      <button className="studio-sidebar-odin" onClick={()=>{if(project)setOdinOpen(true);else go('ai_settings')}}><span className="studio-side-orb"><Sparkles size={19}/></span><span><b>ODIN companion</b><small>{cloudStatus==='connected'?'Cloud intelligence online':cloudStatus==='checking'?'Verifying providers…':'Local analysis available'}</small></span><ArrowRight size={15}/></button>
    </aside>
    <main className="main studio-main" ref={mainRef}>
      <header className="topbar studio-topbar">
        <div className="topbar-leading"><button className="icon-btn mobile-menu-btn" aria-label="Open navigation" onClick={()=>setMobileOpen(true)}><Menu size={19}/></button><span className="studio-topcrumb">Workspace</span><ChevronRight size={14}/><span className="studio-top-location">{page==='overview'?'Home':NAV.find(n=>n.id===page)?.name}</span></div>
        <div className="top-right studio-top-right"><button className="studio-odin-trigger" title="Explore the new investigation canvas" onClick={()=>{if(!embedded)location.hash='#/canvas'}}>New Canvas <ArrowRight size={15}/></button><button className="global-search" onClick={()=>setPaletteOpen(true)} title="Search workspaces (Ctrl+K)"><Search size={17}/><span>Search or jump to…</span><kbd>Ctrl K</kbd></button><span className={cls('connection-pill',cloudStatus)}><span className="status-orb"/>{cloudStatus==='connected'?'AI ready':cloudStatus==='checking'?'Connecting…':'Local ready'}</span><button className="studio-icon-action" aria-label="AI settings" title="AI settings" onClick={()=>go('ai_settings')}><Settings2 size={18}/></button><button className={cls('studio-odin-trigger',odinOpen&&'engaged')} aria-label="Open ODIN companion" disabled={!project} onClick={()=>setOdinOpen(true)}><Sparkles size={17}/><span>Ask ODIN</span></button></div>
      </header>
      <div className="content po-motion-stage" id="workspace-content" key={`${project?.id??'none'}-${page}`}>
        {busy&&<div className="operation-status" role="status" aria-live="polite"><LoaderCircle size={16} className="spin"/><span>{busy==='train'?'Submitting training experiment…':busy==='select'?'Selecting and validating model…':busy==='predict'?'Computing prediction…':'Working…'}</span></div>}
        {error&&<div className="alert-error"><AlertCircle size={18}/><span>{error}</span><button onClick={()=>setError('')}>Dismiss</button></div>}
        {((!project&&page!=='ai_settings')||uploadOpen)&&<section className="landing">{project&&<button className="studio-cancel-upload" onClick={()=>setUploadOpen(false)} aria-label="Cancel new dataset">Cancel upload <X size={16}/></button>}<div className="hero-flag"><Sparkles size={16}/> INTELLIGENT DATA SCIENCE</div><h1>Turn raw data into<br/><em>predictive intelligence.</em></h1><p>Upload a dataset, explore its structure, compare machine learning models and build a working prediction tool. All on your own machine.</p>
          <div className="upload-card"><div className="upload-visual"><UploadCloud size={30}/></div><h3>Start with your dataset</h3><p>CSV or Excel • Up to 40 MB • First worksheet used</p><label className="file-choose"><input type="file" accept=".csv,.xlsx" onChange={(e:any)=>setFile(e.target.files?.[0]??null)}/>{file?file.name:'Choose a file'}</label><button className="btn primary" disabled={!file||loading} onClick={()=>void startUpload()}>{loading?<LoaderCircle className="spin" size={16}/>:<ArrowRight size={16}/>} {loading?'Analysing dataset…':'Analyse dataset'}</button></div>
          <div className="landing-notes"><span><ShieldCheck size={16}/> Files stay on your machine</span><span><Database size={16}/> Real Python ML pipelines</span><span><LockKeyhole size={16}/> Cloud AI requires explicit opt-in</span></div>
        </section>}
        {page==='ai_settings'&&!uploadOpen&&<AISettings/>}
        {project&&!uploadOpen&&page!=='ai_settings'&&<>
          {page!=='overview'&&<div className="heading"><div><div className="eyebrow">PROJECT / {project.name.toUpperCase()}</div><h1>{NAV.find(x=>x.id===page)?.name}</h1><p>{page==='understand'?'Explore the shape, quality and meaning of your uploaded data.':page==='quality'?'Review issues, make safe corrections and restore versions.':page==='explore'?'Investigate distributions, variables and relationships.':page==='assistant'?'Ask questions about verified facts in your dataset.':page==='prepare'?'Review what the model should learn and which features it may use.':page==='model'?'Choose algorithms and run an evidence-based comparison.':page==='evaluate'?'Understand model performance before selecting a prediction pipeline.':'Apply your selected model to new observations.'}</p></div><div className="head-label"><FileSpreadsheet size={16}/>{project.filename}</div></div>}
          
          {page==='deliver'&&<ReportWorkspace key={project.id} projectId={project.id} />}
          {page==='overview'&&<StudioHome project={project} projects={projects} onGo={go} onNew={()=>setUploadOpen(true)} onOpenProject={id=>void loadProject(id)} onResume={reopenExperiment} onAI={()=>setOdinOpen(true)}/>}
          {page==='quality'&&<section className="persisted-workspace"><QualityWorkspace key={project.id} projectId={project.id} onChanged={()=>void qualityChanged()}/></section>}
          {page==='explore'&&<section className="persisted-workspace"><ExploreWorkspace key={project.id} projectId={project.id} versionToken={qualityVersion}/></section>}
          {page==='assistant'&&<section className="persisted-workspace"><AssistantWorkspace key={project.id} projectId={project.id} onSettings={()=>go('ai_settings')}/></section>}
          {page==='understand'&&profile&&<><div className="metrics"><Metric label="DATASET RECORDS" value={fmt(profile.rows)} icon={<Database size={18}/>}/><Metric label="TOTAL COLUMNS" value={fmt(profile.columns_count)} icon={<Layers size={18}/>}/><Metric label="MISSING CELLS" value={fmt(profile.missing_cells)} icon={<CircleHelp size={18}/>}/><Metric label="EXACT DUPLICATES" value={fmt(profile.duplicate_rows)} icon={<Activity size={18}/>}/></div>
            <div className="panel insight"><div className="panel-title"><Sparkles size={19}/><h2>Dataset interpretation</h2><span className="pill muted">RULE-BASED ANALYSIS</span></div><p>{profile.summary}</p><p className="muted-caption">Local dataset statistics are calculated in Python. ODIN Intelligence above provides optional cloud-assisted interpretation from approved summaries.</p></div>
            <div className="panel"><div className="panel-title"><Database size={19}/><h2>Column intelligence</h2><span className="pill">{profile.columns.length} fields</span></div><div className="table-scroll"><table><thead><tr><th>COLUMN</th><th>TYPE</th><th>UNIQUE</th><th>MISSING</th><th>CHECK</th></tr></thead><tbody>{profile.columns.map(c=><tr key={c.name}><td className="cell-strong">{c.name}</td><td><span className="pill">{c.kind}</span></td><td>{fmt(c.unique)}</td><td>{fmt(c.missing_pct)}%</td><td>{c.leakage_risk?<span className="warn">Leakage risk</span>:c.identifier_risk?<span className="warn">Identifier?</span>:<span className="okay">Normal</span>}</td></tr>)}</tbody></table></div></div>
            <div className="panel"><div className="panel-title"><FileSpreadsheet size={18}/><h2>Data preview</h2></div><div className="table-scroll"><table><thead><tr>{profile.columns.slice(0,10).map(c=><th key={c.name}>{c.name}</th>)}</tr></thead><tbody>{profile.preview.map((row,i)=><tr key={i}>{profile.columns.slice(0,10).map(c=><td key={c.name}>{row[c.name]===null?'—':String(row[c.name]??'—').slice(0,55)}</td>)}</tr>)}</tbody></table></div><p className="muted-caption">Showing up to 7 rows and 10 columns.</p></div>
            {profile.warnings.length>0&&<div className="panel"><div className="panel-title"><AlertCircle size={18}/><h2>Review before modelling</h2></div>{profile.warnings.slice(0,7).map((s,i)=><div key={i} className="warning-line"><AlertCircle size={15}/>{s}</div>)}</div>}
            <div className="panel action-panel"><div><h3>Ready to define your objective?</h3><p>Choose the column you want to predict and review the preparation plan.</p></div><button className="btn primary" onClick={()=>go('prepare')}>Prepare data <ArrowRight size={17}/></button></div>
          </>}
          {page==='prepare'&&profile&&<><div className="panel"><div className="panel-title"><Target size={19}/><h2>Define your prediction target</h2></div><p className="body-muted">Which column contains the outcome you want to predict? Suggestions are based on names only and require your confirmation.</p><label className="field-label">TARGET VARIABLE</label><select className="input full" value={target} onChange={(e:any)=>{setTarget(e.target.value);setExperiment(null);setConfirmSplit(false);setError('')}}><option value="">Select a target column…</option>{profile.columns.map(c=><option value={c.name} key={c.name}>{c.name}{profile.target_candidates.includes(c.name)?' · suggested':''}</option>)}</select>{profile.target_candidates.length>0&&<div className="mini-info"><Sparkles size={16}/> Possible targets: {profile.target_candidates.join(', ')}</div>}</div>
            {prep&&<><div className="metrics three"><Metric label="TASK IDENTIFIED" value={prep.task==='classification'?'Classification':'Regression'} icon={<Target size={18}/>} small/><Metric label="PREDICTORS" value={String(prep.available_features.length-excluded.length)} icon={<Database size={18}/>}/><Metric label="MISSING TARGETS" value={String(prep.missing_targets)} icon={<Activity size={18}/>}/></div>
              <div className="panel"><div className="panel-title"><ClipboardCheck size={19}/><h2>Review feature exclusions</h2></div><p className="body-muted">The model will use all columns except the target and features you deliberately exclude. Suggested exclusions are not automatically enforced.</p>
                <button className="btn small" onClick={()=>setExcluded(featureHints.filter(f=>f.risk==='high').map(f=>f.column))}><Sparkles size={14}/> Apply high-risk exclusion suggestions</button>
                <p className="muted-caption">Only structural screening, not validated importance: verify timing and compare features with training-only cross-validation.</p>
                {featureHints.filter(f=>f.risk!=='low').map(f=><div className="warning-line" key={f.column}><AlertCircle size={14}/><b>{f.column}</b>: {f.reasons.join('; ')}</div>)}
                <div className="feature-grid">{prep.available_features.map(c=>{const hint=prepRisk.find(x=>x.column===c);const isOut=excluded.includes(c);return <label className={cls('feature-chip',isOut&&'excluded')} key={c}><input type="checkbox" checked={isOut} onChange={(e:any)=>setExcluded(a=>e.target.checked?[...a,c]:a.filter(x=>x!==c))}/><span>{c}</span>{hint&&<span title={hint.reason}><AlertCircle size={15}/></span>}</label>})}</div>
                <p className="muted-caption">Checked features will be excluded. Columns with warning icons need contextual review.</p>
              </div>
              <div className="panel insight"><div className="panel-title"><WandSparkles size={19}/><h2>Automatic preprocessing plan</h2></div>{prep.transformations.map((p,i)=><div className="checkline" key={i}><CheckCircle2 size={17}/>{p}</div>)}<p className="muted-caption">Preprocessing is learned independently within cross-validation folds to avoid test leakage.</p></div>
              <div className="panel action-panel"><div><h3>Preparation configuration ready</h3><p>Your source file is preserved; this configuration determines the modelling inputs.</p></div><button className="btn primary" onClick={()=>go('model')}>Open Model Lab <ArrowRight size={17}/></button></div>
            </>}
          </>}
          {page==='model'&&!prep&&<MissingRequirement icon={<FlaskConical size={30}/>} title="Choose a prediction target first" body="Model Lab needs a confirmed target and preprocessing plan. You can return here at any time." action="Review preparation" onAction={()=>go('prepare')}/>}
          {page==='model'&&prep&&<><div className="panel"><div className="panel-title"><FlaskConical size={19}/><h2>Choose up to five models</h2><span className="pill">{models.length} / 5 selected</span></div><p className="body-muted">PilotODIN will compare models using cross-validation on the development split. Higher macro F1 is better for classification; lower MAE is better for regression.</p><div className="mini-info"><Sparkles size={16}/> Suggested comparison: {prep.task==='regression'?'Linear Regression as a transparent baseline alongside Random Forest / Gradient Boosting':'Logistic Regression as an interpretable baseline alongside Random Forest / Extra Trees'}. The winner is decided by cross-validation, not the suggestion.</div>
            <div className="model-grid">{available.map(([key,label])=><button key={key} className={cls('model-choice',models.includes(key)&&'chosen')} onClick={()=>setModels(a=>a.includes(key)?a.filter(x=>x!==key):a.length<5?[...a,key]:a)}><div className="model-icon">{models.includes(key)?<Check size={18}/>:<FlaskConical size={18}/>}</div><span>{label}</span></button>)}</div></div>
            <div className="panel"><div className="panel-title"><ShieldCheck size={19}/><h2>Validation safeguards</h2></div><div className="validation-row"><span>Hold-out test set</span><strong>20% (untouched until model selection)</strong></div><div className="validation-row"><span>Development split</span><strong>80% (5-fold CV when possible)</strong></div><div className="validation-row"><span>Primary metric</span><strong>{prep.task==='classification'?'Macro F1':'Mean Absolute Error'}</strong></div>
              <label className="field-label">VALIDATION STRATEGY</label>
              <select className="input" value={splitStrategy} onChange={e=>{setSplitStrategy(e.target.value as 'random'|'time'|'group');setConfirmSplit(false);setSplitColumn('')}}><option value="random">Random: independent observations</option><option value="time">Time: train on earlier records, test on later records</option><option value="group">Group: keep repeated entities in separate folds</option></select>
              {splitStrategy!=='random'&&<><label className="field-label">{splitStrategy==='time'?'DATE / TIME COLUMN':'GROUP / ENTITY COLUMN'}</label><select className="input" value={splitColumn} onChange={e=>setSplitColumn(e.target.value)}><option value="">Choose column…</option>{(profile?.columns??[]).filter(c=>c.name!==target).map(c=><option key={c.name} value={c.name}>{c.name}</option>)}</select><p className="muted-caption">The split column is excluded from predictors to reduce leakage.</p></>}
              {splitStrategy==='random'&&<label className="acknowledge"><input type="checkbox" checked={confirmSplit} onChange={(e:any)=>setConfirmSplit(e.target.checked)}/><span>I confirm that a random split is appropriate. Records are not time-ordered or repeated measurements of the same entity requiring grouped validation.</span></label>}
              <div className="mini-info warn-icon"><AlertCircle size={17}/> Choose the split strategy that matches your data. Random splitting can leak information when records are ordered or repeated; group and time strategies are available above.</div>
            </div><div className="panel action-panel"><div><h3>Start your experiment</h3><p>{models.length} algorithms selected. Model training runs locally in Python.</p></div><button className="btn primary" disabled={!models.length||(splitStrategy==='random'?!confirmSplit:!splitColumn)||busy==='train'} onClick={()=>void startTrain()}>{busy==='train'?<LoaderCircle size={16} className="spin"/>:<Play size={17}/>} Train models</button></div>
          </>}
          {page==='evaluate'&&<>{!experiment?<div className="empty-panel"><FlaskConical size={30}/><h3>No experiment selected</h3><button className="btn primary" onClick={()=>go('model')}>Open Model Lab</button>{project.experiments.map(x=><button className="mini-experiment" key={x.id} onClick={()=>void reopenExperiment(x.id)}>{x.created_at.slice(0,16)} · {x.status} <ArrowRight size={14}/></button>)}</div>:
            <>{['queued','running'].includes(experiment.status)?<div className="empty-panel"><LoaderCircle size={35} className="spin"/><h3>Training in progress</h3><p>Cross-validating models, fitting preprocessing and saving pipelines.</p><div className="pulse-bar"/></div>:
            experiment.status==='failed'?<div className="empty-panel"><AlertCircle size={35}/><h3>Training failed</h3><p>{experiment.error}</p><button className="btn" onClick={()=>go('model')}>Review configuration</button></div>:experiment.results&&<><div className="metrics three"><Metric label="TRAINING ROWS" value={fmt(experiment.results.train_rows)} icon={<Database size={18}/>}/><Metric label="FINAL TEST ROWS" value={fmt(experiment.results.test_rows)} icon={<ShieldCheck size={18}/>}/><Metric label="CROSS-VALIDATION" value={`${experiment.results.folds} folds`} icon={<RefreshCw size={18}/>}/></div>
              <div className="panel"><div className="panel-title"><BarChart3 size={19}/><h2>Cross-validation leaderboard</h2><span className="pill">{experiment.results.primary_metric}</span></div><p className="body-muted">This ranking is based only on development-set cross-validation. The final test set has not been used to choose a winner.</p><div className="table-scroll"><table><thead><tr><th>MODEL</th><th>CV SCORE</th><th>STD DEV.</th><th>ACTION</th></tr></thead><tbody>{ordered.map((m,i)=><tr key={m.key}><td className="cell-strong">{i===0&&<span className="winner">★</span>}{m.name}</td><td>{experiment.results!.task==='classification'?`${((m.cv_metric??0)*100).toFixed(1)}%`:fmt(m.cv_metric)}</td><td>{fmt(m.cv_std)}</td><td>{experiment.selected_model===m.key?<span className="okay">Selected</span>:!experiment.selected_model?<button className="btn small" disabled={busy==='select'} onClick={()=>void chooseModel(m.key)}>Select model <ArrowRight size={14}/></button>:<span className="body-muted">Not selected</span>}</td></tr>)}</tbody></table></div><ModelComparison results={experiment.results}/>{experiment.results.models.filter(m=>m.status==='failed').map(m=><div className="warning-line" key={m.key}><AlertCircle size={15}/>{m.name}: {m.error}</div>)}<div className={cls("mini-info",experiment.results.beats_baseline===false&&"warn-icon")}><Activity size={16}/> Baseline CV score: {experiment.results.task==='classification'?`${(experiment.results.baseline_cv*100).toFixed(1)}% macro F1`:fmt(experiment.results.baseline_cv)}. {experiment.results.beats_baseline===false?"No trained model beat the baseline. Do not assume the highest-ranked model is useful.":"Higher-ranked models are not automatically trustworthy. Inspect held-out results."}</div></div>
              {experiment.final_results&&<EvaluationDetails experiment={experiment}/>}
              {experiment.selected_model&&<button className="btn primary" onClick={()=>go('predict')}>Open Predict Studio <ArrowRight size={16}/></button>}
            </>}
            </>}
          </>}
          {stale&&['model','evaluate','predict'].includes(page)&&<div className="alert-error"><AlertCircle size={16}/> This experiment was trained on a previous data version. Metrics are historical; train a new experiment on Version {qualityVersion} before new predictions.</div>}
          {page==='predict'&&(!experiment?.selected_model||!experiment.results)&&<MissingRequirement icon={<Target size={30}/>} title="No prediction model selected" body="Choose an experiment, review its evaluation, and select a trained model before predicting." action="View experiments" onAction={()=>go('evaluate')}/>}
          {page==='predict'&&experiment?.selected_model&&experiment.results&&!stale&&<div className="pred-grid"><div className="panel"><div className="panel-title"><Target size={19}/><h2>New prediction</h2></div><div className="mini-info"><CheckCircle2 size={16}/> Using {experiment.results.models.find(m=>m.key===experiment.selected_model)?.name} and its fitted preprocessing pipeline.</div>
            <div className="fields-grid">{experiment.results.input_schema.map((f:Field)=><label className="field-wrap" key={f.name}><span className="field-label">{f.name}</span>{f.kind==='select'?<select className="input" value={predictVals[f.name]??''} onChange={(e:any)=>{setPredictVals(a=>({...a,[f.name]:e.target.value}));setPrediction(null)}}><option value="">Missing / unspecified</option>{f.options?.map(c=><option key={c} value={c}>{c}</option>)}</select>:<input className="input" type={f.kind==='number'?'number':'text'} step="any" placeholder={f.kind==='number'&&f.min!==null?`e.g. ${f.min}`:'Enter value'} value={predictVals[f.name]??''} onChange={(e:any)=>{setPredictVals(a=>({...a,[f.name]:e.target.value}));setPrediction(null)}}/>}</label>)}</div><button className="btn primary full" disabled={busy==='predict'} onClick={()=>void runPrediction()}>{busy==='predict'?<LoaderCircle size={16} className="spin"/>:<Sparkles size={16}/>} Generate prediction</button><p className="muted-caption">Blank fields are passed as missing values and handled by the fitted preprocessing pipeline.</p></div>
            <div className="panel prediction-output"><div className="panel-title"><Activity size={19}/><h2>Prediction result</h2></div>{!prediction?<div className="waiting-result"><Target size={35}/><h3>Ready when you are</h3><p>Complete the input form and run your selected model.</p></div>:<><div className="result-hint">PREDICTED {experiment.results.target.toUpperCase()}</div><div className="result-text">{fmtPrediction(prediction.prediction,experiment.results?.task)}</div><p className="prediction-meaning">Predicted value for <b>{experiment.results.target}</b>: <b>{fmtPrediction(prediction.prediction,experiment.results.task)}</b>. {experiment.results.task==='classification'?'Class assignment from the selected model. These probabilities are model estimates, not guarantees.':'Numeric estimate in the target column’s original units; units must be verified with the data owner.'}</p>{prediction.probabilities&&<div className="probabilities">{prediction.probabilities.map(p=><div key={p.class}><div className="prob-label"><span>{String(p.class)}</span><b>{(p.probability*100).toFixed(1)}%</b></div><div className="progress"><div style={{width:`${p.probability*100}%`}}/></div></div>)}</div>}<div className="mini-info warn-icon" role="alert"><AlertCircle size={16}/>{prediction.warning}</div>{prediction.input_warnings?.map((w,i)=><div key={i} className="warning-line"><AlertCircle size={14}/>{w}</div>)}{experiment.final_results&&<div className="prediction-reference"><strong>Model performance on held-out data</strong>{experiment.results.task==='regression'?<p>MAE: {fmt(experiment.final_results.mae as number)} · R²: {fmt(experiment.final_results.r2 as number)}. These describe overall test performance, not a guaranteed error range for this individual prediction.</p>:<p>Test accuracy: {typeof experiment.final_results.accuracy==='number'?(100*(experiment.final_results.accuracy as number)).toFixed(1)+'%':'—'}. This is not the certainty of this specific prediction.</p>}</div>}{(experiment.final_results as {reliability?:{issues?:string[]}}|null)?.reliability?.issues?.length? <div className="reliability-warning"><ShieldCheck size={20}/><div><strong>Unreliable model: experimental prediction only</strong><p>{(experiment.final_results as {reliability?:{issues?:string[]}}).reliability?.issues?.join(" ")}</p></div></div>:null}</>}</div></div>}
        </>}
      </div>
    </main>
    {project&&!embedded&&!uploadOpen&&page!=='ai_settings'&&<StudioAssistant open={odinOpen} onClose={()=>setOdinOpen(false)} onChat={()=>{setOdinOpen(false);go('assistant')}} scope={page==='overview'?'Home':NAV.find(n=>n.id===page)?.name??'Workspace'}><AIInsight key={project.id+':'+page} projectId={project.id} scope={page==='assistant'?'overview':page} version={qualityVersion} target={target} experimentId={experiment?.id} prediction={prediction} onOpenSettings={()=>{setOdinOpen(false);go('ai_settings')}}/></StudioAssistant>}
    {notice&&<div className="toast" role="status"><CheckCircle2 size={18}/><span>{notice}</span><button aria-label="Dismiss notification" onClick={()=>setNotice('')}><X size={15}/></button></div>}
    {paletteOpen&&<div className="command-backdrop" onMouseDown={()=>setPaletteOpen(false)}><section className="command-modal" role="dialog" aria-modal="true" aria-label="Search PilotODIN workspaces" onMouseDown={e=>e.stopPropagation()}>
      <div className="command-input-row"><Search size={21}/><input autoFocus aria-label="Search workspaces" placeholder="Where would you like to go?" value={paletteQuery} onChange={e=>setPaletteQuery(e.target.value)} onKeyDown={e=>{if(e.key==='Enter'&&availableCommands[0])go(availableCommands[0].id)}}/><button className="icon-btn" aria-label="Close command palette" onClick={()=>setPaletteOpen(false)}><X size={17}/></button></div>
      <p className="command-caption">WORKSPACES · {availableCommands.length} RESULTS</p>
      <div className="command-list">{availableCommands.map(n=>{const Icon=n.icon;return <button key={n.id} onClick={()=>go(n.id)}><span className="command-icon"><Icon size={18}/></span><span><b>{n.name}</b><small>{n.sub}</small></span><ArrowRight size={16}/></button>})}{!availableCommands.length&&<p className="command-empty">No matching workspace. Try a different name.</p>}</div>
      <div className="command-footer"><Keyboard size={15}/> Ctrl+K to open · Esc to close · Enter to select first match</div>
    </section></div>}
  </div>
}
function MissingRequirement({icon,title,body,action,onAction}:{icon:ReactNode;title:string;body:string;action:string;onAction:()=>void}){
  return <div className="empty-panel">{icon}<h3>{title}</h3><p>{body}</p><button className="btn primary" onClick={onAction}>{action} <ArrowRight size={16}/></button></div>
}
function Metric({label,value,icon,small=false}:{label:string;value:string;icon:ReactNode;small?:boolean}){return <div className="metric"><div className="metric-top"><span>{label}</span>{icon}</div><strong className={small?'small-value':''}>{value}</strong><div className="metric-bottom"><span/> Computed from dataset</div></div>}
