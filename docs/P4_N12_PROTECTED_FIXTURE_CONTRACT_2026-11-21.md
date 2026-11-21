# PilotODIN P4 | Small protected-root fixture contract (source only)

**Date:** 21 November 2026
**Scope:** N12 R02.5 evidence architecture. This is NOT native execution or P4 acceptance.
**Contract:** `qa/p4_research/n12_protected_fixture_contract.py` and `tests/test_p4_n12_protected_fixture_contract.py`.

## Purpose and boundary

The previous [architecture decision](./P4_N12_FILE_MUTATION_EVIDENCE_DECISION_2026-11-21.md) found that the focused native collector always sets `procmon_loss_reviewed=false` while the A/B comparator requires `true`. Re-running those A/B arms is not a viable completeness proof. Do not change that flag merely to obtain a green check.

This micro-step provides a **read-only receipt-schema contract** and synthetic tests. It does not create directories, alter Windows ACLs, start a token-restricted process, create accounts, collect ETW, launch PilotODIN or touch an owner's device. The schema checker can return `SHAPE_COMPLETE` on fabricated data, but **always returns `native_N12_acceptance: NOT_EVALUATED` and `owner_native_execution_authorized: false`**. Receipt shape is not genuine evidence.

## Exactly two disposable roots

For a separately approved future native test, create only two test directories beneath a newly created, canonical, unique run-scoped folder under the GitHub-hosted Windows `RUNNER_TEMP`:

- **protected:** one known sample file, one replacement target and an empty test location. A trusted fixture supervisor owns the security descriptor, not the restricted writer.
- **permitted:** positive-create space and one known file for a reversible content write. All allowed transient mutations happen here, not within the protected root.

The Python contract records only the labels `protected` and `permitted`, not actual filesystem locations. The future native driver must check canonical confinement, symlink/reparse-point/junction absence, newly created roots, exact owner identity and no overlap with real app data before exercising any operation. Ordinary folder-level ACL assumptions are insufficient.

## First candidate: restricted primary token

Evaluate a trusted supervisor using Windows `CreateRestrictedToken` and `CreateProcessAsUser` to launch **only the generated test writer**. The GitHub Windows runner normally has administrative rights, so a test run as the ordinary runner token does not demonstrate an effective restriction. Neither this API implementation nor a local account is being created now.

Require independently verified primary token, restricting SID, Administrators SID set deny-only, removal of takeover/restore/backup privileges, distinct owner of the protected root and a rights check that actually prevents mutation there while permitting the positive control. A simple `IsTokenRestricted` result is insufficient. Treat any unsupported token launch or inherited privileged escape as **BLOCKED**, never silently fall back to an unrestricted token.

Microsoft references: [restricted tokens](https://learn.microsoft.com/en-us/windows/win32/secauthz/restricted-tokens), [CreateRestrictedToken](https://learn.microsoft.com/en-us/windows/win32/api/securitybaseapi/nf-securitybaseapi-createrestrictedtoken), [CreateProcessAsUser](https://learn.microsoft.com/en-us/windows/win32/api/processthreadsapi/nf-processthreadsapi-createprocessasuserw), [file access rights](https://learn.microsoft.com/en-us/windows/win32/fileio/file-access-rights-constants), [privilege constants](https://learn.microsoft.com/en-us/windows/win32/secauthz/privilege-constants), [GitHub-hosted Windows permissions](https://docs.github.com/en/actions/reference/runners/github-hosted-runners).

## Fixed operation matrix

| Restricted writer attempt | Expected Windows control result |
| --- | --- |
| Create in protected root | Access denied |
| Overwrite existing protected file | Access denied |
| Truncate protected file | Access denied |
| Rename into protected root | Access denied |
| Rename out of protected root | Access denied |
| Delete protected file | Access denied |
| Write then restore protected file | Access denied before any protected content mutation |
| Change protected ACL | Access denied |
| Take ownership of protected file | Access denied |
| Create inside permitted root | Success |
| Write then restore permitted test file | Success; independently observed transient write |

An `access-denied` category alone does **not** prove a file was protected; a missing path, broken writer process, wrong handle, unexpected syscall error or a simulated result must not count. The future driver must bind every result to an observed native Win32 operation, actual path/object identity, verified restricted process and error code, with the permitted control verifying the same writer can perform the operation when allowed.

## Independent evidence and stop conditions

The **identity evidence** is a verified restricted primary token with no privilege/ownership bypass and a real effective access check. **Prevention evidence** requires every protected operation denied and the permitted operations successful under the same writer. **Preservation evidence** requires independently generated full-tree content, metadata and identity agreement. **Observation evidence** requires ETW process-lifetime binding, zero independently verified lost events, complete file-operation path attribution and visibility of the deliberately write-and-restored permitted control. No successful protected mutation or unresolved mutation is acceptable. Cleanup and permission restoration must also be demonstrated on the disposable host.

ETW counters, protected file hashes and Win32 token receipts must come from separate trustworthy runtime observations. The source-only `check_evidence_shape()` validates **only the schema**: exact two root labels, all expected operations, required binary proof labels, strict zero unresolved-mutation counts and no extra raw fields. It cannot verify evidence provenance or OS behavior; even a flawless synthetic receipt never awards native acceptance. Never echo secrets, full filenames, raw SIDs, PIDs, tokens, command lines or event payloads in the public summary.

## Next micro-step

Without running it, specify a bounded **restricted-token capability preflight**: required Windows APIs, expected access token privilege/SID checks and precise fail-closed reasons for launch or effective ACL issues. Do not yet create ACLs, request actual token launches, trigger native CI, run PilotODIN or create installers. A source-reviewed and separately owner-approved disposable Windows capability test is required before physical verification.

## Phase boundary

Official P4 **14/20 (70%)**; file-mutation **3/4 (75%)**; N12 **0/2**. Governing full N12 remains filesystem FAIL, network FAIL, mutation coverage BLOCKED. The historical original-data incident remains open. All live N12 workflows remain disabled. No P5/P8 release authorization.
