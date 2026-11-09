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

test('P4-07 decision usefulness reviews observed identifier repetition without training',()=>{
 const backend=read('backend/target_opportunities.py');
 const panel=read('frontend/src/TargetOpportunities.tsx');
 assert.match(backend,/def _repeated_identifier_evidence\(frame: pd\.DataFrame\)/);
 assert.match(backend,/MAX_ENTITY_ROWS = 30000/);
 assert.match(backend,/MAX_ENTITY_COLUMNS = 8/);
 assert.match(backend,/def _decision_utility_review\(candidate: dict, entity_evidence: dict\)/);
 assert.match(backend,/candidate\["decision_utility"\] = _decision_utility_review/);
 assert.match(backend,/"measured_decision_benefit": False/);
 assert.match(backend,/"verified_group_independence": False/);
 assert.match(backend,/"training_authorised": False/);
 assert.doesNotMatch(backend,/run_training\(|cross_val_score\(|\.fit\(/);
 assert.match(panel,/function DecisionUtilityEvidence/);
 assert.match(panel,/Decision usefulness: not established/);
 assert.match(panel,/Comparison with the existing process/);
 assert.match(panel,/Record-dependence check/);
 assert.match(panel,/item\.decision_utility&&<DecisionUtilityEvidence review=\{item\.decision_utility\}\/>/);
 assert.equal((panel.match(/item\.decision_utility&&<DecisionUtilityEvidence/g)||[]).length,2);
 assert.doesNotMatch(panel,/startTrain\(|autoSelectTarget\(|run_training\(/);
 const tests=read('tests/test_p4_review_queue.py');
 for(const name of ['test_p4_07_repeated_identifier_values_are_observed_not_proven_leakage',
 'test_p4_07_unique_identifiers_do_not_prove_independence',
 'test_p4_07_bounded_scanning_discloses_incomplete_evidence',
 'test_p4_07_no_target_abstention_and_rare_class_blockers_stay_intact'])
 assert.ok(tests.includes(name));
});

test('P4-08 explicit defer, decline, abstain and selected-target evidence stay local',()=>{
 const panel=read('frontend/src/TargetOpportunities.tsx');
 const app=read('frontend/src/App.tsx');
 assert.match(panel,/type ReviewDisposition='deferred'\|'declined'/);
 assert.match(panel,/const \[reviewDispositions,setReviewDispositions\]=useState/);
 assert.match(panel,/if\(selectedTarget===column\)onClearTarget\(\)/);
 assert.match(panel,/if\(selectedTarget\)onClearTarget\(\)/);
 assert.match(panel,/No prediction objective right now/);
 assert.match(panel,/Deferred.*Declined|Deferred':'Declined/);
 assert.match(panel,/Defer target in this review/);
 assert.match(panel,/Decline target in this review/);
 assert.match(panel,/Selected target suitability checkpoint/);
 assert.match(panel,/This manually selected column is not in the/);
 assert.match(panel,/Clear selected target and preparation/);
 assert.match(panel,/Not saved or excluded from manual selection/);
 assert.match(app,/onClearTarget=\{\(\)=>\{if\(!target\)return;/);
 assert.match(app,/setTarget\(''\);setPrep\(null\);setExperiment\(null\);setConfirmSplit\(false\);setError\(''\)/);
 assert.doesNotMatch(panel,/post<|run_training\(|startTrain\(|localStorage\.setItem|sessionStorage\.setItem/);
 assert.match(app,/if\(!project\|\|!prep\|\|prep\.target!==target\)return/);
});

test('P4-12 manual target inspection is current-version, read-only and unranked',()=>{
 const main=read('backend/main.py');
 const backend=read('backend/target_opportunities.py');
 const panel=read('frontend/src/TargetOpportunities.tsx');
 const tests=read('tests/test_p4_manual_target_inspection.py');
 const browser=read('frontend/e2e/p4-real-http-review-queue.spec.ts');
 assert.match(main,/@app\.get\("\/api\/projects\/\{project_id\}\/target-opportunities\/inspect"\)/);
 assert.match(main,/def inspect_manual_target_opportunity\(/);
 assert.match(main,/_local_request\(request\)/);
 assert.match(main,/if version != expected_version:/);
 assert.match(backend,/def inspect_manual_target\(/);
 assert.match(backend,/single_manual_column_not_ranked_or_approved/);
 assert.match(backend,/No supported outcome-name clue was identified/);
 assert.match(backend,/"training_authorised": False/);
 assert.doesNotMatch(backend,/\.fit\(|run_training\(|cross_val_score\(/);
 assert.match(panel,/needsManualInspection/);
 assert.match(panel,/get<ManualTargetInspection>\(path\)/);
 assert.match(panel,/encodeURIComponent\(selectedTarget\)/);
 assert.match(panel,/manualInspection\.project_id===projectId/);
 assert.match(panel,/manualInspection\.version===version/);
 assert.match(panel,/On-demand selected target evidence/);
 assert.match(panel,/Could not verify this selected column/);
 assert.doesNotMatch(panel,/startTrain\(|post<|run_training\(|autoSelectTarget\(/);
 assert.match(tests,/test_p4_12_selected_column_outside_caps_is_screened_without_reordering/);
 assert.match(tests,/test_p4_12_local_version_project_and_invalid_column_rejection/);
 assert.match(browser,/P4-12 real HTTP: out-of-cap manual target inspection and no writes/);
});

test('P4-11 manually selected known blockers remain visible without granting training',()=>{
 const panel=read('frontend/src/TargetOpportunities.tsx');
 const backend=read('backend/target_opportunities.py');
 const review=read('tests/test_p4_review_queue.py');
 const browser=read('frontend/e2e/p4-real-http-review-queue.spec.ts');
 assert.match(panel,/\.\.\.data\.blocked_examples/);
 assert.match(panel,/selectedCandidate\.technical_status==='blocked'/);
 assert.match(panel,/Selected target structural blockers/);
 assert.match(panel,/selectedCandidate\.blockers\.map/);
 assert.match(panel,/not recommended or approved for training/);
 assert.match(panel,/absence from it is not approval/);
 assert.match(panel,/data\.blocked_count>data\.blocked_examples\.length/);
 assert.match(backend,/MAX_BLOCKED_EXAMPLES = 5/);
 assert.match(review,/test_p4_11_bounded_blocked_examples_disclose_omissions/);
 assert.match(browser,/P4-11 real HTTP: manual blocked target shows exact structural reasons/);
 assert.doesNotMatch(panel,/startTrain\(|post<|run_training\(|autoSelectTarget\(/);
});

test('P4-09 phase-exit negative matrix has API and isolated project-switch evidence',()=>{
 const cases=read('tests/test_p4_phase_exit_matrix.py');
 const browser=read('frontend/e2e/p4-real-http-review-queue.spec.ts');
 const workflow=read('.github/workflows/p4-target-ranking.yml');
 for(const kind of ['classification','regression','rare','insufficient','no_named_target'])
  assert.ok(cases.includes('"'+kind+'"'));
 assert.match(cases,/test_p4_09_project_and_quality_version_isolation_and_stale_rejection/);
 assert.match(cases,/status_code == 409/);
 assert.match(cases,/storage\.recent_experiments\(a\) == \[\]/);
 assert.match(browser,/P4-09 real HTTP: project switch resets target review state/);
 assert.match(browser,/expected_version=1/);
 assert.match(workflow,/tests\/test_p4_phase_exit_matrix\.py/);
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
