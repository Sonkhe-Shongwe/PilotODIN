const{test}=require('node:test');const assert=require('node:assert/strict');const fs=require('node:fs');const path=require('node:path');
const read=p=>fs.readFileSync(path.join(__dirname,'../src',p),'utf8');
const app=read('App.tsx'),shell=read('UnifiedShell.tsx'),css=read('unified-shell.css'),tokens=read('design-tokens.css');
test('Stage changes animate a keyed visual container, not the full App',()=>{assert.match(app,/className="content po-motion-stage" id="workspace-content" key=\{/);assert.match(css,/\.po-pane-content \.studio-app \.content\.po-motion-stage/);});
test('Sidebar labels stay in the DOM during compact transition',()=>{assert.match(css,/\.po-global-rail\.po-rail-compact \.po-nav-label\{display:block;/);assert.match(css,/flex-basis var\(--po-motion-sidebar\)/);});
test('Mobile backdrop supports exit fade and disables closed control',()=>{assert.match(shell,/aria-hidden=\{sidebarMode!=='expanded'\}/);assert.match(shell,/disabled=\{sidebarMode!=='expanded'\}/);assert.match(css,/\.po-nav-backdrop\.po-nav-backdrop-open/);});
test('Controls have press response, motion respects accessibility',()=>{assert.match(css,/\.studio-app \.btn:active:not\(:disabled\)/);assert.match(css,/@media\(prefers-reduced-motion:reduce\)/);assert.match(tokens,/--po-motion-stage: 500ms/);});

test('Navigation uses an actual outgoing phase and synchronous route commit',()=>{
 const motion=read('navigationMotion.ts');
 assert.match(motion,/out.finished.then/);
 assert.match(motion,/flushSync\(/);
 assert.match(motion,/pilotodin:route-commit/);
 assert.match(motion,/prefers-reduced-motion: reduce/);
 assert.match(shell,/navigateHashSmoothly\(v==='investigate'/);
 assert.match(shell,/addEventListener\('pilotodin:route-commit'/);
 assert.match(app,/navigateHashSmoothly\(`#\/studio\/\$\{next\}`/);
 assert.match(css,/view-transition-name:none!important/);
});
test('Simple page navigation does not refresh projects via HTTP',()=>{
 assert.match(shell,/const onRoute=\(\)=>setActive\(routeView\(\)\)/);
 assert.doesNotMatch(shell,/const onRoute=\(\)=>\{setActive\(routeView\(\)\);update\(\)\}/);
});
test('Sidebar icon remains mounted and rotates, and active highlight fades',()=>{
 assert.match(shell,/<PanelLeftClose className="po-toggle-glyph"/);
 assert.doesNotMatch(shell,/sidebarMode==='expanded'\?<PanelLeftClose/);
 assert.match(css,/\.po-rail-compact \.po-toggle-glyph\{transform:rotate\(180deg\)\}/);
 assert.match(css,/\.po-rail-active::after\{opacity:1\}/);
});
