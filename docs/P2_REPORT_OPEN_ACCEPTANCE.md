# P2 report-library latest-open selection guard

**25 October 2026: owner-observed focused Windows Node contracts and TypeScript/Vite PASS. Full UI race behavior and release acceptance NOT established.**

## Prior P1 acceptance
Owner screenshot of `Run_PilotODIN_P1_Upload_Staging.bat` shows `P1 isolated import staging: PASS` and `P1 import staging checks passed`, diagnostic ZIP `pilotodin-p1-import-stage-li2_fvh_.zip` locally. ZIP not uploaded, so precise counts/log timings/JSON are not independently verified. Source staged fsync/atomic publish and rollback focused accepted; this does not prove an OS crash/power-loss case, full import lifecycle or final installer.

## A concrete P2 UI race
In `frontend/src/ReportWorkspace.tsx`, `openReport(id,number)` awaited a local GET without checking whether a later click or New report action had superseded the request. A slow response from report A could overwrite report B (or a newly started draft) after the user made a newer choice. This is source-identified risk, not an assertion that the owner experienced the UI failure.

## Bounded fix
- A component-local monotonic `latestOpenRequest` token guards the response, error handling and busy finalization of **read-only** report open requests.
- A newer report Open, New report, explicit Explore→Deliver preselection and a project component reset/unmount invalidate earlier opens. Busy state clears when choosing a new draft or preselecting evidence.
- The saved report backend, evidence SHA and version controls, revision Save and native Save As paths, existing default latest report hydration, project isolation, explicit user writes and dataset original are **not changed**.
- This is not a general cancellation of network requests or a durable orchestration engine. A previous response may complete over the network but cannot replace a newer composer selection.

## One focused Windows gate
`Run_PilotODIN_P2_Report_Open.bat` calls isolated `tools/Verify_P2_Report_Open_Local.py`. Node contracts: four new source checks plus directly affected existing `report-workflow-gates`, `explore-deliver-evidence`, `a4-native-report-save-contract`; frontend `tsc --noEmit && vite build`. One `pilotodin-p2-report-open-*.zip`. No unchanged backend suites, native Tauri, saved revision mutation, original project upload or Qwen.

**Verification honesty:** New P2 code re-fetched/static-checked but no owner's Windows check yet. Source contracts and build do not substitute for a manual race demonstration, nor full P2 acceptance. On failure upload ZIP, on green send results. No GitHub Actions/installer/high RAM AI.

## Owner focused acceptance, 25 October 2026

Owner supplied a Windows screenshot explicitly showing `p2-report-open-contracts: PASS`, `frontend-typescript-vite: PASS`, `P2 report Open navigation gate: PASS` and `P2 report Open focused checks passed`. Diagnostic path `pilotodin-p2-report-open-co3yl_ka.zip` visible locally, not uploaded or inspected independently. The source-contract and compilation scope is accepted, but a real interactive report-A/report-B response race, full project-switch path and desktop installer remain untested. Later manual/browser-driven behavioral confirmation is appropriate before calling the UX fully verified. Next work follows an agreed, coherent P1/P2 controlled-batch plan, not an automatic additional source increment.
