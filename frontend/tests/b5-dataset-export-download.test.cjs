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
  assert.match(api,/return verifyDatasetDownload\(response,body\)/);
});
