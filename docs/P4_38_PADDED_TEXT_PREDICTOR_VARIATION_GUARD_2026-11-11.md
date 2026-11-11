# PilotODIN 1.0 | P4-38 Padded text predictor variation guard

**Date:** 11 November 2026. **Phase:** P4 ACTIVE, no P5 authorisation. **Scope:** Read-only structural target screening and synthetic regression tests. No Windows installer, owner dataset, training, migration or production release.

## Root cause verified from current source

At branch baseline `5d0a58b00b2b270cee7d33d5312666b4eafae0dd`, `_candidate -> has_observed_variation` examined predictor rows with nonmissing target labels. The text branch masked blank/whitespace-only strings but still used `nunique(dropna=True) > 1` to compare untrimmed nonblank values. Consequently a single categorical state alternating `"Gold"` with `"Gold "` produced a raw distinct count of two and supported an otherwise unwarranted reviewable target hypothesis.

This is distinct from already-closed P4-30 blank-predictor and P4-36 padded-target guards. Reproduced by source examination and synthetic fixtures, not by touching owner data or making a claim about any real business predictor.

## Exact implementation

- [Implementation commit `8028e7dbf5ea435134ffc43bd134c7cd019e0df3`](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/8028e7dbf5ea435134ffc43bd134c7cd019e0df3), parent `5d0a58b00b2b270cee7d33d5312666b4eafae0dd`.
- Only `backend/target_opportunities.py` and `tests/test_p4_target_opportunities.py` modified. In the existing bounded labelled-row predictor screening, create a temporary masked text view for empty and nonempty leading/trailing-whitespace-padded strings; require two remaining distinct valid observed predictor values. Never trim the input frame or assign altered values to Quality snapshots.
- Added four parametrized negative fixture cases: `Gold/Gold `, `Gold/ Gold`, `Gold/\tGold`, and two differently padded variants. Each asserts rank-queue abstention, a blocked manual target inspection, no automatic training permission and unchanged original DataFrame.
- Added a positive control retaining `High risk` and `Low risk` as distinct despite additional padded records. Reviewable means structural signal only, not clearance for feature cleaning, leakage, business utility or model training.

## Observed test evidence at exact source

| Verification | Actual result | Boundaries |
| --- | --- | --- |
| [GitHub Actions P4 #43087164123](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/43087164123), source `8028e7db`, attempt 1 | **COMPLETED SUCCESS, 3/3 jobs** | Code/synthetic runner evidence only |
| Focused P4 backend source suite | **136 pytest passed in 3.36s** | Disposable synthetic fixtures, no owner projects |
| Existing P4 Node contracts + A3 Prepare regression | **40 passed / 0 failed** | Source-level contracts, no physical installed desktop |
| TypeScript / Vite | **Build PASS**, Vite 2.08s build step | Compiled frontend source, not Tauri packaging |
| P4 disposable real HTTP Chromium | **9 passed** | GitHub hosted browser and disposable local backend |
| Windows 2022 synthetic integrity/WebView checks | **PASS**, PowerShell 7 and Windows PowerShell 5.1 | Fake paths only; no owner's actual app-data tree |
| Owner latest-source Windows UI | **NOT RETESTED** | Explicit freeze on all intermediate installers |
| Gate C real business decision and physical offline 8 GB | **UNVERIFIED / NOT TESTED** | No simulated evidence can close these |

No installer-build workflow was run, no NSIS artifact was produced, and no owner-installed executable or original dataset was accessed. Some historical Windows QA artefacts exist but do not certify this source SHA. A later documentation-only commit has no separate application CI.

## Current governance and next task

No changes to acceptance criteria. Previous original EXE and independent backup matched baseline, while original project's critical `data/` directory had zero detected differences. Strict **entire original app-data tree preservation FAIL** persists: baseline 320 files vs observed 346; 74 WebView/cache *candidates*, historic writer UNKNOWN. Do not remove files, re-baseline, infer safe attribution or waive the gate.

P4-R01–R06, actual owner offline/8 GB, latest native UI parity, and independently evidenced label provenance, outcome timing, repeated-entity validation, non-model benefit and fair/lawful business purpose (Gate C) are still open. The owner declined a residual-risk closure deferral and froze P4–P7 installer production and downloads; only explicitly reauthorised P8 packaging may eventually occur.

**Disposition:** P4-38 SOURCE FIXED, EXACT-SOURCE CI PASS, OWNER-NATIVE NOT RETESTED. **P4 ACTIVE; P5 NOT AUTHORISED; P8 NOT CERTIFIED.** Next, assess concrete remaining P4 negatives and source-to-native evidence gaps, and route owner-dependent gates to an explicit decision without starting unauthorised work.
