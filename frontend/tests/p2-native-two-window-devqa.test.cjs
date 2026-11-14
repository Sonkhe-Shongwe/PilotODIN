const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const ts=require('typescript');
const root=path.resolve(__dirname,'../..');
const read=p=>fs.readFileSync(path.join(root,p),'utf8');
const config=JSON.parse(read('frontend/src-tauri/tauri.p2-native-two-window.conf.json'));
const peer=read('frontend/src/p2NativeTwoWindowPeer.ts');
const html=read('frontend/p2_native_two_window_peer.html');
const runner=read('tools/Run_P2_Native_Two_Window_Local.ps1');
const seed=read('tools/Seed_P2_Native_Two_Window_Local.py');
const bat=read('Run_PilotODIN_P2_Native_Two_Window.bat');

test('two native windows share the same test-only origin; no installer or models',()=>{
 assert.equal(config.identifier,'com.pilotodin.p2twowindowqa');
 assert.equal(config.build.devUrl,'http://127.0.0.1:5177/p2_native_deliver_consent_qa.html');
 assert.deepEqual(config.app.windows.map(x=>x.label),['main','qapeer']);
 assert.deepEqual(config.app.windows.map(x=>x.url),[
  'http://127.0.0.1:5177/p2_native_deliver_consent_qa.html',
  'http://127.0.0.1:5177/p2_native_two_window_peer.html'
 ]);
 assert.equal(config.bundle.active,false);
 assert.deepEqual(config.bundle.externalBin,[]);
 assert.deepEqual(config.bundle.resources,[]);
});

test('peer native/dev identity gate and exactly one deliberate project selector write',()=>{
 const result=ts.transpileModule(peer,{compilerOptions:{module:ts.ModuleKind.ESNext,target:ts.ScriptTarget.ES2022},reportDiagnostics:true});
 assert.equal((result.diagnostics||[]).filter(d=>d.category===ts.DiagnosticCategory.Error).length,0);
 assert.match(peer,/import\.meta\.env\.DEV&&/);
 for(const flag of ['VITE_P2_NATIVE_TWO_WINDOW_QA','VITE_P2_NATIVE_DELIVER_QA','VITE_PILOTODIN_NATIVE_SMOKE'])
  assert.ok(peer.includes('import.meta.env.'+flag+"==='1'"),flag);
 assert.match(peer,/location\.origin==='http:\/\/127\.0\.0\.1:5177'/);
 assert.match(peer,/isDesktop\(\)/);
 assert.match(peer,/projectA!==projectB/);
 assert.match(peer,/button\.addEventListener\('click',\(\)=>\{/);
 assert.equal((peer.match(/localStorage\.setItem\(/g)||[]).length,1);
 assert.match(peer,/localStorage\.setItem\('pilotodin-current',projectB\)/);
 assert.doesNotMatch(peer,/fetch\(|XMLHttpRequest|invoke\(|post\(|upload\(|dispatchEvent\(new StorageEvent/);
 assert.match(html,/src="\/src\/p2NativeTwoWindowPeer\.ts"/);
});

test('synthetic seeder refuses nonempty or redirected workspaces and verifies two CSV hashes',()=>{
 assert.match(seed,/PHASE = "P2-NATIVE-TWO-WINDOW-DELIVER"/);
 assert.equal((seed.match(/p2-two-window-[AB]-synthetic\.csv/g)||[]).length,2);
 assert.match(seed,/any\(home\.iterdir\(\)\)/);
 assert.match(seed,/fixture\.exists\(\)/);
 assert.match(seed,/is_symlink\(\)/);
 assert.match(seed,/is_relative_to\(\(home \/ "datasets"\)\.resolve\(\)\)/);
 assert.match(seed,/source\.read_bytes\(\) != csv/);
 assert.match(seed,/hashlib\.sha256\(csv\)\.hexdigest\(\)/);
 assert.doesNotMatch(seed,/rmtree|unlink\(|shutil\.move|model\.train/);
});

test('PowerShell launcher enforces safe local ports, no install, scoped cleanup and status archive',()=>{
 assert.match(runner,/Port-Occupied 8000 -or Port-Occupied 5177/);
 assert.match(runner,/PILOTODIN_HOME=\$isolatedWorkspaceHome/);
 assert.match(runner,/VITE_P2_NATIVE_TWO_WINDOW_QA='1'/);
 assert.match(runner,/CARGO_NET_OFFLINE='true'/);
 assert.match(runner,/\& \$npm run build/);
 assert.match(runner,/\& \$npm run desktop:dev -- --config src-tauri\/tauri\.p2-native-two-window\.conf\.json/);
 assert.match(runner,/Stop-Process -Id \$backend\.Id/);
 assert.match(runner,/Compress-Archive -LiteralPath @\(\$resultFile,\$qaManifest,\$fixture\)/);
 assert.doesNotMatch(runner,/npm (install|ci)|cargo install|pyinstaller|tauri build|rm -rf|Remove-Item[^\n]*-Recurse|Stop-Process -Name/);
 assert.doesNotMatch(runner,/\$(?:home|host|pid|profile|input|matches|error)\s*=/i);
 assert.match(bat,/tools\\Run_P2_Native_Two_Window_Local\.ps1/);
});

test('no fake browser storage event or release-acceptance claim',()=>{
 assert.doesNotMatch(peer,/dispatchEvent\(new (StorageEvent|Event)/);
 assert.match(runner,/backend_writes='NO_MUTATION_REQUESTS_OBSERVED'/);
 assert.match(runner,/OWNER_REPORTED_PASS/);
 assert.match(runner,/product_acceptance='NOT_TESTED'/);
 assert.match(runner,/state='REVIEW_REQUIRED'/);
 assert.match(runner,/source_head='NOT_ATTESTED'/);
});
