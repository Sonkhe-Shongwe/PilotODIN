const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const root=path.resolve(__dirname,'../..');
const read=p=>fs.readFileSync(path.join(root,p),'utf8');

test('P4 context persistence is additive project/version scoped and never changes experiments',()=>{
 const sto=read('backend/storage.py');
 assert.match(sto,/CREATE TABLE IF NOT EXISTS target_business_context/);
 assert.match(sto,/PRIMARY KEY \(project_id, quality_version, target_column\)/);
 assert.match(sto,/def save_target_context\(/);
 assert.match(sto,/ON CONFLICT\(project_id,quality_version,target_column\)/);
 assert.match(sto,/def target_contexts\(/);
 assert.doesNotMatch(sto.slice(sto.indexOf('# Explicit USER-PROVIDED'),sto.indexOf('def new_experiment(pid, config):')),/UPDATE experiments|INSERT INTO experiments|DELETE FROM projects/);
});

test('P4 local API guards user context save by project, exact version and matching column',()=>{
 const src=read('backend/main.py');
 const route=src.split('@app.post("/api/projects/{project_id}/target-business-context")')[1]?.split('@app.get("/api/projects/{project_id}/semantics")')[0];
 assert.ok(route,'Expected user-origin POST endpoint');
 assert.match(route,/_local_request\(request\)/);
 assert.match(route,/project_or_404\(project_id\)/);
 assert.match(route,/quality\.current_data\(project_id\)/);
 assert.match(route,/version != body\.expected_version/);
 assert.match(route,/body\.target_column not in frame\.columns/);
 assert.match(route,/storage\.save_target_context\(/);
 assert.doesNotMatch(route,/train_background|new_experiment|select_model/);
});

test('P4 UI submits descriptions only on actual user action, never authorizes fitting',()=>{
 const screen=read('frontend/src/TargetOpportunities.tsx');
 const editor=read('frontend/src/TargetContextEditor.tsx');
 assert.match(screen,/TargetContextEditor/);
 assert.match(screen,/onSaved=\{\(\)=>setRefresh\(n=>n\+1\)\}/);
 assert.match(editor,/onClick=\{\(\)=>void submit\(\)\}/);
 assert.match(editor,/await post<UserTargetContext>/);
 assert.match(editor,/expected_version:version,target_column:column/);
 for(const field of ['outcome_definition','decision_action','prediction_moment','label_source'])
  assert.match(editor,new RegExp(field));
 assert.match(editor,/Not independently verified/);
 assert.doesNotMatch(editor,/startTrain|selectTarget|model\.fit|onChooseTarget/);
});

test('Context is not technical approval; structual blockers and abstention persist',()=>{
 const core=read('backend/target_opportunities.py');
 assert.match(core,/user_described_not_independently_verified/);
 assert.match(core,/technical_status/);
 assert.match(core,/user_contexts = user_contexts or \{\}/);
 assert.match(core,/if name in user_contexts/);
 assert.match(core,/business_relevance"\] = "user_described_unverified"/);
 assert.match(core,/safe_to_train_automatically": False/);
 assert.match(core,/abstained": not bool\(top\)/);
 assert.doesNotMatch(core,/cross_val_score\(|\.fit\(/);
});
