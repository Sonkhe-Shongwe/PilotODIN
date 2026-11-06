# PilotODIN 1.0 | P2 scope and acceptance register (CURRENT)

**Reconciled:** 6 November 2026  
**Repository/branch:** `Sonkhe-Shongwe/PilotODIN` / `feature/live-dev-workspace-20261023`  
**Decision state:** **P2 ACTIVE / REVIEW_REQUIRED; release-font decision BLOCKED ON OWNER; release NOT CERTIFIED**.  
**Scope baseline:** This is a **provisional evidence inventory**, **not an owner-frozen phase-scope matrix** or a phase-closure decision. The [one-primary-phase/closure policy](./PHASE_FOCUS_AND_CLOSURE_POLICY_2026-10-28.md) requires an explicitly frozen and accepted phase scope before closure. No user instruction in the latest handoff approves Unicode inclusion, exclusion, release asset distribution or P2 closure.

## How to read this register

This is a short **current decision index**. [`SESSION_HANDOFF_CURRENT.md`](./SESSION_HANDOFF_CURRENT.md), [`PROJECT_STATUS_CURRENT.md`](./PROJECT_STATUS_CURRENT.md), and [master QA Issue #2](https://github.com/Sonkhe-Shongwe/PilotODIN/issues/2) remain the project's authoritative continuation and status records; the linked focused reports below retain detailed test histories, source SHAs and limitations. A newer scoped result supersedes an older `PENDING` note **only for the same requirement**, not for unrelated release conditions. Do not delete older failed/cancelled workflow evidence.

Statuses used here: **ACCEPTED (scoped)** means the exact named observation/test was completed, not a release; **BLOCKED** means required owner/legal authorization or final artifacts are absent; **OPEN** means no complete recorded acceptance; **CONDITIONAL** depends on the unmade scope decision.

## A. Reporting and Windows Deliver, currently in P2

| ID | Requirement and acceptance boundary | Latest demonstrated evidence | Current status |
| --- | --- | --- | --- |
| P2-D01 | Guided, human-authored report composition, actual saved immutable revision/reload; authenticated legacy HTML/PDF preserve text and evidence | [Guided persistence actual FastAPI/SQLite + Chromium #42092287767](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/42092287767): 2/2 on source `6afe0e71d9c5`; [5 Nov handoff](./SESSION_HANDOFF_CURRENT.md) | **ACCEPTED (hosted real HTTP/browser; synthetic, not installed Windows)** |
| P2-D02 | Verified evidence inspection, immutable revision comparison, no-op save and superseded report export safety | [Evidence inspection #42084006200](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/42084006200), [revision comparison #42076603865](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/42076603865); focused records in handoff | **ACCEPTED (scoped real HTTP/browser/source)** |
| P2-D03 | Unsaved Deliver draft protection on internal New/Open, Explore evidence handoff and primary navigation; correct visible warning | [P2 draft guard](./P2_UNSAVED_REPORT_DRAFT_GUARD_2026-11-05.md), [handoff protection](./P2_EXPLORE_DELIVER_HANDOFF_DRAFT_PROTECTION_2026-11-05.md), [warning fix](./P2_NEW_REPORT_UNSAVED_WARNING_2026-11-05.md) | **ACCEPTED (specific source/browser workflows)** |
| P2-N01 | Real Windows synthetic full shell: unsaved warning, Explore Keep, New project Keep (no late importer), Explore Leave with keyboard usable, New project Leave after approval | [Five-step owner native record](./P2_NATIVE_DELIVER_OWNER_FULL_SHELL_QA_2026-11-06.md): all five `OWNER_REPORTED_PASS`, actual modal/draft/Explore screenshots | **ACCEPTED (five owner-native scenarios, synthetic DEV only)** |
| P2-N02 | Real Windows **two-window** native: foreign project storage event preserves A dirty Deliver, A's deliberate Stay veto and deliberate approved Switch | [Three-step two-window record](./P2_NATIVE_DELIVER_TWO_WINDOW_OWNER_QA_2026-11-06.md): all three `OWNER_REPORTED_PASS`; warning and retained A note screenshot | **ACCEPTED (three owner-native scenarios, synthetic DEV only)** |
| P2-N03 | Optional active dirty Deliver tab-close Keep/Leave detailed sequence | [Tab-close source and focused regressions](./P2_NATIVE_DELIVER_TAB_CLOSE_SAFETY_2026-11-06.md) are recorded. Owner's general tab-no-issue report does **not** specifically show this optional pair | **OPEN (optional scoped residual; not an automatic phase blocker or pass)** |
| P2-A01 | Additional Windows Narrator/screen-reader verification specific to Deliver modal, retained focus, importer and notices | The five-step runner reports keyboard usability for Explore; instrumented Narrator/screen-reader evidence for **all** relevant P2 panels is not recorded | **OPEN (separate accessibility residual; assess priority with owner)** |

## B. Unicode PDF source, licensing and release decision

| ID | Requirement and acceptance boundary | Latest demonstrated evidence | Current status |
| --- | --- | --- | --- |
| P2-U01 | Developer-only synthetic mixed-script PDF uses the actual backend renderer, extraction, visual layout, evidence/table/metric preservation | [P2 actual renderer history](./P2_PDF_UNICODE_PRODUCTION_INTEGRATION_GATE.md): 37,355-byte one-page synthetic PDF visually reviewed after prior sparse two-page correction | **ACCEPTED (synthetic opt-in renderer ONLY)** |
| P2-U02 | Existing authenticated PDF export route remains safe/default legacy, preserves HTML and rejects malformed/partial release authority | [Font owner decision ledger](./P2_PDF_FONT_RELEASE_OWNER_DECISION.md): Windows **28/28** source + in-process authenticated HTTP contracts `19+9` accepted; default loader status `NOT_GRANTED` with blank reference and no pins | **ACCEPTED (source + synthetic in-process HTTP, NOT frozen/installed)** |
| P2-U03 | Establish original font licence provenance and RFN/face facts | [Owner font decision](./P2_PDF_FONT_RELEASE_OWNER_DECISION.md): three full upstream OFL texts and `METADATA.pb` byte/blob identities verified at `google/fonts@e7db6ca603fd4862010383ff17ffd6cc4ffac1c0`; Noto Sans SC's `Source` RFN/`NotoSansSC-Thin` documented | **ACCEPTED (read-only *upstream notice* provenance); NOT a release grant or final binary/hash attestation** |
| P2-U04 | Decide explicitly whether the **1.0 product scope** includes end-user mixed-language Unicode PDF or defers it while keeping legacy PDF | [Unsigned owner decision record](./P2_PDF_FONT_RELEASE_OWNER_DECISION.md), no explicit include/defer choice | **BLOCKED ON OWNER PRODUCT-SCOPE DECISION** |
| P2-U05 | **If included:** independent review/approval of exact three original unmodified font binaries + three full original OFL notices; final **six actual SHA-256**, size/name/path; Noto SC unchanged variable face/RFN treatment; accessible third-party notices and approval reference | Original upstream notice Git blob SHA-1s and DevQA bytes are **not** final six SHA-256/source release approval. `backend/pdf_release_font_loader.py` currently has `RELEASE_APPROVAL_STATUS="NOT_GRANTED"`, `RELEASE_APPROVAL_REFERENCE=""` and `RELEASE_PINNED_FILES=()` | **CONDITIONAL / NOT_GRANTED; no release assets** |
| P2-U06 | **If included and after approval:** normal saved authenticated Unicode PDF, exact six-file sidecar resource integrity, failure-closed missing/corrupt resources, multiple/repeated/concurrent exports, unchanged HTML, offline Windows installed/visual/resource checks | [Production sidecar/font gate](./P2_PDF_PRODUCTION_SIDECAR_FONT_GATE.md) and [owner decision](./P2_PDF_FONT_RELEASE_OWNER_DECISION.md) define proof; developer-only frozen probe and one-page PDF do not prove actual installed release | **CONDITIONAL / NOT_TESTED (actual packaged product)** |
| P2-U07 | **If deferred:** retain legacy end-user PDF and HTML, keep Unicode approval disabled and its proof isolated; record approved P2 scope change and deferred product requirement | Default production loader currently fails closed/uses legacy without Unicode approval; no signed owner deferral exists | **CONDITIONAL / REQUIRES EXPLICIT OWNER APPROVAL** |

## C. Phase and release boundary

- **P1** is CLOSED **for bounded development**, with the separately recorded [P1 closure residuals](./P1_CLOSURE_REGISTER_2026-10-28.md); no reopening without policy grounds.
- **P2** remains the **single active phase**. Its accepted Deliver journeys and developer-only Unicode PDF proof must not be reopened or rerun without relevant source change or a newly evidenced serious defect.
- **P2 closure requires** (i) a frozen owner-approved in-scope requirement matrix, (ii) all critical in-scope product journeys accepted with their required test modality, (iii) no open critical/high in-scope defect, (iv) owner-approved explicit defer/accept decisions for remaining lower-priority residuals, and (v) master Issue #2 plus both handoffs reconciled. **This register is not itself that approval.**
- **P3+** are not activated. **P8 installed/offline/8 GiB Windows release is NOT CERTIFIED**; the synthetic native DevQA window, CI and source renderer tests are not substitutions.
- **Historical results are not automatically current-head CI:** The last verified GitHub branch head when this register was created followed the `6ca9cdd38f23` documentation-only upstream-license update. Specific CI links above belong to their recorded **earlier source SHAs**; the owner's Windows-focused Node/Vite build and native runs were screenshots, not GitHub Actions at this later documentation HEAD. No new full regression, Windows build, installer or font distribution was performed for this register.

## D. One next decision and controlled continuation

**Owner/designated scope authority must choose** either:

1. **Include Unicode PDF in PilotODIN 1.0**, subject to a later *independent* approval of the exact six original distribution files, hashes, notices, RFN/face policy and full source/installed acceptance; **this is not permission to ship assets today**; or
2. **Defer end-user Unicode PDF from the 1.0 scoped development target**, explicitly preserving the accepted legacy PDF and source-only developer proof. This is **not** silent cancellation, P2 closure or 1.0 release approval.

**Until then:** Keep `NOT_GRANTED` loader policy, protect accepted reporting/native workflows, do not add fonts, run installers, start training, expand phase scope or fabricate an approval. The current next engineering action is **owner product-scope decision**, not new speculative implementation. If no decision is available, pause this approval-dependent slice and report the blocker rather than generating duplicate font microtests.

**Continuity rule:** On any substantive future change, update *this short status index* and the linked focused record, then [session handoff](./SESSION_HANDOFF_CURRENT.md), [project status](./PROJECT_STATUS_CURRENT.md) and [Issue #2](https://github.com/Sonkhe-Shongwe/PilotODIN/issues/2), preserving historical failures and exact tested source attribution.
