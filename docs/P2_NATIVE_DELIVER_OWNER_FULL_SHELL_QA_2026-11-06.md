# PilotODIN P2 | Owner-native full-shell Deliver consent DevQA

**Date:** 6 November 2026  
**Branch:** `feature/live-dev-workspace-20261023`  
**Status:** Test-only SOURCE READY; **owner Windows execution NOT YET OBSERVED**. **P2 ACTIVE / REVIEW_REQUIRED; P8 NOT CERTIFIED.**

## 6 November 2026 | First owner native startup observed; test badge no longer masks New project

**Actual owner screenshots (three, startup only):** The owner launched the Windows synthetic full-shell QA BAT and supplied (1) Cargo output with `pilotodin_desktop.pdb` bin/lib output filename-collision **warning** while compiling, (2) `typescript-vite-build: PASS`, Vite `v6.4.5` ready on `127.0.0.1:5177`, and a red PowerShell `NativeCommandError` event at the line invoking `npm run desktop:dev`, and (3) a genuine running titled **PilotODIN P2 Native Deliver Consent - SYNTHETIC DEV QA** Windows application showing the four-row synthetic project, Deliver editor, Explore and Home tabs. **The app visibly launched despite the terminal warnings.** The image does not show a completed Cargo process exit code, final runner `result.json`, native Leave/Keep modal, typed unsaved narrative, five yes/no answers or owner accessibility results; they remain **NOT OBSERVED**. Do not claim five-step native acceptance.

**Narrow test-only blocker found visually:** The previous large amber `position:fixed; right:12px; top:8px` banner overlays the shell header's right side, potentially hiding the **New project** control required for steps C/E even though `pointer-events:none`. In [QA entry source `1c1efbd6b249`](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/1c1efbd6b249b757d9009310bbd3205b37804238) its scope warning is reduced to `SYNTHETIC QA - NO WRITES` and moved to the bottom-left (`left:12px;bottom:8px`) so it cannot cover upper-right header actions. The synthetic-only hostname, native test-only config, GET-only API boundary, owner data isolation and production `UnifiedShell` are unchanged. The full instructions stay in this guide and in the BAT console.

**Regression evidence:** [Two source contracts `49913b8bc786`](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/49913b8bc786d8f8a09942ba6588d98626a73108) require no top/right badge overlay, passive `pointer-events:none`, persistent visible test badge, strict native 5177/dev flags and GET/HEAD-only API gate. The **exact current GitHub blobs** (QA entry `65920a86e01415a20a0a1c9fe8ac3a6f576461a9`, test `eedc921c8f6aadd782845dd85fb0078089529200`) were reconstructed in an isolated Linux source fixture with matching file lengths and FNV-1a fingerprints; **Node 22.16.0 tests 2/2 PASS, 0 failures**. A full Windows Tauri rerun/TypeScript build for this **new QA-only edit** has **not** occurred. The existing runner's warning-stream handling was not changed: `NativeCommandError` alone cannot be treated as native dialog failure when the application opens, and the final process exit/result must still be evaluated after closing.

**Operator action with the already open old QA window:** Do **not** click an obscured New project control by guessing its coordinates, and do not assume missing observations passed. Close the old synthetic QA window safely; answer only genuinely observed steps `yes`, and `no` for unperformed/hidden steps. Keep its status-only archive if it reports blocked. Safely update the active feature branch preserving local changes before a **single focused replacement owner-native run** with the corrected banner, if this UI obstruction prevented C/E. No need to repeat the unrelated 8/8 cross-window Node regression, old P1 tests, font proofs or installers.

**Status:** Windows Tauri **window-open observed, scoped**; native Keep/Leave/focus and new-project importer outcomes **PENDING**. P2 ACTIVE / REVIEW_REQUIRED, P8 NOT CERTIFIED. This is not evidence of running a real installed product.

## Why this specific new gate exists

The earlier [native Deliver source and simulated-IPC acceptance](./P2_NATIVE_DELIVER_SHELL_EXIT_CONSENT_2026-11-06.md) established the Rust command compiled and a Chromium simulation handled Keep/Leave and stale replies. **It did not show a real Windows WebView2 owner-visible Leave Deliver / Keep editing dialog.**

The previously accepted P2 native Save As test window mounts a standalone `ReportWorkspace`, not the full `UnifiedShell`, so rerunning it would not cover the actual shell rail, tabs, header New project action or native Deliver exit command. This new DevQA launcher is for that missing full-shell observation only, not for PDF exports or previous phases.

## New test-only entrypoint and isolation

From the updated feature branch, run **`Run_PilotODIN_P2_Native_Deliver_Consent.bat`** on Windows. Its sole PowerShell worker is `tools/Run_P2_Native_Deliver_Consent_Local.ps1`.

- Uses the existing `.venv-live\Scripts\python.exe`, installed npm dependencies and cached offline Cargo toolchain only. If missing, blocks rather than installing anything. Checks correct Git branch and warns about, but does not reset, local uncommitted work.
- Allocates a **new** isolated `%LOCALAPPDATA%\PilotODIN\DevQA\runs\P2-NATIVE-DELIVER-CONSENT-...\` via existing `tools/qa_foundation.py init`. Its temporary `workspace` is explicitly assigned as `PILOTODIN_HOME` before importing or launching the real backend, and it is required to be empty. Does not touch the actual app projects or normal PilotODIN HOME. Never deletes other QA runs.
- New `tools/Seed_P2_Native_Deliver_Consent_Local.py` creates ONE four-row synthetic CSV project through the real FastAPI TestClient inside that isolated home. It checks that the source bytes are unchanged and live only under the run's `workspace/datasets`; no saved report, approved Quality record, PDF generation, model task, AI or private dataset.
- Refuses to start if ports **8000** or **5177** are in use; never stops an existing service. Starts one test-owned `127.0.0.1:8000` Uvicorn with `--lifespan off`, verifies its exact synthetic project ID, and uses normal `npm run build` with preinstalled packages.
- Runs the real `UnifiedShell` in **Tauri development mode**, with config `frontend/src-tauri/tauri.p2-native-deliver-consent.conf.json`: distinct `com.pilotodin.p2deliverconsentqa` app identifier, Vite **5177**, `bundle.active=false`, no sidecar binaries, model/installer resources or release assets. Existing production `confirm_native_deliver_exit` Rust handler is unchanged.
- QA web entry `frontend/p2_native_deliver_consent_qa.html` and `src/p2NativeDeliverConsentQa.tsx` are development-flag, exact-localhost, native-only. They mount the **actual full UnifiedShell**, set only the synthetic project and initial Deliver route in that separate QA app profile, and reject any browser `fetch` except read-only GET/HEAD to the owned `127.0.0.1:8000/api/` service. This is a deliberate observation-only gate.
- Stops only the test-owned backend, restores all changed process environment variables and retains a **status-only ZIP** in `%LOCALAPPDATA%\PilotODIN\DevQA\archive\`. The archive has run metadata, reported yes/no outcomes and a synthetic CSV hash, **not** source rows, report narrative, HTML/PDF bytes, local credentials, backend/native logs, installed app files or actual project data. The full QA run's private local logs remain under its own run folder.

## Five physical Windows observations

Do not click **Save, Upload/Analyse, Export, Quality corrections, model training, AI/ODIN** or use an existing personal dataset. The automated browser QA blocks writes, but keeping the steps bounded makes the evidence interpretable.

1. On loading the **full-shell Deliver** view of the synthetic project, type a short disposable report interpretation. Confirm that **Unsaved report draft** is visibly shown.
2. Click shell sidebar **Explore**. Confirm an actual native Windows dialog labelled **Leave Deliver / Keep editing** appears. Choose **Keep editing**. Check the report text, Deliver view and URL/route remain unchanged.
3. Click header **New project**. Again choose **Keep editing**. Confirm neither the report nor its navigation changes, and no importer opens now or on a later ordinary Home visit.
4. Repeat **Explore**, this time selecting **Leave Deliver**. Confirm Explore becomes active only after explicit approval, no duplicate confirmation appears, and keyboard focus/Tab navigation remains usable.
5. Return to **Deliver**, type a new synthetic note and select **New project**. Choose **Leave Deliver**. Confirm the normal **synthetic importer** opens only after the approval. Do not select or import another file.

**Optional sixth native observation (not automatically scored by this five-question runner):** With **Explore** also open as a tab, return to **Deliver** and type a short fresh synthetic note. Click the small **Close Deliver tab** button. The actual Windows **Leave Deliver / Keep editing** native dialog must appear. Choose **Keep editing** and verify both the Deliver tab and note remain. Click it again and choose **Leave Deliver**; only then should the Deliver tab close and Explore become active. If the dialog does not appear, or the draft is lost after Keep, report the failure explicitly with a screenshot. This optional extra does **not** convert the five automatic prompts into six accepted observations.

After all observations, close the QA Tauri window. If a separate **Close PilotODIN / Stay** native close confirmation appears, choose Close to exit the QA window. Then answer the **five yes/no prompts** in PowerShell according to what ACTUALLY happened. A missing step is **no**, not an inferred pass.

## Acceptance recording and limits

The runner labels successful responses `OWNER_REPORTED_PASS_REVIEW_REQUIRED`, with the development QA overall result `REVIEW_REQUIRED`; it does **not** mark installed release or full native accessibility acceptance. Native process failure, omitted/no observation, unexpected API mutation, bad synthetic source hash, wrong project/ports or a missing prerequisite yields `FAIL_OR_BLOCKED`. If red, stop and retain the printed single QA diagnostic ZIP; do not retry random older suites.

**Owner deliverables:** Share the final PowerShell console screenshot showing all five outcome lines, and at least one native Stay/Leave dialog screenshot if practical. If anything fails, provide the status-only ZIP and a screenshot of the exact failed step. No original report file or dataset is needed.

**Remaining P2:** physical Windows keyboard/Narrator and direct Studio/external hash/tab-close/dock consent paths remain distinct from the five scoped shell cases. Normal mixed-script Unicode PDF still requires independent approval of **three unchanged Noto binaries, three full original OFL notices, six exact release SHA-256 pins, Noto Sans SC face/RFN and accessible notices**. `RELEASE_APPROVAL_STATUS=NOT_GRANTED` and P8 installer NOT CERTIFIED are unchanged.

## Windows PowerShell reserved-name repair and definitive post-fix source acceptance

During source review, `tools/Run_P2_Native_Deliver_Consent_Local.ps1` was found assigning `$home`. Windows PowerShell treats this as the built-in read-only `$HOME`, case-insensitively; the old P2 native-chain test had historically failed from the same kind of issue. **No owner Windows QA was attempted with this invalid runner.** [Repair `8a95bb81ecf8`](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/8a95bb81ecf82d55a19242af62f082362d8ecc6a) renamed every such use to `$isolatedWorkspaceHome` without changing the QA path or isolation rule.

- [Guard contract `b7dcc16c3283`](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/b7dcc16c32831a46e42cb5cff14ffdaeb95b784f) now rejects assigning PowerShell reserved `HOME/HOST/PID/PROFILE/INPUT/MATCHES/ERROR` automatic variables. Historical intermediate [focused #42158920592](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/42158920592) is **FAILED** only because the prior source regex still expected `$home`; this was repaired by the new guard assertion.
- [Windows PowerShell preflight workflow `4382d5edf15b`](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/4382d5edf15b0eb3e38bec3a9e39c91bad1297b9) runs the actual Windows PowerShell AST parser and `qa_foundation.py preflight` on both Python and PowerShell source, requiring **zero** findings and validating isolated non-bundled Tauri config. Final [CI #42158971543](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/42158971543) **COMPLETED SUCCESS**.
- Final [focused P2 #42158967267](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/42158967267) **COMPLETED SUCCESS, 77/77 Node tests and TS/Vite production build**, exact tested test/source commit `b7dcc16c32831a46e42cb5cff14ffdaeb95b784f`.
- Final [shared frontend #42158967263](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/42158967263) **COMPLETED SUCCESS, 160/160 Node + TS/Vite production build + 5/5 isolated Chromium**, same tested SHA. No running Tauri native dialog or physical Windows owner observation was performed by any of these workflows.

The source-only launcher gate is now **ready for one scoped physical Windows run**. The result of that future run must be recorded independently and must not be assumed from CI.

## Verified source preflight, not an owner-native pass

- [Windows PowerShell parser and non-distributable QA config #42158598871](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/42158598871): **COMPLETED SUCCESS**, Windows PowerShell source parses; no launcher run.
- [Focused P2 #42158622848](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/42158622848): **COMPLETED SUCCESS, 77/77 Node contracts and TypeScript/Vite production build** at source SHA `989f46786922054bb955b2977da617cbda6c2044`. New contracts verify strict test-only config, no installer/AI, exact localhost, write veto, DevQA identity, env restoration and ZIP status-only shape.
- [Shared frontend #42158525389](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/42158525389): **COMPLETED SUCCESS, 160/160 Node + TS/Vite build + 5/5 isolated Chromium**, at source SHA `42ca012aa06ba004000e3cb0ff28fda6bde2bd98`. Later changes only added test contract/workflow and PowerShell source, not production frontend. Existing accepted real P2 hosted HTTP flows remain unchanged and were not repeated for this test-only runner.
- [Windows Tauri/Rust compile #42158074652](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/42158074652): **COMPLETED SUCCESS**, new non-installable Tauri QA config and prior production Rust dialog compile. No native GUI launched and no installer produced.

**Do not claim the five actual Windows observations have passed before the owner runs this entrypoint and shares evidence.**
