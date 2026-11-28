const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const ts=require('typescript');
const shell=fs.readFileSync(path.resolve(__dirname,'../src/UnifiedShell.tsx'),'utf8');
function transpile(name,next){
 const start=shell.indexOf('  const '+name+'=');
 const end=shell.indexOf('\n  };',start);
 assert.ok(start>0&&end>start,'actual '+name+' closure is present');
 const out=ts.transpileModule(shell.slice(start,end+5),{
  compilerOptions:{target:ts.ScriptTarget.ES2021,module:ts.ModuleKind.CommonJS},
  reportDiagnostics:true
 });
 assert.deepEqual((out.diagnostics||[]).filter(z=>z.category===ts.DiagnosticCategory.Error),[]);
 return out.outputText+'\nreturn '+name+';';
}
const before=transpile('beforeRoutePush'),after=transpile('reviewRoute');
const needs=(e,id,current,next,ready)=>!!ready&&e?.projectId===id&&e?.view==='deliver'&&current==='deliver'&&next!=='deliver';
const plan=()=> 'unchanged';
function harness({phase='before',desktop=true,dirty=true,preapproved=null,request='#/studio/explore'}={}){
 const state={native:[],browser:[],prevented:0,rollbacks:[],reverted:[],active:[],dockChanges:0};
 const acceptedRouteHash={current:'#/studio/deliver'};
 const preapprovedRoutePush={current:preapproved};
 const editedPrimary={current:dirty?{projectId:'A',view:'deliver'}:null};
 const editedDock={current:null};
 const dock={secondary:null};
 const win={location:{hash:phase==='before'?'#/studio/deliver':request,
   origin:'http://127.0.0.1:5178',pathname:'/',search:'',href:'http://127.0.0.1:5178/'+request},
  history:{state:{id:'synthetic'},replaceState(saved,title,to){
   assert.deepEqual(saved,{id:'synthetic'});
   state.rollbacks.push(to);
   win.location.hash=to.slice(to.indexOf('#'));
  }},
  confirm(message){state.browser.push(message);return false;},
  dispatchEvent(e){state.reverted.push(e.type);return true;}
 };
 const routeViewFromHash=hash=>hash==='#/canvas'?'investigate':hash.slice('#/studio/'.length);
 const routeView=()=>routeViewFromHash(win.location.hash);
 const invokeGuard=view=>{state.native.push(view);return false;};
 const deps={
  window:win,acceptedRouteHash,preapprovedRoutePush,routeViewFromHash,routeView,
  planExternalRouteActivation:plan,active:'deliver',dock,editedDock,editedPrimary,
  projectId:'A',workspaceReady:true,needsPrimaryStudioExitApproval:needs,
  isDesktop:()=>desktop,navigateWithDockGuard:invokeGuard,
  primaryExitMessage:()=> 'Deliver has unsaved changes',PRIMARY_CANVAS_EXIT_MESSAGE:'Canvas dirty',
  setDock(){state.dockChanges++},nextDockLayout:d=>d,
  setActive:view=>state.active.push(view),Event
 };
 const keys=Object.keys(deps);
 const callback=new Function(...keys,phase==='before'?before:after)(...keys.map(k=>deps[k]));
 const event={cancelable:true,navigationType:'push',destination:{
  url:'http://127.0.0.1:5178/'+request},
  preventDefault(){state.prevented++}};
 return {run:()=>phase==='before'?callback(event):callback(),state,acceptedRouteHash,
   preapprovedRoutePush,editedPrimary,win};
}
test('native precommit intercepts external dirty Deliver hash before history insertion',()=>{
 const h=harness({phase:'before'});
 h.run();
 assert.equal(h.state.prevented,1);
 assert.deepEqual(h.state.native,['explore']);
 assert.deepEqual(h.state.browser,[]);
 assert.deepEqual(h.state.active,[]);
 assert.equal(h.preapprovedRoutePush.current,null);
 assert.equal(h.win.location.hash,'#/studio/deliver');
});
test('native postcommit fallback restores accepted Deliver URL and authoring before native IPC',()=>{
 const h=harness({phase:'after'});
 h.run();
 assert.deepEqual(h.state.rollbacks,['/#/studio/deliver']);
 assert.deepEqual(h.state.reverted,['pilotodin:route-reverted']);
 assert.deepEqual(h.state.native,['explore']);
 assert.deepEqual(h.state.browser,[]);
 assert.deepEqual(h.state.active,[]);
 assert.deepEqual(h.editedPrimary.current,{projectId:'A',view:'deliver'});
 assert.equal(h.acceptedRouteHash.current,'#/studio/deliver');
});
test('preapproved native return consumes one precise route and does not prompt twice',()=>{
 const h=harness({phase:'after',preapproved:'#/studio/explore'});
 h.run();
 assert.deepEqual(h.state.native,[]);
 assert.deepEqual(h.state.browser,[]);
 assert.deepEqual(h.state.rollbacks,[]);
 assert.deepEqual(h.state.active,['explore']);
 assert.equal(h.preapprovedRoutePush.current,null);
 assert.equal(h.acceptedRouteHash.current,'#/studio/explore');
});
test('unchanged route or clean new route never prompts',()=>{
 for(const phase of ['before','after']){
  for(const settings of [{dirty:false},{request:'#/studio/deliver'}]){
   const h=harness({phase,...settings});h.run();
   assert.deepEqual(h.state.native,[]);
   assert.deepEqual(h.state.browser,[]);
  }
 }
});
test('non-native external route retains browser fallback and does not claim Windows acceptance',()=>{
 const h=harness({phase:'after',desktop:false});h.run();
 assert.equal(h.state.browser.length,1);
 assert.deepEqual(h.state.native,[]);
 assert.deepEqual(h.state.rollbacks,['/#/studio/deliver']);
});
test('source verifies native exit uses exact shell guard and no backend mutation',()=>{
 assert.match(shell,/event\.preventDefault\(\);\s*navigateWithDockGuard\(requested\);\s*return;/);
 assert.match(shell,/window\.dispatchEvent\(new Event\('pilotodin:route-reverted'\)\);\s*navigateWithDockGuard\(requested\);\s*return;/);
 assert.doesNotMatch(before+after,/localStorage|sessionStorage|fetch\(|post\(|upload\(|train\(/);
});
