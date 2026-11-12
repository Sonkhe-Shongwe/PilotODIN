# PilotODIN 1.0 | P4-44 Isolated native-dev identity and intermediate-build guard

**Date:** 12 November 2026. **Phase:** P4 ACTIVE. **Primary risk:** P4-R06 (original data safety); secondary R02/R04 native readiness. **Scope:** source-only preventive guard with negative CI; no owner native work.

## Evidence-based defect

The repo's `frontend/package.json` had `desktop:dev` configured as raw `tauri dev`. Tauri merges its default `src-tauri/tauri.conf.json` unless the CLI is passed an explicit configuration override. The default production identifier is `com.pilotodin.studio`. The Tauri Rust backend in `frontend/src-tauri/src/lib.rs` uses `app.path().app_local_data_dir().join("data")` to locate `PILOTODIN_HOME`, and Tauri's app-local directory also determines its default Windows WebView storage. A raw native developer run with the production identity therefore **risks using the original production app-data/WebView path**, despite our separate browser-only live development directory. This is a **potential unsafe developer launch path**, not evidence the owner ran it or that it caused the historically changed 74 original browser/cache candidate files.

The original production app identifier and installed P4 QA identifier (`com.pilotodin.p4nativeqa`) are distinct. The new dev identity is also distinct. Do not equate this code guard with actual owner-native process ownership.

## Implementation

[Code `bf23cdd4af886854953166d4c14a1822e66431c2`](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/bf23cdd4af886854953166d4c14a1822e66431c2):

1. `frontend/src-tauri/tauri.p4-isolated-native-dev.conf.json` uses **`com.pilotodin.p4isolatednativedev`**, uniquely distinct from production and historical QA, with `bundle.active=false`, no resources or external binaries and an explicitly marked unverified native-dev window.
2. `frontend/package.json` changes `desktop:dev` to a standalone Node guard that refuses execution by default. Even after separately documented owner consent, it requires an affirmative local opt-in, checks all three app IDs, data-root overrides and packaging config, then and only then would invoke Tauri dev with the isolated config. **A consent environment variable is not itself owner approval**; no approval is implied by the user's `next`. The opt-in does not magically make the native developer shell fully functional, especially without bundled sidecars/Qwen assets.
3. `frontend/package.json` changes `desktop:build` to a source guard that fails instead of generating installers while P4–P7 packaging is frozen.
4. `frontend/tests/p4-native-dev-isolation.test.cjs` verifies three distinct source IDs, no packaging inputs, default refusal of native development and build, and later explicitly verifies the legacy build workflow cannot be triggered by P4 changes. These tests do not compile Tauri or launch desktop processes.
5. `docs/LIVE_DEVELOPMENT.md` states the browser-only safe route, and warns against raw Tauri CLI bypass.

[Follow-up source `06df5aedfcbc4d83c1793d9e1f23a90bfaea6664`](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/06df5aedfcbc4d83c1793d9e1f23a90bfaea6664) constrains `.github/workflows/native-windows-compile.yml` to its legacy `build-e` branch, not current P4 development; prevents recurring native compile-only probes triggered by `src-tauri` config changes on this branch.

## Actual workflow sequence and limits

The first source commit touched `src-tauri/**`, which accidentally triggered legacy [Build E Native Windows Compilation #43151392404](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/43151392404). It **COMPLETED SUCCESS** with `cargo check`, temporary **intentionally invalid** tiny sidecar/model fixtures and cleanup. The log explicitly confirms the dummy files were removed and no installer made. This was not intended P4 testing, no real runtime was started, no user files were touched, and **we do not count it as evidence for R02/R03/R04 or a licensed native execution milestone**. Follow-up change prevents automatic repeat on P4 branch. The other packaging workflows remain frozen by pre-existing source policies.

**Final exact-source CI:** at `06df5aed`, [P4 run #43151663255](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/43151663255) **COMPLETED SUCCESS, 3/3 jobs**. Logs: **150 Python, 44 Node, TypeScript/Vite, 9 disposable real-HTTP Chromium, Windows synthetic preservation/WebView on PowerShell 7 and 5.1 PASS**. [P1 isolated frontend #43151663198](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/43151663198) **COMPLETED SUCCESS**, **184 Node, TypeScript/Vite, 7 isolated browser PASS**. P4 CI does not create an EXE/MSI/NSIS package; native-dev guard negative tests refuse before invoking Tauri.

## Binding owner data and exit requirements

Independent original backup contains 320 files; a later native observation identified 346 original app-data files and 74 changes. Last available owner read-only comparator classified 0 relative-path/content changes inside critical original `data/`, 74 *candidate* browser/cache modifications, 0 unclassified; original EXE and backup matched original baseline. The strict full-tree preservation gate remains **FAIL**, with historical writer **UNKNOWN**, not an exemption for caches. These are owner-supplied historical observations, not reassessed here.

No actual owner original paths were read or modified, no installer built/downloaded/installed, no normal native dev launched, no new real-business prediction performed, and no model trained. Latest native WebView2, Qwen/8GB and independent real business Gate C remain unverified. P4-R01 through R06 OPEN; owner refused risk deferral. **P4 ACTIVE; P5 NOT AUTHORISED; P8 NOT CERTIFIED**.

**Next closure action:** root-cause investigation of existing 74 original-data differences requires credible historical process/file evidence, not just folder names or later profile snapshots; if writer cannot be reconstructed, document that limitation and establish independent prospective non-interference evidence under an explicitly approved protocol. R01, R02–R05 continue to require their own acceptance evidence. A native unpackaged EXE **cannot** be compiled or executed before separate explicit owner approval.
