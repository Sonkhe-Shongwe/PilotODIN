const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const src=fs.readFileSync(path.resolve(__dirname,'../src/UnifiedShell.tsx'),'utf8');
const css=fs.readFileSync(path.resolve(__dirname,'../src/unified-shell.css'),'utf8');

test('responsive pause is independent of saved dock layout',()=>{
 assert.match(src,/const dockConfigured=!!projectId&&workspaceReady&&dock\.secondary!==null/);
 assert.match(src,/const canSplit=dockConfigured&&hasRoomForDock\(dock,paneWidth\)/);
 assert.match(src,/const dockPaused=dockConfigured&&!canSplit/);
 assert.match(src,/setDock\(savedDock\.secondary===preferred\?nextDockLayout\(savedDock,\{kind:'close'\}\):savedDock\)/);
});
test('an already edited same-project/same-view dock remains mounted when narrow',()=>{
 assert.match(src,/const preservePausedEditedDock=dockPaused&&active!==dock\.secondary&&\s*editedDock\.current\?\.projectId===projectId&&editedDock\.current\?\.view===dock\.secondary/);
 assert.match(src,/const mountDock=canSplit\|\|preservePausedEditedDock/);
 assert.match(src,/const separate=mountDock&&active!==dock\.secondary/);
 assert.match(src,/\{mountDock&&<>/);
 assert.match(src,/\{separate\?<div className="po-pane-content"/);
});
test('unchanged docked workspaces may still unmount when narrow to save memory',()=>{
 assert.ok(src.includes('const mountDock=canSplit||preservePausedEditedDock'));
 assert.ok(!src.includes('const mountDock=dockConfigured'));
});
test('hidden edited pane and splitter cannot be focused when narrow',()=>{
 assert.match(src,/className="po-pane-resizer" hidden=\{!canSplit\}/);
 assert.match(src,/className="po-secondary-pane" hidden=\{!canSplit\}/);
 assert.match(src,/tabIndex=\{canSplit\?0:-1\}/);
 assert.match(css,/\.po-pane-layout:not\(\.po-pane-split\)>\.po-secondary-pane\[hidden\]/);
 assert.match(css,/\.po-pane-layout:not\(\.po-pane-split\)>\.po-pane-resizer\[hidden\]/);
 assert.match(css,/display:none!important/);
});
test('window resizing alone cannot clear an edited marker while pane is retained',()=>{
 assert.match(src,/if\(!separate\)editedDock\.current=null/);
 assert.doesNotMatch(src,/if\(!canSplit\)editedDock\.current=null/);
 assert.match(src,/\},\[separate,projectId,dock\.secondary\]\)/);
});
test('input changes remain scoped to the dock content and not its toolbar',()=>{
 assert.match(src,/onChangeCapture=\{event=>\{if\(dock\.secondary&&isEditableDockInput\(\(event\.target as HTMLElement\)\.tagName\)\)editedDock\.current=\{projectId,view:dock\.secondary\}\}\}/);
 assert.doesNotMatch(src,/<section className="po-secondary-pane"[^>]*onChangeCapture=/);
});
test('user sees an honest in-memory pause notice without an autosave claim',()=>{
 assert.match(src,/preservePausedEditedDock\?'Edited docked fields are kept in memory while this view is narrow \(not saved\)/);
 assert.doesNotMatch(src,/localStorage\.setItem\([^\n]*predictVals|sessionStorage\.setItem\([^\n]*predictVals/);
});
test('existing discard approval remains required for explicit destructive actions',()=>{
 assert.match(src,/confirmEditedDockDiscard\('close'\)/);
 assert.match(src,/confirmEditedDockDiscard\('replace',view\)/);
 assert.match(src,/confirmEditedDockDiscard\('close-tab'\)/);
 assert.match(src,/confirmEditedDockDiscard\('activate',view\)/);
 assert.match(src,/confirmEditedDockDiscard\('reset'\)/);
 assert.match(src,/confirmEditedDockDiscard\('switch-project'\)/);
});
test('responsive code does not introduce a data-write, training or approval side effect',()=>{
 const section=src.slice(src.indexOf('const dockConfigured='),src.indexOf('const paneStyle='));
 assert.doesNotMatch(section,/\bpost\(|\bfetch\(|train\(|applyCorrection|approve\(|setProjectId|localStorage/);
});
