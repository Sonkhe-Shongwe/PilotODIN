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

test('P3-03a associates owner field definitions by exact column without asserting semantic agreement',()=>{
 const screen=read('frontend/src/SemanticOverview.tsx');
 assert.match(screen,/ownerFieldDescriptions=new Map/);
 assert.match(screen,/ownerFieldDescriptions\.has\(item\.column\)/);
 assert.match(screen,/USER DESCRIPTION \(UNVERIFIED\)/);
 assert.match(screen,/user-described, not independently verified/);
 assert.match(screen,/No automatic equivalence or disagreement finding/);
 assert.match(screen,/unique row key does not independently establish/);
 assert.doesNotMatch(screen,/setTarget\(|selectTarget\(|train_background\(/);
});

test('P3 unsaved business context uses existing primary project, exit and native close guards',()=>{
 const ts=require('typescript'),Module=require('node:module');
 const file=path.join(root,'frontend/src/primaryStudioExitGuard.ts');
 const program=ts.transpileModule(fs.readFileSync(file,'utf8'),{
  compilerOptions:{target:ts.ScriptTarget.ES2021,module:ts.ModuleKind.CommonJS},
  reportDiagnostics:true
 });
 assert.equal((program.diagnostics||[]).filter(d=>d.category===ts.DiagnosticCategory.Error).length,0);
 const m=new Module(file,module);m.filename=file;m.paths=module.paths;m._compile(program.outputText,file);
 const needs=m.exports.needsPrimaryStudioExitApproval;
 const edit={projectId:'A',view:'understand'};
 assert.equal(needs(edit,'A','understand','quality',true),true);
 assert.equal(needs(edit,'A','understand','investigate',true),true);
 assert.equal(needs(edit,'A','understand','deliver',true),true);
 assert.equal(needs(edit,'A','understand','understand',true),false);
 assert.equal(needs(edit,'B','understand','quality',true),false);
 assert.equal(needs(edit,'A','understand','quality',false),false);
 // The older Prepare/Model/Predict contract remains unchanged.
 assert.equal(needs({projectId:'A',view:'prepare'},'A','prepare','quality',true),false);
 const app=read('frontend/src/App.tsx');
 const shell=read('frontend/src/UnifiedShell.tsx');
 const dictionary=read('frontend/src/ColumnInvestigation.tsx');
 const overview=read('frontend/src/SemanticOverview.tsx');
 const editor=read('frontend/src/SemanticContextEditor.tsx');
 const unload=read('frontend/src/dockInputDiscardGuard.ts');
 assert.match(editor,/onUnsavedChange\?\.\(dirty\)/);
 assert.match(editor,/onUnsavedChange\?\.\(false\)/);
 assert.match(editor,/existing\?\.domain_description/);
 assert.match(editor,/existing\?\.field_definitions/);
 assert.match(editor,/Unsaved business descriptions/);
 assert.match(dictionary,/onUnsavedChange=\{onUnsavedChange\}/);
 assert.match(overview,/onUnsavedChange=\{onUnsavedChange\}/);
 assert.match(app,/if\(dirty\)onPrimaryDraftEdited\?\.\('understand'\)/);
 assert.match(app,/onPrimaryDraftCleared\?\.\('understand'\)/);
 assert.match(shell,/view==='understand'\|\|view==='prepare'/);
 assert.match(shell,/Your Data Dictionary has unsaved business descriptions/);
 assert.match(unload,/view:'understand'\|'prepare'/);
 assert.doesNotMatch(editor,/localStorage|sessionStorage|train_background\(|setTarget\(/);
});
