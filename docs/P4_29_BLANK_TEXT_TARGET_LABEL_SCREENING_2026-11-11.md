# PilotODIN 1.0 | P4-29 Blank-text outcome label screening safety

**Date:** 11 November 2026. **Scope:** P4 Target Intelligence safety and deterministic aggregate review only. No installer, user-data modification, model training or new development phase.

## Actual source issue

In the prior `backend/target_opportunities.py::_candidate` implementation, `series.notna()`, `series.nunique()`, task inference and class counts treated empty strings and whitespace-only text values as labelled outcomes. On an isolated 80-row synthetic frame with 40 `"Y"` labels, 40 `" "` entries, and one varying feature, the source would count 80 non-missing labels and two apparent classes of 40, so could return **structurally reviewable** despite half the apparent labels being blank. This is a **source-confirmed correctness defect**, not a failure observed on owner datasets or an accepted real-business target.

## Minimal implementation

[Source commit `52ff6cbf62ad48c7def5c84e11eff32f4a6a8aef`](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/52ff6cbf62ad48c7def5c84e11eff32f4a6a8aef) modifies only `backend/target_opportunities.py` and `tests/test_p4_target_opportunities.py`.

- Detect empty/whitespace-only **string** target values in the existing bounded candidate review, and mask them in a **temporary Series**, leaving the approved project DataFrame unchanged.
- Use the temporary view consistently when reporting labelled/missing/distinct counts, evaluating numeric finiteness, inferring task type, computing smallest-class support and selecting predictor rows for structural screening.
- Add a specific blocker for **any** blank-text target label: the owner must address the data quality issue through a separately controlled Quality workflow before this supervised objective may be considered reviewable. Do not silently modify training inputs or treat screening-only masking as model preprocessing.
- Apply the same `_candidate` protection through both the normal queue and explicit manual single-column inspection, preserving the existing no-auto-train and business-unverified policy.
- Retain existing behaviour for nonblank labels. No production training endpoint, Tauri runtime, model weights, historical datasets or owner projects changed.

## Verification ledger

| Evidence | Observed result | Boundary |
| --- | --- | --- |
| [P4 workflow #43061451092](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/43061451092), exact source `52ff6cb` | **COMPLETED SUCCESS**, all 3 jobs | Tested source SHA, not later docs commit |
| P4 synthetic Python suite, including four parametrized blanks and one single-blank case | **PASS** | Synthetic pandas frames only |
| Existing P4 Node contracts and TypeScript/Vite build | **PASS** | Source/frontend; no physical desktop |
| P4 disposable real-HTTP Chromium suite | **PASS** | CI-only isolated service/browser |
| Windows-2022 P4 synthetic data preservation and WebView process checks, including Windows PowerShell 5.1 | **PASS** | Fake files and fake process metadata |
| Owner native Windows P4-29 label-screening UI | **NOT RETESTED** | Earlier native UI testing used prior installed binary |
| Real operational outcome truth, target usefulness, offline 8 GB and release suitability | **UNVERIFIED** | No authority gained through this fix |

The change does **not** modify the separately governed training API or approve predictions. If a blank-string target reaches a different training workflow, that workflow's independent safeguards still apply; this P4 review gate alone is not an end-to-end training ban.

## Preservation and phase boundaries

P4-28 owner-native WebView2 observer completed successfully: 26 current profile-flagged processes, six QA-profile flags, zero original-profile flags, 20 other-profile flags and zero unresolved. This does **not** assign historical writes.

The original EXE and independently preserved pre-QA backup matched baseline; owner-native read-only comparison found zero changes in the source-defined original critical `data/` store. Nonetheless the **strict entire original data-directory fingerprint remains FAIL** (320 baseline files, 346 current files, 74 browser/cache *candidates*, historic writer UNKNOWN). This new P4-29 fix does not change that acceptance result, the frozen criteria or prior declined risk deferral.

Physical source-fixed docking UI parity, true offline Qwen/8 GB operation and independent business Gate C are not verified. **P4 ACTIVE; P4-R01–R06 OPEN; P5 NOT AUTHORISED; P8 NOT CERTIFIED.** No need to repeat WebView profile snapshots or old file-count inventories without specific new evidence or explicit owner acceptance work. Next step is evidence-based P4 acceptance, not scope expansion.
