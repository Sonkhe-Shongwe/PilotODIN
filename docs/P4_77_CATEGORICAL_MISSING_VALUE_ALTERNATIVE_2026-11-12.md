# PilotODIN P4-77 | Guarded categorical missing-value strategy

Date: 12 November 2026. Scope: a bounded BE-024 Prepare improvement inside authorised P4. No model fit, data mutation, native compilation, installer, manual CI dispatch or reuse of prior one-off approval.

## Confirmed gap and implementation

P4-76 added a validated median/mean selection for numeric predictors, but the existing categorical model pipeline used only most-frequent imputation. P4-77 extends the *actual training configuration*, not merely the explanation shown on screen.

- Frontend: a separate categorical selector offers mode / most_frequent (backwards-compatible default) or constant reserved missing marker. Both settings reset upon project, target or Quality version change. The field-level audit retains the backend-provided description for the default strategy; explicit marker selection shows its own truthful treatment. The draft state and experiment request carry the selected value.
- API: strict Pydantic Literal most_frequent or constant and optional backwards-compatible request default. The setting is persisted with experiment config, sent to the background worker and included in training result metadata.
- Python engine: both the baseline and every candidate use the requested categorical SimpleImputer inside fold-local preprocessing and capped OneHotEncoder. The reserved marker is __PILOTODIN_MISSING__. A real observed category with that exact value triggers a validation error *before creating an experiment* and is also refused by the pipeline helper. This avoids silently coalescing a real category with a missing value. The limited 25-category one-hot policy may still group rare marker values into the infrequent bucket; the UI discloses this.
- Source/test files: backend/engine.py, backend/main.py, frontend/src/App.tsx, frontend/src/api.ts, tests/test_p4_consolidated_acceptance.py, frontend/tests/ml-a3-feature-preparation.test.cjs, frontend/e2e/p4-real-http-review-queue.spec.ts. Tests check allowed/default/rejected strategies, unfitted sklearn pipeline configuration, marker collision, stubbed worker propagation and synthetic browser mode-to-marker-to-mode UX. No training experiment was created in the browser case.

## Exact source and actual CI chronology

1. Initial source [4937ba02](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/4937ba02c5cead7dcf5f26da29eb8a2c3158e3d4) produced [P4 run #43294157690](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/43294157690) **COMPLETED FAILURE**. Its Python 183 and independent browser 10/10 tests passed; synthetic Windows preservation checks passed. The P4 Node source-contract step FAILED because the first implementation replaced the backend-derived default categorical treatment description with frontend-composed wording. The P4 TypeScript/Vite step was SKIPPED after the failure. [P1 #43294157680](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/43294157680) succeeded separately on that first source. Preserve the failed P4 outcome.
2. One-file correction [7458cab4](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/7458cab46baa3e9fc6b98f67277a6d1d3240b7b2) restores the backend's treatment for default mode, using a specialised description only when marker is explicitly selected. No backend test or result was rewritten.
3. Exact corrected source [P4 #43294447975](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/43294447975) **COMPLETED SUCCESS, 3/3 jobs**: 183 Python tests PASS, 59 Node tests PASS, TypeScript/Vite PASS, 10/10 disposable real-HTTP Chromium PASS and hosted synthetic Windows PowerShell preservation/WebView safety PASS. [P1 #43294447676](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/43294447676) **SUCCESS**: 187 Node tests, TypeScript/Vite and 7/7 isolated Chromium PASS. [P2 #43294447768](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/43294447768) SUCCESS. All occurred by normal push triggers; no manual dispatch.

## Governing evidence boundaries

This is genuine source implementation and synthetic/integration evidence, not measured model performance, an actual new fit, physical owner Windows/native interaction, 8 GB offline-Qwen feasibility, operational benefit or release certification. BE-024 remains OPEN for wider per-field controls and native acceptance.

P4 ACTIVE; P4-R01-R06 OPEN; original real-business Gate C UNVERIFIED; newest-source native N2-N12 NOT TESTED; physical offline 8 GB NOT TESTED; historical original entire app-local-data STRICT FAIL (320 baseline, 346 observed, 74 differences, historic writer UNKNOWN). Previous native/model-fit one-use approvals CONSUMED, no new installers through P4-P7. P5 NOT AUTHORISED and P8 NOT CERTIFIED.

Next: independent real Gate C decision owner and utility evidence, plus separately authorised native/physical acceptance when available; further BE-024 work only if materially justified, with no speculative training or premature closure.
