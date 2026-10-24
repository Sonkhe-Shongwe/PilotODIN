/* Run with npm run test:workspace, or NODE_PATH=<global node_modules> node --test ... */
const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const source=fs.readFileSync(path.join(__dirname,'../src/workspaceLayout.ts'),'utf8');
const ts=require('typescript');
const compiled=ts.transpileModule(source,{compilerOptions:{target:ts.ScriptTarget.ES2021,module:ts.ModuleKind.CommonJS},reportDiagnostics:true});
assert.equal((compiled.diagnostics||[]).filter(d=>d.category===ts.DiagnosticCategory.Error).length,0);
const exportsObj={};new Function('exports','module',compiled.outputText)(exportsObj,{exports:exportsObj});
const L=exportsObj;
test('unsupported, old and malformed layouts reset to defaults',()=>{
 for(const value of [null,'hi',[],{schema:1,secondary:'quality',side:'left',fraction:.4},{schema:99}])
  assert.deepEqual(L.parseDockLayout(value),L.DEFAULT_DOCK_LAYOUT);
});
test('project layout state is isolated and identifiers cannot overlap storage keys',()=>{
 const keys=['project/a','project-a','project a','A&B','B'].map(L.dockStorageKey);
 assert.equal(new Set(keys).size,keys.length);
 assert.equal(L.dockStorageKey('one'),L.dockStorageKey('one'));
});
test('only recognised analytical components are dockable',()=>{
 for(const view of ['quality','explore','model','deliver','prepare','evaluate','predict','assistant','ai_settings','understand'])assert.equal(L.isSecondaryView(view),true);
 for(const view of ['investigate','overview','../../injected',null,{},123])assert.equal(L.isSecondaryView(view),false);
});
test('cannot dock the primary investigation or home screen in the secondary pane',()=>{
 const original={...L.DEFAULT_DOCK_LAYOUT};
 assert.deepEqual(L.nextDockLayout(original,{kind:'open',view:'investigate'}),original);
 assert.deepEqual(L.nextDockLayout(original,{kind:'open',view:'overview'}),original);
});
test('secondary component, side and width are retained after serialization',()=>{
 let layout=L.nextDockLayout(L.DEFAULT_DOCK_LAYOUT,{kind:'open',view:'explore'});
 layout=L.nextDockLayout(layout,{kind:'resize',fraction:.42});
 layout=L.nextDockLayout(layout,{kind:'flip'});
 assert.deepEqual(L.parseDockLayout(JSON.parse(JSON.stringify(layout))),layout);
 assert.equal(layout.side,'left');assert.equal(layout.secondary,'explore');
});
test('corrupted values do not trigger arbitrary tools or massive pane widths',()=>{
 assert.equal(L.parseDockLayout({schema:2,secondary:'eval(\"danger\")',side:'window',fraction:1e100}).secondary,null);
 assert.equal(L.parseDockLayout({schema:2,secondary:'quality',side:'left',fraction:-100}).fraction,.28);
 assert.equal(L.parseDockLayout({schema:2,secondary:'quality',side:'left',fraction:NaN}).fraction,.39);
});
test('pointer resizer respects correct side and bounds',()=>{
 const right=L.nextDockLayout(L.DEFAULT_DOCK_LAYOUT,{kind:'open',view:'quality'});
 const left=L.nextDockLayout(right,{kind:'flip'});
 assert.ok(Math.abs(L.makeDockResize(right,650,100,1000).fraction-.45)<1e-9);
 assert.ok(Math.abs(L.makeDockResize(left,550,100,1000).fraction-.45)<1e-9);
 assert.equal(L.makeDockResize(right,-300,100,1000).fraction,.58);
 assert.equal(L.makeDockResize(left,-300,100,1000).fraction,.28);
});
test('keyboard resizing and reset never mutate existing layout',()=>{
 const original={...L.DEFAULT_DOCK_LAYOUT};
 const wide=L.nextDockLayout(original,{kind:'resize',fraction:.55});
 assert.equal(L.nextDockLayout(wide,{kind:'close'}).secondary,null);
 assert.equal(L.nextDockLayout(wide,{kind:'reset'}).fraction,.39);
 assert.deepEqual(original,L.DEFAULT_DOCK_LAYOUT);
});
test('frontend app contains separate route and embedded-state boundaries',()=>{
 const app=fs.readFileSync(path.join(__dirname,'../src/App.tsx'),'utf8');
 const shell=fs.readFileSync(path.join(__dirname,'../src/UnifiedShell.tsx'),'utf8');
 assert.match(app,/if\(embedded\)\{[\s\S]*?if\(!isSecondaryView\(next\)\)[\s\S]*?onEmbeddedNavigate\?\.\(next\)/);
 assert.match(app,/if\(location\.hash!==`#\/studio\/\$\{next\}`\)/);
 assert.match(app,/if\(!embedded\)localStorage\.setItem\('pilotodin-current'/);
 assert.match(shell,/embeddedProjectId=\{projectId\}/);
 assert.match(shell,/aria-label="Resize secondary analytical pane"/);
 assert.match(shell,/aria-label="Docked analytical component"/);
 assert.match(app,/if\(embedded && pid!==embeddedProjectId\)/);
 assert.match(app,/if\(embedded\)\{setError\('Import a new dataset from the primary workspace/);
});

test('unavailable saved project is reset only when its selection remains current',()=>{
 const projects=[{id:'B'},{id:'C'}];
 assert.equal(L.shouldClearUnavailableProject('A','A',projects),true);
 assert.equal(L.shouldClearUnavailableProject('A','B',projects),false);
 assert.equal(L.shouldClearUnavailableProject('','',projects),false);
 assert.equal(L.shouldClearUnavailableProject('B','B',projects),false);
 assert.equal(L.shouldClearUnavailableProject('deleted','',projects),false);
});
test('project selector reconciliation is connected to the persistent shell',()=>{
 const shell=fs.readFileSync(path.join(__dirname,'../src/UnifiedShell.tsx'),'utf8');
 assert.match(shell,/shouldClearUnavailableProject\(selectedAtRequestStart,latest,rows\)/);
 assert.match(shell,/localStorage\.removeItem\('pilotodin-current'\)/);
 assert.match(shell,/setWarning\('The previously selected project is no longer available/);
});


test('project-dependent views wait for catalogue validation and expose retry on failure',()=>{
 const shell=fs.readFileSync(path.join(__dirname,'../src/UnifiedShell.tsx'),'utf8');
 assert.match(shell,/catalogState,setCatalogState/);
 assert.match(shell,/setCatalogState\('ready'\)/);
 assert.match(shell,/catalogState==='ready'\?\(active==='investigate'/);
 assert.match(shell,/Checking that the saved project belongs to this local workspace/);
 assert.match(shell,/catalogState==='failed'&&<button[^>]+onClick=/);
 assert.match(shell,/setCatalogState\(previous=>previous==='ready'\?'ready':'failed'\)/);
 assert.match(shell,/key=\{`studio-\$\{projectId\}`\}/);
});
