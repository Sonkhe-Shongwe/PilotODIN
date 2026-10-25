const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const root=path.resolve(__dirname,'../..');
const read=p=>fs.readFileSync(path.join(root,p),'utf8');

test('resource status uses system physical RAM and explicitly reports no E2 certification',()=>{
 const source=read('backend/resource_policy.py');
 assert.match(source,/GlobalMemoryStatusEx/);
 assert.match(source,/"available_gib"/);
 assert.match(source,/"status": "unavailable"/);
 assert.match(source,/offline_8gb_ai_feasibility": "NOT_TESTED"/);
 assert.match(source,/policy_effect": "display_only_p1_not_enforced"/);
 assert.doesNotMatch(source,/(?:subprocess|requests\.|urllib\.request|psutil\.process_iter|os\.system)/);
});

test('resource mode API reuses local-only controls and saves only validated values',()=>{
 const main=read('backend/main.py');
 assert.match(main,/class ResourcePolicyRequest\(BaseModel\)/);
 assert.match(main,/Literal\["adaptive", "low_memory", "performance"\]/);
 assert.match(main,/@app\.get\('\/api\/resource\/status'\)/);
 assert.match(main,/@app\.put\('\/api\/resource\/policy'\)/);
 // Check the actual route bodies rather than relying on comment count,
 // exact whitespace or Windows CRLF line endings.
 const readRoute=main.split('def resource_status(request: Request):')[1]?.split("@app.put('/api/resource/policy')")[0];
 const writeRoute=main.split('def update_resource_policy(body: ResourcePolicyRequest, request: Request):')[1]?.split("@app.get('/api/ai/settings')")[0];
 assert.ok(readRoute,'Resource status handler must exist');
 assert.ok(writeRoute,'Resource policy handler must exist');
 assert.match(readRoute,/_local_request\(request\)/);
 assert.match(readRoute,/return resource_policy\.status\(\)/);
 assert.ok(readRoute.indexOf('_local_request(request)')<readRoute.indexOf('return resource_policy.status()'),'Authorize before reading status');
 assert.match(writeRoute,/_local_request\(request\)/);
 assert.match(writeRoute,/resource_policy\.save_policy\(body\.mode\)/);
 assert.ok(writeRoute.indexOf('_local_request(request)')<writeRoute.indexOf('resource_policy.save_policy(body.mode)'),'Authorize before writing policy');
});

test('Resource-Aware Settings UI is advisory, explicit-save and does not run a model',()=>{
 const ui=read('frontend/src/ResourceSettings.tsx');
 const settings=read('frontend/src/AIWorkspace.tsx');
 assert.match(settings,/import \{ResourceSettings\} from '\.\/ResourceSettings'/);
 assert.match(settings,/<ResourceSettings\/>/);
 assert.match(ui,/Resource-Aware Mode/);
 assert.match(ui,/value=\{draft\}/);
 assert.match(ui,/status\.policy\.mode===draft/);
 assert.match(ui,/\/resource\/status/);
 assert.match(ui,/\/resource\/policy/);
 assert.match(ui,/Heavy-work scheduling is not enabled/);
 assert.match(ui,/No processes are inspected or stopped/);
 assert.doesNotMatch(ui,/launch_bundled_ai|ollama (?:pull|run)|\/ai\/local\/status/);
});
