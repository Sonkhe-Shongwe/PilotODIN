# P1 native WebView2 title-bar close: scoped Windows acceptance

**28 OCT 2026 | P1 NATIVE EDITED-PREPARE TITLE-BAR CLOSE CONFIRMED FAILED; SOURCE SAFETY FIX COMMITTED, NOT YET TESTED.** Owner reports the actual Tauri/WebView2 development window **closed immediately without any warning** when clicking the real Windows title-bar **X** with a modified unsaved Prepare target. This is a **reproduced owner-observed P1 native draft-loss protection defect**, not a synthetic/browser-only concern. The test followed a successful native Rust development build, with isolated local backend provenance verified separately: `tools/run_live_backend.ps1` console displayed `[PilotODIN DEV / Backend] Isolated data: ...\\PilotODIN\\.pilotodin-dev-data` and Uvicorn bound to `127.0.0.1:8000` with successful health/project reads. Report states form target unsaved; exact CSV/project ID at the time of close is not independently verified in screenshot; do not claim durable dataset loss or a specific project modification. No screenshot proves a native confirmation existed; user explicitly says none appeared. **P1 native-close safety FAIL, gate OPEN.**

**Focused code fix committed [`331537766394`](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/331537766394e5837a6f4337d23e4c7fff25dea4)**. Rust `frontend/src-tauri/src/lib.rs` now synchronously vetoes each `main` window `WindowEvent::CloseRequested`, emits a one-use opaque close token, and refuses close if webview has not resolved it. An exact-matching, consumed-once token may invoke `resolve_native_close_request`; only approved requests call native `window.destroy()` (not re-entrant `close()`). JS `UnifiedShell.tsx` registers a Tauri event listener, uses the **existing primary/docked current-project draft indicators**, prompts user on dirty forms, and resolves approved or cancelled requests without transmitting field values, persisting drafts, or changing the Chromium `beforeunload` logic. New `frontend/src/nativeCloseConsent.ts` has fail-closed decision handling; seven **authored but UNEXECUTED** Node tests in `frontend/tests/p1-native-close-consent.test.cjs`, plus one Rust token-consumption unit test **UNEXECUTED**. Source static review checked the intended handler and no unrelated repo file changes. **No TypeScript/Vite build, Node test, Rust compile, Cargo test or Windows native close test has run against this new source. This fix is NOT ACCEPTED yet.** Changes are bounded to P1 native close; no dependency/permissions/CI change, no release bundle/installer, no user data/sidecar/model change. Avoid one-size-fits-all prompts or bypassing the native veto; if the implementation fails at build or runtime, fix the demonstrated root cause without weakening consent or fail-closed behaviour.

**Next owner Windows gate:** safely pull the exact feature branch while preserving local untracked `frontend/src-tauri/Cargo.lock` and `frontend/src-tauri/gen/`, then in `frontend` run `node --test tests/p1-native-close-consent.test.cjs tests/p1-unsaved-reload-guard.test.cjs tests/p1-primary-draft-switch-safety.test.cjs` and `npm run build`; in `frontend/src-tauri` run `cargo test --offline native_close_ticket_tests --lib` if cached toolchain permits. **All pending.** On green, launch only `npm run desktop:dev -- --config src-tauri/tauri.native-a4-smoke.conf.json` with `VITE_PILOTODIN_NATIVE_SMOKE=1` and offline Cargo, the same already-proven isolated backend, and a disposable synthetic CSV. Verify real native X on edited Prepare: prompt, **Stay** must preserve window/project/edited target; explicit **Leave** closes. Repeat edited dock only after initial native acceptance. If the frontend cannot register, native close is deliberately fail-closed and may block exit; report that as a usability/registration failure, not a success. **Do not test with existing projects or certify P1 closed.**


**28 OCT 2026 | P1 DEVELOPMENT TAURI RUST BUILD AND SEPARATE NATIVE WEBVIEW WINDOW OWNER-OBSERVED PASS; UNSAVED NATIVE CLOSE UNTESTED.** New owner Windows screenshots show Cargo compiling `pilotodin-desktop v1.0.0-alpha.1` for `x86_64-pc-windows-msvc`, `Finished 'dev' profile [unoptimized + debuginfo] target(s) in 17.65s`, then `Running target\\debug\\pilotodin-desktop.exe`. A real separate desktop window visibly displays the development-only title **`PilotODIN - A4 Native Save As Smoke (DEV ONLY)`**, matching `tauri.native-a4-smoke.conf.json`, with the PilotODIN shell and Deliver screen rendered. The Cargo `output filename collision` warning did **not** prevent the observed development compilation/launch; this is not itself a proven functional defect. **Native Rust dev compilation and separate-window launch are SCOPED ACCEPTED.** The native title-bar X has **not** been clicked on an edited disposable form in the provided evidence; no observed `CloseRequested`, browser `beforeunload` or Stay/Leave confirmation. **Native draft-close protection remains OPEN.** The window currently shows previously existing project `insurance_claims_CLEANED`, saved report revision 3 and Quality audit evidence. It is **NOT cleared as disposable**; do not change its fields, perform exports/approvals or use it for a destructive close test. The localhost backend is reachable, but screenshots do **not** show proof of its `PILOTODIN_HOME` data-home. Before testing, verify the **existing running backend console** explicitly says `[PilotODIN DEV / Backend] Isolated data: <repo>\\.pilotodin-dev-data`, which `tools/run_live_backend.ps1` prints. A healthy :8000 response alone is insufficient. Then use only a newly imported invented CSV project, change a Prepare form control, click the real native X and record whether a prompt appears; Cancel/Stay and Leave must be owner-observed separately. If no prompt, record actual native P1 failure instead of changing code speculatively. Do not touch untracked `src-tauri/Cargo.lock`, `src-tauri/gen/`, personal datasets, release installer, CI, model downloads or P2-P8. The latest owner screenshots also do not show a fresh `git rev-parse HEAD`, so no exact local SHA is inferred. **P1 only active OPEN phase.**


**28 OCT 2026 | P1 NATIVE WINDOWS PREFLIGHT OWNER-OBSERVED PASS, NATIVE CLOSE UNTESTED.** Windows PowerShell screenshot taken from the verified PilotODIN repository root shows `powershell.exe -NoProfile -ExecutionPolicy Bypass -File ".\\tools\\Verify_A4_Native_Windows.ps1" -PreflightOnly` executed successfully. Console printed **"Preflight checks passed. Current source branch and local backend are ready."** It also printed **"WARNING: Your checkout has local edits. Do not discard these edits."** Diagnostic ZIP created under Windows user TEMP, named `pilotodin-a4-native-443e21918c34.zip`; ZIP contents were **not inspected**. The script's preflight checks Rust/MSVC, npm, dev overlay, backend health and 5174 availability but **does not prove the backend process uses the isolated `.pilotodin-dev-data` home**. No screenshot displays a new `git rev-parse HEAD` from this command, so native preflight is recorded against the feature branch without claiming an exact displayed local SHA. **No Rust compile, dev WebView2 window, native X / Stay / Leave scenario, installer, model, or full A4 regression was run.** Native close remains an open P1 acceptance gate; preserve untracked Cargo.lock and gen. **Next:** confirm the existing `tools/run_live_backend.ps1` terminal explicitly displays isolated `PILOTODIN_HOME=<repo>/.pilotodin-dev-data`; then use only a disposable CSV with the existing `tauri.native-a4-smoke.conf.json` development config to inspect real title-bar X and Stay/Leave. Stop on unknown backend provenance, missing crates, errors or unintended user-data access. No speculative Rust close patch before native observation; P1 sole active phase.


**Status (28 October 2026): native prerequisites / development build / window launch PASSED on the prior source, owner-observed actual edited Prepare title-bar X close FAILED (no warning). Fix committed, revised-source build/tests/manual retest PENDING.** This is the next focused P1 runtime dependency after the owner-observed **18/18 Node contract PASS** and **1/1 real cross-tab Chromium reload PASS** at checkout `9c0c6372b168526054ec34f04cb1e23caf502f99`. Keep P1 as the only active phase.

## Why this gate remains open

The browser tests cover genuine Chromium document reload and beforeunload. **They do not establish that clicking the native Windows WebView2 title-bar X delivers that event.** The current `frontend/src-tauri/src/lib.rs` has no explicit native window CloseRequested handler, so Tauri title-bar close behaviour must be observed before choosing a corrective design. Do not infer a source-confirmed user data-loss event, and do not certify native protection from browser evidence. The existing Rust `RunEvent::Exit` code only cleans up the backend/AI child processes after exit; it is not a pre-close draft veto.

## Safe scope

- **Development WebView2 only**, not an installed release or P8 Windows installer.
- Use **only a disposable synthetic project**, never an original/user-provided dataset or a production workspace.
- Existing `tauri.native-a4-smoke.conf.json` sets a separate Tauri dev identity and Vite port **5174**. `VITE_PILOTODIN_NATIVE_SMOKE=1` must be set only for this local `tauri dev` command. No sidecar/AI model is launched by this development-only configuration.
- The smoke webview accesses the *currently running* localhost backend at **127.0.0.1:8000**. Confirm this is the normal `tools/run_live_backend.ps1` development process with `PILOTODIN_HOME=<repo>/.pilotodin-dev-data`. The A4 preflight tests its health but **does not establish data-home provenance**. Stop rather than connect to a backend with unknown data-home.
- **Do not run** `Run_PilotODIN_A4_Native_Smoke.bat` for this P1 slice: its full A2/A3/A4 regression and export checklist are outside this focused native gate.
- Preserve the owner's untracked `frontend/src-tauri/Cargo.lock` and `frontend/src-tauri/gen/`; those may be locally generated by Cargo/Tauri. Never `git clean`, hard-reset, overwrite or commit them without review.
- Rust/MSVC dependencies may be unavailable or require download on the first build. **Do not install packages, initiate release bundling or launch an installer** as part of this gate.

## Step 1: prerequisite discovery only

From the **repository root** in Windows PowerShell, with the trusted Live Dev backend already running and port 5174 free:

```powershell
git rev-parse HEAD
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\tools\Verify_A4_Native_Windows.ps1 -PreflightOnly
```

The preflight checks the Tauri dev overlay, Rust >= 1.90, MSVC linker, npm, backend health and port 5174. It writes a **temporary** diagnostics ZIP. It does **not** compile Rust or open a native window. If any check fails, **stop**, report only the failure summary/diagnostics after reviewing for paths, and keep native acceptance open.

## Step 2: actual development WebView2 only if preflight passes

Create an invented CSV outside the repository, avoiding personal or project files:

```powershell
$syntheticP1Csv = Join-Path $env:TEMP 'pilotodin-p1-native-close-disposable.csv'
[IO.File]::WriteAllText($syntheticP1Csv, "fraud_reported,amount`r`nN,10`r`nY,20`r`nN,30`r`nY,40`r`n", (New-Object System.Text.UTF8Encoding($false)))
```

From **`frontend`**, and only after confirming the backend is the local isolated Live Dev backend:

```powershell
$env:VITE_PILOTODIN_NATIVE_SMOKE='1'
try {
  npm run desktop:dev -- --config src-tauri/tauri.native-a4-smoke.conf.json
} finally {
  Remove-Item Env:\VITE_PILOTODIN_NATIVE_SMOKE -ErrorAction SilentlyContinue
}
```

This is a Tauri **development** build (port 5174), not an installer, and may take time/require network access for uncached Rust crates. It can create local Cargo files; leave them intact. Confirm a *separate native application window* with the smoke-only title opens; **do not use the browser on 5173** for native acceptance. The app can reach the development backend, so do not explore or edit any existing project in it.

## Step 3: observed behaviour, never assumed PASS

With the invented CSV above, create a new disposable project in the native smoke window and use its editable Prepare target.

| Scenario | Required native observation |
| --- | --- |
| Native edited primary Prepare, title-bar X | The app must ask permission **before** discarding the edited form. No warning + window destroyed is a **native P1 safety failure**. |
| Choose Stay/Cancel in that warning | Original native window, project, route and unsaved edited target remain; no silent reload or overwrite. |
| Retry title-bar X, explicitly choose Leave | Window can exit only after confirmation, without unexpected duplicate prompts or project writes. Unsaved draft recovery after exit is **not promised**. |
| Docked Prepare edited; title-bar X | Repeat with disposable project, ideally after docking Prepare beside Quality. Stay must preserve edited dock values. If the native min-width (1010 px) prevents a paused 680 px dock, record narrow-paused state **NOT REPRODUCIBLE**, not PASS or FAIL. |
| 125%/150% Windows scaling and keyboard/focus | Report only actual observed values and navigation; treat any unavailable scaling/snap test as **PENDING**, not accepted. |

Only verify a check if it was actually seen in the native app. Capture a screenshot showing the native window and any close-confirmation message, plus brief results of Stay and Leave. If no native prompt occurs, **record the failure and do not manually force-close an edited original project**. The disposable CSV/project is deliberately expendable, so a failed close cannot destroy owner data.

## Decision after owner evidence

- **Pass:** native close/Stay/Leave on the tested Windows environment can be accepted within its exact observed scope. P1 still needs integrated import→Quality→switch→failure restoration and other native accessibility/responsiveness gates.
- **Fail:** log a reproducible **native-only** P1 defect with window close steps, tool versions and expected/actual result. Assess a minimal Tauri `CloseRequested` guard separately; **do not** conflate it with `beforeunload`, introduce bypass permissions or silently skip confirmation.
- **Blocked:** record missing Rust/MSVC, backend provenance, dev server, WebView2 or other prerequisite explicitly. P1 stays open.

No new production code, backend, dependency lock, CI, models, installer or P2–P8 work is authorised by this acceptance note.
