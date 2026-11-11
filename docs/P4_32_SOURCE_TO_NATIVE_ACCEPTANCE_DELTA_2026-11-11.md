# PilotODIN 1.0 | P4-32 Source-to-owner-native acceptance delta

**Date:** 11 November 2026  
**Authorised phase:** P4 Target Intelligence, ACTIVE  
**Mode:** GitHub read-only audit and acceptance planning only. **No app build, installer, change to owner files or evidence recreation.**

## Verified comparison boundary

GitHub compare API: [previous owner-tested separate QA source `bca3c57b94a425cd9ef489726e721328d12c2ead` versus audited current source `2b739eccaecb82df05c1025a73d7174edfb410c3`](https://github.com/Sonkhe-Shongwe/PilotODIN/compare/bca3c57b94a425cd9ef489726e721328d12c2ead...2b739eccaecb82df05c1025a73d7174edfb410c3).

**Direct result:** `ahead_by=85`, `behind_by=0`, `status=ahead`, 57 changed files returned. This is the **frozen source comparison at the audited SHA**, not a claim about code changes in the later documentation-only audit commit. The number of commits is not a defect count or a claim that every changed file requires separate user testing. Earlier native owner screenshots are genuine but tied to the older separately identifiable QA source, not the current development HEAD.

The last focused P4 source-and-browser run [#43064149245](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/43064149245) and adjacent P1 isolated frontend [#43064147313](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/43064147313) both **COMPLETED SUCCESS at `6585d4424cce3dc0c98f70ebf8d919efb07126e9`**, before the audited documentation-only HEAD. Neither executes the owner-installed desktop app or proves offline 8 GB feasibility.

## Specific source deltas that matter to a later one-pass native QA

| Changed path(s) | Observed comparison change | Owner-native evidence still needed |
| --- | --- | --- |
| `frontend/src/TargetOpportunities.tsx`, `frontend/src/studio.css` | Added selected-target/checkpoint and decision-evidence styling hooks | Selected target and decision usefulness are legible; selecting/declining never silently trains |
| `frontend/src/UnifiedShell.tsx`, `frontend/src/projectLifecycleSignal.ts`, `frontend/src/unified-shell.css` | Empty-project archived-state safety and drag-to-dock workspace handling; additional shell chrome/clock | No phantom archive banner on an empty project; workspace dock/undo preserves selected project and unsaved state |
| `backend/main.py`, `backend/storage.py` | Explicit 409 conflict and transactional recheck of Quality version + active project on target-context writes | Version changes and archived project must not allow stale context writes, hidden experiments or cross-project leakage |
| `backend/target_opportunities.py` | Timestamp/derived-target blockers, finite-value checks, blank-label/predictor safeguards, labelled-row predictor overlap | Synthetic rare/missing/no-outcome negative cases, explicit manual blocker review and abstention remain visibly fail-closed |
| `qa/p4_native/Measure_P4_Native_Readiness.ps1`, `Compare_P4_Original_Storage.ps1`, `Observe_P4_WebView_Profile_Processes.ps1` | Read-only integrity and diagnostic tooling added since the older QA source | Existing actual 26-process owner snapshot is scoped current-profile evidence, **not** historical file-writer or full-tree certification |

The table is **scope derivation from actual GitHub source diffs**, not a list of proven failures or authorisation to run destructive tests. Detailed previous test instructions already exist in [P4-10](./P4_10_NATIVE_ACCEPTANCE_KIT_2026-11-09.md), [P4-22](./P4_22_WINDOWS_INTEGRITY_AND_RESOURCE_READINESS_2026-11-09.md), [P4-23](./P4_23_CONSOLIDATED_WINDOWS_ACCEPTANCE_GO_NO_GO_2026-11-09.md), and [P4 owner Issue #9](https://github.com/Sonkhe-Shongwe/PilotODIN/issues/9). **Do not create another fixture ZIP or run all old N-cases separately.**

## Remaining gates and explicit authorisation boundary

1. **Frozen original preservation failure: NO-GO.** Independent backup and production EXE hash match, source-defined protected project `data/` subtree 0 detected differences, yet complete original app-data tree comparison is **FAIL** (320 baseline vs 346 current files; 74 browser/cache *candidates*, historical writer UNKNOWN). No cleanup, cache exclusion, reset, replacement backup or acceptance waiver. A new baseline cannot retroactively erase this failure.
2. **One current-source isolated Windows candidate: NOT AUTHORISED.** A future owner decision must separately approve creating/building, transferring and installing ONE identifiable QA candidate, with independently grounded source SHA → CI-built EXE hash → installed QA EXE hash and strict original production app isolation. Do **not** rebuild or install based on generic `next`.
3. **Consolidated physical acceptance after separate owner approval: NOT TESTED for current source.** Only disposable synthetic projects, native Prepare/Target review visibility, stale version and project isolation, no unintended training/writes; source-fixed UI parity, non-atomic original data integrity guard, actual disconnected local inference and sustained 8 GB resource behaviour require real owner equipment and verified observations. Do not claim browser CI or a short RAM sample passes these.
4. **Real business Gate C: UNVERIFIED independently of native work.** Actual authorised decision owner, auditable later outcome labels, predictor availability at as-of decision time, repeated-entity/group/time validation, non-model decision baseline and measured cost/benefit, fair/lawful checks. A safe conclusion may be `NO SUITABLE PREDICTION OBJECTIVE YET`; synthetic classification is not a pass.
5. **Risk signoff and release: PENDING.** Owner previously declined the proposal to defer unresolved P4 risks. Do not close P4, start P5 or certify P8 based on a new manifest or automation check.

## Next authorised action and result

**Read-only GitHub audit COMPLETE.** This document contains no new test pass, owner approval, executable, original data or machine access. No pending workflow was counted as successful. The next significant implementation/release-like operation is **blocked on explicit owner approval** and must also respect the existing failed preservation baseline. A separate private owner discussion can determine whether to authorise one isolated QA validation session while keeping Gate C independent and the preservation mismatch unresolved.

**P4 ACTIVE; P4-R01–R06 OPEN; P5 NOT AUTHORISED; P8 NOT CERTIFIED.**
