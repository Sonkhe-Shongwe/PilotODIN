# PilotODIN 1.0 | Current project status
**As of:** 4 November 2026  
**Branch:** `feature/live-dev-workspace-20261023`  
**Primary phase:** **P1 OPEN** under the [owner-adopted phase policy](./PHASE_FOCUS_AND_CLOSURE_POLICY_2026-10-28.md).  
**Release:** **NOT CERTIFIED**. This document is a scoped development ledger, not a release announcement.

## Executive status
PilotODIN has substantial React/TypeScript, FastAPI/SQLite and Tauri source; several core data, Quality, analysis, modelling and reporting workflows are implemented and have scoped development evidence. The app is **not** a fully integrated, self-contained offline 1.0 product yet. **Only P1 is the current primary implementation/acceptance phase**. Earlier focused P2–P5 engineering does not make those phases complete.

## Latest exact verified code and tests
| Evidence track | Actual result | Source SHA and limitation |
| --- | --- | --- |
| Frontend Node + build + hosted isolated Chromium | **144/144 Node PASS, build PASS, 5/5 Chromium PASS** | [run #41833432539](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/41833432539), tested SHA `ebd10e2db992ee6bc4ec8dc53a436d156d226458`. Retains source focus correction and adds Manager impact preview; no native Windows certification. |
| Disposable loopback backend + Chromium | **3 separate integrated scenarios, each 1/1 PASS** | [run #41833432977](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/41833432977), same tested SHA. A/B Quality/recovery, C consent/approval/undo/restore and D/E manager with read-only impact and project rename/archive/restore/restart all PASS. **Still not native WebView2/Narrator**. |
| Owner Windows P0 development | **117 frontend / 174 backend PASS** at dated checkpoint; observed A2/A3 walkthrough accepted | Earlier scoped Windows development checkpoint, not current whole-system or installed 1.0 certification. |
| Owner Windows P1 native interaction | Edited Prepare title-bar X/Stay/Leave, docked Prepare and WIN-K1–K4 **owner-reported PASS** | DEV ONLY Tauri at dated evidence; untested S/A/screen reader gates remain. |

**Latest documentation HEAD before audit:** `276809852ff420600f1a235c3e7196ff495badc3`. Later documentation-only commits do not inherit an unexecuted test PASS.

## Phase ledger
| Phase | Current accepted boundary | Remaining / formal state |
| --- | --- | --- |
| **P0** Core A2/A3 development | Substantial owner-observed workflows and focused Windows automated checks; **development journey accepted** for the observed checkpoint | Broader production/offline release certification not granted |
| **P1** Import, Quality, project/UI, resource policy | Hosted real-backend Q3 now verifies synthetic consent→approve→undo→restore→restart and mounted keyboard focus; earlier native unsaved-close/keyboard scoped PASS retained | **OPEN**. Native WebView2 Q3 and Narrator, physical scaling/snap, reduced motion, full native journey and formal closure remain |
| **P2** Deliver / PDF / reports | Scoped report, immutable revision, Save As, font resource, Unicode DevQA and frozen sidecar proofs | **REVIEW REQUIRED**. Production Unicode PDF **VISUAL_FAIL** / not accepted; six-file final SHA/licence owner decision **NOT GRANTED**, end-user PDF/release gate open |
| **P3** Semantic understanding | First shared semantic profile and focused verification | Partial. Broader semantic accuracy and real native UX validation |
| **P4** Target intelligence | Focused ranking, business context, timing/provenance and two-axis evidence | Partial. Real-world decision value and integrated experience; **explicit user target choice required** |
| **P5** Durable ML/resource task controls | Focused low-memory slot, factual progress, soft cooperative cancellation and interruption safeguards | Partial. General queue/retry/crash resume, process-level hard-stop and combined AI/ML scheduling |
| **P6** Master Analyst / Master Scientist | Architecture and research; some reusable foundations | **Not product-accepted**. Build deterministic end-to-end Master workflows with approval and validation |
| **P7** Autonomous local ODIN / orchestration | Preliminary typed-tool/controller and resource foundations | **Not accepted as genuine autonomous offline capability**. Grounded multi-step inference, safety, repair, recoverable task control |
| **P8** Clean offline Windows Build F | Desktop/sidecar/installer source and selected older DEV proof exist | **NOT RELEASE CERTIFIED**: clean install, bundled licensed local AI/runtime, real 8 GB coexistence, security/privacy, accessibility, rollback and E-01–E-24 |

## Non-negotiable acceptance boundaries
- A green Node test is **not** a native Windows test. Simulated 150% DPR is **not** physical Windows scaling.
- A source/frozen resource proof is **not** production Unicode rendering or licence approval.
- A working desktop DEV window is **not** clean installed offline 1.0 acceptance.
- A read-only RAM inventory is **not** a successful offline Qwen + ML concurrent benchmark. A prior ~8 GB Windows snapshot showed serious memory pressure, but did not prove infeasibility.
- Historic P1 75–80% and overall ~40–45% figures were illustrative judgements, **not auditable earned-value KPIs**. This ledger therefore uses evidence statuses, not official percentage-complete claims.

## P1 validation blocker, reconciled 4 November 2026
GitHub source and green CI do not establish the remaining Windows-native accessibility, physical scaling/Snap, actual Quality correction/restart and integrated recovery gates. Owner-deferred S1..S4/A1 have **no owner waiver**. Current phase is **P1 OPEN / native acceptance BLOCKED**, not closed, irrespective of the successful hosted Q3 tests. Issue #2 `BE-033` was reconciled against existing source (disabled selector placeholder plus New project control), with native multi-project acceptance still unverified. **This is documentation/QA reconciliation only, no new code, Windows run or tests.**

## Current P1 project-management source increment (4 November 2026)
**Verified tested SHA:** [`5c261a03765f`](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/5c261a03765f7fffe408273a9201ec16f940f3f0). Owner-authorised P1 project-management slice adds an accessible Manager UI and transactional revision-bound **Rename, Archive and Restore**, with archived projects hidden from active selection and original data/evidence retained. **Permanent Delete is not implemented or authorised as a blind data purge.**

Tests: [9/9 isolated backend pytest](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/41827678997) on backend source ancestor `3fde4449`; [143/143 frontend Node, TS/Vite build, 5/5 hosted isolated Chromium](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/41830669671); [all 3 real-Uvicorn/Chromium synthetic scenarios passed](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/41830669685) on `5c261a03765f`, including synthetic project management rename/archive/restore and actual backend restart. Earlier failed CI attempts are historical and were not counted. **No owner/native Windows acceptance**, installer or protected original dataset touched.

**P1 remains OPEN / native acceptance BLOCKED.** This new evidence does not change owner deferred S1..S4/A1 or unverified Narrator, real native Q3/N1 and resource acceptance. Issue #8 tracks further lifecycle design and deletion requirements.

## P1 read-only project deletion-impact increment (4 November 2026)
[Exact tested SHA `ebd10e2db992`](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/ebd10e2db992ee6bc4ec8dc53a436d156d226458) adds **Review impact** to Manager, a no-write `GET /api/projects/{id}/deletion-impact` and an inventory of known direct/indirect SQLite relations plus safe classification of managed dataset/model locations and blockers. The preview reports deletion unavailable. **No permanent DELETE capability has been implemented.**

Verified [12/12 backend pytest](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/41832930061) on unchanged backend source ancestor, [144/144 Node + build + 5/5 Chromium](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/41833432539) and [3/3 real Uvicorn/Chromium](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/41833432977) on final tested SHA, all using disposable projects. [Detailed no-delete and future recovery plan](./P1_PROJECT_DELETION_IMPACT_AND_SAFETY_DESIGN_2026-11-04.md).

**P1 OPEN / native acceptance BLOCKED**. Reviewed impact is not an exhaustive file manifest or an authorisation to delete. Owner Windows/WebView2, screen reader, physical scaling/Snap, Q3/N1 and resource gates are unchanged.

## Current priority and next decision
1. Use the [P1 closure register](./P1_CLOSURE_REGISTER_2026-10-28.md) to reconcile remaining native acceptance, identify which owner-deferred checks must be explicitly accepted as deferrals, and keep P1 OPEN otherwise.
2. Do not create more speculative P1 tests when only missing native evidence blocks closure. Investigate a new code defect only if confirmed and in scope.
3. Carry out a narrowly permitted **read-only/offline 8 GB AI feasibility assessment** when authorised, without installing or training models in protected data.
4. After P1 closure, resume **P2** Unicode PDF production/final owner licence decision, then P3 → P8 according to [complexity-last roadmap](./PILOTODIN_CONSOLIDATED_ROADMAP_COMPLEXITY_LAST.md) and dependencies.

**Safety:** No original/private project or CSV, approved Quality history, external backup, installed app, untracked `Cargo.lock`/`gen`, model, installer or release asset should be changed merely to generate acceptance evidence.

See [short handoff](./SESSION_HANDOFF_CURRENT.md), [documentation audit](./DOCUMENTATION_AUDIT_2026-11-04.md) and [master QA Issue #2](https://github.com/Sonkhe-Shongwe/PilotODIN/issues/2).
