const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const root=path.resolve(__dirname,'../..');
const read=p=>fs.readFileSync(path.join(root,p),'utf8');

test('P5 Low-memory slot is reserved under SQLite write transaction, not an in-memory flag',()=>{
 const storage=read('backend/storage.py');
 const insert=storage.split('def new_experiment_with_capacity(')[1]?.split('def claim_queued_experiment(')[0];
 assert.ok(insert,'atomic allocator must exist');
 assert.match(insert,/con\.execute\("BEGIN IMMEDIATE"\)/);
 assert.match(insert,/WHERE status IN \('queued','running'\)/);
 assert.match(insert,/raise TrainingSlotBusy/);
 assert.ok(insert.indexOf("BEGIN IMMEDIATE") <
           insert.indexOf("SELECT id FROM experiments"),'lock before checking');
 assert.ok(insert.indexOf('raise TrainingSlotBusy') <
           insert.indexOf('INSERT INTO experiments'),'reject before persistence');
});

test('P5 worker terminal and startup recovery transitions are guarded',()=>{
 const storage=read('backend/storage.py');
 const main=read('backend/main.py');
 assert.match(storage,/UPDATE experiments SET status='running' WHERE id=\? AND status='queued'/);
 assert.match(storage,/WHERE id=\? AND status='running'/);
 assert.match(storage,/def recover_interrupted_experiments\(/);
 assert.match(storage,/Training interrupted by application restart/);
 const startup=main.split('async def _lifespan(_app:FastAPI):')[1]?.split('app = FastAPI(')[0];
 assert.ok(startup&&startup.includes('storage.recover_interrupted_experiments()'));
 const worker=main.split('def train_background(')[1]?.split('@app.post("/api/projects/{project_id}/experiments"')[0];
 assert.ok(worker);
 assert.match(worker,/if not storage\.claim_queued_experiment\(eid\):\s*return/);
 assert.match(worker,/storage\.finish_running_experiment\(eid,"completed"/);
 assert.match(worker,/storage\.finish_running_experiment\(eid,"failed"/);
});

test('P5 refusals cannot create a ghost ML experiment or background task',()=>{
 const main=read('backend/main.py');
 const route=main.split('def new_experiment(')[1]?.split('@app.get("/api/experiments/')[0];
 assert.ok(route);
 const low=route.indexOf('storage.new_experiment_with_capacity(project_id,config)');
 const task=route.indexOf('background_tasks.add_task(train_background,eid,project_id,config)');
 assert.ok(low>0&&task>low);
 assert.match(route,/except storage\.TrainingSlotBusy as exc:/);
 assert.match(route,/"code": "ml_training_slot_busy"/);
 assert.match(route,/raise HTTPException\(status_code=503/);
 const regressions=read('tests/test_p5_ml_training_slot.py');
 for(const name of [
  'test_atomic_concurrent_reservations_have_exactly_one_winner',
  'test_process_restart_marks_only_nonterminal_work_failed',
  'test_low_memory_api_busy_refuses_before_background_enqueue',
  'test_adaptive_keeps_existing_multistart_semantics',
 ])assert.ok(regressions.includes(name),'Missing regression: '+name);
});
