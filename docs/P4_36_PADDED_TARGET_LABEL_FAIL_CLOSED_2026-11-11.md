# PilotODIN 1.0 | P4-36 Whitespace-padded target label structural safety

**Date:** 11 November 2026. **Phase:** P4 ACTIVE. **Scope:** P4 read-only supervised target screening, not training, Quality cleanup, native install or phase exit.

## Precise source-confirmed failure mode

The P4-29 screening fix masked fully empty or whitespace-only target strings, but a **nonempty label padded with whitespace** still remained a literal distinct class. A synthetic 80-row frame with `churn=["Y"]*40+["Y "]*40` and a varying numeric predictor therefore looked like 80 valid observations across two 40-row classes, even though both values have the same substantive meaning absent formatting inconsistency. Without Quality review, the class hypothesis could be misleadingly shown as structurally reviewable.

This is an **identified source condition and synthetic reproduction**, not a claim that the owner's actual datasets contained such values. These P4 statistics are screening-only, not proof of label truth or a basis for autonomous training.

## Exact bounded correction

[Source `d6ad1495643e8d8435423b610f7146faf6786bce`](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/d6ad1495643e8d8435423b610f7146faf6786bce) edits only `backend/target_opportunities.py` and `tests/test_p4_target_opportunities.py`.

- In `_candidate`, retain the existing blank-text mask and add a local padded-text mask for **nonempty strings** where `value != value.strip()`. Report effective valid/invalid target counts using a temporary masked Series.
- **Block the entire P4 outcome hypothesis** when any such padded target value is observed; require explicit Quality correction, never silently strip or impute labels.
- Keep internal spaces that are part of legitimate text labels, e.g. `"in progress"` and `"not resolved"`, unchanged and eligible for **structural review only**, subject to all other P4 conditions.
- Apply the same `_candidate` result to both queue recommendations and explicit manual target inspection. Both continue reporting `safe_to_train_automatically=false` and no user-data mutations.
- Preserve bounded row/column preview limits: if a queue or manual inspection is truncated, it remains blocked irrespective of values in the scanned sample. An absence of padded labels in an incomplete sample is **not** proof of clean data.

The patch does **not** change actual training preprocessing, project-storage schema, model fitting, installed original app, real-world target approval or release credentials.

## Verified exact-source CI

| Evidence at SHA `d6ad149` | Actual result | Boundary |
| --- | --- | --- |
| [P4 workflow #43084564958](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/43084564958) | **COMPLETED SUCCESS, all 3 jobs** | Source-only and synthetic/disposable checks |
| Five parametric leading/trailing whitespace examples | **PASS** | Synthetic pandas frame, manual + queue |
| One padded outcome among otherwise supported plain labels | **PASS** | Blocks entire outcome, no silent imputation |
| Two clean categorical outcomes containing internal spaces | **PASS** | Still reviewable but not training-authorised |
| Existing P4 Python, Node contracts and TS/Vite | **PASS** | No desktop packaging |
| Disposable real-HTTP Chromium and synthetic Windows/PowerShell 5.1 safeguards | **PASS** | Not an owner-native installed app |
| Owner physical Windows QA for this source | **NOT RETESTED** | Final installer freeze remains binding |

## Unchanged preservation, Gate C and phase status

Original independent backup and original installed executable matched their baselines, and the original critical project `data/` subtree showed no detected changes. Nevertheless the **strict original whole app-data tree preservation gate is FAIL** (320 baseline vs 346 current files, 74 WebView/browser-cache *candidates*, historic writer UNKNOWN). Prior current-process-profile diagnostics do not identify historical writes. No cleanup, new baseline, cache exclusion waiver or risk deferral authorised.

Latest owner-installed native UI, actual air-gapped/offline Qwen on 8 GB Windows and a verified operational business decision/label timeline/group split/baseline/benefit/fairness **Gate C** remain unverified. No further intermediate installers or packaging until final P8 with separate explicit owner approval.

**Disposition: P4-36 SOURCE FIXED / EXACT-SOURCE CI PASS / OWNER-NATIVE NOT RETESTED. P4 ACTIVE, P4-R01–R06 OPEN, P5 NOT AUTHORISED, P8 NOT CERTIFIED.**
