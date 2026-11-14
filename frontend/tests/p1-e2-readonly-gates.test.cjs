const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const root=path.resolve(__dirname,'../..');
const read=p=>fs.readFileSync(path.join(root,p),'utf8');

test('P1 failed project imports never mask the error with missing Quality tables',()=>{
 const main=read('backend/main.py');
 const testSource=read('tests/test_p1_import_recovery.py');
 assert.match(main,/def _rollback_failed_project_import\(pid: str \| None, path: Path\)/);
 assert.match(main,/SELECT name FROM sqlite_master WHERE type='table'/);
 assert.match(main,/if table in tables/);
 assert.match(main,/con\.execute\("DELETE FROM projects WHERE id=\?"/);
 assert.match(main,/path\.unlink\(missing_ok=True\)/);
 assert.match(main,/Import failed and could not be rolled back safely/);
 assert.match(testSource,/test_import_rollback_works_when_quality_schema_is_missing/);
 assert.match(testSource,/test_partial_quality_registration_is_rolled_back_atomically/);
 assert.match(testSource,/test_rejected_invalid_dataset_removes_staged_bytes/);
 assert.match(testSource,/test_import_rollback_failure_keeps_source_for_recovery/);
});

test('Early E2 hardware inventory cannot make unsupported offline AI claims',()=>{
 const probe=read('tools/Probe_E2_8GB_Offline_Inventory.ps1');
 assert.match(probe,/READ_ONLY_INVENTORY_NOT_8GB_STRESS_OR_OFFLINE_AI/);
 assert.match(probe,/Get-CimInstance -ClassName Win32_OperatingSystem/);
 assert.match(probe,/Get-Process -ErrorAction SilentlyContinue/);
 assert.match(probe,/ai_inference = 'NOT_TESTED'/);
 assert.match(probe,/simultaneous_ai_ml_load = 'NOT_TESTED'/);
 assert.match(probe,/final_e2_decision = 'UNDETERMINED'/);
 assert.match(probe,/local_model_license = 'NOT_VERIFIED'/);
 assert.match(probe,/Set-Content -LiteralPath \$out/);
 assert.doesNotMatch(probe,/(?:Invoke-WebRequest|Invoke-RestMethod|Start-Process|Remove-Item|Stop-Process|Set-ExecutionPolicy|winget|npm install|cargo build)/i);
});

test('P1 import regression is included in next deduplicated local gate',()=>{
 const runner=read('tools/Verify_P0_A4_Readiness.py');
 const appearances=runner.match(/test_p1_import_recovery\.py/g)||[];
 assert.equal(appearances.length,1);
});


test('P1/E2 one-click launcher only runs new import tests and non-invasive inventory',()=>{
 const script=read('tools/Verify_P1_E2_Local.ps1');
 const launcher=read('Run_PilotODIN_P1_E2_Preflight.bat');
 assert.match(launcher,/Verify_P1_E2_Local\.ps1/);
 assert.match(script,/tests\/test_p1_import_recovery\.py/);
 assert.match(script,/Probe_E2_8GB_Offline_Inventory\.ps1/);
 assert.match(script,/PILOTODIN_HOME/);
 assert.match(script,/Compress-Archive/);
 assert.match(script,/offline_ai_and_8gb_certification = 'NOT_TESTED'/);
 assert.doesNotMatch(script,/(?:Verify_P0_A4_Readiness|desktop:build|tauri build|Run_PilotODIN_A4_Native_Smoke|Start-Process|Invoke-WebRequest|Invoke-RestMethod)/);
 assert.doesNotMatch(launcher,/Install|winget/);
});
