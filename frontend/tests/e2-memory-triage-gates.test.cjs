const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const root=path.resolve(__dirname,'../..');
const read=p=>fs.readFileSync(path.join(root,p),'utf8');

test('E2 memory triage is read-only and does not claim offline-model feasibility',()=>{
 const script=read('tools/Probe_E2_Memory_Triage.ps1');
 assert.match(script,/Get-CimInstance -ClassName Win32_OperatingSystem/);
 assert.match(script,/Get-CimInstance -ClassName Win32_Process -Property Name,WorkingSetSize,PrivatePageCount/);
 assert.match(script,/Group-Object -Property Name/);
 assert.match(script,/Select-Object -First 12/);
 assert.match(script,/working_set_gib_sum/);
 assert.match(script,/private_committed_gib_sum/);
 assert.match(script,/contains_executable_names=\$true/);
 assert.match(script,/ollama_model_loaded='NOT_CHECKED'/);
 assert.match(script,/actual_offline_generation='NOT_TESTED'/);
 assert.match(script,/actual_8gb_concurrent_stress='NOT_TESTED'/);
 assert.match(script,/result='UNDETERMINED'/);
 assert.doesNotMatch(script,/Invoke-(?:WebRequest|RestMethod)|Start-Process|Remove-Item|Stop-Process|winget|ollama run|ollama pull|pip install|npm install|cargo build/i);
});

test('E2 memory launcher does not rerun previous P1 or A4 suites',()=>{
 const launcher=read('Run_PilotODIN_E2_Memory_Triage.bat');
 assert.match(launcher,/Probe_E2_Memory_Triage\.ps1/);
 assert.doesNotMatch(launcher,/Verify_P0|Verify_P1_E2_Local|A4_Native|tauri|ollama run|ollama pull/i);
});
