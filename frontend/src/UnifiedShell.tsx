import {useCallback,useEffect,useMemo,useRef,useState} from 'react';
import type {CSSProperties,DragEvent as ReactDragEvent,PointerEvent as ReactPointerEvent,KeyboardEvent as ReactKeyboardEvent} from 'react';
import {Activity,BarChart3,BrainCircuit,Database,FileText,FlaskConical,Home,Settings2,ShieldCheck,Target,X,ChevronDown,Columns2,PanelRightClose,ArrowLeftRight,GripVertical,RotateCcw,PanelLeftClose,Plus} from 'lucide-react';
import {App} from './App';
import {navigateHashSmoothly} from './navigationMotion';
import {InvestigationCanvas} from './InvestigationCanvas';
import {get} from './api';
import {clampFraction,dockStorageKey,hasRoomForDock,isProjectWorkspaceRestored,isSecondaryView,isWorkspaceView,makeDockResize,nextDockLayout,parseDockLayout,shouldClearUnavailableProject,WORKSPACE_VIEWS} from './workspaceLayout';
import type {DockLayout,SecondaryView,WorkspaceView} from './workspaceLayout';
import {SIDEBAR_KEY,resolveSidebarMode} from './sidebarPreferences';
import {createProjectCatalogRequestGuard} from './projectCatalogRequestGuard';
import {nextWorkspaceTabByKey} from './workspaceTabKeyboard';
import {canReorderWorkspaceTab,reorderWorkspaceTabs,shiftWorkspaceTab} from './workspaceTabReorder';
import type {TabDropSide} from './workspaceTabReorder';
import {planWorkspaceTabClose} from './workspaceTabCloseFocus';
import {canRestoreDockDismissFocus,planDockDismissFocus} from './dockDismissFocus';
import {isEditableDockInput,needsDockInputDiscardApproval} from './dockInputDiscardGuard';
import type {EditedDock} from './dockInputDiscardGuard';
import {nextSidebarViewByKey} from './sidebarKeyboardNavigation';
import type {SidebarMode} from './sidebarPreferences';
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
const NAV_SECTIONS:{title:string;ids:View[]}[]=[
 {title:'WORKSPACE',ids:['overview','understand']},
 {title:'ANALYSIS',ids:['investigate','quality','explore']},
 {title:'MODELLING & DELIVERY',ids:['prepare','model','evaluate','predict','deliver']},
 {title:'ASSISTANCE',ids:['assistant','ai_settings']}
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
function navigate(v:View){navigateHashSmoothly(v==='investigate'?'#/canvas':`#/studio/${v}`)}
const labelFor=(view:View)=>ALL.find(i=>i.id===view)?.label??view;
const PANEL_MIN_WIDTH=300;

/** One persistent desktop shell. Tabs and layouts are scoped to a project, not to its data. */
export function UnifiedShell(){
 const [active,setActive]=useState<View>(routeView);
 const [motionReduced,setMotionReduced]=useState(()=>window.matchMedia?.('(prefers-reduced-motion: reduce)').matches??false);
 useEffect(()=>{
  const media=window.matchMedia?.('(prefers-reduced-motion: reduce)');
  if(!media)return;
  const updateMotion=()=>setMotionReduced(media.matches);
  media.addEventListener('change',updateMotion);
  return()=>media.removeEventListener('change',updateMotion);
 },[]);
 const [sidebarMode,setSidebarMode]=useState<SidebarMode>(()=>{
  try{return resolveSidebarMode(localStorage.getItem(SIDEBAR_KEY),window.innerWidth)}
  catch{return resolveSidebarMode(null,window.innerWidth)}
 });
 const [projectId,setProjectId]=useState(localStorage.getItem('pilotodin-current')||'');
 const [projects,setProjects]=useState<ProjectListItem[]>([]);
 // Do not mount data-fetching workspaces until the saved project ID is checked
 // against this environment's catalogue. Live dev intentionally has isolated data.
 const [catalogState,setCatalogState]=useState<'loading'|'ready'|'failed'>('loading');
 const [openTabs,setOpenTabs]=useState<View[]>(()=>readTabs(localStorage.getItem('pilotodin-current')||''));
 const [dock,setDock]=useState<DockLayout>(()=>readDock(localStorage.getItem('pilotodin-current')||''));
 const [restoredFor,setRestoredFor]=useState<string|null>(null);
 const [warning,setWarning]=useState('');
 // Creation uses the existing Studio import form rather than a second uploader.
 const [newProjectOpen,setNewProjectOpen]=useState(false);
 const splitRef=useRef<HTMLDivElement|null>(null);
 const tablistRef=useRef<HTMLDivElement|null>(null);
 const pendingCloseFocus=useRef<{projectId:string;view:View}|null>(null);
 const pendingDockDismissFocus=useRef<{projectId:string;view:View}|null>(null);
 // Memory-only flag, never store the contents of a form or dataset.
 const editedDock=useRef<EditedDock|null>(null);
 const draggedTab=useRef<{projectId:string;view:View}|null>(null);
 const [tabDropTarget,setTabDropTarget]=useState<{view:View;side:TabDropSide}|null>(null);
 const [paneWidth,setPaneWidth]=useState(0);
 const dragCleanup=useRef<(()=>void)|null>(null);
 const catalogRequests=useRef(createProjectCatalogRequestGuard());
 useEffect(()=>()=>catalogRequests.current.invalidate(),[]);
 const refreshProjects=useCallback(async()=>{
  const requestId=catalogRequests.current.begin();
  const selectedAtRequestStart=localStorage.getItem('pilotodin-current')||'';
  try{
   const rows=await get<ProjectListItem[]>('/projects');
   if(!catalogRequests.current.accepts(requestId))return;
   setProjects(rows);
   setCatalogState('ready');
   const latest=localStorage.getItem('pilotodin-current')||'';
   if(shouldClearUnavailableProject(selectedAtRequestStart,latest,rows)){
    localStorage.removeItem('pilotodin-current');
    setProjectId('');
    setWarning('The previously selected project is no longer available. Choose another project to continue.');
    window.dispatchEvent(new Event('pilotodin:project-changed'));
   }else{
    setWarning('');
   }
  }catch(e){
   if(!catalogRequests.current.accepts(requestId))return;
   // A later transient catalogue failure must not destroy an already open view.
   setCatalogState(previous=>previous==='ready'?'ready':'failed');
   setWarning('Project list unavailable: '+(e as Error).message);
  }
 },[]);
 useEffect(()=>{void refreshProjects()},[refreshProjects]);
 useEffect(()=>{
  const update=()=>{const next=localStorage.getItem('pilotodin-current')||'';setProjectId(id=>id===next?id:next);void refreshProjects()};
  const onRoute=()=>setActive(routeView());
  window.addEventListener('hashchange',onRoute);
  window.addEventListener('pilotodin:route-commit',onRoute);
  window.addEventListener('pilotodin:project-changed',update);
  window.addEventListener('storage',update);
  return()=>{window.removeEventListener('hashchange',onRoute);window.removeEventListener('pilotodin:route-commit',onRoute);window.removeEventListener('pilotodin:project-changed',update);window.removeEventListener('storage',update)};
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
 useEffect(()=>{draggedTab.current=null;setTabDropTarget(null)},[projectId]);
 useEffect(()=>{
  const node=splitRef.current;
  if(!node)return;
  const read=()=>setPaneWidth(node.getBoundingClientRect().width);
  read();
  if(typeof ResizeObserver==='undefined'){
   window.addEventListener('resize',read);
   return()=>window.removeEventListener('resize',read);
  }
  const observer=new ResizeObserver(read);
  observer.observe(node);
  return()=>observer.disconnect();
 },[]);
 const workspaceReady=isProjectWorkspaceRestored(projectId,restoredFor,catalogState);
 const shownTabs=useMemo(()=>restoredFor===projectId?openTabs.filter(isWorkspaceView):[],[openTabs,restoredFor,projectId]);
 useEffect(()=>{
  const pending=pendingCloseFocus.current;
  if(!pending)return;
  if(pending.projectId!==projectId){pendingCloseFocus.current=null;return;}
  if(!workspaceReady||active!==pending.view||!shownTabs.includes(pending.view))return;
  const index=shownTabs.indexOf(pending.view);
  const target=tablistRef.current?.querySelectorAll<HTMLButtonElement>('[role="tab"]')?.item(index);
  if(!target)return;
  pendingCloseFocus.current=null;
  target.focus();
 },[active,shownTabs,projectId,workspaceReady]);
 useEffect(()=>{
  const pending=pendingDockDismissFocus.current;
  if(!pending)return;
  if(pending.projectId!==projectId||(workspaceReady&&(active!==pending.view||dock.secondary!==null))){
   pendingDockDismissFocus.current=null;
   return;
  }
  if(!canRestoreDockDismissFocus(pending,projectId,active,shownTabs,dock,workspaceReady))return;
  const target=tablistRef.current?.querySelectorAll<HTMLButtonElement>('[role="tab"]')?.item(shownTabs.indexOf(pending.view));
  pendingDockDismissFocus.current=null;
  target?.focus();
 },[projectId,active,shownTabs,dock.secondary,workspaceReady]);
 const confirmEditedDockDiscard=(action:'close'|'replace'|'switch-project'|'reset'|'close-tab'|'activate',proposed:SecondaryView|null=null)=>{
  if(!needsDockInputDiscardApproval(editedDock.current,projectId,dock.secondary,action,proposed))return true;
  return window.confirm('You changed fields in the docked workspace. This action may discard those entries. Continue?');
 };
 // The primary App has its own local go() path; it must consult the shell BEFORE
 // committing a route which would activate (and therefore unmount) its edited dock.
 const approvePrimaryStudioNavigation=(view:View):boolean=>{
  if(!workspaceReady)return false;
  if(view!==active&&dock.secondary===view&&isSecondaryView(view)){
   if(!confirmEditedDockDiscard('activate',view))return false;
   // Promotion clears the old secondary slot only after approval.
   editedDock.current=null;
   setDock(current=>nextDockLayout(current,{kind:'close'}));
  }
  return true;
 };
 // When a docked view becomes the primary view, the embedded form unmounts.
 // Ask before leaving an edited dock, rather than navigating and warning too late.
 const navigateWithDockGuard=(view:View):boolean=>{
  if(view!==active&&dock.secondary===view&&isSecondaryView(view)){
   if(!confirmEditedDockDiscard('activate',view))return false;
   editedDock.current=null;
   setDock(current=>nextDockLayout(current,{kind:'close'}));
  }
  navigate(view);
  return true;
 };
 const chooseProject=(id:string)=>{if(!id||id===projectId)return;
  if(!confirmEditedDockDiscard('switch-project'))return;
  editedDock.current=null;
  setNewProjectOpen(false);localStorage.setItem('pilotodin-current',id);setProjectId(id);window.dispatchEvent(new Event('pilotodin:project-changed'))};
 const sidebarViews=useMemo(()=>NAV_SECTIONS.flatMap(section=>section.ids),[]);
 const onSidebarKeyDown=(event:ReactKeyboardEvent<HTMLButtonElement>,view:View)=>{
  if(event.altKey||event.ctrlKey||event.metaKey||event.shiftKey)return;
  const next=nextSidebarViewByKey(sidebarViews,view,event.key);
  if(!next)return;
  event.preventDefault();
  if(next!==active&&!navigateWithDockGuard(next))return;
  const buttons=event.currentTarget.closest('#po-nav-items')?.querySelectorAll<HTMLButtonElement>('.po-nav-item');
  buttons?.item(sidebarViews.indexOf(next))?.focus();
 };
 const onWorkspaceTabKeyDown=(event:ReactKeyboardEvent<HTMLButtonElement>,view:View)=>{
  // Keyboard reorder does not activate a workspace, dock it or discard its inputs.
  if(event.altKey&&event.shiftKey&&!event.ctrlKey&&!event.metaKey&&(event.key==='ArrowLeft'||event.key==='ArrowRight')){
   event.preventDefault();
   if(projectId&&workspaceReady)setOpenTabs(tabs=>shiftWorkspaceTab(tabs,view,event.key==='ArrowLeft'?-1:1));
   return;
  }
  if(event.altKey||event.ctrlKey||event.metaKey||event.shiftKey)return;
  const next=nextWorkspaceTabByKey(shownTabs,view,event.key);
  if(!next)return;
  event.preventDefault();
  if(next!==active&&!navigateWithDockGuard(next))return;
  const tabButtons=event.currentTarget.closest('[role="tablist"]')?.querySelectorAll<HTMLButtonElement>('[role="tab"]');
  tabButtons?.item(shownTabs.indexOf(next))?.focus();
 };
 const close=(view:View)=>{
  if(!workspaceReady)return;
  const plan=planWorkspaceTabClose(shownTabs,active,view);
  if(!plan)return;
  if(dock.secondary===view&&!confirmEditedDockDiscard('close-tab'))return;
  if(plan.nextActive!==active&&dock.secondary===plan.nextActive&&isSecondaryView(plan.nextActive)&&!confirmEditedDockDiscard('activate',plan.nextActive))return;
  if(dock.secondary===view||dock.secondary===plan.nextActive&&plan.nextActive!==active)editedDock.current=null;
  pendingCloseFocus.current={projectId,view:plan.focus};
  setOpenTabs(plan.remaining);
  if(plan.nextActive!==active)navigate(plan.nextActive);
  if(dock.secondary===view||(plan.nextActive!==active&&dock.secondary===plan.nextActive))setDock(current=>nextDockLayout(current,{kind:'close'}));
 };
 const closeDock=()=>{
  const focus=planDockDismissFocus(projectId,active,shownTabs,dock,workspaceReady);
  if(!focus||!confirmEditedDockDiscard('close'))return;
  editedDock.current=null;
  pendingDockDismissFocus.current=focus;
  setDock(current=>nextDockLayout(current,{kind:'close'}));
 };
 const dockView=(view:View)=>{
  if(!projectId||!isSecondaryView(view))return;
  if(dock.secondary!==view&&!confirmEditedDockDiscard('replace',view))return;
  if(dock.secondary!==view)editedDock.current=null;
  setDock(current=>nextDockLayout(current,{kind:'open',view}));
 };
 // Drop-on-tab reorders; drop-on-pane keeps the existing independent docking contract.
 const onTabDragOver=(event:ReactDragEvent<HTMLDivElement>,target:View)=>{
  if(!canReorderWorkspaceTab(projectId,workspaceReady,draggedTab.current,target,shownTabs))return;
  event.preventDefault();
  event.stopPropagation();
  event.dataTransfer.dropEffect='move';
  const bounds=event.currentTarget.getBoundingClientRect();
  const side:TabDropSide=event.clientX<bounds.left+bounds.width/2?'before':'after';
  setTabDropTarget(previous=>previous?.view===target&&previous.side===side?previous:{view:target,side});
 };
 const onTabDrop=(event:ReactDragEvent<HTMLDivElement>,target:View)=>{
  const dragged=draggedTab.current;
  if(!canReorderWorkspaceTab(projectId,workspaceReady,dragged,target,shownTabs))return;
  event.preventDefault();
  event.stopPropagation();
  const bounds=event.currentTarget.getBoundingClientRect();
  const side:TabDropSide=event.clientX<bounds.left+bounds.width/2?'before':'after';
  setOpenTabs(tabs=>reorderWorkspaceTabs(tabs,dragged!.view,target,side));
  draggedTab.current=null;
  setTabDropTarget(null);
 };
 const onDrop=(event:ReactDragEvent)=>{
  event.preventDefault();
  const proposed=event.dataTransfer.getData('text/x-pilotodin-workspace');
  if(isSecondaryView(proposed))dockView(proposed);
  draggedTab.current=null;
  setTabDropTarget(null);
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
    e.preventDefault();const ix=shownTabs.indexOf(active);navigateWithDockGuard(shownTabs[(ix+(e.shiftKey?-1:1)+shownTabs.length)%shownTabs.length]);
   }else if(e.key.toLowerCase()==='w'&&shownTabs.length>1){e.preventDefault();close(active)}
  };
  window.addEventListener('keydown',onKey);return()=>window.removeEventListener('keydown',onKey);
 },[active,shownTabs,dock.secondary,projectId,workspaceReady]);
 const toggleSidebar=()=>{
  const next=sidebarMode==='expanded'?'compact':'expanded';
  setSidebarMode(next);
  try{localStorage.setItem(SIDEBAR_KEY,next)}
  catch{setWarning('Sidebar preference could not be saved. It still works this session.')}
 };
 // Leaving Home closes the import flow without changing the selected project.
 useEffect(()=>{if(active!=='overview')setNewProjectOpen(false)},[active]);
 const dockConfigured=!!projectId&&workspaceReady&&dock.secondary!==null;
 const canSplit=dockConfigured&&hasRoomForDock(dock,paneWidth);
 const dockPaused=dockConfigured&&!canSplit;
 // Keep only a previously edited secondary form mounted during a temporary narrow pause.
 // CSS/hidden removes it from view and keyboard focus; no input values are persisted.
 const preservePausedEditedDock=dockPaused&&active!==dock.secondary&&
  editedDock.current?.projectId===projectId&&editedDock.current?.view===dock.secondary;
 const mountDock=canSplit||preservePausedEditedDock;
 const separate=mountDock&&active!==dock.secondary;
 useEffect(()=>{
  // Clear only when the embedded form really unmounts (not during a hidden pause).
  if(!separate)editedDock.current=null;
 },[separate,projectId,dock.secondary]);
 const paneStyle={'--po-secondary-fraction':`${Math.round(clampFraction(dock.fraction)*10000)/100}%`} as CSSProperties;
 return <div className="po-unified-shell">
  <header className="po-shell-title">
   <div className="po-shell-brand"><img className="po-brand-symbol" src="/pilotodin-symbol.svg" alt="" aria-hidden="true"/><span className="po-brand-wordmark"><span className="po-pilot">pilot</span><b>ODIN</b></span></div>
   <span className="po-shell-mode">LOCAL INTELLIGENCE WORKSPACE</span>
   {motionReduced&&<span className="po-motion-reduced" role="status" title="Windows or your browser requests reduced motion. PilotODIN honours this accessibility setting.">Animations reduced by system</span>}
   <div className="po-project-switcher"><Database size={15}/><select aria-label="Switch project" title={projects.length<2?'Import another dataset to switch between projects':'Switch between imported projects'} value={projectId} onChange={e=>chooseProject(e.target.value)}><option value="" disabled>{projects.length?"Select an imported project":"No projects imported yet"}</option>{projects.map(p=><option key={p.id} value={p.id}>{p.name}</option>)}</select><ChevronDown size={14}/></div>
   <button type="button" className="po-new-project-action" title="Import a CSV or Excel file as a separate project" aria-label="New project: import dataset" onClick={()=>{setNewProjectOpen(true);navigate('overview')}}><Plus size={16} aria-hidden="true"/><span>New project</span></button>
  </header>
  <div className="po-shell-row">
   <button type="button" className={`po-nav-backdrop ${sidebarMode==='expanded'?'po-nav-backdrop-open':''}`} aria-label="Close sidebar" aria-hidden={sidebarMode!=='expanded'} tabIndex={sidebarMode==='expanded'?0:-1} disabled={sidebarMode!=='expanded'} onClick={toggleSidebar}/>
   <nav className={`po-global-rail po-rail-${sidebarMode}`} aria-label="Workspace navigation">
    <div className="po-rail-heading"><span>NAVIGATION</span>
     <button type="button" className="po-rail-toggle" aria-label={sidebarMode==='expanded'?'Collapse navigation sidebar':'Expand navigation sidebar'} aria-expanded={sidebarMode==='expanded'} aria-controls="po-nav-items" title={sidebarMode==='expanded'?'Collapse sidebar':'Expand sidebar'} onClick={toggleSidebar}><PanelLeftClose className="po-toggle-glyph" size={20} aria-hidden="true"/></button>
    </div>
    <div id="po-nav-items" className="po-nav-scroller">
     {NAV_SECTIONS.map(section=><div className="po-nav-section" role="group" aria-label={section.title} key={section.title}>
      <span className="po-nav-group-caption" aria-hidden="true">{section.title}</span>
      {ALL.filter(item=>section.ids.includes(item.id)).map(({id,label,icon:Icon})=><button key={id} type="button" className={`po-nav-item ${active===id?'po-rail-active':''}`} aria-current={active===id?'page':undefined} title={sidebarMode==='compact'?label:undefined} aria-label={label} onKeyDown={event=>onSidebarKeyDown(event,id)} onClick={()=>navigateWithDockGuard(id)}><Icon size={20}/><span className="po-nav-label">{label}</span></button>)}
     </div>)}
    </div>
    <div className="po-rail-status"><span className="po-rail-status-dot"/> <span>LOCAL WORKSPACE</span></div>
   </nav>
   <section className="po-shell-workspace">
    <div className="po-global-tabs" role="tablist" aria-label="Open analytical workspaces" ref={tablistRef}>
     {shownTabs.map(view=><div className={`po-tab ${active===view?'po-tab-selected':''} ${tabDropTarget?.view===view?`po-tab-drop-${tabDropTarget.side}`:''}`} key={view} draggable={!!projectId&&workspaceReady} onDragStart={event=>{draggedTab.current={projectId,view};event.dataTransfer.effectAllowed='move';event.dataTransfer.setData('text/x-pilotodin-tab',view);if(isSecondaryView(view))event.dataTransfer.setData('text/x-pilotodin-workspace',view)}} onDragOver={event=>onTabDragOver(event,view)} onDrop={event=>onTabDrop(event,view)} onDragEnd={()=>{draggedTab.current=null;setTabDropTarget(null)}}>
      <button type="button" role="tab" id={`po-workspace-tab-${view}`} aria-controls="po-current-workspace" aria-selected={active===view} tabIndex={active===view?0:-1} onKeyDown={event=>onWorkspaceTabKeyDown(event,view)} onClick={()=>navigateWithDockGuard(view)} title="Drag to reorder; Alt+Shift+Left/Right moves this tab">{labelFor(view)}</button>
      {projectId&&isSecondaryView(view)&&<button type="button" title={`Dock ${labelFor(view)} beside current view`} aria-label={`Dock ${labelFor(view)} beside current view`} onClick={()=>dockView(view)}><Columns2 size={13}/></button>}
      {shownTabs.length>1&&<button type="button" aria-label={`Close ${labelFor(view)} tab`} onClick={()=>close(view)}><X size={12}/></button>}
     </div>)}
     <div className="po-tab-spacer"/>
     <button type="button" className="po-reset-layout" title="Reset workspace layout" aria-label="Reset workspace layout" onClick={()=>{if(!confirmEditedDockDiscard('reset'))return;editedDock.current=null;setDock(nextDockLayout(dock,{kind:'reset'}))}}><RotateCcw size={14}/></button>
    </div>
    {warning&&<p className="po-shell-warning" role="status">{warning}</p>}
    <div className={`po-pane-layout ${canSplit?'po-pane-split':''} ${dock.side==='left'?'po-dock-left':''}`} ref={splitRef} style={paneStyle}>
     <section className="po-primary-pane" id="po-current-workspace" role="tabpanel" aria-labelledby={`po-workspace-tab-${active}`} tabIndex={0}>
      <div className="po-pane-content" key={`primary-${projectId}-${active==='investigate'?'canvas':'studio'}`}>
       {workspaceReady?(active==='investigate'?<InvestigationCanvas key={`canvas-${projectId}`}/>:<App key={`studio-${projectId}`} onPrimaryNavigate={approvePrimaryStudioNavigation} forceNewProject={newProjectOpen&&active==='overview'} onNewProjectClose={()=>setNewProjectOpen(false)}/>):<div className="po-pane-placeholder" role="status"><Database size={26}/><strong>{catalogState==='loading'?'Checking available projects':catalogState==='failed'?'Project catalogue unavailable':'Restoring project workspace'}</strong><p>{catalogState==='failed'?warning:catalogState==='ready'?'Restoring this project’s saved tabs and dock before loading its data.':'Checking that the saved project belongs to this local workspace before loading its data.'}</p>{catalogState==='failed'&&<button type="button" className="ud-btn ud-btn-primary" onClick={()=>{setCatalogState('loading');void refreshProjects()}}>Retry project check</button>}</div>}
      </div>
     </section>
     {mountDock&&<>
      <div className="po-pane-resizer" hidden={!canSplit} role="separator" tabIndex={canSplit?0:-1} aria-label="Resize secondary analytical pane" aria-orientation="vertical" aria-valuemin={28} aria-valuemax={58} aria-valuenow={Math.round(dock.fraction*100)} onPointerDown={resize} onKeyDown={resizeByKey} title="Drag or use arrow keys to resize"><GripVertical size={16}/></div>
      <section className="po-secondary-pane" hidden={!canSplit} aria-label={`Docked ${labelFor(dock.secondary!)} workspace`} onDragOver={e=>e.preventDefault()} onDrop={onDrop}>
       <div className="po-pane-toolbar"><Columns2 size={14}/><strong>Docked workspace</strong>
        <select aria-label="Docked analytical component" value={dock.secondary??''} onChange={e=>{if(isSecondaryView(e.target.value))dockView(e.target.value)}}>
         {WORKSPACE_VIEWS.filter(isSecondaryView).map(view=><option key={view} value={view}>{labelFor(view)}</option>)}
        </select>
        <button type="button" onClick={()=>setDock(current=>nextDockLayout(current,{kind:'flip'}))} aria-label="Move docked pane to opposite side" title="Move pane left or right"><ArrowLeftRight size={15}/></button>
        <button type="button" onClick={closeDock} aria-label="Close docked pane" title="Close docked pane"><PanelRightClose size={16}/></button>
       </div>
       {separate?<div className="po-pane-content" key={`secondary-${projectId}`} onChangeCapture={event=>{if(dock.secondary&&isEditableDockInput((event.target as HTMLElement).tagName))editedDock.current={projectId,view:dock.secondary}}}><App embeddedStage={dock.secondary!} embeddedProjectId={projectId} onEmbeddedNavigate={view=>dockView(view)}/></div>
         :<div className="po-pane-placeholder" role="status"><Columns2 size={28}/><strong>This workspace is already in the primary pane</strong><p>Choose another view from the dock selector. Your other tabs remain available.</p></div>}
      </section>
     </>}
    </div>
    {dockPaused&&<div className="po-dock-narrow-notice" role="status"><Columns2 size={14} aria-hidden="true"/> {preservePausedEditedDock?'Edited docked fields are kept in memory while this view is narrow (not saved). Widen the window or collapse the sidebar to continue.':'Docked view paused while this workspace is narrow. Widen the window or collapse the sidebar to restore your saved split.'}</div>}
    {!dockConfigured&&projectId&&<div className="po-dock-drop-target" onDragOver={e=>e.preventDefault()} onDrop={onDrop}><Columns2 size={14}/> Open a workspace tab beside this view using <strong>Dock beside</strong>, or drag a tab here.</div>}
   </section>
  </div>
 </div>;
}
