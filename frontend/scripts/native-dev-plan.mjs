// Pure source-only launch planning; never spawns, reads environment or touches disk.
import {win32} from "node:path";
const P4 = "src-tauri/tauri.p4-isolated-native-dev.conf.json";
const HOSTED = "src-tauri/tauri.p4-hosted-prestarted.conf.json";
const HOSTED_HOOK = Object.freeze({script:"node scripts/verify-hosted-native-frontdoor.mjs",wait:true});
const A4 = "src-tauri/tauri.native-a4-smoke.conf.json";
const CONSENT = "I_APPROVE_UNPACKAGED_P4_NATIVE_DEV";

export function assertNoPrivateServingEnvironment(env) {
  if (Object.entries(env).some(([key,value]) => value &&
      !(key.toUpperCase()==="PILOTODIN_DESKTOP_ALLOW_DEV" && value==="0") &&
      (/^PILOTODIN_(?:DEV_|DESKTOP_|CONTROL_)/i.test(key) ||
       key.toUpperCase()==="PILOTODIN_SERVER_MODE")))
    throw new Error("Native process must not inherit private serving configuration.");
}

export function assertHostedFrontdoorContext(env) {
  if (env.PILOTODIN_P4_UNPACKAGED_NATIVE_DEV_CONSENT !== CONSENT)
    throw new Error("Native compilation is frozen pending separate explicit owner approval.");
  assertNoPrivateServingEnvironment(env);
  const required = {CI:"true",GITHUB_ACTIONS:"true",RUNNER_OS:"Windows",
    RUNNER_ENVIRONMENT:"github-hosted",GITHUB_EVENT_NAME:"push",GITHUB_RUN_ATTEMPT:"1",
    GITHUB_REF_NAME:"feature/live-dev-workspace-20261023",PILOTODIN_HOSTED_NATIVE_AUTH:"1",
    VITE_PILOTODIN_AUTH_DEV:"1",VITE_PILOTODIN_NATIVE_SMOKE:"1",
    PILOTODIN_P4_PRESTARTED_FRONTDOOR:"1"};
  const root=env.RUNNER_TEMP??"",home=env.PILOTODIN_HOME??"";
  if (Object.entries(required).some(([key,value])=>env[key]!==value) ||
      !/^[0-9]+$/.test(env.GITHUB_RUN_ID??"") ||
      !win32.isAbsolute(root)||!win32.isAbsolute(home)||
      !/^[A-Za-z]:[\\/]/.test(root)||!(/^[A-Za-z]:[\\/]/.test(home))||
      root.split(/[\\/]/).includes("..")||home.split(/[\\/]/).includes("..")||
      win32.normalize(home)!==win32.join(root,"P4-71-only-home-"+env.GITHUB_RUN_ID)||
      env.P1_REAL_HTTP_E2E||env.PILOTODIN_A4_RELAY!==undefined||
      env.VITE_PILOTODIN_P2_FULL_STACK!==undefined)
    throw new Error("Invalid hosted prestarted native frontdoor configuration.");
}

export function nativeDevPlan(args, env, read) {
  if (env.PILOTODIN_P4_UNPACKAGED_NATIVE_DEV_CONSENT !== CONSENT)
    throw new Error("Native compilation is frozen pending separate explicit owner approval. Use the isolated browser-only Live Dev launcher instead.");
  if (env.TAURI_CONFIG || env.TAURI_CONFIG_PATH)
    throw new Error("Inherited Tauri configuration is not permitted.");
  assertNoPrivateServingEnvironment(env);
  const a4 = args.length === 2 && args[0] === "--config" && args[1] === A4;
  const hosted = env.PILOTODIN_P4_PRESTARTED_FRONTDOOR !== undefined ||
    env.PILOTODIN_HOSTED_NATIVE_AUTH !== undefined;
  if (hosted) {
    if (a4 || args.length !== 0) throw new Error("Hosted frontdoor requires the fixed P4 launch.");
    assertHostedFrontdoorContext(env);
  }
  if (args.length !== 0 && !a4)
    throw new Error("Only the fixed isolated P4 default or exact A4 overlay is permitted.");
  if (a4) {
    if (env.PILOTODIN_A4_RELAY !== "1" || env.VITE_PILOTODIN_AUTH_DEV !== "1" ||
        env.VITE_PILOTODIN_NATIVE_SMOKE !== "1" ||
        ["PILOTODIN_HOME","PILOTODIN_SERVER_MODE","PILOTODIN_HOSTED_NATIVE_AUTH",
         "PILOTODIN_DEV_CAPABILITY","PILOTODIN_DEV_ORIGIN","PILOTODIN_DEV_PORT",
         "PILOTODIN_DESKTOP_SESSION","PILOTODIN_DESKTOP_PORT","PILOTODIN_DESKTOP_WATCH_STDIN",
         "PILOTODIN_CONTROL_MODE","PILOTODIN_CONTROL_GENERATION","PILOTODIN_CONTROL_CAPABILITY",
         "P1_REAL_HTTP_E2E"].some(key => env[key]) ||
        (env.PILOTODIN_DESKTOP_ALLOW_DEV ?? "0") !== "0")
      throw new Error("A4 requires its separate authenticated relay without inherited serving credentials.");
  } else if (env.PILOTODIN_A4_RELAY !== undefined) {
    throw new Error("A4 relay cannot use the P4 overlay.");
  }
  const production = read("src-tauri/tauri.conf.json");
  const qa = read("src-tauri/tauri.p4-native-qa.conf.json");
  const isolated = read(P4);
  const smoke = read(A4);
  const expected = ["com.pilotodin.studio","com.pilotodin.p4nativeqa",
                    "com.pilotodin.p4isolatednativedev","com.pilotodin.a4smoke"];
  const configs = [production, qa, isolated, smoke];
  if (configs.some((config, i) => config?.identifier !== expected[i]) ||
      new Set(configs.map(config => config.identifier.toLowerCase())).size !== 4)
    throw new Error("Tauri data identities overlap or have unexpected values.");
  if (configs.some(config => config.app && Object.hasOwn(config.app,"appDirectoriesOverride")) ||
      [isolated, smoke].some(config =>
        config.bundle?.active !== false ||
        !Array.isArray(config.bundle.externalBin) || config.bundle.externalBin.length ||
        !Array.isArray(config.bundle.resources) || config.bundle.resources.length ||
        Object.keys(config.bundle).some(key => !["active","externalBin","resources"].includes(key)) ||
        !Array.isArray(config.app?.windows) || config.app.windows.length !== 1 ||
        config.app.windows[0].label !== "main"))
    throw new Error("App-data override or packaging config violates isolated-dev safeguards.");
  if (production.build?.beforeDevCommand !== "node scripts/deny-unsafe-default-tauri-dev.mjs" ||
      production.build?.beforeBuildCommand !== "node scripts/deny-intermediate-installer.mjs" ||
      production.build?.devUrl !== "http://127.0.0.1:5173" ||
      isolated.build?.beforeDevCommand !== "npm run dev" ||
      Object.keys(isolated.build).length !== 1 ||
      smoke.build?.beforeDevCommand !== "npm run dev -- --port 5174" ||
      smoke.build?.devUrl !== "http://127.0.0.1:5174" ||
      Object.keys(smoke.build).length !== 2)
    throw new Error("Native dev hooks or fixed origins differ from reviewed source.");
  if (hosted) {
    const prestarted = read(HOSTED);
    const expected = {...isolated,build:{beforeDevCommand:HOSTED_HOOK}};
    // Same app identity, window, bundle and all other keys. The sole
    // intentional difference is a synchronous verification-only dev hook.
    if (JSON.stringify(prestarted)!==JSON.stringify(expected))
      throw new Error("Hosted prestarted overlay differs from the isolated P4 profile.");
  }
  // Never forward caller arguments: select one immutable repository path.
  return Object.freeze(["exec","--","tauri","dev","--config",a4 ? A4 : hosted ? HOSTED : P4]);
}
