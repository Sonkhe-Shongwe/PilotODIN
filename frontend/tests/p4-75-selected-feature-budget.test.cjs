const{test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const ts=require('typescript');
// Execute the exact TypeScript helper, stripped through the locked TS compiler.
const source=fs.readFileSync(path.join(__dirname,'../src/selectedFeatureBudget.ts'),'utf8');
const compiled=ts.transpileModule(source,{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2021}}).outputText;
const compiledModule={exports:{}};
new Function('module','exports',compiled)(compiledModule,compiledModule.exports);
const{selectedFeatureBudget}=compiledModule.exports;
const budget={labelled_rows:80,estimated_dense_mb_limit:256};
const fields=[
  {column:'TransactionID',kind:'categorical',distinct:80,default_included:true,missing:1},
  {column:'event_type',kind:'categorical',distinct:2,default_included:true,missing:1},
  {column:'amount',kind:'numeric',distinct:80,default_included:true,missing:1},
  {column:'empty',kind:'categorical',distinct:0,default_included:false,missing:80},
];
test('candidate budget uses capped categories and excludes truly unusable features',()=>{
  const x=selectedFeatureBudget(fields,budget,[],'random','');
  assert.equal(x.includedFeatures,3);
  assert.equal(x.estimatedEncodedColumns,28);
  assert.deepEqual([...x.encodedColumnsByField],[['TransactionID',25],['event_type',2],['amount',1]]);
  assert.equal(x.denseLimitExceeded,false);
});
test('manual and suggested exclusions update selected encoded matrix width',()=>{
  assert.equal(selectedFeatureBudget(fields,budget,['event_type'],'random','').estimatedEncodedColumns,26);
  const x=selectedFeatureBudget(fields,budget,['event_type','TransactionID'],'random','');
  assert.equal(x.estimatedEncodedColumns,1);
  assert.equal(x.includedFeatures,1);
  assert.deepEqual([...x.encodedColumnsByField],[['amount',1]]);
});
test('group/time split columns are removed, random leaves them included',()=>{
  const grouped=selectedFeatureBudget(fields,budget,[],'group','event_type');
  assert.equal(grouped.estimatedEncodedColumns,26);
  assert.equal(grouped.encodedColumnsByField.has('event_type'),false);
  assert.equal(selectedFeatureBudget(fields,budget,[],'time','amount').estimatedEncodedColumns,27);
  assert.equal(selectedFeatureBudget(fields,budget,[],'random','amount').estimatedEncodedColumns,28);
});
test('missing-marker width counts only affected categorical predictors within the cap',()=>{
  const complete={column:'complete',kind:'categorical',distinct:4,default_included:true,missing:0};
  const x=selectedFeatureBudget([...fields,complete],budget,[],'random','','constant');
  assert.deepEqual([...x.encodedColumnsByField],[['TransactionID',25],['event_type',3],['amount',1],['complete',4]]);
  assert.equal(x.estimatedEncodedColumns,33);
});
test('large valid candidates exceed memory threshold, exclusions reopen advisory gate',()=>{
  const wide=Array.from({length:46},(_,i)=>({column:'cat'+i,kind:'categorical',distinct:25,default_included:true,missing:0}));
  const b={labelled_rows:30000,estimated_dense_mb_limit:256};
  assert.equal(selectedFeatureBudget(wide,b,[],'random','').denseLimitExceeded,true);
  assert.equal(selectedFeatureBudget(wide,b,['cat0','cat1','cat2','cat3','cat4'],'random','').denseLimitExceeded,false);
});
test('no included predictors fails closed',()=>{
  const x=selectedFeatureBudget(fields,budget,['TransactionID','event_type','amount'],'random','');
  assert.equal(x.includedFeatures,0);
  assert.equal(x.estimatedEncodedColumns,0);
  assert.equal(x.denseLimitExceeded,true);
});
test('malformed and unsafe estimates fail closed',()=>{
  assert.equal(selectedFeatureBudget([{column:'x',kind:'categorical',distinct:Infinity,default_included:true,missing:0}],budget,[],'random','').denseLimitExceeded,true);
  assert.equal(selectedFeatureBudget(fields,{labelled_rows:Number.MAX_SAFE_INTEGER,estimated_dense_mb_limit:256},[],'random','').denseLimitExceeded,true);
  assert.equal(selectedFeatureBudget(fields,{labelled_rows:80,estimated_dense_mb_limit:0},[],'random','').denseLimitExceeded,true);
});
