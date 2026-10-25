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
 assert.match(source,/policy_effect": "low_memory_new_work_preflight_only_no_scheduler"/);
 assert.match(source,/LOW_MEMORY_MIN_FREE_GIB/);
 assert.match(source,/def admit_new_work\(operation: str\)/);
 // Match executable imports/calls, not English documentation such as
 // "new requests." A broad text substring test produced a false FAIL.
 assert.doesNotMatch(source,/^\s*(?:import\s+(?:subprocess|requests|urllib\.request|psutil)\b|from\s+(?:subprocess|requests|urllib\.request|psutil)\s+import\b)/m,
   'Resource module must not import network/process clients');
 assert.doesNotMatch(source,/\b(?:subprocess\.(?:run|Popen|call)|requests\.(?:get|post|put|delete|request)|urllib\.request\.urlopen|psutil\.process_iter|os\.system)\s*\(/,
   'Resource module must not invoke network/process control operations');
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

test('Resource-Aware Settings UI shows active low-memory screening with explicit-save and no model start',()=>{
 const ui=read('frontend/src/ResourceSettings.tsx');
 const settings=read('frontend/src/AIWorkspace.tsx');
 assert.match(settings,/import \{ResourceSettings\} from '\.\/ResourceSettings'/);
 assert.match(settings,/<ResourceSettings\/>/);
 assert.match(ui,/Resource-Aware Mode/);
 assert.match(ui,/value=\{draft\}/);
 assert.match(ui,/status\.policy\.mode===draft/);
 assert.match(ui,/\/resource\/status/);
 assert.match(ui,/\/resource\/policy/);
 assert.match(ui,/Low-memory mode screens new ML\/local-AI starts/);
 assert.match(ui,/low_memory_training_min_free_gib/);
 assert.match(ui,/low_memory_local_inference_min_free_gib/);
 assert.match(ui,/No processes are inspected or stopped/);
 assert.doesNotMatch(ui,/launch_bundled_ai|ollama (?:pull|run)|\/ai\/local\/status/);
});


test('Low-memory gate sits before any new ML experiment is persisted and leaves baseline guards intact',()=>{
 const main=read('backend/main.py');
 const handler=main.split('def new_experiment(')[1]?.split('@app.get("/api/experiments/')[0];
 assert.ok(handler,'ML experiment route must exist');
 assert.match(handler,/engine\.validate_config\(/);
 assert.match(handler,/engine\.preparation\(/);
 assert.match(handler,/resource_policy\.admit_new_work\("training"\)/);
 assert.match(handler,/HTTPException\(status_code=503/);
 assert.match(handler,/storage\.new_experiment\(project_id,config\)/);
 assert.ok(handler.indexOf('resource_policy.admit_new_work("training")') <
           handler.indexOf('storage.new_experiment(project_id,config)'),
           'No experiment artifacts may be created before admission');
 const provider=read('backend/ai_provider.py');
 const local=provider.split('def local_try()->dict|None:')[1]?.split('    if prefer_local:')[0];
 assert.ok(local,'Local generation request function must exist');
 assert.match(local,/resource_policy\.admit_new_work\('local_inference'\)/);
 assert.ok(local.indexOf("admit_new_work('local_inference')")<
           local.indexOf('bundled_inference.generate('));
 assert.ok(local.indexOf("admit_new_work('local_inference')")<
           local.indexOf('_call_ollama('));
 assert.match(local,/local_failed='resource_limited'/);
});


test('native bundled model request is screened before Tauri worker launch',()=>{
 const api=read('frontend/src/api.ts');
 assert.match(api,/\/resource\/preflight\?operation=local_inference/);
 const startup=api.split('async function requestLocalAI(')[1]?.split('export async function get<T>')[0];
 assert.ok(startup,'Native model startup helper must exist');
 const readCheck=startup.indexOf("fetchLocal('/resource/preflight?operation=local_inference'");
 const launch=startup.indexOf("invoke('launch_bundled_ai')");
 assert.ok(readCheck>=0&&launch>=0&&readCheck<launch,
           'Read-only resource preflight must precede any bundled model launch');
 assert.match(startup,/preflight\.decision!=='allow'/);
 assert.match(startup,/return 'resource_limited'/);
 assert.match(startup,/return 'resource_preflight_unavailable'/);
 assert.match(startup,/headers:authHeaders\(\)/);
 assert.match(api,/typeof d\.message==='string'\?d\.message/);
 const main=read('backend/main.py');
 const preflight=main.split("def resource_preflight(")[1]?.split("@app.put('/api/resource/policy')")[0];
 assert.ok(preflight&&preflight.includes('_local_request(request)'));
 assert.match(preflight,/resource_policy\.admit_new_work\(operation\)/);
});
