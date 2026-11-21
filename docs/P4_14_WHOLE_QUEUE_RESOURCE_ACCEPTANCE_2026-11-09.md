# PilotODIN 1.0 | P4-14 Main Review Queue Resource Safety and Acceptance

**Date:** 9 November 2026  
**Active branch:** `feature/live-dev-workspace-20261023`  
**P4-tested source SHA:** [`42b14da966affae4d64fdc651690633e2d788d92`](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/42b14da966affae4d64fdc651690633e2d788d92)  
**Authority:** Only P4 active; P1/P2/P3 closed for bounded development; P5 not authorised; P8 not certified.

## Purpose and identified gap

P4-13 bounded a single manually requested target inspection. The separate main target recommendation queue still screened **every name-hinted outcome column** and every other potentially varying predictor using the approved *full* DataFrame. That could repeat expensive uniqueness and label-support operations across a wide and long dataset, without a clear queue-level resource budget. P4-14 bounds this read-only screening while retaining normal small-data behavior. It neither limits the full in-memory data load nor authorises training.

## Resource budget and conservative output

| Main queue constraint | P4-14 bound |
| --- | --- |
| Rows for value screening | First **5,000** |
| Headers screened for named outcomes | First **100** |
| Other predictors per candidate | At most **64** |
| Named outcome candidates for a complete scan | At most **64** |
| Partial candidate blocker details | At most **5** |

If **any** budget would truncate the screen, `recommend` does **not** return reviewable recommendations. It returns an explicit abstention reason, an accessible warning in the frontend, a `queue_resource_review` object with observed-versus-original coverage and incomplete reasons, and up to five **structurally blocked sample-only** examples if available in the bounded header window. A named target beyond the first 100 headers cannot be incorrectly presented as proven absent. User descriptions cannot override truncation. The manual column selector and separately guarded P4-12/13 on-demand evidence remain available; neither gives training permission.

The original candidate ordering (owner-described first, observed label support, deterministic name tie-break), up-to-3 suggestions and up-to-12 additional reviewable alternatives are retained **only for fully screened datasets within all limits**. Previously accepted structural outcomes and no-auto-training behavior are unchanged for these normal datasets.

The existing repeated-identifier probe stays aggregate-only and bounded, now to the queue sample if the queue is partial, and reports original row totals and truncation. A value scan missing a predictor, group repetition or a rare class does **not** prove that it is absent in the full dataset. For datasets whose **row** count exceeds 30,000, a **local ML cap caution** is retained without claiming that all rows are labelled.

## Exact automated evidence

- [P4 #42608545990](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/42608545990), **COMPLETED SUCCESS at code SHA**: **66/66 Python**, **26/26 Node**, TypeScript/Vite production build **PASS**, **7/7** disposable real-HTTP Chromium/SQLite/Uvicorn cases **PASS**.
- Six P4-14 synthetic Python tests: unchanged deterministic queue when small; 5,001-row cap with one-column evaluation; 122-column / 120-outcome cap with at most five blocked details, max 65 columns per candidate; late target beyond 100 scanned headers handled as incomplete; 65-predictor cap; and >30,000-row local ML cap caution.
- New P4-14 real-HTTP browser case: disposable 80-row/72-column project with a human-readable `churn` target and many other fields. Backend returns no recommendations; UI shows **Incomplete target screening: no recommended target** and original/observed header coverage; manual choice displays the blocker without saving experiments or making unexpected browser writes.
- [P1 isolated frontend #42608545956](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/42608545956) **COMPLETED SUCCESS at the exact same code SHA**: **160/160 Node contracts**, TypeScript/Vite build **PASS**, **5/5 isolated browser regressions PASS**. Chromium installation was still pending during the initial P4-14 handoff, but the final result was subsequently checked from the run and job logs. No unresolved pending P1 result remains for this SHA.

No real customer datasets, project Quality history, training model, experiment, original file, native EXE or installer were accessed. A failed or pending P1 browser check is not a passing test and should be retained accurately in QA history.

## Remaining product and P4 phase-exit gates

This is a **scan-size budget in the P4 review code**, not a timed service SLA or memory measurement. The approved `quality.current_data` still loads the full project. Physical Windows Tauri/WebView2 acceptance on a source-matched installed build has **not been conducted**. True label provenance, predictors known at decision time, lawful/fair operation, real grouping or time-dependence, measurable decision benefit over a non-model baseline and a separately explicit owner P4 closure decision remain OPEN.

**Disposition:** P4-14 SCOPED SOURCE/P4 CI ACCEPTED. Overall **P4 ACTIVE / NATIVE UNTESTED / P5 NOT AUTHORISED / P8 NOT CERTIFIED**. The next justified P4 step is consolidated phase-specific engineering/regression acceptance and a final gap ledger; native/owner evidence remains separately required.
