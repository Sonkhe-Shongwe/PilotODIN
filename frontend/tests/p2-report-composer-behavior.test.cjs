const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const ts=require('typescript');
const vm=require('node:vm');

const root=path.join(__dirname,'../src');
const source=fs.readFileSync(path.join(root,'reportComposerGate.ts'),'utf8');
const compiled=ts.transpileModule(source,{
 compilerOptions:{target:ts.ScriptTarget.ES2021,module:ts.ModuleKind.CommonJS},
 reportDiagnostics:true,
});
assert.equal(compiled.diagnostics?.length,0);
const exportsForTest={};
vm.runInNewContext(compiled.outputText,{exports:exportsForTest},{filename:'reportComposerGate.js'});
const {ReportComposerGate}=exportsForTest;
const ui=fs.readFileSync(path.join(root,'ReportWorkspace.tsx'),'utf8');

function deferred(){
 let resolve,reject;
 const promise=new Promise((yes,no)=>{resolve=yes;reject=no});
 return {promise,resolve,reject};
}

test('BEHAVIOR: Save completion after edits is still the same view but not the same draft',async()=>{
 const gate=new ReportComposerGate();
 const remote=deferred();
 const observed=[];
 const ticket=gate.begin('save');
 const request=(async()=>{
   const data=await remote.promise;
   if(gate.sameView(ticket))observed.push({id:data.id,olderSnapshot:!gate.sameDraft(ticket)});
   gate.finish(ticket);
 })();
 gate.editDraft();
 remote.resolve({id:'saved-report-revision'});
 await request;
 assert.deepEqual(observed,[{id:'saved-report-revision',olderSnapshot:true}]);
 assert.equal(gate.hasPending(),false);
});

test('BEHAVIOR: a project switch prevents a former request from updating the new view',async()=>{
 const gate=new ReportComposerGate();
 const remote=deferred();
 const rendered=[];
 const old=gate.begin('save');
 const pending=(async()=>{
   const result=await remote.promise;
   if(gate.sameView(old))rendered.push(result);
   gate.finish(old);
 })();
 gate.resetProject();
 const fresh=gate.begin('quality');
 remote.resolve({id:'foreign-report'});
 await pending;
 assert.equal(rendered.length,0);
 assert.equal(gate.sameView(fresh),true);
 assert.equal(gate.finish(old),false);
 assert.equal(gate.finish(fresh),true);
});

test('BEHAVIOR: Quality audit cannot silently append evidence after user edits',async()=>{
 const gate=new ReportComposerGate();
 const remote=deferred();
 const evidence=['existing'];
 const ticket=gate.begin('quality');
 const pending=(async()=>{
   const saved=await remote.promise;
   if(gate.sameDraft(ticket))evidence.push(saved.id);
   gate.finish(ticket);
 })();
 gate.editDraft();
 evidence.push('new-selection');
 remote.resolve({id:'audit'});
 await pending;
 assert.deepEqual(evidence,['existing','new-selection']);
});

test('BEHAVIOR: unrelated write cannot start during a pending save or capture',()=>{
 const gate=new ReportComposerGate();
 const save=gate.begin('save');
 assert.equal(gate.begin('quality'),null);
 assert.equal(gate.begin('save'),null);
 gate.navigate();
 assert.equal(gate.sameView(save),false);
 assert.equal(gate.finish(save),true);
 const quality=gate.begin('quality');
 assert.ok(quality);
 assert.equal(gate.sameDraft(quality),true);
});

test('INTEGRATION: source wires guarded Save, Quality and accurate post-commit refresh errors',()=>{
 assert.match(ui,/const ticket=gate\.begin\('save'\)/);
 assert.match(ui,/const ticket=gate\.begin\('quality'\)/);
 assert.match(ui,/const untouched=gate\.sameDraft\(ticket\)/);
 assert.match(ui,/if\(gate\.sameDraft\(ticket\)\)/);
 assert.match(ui,/if\(gate\.sameView\(ticket\)\)setError/);
 assert.match(ui,/Report revision was saved, but the report library could not refresh/);
 assert.match(ui,/Quality audit v\$\{captured\.dataset_version\} was captured, but its evidence list could not refresh/);
 assert.match(ui,/setSelected\(ids=>ids\.length>=15/);
});

test('INTEGRATION: draft changes and project/evidence navigation invalidate the right epoch',()=>{
 assert.match(ui,/composerGuard\.current\.resetProject\(\)/);
 assert.match(ui,/composerGuard\.current\.navigate\(\)/);
 assert.match(ui,/composerGuard\.current\.editDraft\(\);setTitle/);
 assert.match(ui,/composerGuard\.current\.editDraft\(\);setNarrative/);
 assert.match(ui,/composerGuard\.current\.editDraft\(\);setSelected/);
 assert.match(ui,/latestReportList\.current/);
 assert.match(ui,/saveReportNative\(blob,filename,format\)/);
});
