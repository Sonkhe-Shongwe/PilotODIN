const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const ts=require('typescript');

const shell=fs.readFileSync(path.resolve(__dirname,'../src/UnifiedShell.tsx'),'utf8');
const begin=shell.indexOf(' const chooseProject=');
const end=shell.indexOf(' const sidebarViews=',begin);
assert.ok(begin>0&&end>begin,'actual project switch callback is present');
const compiled=ts.transpileModule(shell.slice(begin,end)+'\nexports.chooseProject=chooseProject;',{
 compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2021},reportDiagnostics:true
});
assert.equal((compiled.diagnostics||[]).filter(d=>d.category===ts.DiagnosticCategory.Error).length,0);
function harness({response=false,reject=false,delayed=false,dirty=true}={}){
 const calls={ipc:0,browser:0,events:[],warnings:[],waiting:[]};
 const projectId='A';
 const pendingExternalSwitch={current:null};
 const nativeProjectSwitchPromptPending={current:false};
 const editedPrimary={current:dirty?{projectId,view:'prepare'}:null};
 const editedDock={current:null};
 const dock={secondary:null};
 const currentProjectRef={current:'A'};
 let release;
 const deferred=new Promise(resolve=>{release=resolve;});
 const invoke=()=>{
  calls.ipc++;
  if(reject)return Promise.reject(new Error('Native dialog unavailable'));
  return delayed?deferred:Promise.resolve(response);
 };
 const onConfirm=()=>{calls.browser++;throw Error('Native path called window.confirm');};
 class CustomEvent{constructor(type,opts){this.type=type;this.detail=opts.detail;}}
 const fn=new Function('projectId','workspaceReady','pendingExternalSwitch',
   'nativeProjectSwitchPromptPending','editedPrimary','editedDock','dock',
   'needsDockInputDiscardApproval','isDesktop','invoke','currentProjectRef',
   'confirmProjectDraftDiscard','window','CustomEvent','setWarning',
   'setNativeProjectSwitchWaiting','exports',
   compiled.outputText+'\nreturn exports.chooseProject;')(
    projectId,true,pendingExternalSwitch,nativeProjectSwitchPromptPending,
    editedPrimary,editedDock,dock,()=>false,()=>true,invoke,currentProjectRef,
    onConfirm,{dispatchEvent:event=>calls.events.push(event)},CustomEvent,
    message=>calls.warnings.push(message),
    state=>calls.waiting.push(state),{});
 return {fn,calls,pendingExternalSwitch,nativeProjectSwitchPromptPending,
         currentProjectRef,release};
}
const flush=()=>new Promise(resolve=>setImmediate(resolve));

test('native Stay cancels the switch without changing the selected project',async()=>{
 const h=harness({response:false});
 h.fn('B');
 assert.equal(h.nativeProjectSwitchPromptPending.current,true);
 assert.equal(h.pendingExternalSwitch.current,null);
 await flush();
 assert.equal(h.calls.ipc,1);
 assert.equal(h.calls.browser,0);
 assert.equal(h.pendingExternalSwitch.current,null);
 assert.deepEqual(h.calls.events,[]);
 assert.deepEqual(h.calls.waiting,[true,false]);
});
test('native explicit approval begins a provisional read but never commits identity before backend GET',async()=>{
 const h=harness({response:true});
 h.fn('B');await flush();
 assert.equal(h.pendingExternalSwitch.current?.previousId,'A');
 assert.equal(h.pendingExternalSwitch.current?.requestedId,'B');
 assert.deepEqual(h.calls.events.map(e=>e.type),['pilotodin:primary-project-load-requested']);
 assert.deepEqual(h.calls.waiting,[true,false]);
 assert.equal(h.calls.browser,0);
});
test('a stale native approval and a failed dialog both keep the old project',async()=>{
 const stale=harness({delayed:true});
 stale.fn('B');stale.currentProjectRef.current='C';stale.release(true);await flush();
 assert.equal(stale.pendingExternalSwitch.current,null);
 assert.deepEqual(stale.calls.events,[]);
 const failed=harness({reject:true});failed.fn('B');await flush();
 assert.equal(failed.pendingExternalSwitch.current,null);
 assert.deepEqual(failed.calls.events,[]);
 assert.match(failed.calls.warnings[0],/Your current project and edits were kept/);
});
test('a second selection cannot bypass pending native consent',async()=>{
 const h=harness({delayed:true});
 h.fn('B');h.fn('C');assert.equal(h.calls.ipc,1);
 h.release(false);await flush();
 assert.equal(h.pendingExternalSwitch.current,null);
});
