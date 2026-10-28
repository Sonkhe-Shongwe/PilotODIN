const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const ts=require('typescript');
const Module=require('node:module');
const root=path.resolve(__dirname,'../src');
const app=fs.readFileSync(path.join(root,'App.tsx'),'utf8');
const shell=fs.readFileSync(path.join(root,'UnifiedShell.tsx'),'utf8');
const helperFile=path.join(root,'dockInputDiscardGuard.ts');
const compiledHelper=ts.transpileModule(fs.readFileSync(helperFile,'utf8'),{
 compilerOptions:{target:ts.ScriptTarget.ES2021,module:ts.ModuleKind.CommonJS},
 reportDiagnostics:true
});
assert.equal((compiledHelper.diagnostics||[]).filter(d=>d.category===ts.DiagnosticCategory.Error).length,0);
const helper=new Module(helperFile,module);
helper.filename=helperFile;helper.paths=module.paths;
helper._compile(compiledHelper.outputText,helperFile);
const {needsDockInputDiscardApproval}=helper.exports;
const begin=shell.indexOf(' const markPrimaryDraftEdited=');
const finish=shell.indexOf('\n // The primary App has',begin);
assert.ok(begin>0&&finish>begin);
const source=shell.slice(begin,finish);
const compiled=ts.transpileModule(source+'\nexports.create={markPrimaryDraftEdited,confirmProjectDraftDiscard};',{
 compilerOptions:{target:ts.ScriptTarget.ES2021,module:ts.ModuleKind.CommonJS},
 reportDiagnostics:true
});
assert.equal((compiled.diagnostics||[]).filter(d=>d.category===ts.DiagnosticCategory.Error).length,0);
function harness({projectId='A',approval=false,primary=null,dockEdited=null,secondary='prepare',ready=true}={}){
 const log={prompts:[],fallback:0};
 const editedPrimary={current:primary},editedDock={current:dockEdited};
 const mockWindow={confirm(message){log.prompts.push(message);return approval}};
 const exports={};
 const funcs=new Function('projectId','workspaceReady','editedPrimary','editedDock','dock',
 'window','needsDockInputDiscardApproval','confirmEditedDockDiscard','exports',
 compiled.outputText+'\nreturn exports.create;')(
 projectId,ready,editedPrimary,editedDock,{secondary},mockWindow,
 needsDockInputDiscardApproval,()=>{log.fallback++;return true},exports);
 return {...funcs,editedPrimary,editedDock,log};
}
test('primary Prepare target edit is tracked only for the current ready project',()=>{
 const h=harness();h.markPrimaryDraftEdited('prepare');
 assert.deepEqual(h.editedPrimary.current,{projectId:'A',view:'prepare'});
 const invalid=harness({ready:false});invalid.markPrimaryDraftEdited('prepare');
 assert.equal(invalid.editedPrimary.current,null);
 const wrong=harness();wrong.markPrimaryDraftEdited('quality');
 assert.equal(wrong.editedPrimary.current,null);
});
test('primary-only unsaved draft requires one confirmation and Cancel leaves marker unchanged',()=>{
 const h=harness({approval:false});
 h.markPrimaryDraftEdited('prepare');
 assert.equal(h.confirmProjectDraftDiscard(),false);
 assert.equal(h.log.prompts.length,1);
 assert.match(h.log.prompts[0],/primary workspace.*Switching projects may discard/);
 assert.equal(h.log.fallback,0);
 assert.deepEqual(h.editedPrimary.current,{projectId:'A',view:'prepare'});
});
test('primary plus secondary edits produce one combined prompt, not sequential prompts',()=>{
 const h=harness({primary:{projectId:'A',view:'model'},
   dockEdited:{projectId:'A',view:'prepare'},approval:true});
 assert.equal(h.confirmProjectDraftDiscard(),true);
 assert.equal(h.log.prompts.length,1);
 assert.match(h.log.prompts[0],/primary and docked workspaces/);
});
test('stale primary draft cannot block another project',()=>{
 const h=harness({projectId:'B',primary:{projectId:'A',view:'prepare'}});
 assert.equal(h.confirmProjectDraftDiscard(),true);
 assert.equal(h.log.prompts.length,0);
 assert.equal(h.log.fallback,1);
});
test('primary draft capture is restricted to main Studio form, not its project selector',()=>{
 assert.match(app,/onPrimaryDraftEdited\?:\(view:Stage\)=>void/);
 assert.match(app,/<div className="content po-motion-stage"[^\n]*onChangeCapture=/);
 assert.match(app,/if\(embedded\|\|!project\|\|!\['prepare','model','predict'\]\.includes\(page\)\)return/);
 assert.match(app,/onPrimaryDraftEdited\?\.\(page\)/);
 assert.match(app,/onChooseTarget=\{column=>\{[^\n]*onPrimaryDraftEdited\?\.\('prepare'\)/);
 assert.match(shell,/onPrimaryDraftEdited=\{markPrimaryDraftEdited\}/);
 assert.doesNotMatch(shell,/<App embeddedStage=\{dock\.secondary!\}[^\n]*onPrimaryDraftEdited/);
});
test('both project selectors and import preflight check drafts before any project change',()=>{
 const choose=shell.slice(shell.indexOf('const chooseProject='),shell.indexOf('const sidebarViews='));
 assert.ok(choose.indexOf('if(!confirmProjectDraftDiscard())return;')>=0);
 assert.ok(choose.indexOf('if(!confirmProjectDraftDiscard())return;')<choose.indexOf('setProjectId(id)'));
 const start=shell.slice(shell.indexOf('const approvePrimaryProjectUpload='),shell.indexOf('const chooseProject='));
 assert.match(start,/return confirmProjectDraftDiscard\(\)/);
 assert.match(start,/if\(!confirmProjectDraftDiscard\(\)\)return false/);
});
test('primary draft is cleared only after a successful direct Studio fetch',()=>{
 const read=app.indexOf('await Promise.all([get<Project>');
 const commit=app.indexOf('onPrimaryProjectLoaded?.();',read);
 const reset=app.indexOf('setProject(null)',read);
 assert.ok(read>=0&&commit>read&&reset>commit);
 assert.match(shell,/const commitPrimaryLoadedProject=\(\)=>\{editedPrimary\.current=null;\}/);
 assert.match(shell,/onPrimaryProjectLoaded=\{commitPrimaryLoadedProject\}/);
 assert.doesNotMatch(source,/localStorage|sessionStorage|fetch\(|post\(|upload\(|train\(/);
});
