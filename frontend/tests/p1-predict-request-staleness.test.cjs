const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs'),path=require('node:path'),ts=require('typescript');
const app=fs.readFileSync(path.resolve(__dirname,'../src/App.tsx'),'utf8');

// Exercise the actual production input-edit and asynchronous response handlers.
const begin=app.indexOf('  function updatePredictionInput(name:string,value:string){');
const end=app.indexOf('  async function reopenExperiment(',begin);
assert.ok(begin>0&&end>begin,'Predict handlers must remain extractable from App');
const block=app.slice(begin,end);
const compiled=ts.transpileModule(block+'\nexports.handlers={updatePredictionInput,runPrediction};',{
  compilerOptions:{target:ts.ScriptTarget.ES2021,module:ts.ModuleKind.CommonJS},
  reportDiagnostics:true,
});
assert.equal((compiled.diagnostics||[]).filter(x=>x.category===ts.DiagnosticCategory.Error).length,0);

function harness(){
  const requestRevision={current:0};
  let values={Amount:'10'},prediction=null,busy='',error='',notice='',projectValid=true;
  let requested=null,resolve,reject;
  const deferred=new Promise((yes,no)=>{resolve=yes;reject=no});
  const project={id:'synthetic-project'};
  const experiment={id:'synthetic-experiment',project_id:project.id,selected_model:'model-1',results:{input_schema:[{name:'Amount'}]}};
  const projectOperations={current:{snapshot:()=>7,accepts:(id,generation)=>projectValid&&id===project.id&&generation===7}};
  const exports={};
  const handlers=new Function(
    'experiment','project','predictVals','predictionRequestRevision','projectOperations',
    'setError','setBusy','post','setPrediction','setNotice','setPredictVals','exports',
    compiled.outputText+'\nreturn exports.handlers;'
  )(experiment,project,values,requestRevision,projectOperations,
    v=>{error=v},v=>{busy=v},(url,payload)=>{requested={url,payload};return deferred},
    v=>{prediction=v},v=>{notice=v},fn=>{values=typeof fn==='function'?fn(values):fn},exports);
  return {...handlers,finish:result=>resolve(result),fail:err=>reject(err),
    invalidateProject:()=>{projectValid=false},
    state:()=>({values,prediction,busy,error,notice,requested,revision:requestRevision.current})};
}

test('matching current Predict input accepts the real computed response and exact submitted values',async()=>{
  const h=harness(),pending=h.runPrediction();
  assert.deepEqual(h.state().requested,{url:'/experiments/synthetic-experiment/predict',payload:{values:{Amount:'10'}}});
  h.finish({prediction:42,warning:'synthetic only'});
  await pending;
  assert.equal(h.state().prediction.prediction,42);
  assert.equal(h.state().busy,'');
  assert.match(h.state().notice,/Prediction computed/);
});

test('editing a Predict input during a request invalidates its successful response',async()=>{
  const h=harness(),pending=h.runPrediction();
  h.updatePredictionInput('Amount','11');
  h.finish({prediction:99,warning:'for old inputs'});
  await pending;
  assert.deepEqual(h.state().values,{Amount:'11'});
  assert.equal(h.state().prediction,null);
  assert.equal(h.state().busy,'');
  assert.equal(h.state().notice,'');
  assert.equal(h.state().requested.payload.values.Amount,'10');
});

test('editing and restoring an input still invalidates old results, and old errors are suppressed',async()=>{
  const h=harness(),pending=h.runPrediction();
  h.updatePredictionInput('Amount','11');
  h.updatePredictionInput('Amount','10');
  h.fail(new Error('stale prediction error'));
  await pending;
  assert.equal(h.state().error,'');
  assert.equal(h.state().prediction,null);
  assert.equal(h.state().revision,3);
});

test('the previous project-generation rejection stays in force',async()=>{
  const h=harness(),pending=h.runPrediction();
  h.invalidateProject();
  h.finish({prediction:'wrong project',warning:''});
  await pending;
  assert.equal(h.state().prediction,null);
  assert.equal(h.state().notice,'');
});

test('model/version transition invalidates requests and both React input variants share the safe handler',()=>{
  assert.match(app,/predictionRequestRevision\.current\+=1;\s*setPredictVals\(\{\}\);setPrediction\(null\);\s*\},\[project\?\.id,experiment\?\.id,experiment\?\.selected_model,qualityVersion\]\)/);
  assert.equal((app.match(/onChange=\{\(e:any\)=>updatePredictionInput\(f\.name,e\.target\.value\)\}/g)||[]).length,2);
  assert.match(block,/predictionRequestRevision\.current!==requestRevision/);
  assert.match(block,/predictionRequestRevision\.current===requestRevision/);
  assert.match(block,/if\(!experiment\?\.selected_model\|\|!experiment\.results\|\|!project/);
  assert.doesNotMatch(block,/localStorage|sessionStorage|fetch\(|upload\(|deleteProject\(/);
});
