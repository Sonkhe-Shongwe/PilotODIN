# P3 — Shared deterministic semantic hypothesis profile (first increment)

**25 October 2026 — P3 first deterministic semantic-profile increment FOCUSED WINDOWS ACCEPTANCE PASS (initial failure corrected by owner-tested targeted rerun).**

> **6 November 2026 P3 phase activation:** The owner approved starting P3 after reviewing its plan; P3-02 user-described dataset business context has source/CI acceptance evidence and an outstanding real browser/native interaction gate. See [P3 current acceptance register](./P3_SEMANTIC_CONTEXT_ACCEPTANCE_2026-11-06.md). All earlier P3-01 failure/repair notes below remain historically accurate.

## Why P3 follows the accepted P5 minimum

The owner's published complexity-last roadmap places deterministic P3 semantic understanding and P4 target opportunity ranking ahead of large P5/P7 orchestration. The P5 foundation now has owner-inspected 25/3 (single Low-memory slot), 18/7 + Vite (durable training progress), and **45/12 + Vite (cooperative cancellation/soft timeout)** green focused Windows suites. Full durable scheduling and hard preemptive job kill remain later architecture problems. Do not lose time repeatedly testing earlier accepted P5 work.

**Source grounding for P5 last gate:** Uploaded `pilotodin-p5-cancel-ayag0sci.zip`, with extracted `result.json` at **2026-10-25T18:38:46.030809Z** shows three PASS phases exit code zero; `p5-training-cancellation-backend.log` **45 passed in 5.05s**; `p5-training-cancellation-node.log` **12 pass/0 fail**; Vite `tsc --noEmit && vite build` **PASS** with 1,618 modules, build **3.47s** and a **non-blocking bundle chunk warning**. Synthetic-only; no owner dataset changes. The inherited runner metadata combining `durable_general_scheduler_or_safe_cancellation` under `NOT_IMPLEMENTED` is imprecise: **cooperative ML cancellation is implemented/tested; the general scheduler is NOT**.

## P3 first feature and its limitations

The goal is to provide **read-only, evidence-bounded business context** as an enhancement to the existing Your Data → Data Dictionary and Column Investigation feature.

- **Backend `backend/semantic_profile.py`** reuses `column_intelligence.overview` over the current approved version. Uses header patterns, stored dtypes and observed cardinality plus the existing bounded shape/type hints. Returns **NO raw sample values**, no guessed source business facts, no trained model scores, no auto-target selection and no changes to stored data.
- **Domain** is `hypothesis` ONLY when at least two distinct vocabulary concepts from at least two independent columns match a recognisable category (insurance, retail, education, banking, manufacturing). Equal-high competing domains produce `unknown`; no match produces `unknown`. Labels are **tentative guesses from field names**, never truth or certainty scores; actual business context must be confirmed.
- **Record grain** is `hypothesis` ONLY if a single complete row-unique identifier-like column exists. It states only a **possible unique row key**; it does not claim that a row equals a specific customer/order/claim/visit. Multiple unique IDs, missing IDs, zero rows and nonunique ID columns return `unknown` as appropriate.
- **Field hypotheses** are possible identifier, time, monetary and outcome roles with explicit evidence basis such as `name_only`, `stored_dtype`, `name_and_cardinality`. Units, label timing and whether a column is a valid prediction target are always unknown without context. Output is bounded to **80 columns** inspected for individual hints, and client UI shows at most the first 20 hinted fields. All outputs mark inferred concepts `hypothesis`; measurements remain `observed`.
- **Endpoint** `GET /api/projects/{project_id}/semantics?expected_version=N` rejects missing project (404), missing/invalid version (422) or stale approved working version (409). Reuses existing local backend/project/session security. No broad cross-project semantic cache.
- **Frontend** `frontend/src/SemanticOverview.tsx` embeds in the existing `ColumnInvestigation` dictionary after its measured row/field counts; displays Domain/possible key, evidence/reason and optional details. It reloads on project/version changes and says explicitly `UNVERIFIED`, `Unknown` when appropriate, and **does not select a target**. No new navigation tab, LLM request, data transformation or model training.

## Focused tests and owner acceptance

- `tests/test_p3_semantic_profile.py`: nine synthetic tests for insurance fraud-labelled columns, retail repeat-order rows, no clues/abstention, conflicting domains, completely missing/empty rows, bounded response/no raw values, duplicate columns, versioned project-scoped API and local-origin guard.
- `frontend/tests/p3-semantic-profile-contracts.test.cjs`: four source contracts for read-only semantics and abstention, exact version API, dictionary UI status, and synthetic test coverage.
- Future unified backend suite `tools/Verify_P0_A4_Readiness.py` includes the P3 Python test once.
- **Exactly one Windows check:** `Run_PilotODIN_P3_Semantic_Profile.bat` calls `tools/Verify_P3_Semantic_Profile_Local.py`, running only new P3 + existing column-intelligence Pytests, four P3 Node source contracts, and TypeScript/Vite build because the new screen was integrated. Synthetic isolated PILOTODIN_HOME. Output one `pilotodin-p3-semantics-*.zip` with JSON and phase logs; upload only if failed. No real insurance dataset import, long-running ML, native Save As, old P5 tests, Qwen downloads or E2 RAM scans.

**Truth:** This new P3 batch's source has been committed and reviewed, but **NO P3 owner Windows tests have yet been executed**. Do not mark P3 accepted merely because older P5 is green.

## Owner failure evidence and targeted source repair — 25 October 2026

The owner ran the original `Run_PilotODIN_P3_Semantic_Profile.bat` and uploaded `pilotodin-p3-semantics-ocmar9cg.zip`. We **directly inspected all four files** (`result.json`, `p3-semantics-and-column-backend.log`, `p3-semantic-ui-contracts.log`, `frontend-typescript-vite.log`).

- `result.json` UTC **2026-10-25T19:01:09.511586Z**: overall **FAIL** because of the backend phase; isolated data only; no user projects modified.
- Backend **13 passed / 2 failed in 3.67s**, failures in `test_retail_is_tentative_and_does_not_claim_order_grain` and `test_semantic_api_is_project_scoped_and_version_pinned`.
- Node frontend source-contracts **4/4 PASS**, 0 failed. TypeScript/Vite **PASS**, 1,619 modules transformed, 3.65s build; non-blocking bundle-size warning.
- **Failure 1 was a brittle assertion**, not a modelling issue: test expected exact substring "record grain", while truthful runtime explanation says "row grain". The regression now tests the substantive meaning: the word "grain" and need for "business" confirmation must both appear, while state/identifier remain unknown.
- **Failure 2 was a real endpoint hardening gap**: cross-origin `Origin: https://external.example` was returned 200 by the GET endpoint in dev mode. CORS alone does not reject the HTTP request. The route now calls existing `_local_request(request)` **before** project/data access; existing local development origin remains accepted in an additional test, external origin must produce 403. This intentionally tightens only the new semantic GET endpoint, not the unrelated existing GET routes.
- Existing P3 Node source contract was tightened to require a `Request` and server-side local guard in the new route. Old P3 BAT failure-message typo "P5 check did not pass" corrected.

**Minimal rerun:** `Run_PilotODIN_P3_Semantic_Repair.bat` (new), invoking `tools/Verify_P3_Semantic_Repair_Local.py`. Runs ONLY the new P3 Python tests and updated four Node contracts, in isolated synthetic test environment. **Does not repeat TypeScript/Vite**, which already passed and no frontend application component changed in the fixes; does not re-run the unchanged column-intelligence tests, old P5/P1/P0/A4 or native installer. Reports one fresh `pilotodin-p3-repair-*.zip` with both phase logs and JSON. **Historical pre-rerun status only:** This sentence originally recorded the pending repaired owner test; it is superseded by the independently inspected green ZIP described in the Verified P3 repair acceptance section.

## Verified P3 repair acceptance — 25 October 2026

The owner completed `Run_PilotODIN_P3_Semantic_Repair.bat` and uploaded **`pilotodin-p3-repair-x8uxs9kq.zip`**. We directly opened the ZIP and read `result.json`, `p3-semantics-and-column-backend.log`, and `p3-semantic-ui-contracts.log`, rather than relying only on the screenshot.

- **Runner UTC:** `2026-10-25T19:12:02.212135+00:00`, **overall PASS**; both phases returned **exit code 0**.
- **Backend:** `tests/test_p3_semantic_profile.py` **9/9 PASS in 6.16s**, including the formerly brittle grain assertion and the HTTP local-vs-foreign `Origin` security regression.
- **Node source contracts:** **4/4 PASS**, 0 failed/skipped/cancelled; approximately 144 ms.
- The original three-phase P3 run had already produced **TypeScript/Vite PASS** and passed all unchanged column-intelligence tests (original total 13 pass, 2 fail; the two new semantic failures are now fixed). No frontend application file changed during the targeted repairs, so neither build nor the adjacent suite was repeated.
- Both runs were isolated, synthetic and reported no access to original datasets. **No actual business semantics have been confirmed by a user**, and the UI remains explicitly hypothesis-only.
- **Acceptance:** First P3 read-only deterministic semantic profiles, version-pinned project scope, local origin check and uncertainty/abstention contract have passed the focused Windows gates. This is not manual end-to-end native semantic UI review, a learned business ontology, or P4 target-selection capability. No additional P3 verification action is needed unless relevant source changes.

**Next engineering target:** bounded P4 prediction-target **recommendations, not autonomous selection**. Evaluate defensible label eligibility and data availability, clearly separate possible business value from ML readiness, flag identifier/time leakage and require explicit user selection. Preserve P3 abstention where evidence cannot justify a hypothesis.

## Next after one green P3 gate

Continue P3 narrowly (optional user-confirmed business glossary/context) and then **P4 explicit user-controlled target opportunity recommendations**, with conservative eligibility gates, separate business-value/readiness rationale, group/time/leakage caution, and full abstention for datasets lacking defensible targets. Do not auto-train or silently choose a target. Larger P5 multi-operation durable queue, P6 Master modes, P7 orchestration and P8 installer remain later. **Actual offline licensed Qwen inference with measured concurrent 8GB peak RAM is E2 UNDETERMINED.**
