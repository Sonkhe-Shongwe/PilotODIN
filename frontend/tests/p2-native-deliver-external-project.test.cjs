const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const ts=require('typescript');
const Module=require('node:module');

const root=path.resolve(__dirname,'../src');
const guardFile=path.join(root,'externalProjectTransitionGuard.ts');
const guardSource=fs.readFileSync(guardFile,'utf8');
const shell=fs.readFileSync(path.join(root,'UnifiedShell.tsx'),'utf8');
function transpile(source){
 const result=ts.transpileModule(source,{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2021},reportDiagnostics:true});
 assert.equal((result.diagnostics||[]).filter(d=>d.category===ts.DiagnosticCategory.Error).length,0);
 return result.outputText;
}
const mod=new Module(guardFile,module);
mod.filename=guardFile;mod.paths=module.paths;
mod._compile(transpile(guardSource),guardFile);
const {planExternalProjectTransition,shouldHoldNativeDeliverExternalProjectChange}=mod.exports;
const start=shell.indexOf('  const reviewProject=(event:Event)=>{');
const end=shell.indexOf('\n  };',start);
assert.ok(start>=0&&end>start&&end-start<6000,'actual external-project handler');
const extracted=shell.slice(start,end+5);
const compiled=transpile(extracted);

function harness({native=true,edited='deliver',type='storage',requested='B',allow=false,markerProject='A',dockView=null}={}){
 const events={prompts:[],dispatched:[],warnings:[],stopped:0,writes:[],projects:[],refresh:0};
 const projectId='A', editedPrimary={current:edited?{projectId:markerProject,view:edited}:null};
 const dock={secondary:dockView}, editedDock={current:dockView?{projectId:'A',view:dockView}:null};
 const pendingExternalSwitch={current:null};
 const localStorage={
  getItem(key){assert.equal(key,'pilotodin-current');return requested;},
  setItem(key,value){events.writes.push([key,value]);}
 };
 const window={
  confirm(msg){events.prompts.push(msg);return allow;},
  dispatchEvent(e){events.dispatched.push(e.type);return true;}
 };
 const deps={
  window,localStorage,pendingExternalSwitch,planExternalProjectTransition,
  projectId,dock,editedDock,workspaceReady:true,editedPrimary,
  refreshProjects(){events.refresh++;},isDesktop:()=>native,
  shouldHoldNativeDeliverExternalProjectChange,
  needsDockInputDiscardApproval:()=>!!dockView,
  setWarning:msg=>events.warnings.push(msg),
  setProjectId:id=>events.projects.push(id),Event
 };
 const names=Object.keys(deps);
 const reviewProject=new Function(...names,compiled+'\nreturn reviewProject;')(...names.map(name=>deps[name]));
 reviewProject({type,key:type==='storage'?'pilotodin-current':undefined,stopImmediatePropagation(){events.stopped++;}});
 return {events,editedPrimary,pendingExternalSwitch};
}

test('native external selection retains the unsaved Deliver draft without implicit project change',()=>{
 const h=harness();
 assert.deepEqual(h.events.prompts,[]);
 assert.deepEqual(h.events.dispatched,[]);
 assert.deepEqual(h.events.writes,[]);
 assert.deepEqual(h.events.projects,[]);
 assert.equal(h.events.stopped,1);
 assert.equal(h.pendingExternalSwitch.current,null);
 assert.deepEqual(h.editedPrimary.current,{projectId:'A',view:'deliver'});
 assert.match(h.events.warnings.join(' '),/unsaved Deliver report/);
});

test('repeated external selection cannot arm a deferred native Deliver project switch',()=>{
 for(let i=0;i<3;i++){
  const h=harness();
  assert.equal(h.events.stopped,1);
  assert.equal(h.pendingExternalSwitch.current,null);
  assert.deepEqual(h.events.writes,[]);
 }
});

test('browser cross-window selection preserves existing confirmation and cancel',()=>{
 const h=harness({native:false});
 assert.equal(h.events.prompts.length,1);
 assert.equal(h.events.stopped,1);
 assert.equal(h.pendingExternalSwitch.current,null);
});

test('clean native workspace still receives the external project reconciliation event',()=>{
 const h=harness({edited:null});
 assert.deepEqual(h.events.prompts,[]);
 assert.deepEqual(h.events.dispatched,['pilotodin:project-changed']);
 assert.equal(h.events.stopped,0);
});

test('same-window project-changed events do not use the new external native veto',()=>{
 const h=harness({type:'pilotodin:project-changed'});
 assert.equal(h.events.prompts.length,1);
 assert.equal(h.events.stopped,1);
});

test('Prepare edits and unrelated markers retain their previous project transition rules',()=>{
 const prepare=harness({edited:'prepare'});
 assert.equal(prepare.events.prompts.length,1);
 assert.equal(prepare.events.stopped,1);
 const other=harness({markerProject:'OTHER'});
 assert.deepEqual(other.events.prompts,[]);
 assert.deepEqual(other.events.dispatched,['pilotodin:project-changed']);
 assert.equal(other.events.stopped,0);
});

test('unchanged selected project never prompts or causes a second project load',()=>{
 const h=harness({requested:'A'});
 assert.deepEqual(h.events.prompts,[]);
 assert.deepEqual(h.events.dispatched,[]);
 assert.equal(h.pendingExternalSwitch.current,null);
 assert.equal(h.events.stopped,0);
});

test('the native Deliver protection precedes browser confirmation and cannot write shared project selection',()=>{
 assert.match(shell,/import \{planExternalProjectTransition,shouldHoldNativeDeliverExternalProjectChange\} from '\.\/externalProjectTransitionGuard';/);
 const hold=extracted.indexOf('shouldHoldNativeDeliverExternalProjectChange(');
 const prompt=extracted.indexOf('window.confirm(');
 assert.ok(hold>=0&&prompt>hold);
 assert.match(extracted.slice(hold,prompt),/stopImmediatePropagation\(\)/);
 assert.doesNotMatch(extracted.slice(hold,prompt),/localStorage\.setItem|setProjectId\(/);
 assert.match(guardSource,/eventType==='storage'&&decision==='confirm'&&native/);
});
