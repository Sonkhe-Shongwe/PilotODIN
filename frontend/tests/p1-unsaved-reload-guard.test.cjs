const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const ts=require('typescript');
const Module=require('node:module');
const root=path.resolve(__dirname,'../src');
const source=fs.readFileSync(path.join(root,'dockInputDiscardGuard.ts'),'utf8');
const shell=fs.readFileSync(path.join(root,'UnifiedShell.tsx'),'utf8');
const compiled=ts.transpileModule(source,{
 compilerOptions:{target:ts.ScriptTarget.ES2021,module:ts.ModuleKind.CommonJS},
 reportDiagnostics:true
});
assert.equal((compiled.diagnostics||[]).filter(d=>d.category===ts.DiagnosticCategory.Error).length,0);
const filename=path.join(root,'dockInputDiscardGuard.ts');
const helper=new Module(filename,module);
helper.filename=filename;helper.paths=module.paths;
helper._compile(compiled.outputText,filename);
const {hasUnsavedWorkspaceDraftForUnload:guard}=helper.exports;
const primary=(projectId='A',view='prepare')=>({projectId,view});
const dock=(projectId='A',view='prepare')=>({projectId,view});
test('no warning for empty or unavailable project or an untouched workspace',()=>{
 assert.equal(guard('',true,'prepare',primary(),dock(),'prepare'),false);
 assert.equal(guard('A',false,'prepare',primary(),dock(),'quality'),false);
 assert.equal(guard('A',true,'prepare',null,null,null),false);
});
test('the mounted Studio warns across its subviews, but not once replaced by Investigation',()=>{
 assert.equal(guard('A',true,'prepare',primary(),null,null),true);
 assert.equal(guard('A',true,'model',primary(),null,null),true);
 assert.equal(guard('A',true,'prepare',primary('B'),null,null),false);
 assert.equal(guard('A',true,'model',primary('A','model'),null,null),true);
 assert.equal(guard('A',true,'predict',primary('A','predict'),null,null),true);
 assert.equal(guard('A',true,'quality',primary('A','model'),null,null),true);
 assert.equal(guard('A',true,'investigate',primary('A','model'),null,null),false);
});
test('only a still docked edited form causes an unload warning',()=>{
 assert.equal(guard('A',true,'quality',null,dock(),'prepare'),true);
 assert.equal(guard('A',true,'quality',null,dock('B'),'prepare'),false);
 assert.equal(guard('A',true,'quality',null,dock(),'model'),false);
 assert.equal(guard('A',true,'prepare',null,dock(),'prepare'),false);
 assert.equal(guard('A',true,'quality',null,dock(),null),false);
});
test('one warning decision covers both edited forms, including narrowed dock',()=>{
 assert.equal(guard('A',true,'model',primary('A','model'),dock(),'prepare'),true);
 assert.equal(guard('A',true,'quality',primary('A','model'),dock(),'prepare'),true);
});
test('shell wires beforeunload with cancellation, cleanup and no draft persistence',()=>{
 assert.match(shell,/useEffect\(\(\)=>\{\s*const onBeforeUnload=\(event:BeforeUnloadEvent\)=>\{/);
 assert.match(shell,/if\(!hasUnsavedWorkspaceDraftForUnload\(projectId,workspaceReady,active,/);
 assert.match(shell,/event\.preventDefault\(\);\s*event\.returnValue=''/);
 assert.match(shell,/window\.addEventListener\('beforeunload',onBeforeUnload\)/);
 assert.match(shell,/window\.removeEventListener\('beforeunload',onBeforeUnload\)/);
 const hook=shell.slice(shell.indexOf(' const onBeforeUnload='),shell.indexOf(' },[projectId,workspaceReady,active,dock.secondary]);'));
 assert.doesNotMatch(hook,/localStorage|sessionStorage|fetch\(|post\(|setProjectId\(|setDock\(/);
});
