const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const ts=require('typescript');
const src=fs.readFileSync(path.join(__dirname,'../src/api.ts'),'utf8');
const result=ts.transpileModule(src,{compilerOptions:{target:ts.ScriptTarget.ES2021,module:ts.ModuleKind.CommonJS},reportDiagnostics:true});
assert.equal((result.diagnostics||[]).filter(x=>x.category===ts.DiagnosticCategory.Error).length,0);
const mod={exports:{}};
new Function('require','module','exports',result.outputText)(()=>({invoke:async()=>{}}),mod,mod.exports);
const {shouldLaunchBundledAI}=mod.exports;
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
