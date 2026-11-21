const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const root=path.resolve(__dirname,'../..');
const read=p=>fs.readFileSync(path.join(root,p),'utf8');

test('P4 timing review uses bounded deterministic read-only clues, never approves training',()=>{
 const src=read('backend/target_timing_review.py');
 assert.match(src,/def review_prediction_context\(/);
 assert.match(src,/MAX_SCANNED_HEADERS = 100/);
 assert.match(src,/MAX_HEADER_FLAGS = 5/);
 assert.match(src,/safe_to_train_automatically": False/);
 assert.match(src,/unverified_user_text_and_header_clues/);
 assert.doesNotMatch(src,/\.fit\(|run_training\(|new_experiment\(|sqlite3|requests\.|open\(/);
});

test('Existing bounded recommender adds review metadata without altering technical blockers',()=>{
 const src=read('backend/target_opportunities.py');
 assert.match(src,/candidate\["risk_review"\] = target_timing_review\.review_prediction_context\(/);
 assert.match(src,/frame\.columns, name, candidate\["user_context"\]/);
 assert.match(src,/technical_status/);
 assert.match(src,/safe_to_train_automatically": False/);
});

test('Frontend renders unresolved timing and label provenance without training or extra endpoints',()=>{
 const src=read('frontend/src/TargetOpportunities.tsx');
 assert.match(src,/Prediction timing and label provenance: review required/);
 assert.match(src,/item\.risk_review\.questions\.map/);
 assert.match(src,/item\.risk_review\.header_flags\.map/);
 assert.match(src,/possible_after_event_wording/);
 assert.match(src,/possibly_unconfirmed_or_proxy/);
 assert.doesNotMatch(src,/startTrain\(|approveTarget\(|post<|model\.fit\(/);
});
