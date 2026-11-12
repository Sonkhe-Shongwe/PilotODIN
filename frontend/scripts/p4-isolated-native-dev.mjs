// P4-R06 safety gate. Native development compiles a new executable.
// An explicit owner decision is necessary, independent of this local opt-in.
import { readFileSync } from "node:fs";
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
const root = join(dirname(fileURLToPath(import.meta.url)), "..");
function stop(why) { console.error("STOP: " + why); process.exit(2); }
if (process.env.PILOTODIN_P4_UNPACKAGED_NATIVE_DEV_CONSENT !==
    "I_APPROVE_UNPACKAGED_P4_NATIVE_DEV") {
  stop("Native compilation is frozen pending separate explicit owner approval. Use the isolated browser-only Live Dev launcher instead.");
}
const read = (p) => JSON.parse(readFileSync(join(root, p), "utf8"));
const production = read("src-tauri/tauri.conf.json");
const qa = read("src-tauri/tauri.p4-native-qa.conf.json");
const isolated = read("src-tauri/tauri.p4-isolated-native-dev.conf.json");
const identifiers = [production.identifier, qa.identifier, isolated.identifier];
if (identifiers.some((s) => !s || typeof s !== "string") ||
    new Set(identifiers.map((s) => s.toLowerCase())).size !== 3 ||
    isolated.identifier !== "com.pilotodin.p4isolatednativedev") {
  stop("Tauri data identities overlap or have unexpected values.");
}
if (production.app?.appDirectoriesOverride || isolated.app?.appDirectoriesOverride ||
    isolated.bundle?.active !== false ||
    !Array.isArray(isolated.bundle.externalBin) || isolated.bundle.externalBin.length ||
    !Array.isArray(isolated.bundle.resources) || isolated.bundle.resources.length) {
  stop("App-data override or packaging config violates isolated-dev safeguards.");
}
// Future opt-in only. Not executed, compiled or authorised in P4-44.
const command = process.platform === "win32" ? "npm.cmd" : "npm";
const result = spawnSync(command, ["exec", "--", "tauri", "dev", "--config",
  "src-tauri/tauri.p4-isolated-native-dev.conf.json"], {
  cwd: root, stdio: "inherit", shell: process.platform === "win32"
});
if (result.error) stop("Tauri developer command could not start: " + result.error.message);
process.exit(result.status ?? 1);
