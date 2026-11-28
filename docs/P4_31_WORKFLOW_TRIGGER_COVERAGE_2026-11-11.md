# PilotODIN 1.0 | P4-31 GitHub Actions test-trigger coverage

**Date:** 11 November 2026. **Scope:** P4 CI correctness and continuity. No application feature, installer, model or owner data changed.

## Confirmed workflow gap

The P4 GitHub Actions workflow `.github/workflows/p4-target-ranking.yml` runs focused Python tests and Node contracts, but at prior `11b89f17` seven of those executed test files were **not present in `on.push.paths`**. A commit modifying only one of these tests would not independently trigger this P4 workflow. Recent P4-29 and P4-30 code commits triggered CI through the concurrently edited `backend/target_opportunities.py` file; that did not prove test-only commits had coverage.

The missing trigger paths were:

- `tests/test_p4_target_opportunities.py`
- `tests/test_p4_target_business_context.py`
- `tests/test_p4_prediction_timing_review.py`
- `tests/test_p4_two_axis_evidence.py`
- `frontend/tests/p4-business-context-contracts.test.cjs`
- `frontend/tests/p4-prediction-timing-contracts.test.cjs`
- `frontend/tests/p4-two-axis-contracts.test.cjs`

## Implemented

[Exact source `6585d4424cce3dc0c98f70ebf8d919efb07126e9`](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/6585d4424cce3dc0c98f70ebf8d919efb07126e9):

1. Add the seven previously omitted test-file entries to `on.push.paths` without expanding workflow into unauthorised phases or changing existing test commands.
2. In `frontend/tests/p4-review-queue-contracts.test.cjs`, add a regression assertion that the workflow's **16 referenced focused P4 Python/Node test files** are all included in the push filter. This is a source-contract check; it verifies filter membership, not GitHub's entire event scheduler.

Both changes were confined to the existing P4 workflow and its P4 test contract. No dependencies were added, no non-test source code was rewritten, no app launched, and no owner filesystem files were accessed or modified.

## Exact-source verification

| Run | GitHub result | Verified scope |
| --- | --- | --- |
| [P4 #43064149245](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/43064149245) at `6585d442` | **COMPLETED SUCCESS, all 3 jobs** | Focused synthetic Python/Node source contracts, TypeScript/Vite, disposable real-HTTP Chromium, synthetic Windows preservation/PowerShell 5.1 |
| [P1 isolated frontend #43064147313](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/43064147313) at `6585d442` | **COMPLETED SUCCESS** | Adjacent frontend regressions only, not P1 phase reopening |
| Owner-installed Windows native desktop acceptance | **NOT TESTED** | Trigger fix does not certify an installed app |
| Subsequent documentation-only commit | **No fresh application CI claimed** | Results belong to exact source SHA above |

GitHub accepted the changed workflow and triggered the P4 run from the commit. The added test contract also passed as part of the P4 Node test stage. The filter change helps future test-only commits obtain routine CI checks, but it does not substitute for real Windows, privacy or operational acceptance.

## Phase and data-preservation restrictions

The original EXE and independently preserved backup matched baseline, and the source-defined protected project `data/` subtree had zero differences. However the **complete original app-data tree comparison remains FAIL** (320 baseline vs 346 current files; 74 browser/cache *candidates*; historical writer UNKNOWN). The owner-native P4-28 current WebView2 observer succeeded but did not determine who wrote those past changes.

Physical Windows UI source parity, offline local Qwen/8 GB operation, independent real-business label/timing/group/benefit/fairness Gate C and residual P4-R01–R06 remain unresolved. No baseline reset, cleanup, data change, installer, release, waiver or new phase authorised.

**Disposition: P4-31 CI correction SOURCE AND CI VERIFIED; overall P4 ACTIVE; P5 NOT AUTHORISED; P8 NOT CERTIFIED.**
