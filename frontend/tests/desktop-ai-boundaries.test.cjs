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
   assert.equal(options.headers['X-PilotODIN-Session'],'a'.repeat(64));
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
  api.configureDesktopAPI({port:12345,token:'a'.repeat(64)});
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
  api.configureDesktopAPI({port:12345,token:'a'.repeat(64)});
  await assert.rejects(api.post(`${route}/${action}`,{}),{message});
  assert.deepEqual(events,['preflight','post']);
 }
});
test('secondary panes are barred from primary global controls',()=>{
 const app=fs.readFileSync(path.join(__dirname,'../src/App.tsx'),'utf8');
 assert.match(app,/if\(embedded && pid!==embeddedProjectId\)/);
 assert.match(app,/if\(embedded\)\{setError\('Import a new dataset from the primary workspace/);
 assert.match(app,/if\(embedded\)return;\s*const handler=\(event:KeyboardEvent\)/);
 const passive=app.slice(app.indexOf('// Saved status is passive;'),app.indexOf('const availableCommands='));
 assert.match(passive,/if\(embedded\|\|consentSession\.pending\)return;\s*let live=true;\s*const generation=consentSession\.generation;\s*get<SavedCloudPermission>\('\/ai\/settings'\)/);
 assert.match(passive,/if\(live&&cloudConsentIsCurrent\(generation\)\)setSavedStatus/);
 assert.match(passive,/return\(\)=>\{live=false\}/);
 assert.doesNotMatch(passive,/post\(|\/ai\/test\/|\/ai\/verify-connected/);
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
 assert.match(workspace,/!localPanelMayContinue\(result\.source\)/);
 assert.match(workspace,/const continuationProvider = 'ollama'/);
 assert.match(workspace,/selected_provider:continuationProvider,cloud_intent:false,continuation_text:result\.answer/);
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
   assert.equal(options.headers['X-PilotODIN-Session'],'a'.repeat(64));
   assert.deepEqual(JSON.parse(options.body),body);
   return Response.json({answer:'Verified rules',fallback:true,local_status:'resource_busy'});
  });
  api.configureDesktopAPI({port:12345,token:'a'.repeat(64),backend_driven_inference:true});
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
 api.configureDesktopAPI({port:12345,token:'a'.repeat(64),backend_driven_inference:true});
 await assert.rejects(api.post('/investigations/id/autonomy/start',{backend_driven_inference:false}),{message:'resource_busy'});
 assert.deepEqual(events,['/api/investigations/id/autonomy/start']);
 assert.throws(()=>api.configureDesktopAPI({port:12345,token:'a'.repeat(64),backend_driven_inference:'true'}));
});


test('owned routing mode is explicit metadata and not inferred from request',()=>{
 const api=loadAPI(async()=>assert.fail('Unexpected IPC'),async()=>assert.fail('Unexpected fetch'));
 assert.equal(api.usesOwnedInference(),false);
 api.configureDesktopAPI({port:12345,token:'a'.repeat(64),backend_driven_inference:true});
 assert.equal(api.usesOwnedInference(),true);
 api.configureDesktopAPI({port:12345,token:'a'.repeat(64),backend_driven_inference:false});
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
 assert.match(assistant,/useLayoutEffect\(\(\)=>fence.enter\(\),\[fence,projectId,session\.generation\]\)/);
 assert.match(assistant,/const ticket=fence.begin\(\);if\(!ticket\)return/);
 assert.match(assistant,/if\(!fence.isCurrent\(ticket\)\)return/);
 assert.match(assistant,/finally\{if\(fence.finish\(ticket\)\)setBusy\(false\)\}/);
 assert.match(insight,/useLayoutEffect\(\(\)=>fence.enter\(\),\[fence,fingerprint\]\)/);
 assert.equal((insight.match(/const ticket=fence.begin\(\);if\(!ticket\)return/g)||[]).length,3);
 assert.equal((insight.match(/finally\{if\(fence.finish\(ticket\)\)setBusy\(false\)\}/g)||[]).length,3);
 assert.match(insight,/if\(fence.isCurrent\(ticket\)&&cloudConsentIsCurrent\(session\.generation\)&&r.source!=='cloud_llm'\)setResult\(/);
 assert.doesNotMatch(insight,/insightCache|pendingInsights/);
 assert.match(insight,/if\(fence.isCurrent\(ticket\)\)setInvestigationResult\(/);
 assert.match(insight,/usesOwnedInference\(\)\?'waiting for the selected route/);
 assert.match(insight,/value="auto">Smart Auto \(local only\)/);
});


test('C3 explicit development API accepts only approved origins and sends only a same-origin proxy marker',async()=>{
 for(const port of [5173,5174,5176,5177,5178]){
   const origin='http://127.0.0.1:'+port;
   const seen=[];
   const api=loadAPI(async()=>{throw Error('Unexpected native IPC');},async(url,options)=>{
     seen.push({url,headers:options.headers});
     return {ok:true,json:async()=>({status:'ok'})};
   });
   for(const invalid of ['http://127.0.0.1:5175',
     'http://127.0.0.1:5179','http://127.0.0.1:8000','http://localhost:'+port,
     'http://192.0.2.1:'+port,'https://127.0.0.1:'+port,origin+'/',origin+'/api','']){
     assert.throws(()=>api.configureDevelopmentAPI(invalid),invalid);
   }
   api.configureDevelopmentAPI(origin);
   assert.equal(api.apiBase(),origin+'/api');
   await api.get('/health');
   assert.deepEqual(seen,[{url:origin+'/api/health',headers:{'X-PilotODIN-Dev-Request':'1'}}]);
   assert.throws(()=>api.configureDesktopAPI({port:12345,token:'b'.repeat(64)}));
 }
 const desktop=loadAPI();
 desktop.configureDesktopAPI({port:12345,token:'b'.repeat(64)});
 for(const port of [5173,5174,5176,5177,5178])
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

test('C3 unconfigured API cannot perform HTTP or IPC and rejects invalid desktop sessions',async()=>{
  const api=loadAPI(async()=>assert.fail('Unexpected IPC'),async()=>assert.fail('Unexpected fetch'));
  assert.throws(()=>api.apiBase(),/has not been configured/);
  await assert.rejects(api.get('/health'),/has not been configured/);
  await assert.rejects(api.post('/projects/id/ai/insight',{}),/has not been configured/);
  await assert.rejects(api.put('/ai/settings',{}),/has not been configured/);
  await assert.rejects(api.upload(new Blob(['synthetic'])),/has not been configured/);
  for(const token of [undefined,null,0,'','test-session','a'.repeat(63),'A'.repeat(64),'a'.repeat(65),'a'.repeat(63)+'\n']){
    assert.throws(()=>api.configureDesktopAPI({port:18042,token}),/Invalid desktop API/);
  }
  for(const port of [undefined,0,1023,65536,18042.5,'18042']){
    assert.throws(()=>api.configureDesktopAPI({port,token:'a'.repeat(64)}),/Invalid desktop API/);
  }
  assert.throws(()=>api.apiBase(),/has not been configured/);
});
test('C3 intercepted fixture is distinct from paired Live Dev and never has a desktop credential',async()=>{
  const seen=[];
  const api=loadAPI(async()=>assert.fail('Unexpected IPC'),async(url,options)=>{
    seen.push({url,headers:options.headers});return Response.json({status:'ok'});
  });
  const origin='http://127.0.0.1:5187';
  assert.throws(()=>api.configureDevelopmentAPI(origin));
  for(const invalid of ['http://localhost:5187','http://127.0.0.1:8000','http://127.0.0.1:5173',origin+'/']) {
    assert.throws(()=>api.configureInterceptedFixtureAPI(invalid));
  }
  api.configureInterceptedFixtureAPI(origin);
  await api.get('/health');
  assert.deepEqual(seen,[{url:origin+'/api/health',headers:{'X-PilotODIN-Dev-Request':'1'}}]);
  assert.throws(()=>api.configureDevelopmentAPI('http://127.0.0.1:5173'));
  assert.throws(()=>api.configureDesktopAPI({port:18042,token:'a'.repeat(64)}));
  const dev=loadAPI();
  dev.configureDevelopmentAPI('http://127.0.0.1:5173');
  assert.throws(()=>dev.configureInterceptedFixtureAPI(origin));
});


test('C3 authenticated GET, POST, PUT and multipart upload share exact destination and refuse redirects',async()=>{
 const modes=['desktop','dev','intercepted'];
 for(const mode of modes){
  const calls=[];
  const api=loadAPI(async()=>assert.fail('Unexpected native IPC'),async(url,options)=>{
   calls.push({url,options});
   assert.equal(options.redirect,'error');
   return Response.json({status:'ok'});
  });
  const origin=mode==='desktop'?'http://127.0.0.1:18042':mode==='dev'?'http://127.0.0.1:5173':'http://127.0.0.1:5187';
  if(mode==='desktop')api.configureDesktopAPI({port:18042,token:'a'.repeat(64)});
  else if(mode==='dev')api.configureDevelopmentAPI(origin);
  else api.configureInterceptedFixtureAPI(origin);
  const signal=new AbortController().signal;
  await api.get('/health',{signal});
  await api.get('/projects?column=Revenue%20%26%20Cost%2FUnit');
  await api.post('/projects/id/reports',{synthetic:true});
  await api.put('/ai/settings',{cloud_enabled:false});
  await api.upload(new File(['synthetic'], 'fixture.csv',{type:'text/csv'}));
  assert.deepEqual(calls.map(x=>x.url),['/health','/projects?column=Revenue%20%26%20Cost%2FUnit',
    '/projects/id/reports','/ai/settings','/projects'].map(p=>origin+'/api'+p));
  assert.deepEqual(calls.map(x=>x.options.method??'GET'),['GET','GET','POST','PUT','POST']);
  assert.equal(calls[0].options.signal,signal);
  for(const {url,options} of calls){
   const header=mode==='desktop'?'X-PilotODIN-Session':'X-PilotODIN-Dev-Request';
   assert.equal(options.headers[header],mode==='desktop'?'a'.repeat(64):'1');
   assert.equal(Object.hasOwn(options.headers,'X-PilotODIN-Dev-Capability'),false);
   assert.ok(!url.includes('a'.repeat(64)));
  }
  assert.ok(calls[4].options.body instanceof FormData);
 }
});

test('C3 invalid or normalized escape destinations refuse before HTTP and native launch',async()=>{
 const api=loadAPI(async()=>assert.fail('Unexpected native IPC'),async()=>assert.fail('Unexpected fetch'));
 api.configureDesktopAPI({port:18042,token:'a'.repeat(64)});
 for(const path of ['','health','https://invalid.example/health','//invalid.example/health',
    '/','/../health','/./health','/%2e%2e/health','/projects/../ai/insight',
    '/projects/%2e%2e/ai/insight','/projects/%2f/ai/insight','/projects/%5c/ai/insight',
    '/projects/\\bad','/health#fragment','/health\n']){
  await assert.rejects(api.get(path),/Invalid local API destination/);
  await assert.rejects(api.post(path,{}),/Invalid local API destination/);
  await assert.rejects(api.put(path,{}),/Invalid local API destination/);
 }
});

test('C3 unexpected redirect and redirect transport failure cannot replay credentials or read response',async()=>{
 const secret='a'.repeat(64);
 for(const status of [301,302,303,307,308]){
  const calls=[];
  let cancelled=false;
  const response=new Response(new ReadableStream({cancel(){cancelled=true}}),
    {status,headers:{Location:'https://invalid.example/private-trap'}});
  const api=loadAPI(async()=>assert.fail('Unexpected IPC'),async(url,options)=>{
   calls.push(url);assert.equal(options.redirect,'error');return response;
  });
  api.configureDesktopAPI({port:18042,token:secret});
  await assert.rejects(api.get('/health'),/Local API redirect refused/);
  assert.equal(cancelled,true);
  assert.deepEqual(calls,['http://127.0.0.1:18042/api/health']);
 }
 const calls=[];
 const api=loadAPI(async()=>assert.fail('Unexpected IPC'),async(url,options)=>{
  calls.push(url);assert.equal(options.redirect,'error');
  throw new TypeError('redirect trap '+secret);
 });
 api.configureDesktopAPI({port:18042,token:secret});
 await assert.rejects(api.post('/projects/id/reports?private=synthetic',{}),error=>
  /Could not connect to PilotODIN/.test(error.message)&&!error.message.includes(secret)&&
  !error.message.includes('synthetic')&&!error.message.includes('redirect trap'));
 assert.deepEqual(calls,['http://127.0.0.1:18042/api/projects/id/reports?private=synthetic']);
});

test('C3 archived hosted desktop driver source confines direct session requests without running native QA',()=>{
 const driver=fs.readFileSync(path.join(__dirname,'../e2e/p4-r03-hosted-desktop.mjs'),'utf8');
 assert.match(driver,/Number\.isInteger\(connection\.port\)/);
 assert.match(driver,/connection\.port<1024\|\|connection\.port>65535/);
 assert.match(driver,/path!=='\/ai\/settings'&&path!=='\/resource\/policy'/);
 assert.equal((driver.match(/redirect:'error'/g)||[]).length,3);
 assert.match(driver,/PILOTODIN_R03_HOSTED_DESKTOP !== 'approved'/);
});


// C4 C1: execute the actual renderer-local mutation fence and saved permission
// policy. No fetch, provider, IPC, native or model is invoked.
function loadCloudConsentSession(){
 const source=fs.readFileSync(path.join(__dirname,'../src/cloudConsentSession.ts'),'utf8');
 const output=ts.transpileModule(source,{compilerOptions:{target:ts.ScriptTarget.ES2021,module:ts.ModuleKind.CommonJS}}).outputText;
 const mod={exports:{}};
 new Function('module','exports',output)(mod,mod.exports);
 return mod.exports;
}
test('C4 settings operations synchronously invalidate stale status and keep exact ownership',()=>{
 const session=loadCloudConsentSession();
 const first=session.cloudConsentSnapshot();
 const seen=[];
 const unsubscribe=session.subscribeCloudConsent(()=>seen.push(session.cloudConsentSnapshot()));
 assert.ok(Object.isFrozen(first));
 const ticket=session.beginCloudSettingsOperation(first.generation);
 assert.ok(ticket);
 assert.equal(session.cloudConsentIsCurrent(first.generation),false);
 assert.equal(session.cloudConsentSnapshot().pending,true);
 assert.equal(session.beginCloudSettingsOperation(session.cloudConsentSnapshot().generation),null);
 assert.equal(session.finishCloudSettingsOperation({...ticket}),null);
 const settled=session.finishCloudSettingsOperation(ticket);
 assert.equal(settled.pending,false);
 assert.equal(session.cloudConsentIsCurrent(settled.generation),true);
 assert.equal(session.beginCloudSettingsOperation(first.generation),null);
 const next=session.beginCloudSettingsOperation(settled.generation);
 assert.ok(next);
 assert.equal(session.finishCloudSettingsOperation(ticket),null);
 assert.equal(session.cloudConsentSnapshot().pending,true);
 assert.ok(session.finishCloudSettingsOperation(next));
 assert.equal(seen.length,4);
 unsubscribe();
});
test('C4 explicit handshake needs confirmed saved consent and configured key, not verified status',()=>{
 const session=loadCloudConsentSession();
 const saved={cloud_enabled:true,share_aggregates:true,intelligence_mode:'hybrid',
   providers:[{id:'gemini',connected:true,verified:false},{id:'groq',connected:false,verified:true}]};
 assert.equal(session.canTestCloud(saved,'gemini'),true);
 assert.equal(session.savedCloudStatus(saved),'unverified');
 assert.equal(session.canTestCloud(saved,'groq'),false);
 assert.equal(session.canTestCloud(saved,'invalid'),false);
 for(const invalid of [null,{...saved,cloud_enabled:'true'},{...saved,share_aggregates:false},
  {...saved,intelligence_mode:'local'},{...saved,intelligence_mode:'invalid'},
  {...saved,credential_warning:'uncertain'},{...saved,settings_warning:'uncertain'},
  {...saved,providers:[{id:'gemini',connected:'true'}]}]){
   assert.equal(session.canTestCloud(invalid,'gemini'),false);
 }
 const verified={...saved,providers:[{id:'gemini',connected:true,verified:true}]};
 assert.equal(session.savedCloudStatus(verified),'connected');
 assert.equal(session.savedCloudStatus({...verified,cloud_enabled:false}),'local');
});
test('C4 settings and startup only use manual handshake, never key-save or startup cloud probes',()=>{
 const source=fs.readFileSync(path.join(__dirname,'../src/AIWorkspace.tsx'),'utf8');
 const settings=source.slice(source.indexOf('export function AISettings'),source.indexOf('const labels'));
 const shell=fs.readFileSync(path.join(__dirname,'../src/App.tsx'),'utf8');
 const testBody=settings.slice(settings.indexOf('async function testProvider'),settings.indexOf('async function testLocal'));
 const keyBody=settings.slice(settings.indexOf('async function saveKey'),settings.indexOf('function move'));
 assert.match(testBody,/!fresh\|\|dirty\|\|!canTestCloud\(confirmed,provider\)/);
 assert.match(testBody,/await get<Settings>\('\/ai\/settings'\)/);
 assert.match(testBody,/if\(!canTestCloud\(saved,provider\)\)return/);
 assert.match(testBody,/\{cloud_intent:true\}/);
 assert.doesNotMatch(keyBody,/testProvider\(|\/ai\/test\//);
 assert.match(keyBody,/Connection not tested/);
 assert.doesNotMatch(shell,/\/ai\/verify-connected|\/ai\/test\//);
 assert.match(shell,/cloudConsentIsCurrent\(generation\)/);
 assert.match(settings,/OpenRouter may route this handshake downstream; project-data sharing through OpenRouter is disabled/);
 assert.doesNotMatch(source.slice(source.indexOf('export function AIInsight')), /cloud_intent:true/);
});


test('C4 C2 saved cloud preference cannot become a local panel route or request',()=>{
 const session=loadCloudConsentSession();
 for(const value of ['gemini','groq','openrouter','unknown',null,undefined,true,{}]){
   assert.equal(session.localPanelProvider(value),'auto');
   assert.equal(session.localPanelRequest(value),null);
 }
 for(const value of ['auto','local','ollama']){
   assert.equal(session.localPanelProvider(value),value);
   assert.deepEqual(session.localPanelRequest(value),{selected_provider:value,cloud_intent:false});
 }
 assert.equal(session.localPanelMayContinue('local_llm'),true);
 for(const value of ['cloud_llm','local_rules',null,undefined])assert.equal(session.localPanelMayContinue(value),false);
});
test('C4 C2 named destinations and disclosure remain held before project cloud enablement',()=>{
 const session=loadCloudConsentSession();
 assert.equal(session.projectCloudProviderName('gemini'),'Google Gemini');
 assert.equal(session.projectCloudProviderName('groq'),'GroqCloud');
 assert.equal(session.projectCloudProviderName('openrouter'),'OpenRouter');
 assert.equal(session.projectCloudProviderName('auto'),null);
 assert.match(session.projectCloudHold('gemini'),/not available/);
 assert.match(session.projectCloudHold('openrouter'),/downstream destinations/);
 for(const word of ['column names','your question','not guaranteed anonymous','Uploaded rows','previous answers','cannot be recalled']){
   assert.ok(session.projectCloudDisclosure.includes(word));
 }
});
test('C4 C2 actual panels keep auto local and never persist a cloud choice or continue cloud answers',()=>{
 const assistant=fs.readFileSync(path.join(__dirname,'../src/AssistantWorkspace.tsx'),'utf8');
 const workspace=fs.readFileSync(path.join(__dirname,'../src/AIWorkspace.tsx'),'utf8');
 const insight=workspace.slice(workspace.indexOf('export function AIInsight'));
 for(const panel of [assistant,insight]){
   assert.match(panel,/localPanelProvider\(localStorage.getItem/);
   assert.match(panel,/if\(isLocalPanelProvider\(e.target.value\)\)localStorage.setItem/);
   assert.match(panel,/projectCloudDisclosure/);
   assert.match(panel,/projectCloudHold/);
   assert.match(panel,/localPanelRequest/);
   assert.match(panel,/!routeAvailable\|\|session.pending/);
   assert.doesNotMatch(panel,/cloud_intent:true/);
 }
 assert.match(insight,/auto_insights===true&&r.local_model_enabled===true/);
 assert.match(insight,/if\(auto&&routeAvailable&&!session.pending\)void run\(false\)/);
 assert.match(assistant,/!localPanelMayContinue\(last.answerSource\)/);
 assert.match(assistant,/r.source==='cloud_llm'\)return/);
 assert.doesNotMatch(insight,/insightCache|pendingInsights/);
});
