# PilotODIN 1.0 | P4-62 Prepare exclusion review and first prospective CI-shadow witnesses

**Date:** 12 November 2026. **Active branch:** `feature/live-dev-workspace-20261023`. **Final source SHA verified:** `d248455450a4d6be42b6207718fb32e335ee510b`. **Phase:** P4 Target Intelligence ACTIVE, P4-R01–R06 OPEN. **Scope:** one genuine BE-024 Prepare usability/safety correction plus two strictly manual, naturally observed P1 workflow outcomes under the P4-61 frozen candidate-evaluation rule. Not a native build, installed application acceptance, operational business utility study or risk waiver.

## 1. Confirmed BE-024 requirement and bounded implementation

[Master QA Issue #2](https://github.com/Sonkhe-Shongwe/PilotODIN/issues/2) BE-024 explicitly required the Prepare high-risk suggestion control to **display and approve the precise inclusion/exclusion diff**, never silently overwrite prior manual exclusions. Existing `App.tsx` already merged suggestions without replacing exclusions, but the button still **applied them immediately**, without presenting the proposed change first.

[Source commit `bd9e098`](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/bd9e0987c998cef658c01d5243e9eb57f4ca0610) changes only:
- `frontend/src/App.tsx`: a separate **Review high-risk exclusion suggestions** step, with candidate names, newly excluded fields, preserved existing manual exclusions, included-predictor counts before/after, an explicit **Apply reviewed exclusions** confirmation and **Cancel exclusion review**. No edit is reported to the primary Studio shell until an actual new exclusion is committed. Preview is reset for project/target/Quality-version changes. Selected checkbox exclusions are merged, not overwritten.
- `frontend/tests/p1-primary-button-edit-markers.test.cjs`: real compiled handler tests for no edit before review, no-op, add, queued-checkbox preservation and embedded Studio draft rules.
- `frontend/tests/ml-a3-feature-preparation.test.cjs`: source contract for the two-step preview, before/after count and cancellation.
- `frontend/e2e/p4-real-http-review-queue.spec.ts`: disposable real-HTTP UI test for preview, cancel, additive apply, manual checkbox preservation, zero experiment creation, and no unexpected network writes.

**Important limits:** This meets **the explicit approval/diff portion** of BE-024 in source/browser tests. BE-024's other requested per-feature sample categories, supported preprocessing overrides, full immutable experiment-config semantics and actual owner-native Prepare observations are not declared accepted or closed. No model fit or original dataset mutation occurs.

## 2. Preserve the first exact-source CI failure

At `bd9e098`, normal push-triggered workflows:
- [P1 Isolated Frontend Verification #43219452141](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/43219452141): **COMPLETED SUCCESS** at that exact SHA; **185 Node tests PASS**, TypeScript/Vite build PASS, **7 synthetic Chromium cases PASS**.
- [P2 Report Export Draft Safety #43219451939](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/43219451939): **COMPLETED SUCCESS**, 97 Node checks and production frontend build.
- [P4 Target Review #43219451921](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/43219451921): **COMPLETED FAILURE**. Python 180 PASS, Node 47 PASS, frontend TS/Vite build PASS, Windows synthetic PowerShell safety PASS and nine of ten browser tests PASS. **New P4-62 test failed at fixture upload HTTP 422**, before rendering the review UI. Exact test-fixture cause: escaped literal `\\n` row separators rather than real CSV newlines. This is a **new test-fixture preparation defect**; it is not evidence the owner application was tested and failed or that actual datasets were damaged. The failed run remains in history.

One-file [correction `d248455`](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/d248455450a4d6be42b6207718fb32e335ee510b) changes **only** the newly added CSV fixture separator in `frontend/e2e/p4-real-http-review-queue.spec.ts`. Before pushing it, an isolated source-expression evaluation confirmed a four-column CSV with **one header plus 80 synthetic rows**.

## 3. Exact-source verification after bounded correction

All ordinary push-triggered workflows at source SHA `d248455450a4d6be42b6207718fb32e335ee510b`, with **no manual workflow dispatch**:
- [P1 #43220367222](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/43220367222) **COMPLETED SUCCESS**: **185 Node tests**, TypeScript/Vite build and **7 isolated Chromium tests PASS**.
- [P4 #43220367214](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/43220367214) **COMPLETED SUCCESS, 3/3 jobs**: **180 Python tests**, **47 Node tests**, TS/Vite build, **10 disposable real-HTTP Chromium tests**, and hosted Windows PowerShell 7 / 5.1 **synthetic original-storage/WebView safety probes** all PASS.
- P2's passing source run was at prior `bd9e098`; no P2 run is claimed for the one-file fixture-only `d248455` change.
- Neither workflow compiled a native installer, observed a personal physical 8 GB machine/Qwen runtime or measured real-world prediction value.

**Technical disposition:** P4-62 scoped source/frontend/browser review interaction PASS at `d248455`. No installed/native Windows acceptance claim and no closure of full BE-024 or broader phase gates.

## 4. P4-61 manual-only prospective study, witnesses before each push

Under [P4-61 charter](./P4_61_OWNER_APPROVED_MANUAL_CI_GATE_C_FEASIBILITY_2026-11-12.md) the human owner approved **candidate feasibility evaluation only**, no model training, extra/manual CI execution, intervention, install/native build, gate waiver or phase closure.

| Genuine change | GitHub pre-push witness | Commit (committer UTC) | Frozen rule recommendation | First naturally triggered P1 outcome |
| --- | --- | --- | --- | --- |
| BE-024 source and tests | [Issue #9 witness #6823762508](https://github.com/Sonkhe-Shongwe/PilotODIN/issues/9#issuecomment-6823762508), created **12:35:31Z** | `bd9e098`, **12:36:24Z** | **YES** hypothetical `npm run build --prefix frontend`, because `frontend/src/App.tsx` changes | [#43219452141](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/43219452141), created **12:36:29Z**, **SUCCESS** |
| Observed fixture correction | [Issue #9 witness #6823903413](https://github.com/Sonkhe-Shongwe/PilotODIN/issues/9#issuecomment-6823903413), created **12:42:06Z** | `d248455`, **12:42:23Z** | **NO**: test-only `frontend/e2e/` change, no listed build-risk trigger paths | [#43220367222](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/43220367222), created **12:42:27Z**, **SUCCESS** |

Both issue witnesses preserve the **frozen rule output**, path list, base SHA, proposed content-addressed new Git blob SHA(s), pre-commit fullfile patch SHA-256, change purpose and explicit no-extra-check declaration. Their GitHub **server timestamp precedes each commit's recorded committer timestamp and the corresponding P1 run creation**. This is persuasive **pre-commit recommendation chronology**, but does not independently prove the actual git push instant, signed human choice, git-index patch equivalence or immutable local time records.

**Study measurement boundaries:**
- **2 prospective externally timestamped rule recommendations**, **2 exact-SHA first P1 matches**, **2 P1 successes**, **0 P1 failures**, **0 P1 censored runs** among these two; no statistical conclusions.
- **0 independently verified owner decisions to carry out an extra check**, **0 actual additional preflight checks**, human diagnostic time **NOT SUPPLIED**, preflight time **NOT SUPPLIED**, avoided incidents **NOT ESTABLISHED**, relative decision utility / ROI **NOT ESTABLISHED**.
- No complete P4-57 `pre.jsonl`/`post.jsonl` provenance-validated study is asserted. GitHub's commit author/committer timestamps and workflow creation do not establish the exact `push_at_utc` required by that schema. Do not invent a push timestamp or backfill an owner choice to satisfy the validator.
- The **P4 real-HTTP failure at the first SHA despite P1 PASS** illustrates a critical scope limitation: P1 success is not a substitute for all other workflow outcomes. Do **not** turn the P4 test-only failure into a `P1 failure` or retrospectively change the frozen YES/NO recommendations.
- All observed CI was triggered **normally by genuine P4 development pushes**. No manual dispatch, targeted extra check, auto-monitoring hook, training, deployment or CI-workflow edit.

### Feasibility verdict and next evidence

**A pre-commit shadow recommendation can be timestamped independently in GitHub and reconciled to a subsequent exact source SHA and existing P1 outcome.** This confirms a narrow observation *mechanism*, **not real decision benefit or eligibility under the original Gate C acceptance charter**. The two observations are far too small for predictive/causal inference.

When further genuinely necessary frontend work arises, capture the frozen rule before the normal push, then review its exact first P1 outcome later. Do not create patches to increase sample count. A future legitimate operational decision owner, independently sourced label/failure attribution, actual action/time/cost and controlled baseline remain necessary before any business-value or Gate C claim.

## 5. Restrictions unchanged

**P4 ACTIVE, P4-R01–R06 OPEN, real-world Gate C UNVERIFIED, BE-024 remaining acceptance OPEN, P5 NOT AUTHORISED, P8 NOT CERTIFIED.** Original owner full app-local-data strict preservation **FAIL** remains (320 backed-up vs 346 observed entries, 74 cache/WebView candidates; writer UNKNOWN). Prior original protected `data/` subtree 0 observed differences is narrower evidence, not a waiver. No additional installer/native build permitted; one-off P4-47 native and P4-55 model-fit authority consumed.

**Next engineering priority:** obtain independent owner operational use-case evidence and eventual separately authorised source-matched native/physical Windows acceptance. Do not start new model fits, artificial CI executions or arbitrary feature-screen patches to manufacture progress.
