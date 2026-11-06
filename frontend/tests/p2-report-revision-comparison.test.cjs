const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const ts=require('typescript');
const vm=require('node:vm');

const root=path.join(__dirname,'../src');
function loadTS(name){
 const content=fs.readFileSync(path.join(root,name),'utf8');
 const compiled=ts.transpileModule(content,{
  compilerOptions:{target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.CommonJS},
  fileName:name,reportDiagnostics:true
 });
 assert.equal(compiled.diagnostics?.length,0);
 const module={exports:{}};
 vm.runInNewContext(compiled.outputText,{exports:module.exports,module},{filename:name});
 return module.exports;
}
const {compareFrozenReports}=loadTS('reportRevisionComparison.ts');
const {ReportComposerGate,ReportReadGate}=loadTS('reportComposerGate.ts');
const ui=fs.readFileSync(path.join(root,'ReportWorkspace.tsx'),'utf8');

function snap(revision,overrides={}){
 return {
  id:'b'.repeat(32),revision,title:'Verified Synthetic Revenue',
  narrative:'Original analyst interpretation',content_sha256:String(revision).repeat(64),
  dataset_versions:[0],
  evidence:[
   {id:'a'.repeat(32),operation:'overview',dataset_version:0,result:{rows:3}},
   {id:'c'.repeat(32),operation:'compare',dataset_version:0,result:{median:19}},
  ],
  ...overrides
 };
}
function ids(items){return Array.from(items, item=>item.id)}

test('BEHAVIOR: only identical saved snapshot digests are reported identical',()=>{
 const first=snap(1,{content_sha256:'f'.repeat(64)});
 const second=snap(2,{content_sha256:'f'.repeat(64)});
 const result=compareFrozenReports(first,second);
 assert.equal(result.identical,true);
 assert.equal(result.otherSnapshotChanged,false);
 assert.equal(result.added.length,0);
 assert.equal(result.removed.length,0);
});

test('BEHAVIOR: same visible exhibit list but different full snapshot is not claimed identical',()=>{
 const result=compareFrozenReports(snap(1),snap(2));
 assert.equal(result.identical,false);
 assert.equal(result.otherSnapshotChanged,true);
});

test('BEHAVIOR: title and interpretation are tracked without changing originals',()=>{
 const before=snap(1),after=snap(2,{
  title:'New title',narrative:'Analyst changed narrative'
 });
 const serialized=JSON.stringify(before);
 const result=compareFrozenReports(before,after);
 assert.equal(result.titleChanged,true);
 assert.equal(result.narrativeChanged,true);
 assert.equal(result.oldTitle,'Verified Synthetic Revenue');
 assert.equal(result.newNarrative,'Analyst changed narrative');
 assert.equal(result.otherSnapshotChanged,false);
 assert.equal(JSON.stringify(before),serialized);
});

test('BEHAVIOR: added and removed verified exhibits retain original dataset versions',()=>{
 const before=snap(1),after=snap(2,{
  dataset_versions:[1],
  evidence:[before.evidence[1],{
   id:'d'.repeat(32),operation:'quality_audit',dataset_version:1,result:{findings:1}
  }]
 });
 const result=compareFrozenReports(before,after);
 assert.deepEqual(ids(result.added),['d'.repeat(32)]);
 assert.deepEqual(ids(result.removed),['a'.repeat(32)]);
 assert.equal(result.added[0].toVersion,1);
 assert.equal(result.removed[0].fromVersion,0);
 assert.deepEqual(Array.from(result.versionsAdded),[1]);
 assert.deepEqual(Array.from(result.versionsRemoved),[0]);
 assert.equal(result.orderChanged,false);
});

test('BEHAVIOR: reordering existing exhibits is visible but no evidence is removed',()=>{
 const old=snap(1);
 const newer=snap(2,{evidence:[old.evidence[1],old.evidence[0]]});
 const result=compareFrozenReports(old,newer);
 assert.equal(result.orderChanged,true);
 assert.equal(result.added.length,0);
 assert.equal(result.removed.length,0);
 assert.equal(result.changed.length,0);
});

test('BEHAVIOR: stored evidence payload change with same ID is not overlooked',()=>{
 const old=snap(1);
 const newEvidence=old.evidence.map((x,i)=>i===0?{...x,result:{rows:4}}:x);
 const result=compareFrozenReports(old,snap(2,{evidence:newEvidence}));
 assert.deepEqual(ids(result.changed),['a'.repeat(32)]);
 assert.equal(result.orderChanged,false);
});

test('SAFETY: different report IDs, reversed revisions and duplicate artifact IDs fail',()=>{
 assert.throws(()=>compareFrozenReports(snap(1),snap(2,{id:'d'.repeat(32)})),
  /unrelated|ordered/);
 assert.throws(()=>compareFrozenReports(snap(2),snap(1)),/unrelated|ordered/);
 assert.throws(()=>compareFrozenReports(snap(1),snap(1)),/unrelated|ordered/);
 const before=snap(1);
 assert.throws(()=>compareFrozenReports(before,snap(2,{
  evidence:[before.evidence[0],before.evidence[0]]
 })),/duplicate evidence/);
});

test('BEHAVIOR: stale comparison token is invalidated by new revision selection/project switch',()=>{
 const gate=new ReportReadGate();
 const first=gate.beginComparison(),second=gate.beginComparison();
 assert.equal(gate.isCurrentComparison(first),false);
 assert.equal(gate.isCurrentComparison(second),true);
 gate.invalidateComparison();
 assert.equal(gate.isCurrentComparison(second),false);
 const latest=gate.beginComparison();
 gate.invalidateAll();
 assert.equal(gate.isCurrentComparison(latest),false);
 const composer=new ReportComposerGate();
 const view=composer.currentView();
 composer.navigate();
 assert.equal(composer.isCurrentView(view),false);
});

test('INTEGRATION: Deliver loads immutable old revision and protects against stale responses',()=>{
 assert.match(ui,/async function comparePreviousSavedRevision\(\)/);
 assert.match(ui,/const previousRevisions=opened\.revisions\.filter\(v=>v<opened\.revision\)/);
 assert.match(ui,/const priorRevision=previousRevisions\[previousRevisions\.length-1\]/);
 assert.match(ui,/const ticket=readGuard\.current\.beginComparison\(\)/);
 assert.match(ui,/activeProjectRef\.current===projectId/);
 assert.match(ui,/readGuard\.current\.isCurrentComparison\(ticket\)/);
 assert.match(ui,/get<SavedReport>\(`\/reports\/\$\{encodeURIComponent\(reportId\)\}\?revision=\$\{priorRevision\}`\)/);
 assert.match(ui,/compareFrozenReports\(before,latest\)/);
 assert.match(ui,/revisionComparison\.comparison\.to===\(revision\?\?opened\?\.revision\)/);
 assert.match(ui,/Compare with previous saved revision/);
 assert.match(ui,/Only frozen saved evidence is compared/);
 assert.match(ui,/clearComparison\(\)/);
});
