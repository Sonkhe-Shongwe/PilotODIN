'use strict';
const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const Module=require('node:module');
const ts=require('../node_modules/typescript');
const src=path.join(__dirname,'../src');
const read=name=>fs.readFileSync(path.join(src,name),'utf8');
const compiled=ts.transpileModule(read('shellClockFormat.ts'),{
 reportDiagnostics:true,compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022}
});
assert.equal(compiled.diagnostics?.filter(x=>x.category===ts.DiagnosticCategory.Error).length||0,0);
const m=new Module(path.join(src,'shellClockFormat.ts'));
m.filename=path.join(src,'shellClockFormat.ts');
m.paths=Module._nodeModulePaths(src);
m._compile(compiled.outputText,m.filename);
const {formatShellClock,msUntilNextClockMinute}=m.exports;

test('clock uses stable 24-hour local HH:mm without ticking seconds',()=>{
 const d=new Date(2026,10,10,23,34,59);
 const clock=formatShellClock(d,'en-GB');
 assert.equal(clock.time,'23:34');
 assert.match(clock.date,/^TUE · 10 NOV$/);
 assert.match(clock.fullDescription,/2026/);
 assert.match(clock.fullDescription,/23:34/);
 assert.match(clock.fullDescription,/time|[A-Z]{3,}/i);
});
test('clock rolls to midnight and next date with the local Date',()=>{
 const d=new Date(2026,10,11,0,0,0);
 const clock=formatShellClock(d,'en-GB');
 assert.equal(clock.time,'00:00');
 assert.equal(clock.date,'WED · 11 NOV');
});
test('minute-boundary rescheduling accounts for drift after wake',()=>{
 assert.equal(msUntilNextClockMinute(0),60035);
 assert.equal(msUntilNextClockMinute(59999),36);
 assert.equal(msUntilNextClockMinute(60999),59036);
 assert.ok(msUntilNextClockMinute(179999)<100);
});
test('clock is a single persistent shell element before project controls',()=>{
 const shell=read('UnifiedShell.tsx');
 const clock=read('ShellClock.tsx');
 const css=read('unified-shell.css');
 assert.match(shell,/import \{ShellClock\} from '\.\/ShellClock'/);
 assert.equal((shell.match(/<ShellClock\s*\/>/g)||[]).length,1);
 const header=shell.split('<header className="po-shell-title">')[1].split('</header>')[0];
 assert.ok(header.indexOf('<ShellClock/>')>header.indexOf('po-shell-mode'));
 assert.ok(header.indexOf('<ShellClock/>')<header.indexOf('po-project-switcher'));
 assert.match(clock,/dateTime=\{now\.toISOString\(\)\}/);
 assert.match(clock,/aria-label=\{display\.fullDescription\}/);
 assert.doesNotMatch(clock,/aria-live=|setInterval|fetch\(|localStorage|post\(/);
 assert.match(clock,/visibilitychange/);
 assert.match(clock,/window\.addEventListener\('focus',refresh\)/);
 assert.match(clock,/window\.removeEventListener\('focus',refresh\)/);
 assert.match(css,/font-variant-numeric:tabular-nums/);
 assert.match(css,/@media\(max-width:1200px\)/);
 assert.match(css,/@media\(max-width:1000px\)\{\.po-shell-clock\{display:none\}\}/);
 assert.doesNotMatch(cssExtraFromClock(css),/backdrop-filter/);
});
function cssExtraFromClock(css){return css.slice(css.lastIndexOf('/* Satin Chronograph:'))}
