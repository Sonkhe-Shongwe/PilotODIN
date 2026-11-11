const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const ts=require('typescript');
const Module=require('node:module');
const filename=path.resolve(__dirname,'../src/workspaceTabReorder.ts');
const compiled=ts.transpileModule(fs.readFileSync(filename,'utf8'),{
 compilerOptions:{target:ts.ScriptTarget.ES2021,module:ts.ModuleKind.CommonJS},
 reportDiagnostics:true
});
assert.deepEqual((compiled.diagnostics||[]).filter(d=>d.category===ts.DiagnosticCategory.Error),[]);
const mod=new Module(filename,module);
mod.filename=filename;mod.paths=module.paths;mod._compile(compiled.outputText,filename);
const {reorderWorkspaceTabs,shiftWorkspaceTab,canReorderWorkspaceTab}=mod.exports;
const initial=Object.freeze(['overview','quality','prepare','evaluate']);

test('Quality snaps before Home when dragged to its left edge',()=>{
 assert.deepEqual(reorderWorkspaceTabs(initial,'quality','overview','before'),
  ['quality','overview','prepare','evaluate']);
});
test('Home can move behind Quality',()=>{
 assert.deepEqual(reorderWorkspaceTabs(initial,'overview','quality','after'),
  ['quality','overview','prepare','evaluate']);
});
test('last tab can move first',()=>{
 assert.deepEqual(reorderWorkspaceTabs(initial,'evaluate','overview','before'),
  ['evaluate','overview','quality','prepare']);
});
test('first tab can move last',()=>{
 assert.deepEqual(reorderWorkspaceTabs(initial,'overview','evaluate','after'),
  ['quality','prepare','evaluate','overview']);
});
test('move to preceding or following position can be an exact no-op',()=>{
 assert.deepEqual(reorderWorkspaceTabs(initial,'overview','quality','before'),initial);
 assert.deepEqual(reorderWorkspaceTabs(initial,'prepare','quality','after'),initial);
 assert.deepEqual(reorderWorkspaceTabs(initial,'quality','quality','before'),initial);
});
test('unknown and stale sources or targets cannot alter open tabs',()=>{
 assert.deepEqual(reorderWorkspaceTabs(initial,'assistant','quality','before'),initial);
 assert.deepEqual(reorderWorkspaceTabs(initial,'quality','assistant','after'),initial);
 assert.deepEqual(reorderWorkspaceTabs(initial,'quality','prepare','sideways'),initial);
});
test('duplicate tab lists are rejected rather than silently losing a tab',()=>{
 assert.deepEqual(reorderWorkspaceTabs(['overview','quality','quality'],'quality','overview','before'),
  ['overview','quality','quality']);
});
test('source tab order and selection are not mutated',()=>{
 const original=[...initial];
 const result=reorderWorkspaceTabs(initial,'prepare','overview','before');
 assert.deepEqual(original,initial);
 assert.notEqual(result,initial);
 assert.equal(result.length,original.length);
});
test('keyboard move left and right updates only the chosen order',()=>{
 assert.deepEqual(shiftWorkspaceTab(initial,'quality',-1),['quality','overview','prepare','evaluate']);
 assert.deepEqual(shiftWorkspaceTab(initial,'quality',1),['overview','prepare','quality','evaluate']);
});
test('keyboard movement at either boundary is safe',()=>{
 assert.deepEqual(shiftWorkspaceTab(initial,'overview',-1),initial);
 assert.deepEqual(shiftWorkspaceTab(initial,'evaluate',1),initial);
 assert.deepEqual(shiftWorkspaceTab(initial,'assistant',1),initial);
});
test('drag requires same project, ready project and an open target',()=>{
 const drag={projectId:'A',view:'quality'};
 assert.equal(canReorderWorkspaceTab('A',true,drag,'overview',initial),true);
 assert.equal(canReorderWorkspaceTab('B',true,drag,'overview',initial),false);
 assert.equal(canReorderWorkspaceTab('A',false,drag,'overview',initial),false);
 assert.equal(canReorderWorkspaceTab('',true,drag,'overview',initial),false);
 assert.equal(canReorderWorkspaceTab('A',true,null,'overview',initial),false);
 assert.equal(canReorderWorkspaceTab('A',true,drag,'quality',initial),false);
 assert.equal(canReorderWorkspaceTab('A',true,drag,'model',initial),false);
});
test('tab strip has separate reorder/drop and dock targets',()=>{
 const shell=fs.readFileSync(path.resolve(__dirname,'../src/UnifiedShell.tsx'),'utf8');
 assert.match(shell,/import \{canReorderWorkspaceTab,reorderWorkspaceTabs,shiftWorkspaceTab\} from '\.\/workspaceTabReorder'/);
 assert.match(shell,/const onTabDragOver=/);
 assert.match(shell,/const onTabDrop=/);
 assert.match(shell,/setOpenTabs\(tabs=>reorderWorkspaceTabs\(tabs,dragged!\.view,target,side\)\)/);
 assert.match(shell,/draggable=\{!!projectId&&workspaceReady\}/);
 assert.match(shell,/onDragOver=\{event=>onTabDragOver\(event,view\)\} onDrop=\{event=>onTabDrop\(event,view\)\}/);
 assert.match(shell,/event\.dataTransfer\.setData\('text\/x-pilotodin-workspace',view\)/);
 assert.match(shell,/if\(isSecondaryView\(proposed\)\)dockView\(proposed\)/);
});
test('tab movement does not call navigation or quality/data writes',()=>{
 const helper=fs.readFileSync(filename,'utf8');
 assert.doesNotMatch(helper,/navigate\(|dockView\(|localStorage|sessionStorage|fetch\(|post\(|setActive|setDock/);
 const shell=fs.readFileSync(path.resolve(__dirname,'../src/UnifiedShell.tsx'),'utf8');
 assert.match(shell,/const draggedTab=useRef<\{projectId:string;view:View\}\|null>\(null\)/);
 assert.match(shell,/useEffect\(\(\)=>\{draggedTab\.current=null;setTabDropTarget\(null\);setPrimaryDockHover\(false\)\},\[projectId\]\)/);
});
test('project order is still saved and restored through existing scoped key',()=>{
 const shell=fs.readFileSync(path.resolve(__dirname,'../src/UnifiedShell.tsx'),'utf8');
 assert.match(shell,/const keyFor=\(id:string\)=>`pilotodin-workspace-tabs-v1-/);
 assert.match(shell,/setOpenTabs\(tabs\.includes\(preferred\)\?tabs:\[\.\.\.tabs,preferred\]\.slice\(-8\)\)/);
 assert.match(shell,/localStorage\.setItem\(keyFor\(projectId\),JSON\.stringify\(openTabs\)\)/);
});
test('keyboard alternative and drop edge indication are explicit',()=>{
 const shell=fs.readFileSync(path.resolve(__dirname,'../src/UnifiedShell.tsx'),'utf8');
 const css=fs.readFileSync(path.resolve(__dirname,'../src/unified-shell.css'),'utf8');
 assert.match(shell,/event\.altKey&&event\.shiftKey&&!event\.ctrlKey&&!event\.metaKey/);
 assert.match(shell,/setOpenTabs\(tabs=>shiftWorkspaceTab\(tabs,view,event\.key==='ArrowLeft'\?-1:1\)\)/);
 assert.match(shell,/po-tab-drop-\$\{tabDropTarget\.side\}/);
 assert.match(css,/\.po-tab-drop-before::before/);
 assert.match(css,/\.po-tab-drop-after::after/);
});

test('drag-to-dock accepts only matching project tabs in workspace content',()=>{
 const shell=fs.readFileSync(path.resolve(__dirname,'../src/UnifiedShell.tsx'),'utf8');
 const css=fs.readFileSync(path.resolve(__dirname,'../src/unified-shell.css'),'utf8');
 assert.match(shell,/const canDockOverPrimary=/);
 assert.match(shell,/dragged\.projectId===projectId/);
 assert.match(shell,/dragged\.view!==active/);
 assert.match(shell,/Array\.from\(event\.dataTransfer\.types\)\.includes\('text\/x-pilotodin-workspace'\)/);
 assert.match(shell,/onDragOver=\{onPrimaryDragOver\} onDragLeave=\{onPrimaryDragLeave\} onDrop=\{onPrimaryDrop\}/);
 assert.match(css,/\.po-primary-pane\.po-primary-dock-hover::after/);
 // Keep independent tab-strip reorder behaviour: dropping on a tab does not dock.
 assert.match(shell,/onDrop=\{event=>onTabDrop\(event,view\)\}/);
});
