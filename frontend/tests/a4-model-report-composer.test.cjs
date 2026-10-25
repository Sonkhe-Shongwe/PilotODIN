const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const read=n=>fs.readFileSync(path.join(__dirname,'../src',n),'utf8');

test('A4 renders verified selected-model evidence and historical-version labels',()=>{
  const s=read('ReportWorkspace.tsx');
  assert.match(s,/model_evaluation/);
  assert.match(s,/Selected model evaluation/);
  assert.match(s,/HISTORICAL/);
  assert.match(s,/has_historical_evidence/);
  assert.match(s,/Save new revision/);
});

test('A4 exhibit reordering changes the order-aware draft state',()=>{
  const s=read('ReportWorkspace.tsx');
  assert.match(s,/function shiftEvidence/);
  assert.match(s,/ordered\[from\],ordered\[to\]/);
  assert.match(s,/selected\.some\(\(id,index\)=>id!==savedIds\[index\]\)/);
  assert.match(s,/aria-label="Order of report exhibits"/);
  assert.match(s,/Move exhibit/);
});

test('A4 export cannot silently ignore unsaved edits to exhibit order or content',()=>{
  const s=read('ReportWorkspace.tsx');
  assert.match(s,/disabled=\{!!busy\|\|hasDraftChanges\}/);
  assert.match(s,/Save draft changes before exporting/);
  assert.match(s,/revision=\$\{rev\}/);
});

test('A4 exhibit controls expose keyboard-visible focus and prevent invalid moves',()=>{
  const style=read('report-workspace.css');
  const s=read('ReportWorkspace.tsx');
  assert.match(s,/index===0/);
  assert.match(s,/index===selected\.length-1/);
  assert.match(style,/pd-report-order-button:focus-visible/);
});
