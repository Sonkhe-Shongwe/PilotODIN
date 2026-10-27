const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const ts=require('typescript');
const vm=require('node:vm');

const root=path.join(__dirname,'../src');
function loadTS(name){
 const source=fs.readFileSync(path.join(root,name),'utf8');
 const result=ts.transpileModule(source,{compilerOptions:{
  target:ts.ScriptTarget.ES2021,module:ts.ModuleKind.CommonJS
 },reportDiagnostics:true,fileName:name});
 assert.equal(result.diagnostics?.length,0);
 const module={exports:{}};
 vm.runInNewContext(result.outputText,{exports:module.exports,module},{filename:name});
 return module.exports;
}
const {savedReportPreviewDocument,MAX_SAVED_HTML_PREVIEW_CHARS}=loadTS('reportSavedPreview.ts');
const {ReportReadGate,ReportComposerGate}=loadTS('reportComposerGate.ts');
const ui=fs.readFileSync(path.join(root,'ReportWorkspace.tsx'),'utf8');
const css=fs.readFileSync(path.join(root,'report-workspace.css'),'utf8');
const doc='<!doctype html><html lang="en"><head><meta charset="utf-8"><style>body{color:navy}</style></head><body><p>café 漢字 ₹ 📈 &lt;script&gt;</p></body></html>';

test('Saved preview retains exact escaped evidence and inserts restrictive CSP',()=>{
 const prepared=savedReportPreviewDocument(doc);
 assert.match(prepared,/Content-Security-Policy/);
 assert.match(prepared,/default-src 'none'/);
 assert.match(prepared,/script-src 'none'/);
 assert.match(prepared,/connect-src 'none'/);
 assert.match(prepared,/style-src 'unsafe-inline'/);
 assert.match(prepared,/base-uri 'none'/);
 assert.match(prepared,/form-action 'none'/);
 assert.match(prepared,/café 漢字 ₹ 📈 &lt;script&gt;/);
 assert.equal(prepared.split('Content-Security-Policy').length-1,1);
});

test('Preview refuses non-report and incomplete or excessively large HTML',()=>{
 for(const input of ('','<html><head></head><body></body></html>',
   '<!doctype html><body>no head</body></html>',
   '<!doctype html><html><head></head>', 'x'.repeat(MAX_SAVED_HTML_PREVIEW_CHARS+1))){
  assert.throws(()=>savedReportPreviewDocument(input),/preview|report/i);
 }
});

test('Preview refuses active HTML content even though frame is sandboxed',()=>{
 for(const part of ('<script>alert(1)</script>','<iframe src="https://example.com"></iframe>',
   '<object data="file:///secret"></object>', '<link rel="stylesheet" href="https://example.com/x.css">',
   '<base href="https://example.com/">', '<meta http-equiv="refresh" content="0;url=https://x.invalid">',
   '<form action="https://x.invalid"></form>')){
  const content=doc.replace('</body>',part+'</body>');
  assert.throws(()=>savedReportPreviewDocument(content),/unsupported active HTML/);
 }
});

test('Two saved preview requests cannot swap displayed revision when resolved backwards',()=>{
 const guard=new ReportReadGate(),composer=new ReportComposerGate();
 const view=composer.currentView();
 const older=guard.beginPreview();
 const newer=guard.beginPreview();
 assert.equal(guard.isCurrentPreview(older),false);
 assert.equal(guard.isCurrentPreview(newer),true);
 let visible='Revision 2';
 if(composer.isCurrentView(view)&&guard.isCurrentPreview(older))visible='Revision 1';
 assert.equal(visible,'Revision 2');
 guard.invalidatePreview();
 assert.equal(guard.isCurrentPreview(newer),false);
});

test('Project and saved revision navigation prevent a pending preview from appearing',()=>{
 const guard=new ReportReadGate(),composer=new ReportComposerGate();
 const view=composer.currentView(),preview=guard.beginPreview();
 composer.navigate();guard.invalidatePreview();
 assert.equal(composer.isCurrentView(view),false);
 assert.equal(guard.isCurrentPreview(preview),false);
 const current=guard.beginPreview();
 guard.invalidateAll();
 assert.equal(guard.isCurrentPreview(current),false);
});

test('Preview lifecycle uses authenticated immutable HTML, never native Save As',()=>{
 assert.match(ui,/const ticket=readGuard\.current\.beginPreview\(\)/);
 assert.match(ui,/readGuard\.current\.isCurrentPreview\(ticket\)/);
 assert.match(ui,/downloadReportFile/);
 assert.match(ui,/export\/html\?revision=/);
 assert.match(ui,/setSavedPreview\(\{id,revision:rev,html:savedReportPreviewDocument\(raw\)\}\)/);
 assert.match(ui,/onClick=\{\(\)=>void previewSavedRevision\(\)\}/);
 assert.match(ui,/readGuard\.current\.invalidatePreview\(\)/);
 assert.match(ui,/srcDoc=\{savedPreview\.html\}/);
 assert.match(ui,/sandbox=""/);
 assert.match(ui,/referrerPolicy="no-referrer"/);
 assert.match(ui,/No download was created/);
 assert.match(ui,/Unsaved draft changes are not included/);
 assert.match(css,/\.pd-report-saved-preview-frame/);
});
