const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const ts=require('typescript');
const Module=require('node:module');

const guardFile=path.resolve(__dirname,'../src/externalRouteActivationGuard.ts');
const shell=fs.readFileSync(path.resolve(__dirname,'../src/UnifiedShell.tsx'),'utf8');
const app=fs.readFileSync(path.resolve(__dirname,'../src/App.tsx'),'utf8');
const compiled=ts.transpileModule(fs.readFileSync(guardFile,'utf8'),{
 compilerOptions:{target:ts.ScriptTarget.ES2021,module:ts.ModuleKind.CommonJS},
 reportDiagnostics:true
});
assert.equal((compiled.diagnostics||[]).filter(d=>d.category===ts.DiagnosticCategory.Error).length,0);
const mod=new Module(guardFile,module);mod.filename=guardFile;mod.paths=module.paths;
mod._compile(compiled.outputText,guardFile);
const {planExternalRouteActivation}=mod.exports;
const edited={projectId:'A',view:'prepare'};

test('edited current dock needs approval when URL promotes it into primary',()=>{
 assert.equal(planExternalRouteActivation('quality','prepare','prepare',edited,'A',true),'confirm-promote');
});
test('unedited current dock can be promoted without a confirmation',()=>{
 assert.equal(planExternalRouteActivation('quality','prepare','prepare',null,'A',true),'promote');
});
test('unrelated direct route leaves the edited dock untouched',()=>{
 assert.equal(planExternalRouteActivation('quality','explore','prepare',edited,'A',true),'unchanged');
});
test('same primary route remains unchanged',()=>{
 assert.equal(planExternalRouteActivation('quality','quality','prepare',edited,'A',true),'unchanged');
});
test('a stale edit marker from a different project cannot trigger a warning',()=>{
 assert.equal(planExternalRouteActivation('quality','prepare','prepare',edited,'B',true),'promote');
});
test('a stale edited secondary-view marker cannot trigger a warning',()=>{
 assert.equal(planExternalRouteActivation('quality','prepare','prepare',{projectId:'A',view:'model'},'A',true),'promote');
});
test('unready or empty project never uses an external route to close the dock',()=>{
 assert.equal(planExternalRouteActivation('quality','prepare','prepare',edited,'A',false),'unchanged');
 assert.equal(planExternalRouteActivation('quality','prepare','prepare',edited,'',true),'unchanged');
});
test('no secondary dock means normal external routing has no split cleanup',()=>{
 assert.equal(planExternalRouteActivation('quality','prepare',null,edited,'A',true),'unchanged');
});
test('no arbitrary field values or storage appear in pure external route planner',()=>{
 const src=fs.readFileSync(guardFile,'utf8');
 assert.doesNotMatch(src,/localStorage|sessionStorage|window|fetch\(|post\(|upload\(|predictVals|train\(/);
});

const begin=shell.indexOf('  const reviewRoute=()=>{');
const end=shell.indexOf('\n  };',begin);
assert.ok(begin>0&&end>begin,'the actual shell capture handler must exist');
const handlerSource=shell.slice(begin,end+5);
function routeHarness({before='#/studio/quality',after='#/studio/prepare',dockView='prepare',
 current='quality',edit=edited,approval=false,ready=true,projectId='A'}={}){
 const journal={prompts:0,dockCloses:0,rollbacks:0};
 const activeUpdates=[];
 const dispatched=[];
 const listeners=new Map();
 const win={
  location:{hash:after,pathname:'/',search:''},
  history:{state:{session:'existing'},replaceState(state,title,url){
   journal.rollbacks++;assert.deepEqual(state,{session:'existing'});
   win.location.hash=url.slice(url.indexOf('#'));
  }},
  confirm(message){journal.prompts++;assert.match(message,/changed fields/);return approval;},
  addEventListener(name,callback){const handlers=listeners.get(name)||new Set();handlers.add(callback);listeners.set(name,handlers);},
  removeEventListener(name,callback){listeners.get(name)?.delete(callback);},
  dispatchEvent(event){dispatched.push(event.type);for(const callback of listeners.get(event.type)||[])callback(event);return true;}
 };
 const editedDock={current:edit};
 const acceptedRouteHash={current:before};
 const dock={secondary:dockView};
 const setDock=(callback)=>{const next=callback({secondary:dockView});if(next.secondary===null)journal.dockCloses++};
 const setActive=(view)=>{activeUpdates.push(view)};
 const nextDockLayout=(current,action)=>{assert.equal(action.kind,'close');return {...current,secondary:null}};
 const routeView=()=>win.location.hash.startsWith('#/studio/')?win.location.hash.slice(9):'overview';
 const run=new Function('window','acceptedRouteHash','routeView','planExternalRouteActivation',
  'active','dock','editedDock','projectId','workspaceReady','setDock','nextDockLayout','setActive',
  handlerSource+'\n return reviewRoute;')(
   win,acceptedRouteHash,routeView,planExternalRouteActivation,current,dock,editedDock,projectId,ready,
   setDock,nextDockLayout,setActive);
 return {run,win,journal,editedDock,acceptedRouteHash,activeUpdates,dispatched};
}
test('Cancel rolls browser URL back without unmounting edited dock or clearing its marker',()=>{
 const a=routeHarness();a.run();
 assert.deepEqual(a.journal,{prompts:1,dockCloses:0,rollbacks:1});
 assert.equal(a.win.location.hash,'#/studio/quality');
 assert.deepEqual(a.editedDock.current,edited);
 assert.equal(a.acceptedRouteHash.current,'#/studio/quality');
 assert.deepEqual(a.activeUpdates,[],'Cancel must not activate another workspace');
 assert.deepEqual(a.dispatched,['pilotodin:route-reverted']);
});
test('approved edited route closes the dock and records the new accepted URL',()=>{
 const a=routeHarness({approval:true});a.run();
 assert.deepEqual(a.journal,{prompts:1,dockCloses:1,rollbacks:0});
 assert.equal(a.editedDock.current,null);
 assert.equal(a.acceptedRouteHash.current,'#/studio/prepare');
 assert.deepEqual(a.activeUpdates,['prepare']);
 assert.deepEqual(a.dispatched,[],'approved navigation does not broadcast a rollback');
});
test('unedited direct route promotes secondary with no confirm and no duplicate dock',()=>{
 const a=routeHarness({edit:null});a.run();
 assert.deepEqual(a.journal,{prompts:0,dockCloses:1,rollbacks:0});
 assert.deepEqual(a.activeUpdates,['prepare']);
});
test('unrelated external navigation does not close or clear edited secondary',()=>{
 const a=routeHarness({after:'#/studio/explore'});a.run();
 assert.deepEqual(a.journal,{prompts:0,dockCloses:0,rollbacks:0});
 assert.deepEqual(a.editedDock.current,edited);
 assert.equal(a.acceptedRouteHash.current,'#/studio/explore');
 assert.deepEqual(a.activeUpdates,['explore']);
});
test('duplicate hashchange after approved route commit does not prompt twice',()=>{
 const a=routeHarness({approval:true});a.run();a.run();
 assert.equal(a.journal.prompts,1);assert.equal(a.journal.dockCloses,1);
 assert.deepEqual(a.activeUpdates,['prepare']);
});
test('cancelled route does not trigger a second prompt on delayed event',()=>{
 const a=routeHarness();a.run();a.run();
 assert.equal(a.journal.prompts,1);assert.equal(a.journal.rollbacks,1);
 assert.deepEqual(a.activeUpdates,[]);
 assert.deepEqual(a.dispatched,['pilotodin:route-reverted']);
});
test('unready project does not alter the dock on external route',()=>{
 const a=routeHarness({ready:false});a.run();
 assert.equal(a.journal.prompts,0);assert.equal(a.journal.dockCloses,0);
});
test('capture listeners run before ordinary App hash listeners and are removed on cleanup',()=>{
 assert.match(shell,/window\.addEventListener\('hashchange',reviewRoute,true\)/);
 assert.match(shell,/window\.addEventListener\('pilotodin:route-commit',reviewRoute,true\)/);
 assert.match(shell,/window\.removeEventListener\('hashchange',reviewRoute,true\)/);
 assert.match(shell,/window\.removeEventListener\('pilotodin:route-commit',reviewRoute,true\)/);
 assert.match(app,/window\.addEventListener\('hashchange',sync\)/);
});
test('the shell retains existing project, tab, and keyboard navigation without editing data',()=>{
 assert.match(shell,/const chooseProject=\(id:string\)=>/);
 assert.match(shell,/const navigateWithDockGuard=\(view:View\):boolean=>/);
 assert.match(shell,/onPrimaryNavigate=\{approvePrimaryStudioNavigation\}/);
 assert.match(shell,/const onWorkspaceTabKeyDown=/);
 assert.match(shell,/const onSidebarKeyDown=/);
 assert.doesNotMatch(handlerSource,/localStorage|sessionStorage|\bpost\(|\bfetch\(|\bupload\(|\btrain\(/);
});

test('a single guarded handler owns hash, history and route-commit workspace updates',()=>{
 assert.match(shell,/if\(requested!==active\)setActive\(requested\)/);
 assert.doesNotMatch(shell,/const onRoute=\(\)=>setActive\(routeView\(\)\)/);
 assert.doesNotMatch(shell,/window\.addEventListener\('hashchange',onRoute\)/);
 assert.doesNotMatch(shell,/window\.addEventListener\('pilotodin:route-commit',onRoute\)/);
});
test('project restoration closes a saved dock matching the restored primary view',()=>{
 assert.match(shell,/const savedDock=readDock\(projectId\)/);
 assert.match(shell,/setDock\(savedDock\.secondary===preferred\?nextDockLayout\(savedDock,\{kind:'close'\}\):savedDock\)/);
 assert.match(shell,/setActive\(preferred\)/);
});

test('Studio listens and unregisters its rollback synchronisation event',()=>{
 assert.match(app,/window\.addEventListener\('pilotodin:route-reverted',sync\)/);
 assert.match(app,/window\.removeEventListener\('pilotodin:route-reverted',sync\)/);
 assert.match(shell,/window\.dispatchEvent\(new Event\('pilotodin:route-reverted'\)\)/);
});

test('rejected external route restores actual Studio displayed page, not just address and tab',()=>{
 // Replay the actual primary Studio useEffect listener code against a fake browser
 // so this catches the observed Quality tab / Prepare body desynchronisation.
 const start=app.indexOf('  useEffect(()=>{if(embeddedStage!==undefined)');
 const ending=' },[embeddedStage]);';
 const stop=app.indexOf(ending,start);
 assert.ok(start>=0&&stop>start);
 const effectSource=app.slice(start,stop+ending.length);
 const a=routeHarness();
 const primary={page:'prepare'}; // the observed stale content after URL rollback
 let cleanup=null;
 new Function('useEffect','embeddedStage','setPage','requestedStudioStage','window',effectSource)(
  callback=>{cleanup=callback()},
  undefined,
  next=>{primary.page=next},
  ()=>a.win.location.hash.slice('#/studio/'.length),
  a.win
 );
 assert.equal(primary.page,'prepare');
 a.run();
 assert.equal(a.win.location.hash,'#/studio/quality');
 assert.equal(primary.page,'quality','primary Studio must show the accepted route');
 assert.deepEqual(a.activeUpdates,[],'shell remains Quality without remounting the edited dock');
 assert.equal(a.journal.dockCloses,0);
 assert.deepEqual(a.editedDock.current,edited);
 assert.equal(typeof cleanup,'function');
 cleanup();
 assert.equal(a.win.dispatchEvent(new Event('pilotodin:route-reverted')),true);
 assert.equal(primary.page,'quality');
});

test('rollback sync belongs only to primary Studio, never the embedded secondary',()=>{
 const start=app.indexOf('  useEffect(()=>{if(embeddedStage!==undefined)');
 const ending=' },[embeddedStage]);';
 const stop=app.indexOf(ending,start);
 const effectSource=app.slice(start,stop+ending.length);
 const a=routeHarness();
 const embeddedPage={value:'quality'};
 new Function('useEffect','embeddedStage','setPage','requestedStudioStage','window',effectSource)(
  callback=>callback(),
  'prepare',
  next=>{embeddedPage.value=next},
  ()=>a.win.location.hash.slice('#/studio/'.length),
  a.win
 );
 assert.equal(embeddedPage.value,'prepare');
 a.run();
 assert.equal(embeddedPage.value,'prepare','dock is not redirected by primary rollback');
});
