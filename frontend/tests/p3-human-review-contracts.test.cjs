'use strict';
const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const ts=require('typescript');
const root=path.resolve(__dirname,'../..');
const read=p=>fs.readFileSync(path.join(root,p),'utf8');

test('P3-03 owner review never mutates the dataset or authorises ML',()=>{
 const storage=read('backend/storage.py');
 const endpoint=read('backend/main.py');
 const review=read('backend/semantic_review.py');
 assert.match(storage,/CREATE TABLE IF NOT EXISTS semantic_human_reviews/);
 assert.match(storage,/CREATE TABLE IF NOT EXISTS semantic_human_review_events/);
 assert.match(storage,/PRIMARY KEY \(project_id, quality_version, column_name, hypothesis_role\)/);
 assert.match(storage,/BEGIN IMMEDIATE/);
 assert.match(storage,/SELECT current_version FROM quality_state/);
 assert.match(storage,/current_revision != expected_revision/);
 assert.match(endpoint,/@app\.get\("\/api\/projects\/\{project_id\}\/semantic-reviews"\)/);
 assert.match(endpoint,/@app\.post\("\/api\/projects\/\{project_id\}\/semantic-reviews"\)/);
 assert.match(endpoint,/storage\.save_human_review/);
 assert.match(endpoint,/_local_request\(request\)/);
 assert.match(endpoint,/selected_candidate/);
 assert.match(review,/def fingerprint\(/);
 assert.doesNotMatch(review,/train_background|select_target|launch_bundled_ai/);
 const block=endpoint.split('@app.post("/api/projects/{project_id}/semantic-reviews")')[1]
  ?.split('@app.get("/api/projects/{project_id}/columns/detail")')[0];
 assert.ok(block);
 assert.doesNotMatch(block,/quality\.commit|train_background|set_target|launch_bundled_ai/);
});

test('P3-03 review UI requires owner click, revision lock and protects unsaved changes',()=>{
 const panel=read('frontend/src/SemanticReviewPanel.tsx');
 const overview=read('frontend/src/SemanticOverview.tsx');
 const result=ts.transpileModule(panel,{reportDiagnostics:true,
  compilerOptions:{jsx:ts.JsxEmit.ReactJSX, target:ts.ScriptTarget.ES2022,
   module:ts.ModuleKind.ESNext}});
 assert.equal((result.diagnostics||[]).filter(x=>x.category===ts.DiagnosticCategory.Error).length,0);
 assert.match(panel,/Save owner review/);
 assert.match(panel,/Discard review edits/);
 assert.match(panel,/disabled=\{!valid\}/);
 assert.match(panel,/expected_version:version/);
 assert.match(panel,/expected_revision:chosen\.revision/);
 assert.match(panel,/onUnsavedChange\?\.\(dirty\)/);
 assert.match(panel,/owner_attestation_not_independently_verified/);
 assert.match(panel,/reassessment_required/);
 assert.match(panel,/disabled=\{busy\|\|dirty\}/);
 assert.doesNotMatch(panel,/train_background|setTarget\(|selectTarget\(/);
 assert.match(overview,/descriptionDirty\|\|humanReviewDirty/);
 assert.match(overview,/onUnsavedChange=\{setDescriptionDirty\}/);
 assert.match(overview,/onUnsavedChange=\{setHumanReviewDirty\}/);
});
