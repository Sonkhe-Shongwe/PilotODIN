// Pure source-only launch planning; never spawns, reads environment or touches disk.
const P4 = "src-tauri/tauri.p4-isolated-native-dev.conf.json";
const A4 = "src-tauri/tauri.native-a4-smoke.conf.json";
const CONSENT = "I_APPROVE_UNPACKAGED_P4_NATIVE_DEV";

export function nativeDevPlan(args, env, read) {
  if (env.PILOTODIN_P4_UNPACKAGED_NATIVE_DEV_CONSENT !== CONSENT)
    throw new Error("Native compilation is frozen pending separate explicit owner approval. Use the isolated browser-only Live Dev launcher instead.");
  if (env.TAURI_CONFIG || env.TAURI_CONFIG_PATH)
    throw new Error("Inherited Tauri configuration is not permitted.");
  const a4 = args.length === 2 && args[0] === "--config" && args[1] === A4;
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
  // Never forward caller arguments: select one immutable repository path.
  return Object.freeze(["exec","--","tauri","dev","--config",a4 ? A4 : P4]);
}
