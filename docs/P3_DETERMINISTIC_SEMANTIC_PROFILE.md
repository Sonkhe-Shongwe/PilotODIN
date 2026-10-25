# P3 — Shared deterministic semantic hypothesis profile (first increment)

**25 October 2026 — source implemented, focused owner Windows verification PENDING.**

## Why P3 follows the accepted P5 minimum

The owner's published complexity-last roadmap places deterministic P3 semantic understanding and P4 target opportunity ranking ahead of large P5/P7 orchestration. The P5 foundation now has owner-inspected 25/3 (single Low-memory slot), 18/7 + Vite (durable training progress), and **45/12 + Vite (cooperative cancellation/soft timeout)** green focused Windows suites. Full durable scheduling and hard preemptive job kill remain later architecture problems. Do not lose time repeatedly testing earlier accepted P5 work.

**Source grounding for P5 last gate:** Uploaded `pilotodin-p5-cancel-ayag0sci.zip`, with extracted `result.json` at **2026-10-25T18:38:46.030809Z** shows three PASS phases exit code zero; `p5-training-cancellation-backend.log` **45 passed in 5.05s**; `p5-training-cancellation-node.log` **12 pass/0 fail**; Vite `tsc --noEmit && vite build` **PASS** with 1,618 modules, build **3.47s** and a **non-blocking bundle chunk warning**. Synthetic-only; no owner dataset changes. The inherited runner metadata combining `durable_general_scheduler_or_safe_cancellation` under `NOT_IMPLEMENTED` is imprecise: **cooperative ML cancellation is implemented/tested; the general scheduler is NOT**.

## P3 first feature and its limitations

The goal is to provide **read-only, evidence-bounded business context** as an enhancement to the existing Your Data → Data Dictionary and Column Investigation feature.

- **Backend `backend/semantic_profile.py`** reuses `column_intelligence.overview` over the current approved version. Uses header patterns, stored dtypes and observed cardinality plus the existing bounded shape/type hints. Returns **NO raw sample values**, no guessed source business facts, no trained model scores, no auto-target selection and no changes to stored data.
- **Domain** is `hypothesis` ONLY when at least two distinct vocabulary concepts match a recognisable category (insurance, retail, education, banking, manufacturing). Equal-high competing domains produce `unknown`; no match produces `unknown`. Labels are **tentative guesses from field names**, never truth or certainty scores; actual business context must be confirmed.
- **Record grain** is `hypothesis` ONLY if a single complete row-unique identifier-like column exists. It states only a **possible unique row key**; it does not claim that a row equals a specific customer/order/claim/visit. Multiple unique IDs, missing IDs, zero rows and nonunique ID columns return `unknown` as appropriate.
- **Field hypotheses** are possible identifier, time, monetary and outcome roles with explicit evidence basis such as `name_only`, `stored_dtype`, `name_and_cardinality`. Units, label timing and whether a column is a valid prediction target are always unknown without context. Output is bounded to **80 columns** inspected for individual hints, and client UI shows at most the first 20 hinted fields. All outputs mark inferred concepts `hypothesis`; measurements remain `observed`.
- **Endpoint** `GET /api/projects/{project_id}/semantics?expected_version=N` rejects missing project (404), missing/invalid version (422) or stale approved working version (409). Reuses existing local backend/project/session security. No broad cross-project semantic cache.
- **Frontend** `frontend/src/SemanticOverview.tsx` embeds in the existing `ColumnInvestigation` dictionary after its measured row/field counts; displays Domain/possible key, evidence/reason and optional details. It reloads on project/version changes and says explicitly `UNVERIFIED`, `Unknown` when appropriate, and **does not select a target**. No new navigation tab, LLM request, data transformation or model training.

## Focused tests and owner acceptance

- `tests/test_p3_semantic_profile.py`: eight synthetic tests for insurance fraud-labelled columns, retail repeat-order rows, no clues/abstention, conflicting domains, completely missing/empty rows, bounded response/no raw values, duplicate columns, versioned project-scoped API and local-origin guard.
- `frontend/tests/p3-semantic-profile-contracts.test.cjs`: four source contracts for read-only semantics and abstention, exact version API, dictionary UI status, and synthetic test coverage.
- Future unified backend suite `tools/Verify_P0_A4_Readiness.py` includes the P3 Python test once.
- **Exactly one Windows check:** `Run_PilotODIN_P3_Semantic_Profile.bat` calls `tools/Verify_P3_Semantic_Profile_Local.py`, running only new P3 + existing column-intelligence Pytests, four P3 Node source contracts, and TypeScript/Vite build because the new screen was integrated. Synthetic isolated PILOTODIN_HOME. Output one `pilotodin-p3-semantics-*.zip` with JSON and phase logs; upload only if failed. No real insurance dataset import, long-running ML, native Save As, old P5 tests, Qwen downloads or E2 RAM scans.

**Truth:** This new P3 batch's source has been committed and reviewed, but **NO P3 owner Windows tests have yet been executed**. Do not mark P3 accepted merely because older P5 is green.

## Next after one green P3 gate

Continue P3 narrowly (optional user-confirmed business glossary/context) and then **P4 explicit user-controlled target opportunity recommendations**, with conservative eligibility gates, separate business-value/readiness rationale, group/time/leakage caution, and full abstention for datasets lacking defensible targets. Do not auto-train or silently choose a target. Larger P5 multi-operation durable queue, P6 Master modes, P7 orchestration and P8 installer remain later. **Actual offline licensed Qwen inference with measured concurrent 8GB peak RAM is E2 UNDETERMINED.**
