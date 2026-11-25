// P4-R06 safety gate. Native development compiles a new executable.
// An explicit owner decision is necessary, independent of this local opt-in.
import { readFileSync } from "node:fs";
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import { nativeDevPlan } from "./native-dev-plan.mjs";
const root = join(dirname(fileURLToPath(import.meta.url)), "..");
function stop(why) { console.error("STOP: " + why); process.exit(2); }
if (process.env.PILOTODIN_P4_UNPACKAGED_NATIVE_DEV_CONSENT !==
    "I_APPROVE_UNPACKAGED_P4_NATIVE_DEV") {
  stop("Native compilation is frozen pending separate explicit owner approval. Use the isolated browser-only Live Dev launcher instead.");
}
const read = (p) => JSON.parse(readFileSync(join(root, p), "utf8"));
let args;
try { args = nativeDevPlan(process.argv.slice(2), process.env, read); }
catch (error) { stop(error.message); }
// Future opt-in only. Source planning is not native compilation approval.
const command = process.platform === "win32" ? "npm.cmd" : "npm";
const result = spawnSync(command, args, {
  cwd: root, stdio: "inherit", shell: process.platform === "win32"
});
if (result.error) stop("Tauri developer command could not start: " + result.error.message);
process.exit(result.status ?? 1);
