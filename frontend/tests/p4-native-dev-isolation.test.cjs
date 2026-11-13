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
