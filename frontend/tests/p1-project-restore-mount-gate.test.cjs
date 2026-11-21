const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const ts=require('typescript');
const Module=require('node:module');
const f=path.resolve(__dirname,'../src/workspaceLayout.ts');
const compiled=ts.transpileModule(fs.readFileSync(f,'utf8'),{
 compilerOptions:{target:ts.ScriptTarget.ES2021,module:ts.ModuleKind.CommonJS},
 reportDiagnostics:true
});
assert.equal((compiled.diagnostics||[]).filter(x=>x.category===ts.DiagnosticCategory.Error).length,0);
const moduleUnderTest=new Module(f,module);
moduleUnderTest.filename=f;moduleUnderTest.paths=module.paths;
moduleUnderTest._compile(compiled.outputText,f);
const {isProjectWorkspaceRestored,dockStorageKey,DEFAULT_DOCK_LAYOUT,hasRoomForDock}=moduleUnderTest.exports;

test('new selected project cannot mount with prior project restoration',()=>{
 assert.equal(isProjectWorkspaceRestored('new-project','old-project','ready'),false);
 assert.equal(isProjectWorkspaceRestored('new-project',null,'ready'),false);
});

test('mounts only when selected project and completed restoration match',()=>{
 assert.equal(isProjectWorkspaceRestored('P0_SYNTHETIC_UI_ML_80','P0_SYNTHETIC_UI_ML_80','ready'),true);
 assert.equal(isProjectWorkspaceRestored('project B','project B','ready'),true);
});

test('catalogue validation must be ready even if restore IDs match',()=>{
 for(const state of ['loading','failed']){
  assert.equal(isProjectWorkspaceRestored('project B','project B',state),false);
 }
});

test('empty project import workspace is allowed after its empty-state restore',()=>{
 assert.equal(isProjectWorkspaceRestored('','', 'ready'),true);
 assert.equal(isProjectWorkspaceRestored('',null,'ready'),false);
});

test('switch A to B to A does not accept an outdated B restoration',()=>{
 const selected=['A','B','A'];
 const restored=['A','A','B'];
 assert.deepEqual(selected.map((id,i)=>isProjectWorkspaceRestored(id,restored[i],'ready')),[true,false,false]);
 assert.equal(isProjectWorkspaceRestored('A','A','ready'),true);
});

test('pure project-restoration gate preserves stored project keys and layout state',()=>{
 const layout={...DEFAULT_DOCK_LAYOUT,secondary:'prepare',side:'left',fraction:.42};
 const before=JSON.stringify(layout),keys=[dockStorageKey('A'),dockStorageKey('B')];
 assert.equal(isProjectWorkspaceRestored('A','B','ready'),false);
 assert.equal(JSON.stringify(layout),before);
 assert.notEqual(keys[0],keys[1]);
 assert.equal(hasRoomForDock(layout,950),true);
});

test('shell never mounts a project-specific App while restoration is mismatched',()=>{
 const source=fs.readFileSync(path.resolve(__dirname,'../src/UnifiedShell.tsx'),'utf8');
 assert.match(source,/import \{[^}]*isProjectWorkspaceRestored[^}]*\} from '\.\/workspaceLayout'/);
 assert.match(source,/const workspaceReady=isProjectWorkspaceRestored\(projectId,restoredFor,catalogState\)/);
 assert.match(source,/workspaceReady\?\(active==='investigate'\?/);
 assert.match(source,/studio-\$\{projectId\}/);
 assert.match(source,/Restoring this project’s saved tabs and dock before loading its data/);
});

test('project-specific tabs and secondary dock are gated until the same project is restored',()=>{
 const source=fs.readFileSync(path.resolve(__dirname,'../src/UnifiedShell.tsx'),'utf8');
 assert.match(source,/restoredFor===projectId\?openTabs\.filter\(isWorkspaceView\):\[\]/);
 assert.match(source,/const dockConfigured=!!projectId&&workspaceReady&&dock\.secondary!==null/);
 assert.match(source,/const canSplit=dockConfigured&&hasRoomForDock\(dock,paneWidth\)/);
 assert.match(source,/setRestoredFor\(projectId\)/);
 assert.match(source,/const savedDock=readDock\(projectId\)/);
 assert.match(source,/setDock\(savedDock\.secondary===preferred\?nextDockLayout\(savedDock,\{kind:'close'\}\):savedDock\)/);
 assert.match(source,/if\(restoredFor!==projectId\)return/);
});
