const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const read=name=>fs.readFileSync(path.join(__dirname,'../src',name),'utf8');
const component=read('FeatureSensitivity.tsx');
const evals=read('EvaluationDetails.tsx');
const api=read('api.ts');
const app=read('App.tsx');
const css=read('studio.css');

test('Evaluate only displays post-selection feature sensitivity with bounded coverage',()=>{
 assert.match(evals,/feature_sensitivity\?:FeatureSensitivityEvidence/);
 assert.match(evals,/<FeatureSensitivity data=\{r\.feature_sensitivity\}\/>/);
 assert.match(component,/Which inputs influence this model's score\?/);
 assert.match(component,/Post-selection · descriptive/);
 assert.match(component,/features_evaluated\?\?0/);
 assert.match(component,/total_predictors\?\?0/);
 assert.match(component,/sample_rows\?\?0/);
 assert.match(component,/repeats\?\?0/);
 assert.match(component,/scores\.map\(row=>/);
 assert.match(component,/Untested predictors|untested predictors/i);
});

test('Sensitivities never claim causal or per-record explanation',()=>{
 assert.match(component,/NOT causal effects, coefficients, or explanations of any single prediction/);
 assert.match(component,/The same test result must never be used to choose, retrain or tune the model/);
 assert.match(component,/This legacy evaluation has no post-selection sensitivity analysis/);
 assert.match(component,/Existing held-out metrics remain unchanged/);
 assert.match(css,/\.po-ml-sensitivity-table\{max-height:325px/);
});

test('Prepare exposes a backend-sourced 8 GB resource limit without hardcoded frontend estimate',()=>{
 assert.match(api,/resource_plan\?:\{labelled_rows:number/);
 assert.match(api,/estimated_dense_training_mb:number/);
 assert.match(app,/Local training resource preflight/);
 assert.match(app,/prep\.resource_plan\.within_local_budget/);
 assert.match(app,/prep\.resource_plan\.row_limit/);
 assert.match(app,/prep\.resource_plan\.estimated_dense_mb_limit/);
 assert.match(app,/before manual exclusions|prep\.resource_plan_scope/);
 assert.match(app,/the source project remains unchanged|separately reviewed smaller dataset/i);
 assert.match(css,/\.po-ml-resource-plan/);
});
