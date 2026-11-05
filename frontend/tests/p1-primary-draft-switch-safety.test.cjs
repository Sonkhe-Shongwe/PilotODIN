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
// Compile the exact two callbacks, not adjacent React lifecycle effects.
// The unload guard is separately verified in p1-unsaved-reload-guard.test.cjs.
const begin=shell.indexOf(' const markPrimaryDraftEdited=');
const markClose=shell.indexOf('\n };',begin);
const confirmBegin=shell.indexOf(' const confirmProjectDraftDiscard=',markClose);
const finish=shell.indexOf('\n // The primary App has',confirmBegin);
assert.ok(begin>0&&markClose>begin&&confirmBegin>markClose&&finish>confirmBegin);
const source=shell.slice(begin,markClose+4)+'\n'+shell.slice(confirmBegin,finish);
assert.match(source,/const markPrimaryDraftEdited=\(view:View\)=>\{/);
assert.match(source,/const confirmProjectDraftDiscard=\(\):boolean=>\{/);
assert.doesNotMatch(source,/\buseEffect\s*\(/);
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
 assert.match(app,/if\(!embedded&&e\.target\.value!==target\)onPrimaryDraftEdited\?\.\('prepare'\)/,
  'Target selection directly marks an unsaved draft without relying on bubbling');
 assert.match(shell,/onPrimaryDraftEdited=\{markPrimaryDraftEdited\}/);
 assert.doesNotMatch(shell,/<App embeddedStage=\{dock\.secondary!\}[^\n]*onPrimaryDraftEdited/);
});
test('both project selectors and import preflight check drafts before any project change',()=>{
 const choose=shell.slice(shell.indexOf('const chooseProject='),shell.indexOf('const sidebarViews='));
 const consent=choose.indexOf('if(!confirmProjectDraftDiscard())return;');
 const provisional=choose.indexOf('pendingExternalSwitch.current={');
 const native=choose.indexOf("invoke<boolean>('confirm_native_project_switch')");
 assert.ok(native>=0&&native<consent,'The native dialog precedes browser-only fallback');
 assert.match(choose,/nativeProjectSwitchPromptPending\.current=true/);
 assert.match(choose,/if\(!approved\|\|currentProjectRef\.current!==origin\|\|/);
 assert.match(choose,/pendingExternalSwitch\.current!==null\)return/);
 const request=choose.indexOf("pilotodin:primary-project-load-requested");
 assert.ok(consent>=0&&provisional>consent&&request>provisional,
   'consent must precede a provisional B request, never an immediate identity commit');
 assert.doesNotMatch(choose,/localStorage\.(?:setItem|removeItem)\s*\(|\bsetProjectId\s*\(/,
   'choosing B must not change A storage or unmount A before successful GETs');
 const loaded=shell.slice(shell.indexOf('const commitPrimaryLoadedProject='),shell.indexOf('const consumePrimaryProjectHandoff='));
 assert.match(loaded,/pendingExternalSwitch\.current\?\.requestedId===id/);
 assert.ok(loaded.indexOf('primaryProjectHandoff.current=snapshot')>=0);
 assert.ok(loaded.indexOf('primaryProjectHandoff.current=snapshot')<loaded.indexOf('setProjectId(id)'),
   'commit is allowed only after the verified project/profile snapshot is staged');
 const start=shell.slice(shell.indexOf('const approvePrimaryProjectUpload='),shell.indexOf('const chooseProject='));
 assert.match(start,/return confirmProjectDraftDiscard\(\)/);
 assert.match(start,/if\(!confirmProjectDraftDiscard\(\)\)return false/);
});
test('primary draft is cleared only after a successful direct Studio fetch',()=>{
 const read=app.indexOf('await Promise.all([get<Project>');
 const commit=app.indexOf('onPrimaryProjectLoaded?.(pid,{id:pid,project:verifiedProject,version:q.version});',read);
 const reset=app.indexOf('setProject(null)',read);
 assert.ok(read>=0&&commit>read&&reset>commit);
 assert.match(shell,/const commitPrimaryLoadedProject=\(id:string,snapshot:PrimaryProjectLoadSnapshot\)=>\{/);
 assert.match(shell,/pendingExternalSwitch\.current\?\.requestedId===id/);
 assert.match(shell,/const failPrimaryProjectLoad=\(id:string\)=>\{/);
 assert.match(shell,/onPrimaryProjectLoaded=\{commitPrimaryLoadedProject\}/);
 assert.doesNotMatch(source,/localStorage|sessionStorage|fetch\(|post\(|upload\(|train\(/);
});


test('native unsaved-project confirmation invokes a real owner-visible Windows dialog',()=>{
 const rust=fs.readFileSync(path.resolve(__dirname,'../src-tauri/src/lib.rs'),'utf8');
 const start=rust.indexOf('async fn confirm_native_project_switch(');
 const end=rust.indexOf('\n#[derive(Deserialize)]',start);
 assert.ok(start>0&&end>start);
 const dialog=rust.slice(start,end);
 assert.match(dialog,/window\.label\(\) != "main"/);
 assert.match(dialog,/"Switch project"\.into\(\), "Stay"\.into\(\)/);
 assert.match(dialog,/spawn_blocking\(move \|\| prompt\.blocking_show\(\)\)/);
 assert.match(rust,/resolve_native_close_request, confirm_native_close, confirm_native_project_switch/);
 const choose=shell.slice(shell.indexOf('const chooseProject='),shell.indexOf('const sidebarViews='));
 assert.match(choose,/if\(!approvedNative&&isDesktop\(\)&&hasDraft\)/);
 assert.match(choose,/chooseProject\(id,true\)/);
 assert.match(choose,/setWarning\('Could not show the Windows unsaved-changes confirmation/);
 assert.match(choose,/Your current project and edits were kept/);
 assert.match(choose,/if\(!approvedNative\)\{\s+if\(!confirmProjectDraftDiscard\(\)\)return;/);
});
