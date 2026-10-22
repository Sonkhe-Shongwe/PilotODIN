const {test}=require('node:test');
const assert=require('node:assert/strict');
const path=require('node:path');
const fs=require('node:fs');
const ts=require('typescript');
const source=fs.readFileSync(path.join(__dirname,'../src/projectOperationGuard.ts'),'utf8');
const compiled=ts.transpileModule(source,{compilerOptions:{target:ts.ScriptTarget.ES2021,module:ts.ModuleKind.CommonJS},reportDiagnostics:true});
assert.equal(compiled.diagnostics?.filter(d=>d.category===ts.DiagnosticCategory.Error).length||0,0);
const moduleExports={};
new Function('module','exports',compiled.outputText)({exports:moduleExports},moduleExports);
const {createProjectOperationGuard}=moduleExports;
function deferred(){let resolve;const promise=new Promise(r=>resolve=r);return {promise,resolve}}
test('same-project request accepted at matching generation',()=>{
 const guard=createProjectOperationGuard();const generation=guard.begin('A');
 assert.equal(guard.accepts('A',generation),true);
 assert.equal(guard.accepts('B',generation),false);
 assert.equal(guard.accepts('A',generation+1),false);
});
test('late result from earlier project is discarded after switch',async()=>{
 const guard=createProjectOperationGuard();const a=guard.begin('A');
 const delayed=deferred();const displayed=[];
 const inFlight=delayed.promise.then(value=>{if(guard.accepts('A',a))displayed.push(value)});
 const b=guard.begin('B');delayed.resolve('Old model output');await inFlight;
 assert.deepEqual(displayed,[]);
 assert.equal(guard.accepts('B',b),true);
});
test('a request from a prior generation of the same project is rejected',()=>{
 const guard=createProjectOperationGuard();const old=guard.begin('A');guard.begin('B');const now=guard.begin('A');
 assert.equal(guard.accepts('A',old),false);
 assert.equal(guard.accepts('A',now),true);
});
test('unmount invalidates every in-flight reply',()=>{
 const guard=createProjectOperationGuard();const old=guard.begin('A');guard.invalidate();
 assert.equal(guard.accepts('A',old),false);
});
test('App guards training, prediction, experiment and quality response paths',()=>{
 const app=fs.readFileSync(path.join(__dirname,'../src/App.tsx'),'utf8');
 for(const fn of ['startTrain','chooseModel','runPrediction','reopenExperiment','qualityChanged']){
  const found=app.match(new RegExp(`async function ${fn}\\([\\s\\S]*?(?=\\n  (?:async function|useEffect|const profile|return <div))`));
  assert.ok(found,`Missing function ${fn}`);
  assert.match(found[0],/projectOperations\.current\.accepts\(projectId,generation\)/,`${fn} must gate late results`);
 }
 assert.match(app,/result\.project_id!==projectId/);
 assert.match(app,/exp\.project_id!==projectId/);
 assert.match(app,/!embedded&&!uploadOpen&&page!=='ai_settings'&&<StudioAssistant/);
});
