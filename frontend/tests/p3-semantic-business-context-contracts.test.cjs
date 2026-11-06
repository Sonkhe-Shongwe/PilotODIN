const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const root=path.resolve(__dirname,'../..');
const read=p=>fs.readFileSync(path.join(root,p),'utf8');

test('P3 saved metadata uses version-locked, separate, explicitly unverified storage',()=>{
 const s=read('backend/storage.py');
 assert.match(s,/CREATE TABLE IF NOT EXISTS semantic_business_context/);
 assert.match(s,/PRIMARY KEY \(project_id,quality_version\)/);
 assert.match(s,/def save_semantic_context/);
 assert.match(s,/user_described_not_independently_verified/);
 assert.match(s,/target_business_context/);
});

test('P3 API validates local origin, version and columns before write',()=>{
 const s=read('backend/main.py');
 const block=s.split('@app.post("/api/projects/{project_id}/semantic-business-context")')[1]?.split('@app.get("/api/projects/{project_id}/semantics")')[0];
 assert.ok(block);
 assert.match(block,/_local_request\(request\)/);
 assert.match(block,/project_or_404\(project_id\)/);
 assert.match(block,/quality\.current_data\(project_id\)/);
 assert.match(block,/version != body\.expected_version/);
 assert.match(block,/col not in frame\.columns/);
 assert.match(block,/col in seen/);
 assert.match(block,/storage\.save_semantic_context/);
 assert.doesNotMatch(block,/train_background|new_experiment|quality\.commit/);
});

test('P3 editor requires explicit save and labels notes as owner descriptions',()=>{
 const s=read('frontend/src/SemanticContextEditor.tsx');
 const screen=read('frontend/src/SemanticOverview.tsx');
 assert.match(s,/Save business descriptions/);
 assert.match(s,/expected_version:version/);
 assert.match(s,/user-provided, not independently verified/i);
 assert.match(s,/disabled=\{!ready\|\|busy\}/);
 assert.match(screen,/user_context/);
 assert.match(screen,/data\.domain\.reason/);
 assert.match(screen,/SemanticContextEditor/);
 assert.doesNotMatch(s,/startTrain\(|selectTarget\(|setTarget\(/);
});

test('P3 UI is integrated under existing versioned data dictionary',()=>{
 const s=read('frontend/src/ColumnInvestigation.tsx');
 assert.match(s,/import \{SemanticOverview\}/);
 assert.match(s,/columns=\{dictionary\.columns\.map\(item=>item\.name\)\}/);
 assert.match(s,/version=\{dictionary\.version\}/);
});
