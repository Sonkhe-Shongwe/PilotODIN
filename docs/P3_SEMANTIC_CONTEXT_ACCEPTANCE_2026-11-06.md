# PilotODIN P3 | Current semantic intelligence development and acceptance register

**Date:** 6 November 2026  
**Active phase:** **P3 ACTIVE / IN DEVELOPMENT** under the owner's "okay lets begin" instruction directly following the reviewed P3 plan. P1 and P2 remain closed for bounded development. This is **not** P3 completion, P4 reactivation or 1.0 release certification.  
**Branch:** `feature/live-dev-workspace-20261023`.  
**Source commits:** [P3-02 feature `b5e556fa8bdf`](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/b5e556fa8bdffcbe8b5522e1475ec90272ff46cb) followed by [P1-compatible impact inventory `b660dd193d87`](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/b660dd193d87efd5e05b6b56659485e5f0323da4). Subsequent documentation-only commits are not fresh source test runs.

## Frozen working boundaries for this increment

P3 supplies deterministic, read-only **hypotheses** about industry, possible unique record key, field roles and observed metadata, plus **explicit human-authored contextual descriptions**. The latter are **user-provided and NOT independently verified**. No learned semantics, semantic confidence percentage, invented data provenance, automatic supervised target selection, P4 business-value rating, LLM/cloud inference, model training or modification of original/approved working datasets.

P4 already owns specialised target descriptions (outcome, decision, prediction moment, label source) in the separate `target_business_context` table. P3 does not duplicate, overwrite or automatically interpret that P4 data as truth. No schema-wide semantics are confirmed by an operator merely saving an unverified note.

## Current P3 acceptance matrix

| ID | Scope / critical acceptance expectation | Actual evidence | Disposition |
| --- | --- | --- | --- |
| **P3-01** | Deterministic bounded domain/grain/field hypotheses and explicit abstention; read-only project/version pinning and local-origin check | [First P3 focused Windows record](./P3_DETERMINISTIC_SEMANTIC_PROFILE.md): **9/9 Python and 4/4 Node PASS** 25 October, with earlier TS/Vite PASS; original failure then targeted repair preserved | **ACCEPTED, scoped source/Windows tests**, not manual desktop semantic review |
| **P3-02a** | User-triggered descriptions of domain, what one row represents and up to eight field definitions; SQLite by project+Quality version, labelled `user_described_not_independently_verified`, no auto-approval | `backend/storage.py`, `backend/main.py`; [P3 GitHub CI #42243211489](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/42243211489): **20/20 Python PASS** across new P3, original P3 and adjacent P4; source modules compiled | **IMPLEMENTED / SYNTHETIC BACKEND PASS**, actual native owner interaction still pending |
| **P3-02b** | Existing Data Dictionary editor Save/display, separate original hypothesis from user text, limit 8 entries, explicit action, no P4 mutation | `SemanticContextEditor.tsx`, `SemanticOverview.tsx`, `ColumnInvestigation.tsx`; same [CI #42243211489](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/42243211489): **8/8 Node contracts PASS**, `tsc --noEmit && vite build` **PASS** (1,652 transformed modules) | **IMPLEMENTED / SOURCE+BUILD PASS**, **real HTTP/browser and Windows WebView2 UX pending** |
| **P3-02c** | New table not misclassified as unknown project material by the P1 read-only impact inventory | [Initial P1 lifecycle run #42243211342](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/42243211342) **FAIL 16 pass/2 fail** (new table unrecognised). `backend/project_delete_impact.py` corrected to explicitly classify and count the table; [rerun #42243608383](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/42243608383) **SUCCESS, 18/18 PASS** at SHA `b660dd193d87` | **FIX VERIFIED**, preserve initial failure evidence; no project deletion feature activated |
| **P3-03** | Reconcile user-described meaning vs inferred hypotheses; maintain disagreement/unknown status, optional safe reuse of confirmed-by-user metadata in relevant views without bypassing existing P4 gates | Current screen shows user descriptions alongside hypothesis, but broader cross-view reconciliation and independently reviewed provenance **not complete** | **OPEN / carefully scoped next P3 requirement** |
| **P3-04** | One bounded end-to-end UI run including Save/reopen, edit, project change, version change, keyboard focus/errors, no actual data mutation; P3 closure matrix and owner approval | No new native Windows/installed app or real Uvicorn+Chromium UI run for P3-02 | **OPEN / next acceptance gate** |

**Source and build evidence scope:** The P3-02 feature commit `b5e556fa8bdf` triggered seven GitHub workflows. P3 focused **SUCCESS**: 20/20 Python, 8/8 Node, TypeScript/Vite PASS; existing P1 backend/real HTTP/frontend plus P2 report comparison and revision idempotency succeeded. **P1 lifecycle initially FAILED** due to the new table, fixed in `b660dd193d87`, rerun **18/18 PASS**. The successful P3 workflow ran on feature SHA `b5e556fa8bdf`, not after the inventory-only fix; the targeted P1 workflow ran on `b660dd193d87`. Both are Linux runner synthetic evidence, not physical Windows testing.

## Validation and security boundary

- All writes require explicit user POST through the existing local-host/desktop-session protected API, current project and expected approved Quality version; empty descriptions, duplicate/unknown field keys and invalid lengths are rejected.
- The GET `/api/projects/{id}/semantics?expected_version=N` still returns original unmodified hypotheses, now accompanied by `user_context` or null. User description does not override observed counts, ID uniqueness, risk warning, or target selection.
- SQLite `semantic_business_context` is additive and holds only descriptions; no backfill, source mutation, new ML experiment or automatic P4 context migration.
- Known limitation: a user can type inaccurate contextual claims. Text is labelled **user-described not independently verified**; a saved note is not statistical truth, source provenance certification or a business context confirmation gate for automated training.
- Tests run with disposable synthetic projects on GitHub runners. No original owner datasets/models, installer, trained weights, original font binaries or licence documents were changed.

## Next justified engineering action

**Before wider P3-03 scope:** obtain actual P3-02 Save/reopen/edit browser or native evidence in one deliberately bounded synthetic Data Dictionary journey (including project/version change and error handling) to validate real UI and persistence. If a defect is reproduced, fix it narrowly, run affected tests and record Issue #2. Do not rerun the accepted historic P3-01 or P2 acceptance matrices without changed source. After this verification, choose whether any stronger shared 'confirmed' semantics and cross-view use are justified; do not invent ontology/AI or duplicate P4 metadata. P3 must not be closed without final owner-scoped acceptance and unresolved High/Critical triage.
