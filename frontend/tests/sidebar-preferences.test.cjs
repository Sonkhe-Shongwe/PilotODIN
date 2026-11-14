const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const ts=require('typescript');
const input=fs.readFileSync(path.join(__dirname,'../src/sidebarPreferences.ts'),'utf8');
const output=ts.transpileModule(input,{compilerOptions:{target:ts.ScriptTarget.ES2021,module:ts.ModuleKind.CommonJS}});
const mod={exports:{}};new Function('exports','module',output.outputText)(mod.exports,mod);
test('new wide screens default expanded and narrow ones default compact',()=>{
 assert.equal(mod.exports.resolveSidebarMode(null,1680),'expanded');
 assert.equal(mod.exports.resolveSidebarMode(null,720),'compact');
});
test('stored user choice is honoured on all viewport sizes',()=>{
 assert.equal(mod.exports.resolveSidebarMode('expanded',375),'expanded');
 assert.equal(mod.exports.resolveSidebarMode('compact',2000),'compact');
});
test('corrupted stored values are not accepted',()=>{
 assert.equal(mod.exports.resolveSidebarMode('nope',1200),'expanded');
 assert.equal(mod.exports.resolveSidebarMode({},700),'compact');
});
test('sidebar actions are accessible and persist',()=>{
 const shell=fs.readFileSync(path.join(__dirname,'../src/UnifiedShell.tsx'),'utf8');
 assert.match(shell,/aria-expanded=\{sidebarMode==='expanded'\}/);
 assert.match(shell,/localStorage\.setItem\(SIDEBAR_KEY,next\)/);
 assert.match(shell,/NAV_SECTIONS\.map/);
 assert.match(shell,/po-nav-backdrop/);
});
