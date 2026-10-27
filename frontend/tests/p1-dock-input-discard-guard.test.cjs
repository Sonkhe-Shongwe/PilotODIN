const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const ts=require('typescript');
const Module=require('node:module');
const file=path.resolve(__dirname,'../src/dockInputDiscardGuard.ts');
const compiled=ts.transpileModule(fs.readFileSync(file,'utf8'),{
  compilerOptions:{target:ts.ScriptTarget.ES2021,module:ts.ModuleKind.CommonJS},
  reportDiagnostics:true
});
assert.deepEqual((compiled.diagnostics||[]).filter(d=>d.category===ts.DiagnosticCategory.Error),[]);
const m=new Module(file,module);m.filename=file;m.paths=module.paths;m._compile(compiled.outputText,file);
const {isEditableDockInput,needsDockInputDiscardApproval}=m.exports;
const edited=Object.freeze({projectId:'project A',view:'prepare'});

test('input select and textarea are tracked while buttons and labels are not',()=>{
  for(const tag of ['INPUT','SELECT','TEXTAREA'])assert.equal(isEditableDockInput(tag),true);
  for(const tag of ['BUTTON','DIV','SECTION','A','LABEL'])assert.equal(isEditableDockInput(tag),false);
});
test('closing edited dock in same project requires explicit approval',()=>{
  assert.equal(needsDockInputDiscardApproval(edited,'project A','prepare','close'),true);
});
test('switching project with edited dock requires approval before project ID changes',()=>{
  assert.equal(needsDockInputDiscardApproval(edited,'project A','prepare','switch-project'),true);
});
test('replacing edited secondary view requires approval only for a different view',()=>{
  assert.equal(needsDockInputDiscardApproval(edited,'project A','prepare','replace','quality'),true);
  assert.equal(needsDockInputDiscardApproval(edited,'project A','prepare','replace','prepare'),false);
});
test('closing the edited tab and resetting an edited layout require approval',()=>{
  assert.equal(needsDockInputDiscardApproval(edited,'project A','prepare','close-tab'),true);
  assert.equal(needsDockInputDiscardApproval(edited,'project A','prepare','reset'),true);
});
test('no changed input or closed dock does not block navigation',()=>{
  assert.equal(needsDockInputDiscardApproval(null,'project A','prepare','close'),false);
  assert.equal(needsDockInputDiscardApproval(edited,'project A',null,'close'),false);
});
test('another project or another secondary view cannot trigger stale approval',()=>{
  assert.equal(needsDockInputDiscardApproval(edited,'project B','prepare','close'),false);
  assert.equal(needsDockInputDiscardApproval(edited,'project A','quality','close'),false);
});
test('guard only sees identity flags and does not mutate user form values',()=>{
  const before=JSON.stringify(edited);
  needsDockInputDiscardApproval(edited,'project A','prepare','close');
  assert.equal(JSON.stringify(edited),before);
  assert.deepEqual(Object.keys(edited).sort(),['projectId','view']);
});
test('only input changes in the embedded pane mark the project and view; toolbar changes do not',()=>{
  const shell=fs.readFileSync(path.resolve(__dirname,'../src/UnifiedShell.tsx'),'utf8');
  assert.match(shell,/const editedDock=useRef<EditedDock\|null>\(null\)/);
  assert.match(shell,/onChangeCapture=\{event=>\{if\(dock\.secondary&&isEditableDockInput\(\(event\.target as HTMLElement\)\.tagName\)\)editedDock\.current=\{projectId,view:dock\.secondary\}\}\}/);
  assert.match(shell,/className="po-pane-content" key=/);
  assert.doesNotMatch(shell,/<section className="po-secondary-pane"[^>]*onChangeCapture=/);
});
test('cancelled dock dismissal exits before layout focus or edit flag updates',()=>{
  const shell=fs.readFileSync(path.resolve(__dirname,'../src/UnifiedShell.tsx'),'utf8');
  assert.match(shell,/if\(!focus\|\|!confirmEditedDockDiscard\('close'\)\)return;\s*editedDock\.current=null;\s*pendingDockDismissFocus\.current=focus;/);
  assert.match(shell,/if\(dock\.secondary!==view&&!confirmEditedDockDiscard\('replace',view\)\)return;/);
  assert.match(shell,/if\(dock\.secondary===view&&!confirmEditedDockDiscard\('close-tab'\)\)return;/);
  assert.match(shell,/if\(!confirmEditedDockDiscard\('switch-project'\)\)return;/);
  assert.match(shell,/if\(!confirmEditedDockDiscard\('reset'\)\)return;/);
});
test('confirmation is explicit and does not persist any field values',()=>{
  const shell=fs.readFileSync(path.resolve(__dirname,'../src/UnifiedShell.tsx'),'utf8');
  const guard=fs.readFileSync(file,'utf8');
  assert.match(shell,/return window\.confirm\('You changed fields in the docked workspace/);
  assert.match(shell,/if\(!needsDockInputDiscardApproval\(editedDock\.current,projectId,dock\.secondary,action,proposed\)\)return true;/);
  assert.doesNotMatch(guard,/localStorage|sessionStorage|fetch\(|post\(/);
});
test('responsive unmount clears stale edited flag instead of claiming inputs survive',()=>{
  const shell=fs.readFileSync(path.resolve(__dirname,'../src/UnifiedShell.tsx'),'utf8');
  assert.match(shell,/if\(!separate\)editedDock\.current=null/);
  assert.match(shell, /\},\[separate,projectId,dock\.secondary\]\)/);
});
test('accepted keyboard and project readiness guards remain in the source',()=>{
  const shell=fs.readFileSync(path.resolve(__dirname,'../src/UnifiedShell.tsx'),'utf8');
  assert.match(shell,/onKeyDown=\{event=>onSidebarKeyDown\(event,id\)\}/);
  assert.match(shell,/onKeyDown=\{event=>onWorkspaceTabKeyDown\(event,view\)\}/);
  assert.match(shell,/const workspaceReady=isProjectWorkspaceRestored\(projectId,restoredFor,catalogState\)/);
  assert.match(shell,/const closeDock=\(\)=>/);
  assert.match(shell,/pendingDockDismissFocus\.current=focus/);
});
