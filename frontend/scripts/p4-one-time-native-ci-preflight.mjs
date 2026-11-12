// One-time P4 Windows acceptance: read-only config + hosted runner preflight.
// This program is deliberately unable to initiate native compilation.
import { readFileSync, existsSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join, resolve } from "node:path";
const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const die = (why) => { console.error("P4 PREFLIGHT STOP: " + why); process.exit(2); };
const check = (ok, why) => { if (!ok) die(why); };
const read = (f) => JSON.parse(readFileSync(join(root, f), "utf8"));

check(process.platform === "win32", "This native exercise requires a Windows runner.");
check(process.env.GITHUB_ACTIONS === "true" &&
  process.env.RUNNER_ENVIRONMENT === "github-hosted",
  "Refuse local, self-hosted or unidentified runner; owner hardware is prohibited.");
check(process.env.GITHUB_EVENT_NAME === "push" &&
  process.env.GITHUB_REF_NAME === "feature/live-dev-workspace-20261023" &&
  process.env.GITHUB_RUN_ATTEMPT === "1",
  "Only the original one-time approved push on the development branch is allowed.");
const local = process.env.LOCALAPPDATA;
const roaming = process.env.APPDATA;
check(local && roaming && process.env.RUNNER_TEMP && process.env.GITHUB_SHA,
  "Windows profile, runner temp or source SHA unavailable.");
const production = read("src-tauri/tauri.conf.json");
const oldQa = read("src-tauri/tauri.p4-native-qa.conf.json");
const dev = read("src-tauri/tauri.p4-isolated-native-dev.conf.json");
const ci = read("src-tauri/tauri.p4-one-time-unpackaged-ci.conf.json");
const ids = [production.identifier, oldQa.identifier, dev.identifier, ci.identifier];
check(ids[0] === "com.pilotodin.studio" &&
  ids[1] === "com.pilotodin.p4nativeqa" &&
  ids[2] === "com.pilotodin.p4isolatednativedev" && ids[3] === ids[2],
  "Unexpected production, historic QA or one-time native identity.");
check(new Set(ids.slice(0,3).map(x => x.toLowerCase())).size === 3,
  "Native identity aliases production or the installed QA app.");
for (const [name, value] of [["production", production], ["old QA", oldQa], ["dev", dev], ["one-time", ci]]) {
  check(!value.app?.appDirectoriesOverride &&
    !value.app?.windows?.some(w => w.dataDirectory),
    name + " sets a custom app/WebView storage directory.");
}
check(ci.bundle?.active === false &&
  Array.isArray(ci.bundle.externalBin) && ci.bundle.externalBin.length === 0 &&
  Array.isArray(ci.bundle.resources) && ci.bundle.resources.length === 0,
  "One-time native test must be unbundled and resource/sidecar-free.");
check(ci.build?.beforeBuildCommand === "npm run build" &&
  ci.build?.beforeDevCommand === "node scripts/deny-unsafe-default-tauri-dev.mjs" &&
  production.build?.beforeBuildCommand === "node scripts/deny-intermediate-installer.mjs" &&
  production.build?.beforeDevCommand === "node scripts/deny-unsafe-default-tauri-dev.mjs",
  "Build hooks differ from reviewed isolated compile/production refusal.");
const rust = readFileSync(join(root, "src-tauri/src/lib.rs"), "utf8");
check(rust.includes('app.path().app_local_data_dir().map_err(|e| e.to_string())?.join("data")') &&
  rust.includes('.env("PILOTODIN_HOME", data_dir.to_string_lossy().to_string())'),
  "Rust backend home path no longer follows the isolated Tauri identity.");
check(!process.env.PILOTODIN_HOME,
  "An inherited user or production storage root is not permitted.");
for (const base of [local, roaming]) {
  for (const name of [production.identifier, oldQa.identifier]) {
    check(!existsSync(join(base, name)),
      "Hosted runner unexpectedly contains a protected original/installed QA app-data directory.");
  }
}
const workflow = readFileSync(join(root, "../.github/workflows/p4-once-isolated-native-acceptance.yml"), "utf8");
check(workflow.includes("tauri build --no-bundle") &&
  !workflow.includes("actions/upload-artifact") &&
  !workflow.includes("tauri bundle") &&
  workflow.includes("needs: p4-preflight") &&
  workflow.includes("github.run_attempt == 1"),
  "One-time workflow build/publishing restrictions changed.");
console.log("P4 PREFLIGHT PASS: GitHub-hosted disposable Windows runner, separate source identifiers, isolated WebView/app data, no original/QA directories, no installer, no model resources; source SHA " + process.env.GITHUB_SHA);
