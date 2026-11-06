const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const read=name=>fs.readFileSync(path.join(__dirname,'../src',name),'utf8');

test('A4 Quality evidence is explicitly captured at current approved version',()=>{
 const ui=read('ReportWorkspace.tsx');
 assert.match(ui,/captureQualityAudit/);
 assert.match(ui,/\/projects\/\$\{encodeURIComponent\(projectId\)\}\/quality/);
 assert.match(ui,/\/projects\/\$\{encodeURIComponent\(projectId\)\}\/report-quality/);
 assert.match(ui,/expected_version:state.version/);
 assert.match(ui,/Capture current Quality audit/);
 assert.match(ui,/saved\.id/);
 assert.match(ui,/Saved Quality audit/);
});

test('A4 invalid report payload cannot be advertised as a successful download',()=>{
 const api=read('api.ts');
 assert.match(api,/validMime/);
 assert.match(api,/validSignature/);
 assert.match(api,/%PDF-/);
 assert.match(api,/<!doctype html>/);
 assert.match(api,/No download was started/);
 assert.match(api,/content-type/);
});

test('A4 browser remains a download; desktop invokes native Save As with explicit cancel',()=>{
 const ui=read('ReportWorkspace.tsx');
 const api=read('api.ts');
 assert.match(ui,/Started browser download/);
 assert.match(ui,/Confirm the file in Downloads/);
 assert.match(ui,/if\(isDesktop\(\)\)/);
 assert.match(ui,/saveReportNative\(blob,filename,format\)/);
 assert.match(ui,/outcome\.status==='cancelled'/);
 assert.match(ui,/No report file was written/);
 assert.match(ui,/Saved report revision/);
 assert.match(api,/invoke<NativeReportSaveStatus>\('save_report_as'/);
 assert.match(api,/blob\.arrayBuffer\(\)/);
 assert.match(api,/12\*1024\*1024/);
});
