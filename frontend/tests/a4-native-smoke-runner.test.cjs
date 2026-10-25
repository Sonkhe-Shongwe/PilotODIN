const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const base=path.join(__dirname,'..');
const read=(p)=>fs.readFileSync(path.join(base,p),'utf8');

test('Vite ImportMetaEnv is explicitly available to the strict frontend TS build',()=>{
 const declarations=read('src/vite-env.d.ts');
 const tsconfig=JSON.parse(read('tsconfig.json'));
 assert.match(declarations,/\/\/\/ <reference types="vite\/client" \/>/);
 assert.match(declarations,/interface ImportMetaEnv/);
 assert.match(declarations,/VITE_PILOTODIN_NATIVE_SMOKE\?: string/);
 assert.ok(tsconfig.include.includes('src'));
});

test('A4 native smoke mode is enabled only for Vite DEV and exact opt-in variable',()=>{
 const bootstrap=read('src/desktopBootstrap.ts');
 assert.match(bootstrap,/import\.meta\.env\.DEV && import\.meta\.env\.VITE_PILOTODIN_NATIVE_SMOKE === '1'/);
 assert.match(bootstrap,/if \(isNativeA4SmokeMode\(\)\)/);
 assert.match(bootstrap,/if \(!isDesktop\(\)\) return;/);
 assert.match(bootstrap,/const connection = await invoke<DesktopConnection>\('launch_backend'\)/);
});

test('A4 native debug overlay never modifies bundling or release resources',()=>{
 const overlay=JSON.parse(read('src-tauri/tauri.native-a4-smoke.conf.json'));
 const release=JSON.parse(read('src-tauri/tauri.conf.json'));
 assert.equal(overlay.build.devUrl,'http://127.0.0.1:5174');
 assert.match(overlay.build.beforeDevCommand,/--port 5174/);
 assert.equal(overlay.bundle.active,false);
 assert.deepEqual(overlay.bundle.externalBin,[]);
 assert.deepEqual(overlay.bundle.resources,[]);
 assert.notEqual(overlay.identifier,release.identifier);
 assert.equal(release.bundle.active,true);
 assert.ok(release.bundle.externalBin.length>0);
 assert.ok(Object.keys(release.bundle.resources).length>0);
});

test('A4 Windows runner checks native prerequisites and includes regression diagnostics',()=>{
 const script=fs.readFileSync(path.join(base,'..','tools','Verify_A4_Native_Windows.ps1'),'utf8');
 const launcher=fs.readFileSync(path.join(base,'..','Run_PilotODIN_A4_Native_Smoke.bat'),'utf8');
 assert.match(script,/rustc\.exe/);
 assert.match(script,/cargo\.exe/);
 assert.match(script,/http:\/\/127\.0\.0\.1:8000\/api\/health/);
 assert.match(script,/Port-Open 5174/);
 assert.match(script,/Verify_P0_A4_Readiness\.py/);
 assert.match(script,/VITE_PILOTODIN_NATIVE_SMOKE='1'/);
 assert.match(script,/npm\.cmd/);
 assert.match(script,/src-tauri\/tauri\.native-a4-smoke\.conf\.json/);
 assert.match(script,/Compress-Archive/);
 assert.match(script,/Ask-Result/);
 assert.match(launcher,/Verify_A4_Native_Windows\.ps1/);
 assert.doesNotMatch(script,/Build_Windows_Installer|Stage_Bundled_Inference|Stage_Pinned_Offline_AI/);
});


test('A4 native runner does not abort PowerShell 5.1 on normal Tauri STDERR status',()=>{
 const script=fs.readFileSync(path.join(base,'..','tools','Verify_A4_Native_Windows.ps1'),'utf8');
 assert.match(script,/PowerShell 5\.1/);
 assert.match(script,/\$previousErrorActionPreference=\$ErrorActionPreference/);
 assert.match(script,/\$ErrorActionPreference='Continue'/);
 assert.match(script,/2>&1 \| Tee-Object -FilePath \$log/);
 assert.match(script,/\$exitCode=if\(\$null -eq \$LASTEXITCODE\)\{1\}else\{\[int\]\$LASTEXITCODE\}/);
 assert.match(script,/\$ErrorActionPreference=\$previousErrorActionPreference/);
 assert.match(script,/Launcher exception:/);
});


test('A4 checks Microsoft MSVC linker before expensive regression and Tauri build',()=>{
 const script=fs.readFileSync(path.join(base,'..','tools','Verify_A4_Native_Windows.ps1'),'utf8');
 assert.match(script,/function Find-MsvcLinker/);
 assert.match(script,/VC\\Tools\\MSVC/);
 assert.match(script,/bin\\Hostx64\\x64\\link\.exe/);
 assert.match(script,/vswhere\.exe/);
 assert.match(script,/msvc_linker_found/);
 assert.match(script,/Desktop development with C\+\+/);
 const linkerCheck=script.indexOf('$msvcLinker=Find-MsvcLinker');
 const regressions=script.indexOf("Running the ONE consolidated A2/A3/A4 regression gate");
 const cargoStart=script.indexOf('& $npm run desktop:dev');
 assert.ok(linkerCheck>=0&&linkerCheck<regressions&&regressions<cargoStart,
           'MSVC checks must happen before all expensive test and Cargo work');
});
