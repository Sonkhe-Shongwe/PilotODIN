import {useCallback,useEffect,useMemo,useRef,useState} from 'react';
import type {CSSProperties,DragEvent as ReactDragEvent,PointerEvent as ReactPointerEvent,KeyboardEvent as ReactKeyboardEvent} from 'react';
import {Activity,BarChart3,BrainCircuit,Database,FileText,FlaskConical,Home,Settings2,ShieldCheck,Target,X,ChevronDown,Columns2,PanelRightClose,ArrowLeftRight,GripVertical,RotateCcw,PanelLeftClose,Plus} from 'lucide-react';
import {App} from './App';
import {ProjectManager} from './ProjectManager';
import {ShellClock} from './ShellClock';
import {projectOptionLabels} from './projectOptionLabels';
import {isCurrentProjectHeldArchived,parseProjectLifecycleSignal,preserveMountedUnavailableProject,publishProjectLifecycleSignal,PROJECT_LIFECYCLE_SIGNAL_KEY} from './projectLifecycleSignal';
import type {ManagedProject} from './ProjectManager';
import type {PrimaryProjectLoadSnapshot} from './App';
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
import {hasUnsavedWorkspaceDraftForUnload,isEditableDockInput,needsDockInputDiscardApproval} from './dockInputDiscardGuard';
import {isDesktop} from './desktopBootstrap';
import {invoke} from '@tauri-apps/api/core';
import {listen} from '@tauri-apps/api/event';
import {NATIVE_CLOSE_EVENT,resolveNativeCloseRequest} from './nativeCloseConsent';
import type {NativeCloseRequest} from './nativeCloseConsent';
import {planExternalRouteActivation} from './externalRouteActivationGuard';
import {needsPrimaryStudioExitApproval} from './primaryStudioExitGuard';
import {planExternalProjectTransition,shouldHoldNativeDeliverExternalProjectChange} from './externalProjectTransitionGuard';
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
function routeViewFromHash(hash:string):View {
 if(hash.startsWith('#/canvas'))return 'investigate';
 const m=hash.match(/^#\/studio\/([a-z_]+)$/);
 return isWorkspaceView(m?.[1])?m![1] as View:'overview';
}
function routeView():View {return routeViewFromHash(location.hash);}
function navigate(v:View){navigateHashSmoothly(v==='investigate'?'#/canvas':`#/studio/${v}`)}
const labelFor=(view:View)=>ALL.find(i=>i.id===view)?.label??view;
const PANEL_MIN_WIDTH=300;
const PRIMARY_CANVAS_EXIT_MESSAGE='You changed fields in the primary workspace. Opening Investigate will discard those unsaved entries. Continue?';
const primaryExitMessage=(current:View)=>current==='deliver'
 ?'Your Deliver report contains unsaved changes. Switching workspaces will discard these edits. Continue?'
 :current==='understand'
 ?'Your Data Dictionary has unsaved business descriptions. Switching workspaces will discard these edits. Continue?'
 :PRIMARY_CANVAS_EXIT_MESSAGE;

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
 const selectorLabels=useMemo(()=>projectOptionLabels(projects),[projects]);
 // Do not mount data-fetching workspaces until the saved project ID is checked
 // against this environment's catalogue. Live dev intentionally has isolated data.
 const [catalogState,setCatalogState]=useState<'loading'|'ready'|'failed'>('loading');
 // A verified archive in another window is not permission to discard local drafts.
 const [heldArchivedId,setHeldArchivedId]=useState('');
 const heldArchivedRef=useRef('');
 const currentProjectRef=useRef(projectId);
 currentProjectRef.current=projectId;
 const currentActiveRef=useRef(active);
 currentActiveRef.current=active;
 // One-use native dialog; no draft text is cached in the consent ticket.
 const nativeDeliverExitPending=useRef(false);
 const nativeDeliverExitTicket=useRef(0);
 useEffect(()=>()=>{nativeDeliverExitTicket.current++;nativeDeliverExitPending.current=false},[]);
 const [openTabs,setOpenTabs]=useState<View[]>(()=>readTabs(localStorage.getItem('pilotodin-current')||''));
 const [dock,setDock]=useState<DockLayout>(()=>readDock(localStorage.getItem('pilotodin-current')||''));
 const currentDockSecondaryRef=useRef(dock.secondary);
 currentDockSecondaryRef.current=dock.secondary;
 const [restoredFor,setRestoredFor]=useState<string|null>(null);
 const [warning,setWarning]=useState('');
 // Creation uses the existing Studio import form rather than a second uploader.
 const [newProjectOpen,setNewProjectOpen]=useState(false);
 const [projectManagerOpen,setProjectManagerOpen]=useState(false);
 const splitRef=useRef<HTMLDivElement|null>(null);
 const tablistRef=useRef<HTMLDivElement|null>(null);
 const pendingCloseFocus=useRef<{projectId:string;view:View}|null>(null);
 const pendingDockDismissFocus=useRef<{projectId:string;view:View}|null>(null);
 // Memory-only flags: no form content or dataset values are stored.
 const editedDock=useRef<EditedDock|null>(null);
 const editedPrimary=useRef<{projectId:string;view:'understand'|'prepare'|'model'|'predict'|'deliver'}|null>(null);
 // Tauri/WebView2 may not display a synchronous browser confirm. Keep native
 // project-switch consent serialized and never store unsaved form values.
 const nativeProjectSwitchPromptPending=useRef(false);
 const [nativeProjectSwitchWaiting,setNativeProjectSwitchWaiting]=useState(false);
 // A consented external switch is provisional until the existing Studio has
 // read the requested project. A failed GET must never unmount this draft.
 const pendingExternalSwitch=useRef<{
  requestedId:string;previousId:string;fromStorage:boolean;
  primary:typeof editedPrimary.current;secondary:EditedDock|null;
 }|null>(null);
 // One-use memory-only result of both successful primary B GETs. The keyed
 // Studio mount consumes it instead of repeating reads after shell commit.
 const primaryProjectHandoff=useRef<PrimaryProjectLoadSnapshot|null>(null);
 // Last accepted URL is memory-only; never store form values or push synthetic history entries.
 const acceptedRouteHash=useRef(window.location.hash);
 // One-shot preapproved same-document push consent, never persisted.
 const preapprovedRoutePush=useRef<string|null>(null);
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
   if(heldArchivedRef.current&&rows.some(item=>item.id===heldArchivedRef.current)){
    heldArchivedRef.current='';
    setHeldArchivedId('');
   }
   const mountedId=currentProjectRef.current;
   // Empty import workspace IDs must never be reported as archived.
   const mountedIsHeldArchived=isCurrentProjectHeldArchived(mountedId,heldArchivedRef.current);
   if(shouldClearUnavailableProject(selectedAtRequestStart,latest,rows)){
    if(preserveMountedUnavailableProject(mountedId,latest,selectedAtRequestStart,
      mountedIsHeldArchived)){
     // Another tab changed the shared selector, or archived our open project.
     // Never clear shared storage or unmount our potentially edited workspace.
     setWarning(mountedIsHeldArchived
      ?'This project was archived in another window. Your unsaved fields remain visible here. Restore it using Manage projects before making changes.'
      :'Another tab selected a project that is no longer available. Your current workspace remains mounted; choose a valid project before reloading.');
     return;
    }
    localStorage.removeItem('pilotodin-current');
    setProjectId('');
    setWarning('The previously selected project is no longer available. Choose another project to continue.');
    window.dispatchEvent(new CustomEvent('pilotodin:project-changed',{detail:{reason:'unavailable'}}));
   }else{
    setWarning(mountedIsHeldArchived
     ?'This project was archived in another window. Your unsaved fields remain visible here. Restore it using Manage projects before making changes.':'');
   }
  }catch(e){
   if(!catalogRequests.current.accepts(requestId))return;
   // A later transient catalogue failure must not destroy an already open view.
   setCatalogState(previous=>previous==='ready'?'ready':'failed');
   setWarning('Project list unavailable: '+(e as Error).message);
  }
 },[]);
 useEffect(()=>{void refreshProjects()},[refreshProjects]);
 // Notifications are hints only. Verify the exact project revision/state
 // against the local backend before surfacing an archive or rename.
 useEffect(()=>{
  let active=true;
  let sequence=0;
  const receive=(event:StorageEvent)=>{
   if(event.key!==PROJECT_LIFECYCLE_SIGNAL_KEY)return;
   const signal=parseProjectLifecycleSignal(event.newValue);
   if(!signal)return;
   const request=++sequence;
   void get<ManagedProject[]>('/projects/manage').then(rows=>{
    if(!active||request!==sequence)return;
    const row=rows.find(item=>item.id===signal.id);
    if(!row||row.revision<signal.revision)return;
    const isArchived=row.archived_at!==null;
    if(row.id===currentProjectRef.current){
     heldArchivedRef.current=isArchived?row.id:'';
     setHeldArchivedId(heldArchivedRef.current);
    }
    window.dispatchEvent(new CustomEvent('pilotodin:project-metadata-changed',{
     detail:{id:row.id,name:row.name,filename:row.filename,archived:isArchived}
    }));
    void refreshProjects();
   }).catch(()=>{
    if(active&&request===sequence)
     setWarning('Could not verify a change from another window. Your current workspace remains mounted. Retry when the local backend is available.');
   });
  };
  window.addEventListener('storage',receive);
  return()=>{active=false;sequence++;window.removeEventListener('storage',receive)};
 },[refreshProjects]);

 useEffect(()=>{
  // Restore this project's state as one operation. Previous project's panes are discarded.
  const tabs=readTabs(projectId);
  const preferred=readActive(projectId)??(isWorkspaceView(routeView())?routeView():'overview');
  setOpenTabs(tabs.includes(preferred)?tabs:[...tabs,preferred].slice(-8));
  // A restored project must not start with its primary view duplicated in a dock.
  // No in-memory edited form survives a new project workspace restoration.
  const savedDock=readDock(projectId);
  setDock(savedDock.secondary===preferred?nextDockLayout(savedDock,{kind:'close'}):savedDock);
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
 useEffect(()=>{draggedTab.current=null;setTabDropTarget(null);setPrimaryDockHover(false)},[projectId]);
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
 useEffect(()=>{
  const reviewProject=(event:Event)=>{
   if(event.type==='storage'&&(event as StorageEvent).key!==null&&(event as StorageEvent).key!=='pilotodin-current')return;
   const requested=localStorage.getItem('pilotodin-current')||'';
   const unavailable=event.type==='pilotodin:project-changed'&&(event as CustomEvent<{reason?:string}>).detail?.reason==='unavailable';
   // A storage notification is bridged to the ordinary App listener. Never
   // ask twice or let the bridge change the shell's project before the GET.
   if(pendingExternalSwitch.current?.requestedId===requested&&!unavailable)return;
   if(pendingExternalSwitch.current&&pendingExternalSwitch.current.requestedId!==requested)
    pendingExternalSwitch.current=null;
   const decision=planExternalProjectTransition(projectId,requested,dock.secondary,editedDock.current,workspaceReady,unavailable,editedPrimary.current?.projectId??null);
   if(decision==='unchanged'){
    if(event.type==='pilotodin:project-changed')void refreshProjects();
    return;
   }
   if(shouldHoldNativeDeliverExternalProjectChange(event.type,decision,isDesktop(),projectId,editedPrimary.current)){
    // Another window's selector is not permission to discard our report.
    // Keep this project mounted until the user switches with native consent here.
    setWarning("Another tab selected a different project. This window kept your unsaved Deliver report. Use Switch project here after saving; reloading may select the other tab's project.");
    event.stopImmediatePropagation();
    return;
   }
   if(decision==='confirm'&&!window.confirm(
    editedPrimary.current?.projectId===projectId
      ?(needsDockInputDiscardApproval(editedDock.current,projectId,dock.secondary,'switch-project')
        ?'You changed fields in the primary and docked workspaces. Switching projects may discard those entries. Continue?'
        :'You changed fields in the primary workspace. Switching projects may discard those entries. Continue?')
      :'You changed fields in the docked workspace. Switching projects may discard those entries. Continue?')){
    if(event.type==='storage'){
     // Do not write an earlier project ID back into shared storage: multiple edited
     // browser tabs could otherwise repeatedly veto and revert each other's choice.
     setWarning('Another tab selected a different project. This window keeps its unsaved workspace; reloading may use the other tab’s selection.');
    }else{
     try{localStorage.setItem('pilotodin-current',projectId)}
     catch{setWarning('Project selection could not be restored. Unsaved entries remain in this window; avoid reloading until you resolve the selection.')}
    }
    // A cancelled external selection must not reach Studio's project load listener.
    event.stopImmediatePropagation();
    return;
   }
   if(decision==='confirm'){
    // Consent is not a successful project load. Keep the current App keyed to
    // A and its edits mounted until the requested B project GETs both succeed.
    pendingExternalSwitch.current={
     requestedId:requested,previousId:projectId,fromStorage:event.type==='storage',
     primary:editedPrimary.current,secondary:editedDock.current,
    };
    if(event.type==='storage'){
     window.dispatchEvent(new Event('pilotodin:project-changed'));
    }
    // For a same-tab project-change, this event continues into App directly.
    return;
   }
   // Backend-confirmed removal and unedited changes retain earlier handling.
   editedDock.current=null;
   editedPrimary.current=null;
   if(event.type==='storage'){
    // Primary Studio does not listen directly to cross-tab storage events.
    window.dispatchEvent(new Event('pilotodin:project-changed'));
    return;
   }
   setProjectId(requested);
   void refreshProjects();
  };
  window.addEventListener('pilotodin:project-changed',reviewProject,true);
  window.addEventListener('storage',reviewProject,true);
  return()=>{
   window.removeEventListener('pilotodin:project-changed',reviewProject,true);
   window.removeEventListener('storage',reviewProject,true);
  };
 },[projectId,dock.secondary,workspaceReady,refreshProjects]);
 useEffect(()=>{
  // Cancel a same-document hash push BEFORE the browser inserts history.
  // replaceState in hashchange can only rewrite a duplicate, not remove it.
  // Keep the after-commit guard for unsupported APIs and history traversals.
  const beforeRoutePush=(event:Event)=>{
   const nav=event as Event&{navigationType?:string;destination?:{url:string}};
   if(!event.cancelable||nav.navigationType!=='push'||!nav.destination)return;
   let destination:URL;
   try{destination=new URL(nav.destination.url,window.location.href)}catch{return}
   const here=window.location;
   if(destination.origin!==here.origin||destination.pathname!==here.pathname||destination.search!==here.search)return;
   if(destination.hash===acceptedRouteHash.current)return;
   if(preapprovedRoutePush.current!==destination.hash)preapprovedRoutePush.current=null;
   if(preapprovedRoutePush.current===destination.hash)return;
   const requested=routeViewFromHash(destination.hash);
   const primaryExit=needsPrimaryStudioExitApproval(editedPrimary.current,projectId,active,requested,workspaceReady);
   const dockPromotion=planExternalRouteActivation(active,requested,dock.secondary,editedDock.current,projectId,workspaceReady);
   if(!primaryExit&&dockPromotion!=='confirm-promote')return;
   if(primaryExit&&active==='deliver'&&isDesktop()){
    // Cancel an unapproved hash PUSH before it enters browser history.
    // The existing native one-use shell guard owns any later route commit.
    event.preventDefault();
    navigateWithDockGuard(requested);
    return;
   }
   if(!window.confirm(primaryExit?primaryExitMessage(active):
    'You changed fields in the docked workspace. This action may discard those entries. Continue?')){
    event.preventDefault();
    return;
   }
   // Only the next commit of this precise hash may reuse this consent.
   preapprovedRoutePush.current=destination.hash;
  };
  const navigationAPI=(window as Window&{navigation?:EventTarget}).navigation;
  navigationAPI?.addEventListener('navigate',beforeRoutePush);
  // Capture runs before Studio's ordinary hash listeners even if they were registered first.
  // URL/history actions are already committed by the browser, so Cancel replaces the hash
  // in the current history entry before any workspace listener sees the destination.
  const reviewRoute=()=>{
   const requestedHash=window.location.hash;
   // Both internal route-commit and later hashchange may report the same URL.
   // Ignore repeat delivery even if React has not yet rendered its new active view.
   if(requestedHash===acceptedRouteHash.current)return;
   const requested=routeView();
   const decision=planExternalRouteActivation(active,requested,dock.secondary,editedDock.current,projectId,workspaceReady);
   const primaryExit=needsPrimaryStudioExitApproval(editedPrimary.current,projectId,active,requested,workspaceReady);
   const alreadyApproved=preapprovedRoutePush.current===requestedHash;
   preapprovedRoutePush.current=null;
   if(primaryExit&&!alreadyApproved&&active==='deliver'&&isDesktop()){
    // A hashchange/history traversal may be committed before the shell sees it.
    // Restore the accepted URL and Studio page synchronously, leaving dirty
    // Deliver mounted. Only an approved native dialog may initiate a new push.
    const restore=acceptedRouteHash.current||'#/studio/deliver';
    window.history.replaceState(window.history.state,'',window.location.pathname+window.location.search+restore);
    window.dispatchEvent(new Event('pilotodin:route-reverted'));
    navigateWithDockGuard(requested);
    return;
   }
   if((primaryExit||decision==='confirm-promote')&&!alreadyApproved&&!window.confirm(
     primaryExit?primaryExitMessage(active):
      'You changed fields in the docked workspace. This action may discard those entries. Continue?')){
    const restore=acceptedRouteHash.current||(active==='investigate'?'#/canvas':`#/studio/${active}`);
    window.history.replaceState(window.history.state,'',window.location.pathname+window.location.search+restore);
    // replaceState does not fire hashchange. Tell the primary Studio to resync its
    // own displayed stage from the accepted URL after a rejected navigation.
    window.dispatchEvent(new Event('pilotodin:route-reverted'));
    return;
   }
   if(primaryExit)editedPrimary.current=null;
   if(decision!=='unchanged'){
    editedDock.current=null;
    setDock(current=>nextDockLayout(current,{kind:'close'}));
   }
   acceptedRouteHash.current=requestedHash;
   // This is the sole URL -> active workspace commit. No unguarded listener
   // can activate an edited dock after a cancelled navigation.
   if(requested!==active)setActive(requested);
  };
  // Direct hash changes and internal route commits share one guarded handler.
  // The accepted hash prevents duplicate confirmation on delayed hashchange.
  window.addEventListener('hashchange',reviewRoute,true);
  window.addEventListener('pilotodin:route-commit',reviewRoute,true);
  return()=>{
   navigationAPI?.removeEventListener('navigate',beforeRoutePush);
   window.removeEventListener('hashchange',reviewRoute,true);
   window.removeEventListener('pilotodin:route-commit',reviewRoute,true);
  };
 },[active,dock.secondary,projectId,workspaceReady]);
 const shownTabs=useMemo(()=>restoredFor===projectId?openTabs.filter(isWorkspaceView):[],[openTabs,restoredFor,projectId]);
 const currentTabsSignatureRef=useRef('');
 currentTabsSignatureRef.current=shownTabs.join('|');
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
 const markPrimaryDraftEdited=(view:View)=>{
  if(workspaceReady&&projectId&&(view==='understand'||view==='prepare'||view==='model'||view==='predict'||view==='deliver'))editedPrimary.current={projectId,view};
 };
 const clearPrimaryDraft=(view:View)=>{
  if(editedPrimary.current?.projectId===projectId&&editedPrimary.current?.view===view)
   editedPrimary.current=null;
 };
 // Rust vetoes an OS CloseRequested before sending a one-use ticket here.
 // Keep the latest project/form context without reinstalling the listener on
 // each edit. A failed/missing JS listener cannot bypass Rust's native veto.
 const nativeCloseContext=useRef({projectId,workspaceReady,active,secondary:dock.secondary});
 nativeCloseContext.current={projectId,workspaceReady,active,secondary:dock.secondary};
 useEffect(()=>{
  if(!isDesktop())return;
  let disposed=false;
  let unlisten:(()=>void)|undefined;
  void listen<NativeCloseRequest>(NATIVE_CLOSE_EVENT,({payload})=>{
   void resolveNativeCloseRequest(payload,()=>{
    const state=nativeCloseContext.current;
    return hasUnsavedWorkspaceDraftForUnload(state.projectId,state.workspaceReady,
     state.active,editedPrimary.current,editedDock.current,state.secondary);
   },(_message,token)=>invoke<boolean>('confirm_native_close',{token}),
   (token,approve)=>invoke<void>('resolve_native_close_request',{token,approve}))
   .catch(error=>{
    console.error('[PilotODIN native close] confirmation or resolution failed',error);
    setWarning('Native close confirmation could not be completed. Your workspace remains open.');
   });
  }).then(stop=>{
   if(disposed)stop();else unlisten=stop;
  }).catch(()=>setWarning('Native close protection could not be registered. Closing is blocked for safety.'));
  return()=>{disposed=true;unlisten?.()};
 },[]);
 // Browser reload/navigation and WebView close (where supported) must ask before
 // losing live form edits. The user can stay and keep the mounted in-memory draft;
 // consenting to leave does not persist draft values or mutate the dataset.
 useEffect(()=>{
  const onBeforeUnload=(event:BeforeUnloadEvent)=>{
   if(!hasUnsavedWorkspaceDraftForUnload(projectId,workspaceReady,active,
    editedPrimary.current,editedDock.current,dock.secondary))return;
   event.preventDefault();
   event.returnValue=''; // Legacy confirmation requirement in Chromium/WebView.
  };
  window.addEventListener('beforeunload',onBeforeUnload);
  return()=>window.removeEventListener('beforeunload',onBeforeUnload);
 },[projectId,workspaceReady,active,dock.secondary]);
 // Keep dropped files and links from navigating the WebView away from the
 // workspace. The file input can still accept files and tabs use custom types.
 useEffect(()=>{
  const preventDropNavigation=(event:DragEvent)=>{
   const types=event.dataTransfer?.types;
   const fileDrop=types?.includes('Files');
   const fileInput=event.target instanceof HTMLInputElement&&event.target.type==='file';
   if(fileDrop&&fileInput)return;
   if(fileDrop||types?.includes('text/uri-list')){
    event.preventDefault();
   }
  };
  window.addEventListener('dragover',preventDropNavigation);
  window.addEventListener('drop',preventDropNavigation);
  return()=>{
   window.removeEventListener('dragover',preventDropNavigation);
   window.removeEventListener('drop',preventDropNavigation);
  };
 },[]);
 const confirmProjectDraftDiscard=():boolean=>{
  // A single prompt covers both forms when both are edited.
  if(editedPrimary.current?.projectId!==projectId)return confirmEditedDockDiscard('switch-project');
  const dockDirty=needsDockInputDiscardApproval(editedDock.current,projectId,dock.secondary,'switch-project');
  return window.confirm(dockDirty
   ?'You changed fields in the primary and docked workspaces. Switching projects may discard those entries. Continue?'
   :'You changed fields in the primary workspace. Switching projects may discard those entries. Continue?');
 };
 // The primary App has its own local go() path; it must consult the shell BEFORE
 // committing a route which would activate (and therefore unmount) its edited dock.
 const approvePrimaryStudioNavigation=(view:View,afterNavigate?:()=>void):boolean=>{
  if(!workspaceReady)return false;
  if(needsPrimaryStudioExitApproval(editedPrimary.current,projectId,active,view,workspaceReady)){
   if(active==='deliver'&&isDesktop()){
    // Studio's go() is synchronous. The shell owns the one-use native dialog,
    // route commit and optional importer action after explicit permission.
    // Return false now so App cannot mutate or unmount the dirty report.
    navigateWithDockGuard(view,afterNavigate);
    return false;
   }
   if(!window.confirm(primaryExitMessage(active)))return false;
   preapprovedRoutePush.current=`#/studio/${view}`;
  }
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
 const navigateWithDockGuard=(view:View,afterNavigate?:()=>void,nativeApproved=false):boolean=>{
  const primaryExit=needsPrimaryStudioExitApproval(editedPrimary.current,projectId,active,view,workspaceReady);
  if(primaryExit){
   if(!nativeApproved&&active==='deliver'&&isDesktop()){
    // Native approval is asynchronous; no route, draft or importer changes first.
    if(nativeDeliverExitPending.current)return false;
    const sourceProject=projectId,sourceView=active,sourceHash=window.location.hash;
    const ticket=++nativeDeliverExitTicket.current;
    nativeDeliverExitPending.current=true;
    void invoke<boolean>('confirm_native_deliver_exit').then(approved=>{
     if(ticket!==nativeDeliverExitTicket.current)return;
     nativeDeliverExitPending.current=false;
     if(!approved||currentProjectRef.current!==sourceProject||
      currentActiveRef.current!==sourceView||window.location.hash!==sourceHash||
      editedPrimary.current?.projectId!==sourceProject||editedPrimary.current?.view!=='deliver')return;
     navigateWithDockGuard(view,afterNavigate,true);
    }).catch(()=>{
     if(ticket!==nativeDeliverExitTicket.current)return;
     nativeDeliverExitPending.current=false;
     setWarning('Could not show the Windows Deliver confirmation. Your unsaved report was kept.');
    });
    return false;
   }
   if(!nativeApproved&&!window.confirm(primaryExitMessage(active)))return false;
  }
  if(view!==active&&dock.secondary===view&&isSecondaryView(view)){
   if(!confirmEditedDockDiscard('activate',view))return false;
   editedDock.current=null;
   setDock(current=>nextDockLayout(current,{kind:'close'}));
  }
  // Set route-specific preapproval only after all navigation guards pass.
  if(primaryExit)preapprovedRoutePush.current=view==='investigate'?'#/canvas':`#/studio/${view}`;
  navigate(view);
  afterNavigate?.();
  return true;
 };
 // Primary Studio may load projects directly from its selector, Home cards or
 // import completion. Authorize BEFORE App clears its project-specific state.
 // Upload preflight must run before the API creates a dataset. Consent itself
 // does not discard the edited-dock marker: failed imports leave drafts guarded.
 const approvePrimaryProjectUpload=():boolean=>{
  if(!workspaceReady)return false;
  return confirmProjectDraftDiscard();
 };
 const commitPrimaryUploadedProject=()=>{editedDock.current=null;editedPrimary.current=null;};
 const commitPrimaryLoadedProject=(id:string,snapshot:PrimaryProjectLoadSnapshot)=>{
  if(pendingExternalSwitch.current?.requestedId===id){
   // The old A Studio remains mounted until BOTH B reads succeeded. This
   // snapshot is consumed by the one new B instance; never store it on disk.
   primaryProjectHandoff.current=snapshot;
   pendingExternalSwitch.current=null;
   editedPrimary.current=null;editedDock.current=null;
   setNewProjectOpen(false);
   // Only commit shell identity after App has successfully read both B GETs.
   setProjectId(id);
   void refreshProjects();
  }else editedPrimary.current=null;
 };
 const consumePrimaryProjectHandoff=(id:string)=>{
  if(primaryProjectHandoff.current?.id===id)primaryProjectHandoff.current=null;
 };
 const failPrimaryProjectLoad=(id:string)=>{
  const pending=pendingExternalSwitch.current;
  if(!pending||pending.requestedId!==id)return;
  pendingExternalSwitch.current=null;
  // App never reset its mounted A form on a failed GET. Keep those markers.
  editedPrimary.current=pending.primary;editedDock.current=pending.secondary;
  if(!pending.fromStorage){
   try{
    if(localStorage.getItem('pilotodin-current')===id)
     localStorage.setItem('pilotodin-current',pending.previousId);
   }catch{setWarning('Could not restore project selection; this window retains its unsaved workspace.')}
  }
  setWarning(pending.fromStorage
   ?'The other tab selected a project that could not be opened here. This window retains its unsaved workspace; reloading may use the other tab’s selection.'
   :'The selected project could not be opened. This window retains its unsaved workspace.');
 };
 const approvePrimaryProjectLoad=(id:string):boolean=>{
  if(!id||!workspaceReady)return false;
  if(id===projectId)return true;
  // Approval was already granted for this exact external project event.
  if(pendingExternalSwitch.current?.requestedId===id)return true;
  if(!confirmProjectDraftDiscard())return false;
  editedDock.current=null;
  return true;
 };
 const metadataChanged=(next:ManagedProject)=>{
  // Only an identity/version hint crosses windows; consumers verify with HTTP.
  publishProjectLifecycleSignal({id:next.id,revision:next.revision,archived:next.archived_at!==null});
  void refreshProjects();
  window.dispatchEvent(new CustomEvent('pilotodin:project-metadata-changed',
   {detail:{id:next.id,name:next.name,filename:next.filename,archived:next.archived_at!==null}}));
 };
 const chooseProject=(id:string,approvedNative=false)=>{
  if(!id||id===projectId||!workspaceReady)return;
  // A previous approval for this exact in-flight read is not a second switch.
  if(pendingExternalSwitch.current?.requestedId===id)return;
  if(nativeProjectSwitchPromptPending.current&&!approvedNative)return;
  const hasDraft=editedPrimary.current?.projectId===projectId||
   needsDockInputDiscardApproval(editedDock.current,projectId,dock.secondary,'switch-project');
  if(!approvedNative&&isDesktop()&&hasDraft){
   // Native system consent is asynchronous; cancellation or failure keeps the
   // current project and draft mounted. Ignore replies to stale project IDs.
   nativeProjectSwitchPromptPending.current=true;
   setNativeProjectSwitchWaiting(true);
   const origin=projectId;
   void invoke<boolean>('confirm_native_project_switch').then(approved=>{
    nativeProjectSwitchPromptPending.current=false;
    setNativeProjectSwitchWaiting(false);
    if(!approved||currentProjectRef.current!==origin||
      pendingExternalSwitch.current!==null)return;
    chooseProject(id,true);
   }).catch(()=>{
    nativeProjectSwitchPromptPending.current=false;
    setNativeProjectSwitchWaiting(false);
    setWarning('Could not show the Windows unsaved-changes confirmation. Your current project and edits were kept.');
   });
   return;
  }
  if(!approvedNative){
   if(!confirmProjectDraftDiscard())return;
  }
  // Do not write shared selection or unmount A before both B GETs succeed.
  // Keep primary/dock edits and the import panel mounted if B fails.
  pendingExternalSwitch.current={
   requestedId:id,previousId:projectId,fromStorage:false,
   primary:editedPrimary.current,secondary:editedDock.current,
  };
  window.dispatchEvent(new CustomEvent('pilotodin:primary-project-load-requested',
   {detail:{projectId:id}}));
 };
 const sidebarViews=useMemo(()=>NAV_SECTIONS.flatMap(section=>section.ids),[]);
 const onSidebarKeyDown=(event:ReactKeyboardEvent<HTMLButtonElement>,view:View)=>{
  if(event.altKey||event.ctrlKey||event.metaKey||event.shiftKey)return;
  const next=nextSidebarViewByKey(sidebarViews,view,event.key);
  if(!next)return;
  event.preventDefault();
  const buttons=event.currentTarget.closest('#po-nav-items')?.querySelectorAll<HTMLButtonElement>('.po-nav-item');
  const target=buttons?.item(sidebarViews.indexOf(next));
  if(next!==active){navigateWithDockGuard(next,()=>target?.focus());return;}
  target?.focus();
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
  const tabButtons=event.currentTarget.closest('[role="tablist"]')?.querySelectorAll<HTMLButtonElement>('[role="tab"]');
  const target=tabButtons?.item(shownTabs.indexOf(next));
  if(next!==active){navigateWithDockGuard(next,()=>target?.focus());return;}
  target?.focus();
 };
 const close=(view:View,nativeApproved=false)=>{
  if(!workspaceReady)return;
  // A second tab click cannot bypass another outstanding native Deliver prompt.
  if(!nativeApproved&&isDesktop()&&nativeDeliverExitPending.current)return;
  const plan=planWorkspaceTabClose(shownTabs,active,view);
  if(!plan)return;
  const primaryExit=plan.nextActive!==active&&
   needsPrimaryStudioExitApproval(editedPrimary.current,projectId,active,plan.nextActive,workspaceReady);
  if(primaryExit&&!nativeApproved&&active==='deliver'&&isDesktop()){
   // The same main-window Rust dialog protects both navigation and tab close.
   // Approval may only close the original tab under the original tab layout.
   const originProject=projectId,originHash=window.location.hash;
   const originTabs=shownTabs.join('|'),originDock=dock.secondary;
   const ticket=++nativeDeliverExitTicket.current;
   nativeDeliverExitPending.current=true;
   void invoke<boolean>('confirm_native_deliver_exit').then(approved=>{
    if(ticket!==nativeDeliverExitTicket.current)return;
    nativeDeliverExitPending.current=false;
    if(!approved||currentProjectRef.current!==originProject||
       currentActiveRef.current!=='deliver'||window.location.hash!==originHash||
       editedPrimary.current?.projectId!==originProject||editedPrimary.current?.view!=='deliver'||
       currentTabsSignatureRef.current!==originTabs||
       currentDockSecondaryRef.current!==originDock)return;
    // Re-run every remaining dock guard before mutating the tab or route.
    close(view,true);
   }).catch(()=>{
    if(ticket!==nativeDeliverExitTicket.current)return;
    nativeDeliverExitPending.current=false;
    setWarning('Could not show the Windows Deliver tab-close confirmation. Your unsaved report was kept.');
   });
   return;
  }
  if(dock.secondary===view&&!confirmEditedDockDiscard('close-tab'))return;
  if(plan.nextActive!==active&&dock.secondary===plan.nextActive&&isSecondaryView(plan.nextActive)&&!confirmEditedDockDiscard('activate',plan.nextActive))return;
  if(primaryExit){
   if(!nativeApproved&&!window.confirm(primaryExitMessage(active)))return;
   // Only the next exact route is authorised, never future workspace changes.
   preapprovedRoutePush.current=plan.nextActive==='investigate'?'#/canvas':`#/studio/${plan.nextActive}`;
  }
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
 const [primaryDockHover,setPrimaryDockHover]=useState(false);
 // A tab dragged over the workspace itself should dock here. The tab strip
 // remains an independent reorder target; foreign files/URLs never dock.
 const canDockOverPrimary=(event:ReactDragEvent)=>{
  const dragged=draggedTab.current;
  return !!projectId&&workspaceReady&&!!dragged&&dragged.projectId===projectId&&
   isSecondaryView(dragged.view)&&dragged.view!==active&&
   Array.from(event.dataTransfer.types).includes('text/x-pilotodin-workspace');
 };
 const onPrimaryDragOver=(event:ReactDragEvent<HTMLElement>)=>{
  if(!canDockOverPrimary(event))return;
  event.preventDefault();event.stopPropagation();
  event.dataTransfer.dropEffect='move';
  setPrimaryDockHover(true);
 };
 const onPrimaryDragLeave=(event:ReactDragEvent<HTMLElement>)=>{
  if(!event.currentTarget.contains(event.relatedTarget as Node|null))setPrimaryDockHover(false);
 };
 const onPrimaryDrop=(event:ReactDragEvent<HTMLElement>)=>{
  if(!canDockOverPrimary(event))return;
  event.preventDefault();event.stopPropagation();
  const view=draggedTab.current!.view;
  setPrimaryDockHover(false);
  draggedTab.current=null;setTabDropTarget(null);
  dockView(view);
 };
 const onDrop=(event:ReactDragEvent)=>{
  event.preventDefault();
  const proposed=event.dataTransfer.getData('text/x-pilotodin-workspace');
  if(isSecondaryView(proposed))dockView(proposed);
  draggedTab.current=null;
  setPrimaryDockHover(false);
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
   <ShellClock/>
   <div className="po-project-switcher">
    <Database className="po-project-switcher-icon" size={16} aria-hidden="true"/>
    <select aria-label="Switch project" title={selectorLabels.get(projectId)??(projects.length?'Switch between imported projects':'Import another dataset to switch between projects')} value={projectId} disabled={nativeProjectSwitchWaiting} onChange={e=>chooseProject(e.target.value)}>
     <option value="" disabled>{projects.length?"Select an imported project":"No projects imported yet"}</option>
     {heldArchivedId===projectId&&!!projectId&&!projects.some(p=>p.id===projectId)&&<option value={projectId} disabled>Archived in another window (restore to continue)</option>}
     {projects.map(p=><option key={p.id} value={p.id}>{selectorLabels.get(p.id)??p.name}</option>)}
    </select>
    <ChevronDown className="po-project-switcher-arrow" size={16} aria-hidden="true"/>
   </div>
   <button type="button" className="po-new-project-action" title="Import a CSV or Excel file as a separate project" aria-label="New project: import dataset" onClick={()=>navigateWithDockGuard('overview',()=>setNewProjectOpen(true))}><Plus size={16} aria-hidden="true"/><span>New project</span></button>
   <button type="button" className="po-manage-project-action" title="Rename, archive or restore projects" aria-label="Manage projects" onClick={()=>setProjectManagerOpen(true)}><Settings2 size={16} aria-hidden="true"/><span>Manage</span></button>
  </header>
  {projectManagerOpen&&<ProjectManager currentProjectId={projectId} onClose={()=>setProjectManagerOpen(false)} onChanged={metadataChanged}/>}
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
     {shownTabs.map(view=><div className={`po-tab ${active===view?'po-tab-selected':''} ${tabDropTarget?.view===view?`po-tab-drop-${tabDropTarget.side}`:''}`} key={view} draggable={!!projectId&&workspaceReady} onDragStart={event=>{draggedTab.current={projectId,view};event.dataTransfer.effectAllowed='move';event.dataTransfer.setData('text/x-pilotodin-tab',view);if(isSecondaryView(view))event.dataTransfer.setData('text/x-pilotodin-workspace',view)}} onDragOver={event=>onTabDragOver(event,view)} onDrop={event=>onTabDrop(event,view)} onDragEnd={()=>{draggedTab.current=null;setTabDropTarget(null);setPrimaryDockHover(false)}}>
      <button type="button" role="tab" id={`po-workspace-tab-${view}`} aria-controls="po-current-workspace" aria-selected={active===view} tabIndex={active===view?0:-1} onKeyDown={event=>onWorkspaceTabKeyDown(event,view)} onClick={()=>navigateWithDockGuard(view)} title="Drag to reorder; Alt+Shift+Left/Right moves this tab">{labelFor(view)}</button>
      {projectId&&isSecondaryView(view)&&<button type="button" title={`Dock ${labelFor(view)} beside current view`} aria-label={`Dock ${labelFor(view)} beside current view`} onClick={()=>dockView(view)}><Columns2 size={13}/></button>}
      {shownTabs.length>1&&<button type="button" aria-label={`Close ${labelFor(view)} tab`} onClick={()=>close(view)}><X size={12}/></button>}
     </div>)}
     <div className="po-tab-spacer"/>
     <button type="button" className="po-reset-layout" title="Reset workspace layout" aria-label="Reset workspace layout" onClick={()=>{if(!confirmEditedDockDiscard('reset'))return;editedDock.current=null;setDock(nextDockLayout(dock,{kind:'reset'}))}}><RotateCcw size={14}/></button>
    </div>
    {warning&&<p className="po-shell-warning" role="status">{warning}</p>}
    <div className={`po-pane-layout ${canSplit?'po-pane-split':''} ${dock.side==='left'?'po-dock-left':''}`} ref={splitRef} style={paneStyle}>
     <section className={`po-primary-pane ${primaryDockHover?'po-primary-dock-hover':''}`} id="po-current-workspace" role="tabpanel" aria-labelledby={`po-workspace-tab-${active}`} tabIndex={0} onDragOver={onPrimaryDragOver} onDragLeave={onPrimaryDragLeave} onDrop={onPrimaryDrop}>
      <div className="po-pane-content" key={`primary-${projectId}-${active==='investigate'?'canvas':'studio'}`}>
       {workspaceReady?(active==='investigate'?<InvestigationCanvas key={`canvas-${projectId}`}/>:<App key={`studio-${projectId}`} onPrimaryNavigate={approvePrimaryStudioNavigation} onBeforePrimaryProjectLoad={approvePrimaryProjectLoad} onBeforePrimaryProjectUpload={approvePrimaryProjectUpload} onPrimaryUploadedProjectCommitted={commitPrimaryUploadedProject} onPrimaryDraftEdited={markPrimaryDraftEdited} onPrimaryDraftCleared={clearPrimaryDraft} onPrimaryProjectLoaded={commitPrimaryLoadedProject} onPrimaryProjectLoadFailed={failPrimaryProjectLoad} primaryProjectHandoff={primaryProjectHandoff.current?.id===projectId?primaryProjectHandoff.current:undefined} onPrimaryProjectHandoffConsumed={consumePrimaryProjectHandoff} forceNewProject={newProjectOpen&&active==='overview'} onNewProjectClose={()=>setNewProjectOpen(false)}/>):<div className="po-pane-placeholder" role="status"><Database size={26}/><strong>{catalogState==='loading'?'Checking available projects':catalogState==='failed'?'Project catalogue unavailable':'Restoring project workspace'}</strong><p>{catalogState==='failed'?warning:catalogState==='ready'?'Restoring this project’s saved tabs and dock before loading its data.':'Checking that the saved project belongs to this local workspace before loading its data.'}</p>{catalogState==='failed'&&<button type="button" className="ud-btn ud-btn-primary" onClick={()=>{setCatalogState('loading');void refreshProjects()}}>Retry project check</button>}</div>}
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
