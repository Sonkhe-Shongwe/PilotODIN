const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const root=path.resolve(__dirname,'../..');
const read=p=>fs.readFileSync(path.join(root,p),'utf8');

test('P5 stage ledger is additive, SQLite persisted and does not invent percentages',()=>{
 const storage=read('backend/storage.py');
 assert.match(storage,/CREATE TABLE IF NOT EXISTS experiment_progress_events/);
 assert.match(storage,/CREATE INDEX IF NOT EXISTS experiment_progress_by_run/);
 assert.match(storage,/def _append_progress\(con, eid, stage, detail\):/);
 assert.match(storage,/def _progress_for\(con, eid, status\):/);
 assert.match(storage,/def advance_running_experiment\(eid, stage, detail\):/);
 assert.match(storage,/def recover_interrupted_experiments\(\):/);
 assert.match(storage,/history_available": False/);
 assert.match(storage,/running_legacy/);
 assert.doesNotMatch(storage,/percent_complete|estimated_percent|percentage_complete/);
});

test('P5 queued, worker, terminal and interrupted transitions append honest stages',()=>{
 const storage=read('backend/storage.py');
 const main=read('backend/main.py');
 const worker=main.split('def train_background(')[1]?.split('@app.post("/api/projects/{project_id}/experiments"')[0];
 assert.ok(worker,'Training worker found');
 assert.match(storage,/ACTIVE_STAGE_ORDER = \("loading_data", "training_models", "saving_artifacts"\)/);
 const order=[
  'claim_queued_experiment(eid)',
  'df=df_for(p,config["quality_version"])',
  '"training_models"',
  'engine.run_training(df',
  '"saving_artifacts"',
  'joblib.dump(pipe',
  'finish_running_experiment(eid,"completed"',
 ];
 const indices=order.map(x=>worker.indexOf(x));
 assert.ok(indices.every(i=>i>=0),'Every observed work milestone must exist');
 assert.ok(indices.every((i,k)=>k===0||i>indices[k-1]),
           'Stages must follow real work in the correct order');
 assert.match(storage,/_append_progress\(con,eid,"queued"/);
 assert.match(storage,/_append_progress\(con,eid,"loading_data"/);
 assert.match(storage,/if changed\.rowcount == 1:[\s\S]*?_append_progress\(/);
 assert.match(storage,/Backend restarted while training was unfinished/);
});

test('P5 existing experiment API and Evaluate polling expose real stages without fabricated ETA',()=>{
 const main=read('backend/main.py');
 const api=read('frontend/src/api.ts');
 const app=read('frontend/src/App.tsx');
 const response=main.split('def get_experiment(experiment_id:str):')[1]?.split('@app.post("/api/experiments/{experiment_id}/select")')[0];
 assert.ok(response&&response.includes('"progress":e["progress"]'));
 assert.match(api,/export type ExperimentProgressEvent/);
 assert.match(api,/export type ExperimentProgress =/);
 assert.match(api,/progress\?:ExperimentProgress/);
 assert.match(app,/experiment\.progress\?\.label/);
 assert.match(app,/experiment\.progress\?\.detail/);
 assert.match(app,/experiment\.progress\.history\.map/);
 assert.match(app,/Stages are observed checkpoints, not estimated percentages/);
 assert.match(app,/get<Experiment>\(\`\/experiments\/\$\{experimentId\}\`\)/);
 assert.doesNotMatch(app,/experiment\.progress\?\.percent/);
});

test('P5 focused backend acceptance exercises migration, status transitions and app response',()=>{
 const source=read('tests/test_p5_training_progress.py');
 for(const name of [
  'test_queued_event_persisted_for_both_admission_paths',
  'test_running_stage_sequence_is_monotonic_and_durable',
  'test_legacy_experiments_do_not_receive_invented_milestones',
  'test_original_completed_history_survives_progress_migration',
  'test_recovery_adds_one_terminal_event_and_preserves_completed_model',
  'test_read_only_experiment_endpoint_exposes_persisted_progress',
  'test_worker_milestones_are_observed_not_estimated',
  'test_worker_failure_preserves_real_last_stage_and_no_results',
  'test_stale_worker_cannot_emit_new_milestones_after_restart',
 ])assert.ok(source.includes(name),'Missing: '+name);
});
