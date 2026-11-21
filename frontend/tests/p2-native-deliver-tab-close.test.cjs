const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const ts=require('typescript');
const Module=require('node:module');

const frontend=path.resolve(__dirname,'../src');
const source=fs.readFileSync(path.join(frontend,'UnifiedShell.tsx'),'utf8');
function loadPlanner(){
 const p=path.join(frontend,'workspaceTabCloseFocus.ts');
 const compiled=ts.transpileModule(fs.readFileSync(p,'utf8'),{
  compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2021},
  reportDiagnostics:true
 });
 assert.equal((compiled.diagnostics||[]).filter(d=>d.category===ts.DiagnosticCategory.Error).length,0);
 const mod=new Module(p,module);mod.filename=p;mod.paths=module.paths;
 mod._compile(compiled.outputText,p);
 return mod.exports.planWorkspaceTabClose;
}
const planWorkspaceTabClose=loadPlanner();
const begin=source.indexOf(' const close=(view:View,nativeApproved=false)=>{');
const end=source.indexOf(' const closeDock=()=>{',begin);
assert.ok(begin>0&&end>begin&&end-begin<4700,'actual native guarded tab-close code');
const compiled=ts.transpileModule(source.slice(begin,end)+'\nexports.close=close;',{
 compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2021},
 reportDiagnostics:true
});
assert.equal((compiled.diagnostics||[]).filter(d=>d.category===ts.DiagnosticCategory.Error).length,0);
const settle=()=>new Promise(resolve=>setImmediate(resolve));

function harness({native=true,answer=false,fail=false,held=false,dirty=true,tab=['explore','deliver'],dockView=null}={}){
 const events={ipc:[],browser:[],tabs:[],routes:[],dock:[],warnings:[],focus:[],confirmDock:[]};
 const projectId='A',active='deliver';
 const shownTabs=tab;
 const dock={secondary:dockView};
 const editedPrimary={current:dirty?{projectId:'A',view:'deliver'}:null};
 const editedDock={current:dockView?{projectId:'A',view:dockView}:null};
 const currentProjectRef={current:projectId};
 const currentActiveRef={current:active};
 const currentTabsSignatureRef={current:shownTabs.join('|')};
 const currentDockSecondaryRef={current:dock.secondary};
 const nativeDeliverExitTicket={current:0};
 const nativeDeliverExitPending={current:false};
 const preapprovedRoutePush={current:null};
 const pendingCloseFocus={current:null};
 const window={
  location:{hash:'#/studio/deliver'},
  confirm(message){events.browser.push(message);return answer;}
 };
 let release;
 const deferred=new Promise((resolve)=>{release=resolve;});
 const invoke=(command)=>{
  events.ipc.push(command);
  if(fail)return Promise.reject(new Error('No native dialog'));
  return held?deferred:Promise.resolve(answer);
 };
 const names=[
  'workspaceReady','isDesktop','nativeDeliverExitPending','planWorkspaceTabClose',
  'shownTabs','active','dock','projectId','editedPrimary','needsPrimaryStudioExitApproval',
  'window','nativeDeliverExitTicket','invoke','currentProjectRef','currentActiveRef',
  'currentTabsSignatureRef','currentDockSecondaryRef','setWarning',
  'confirmEditedDockDiscard','isSecondaryView','preapprovedRoutePush',
  'primaryExitMessage','editedDock','pendingCloseFocus','setOpenTabs','navigate',
  'setDock','nextDockLayout','exports'
 ];
 const values=[
  true,()=>native,nativeDeliverExitPending,planWorkspaceTabClose,shownTabs,active,dock,projectId,
  editedPrimary,(marker,id,current,next,ready)=>!!ready&&marker?.projectId===id&&
   marker?.view===current&&current==='deliver'&&next!=='deliver',
  window,nativeDeliverExitTicket,invoke,currentProjectRef,currentActiveRef,
  currentTabsSignatureRef,currentDockSecondaryRef,msg=>events.warnings.push(msg),
  action=>{events.confirmDock.push(action);return answer;},
  view=>['prepare','model','predict','explore','quality','understand'].includes(view),
  preapprovedRoutePush,()=> 'You changed the Deliver report',
  editedDock,pendingCloseFocus,
  tabs=>events.tabs.push(tabs),view=>events.routes.push(view),
  callback=>events.dock.push(callback(dock)),(current,action)=>({...current,secondary:null}),{}
 ];
 const close=new Function(...names,compiled.outputText+'\nreturn exports.close;')(...values);
 return {close,events,release,editedPrimary,currentProjectRef,currentActiveRef,
  currentTabsSignatureRef,currentDockSecondaryRef,nativeDeliverExitPending,
  nativeDeliverExitTicket,preapprovedRoutePush,pendingCloseFocus,window};
}

test('Keep editing never closes a dirty Deliver tab or discards its primary draft',async()=>{
 const h=harness();
 h.close('deliver');
 assert.equal(h.nativeDeliverExitPending.current,true);
 assert.deepEqual(h.events.tabs,[]);
 assert.deepEqual(h.events.routes,[]);
 await settle();
 assert.deepEqual(h.events.ipc,['confirm_native_deliver_exit']);
 assert.deepEqual(h.events.browser,[]);
 assert.deepEqual(h.events.tabs,[]);
 assert.equal(h.editedPrimary.current.view,'deliver');
 assert.equal(h.pendingCloseFocus.current,null);
 assert.equal(h.nativeDeliverExitPending.current,false);
});

test('native Leave Deliver closes exactly the selected tab and preserves fallback focus',async()=>{
 const h=harness({answer:true});
 h.close('deliver');await settle();
 assert.deepEqual(h.events.ipc,['confirm_native_deliver_exit']);
 assert.deepEqual(h.events.browser,[]);
 assert.deepEqual(h.events.tabs,[['explore']]);
 assert.deepEqual(h.events.routes,['explore']);
 assert.deepEqual(h.pendingCloseFocus.current,{projectId:'A',view:'explore'});
 assert.equal(h.preapprovedRoutePush.current,'#/studio/explore');
});

test('while native modal is pending a second close click cannot bypass consent',async()=>{
 const h=harness({held:true});
 h.close('deliver');h.close('explore');h.close('deliver');
 assert.deepEqual(h.events.ipc,['confirm_native_deliver_exit']);
 assert.deepEqual(h.events.tabs,[]);
 h.release(false);await settle();
 assert.deepEqual(h.events.tabs,[]);
});

test('a stale project, active route, hash, dirty flag, layout or ticket vetoes late Leave',async()=>{
 const changes=[
  h=>{h.currentProjectRef.current='B';},
  h=>{h.currentActiveRef.current='overview';},
  h=>{h.window.location.hash='#/studio/explore';},
  h=>{h.editedPrimary.current=null;},
  h=>{h.currentTabsSignatureRef.current='deliver|quality';},
  h=>{h.currentDockSecondaryRef.current='quality';},
  h=>{h.nativeDeliverExitTicket.current++;}
 ];
 for(const change of changes){
  const h=harness({held:true});
  h.close('deliver');change(h);h.release(true);await settle();
  assert.deepEqual(h.events.tabs,[]);
  assert.deepEqual(h.events.routes,[]);
  assert.deepEqual(h.events.browser,[]);
  assert.equal(h.preapprovedRoutePush.current,null);
 }
});

test('native IPC failure fails closed with visible status, no browser prompt fallback',async()=>{
 const h=harness({fail:true});
 h.close('deliver');await settle();
 assert.deepEqual(h.events.tabs,[]);
 assert.deepEqual(h.events.routes,[]);
 assert.deepEqual(h.events.browser,[]);
 assert.match(h.events.warnings.join(' '),/unsaved report was kept/);
});

test('clean active Deliver close and inactive tab close need no unnecessary native modal',()=>{
 const clean=harness({dirty:false});
 clean.close('deliver');
 assert.deepEqual(clean.events.ipc,[]);
 assert.deepEqual(clean.events.tabs,[['explore']]);
 const inactive=harness();
 inactive.close('explore');
 assert.deepEqual(inactive.events.ipc,[]);
 assert.deepEqual(inactive.events.tabs,[['deliver']]);
 assert.deepEqual(inactive.events.routes,[]);
});

test('web fallback still requires explicit browser consent',()=>{
 const no=harness({native:false});
 no.close('deliver');
 assert.deepEqual(no.events.tabs,[]);
 assert.equal(no.events.browser.length,1);
 const yes=harness({native:false,answer:true});
 yes.close('deliver');
 assert.deepEqual(yes.events.tabs,[['explore']]);
 assert.deepEqual(yes.events.routes,['explore']);
});

test('native approval is not sufficient to bypass an edited dock promotion veto',async()=>{
 const h=harness({native:true,answer:true,dockView:'explore'});
 h.close('deliver');await settle();
 assert.deepEqual(h.events.ipc,['confirm_native_deliver_exit']);
 assert.deepEqual(h.events.confirmDock,['activate']);
 assert.deepEqual(h.events.tabs,[['explore']]);
 const denied=harness({native:true,held:true,dockView:'explore'});
 denied.close('deliver');
 denied.release(true);await settle();
 // Here the mocked dock guard itself rejects because answer is false.
 assert.deepEqual(denied.events.confirmDock,['activate']);
 assert.deepEqual(denied.events.tabs,[]);
 assert.deepEqual(denied.events.routes,[]);
});

test('the real rendered tab-close button calls the guarded close callback',()=>{
 assert.match(source,/aria-label=\{\`Close \$\{labelFor\(view\)\} tab\`\} onClick=\{\(\)=>close\(view\)\}/);
 assert.match(source,/const currentTabsSignatureRef=useRef\(''\)/);
 assert.match(source,/currentTabsSignatureRef\.current=shownTabs\.join\('\|'\)/);
 assert.match(source,/nativeDeliverExitPending\.current=true/);
 assert.match(source,/if\(primaryExit\)\{/);
 assert.doesNotMatch(source.slice(begin,end),/localStorage|sessionStorage|fetch\(|post\(|upload\(|train\(/);
});
