# PilotODIN P3 | Unsaved semantic descriptions, primary-workspace draft protection

**Date:** 6 November 2026. **Phase:** P3 ACTIVE, P1/P2 bounded development CLOSED, P8 NOT CERTIFIED.  
**Source feature SHA:** `6542ea18e58f44de14ff740840af96e2f117c3ed`. **Compatibility fix SHA:** `94577c12e86e0f450d74bc24f2cb5145b2e96993`.  
**Acceptance:** **Scoped browser and source PASS** with a preserved failed first CI set, **owner native Windows WebView2 acceptance PENDING**.

## User-safety gap and bounded P3 remedy

Prior P3 Data Dictionary business-domain/row/field editor allowed unsaved user-written descriptions, but **the primary workspace's existing unsaved-draft marker covered Prepare/Model/Predict/Deliver, not Your Data (`understand`)**. Switching project or leaving Your Data therefore could discard unsaved text with no shared-shell consent in some navigation paths.

The P3 increment now:
- Computes a **memory-only dirty indicator** by comparing the normalized in-editor domain/row/field descriptions to the currently saved `user_context` for the same project and Quality version. It **does not persist draft text or commit new data**; it clears the marker after confirmed Save or permitted unmount.
- Passes only the dirty boolean through `SemanticContextEditor → SemanticOverview → ColumnInvestigation → App` to the existing shell; no user text goes into project-selection/localStorage/native-dialog state.
- Extends existing `primaryStudioExitGuard`, shell's primary draft marker, unload guard type, existing route and project-consent logic to include `understand`. **A dirty Your Data form now requests consent before leaving its primary view or changing project**; a refusal retains its mounted values. Existing closed P1/P2 draft guard behavior remains in place.
- Adds a small visible "Unsaved business descriptions" reminder in the editor. Deliberately **does not** make the semantic description a confirmed business fact, model input or target. The docked form retains its existing generic P1 edited-dock capture and may conservatively prompt on other form changes; no new cross-view synchronization.

## CI chronology and exact limitations

1. [First feature commit `6542ea18e58f`](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/6542ea18e58f44de14ff740840af96e2f117c3ed) ran an updated **real local Uvicorn + Chromium + SQLite** guarded journey: [P3 workflow #42255422240](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/42255422240) **SUCCESS, 1/1 PASS in 5.8 seconds**. Besides the already accepted Save/reopen/edit and project/version boundary, it now covers keyboard expansion, invalid field input, dialog **Cancel** for an attempted dirty project switch, preserved text, keyboard-driven Save, and clearing the dirty indicator. Synthetic data only, no owner assets or native Tauri.
2. The same source SHA had **three distinct red runs**: [P3 focus #42255422039](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/42255422039) compiled/ran **20/20 Python and 10/10 Node PASS**, then **TypeScript/Vite FAIL** due to unexpanded `editedPrimary` ref type; [P1 frontend #42255422674](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/42255422674) **160/160 Node PASS** then the same TS failure; [P2 report draft safety #42255422369](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/42255422369) **96/97 Node PASS, 1 FAIL**, because a brittle source assertion expected the older four-value type. None of these failures should be called a successful whole workflow or erased. No evidence of report data corruption was found in their logs.
3. [Compatibility commit `94577c12e86e`](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/94577c12e86e0f450d74bc24f2cb5145b2e96993) **only** completes the primary ref TypeScript union and updates the older P2 type assertion. **Actual green reruns at this SHA:** [P1 isolated frontend #42255787793](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/42255787793) **SUCCESS: 160/160 Node, TypeScript/Vite PASS (1,652 modules), 5/5 synthetic browser cases**; [P2 report safety #42255787825](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/42255787825) **SUCCESS: 97/97 Node and TS/Vite PASS**; [P2 real HTTP revision comparison #42255787876](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/42255787876) **SUCCESS** in its named scoped integration check. Do not reattribute the P3 1/1 browser test to `94577c12`, since its workflow did not rerun on this type/test-only patch.
4. [P1 disposable real HTTP #42255787905](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/42255787905) was still **IN PROGRESS** when the first draft of this ledger was prepared (long Chromium install). Check final conclusion separately before claiming a green/red result; it is **not necessary to invent** a verdict for P3.

**What is accepted:** Controlled primary-browser draft Cancel and safe Save with the existing reusable consent mechanism; source and production build compatibility after two-line repair, with scoped P1/P2 regression. **What is not yet accepted:** Physical owner Windows WebView2 native project-switch/keyboard/unload consent and `P3-04` full closure. No installed release or OS window-close proof from these Linux runners.

## Next verification and owner action

[Owner Windows synthetic W1–W4 checklist](./P3_SEMANTIC_CONTEXT_OWNER_WINDOWS_QA_2026-11-06.md) now includes deliberately editing the P3 context and attempting a project change, **Cancel**, checking values are still present, completing an explicit Save and then switching without a false dirty prompt. Only genuine owner native shell evidence with exact local HEAD can close that modality. If using `Start_PilotODIN_Live_Dev.bat`, label the run Windows **browser preview**, never native WebView2.

Remain P3 ACTIVE, P3-03a source/browser accepted at read-only scope only, P3-04 owner-native manual evidence pending, no automatic P4 activation or P8 release.
