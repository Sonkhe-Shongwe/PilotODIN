const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const ts=require('typescript');
const vm=require('node:vm');

const srcRoot=path.join(__dirname,'../src');
const source=fs.readFileSync(path.join(srcRoot,'reportComposerGate.ts'),'utf8');
const compiled=ts.transpileModule(source,{compilerOptions:{
 target:ts.ScriptTarget.ES2021,module:ts.ModuleKind.CommonJS
},reportDiagnostics:true});
assert.equal(compiled.diagnostics?.length,0);
const exported={};
vm.runInNewContext(compiled.outputText,{exports:exported},{filename:'reportComposerGate.js'});
const {ReportReadGate,ReportComposerGate}=exported;
const ui=fs.readFileSync(path.join(srcRoot,'ReportWorkspace.tsx'),'utf8');

function deferred(){
 let resolve,reject;
 const promise=new Promise((yes,no)=>{resolve=yes;reject=no});
 return {promise,resolve,reject};
}

test('BEHAVIOR: older initial evidence result cannot replace newer post-audit list',async()=>{
 const guard=new ReportReadGate();
 const initial=guard.beginEvidence(),a=deferred();
 const newer=guard.beginEvidence(),b=deferred();
 const displayed=[];
 const oldPending=a.promise.then(v=>{if(guard.isCurrentEvidence(initial))displayed.push(v)});
 const newPending=b.promise.then(v=>{if(guard.isCurrentEvidence(newer))displayed.push(v)});
 b.resolve(['new audit']);a.resolve(['old items']);
 await Promise.all([oldPending,newPending]);
 assert.equal(displayed.length,1);
 assert.deepEqual(displayed[0],['new audit']);
});

test('BEHAVIOR: project switch suppresses delayed evidence and export responses',async()=>{
 const reads=new ReportReadGate();
 const view=new ReportComposerGate();
 const evidenceTicket=reads.beginEvidence();
 const exportTicket=reads.beginExport();
 const viewTicket=view.currentView();
 const response=deferred();
 const writes=[];
 const run=response.promise.then(v=>{
  if(view.isCurrentView(viewTicket)&&reads.isCurrentExport(exportTicket))writes.push(v);
 });
 view.resetProject();reads.invalidateAll();
 response.resolve({filename:'previous-project.html'});
 await run;
 assert.deepEqual(writes,[]);
 assert.equal(reads.isCurrentEvidence(evidenceTicket),false);
 assert.equal(reads.isCurrentExport(exportTicket),false);
});

test('BEHAVIOR: a newer export supersedes the first before any Save As operation',async()=>{
 const reads=new ReportReadGate();
 const view=new ReportComposerGate();
 const old=reads.beginExport(),a=deferred();
 const newest=reads.beginExport(),b=deferred();
 const v=view.currentView();
 const saveAsCalls=[];
 const first=a.promise.then(name=>{
  if(view.isCurrentView(v)&&reads.isCurrentExport(old))saveAsCalls.push(name);
 });
 const second=b.promise.then(name=>{
  if(view.isCurrentView(v)&&reads.isCurrentExport(newest))saveAsCalls.push(name);
 });
 a.resolve('old.pdf');b.resolve('current.pdf');
 await Promise.all([first,second]);
 assert.deepEqual(saveAsCalls,['current.pdf']);
});

test('BEHAVIOR: navigation invalidates delayed export without mutating backend report',()=>{
 const gate=new ReportComposerGate();
 const token=gate.currentView();
 assert.equal(gate.isCurrentView(token),true);
 gate.navigate();
 assert.equal(gate.isCurrentView(token),false);
 assert.equal(gate.isCurrentView(gate.currentView()),true);
});

test('INTEGRATION: initial and refreshed evidence reads require current ticket',()=>{
 assert.match(ui,/const initialEvidenceTicket=readGuard\.current\.beginEvidence\(\)/);
 assert.match(ui,/mounted&&readGuard\.current\.isCurrentEvidence\(initialEvidenceTicket\)/);
 assert.match(ui,/const evidenceTicket=readGuard\.current\.beginEvidence\(\)/);
 assert.match(ui,/!readGuard\.current\.isCurrentEvidence\(evidenceTicket\)/);
 assert.match(ui,/readGuard\.current\.invalidateAll\(\)/);
});

test('INTEGRATION: after loading an export, stale views cannot launch native or browser saves',()=>{
 assert.match(ui,/const viewTicket=composerGuard\.current\.currentView\(\)/);
 assert.match(ui,/const exportTicket=readGuard\.current\.beginExport\(\)/);
 assert.match(ui,/if\(!isCurrent\(\)\)return; \/\/ Never launch Save As/);
 assert.match(ui,/if\(!isCurrent\(\)\)return; \/\/ An already-open native dialog/);
 assert.match(ui,/await saveReportNative\(blob,filename,format\)/);
 assert.match(ui,/finally\{if\(isCurrent\(\)\)setBusy\(''\)\}/);
});

test('INTEGRATION: draft edits prevent in-flight report Open from overwriting new text',()=>{
 assert.match(ui,/function onDraftEdit\(\)\{/);
 assert.match(ui,/latestOpenRequest\.current\+\+;\s*if\(busy==='open'\)setBusy\(''\)/);
 assert.match(ui,/onDraftEdit\(\);setTitle\(e\.target\.value\)/);
 assert.match(ui,/onDraftEdit\(\);setNarrative\(e\.target\.value\)/);
 assert.match(ui,/onDraftEdit\(\);setSelected\(/);
 assert.match(ui,/if\(ticket!==latestOpenRequest\.current\)return;/);
});
