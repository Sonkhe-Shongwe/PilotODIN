const{test}=require('node:test');const assert=require('node:assert/strict');const fs=require('node:fs');const path=require('node:path');
const read=p=>fs.readFileSync(path.join(__dirname,'../src',p),'utf8');
const app=read('App.tsx'),shell=read('UnifiedShell.tsx'),css=read('unified-shell.css'),tokens=read('design-tokens.css');
test('Stage changes animate a keyed visual container, not the full App',()=>{assert.match(app,/className="content po-motion-stage" id="workspace-content" key=\{/);assert.match(css,/\.po-pane-content \.studio-app \.content\.po-motion-stage/);});
test('Sidebar labels stay in the DOM during compact transition',()=>{assert.match(css,/\.po-global-rail\.po-rail-compact \.po-nav-label\{display:block;/);assert.match(css,/flex-basis var\(--po-motion-sidebar\)/);});
test('Mobile backdrop supports exit fade and disables closed control',()=>{assert.match(shell,/aria-hidden=\{sidebarMode!=='expanded'\}/);assert.match(shell,/disabled=\{sidebarMode!=='expanded'\}/);assert.match(css,/\.po-nav-backdrop\.po-nav-backdrop-open/);});
test('Controls have press response, motion respects accessibility',()=>{assert.match(css,/\.studio-app \.btn:active:not\(:disabled\)/);assert.match(css,/@media\(prefers-reduced-motion:reduce\)/);assert.match(tokens,/--po-motion-stage: 220ms/);});
