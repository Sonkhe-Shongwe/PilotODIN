const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const ts=require('typescript');
const Module=require('node:module');
const filename=path.resolve(__dirname,'../src/workspaceTabCloseFocus.ts');
const compiled=ts.transpileModule(fs.readFileSync(filename,'utf8'),{
  compilerOptions:{target:ts.ScriptTarget.ES2021,module:ts.ModuleKind.CommonJS},
  reportDiagnostics:true
});
assert.equal((compiled.diagnostics||[]).filter(x=>x.category===ts.DiagnosticCategory.Error).length,0);
const moduleUnderTest=new Module(filename,module);
moduleUnderTest.filename=filename;moduleUnderTest.paths=module.paths;
moduleUnderTest._compile(compiled.outputText,filename);
const {planWorkspaceTabClose}=moduleUnderTest.exports;
const tabs=Object.freeze(['overview','quality','prepare','evaluate','predict']);

test('closing selected workspace preserves existing last-tab fallback',()=>{
 const plan=planWorkspaceTabClose(tabs,'quality','quality');
 assert.deepEqual(plan,{remaining:['overview','prepare','evaluate','predict'],nextActive:'predict',focus:'predict'});
});

test('closing last active workspace selects and focuses previous surviving last tab',()=>{
 const plan=planWorkspaceTabClose(tabs,'predict','predict');
 assert.equal(plan.nextActive,'evaluate');
 assert.equal(plan.focus,'evaluate');
 assert.ok(plan.remaining.every(t=>t!=='predict'));
});

test('closing inactive workspace keeps selection and restores focus to selected tab',()=>{
 const plan=planWorkspaceTabClose(tabs,'quality','prepare');
 assert.equal(plan.nextActive,'quality');
 assert.equal(plan.focus,'quality');
 assert.deepEqual(plan.remaining,['overview','quality','evaluate','predict']);
});

test('closing first inactive tab does not change active workspace',()=>{
 const plan=planWorkspaceTabClose(tabs,'predict','overview');
 assert.equal(plan.nextActive,'predict');
 assert.equal(plan.focus,'predict');
});

test('never close sole remaining workspace',()=>{
 assert.equal(planWorkspaceTabClose(['quality'],'quality','quality'),null);
});

test('invalid or stale close requests cannot remove another tab',()=>{
 assert.equal(planWorkspaceTabClose(tabs,'quality','assistant'),null);
 assert.equal(planWorkspaceTabClose(tabs,'assistant','quality'),null);
 assert.equal(planWorkspaceTabClose([], 'quality','quality'),null);
});

test('closing is a pure plan with no mutation of existing tab order',()=>{
 const before=[...tabs];
 planWorkspaceTabClose(tabs,'evaluate','quality');
 assert.deepEqual(tabs,before);
});

test('workspace shell queues focus only for valid current-project closes',()=>{
 const shell=fs.readFileSync(path.resolve(__dirname,'../src/UnifiedShell.tsx'),'utf8');
 assert.match(shell,/import \{planWorkspaceTabClose\} from '\.\/workspaceTabCloseFocus'/);
 assert.match(shell,/const pendingCloseFocus=useRef<\{projectId:string;view:View\}\|null>\(null\)/);
 assert.match(shell,/if\(!workspaceReady\)return;\s*const plan=planWorkspaceTabClose\(shownTabs,active,view\)/);
 assert.match(shell,/if\(!plan\)return;[\s\S]*?pendingCloseFocus\.current=\{projectId,view:plan\.focus\}/);
 assert.match(shell,/setOpenTabs\(plan\.remaining\)/);
 assert.match(shell,/if\(plan\.nextActive!==active\)navigate\(plan\.nextActive\)/);
});

test('focus is restored only after project, visible tabs, and active view align',()=>{
 const shell=fs.readFileSync(path.resolve(__dirname,'../src/UnifiedShell.tsx'),'utf8');
 assert.match(shell,/if\(pending\.projectId!==projectId\)\{pendingCloseFocus\.current=null;return;\}/);
 assert.match(shell,/if\(!workspaceReady\|\|active!==pending\.view\|\|!shownTabs\.includes\(pending\.view\)\)return/);
 assert.match(shell,/tablistRef\.current\?\.querySelectorAll<HTMLButtonElement>\('\[role="tab"\]'\)/);
 assert.match(shell,/if\(!target\)return;\s*pendingCloseFocus\.current=null;\s*target\.focus\(\)/);
 assert.match(shell,/ref=\{tablistRef\}/);
});

test('focus restoration does not alter existing keyboard, dock, or project guards',()=>{
 const shell=fs.readFileSync(path.resolve(__dirname,'../src/UnifiedShell.tsx'),'utf8');
 assert.match(shell,/onKeyDown=\{event=>onWorkspaceTabKeyDown\(event,view\)\}/);
 assert.match(shell,/onKeyDown=\{event=>onSidebarKeyDown\(event,id\)\}/);
 assert.match(shell,/onClick=\{\(\)=>close\(view\)\}/);
 assert.match(shell,/if\(dock\.secondary===view\|\|\(plan\.nextActive!==active&&dock\.secondary===plan\.nextActive\)\)setDock\(current=>nextDockLayout\(current,\{kind:'close'\}\)\)/);
 assert.match(shell,/const workspaceReady=isProjectWorkspaceRestored\(projectId,restoredFor,catalogState\)/);
 assert.match(shell,/setDock\(savedDock\.secondary===preferred\?nextDockLayout\(savedDock,\{kind:'close'\}\):savedDock\)/);
});
