const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const {createHash}=require('node:crypto');
const ts=require('typescript');
const source=fs.readFileSync(path.join(__dirname,'../src/datasetExportDownload.ts'),'utf8');
const compiled=ts.transpileModule(source,{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2021}}).outputText;
const mod={exports:{}};
new Function('module','exports',compiled)(mod,mod.exports);
const {verifyDatasetDownload,MAX_DATASET_EXPORT_BYTES}=mod.exports;
const csv=Buffer.from('\ufeffID,Amount\r\nA001,12\r\n');
const zip=Buffer.from([0x50,0x4b,3,4,1,2,3,4]); // signature only, not a workbook
const hash=bytes=>createHash('sha256').update(bytes).digest('hex');
const req={version:0,format:'csv',filters:[]};
function response(bytes=csv,overrides={},request=req,body=bytes){
  const headers={
    'content-disposition':'attachment; filename="Generated_cleaned_v'+request.version+(request.filters?.length?'_filtered':'')+'.'+request.format+'"',
    'content-type':request.format==='csv'?'text/csv; charset=utf-8':'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    'content-length':String(bytes.length),'x-pilotodin-export-sha256':hash(bytes),
    'x-pilotodin-dataset-version':String(request.version),'x-pilotodin-exported-rows':'1',...overrides
  };
  return new Response(body,{headers});
}
test('CSV and filtered XLSX metadata and exact bytes are retained',async()=>{
  const a=await verifyDatasetDownload(response(),req);
  assert.equal(a.filename,'Generated_cleaned_v0.csv');
  assert.equal(a.expectedBytes,csv.length);
  assert.equal(a.sha256,hash(csv));assert.equal(a.rows,1);
  assert.deepEqual(Buffer.from(await a.blob.arrayBuffer()),csv);
  const r={version:17,format:'xlsx',filters:[{}]};
  const b=await verifyDatasetDownload(response(zip,{},r),r);
  assert.equal(b.filename,'Generated_cleaned_v17_filtered.xlsx');
  assert.deepEqual(Buffer.from(await b.blob.arrayBuffer()),zip);
});
test('wrong, missing, duplicate or noncanonical metadata is refused',async()=>{
  for(const headers of [
    {'x-pilotodin-dataset-version':'1'},{'x-pilotodin-dataset-version':'00'},
    {'content-length':'0'},{'content-length':String(MAX_DATASET_EXPORT_BYTES+1)},
    {'content-length':'1e2'},{'content-length':'12, 12'},
    {'x-pilotodin-exported-rows':'-1'},{'x-pilotodin-exported-rows':'9007199254740992'},
    {'x-pilotodin-export-sha256':''},{'x-pilotodin-export-sha256':'A'.repeat(64)},
    {'content-disposition':'attachment; filename="../Generated_cleaned_v0.csv"'},
    {'content-disposition':'attachment; filename="Generated_cleaned_v1.csv"'},
    {'content-disposition':'attachment; filename="Generated_cleaned_v0_filtered.csv"'},
    {'content-disposition':'attachment; filename="Generated_cleaned_v0.xlsx"'},
    {'content-type':'text/html'}
  ])await assert.rejects(verifyDatasetDownload(response(csv,headers),req));
  await assert.rejects(verifyDatasetDownload(new Response(csv),req));
});
test('short, overlong, changed or wrong-signature payloads are refused',async()=>{
  await assert.rejects(verifyDatasetDownload(response(csv,{},req,csv.subarray(0,csv.length-1)),req));
  await assert.rejects(verifyDatasetDownload(response(csv,{},req,Buffer.concat([csv,Buffer.from('x')])),req));
  const changed=Buffer.from(csv);changed[5]^=1;
  await assert.rejects(verifyDatasetDownload(response(csv,{},req,changed),req));
  await assert.rejects(verifyDatasetDownload(response(Buffer.from('not csv')),req));
  await assert.rejects(verifyDatasetDownload(response(csv,{'x-pilotodin-export-sha256':'0'.repeat(64)}),req));
});
test('oversized metadata cancels without consuming the stream',async()=>{
  let cancelled=false;
  const stream=new ReadableStream({cancel(){cancelled=true;}});
  await assert.rejects(verifyDatasetDownload(response(csv,{'content-length':String(MAX_DATASET_EXPORT_BYTES+1)},req,stream),req));
  assert.equal(cancelled,true);
});
test('excess bytes cancel an unfinished transfer',async()=>{
  let cancelled=false;
  const stream=new ReadableStream({start(c){c.enqueue(Buffer.concat([csv,Buffer.from('x')]));},cancel(){cancelled=true;}});
  await assert.rejects(verifyDatasetDownload(response(csv,{},req,stream),req));
  assert.equal(cancelled,true);
});
test('production download calls the strict verifier before returning bytes',()=>{
  const api=fs.readFileSync(path.join(__dirname,'../src/api.ts'),'utf8');
  assert.match(api,/return verifyDatasetDownload\(response,body,project\)/);
});

test('signed receipt metadata must match the requested project and be complete',async()=>{
  const project='a'.repeat(32);
  const headers={'x-pilotodin-export-project':project,'x-pilotodin-export-operation':'b'.repeat(32),'x-pilotodin-export-mac':'c'.repeat(64)};
  const result=await verifyDatasetDownload(response(csv,headers),req,project);
  assert.deepEqual(result.receipt,{project,operation:'b'.repeat(32),mac:'c'.repeat(64)});
  await assert.rejects(verifyDatasetDownload(response(csv,headers),req,'d'.repeat(32)));
  await assert.rejects(verifyDatasetDownload(response(csv,{...headers,'x-pilotodin-export-mac':''}),req,project));
  assert.equal((await verifyDatasetDownload(response(),req)).receipt,null);
});

test('native binary IPC is separate, authenticated, current and cancellation-aware',async()=>{
  const api=fs.readFileSync(path.join(__dirname,'../src/api.ts'),'utf8');
  const js=ts.transpileModule(api,{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2021}}).outputText;
  const calls=[];
  let outcome={status:'cancelled',filename:null};
  const module={exports:{}};
  const mockRequire=name=>{
    if(name==='@tauri-apps/api/core')return {invoke:async(...args)=>{calls.push(args);return outcome}};
    if(name==='./datasetExportDownload')return mod.exports;
    throw Error('Unexpected import '+name);
  };
  new Function('module','exports','require','window',js)(module,module.exports,mockRequire,{__TAURI_INTERNALS__:{}});
  const save=module.exports.saveDatasetNative;
  const project='a'.repeat(32);
  const headers={'x-pilotodin-export-project':project,'x-pilotodin-export-operation':'b'.repeat(32),'x-pilotodin-export-mac':'c'.repeat(64)};
  const signed=await verifyDatasetDownload(response(csv,headers),req,project);
  await assert.rejects(save({...signed,receipt:null},()=>true));
  await assert.rejects(save(signed,()=>false));
  let checks=0;
  await assert.rejects(save(signed,()=>++checks===1));
  await assert.rejects(save({...signed,expectedBytes:1},()=>true));
  assert.equal(calls.length,0);
  assert.deepEqual(await save(signed,()=>true),outcome);
  assert.equal(calls[0][0],'save_dataset_as');
  assert.deepEqual(Buffer.from(calls[0][1]),csv);
  assert.equal(calls[0][2].headers['x-pilotodin-export-mac'],headers['x-pilotodin-export-mac']);
  assert.equal(Object.keys(calls[0][2].headers).length,9);
  outcome={status:'saved',filename:'chosen.csv'};
  assert.deepEqual(await save(signed,()=>true),outcome);
  outcome={status:'saved',filename:null};
  await assert.rejects(save(signed,()=>true));
});
test('native dataset consent gates precede publication and do not broaden capabilities',()=>{
  const ui=fs.readFileSync(path.join(__dirname,'../src/QualityWorkspace.tsx'),'utf8');
  const host=fs.readFileSync(path.join(__dirname,'../src-tauri/src/lib.rs'),'utf8');
  const caps=JSON.parse(fs.readFileSync(path.join(__dirname,'../src-tauri/capabilities/default.json'),'utf8'));
  assert.match(ui,/if\(isDesktop\(\)\)\{\s*const outcome=await saveDatasetNative\(download,isCurrent\)/);
  assert.match(ui,/Dataset Save As cancelled\. No destination file was written/);
  assert.ok(ui.indexOf('saveDatasetNative(download,isCurrent)')<ui.indexOf('URL.createObjectURL(blob)'));
  const command=host.slice(host.indexOf('async fn save_dataset_as('),host.indexOf('async fn save_report_as('));
  for(const marker of ['window.label()!="main"','Metadata::from_headers','InvokeBody::Raw','compare_exchange','metadata.verify(&key)?','dataset_file::validate','blocking_save_file','None=>return Ok','dataset_file::publish_new']){
    assert.ok(command.includes(marker),marker);
  }
  assert.ok(command.indexOf('metadata.verify(&key)?')<command.indexOf('blocking_save_file'));
  assert.ok(command.indexOf('None=>return Ok')<command.indexOf('dataset_file::publish_new'));
  assert.deepEqual(caps.permissions,['core:default']);
  assert.match(host,/save_report_as, save_dataset_as,/);
});

test('B5 export selection stays fixed during transfer and normal close waits for active save',()=>{
  const ui=fs.readFileSync(path.join(__dirname,'../src/QualityWorkspace.tsx'),'utf8');
  const host=fs.readFileSync(path.join(__dirname,'../src-tauri/src/lib.rs'),'utf8');
  for(const name of ['exportVersion','exportFormat','exportFilterColumn'])assert.ok(ui.includes('<select disabled={exporting} value={'+name+'}'),name);
  assert.ok(ui.includes('<input disabled={exporting} aria-label="Filter contains"'));
  assert.ok(ui.includes('type="checkbox" disabled={exporting} checked={exportColumns.includes(column)}'));
  const stop=host.slice(host.indexOf('fn stop_owned_workers('),host.indexOf('async fn launch_backend('));
  assert.ok(stop.indexOf('state.stopping.store(true')<stop.indexOf('state.dataset_save_busy.load'));
  assert.ok(stop.indexOf('state.dataset_save_busy.load')<stop.indexOf('state.launch_gate.try_lock'));
  const roots=host.slice(host.indexOf('fn dataset_destination_roots('),host.indexOf('async fn save_dataset_as('));
  assert.ok(roots.includes('std::env::current_exe()'));
  assert.ok(roots.includes('protected.push(executable_parent)'));
  const save=host.slice(host.indexOf('async fn save_dataset_as('),host.indexOf('async fn save_report_as('));
  assert.ok(save.indexOf('blocking_save_file')<save.indexOf('state.launch_gate.lock()'));
  assert.ok(save.indexOf('state.launch_gate.lock()')<save.lastIndexOf('current_dataset_export_key(&app)?'));
  assert.ok(save.lastIndexOf('current_dataset_export_key(&app)?')<save.indexOf('dataset_file::publish_new'));
});
