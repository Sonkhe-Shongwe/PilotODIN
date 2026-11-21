# PilotODIN 1.0 | P4-63 Prepare feature-advice scope, CI regression and prospective shadow outcomes

**Recorded:** 12 November 2026. **Branch:** `feature/live-dev-workspace-20261023`. **Latest exact source/test correction:** `ecbc81ddcfd7601467df235969bc052b81a4153b`. **Active phase:** P4. **Status:** Focused source safety change CI verified, P4-R01–R06 and full BE-024 acceptance still OPEN. Not an owner-native/physical Windows, 8 GB/offline AI, real-business Gate C, release or original-data integrity acceptance.

## Confirmed source-risk boundary and implementation

- Existing `frontend/src/App.tsx` held `featureHints` as a bare array fetched asynchronously for a chosen target. When switching target/project/Quality version, advice from the previous selection could remain in the render until new advice arrived and was used by P4-62's exclusion preview/apply action. This is a **source-confirmed stale evidence hazard**, not a witnessed real user-data incident or proof of model leakage.
- [P4-63 source `0b1f9b1`](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/0b1f9b1611ff4939db79996101a9282d7a2eec60) adds `frontend/src/featureHintScope.ts` with the pure `visibleFeatureHints` gate (exact project ID, target and Quality version) and binds received advice to the request's captured identity. Target/project/version mismatch returns no feature hints immediately, including while a stale request is pending. Project load resets scoped state. The existing in-flight effect cleanup still guards late responses.
- The only source and test changes at `0b1f9b1`: `frontend/src/App.tsx`, `frontend/src/featureHintScope.ts`, `frontend/tests/ml-a3-feature-preparation.test.cjs`, `frontend/tests/p1-primary-button-edit-markers.test.cjs`. Synthetic unit cases cover exact match, project switch, target switch, Quality version switch, unselected state and old-version late result, without ML/data writes.
- **Limit:** The backend `/features?target` endpoint itself does not return an independently signed response version. This change binds what the frontend requested and prevents cross-selection stale local advice. It does not independently certify the backend snapshot or close every BE-024 preprocessing requirement.

## Preserve first exact-source CI failure and scoped correction

At `0b1f9b1`, naturally triggered workflows:
- [P4 Actions #43222817559](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/43222817559) **COMPLETED SUCCESS 3/3 jobs**: 180 Python PASS, 49 Node PASS, TypeScript/Vite build PASS, 10 disposable real-HTTP Chromium PASS, hosted Windows PowerShell synthetic storage/WebView safety PASS.
- [P2 Actions #43222817585](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/43222817585) **COMPLETED SUCCESS**: 97 Node PASS and frontend build PASS.
- [P1 Actions #43222817679](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/43222817679) **COMPLETED FAILURE**: **178/186 Node tests PASS, 8 FAIL**, before TypeScript/Vite and browser stages. P1 contract `p1-playwright-pilot-contract.test.cjs` demanded the old unscoped `setFeatureHints([])` string; P1 project-switch `loadProject` harnesses injected the old `setFeatureHints` function rather than the current `setFeatureHintSnapshot`, causing otherwise unrelated success assertions to fail. These are **source-contract/test-harness alignment defects**, not proof the current UI genuinely failed project switching.
- [Focused test-only repair `ecbc81d`](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/ecbc81ddcfd7601467df235969bc052b81a4153b) changes precisely `frontend/tests/p1-playwright-pilot-contract.test.cjs`, `frontend/tests/p1-primary-project-load-approval.test.cjs` and `frontend/tests/p1-project-switch-generation.test.cjs`. It updates expectations to the new fail-closed scoped reset and injects the correct setter in extracted loader tests. **No application source, model, workflow, installer or owner dataset changed.**
- [P1 Actions #43223536199](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/43223536199) at the exact corrected test SHA **COMPLETED SUCCESS**: **186 Node tests PASS**, TypeScript/Vite build PASS, **7 isolated Chromium cases PASS**. No second P4/P2 run was triggered by the P1-only test repair; their verified application source remains from prior `0b1f9b1`.

**Verification disposition:** The targeted P4-63 frontend scope correction has passed P4/P2 source/synthetic checks and all P1 tests after fixing test harnesses. The original P1 FAILED run remains a recorded failed run; later success does not convert it to PASS.

## P4-61 prospective CI candidate feasibility, frozen recommendation chronology

For these genuinely justified source and test changes, operator-computed [P4-61](./P4_61_OWNER_APPROVED_MANUAL_CI_GATE_C_FEASIBILITY_2026-11-12.md) YES/NO recommendations were independently timestamped in GitHub **before each source commit**. The frozen rule did **not** change after failures, and no extra preflight was actually executed.

| Change | Prior GitHub timestamped shadow witness | Frozen recommendation | Earliest exact-SHA normal P1 outcome |
| --- | --- | --- | --- |
| P4-62 Prepare UI | [#6823762508](https://github.com/Sonkhe-Shongwe/PilotODIN/issues/9#issuecomment-6823762508) | YES, hypothetical frontend build | [#43219452141](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/43219452141) SUCCESS |
| P4-62B observed fixture correction | [#6823903413](https://github.com/Sonkhe-Shongwe/PilotODIN/issues/9#issuecomment-6823903413) | NO, test-only | [#43220367222](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/43220367222) SUCCESS |
| P4-63 scoped feature advice | [#6824244783](https://github.com/Sonkhe-Shongwe/PilotODIN/issues/9#issuecomment-6824244783), created **12:57:53Z** | YES, source TS/TSX | [#43222817679](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/43222817679) FAILURE, 8 stale test-contract failures |
| P4-63B test-harness repair | [#6824344611](https://github.com/Sonkhe-Shongwe/PilotODIN/issues/9#issuecomment-6824344611), created **13:02:22Z** | NO, test-only | [#43223536199](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/43223536199) SUCCESS |

**Counts and limits:** 4 prospective server-timestamped **rule** recommendations, 4 first exact-source P1 run matches (3 SUCCESS, 1 FAILURE, 0 cancelled); **0 independently witnessed owner preflight actions**, **0 actual additional checks**, measured human debug minutes **not supplied**, **no measured saved time or causal avoided failures**. The P4-63 failure's underlying issue is observable in source and CI, but its independent study `failure_attribution` remains **unadjudicated**, not automatically `new_actionable`. The shadow observations do not provide independently authenticated exact push timestamps or a complete validated private pre/post JSONL dataset under P4-57/58; do not manufacture these after the event. P1 only checks a subset of frontend risks, and a P1 failure or success is not equivalent to P4 acceptance.

**Gate C status:** Still **UNVERIFIED**. There is no independently approved real-business decision charter, label/time independence evidence, observed counterfactual action, human cost or quantified benefit. This remains only a prospective instrumentation feasibility signal. No deliberate development push, test or CI action was created exclusively to collect study samples.

## Owner-controlled gates and next

P4 **ACTIVE**, P4-R01–R06 **OPEN**, broader BE-024 usability/native Prepare evidence **OPEN**, historical original entire app-local-data integrity **STRICT FAIL** (320 backed-up vs 346 observed files, 74 WebView/cache candidates, historic writer UNKNOWN), critical original `data/` subtree scoped 0 differences, **P5 NOT AUTHORISED**, **P8 NOT CERTIFIED**. Owner no-intermediate-installer freeze, refused P4 risk deferral and consumed P4-47 native/P4-55 model-fit one-time permissions remain binding.

**Next legitimate milestone:** Independently corroborate the proposed operational decision, labels, baseline and actual benefit for Gate C. Separately request express owner approval before any isolated native/physical 8 GB/offline acceptance work. Do not create additional minor source changes just to increase study N.
