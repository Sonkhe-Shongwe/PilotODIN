const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const root=path.resolve(__dirname,'../..');
const read=p=>fs.readFileSync(path.join(root,p),'utf8');

test('P5 cancel is transactional: queued stops now, running only requests stop',()=>{
 const source=read('backend/storage.py');
 const body=source.split('def request_training_cancel(eid):')[1]?.split('def finish_interrupted_experiment(')[0];
 assert.ok(body,'cancel handler must exist');
 assert.match(body,/BEGIN IMMEDIATE/);
 assert.match(body,/status='cancelled'/);
 assert.match(body,/_append_progress\(con,eid,"cancelled"/);
 assert.match(body,/cancel_requested=1/);
 assert.match(body,/return "cancellation_requested"/);
 assert.match(body,/return "already_finished"/);
 assert.doesNotMatch(body,/os\.kill|terminate\(|task\.cancel\(/);
});

test('P5 cooperative timeout/checkpoint validates terminal commit and engine callbacks',()=>{
 const storage=read('backend/storage.py'),engine=read('backend/engine.py');
 assert.match(storage,/CREATE TABLE IF NOT EXISTS experiment_run_controls/);
 assert.match(storage,/def check_training_interruption\(eid\):/);
 assert.match(storage,/def finish_interrupted_experiment\(eid, reason\):/);
 assert.match(storage,/if status == "completed":\s*reason = _requested_interruption/);
 assert.match(storage,/if reason:\s*raise TrainingInterrupted\(reason\)/);
 assert.match(engine,/stop_check=None/);
 assert.match(engine,/checkpoint\(\)/);
 assert.match(engine,/except InterruptedError:\s*raise/);
 assert.doesNotMatch(engine,/threading\.Thread.*kill|os\.kill\(/);
});

test('P5 FastAPI cancel endpoint and worker do not claim forced interruption',()=>{
 const main=read('backend/main.py');
 const cancel=main.split('def cancel_training(experiment_id:str, request:Request):')[1]?.split('@app.post("/api/experiments/{experiment_id}/select")')[0];
 assert.ok(cancel);
 assert.match(cancel,/_local_request\(request\)/);
 assert.match(cancel,/request_training_cancel\(experiment_id\)/);
 assert.match(cancel,/current sklearn CV\/fit cannot be forcibly stopped|running sklearn CV\/fit cannot be forcibly stopped/);
 const worker=main.split('def train_background(')[1]?.split('@app.post("/api/projects/{project_id}/experiments"')[0];
 assert.ok(worker);
 assert.match(worker,/stop_check=lambda: storage\.check_training_interruption\(eid\)/);
 assert.match(worker,/except storage\.TrainingInterrupted as e:/);
 assert.match(worker,/storage\.finish_interrupted_experiment\(eid,e\.status\)/);
 assert.match(worker,/shutil\.rmtree\(artifact_path,ignore_errors=True\)/);
 assert.match(worker,/if artifact_path is not None and not finished:/);
 const route=main.split('def new_experiment(')[1]?.split('@app.get("/api/experiments/')[0];
 assert.ok(route);
 assert.match(route,/"max_duration_seconds":body\.max_duration_seconds/);
});

test('P5 Model Lab and Evaluate offer explicit timeout and honest cancellation UI',()=>{
 const frontend=read('frontend/src/App.tsx'),api=read('frontend/src/api.ts');
 assert.match(frontend,/max_duration_seconds:trainingLimitMinutes\?trainingLimitMinutes\*60:null/);
 assert.match(frontend,/No time limit/);
 assert.match(frontend,/Soft limit:/);
 assert.match(frontend,/async function cancelTrain\(\)/);
 assert.match(frontend,/post<\{status:string;message:string\}>\(\`\/experiments\/\$\{eid\}\/cancel\`,\{\}\)/);
 assert.match(frontend,/Cancellation requested; the current fitting operation may still be running/);
 assert.match(frontend,/Training time limit reached/);
 assert.match(api,/control\?:\{cancel_requested:boolean/);
 assert.match(api,/max_duration_seconds\?:number\|null/);
});

test('P5 focused regression suite explicitly tests cancel and timeouts against isolated data',()=>{
 const testSource=read('tests/test_p5_training_cancellation.py');
 for(const name of [
  'test_queued_cancellation_is_immediate_idempotent_and_frees_slot',
  'test_running_cancellation_is_only_pending_until_checkpoint',
  'test_deadline_begins_on_claim_and_is_checked_cooperatively',
  'test_partial_artifacts_deleted_after_cancellation_during_save',
  'test_completed_artifacts_are_preserved_and_cannot_be_cancelled',
  'test_engine_checkpoint_interrupt_is_not_swallowed_by_per_model_exception',
  'test_worker_exits_after_request_inside_blocking_training',
 ])assert.ok(testSource.includes(name),'Missing regression '+name);
});
