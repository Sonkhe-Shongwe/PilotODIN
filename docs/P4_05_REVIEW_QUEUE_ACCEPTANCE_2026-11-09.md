# PilotODIN 1.0 | P4-05 Transparent Target Review Queue

**Owner direction:** 9 November 2026: after P3 was explicitly closed and the assistant proposed beginning P4-05 target recommendation work, the owner replied **"next"**. This is understood as approval to begin the **bounded P4 development increment**, not P5, P6, training, a new release or a silent target choice.

**Active phase:** P4 (Target Intelligence). **P3:** CLOSED for bounded development, documented residuals retained. **P4 full phase closure:** NOT ACCEPTED. **P8:** NOT CERTIFIED.

**Branch:** `feature/live-dev-workspace-20261023`. **Code/evidence SHA:** `ecb43e7162f002fd81a32064340e718e42419c73`. All changes are local deterministic profiling and React display. No Tauri/Rust, installer, model, dataset mutation or owner file modified.

## Preserve the pre-existing P4 work

Existing P4-01 structural screening/abstention, P4-02 owner-described target business context, P4-03 timing and label-origin questions, and P4-04 two independent evidence axes had previously received **focused development acceptance** in their own 25 October source/owner tests. The scopes are not equivalent to true business-value verification, actual prediction-time evidence, full native flow or ML training authorisation. None was redesigned or rerun separately.

## P4-05: accepted first incremental behavior

- **Explainable investigation queue, not a valuable-target score.** `backend/target_opportunities.py` now returns `ranking_contract` with explicit ordered keys: user-described decision documentation (unverified) first, observed nonmissing label support second, and stable column name last. It asserts `business_value_verified=false`, `model_performance_measured=false`, and `automatic_target_selection=false`. The legacy ordering is intentionally preserved, not secretly recalibrated or rebranded as a proven business outcome.
- **For each reviewable candidate:** `review_priority` supplies exact review position, total eligible candidates, order explanation, observed label-count caveat and four always-open proof questions (business decision, label source, prediction moment/input availability, defensible split/leakage validation). Missing labels and possible lexical timing/provenance cues add explicit investigative checks. All are conservative, bounded, read-only and `training_authorised=false`.
- **Lower-ranked alternatives visible:** the first three shortlist cards remain, plus up to 12 additional eligible reviewable candidate rows with a direct **Review this alternative target** button. The UI explains their lower position does **not** mean lower proven business value. If more eligible candidates exist, it displays a truthful omitted count and retains the existing manual target chooser.
- **Human control:** The alternative button calls the same existing `onChooseTarget(column)` callback that clears stale Prepare and experimental state. It **does not** save an approval, select a target automatically, train, tune against holdouts or bypass resource/leakage/split validations.
- **Existing blockers and abstention retained:** For no plausible outcome or structurally blocked labels, the system continues to abstain. Capped blocked examples still disclose reasons. `safe_to_train_automatically=false` remains unchanged throughout.
- **No independent business-value claims:** Owner text is a user description, not corroborated decision utility, lawful/fair use, label authenticity or availability at the decision time. The review queue's position is *not* a calibrated safety, accuracy or value ranking; real P4 decision-value ranking requires later explicit owner/governance policy and independent operational facts.

## Actual automated evidence at exact code SHA

- [P4 focused source/backend/frontend + real HTTP CI #42582746289](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/42582746289) **COMPLETED SUCCESS**:
  - **38/38 Python** across existing four P4 targeted backend files and new `tests/test_p4_review_queue.py`.
  - **17/17 Node** across existing P4 frontend contracts and new `frontend/tests/p4-review-queue-contracts.test.cjs`.
  - Frontend `tsc --noEmit` / Vite bundle **PASS**.
  - **1/1 real headless Chromium** test with an isolated, runner-owned Uvicorn/SQLite synthetic 80-row project **PASS**. It observed the ranking caveat and review checklist, opened additional reviewable targets, explicitly selected an alternative for Prepare, confirmed no browser write/auto-training, and checked no experiment was created.
- [P1 frontend compatibility #42582746278](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/42582746278) **COMPLETED SUCCESS** at the same SHA. Its original five isolated Chromium scenarios remained PASS.
- **Historical first-attempt red CI #42582192905:** New backend tests passed; one old P4 Node source contract had a stale assumption that ignored the more recent unsaved Prepare guard in App.tsx. The obsolete assertion was tightened to verify the current guard and clear-stale-state behavior in source commit `fe46b2c55bd26d44bfaac042d4732dfd2f629e35`. Final exact-source CI fully green. Do not represent the red initial job as a new product failure.
- Test conditions are disposable local backend / GitHub CI, **not actual owner Windows Tauri/WebView2** nor a final production release. No repeated owner QA is needed for this exact unaffected scope.

## What's still needed for P4 full completion

1. **Grounded business-decision assessment policy:** Add or agree defensible evidence requirements for decision/action, verified label origin and predictor timing. No fabricated numeric `predictability` or business-value percentage.
2. **Hard blockers beyond basic structural screening:** Determine appropriate response to actual invalid time/provenance, sensitive or disallowed outcomes, dataset entity/repetition, non-independent labels or missing reliable decision context, without presuming header heuristics are verified facts.
3. **Full human target-choice journey:** Prove a user can select an eligible suggested *or lower-ranked* target, inspect scientific review, and deliberately continue or abstain without unintended training or stale revision leakage.
4. **Diverse datasets and native acceptance:** Representative classification, regression, no-credible-target, repeated-entity, rare-event, insufficient-label and derived-label examples; one bounded native journey only if a native-specific requirement is newly introduced. Do not repeat accepted W1–W5 or unchanged existing P4 focused gates.
5. **P4 closure:** Freeze owner-approved scope, triage P4-specific high/critical issues, verify affected source/browser/native requirements, consent/rollback, then obtain separate owner phase closure approval. Do not begin P5 without another authorisation.

**Disposition:** **P4-05 transparent human-review queue first slice: SCOPED SOURCE + REAL HTTP BROWSER ACCEPTED.** P4 ACTIVE, full target suitability/business value not certified. No automatic target selection or model training.
