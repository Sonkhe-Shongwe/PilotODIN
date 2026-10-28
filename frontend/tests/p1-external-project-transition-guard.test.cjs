const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const ts=require('typescript');
const Module=require('node:module');
const root=path.resolve(__dirname,'../src');
const helperPath=path.join(root,'externalProjectTransitionGuard.ts');
const helperSource=fs.readFileSync(helperPath,'utf8');
const shell=fs.readFileSync(path.join(root,'UnifiedShell.tsx'),'utf8');
const app=fs.readFileSync(path.join(root,'App.tsx'),'utf8');
const compile=(source)=>ts.transpileModule(source,{compilerOptions:{
 target:ts.ScriptTarget.ES2021,module:ts.ModuleKind.CommonJS},reportDiagnostics:true});
const helperJs=compile(helperSource);
assert.equal((helperJs.diagnostics||[]).filter(d=>d.category===ts.DiagnosticCategory.Error).length,0);
const mod=new Module(helperPath,module);
mod.filename=helperPath;mod.paths=module.paths;mod._compile(helperJs.outputText,helperPath);
const {planExternalProjectTransition}=mod.exports;
const edited={projectId:'A',view:'prepare'};

test('external switch from A to B requires approval while Prepare is edited',()=>{
 assert.equal(planExternalProjectTransition('A','B','prepare',edited,true),'confirm');
});
test('unmodified or absent dock permits an external project transition',()=>{
 assert.equal(planExternalProjectTransition('A','B','prepare',null,true),'accept');
 assert.equal(planExternalProjectTransition('A','B',null,edited,true),'accept');
});
test('stale or mismatched edit markers cannot block a separate project',()=>{
 assert.equal(planExternalProjectTransition('A','B','prepare',{projectId:'B',view:'prepare'},true),'accept');
 assert.equal(planExternalProjectTransition('A','B','prepare',{projectId:'A',view:'model'},true),'accept');
});
test('no project change causes neither confirmation nor reload',()=>{
 assert.equal(planExternalProjectTransition('A','A','prepare',edited,true),'unchanged');
});
test('unrestored and empty initial workspace do not claim an edited project',()=>{
 assert.equal(planExternalProjectTransition('A','B','prepare',edited,false),'accept');
 assert.equal(planExternalProjectTransition('','B','prepare',edited,true),'accept');
});
test('backend confirmed deletion remains non-cancellable',()=>{
 assert.equal(planExternalProjectTransition('A','','prepare',edited,true,true),'accept');
});
test('project decision helper stores no project data or form values',()=>{
 assert.doesNotMatch(helperSource,/localStorage|sessionStorage|fetch\(|post\(|window\.|predictVals|train\(/);
});

const begin=shell.indexOf('  const reviewProject=(event:Event)=>{');
const end=shell.indexOf('\n  };',begin);
assert.ok(begin>0&&end>begin,'capture project handler must exist');
const handlerSource=shell.slice(begin,end+5);
const handlerJs=compile(handlerSource+'\nexport {reviewProject};');
assert.equal((handlerJs.diagnostics||[]).filter(d=>d.category===ts.DiagnosticCategory.Error).length,0);
function harness({requested='B',from='A',edit=edited,approval=false,
 eventType='pilotodin:project-changed',key='pilotodin-current',
 unavailable=false,restoreFails=false,primaryEdit=null}={}){
 let stored=requested,appLoads=0;
 const log={prompts:0,restores:0,accepted:[],refresh:0,warnings:[],stopped:0,events:[]};
 const listeners=new Map();
 const localStorage={
  getItem(name){assert.equal(name,'pilotodin-current');return stored},
  setItem(name,value){assert.equal(name,'pilotodin-current');if(restoreFails)throw Error('storage denied');stored=value;log.restores++}
 };
 class TestEvent {
  constructor(type,details={}){this.type=type;this.key=details.key??null;this.detail=details.detail;this.stopped=false}
  stopImmediatePropagation(){this.stopped=true;log.stopped++}
 }
 const window={
  confirm(message){assert.match(message,/Switching projects may discard/);log.prompts++;return approval},
  addEventListener(name,callback,capture=false){
   const set=listeners.get(name)||[];set.push({callback,capture});listeners.set(name,set)
  },
  dispatchEvent(event){
   log.events.push(event.type);
   const handlers=[...(listeners.get(event.type)||[])].sort((a,b)=>Number(b.capture)-Number(a.capture));
   for(const h of handlers){if(event.stopped)break;h.callback(event)}
  }
 };
 const dock={secondary:'prepare'};
 const editedDock={current:edit};
 const editedPrimary={current:primaryEdit};
 const pendingExternalSwitch={current:null};
 const needsDockInputDiscardApproval=(marker,id,secondary)=>!!marker&&marker.projectId===id&&marker.view===secondary;
 const setProjectId=id=>{log.accepted.push(id)};
 const refreshProjects=()=>{log.refresh++};
 const setWarning=message=>log.warnings.push(message);
 const exports={};
 const reviewProject=new Function('window','localStorage','projectId','dock','editedDock','editedPrimary','pendingExternalSwitch','needsDockInputDiscardApproval','workspaceReady',
 'planExternalProjectTransition','refreshProjects','setProjectId','setWarning','Event','exports',
 handlerJs.outputText+'\nreturn exports.reviewProject;')(
 window,localStorage,from,dock,editedDock,editedPrimary,pendingExternalSwitch,needsDockInputDiscardApproval,true,planExternalProjectTransition,
 refreshProjects,setProjectId,setWarning,TestEvent,exports);
 window.addEventListener('pilotodin:project-changed',reviewProject,true);
 window.addEventListener('storage',reviewProject,true);
 window.addEventListener('pilotodin:project-changed',()=>{appLoads++},false);
 const callbacksStart=shell.indexOf(' const commitPrimaryLoadedProject=(id:string)=>{');
 const callbacksEnd=shell.indexOf('\n const approvePrimaryProjectLoad=',callbacksStart);
 assert.ok(callbacksStart>0&&callbacksEnd>callbacksStart);
 const callbacksJs=compile(shell.slice(callbacksStart,callbacksEnd)
   +'\nexport {commitPrimaryLoadedProject,failPrimaryProjectLoad};');
 const action=new Function('pendingExternalSwitch','editedDock','editedPrimary',
  'setProjectId','refreshProjects','localStorage','setWarning','exports',
  callbacksJs.outputText+'\nreturn exports;')(
  pendingExternalSwitch,editedDock,editedPrimary,setProjectId,refreshProjects,
  localStorage,setWarning,{});
 const event=new TestEvent(eventType,{key,detail:unavailable?{reason:'unavailable'}:undefined});
 return {run(){window.dispatchEvent(event)},succeed:id=>action.commitPrimaryLoadedProject(id),
  fail:id=>action.failPrimaryProjectLoad(id),log,getStored:()=>stored,
 getAppLoads:()=>appLoads,editedDock,editedPrimary,pendingExternalSwitch,event,window,TestEvent};
}
test('Cancel restores local project selection and blocks primary Studio notification',()=>{
 const h=harness();h.run();
 assert.equal(h.getStored(),'A');
 assert.deepEqual(h.log.accepted,[]);
 assert.equal(h.getAppLoads(),0);
 assert.equal(h.log.prompts,1);
 assert.equal(h.log.stopped,1);
 assert.deepEqual(h.editedDock.current,edited);
});
test('Approve passes a single accepted project to normal Studio and clears edit marker',()=>{
 const h=harness({approval:true});h.run();
 assert.equal(h.getStored(),'B');
 assert.deepEqual(h.log.accepted,[],'consent alone cannot unmount A');
 assert.equal(h.getAppLoads(),1);
 assert.equal(h.log.prompts,1);
 assert.deepEqual(h.editedDock.current,edited);
 assert.equal(h.pendingExternalSwitch.current.requestedId,'B');
 h.succeed('B');
 assert.deepEqual(h.log.accepted,['B']);
 assert.equal(h.editedDock.current,null);
 assert.equal(h.pendingExternalSwitch.current,null);
});
test('Cancel in one browser tab does not rewrite another tab\'s project selection',()=>{
 const h=harness({eventType:'storage'});h.run();
 assert.equal(h.getStored(),'B','shared selection is owned by the other tab');
 assert.equal(h.log.restores,0,'no repeated cross-tab storage rollback loop');
 assert.equal(h.log.stopped,1);
 assert.equal(h.log.warnings.length,1,'warn that a reload may use the other selection');
 assert.deepEqual(h.log.accepted,[],'current edited A workspace remains mounted');
 assert.deepEqual(h.editedDock.current,edited);
 assert.equal(h.getAppLoads(),0);
});
test('approved cross-tab storage change notifies Studio through existing event once',()=>{
 const h=harness({eventType:'storage',approval:true});h.run();
 assert.deepEqual(h.log.accepted,[]);
 assert.equal(h.getAppLoads(),1);
 h.succeed('B');
 assert.deepEqual(h.log.accepted,['B']);
 assert.equal(h.log.refresh,1);
 assert.deepEqual(h.log.events,['storage','pilotodin:project-changed']);
});
test('unrelated localStorage preferences never trigger switch or prompts',()=>{
 const h=harness({eventType:'storage',key:'pilotodin-sidebar-mode-v1'});h.run();
 assert.equal(h.log.prompts,0);assert.equal(h.log.refresh,0);
 assert.deepEqual(h.log.accepted,[]);
 assert.deepEqual(h.editedDock.current,edited);
});
test('unchanged project-change notification refreshes without remounting the dock',()=>{
 const h=harness({requested:'A'});h.run();
 assert.equal(h.log.prompts,0);
 assert.equal(h.log.refresh,1);
 assert.deepEqual(h.log.accepted,[]);
 assert.deepEqual(h.editedDock.current,edited);
});
test('validated catalogue removal is accepted even if obsolete project has edits',()=>{
 const h=harness({requested:'',unavailable:true});h.run();
 assert.equal(h.log.prompts,0);
 assert.deepEqual(h.log.accepted,['']);
 assert.equal(h.editedDock.current,null);
});
test('failure to restore selected ID reports a warning without discarding this dock',()=>{
 const h=harness({restoreFails:true});h.run();
 assert.equal(h.log.stopped,1);
 assert.equal(h.log.warnings.length,1);
 assert.deepEqual(h.log.accepted,[]);
 assert.deepEqual(h.editedDock.current,edited);
});
test('source registers capture project handlers before ordinary App project listener',()=>{
 assert.match(shell,/window\.addEventListener\('pilotodin:project-changed',reviewProject,true\)/);
 assert.match(shell,/window\.addEventListener\('storage',reviewProject,true\)/);
 assert.match(shell,/window\.removeEventListener\('pilotodin:project-changed',reviewProject,true\)/);
 assert.match(shell,/window\.removeEventListener\('storage',reviewProject,true\)/);
 assert.match(app,/window\.addEventListener\('pilotodin:project-changed',handler\)/);
 assert.doesNotMatch(shell,/const update=\(\)=>\{const next=localStorage\.getItem\('pilotodin-current'\)/);
});
test('ordinary user selector remains guarded and backend deletion is tagged separately',()=>{
 assert.match(shell,/const chooseProject=\(id:string\)=>/);
 assert.match(shell,/if\(!confirmProjectDraftDiscard\(\)\)return/);
 assert.match(shell,/new CustomEvent\('pilotodin:project-changed',\{detail:\{reason:'unavailable'\}\}\)/);
});
test('project notification handler does not copy form contents or authorise data/ML changes',()=>{
 assert.doesNotMatch(handlerSource,/predictVals|sessionStorage|setTarget\(|train\(|upload\(|post\(|setProject\(/);
});
test('external project transition recognizes edited primary Prepare without an edited dock',()=>{
 assert.equal(planExternalProjectTransition('A','B',null,null,true,false,'A'),'confirm');
 assert.equal(planExternalProjectTransition('A','B','quality',null,true,false,'A'),'confirm');
 assert.equal(planExternalProjectTransition('A','B',null,null,true,false,'B'),'accept');
 assert.equal(planExternalProjectTransition('A','B',null,null,true,false,null),'accept');
 assert.equal(planExternalProjectTransition('A','A',null,null,true,false,'A'),'unchanged');
});
test('confirmed backend removal cannot be vetoed by a primary draft marker',()=>{
 assert.equal(planExternalProjectTransition('A','',null,null,true,true,'A'),'accept');
});
test('cross-tab Cancel of dirty primary prevents app load and preserves both tabs ownership',()=>{
 const edit={projectId:'A',view:'prepare'};
 const h=harness({edit:null,primaryEdit:edit,eventType:'storage'});
 h.run();
 assert.equal(h.log.prompts,1);
 assert.equal(h.getStored(),'B','a separate tab owns the shared selection');
 assert.equal(h.log.restores,0,'Cancel cannot rewrite shared storage');
 assert.deepEqual(h.log.accepted,[]);
 assert.equal(h.getAppLoads(),0);
 assert.equal(h.log.stopped,1);
 assert.equal(h.log.warnings.length,1);
 assert.deepEqual(h.editedPrimary.current,edit);
});
test('local external selection Cancel restores local storage without losing primary edit',()=>{
 const edit={projectId:'A',view:'model'};
 const h=harness({edit:null,primaryEdit:edit,eventType:'pilotodin:project-changed'});
 h.run();
 assert.equal(h.getStored(),'A');
 assert.equal(h.log.restores,1);
 assert.deepEqual(h.log.accepted,[]);
 assert.equal(h.log.prompts,1);
 assert.equal(h.getAppLoads(),0);
 assert.deepEqual(h.editedPrimary.current,edit);
});
test('approved cross-tab switch presents one combined prompt for primary and secondary edits',()=>{
 const edit={projectId:'A',view:'prepare'};
 const h=harness({edit,primaryEdit:edit,eventType:'storage',approval:true});
 h.run();
 assert.equal(h.log.prompts,1);
 assert.deepEqual(h.log.accepted,[],'pending read must keep primary A mounted');
 assert.deepEqual(h.editedPrimary.current,edit);
 assert.deepEqual(h.editedDock.current,edit);
 assert.equal(h.pendingExternalSwitch.current.requestedId,'B');
 assert.equal(h.getAppLoads(),1);
 assert.equal(h.log.restores,0);
 h.succeed('B');
 assert.deepEqual(h.log.accepted,['B']);
 assert.equal(h.editedPrimary.current,null);
 assert.equal(h.editedDock.current,null);
 assert.deepEqual(h.log.events,['storage','pilotodin:project-changed']);
});
test('unrelated storage key and unchanged project do not prompt for dirty primary',()=>{
 const edit={projectId:'A',view:'prepare'};
 const a=harness({edit:null,primaryEdit:edit,eventType:'storage',key:'pilotodin-sidebar-mode-v1'});a.run();
 const b=harness({edit:null,primaryEdit:edit,requested:'A'});b.run();
 assert.equal(a.log.prompts,0);assert.equal(b.log.prompts,0);
 assert.deepEqual(a.editedPrimary.current,edit);
 assert.deepEqual(b.editedPrimary.current,edit);
});

test('approved cross-tab B read failure keeps primary A and edited dock mounted',()=>{
 const edit={projectId:'A',view:'prepare'};
 const h=harness({eventType:'storage',primaryEdit:edit,edit,approval:true});
 h.run();
 assert.equal(h.log.prompts,1);
 assert.equal(h.getAppLoads(),1);
 assert.deepEqual(h.log.accepted,[]);
 h.fail('B');
 assert.deepEqual(h.log.accepted,[]);
 assert.deepEqual(h.editedPrimary.current,edit);
 assert.deepEqual(h.editedDock.current,edit);
 assert.equal(h.pendingExternalSwitch.current,null);
 assert.equal(h.getStored(),'B','do not roll back another tab shared selection');
 assert.equal(h.log.restores,0);
 assert.match(h.log.warnings.at(-1),/could not be opened here/);
});
test('approved same-tab external B read failure restores local choice without losing drafts',()=>{
 const edit={projectId:'A',view:'prepare'};
 const h=harness({eventType:'pilotodin:project-changed',primaryEdit:edit,edit:null,approval:true});
 h.run();
 assert.deepEqual(h.log.accepted,[]);
 h.fail('B');
 assert.equal(h.getStored(),'A');
 assert.equal(h.log.restores,1);
 assert.deepEqual(h.editedPrimary.current,edit);
 assert.deepEqual(h.log.accepted,[]);
});
test('failure of an unrelated project never consumes pending external approval',()=>{
 const edit={projectId:'A',view:'prepare'};
 const h=harness({eventType:'storage',primaryEdit:edit,edit:null,approval:true});
 h.run();h.fail('C');
 assert.equal(h.pendingExternalSwitch.current.requestedId,'B');
 assert.deepEqual(h.editedPrimary.current,edit);
 assert.deepEqual(h.log.accepted,[]);
});
test('consented external read must finish before project ID is committed to the shell',()=>{
 const src=shell.slice(shell.indexOf('  const reviewProject='),shell.indexOf('  };',shell.indexOf('  const reviewProject=')));
 assert.match(src,/if\(decision==='confirm'\)\{/);
 assert.match(src,/pendingExternalSwitch\.current=\{/);
 assert.ok(src.indexOf("if(decision==='confirm'){")<src.indexOf('setProjectId(requested)'));
 assert.match(shell,/onPrimaryProjectLoadFailed=\{failPrimaryProjectLoad\}/);
});
