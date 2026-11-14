# PilotODIN 1.0 | P4-46 Closure-evidence feasibility and hard-stop protocol

**Date:** 12 November 2026. **Type:** evidence review and acceptance decision protocol only. **No code change, CI run, user-machine access, installer, original-data read, model fitting, or new owner approval.**

## Why this checkpoint exists

P4-43, P4-44 and P4-45 substantially improved prospective source safety, original-data comparator reliability, isolated native-dev identity and default-deny development entry points. Automated source tests for P4-45 [#43154963023](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/43154963023) and P1 [#43154962962](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/43154962962) completed successfully. **None can prove who changed a file in the original installed app-data directory before the tests.** Continuing to add source-only refusal guards without new specific evidence would inflate engineering effort without advancing P4 exit.

Owner's binding decision on 9 November 2026 was to **decline** the proposal to close P4 with unresolved risks deferred. No change is proposed to that decision.

## 1. Current independent R06 evidence, not a waiver

This is the actual owner Windows read-only comparator evidence recorded in [P4-24](./P4_24_STORAGE_DRIFT_ISOLATION_SOURCE_VERIFICATION_2026-11-11.md), reinforced by later read-only [P4-25](./P4_25_WEBVIEW_PROFILE_PROCESS_OBSERVATION_2026-11-11.md) and synthetic P4-41/43 changes:

| Observation | Evidence | Safe interpretation |
| --- | --- | --- |
| Independent preserved original backup | **Matches** historical baseline | The reference backup is intact |
| Original installed production EXE | **SHA matches** original baseline | No detected original desktop executable replacement |
| Protected original project-store `data/` relative file paths+contents | **0 added, 0 modified, 0 missing** in captured comparison | Useful scoped file evidence; **not** a certificate for all original app data |
| Entire original app-local-data tree | **FAIL**; 320 files reference vs 346 current; 74 file differences | Strict whole-tree preservation gate does not pass |
| Difference classification | 74 **browser/cache candidates**; 0 unclassified by known directory-segment patterns | Classification based on folder patterns, **not** proof of harmlessness or historical process |
| Owner's current live WebView2 launch-flag snapshot | 26 processes; 6 QA-root, 0 original-root, 20 other, 0 unresolved | Snapshot confirms only current profile launch arguments, **not** historical file writes or non-interference |
| Historical file-writer PID / executable and cause | **UNKNOWN** | No source-derived or synthetic tool can reconstruct this alone |

**Important scientific distinction:** Even verified future non-interference cannot transform the earlier failed 320/346 historical comparison into a prior PASS. The historical FAIL must remain in the register. A subsequently accepted *incident resolution* requires documented independent evidence and a **separate explicit owner judgement**, not a silent baseline reset or a browser-cache waiver.

## 2. What additional evidence is actually obtainable?

### R06-A: Historical attribution, conditional on prior records

The only credible route to specific *past* writer attribution is pre-existing, timestamp-relevant independent evidence, such as process/file-access auditing that was enabled **before** the changed files were written, or trustworthy application/OS diagnostic records capturing the write. Windows Security file-access events would only be useful if object-access auditing and relevant file/directory auditing were already enabled, retained and sufficient; ordinary event logs do not necessarily capture file writes. A filesystem change journal, if available and retained, can show metadata and change events but **does not by itself identify the writing process**. Later WebView2 `--user-data-dir` process lists are prospective snapshots, not a history.

**No request for admin permissions, registry changes, event audit enablement, USN reset, elevated commands, forensic downloads, or bulk export to GitHub is authorised.** Do not assume historic logs exist. No event log is supplied to the project at this checkpoint. Therefore R06 writer attribution remains UNKNOWN.

### R06-B: Prospective application non-interference, requiring explicit separate owner approval

A future controlled native test could establish **prospective**, limited non-interference, not old writer identity. Preconditions:
1. Separate explicit owner authorisation for any unpackaged native executable compilation **if** that would amend the current freeze, or defer until a final, separately approved P8 candidate. `next` is not authorisation.
2. Isolated, disposable QA environment, separate verified app ID, WebView profile, engine home and test projects; never open or migrate owner original projects.
3. Trusted historical backup and baseline preserved unchanged, with read-only original EXE/full-tree comparison **before and after**; record independent scoped observations, not a rewritten historical baseline.
4. Collect bounded, appropriately lawful and privacy-preserving prospective process/file access evidence; never equate a launch flag with proof of zero writes. Native functionality/8 GB Qwen must have independent evidence.
5. Any unexpected original-directory changes are a **STOP/FAIL**, not a cleanup task. Do not delete browser caches, restore files or ignore categories to create a PASS.

If this prospective study passes, it may support an **incident disposition** and source-isolation confidence, but cannot prove which process wrote the original 74 differences. A separate owner decision must determine whether the historical incident has been sufficiently explained/remediated under the **unchanged** phase-exit standard. If that cannot be justified without risk deferral, R06 stays OPEN.

## 3. Practical P4 exit dependencies: no synthetic substitution

| Risk | Existing technical evidence | Actual required exit evidence |
| --- | --- | --- |
| P4-R01 business decision / Gate C | P4 target review is synthetic-verified only | Independently verified actual business owner, label source/audit, decision moment, point-in-time predictors, entity/time dependence, non-model baseline, cost/benefit and lawful/fair use; no model fitting merely to manufacture evidence |
| P4-R02 native negative + Quality revision | Synthetic Python/Chromium tests passed | Source-matched actual Windows WebView2 N8–N11 plus relevant N4/N7/N12 cases |
| P4-R03 8 GB offline coexistence | No owner physical combined measurement | Sustained isolated actual 8 GB Windows + analytics + local Qwen + WebView2 with offline isolation and recorded measurements |
| P4-R04 native UX regressions | False archive notice and squeezed Decision usefulness source-fixed | Source-matched real Windows screenshots/interaction confirming repaired native UI and selected-target readability |
| P4-R05 Prepare controls / BE-024 | High-risk suggestion merge source corrected; partial regression tests | Independently accepted required Prepare interaction scope and native tested functional controls; no silent deferral of BE-024 |
| P4-R06 strict original storage | Original EXE/backup intact and project `data/` unchanged in observed comparison; **full tree FAIL** | Credible incident resolution and prospective non-interference evidence subject to explicit owner approval; historic FAIL retained |

## 4. Single consolidated future native acceptance, if separately approved

The same source-matched **one** isolated physical Windows session could investigate **R02 + R04 + R05**, and instrument **R03**. It should run only after source is ready, with disposable datasets and no intermediate installer; if a new native compilation is needed, owner must first decide whether that is allowed under the no-EXE freeze. The existing browser-only `Start_PilotODIN_Live_Dev.bat` may help inspect code/UI but **cannot** certify native WebView2, bundled Qwen or Windows resource performance. Do not trigger installed QA, create any executable, or seek a cloud CI substitute in lieu of this decision.

**R01** needs a legitimate, independently evidenced real business prediction objective, not a generated example or arbitrary public dataset presented as an approved business decision. If unavailable, mark **NO SUITABLE OBJECTIVE / UNVERIFIED**, not PASS.

**R06** needs real historical/prospective integrity evidence. Re-running the already successful Windows synthetic comparator or process observer without a reason is not a closure strategy.

## 5. Present decision: HOLD, not a waiver

1. **No further speculative P4-R06 micro-patches** unless a reproducible new fault emerges.
2. **No owner-machine commands or native build** based on generic `next`; preserve baseline, backup, evidence and app.
3. Current owner decision still forbids P4–P7 intermediate EXE/MSI/NSIS creation, download or install and rejected closure with known risks deferred.
4. Obtain **separate explicit owner decision** on whether an unpackaged, isolated native-dev executable is authorised. If not, native acceptance waits for a separately authorised final-stage candidate, and P4 cannot be fully closed under current unchanged native-exit conditions.
5. Obtain a **legitimate real business case** and available past file-access evidence, if any. Do not invent either.
6. Keep master QA Issue #2 and owner Issue #9 OPEN, R01–R06 OPEN, **P4 ACTIVE, P5 NOT AUTHORISED, P8 NOT CERTIFIED.**

**This is a documented dependency checkpoint, not an engineering feature completion or a new automated PASS.**
