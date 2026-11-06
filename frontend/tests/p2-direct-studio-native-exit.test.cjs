const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const ts=require('typescript');

const root=path.resolve(__dirname,'../src');
const app=fs.readFileSync(path.join(root,'App.tsx'),'utf8');
const shell=fs.readFileSync(path.join(root,'UnifiedShell.tsx'),'utf8');

function compile(source, start, end, exports){
 const first=source.indexOf(start),last=source.indexOf(end,first);
 assert.ok(first>=0&&last>first,'Actual source block is present: '+start);
 const result=ts.transpileModule(source.slice(first,last)+'\n'+exports,{
  compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2021},
  reportDiagnostics:true
 });
 assert.equal((result.diagnostics||[]).filter(d=>d.category===ts.DiagnosticCategory.Error).length,0);
 return result.outputText;
}
const appFunctions=compile(app,'  function requestNewDataset():void{',
 '  useEffect(()=>{setVisitedStages','exports.go=go;exports.requestNewDataset=requestNewDataset;');
const shellFunction=compile(shell,' const approvePrimaryStudioNavigation=',
 ' // When a docked view becomes the primary view',
 'exports.approvePrimaryStudioNavigation=approvePrimaryStudioNavigation;');

function appHarness({authorize=()=>true}={}){
 const events=[];
 const state={
  file:'old',upload:false,palette:true,paletteQuery:'AI',mobile:true,
  deliverEvidenceId:'e'.repeat(32),error:'old'
 };
 const vars=[
  'embedded','page','onPrimaryNavigate','setQualityFocus','setDeliverEvidenceId',
  'scrollRef','mainRef','setError','setUploadOpen','setMobileOpen','setPaletteOpen',
  'setPaletteQuery','setFile','location','navigateHashSmoothly','setPage',
  'setNotice','onEmbeddedNavigate','isSecondaryView','exports'
 ];
 const values=[
  false,'deliver',authorize,()=>events.push('quality-clear'),
  value=>{state.deliverEvidenceId=value;events.push('evidence-clear');},
  {current:{}},{current:{scrollTop:15}},value=>{state.error=value;},
  value=>{state.upload=typeof value==='function'?value(state.upload):value;events.push('upload:'+state.upload);},
  value=>{state.mobile=value;},value=>{state.palette=value;},
  value=>{state.paletteQuery=value;},value=>{state.file=value;},
  {hash:'#/studio/deliver'},()=>events.push('route'),()=>events.push('page'),
  ()=>events.push('notice'),()=>{},()=>true,{}
 ];
 const functions=new Function(...vars,appFunctions+
  '\nreturn {go:exports.go,requestNewDataset:exports.requestNewDataset};')(...values);
 return {state,events,...functions};
}
function shellHarness({native=true,dirty=true,approve=true}={}){
 const calls={browser:[],delegated:[],callbacks:[],preapproved:null};
 const editedPrimary={current:dirty?{projectId:'A',view:'deliver'}:null};
 const preapprovedRoutePush={current:null};
 const vars=[
  'workspaceReady','needsPrimaryStudioExitApproval','editedPrimary','projectId',
  'active','isDesktop','navigateWithDockGuard','window','primaryExitMessage',
  'preapprovedRoutePush','dock','isSecondaryView','confirmEditedDockDiscard',
  'setDock','nextDockLayout','exports'
 ];
 const values=[
  true,(edited,id,active,target,ready)=>!!ready&&!!edited&&edited.projectId===id&&active==='deliver'&&target!=='deliver',
  editedPrimary,'A','deliver',()=>native,
  (target,after)=>{calls.delegated.push(target);calls.callbacks.push(after);return false;},
  {confirm:message=>{calls.browser.push(message);return approve;}},
  ()=> 'Synthetic dirty Deliver browser warning',
  preapprovedRoutePush,{secondary:null},()=>false,()=>true,()=>{},()=>({}),{}
 ];
 const fn=new Function(...vars,shellFunction+
  '\nreturn exports.approvePrimaryStudioNavigation;')(...values);
 return {fn,calls,preapprovedRoutePush};
}
test('native dirty Deliver direct Studio navigation delegates to existing native shell and refuses synchronous page mutation',()=>{
 const s=shellHarness();
 let finished=0;
 assert.equal(s.fn('ai_settings',()=>{finished++}),false);
 assert.deepEqual(s.calls.delegated,['ai_settings']);
 assert.deepEqual(s.calls.browser,[]);
 assert.equal(finished,0);
 assert.equal(s.preapprovedRoutePush.current,null);
 s.calls.callbacks[0]();
 assert.equal(finished,1);
});
test('native Studio direct New dataset waits for native permission before staging importer or clearing command palette',()=>{
 const shell=shellHarness();
 const appView=appHarness({authorize:(target,done)=>shell.fn(target,done)});
 appView.requestNewDataset();
 assert.deepEqual(shell.calls.delegated,['overview']);
 assert.equal(appView.state.upload,false);
 assert.equal(appView.state.file,'old');
 assert.equal(appView.state.palette,true);
 assert.equal(appView.state.paletteQuery,'AI');
 assert.equal(appView.state.deliverEvidenceId,'e'.repeat(32));
 assert.deepEqual(appView.events,[]);
 // The callback is invoked only after a separate native dialog has approved
 // the shell's exact route. A Stay/error path never calls it.
 assert.equal(shell.calls.callbacks.length,1);
 shell.calls.callbacks[0]();
 assert.equal(appView.state.upload,true);
 assert.equal(appView.state.file,null);
 assert.equal(appView.state.palette,false);
 assert.equal(appView.state.paletteQuery,'');
 assert.equal(appView.state.deliverEvidenceId,null);
 assert.equal(appView.state.error,'');
 assert.deepEqual(shell.calls.browser,[]);
});
test('native direct command palette change retains the palette while consent is pending, and closes it after approval',()=>{
 const shell=shellHarness();
 const appView=appHarness({authorize:(target,done)=>shell.fn(target,done)});
 assert.equal(appView.go('ai_settings'),false);
 assert.equal(appView.state.palette,true);
 assert.equal(appView.state.deliverEvidenceId,'e'.repeat(32));
 assert.deepEqual(appView.events,[]);
 assert.deepEqual(shell.calls.delegated,['ai_settings']);
 shell.calls.callbacks[0]();
 assert.equal(appView.state.palette,false);
 assert.equal(appView.state.deliverEvidenceId,null);
 assert.equal(appView.state.upload,false);
});
test('non-native browser confirm remains synchronous and cannot open importer after Stay',()=>{
 const reject=shellHarness({native:false,approve:false});
 let after=0;
 assert.equal(reject.fn('overview',()=>{after++;}),false);
 assert.equal(reject.calls.browser.length,1);
 assert.deepEqual(reject.calls.delegated,[]);
 assert.equal(after,0);
 assert.equal(reject.preapprovedRoutePush.current,null);
 const accepted=shellHarness({native:false,approve:true});
 assert.equal(accepted.fn('overview'),true);
 assert.equal(accepted.calls.browser.length,1);
 assert.equal(accepted.preapprovedRoutePush.current,'#/studio/overview');
});
test('no changed Deliver draft or unready workspace does not stage native approval',()=>{
 const clean=shellHarness({native:true,dirty:false});
 assert.equal(clean.fn('explore'),true);
 assert.deepEqual(clean.calls.delegated,[]);
 assert.deepEqual(clean.calls.browser,[]);
 assert.match(shell,/navigateWithDockGuard\(view,afterNavigate\)/);
 assert.match(app,/if\(!embedded&&next!==page&&onPrimaryNavigate&&!onPrimaryNavigate\(next,complete\)\)return false/);
});
