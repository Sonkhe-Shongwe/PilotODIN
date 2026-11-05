const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const ts=require('typescript');
const vm=require('node:vm');
const root=path.resolve(__dirname,'../src');
const source=fs.readFileSync(path.join(root,'primaryStudioExitGuard.ts'),'utf8');
const compiled=ts.transpileModule(source,{compilerOptions:{
 module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2021},reportDiagnostics:true});
assert.equal(compiled.diagnostics?.length,0);
const module={exports:{}};
vm.runInNewContext(compiled.outputText,{module,exports:module.exports});
const {needsPrimaryStudioExitApproval:needs}=module.exports;
const report=fs.readFileSync(path.join(root,'ReportWorkspace.tsx'),'utf8');
const app=fs.readFileSync(path.join(root,'App.tsx'),'utf8');
const shell=fs.readFileSync(path.join(root,'UnifiedShell.tsx'),'utf8');
const primary=(view,projectId='a'.repeat(32))=>({projectId,view});
const id='a'.repeat(32);

test('BEHAVIOR: dirty Deliver must have consent before every different primary stage',()=>{
 for(const target of ['explore','quality','prepare','overview','model','evaluate','investigate','assistant']){
  assert.equal(needs(primary('deliver'),id,'deliver',target,true),true,target);
 }
});
test('BEHAVIOR: unchanged, different-project and not-ready states never prompt',()=>{
 assert.equal(needs(primary('deliver'),id,'deliver','deliver',true),false);
 assert.equal(needs(primary('deliver'),'b'.repeat(32),'deliver','explore',true),false);
 assert.equal(needs(primary('deliver'),id,'deliver','explore',false),false);
 assert.equal(needs(null,id,'deliver','explore',true),false);
});
test('BEHAVIOR: legacy Prepare Model Predict still guard Canvas and not unrelated subviews',()=>{
 for(const view of ['prepare','model','predict']){
  assert.equal(needs(primary(view),id,view,'investigate',true),true);
  assert.equal(needs(primary(view),id,view,'quality',true),false);
 }
});
test('INTEGRATION: ReportWorkspace only resets handoff after validated evidence and explicit approval',()=>{
 assert.match(report,/appliedHandoff\.current=preselectEvidenceId/);
 assert.match(report,/const option=projectEvidence\.find\(item=>item\.id===preselectEvidenceId\)/);
 assert.match(report,/if\(composerGuard\.current\.hasPending\(\)\)/);
 assert.match(report,/if\(hasUnsavedWork\)\{[\s\S]*?setPendingDiscard\(\{kind:'handoff',projectId,id:preselectEvidenceId\}\)/);
 assert.match(report,/else if\(action\.kind==='handoff'\)applyEvidenceHandoff\(action\.id\)/);
 assert.match(report,/function applyEvidenceHandoff\(id:string\)\{[\s\S]*?composerGuard\.current\.navigate\(\);setBusy\(''\)/);
 assert.match(report,/setNarrative\(''\);setActiveOutlineId\(null\);setSelected\(\[id\]\)/);
 assert.match(report,/pendingDiscard\.kind==='handoff'\?'Using a saved Explore analysis'/);
});
test('INTEGRATION: App does not queue Explore evidence if primary navigation was denied',()=>{
 assert.match(app,/function go\(next:Stage\):boolean\{/);
 assert.match(app,/if\(!embedded&&next!==page&&onPrimaryNavigate&&!onPrimaryNavigate\(next\)\)return false/);
 assert.match(app,/onSendToDeliver=\{snapshotId=>\{if\(\/\^\[a-f0-9\]\{32\}\$\/\.test\(snapshotId\)&&go\('deliver'\)\)setDeliverEvidenceId\(snapshotId\)\}\}/);
});
test('INTEGRATION: shell guards Deliver exit and receives only dirty markers, not narrative',()=>{
 assert.match(report,/onUnsavedChange\?\(dirty:boolean\)=>void/);
 assert.match(report,/onUnsavedChange\?\.\(hasUnsavedWork\)/);
 assert.match(app,/onPrimaryDraftCleared\?\.\('deliver'\)/);
 assert.match(app,/onPrimaryDraftEdited\?\.\('deliver'\)/);
 assert.match(shell,/view==='predict'\|\|view==='deliver'/);
 assert.match(shell,/const clearPrimaryDraft=\(view:View\)=>\{/);
 assert.match(shell,/if\(needsPrimaryStudioExitApproval\(editedPrimary\.current,projectId,active,view,workspaceReady\)\)/);
 assert.match(shell,/primaryExitMessage\(active\)/);
 assert.match(shell,/preapprovedRoutePush\.current=plan\.nextActive==='investigate'/);
 assert.doesNotMatch(source,/localStorage|sessionStorage|fetch\(|post\(/);
});
test('INTEGRATION: native close and reload guard also accept Deliver dirty marker',()=>{
 const unload=fs.readFileSync(path.join(root,'dockInputDiscardGuard.ts'),'utf8');
 assert.match(unload,/view:'prepare'\|'model'\|'predict'\|'deliver'/);
 assert.match(shell,/onPrimaryDraftCleared=\{clearPrimaryDraft\}/);
});
