# PilotODIN 1.0 | P4-15 Consolidated Technical Acceptance and Phase-Exit Gap Ledger

**Evidence date:** 9 November 2026  
**Development branch:** `feature/live-dev-workspace-20261023`  
**Exact tested source:** [`0770bfdc3dc96b48b862df432b6fecd39959c920`](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/0770bfdc3dc96b48b862df432b6fecd39959c920)  
**Phase authority:** P4 Target Intelligence **ACTIVE**. P1/P2/P3 development-CLOSED; P5–P8 NOT AUTHORISED. No owner P4 closure, native Windows acceptance or release certification.

## Purpose, changes and scope

P4-01–14 implemented named target discovery, classification/regression structure checks, unverified decision/label/timing review, deterministic manual review ranking, explicit owner choice/defer/decline/abstain, project and Quality-version isolation, selected-target blocker warnings, on-demand selected-column inspection, and read-only row/column/candidate resource bounds. Each increment received focused synthetic CI acceptance. P4-15 consolidates these into a **cross-feature regression gate** and records outstanding evidence. It introduces **no production functionality, training, automatic target selection, native EXE or installer**.

Changes at this source SHA are restricted to:
- `tests/test_p4_consolidated_acceptance.py`: 9 Python test cases (six parametrized scenarios plus three integration/negative cases).
- `frontend/e2e/p4-real-http-review-queue.spec.ts`: one additional real-HTTP browser scenario across wide and regular disposable projects.
- `frontend/tests/p4-review-queue-contracts.test.cjs`: one P4-15 test/evidence source contract.
- `.github/workflows/p4-target-ranking.yml`: runs and watches the consolidated Python test file.

No original owner data or saved project/experiment/model/report was accessed or changed.

## Actual exact-source CI outcomes

| Gate | Exact result | Assessment |
| --- | --- | --- |
| [P4 Actions #42610573693](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/42610573693): Python | **75/75 PASS**, including 9 new integrated cases | Scoped synthetic source acceptance |
| Same P4 run: Node contracts | **27/27 PASS** | Frontend/backend integration source contracts |
| Same P4 run: frontend TypeScript and Vite build | **PASS** | Compiled production frontend bundle |
| Same P4 run: real-HTTP Chromium/Uvicorn/disposable SQLite | **8/8 PASS**, including P4-15 project-switch scenario | Isolated browser + real HTTP, not Windows native |
| [P1 frontend #42610573689](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/42610573689) at same source SHA | **160/160 Node**, build PASS, **5/5** isolated browser PASS | Adjacent P1 regression coverage, not P1 re-opening |
| P2/P3 workflows | **Not rerun for this test-only P4-15 commit** | Do not invent P2/P3 acceptance |
| Source-matched installed Windows Tauri/WebView2 | **NOT TESTED** | Owner native milestone required |
| Real operational label, group/time, benefit, legal and fairness claims | **NOT VERIFIED** | Owner data/process evidence required |

The 6 parametrized synthetic cases verify normal classification, numeric regression, rare class (4/80), insufficient labelled rows (24/80), no named outcome and wide/predictor-over-cap abstention. Three more cases cover queue-versus-manual-scan fail-closed behaviour, derived-score and duplicate-header rejection, and real TestClient API project/context/version/origin boundaries across three disposable SQLite projects. No ML fit, predicted scores or original owner data.

The eighth real-HTTP P4 browser case imports two disposable projects: A is wide with intentionally incomplete queue evidence; B is a normal numeric regression case. It confirms no recommended A target, a blocked manually selected A outcome, B's independently reviewable `future_cost`, user-initiated choice and abstention, state clearing when switching back to A, version-stale **409** and foreign-Origin **403** API rejection, no unsolicited browser writes and zero saved experiments. Prior seven browser scenarios rerun and passed together.

## Consolidated P4 phase-exit evidence matrix

| Acceptance area | Status | What has and has not been demonstrated |
| --- | --- | --- |
| P4-01 to P4-04 discovery, named outcomes, aggregate technical support | **SCOPED PASS** | Synthetic classification/regression; without arbitrary numeric auto-target or validation claims |
| P4-05/06 review ordering and accessible alternatives | **SCOPED PASS** | Deterministic owner-described-first human review, top 3 + up to 12 alternatives; not business-value ranking |
| P4-07 repeated IDs, timing/label provenance, decision usefulness | **SCOPED PASS, BUSINESS UNVERIFIED** | Bounded aggregate/lexical warnings; not actual entity identity, as-of values, independent label origin or benefit |
| P4-08 choice/defer/decline/abstain and state reset | **SCOPED PASS** | Explicit temporary controls; no automatic selection, saved experiment or training |
| P4-09 negative cases and project/version security | **SCOPED PASS** | Rare/insufficient/no target, duplicate/derived, project-scoped context, stale version 409, foreign Origin 403 |
| P4-10 optional native acceptance kit | **KIT VERIFIED ONLY; NATIVE NOT TESTED** | Synthetic materials prepared and self-checked; they do not demonstrate physical Windows operation |
| P4-11/12 blocker explanation and manual out-of-list inspection | **SCOPED PASS** | Exact selected structural reason, read-only project/version-bound single-column response; no independent approval |
| P4-13 single-column resource limits | **SCOPED PASS** | At most 5,000 rows × target plus 32 predictors for value checks; partial results blocked |
| P4-14 whole queue resource limits | **SCOPED PASS** | At most 5,000 rows, 100 headers, 64 predictors, 64 named outcomes; incomplete queue abstains |
| P4-15 consolidated regression | **SCOPED PASS** | 75 Python, 27 Node, 8 real-HTTP Chromium, frontend build and P1 adjacent regressions at exact source SHA |
| Measured native app memory, elapsed time, offline/8 GB Windows | **NOT TESTED** | Source bounds do not cap full DataFrame load, machine RAM or native WebView2 process |
| Owner independent label provenance, definition and as-of prediction timestamp | **OPEN / UNVERIFIED** | User-description text and column headers are not independent truth |
| True group/time split, leakage controls and operational validation | **OPEN / UNVERIFIED** | Observed repeated IDs are prompts, not group keys or safe split evidence |
| Decision owner, non-model baseline, measured benefit/cost and lawful/fair purpose | **OPEN / UNVERIFIED** | No demonstrated real business suitability or measured intervention value |
| Source-matched Windows/Tauri/WebView2 Prepare + P4 native journey | **NOT TESTED** | Must record exact installed executable version/source and observed results |
| P4-specific QA triage and historical product-wide risks | **PARTIAL / OPEN** | Master [QA Issue #2](https://github.com/Sonkhe-Shongwe/PilotODIN/issues/2) stays OPEN; previous BE-024 Prepare native and expert-control issue not independently closed; unrelated historical Critical/High, including BE-020/021/027, remain registered |
| Explicit owner's scoped P4 phase closure | **PENDING** | Generic `next`, source commits and green GitHub Actions are not owner signoff |
| Product-wide release / P8 certification | **NOT AUTHORISED / NOT CERTIFIED** | Unresolved critical/high and broader phase requirements remain outside P4 |

## Evidence limits, open work and next milestone

P4-15 has **no newly observed failing automated checks at the tested source commit**. This does not prove the absence of defects or that P4 is done. Some source paths remain intentionally conservative: the main queue offers no shortlist beyond its scan budgets, and the separate manual detail screen also blocks an incomplete view. The app still loads the approved DataFrame before performing these bounded P4 screens. Full Windows native 8 GB / offline memory behavior was neither benchmarked nor observed.

The next milestone (proposed **P4-16**) is not an invitation to keep adding speculative product features. Gather the minimum required *real* information: a demonstrably source-matched installed Windows executable (or mark native acceptance **BLOCKED/NOT TESTED**), one controlled disposable native P4 classification/regression/abstention and switching walkthrough with observed PASS/FAIL records, and enough grounded real-business context to judge intended target, true label source, decision-time predictors, grouping/time validation, benefit over a non-model baseline and permitted/fair use. Avoid another download bundle if the already available P4-10 synthetic kit and existing source-matched app suffice. **Do not rebuild or install the desktop application without separate scope authorisation.**

After evidence is recorded and P4-specific defect/risk triage is complete, ask for a **separate explicit P4-17 scoped phase-close decision**. Do not infer closure; do not begin P5 without new authority. No P8 release certification.

**P4-15 DISPOSITION:** **CONSOLIDATED SOURCE/CI/SYNTHETIC BROWSER TECHNICAL ACCEPTANCE PASSED.** Overall **P4 ACTIVE**, P4 physical native/real-business phase-exit evidence OPEN, P5 NOT AUTHORISED, P8 NOT CERTIFIED.
