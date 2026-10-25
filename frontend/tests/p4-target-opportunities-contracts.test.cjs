const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const root=path.resolve(__dirname,'../..');
const read=p=>fs.readFileSync(path.join(root,p),'utf8');

test('P4 is read-only deterministic screening, not an AutoML run or automatic target selection',()=>{
 const src=read('backend/target_opportunities.py');
 assert.match(src,/MAX_SUGGESTIONS = 3/);
 assert.match(src,/def recommend\(frame: pd\.DataFrame, version: int\)/);
 assert.match(src,/business_relevance": "unverified"/);
 assert.match(src,/safe_to_train_automatically": False/);
 assert.match(src,/technical_status": "reviewable" if not blockers else "blocked"/);
 assert.match(src,/No model trained or business value scored/);
 assert.match(src,/abstained": not bool\(top\)/);
 assert.doesNotMatch(src,/run_training\(|cross_val_score\(|\.fit\(|joblib\.dump|new_experiment\(/);
});

test('P4 GET endpoint is version-bound, guarded against foreign origin, and cannot mutate models',()=>{
 const main=read('backend/main.py');
 const route=main.split('@app.get("/api/projects/{project_id}/target-opportunities")')[1]?.split('@app.get("/api/projects/{project_id}/semantics")')[0];
 assert.ok(route,'Expected read-only target-opportunity endpoint');
 assert.match(route,/request: Request/);
 assert.match(route,/_local_request\(request\)/);
 assert.match(route,/project_or_404\(project_id\)/);
 assert.match(route,/quality\.current_data\(project_id\)/);
 assert.match(route,/version != expected_version/);
 assert.match(route,/status_code=409/);
 assert.match(route,/target_opportunities\.recommend\(frame, version\)/);
 assert.doesNotMatch(route,/new_experiment|train_background|select_model|storage\.mark\(/);
});

test('P4 recommendations require a separate explicit button press before the existing target choice',()=>{
 const src=read('frontend/src/TargetOpportunities.tsx');
 const app=read('frontend/src/App.tsx');
 assert.match(src,/expected_version=\$\{version\}/);
 assert.match(src,/if\(result\.version!==version\)/);
 assert.match(src,/onClick=\{\(\)=>onChooseTarget\(item\.column\)\}/);
 assert.match(src,/Business relevance: unknown until you confirm/i);
 assert.match(src,/You decide the target/);
 assert.match(app,/import \{TargetOpportunities\} from '\.\/TargetOpportunities'/);
 assert.match(app,/<TargetOpportunities key=\{project\.id\+'\-'\+qualityVersion\}/);
 assert.match(app,/onChooseTarget=\{column=>\{if\(!profile\.columns\.some\(c=>c\.name===column\)\)return;setTarget\(column\)/);
 assert.doesNotMatch(src,/setTarget\(|startTrain\(|post<|onChooseTarget\(item\.column\);\s*\}/);
});

test('P4 synthetic backend suite covers abstention, sensitive flags, label support, resource limit, origin',()=>{
 const src=read('tests/test_p4_target_opportunities.py');
 for(const n of [
  'test_insurance_shortlist_is_explicit_review_only',
  'test_rare_class_and_insufficient_label_support_are_blocked',
  'test_ambiguous_no_outcome_abstains_without_arbitrary_numeric_target',
  'test_value_regression_cannot_be_mistaken_for_predictive_accuracy',
  'test_text_identifiers_empty_and_constant_labels_never_get_reviewable_shortlist',
  'test_missing_labels_are_aggregated_without_personal_values',
  'test_record_limit_blocks_candidate_without_training',
  'test_deterministic_bounded_shortlist',
  'test_project_version_and_origin_guards_are_enforced',
 ])assert.ok(src.includes(n),'Missing regression: '+n);
});
