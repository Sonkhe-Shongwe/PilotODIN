# PilotODIN P2 | Owner-native full-shell Deliver consent DevQA

**Date:** 6 November 2026  
**Branch:** `feature/live-dev-workspace-20261023`  
**Status:** Test-only SOURCE READY; **owner Windows execution NOT YET OBSERVED**. **P2 ACTIVE / REVIEW_REQUIRED; P8 NOT CERTIFIED.**

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

After all observations, close the QA Tauri window. If a separate **Close PilotODIN / Stay** native close confirmation appears, choose Close to exit the QA window. Then answer the **five yes/no prompts** in PowerShell according to what ACTUALLY happened. A missing step is **no**, not an inferred pass.

## Acceptance recording and limits

The runner labels successful responses `OWNER_REPORTED_PASS_REVIEW_REQUIRED`, with the development QA overall result `REVIEW_REQUIRED`; it does **not** mark installed release or full native accessibility acceptance. Native process failure, omitted/no observation, unexpected API mutation, bad synthetic source hash, wrong project/ports or a missing prerequisite yields `FAIL_OR_BLOCKED`. If red, stop and retain the printed single QA diagnostic ZIP; do not retry random older suites.

**Owner deliverables:** Share the final PowerShell console screenshot showing all five outcome lines, and at least one native Stay/Leave dialog screenshot if practical. If anything fails, provide the status-only ZIP and a screenshot of the exact failed step. No original report file or dataset is needed.

**Remaining P2:** physical Windows keyboard/Narrator and direct Studio/external hash/tab-close/dock consent paths remain distinct from the five scoped shell cases. Normal mixed-script Unicode PDF still requires independent approval of **three unchanged Noto binaries, three full original OFL notices, six exact release SHA-256 pins, Noto Sans SC face/RFN and accessible notices**. `RELEASE_APPROVAL_STATUS=NOT_GRANTED` and P8 installer NOT CERTIFIED are unchanged.

## Verified source preflight, not an owner-native pass

- [Windows PowerShell parser and non-distributable QA config #42158598871](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/42158598871): **COMPLETED SUCCESS**, Windows PowerShell source parses; no launcher run.
- [Focused P2 #42158622848](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/42158622848): **COMPLETED SUCCESS, 77/77 Node contracts and TypeScript/Vite production build** at source SHA `989f46786922054bb955b2977da617cbda6c2044`. New contracts verify strict test-only config, no installer/AI, exact localhost, write veto, DevQA identity, env restoration and ZIP status-only shape.
- [Shared frontend #42158525389](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/42158525389): **COMPLETED SUCCESS, 160/160 Node + TS/Vite build + 5/5 isolated Chromium**, at source SHA `42ca012aa06ba004000e3cb0ff28fda6bde2bd98`. Later changes only added test contract/workflow and PowerShell source, not production frontend. Existing accepted real P2 hosted HTTP flows remain unchanged and were not repeated for this test-only runner.
- [Windows Tauri/Rust compile #42158074652](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/42158074652): **COMPLETED SUCCESS**, new non-installable Tauri QA config and prior production Rust dialog compile. No native GUI launched and no installer produced.

**Do not claim the five actual Windows observations have passed before the owner runs this entrypoint and shares evidence.**
