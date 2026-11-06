const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const root=path.resolve(__dirname,'../..');
const get=file=>fs.readFileSync(path.join(root,file),'utf8');
const python=get('tools/Seed_P2_Native_Deliver_Consent_Local.py');
const ps=get('tools/Run_P2_Native_Deliver_Consent_Local.ps1');
const bat=get('Run_PilotODIN_P2_Native_Deliver_Consent.bat');
const page=get('frontend/p2_native_deliver_consent_qa.html');
const ui=get('frontend/src/p2NativeDeliverConsentQa.tsx');
const config=JSON.parse(get('frontend/src-tauri/tauri.p2-native-deliver-consent.conf.json'));

test('QA runs in a non-distributable isolated Tauri identifier and fixed unique Vite port',()=>{
 assert.equal(config.identifier,'com.pilotodin.p2deliverconsentqa');
 assert.equal(config.bundle.active,false);
 assert.deepEqual(config.bundle.externalBin,[]);
 assert.deepEqual(config.bundle.resources,[]);
 assert.match(config.build.beforeDevCommand,/npm run dev -- --port 5177/);
 assert.equal(config.build.devUrl,'http://127.0.0.1:5177/p2_native_deliver_consent_qa.html');
 assert.equal(config.app.windows[0].label,'main');
 assert.doesNotMatch(config.build.devUrl,/localhost:8000|127\.0\.0\.1:8000/);
});

test('test page mounts actual full shell with the protected native bridge, not bare ReportWorkspace',()=>{
 assert.match(page,/src\/p2NativeDeliverConsentQa\.tsx/);
 assert.match(ui,/import \{UnifiedShell\} from '\.\/UnifiedShell'/);
 assert.match(ui,/<React\.StrictMode><UnifiedShell\/><\/React\.StrictMode>/);
 assert.doesNotMatch(ui,/import \{ReportWorkspace\}/);
 assert.match(ui,/import\.meta\.env\.DEV/);
 assert.match(ui,/VITE_P2_NATIVE_DELIVER_QA==='1'/);
 assert.match(ui,/VITE_PILOTODIN_NATIVE_SMOKE==='1'/);
 assert.match(ui,/location\.origin==='http:\/\/127\.0\.0\.1:5177'/);
 assert.match(ui,/isDesktop\(\)/);
});

test('browser QA locks exact synthetic project and permits only read requests to owned API',()=>{
 assert.match(ui,/localStorage\.setItem\('pilotodin-current',id\)/);
 assert.match(ui,/localStorage\.setItem\('pilotodin-workspace-active-v1-'\+id,'deliver'\)/);
 assert.match(ui,/window\.fetch=\(\(input:RequestInfo\|URL,init\?:RequestInit\)=>/);
 assert.match(ui,/url\.origin!=='http:\/\/127\.0\.0\.1:8000'/);
 assert.match(ui,/!url\.pathname\.startsWith\('\/api\/'\)/);
 assert.match(ui,/!\['GET','HEAD'\]\.includes\(method\)/);
 assert.doesNotMatch(ui,/\bpost\(|\bupload\(|\btrain\(/);
});

test('seed refuses non-empty and redirected workspace, validates true bytes and writes only fixture metadata',()=>{
 assert.match(python,/PILOTODIN_HOME/);
 assert.match(python,/READY_NOT_TESTED/);
 assert.match(python,/P2-NATIVE-DELIVER-CONSENT/);
 assert.match(python,/any\(home\.iterdir\(\)\)/);
 assert.match(python,/is_junction/);
 assert.match(python,/TestClient\(app\)\.post\(/);
 assert.match(python,/source\.read_bytes\(\) != CSV/);
 assert.match(python,/output\.write_text\(json\.dumps\(/);
 assert.doesNotMatch(python,/shutil\.rmtree|os\.remove|unlink\(|\btrain\(|\bfit\(/);
});

test('Windows entrypoint never starts installed release, modifies originals or installs packages',()=>{
 assert.match(bat,/Run_P2_Native_Deliver_Consent_Local\.ps1/);
 assert.match(ps,/qaTool init --phase P2-NATIVE-DELIVER-CONSENT --json/);
 assert.match(ps,/PILOTODIN_HOME=\$home/);
 assert.match(ps,/PILOTODIN_DESKTOP_SESSION/);
 assert.match(ps,/CARGO_NET_OFFLINE='true'/);
 assert.match(ps,/Port-Occupied 8000 -or Port-Occupied 5177/);
 assert.match(ps,/--host','127\.0\.0\.1','--port','8000'/);
 assert.match(ps,/--lifespan','off'/);
 assert.match(ps,/npm run desktop:dev -- --config src-tauri\/tauri\.p2-native-deliver-consent\.conf\.json/);
 assert.match(ps,/Test-Path -LiteralPath \(Join-Path \$frontend 'node_modules'\)/);
 assert.doesNotMatch(ps,/npm (?:ci|install)|pip install|cargo install|desktop:build|tauri build|Remove-Item.*?workspace/i);
});

test('owner native observations are explicit and no AI/PDF/font gate is accepted',()=>{
 for(const label of ['dirty_warning','explore_keep','new_project_keep','explore_leave','new_project_leave']){
  assert.match(ps,new RegExp("Owner-Check '"+label+"'"));
 }
 assert.match(ps,/OWNER_REPORTED_PASS_REVIEW_REQUIRED/);
 assert.match(ps,/product_acceptance='NOT_TESTED'/);
 assert.match(ps,/installer='NOT_BUILT'/);
 assert.match(ps,/models='NOT_LAUNCHED'/);
 assert.match(ps,/backend_writes='NO_MUTATION_REQUESTS_OBSERVED'/);
 assert.match(ps,/NO|No.*original/);
 assert.doesNotMatch(ps,/RELEASE_APPROVAL_STATUS|GRANTED_BY_INDEPENDENT_OWNER_REVIEW/);
});

test('runner records failure even on native process error and restores process env and owned backend',()=>{
 assert.match(ps,/if\(\$nativeCode -ne 0\)\{throw/);
 assert.match(ps,/if\(\$results -contains \$false\)\{throw/);
 assert.match(ps,/Get-FileHash -LiteralPath \$dataset -Algorithm SHA256/);
 assert.match(ps,/Stop-Process -Id \$backend\.Id -Force/);
 assert.match(ps,/foreach\(\$name in \$oldEnv\.Keys\)/);
 assert.match(ps,/finally\{/);
 assert.match(ps,/Compress-Archive -LiteralPath \$statusSources/);
 assert.doesNotMatch(ps,/Compress-Archive.*backendLog|Compress-Archive.*nativeLog/);
});
