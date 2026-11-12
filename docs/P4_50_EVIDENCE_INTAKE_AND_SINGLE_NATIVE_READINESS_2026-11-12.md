# PilotODIN 1.0 | P4-50 Read-only evidence intake and single native acceptance readiness

**Date:** 12 November 2026. **Type:** independent-evidence audit and future test sequencing, NOT a new acceptance result. **Authorised action:** analyse repository issue/doc records and prepare the plan. No app-code changes, CI, user-device access, native build, installer, original-app writes, model fit, audit-policy changes or P4 phase closure.

**Controlling sources:** [P4-24 owner original storage comparator](./P4_24_STORAGE_DRIFT_ISOLATION_SOURCE_VERIFICATION_2026-11-11.md), [P4-25 actual owner WebView2 observation](./P4_25_WEBVIEW_PROFILE_PROCESS_OBSERVATION_2026-11-11.md), [P4-46 evidence boundary](./P4_46_CLOSURE_EVIDENCE_AND_DECISION_BOUNDARY_2026-11-12.md), [P4-47 one-use native CI smoke](./P4_47_ONE_APPROVED_UNPACKAGED_NATIVE_CI_ACCEPTANCE_2026-11-12.md), [P4-49 final implementation](./P4_49_MIXED_CASE_IDENTIFIER_SCREEN_2026-11-12.md), [existing disposable native kit](../qa/p4_native/README.md), [native results template](../qa/p4_native/RESULTS_TEMPLATE.md), [master QA #2](https://github.com/Sonkhe-Shongwe/PilotODIN/issues/2) and [owner P4 acceptance #9](https://github.com/Sonkhe-Shongwe/PilotODIN/issues/9).

## Audit verdict: facts must be distinguished from unknowns

| Scope | Available evidence | Verdict / boundary |
| --- | --- | --- |
| Trusted pre-QA backup | Original independent backup recomputed to trusted historical baseline | **MATCH** for preserved backup reference |
| Old production executable | Original installed desktop SHA matched trusted original baseline | **MATCH** for scoped original EXE |
| Critical original project store | Relative files under original `data/`: **0 added / 0 changed / 0 missing** in owner-observed comparator | Scoped original project-store file evidence, NOT full app-data certification |
| Entire original application-local-data tree | 320 files backup, 346 files observed, **30 added, 40 modified, 4 missing = 74 differences** | **STRICT FAIL**, not waived, no cleanup/rebaseline authorised |
| Difference classification | 74 browser/cache *candidates* and 0 unclassified according to known folder-segment patterns | Names indicate candidate categories, NOT harmlessness, process identity or cause |
| Live WebView2 metadata | 26 processes: 6 separate QA-root flags, 0 original-root flags, 20 other, 0 unresolved | Current **non-atomic** profile-flag observation only; NOT historic writer evidence |
| Historic writer of 74 changed files | No contemporaneous process/file-write audit supplied in the project docs and current Issue #2 / Issue #9 records | **UNKNOWN**. No claim that no such evidence exists elsewhere on owner Windows |
| Source-matched unpackaged CI smoke | One previous owner-approved isolated Windows CI `tauri build --no-bundle` plus 12s process smoke, without bundled sidecars/Qwen | **PASS for limited CI native startup/profile scope only**; permission consumed; no full P4 workflow/native 8 GB proof |
| Real operational prediction objective | No independent business decision owner, outcome truth, as-of feature availability, independent baseline or benefit/fairness evidence supplied | **Gate C UNVERIFIED**, no approved target or fit |
| Latest P4-49 source CI | 163 Python + 45 Node + 9 real-HTTP Chromium; TS/Vite; synthetic Windows safety all PASS | Source/synthetic PASS; not user-native full acceptance |

### R06 historical audit: evidence available versus not available

**Completed this checkpoint:** review the P4-24/25/46/47 records and issue history for retained, timestamp-relevant process/file-access attribution. The available material repeats UNKNOWN writer and supplies no attributed process event, file-handle trace, or historical per-file writer audit. The GitHub code/issue search found no supplied Sysmon report. **Negative search is limited to the checked repository and issues**, never a determination about Windows logs on the owner's machine.

**If owner already has pre-existing independent logs:** privately preserve their original format and provenance. Relevant evidence must establish the event timestamp, actual original app-data object written, executable/process identity and mapping to the incident window, with reliable chain of custody. Object-access auditing must have been enabled when the event occurred to be meaningful; ordinary Windows Event Viewer logs or USN change metadata do not alone prove a historical process writer. Accept a redacted summary only when independently verifiable. Do not assume those logs exist.

**Do NOT** turn on audit policies after the fact, request admin elevation, perform scans against the original app directory, copy private logs into public GitHub, reset journals, install forensic utilities, reopen the production app for experimentation, delete/recreate caches, restore app data or alter the baseline. If no relevant prior audit exists, record **HISTORICAL WRITER UNRECOVERABLE FROM CURRENT EVIDENCE** (not a claimed cause and not a PASS). R06 remains OPEN with the strict earlier FAIL preserved.

### R01 real business Gate C: minimum independent intake, not hypothetical ML data

Before recommending/approving any actual prediction objective, record these facts against **one** legitimate, permitted use case. If an independent source is unavailable, use `NOT SUPPLIED` rather than fabricate evidence.

| Required item | Evidence and acceptance check |
| --- | --- |
| Decision and decision owner | Human/organisation actually responsible; concrete intervention available at prediction moment and who authorises it |
| True outcome | Exactly defined event/value, observation period, reporting delay and how labels are independently confirmed |
| Origin and audit trail | Non-sensitive description of system-of-record and independently verifiable label provenance; no user-owned row exports |
| As-of prediction time | Decision timestamp or cutoff and proof candidate features were observable before that moment, not retrospectively populated |
| Independence and split | Whether entities repeat; group key/time ordering from documented data grain; reserved validation strategy and leakage risks |
| Non-model baseline | Measured existing decision rule/process over comparable periods/groups, not a synthetically selected benchmark |
| Business cost and benefit | Estimated intervention cost, errors/false positives, measured comparative decision utility, limitations and who signs off |
| Lawful/fair deployment | Data rights/permissions, potential affected persons, relevant safeguards, reasonable decision explanation and adverse-impact review |

**This is an evidence request, not a licence to ingest private records or fit a model.** If no eligible business case exists, P4-R01 must remain UNVERIFIED, and `NO SUITABLE PREDICTION OBJECTIVE YET` is a valid product outcome, not P4 closure.

### Consolidated future native acceptance: one source-matched, separately approved milestone

**Status now: BLOCKED, NOT RUN.** Do not use a generic `next` or this planning document as new compilation/install authority. The P4-47 owner-approved one-off build is completed and its temporary gate retired. Any future unpackaged native developer build requires **new explicit owner approval**. P4–P7 intermediate installers, distributed EXEs, MSI/NSIS and any original-data migration remain forbidden. No standalone backend or model sidecar can be claimed present in the old 12s CI smoke.

1. **Before anything runs:** independently link exact source SHA -> trusted native build record -> executable SHA; verify distinct `com.pilotodin.p4isolatednativedev` identity from `com.pilotodin.studio` and `com.pilotodin.p4nativeqa`, distinct WebView profile/storage, no inherited `PILOTODIN_HOME`, no original data directory override, no paths under owner original app/data. Disposable machine and data only. No installer. If any check fails or approval absent: **STOP/BLOCKED**.
2. **Native P4 functional cases, using existing fixture generator/manifest:** N1 native lineage, N2 balanced classification + alternatives, N3 repeated synthetic IDs disclosure (not entity proof), N4 defer/decline/reselect stale-state protection, N5 explicit abstention/no modelling, N6 finite regression/manual target, N7 project switching isolation, N8 four-of-80 rare class block, N9 24-of-80 labelled row block, N10 unnamed target abstention, N11 safe Quality-version change 409/stale view rejection without touching original projects, N12 no automatic fit/cloud/original-data write. Existing older owner-native subcases remain **historical**, not falsely replayed on newest source.
3. **Current native UX/Prepare (R04/R05):** verify archive warning only on true archived project, readable Decision usefulness and target strip, additive user exclusion choices, included predictor count, per-field preprocessing explanation and high-risk acknowledgement. Record actual screen observation, exact native SHA and PASS/FAIL, not just source tests. No training experiment needed to verify the explicit gates.
4. **Physical offline 8 GB (R03):** only on a separately approved 8 GB target system and with genuinely present, permitted local Qwen runtime/sidecar, capture actual system RAM, sustained concurrent native UI, WebView2, analytics and inference process measurements with true offline isolation. Pre-set duration, workload and stop limits with owner before proceeding. No stand-in CI runner, 12-second no-Qwen smoke or shell-only profile snapshot may substitute. If model/sidecar unavailable: **NOT TESTED**.
5. **Prospective R06 non-interference:** only if separately approved and feasible under existing restrictions, take an independent read-only original EXE + complete original-app-data snapshot before/after isolated disposable native session, preserving reference backup and prior failed report untouched. Any new difference: **STOP/FAIL**. Prospective PASS would still NOT identify the previous writer, erase 74 historical changes or automatically close strict R06.
6. **Evidence capture and decision:** record per-case observed outcome/sha/time, minimal sanitised screenshots/logs and explicit `PASS / FAIL / NOT TESTED / BLOCKED` in [Issue #9](https://github.com/Sonkhe-Shongwe/PilotODIN/issues/9) and defects in [Issue #2](https://github.com/Sonkhe-Shongwe/PilotODIN/issues/2). Do not post personally identifying operational data or raw private paths publicly. No P4 risk waivers or advancement to P5/P8 without owner's separate informed decision.

## Immediate action disposition, 12 November 2026

- **DONE:** Read-only evidence audit of public project records and existing documented owner observations; source-matched synthetic CI evidence reviewed; future test steps scoped to the exact open gates.
- **PENDING OWNER-SUPPLIED EVIDENCE:** contemporaneous historical writer audit (only if already exists) and independent legitimate business decision/label evidence.
- **BLOCKED:** new compiled native functional application and owner physical 8 GB/Qwen evidence; no fresh permission or environment supplied.
- **NO CHANGE:** no modified source/test scripts, CI run, native compile, installer, original files, baselines, business decision records, existing QA PASS/FAIL or phase criteria. P4-R01–R06 stay OPEN; **P4 ACTIVE, P5 NOT AUTHORISED, P8 NOT CERTIFIED.**

**Next useful work:** assess any newly provided independent historical writer evidence or real business use case on its merits. Only after a new explicit owner scope decision and proven isolation preflight should the consolidated source-matched native test be scheduled. Avoid duplicate fixture bundles or speculative source micro-patches.
