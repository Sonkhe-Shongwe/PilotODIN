import {useCallback,useEffect,useMemo,useRef,useState} from 'react';
import type {CSSProperties,DragEvent as ReactDragEvent,PointerEvent as ReactPointerEvent,KeyboardEvent as ReactKeyboardEvent} from 'react';
import {Activity,BarChart3,BrainCircuit,Database,FileText,FlaskConical,Home,Settings2,ShieldCheck,Target,X,ChevronDown,Columns2,PanelRightClose,ArrowLeftRight,GripVertical,RotateCcw} from 'lucide-react';
import {App} from './App';
import {InvestigationCanvas} from './InvestigationCanvas';
import {get} from './api';
import {clampFraction,dockStorageKey,isSecondaryView,isWorkspaceView,makeDockResize,nextDockLayout,parseDockLayout,shouldClearUnavailableProject,WORKSPACE_VIEWS} from './workspaceLayout';
import type {DockLayout,SecondaryView,WorkspaceView} from './workspaceLayout';
import './unified-shell.css';

type ProjectListItem={id:string;name:string;filename:string};
type View=WorkspaceView;
const ALL:{id:View;label:string;icon:typeof Home}[]=[
 {id:'overview',label:'Home',icon:Home}, {id:'understand',label:'Your data',icon:Database},
 {id:'investigate',label:'Investigate',icon:BrainCircuit}, {id:'quality',label:'Quality',icon:ShieldCheck},
 {id:'explore',label:'Explore',icon:BarChart3}, {id:'prepare',label:'Prepare',icon:Database},
 {id:'model',label:'Model',icon:FlaskConical}, {id:'evaluate',label:'Evaluate',icon:Activity},
 {id:'predict',label:'Predict',icon:Target}, {id:'deliver',label:'Deliver',icon:FileText},
 {id:'assistant',label:'Ask ODIN',icon:BrainCircuit}, {id:'ai_settings',label:'Settings',icon:Settings2}
];
const keyFor=(id:string)=>`pilotodin-workspace-tabs-v1-${encodeURIComponent(id||'none')}`;
const activeKey=(id:string)=>`pilotodin-workspace-active-v1-${encodeURIComponent(id||'none')}`;
function readTabs(projectId:string):View[]{
 try{const data=JSON.parse(localStorage.getItem(keyFor(projectId))||'[]');
  if(Array.isArray(data)){const valid=data.filter(isWorkspaceView);return [...new Set<View>(valid)].slice(-8)}
 }catch{/* invalid preferences are not authoritative project data */}
 return [];
}
function readActive(projectId:string):View|null {try{const raw=localStorage.getItem(activeKey(projectId));return isWorkspaceView(raw)?raw:null}catch{return null}}
function readDock(projectId:string):DockLayout{
 try{return parseDockLayout(JSON.parse(localStorage.getItem(dockStorageKey(projectId))||'null'))}catch{return parseDockLayout(null)}
}
function routeView():View {
 if(location.hash.startsWith('#/canvas'))return 'investigate';
 const m=location.hash.match(/^#\/studio\/([a-z_]+)$/);
 return isWorkspaceView(m?.[1])?m![1] as View:'overview';
}
function navigate(v:View){location.hash=v==='investigate'?'#/canvas':`#/studio/${v}`}
const labelFor=(view:View)=>ALL.find(i=>i.id===view)?.label??view;
const PANEL_MIN_WIDTH=300;

/** One persistent desktop shell. Tabs and layouts are scoped to a project, not to its data. */
export function UnifiedShell(){
 const [active,setActive]=useState<View>(routeView);
 const [projectId,setProjectId]=useState(localStorage.getItem('pilotodin-current')||'');
 const [projects,setProjects]=useState<ProjectListItem[]>([]);
 const [openTabs,setOpenTabs]=useState<View[]>(()=>readTabs(localStorage.getItem('pilotodin-current')||''));
 const [dock,setDock]=useState<DockLayout>(()=>readDock(localStorage.getItem('pilotodin-current')||''));
 const [restoredFor,setRestoredFor]=useState<string|null>(null);
 const [warning,setWarning]=useState('');
 const splitRef=useRef<HTMLDivElement|null>(null);
 const dragCleanup=useRef<(()=>void)|null>(null);
 const refreshProjects=useCallback(async()=>{
  const selectedAtRequestStart=localStorage.getItem('pilotodin-current')||'';
  try{
   const rows=await get<ProjectListItem[]>('/projects');
   setProjects(rows);
   const latest=localStorage.getItem('pilotodin-current')||'';
   if(shouldClearUnavailableProject(selectedAtRequestStart,latest,rows)){
    localStorage.removeItem('pilotodin-current');
    setProjectId('');
    setWarning('The previously selected project is no longer available. Choose another project to continue.');
    window.dispatchEvent(new Event('pilotodin:project-changed'));
   }else{
    setWarning('');
   }
  }catch(e){setWarning('Project list unavailable: '+(e as Error).message)}
 },[]);
 useEffect(()=>{void refreshProjects()},[refreshProjects]);
 useEffect(()=>{
  const update=()=>{const next=localStorage.getItem('pilotodin-current')||'';setProjectId(id=>id===next?id:next);void refreshProjects()};
  const onRoute=()=>{setActive(routeView());update()};
  window.addEventListener('hashchange',onRoute);
  window.addEventListener('pilotodin:project-changed',update);
  window.addEventListener('storage',update);
  return()=>{window.removeEventListener('hashchange',onRoute);window.removeEventListener('pilotodin:project-changed',update);window.removeEventListener('storage',update)};
 },[refreshProjects]);
 useEffect(()=>{
  // Restore this project's state as one operation. Previous project's panes are discarded.
  const tabs=readTabs(projectId);
  const preferred=readActive(projectId)??(isWorkspaceView(routeView())?routeView():'overview');
  setOpenTabs(tabs.includes(preferred)?tabs:[...tabs,preferred].slice(-8));
  setDock(readDock(projectId));
  setActive(preferred);
  setRestoredFor(projectId);
  navigate(preferred);
 },[projectId]);
 useEffect(()=>{if(restoredFor!==projectId)return;setOpenTabs(old=>old.includes(active)?old:[...old,active].slice(-8))},[active,projectId,restoredFor]);
 useEffect(()=>{
  if(restoredFor!==projectId)return;
  try{localStorage.setItem(keyFor(projectId),JSON.stringify(openTabs));localStorage.setItem(activeKey(projectId),active)}catch{setWarning('Workspace preferences could not be saved; analytical work remains safe.')}
 },[openTabs,active,projectId,restoredFor]);
 useEffect(()=>{
  if(restoredFor!==projectId)return;
  try{localStorage.setItem(dockStorageKey(projectId),JSON.stringify(dock))}catch{setWarning('Pane layout could not be saved; project data is unaffected.')}
 },[dock,projectId,restoredFor]);
 useEffect(()=>()=>dragCleanup.current?.(),[]);
 const shownTabs=useMemo(()=>openTabs.filter(isWorkspaceView),[openTabs]);
 const chooseProject=(id:string)=>{if(!id||id===projectId)return;localStorage.setItem('pilotodin-current',id);setProjectId(id);window.dispatchEvent(new Event('pilotodin:project-changed'))};
 const close=(view:View)=>{
  const next=shownTabs.filter(t=>t!==view);setOpenTabs(next);
  if(view===active)navigate(next[next.length-1]||'overview');
  if(dock.secondary===view)setDock(current=>nextDockLayout(current,{kind:'close'}));
 };
 const dockView=(view:View)=>{
  if(!projectId||!isSecondaryView(view))return;
  setDock(current=>nextDockLayout(current,{kind:'open',view}));
 };
 const onDrop=(event:ReactDragEvent)=>{
  event.preventDefault();
  const proposed=event.dataTransfer.getData('text/x-pilotodin-workspace');
  if(isSecondaryView(proposed))dockView(proposed);
 };
 const resize=(event:ReactPointerEvent<HTMLDivElement>)=>{
  if(!splitRef.current)return;
  event.preventDefault();dragCleanup.current?.();
  const bound=splitRef.current.getBoundingClientRect();
  const move=(e:PointerEvent)=>setDock(current=>makeDockResize(current,e.clientX,bound.left,bound.width));
  const cleanup=()=>{window.removeEventListener('pointermove',move);window.removeEventListener('pointerup',cleanup);window.removeEventListener('pointercancel',cleanup);dragCleanup.current=null};
  window.addEventListener('pointermove',move);window.addEventListener('pointerup',cleanup);window.addEventListener('pointercancel',cleanup);dragCleanup.current=cleanup;
 };
 const resizeByKey=(event:ReactKeyboardEvent<HTMLDivElement>)=>{
  const direction=dock.side==='right'?-1:1;
  if(event.key==='ArrowLeft'||event.key==='ArrowRight'){
   event.preventDefault();const motion=(event.key==='ArrowRight'?1:-1)*direction*.025;
   setDock(current=>nextDockLayout(current,{kind:'resize',fraction:current.fraction+motion}));
  }
  if(event.key==='Home'||event.key==='End'){
   event.preventDefault();setDock(current=>nextDockLayout(current,{kind:'resize',fraction:event.key==='Home'?.28:.58}));
  }
 };
 useEffect(()=>{
  const onKey=(e:KeyboardEvent)=>{
   if(!(e.ctrlKey||e.metaKey)||e.altKey)return;
   const target=e.target as HTMLElement|null;
   if(target?.isContentEditable)return;
   const tag=target?.tagName;
   if((tag==='INPUT'||tag==='TEXTAREA'||tag==='SELECT')&&e.key.toLowerCase()==='w')return;
   if(e.key==='Tab'&&shownTabs.length>1){
    e.preventDefault();const ix=shownTabs.indexOf(active);navigate(shownTabs[(ix+(e.shiftKey?-1:1)+shownTabs.length)%shownTabs.length]);
   }else if(e.key.toLowerCase()==='w'&&shownTabs.length>1){e.preventDefault();close(active)}
  };
  window.addEventListener('keydown',onKey);return()=>window.removeEventListener('keydown',onKey);
 },[active,shownTabs,dock.secondary]);
 const canSplit=!!projectId&&dock.secondary!==null;
 const separate=canSplit&&active!==dock.secondary;
 const paneStyle={'--po-secondary-fraction':`${Math.round(clampFraction(dock.fraction)*10000)/100}%`} as CSSProperties;
 return <div className="po-unified-shell">
  <header className="po-shell-title">
   <div className="po-shell-brand"><span className="po-pilot">pilot</span><b>ODIN</b></div>
   <span className="po-shell-mode">LOCAL INTELLIGENCE WORKSPACE</span>
   <div className="po-project-switcher"><Database size={15}/><select aria-label="Active project" value={projectId} onChange={e=>chooseProject(e.target.value)}><option value="">Choose a project</option>{projects.map(p=><option key={p.id} value={p.id}>{p.name}</option>)}</select><ChevronDown size={14}/></div>
  </header>
  <div className="po-shell-row">
   <nav className="po-global-rail" aria-label="Workspace navigation">{ALL.map(({id,label,icon:Icon})=><button key={id} type="button" className={active===id?'po-rail-active':''} aria-current={active===id?'page':undefined} title={label} aria-label={label} onClick={()=>navigate(id)}><Icon size={20}/><span>{label}</span></button>)}</nav>
   <section className="po-shell-workspace">
    <div className="po-global-tabs" role="tablist" aria-label="Open analytical workspaces">
     {shownTabs.map(view=><div className={`po-tab ${active===view?'po-tab-selected':''}`} key={view} draggable={!!projectId&&isSecondaryView(view)} onDragStart={e=>e.dataTransfer.setData('text/x-pilotodin-workspace',view)}>
      <button role="tab" aria-selected={active===view} onClick={()=>navigate(view)}>{labelFor(view)}</button>
      {projectId&&isSecondaryView(view)&&<button type="button" title={`Dock ${labelFor(view)} beside current view`} aria-label={`Dock ${labelFor(view)} beside current view`} onClick={()=>dockView(view)}><Columns2 size={13}/></button>}
      {shownTabs.length>1&&<button type="button" aria-label={`Close ${labelFor(view)} tab`} onClick={()=>close(view)}><X size={12}/></button>}
     </div>)}
     <div className="po-tab-spacer"/>
     <button type="button" className="po-reset-layout" title="Reset workspace layout" aria-label="Reset workspace layout" onClick={()=>setDock(nextDockLayout(dock,{kind:'reset'}))}><RotateCcw size={14}/></button>
    </div>
    {warning&&<p className="po-shell-warning" role="status">{warning}</p>}
    <div className={`po-pane-layout ${canSplit?'po-pane-split':''} ${dock.side==='left'?'po-dock-left':''}`} ref={splitRef} style={paneStyle}>
     <section className="po-primary-pane" aria-label={`${labelFor(active)} workspace`}>
      <div className="po-pane-content" key={`primary-${projectId}-${active==='investigate'?'canvas':'studio'}`}>
       {active==='investigate'?<InvestigationCanvas/>:<App/>}
      </div>
     </section>
     {canSplit&&<>
      <div className="po-pane-resizer" role="separator" tabIndex={0} aria-label="Resize secondary analytical pane" aria-orientation="vertical" aria-valuemin={28} aria-valuemax={58} aria-valuenow={Math.round(dock.fraction*100)} onPointerDown={resize} onKeyDown={resizeByKey} title="Drag or use arrow keys to resize"><GripVertical size={16}/></div>
      <section className="po-secondary-pane" aria-label={`Docked ${labelFor(dock.secondary!)} workspace`} onDragOver={e=>e.preventDefault()} onDrop={onDrop}>
       <div className="po-pane-toolbar"><Columns2 size={14}/><strong>Docked workspace</strong>
        <select aria-label="Docked analytical component" value={dock.secondary??''} onChange={e=>{if(isSecondaryView(e.target.value))dockView(e.target.value)}}>
         {WORKSPACE_VIEWS.filter(isSecondaryView).map(view=><option key={view} value={view}>{labelFor(view)}</option>)}
        </select>
        <button type="button" onClick={()=>setDock(current=>nextDockLayout(current,{kind:'flip'}))} aria-label="Move docked pane to opposite side" title="Move pane left or right"><ArrowLeftRight size={15}/></button>
        <button type="button" onClick={()=>setDock(current=>nextDockLayout(current,{kind:'close'}))} aria-label="Close docked pane" title="Close docked pane"><PanelRightClose size={16}/></button>
       </div>
       {separate?<div className="po-pane-content" key={`secondary-${projectId}`}><App embeddedStage={dock.secondary!} embeddedProjectId={projectId} onEmbeddedNavigate={view=>dockView(view)}/></div>
         :<div className="po-pane-placeholder" role="status"><Columns2 size={28}/><strong>This workspace is already in the primary pane</strong><p>Choose another view from the dock selector. Your other tabs remain available.</p></div>}
      </section>
     </>}
    </div>
    {!canSplit&&projectId&&<div className="po-dock-drop-target" onDragOver={e=>e.preventDefault()} onDrop={onDrop}><Columns2 size={14}/> Open a workspace tab beside this view using <strong>Dock beside</strong>, or drag a tab here.</div>}
   </section>
  </div>
 </div>;
}
