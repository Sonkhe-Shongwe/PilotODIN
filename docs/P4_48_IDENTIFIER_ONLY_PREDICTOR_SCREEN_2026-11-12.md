# PilotODIN 1.0 | P4-48 Identifier-only predictor structural screening

**Date:** 12 November 2026. **Authorised phase:** P4 Target Intelligence only. **Implementation:** [`24e1173`](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/24e1173dac25bfaa4628fd090a1bb40644530b22), corrected [`654f61f`](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/654f61f8de7882bca3c24b557b4f46842f197921). **Final exact-source CI:** [#43173575042](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/43173575042) SUCCESS, 3/3 jobs.

## Confirmed structural eligibility defect

The pre-existing read-only `_candidate` screen in `backend/target_opportunities.py` considered each non-target header with more than one observed value among labelled rows sufficient predictor variation. An 80-row synthetic frame with `churn = Y/N` (40 each) and `account_id = ID-000 ... ID-079` had two supported outcome labels and an apparently varying predictor, even though the only predictor was a unique record identifier. The current predicate would classify this **structurally reviewable**. This is a source-confirmed misleading target screening result; no original user data was inspected and **no model was trained**.

## Scope of correction

- Keep the existing `_is_identifier` naming policy. Skip identifier-like headers when requiring at least one varying, observed candidate predictor; retain identifiers in read-only aggregate repeated-ID evidence and source Quality snapshots.
- Apply exactly the same bounded `_candidate` safeguard in ranked and explicitly requested manual screens.
- Restore the established `No non-constant, non-empty candidate predictor remains.` blocker string for P4-13 partial-inspection replacement, while emitting an additional independent explanation when identifier-like headers were excluded.
- Add four parameterised negative regressions (`account_id`, `policy_number`, `customer_uuid`, `case_key`) plus one genuine predictor control. Verify blocked vs reviewable states, no automatic training, manual equivalence and complete input frame preservation.

This is only a conservative structural screen. It cannot independently verify label provenance, prediction time, true entity dependence, business utility or actual selected-model performance.

## Exact-source verification and preserved failure

| Commit / Actions | Result | Verified facts |
| --- | --- | --- |
| [`24e1173`](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/24e1173dac25bfaa4628fd090a1bb40644530b22), [#43173363772](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/43173363772) | **FAILED** | 154 Python pass, 1 pre-existing P4-13 manual truncation diagnostic failure; original change inadvertently altered exact error string expected by partial-inspection rewrite. Do not count this run as passed. |
| [`654f61f`](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/654f61f8de7882bca3c24b557b4f46842f197921), [#43173575042](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/43173575042) | **SUCCESS 3/3** | 155 Python pass, 45 Node pass, TS/Vite build pass, 9 real-HTTP Chromium pass, synthetic Windows original-data/WebView checks pass on PowerShell 7 and 5.1. |

Tests used disposable generated fixtures, hosted runners and existing declared test dependencies. No new source-specific native compilation, installer, bundled Qwen or physical owner hardware test occurred. A green synthetic test does not provide Windows release or P4 phase-exit certification.

## Unchanged owner boundaries and next requirement

P4-R01–R06 remain OPEN. R06's 320-vs-346 whole original app-data file mismatch and 74 browser/cache *candidates* remain historical strict **FAIL** with unknown writer; earlier scoped original `data/` comparison found 0 differences, but that does not close whole-tree preservation. Independent real business Gate C and native functional version/negative checks, UX/Prepare acceptance and sustained physical offline 8 GB Qwen are not supplied by this increment. Owner refused risk deferral on 9 November; P4 is active, P5 unauthorised and P8 uncertified. P4-47 one-use native permission is consumed. Do not repeat native compilation or perform owner-machine actions on `next`.

**Next:** obtain genuinely independent owner/business label and decision context plus separately authorised source-matched, isolated functional Windows evidence; continue source code changes only on a reproducible P4 defect.
