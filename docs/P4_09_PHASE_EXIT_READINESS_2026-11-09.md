# PilotODIN 1.0 | P4-09 Phase-Exit Readiness and Negative-Case Evidence

**Prepared 9 November 2026**  
**Branch:** `feature/live-dev-workspace-20261023`  
**Verified application SHA:** [`e855d945139267e9a16104fb43cb24b9150fb3dc`](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/e855d945139267e9a16104fb43cb24b9150fb3dc)  
**Phase authority:** P4 ACTIVE only. P1/P2/P3 CLOSED for bounded development. P5–P8 not authorised.

## Purpose and decision

P4-01–08 are accepted for their **bounded developer scope**. P4-09 adds phase-exit *negative testing and an evidence matrix*, not new functionality. A complete P4 phase may **not** be declared closed just because synthetic tests pass. The missing real-business and native desktop evidence cannot be invented. **Current overall P4 closure disposition: BLOCKED / PENDING owner evidence and explicit phase-close decision.** This is NOT a new release or installer.

## Exact source and testing changes

- `tests/test_p4_phase_exit_matrix.py` (seven synthetic Python tests): parameterized classification, numeric regression, rare classification minority support, fewer than 30 labels, no named target, repeated identifiers with privacy-preserving counts, stale GET/POST Quality version boundaries, project-scoped saved owner descriptions, foreign Origin rejection, duplicate header rejection and derived probability abstention. No model fitting. No original datasets accessed.
- `frontend/e2e/p4-real-http-review-queue.spec.ts` adds a third **real-HTTP, disposable Uvicorn/SQLite and Chromium** scenario. It creates three synthetic projects, exercises an actual guarded project chooser switch from classification to regression to no-named-target and back, checks that temporary defer/abstain state and selected targets do not leak, stale Quality-version requests return HTTP 409, and no experiments were created. The request allowlist authorizes GETs for only those three disposable project IDs; writes are blocked in the browser scenario.
- `frontend/tests/p4-review-queue-contracts.test.cjs` registers the P4-09 suite's negative-case and browser-source contracts.
- `.github/workflows/p4-target-ranking.yml` includes the P4-09 Python test file in path triggers and the existing focused pytest step. No dependencies, original project revisions or model weights changed.

**Actual CI source evidence:**
- [P4 #42593540857](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/42593540857): **COMPLETED SUCCESS at exact source SHA**: **49/49 Python**, **21/21 Node**, frontend TypeScript/Vite **PASS**, **3/3** disposable real-HTTP Chromium browser tests **PASS**. The new P4-09 browser scenario passed in the same run.
- [P1 #42593540593](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/42593540593): **COMPLETED SUCCESS at same source SHA**: **160/160** source contracts, TypeScript/Vite production build **PASS**, **5/5** isolated browser tests **PASS**.
- **Evidence limitation:** Linux GitHub Actions and synthetic browser/API tests are compiled-source and hosted-browser evidence, not a Windows-installed Tauri/WebView2 observation, real data model validation or owner phase acceptance.

## P4 bounded phase-exit matrix

| Acceptance gate | Status | Evidence / missing proof |
| --- | --- | --- |
| Named classification target, technical label support, no auto-selection | SCOPED PASS | P4-09 synthetic fixture plus prior P4-01–08; no business truth claim |
| Numeric regression target reviewed without performance or value score | SCOPED PASS | P4-09 80-row synthetic regression |
| Rare labels and insufficient labelled rows are not recommended as reviewable | SCOPED PASS | Minority 4/80 and 24/80 labelled; structural abstention tested; manual Prepare chooser remains separately controlled |
| No named outcome means abstention, not arbitrary numeric target | SCOPED PASS | Python and real-HTTP browser no-target fixture |
| Repeated identifier names/values prompt dependency questions | SCOPED PASS | Synthetic 80 values / 40 distinct; not independently verified true entities or leakage |
| Version and project isolation, stale requests rejected | SCOPED PASS | Disposable TestClient GET/POST 409, separate projects/context, browser project switch |
| User can explicitly select, defer, decline, abstain; no unexpected experiments | SCOPED PASS | Previously accepted P4-08 + P4-09 cross-project real-HTTP scenario |
| Label provenance, as-of decision moment and true entity/group split | OPEN / UNVERIFIED | Requires grounded source evidence, entity definition, available-at-time fields and a justified validation method |
| Measurable decision utility, non-model baseline, operational owner & fairness/lawful use | OPEN / UNVERIFIED | User descriptions and aggregate labels do not independently verify business value or authority |
| Physical Windows Tauri/WebView2 P4 workflow with disposable source | NOT TESTED | Owner must run the current installed/source-matched native desktop build and record exact observed results |
| P4-specific confirmed critical/high risk screen and exit judgement | PARTIAL | This increment introduced no new confirmed P4 critical/high; historical QA items and native untested risks remain. Owner must review and decide closure |
| Owner's explicit P4 scoped closure approval | PENDING | No owner approval provided; do not move to P5 |
| P8 full release qualification and offline 8 GB Qwen | NOT IN P4 ACCEPTANCE | Separate future gate; historical Critical/High release risks remain open |

## Owner native test checklist (not performed by this session)

Use only a disposable synthetic dataset and a Windows native build **whose source commit is explicitly identified**. Do not overwrite an original project, model, font or saved report; do not build an installer or trigger model training for this P4-only check.

1. Record Windows version, native app/Tauri/WebView2 build identity and exact Git commit/version. If installed app does not contain P4-09 source, mark the current-native-evidence gate **NOT TESTED**, not PASS.
2. Import a synthetic classification CSV with 80 rows, two classes with adequate support, repeating harmless `account_id`, and at least one varying predictor. Open Prepare; check structural evidence and repeated-header aggregate without raw identifier disclosure.
3. Verify explicit **Review**, **Defer**, **Decline** and **No prediction objective right now** clear or retain only the documented session state. Confirm no training starts and no experiment is generated.
4. In a second disposable project, use 80 finite distinct numeric `future_cost` outcomes and a predictor; check regression hypothesis and manual choice. Changing project must not import the first project's temporary review status or selected target.
5. Try a rare-class (`4/80`) or insufficient-label (`24/80`) synthetic dataset and an unrelated numeric dataset. Observe blockers/abstention; do not treat a manual alternative choice as approved prediction suitability.
6. For version boundaries, use only an approved synthetic Quality working-version change if the native test harness already supports it. Verify prior descriptions are not silently adopted on the new version and stale requests do not produce phantom success. If safe native steps are unavailable, explicitly mark this subcase **UNTESTED**; do not mutate owner data.
7. Record actual outcome per case (PASS / FAIL / UNTESTED), screenshot or log only with consent, exact app and data versions, and attach a small diagnostic if any problem occurs. A green CI log is not native acceptance.

**Required owner decision after evidence:** Approve or reject **bounded P4 development closure**, explicitly listing any residual native or real-decision risks accepted for later phases. Closure must not be inferred from `next`, this report or a branch commit. P8 release remains uncertified.

## Issue #2 triage and next dependency

Reviewed master QA Issue #2. Historical **BE-024 Medium / Prepare** lists configurable preprocessing and earlier high-risk suggestion behaviour. Source has subsequently changed to an additive exclusion implementation, but the old installed defect observation has not been independently reproduced or accepted as fixed in physical Windows. Preserve the issue and do not retroactively close it.

Separate **Critical/High** findings for AI (including BE-020/021), Predict (BE-027) and other workspaces remain in the master register for their authorised phases and consolidated release; their existence prevents product-wide certification but does not authorise unrelated P4 development. This P4-only suite does not imply the product is defect free.

**Next single action:** obtain owner native P4-only acceptance evidence using the above safe checklist (if a source-matched desktop build is available), then perform a documented scoped P4 exit decision. No P5 work without explicit separate authorisation.
