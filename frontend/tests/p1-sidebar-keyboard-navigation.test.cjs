const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const ts=require('typescript');
const Module=require('node:module');

const file=path.resolve(__dirname,'../src/sidebarKeyboardNavigation.ts');
const compiled=ts.transpileModule(fs.readFileSync(file,'utf8'),{
  compilerOptions:{target:ts.ScriptTarget.ES2021,module:ts.ModuleKind.CommonJS},
  reportDiagnostics:true
});
assert.deepEqual((compiled.diagnostics||[]).filter(x=>x.category===ts.DiagnosticCategory.Error),[]);
const loader=new Module(file,module);loader.filename=file;loader.paths=module.paths;
loader._compile(compiled.outputText,file);
const {nextSidebarViewByKey}=loader.exports;
const views=Object.freeze(['overview','understand','investigate','quality','explore','prepare','model','evaluate','predict','deliver','assistant','ai_settings']);

test('Down Arrow on Home navigates to Your data rather than scrolling',()=>{
  assert.equal(nextSidebarViewByKey(views,'overview','ArrowDown'),'understand');
});

test('Up Arrow on Your data navigates back to Home',()=>{
  assert.equal(nextSidebarViewByKey(views,'understand','ArrowUp'),'overview');
});

test('Down crosses from WORKSPACE to ANALYSIS in rendered order',()=>{
  assert.equal(nextSidebarViewByKey(views,'understand','ArrowDown'),'investigate');
});

test('Down crosses section boundary from Explore to Prepare',()=>{
  assert.equal(nextSidebarViewByKey(views,'explore','ArrowDown'),'prepare');
});

test('navigation wraps at the beginning and end without losing focus',()=>{
  assert.equal(nextSidebarViewByKey(views,'overview','ArrowUp'),'ai_settings');
  assert.equal(nextSidebarViewByKey(views,'ai_settings','ArrowDown'),'overview');
});

test('Home and End navigate to first and last sidebar destinations',()=>{
  assert.equal(nextSidebarViewByKey(views,'quality','Home'),'overview');
  assert.equal(nextSidebarViewByKey(views,'quality','End'),'ai_settings');
});

test('native Tab, Enter, Space, Escape, left/right and other keys pass through',()=>{
  for(const key of ['Tab','Enter',' ','Escape','ArrowLeft','ArrowRight','PageDown','w']){
    assert.equal(nextSidebarViewByKey(views,'overview',key),null);
  }
});

test('empty or unknown navigation item never triggers an action',()=>{
  assert.equal(nextSidebarViewByKey([], 'overview','ArrowDown'),null);
  assert.equal(nextSidebarViewByKey(views,'not-a-view','ArrowDown'),null);
});

test('selection logic does not alter rendered order or project data',()=>{
  const before=[...views];
  nextSidebarViewByKey(views,'overview','ArrowDown');
  assert.deepEqual(views,before);
});

test('rendered sidebar order aligns with helper from Home through Settings',()=>{
  const shell=fs.readFileSync(path.resolve(__dirname,'../src/UnifiedShell.tsx'),'utf8');
  assert.match(shell,/const sidebarViews=useMemo\(\(\)=>NAV_SECTIONS\.flatMap\(section=>section\.ids\),\[\]\)/);
  assert.match(shell,/title:'WORKSPACE',ids:\['overview','understand'\]/);
  assert.match(shell,/title:'ANALYSIS',ids:\['investigate','quality','explore'\]/);
  assert.match(shell,/title:'MODELLING & DELIVERY',ids:\['prepare','model','evaluate','predict','deliver'\]/);
  assert.match(shell,/title:'ASSISTANCE',ids:\['assistant','ai_settings'\]/);
});

test('sidebar handles only unmodified navigation keys and focuses the destination',()=>{
  const shell=fs.readFileSync(path.resolve(__dirname,'../src/UnifiedShell.tsx'),'utf8');
  assert.match(shell,/import \{nextSidebarViewByKey\} from '\.\/sidebarKeyboardNavigation'/);
  assert.match(shell,/onSidebarKeyDown=\(event:ReactKeyboardEvent<HTMLButtonElement>,view:View\)=>/);
  assert.match(shell,/if\(event\.altKey\|\|event\.ctrlKey\|\|event\.metaKey\|\|event\.shiftKey\)return/);
  assert.match(shell,/const next=nextSidebarViewByKey\(sidebarViews,view,event\.key\)/);
  assert.match(shell,/if\(!next\)return;\s*event\.preventDefault\(\)/);
  assert.match(shell,/closest\('#po-nav-items'\)\?\.querySelectorAll<HTMLButtonElement>\('\.po-nav-item'\)/);
  assert.match(shell,/buttons\?\.item\(sidebarViews\.indexOf\(next\)\)\?\.focus\(\)/);
  assert.match(shell,/if\(next!==active&&!navigateWithDockGuard\(next\)\)return/);
});

test('sidebar label buttons get key handlers without changing existing click or tab controls',()=>{
  const shell=fs.readFileSync(path.resolve(__dirname,'../src/UnifiedShell.tsx'),'utf8');
  assert.match(shell,/aria-label=\{label\} onKeyDown=\{event=>onSidebarKeyDown\(event,id\)\} onClick=\{\(\)=>navigateWithDockGuard\(id\)\}/);
  assert.match(shell,/aria-current=\{active===id\?'page':undefined\}/);
  assert.match(shell,/import \{nextWorkspaceTabByKey\} from '\.\/workspaceTabKeyboard'/);
  assert.match(shell,/onKeyDown=\{event=>onWorkspaceTabKeyDown\(event,view\)\}/);
  assert.match(shell,/className="po-rail-toggle"/);
  assert.match(shell,/workspaceReady=isProjectWorkspaceRestored\(projectId,restoredFor,catalogState\)/);
});
