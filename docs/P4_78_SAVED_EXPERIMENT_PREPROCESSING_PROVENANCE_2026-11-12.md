# PilotODIN 1.0 | P4-78 Saved experiment preprocessing provenance

**Date:** 12 November 2026. **Scope:** bounded BE-024 transparency/correctness improvement inside active P4; source-only UI and test contracts. No training, experiment creation, saved model change, native build, installer, original-owner data access or reuse of one-time approvals.

## Verified problem

P4-76/P4-77 introduced true, saved, separately validated numeric and categorical imputation choices. The backend persisted them in experiment config and passed them to fold-local pipelines, but the existing Evaluate/Predict interface did not show those recorded settings when reopening an experiment. A user could see fresh default median/mode controls in Prepare and incorrectly infer they described the preprocessing configuration of a historical experiment. This is an **observed source-level visibility gap**, not evidence that a trained model used the wrong strategy, or that an owner experienced incorrect predictions.

## Minimal corrective implementation

[Source commit cf674b83](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/cf674b83e2915959ee7aa3c327928d46eebec949) changes only `frontend/src/App.tsx` and `frontend/tests/ml-a3-feature-preparation.test.cjs`.

A small shared read-only `RecordedExperimentPreprocessing` component displays the saved numeric/categorical choices and, when available, the historical working-data version. It is rendered in Evaluate (including queued/failed experiment states where only configuration, not successful fitting, can be asserted) and alongside Predict when a selected model exists. Values are read **only from `experiment.config`**, never from current `numericImputation`/`categoricalImputation` UI draft state.

For historical records where a strategy was not explicitly stored, the panel discloses the documented **median/mode legacy defaults as not recorded** rather than suggesting a saved selection existed. It explicitly states that the recorded configuration is not independent proof of successful model fitting. No backend engine, ML fitting path, persistence, audit baseline, stored experiment or Prepare default was modified.

The added Node source contract checks for both saved-config bindings, legacy fallback labels, version provenance, the disclaimer and placement in Evaluate/Predict. This is a **source contract**, not a standalone automated reopen-UI interaction.

## Exact-source verification

- [P4 run #43296116379](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/43296116379) at **cf674b83e2915959ee7aa3c327928d46eebec949**, **COMPLETED SUCCESS, 3/3 jobs**: **183 Python PASS, 60 Node PASS, TypeScript/Vite build PASS, 10/10 disposable real-HTTP Chromium PASS, hosted synthetic Windows preservation/WebView safety PASS**.
- [P1 frontend #43296116284](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/43296116284), same source, **COMPLETED SUCCESS**: **187 Node PASS, TypeScript/Vite build PASS, 7/7 isolated Chromium PASS**.
- [P2 report safety #43296116207](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/43296116207) **COMPLETED SUCCESS** at same source.
- These were automatic ordinary push workflows, **no manual dispatch**. They test checked-in source and existing synthetic/browser scenarios. The added provenance panel itself was not separately exercised by a true saved-experiment browser recreation or native Windows UI interaction, and must not be labelled physically accepted.

## Governing status and next evidence

P4 **ACTIVE**; P4-R01–R06 **OPEN**; original real-business **Gate C UNVERIFIED**; BE-024 wider per-column controls/native acceptance **OPEN**; latest-source native Windows interactions **NOT TESTED**, physical sustained 8 GB/offline-Qwen **NOT TESTED**, original entire application-local-data historical **STRICT FAIL** (320 backed-up files versus 346 observed, 74 differences, historical writer UNKNOWN). One-use permissions for native compiling and model fitting remain **CONSUMED**, intermediate installer freeze remains binding. P5 **NOT AUTHORISED**; P8 **NOT CERTIFIED**.

Next highest-value action requires **independently controlled operational decision, label and prediction-time provenance, non-model baseline/utility evidence** for Gate C, or **fresh explicit owner authority and suitable hardware** for physical Windows/offline 8 GB acceptance. Do not invent business outcomes, fit models, build installers, or close P4 to produce artificial progress.
