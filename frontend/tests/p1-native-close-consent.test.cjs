const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const ts=require('typescript');
const Module=require('node:module');

const dir=path.resolve(__dirname,'../src');
const file=path.join(dir,'nativeCloseConsent.ts');
const rust=fs.readFileSync(path.join(dir,'../src-tauri/src/lib.rs'),'utf8');
const shell=fs.readFileSync(path.join(dir,'UnifiedShell.tsx'),'utf8');
const js=ts.transpileModule(fs.readFileSync(file,'utf8'),{
 compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2021},
 reportDiagnostics:true
});
assert.equal((js.diagnostics||[]).filter(d=>d.category===ts.DiagnosticCategory.Error).length,0);
const mod=new Module(file,module);
mod.filename=file;mod.paths=module.paths;
mod._compile(js.outputText,file);
const {resolveNativeCloseRequest,NATIVE_CLOSE_MESSAGE,NATIVE_CLOSE_EVENT}=mod.exports;
const token='a'.repeat(32);

test('native close clean form approves one ticket without prompting',async()=>{
 const calls=[],asked=[];
 await resolveNativeCloseRequest({token},()=>false,msg=>(asked.push(msg),false),
  async(t,approve)=>calls.push([t,approve]));
 assert.deepEqual(calls,[[token,true]]);
 assert.deepEqual(asked,[]);
});
test('edited form native Close Cancel blocks window and keeps consent message',async()=>{
 const calls=[],asked=[];
 await resolveNativeCloseRequest({token},()=>true,msg=>(asked.push(msg),false),
  async(t,approve)=>calls.push([t,approve]));
 assert.deepEqual(calls,[[token,false]]);
 assert.deepEqual(asked,[NATIVE_CLOSE_MESSAGE]);
 assert.match(asked[0],/unsaved changes.*discard/);
});
test('edited form native Close Leave approves exactly the current ticket',async()=>{
 const calls=[];
 await resolveNativeCloseRequest({token},()=>true,()=>true,
  async(t,approve)=>calls.push([t,approve]));
 assert.deepEqual(calls,[[token,true]]);
});
test('dirty-check or confirmation errors fail closed',async()=>{
 for(const which of ['dirty','confirm']){
  const calls=[];
  await resolveNativeCloseRequest({token},
   ()=>{if(which==='dirty')throw Error('failed');return true},
   ()=>{if(which==='confirm')throw Error('failed');return true},
   async(t,approve)=>calls.push([t,approve]));
  assert.deepEqual(calls,[[token,false]]);
 }
});
test('missing, malformed, and unexpected tokens cannot issue native close',async()=>{
 const calls=[];
 for(const payload of [null,{},'x',{token:5},{token:'../../close'},{token:'0'.repeat(31)}])
  await resolveNativeCloseRequest(payload,()=>false,()=>true,async(...args)=>calls.push(args));
 assert.deepEqual(calls,[]);
});
test('Rust intercepts before close, uses one-time ticket, no writes or broad permission',()=>{
 assert.match(rust,/CloseRequested \{ api, \.\. \} = event/);
 assert.match(rust,/api\.prevent_close\(\)/);
 assert.match(rust,/window\.emit\(\s*"pilotodin:native-close-requested"/);
 assert.match(rust,/consume_native_close_ticket\(&mut pending, &token\)/);
 assert.match(rust,/window\.label\(\) != "main"/);
 assert.match(rust,/window\.destroy\(\)/);
 assert.doesNotMatch(rust,/window\.close\(\)/);
 assert.match(rust,/#\[test\]\s*fn only_current_ticket_can_authorize_one_native_close_resolution/);
 // Match structural Rust declarations, never an exact LF/CRLF separator.
 // A missing end marker must fail explicitly, not silently scan the whole file.
 function extractHandler(source){
  const start=source.indexOf('fn resolve_native_close_request(');
  const end=source.indexOf('struct ModelManifest',start);
  assert.ok(start>=0&&end>start,'native close handler boundaries must be present');
  return source.slice(start,end);
 }
 const handler=extractHandler(rust);
 assert.doesNotMatch(handler,/std::fs::write|localStorage|sessionStorage|launch_backend|launch_bundled_ai/);
 // Git may check Rust out with CRLF on Windows; simulate that even on Linux.
 const windowsSource=rust.replace(/\r?\n/g,'\r\n');
 assert.equal(extractHandler(windowsSource).replace(/\r\n/g,'\n'),handler.replace(/\r\n/g,'\n'));

});
test('shell registers native listener separately and preserves browser unload guard',()=>{
 assert.match(shell,/if\(!isDesktop\(\)\)return/);
 assert.match(shell,/listen<NativeCloseRequest>\(NATIVE_CLOSE_EVENT/);
 assert.match(shell,/hasUnsavedWorkspaceDraftForUnload\(state\.projectId,state\.workspaceReady/);
 assert.match(shell,/invoke<void>\('resolve_native_close_request',\{token,approve\}\)/);
 assert.match(shell,/return\(\)=>\{disposed=true;unlisten\?\.\(\)\}/);
 assert.match(shell,/window\.addEventListener\('beforeunload',onBeforeUnload\)/);
 assert.match(shell,/window\.removeEventListener\('beforeunload',onBeforeUnload\)/);
 assert.equal(NATIVE_CLOSE_EVENT,'pilotodin:native-close-requested');
});
