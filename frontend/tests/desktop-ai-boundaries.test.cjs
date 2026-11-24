const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const ts=require('typescript');
const src=fs.readFileSync(path.join(__dirname,'../src/api.ts'),'utf8');
const result=ts.transpileModule(src,{compilerOptions:{target:ts.ScriptTarget.ES2021,module:ts.ModuleKind.CommonJS},reportDiagnostics:true});
assert.equal((result.diagnostics||[]).filter(x=>x.category===ts.DiagnosticCategory.Error).length,0);
function loadAPI(invoke=async()=>{}, fetch=undefined){
 const mod={exports:{}};
 new Function('require','module','exports','fetch',result.outputText)(()=>({invoke}),mod,mod.exports,fetch);
 return mod.exports;
}
const {shouldLaunchBundledAI}=loadAPI();
test('passive local AI health checks never launch the model',()=>{
 for(const path of ['/ai/local/status','/ai/settings','/projects','/health','/investigations/id/autonomy'])
  assert.equal(shouldLaunchBundledAI(path,'GET'),false,path);
});
test('only intentional AI operations can launch local worker',()=>{
 for(const path of ['/projects/id/ai/insight','/investigations/id/autonomy/start','/investigations/id/autonomy/resume'])
  assert.equal(shouldLaunchBundledAI(path,'POST'),true,path);
 for(const path of ['/bad/ai/insight','/projects/id/ai/test','/investigations/id/autonomy/cancel','/projects/id/clean/commit'])
  assert.equal(shouldLaunchBundledAI(path,'POST'),false,path);
});
test('explicit cloud-provider requests never wake the local model',()=>{
 for(const provider of ['gemini','groq','openrouter'])
  assert.equal(shouldLaunchBundledAI('/projects/id/ai/insight','POST',{selected_provider:provider}),false);
 // Explicit rules-only analysis must not allocate the bundled LLM.
 assert.equal(shouldLaunchBundledAI('/projects/id/ai/insight','POST',{selected_provider:'local'}),false);
 for(const provider of ['ollama','auto',undefined])
  assert.equal(shouldLaunchBundledAI('/projects/id/ai/insight','POST',{selected_provider:provider}),true);
});
test('desktop insights consult routing and memory before launch and still post after a skip',async()=>{
 const path='/projects/id/ai/insight';
 const reply={answer:'Verified evidence',fallback:true};
 for(const [decision,code,body,expectedIssue] of [
  ['skip','local_model_disabled',{selected_provider:'auto',question:'How many rows?'},undefined],
  ['skip','rules_only',{context:'quality',question:'What is missing?'},undefined],
  ['allow',undefined,{context:'quality',selected_provider:'ollama'},undefined],
  ['defer','low_memory_headroom',{selected_provider:'ollama'},'resource_limited'],
 ]){
  const events=[];
  const api=loadAPI(async command=>events.push(command),async (url,options)=>{
   assert.equal(options.headers['X-PilotODIN-Session'],'test-session');
   const requested=new URL(url);
   if(requested.pathname==='/api/resource/preflight'){
    events.push('preflight');
    assert.equal(requested.searchParams.get('operation'),'local_inference');
    assert.equal(requested.searchParams.get('insight_context'),body.context??'assistant');
    assert.equal(requested.searchParams.get('selected_provider'),body.selected_provider??null);
    assert.equal(requested.searchParams.has('question'),false);
    return Response.json({decision,code});
   }
   events.push('post');
   assert.equal(requested.pathname,`/api${path}`);
   assert.equal(options.method,'POST');
   assert.deepEqual(JSON.parse(options.body),body);
   return Response.json(reply);
  });
  api.configureDesktopAPI({port:12345,token:'test-session'});
  const answer=await api.post(path,body);
  assert.equal(answer.answer,reply.answer);
  assert.equal(answer.local_startup_issue,expectedIssue);
  assert.deepEqual(events,decision==='allow'?['preflight','launch_bundled_ai','post']:['preflight','post']);
 }
});
test('automatic investigation skips worker launch and reports the API reason when offline AI is disabled',async()=>{
 const route='/investigations/id/autonomy';
 for(const action of ['start','resume']){
  const events=[];
  const message='Automatic investigation requires offline AI. Enable it in AI Settings or run an analysis manually.';
  const api=loadAPI(async()=>assert.fail('Started the disabled worker'),async (url,options)=>{
   const requested=new URL(url);
   if(requested.pathname==='/api/resource/preflight'){
    events.push('preflight');
    assert.equal(requested.searchParams.get('operation'),'local_inference');
    assert.equal(requested.searchParams.get('investigation_autonomy'),'true');
    return Response.json({decision:'skip',code:'local_model_disabled'});
   }
   events.push('post');
   assert.equal(requested.pathname,`/api${route}/${action}`);
   assert.equal(options.method,'POST');
   return Response.json({detail:message},{status:409});
  });
  api.configureDesktopAPI({port:12345,token:'test-session'});
  await assert.rejects(api.post(`${route}/${action}`,{}),{message});
  assert.deepEqual(events,['preflight','post']);
 }
});
test('secondary panes are barred from primary global controls',()=>{
 const app=fs.readFileSync(path.join(__dirname,'../src/App.tsx'),'utf8');
 assert.match(app,/if\(embedded && pid!==embeddedProjectId\)/);
 assert.match(app,/if\(embedded\)\{setError\('Import a new dataset from the primary workspace/);
 assert.match(app,/if\(embedded\)return;\s*const handler=\(event:KeyboardEvent\)/);
 assert.match(app,/if\(embedded\)return;\s*let live=true/);
});

test('Ask ODIN labels deterministic fallback and exposes the explicit offline model route',()=>{
 const assistant=fs.readFileSync(path.join(__dirname,'../src/AssistantWorkspace.tsx'),'utf8');
 assert.match(assistant,/value="ollama"/);
 assert.match(assistant,/VERIFIED RULES · NO LLM/);
 assert.match(assistant,/local_startup_issue/);
 assert.match(assistant,/No language-model answer was generated/);
});

test('continuing an offline workspace explanation pins the request to the local model',()=>{
 const workspace=fs.readFileSync(path.join(__dirname,'../src/AIWorkspace.tsx'),'utf8');
 assert.match(workspace,/const continuationProvider = result\.source === 'local_llm' \? 'ollama' : selectedProvider/);
 assert.match(workspace,/selected_provider:continuationProvider,continuation_text:result\.answer/);
});


test('owned desktop posts demand directly without preflight or launch IPC',async()=>{
 for(const [path,body] of [
  ['/projects/id/ai/insight',{selected_provider:'ollama',question:'How many rows?'}],
  ['/projects/id/ai/insight',{selected_provider:'gemini'}],
  ['/investigations/id/autonomy/start',{}],
  ['/investigations/id/autonomy/resume',{}],
 ]){
  const events=[];
  const api=loadAPI(async()=>assert.fail('Owned mode must never invoke legacy launch'),async(url,options)=>{
   events.push(new URL(url).pathname);
   assert.equal(options.method,'POST');
   assert.equal(options.headers['X-PilotODIN-Session'],'test-session');
   assert.deepEqual(JSON.parse(options.body),body);
   return Response.json({answer:'Verified rules',fallback:true,local_status:'resource_busy'});
  });
  api.configureDesktopAPI({port:12345,token:'test-session',backend_driven_inference:true});
  const result=await api.post(path,body);
  assert.deepEqual(events,['/api'+path]);
  assert.equal(result.local_status,'resource_busy');
  assert.equal(result.local_startup_issue,undefined);
 }
});
test('owned mode does not retry a refused demand or trust request-body routing flags',async()=>{
 const events=[];
 const api=loadAPI(async()=>assert.fail('Unexpected launch'),async(url,options)=>{
  events.push(new URL(url).pathname);
  return Response.json({detail:'resource_busy'},{status:503});
 });
 api.configureDesktopAPI({port:12345,token:'test-session',backend_driven_inference:true});
 await assert.rejects(api.post('/investigations/id/autonomy/start',{backend_driven_inference:false}),{message:'resource_busy'});
 assert.deepEqual(events,['/api/investigations/id/autonomy/start']);
 assert.throws(()=>api.configureDesktopAPI({port:12345,token:'test-session',backend_driven_inference:'true'}));
});
