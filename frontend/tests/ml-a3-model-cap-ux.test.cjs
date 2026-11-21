const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const read=name=>fs.readFileSync(path.join(__dirname,'../src',name),'utf8');
const app=read('App.tsx');
const types=read('api.ts');

test('model training limits originate on the backend and are scoped to selected models',()=>{
 assert.match(types,/model_family_row_limits:Record<string,number>/);
 assert.match(types,/selected_model_row_limit:number/);
 assert.match(app,/const selectedResourcePlan=prep\?\.resource_plan/);
 assert.match(app,/const modelRowLimit=selectedResourcePlan\?Math\.min\(selectedResourcePlan\.row_limit,\.\.\.models\.map/);
 assert.match(app,/selectedResourcePlan\.model_family_row_limits\[key\]/);
 assert.match(app,/const modelBudgetExceeded=/);
 assert.match(app,/Selected-model budget: at most/);
 assert.match(app,/Kernel SVM\/SVR training has a stricter row limit/);
 assert.match(app,/K-nearest neighbours training has a stricter row limit/);
});

test('blocked model-family budget cannot be bypassed through the Train button',()=>{
 assert.match(app,/disabled=\{!models\.length\|\|modelBudgetExceeded\|\|/);
 assert.match(app,/Remove the expensive model or use a reviewed smaller dataset/);
 assert.match(app,/server checks dense memory separately/);
 assert.match(app,/acknowledge_feature_risks:acknowledgeFeatureRisks/);
});
