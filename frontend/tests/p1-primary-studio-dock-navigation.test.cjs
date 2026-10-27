const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const ts=require('typescript');
const Module=require('node:module');

const app=fs.readFileSync(path.resolve(__dirname,'../src/App.tsx'),'utf8');
const shell=fs.readFileSync(path.resolve(__dirname,'../src/UnifiedShell.tsx'),'utf8');
const guardPath=path.resolve(__dirname,'../src/dockInputDiscardGuard.ts');
const compiled=ts.transpileModule(fs.readFileSync(guardPath,'utf8'),{
 compilerOptions:{target:ts.ScriptTarget.ES2021,module:ts.ModuleKind.CommonJS},
 reportDiagnostics:true
});
assert.deepEqual((compiled.diagnostics||[]).filter(d=>d.category===ts.DiagnosticCategory.Error),[]);
const mod=new Module(guardPath,module);
mod.filename=guardPath;mod.paths=module.paths;mod._compile(compiled.outputText,guardPath);
const {needsDockInputDiscardApproval}=mod.exports;

test('primary App exposes a typed veto callback and shell passes it only to primary Studio',()=>{
 assert.match(app,/onPrimaryNavigate\?:\(view:Stage\)=>boolean/);
 assert.match(app,/App\(\{embeddedStage,embeddedProjectId,onEmbeddedNavigate,onPrimaryNavigate,forceNewProject=false/);
 assert.match(shell,/<App key=\{`studio-\$\{projectId\}\`} onPrimaryNavigate=\{approvePrimaryStudioNavigation\}/);
 assert.match(shell,/<App embeddedStage=\{dock\.secondary!\} embeddedProjectId=\{projectId\} onEmbeddedNavigate=\{view=>dockView\(view\)\}/);
});
test('go veto runs before quality focus, deliver focus, scroll or page mutation',()=>{
 const start=app.indexOf('  function go(next:Stage){');
 const end=app.indexOf('  useEffect(()=>{setVisitedStages',start);
 assert.ok(start>=0&&end>start);
 const body=app.slice(start,end);
 const guard=body.indexOf('if(!embedded&&next!==page&&onPrimaryNavigate&&!onPrimaryNavigate(next))return;');
 assert.ok(guard>=0);
 for(const effect of ["setQualityFocus(null)","setDeliverEvidenceId(null)","scrollRef.current[page]","navigateHashSmoothly("]){
  assert.ok(body.indexOf(effect)>guard, effect+' must follow veto');
 }
});
test('shell checks that the project workspace is ready before granting primary route',()=>{
 assert.match(shell,/const approvePrimaryStudioNavigation=\(view:View\):boolean=>\{\s*if\(!workspaceReady\)return false;/);
});
test('shell warns only when primary navigation would activate the current secondary dock',()=>{
 assert.match(shell,/if\(view!==active&&dock\.secondary===view&&isSecondaryView\(view\)\)\{\s*if\(!confirmEditedDockDiscard\('activate',view\)\)return false;/);
 assert.match(shell,/if\(!confirmEditedDockDiscard\('activate',view\)\)return false;\s*editedDock\.current=null;/);
});
test('same-project edited dock activation requires a warning; unrelated route does not',()=>{
 const edited={projectId:'A',view:'prepare'};
 assert.equal(needsDockInputDiscardApproval(edited,'A','prepare','activate','prepare'),true);
 assert.equal(needsDockInputDiscardApproval(edited,'A','prepare','activate','quality'),false);
 assert.equal(needsDockInputDiscardApproval(edited,'A','quality','activate','quality'),false);
 assert.equal(needsDockInputDiscardApproval(edited,'B','prepare','activate','prepare'),false);
});
test('no changed input means no destructive activation confirmation',()=>{
 assert.equal(needsDockInputDiscardApproval(null,'A','prepare','activate','prepare'),false);
});
test('embedded navigation remains limited to the existing dock registry',()=>{
 assert.match(app,/if\(embedded\)\{[\s\S]*?if\(!isSecondaryView\(next\)\)\{/);
 assert.match(app,/onEmbeddedNavigate\?\.\(next\)/);
 assert.match(app,/\/\/ Prop is authoritative: do not render an unapproved page while it updates/);
 assert.doesNotMatch(app,/onPrimaryNavigate\?\.\(next\)[\s\S]*onEmbeddedNavigate/);
});
test('primary route still navigates by the existing path after approval',()=>{
 assert.match(app,/if\(location\.hash!==`#\/studio\/\$\{next\}`\)navigateHashSmoothly\(`#\/studio\/\$\{next\}`,\(\)=>setPage\(next\)\)/);
});
test('source guard never stores form content or authorises Quality, model or dataset writes',()=>{
 const section=shell.slice(shell.indexOf('const approvePrimaryStudioNavigation='),shell.indexOf('const navigateWithDockGuard='));
 assert.ok(section.length>0&&section.length<1200);
 assert.doesNotMatch(section,/localStorage|sessionStorage|\bpost\(|\bupload\(|setPredictVals|setProjectId|setDock|train\(/);
});
test('previous tab/rail route guard remains present and independent',()=>{
 assert.match(shell,/const navigateWithDockGuard=\(view:View\):boolean=>\{/);
 assert.match(shell,/onClick=\{\(\)=>navigateWithDockGuard\(id\)\}/);
 assert.match(shell,/onClick=\{\(\)=>navigateWithDockGuard\(view\)\}/);
 assert.match(shell,/const closeDock=\(\)=>/);
});
