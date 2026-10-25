# P4 increment 3 — conservative prediction timing and label provenance review

**25 October 2026: code/source batch prepared; owner Windows execution PENDING.**

## Why this increment exists
P4's first owner-accepted increment screens structurally plausible target labels. Its second accepted increment captures four user-provided descriptions (outcome meaning, decision, prediction moment and historical label source) scoped to project, approved Quality version and target. Those descriptions are NOT independent business or temporal evidence.

This third increment adds a read-only **review aid**, not a gate that establishes that training is safe or that a model will be useful. It reuses the version-bound GET and current P4 Prepare panel, with **no new endpoint, migration, experiment, dataset transformation, or AI call**.

## Exact behavior
- `backend/target_timing_review.py`: bounded deterministic review of *column names* and saved user text. Optional lexical wording cues (`after`, `reported`, `suspected`, `unknown`, etc.) are presented only as questions. A match does NOT prove leakage, a bad label or late knowledge. A nonmatch does NOT prove safety. Scan at most 100 headers, return at most five header-only clues with truncation label. Never read raw cell values or train.
- `backend/target_opportunities.py`: attach `risk_review` to existing candidates, **without** modifying ranking, structural eligibility, existing blockers or `safe_to_train_automatically=false`. No user description means `context_missing` and review questions, never approved status.
- `frontend/src/TargetOpportunities.tsx`: a collapsible **Prediction timing and label provenance: review required** block for each proposed target. Render explicit caveats and bounded questions; keep the existing Save context and separate Review this target action unchanged.
- Input source remains the existing local/version-scoped `GET /api/projects/{id}/target-opportunities`, guarded by local-origin/version/project checks. No other project or dataset version context is fetched.
- Explicit non-goals: claiming that text verifies label provenance, training permission, suitable split, timing correctness, fairness or causation; returning derived predictive accuracy; sending context to cloud.

## One focused Windows acceptance gate, NOT YET RUN
`Run_PilotODIN_P4_Prediction_Timing.bat` calls `tools/Verify_P4_Prediction_Timing_Local.py` using `.venv-live\Scripts\python.exe` and isolated synthetic `PILOTODIN_HOME`. Three phases: new P4 review Python + directly affected two old P4 Python modules; new P4 Node source contracts + directly affected two old P4 Node contracts; `npm run build` (TypeScript and Vite). One `pilotodin-p4-timing-*.zip` with result.json and phase logs. If FAIL upload ZIP for targeted repair; if PASS report PASS. Do not repeat P0/A4/P1/P3/P5, run hosted GitHub Actions or fetch Qwen.

## Acceptance limits
Source-only implementation and test definitions are not execution evidence. Owner Windows gate remains **PENDING** until actual test output arrives. Even successful focused tests would not prove a real Windows installed app, 8 GB combined AI/ML feasibility, full native UX or any of E-01–E-24. Preserve original immutability, exact Quality approval, explicit target choice and scientifically sound ML preparation.
