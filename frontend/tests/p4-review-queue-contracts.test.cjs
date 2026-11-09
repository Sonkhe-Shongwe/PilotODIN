'use strict';
const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const ts=require('../node_modules/typescript');
const root=path.resolve(__dirname,'../..');
const read=p=>fs.readFileSync(path.join(root,p),'utf8');

test('P4-05 explainable review queue does not validate business value or trigger ML',()=>{
 const source=read('backend/target_opportunities.py');
 assert.match(source,/def _review_priority\(candidate: dict, position: int, total: int\)/);
 assert.match(source,/MAX_OTHER_REVIEWABLE = 12/);
 assert.match(source,/"human_review_queue_not_business_value_ranking"/);
 assert.match(source,/"business_value": "not_established"/);
 assert.match(source,/"target_safety": "not_established"/);
 assert.match(source,/"training_authorised": False/);
 assert.match(source,/"model_performance_measured": False/);
 assert.match(source,/"automatic_target_selection": False/);
 assert.match(source,/"other_reviewable": other/);
 assert.match(source,/len\(suggestions\) - MAX_SUGGESTIONS - MAX_OTHER_REVIEWABLE/);
 assert.doesNotMatch(source,/\.fit\(|run_training\(|cross_val_score\(|autoselect_target\(/);
});

test('P4-05 UI explains review order and exposes other targets by explicit click only',()=>{
 const panel=read('frontend/src/TargetOpportunities.tsx');
 const app=read('frontend/src/App.tsx');
 const compiled=ts.transpileModule(panel,{reportDiagnostics:true,compilerOptions:{
  target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.ESNext,jsx:ts.JsxEmit.ReactJSX
 }});
 assert.equal(compiled.diagnostics?.filter(x=>x.category===ts.DiagnosticCategory.Error).length||0,0);
 assert.match(panel,/Review order, not an estimated business-value ranking/);
 assert.match(panel,/Evidence needed before selecting this target/);
 assert.match(panel,/Review position/);
 assert.match(panel,/More structurally reviewable targets/);
 assert.match(panel,/omitted_reviewable_count/);
 assert.match(panel,/Review this alternative target/);
 assert.match(panel,/onClick=\{\(\)=>onChooseTarget\(item\.column\)\}/);
 assert.match(panel,/The existing manual target chooser remains available/);
 assert.match(app,/setTarget\(column\);setPrep\(null\)/);
 assert.doesNotMatch(panel,/startTrain\(|post<|run_training\(|autoSelectTarget\(/);
});

test('P4-06 alternative targets expose the same version-scoped human review path',()=>{
 const panel=read('frontend/src/TargetOpportunities.tsx');
 const alternative=panel.split('data.other_reviewable!.map(item=>')[1]?.split('{(data.omitted_reviewable_count')[0];
 assert.ok(alternative,'Expected bounded alternative review section');
 assert.match(alternative,/Review evidence for alternative/);
 assert.match(alternative,/Inspect evidence and unresolved risks/);
 assert.match(alternative,/review_priority\?\.required_checks/);
 assert.match(alternative,/item\.risk_review\.header_flags/);
 assert.match(alternative,/Business value and target safety remain unverified/);
 assert.match(alternative,/TargetContextEditor projectId=\{projectId\} version=\{version\} column=\{item\.column\}/);
 assert.match(alternative,/existing=\{item\.user_context\?\?null\} onSaved=\{\(\)=>setRefresh\(n=>n\+1\)\}/);
 assert.match(alternative,/onClick=\{\(\)=>onChooseTarget\(item\.column\)\}/);
 assert.doesNotMatch(alternative,/startTrain\(|post<|run_training\(|autoSelectTarget\(/);
});

test('P4-05 tests cover disclosed ordering, overflow, no target, missing labels',()=>{
 const testSource=read('tests/test_p4_review_queue.py');
 for(const testName of [
  'test_review_order_is_explained_but_business_value_is_not_claimed',
  'test_missing_decision_is_an_explicit_review_step_not_a_low_value_verdict',
  'test_missing_labels_and_unverified_header_clues_are_visible_without_unsafe_claims',
  'test_additional_options_visible_without_selection_or_training',
  'test_large_eligible_set_is_bounded_and_manual_dropdown_remains_the_fallback',
  'test_all_blocked_or_no_named_outcomes_abstain_without_queue_or_approval',
 ])assert.ok(testSource.includes(testName),'Missing focused regression: '+testName);
});
