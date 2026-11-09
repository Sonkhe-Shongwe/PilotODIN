# PilotODIN 1.0 | P4-21 Atomic Target-Context Save Integrity Audit

**Evidence date:** 9 November 2026  
**Instruction:** The owner said `next` after P4-20, authorising a bounded **P4 safety/data-integrity audit**, NOT P4 closure, training, old-project changes, a Windows installer, P5 or release. The owner's prior explicit refusal to defer unresolved P4 risks remains in force.  
**Repo and branch:** `Sonkhe-Shongwe/PilotODIN` / `feature/live-dev-workspace-20261023`  
**Exact tested application source:** [`65f805933b5993c25f66d4a3e50a76cde91c56db`](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/65f805933b5993c25f66d4a3e50a76cde91c56db)  
**Exact P4 CI:** [#42696149447](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/42696149447), **COMPLETED SUCCESS** at that SHA, **110/110 Python**, **28/28 frontend Node**, TypeScript/Vite production build **PASS**, **8/8 real-HTTP Chromium/Uvicorn** disposable browser tests **PASS**.

## Source-confirmed integrity race

The route `POST /api/projects/{project_id}/target-business-context` first called `quality.current_data(project_id)`, rejected a stale `body.expected_version`, validated that the requested column existed in that version and checked submitted user-description fields. **Later**, `storage.save_target_context` acquired its own SQLite `BEGIN IMMEDIATE` transaction and inserted/upserted `target_business_context` **without checking current Quality version or archive status under the same transaction lock**.

A concurrent Quality version change or project archive **after the route's initial check but before the storage commit** could therefore yield HTTP 200 for saved descriptions attached to a no-longer-current working dataset or archived project. The transaction boundary matters: a pre-transaction version check and the HTTP archive middleware are not an atomic commit-time fence. This is a **source-confirmed concurrency integrity gap**, not an observed owner production race, leaked personal data, or confirmed trained model.

## Bounded correction at exact source

- **`backend/storage.py`:** Add `TargetContextConflict` and, immediately following `BEGIN IMMEDIATE`, call the existing `project_lifecycle.require_active_for_write(con, project_id)`. Check `quality_state.current_version == quality_version` **inside that same writer transaction before any INSERT**. If Quality state is absent or different, fail closed with a version-conflict exception. This follows the existing `save_human_review` atomic Quality and archive fencing pattern and uses SQLite's same one-writer lock as actual Quality changes/project archiving.
- **`backend/main.py`:** Report `TargetContextConflict` as HTTP **409** and `ProjectLifecycleError` as its exact status (409 archived, 404 removed), rather than returning false success or generic 500.
- **`tests/test_p4_target_business_context.py`:** Add two deterministic *simulated interleaving* checks: a version change between initial API check and storage commit, and project archiving in the same gap. Both must return **409**, preserve empty target-context records and create no experiment. Existing disposable fixtures now create synthetic `quality_state` rows, modelling the real registered-project invariant.
- **`tests/test_p4_phase_exit_matrix.py` / `tests/test_p4_consolidated_acceptance.py`:** Seed/update matching synthetic `quality_state` rows when a mocked `quality.current_data` changes its version. This validates the new storage boundary without requiring owner source files or real Quality commits.

No inference, target recommendation, model training/selection, source CSV, Quality operation, native Tauri, UI component, release artifact or installed project was modified by the fix. An explicit user-submitted target description remains **unverified**, not objective proof of a valid decision, and only authorised saves persist.

## Verification and acceptance boundary

| Evidence family | Observed outcome and limits |
| --- | --- |
| P4 exact-source Python including both save-race regressions | **110/110 PASS** in #42696149447 |
| P4 frontend Node contracts | **28/28 PASS** in #42696149447 |
| P4 production TypeScript/Vite bundle | **PASS** in #42696149447 |
| Disposable real-HTTP Chromium target-review suite | **8/8 PASS** in #42696149447 |
| Related project-lifecycle and P3 semantic source/browser CI | Project-lifecycle #42696149805, P3 semantic source #42696149733 and P3 semantic browser #42696149834 **COMPLETED SUCCESS** at same code SHA |
| P2 saved-revision/report and P1 source recovery adjacent workflows | #42696149579, #42696149694, #42696149671 **COMPLETED SUCCESS** at same code SHA |
| P1 real-HTTP browser adjacent workflow | **IN PROGRESS at report drafting**; do not infer a pass from other workflows |
| New P4 atomic guard on owner's physically installed Windows Tauri/WebView2 | **NOT TESTED**; QA installation remains earlier exact source `bca3c57b94a425cd9ef489726e721328d12c2ead` |
| Real simultaneous thread/process schedule under owner Windows | **NOT DIRECTLY REPRODUCED**; deterministic forced interleaving and SQLite transaction lock semantics tested via synthetic API |
| Measured native 8 GB/offline and full data-integrity/restore | **OPEN / NOT FULLY TESTED**; no installer, old-project operation or model training executed |
| Original operational Gate C label/time/group/baseline/cost/fairness proof | **UNVERIFIED AND NOT WAIVED**; saved user text does not establish independent truth |

## Residual risks, follow-up and phase

**P4-21-01:** Target-description save race is **SOURCE-FIXED / CI PASS / OWNER-NATIVE NOT RETESTED**. It is not a model-training or active-user-data incident. The table named `target_business_context` remains only a durable owner-described context record; successful POST never marks label truth/decision usefulness verified.

**Unchanged Gate C and native risk:** The owner has not approved a P4 closure deferral or real operational label evidence. N8–N12 physical negative/version/no-original-write checks, restored backup integrity, owner desktop/UI source-fix retest and 8 GB/offline resource measurements remain OPEN. The installed older QA app remains intact. The broader issue register includes BE-024 Prepare usability and critical/high product-wide defects for later phase/release triage.

**Next risk-first work:** Do not broaden into endless target edge cases or another 1.5 GB installer per patch. Prioritise **one consolidated owner-authorised native milestone with actual 8 GB/offline memory observations and original-app preservation** after sufficient source fixes, and a separately grounded real operational case for Gate C. If a critical data-integrity fault is independently demonstrated before then, use the narrow safety exception to fix it immediately.

**Binding phase state:** P4 **ACTIVE / CLOSURE NOT APPROVED**; P5 **NOT AUTHORISED**, P8 **NOT CERTIFIED**. Master QA #2 and P4 evidence Issue #9 **OPEN**. This source check does not waive any exit requirement.
