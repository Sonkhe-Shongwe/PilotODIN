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
 unavailable=false,restoreFails=false}={}){
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
 const setProjectId=id=>{log.accepted.push(id)};
 const refreshProjects=()=>{log.refresh++};
 const setWarning=message=>log.warnings.push(message);
 const exports={};
 const reviewProject=new Function('window','localStorage','projectId','dock','editedDock','workspaceReady',
 'planExternalProjectTransition','refreshProjects','setProjectId','setWarning','Event','exports',
 handlerJs.outputText+'\nreturn exports.reviewProject;')(
 window,localStorage,from,dock,editedDock,true,planExternalProjectTransition,
 refreshProjects,setProjectId,setWarning,TestEvent,exports);
 window.addEventListener('pilotodin:project-changed',reviewProject,true);
 window.addEventListener('storage',reviewProject,true);
 window.addEventListener('pilotodin:project-changed',()=>{appLoads++},false);
 const event=new TestEvent(eventType,{key,detail:unavailable?{reason:'unavailable'}:undefined});
 return {run(){window.dispatchEvent(event)},log,getStored:()=>stored,
 getAppLoads:()=>appLoads,editedDock,event,window,TestEvent};
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
 assert.deepEqual(h.log.accepted,['B']);
 assert.equal(h.getAppLoads(),1);
 assert.equal(h.log.prompts,1);
 assert.equal(h.editedDock.current,null);
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
 assert.deepEqual(h.log.accepted,['B']);
 assert.equal(h.getAppLoads(),1);
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
