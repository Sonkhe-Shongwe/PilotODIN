# P4 second increment — version-bound user-described target business context

**25 October 2026 — source committed, owner Windows focused verification PENDING.**

## Established accepted baseline

The previous **first P4 target-opportunity screening** is owner-accepted within isolated synthetic Windows checks, from inspected `pilotodin-p4-targets-tunirk21.zip`: `result.json` timestamp **2026-10-25T19:39:55.547843+00:00**, all three phases PASS/exit 0. Backend **21/21 PASS in 5.82s** (12 P4 + nine P3); Node **8/8 PASS** (P4 + P3); TypeScript/Vite **PASS**, 1,620 modules and 3.90s build; only non-blocking >500 kB bundle warning. `original_datasets_accessed=false`; native Tauri and offline 8GB/Qwen not tested.

This *new* second increment must be verified separately, without replaying the old full P4 first-stage suite, P3, P5 or P0/A4.

## Boundaries and rationale

The original P4 screen could flag plausible target labels but **could not know** the business decision, the outcome definition, prediction point or where labels originate. This increment accepts a user's **explicitly submitted description**, preserves it **locally and version-bound**, and displays its meaning next to measured label evidence. It does **not** independently substantiate the description or make unsafe target selection decisions.

- **Additive SQLite table** `target_business_context` through `backend/storage.py::init` keyed by **project_id + quality_version + target_column**. Stores four short human-provided text fields: outcome definition, contemplated decision/action, exact prediction moment and historical label source; captures last-updated time. An explicit save updates only that exact key. Earlier working-version descriptions are not automatically treated as current. No source dataset, experiment, model or other project's metadata is changed by this save.
- **GET target-opportunities** reads descriptions strictly for the current project and approved Quality working-version, attaches `user_context` to only matching candidates, and marks `business_relevance=user_described_unverified`. Without user context, candidates remain `business_relevance=unverified`. The overall panel distinguishes whether any of the shown candidates has a user description. Context-bearing reviewable candidates sort first (then by observed label count); this is **not a quantified business value/reliability ranking**. Existing structural blockers, label support gates and abstention always override descriptive text, even for a confident user description.
- **Local-only POST** `/api/projects/{project_id}/target-business-context` requires `_local_request(request)` before any project/data read, exact existing project and approved data version, an exact current field name, and 10–600 or 10–500 nonwhitespace characters as appropriate. Returns 409 when stale version, 404 for missing project, 422 for invalid column/text, 403 for foreign Origin. Uses Pydantic field limits and SQL parameters. The submitted text is the user's statement, **not automatically validated** truth or consent to train.
- **Frontend** `TargetContextEditor.tsx` provides optional expand/collapse editor **inside** each candidate (max three) with four editable descriptions and an explicit **Save user description** button. It never automatically saves, selects targets or runs experiments. `TargetOpportunities.tsx` refreshes version-scoped recommendations after a successful save. The initial **Review this target** selection button remains separate and the existing A3 user-confirmed target, preparation, model resource/leakage and validation gates are unchanged.
- **No remote AI/cloud calls**, no LLM understanding, no modelling, and no real-time semantic verification. Descriptions are local metadata and might contain sensitive context the user chooses to type; do not automatically include them in LLM prompts or exports. In this increment no API beyond the existing local backend receives them.

## Focused automated tests and one owner gate

- New `tests/test_p4_target_business_context.py`: **five synthetic tests** for save+read and no model creation, project/version isolation and upserts, external Origin/invalid body/unknown field/unknown project blocking, cannot override rare-class structural blockers, and cannot fabricate target outcomes from arbitrary columns.
- Existing `tests/test_p4_target_opportunities.py` retained in the same focused test run because context augments its response; no unrelated P3/P5/P0/A4 suite.
- New `frontend/tests/p4-business-context-contracts.test.cjs`: **four source-contract tests** for additive version-scoped SQLite schema, guarded POST, explicit editor click/no training, and no bypass of prior P4 abstention/technical blocks.
- Existing `frontend/tests/p4-target-opportunities-contracts.test.cjs` updated to accurately reflect user-context status wording, tested alongside new Node checks. Affected front-end components are rebuilt with `tsc --noEmit && vite build`.
- Future comprehensive backend suite registers new Python module once.
- **ONE pending owner Windows check:** Pull active `feature/live-dev-workspace-20261023` and run `Run_PilotODIN_P4_Business_Context.bat` once. It invokes `tools/Verify_P4_Business_Context_Local.py`: focused new/affected P4 Python modules, four new plus four existing P4 Node source-contract tests and frontend TypeScript/Vite build. Isolated temporary `PILOTODIN_HOME`; one `pilotodin-p4-context-*.zip` diagnostics archive. On failure share that ZIP, not repeated broad old tests.

**Verification honesty:** All new source was committed and reviewed but **no owner Windows run for the second increment is yet recorded**. The earlier P4 21/8/Vite result applies ONLY to the first increment.

## Next after acceptance

Further P4 refinement may add explicit, reviewable evidence for timing/provenance, identification of repeated entities and feature availability, and only then explain **decision-value ranking** with grounded criteria (actionability, label confirmation, technical feasibility and risks). Do not infer causality, target prediction success, factual decision value or ethics approval merely because four text fields have been supplied. Masters/ODIN orchestration, real offline licensed Qwen with concurrent peak RAM on 8GB (E2) and P8 installer remain separate, unverified work.
