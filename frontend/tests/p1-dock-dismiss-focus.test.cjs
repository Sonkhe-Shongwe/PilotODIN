const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const ts=require('typescript');
const Module=require('node:module');
const file=path.resolve(__dirname,'../src/dockDismissFocus.ts');
const compiled=ts.transpileModule(fs.readFileSync(file,'utf8'),{
 compilerOptions:{target:ts.ScriptTarget.ES2021,module:ts.ModuleKind.CommonJS},
 reportDiagnostics:true
});
assert.equal((compiled.diagnostics||[]).filter(d=>d.category===ts.DiagnosticCategory.Error).length,0);
const m=new Module(file,module);m.filename=file;m.paths=module.paths;m._compile(compiled.outputText,file);
const {planDockDismissFocus,canRestoreDockDismissFocus}=m.exports;
const opened=Object.freeze({schema:2,secondary:'prepare',side:'right',fraction:.39});
const closed={...opened,secondary:null};
const tabs=Object.freeze(['overview','quality','prepare']);

test('explicit dock close plans focus on selected primary workspace',()=>{
 assert.deepEqual(planDockDismissFocus('project A','quality',tabs,opened,true),{projectId:'project A',view:'quality'});
});
test('the selected primary tab can also be the docked component',()=>{
 assert.deepEqual(planDockDismissFocus('project A','prepare',tabs,opened,true),{projectId:'project A',view:'prepare'});
});
test('refuse unready or unknown project, closed dock, or inactive tab',()=>{
 assert.equal(planDockDismissFocus('project A','quality',tabs,opened,false),null);
 assert.equal(planDockDismissFocus('','quality',tabs,opened,true),null);
 assert.equal(planDockDismissFocus('project A','quality',tabs,closed,true),null);
 assert.equal(planDockDismissFocus('project A','predict',tabs,opened,true),null);
});
test('only restore after dock is closed and current project is ready',()=>{
 const pending=planDockDismissFocus('project A','quality',tabs,opened,true);
 assert.equal(canRestoreDockDismissFocus(pending,'project A','quality',tabs,opened,true),false);
 assert.equal(canRestoreDockDismissFocus(pending,'project A','quality',tabs,closed,true),true);
 assert.equal(canRestoreDockDismissFocus(pending,'project A','quality',tabs,closed,false),false);
});
test('changing selected project prevents stale focus from crossing projects',()=>{
 const pending=planDockDismissFocus('project A','quality',tabs,opened,true);
 assert.equal(canRestoreDockDismissFocus(pending,'project B','quality',tabs,closed,true),false);
});
test('changing the active workspace or closing the target tab prevents focus stealing',()=>{
 const pending=planDockDismissFocus('project A','quality',tabs,opened,true);
 assert.equal(canRestoreDockDismissFocus(pending,'project A','overview',tabs,closed,true),false);
 assert.equal(canRestoreDockDismissFocus(pending,'project A','quality',['overview','prepare'],closed,true),false);
});
test('unknown requests do nothing and planner cannot mutate saved dock or tabs',()=>{
 const original=JSON.stringify(opened),order=[...tabs];
 assert.equal(canRestoreDockDismissFocus(null,'project A','quality',tabs,closed,true),false);
 planDockDismissFocus('project A','quality',tabs,opened,true);
 assert.deepEqual(tabs,order);
 assert.equal(JSON.stringify(opened),original);
});
test('shell routes only explicit dock close through project-scoped focus and layout close',()=>{
 const s=fs.readFileSync(path.resolve(__dirname,'../src/UnifiedShell.tsx'),'utf8');
 assert.match(s,/import \{canRestoreDockDismissFocus,planDockDismissFocus\} from '\.\/dockDismissFocus'/);
 assert.match(s,/const pendingDockDismissFocus=useRef<\{projectId:string;view:View\}\|null>\(null\)/);
 assert.match(s,/const closeDock=\(\)=>\{\s*const focus=planDockDismissFocus\(projectId,active,shownTabs,dock,workspaceReady\)/);
 assert.match(s,/if\(!focus\)return;\s*pendingDockDismissFocus\.current=focus;\s*setDock\(current=>nextDockLayout\(current,\{kind:'close'\}\)\)/);
 assert.match(s,/<button type="button" onClick=\{closeDock\} aria-label="Close docked pane"/);
});
test('focus effect waits for finished dock close and safely clears an obsolete project',()=>{
 const s=fs.readFileSync(path.resolve(__dirname,'../src/UnifiedShell.tsx'),'utf8');
 assert.match(s,/if\(pending\.projectId!==projectId\|\| \(workspaceReady&&active!==pending\.view\)\)/);
 assert.match(s,/if\(!canRestoreDockDismissFocus\(pending,projectId,active,shownTabs,dock,workspaceReady\)\)return/);
 assert.match(s,/tablistRef\.current\?\.querySelectorAll<HTMLButtonElement>\('\[role="tab"\]'\)/);
 assert.match(s,/pendingDockDismissFocus\.current=null;\s*target\?\.focus\(\)/);
 assert.match(s,/\},\[projectId,active,shownTabs,dock\.secondary,workspaceReady\]\)/);
});
test('existing accepted tab-close, sidebar and project gating remain wired',()=>{
 const s=fs.readFileSync(path.resolve(__dirname,'../src/UnifiedShell.tsx'),'utf8');
 assert.match(s,/pendingCloseFocus\.current=\{projectId,view:plan\.focus\}/);
 assert.match(s,/onKeyDown=\{event=>onSidebarKeyDown\(event,id\)\}/);
 assert.match(s,/onKeyDown=\{event=>onWorkspaceTabKeyDown\(event,view\)\}/);
 assert.match(s,/const workspaceReady=isProjectWorkspaceRestored\(projectId,restoredFor,catalogState\)/);
 assert.match(s,/setDock\(readDock\(projectId\)\)/);
 assert.match(s,/aria-label="Move docked pane to opposite side"/);
});
