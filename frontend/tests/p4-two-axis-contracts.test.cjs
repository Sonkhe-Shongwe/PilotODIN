const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const root=path.resolve(__dirname,'../..');
const read=p=>fs.readFileSync(path.join(root,p),'utf8');

test('P4 assessment separates observed technical evidence from unverified user decision context',()=>{
 const src=read('backend/target_opportunities.py');
 assert.match(src,/def _assessment_axes\(candidate: dict\)/);
 assert.match(src,/observed_aggregates_and_structural_screening/);
 assert.match(src,/user_described_unverified/);
 assert.match(src,/no_user_description/);
 assert.match(src,/review_required": True/);
 assert.match(src,/safe_to_train_automatically": False/);
 assert.doesNotMatch(src,/cross_val_score\(|run_training\(|\.fit\(/);
});

test('P4 candidates receive descriptive axes but technical screening and ranking remain',()=>{
 const src=read('backend/target_opportunities.py');
 assert.match(src,/candidate\["assessment_axes"\] = _assessment_axes\(candidate\)/);
 assert.match(src,/candidate\["risk_review"\] = target_timing_review\.review_prediction_context\(/);
 assert.match(src,/if candidate\["technical_status"\] == "reviewable"/);
 assert.match(src,/suggestions.sort\(/);
 assert.match(src,/abstained": not bool\(top\)/);
});

test('P4 frontend displays two independent evidence states without authorizing training',()=>{
 const src=read('frontend/src/TargetOpportunities.tsx');
 assert.match(src,/Two-axis prediction opportunity assessment/);
 assert.match(src,/Technical readiness:/);
 assert.match(src,/Decision relevance:/);
 assert.match(src,/Two separate evidence states, not model accuracy or a business-value score/);
 assert.match(src,/onClick=\{\(\)=>onChooseTarget\(item\.column\)\}/);
 assert.doesNotMatch(src,/startTrain\(|autoSelectTarget\(|model\.fit\(/);
});
