const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const ts=require('typescript');
const Module=require('node:module');

const filename=path.resolve(__dirname,'../src/workspaceTabKeyboard.ts');
const compiled=ts.transpileModule(fs.readFileSync(filename,'utf8'),{
  compilerOptions:{target:ts.ScriptTarget.ES2021,module:ts.ModuleKind.CommonJS},
  reportDiagnostics:true
});
assert.deepEqual((compiled.diagnostics||[]).filter(d=>d.category===ts.DiagnosticCategory.Error),[]);
const m=new Module(filename,module);m.filename=filename;m.paths=module.paths;
m._compile(compiled.outputText,filename);
const {nextWorkspaceTabByKey}=m.exports;
const tabs=Object.freeze(['overview','quality','prepare','model','predict']);

test('Right Arrow advances focus selection one workspace',()=>{
  assert.equal(nextWorkspaceTabByKey(tabs,'quality','ArrowRight'),'prepare');
});

test('Left Arrow moves focus selection backward one workspace',()=>{
  assert.equal(nextWorkspaceTabByKey(tabs,'prepare','ArrowLeft'),'quality');
});

test('Arrow keys wrap first and last tabs',()=>{
  assert.equal(nextWorkspaceTabByKey(tabs,'overview','ArrowLeft'),'predict');
  assert.equal(nextWorkspaceTabByKey(tabs,'predict','ArrowRight'),'overview');
});

test('Home and End select first and last open tab',()=>{
  assert.equal(nextWorkspaceTabByKey(tabs,'prepare','Home'),'overview');
  assert.equal(nextWorkspaceTabByKey(tabs,'prepare','End'),'predict');
});

test('unhandled native browser keys do not change the workspace',()=>{
  for(const key of ['Tab','Escape','Enter',' ','PageUp','PageDown','w']){
    assert.equal(nextWorkspaceTabByKey(tabs,'prepare',key),null);
  }
});

test('unknown, unmounted and empty workspace tabs do not navigate',()=>{
  assert.equal(nextWorkspaceTabByKey(tabs,'assistant','ArrowRight'),null);
  assert.equal(nextWorkspaceTabByKey([],'overview','Home'),null);
});

test('selector is pure and does not alter tabs or saved project state',()=>{
  const before=[...tabs];
  nextWorkspaceTabByKey(tabs,'model','ArrowRight');
  assert.deepEqual(tabs,before);
});

test('shell keyboard event handles only unmodified keys, prevents only handled default, and focuses next tab',()=>{
  const source=fs.readFileSync(path.resolve(__dirname,'../src/UnifiedShell.tsx'),'utf8');
  assert.match(source,/import \{nextWorkspaceTabByKey\} from '\.\/workspaceTabKeyboard'/);
  assert.match(source,/onWorkspaceTabKeyDown=\(event:ReactKeyboardEvent<HTMLButtonElement>,view:View\)=>/);
  assert.match(source,/if\(event\.altKey\|\|event\.ctrlKey\|\|event\.metaKey\|\|event\.shiftKey\)return/);
  assert.match(source,/const next=nextWorkspaceTabByKey\(shownTabs,view,event\.key\)/);
  assert.match(source,/if\(!next\)return;\s*event\.preventDefault\(\)/);
  assert.match(source,/tabButtons\?\.item\(shownTabs\.indexOf\(next\)\)\?\.focus\(\)/);
  assert.match(source,/if\(next!==active&&!navigateWithDockGuard\(next\)\)return/);
});

test('tablist uses one roving tab stop with explicit selected state and labelled panel',()=>{
  const source=fs.readFileSync(path.resolve(__dirname,'../src/UnifiedShell.tsx'),'utf8');
  assert.ok(source.includes('role="tablist" aria-label="Open analytical workspaces"'));
  assert.ok(source.includes('role="tab" id={'));
  assert.ok(source.includes('aria-controls="po-current-workspace" aria-selected={active===view} tabIndex={active===view?0:-1}'));
  assert.ok(source.includes('role="tabpanel" aria-labelledby={'));
  assert.ok(source.includes('onKeyDown={event=>onWorkspaceTabKeyDown(event,view)}'));
});

test('existing tab docking, closing, project gating and focus-visible CSS remain intact',()=>{
  const src=fs.readFileSync(path.resolve(__dirname,'../src/UnifiedShell.tsx'),'utf8');
  const css=fs.readFileSync(path.resolve(__dirname,'../src/unified-shell.css'),'utf8');
  assert.match(src,/workspaceReady=isProjectWorkspaceRestored\(projectId,restoredFor,catalogState\)/);
  assert.match(src,/onClick=\{\(\)=>dockView\(view\)\}/);
  assert.match(src,/onClick=\{\(\)=>close\(view\)\}/);
  assert.match(src,/const dockConfigured=!!projectId&&workspaceReady&&dock\.secondary!==null/);
  assert.match(css,/\.po-global-tabs button:focus-visible/);
});
