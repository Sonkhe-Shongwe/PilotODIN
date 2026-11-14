# PilotODIN 1.0 | P4-64 read-only Prepare and feature advice Quality-version binding

**Date:** 12 November 2026. **Branch:** `feature/live-dev-workspace-20261023`. **Verified source SHA:** `969ab82d7e4c0fdc9faba5745671fcd7c27e002e`. **Phase:** P4 Target Intelligence ACTIVE. **Scope:** version-provenance correctness, no new modelling, intervention, native build or installer.

## Confirmed defect boundary

The previous P4-63 source checked that a feature-advice response was associated with the currently selected project, target and Quality version **as requested by the frontend**, but `GET /api/projects/{project_id}/features` did not require the dataset version. `GET /preparation` had the same omission. The backend could therefore compute a response from a newer committed Quality revision than the frontend requested, and the frontend had no response-level proof that its advice or preparation plan matched the displayed revision. This is a source-confirmed stale-data race **risk**, not evidence that a real owner project or trained model was affected.

## Correction committed

[Source commit `969ab82`](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/969ab82d7e4c0fdc9faba5745671fcd7c27e002e) changes exactly seven source/test files:
- `backend/main.py`: both read-only endpoints accept optional `expected_version` for backward compatibility. A pinned request returns HTTP **409** when its working Quality revision differs. Both call the existing `_require_p4_review_version_fresh` committed-SQLite recheck after computing results, before returning the response, to detect a mid-computation version advance. `preparation` returns `quality_version`; `features` already returns `version`. A missing or negative version does not grant a stale pinned Studio request approval. Existing read-only unpinned external clients remain supported, **without the version guarantee**.
- `frontend/src/App.tsx` and `frontend/src/api.ts`: Studio always pins the displayed `qualityVersion` in both URLs; it accepts a Prepare response only when **both** returned version and target match, and feature hints only when returned version matches the request identity captured in P4-63.
- `frontend/e2e/isolated-workspace.spec.ts` and `frontend/tests/p1-playwright-pilot-contract.test.cjs`: isolated synthetic read-only allowlists require exact version-pinned paths for A and B; unpinned/stale synthetic read URLs are blocked, preserving no unexpected reads/writes.
- `frontend/tests/ml-a3-feature-preparation.test.cjs`: source contract verifies pinned endpoint URLs and fail-closed response acceptance.
- `tests/test_p4_consolidated_acceptance.py`: disposable SQLite project/Quality state and synthetic dataframe assert correct responses, negative version 422, stale-version 409, and a simulated case where the loaded dataframe reports version 0 but committed Quality state has advanced to 1: **409 after scan**. Assert synthetic frame unchanged and no experiment records.

**Boundary:** Post-read committed-version check narrows, but is not an atomic database read transaction. Unpinned legacy calls have no version guarantee, and frontend version gating depends on its most recently verified Quality state. No claim about owner-native observations, actual business benefit or full BE-024 preprocessing controls follows.

## Exact-source CI results

**All ten normal push-triggered workflows at `969ab82d7e4c0fdc9faba5745671fcd7c27e002e` completed SUCCESS; no workflow manually dispatched.** Applicable checks:

| Workflow | Verified result |
| --- | --- |
| [P4 Target Review Queue #43230241556](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/43230241556) | **3/3 jobs SUCCESS**; **181 Python PASS**, **50 Node PASS**, TypeScript/Vite build PASS, **10 actual disposable real-HTTP Chromium PASS**, synthetic Windows PowerShell read-only preservation/WebView probes PASS |
| [P1 Isolated Frontend #43230242001](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/43230242001) | **SUCCESS**; **187 Node PASS**, TypeScript/Vite build PASS, **7 isolated Chromium PASS** |
| [P1 Disposable Backend/Browser #43230241608](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/43230241608) | **SUCCESS**, disposable real-HTTP browser/backend scope |
| [P2 Report Export #43230242782](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/43230242782) | **SUCCESS**, 97 Node and frontend build |
| [P1/P2/P3 six additional naturally triggered workflows](https://github.com/Sonkhe-Shongwe/PilotODIN/actions?query=branch%3Afeature%2Flive-dev-workspace-20261023) | **SUCCESS**: P1 source recovery, project lifecycle; P2 immutable revision idempotency, saved revision real-HTTP comparison; P3 semantic context and real-HTTP semantic context |

No model fit, synthetic training, manual CI dispatch, installer, native Tauri build, original owner data write or physical 8 GB/Qwen test was performed. Compilation/build here is the TypeScript/Vite frontend only, **not** a Windows native distribution or owner-native acceptance.

## Prospective P4-61 study record, without relabelling

Before commit, [Issue #9 pre-push witness #6825288440](https://github.com/Sonkhe-Shongwe/PilotODIN/issues/9#issuecomment-6825288440) was created by GitHub at **13:44:19Z**. It records base `e151f96`, seven full-file proposed Git blob identities, SHA-256 canonical patch digest `26179d5600e4192163f17015709040ef6632c5a0ab0cd30fbbb11088474568cc`, and the **frozen rule YES** because `frontend/src/App.tsx`/`api.ts` changed. Hypothetical check: `npm run build --prefix frontend`, **NOT executed as an extra pre-push action**. Commit committer time was **13:44:45Z**, and first normally triggered exact-source [P1 #43230242001](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/43230242001) created **13:44:51Z**, outcome **SUCCESS**.

Cumulative manual shadow feasibility: **5 server-timestamped prospective rule outputs**, **5 first exact-SHA P1 run matches (4 SUCCESS, 1 FAILURE, 0 censored)**. No witnessed independent **human** decision to run or skip an extra check; **zero extra preflight interventions**, no verified push-at time, no full privately logged P4-57/58 decision/outcome pair, no human debugging minutes or measured saved time, no independently adjudicated actionable-failure label, no causal benefit. The previous P4-63 P1 failure remains **FAIL**, not reinterpreted. This limited CI observation mechanism is **not** business acceptance Gate C evidence.

## Binding acceptance and next decision

P4 **ACTIVE; P4-R01–R06 OPEN; Gate C UNVERIFIED; BE-024 broader preprocessing/native review OPEN; original entire app-local-data historical STRICT FAIL** (320 baseline vs 346 observed, 74 cache/WebView candidates, historic writer UNKNOWN). No new evidence of the historic writer. **P5 NOT AUTHORISED; P8 NOT CERTIFIED.** Owner refused risk-deferral closure; intermediate installer freeze and consumed P4-47 unpackaged native/P4-55 model-fit one-use approvals remain binding.

**Next meaningful milestone:** independent real-business decision owner, labels, predecision features, baseline and benefit evidence for Gate C or a **separately expressly authorised** source-matched isolated owner/native physical 8 GB/offline acceptance test. No additional source micro-increment or manufactured CI study observation unless a fresh substantial defect is independently confirmed.
