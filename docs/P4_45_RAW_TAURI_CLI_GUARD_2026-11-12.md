# PilotODIN 1.0 | P4-45 Raw Tauri development and build pre-hook guard

**Date:** 12 November 2026. **Phase:** P4 ACTIVE. **Risk:** P4-R06 prospective protection, not historical preservation closure. **Installer and native executable freeze:** in force.

## Confirmed source bypass

P4-44 replaced two npm scripts with explicit default-deny Node launchers, avoiding a normal unguarded `tauri dev` run with the original Tauri identifier. However, a developer could still invoke the Tauri CLI **directly**. Source `frontend/src-tauri/tauri.conf.json` previously had `identifier=com.pilotodin.studio`, `build.beforeDevCommand=npm run dev`, `build.beforeBuildCommand=npm run build`. With no additional config override, the default native dev identity is production; Rust backend uses app-local-data `/data` as `PILOTODIN_HOME`. This is a potential way to reach the original app's data/profile roots. It **does not establish that the owner or the QA build invoked raw Tauri, or attribute any historic file write**.

## Narrow mitigation without native compilation

[Code commit `54d2bce6e4a8192689a6c37e438f2ee9a24fc423`](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/54d2bce6e4a8192689a6c37e438f2ee9a24fc423) changes only:
1. `frontend/src-tauri/tauri.conf.json`: before-dev hook defaults to new `node scripts/deny-unsafe-default-tauri-dev.mjs`; before-build hook defaults to existing installer refusal. Production identity remains `com.pilotodin.studio` to avoid an accidental release identity or migration change.
2. `frontend/scripts/deny-unsafe-default-tauri-dev.mjs`: exits nonzero before an ordinary raw Tauri dev flow starts native work, with an explicit refusal message.
3. `frontend/src-tauri/tauri.p4-isolated-native-dev.conf.json`: replaces the pre-dev hook **only** with frontend development server `npm run dev`, retaining different identifier `com.pilotodin.p4isolatednativedev` and no bundled resources/external executables. Isolated command remains denied by the P4-44 Node guard until independent explicit owner approval and opt-in.
4. `frontend/tests/p4-native-dev-isolation.test.cjs`: source-level contracts for identity separation, merged default-deny raw dev/build hooks, and direct execution of the refusal script. No Tauri CLI runtime is executed.
5. `.github/workflows/p4-target-ranking.yml` includes changed source/config/test paths in existing source-only CI.
6. `docs/LIVE_DEVELOPMENT.md` explains the default-deny hooks and their limits.

Tauri v2's config merge semantics allow `--config` to override pre-dev command and identifier. Command-line options may likewise override hooks. These safeguards deter accidental invocation via the repository's **default** config and scripts; they **do not constitute mandatory OS-level access denial**. `npm run build` (frontend TypeScript/Vite) remains normal and is not a desktop installer operation. Raw `tauri build` using the normal config fails its hook but a custom override could bypass it; owner restriction still applies. No new native compilation or installer was authorised or run.

## Verification

- [P4 source-only Actions #43154963023](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/43154963023), exact `54d2bce6`: **COMPLETED SUCCESS 3/3 jobs**. **150 Python pytest PASS; 45 Node PASS; Vite/TS PASS; 9 real-HTTP disposable Chromium PASS; synthetic Windows PowerShell 7 + 5.1 preservation/WebView PASS**.
- [P1 source-only Actions #43154962962](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/43154962962), same exact SHA: **COMPLETED SUCCESS**. **184 Node PASS; TS/Vite PASS; 7 disposable browser PASS**.
- No native Tauri executable built, installed or run, no original owner project/app data used, no model inference or training, no packages or interim installers produced.

## P4 exit and next evidence

The **actual owner original whole app-data tree preservation gate remains FAIL** (independent pre-QA backup 320 files; current original app-data 346; 74 changes classified as *browser/cache candidates*, historical writing process unknown). Owner earlier verified old production EXE and independent backup hashes intact and protected `data/` had no detected file differences. Historical **full-tree** preservation and source attribution cannot be retroactively proved from config files or synthetic CI.

P4-R01–R06 OPEN; real business Gate C, current-source native Windows WebView2, physical offline 8 GB Qwen unverified. The owner refused closure by risk deferral and forbids intermediate P4–P7 installers/executables. Native compilation remains denied unless separately expressly authorised. **P4 ACTIVE, P5 NOT AUTHORISED, P8 NOT CERTIFIED.**

**Next:** Stop repeating defensive source micro-patches absent a demonstrated risk. A meaningful R06 closure needs credible original incident evidence or a separately authorised prospective non-interference protocol with a documented disposition of the historical failure. R01 needs a genuine independently supported business use case. Neither can be manufactured by CI.
