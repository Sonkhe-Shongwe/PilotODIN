'use strict';
// Executable regression for the exact Tauri Windows fetch-first IPC request.
// Runs in Node without opening a native window or touching owner data.
const test=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');
const ts=require('../node_modules/typescript');
const sourcePath=path.resolve(__dirname,'../src/p3NativeW5IpcGuard.ts');
const code=fs.readFileSync(sourcePath,'utf8');
const js=ts.transpileModule(code,{
  compilerOptions:{target:ts.ScriptTarget.ES2021,module:ts.ModuleKind.CommonJS}
}).outputText;
const moduleExports={};
vm.runInNewContext(js,{exports:moduleExports,URL,Headers});
const {isNativeW5FinishIpcRequest:permits}=moduleExports;
const headers=new Headers({
  'Tauri-Invoke-Key':'opaque-local-test-key',
  'Tauri-Callback':'1234',
  'Tauri-Error':'5678',
  'Content-Type':'application/json',
});
const options={method:'POST',headers,body:'{}'};
const windows='http://ipc.localhost/finish_p3_w5_synthetic_qa';
const other='ipc://localhost/finish_p3_w5_synthetic_qa';

test('Tauri Windows WebView2 exact finish IPC request passes through',()=>{
  assert.equal(permits(new URL(windows),'POST',options),true);
  assert.equal(permits(new URL(other),'POST',options),true);
  assert.equal(permits(new URL(windows),'POST',{...options,headers:Object.fromEntries(headers)}),true);
});
test('normal browser and other Tauri command calls stay blocked',()=>{
  for(const name of [
    'http://127.0.0.1:8000/api/projects/a/quality/commit',
    'https://example.com/finish_p3_w5_synthetic_qa',
    'http://ipc.localhost/plugin%3Aevent%7Clisten',
    'http://ipc.localhost/launch_backend',
    'http://ipc.localhost:99/finish_p3_w5_synthetic_qa',
    'http://ipc.localhost/finish_p3_w5_synthetic_qa?bypass=1',
    'http://ipc.localhost/finish_p3_w5_synthetic_qa#fragment',
    'ipc://other-host/finish_p3_w5_synthetic_qa',
    'http://user@ipc.localhost/finish_p3_w5_synthetic_qa',
  ])assert.equal(permits(new URL(name),'POST',options),false,name);
  assert.equal(permits(new URL(windows),'GET',options),false);
});
test('an unmarked IPC-like request cannot bypass the synthetic API guard',()=>{
  assert.equal(permits(new URL(windows),'POST',undefined),false);
  for(const omitted of ['Tauri-Invoke-Key','Tauri-Callback','Tauri-Error']){
    const incomplete=new Headers(headers);
    incomplete.delete(omitted);
    assert.equal(permits(new URL(windows),'POST',{headers:incomplete}),false,omitted);
  }
});
