const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const ts=require('typescript');
const Module=require('node:module');
const filename=path.resolve(__dirname,'../src/workspaceLayout.ts');
const compiled=ts.transpileModule(fs.readFileSync(filename,'utf8'),{
  compilerOptions:{target:ts.ScriptTarget.ES2021,module:ts.ModuleKind.CommonJS}
}).outputText;
const m=new Module(filename,module);
m.filename=filename;m.paths=module.paths;m._compile(compiled,filename);
const {hasRoomForDock,DEFAULT_DOCK_LAYOUT,nextDockLayout,parseDockLayout,DOCK_DIVIDER_PX,DOCK_MIN_PANE_PX}=m.exports;
const opened=(fraction=.39)=>nextDockLayout({...DEFAULT_DOCK_LAYOUT,fraction},{kind:'open',view:'quality'});

test('never split when no dock is configured or width cannot be measured',()=>{
  assert.equal(hasRoomForDock(DEFAULT_DOCK_LAYOUT,1200),false);
  for(const width of [0,-1,NaN,Infinity])assert.equal(hasRoomForDock(opened(),width),false);
});

test('narrow content pauses saved dock even if overall browser viewport is wide',()=>{
  const dock=opened();
  for(const width of [250,590,680,750])assert.equal(hasRoomForDock(dock,width),false);
  assert.equal(hasRoomForDock(dock,800),true);
});

test('minimum width protects the primary and secondary panes at asymmetric fractions',()=>{
  const wideSecondary=opened(.58);
  assert.equal(hasRoomForDock(wideSecondary,710),false);
  assert.equal(hasRoomForDock(wideSecondary,750),true);
  const narrowSecondary=opened(.28);
  assert.equal(hasRoomForDock(narrowSecondary,800),false);
  assert.equal(hasRoomForDock(narrowSecondary,1100),true);
  assert.equal(DOCK_DIVIDER_PX,9);
  assert.equal(DOCK_MIN_PANE_PX,300);
});

test('a measured width transition does not erase saved dock or pane side',()=>{
  const selected=nextDockLayout(opened(.4),{kind:'flip'});
  const stored=JSON.stringify(selected);
  assert.equal(hasRoomForDock(selected,550),false);
  assert.equal(hasRoomForDock(selected,900),true);
  assert.equal(JSON.stringify(selected),stored);
  assert.deepEqual(parseDockLayout(JSON.parse(stored)),selected);
});

test('temporary width collapse cannot silently close or reset another project layout',()=>{
  const a=opened(.4),b=nextDockLayout(opened(.52),{kind:'flip'});
  hasRoomForDock(a,400);
  hasRoomForDock(b,1000);
  assert.equal(a.secondary,'quality');
  assert.equal(a.side,'right');
  assert.equal(b.side,'left');
  assert.equal(b.fraction,.52);
});

test('responsive shell measures actual content width and preserves configured dock state',()=>{
  const src=fs.readFileSync(path.resolve(__dirname,'../src/UnifiedShell.tsx'),'utf8');
  assert.match(src,/import \{[^}]*hasRoomForDock[^}]*\} from '\.\/workspaceLayout'/);
  assert.match(src,/const \[paneWidth,setPaneWidth\]=useState\(0\)/);
  assert.match(src,/new ResizeObserver\(read\)/);
  assert.match(src,/getBoundingClientRect\(\)\.width/);
  assert.match(src,/observer\.disconnect\(\)/);
  assert.match(src,/const canSplit=dockConfigured&&hasRoomForDock\(dock,paneWidth\)/);
  assert.match(src,/const dockPaused=dockConfigured&&!canSplit/);
  assert.match(src,/setDock\(readDock\(projectId\)\)/);
});

test('temporary collapse hides the resizer and secondary App, not the main workspace',()=>{
  const src=fs.readFileSync(path.resolve(__dirname,'../src/UnifiedShell.tsx'),'utf8');
  assert.match(src,/\{canSplit&&<>/);
  assert.match(src,/className="po-primary-pane"/);
  assert.match(src,/dockPaused&&<div className="po-dock-narrow-notice" role="status"/);
  assert.match(src,/!dockConfigured&&projectId&&<div className="po-dock-drop-target"/);
  assert.match(src,/embeddedProjectId=\{projectId\}/);
});

test('paused message remains discoverable and readable on narrow screens',()=>{
  const css=fs.readFileSync(path.resolve(__dirname,'../src/unified-shell.css'),'utf8');
  assert.match(css,/\.po-dock-narrow-notice\s*\{/);
  assert.match(css,/\.po-dock-narrow-notice svg\{flex:none\}/);
  assert.match(css,/@media\(max-width:650px\)/);
});
