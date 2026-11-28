const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');

const root=path.resolve(__dirname,'../..');
const ps=fs.readFileSync(path.join(root,'tools/Run_P2_Native_Deliver_Consent_Local.ps1'),'utf8');
const bat=fs.readFileSync(path.join(root,'Run_PilotODIN_P2_Narrator_Focus.bat'),'utf8');
const legacy=['dirty_warning','explore_keep','new_project_keep','explore_leave','new_project_leave'];
const a01=['a01_warning_narrator','a01_native_dialog_narrator','a01_keep_focus','a01_leave_importer_focus'];

test('separate opt-in accessibility mode; existing five-step entry remains default',()=>{
 assert.match(ps,/param\(\[switch\]\$AccessibilityOnly\)/);
 assert.match(ps,/if\(\$AccessibilityOnly\)\{/);
 assert.match(ps,/\}else\{\s*\$results=@\(/);
 for(const name of legacy)
  assert.equal((ps.match(new RegExp("Owner-Check '"+name+"'","g"))||[]).length,1,name);
 assert.deepEqual((ps.match(/Owner-Check '(?:dirty_warning|explore_keep|new_project_keep|explore_leave|new_project_leave)'/g)||[])
  .map(x=>x.match(/'([^']+)'/)[1]),legacy);
 assert.match(ps,/observation_mode=\$\(if\(\$AccessibilityOnly\)/);
 assert.match(bat,/Run_P2_Native_Deliver_Consent_Local\.ps1" -AccessibilityOnly/);
 assert.match(bat,/OWNER ACCESSIBILITY OBSERVATIONS RECORDED; REVIEW REQUIRED/);
});

test('four required Narrator and keyboard checks have explicit owner prompts',()=>{
 for(const name of a01)
  assert.equal((ps.match(new RegExp("Owner-Check '"+name+"'","g"))||[]).length,1,name);
 assert.match(ps,/Narrator could identify the unsaved-report warning/);
 assert.match(ps,/Narrator clearly identified its purpose/);
 assert.match(ps,/Tab\/Shift\+Tab reached the modal choices/);
 assert.match(ps,/keyboard-accessible synthetic importer only after consent/);
 assert.match(ps,/P2-A01 native keyboard\/Narrator: OWNER-REPORTED OBSERVATIONS COMPLETE \(REVIEW REQUIRED\)/);
 assert.doesNotMatch(ps,/P2-A01 native keyboard\/Narrator: ACCEPTED/);
});

test('test-only safeguards, process isolation and fail-closed outcome unchanged',()=>{
 assert.match(ps,/PILOTODIN_HOME=\$isolatedWorkspaceHome/);
 assert.match(ps,/Port-Occupied 8000 -or Port-Occupied 5177/);
 assert.match(ps,/VITE_P2_NATIVE_DELIVER_QA='1'/);
 assert.match(ps,/CARGO_NET_OFFLINE='true'/);
 assert.match(ps,/owner_native_observations=\$\(if\(\$AccessibilityOnly\)/);
 assert.match(ps,/if\(\$results -contains \$false\)\{throw/);
 assert.match(ps,/backend_writes='NO_MUTATION_REQUESTS_OBSERVED'/);
 assert.match(ps,/Stop-Process -Id \$backend\.Id/);
 assert.match(ps,/product_acceptance='NOT_TESTED'/);
 assert.match(ps,/Compress-Archive -LiteralPath \$statusSources/);
 assert.doesNotMatch(ps,/npm (install|ci)|cargo install|tauri build|Stop-Process -Name|Remove-Item[^\n]*-Recurse/);
});
