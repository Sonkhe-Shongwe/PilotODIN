// CI source-only safeguard: no Tauri runtime, compilation or packaging.
const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const { spawnSync } = require("node:child_process");
const root = path.resolve(__dirname, "..");
const read = (p) => JSON.parse(fs.readFileSync(path.join(root, p), "utf8"));
const scripts = read("package.json").scripts;
const prod = read("src-tauri/tauri.conf.json");
const qa = read("src-tauri/tauri.p4-native-qa.conf.json");
const dev = read("src-tauri/tauri.p4-isolated-native-dev.conf.json");
test("native dev uses a distinct app-local data and WebView identity", () => {
  assert.equal(prod.identifier, "com.pilotodin.studio");
  assert.equal(qa.identifier, "com.pilotodin.p4nativeqa");
  assert.equal(dev.identifier, "com.pilotodin.p4isolatednativedev");
  assert.equal(new Set([prod.identifier, qa.identifier, dev.identifier]).size, 3);
  assert.equal(dev.app.windows[0].label, "main");
  assert.equal(dev.bundle.active, false);
  assert.deepEqual(dev.bundle.externalBin, []);
  assert.deepEqual(dev.bundle.resources, []);
  assert.equal(prod.app?.appDirectoriesOverride, undefined);
  assert.equal(dev.app?.appDirectoriesOverride, undefined);
  assert.equal(scripts["desktop:dev"], "node scripts/p4-isolated-native-dev.mjs");
});
test("production and isolated dev windows allow HTML workspace tab dragging on Windows", () => {
  for (const config of [prod, dev]) {
    const main = config.app.windows.find(window => window.label === "main");
    assert.equal(main?.dragDropEnabled, false);
  }
});
test("native dev refuses execution without separate local opt-in", () => {
  const p = spawnSync(process.execPath, ["scripts/p4-isolated-native-dev.mjs"], {
    cwd: root, encoding: "utf8",
    env: { ...process.env, PILOTODIN_P4_UNPACKAGED_NATIVE_DEV_CONSENT: "" }
  });
  assert.equal(p.status, 2);
  assert.match(p.stderr, /STOP: Native compilation is frozen/);
});
test("desktop build script refuses intermediate packaging", () => {
  assert.equal(scripts["desktop:build"], "node scripts/deny-intermediate-installer.mjs");
  const p = spawnSync(process.execPath, ["scripts/deny-intermediate-installer.mjs"], {cwd:root,encoding:"utf8"});
  assert.equal(p.status, 2);
  assert.match(p.stderr, /STOP: PilotODIN intermediate installer packaging remains frozen/);
});

test("legacy native compilation is not triggered by P4 development branch", () => {
  const yaml = fs.readFileSync(
    path.join(root, "..", ".github", "workflows", "native-windows-compile.yml"), "utf8"
  );
  assert.match(yaml, /branches:\s*\[build-e\]/);
  assert.doesNotMatch(yaml, /branches:\s*\[[^\]]*feature\/live-dev-workspace/);
});

test("raw default Tauri dev and build have source-level fail-closed hooks", () => {
  assert.equal(prod.build.beforeDevCommand, "node scripts/deny-unsafe-default-tauri-dev.mjs");
  assert.equal(prod.build.beforeBuildCommand, "node scripts/deny-intermediate-installer.mjs");
  assert.equal(dev.build.beforeDevCommand, "npm run dev");
  // Merge-patch semantics: isolated override replaces only dev hook;
  // production-identity default has no usable pre-dev server startup.
  const merged = { ...prod.build, ...dev.build };
  assert.equal(merged.beforeDevCommand, "npm run dev");
  assert.equal(merged.beforeBuildCommand, "node scripts/deny-intermediate-installer.mjs");
  const denial = spawnSync(process.execPath, ["scripts/deny-unsafe-default-tauri-dev.mjs"], {
    cwd: root, encoding: "utf8"
  });
  assert.equal(denial.status, 2);
  assert.match(denial.stderr, /STOP: Default Tauri native development uses PilotODIN production identity/);
  assert.equal(prod.identifier, "com.pilotodin.studio");
});


test("fixed native launch plan selects A4 only with exact relay and existing separate consent", async () => {
  const { nativeDevPlan } = await import("../scripts/native-dev-plan.mjs");
  const a4 = "src-tauri/tauri.native-a4-smoke.conf.json";
  const p4 = "src-tauri/tauri.p4-isolated-native-dev.conf.json";
  const consent = { PILOTODIN_P4_UNPACKAGED_NATIVE_DEV_CONSENT: "I_APPROVE_UNPACKAGED_P4_NATIVE_DEV" };
  const relay = { ...consent, PILOTODIN_A4_RELAY: "1", VITE_PILOTODIN_AUTH_DEV: "1", VITE_PILOTODIN_NATIVE_SMOKE: "1" };
  assert.deepEqual(nativeDevPlan([], consent, read), ["exec","--","tauri","dev","--config",p4]);
  assert.deepEqual(nativeDevPlan(["--config",a4], relay, read), ["exec","--","tauri","dev","--config",a4]);
  assert.throws(() => nativeDevPlan(["--config",a4], {}, () => {throw Error("must not read");}), /compilation is frozen/);
  for (const args of [["--config",p4],["--config","src-tauri/tauri.conf.json"],["--config",a4,"--release"],["--config","../"+a4],["--no-watch"]])
    assert.throws(() => nativeDevPlan(args, relay, read), /fixed isolated P4 default/);
  for (const change of [{PILOTODIN_A4_RELAY:"0"},{VITE_PILOTODIN_AUTH_DEV:"0"},{VITE_PILOTODIN_NATIVE_SMOKE:"0"},
    {PILOTODIN_HOME:"foreign"},{PILOTODIN_DEV_CAPABILITY:"private"},{PILOTODIN_HOSTED_NATIVE_AUTH:"1"}])
    assert.throws(() => nativeDevPlan(["--config",a4], {...relay,...change}, read), /separate authenticated relay|private serving configuration|fixed P4 launch/);
  assert.throws(() => nativeDevPlan([], relay, read), /A4 relay cannot use the P4 overlay/);
  for(const markers of [{VITE_PILOTODIN_NATIVE_SMOKE:"1"},{VITE_PILOTODIN_AUTH_DEV:"1"},
    {VITE_PILOTODIN_NATIVE_SMOKE:"1",VITE_PILOTODIN_AUTH_DEV:"1"}]){
    assert.throws(()=>nativeDevPlan([], {...consent,...markers},()=>{throw Error("unexpected config read");}),
      /Native smoke requires the authenticated A4 or hosted frontdoor/);
  }
  assert.throws(() => nativeDevPlan([], {...consent,TAURI_CONFIG:"{}"},read), /Inherited Tauri configuration/);
  for (const mutate of [
    config => {config.identifier = prod.identifier;},
    config => {config.bundle.active = true;},
    config => {config.app.appDirectoriesOverride = {};},
    config => {config.build.devUrl = "http://127.0.0.1:5173";},
    config => {config.build.beforeBuildCommand = "arbitrary";}
  ]) {
    const altered = p => {const config=read(p);if(p===a4)mutate(config);return config;};
    assert.throws(() => nativeDevPlan(["--config",a4],relay,altered));
  }
});


test("hosted P4 prestarted plan retains the isolated identity and excludes private service inputs", async () => {
  const {nativeDevPlan,assertNoPrivateServingEnvironment}=await import("../scripts/native-dev-plan.mjs");
  const hosted="src-tauri/tauri.p4-hosted-prestarted.conf.json";
  const env={CI:"true",GITHUB_ACTIONS:"true",RUNNER_OS:"Windows",
    RUNNER_ENVIRONMENT:"github-hosted",GITHUB_EVENT_NAME:"push",GITHUB_RUN_ATTEMPT:"1",
    GITHUB_REF_NAME:"feature/live-dev-workspace-20261023",GITHUB_RUN_ID:"123",
    RUNNER_TEMP:"D:\\runner\\temp",PILOTODIN_HOME:"D:\\runner\\temp\\P4-71-only-home-123",
    PILOTODIN_HOSTED_NATIVE_AUTH:"1",VITE_PILOTODIN_AUTH_DEV:"1",
    VITE_PILOTODIN_NATIVE_SMOKE:"1",PILOTODIN_P4_PRESTARTED_FRONTDOOR:"1",
    PILOTODIN_P4_UNPACKAGED_NATIVE_DEV_CONSENT:"I_APPROVE_UNPACKAGED_P4_NATIVE_DEV"};
  assert.deepEqual(nativeDevPlan([],env,read),["exec","--","tauri","dev","--config",hosted]);
  const original=read("src-tauri/tauri.p4-isolated-native-dev.conf.json");
  const selected=read(hosted);
  assert.deepEqual(selected,{...original,build:{beforeDevCommand:{script:"node scripts/verify-hosted-native-frontdoor.mjs",wait:true}}});
  for(const change of [{PILOTODIN_DEV_CAPABILITY:"private"},{pilotodin_dev_capability:"private"},
    {PILOTODIN_DEV_ORIGIN:"http://127.0.0.1:5173"},{PILOTODIN_DEV_PORT:"8000"},
    {PILOTODIN_SERVER_MODE:"hosted-fixture"},{PILOTODIN_DESKTOP_SESSION:"private"},{PILOTODIN_CONTROL_CAPABILITY:"private"}]){
    assert.throws(()=>nativeDevPlan([],{...env,...change},()=>{throw Error("unexpected config read");}),/private serving configuration/);
    assert.throws(()=>assertNoPrivateServingEnvironment(change),/private serving configuration/);
  }
  assert.doesNotThrow(()=>assertNoPrivateServingEnvironment({PILOTODIN_DESKTOP_ALLOW_DEV:"0"}));
  for(const change of [{PILOTODIN_P4_UNPACKAGED_NATIVE_DEV_CONSENT:""},{PILOTODIN_P4_PRESTARTED_FRONTDOOR:"0"},
    {PILOTODIN_HOSTED_NATIVE_AUTH:"0"},{VITE_PILOTODIN_AUTH_DEV:"0"},{VITE_PILOTODIN_NATIVE_SMOKE:"0"},
    {GITHUB_RUN_ATTEMPT:"2"},{RUNNER_OS:"Linux"},{RUNNER_ENVIRONMENT:"self-hosted"},
    {GITHUB_EVENT_NAME:"workflow_dispatch"},{GITHUB_RUN_ID:"124"},{PILOTODIN_HOME:"D:\\foreign\\P4-71-only-home-123"},
    {PILOTODIN_HOME:"D:\\runner\\temp\\..\\temp\\P4-71-only-home-123"},
    {PILOTODIN_A4_RELAY:"1"},{VITE_PILOTODIN_P2_FULL_STACK:"1"},{TAURI_CONFIG:"{}"}])
    assert.throws(()=>nativeDevPlan([],{...env,...change},read));
  for(const args of [["--config",hosted],["--config","src-tauri/tauri.native-a4-smoke.conf.json"],["--release"]])
    assert.throws(()=>nativeDevPlan(args,env,read));
  for(const mutate of [c=>{c.identifier="com.pilotodin.studio";},c=>{c.bundle.active=true;},
    c=>{c.app.appDirectoriesOverride={};},c=>{c.build.beforeDevCommand.wait=false;},
    c=>{c.build.beforeDevCommand.script="npm run dev";},c=>{c.build.devUrl="http://127.0.0.1:8000";}])
    assert.throws(()=>nativeDevPlan([],env,p=>{const c=read(p);if(p===hosted)mutate(c);return c;}),/differs from the isolated P4 profile/);
  // Run only the refusal branch, never a live hook request or native execution.
  const refused=spawnSync(process.execPath,["scripts/verify-hosted-native-frontdoor.mjs"],{
    cwd:root,encoding:"utf8",env:{...process.env,PILOTODIN_P4_UNPACKAGED_NATIVE_DEV_CONSENT:""}
  });
  assert.equal(refused.status,2);
  assert.match(refused.stderr,/hosted native frontdoor verification refused/);
});

test("hosted runner clears private serving inputs before native, probe, relaunch and cleanup",()=>{
  const src=fs.readFileSync(path.join(root,"..","qa","p4_native","Run_P4_71_Disposable_Windows.ps1"),"utf8");
  const backend=src.indexOf("$backend = Start-Process -FilePath 'python.exe'");
  const vite=src.indexOf("$devServer = Start-Process -FilePath 'node.exe'");
  const clear=src.indexOf("\n Clear-PrivateServingInputs\n Assert-PublicNativeEnvironment",vite);
  const native=src.indexOf("$native = Start-Process -FilePath 'cmd.exe'");
  assert.ok(backend>0&&backend<vite&&vite<clear&&clear<native);
  assert.equal(src.match(/\$devServer = Start-Process/g).length,1);
  assert.match(src,/--port','5173','--strictPort'/);
  assert.match(src,/Test-OwnedLoopbackListener \$backend 8000/);
  assert.match(src,/Test-OwnedLoopbackListener \$devServer 5173/);
  assert.match(src,/LocalAddress -ceq '127\.0\.0\.1'/);
  assert.match(src,/OwningProcess -eq \$process\.Id/);
  assert.match(src,/Create\('http:\/\/127\.0\.0\.1:5173\/api\/health'\)/);
  assert.match(src,/Headers\.Add\('X-PilotODIN-Dev-Request','1'\)/);
  assert.match(src,/Assert-PublicNativeEnvironment\s+if\(-not \(Test-OwnedFrontdoor\)\)\{Fail 'Owned authenticated Vite unavailable before probe'\}/);
  assert.match(src,/Assert-PublicNativeEnvironment\s+\$reopened = Start-Process/);
  assert.match(src,/Original authenticated Vite unavailable for relaunch/);
  assert.match(src,/finally \{\s+# Clear before starting any cleanup command[^\n]*\n Clear-PrivateServingInputs/);
  const hook=fs.readFileSync(path.join(root,"scripts","verify-hosted-native-frontdoor.mjs"),"utf8");
  assert.doesNotMatch(hook,/PILOTODIN_DEV_CAPABILITY|child_process|8000/);
  assert.match(hook,/redirect:"error"/);
  assert.match(hook,/assertHostedFrontdoorContext\(process\.env\)/);
});


test("historical environment opt-in cannot reactivate native compilation", () => {
  const p = spawnSync(process.execPath, ["scripts/p4-isolated-native-dev.mjs"], {
    cwd: root, encoding: "utf8",
    env: { ...process.env, PILOTODIN_P4_UNPACKAGED_NATIVE_DEV_CONSENT: "I_APPROVE_UNPACKAGED_P4_NATIVE_DEV" }
  });
  assert.equal(p.status, 2);
  assert.match(p.stderr, /STOP: Native compilation is frozen/);
});
