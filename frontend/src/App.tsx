import {useEffect, useId, useMemo, useRef, useState} from 'react';
import type {ReactNode} from 'react';
import {Activity, AlertCircle, ArrowDownRight, ArrowRight, BarChart3, BrainCircuit, Check, CheckCircle2, ChevronRight, CircleHelp, ClipboardCheck, Database, FileSpreadsheet, FlaskConical, FolderOpen, Layers, LoaderCircle, LockKeyhole, Play, Plus, RefreshCw, ShieldCheck, Sparkles, PanelLeftClose, PanelLeftOpen, Target, UploadCloud, WandSparkles, Search, Menu, X, Keyboard, Wifi, WifiOff, ChevronDown, Settings2, House, MessageSquareText} from 'lucide-react';
import {Experiment, Prep, Profile, Project, Field, get, post, upload} from './api';
import {QualityWorkspace} from './QualityWorkspace';
import {CategoryQualityAdvice} from './CategoryQualityReviewPrompt';
import {hasWhitespaceCategoryCollision} from './categoryQualityAdvice';
import {visibleFeatureHints} from './featureHintScope';
import {selectedFeatureBudget} from './selectedFeatureBudget';
import type {ScopedFeatureHints} from './featureHintScope';
import type {QualityFocus} from './qualityHandoff';
import {ExploreWorkspace} from './ExploreWorkspace';
import {ColumnInvestigation} from './ColumnInvestigation';
import {TargetOpportunities} from './TargetOpportunities';
import {AssistantWorkspace} from './AssistantWorkspace';
import {AISettings,AIInsight} from './AIWorkspace';
import {EvaluationDetails} from './EvaluationDetails';
import {ModelComparison} from './ModelComparison';
import {predictionCategoryChoices} from './predictionCategoryChoices';
import {StudioHome} from './StudioHome';
import {StudioAssistant} from './StudioAssistant';
import {ReportWorkspace} from './ReportWorkspace';
import {isSecondaryView} from './workspaceLayout';
import {createProjectOperationGuard} from './projectOperationGuard';
import {createLiveProfileVersionGuard} from './liveProfileVersionGuard';
import {mayCommitProjectSelection} from './projectSelectionCommitGuard';
import {navigateHashSmoothly} from './navigationMotion';

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
const C_MODELS=[['logistic_regression','Logistic Regression'],['decision_tree','Decision Tree'],['random_forest','Random Forest'],['extra_trees','Extra Trees'],['gradient_boosting','Gradient Boosting'],['hist_gradient_boosting','Histogram Gradient Boosting'],['knn','K-Nearest Neighbours'],['svm','Support Vector Classifier'],['naive_bayes','Gaussian Naive Bayes']];
const R_MODELS=[['linear_regression','Linear Regression'],['ridge','Ridge Regression'],['elastic_net','Elastic Net'],['decision_tree','Decision Tree'],['random_forest','Random Forest'],['gradient_boosting','Gradient Boosting'],['hist_gradient_boosting','Histogram Gradient Boosting'],['knn','K-Nearest Neighbours'],['svr','Support Vector Regression']];
type ModelCategory='Baseline & Linear'|'Trees & Ensembles'|'Distance & Margin'|'Probabilistic';
const MODEL_CATEGORIES:ModelCategory[]=['Baseline & Linear','Trees & Ensembles','Distance & Margin','Probabilistic'];
const MODEL_INFO:Record<string,{category:ModelCategory;summary:string;cost:string}>={
 logistic_regression:{category:'Baseline & Linear',summary:'Interpretable classification baseline',cost:'Light'},
 linear_regression:{category:'Baseline & Linear',summary:'Interpretable regression baseline',cost:'Light'},
 ridge:{category:'Baseline & Linear',summary:'Regularised linear regression',cost:'Light'},
 elastic_net:{category:'Baseline & Linear',summary:'Sparse and regularised linear estimator',cost:'Light'},
 decision_tree:{category:'Trees & Ensembles',summary:'Single, inspectable decision tree',cost:'Light'},
 random_forest:{category:'Trees & Ensembles',summary:'Bagged trees; robust tabular baseline',cost:'Moderate'},
 extra_trees:{category:'Trees & Ensembles',summary:'Randomised tree ensemble',cost:'Moderate'},
 gradient_boosting:{category:'Trees & Ensembles',summary:'Sequential boosted trees',cost:'Moderate'},
 hist_gradient_boosting:{category:'Trees & Ensembles',summary:'Histogram-based boosted trees',cost:'Moderate'},
 knn:{category:'Distance & Margin',summary:'Nearest neighbours, scaled numeric features',cost:'Moderate'},
 svm:{category:'Distance & Margin',summary:'Kernel margin classifier; can be slow for large datasets',cost:'Heavy'},
 svr:{category:'Distance & Margin',summary:'Kernel-based numeric prediction; may be slow',cost:'Heavy'},
 naive_bayes:{category:'Probabilistic',summary:'Fast Gaussian probabilistic classifier',cost:'Light'}
};
function fmt(n:number|null|undefined){return typeof n==='number'?n.toLocaleString(undefined,{maximumFractionDigits:4}):'—'}
function fmtPrediction(value:string|number,task:string|undefined){return typeof value==='number'?value.toLocaleString(undefined,{minimumFractionDigits:task==='regression'?2:0,maximumFractionDigits:task==='regression'?2:4}):String(value)}
function cls(...x:(string|false|undefined)[]){return x.filter(Boolean).join(' ')}

/** Historical experiment settings must never be inferred from the current Prepare draft. */
function RecordedExperimentPreprocessing({experiment}:{experiment:Experiment}){
  const numeric=experiment.config.numeric_imputation;
  const categorical=experiment.config.categorical_imputation;
  const numericLabel=numeric==='mean'?'Mean':numeric==='median'?'Median':numeric===undefined?'Median (legacy default; not recorded)':'Unrecognised numeric strategy';
  const categoricalLabel=categorical==='constant'?'Reserved missing marker':categorical==='most_frequent'?'Mode (most frequent)':categorical===undefined?'Mode (legacy default; not recorded)':'Unrecognised categorical strategy';
  const version=experiment.config.quality_version;
  return <section className="panel" role="region" aria-label="Recorded experiment preprocessing">
    <div className="panel-title"><ClipboardCheck size={19}/><h2>Recorded experiment preprocessing</h2></div>
    <p className="body-muted">Saved experiment configuration for working data version {Number.isSafeInteger(version)&&version!==undefined&&version>=0?`v${version}`:'not recorded'}. This is not the current Prepare draft or independent proof of a fitted model.</p>
    <p><strong>Numeric missing values:</strong> {numericLabel} · <strong>Categorical missing values:</strong> {categoricalLabel}.</p>
    <p className="muted-caption">Legacy defaults are identified explicitly where the setting was not saved. Training success and model validity require their own evidence.</p>
  </section>;
}

/** A one-use, memory-only snapshot from two successful project/profile reads.
 * The shell may hand it to the next project-keyed primary Studio instance.
 * No snapshot is persisted, and failed/stale reads never create one.
 */
export type PrimaryProjectLoadSnapshot={id:string;project:Project;version:number};

/** A second analytical pane receives an explicit stage and cannot control the global route. */
export function App({embeddedStage,embeddedProjectId,onEmbeddedNavigate,onPrimaryNavigate,onBeforePrimaryProjectLoad,onBeforePrimaryProjectUpload,onPrimaryUploadedProjectCommitted,forceNewProject=false,onNewProjectClose,onPrimaryDraftEdited,onPrimaryDraftCleared,onPrimaryProjectLoaded,onPrimaryProjectLoadFailed,primaryProjectHandoff,onPrimaryProjectHandoffConsumed}:{
  embeddedStage?: Stage;
  embeddedProjectId?: string;
  onEmbeddedNavigate?:(view:Stage)=>void;
  // Primary Studio changes need shell approval before they can discard an edited dock.
  onPrimaryNavigate?:(view:Stage,afterNavigate?:()=>void)=>boolean;
  // Shell approval must precede any primary project state reset.
  onBeforePrimaryProjectLoad?:(projectId:string)=>boolean;
  // Consent must happen before upload creates a new local dataset project.
  onBeforePrimaryProjectUpload?:()=>boolean;
  // Complete an authorised upload switch only after its project fetch succeeds.
  onPrimaryUploadedProjectCommitted?:()=>void;
  // Report only a memory-only edit signal; never transmit field values.
  onPrimaryDraftEdited?:(view:Stage)=>void;
  onPrimaryDraftCleared?:(view:Stage)=>void;
  onPrimaryProjectLoaded?:(projectId:string,snapshot:PrimaryProjectLoadSnapshot)=>void;
  onPrimaryProjectLoadFailed?:(projectId:string)=>void;
  primaryProjectHandoff?:PrimaryProjectLoadSnapshot;
  onPrimaryProjectHandoffConsumed?:(projectId:string)=>void;
  forceNewProject?:boolean;
  onNewProjectClose?:()=>void;
}={}){
 const targetFieldId=useId();
 const embedded=embeddedStage!==undefined;
 // Never hydrate a stale cross-tab selection, and never use this in a dock.
 const initialVerifiedProject=!embedded&&primaryProjectHandoff?.id===(localStorage.getItem('pilotodin-current')||'')
   ?primaryProjectHandoff:null;
  const [project,setProject]=useState<Project|null>(()=>initialVerifiedProject?.project??null);
  const [projects,setProjects]=useState<{id:string;name:string;filename:string}[]>([]);
  const [page,setPage]=useState<Stage>(()=>embeddedStage??requestedStudioStage());
  const [file,setFile]=useState<File|null>(null);
  const [loading,setLoading]=useState(false);
  const [error,setError]=useState('');
  const [target,setTarget]=useState('');
  const [prep,setPrep]=useState<Prep|null>(null);
  const [excluded,setExcluded]=useState<string[]>([]);
  const [numericImputation,setNumericImputation]=useState<'median'|'mean'>('median');
  const [categoricalImputation,setCategoricalImputation]=useState<'most_frequent'|'constant'>('most_frequent');
  const [reviewHighRiskExclusions,setReviewHighRiskExclusions]=useState(false);
  const [models,setModels]=useState<string[]>(['logistic_regression','random_forest','extra_trees']);
  const [confirmSplit,setConfirmSplit]=useState(false);
  const [acknowledgeFeatureRisks,setAcknowledgeFeatureRisks]=useState(false);
  const [splitStrategy,setSplitStrategy]=useState<'random'|'group'|'time'>('random');
  const [splitColumn,setSplitColumn]=useState('');
  const [trainingLimitMinutes,setTrainingLimitMinutes]=useState(0);
  const [sidebarCollapsed,setSidebarCollapsed]=useState(false);
  const [experiment,setExperiment]=useState<Experiment|null>(null);
  const [predictVals,setPredictVals]=useState<Record<string,string>>({});
  // A resolved prediction must never be shown for inputs or a model that changed in flight.
  const predictionRequestRevision=useRef(0);
  const [prediction,setPrediction]=useState<{prediction:string|number;probabilities?:{class:string|number;probability:number}[];probability_estimates_calibrated?:boolean;warning:string;input_warnings?:string[]}|null>(null);
  const [uploadOpen,setUploadOpen]=useState(false);
  const showUpload=uploadOpen||(!embedded&&forceNewProject);
  const [busy,setBusy]=useState('');
  const [qualityVersion,setQualityVersion]=useState(initialVerifiedProject?.version??0);
  const [qualityFocus,setQualityFocus]=useState<QualityFocus|null>(null);
  const [deliverEvidenceId,setDeliverEvidenceId]=useState<string|null>(null);
  const [featureHintSnapshot,setFeatureHintSnapshot]=useState<ScopedFeatureHints|null>(null);
  // Never render or apply hints from a different project, target, or Quality version.
  const featureHints=visibleFeatureHints(featureHintSnapshot,project?.id,target,qualityVersion);
  const liveProjectId=useRef(project?.id??'');
  liveProjectId.current=project?.id??'';
  const uploadViewMounted=useRef(true);
  useEffect(()=>{uploadViewMounted.current=true;return()=>{uploadViewMounted.current=false}},[]);
  const latestProjectRequest=useRef(0);
  // A verified cross-root project handoff must accept local operations on mount.
  const projectOperations=useRef(createProjectOperationGuard(initialVerifiedProject?.id??''));
  // Late reads from a prior Quality version cannot roll the visible profile back.
  const liveProfileVersionGuard=useRef(createLiveProfileVersionGuard(
    initialVerifiedProject?.id??'',initialVerifiedProject?.version??0));
  useEffect(()=>{
    // Strict Mode replays mount effects. Restore the verified handoff's scope
    // after cleanup, since that path skips loadProject on mount.
    if(initialVerifiedProject)projectOperations.current.begin(initialVerifiedProject.id);
    return()=>projectOperations.current.invalidate();
  },[]);
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
  window.addEventListener('hashchange',sync);window.addEventListener('pilotodin:route-commit',sync);
  // replaceState on a rejected route emits no hashchange, so use the shell's
  // explicit rollback signal to align the displayed primary Studio page.
  window.addEventListener('pilotodin:route-reverted',sync);
  return()=>{window.removeEventListener('hashchange',sync);window.removeEventListener('pilotodin:route-commit',sync);window.removeEventListener('pilotodin:route-reverted',sync)}
 },[embeddedStage]);
  function requestNewDataset():void{
    // Stage importer state only after navigation approval. A native Windows
    // dialog completes asynchronously, so the post-navigation callback must
    // be carried through the shell rather than set eagerly on refusal.
    if(embedded)return;
    go('overview',()=>{setFile(null);setUploadOpen(true)});
  }
  function go(next:Stage,afterNavigate?:()=>void):boolean{
    // Keep Studio-local cleanup with the exact approved route. For a native
    // Windows dialog this callback is deferred, so cancel never hides a draft
    // or arms an importer and Leave closes the command palette correctly.
    const complete=()=>{
      if(next!=='quality')setQualityFocus(null);
      if(next!=='deliver')setDeliverEvidenceId(null);
      scrollRef.current[page]=mainRef.current?.scrollTop??0;
      setError('');setUploadOpen(false);setMobileOpen(false);setPaletteOpen(false);
      setPaletteQuery('');
      afterNavigate?.();
    };
    // Refuse destructive primary navigation BEFORE touching route or page state.
    // Embedded navigation continues to use its existing dock-only authority.
    if(!embedded&&next!==page&&onPrimaryNavigate&&!onPrimaryNavigate(next,complete))return false;
    if(embedded){
      // Embedded views cannot navigate the main window or escape the dock registry.
      if(!isSecondaryView(next)){
        setNotice('Open this workspace in the primary navigation instead.');
        setPaletteOpen(false);
        return false;
      }
      onEmbeddedNavigate?.(next);
      // Prop is authoritative: do not render an unapproved page while it updates.
    }else{
      if(location.hash!==`#/studio/${next}`)navigateHashSmoothly(`#/studio/${next}`,()=>setPage(next));
      else setPage(next);
    }
    complete();
    return true;
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
  useEffect(()=>{
    void refreshProjects();
    const pid=embeddedProjectId??localStorage.getItem('pilotodin-current');
    // Retire the handoff even when another tab has changed the shared choice.
    if(primaryProjectHandoff)onPrimaryProjectHandoffConsumed?.(primaryProjectHandoff.id);
    // The successful B pair was already read by the preceding Studio instance.
    // Never repeat it merely because the keyed component remounted.
    if(pid&&pid!==initialVerifiedProject?.id)void loadProject(pid);
  },[embeddedProjectId]);
  useEffect(()=>{
    if(embedded)return;
    const handler=()=>{
      const id=localStorage.getItem('pilotodin-current');
      if(id&&id!==project?.id)void loadProject(id);
    };
    const requestedByShell=(event:Event)=>{
      // The global same-tab selector has approved a provisional, read-only
      // attempt. Preserve shared A until its requested B profile succeeds.
      const id=(event as CustomEvent<{projectId?:string}>).detail?.projectId;
      if(typeof id==='string'&&id&&id!==project?.id)void loadProject(id);
    };
    window.addEventListener('pilotodin:project-changed',handler);
    window.addEventListener('pilotodin:primary-project-load-requested',requestedByShell);
    return()=>{
      window.removeEventListener('pilotodin:project-changed',handler);
      window.removeEventListener('pilotodin:primary-project-load-requested',requestedByShell);
    };
  },[project?.id,embedded]);
  useEffect(()=>{if(!embedded&&project?.id)window.dispatchEvent(new Event('pilotodin:project-changed'))},[project?.id,embedded]);
  // Name updates must not reload the Studio or discard in-memory Prepare inputs.
  useEffect(()=>{
   const metadata=(event:Event)=>{
    const d=(event as CustomEvent<{id?:string;name?:string;filename?:string;archived?:boolean}>).detail;
    if(!d||typeof d.id!=='string'||typeof d.name!=='string'||typeof d.filename!=='string')return;
     const id=d.id,name=d.name,filename=d.filename,archived=d.archived;
    setProject(old=>old?.id===id?{...old,name}:old);
    setProjects(old=>archived?old.filter(row=>row.id!==id):
     old.some(row=>row.id===id)?old.map(row=>row.id===id?{...row,name}:row):
     [...old,{id,name,filename}]);
   };
   window.addEventListener('pilotodin:project-metadata-changed',metadata);
   return()=>window.removeEventListener('pilotodin:project-metadata-changed',metadata);
  },[]);

  useEffect(()=>{if(!embedded&&!location.hash.startsWith('#/canvas')&&location.hash!==`#/studio/${page}`)location.hash=`#/studio/${page}`},[page,embedded]);
  async function loadProject(pid:string,approvedBeforeUpload=false):Promise<boolean>{
    // The global shell owns the project identity. Embedded panes cannot switch it.
    if(embedded && pid!==embeddedProjectId){
      setNotice('Change projects using the global project selector.');
      return false;
    }
    // Direct Studio project selector, Home cards and the final post-upload load
    // must not clear a mounted primary project or edited dock before approval.
    if(!embedded&&pid!==project?.id&&!approvedBeforeUpload&&onBeforePrimaryProjectLoad&&!onBeforePrimaryProjectLoad(pid))return false;
    // Snapshot shared selection before awaiting any network work. Another tab
    // can choose a different project while this read is in progress.
    const selectedWhenStarted=embedded?'':localStorage.getItem('pilotodin-current')||'';
    const request=++latestProjectRequest.current;
    // Do not invalidate the current project's in-flight work on a provisional read.
    // Fetch first: failed project reads must not discard the current unsaved work.
    try{const [p,q]=await Promise.all([get<Project>(`/projects/${pid}`),get<{version:number;profile?:Profile}>(`/projects/${pid}/live-profile`)]);if(request!==latestProjectRequest.current)return false;
    if(!embedded&&!mayCommitProjectSelection(
      selectedWhenStarted,localStorage.getItem('pilotodin-current')||'',pid)){
      setNotice('Another tab selected a different project while this one was loading. The older load was not applied.');
      onPrimaryProjectLoadFailed?.(pid);
      return false;
    }
    const verifiedProject:Project=q.profile?{...p,profile:q.profile}:p;
    // Invalidate old-project operations only after both GETs and selection checks passed.
    if(!Number.isSafeInteger(q.version)||q.version<0)throw new Error('Invalid working Quality version.');
    projectOperations.current.begin(pid);
    liveProfileVersionGuard.current.reset(pid,q.version);
    if(!embedded&&pid!==project?.id)
      onPrimaryProjectLoaded?.(pid,{id:pid,project:verifiedProject,version:q.version});
    if(approvedBeforeUpload)onPrimaryUploadedProjectCommitted?.();
    setProject(null);setPrep(null);setExperiment(null);setPrediction(null);setTarget('');setQualityFocus(null);setDeliverEvidenceId(null);
    setQualityVersion(q.version);setFeatureHintSnapshot(null);setProject(verifiedProject);if(!embedded)localStorage.setItem('pilotodin-current',pid);setTarget('');setPrep(null);setExcluded([]);setExperiment(null);setPrediction(null);setPredictVals({});setConfirmSplit(false);setPage(embeddedStage??requestedStudioStage());setVisitedStages([embeddedStage??requestedStudioStage()]);scrollRef.current={};setUploadOpen(false);setError('');return true;}catch(e){
      if(request!==latestProjectRequest.current)return false;
      setError(`Could not open project: ${(e as Error).message}`);
      if(!embedded)onPrimaryProjectLoadFailed?.(pid);
      // Never remove the user's selected project on a transient API failure.
      return false;
    }}
  useEffect(()=>{setNumericImputation('median');setCategoricalImputation('most_frequent');if(!project||!target){setPrep(null);return;}let active=true;
    setPrep(null); // A previous target/version's plan must not be reused while loading.
    get<Prep>(`/projects/${project.id}/preparation?target=${encodeURIComponent(target)}&expected_version=${qualityVersion}`).then(p=>{
      if(!active||p.quality_version!==qualityVersion||p.target!==target)return;
      setPrep(p);setExcluded(p.recommend_exclude.filter(c=>c.reason.includes('constant')||c.reason.includes('all values')).map(c=>c.column));
      setModels(p.task==='classification'?['logistic_regression','random_forest','extra_trees']:['linear_regression','random_forest','gradient_boosting']);
    }).catch(e=>{if(active){setPrep(null);setError(e.message)}});
    return()=>{active=false};
  },[project?.id,target,qualityVersion]);
  useEffect(()=>{
    if(!project||!target){setFeatureHintSnapshot(null);return;}
    const requested={projectId:project.id,target,version:qualityVersion};
    let live=true;
    get<{version:number;features:{column:string;risk:string;reasons:string[]}[]}>(`/projects/${requested.projectId}/features?target=${encodeURIComponent(requested.target)}&expected_version=${requested.version}`)
      .then(r=>{if(live)setFeatureHintSnapshot(r.version===requested.version?{...requested,features:r.features}:null);})
      .catch(()=>{if(live)setFeatureHintSnapshot(null);});
    return()=>{live=false};
  },[project?.id,target,qualityVersion]);
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
    if(!file)return;
    // The user may still be editing the current dock. Do not create the
    // new project or mutate the current import UI until they approve.
    if(onBeforePrimaryProjectUpload&&!onBeforePrimaryProjectUpload())return;
    const initialProjectId=project?.id??'';
    setLoading(true);setError('');try{
    const data=await upload(file);
    // Upload cannot be rolled back, but an unmounted old Studio must not adopt
    // its result and override a newly selected project.
    if(!uploadViewMounted.current)return;
    await refreshProjects();
    if(!uploadViewMounted.current)return;
    // This upload was authorised before its network request. If the mounted
    // primary project changed during the upload, do not reuse stale consent.
    const opened=await loadProject(data.id,liveProjectId.current===initialProjectId);
    if(!opened){
      // Upload already succeeded; clear its selected file so retry cannot upload
      // the same data again. Hide the import overlay without switching projects.
      setUploadOpen(false);setFile(null);onNewProjectClose?.();
      setNotice('Dataset was imported but was not opened. Select it later to switch projects.');
      return;
    }
    setUploadOpen(false);setFile(null);onNewProjectClose?.();setNotice("Dataset imported and profiled successfully");
  }catch(e){if(uploadViewMounted.current)setError((e as Error).message)}finally{if(uploadViewMounted.current)setLoading(false)}}
  // Button-only Model Lab edits do not emit input/change events. Report a
  // dirty primary Studio form only when the selected model set changes.
  function toggleModelChoice(key:string){
    const next=models.includes(key)?models.filter(name=>name!==key):
      models.length<5?[...models,key]:models;
    if(next===models)return; // Six-model cap; no edit and no warning.
    if(!embedded)onPrimaryDraftEdited?.('model');
    setModels(next);
  }
  // Preview exact changes before this button-only edit; preserve manual exclusions.
  function applyHighRiskExclusionSuggestions(){
    if(!prep||!reviewHighRiskExclusions)return;
    const proposed=[
      ...prep.high_risk_features,
      ...featureHints.filter(f=>f.risk==='high').map(f=>f.column)
        .filter(column=>prep.available_features.includes(column)),
    ];
    // Merge against current React state; never discard a queued checkbox edit.
    const additions=proposed.filter(column=>!excluded.includes(column));
    if(!additions.length){setReviewHighRiskExclusions(false);return;}
    if(!embedded)onPrimaryDraftEdited?.('prepare');
    setExcluded(current=>[...new Set([...current,...additions])]);
    setReviewHighRiskExclusions(false);
  }
  async function startTrain(){
    if(!project||!prep||prep.target!==target)return;
    if(modelBudgetExceeded){setError('Selected predictor estimate or model row limit exceeds the local training budget. Review exclusions and model selection.');return;}
    if(unresolvedFeatureRisks.length&&!acknowledgeFeatureRisks){setError('Review or exclude high-risk predictors before training.');return;}
    const projectId=project.id, generation=projectOperations.current.snapshot(projectId);
    setError('');setBusy('train');
    try{
      const d=await post<{id:string;status:string}>(`/projects/${projectId}/experiments`,{
        target,task:prep.task,excluded_features:excluded,models,
        acknowledge_random_split:splitStrategy==='random'?confirmSplit:false,
        split_strategy:splitStrategy,split_column:splitStrategy==='random'?null:splitColumn,
        expected_quality_version:qualityVersion,
        acknowledge_feature_risks:acknowledgeFeatureRisks,
        numeric_imputation:numericImputation,categorical_imputation:categoricalImputation,
        max_duration_seconds:trainingLimitMinutes?trainingLimitMinutes*60:null
      });
      if(!projectOperations.current.accepts(projectId,generation))return;
      setExperiment({id:d.id,project_id:projectId,status:d.status,config:{target,task:prep.task,excluded,models,quality_version:qualityVersion,split_strategy:splitStrategy,split_column:splitColumn,numeric_imputation:numericImputation,categorical_imputation:categoricalImputation,max_duration_seconds:trainingLimitMinutes?trainingLimitMinutes*60:null},results:null,error:null,selected_model:null,final_results:null});
      setProject(p=>p?.id===projectId?{...p,experiments:[{id:d.id,status:d.status,selected_model:null,created_at:new Date().toISOString()},...p.experiments]}:p);
      go('evaluate');setNotice('Experiment created. Training status will update automatically.');
    }catch(e){if(projectOperations.current.accepts(projectId,generation))setError((e as Error).message)}
    finally{if(projectOperations.current.accepts(projectId,generation))setBusy('')}
  }
  async function cancelTrain(){
    if(!project||!experiment||experiment.project_id!==project.id||!['queued','running'].includes(experiment.status))return;
    const projectId=project.id, generation=projectOperations.current.snapshot(projectId), eid=experiment.id;
    setBusy('cancel');setError('');
    try{
      const response=await post<{status:string;message:string}>(`/experiments/${eid}/cancel`,{});
      const latest=await get<Experiment>(`/experiments/${eid}`);
      if(!projectOperations.current.accepts(projectId,generation)||latest.project_id!==projectId)return;
      setExperiment(current=>current?.id===eid?latest:current);
      setProject(p=>p?.id===projectId?{...p,experiments:p.experiments.map(x=>x.id===eid?{...x,status:latest.status}:x)}:p);
      setNotice(response.message);
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
      setPredictVals({});setPrediction(null);go('evaluate');
      setNotice('Model selected. Review held-out evaluation results before proceeding to Predict Studio.');
    }catch(e){if(projectOperations.current.accepts(projectId,generation))setError((e as Error).message)}
    finally{if(projectOperations.current.accepts(projectId,generation))setBusy('')}
  }
  function updatePredictionInput(name:string,value:string){
    // Invalidate a pending request even if the user later restores the old value.
    // Editing must also release that stale request's loading lock, so a new
    // prediction can be submitted without waiting for the old network reply.
    predictionRequestRevision.current+=1;
    setPredictVals(current=>({...current,[name]:value}));
    setPrediction(null);
    setBusy(current=>current==='predict'?'':current);
    setError('');
  }
  async function runPrediction(){
    if(!experiment?.selected_model||!experiment.results||!project||experiment.project_id!==project.id)return;
    const projectId=project.id, generation=projectOperations.current.snapshot(projectId), experimentId=experiment.id;
    const requestRevision=++predictionRequestRevision.current;
    setError('');setBusy('predict');
    try{
      const values=Object.fromEntries((experiment.results?.input_schema??[]).map(f=>[f.name,predictVals[f.name]??'']));
      const result=await post<{prediction:string|number;probabilities?:{class:string|number;probability:number}[];probability_estimates_calibrated?:boolean;warning:string;input_warnings?:string[]}>(`/experiments/${experimentId}/predict`,{values});
      if(!projectOperations.current.accepts(projectId,generation)||predictionRequestRevision.current!==requestRevision)return;
      setPrediction(result);setNotice('Prediction computed using the selected model');
    }catch(e){if(projectOperations.current.accepts(projectId,generation)&&predictionRequestRevision.current===requestRevision)setError((e as Error).message)}
    // An older request cannot dismiss a newer request's loading indicator.
    finally{if(projectOperations.current.accepts(projectId,generation)&&predictionRequestRevision.current===requestRevision)
      setBusy(current=>current==='predict'?'':current)}
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
      // Reopen onto final evidence, not prediction inputs.
      go('evaluate');
    }catch(e){if(projectOperations.current.accepts(projectId,generation))setError((e as Error).message)}
  }
  useEffect(()=>{
    // A model or dataset-version transition invalidates a pending prediction
    // AND frees its UI loading state without changing another operation.
    predictionRequestRevision.current+=1;
    setPredictVals({});setPrediction(null);
    setBusy(current=>current==='predict'?'':current);
  },[project?.id,experiment?.id,experiment?.selected_model,qualityVersion]);
  useEffect(()=>{
   const onDataset=(event:Event)=>{
    if(!project||(event as CustomEvent<{projectId:string}>).detail?.projectId!==project.id)return;
    const currentProjectId=project.id;
    const generation=projectOperations.current.snapshot(currentProjectId);
    void get<{version:number;profile:Profile}>(`/projects/${currentProjectId}/live-profile`).then(next=>{
      if(!projectOperations.current.accepts(currentProjectId,generation)
        ||!liveProfileVersionGuard.current.accept(currentProjectId,next.version))return;
      setQualityVersion(next.version);
      setProject(old=>old?.id===currentProjectId?{...old,profile:next.profile}:old);
      setPrediction(null);
    }).catch(()=>{/* Keep the last verified state until a successful refresh. */});
   };
   window.addEventListener('pilotodin:dataset-changed',onDataset);
   return()=>window.removeEventListener('pilotodin:dataset-changed',onDataset);
  },[project?.id]);
  const profile=project?.profile;
  const unresolvedFeatureRisks=(prep?.high_risk_features??[]).filter(name=>!excluded.includes(name)&&!(splitStrategy!=='random'&&splitColumn===name));
  const selectedResourcePlan=prep?.resource_plan;
  // Current included fields, never the stale all-candidate plan. The backend
  // independently rechecks the final labelled-only data before any fit.
  const selectedBudget=prep?.resource_plan?selectedFeatureBudget(prep.feature_audit,prep.resource_plan,excluded,splitStrategy,splitColumn):null;
  const modelRowLimit=selectedResourcePlan?Math.min(selectedResourcePlan.row_limit,...models.map(key=>selectedResourcePlan.model_family_row_limits[key]??selectedResourcePlan.row_limit)):null;
  const rowBudgetExceeded=!!selectedResourcePlan&&modelRowLimit!==null&&selectedResourcePlan.labelled_rows>modelRowLimit;
  const modelBudgetExceeded=rowBudgetExceeded||!!selectedBudget?.denseLimitExceeded;
  useEffect(()=>{setAcknowledgeFeatureRisks(false)},[project?.id,target,qualityVersion,excluded,splitStrategy,splitColumn]);
  const prepRisk=prep?.recommend_exclude??[];
  // No mutation until the user confirms a proposed high-risk exclusion diff.
  const highRiskExclusionCandidates=prep?[...new Set([
    ...prep.high_risk_features,
    ...featureHints.filter(f=>f.risk==='high').map(f=>f.column)
  ])].filter(column=>prep.available_features.includes(column)):[];
  const pendingHighRiskExclusions=highRiskExclusionCandidates.filter(column=>!excluded.includes(column));
  const includedNow=(prep?.feature_audit??[]).filter(f=>f.default_included&&!excluded.includes(f.column)&&!(splitStrategy!=='random'&&splitColumn===f.column)).length;
  const includedAfterReview=(prep?.feature_audit??[]).filter(f=>f.default_included&&!excluded.includes(f.column)&&!pendingHighRiskExclusions.includes(f.column)&&!(splitStrategy!=='random'&&splitColumn===f.column)).length;
  useEffect(()=>{setReviewHighRiskExclusions(false)},[project?.id,target,qualityVersion]);
  const available=prep?.task==='regression'?R_MODELS:C_MODELS;
  const ordered=useMemo(()=>[...((experiment?.results?.models??[]).filter(x=>x.status==='ready'))].sort((a,b)=> experiment?.results?.task==='regression'?(a.cv_metric??0)-(b.cv_metric??0):(b.cv_metric??0)-(a.cv_metric??0)),[experiment?.results]);
  const hasProject=!!project;
  const stale=!!experiment&&(experiment.is_stale||((experiment.config.quality_version??0)!==qualityVersion));
  async function qualityChanged(){
    if(!project)return;
    const projectId=project.id, generation=projectOperations.current.snapshot(projectId);
    try{
      const v=await get<{version:number;profile:Profile}>(`/projects/${projectId}/live-profile`);
      if(!projectOperations.current.accepts(projectId,generation)
        ||!liveProfileVersionGuard.current.accept(projectId,v.version))return;
      setQualityVersion(v.version);
      setProject(old=>old?.id===projectId?{...old,profile:v.profile}:old);
      if(experiment?.project_id===projectId){
        const updated=await get<Experiment>(`/experiments/${experiment.id}`);
        if(!projectOperations.current.accepts(projectId,generation)
          ||!liveProfileVersionGuard.current.isCurrent(projectId,v.version))return;
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
        <button className="new-project" disabled={embedded} onClick={requestNewDataset}><Plus size={16}/> New dataset</button>
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
      <div className="content po-motion-stage" id="workspace-content" key={`${project?.id??'none'}-${page}`} onChangeCapture={event=>{
        // Project chooser is outside this stage: it must never mark a draft.
        if(embedded||!project||!['prepare','model','predict'].includes(page))return;
        const tag=(event.target as HTMLElement).tagName;
        if(tag==='INPUT'||tag==='TEXTAREA'||tag==='SELECT')onPrimaryDraftEdited?.(page);
      }}>
        {busy&&<div className="operation-status" role="status" aria-live="polite"><LoaderCircle size={16} className="spin"/><span>{busy==='train'?'Submitting training experiment…':busy==='select'?'Selecting and validating model…':busy==='predict'?'Computing prediction…':'Working…'}</span></div>}
        {error&&<div className="alert-error"><AlertCircle size={18}/><span>{error}</span><button onClick={()=>setError('')}>Dismiss</button></div>}
        {((!project&&page!=='ai_settings')||showUpload)&&<section className="landing">{project&&<button className="studio-cancel-upload" onClick={()=>{setUploadOpen(false);setFile(null);onNewProjectClose?.()}} aria-label="Cancel new dataset">Cancel upload <X size={16}/></button>}<div className="hero-flag"><Sparkles size={16}/> INTELLIGENT DATA SCIENCE</div><h1>Turn raw data into<br/><em>predictive intelligence.</em></h1><p>Upload a dataset, explore its structure, compare machine learning models and build a working prediction tool. All on your own machine.</p>
          <div className="upload-card"><div className="upload-visual"><UploadCloud size={30}/></div><h3>Start with your dataset</h3><p>CSV or Excel • Up to 40 MB • First worksheet used</p><label className="file-choose"><input type="file" accept=".csv,.xlsx" onChange={(e:any)=>setFile(e.target.files?.[0]??null)}/>{file?file.name:'Choose a file'}</label><button className="btn primary" disabled={!file||loading} onClick={()=>void startUpload()}>{loading?<LoaderCircle className="spin" size={16}/>:<ArrowRight size={16}/>} {loading?'Analysing dataset…':'Analyse dataset'}</button></div>
          <div className="landing-notes"><span><ShieldCheck size={16}/> Files stay on your machine</span><span><Database size={16}/> Real Python ML pipelines</span><span><LockKeyhole size={16}/> Cloud AI requires explicit opt-in</span></div>
        </section>}
        {page==='ai_settings'&&!showUpload&&<AISettings/>}
        {project&&!showUpload&&page!=='ai_settings'&&<>
          {page!=='overview'&&<div className="heading"><div><div className="eyebrow">PROJECT / {project.name.toUpperCase()}</div><h1>{NAV.find(x=>x.id===page)?.name}</h1><p>{page==='understand'?'Explore the shape, quality and meaning of your uploaded data.':page==='quality'?'Review issues, make safe corrections and restore versions.':page==='explore'?'Investigate distributions, variables and relationships.':page==='assistant'?'Ask questions about verified facts in your dataset.':page==='prepare'?'Review what the model should learn and which features it may use.':page==='model'?'Choose algorithms and run an evidence-based comparison.':page==='evaluate'?'Understand model performance before selecting a prediction pipeline.':page==='deliver'?'Create evidence-backed reports, review saved revisions and export professional PDF or HTML documents.':'Apply your selected model to new observations.'}</p></div><div className="head-label"><FileSpreadsheet size={16}/>{project.filename}</div></div>}
          
          {page==='deliver'&&<ReportWorkspace key={project.id} projectId={project.id} preselectEvidenceId={deliverEvidenceId} onUnsavedChange={dirty=>{if(embedded)return;if(dirty)onPrimaryDraftEdited?.('deliver');else onPrimaryDraftCleared?.('deliver')}}/>}
          {page==='overview'&&<StudioHome project={project} projects={projects} onGo={go} onNew={()=>setUploadOpen(true)} onOpenProject={id=>void loadProject(id)} onResume={reopenExperiment} onAI={()=>setOdinOpen(true)}/>}
          {page==='quality'&&<section className="persisted-workspace"><QualityWorkspace key={project.id} projectId={project.id} initialFocus={qualityFocus} onChanged={()=>{setQualityFocus(null);void qualityChanged()}}/></section>}
          {page==='explore'&&<section className="persisted-workspace"><ExploreWorkspace key={project.id} projectId={project.id} versionToken={qualityVersion} onReviewQuality={focus=>{if(focus.projectId===project.id&&focus.version===qualityVersion){setQualityFocus(focus);go('quality')}}} onSendToDeliver={snapshotId=>{if(/^[a-f0-9]{32}$/.test(snapshotId)&&go('deliver'))setDeliverEvidenceId(snapshotId)}}/></section>}
          {page==='assistant'&&<section className="persisted-workspace"><AssistantWorkspace key={project.id} projectId={project.id} onSettings={()=>go('ai_settings')}/></section>}
          {page==='understand'&&profile&&<><div className="metrics"><Metric label="DATASET RECORDS" value={fmt(profile.rows)} icon={<Database size={18}/>}/><Metric label="TOTAL COLUMNS" value={fmt(profile.columns_count)} icon={<Layers size={18}/>}/><Metric label="MISSING CELLS" value={fmt(profile.missing_cells)} icon={<CircleHelp size={18}/>}/><Metric label="EXACT DUPLICATES" value={fmt(profile.duplicate_rows)} icon={<Activity size={18}/>}/></div>
            <div className="panel insight"><div className="panel-title"><Sparkles size={19}/><h2>Dataset interpretation</h2><span className="pill muted">RULE-BASED ANALYSIS</span></div><p>{profile.summary}</p><p className="muted-caption">Local dataset statistics are calculated in Python. ODIN Intelligence above provides optional cloud-assisted interpretation from approved summaries.</p></div>
            <ColumnInvestigation key={project.id} projectId={project.id} versionToken={qualityVersion}
             onUnsavedChange={dirty=>{
              if(embedded)return;
              if(dirty)onPrimaryDraftEdited?.('understand');
              else onPrimaryDraftCleared?.('understand');
             }}/>
             <div className="panel"><div className="panel-title"><FileSpreadsheet size={18}/><h2>Data preview</h2></div><div className="table-scroll"><table><thead><tr>{profile.columns.slice(0,10).map(c=><th key={c.name}>{c.name}</th>)}</tr></thead><tbody>{profile.preview.map((row,i)=><tr key={i}>{profile.columns.slice(0,10).map(c=><td key={c.name}>{row[c.name]===null?'—':String(row[c.name]??'—').slice(0,55)}</td>)}</tr>)}</tbody></table></div><p className="muted-caption">Showing up to 7 rows and 10 columns.</p></div>
            {profile.warnings.length>0&&<div className="panel"><div className="panel-title"><AlertCircle size={18}/><h2>Review before modelling</h2></div>{profile.warnings.slice(0,7).map((s,i)=><div key={i} className="warning-line"><AlertCircle size={15}/>{s}</div>)}</div>}
            <div className="panel action-panel"><div><h3>Ready to define your objective?</h3><p>Choose the column you want to predict and review the preparation plan.</p></div><button className="btn primary" onClick={()=>go('prepare')}>Prepare data <ArrowRight size={17}/></button></div>
          </>}
          {page==='prepare'&&profile&&<><div className="panel"><div className="panel-title"><Target size={19}/><h2>Define your prediction target</h2></div><p className="body-muted">Which column contains the outcome you want to predict? Suggestions are based on names only and require your confirmation.</p><label className="field-label" htmlFor={targetFieldId}>TARGET VARIABLE</label><select id={targetFieldId} className="input full" value={target} onChange={(e:any)=>{if(!embedded&&e.target.value!==target)onPrimaryDraftEdited?.('prepare');setTarget(e.target.value);setPrep(null);setExperiment(null);setConfirmSplit(false);setError('')}}><option value="">Select a target column…</option>{profile.columns.map(c=><option value={c.name} key={c.name}>{c.name}</option>)}</select>{profile.target_candidates.length>0&&<p className="muted-caption">The imported-file name hints above are unverified. See the screened opportunities below for label support and structural warnings.</p>}</div>
            <TargetOpportunities key={project.id+'-'+qualityVersion} projectId={project.id} version={qualityVersion} selectedTarget={target} onChooseTarget={column=>{if(!profile.columns.some(c=>c.name===column))return;if(!embedded)onPrimaryDraftEdited?.('prepare');setTarget(column);setPrep(null);setExperiment(null);setConfirmSplit(false);setError('')}} onClearTarget={()=>{if(!target)return;if(!embedded)onPrimaryDraftEdited?.('prepare');setTarget('');setPrep(null);setExperiment(null);setConfirmSplit(false);setError('')}}/>
            {prep&&<>{!embedded&&<CategoryQualityAdvice projectId={project.id} version={qualityVersion} columns={prep.feature_audit.filter(f=>f.kind==='categorical'&&f.default_included&&!excluded.includes(f.column)).map(f=>f.column)} location="prepare" onReview={(focus:QualityFocus)=>{if(focus.projectId===project.id&&focus.version===qualityVersion){setQualityFocus(focus);go('quality')}}}/>}<div className="metrics three"><Metric label="TASK IDENTIFIED" value={prep.task==='classification'?'Classification':'Regression'} icon={<Target size={18}/>} small/><Metric label="INCLUDED PREDICTORS" value={String(prep.feature_audit.filter(f=>f.default_included&&!excluded.includes(f.column)&&!(splitStrategy!=='random'&&splitColumn===f.column)).length)} icon={<Database size={18}/>}/><Metric label="MISSING TARGETS" value={String(prep.missing_targets)} icon={<Activity size={18}/>}/></div>
              <div className="panel"><div className="panel-title"><ClipboardCheck size={19}/><h2>Review feature exclusions</h2></div><p className="body-muted">The model will use all columns except the target and features you deliberately exclude. Suggested exclusions are not automatically enforced.</p>
                <button className="btn small" type="button" aria-expanded={reviewHighRiskExclusions} disabled={!highRiskExclusionCandidates.length} onClick={()=>setReviewHighRiskExclusions(open=>!open)}><Sparkles size={14}/> Review high-risk exclusion suggestions</button>
                {reviewHighRiskExclusions&&<div className="mini-info po-ml-exclusion-review" role="group" aria-label="Review proposed high-risk exclusions" style={{display:'block',minWidth:0,overflowWrap:'anywhere'}}>
                  <strong>Review exclusions before applying</strong>
                  <p className="muted-caption">Will additionally exclude ({pendingHighRiskExclusions.length}): {pendingHighRiskExclusions.length?pendingHighRiskExclusions.join(', '):'None. All suggested fields are already excluded.'}</p>
                  <p className="muted-caption">Already excluded, kept unchanged ({excluded.length}): {excluded.length?excluded.join(', '):'None'}</p>
                  <p className="muted-caption">Included predictors: {includedNow} before, {includedAfterReview} after. These are structural counts, not validated importance.</p>
                  <p className="muted-caption">Nothing changes until you explicitly apply. You can cancel or edit checkboxes manually.</p>
                  <button className="btn small" type="button" disabled={!pendingHighRiskExclusions.length} onClick={applyHighRiskExclusionSuggestions}>Apply reviewed exclusions</button>
                  <button className="btn small" type="button" onClick={()=>setReviewHighRiskExclusions(false)}>Cancel exclusion review</button>
                </div>}
                <p className="muted-caption">Only structural screening, not validated importance: verify timing and compare features with training-only cross-validation.</p>
                {featureHints.filter(f=>f.risk!=='low').map(f=><div className="warning-line" key={f.column}><AlertCircle size={14}/><b>{f.column}</b>: {f.reasons.join('; ')}</div>)}
                <div className="feature-grid">{prep.available_features.map(c=>{const hint=prepRisk.find(x=>x.column===c);const isOut=excluded.includes(c);return <label className={cls('feature-chip',isOut&&'excluded')} key={c}><input type="checkbox" checked={isOut} onChange={(e:any)=>setExcluded(a=>e.target.checked?[...a,c]:a.filter(x=>x!==c))}/><span>{c}</span>{hint&&<span title={hint.reason}><AlertCircle size={15}/></span>}</label>})}</div>
                <p className="muted-caption">Checked features will be excluded. Columns with warning icons need contextual review.</p>
                 <div className="mini-info">{prep.available_features.length} candidate predictors · {prep.feature_audit.filter(f=>f.default_included&&!excluded.includes(f.column)&&!(splitStrategy!=='random'&&splitColumn===f.column)).length} currently included · {unresolvedFeatureRisks.length} included high-risk predictors. Split columns and all-empty fields are excluded by the backend.</div>
                 {selectedBudget&&prep.resource_plan&&<div className={cls('po-ml-resource-plan',selectedBudget.denseLimitExceeded&&'po-ml-resource-warning')}>
                   <strong><Database size={17}/> Local training resource preflight: selected predictors</strong>
                   <div className="po-ml-resource-metrics"><span><b>{prep.resource_plan.labelled_rows.toLocaleString()}</b> labelled rows</span><span><b>{selectedBudget.estimatedEncodedColumns.toLocaleString()}</b> estimated encoded columns</span><span><b>{selectedBudget.estimatedDenseTrainingMb.toLocaleString()} MB</b> approximate dense matrix</span></div>
                   <p>{selectedBudget.denseLimitExceeded?'The currently included predictors exceed this preliminary memory budget, or no usable predictors remain. Review exclusions before training.':'The current included predictors fit this preliminary dense-matrix estimate.'} Training rejects datasets exceeding {prep.resource_plan.row_limit.toLocaleString()} labelled rows or {prep.resource_plan.estimated_dense_mb_limit} MB estimated dense features.</p>
                   <small>Selected-feature estimate reflects your exclusions and split key. It is not measured RAM or model approval. The backend recalculates on labelled rows and may reject the request. {prep.resource_plan.note}</small>
                 </div>}
                 <h3 className="po-feature-audit-title">Feature-by-feature preparation audit</h3>
                 <div className="table-scroll po-ml-feature-audit"><table><thead><tr><th>FIELD / ROLE</th><th>OBSERVATIONS</th><th>PREPROCESSING</th><th>RISK REVIEW</th></tr></thead><tbody>
                   {prep.feature_audit.map(f=>{
                    const excludedByChoice=excluded.includes(f.column),isSplit=splitStrategy!=='random'&&splitColumn===f.column;
                    const examples=f.category_examples??[];
                    return <tr key={f.column}>
                     <td><strong>{f.column}</strong><small>{excludedByChoice?'Excluded by user':isSplit?'Excluded as split key':!f.default_included?'Unusable / excluded':'Included predictor'}</small></td>
                     <td>{f.kind} · {f.missing} missing ({f.missing_pct}%) · {f.distinct} distinct
                      {f.kind==='categorical'&&f.distinct>0&&f.risk==='high'&&<small className="po-ml-category-examples">Examples hidden for high-risk fields</small>}
                      {f.kind==='categorical'&&f.risk!=='high'&&examples.length>0&&
                       <small className="po-ml-category-examples">Observed examples ({examples.length} of {f.distinct}) {examples.map(value=>JSON.stringify(value)).join(', ')}</small>}
                     </td>
                     <td>{excludedByChoice||isSplit||!f.default_included?'No training transform':f.kind==='numeric'?`Numeric: ${numericImputation} imputation fitted on training folds`:categoricalImputation==='constant'?`Categorical: missing-marker imputation + capped one-hot encoding fitted on training folds`:f.treatment}</td>
                     <td>{f.risk==='high'?<strong className="po-ml-risk-high">High — review required</strong>:f.risk==='review'?'Review suggested':'No structural warning'}{f.reasons.length>0&&<small>{f.reasons.join('; ')}</small>}</td>
                    </tr>
                   })}
                 </tbody></table></div>
              </div>
              <div className="panel insight"><div className="panel-title"><WandSparkles size={19}/><h2>Automatic preprocessing plan</h2></div>
                <label className="field-label" htmlFor="numeric-imputation-strategy">Numeric missing-value treatment</label>
                <select id="numeric-imputation-strategy" className="input" aria-label="Numeric imputation method" value={numericImputation} onChange={event=>{if(!embedded)onPrimaryDraftEdited?.('prepare');setNumericImputation(event.target.value as 'median'|'mean')}}>
                  <option value="median">Median (default, resistant to outliers)</option>
                  <option value="mean">Mean (sensitive to outliers)</option>
                </select>
                <p className="muted-caption">Applies to all included numeric predictors. This setting is persisted with the experiment and fitted separately inside training folds, not applied to your original dataset.</p>
                <label className="field-label" htmlFor="categorical-imputation-strategy">Categorical missing-value treatment</label>
                <select id="categorical-imputation-strategy" className="input" aria-label="Categorical imputation method" value={categoricalImputation} onChange={event=>{if(!embedded)onPrimaryDraftEdited?.('prepare');setCategoricalImputation(event.target.value as 'most_frequent'|'constant')}}>
                  <option value="most_frequent">Mode (default; most frequent observed value)</option>
                  <option value="constant">Missing marker (keep missingness visible)</option>
                </select>
                <p className="muted-caption">Applies to included categorical predictors with a reserved marker for missing values. Existing values matching that marker are rejected before training. The capped one-hot encoder may group an infrequent marker with other rare categories. No original data changes.</p>
                {prep.transformations.map((p,i)=><div className="checkline" key={i}><CheckCircle2 size={17}/>{p.startsWith('Numeric:')?`Numeric: training-fold ${numericImputation} imputation; all-missing columns omitted`:p.startsWith('Categorical:')?`Categorical: training-fold ${categoricalImputation==='constant'?'missing-marker':'mode'} imputation and capped one-hot encoding`:p}</div>)}
                <p className="muted-caption">Preprocessing is learned independently within cross-validation folds to avoid test leakage.</p></div>
              <div className="panel action-panel"><div><h3>Preparation configuration ready</h3><p>Your source file is preserved; this configuration determines the modelling inputs.</p></div><button className="btn primary" onClick={()=>go('model')}>Open Model Lab <ArrowRight size={17}/></button></div>
            </>}
          </>}
          {page==='model'&&!prep&&<MissingRequirement icon={<FlaskConical size={30}/>} title="Choose a prediction target first" body="Model Lab needs a confirmed target and preprocessing plan. You can return here at any time." action="Review preparation" onAction={()=>go('prepare')}/>}
          {page==='model'&&prep&&<><div className="panel"><div className="panel-title"><FlaskConical size={19}/><h2>Choose up to five models</h2><span className="pill">{models.length} / 5 selected</span></div><p className="body-muted">PilotODIN will compare models using cross-validation on the development split. Higher macro F1 is better for classification; lower MAE is better for regression.</p><div className="mini-info"><Sparkles size={16}/> Suggested comparison: {prep.task==='regression'?'Linear Regression as a transparent baseline alongside Random Forest / Gradient Boosting':'Logistic Regression as an interpretable baseline alongside Random Forest / Extra Trees'}. The winner is decided by cross-validation, not the suggestion.</div>
            {models.length>0&&prep.resource_plan&&<div className={cls('mini-info',modelBudgetExceeded&&'warn-icon')} role="status"><Database size={16}/> Selected-model budget: at most {modelRowLimit?.toLocaleString()} labelled rows for this comparison. {models.some(m=>m==='svm'||m==='svr')?'Kernel SVM/SVR training has a stricter row limit.':models.includes('knn')?'K-nearest neighbours training has a stricter row limit.':'General resource limit applies.'} {modelBudgetExceeded?(rowBudgetExceeded?'This dataset exceeds the selected algorithm row limit. Remove the expensive model or use a reviewed smaller dataset.':'The selected predictor set exceeds the preliminary dense-memory limit or has no usable features. Review exclusions before training.'):'The selected row and predictor estimates are within budget; the server performs a final admission check.'}</div>}
            <div className="model-family-list">{MODEL_CATEGORIES.map(category=>{const options=available.filter(([key])=>MODEL_INFO[key]?.category===category);if(!options.length)return null;return <section className="model-family" key={category}><div className="model-family-heading"><strong>{category}</strong><small>{options.length} supported algorithms</small></div><div className="model-grid">{options.map(([key,label])=><button key={key} type="button" aria-pressed={models.includes(key)} className={cls('model-choice',models.includes(key)&&'chosen')} onClick={()=>toggleModelChoice(key)}><div className="model-icon">{models.includes(key)?<Check size={18}/>:<FlaskConical size={18}/>}</div><span className="model-choice-copy"><strong>{label}</strong><small>{MODEL_INFO[key]?.summary}</small><small className="model-cost">Resource level: {MODEL_INFO[key]?.cost}</small></span></button>)}</div></section>})}</div></div>
            <div className="panel"><div className="panel-title"><ShieldCheck size={19}/><h2>Validation safeguards</h2></div><div className="validation-row"><span>Hold-out test set</span><strong>20% (untouched until model selection)</strong></div><div className="validation-row"><span>Development split</span><strong>80% (5-fold CV when possible)</strong></div><div className="validation-row"><span>Primary metric</span><strong>{prep.task==='classification'?'Macro F1':'Mean Absolute Error'}</strong></div>
              <label className="field-label">VALIDATION STRATEGY</label>
              <select className="input" value={splitStrategy} onChange={e=>{setSplitStrategy(e.target.value as 'random'|'time'|'group');setConfirmSplit(false);setSplitColumn('')}}><option value="random">Random: independent observations</option><option value="time">Time: train on earlier records, test on later records</option><option value="group">Group: keep repeated entities in separate folds</option></select>
              {splitStrategy!=='random'&&<><label className="field-label">{splitStrategy==='time'?'DATE / TIME COLUMN':'GROUP / ENTITY COLUMN'}</label><select className="input" value={splitColumn} onChange={e=>setSplitColumn(e.target.value)}><option value="">Choose column…</option>{(profile?.columns??[]).filter(c=>c.name!==target).map(c=><option key={c.name} value={c.name}>{c.name}</option>)}</select><p className="muted-caption">The split column is excluded from predictors to reduce leakage.</p></>}
              {splitStrategy==='random'&&<label className="acknowledge"><input type="checkbox" checked={confirmSplit} onChange={(e:any)=>setConfirmSplit(e.target.checked)}/><span>I confirm that a random split is appropriate. Records are not time-ordered or repeated measurements of the same entity requiring grouped validation.</span></label>}
              <div className="mini-info warn-icon"><AlertCircle size={17}/> Choose the split strategy that matches your data. Random splitting can leak information when records are ordered or repeated; group and time strategies are available above. Identical timestamps at a train/test boundary are rejected rather than split between sets.</div>
               {unresolvedFeatureRisks.length>0&&<div className="po-ml-feature-risk-gate" role="group" aria-label="High-risk predictor review">
                 <strong><ShieldCheck size={17}/> Review required: {unresolvedFeatureRisks.length} included high-risk predictors</strong>
                 <p>{unresolvedFeatureRisks.join(', ')}. These may identify individual records or contain information unavailable at prediction time. Excluding them is usually safer; including them does not establish predictive validity.</p>
                 <label className="acknowledge"><input type="checkbox" checked={acknowledgeFeatureRisks} onChange={e=>setAcknowledgeFeatureRisks(e.target.checked)}/><span>I have reviewed these columns, their availability at prediction time, and the possibility of leakage. I deliberately accept their inclusion in this experiment.</span></label>
               </div>}
            </div><div className="panel action-panel"><div><h3>Start your experiment</h3><p>{models.length} algorithms selected. Model training runs locally in Python.</p><label className="field-label" htmlFor="training-soft-timeout">Optional training time limit</label><select id="training-soft-timeout" className="input" value={trainingLimitMinutes} onChange={e=>setTrainingLimitMinutes(Number(e.target.value))}><option value={0}>No time limit</option><option value={10}>10 minutes</option><option value={30}>30 minutes</option><option value={60}>60 minutes</option></select><p className="muted-caption">Soft limit: a model fit already underway finishes before PilotODIN can stop at a checkpoint.</p></div><button className="btn primary" disabled={!models.length||modelBudgetExceeded||(splitStrategy==='random'?!confirmSplit:!splitColumn)||(unresolvedFeatureRisks.length>0&&!acknowledgeFeatureRisks)||busy==='train'} onClick={()=>void startTrain()}>{busy==='train'?<LoaderCircle size={16} className="spin"/>:<Play size={17}/>} Train models</button></div>
          </>}
          {page==='evaluate'&&<>{!experiment?<div className="empty-panel"><FlaskConical size={30}/><h3>No experiment selected</h3><button className="btn primary" onClick={()=>go('model')}>Open Model Lab</button>{project.experiments.map(x=><button className="mini-experiment" key={x.id} onClick={()=>void reopenExperiment(x.id)}>{x.created_at.slice(0,16)} · {x.status} <ArrowRight size={14}/></button>)}</div>:
            <><RecordedExperimentPreprocessing experiment={experiment}/>{['queued','running'].includes(experiment.status)?<div className="empty-panel" role="status" aria-live="polite"><LoaderCircle size={35} className="spin"/><h3>{experiment.progress?.label??(experiment.status==='queued'?'Waiting to start':'Training in progress')}</h3><p>{experiment.progress?.detail??'Waiting for the next verified training milestone.'}</p>{experiment.progress?.history_available&&<p className="muted-caption">Recorded stages: {experiment.progress.history.map(item=>item.label).join(' · ')}</p>}<p className="muted-caption">Stages are observed checkpoints, not estimated percentages.</p>{experiment.control?.cancel_requested?<p className="warning-line" role="status">Cancellation requested; the current fitting operation may still be running. PilotODIN will confirm cancellation at its next safe checkpoint.</p>:<button className="btn" type="button" disabled={busy==='cancel'} onClick={()=>void cancelTrain()}>{busy==='cancel'?'Requesting…':experiment.status==='queued'?'Cancel queued training':'Request safe cancellation'}</button>}<div className="pulse-bar"/></div>:
            ['failed','cancelled','timed_out'].includes(experiment.status)?<div className="empty-panel"><AlertCircle size={35}/><h3>{experiment.status==='cancelled'?'Training cancelled':experiment.status==='timed_out'?'Training time limit reached':'Training failed'}</h3><p>{experiment.error}</p>{experiment.progress?.history_available&&<p className="muted-caption">Last recorded event: {experiment.progress.detail}</p>}<button className="btn" onClick={()=>go('model')}>Review configuration</button></div>:experiment.results&&<><div className="metrics three"><Metric label="TRAINING ROWS" value={fmt(experiment.results.train_rows)} icon={<Database size={18}/>}/><Metric label="FINAL TEST ROWS" value={fmt(experiment.results.test_rows)} icon={<ShieldCheck size={18}/>}/><Metric label="CROSS-VALIDATION" value={`${experiment.results.folds} folds`} icon={<RefreshCw size={18}/>}/></div>
              <div className="panel"><div className="panel-title"><BarChart3 size={19}/><h2>Cross-validation leaderboard</h2><span className="pill">{experiment.results.primary_metric}</span></div><p className="body-muted">This ranking is based only on development-set cross-validation. The final test set has not been used to choose a winner.</p><div className="table-scroll"><table><thead><tr><th>MODEL</th><th>CV SCORE</th><th>STD DEV.</th><th>ACTION</th></tr></thead><tbody>{ordered.map((m,i)=><tr key={m.key}><td className="cell-strong">{i===0&&<span className="winner">★</span>}{m.name}</td><td>{experiment.results!.task==='classification'?`${((m.cv_metric??0)*100).toFixed(1)}%`:fmt(m.cv_metric)}</td><td>{fmt(m.cv_std)}</td><td>{experiment.selected_model===m.key?<span className="okay">Selected</span>:!experiment.selected_model?<button className="btn small" disabled={busy==='select'} onClick={()=>void chooseModel(m.key)}>Select model <ArrowRight size={14}/></button>:<span className="body-muted">Not selected</span>}</td></tr>)}</tbody></table></div><ModelComparison results={experiment.results}/>{experiment.results.models.filter(m=>m.status==='failed').map(m=><div className="warning-line" key={m.key}><AlertCircle size={15}/>{m.name}: {m.error}</div>)}<div className={cls("mini-info",experiment.results.beats_baseline===false&&"warn-icon")}><Activity size={16}/> Baseline CV score: {experiment.results.task==='classification'?`${(experiment.results.baseline_cv*100).toFixed(1)}% macro F1`:fmt(experiment.results.baseline_cv)}. {experiment.results.beats_baseline===false?"No trained model beat the baseline. Do not assume the highest-ranked model is useful.":"Higher-ranked models are not automatically trustworthy. Inspect held-out results."}</div></div>
              {experiment.final_results&&<EvaluationDetails experiment={experiment}/>}
              {experiment.selected_model&&<button className="btn primary" onClick={()=>go('predict')}>Open Predict Studio <ArrowRight size={16}/></button>}
            </>}
            </>}
          </>}
          {stale&&['model','evaluate','predict'].includes(page)&&<div className="alert-error"><AlertCircle size={16}/> This experiment was trained on a previous data version. Metrics are historical; train a new experiment on Version {qualityVersion} before new predictions.</div>}
          {page==='predict'&&(!experiment?.selected_model||!experiment.results)&&<MissingRequirement icon={<Target size={30}/>} title="No prediction model selected" body="Choose an experiment, review its evaluation, and select a trained model before predicting." action="View experiments" onAction={()=>go('evaluate')}/>}
          {page==='predict'&&experiment?.selected_model&&experiment.results&&!stale&&!embedded&&<CategoryQualityAdvice projectId={project.id} version={qualityVersion} columns={experiment.results.input_schema.filter((f:Field)=>f.kind==='select'&&hasWhitespaceCategoryCollision(f.options??[])).map((f:Field)=>f.name)} location="predict" onReview={(focus:QualityFocus)=>{if(focus.projectId===project.id&&focus.version===qualityVersion){setQualityFocus(focus);go('quality')}}}/>}
          {page==='predict'&&experiment?.selected_model&&experiment.results&&!stale&&<RecordedExperimentPreprocessing experiment={experiment}/>}
           {page==='predict'&&experiment?.selected_model&&experiment.results&&!stale&&<div className="pred-grid"><div className="panel"><div className="panel-title"><Target size={19}/><h2>New prediction</h2></div><div className="mini-info"><CheckCircle2 size={16}/> Using {experiment.results.models.find(m=>m.key===experiment.selected_model)?.name} and its fitted preprocessing pipeline.</div>
            <div className="fields-grid">{experiment.results.input_schema.map((f:Field)=><label className="field-wrap" key={f.name}><span className="field-label">{f.name}</span>{f.kind==='select'?<select className="input" value={predictVals[f.name]??''} onChange={(e:any)=>updatePredictionInput(f.name,e.target.value)}><option value="">Missing / unspecified</option>{predictionCategoryChoices(f.options??[]).map(c=><option key={c.value} value={c.value}>{c.label}</option>)}</select>:<input className="input" type={f.kind==='number'?'number':'text'} step={f.domain?.integer?1:'any'} min={f.domain?.min} max={f.domain?.max} placeholder={f.kind==='number'&&f.min!==null?`e.g. ${f.min}`:'Enter value'} value={predictVals[f.name]??''} onChange={(e:any)=>updatePredictionInput(f.name,e.target.value)}/>}</label>)}</div><button className="btn primary full" disabled={busy==='predict'} onClick={()=>void runPrediction()}>{busy==='predict'?<LoaderCircle size={16} className="spin"/>:<Sparkles size={16}/>} Generate prediction</button><p className="muted-caption">Blank fields are passed as missing values and handled by the fitted preprocessing pipeline.</p></div>
            <div className="panel prediction-output"><div className="panel-title"><Activity size={19}/><h2>Prediction result</h2></div>{!prediction?<div className="waiting-result"><Target size={35}/><h3>Ready when you are</h3><p>Complete the input form and run your selected model.</p></div>:<><div className="result-hint">PREDICTED {experiment.results.target.toUpperCase()}</div><div className="result-text">{fmtPrediction(prediction.prediction,experiment.results?.task)}</div><p className="prediction-meaning">Predicted value for <b>{experiment.results.target}</b>: <b>{fmtPrediction(prediction.prediction,experiment.results.task)}</b>. {experiment.results.task==='classification'?'Class assignment from the selected model. These probabilities are model estimates, not guarantees.':'Numeric estimate in the target column’s original units; units must be verified with the data owner.'}</p>{prediction.probabilities&&<div className="probabilities">{prediction.probabilities.map(p=><div key={p.class}><div className="prob-label"><span>{String(p.class)}</span><b>{(p.probability*100).toFixed(1)}%</b></div><div className="progress"><div style={{width:`${p.probability*100}%`}}/></div></div>)}</div>}{prediction.probabilities&&prediction.probability_estimates_calibrated!==true&&<p className="po-ml-uncalibrated">Class probability estimates are not independently calibrated. An 80% model estimate does not establish an 80% real-world chance.</p>}<div className="mini-info warn-icon" role="alert"><AlertCircle size={16}/>{prediction.warning}</div>{prediction.input_warnings?.map((w,i)=><div key={i} className="warning-line"><AlertCircle size={14}/>{w}</div>)}{experiment.final_results&&<div className="prediction-reference"><strong>Model performance on held-out data</strong>{experiment.results.task==='regression'?<p>MAE: {fmt(experiment.final_results.mae as number)} · R²: {fmt(experiment.final_results.r2 as number)}. These describe overall test performance, not a guaranteed error range for this individual prediction.</p>:<p>Test accuracy: {typeof experiment.final_results.accuracy==='number'?(100*(experiment.final_results.accuracy as number)).toFixed(1)+'%':'—'}. This is not the certainty of this specific prediction.</p>}</div>}{(experiment.final_results as {reliability?:{issues?:string[]}}|null)?.reliability?.issues?.length? <div className="reliability-warning"><ShieldCheck size={20}/><div><strong>Unreliable model: experimental prediction only</strong><p>{(experiment.final_results as {reliability?:{issues?:string[]}}).reliability?.issues?.join(" ")}</p></div></div>:null}</>}</div></div>}
        </>}
      </div>
    </main>
    {project&&!embedded&&!showUpload&&page!=='ai_settings'&&<StudioAssistant open={odinOpen} onClose={()=>setOdinOpen(false)} onChat={()=>{setOdinOpen(false);go('assistant')}} scope={page==='overview'?'Home':NAV.find(n=>n.id===page)?.name??'Workspace'}><AIInsight key={project.id+':'+page} projectId={project.id} scope={page==='assistant'?'overview':page} version={qualityVersion} target={target} experimentId={experiment?.id} prediction={prediction} onOpenSettings={()=>{setOdinOpen(false);go('ai_settings')}}/></StudioAssistant>}
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
