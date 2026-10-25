# PilotODIN — CURRENT CHECKPOINT / NEW-CHAT ENTRY POINT

**Snapshot date:** 25 October 2026 (South Africa, UTC+02:00)  
**Status:** authoritative short continuity summary; keep this up to date, never delete historical QA evidence.  
**Repository:** private `Sonkhe-Shongwe/PilotODIN`  
**Active working branch:** `feature/live-dev-workspace-20261023` (**not** `main`)  
**Recorded source HEAD at creation, before these continuity-doc commits:** `b8665c78da14ab6388a1cf568579a936a034f99a`. **Always fetch the live feature-branch HEAD again before editing**; do not assume this snapshot hash stays the branch tip.  
**Master QA:** https://github.com/Sonkhe-Shongwe/PilotODIN/issues/2 (latest dated comments supersede older issue-body summaries).  
**Implementation roadmap:** [P0–P8 complexity-last](./PILOTODIN_CONSOLIDATED_ROADMAP_COMPLEXITY_LAST.md).  
**Long chronological history:** [CONTINUE_HERE.md](./CONTINUE_HERE.md). Earlier sections under "Read this first" and earlier "How to continue in a new ChatGPT tab" were historical research-stage statements; **this file supersedes them**.

## Read in this order, then proceed without repeating established questions

1. **This file first** for current phase, actual verification vs unverified new code, next action, hard prohibitions.
2. **Live feature-branch HEAD and relevant implementation/test files** on GitHub for any coding action; do not rely solely on written notes.
3. **Master QA Issue #2**: read the most recent comments, use exact observed Windows PASS/FAIL with commit/time where available.
4. **Roadmap** for phase ordering; **Resource-Aware Mode spec** [here](./RESOURCE_AWARE_MODE_DESIGN.md) for the active feature; A2/A3/A4 documents only if the new task materially concerns them.
5. Original master reconstruction blueprint (owner DOCX) for binding E-01–E-24 and E2/release scope; if it is not accessible in the new chat, **do not pretend it was read**.

## Project identity, environment and protected constraints

PilotODIN 1.0: **local-first, single-user Windows desktop data analytics and ML platform**; React/TypeScript/Vite frontend and Tauri/Rust native shell; Python/FastAPI, SQLite, pandas/sklearn analytics; future optional licensed **local** Qwen inference (not bundled/proven yet). Preserve immutable uploaded originals, versioned working data, explicit Quality approvals, honest deterministic statistics, leakage-safe split/target selection, project isolation and end-to-end report provenance. Explicitly **the user chooses the supervised prediction target**; target suggestion/automatic Master Analyst/Scientist remain research/planned, not shipped.

User's Windows clone uses **GitHub Desktop** on the active feature branch, `Start_PilotODIN_Live_Dev.bat` for development (frontend localhost:5173, backend localhost:8000), and `.venv-live\Scripts\python.exe`. The separate Tauri DEV ONLY smoke window was already compiled/opened and validated for native Save As. `PILOTODIN_HOME` and test `tmp_path` must isolate regression data. Do not launch installer, GitHub Actions (hosted minutes exhausted), or a high-RAM model spontaneously. Don't discard user's uncommitted files; past tests reported a dirty local checkout.

## What has been **owner-observed as passing** (do not retest reflexively)

| Milestone | Evidence | Acceptance limit |
| --- | --- | --- |
| **P0 development A2/A3/A4** | Owner-uploaded consolidated Windows archive showed **117/117 frontend tests, 174/174 backend tests, TypeScript/Vite + Python syntax PASS**; owner followed A2/A3 UI checklist and said **"everything works fine."** | Development workflows accepted as observed, not clean release or exhaustive edge cases; green suite predates newer P1 work. |
| **A3 real ML example** | `insurance_claims_CLEANED`, v0, selected Logistic Regression; held-out **82% accuracy / 73.8% macro F1 / 53.1% fraud-class recall** on 200 rows. Saved experiment reopening, invalid incident hour and Evaluate/Deliver examples demonstrated. | Fraud-class recall limitations must be transparent; avoid presenting predicted fraud as confirmed. Do not retrain/reimport to repeat past acceptance. |
| **A4 native Windows development export** | Separate real Tauri window launched; owner confirmed PDF/HTML Windows Save As and Cancel creates no file. User-supplied report revision 3 artifacts inspected: identical report SHA/data, evidence and readable five-page PDF. | **DEV ONLY** native test, not an installed offline release or all A4 failure paths. |
| **P1 failed-import recoverability** | One `Run_PilotODIN_P1_E2_Preflight.bat` owner run: **4/4 isolated Pytests PASS**, no real user data modified. | Covers four synthetic rollback cases, not total P1 release acceptance. |
| **Resource-Aware Phase 1 UI, admission and core backend** | **LATEST owner ZIP** `pilotodin-p1-resource-inm4loku.zip` (25 Oct 2026 ~19:08 SAST): **27/27 backend resource-policy+admission Pytests PASS**, **4/5 Node frontend source tests PASS**, **TypeScript/Vite build PASS**. Only Node false-negative banned-text assertion failed by matching ordinary documentation `requests.`; corrected in later test-only commit, but new Node execution PENDING. Earlier owner screenshot shows **Low-memory saved** and **1.09/7.80 GiB** displayed. | Low-memory admission Python tests are now Windows PASS on owner's checkout. Full restart preference persistence, the corrected fifth Node test, native model-loader end-to-end prevention and actual offline 8 GB operation are not independently accepted. |
| **E2 memory inventories** | Physical Windows RAM **7.804 GiB**. Free RAM observed **0.572 GiB** with heavy background load, **1.019 GiB** after RAID closed, and **1.09 GiB** later in Settings. Chrome/RAID/Plarium/Steam/ChatGPT/Edge notable; one Ollama process seen. | **E2 UNDETERMINED**. No demonstrated loaded Qwen, token generation, disconnected/offline operation, peak concurrent load, licensing or 8 GB release acceptance. No more repetitive scans requested. |

## **Exactly where engineering stopped — active P1 feature**

The owner approved **Resource-Aware Mode**: Adaptive (default), Low-memory and Performance. Settings save/read-only RAM are owner-observed. **The next Low-memory admission source WAS Windows-tested in Python: 27/27 backend cases passed**; only the source-contract Node test's broad banned-text assertion produced a false-negative, while Vite/TypeScript build passed. Its narrower assertion has now been committed but has **not yet been executed by the owner**. Code areas:

- `backend/resource_policy.py`: `admit_new_work` for **NEW** Low-memory operations only: new ML training screening floor **0.75 GiB available RAM**; new local bundled/Ollama inference floor **2.0 GiB**. If memory observation unavailable, defer new work in Low-memory. Floors are **heuristics, not peak memory guarantees**. Adaptive/Performance retain all existing hard resource/integrity caps.
- `backend/main.py`: new experiment calls admission **after** existing validity checks but **before** experiment persistence/background enqueue; retryable HTTP 503 and no ghost experiment if deferred. `GET /api/resource/preflight?operation=local_inference` reuses local-session scope.
- `backend/ai_provider.py`: local inference can decline below threshold and return **verified deterministic analysis**; preserve cloud consent policy.
- `frontend/src/api.ts`: IMPORTANT, the native desktop path previously launched bundled Rust AI worker before Python request; now **checks the same local-session resource preflight first**, without starting the model if low/unavailable; renders human-readable 503 messages.
- `frontend/src/ResourceSettings.tsx`: displays active Low-memory screens and floors, not an implemented durable scheduler.
- `tests/test_p1_resource_admission.py`, updated `tests/test_p1_resource_policy.py` and `frontend/tests/p1-resource-settings.test.cjs`: fake-RAM cases, preflight before artifact creation and native launch, no model calls, fallback and scoping. `tools/Verify_P1_Resource_Local.py`/one-click BAT now include focused suites; future consolidated runner includes them once.
- **Latest owner diagnostics:** `pilotodin-p1-resource-inm4loku.zip` includes `result.json` and logs: Pytest **27 passed in 4.15 seconds**; Node **4 passed / 1 failed** due broad textual `requests.` match in a Python docstring; frontend `tsc --noEmit && vite build` PASS (1618 modules). One targeted Node test assertion has been narrowed to executable imports/calls in `frontend/tests/p1-resource-settings.test.cjs` (test-only source correction, re-fetched and evaluated against current backend source, but **NOT YET run on owner's Windows**). `tools/Verify_P1_Resource_Local.py` now distinguishes implemented bounded preflight from the not-yet-built durable scheduler. No user dataset was tested/mutated.

**Next single owner verification action:** Pull current `feature/live-dev-workspace-20261023` once, open a PowerShell terminal in the GitHub Desktop clone's repository root and run **`cd frontend`** then **`node --test tests/p1-resource-settings.test.cjs`**. This checks ONLY the corrected **five** Node source-contract tests. Previously green **27 Python** tests and Vite build need **not** be repeated for this test-only fix. After Node 5/5 PASS, optionally observe Settings persists Low-memory on reopening/restarting; avoid reimporting/training the insurance dataset or loading Qwen. If Node red, share the short result/error and fix in one batch. Exact test passed status is still **pending** on the corrected commit.

**Next design milestone AFTER this gate:** bounded memory-aware serialization/cancellation for heavy operations (P5), reusing existing task contracts. **Do not jump ahead to full Qwen model startup or Master modes** before true E2 offline/8 GB feasibility.

## What is still genuinely open

- New active low-memory admission: **27/27 backend owner Windows tests PASS**; updated Node source contract **5th test pending**, as are true native prelaunch runtime observation and calibrated peak-memory testing.
- Per-device preference persisted through full restart: not yet explicitly observed.
- P1 remaining difficult imports, recovery/version lifecycle, project/UI edge cases; full release QA open.
- P2 remaining report polish/error paths (native DEV Save As itself already passed).
- E2 real licensed small local Qwen runtime, *disconnected* offline token generation and measured concurrent PilotODIN/ML on 8 GB hardware: **not yet performed**.
- P3 semantic data understanding, P4 business-value target recommendations with **user-target selection**, P5 durable task status/recovery, P6 Master Analyst/Scientist, P7 full orchestration, P8 standalone offline installer and original **E-01–E-24** acceptance: **not complete**.

## Operating protocol for every further ChatGPT session

1. **Verify repository HEAD and read this file plus current QA comments** before changing source or reporting status. New-chat summaries are pointers, not substitutes for code and test evidence.
2. Make coherent small development **batches** with tests; write to active feature branch, not main. Keep original datasets/data history intact; **never launch GitHub Actions or final installer** without explicit authorization.
3. Use user-visible Windows verification only when truly necessary because GitHub connector can commit/review but **cannot execute Rust/Tauri on user's laptop**. Prefer **one** focused launcher and one ZIP per development package; never claim an unrun test passed.
4. Record after each meaningful batch: **latest source commit**, code vs tests vs actual owner evidence, open blockers, **exact next action** in this file and QA Issue #2. Reconcile older docs; historical logs are not current to-do lists.
5. **Privacy/access:** This is a private GitHub repository. A new chat needs GitHub connector permissions to read it. Chat-only screenshots and local Temp ZIP paths do not automatically transfer to a different chat; status is recorded here, and artifacts must be supplied again only if the new task requires inspecting their contents. Original DOCX blueprint may need Project file access for new architecture work.
6. Avoid follow-up questions if facts already in this handoff answer them. Ask only if a truly essential authorization, missing resource or ambiguous requirement prevents safe work. **Zero questions cannot be guaranteed** across missing permissions, local UI observation or external changes.

## COPY THIS INTO A NEW CHAT (current version)

> Continue PilotODIN 1.0 development from the **current GitHub handoff**, not from older chat memory. The private repository is `Sonkhe-Shongwe/PilotODIN`, active branch `feature/live-dev-workspace-20261023`. Before acting, read **`docs/SESSION_HANDOFF_CURRENT.md`**, fetch the live branch HEAD, inspect latest QA Issue #2 comments and read `docs/CONTINUE_HERE.md` only for historical details. Respect the **recorded owner-PASS vs unverified new-code distinction**. Our present focus is P1 **Resource-Aware Mode**: Low-memory Settings save/RAM display were observed working; the latest 0.75 GiB training / 2.0 GiB local-AI preflight plus native prelaunch check is committed but not yet Windows-tested. The latest owner ZIP shows **27/27 backend tests PASS**, **4/5 Node tests PASS** and **TypeScript/Vite build PASS**; the sole Node failure was an overbroad `requests.` text match in Python documentation, and its assertion has been corrected in GitHub but not yet rerun. Next pull the branch and run **only `cd frontend; node --test tests/p1-resource-settings.test.cjs`** (expect five tests), then proceed with resource-aware task coordination after that passes. Preserve data/version/approval/leakage safeguards, no automatic model download, no hosted Actions, no installer and no repeated P0/A4 tests. Work in coherent GitHub batches, document exact commits/tests, and **do not ask me to restate decisions already recorded**. If I say “next,” proceed from the next verified gate rather than restarting planning.

