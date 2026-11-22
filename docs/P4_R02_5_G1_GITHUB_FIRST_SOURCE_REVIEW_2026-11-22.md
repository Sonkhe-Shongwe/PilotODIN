# PilotODIN P4 R02.5 | G1 GitHub-first candidate review

**Date:** 22 November 2026
**Status:** uncommitted source-only candidate; **NOT** integrated, a native observation or acceptance credit.

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
- GitHub branch commit/push/CI: **NONE**. The accompanying git-apply patch is intended for explicit review, not unattended publication.
