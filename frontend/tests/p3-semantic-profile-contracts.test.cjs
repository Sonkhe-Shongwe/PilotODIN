const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const root=path.resolve(__dirname,'../..');
const read=p=>fs.readFileSync(path.join(root,p),'utf8');

test('P3 semantics are deterministic read-only metadata with explicit uncertainty',()=>{
 const source=read('backend/semantic_profile.py');
 assert.match(source,/Read-only local heuristics/);
 assert.match(source,/MAX_FIELDS = 80/);
 assert.match(source,/column_intelligence\.overview\(frame, version\)/);
 assert.match(source,/"state": "unknown"/);
 assert.match(source,/"state": "hypothesis"/);
 assert.match(source,/no.*target selection/i);
 assert.doesNotMatch(source,/\.fit\(|joblib\.load|openai|gemini|ollama|\.to_csv\(|\.to_sql\(/i);
});

test('P3 route requires approved project and exact version, with no target training',()=>{
 const main=read('backend/main.py');
 const route=main.split('@app.get("/api/projects/{project_id}/semantics")')[1]?.split('@app.get("/api/projects/{project_id}/columns/detail")')[0];
 assert.ok(route,'Expected version-pinned semantics GET route');
 assert.match(route,/request: Request/);
 assert.match(route,/_local_request\(request\)/);
 assert.match(route,/project_or_404\(project_id\)/);
 assert.match(route,/quality\.current_data\(project_id\)/);
 assert.match(route,/version != expected_version/);
 assert.match(route,/HTTPException\(\s*status_code=409/);
 assert.match(route,/semantic_profile\.overview\(frame, version\)/);
 assert.doesNotMatch(route,/new_experiment|joblib|train_background|quality\.commit/);
});

test('P3 data dictionary displays unknowns and evidence, without auto-target confirmation',()=>{
 const ui=read('frontend/src/SemanticOverview.tsx');
 const col=read('frontend/src/ColumnInvestigation.tsx');
 assert.match(col,/import \{SemanticOverview\} from '\.\/SemanticOverview'/);
 assert.match(col,/version=\{dictionary\.version\}/);
 assert.match(ui,/expected_version=\$\{version\}/);
 assert.match(ui,/if\(result\.version!==version\)/);
 assert.match(ui,/business meaning|Business meaning hypotheses/i);
 assert.match(ui,/Unknown — insufficient evidence/);
 assert.match(ui,/no prediction target is selected/i);
 assert.match(ui,/on.*?projectId,version/s);
 assert.doesNotMatch(ui,/startTrain\(|selectTarget\(|setTarget\(/);
});

test('P3 tests include domain alternatives, abstention, privacy and stale-version handling',()=>{
 const src=read('tests/test_p3_semantic_profile.py');
 for(const name of [
  'test_insurance_is_a_header_hypothesis_not_confirmed_business_meaning',
  'test_retail_is_tentative_and_does_not_claim_order_grain',
  'test_no_semantic_signal_abstains_without_inventing_domain_or_target',
  'test_conflicting_domain_clues_abstain_instead_of_ranking_by_guesswork',
  'test_response_is_bounded_and_never_exports_sample_values',
  'test_semantic_api_is_project_scoped_and_version_pinned',
 ])assert.ok(src.includes(name),'Missing regression: '+name);
});
