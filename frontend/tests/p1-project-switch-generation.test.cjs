const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs'),path=require('node:path'),ts=require('typescript');
const app=fs.readFileSync(path.resolve(__dirname,'../src/App.tsx'),'utf8');
const guardSource=fs.readFileSync(path.resolve(__dirname,'../src/projectOperationGuard.ts'),'utf8');
const js=ts.transpileModule(guardSource,{compilerOptions:{target:ts.ScriptTarget.ES2021,module:ts.ModuleKind.CommonJS}}).outputText;
const moduleExports={};
new Function('module','exports',js)({exports:moduleExports},moduleExports);
const {createProjectOperationGuard}=moduleExports;
const profileGuardSource=fs.readFileSync(path.resolve(__dirname,'../src/liveProfileVersionGuard.ts'),'utf8');
const profileJs=ts.transpileModule(profileGuardSource,{compilerOptions:{target:ts.ScriptTarget.ES2021,module:ts.ModuleKind.CommonJS}}).outputText;
const profileExports={};
new Function('module','exports',profileJs)({exports:profileExports},profileExports);
const {createLiveProfileVersionGuard}=profileExports;
const begin=app.indexOf('  async function loadProject(pid:string,approvedBeforeUpload=false):Promise<boolean>{');
const end=app.indexOf('\n  useEffect(()=>{if(!project||!target)',begin);
assert.ok(begin>=0&&end>begin,'actual project load handler must be present');
const body=app.slice(begin,end);
const compiled=ts.transpileModule(body+'\nexports.loadProject=loadProject;',{
 compilerOptions:{target:ts.ScriptTarget.ES2021,module:ts.ModuleKind.CommonJS},
 reportDiagnostics:true
});
assert.equal((compiled.diagnostics||[]).filter(d=>d.category===ts.DiagnosticCategory.Error).length,0);

function harness(){
  const guard=createProjectOperationGuard('A');
  const tokenA=guard.snapshot('A');
  let complete,fail;
  const gate=new Promise((resolve,reject)=>{complete=resolve;fail=reject});
  const events=[],reads=[];
  let shared='A';
  const ctx={
    embedded:false,embeddedProjectId:undefined,project:{id:'A'},
    onBeforePrimaryProjectLoad:()=>true,
    onPrimaryProjectLoaded:(id)=>events.push('loaded:'+id),
    onPrimaryProjectLoadFailed:(id)=>events.push('failed:'+id),
    onPrimaryUploadedProjectCommitted:()=>events.push('upload-committed'),
    setNotice:msg=>events.push('notice:'+msg),
    latestProjectRequest:{current:0},projectOperations:{current:guard},
    liveProfileVersionGuard:{current:createLiveProfileVersionGuard('A',0)},
    get:url=>{reads.push(url);return gate.then(()=>{
      if(url.endsWith('/live-profile'))return {version:0};
      return {id:'B',name:'disposable',filename:'synthetic.csv'};
    })},
    localStorage:{getItem:()=>shared,setItem:(key,value)=>{shared=value;events.push('selected:'+value)}},
    mayCommitProjectSelection:(start,now,pid)=>start===now&&pid==='B',
    embeddedStage:undefined,requestedStudioStage:()=> 'quality',scrollRef:{current:{}}
  };
  for(const name of ['setProject','setPrep','setExperiment','setPrediction','setTarget',
    'setQualityFocus','setDeliverEvidenceId','setQualityVersion','setFeatureHintSnapshot',
    'setExcluded','setPredictVals','setConfirmSplit','setPage','setVisitedStages',
    'setUploadOpen','setError'])
    ctx[name]=value=>events.push(name);
  const keys=Object.keys(ctx),exports={};
  const fn=new Function(...keys,'exports',compiled.outputText+'\nreturn exports.loadProject;')(
    ...Object.values(ctx),exports);
  return {load:()=>fn('B'),acceptA:()=>guard.accepts('A',tokenA),
    acceptB:()=>guard.accepts('B',guard.snapshot('B')),
    finish:()=>complete(),reject:()=>fail(new Error('synthetic HTTP 503')),
    reads,events,selected:()=>shared,guard};
}

test('a pending project switch retains the original project generation while reading',async()=>{
  const h=harness(),p=h.load();
  assert.deepEqual(h.reads,['/projects/B','/projects/B/live-profile']);
  assert.equal(h.acceptA(),true);
  h.reject();
  assert.equal(await p,false);
  assert.equal(h.acceptA(),true);
});

test('failed destination read keeps original project operations usable and does not change selection',async()=>{
  const h=harness(),p=h.load();
  h.reject();await p;
  const originalGeneration=h.guard.snapshot('A');
  assert.equal(h.guard.accepts('A',originalGeneration),true);
  assert.equal(h.selected(),'A');
  assert.ok(h.events.includes('failed:B'));
  assert.equal(h.events.includes('loaded:B'),false);
  assert.equal(h.events.some(e=>e==='setProject'),false);
});

test('successful destination read invalidates old work and enables the new project',async()=>{
  const h=harness(),p=h.load();
  assert.equal(h.acceptA(),true);
  h.finish();assert.equal(await p,true);
  assert.equal(h.acceptA(),false);
  assert.equal(h.acceptB(),true);
  assert.equal(h.selected(),'B');
  assert.ok(h.events.includes('loaded:B'));
});

test('remounted Studio immediately accepts a verified handoff without repeat network reads',()=>{
  const guard=createProjectOperationGuard('B');
  const generation=guard.snapshot('B');
  assert.equal(guard.accepts('B',generation),true);
  assert.equal(guard.accepts('A',generation),false);
  assert.match(app,/useRef\(createProjectOperationGuard\(initialVerifiedProject\?\.id\?\?''\)\)/);
});

test('unverified default guard refuses operations until an actual successful project load',()=>{
  const guard=createProjectOperationGuard();
  assert.equal(guard.snapshot('A'),-1);
  assert.equal(guard.accepts('A',-1),false);
  const generation=guard.begin('A');
  assert.equal(guard.accepts('A',generation),true);
  guard.invalidate();
  assert.equal(guard.accepts('A',generation),false);
});
