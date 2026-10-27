const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const ts=require('typescript');
const Module=require('node:module');
const shell=fs.readFileSync(path.resolve(__dirname,'../src/UnifiedShell.tsx'),'utf8');
const app=fs.readFileSync(path.resolve(__dirname,'../src/App.tsx'),'utf8');
const guardFile=path.resolve(__dirname,'../src/dockInputDiscardGuard.ts');
const compiled=ts.transpileModule(fs.readFileSync(guardFile,'utf8'),{
 compilerOptions:{target:ts.ScriptTarget.ES2021,module:ts.ModuleKind.CommonJS},reportDiagnostics:true
});
assert.equal((compiled.diagnostics||[]).filter(d=>d.category===ts.DiagnosticCategory.Error).length,0);
const mod=new Module(guardFile,module);mod.filename=guardFile;mod.paths=module.paths;mod._compile(compiled.outputText,guardFile);
const {needsDockInputDiscardApproval}=mod.exports;
function section(from,to){const a=shell.indexOf(from),b=shell.indexOf(to,a);assert.ok(a>=0&&b>a);return shell.slice(a,b)}
test('primary Studio promotion closes its former secondary dock only after confirmation',()=>{
 const s=section('const approvePrimaryStudioNavigation=','const navigateWithDockGuard=');
 assert.match(s,/if\(view!==active&&dock\.secondary===view&&isSecondaryView\(view\)\)/);
 const veto=s.indexOf("if(!confirmEditedDockDiscard('activate',view))return false;");
 const close=s.indexOf("setDock(current=>nextDockLayout(current,{kind:'close'}))");
 assert.ok(veto>=0&&close>veto);
 assert.match(s,/if\(!workspaceReady\)return false/);
});
test('top tab, sidebar and keyboard promotion clear the old dock after approval',()=>{
 const s=section('const navigateWithDockGuard=','const chooseProject=');
 assert.match(s,/if\(view!==active&&dock\.secondary===view&&isSecondaryView\(view\)\)/);
 assert.ok(s.indexOf("if(!confirmEditedDockDiscard('activate',view))return false")<s.indexOf("setDock(current=>nextDockLayout(current,{kind:'close'}))"));
 assert.ok(s.indexOf("setDock(current=>nextDockLayout(current,{kind:'close'}))")<s.indexOf('navigate(view)'));
});
test('when primary and dock differ, unrelated routes do not automatically close dock',()=>{
 const s=section('const navigateWithDockGuard=','const chooseProject=');
 assert.ok(s.indexOf("setDock(current=>nextDockLayout(current,{kind:'close'}))")<s.indexOf('}\n  navigate(view);'));
});
test('selecting current already-active primary workspace is a no-op for promotion',()=>{
 const s=section('const approvePrimaryStudioNavigation=','const navigateWithDockGuard=');
 assert.match(s,/view!==active&&dock\.secondary===view/);
});
test('edited secondary needs explicit approval for promotion',()=>{
 const edited={projectId:'A',view:'prepare'};
 assert.equal(needsDockInputDiscardApproval(edited,'A','prepare','activate','prepare'),true);
 assert.equal(needsDockInputDiscardApproval(edited,'A','prepare','activate','quality'),false);
});
test('unedited secondary promotion needs no discard warning',()=>{
 assert.equal(needsDockInputDiscardApproval(null,'A','prepare','activate','prepare'),false);
});
test('cancellation cannot clear edit marker or dock before warning decision',()=>{
 for(const name of ['const approvePrimaryStudioNavigation=','const navigateWithDockGuard=']){
  const s=section(name,name==='const approvePrimaryStudioNavigation='?'const navigateWithDockGuard=':'const chooseProject=');
  const approval=s.indexOf("if(!confirmEditedDockDiscard('activate',view))return false");
  assert.ok(approval>=0&&s.indexOf('editedDock.current=null')>approval);
  assert.ok(s.indexOf("setDock(current=>nextDockLayout(current,{kind:'close'}))")>approval);
 }
});
test('closing another tab into a docked view no longer leaves duplicate placeholder',()=>{
 const s=section('const close=(view:View)=>','const closeDock=');
 assert.match(s,/plan\.nextActive!==active&&dock\.secondary===plan\.nextActive/);
 assert.match(s,/if\(dock\.secondary===view\|\|\(plan\.nextActive!==active&&dock\.secondary===plan\.nextActive\)\)setDock\(current=>nextDockLayout\(current,\{kind:'close'\}\)\)/);
 assert.ok(s.indexOf("!confirmEditedDockDiscard('activate',plan.nextActive)")<s.indexOf('setOpenTabs(plan.remaining)'));
});
test('primary command palette retains the optional before-route shell veto',()=>{
 assert.match(app,/if\(!embedded&&next!==page&&onPrimaryNavigate&&!onPrimaryNavigate\(next\)\)return/);
 assert.match(shell,/onPrimaryNavigate=\{approvePrimaryStudioNavigation\}/);
});
test('promotion changes only layout and existing route without touching data or training',()=>{
 const s=section('const approvePrimaryStudioNavigation=','const chooseProject=');
 assert.doesNotMatch(s,/localStorage|sessionStorage|\bpost\(|\bfetch\(|train\(|setPredictVals|upload\(|QualityCorrection/);
});
