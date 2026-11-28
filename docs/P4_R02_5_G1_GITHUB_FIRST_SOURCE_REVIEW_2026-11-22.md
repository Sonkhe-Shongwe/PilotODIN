# PilotODIN P4 R02.5 | G1 GitHub-first candidate review

**Date:** 22 November 2026
**Status:** G1 candidate published source-only at [`f9a18ef`](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/f9a18efb5d18fc6e4066cd04ddd378c666735157); G1.2 hardening below is an **uncommitted** follow-up. Neither is a native observation or acceptance credit.

## Published baseline reviewed

- Repository: `Sonkhe-Shongwe/PilotODIN`.
- Branch: `feature/live-dev-workspace-20261023`, commit `f5958b5bc892d92c7d01049af4cb86b7ac044c74` (GitHub compare to branch returned `identical`, zero ahead/behind).
- Existing strict correlator: `qa/p4_native/n12_etw_correlate.py`, Git blob `e6a16a540a0e57179775881b0bd447dbe5c69563`.
- Existing app journey: `qa/p4_research/n12_app_journey.py`, Git blob `8216e41b45271b787d34daa8cbdd9065839928f8`.
- The two new module/test repository destinations did not exist on the checked published branch; they are additive, with no existing file overwritten.
- Existing authority: `docs/DOCUMENTATION_INDEX.md`, `docs/SESSION_HANDOFF_CURRENT.md`, `docs/PROJECT_STATUS_CURRENT.md`, `docs/P4_R02_5_FILE_MUTATION_CREDIT_RECONCILIATION_2026-11-21.md`. `AGENTS.md` and the named 22 November local-only audit were **not** found on the published branch. They have **not** been treated as read or verified.

## Candidate scope

- `qa/p4_research/n12_physical_destination.py`: a **default-off, supplemental** assessment of already independently supplied original Windows file handle path evidence. It never launches the app, opens a filename or assigns native acceptance. Without separately corroborated original file handles, FileObject/IRP/path epoch, successful completion and complete loss/identity evidence, it reports `BLOCKED`.
- `tests/test_p4_n12_physical_destination.py`: deterministic standalone synthetic positive and negative scenarios. Uses only Python standard library.
- This document: exact-source read-only review and tests, no policy change.

### Concrete RED / GREEN finding

The 22 November original candidate used `casefold()` on all path components and accepted invalid Windows filename characters and reserved device names. Adversarial tests demonstrated false `CONTAINED_CANDIDATE_ONLY` assessments for ambiguous case spelling (`Straße` / `STRASSE`) and Windows-invalid/device components. Initial expanded candidate suite: **30 tests, 13 failing assertions**. The corrected code:

1. Preserves exact directory component spelling. NTFS directories can be case-sensitive, so even ASCII-only case mismatches are `BLOCKED` unless a separately reviewed proof strategy is introduced.
2. Rejects invalid Windows name characters, reserved DOS device basenames, control characters and previously rejected alias/traversal forms.
3. Requires independently corroborated Windows file-handle and ETW evidence before returning any supplemental candidate.
4. Never widens permitted roots, changes `n12_etw_correlate.py`, hides outside operations or upgrades an acceptance status.

**Verified in isolated Linux Python 3.13:**

```bash
PYTHONDONTWRITEBYTECODE=1 python -B -m unittest discover -s tests -p 'test_p4_n12_physical_destination.py' -v
python -m py_compile qa/p4_research/n12_physical_destination.py tests/test_p4_n12_physical_destination.py
```

**Result:** 31/31 synthetic tests PASSED; Python syntax check PASSED. No Windows ABI compilation, actual original WebView2 handle access, genuine FileIO source integration, whole-repository test suite or GitHub Actions execution was performed.

## Admission / follow-up gates

1. Review the published baseline, missing `AGENTS.md` and any later source changes before committing. Confirm these files remain absent and compare against independently developed unpublished work if it becomes available.
2. Test compatibility with the existing FileIO and authenticated private child-channel architecture before wiring this candidate. The original file **handle** must be independently observed; a process handle, UDF string or re-opened file path does not qualify.
3. Run focused and wider GitHub CI only when separately authorised. Real Sysmon, ETW, original handle acquisition, application/native runs and sensitive evidence require fresh precise one-use owner authorisation.
4. Keep every existing N12 filesystem FAIL/network FAIL and FileIO coverage BLOCKED classification. The correction is a fail-closed supporting source proposal, not a mechanism or diagnosis of the actual 113 outside-root WebView-network write credits.

## Progress ledger

- Four-gate remaining-work execution: **G1 IN PROGRESS, 0/4 completed, 0%**.
- Historical internal file-mutation engineering: **3/4 (75%)**, unchanged.
- Official R02.5: **0/5**; N12 **0/2**; P4 **14/20 (70%)**, unchanged.
- G1 published one authorised source-only commit: `f9a18efb5d18fc6e4066cd04ddd378c666735157` (three additive files); no automatically triggered CI run had been observed at initial publication. G1.2 changes are **not yet published**.


## G1.2 follow-up | Source compatibility and boundary hardening

**22 November 2026 | Source-only review and hardened candidate, not native evidence or acceptance.**

## GitHub authority and immutable baseline

- Repository: `Sonkhe-Shongwe/PilotODIN`, branch `feature/live-dev-workspace-20261023`.
- Published G1 parent: [`f9a18efb5d18fc6e4066cd04ddd378c666735157`](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/f9a18efb5d18fc6e4066cd04ddd378c666735157). Its three files were independently fetched and verified against their Git blobs before this work.
- Candidate: `qa/p4_research/n12_physical_destination.py` (Git blob `6955bbcd13dbab2e1b89f999a0628d982b60e3a6`). Tests: `tests/test_p4_n12_physical_destination.py` (Git blob `f3c1bfb2d8c76b73f94902f7da2aa249b03ac365`).
- Read-only source interfaces reviewed: `qa/p4_research/n12_no_cdp_fileio_review.py` (Git blob `11e13a58f84f0ee7b270a1842d3cdae8ad9433eb`) and `qa/p4_native/n12_etw_correlate.py` (Git blob `e6a16a540a0e57179775881b0bd447dbe5c69563`).
- This candidate changes **only** the physical-destination module, its focused test, and this document. The strict reducer, no-CDP runner, approval gates, native workflow, allowed roots and product code remain untouched.

## What the architecture actually establishes

The no-CDP reviewer currently calls `trace.inspect_etw_files(...)`, uses original app and WebView **process** handle/lifetime evidence, and returns `_fixed_report(...)` with `status=BLOCKED`, `native_N12_acceptance=NOT_EVALUATED`, `file_mutation_acceptance=NOT_EVALUATED`. These are not original Windows **file** handles for each mutation.

The G1 candidate needs a trusted original *file* handle, permitted-root handles, same-file-object/IRP/write completion, request-time path epoch, complete original writer lifetime, alias/reparse evidence and independent collector loss review. There is currently no verified production/no-CDP source bridge satisfying these simultaneous inputs. **Do not connect the candidate to `inspect_etw_files` or use it to credit paths by inference.** A process handle, WebView UDF string, public redacted receipt or path reopened by name is not interchangeable with the original file handle.

Before any future integration, the private source boundary would need to:

1. Supply separately authorised original-file-handle evidence for the precise observed mutation, with demonstrated ownership and lifetime; observe root handles under the same approved policy.
2. Independently bind the real writer process/thread, ETW FileObject/FileKey/IRP completion, request-time path epoch and observed final file path. Reject ambiguous joins, close/reuse, rename and mismatched paths.
3. Establish volume, directory case semantics, reparse/alias conditions, loss accounting and successful write completion from independent source data.
4. Retain private raw paths/handles only inside the authorised disposable evidence boundary; emit fixed redacted labels with all native acceptance fields still NOT_EVALUATED.
5. Re-run the original unmodified strict FileIO audit and controls. A supplemental physical-destination candidate cannot override original violations, unresolved writes, unsupported operations, protected-root requirements or network failures.

## RED to GREEN: two verified source defects

The original 31-test G1 candidate had two isolated robustness problems:

- With multiple permitted roots, the first case-ambiguous spelling could return BLOCKED even if a later root was an exact match on the same volume. This made the decision depend on root order. **Correction:** validate every root, scan all exact matches before applying a remaining case ambiguity. A root case difference by itself still blocks; it never grants containment.
- Malformed evidence envelopes (`None`, dictionary instead of typed private handle, invalid root tuples or missing corroboration object) raised `AttributeError` instead of returning a fixed `BLOCKED` result. **Correction:** type-check the evidence boundary before property access; do not accept strings, dictionaries or partial root tuples as independently observed handles.

Added four focused tests, including all six permutations of a three-root set, malformed input subcases and a retained case-ambiguity-negative case. Initial RED run at 34 tests exhibited **one failing assertion and eight erroring malformed-input subcases**. Hardened GREEN run: **35/35 synthetic tests PASS** (Python 3.13, isolated source-only Linux container). No Windows adapter execution, full-repository CI, GitHub commit, app launch, native capture, original-file-handle witness or true product filesystem verification was performed.

## Admission gate for this uncommitted follow-up

- Verify published branch HEAD remains `f9a18efb5d18fc6e4066cd04ddd378c666735157` before applying.
- Review and approve separately before committing or allowing CI auto-dispatch; a previous one-use source commit authorisation was consumed.
- Do not claim G1's 25% milestone closed by this source-only hardening. G1 still needs a verified safe integration contract and broader repo CI. Real native capture also needs entirely fresh explicit one-use approval and consumes no prior marker.
- Historic N12 filesystem FAIL, network FAIL and mutation coverage BLOCKED persist. Official R02.5 0/5, N12 0/2, P4 14/20 (70%); historical internal file-mutation engineering 3/4 (75%); four-phase execution G1 in progress, **0/4 completed (0%)**.
