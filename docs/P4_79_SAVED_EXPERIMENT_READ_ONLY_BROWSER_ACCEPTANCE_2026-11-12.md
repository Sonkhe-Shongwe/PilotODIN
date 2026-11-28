# PilotODIN P4-79 | Read-only synthetic historical-experiment browser acceptance

**Date:** 12 November 2026. **Governing phase:** P4 ACTIVE, BE-024 limited Prepare/Evaluate provenance. **Scope:** test-only browser integration proof for P4-78 source visibility; no product-source change, training, model serialization, installed Windows testing, installer or original owner-data access.

## Why the test matters

P4-78 added a read-only summary of `experiment.config.numeric_imputation` and `experiment.config.categorical_imputation` to Evaluate and Predict, including unrecorded legacy-default labels. Its earlier acceptance only asserted source contracts; it had not actually reopened a saved-shaped experiment in the real browser. This one test addresses that specific known evidence gap, without claiming operational model fitting or full physical acceptance.

## Controlled implementation and safety

[Initial test commit `02567978`](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/025679784cbafd6cefafedf9eb36cc3a718824ae) adds a single `P4-79` test to the existing `frontend/e2e/p4-real-http-review-queue.spec.ts` suite. The existing dedicated GitHub-runner guard starts a disposable real Uvicorn backend and uploads an 80-row synthetic project before the browser request block is installed.

A Playwright **GET-only overlay** substitutes two synthetic saved-shaped experiment records at the UI boundary. One is a failed legacy experiment with both imputation fields absent; the other is a nominal completed display-only experiment with numeric `mean`, categorical `constant`, Quality version 0 and synthetic result metadata. The latter is **not an actual completed model** and has no fitted pipeline or saved artifact. The browser reopens both records via Evaluate and checks the legacy labels, explicit settings and Predict panel. All other requests remain subject to the existing strict read-only browser guard. The real backend's project endpoint is checked afterwards to assert its experiment history is still **empty**. There are **zero browser POST requests for experiments**, and no test click on Train or Generate prediction.

## Exact-source CI history and focused test correction

1. Initial test commit `02567978`: [P4 #43298867168](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/43298867168) **COMPLETED FAILURE**. The 183 Python tests, 60 Node contracts, TypeScript/Vite build and synthetic hosted Windows safety all PASS. Of 11 disposable real-HTTP Chromium cases, 10 PASS and the new P4-79 case **FAILS** with a 90-second timeout waiting for an Overview navigation button. In that case, the synthetic legacy record and its saved-default assertions had already rendered. Do not relabel the historical failure as passing.
2. Narrow test-only correction [`db811488`](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/db811488cef9a53b53736ff5d42d6643f4853ac3) replaces the fragile Overview navigation dependency with a fresh Evaluate page reload and explicit selection of the alternate synthetic record. It changes **only the P4 browser test**, not the app, server, model behaviour or safety guard.
3. [Corrected exact-source P4 #43299568196](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/43299568196) **COMPLETED SUCCESS (3/3 jobs)**: **183 Python PASS**, **60 Node PASS**, TypeScript/Vite build PASS, **11/11 real-HTTP Chromium PASS** (including P4-79), synthetic Windows PowerShell storage/WebView safety PASS. [P1 #43299568087](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/43299568087) **COMPLETED SUCCESS** on the same source: **187 Node PASS**, TypeScript/Vite build PASS, **7/7 Chromium PASS**. These were ordinary push-triggered jobs, no manual workflow dispatch.

## Acceptance boundaries

The P4-79 browser case verifies rendering and navigation through **synthetic GET response overlays**, not actual persisted training, read-back of a genuinely saved model, saved artifact fidelity, physical Windows/WebView, measured business value or resource/offline suitability. The backend's real empty experiment history is an intentional negative control. The existing P4-78 source is unchanged.

P4 **ACTIVE**, P4-R01–R06 **OPEN**, BE-024 broad/native acceptance **OPEN**, original operational Gate C **UNVERIFIED**, historical entire original app-data-tree preservation **STRICT FAIL** (320 backed up / 346 observed; 74 differences; past writer UNKNOWN). Physical owner 8 GB/offline and current-source installed native interactions still **NOT TESTED**. One-time native/model-fit approvals remain **CONSUMED**, intermediate installer freeze remains binding, P5 **NOT AUTHORISED**, P8 **NOT CERTIFIED**.

**Next:** No more incremental source-only cosmetics solely to produce a commit. Prioritise independently supplied real-business decision/label/prediction-time and baseline/utility evidence plus separately approved physical native/8 GB tests. Maintain open status honestly if those independent dependencies are unavailable.
