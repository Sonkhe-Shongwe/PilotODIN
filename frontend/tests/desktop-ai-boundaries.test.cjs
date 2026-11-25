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


test('owned routing mode is explicit metadata and not inferred from request',()=>{
 const api=loadAPI(async()=>assert.fail('Unexpected IPC'),async()=>assert.fail('Unexpected fetch'));
 assert.equal(api.usesOwnedInference(),false);
 api.configureDesktopAPI({port:12345,token:'test-session',backend_driven_inference:true});
 assert.equal(api.usesOwnedInference(),true);
 api.configureDesktopAPI({port:12345,token:'test-session',backend_driven_inference:false});
 assert.equal(api.usesOwnedInference(),false);
});


test('native report and dataset share one pre-copy save guard',async()=>{
 const oldWindow=globalThis.window;
 globalThis.window={__TAURI_INTERNALS__:{}};
 try {
  let finish;
  const held=new Promise(resolve=>{finish=resolve;});
  let invoked=0;
  const api=loadAPI(async command=>{assert.equal(command,'save_report_as');invoked++;await held;return {status:'cancelled',filename:null};});
  const blob=new Blob(['%PDF-test']);
  const pending=api.saveReportNative(blob,'test.pdf','pdf');
  await assert.rejects(api.saveDatasetNative({},()=>true),/Another native Save As/);
  await assert.rejects(api.saveReportNative(blob,'test.pdf','pdf'),/Another native Save As/);
  finish();
  assert.equal((await pending).status,'cancelled');
  assert.equal((await api.saveReportNative(blob,'test.pdf','pdf')).status,'cancelled');
  assert.equal(invoked,2);
 }finally{if(oldWindow===undefined)delete globalThis.window;else globalThis.window=oldWindow;}
});

// Execute the actual shared panel request fence against controlled deferred work.
function loadInsightFence(){
 const source=fs.readFileSync(path.join(__dirname,'../src/insightRequestFence.ts'),'utf8');
 const output=ts.transpileModule(source,{compilerOptions:{target:ts.ScriptTarget.ES2021,module:ts.ModuleKind.CommonJS}}).outputText;
 const mod={exports:{}};
 new Function('module','exports',output)(mod,mod.exports);
 return mod.exports.createInsightRequestFence;
}
test('C2 request fence refuses synchronous duplicate and keeps ownership until actual settlement',async()=>{
 const fence=loadInsightFence()();const leave=fence.enter();const first=fence.begin();
 assert.ok(first);assert.equal(fence.begin(),null);
 let resolve;const pending=new Promise(r=>{resolve=r});
 let published=false;
 const work=pending.then(()=>{if(fence.isCurrent(first))published=true}).finally(()=>fence.finish(first));
 assert.equal(fence.begin(),null);resolve();await work;
 assert.equal(published,true);assert.ok(fence.begin());leave();
});
test('C2 old context completion cannot publish even after returning to the same context',async()=>{
 const fence=loadInsightFence()();const leaveA=fence.enter();const old=fence.begin();
 let resolve;const pending=new Promise(r=>{resolve=r});let published=false;
 const work=pending.then(()=>{if(fence.isCurrent(old))published=true}).finally(()=>fence.finish(old));
 leaveA();const leaveB=fence.enter();leaveB();fence.enter();
 assert.equal(fence.isCurrent(old),false);assert.equal(fence.begin(),null);
 resolve();await work;assert.equal(published,false);
 const next=fence.begin();assert.ok(next);assert.equal(fence.finish(old),false);
 assert.equal(fence.isCurrent(next),true);assert.equal(fence.finish(next),true);
});
test('C2 unmount invalidates late error and old cleanup cannot clear newer scope',()=>{
 const fence=loadInsightFence()();const oldCleanup=fence.enter();const old=fence.begin();
 const cleanup=fence.enter();oldCleanup();
 assert.equal(fence.isCurrent(old),false);assert.equal(fence.finish(old),true);
 const next=fence.begin();assert.ok(next);cleanup();
 assert.equal(fence.isCurrent(next),false);assert.equal(fence.finish(next),false);
 assert.equal(fence.begin(),null);
});
test('C2 both actual panels bind request ownership, late results and truthful owned waiting',()=>{
 const assistant=fs.readFileSync(path.join(__dirname,'../src/AssistantWorkspace.tsx'),'utf8');
 const insight=fs.readFileSync(path.join(__dirname,'../src/AIWorkspace.tsx'),'utf8');
 assert.match(assistant,/useLayoutEffect\(\(\)=>fence.enter\(\),\[fence,projectId\]\)/);
 assert.match(assistant,/const ticket=fence.begin\(\);if\(!ticket\)return/);
 assert.match(assistant,/if\(!fence.isCurrent\(ticket\)\)return/);
 assert.match(assistant,/finally\{if\(fence.finish\(ticket\)\)setBusy\(false\)\}/);
 assert.match(insight,/useLayoutEffect\(\(\)=>fence.enter\(\),\[fence,fingerprint\]\)/);
 assert.equal((insight.match(/const ticket=fence.begin\(\);if\(!ticket\)return/g)||[]).length,3);
 assert.equal((insight.match(/finally\{if\(fence.finish\(ticket\)\)setBusy\(false\)\}/g)||[]).length,3);
 assert.match(insight,/if\(fence.isCurrent\(ticket\)\)\{insightCache.set/);
 assert.match(insight,/if\(fence.isCurrent\(ticket\)\)setResult\(/);
 assert.match(insight,/if\(fence.isCurrent\(ticket\)\)setInvestigationResult\(/);
 assert.match(insight,/usesOwnedInference\(\)\?'waiting for the selected route/);
 assert.match(insight,/usesOwnedInference\(\)\?"Smart Auto \(local only\)"/);
});


test('C3 explicit development API accepts only approved origins and sends only a same-origin proxy marker',async()=>{
 for(const port of [5173,5176,5177,5178]){
   const origin='http://127.0.0.1:'+port;
   const seen=[];
   const api=loadAPI(async()=>{throw Error('Unexpected native IPC');},async(url,options)=>{
     seen.push({url,headers:options.headers});
     return {ok:true,json:async()=>({status:'ok'})};
   });
   for(const invalid of ['http://127.0.0.1:5174','http://127.0.0.1:5175',
     'http://127.0.0.1:5179','http://127.0.0.1:8000','http://localhost:'+port,
     'http://192.0.2.1:'+port,'https://127.0.0.1:'+port,origin+'/',origin+'/api','']){
     assert.throws(()=>api.configureDevelopmentAPI(invalid),invalid);
   }
   api.configureDevelopmentAPI(origin);
   assert.equal(api.apiBase(),origin+'/api');
   await api.get('/health');
   assert.deepEqual(seen,[{url:origin+'/api/health',headers:{'X-PilotODIN-Dev-Request':'1'}}]);
   assert.throws(()=>api.configureDesktopAPI({port:12345,token:'fixture'}));
 }
 const desktop=loadAPI();
 desktop.configureDesktopAPI({port:12345,token:'fixture'});
 for(const port of [5173,5176,5177,5178])
   assert.throws(()=>desktop.configureDevelopmentAPI('http://127.0.0.1:'+port));
});

test('C3 Live Dev proxy enforces local origin, marker and fixed private backend',async()=>{
 const {liveDevProxyTrust,liveDevProxyPlan}=await import('../scripts/live-dev-api-proxy.mjs');
 const env={PILOTODIN_SERVER_MODE:'dev',VITE_PILOTODIN_AUTH_DEV:'1',
   PILOTODIN_DEV_ORIGIN:'http://127.0.0.1:5173',PILOTODIN_DEV_PORT:'8000',PILOTODIN_DEV_CAPABILITY:'a'.repeat(64)};
 const trust=liveDevProxyTrust(env);
 assert.ok(Object.isFrozen(trust));
 for(const change of [{PILOTODIN_DEV_CAPABILITY:''},{PILOTODIN_DEV_ORIGIN:'http://localhost:5173'},
   {PILOTODIN_DEV_PORT:'8001'},{PILOTODIN_DESKTOP_SESSION:'a'.repeat(64)},{PILOTODIN_SERVER_MODE:'hosted-fixture'}]){
   assert.throws(()=>liveDevProxyTrust({...env,...change}));
 }
 const raw=['Host','127.0.0.1:5173','X-PilotODIN-Dev-Request','1','Sec-Fetch-Site','same-origin'];
 const req={url:'/api/projects?version=0',method:'GET',socket:{remoteAddress:'127.0.0.1'},rawHeaders:raw};
 const plan=liveDevProxyPlan(req,trust);
 assert.equal(plan.status,200);
 assert.equal(plan.options.hostname,'127.0.0.1');
 assert.equal(plan.options.port,8000);
 assert.equal(plan.options.path,req.url);
 assert.equal(plan.options.headers['x-pilotodin-dev-capability'],'a'.repeat(64));
 assert.equal(plan.options.headers.origin,'http://127.0.0.1:5173');
 assert.equal(liveDevProxyPlan({...req,url:'/src/main.tsx'},trust),null);
 const cli=['Host','127.0.0.1:5173','X-PilotODIN-Dev-Request','1','Origin','http://127.0.0.1:5173'];
 assert.equal(liveDevProxyPlan({...req,rawHeaders:cli},trust).status,200);
 for(const bad of [{socket:{remoteAddress:'192.0.2.1'}},{method:'OPTIONS'},
   {rawHeaders:raw.slice(0,2)},{rawHeaders:['Host','evil.example',...raw.slice(2)]},
   {rawHeaders:[...raw,'Origin','https://evil.example']},
   {rawHeaders:[...raw,'X-PilotODIN-Dev-Request','1']},
   {rawHeaders:[...raw,'X-Forwarded-For','127.0.0.1']},
   {rawHeaders:[...raw,'X-PilotODIN-Dev-Capability','a'.repeat(64)]},
   {rawHeaders:[...raw,'Referer','https://evil.example/path']},
   {rawHeaders:[...raw,'Content-Length','10','Transfer-Encoding','chunked']},
   {rawHeaders:[...raw.slice(0,4),'Sec-Fetch-Site','cross-site']},
   {rawHeaders:raw.slice(0,4)},{url:'/api/\\evil'},{url:'/api'}]){
   assert.ok([400,403].includes(liveDevProxyPlan({...req,...bad},trust).status));
 }
});


test('C3 hosted browser proxy uses distinct exact origin and keeps private capability server-side',async()=>{
 const {liveDevProxyTrust,liveDevProxyPlan}=await import('../scripts/live-dev-api-proxy.mjs');
 const env={PILOTODIN_SERVER_MODE:'hosted-fixture',VITE_PILOTODIN_AUTH_DEV:'1',
   PILOTODIN_DEV_ORIGIN:'http://127.0.0.1:5178',PILOTODIN_DEV_PORT:'8000',
   PILOTODIN_DEV_CAPABILITY:'a'.repeat(64),CI:'true',GITHUB_ACTIONS:'true',
   P1_REAL_HTTP_E2E:'1',GITHUB_RUN_ID:'123',RUNNER_TEMP:'/tmp/runner',
   PILOTODIN_HOME:'/tmp/runner/pilotodin-p1-real-http-123'};
 const trust=liveDevProxyTrust(env);
 assert.equal(trust.port,5178);
 assert.throws(()=>liveDevProxyTrust({...env,P1_REAL_HTTP_E2E:''}));
 assert.throws(()=>liveDevProxyTrust({...env,PILOTODIN_HOME:'/tmp/other'}));
 const req={url:'/api/health',method:'GET',socket:{remoteAddress:'127.0.0.1'},
   rawHeaders:['Host','127.0.0.1:5178','X-PilotODIN-Dev-Request','1','Origin','http://127.0.0.1:5178']};
 assert.equal(liveDevProxyPlan(req,trust).options.headers.origin,'http://127.0.0.1:5178');
 assert.equal(liveDevProxyPlan({...req,rawHeaders:req.rawHeaders.slice(0,4)},trust).status,403);
 const seen=[];const api=loadAPI(async()=>{},async(url,options)=>{
   seen.push({url,headers:options.headers});return {ok:true,json:async()=>({status:'ok'})};
 });
 api.configureDevelopmentAPI('http://127.0.0.1:5178');await api.get('/health');
 assert.deepEqual(seen,[{url:'http://127.0.0.1:5178/api/health',headers:{'X-PilotODIN-Dev-Request':'1'}}]);
});


test('C3 proxy distinguishes denied requests from unavailable upstream without exposing capability',async()=>{
 const {createLiveDevProxy,liveDevProxyTrust}=await import('../scripts/live-dev-api-proxy.mjs');
 const {EventEmitter}=require('node:events');
 const env={PILOTODIN_SERVER_MODE:'dev',VITE_PILOTODIN_AUTH_DEV:'1',
   PILOTODIN_DEV_ORIGIN:'http://127.0.0.1:5173',PILOTODIN_DEV_PORT:'8000',PILOTODIN_DEV_CAPABILITY:'a'.repeat(64)};
 const trust=liveDevProxyTrust(env);
 function response(){
   const res=new EventEmitter();
   res.writeHead=(status)=>{res.status=status;res.headersSent=true};
   res.end=body=>{res.body=body;res.writableEnded=true};
   return res;
 }
 const upstream=new EventEmitter();
 upstream.destroy=()=>{};
 let calls=0;
 const proxy=createLiveDevProxy(trust,()=>{calls++;return upstream});
 const req=new EventEmitter();
 Object.assign(req,{url:'/api/health',method:'GET',socket:{remoteAddress:'127.0.0.1'},
   rawHeaders:['Host','127.0.0.1:5173','X-PilotODIN-Dev-Request','1','Origin','http://127.0.0.1:5173'],
   pipe:()=>{}});
 const denied=response();
 proxy({...req,rawHeaders:req.rawHeaders.slice(0,2)},denied,()=>assert.fail('unexpected next'));
 assert.equal(denied.status,403);assert.equal(calls,0);
 assert.match(JSON.parse(denied.body).detail,/request refused/);
 const unavailable=response();
 proxy(req,unavailable,()=>assert.fail('unexpected next'));
 upstream.emit('error',Error('private upstream failure '+trust.capability));
 assert.equal(unavailable.status,502);assert.equal(calls,1);
 assert.match(JSON.parse(unavailable.body).detail,/Could not connect to PilotODIN/);
 assert.ok(!unavailable.body.includes(trust.capability));
});
