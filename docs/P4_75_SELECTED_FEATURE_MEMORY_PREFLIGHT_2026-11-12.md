# PilotODIN P4-75 | Selected-feature Prepare memory preflight

**12 November 2026.** Bounded P4/BE-024 usability and accurate resource guidance. No original owner data, native build, installer, model fitting, or phase advancement.

## Confirmed source-level mismatch

The Python engine recomputes the fit-time estimate from effective non-empty, non-excluded **labelled** predictor columns. Numeric width is 1; categorical one-hot width is capped at 25; its dense limit is 256 MiB. Prepare previously kept displaying `prep.resource_plan`, an **all-usable-candidate** estimate fetched before manual exclusions. A user could exclude high-cardinality features and the resource warning remained overstated. The old Model Lab **Train button was disabled by model-family row limits, not by this stale dense estimate**. No false historical dense-related button disable is claimed.

## Bounded implementation

- New pure `frontend/src/selectedFeatureBudget.ts` computes a **conservative selected-feature estimate** from version-pinned `feature_audit` fields. It honours exclusions, excludes unusable fields and removes the group/time split key. Numeric contribution is one column; categorical contribution `min(25,max(1,distinct))`; estimated bytes equal `labelled_rows × encoded_width × 8`. It rejects invalid metadata, unsafe integer arithmetic, no predictors and over-budget selected matrices.
- Prepare's resource guidance now reflects **current selected predictors** rather than all candidates. It identifies approximate matrix bytes/encoded width as an advisory upper bound, **not** measured peak system RAM or training authority. The Python backend remains the final admission gate on the labelled effective dataset.
- Model Lab separately evaluates **model-family row limits** and **selected-feature dense estimate**. The Train button and the existing start handler refuse a known over-budget/empty selection before a request. Backend validations, split/leakage checks, memory controls, model selection and training pipelines are unchanged.
- Six locally executed pure-helper tests PASSED: categorical cap, exclusions, group/time split keys, a large matrix becoming feasible after exclusion, no features, malformed/non-finite metadata. The exact helper and tests are identified by Git blob hashes `4cc08dbcf61ca4db65587183a8cf4a59272c48ad` and `e3bc0a90c4f0be5b0b809bda42e729931d7c2213`.
- The existing synthetic P4-62 Chromium journey is extended to assert estimated encoded columns update **28 → 26 → 1** under successive manual and suggested exclusions, while keeping the P4-74 field audit, HTTP 409 version pinning and **zero experiment history** checks. CI outcome must be separately verified, never presumed.

## Explicit limitations and prohibitions

No configurable per-column preprocessing algorithms (e.g., categorical alternative encoders) are added, and **BE-024 remains OPEN**. No model fit was run, and no physical Windows-native, 8 GB/offline Qwen, operating decision or Gate C acceptance was observed. This is a frontend preflight/clarity correction, not an observed saved-time, accuracy or actual memory benchmark.

**Governance unchanged:** P4 ACTIVE; R01–R06 OPEN; real business Gate C UNVERIFIED; historical original entire app-local-data STRICT FAIL (320 baseline vs 346 observed, 74 different files, past writer UNKNOWN); P5 NOT AUTHORISED; P8 NOT CERTIFIED. Previous one-use native/model-fit authorisations consumed. No original app or installer touched.
