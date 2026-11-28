const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const ts=require('typescript');

const root=path.resolve(__dirname,'../src');
const shell=fs.readFileSync(path.join(root,'UnifiedShell.tsx'),'utf8');
const rust=fs.readFileSync(path.resolve(root,'../src-tauri/src/lib.rs'),'utf8');
const begin=shell.indexOf(' const navigateWithDockGuard=');
const end=shell.indexOf(' // Primary Studio may load projects directly',begin);
assert.ok(begin>0&&end>begin&&end-begin<4500,'specific shell navigation handler present');
const compiled=ts.transpileModule(shell.slice(begin,end)+'\nexports.navigateWithDockGuard=navigateWithDockGuard;',{
 compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2021},reportDiagnostics:true
});
assert.equal((compiled.diagnostics||[]).filter(d=>d.category===ts.DiagnosticCategory.Error).length,0);

const flush=()=>new Promise(resolve=>setImmediate(resolve));
function harness({native=true,response=false,reject=false,deferred=false,dirty=true}={}){
 const calls={ipc:[],browser:[],routes:[],warnings:[],after:[],dock:[]};
 const projectId='A',active='deliver';
 const editedPrimary={current:dirty?{projectId,view:'deliver'}:null};
 const currentProjectRef={current:projectId};
 const currentActiveRef={current:active};
 const preapprovedRoutePush={current:null};
 const nativeDeliverExitPending={current:false};
 const nativeDeliverExitTicket={current:0};
 const window={location:{hash:'#/studio/deliver'},confirm:(message)=>{
  calls.browser.push(message);
  return response;
 }};
 let release;
 const held=new Promise(resolve=>{release=resolve;});
 const invoke=(command)=>{
  calls.ipc.push(command);
  if(reject)return Promise.reject(new Error('synthetic native IPC failure'));
  return deferred?held:Promise.resolve(response);
 };
 const names=[
  'projectId','active','workspaceReady','editedPrimary','needsPrimaryStudioExitApproval',
  'isDesktop','nativeDeliverExitPending','nativeDeliverExitTicket','window','invoke',
  'currentProjectRef','currentActiveRef','setWarning','dock','isSecondaryView',
  'confirmEditedDockDiscard','setDock','nextDockLayout','preapprovedRoutePush',
  'primaryExitMessage','navigate','exports'
 ];
 const values=[
  projectId,active,true,editedPrimary,
  (edited,id,view,target,ready)=>ready&&edited?.projectId===id&&edited?.view===view&&view==='deliver'&&target!==view,
  ()=>native,nativeDeliverExitPending,nativeDeliverExitTicket,window,invoke,
  currentProjectRef,currentActiveRef,message=>calls.warnings.push(message),
  {secondary:null},()=>false,()=>true,()=>calls.dock.push('reset'),()=>({secondary:null}),
  preapprovedRoutePush,()=> 'Your Deliver report contains unsaved changes',
  next=>calls.routes.push(next),{}
 ];
 const bound=new Function(...names,compiled.outputText+'\nreturn exports.navigateWithDockGuard;')(...values);
 const doNavigate=(target='overview')=>bound(target,()=>calls.after.push(target));
 return {calls,doNavigate,release,window,editedPrimary,currentProjectRef,currentActiveRef,
  nativeDeliverExitPending,nativeDeliverExitTicket,preapprovedRoutePush};
}

test('native Deliver Stay never changes route or starts New project importer',async()=>{
 const h=harness({response:false});
 assert.equal(h.doNavigate(),false);
 assert.equal(h.nativeDeliverExitPending.current,true);
 assert.equal(h.preapprovedRoutePush.current,null);
 await flush();
 assert.deepEqual(h.calls.ipc,['confirm_native_deliver_exit']);
 assert.deepEqual(h.calls.routes,[]);
 assert.deepEqual(h.calls.after,[]);
 assert.deepEqual(h.calls.browser,[]);
 assert.equal(h.nativeDeliverExitPending.current,false);
});

test('explicit native Deliver approval commits exactly requested route and deferred importer action',async()=>{
 const h=harness({response:true});
 assert.equal(h.doNavigate('overview'),false);
 assert.deepEqual(h.calls.routes,[]);
 assert.deepEqual(h.calls.after,[]);
 await flush();
 assert.deepEqual(h.calls.routes,['overview']);
 assert.deepEqual(h.calls.after,['overview']);
 assert.equal(h.preapprovedRoutePush.current,'#/studio/overview');
 assert.equal(h.calls.ipc.length,1);
 assert.deepEqual(h.calls.browser,[]);
});

test('native IPC failure fails closed with visible status, not browser confirm fallback',async()=>{
 const h=harness({reject:true});
 assert.equal(h.doNavigate('explore'),false);
 await flush();
 assert.deepEqual(h.calls.routes,[]);
 assert.deepEqual(h.calls.after,[]);
 assert.equal(h.preapprovedRoutePush.current,null);
 assert.equal(h.calls.browser.length,0);
 assert.match(h.calls.warnings.join(' '),/Your unsaved report was kept/);
});

test('pending native consent ignores other route requests',async()=>{
 const h=harness({deferred:true});
 assert.equal(h.doNavigate('overview'),false);
 assert.equal(h.doNavigate('investigate'),false);
 assert.deepEqual(h.calls.ipc,['confirm_native_deliver_exit']);
 h.release(true);await flush();
 assert.deepEqual(h.calls.routes,['overview']);
 assert.deepEqual(h.calls.after,['overview']);
});

test('stale project, view, hash or edited marker vetoes late approval',async()=>{
 for(const invalidate of [
  h=>{h.currentProjectRef.current='B';},
  h=>{h.currentActiveRef.current='explore';},
  h=>{h.window.location.hash='#/studio/explore';},
  h=>{h.editedPrimary.current=null;},
  h=>{h.nativeDeliverExitTicket.current++;}
 ]){
  const h=harness({deferred:true});
  h.doNavigate('overview');invalidate(h);h.release(true);await flush();
  assert.deepEqual(h.calls.routes,[]);
  assert.deepEqual(h.calls.after,[]);
  assert.equal(h.preapprovedRoutePush.current,null);
 }
});

test('non-native browser fallback remains synchronous and requires explicit consent',()=>{
 const no=harness({native:false,response:false});
 assert.equal(no.doNavigate('overview'),false);
 assert.equal(no.calls.ipc.length,0);
 assert.equal(no.calls.browser.length,1);
 assert.deepEqual(no.calls.routes,[]);
 const yes=harness({native:false,response:true});
 assert.equal(yes.doNavigate('overview'),true);
 assert.deepEqual(yes.calls.routes,['overview']);
 assert.deepEqual(yes.calls.after,['overview']);
 assert.equal(yes.preapprovedRoutePush.current,'#/studio/overview');
});

test('source connects shell header and keyboard focus to deferred action on actual route approval',()=>{
 assert.match(shell,/onClick=\{\(\)=>navigateWithDockGuard\('overview',\(\)=>setNewProjectOpen\(true\)\)\}/);
 assert.match(shell,/navigateWithDockGuard\(next,\(\)=>target\?\.focus\(\)\)/);
 assert.match(shell,/if\(primaryExit\)preapprovedRoutePush\.current=/);
 assert.match(shell,/if\(ticket!==nativeDeliverExitTicket\.current\)return/);
});

test('Rust native dialog is main-window-only, warning, explicit and off the WebView thread',()=>{
 const start=rust.indexOf('async fn confirm_native_deliver_exit(');
 const end=rust.indexOf('#[derive(Deserialize)]',start);
 assert.ok(start>0&&end>start,'specific native command exists');
 const fn=rust.slice(start,end);
 assert.match(fn,/window\.label\(\) != "main"/);
 assert.match(fn,/MessageDialogKind::Warning/);
 assert.match(fn,/Leave Deliver/);
 assert.match(fn,/Keep editing/);
 assert.match(fn,/spawn_blocking\(move \|\| prompt\.blocking_show\(\)\)/);
 assert.match(rust,/confirm_native_deliver_exit\s*\]/);
});
