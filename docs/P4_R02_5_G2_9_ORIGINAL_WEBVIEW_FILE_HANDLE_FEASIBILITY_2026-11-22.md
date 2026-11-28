# PilotODIN R02.5 | G2.9 original WebView2 file-handle attribution feasibility

**22 November 2026. GitHub source-only audit and admission contract, NOT native instrumentation or permission.**

## Decision

The successful [generated Sysmon bookends #45049623361](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/45049623361) corroborated two independent TCP/UDP collector windows on hosted Windows, but **did not launch PilotODIN, WebView2 or Kernel-File ETW**. It therefore does not establish original WebView2 **file** handle provenance. G2 cannot reach 50% with a generated fixture or original WebView **process** handles alone.

**GO** for narrowly specified, separately approved evidence engineering only after the actual Windows file-handle acquisition and FileObject matching mechanism is reviewed. **NO-GO** for interpreting a process query handle, a reopened file by name, a file's volume serial/index, a WebView profile or a synthetic caller-supplied `original_file_handle` string as actual original-file-handle proof. Do not make a native approval request until the candidate capture mechanism and privacy bounds are source-reviewed.

## Exact source inventory and trust boundary

| Current source | Directly supported evidence | Cannot supply |
| --- | --- | --- |
| `qa/p4_research/n12_no_cdp_child_handles.py` `ScopedQaChildHandleObserver` | Original retained **process query handles** for sampled WebView children, bound to PID and process birth/exit | A WebView-owned original **file handle** or its relation to ETW FileObject |
| `qa/p4_research/n12_private_child_pipe.py` `WITNESS_FIELDS` | Private authenticated process-lifetime transport (`pid`, `birth`, `exit`, two images, parent PID) | File handle values, FileObject, FileKey, IRP, path or handle-open epochs |
| `qa/p4_native/n12_etw_probe.py` and `qa/p4_research/n12_fileio_identity_join.py` | Real historical **generated** file writes and a retained original **generated writer process handle**; ETW request/completion | Authenticated WebView-owned file handles from a real product |
| `qa/p4_research/n12_physical_destination.py` `observe_supplied_windows_handle` | Queries final path and volume metadata of a **caller-supplied handle** | Acquires original WebView file handle, proves owner PID, kernel FileObject address, or request-time name epoch. Explicitly returns `UNVERIFIED_HANDLE_PROVENANCE` |
| `qa/p4_research/n12_fileio_pair_contract.py` | Indexed source-only ETW Write 16 and OperationEnd 24 matching, negative reuse/epoch checks, `PrivateOriginalFilePair` | Native authentication of any caller-provided handle, process birth, FileObject pointer, completion or loss claims |
| `qa/p4_research/n12_no_cdp_fileio_review.py` | Existing strict audit, role/path gaps, counts, child process handles, same-capture restore and loss summary | Accepts no substitute for independent original **file** handle / ETW / path / operation proof; returns `BLOCKED`, `NOT_EVALUATED` |

## Candidate minimum native witness, NOT yet implemented

For each actual WebView2 file write that would receive destination credit, a separately authorised **bounded original-handle observation** would need to establish, inside one real capture:

1. **Original writer identity:** genuine WebView2 descendant PID *plus exact process birth / ETW sequence*, verified original process handle and image; not a PID alone. Any missed/reused child blocks.
2. **Original file-handle acquisition:** recorded evidence that the specific file handle belonged to the verified writer process at the relevant time and, if a safe approved implementation duplicates it, that it refers to the **same underlying file object**. A newly opened handle by pathname is not the original handle. Process query handles are not file handles.
3. **Kernel object bridge:** independently corroborated mapping from that original writer file handle's object identity to the Kernel-File event `FileObject` or other supported robust identifier, and the exact `FileKey`, `Irp`, issuing thread and writer lifetime. Do not assume file index, volume serial or final pathname is an ETW kernel pointer.
4. **Operation/epoch:** request-time Write (Event 16), unique successful OperationEnd (Event 24), no ambiguous IRP reuse, file-object/name/handle close/rename/reparse transition between observation, request and completion. A stop-time name alone is insufficient.
5. **Physical destination:** request-time path, independent handle-derived destination under verified root handles, volume identity and case/alias/reparse checks. Any unresolved root or location blocks, including protected or outside-scope mutations. Raw identifiers and private paths remain runner-private.
6. **Completeness:** real app launch-through-exit and original handle coverage including short-lived WebView descendants, independent Kernel-File ETW loss/counter review, before/after snapshots and same-capture two-write restore, calibrated capture bookends and cleanup. Missing observation never earns negative proof.

**Capability decision:** Microsoft documents `DuplicateHandle` for permitted cross-process handle duplication, but it requires appropriate source-process rights including `PROCESS_DUP_HANDLE`. A safe *discovery* route for the original WebView file handle is not presently implemented. The native `NtQuerySystemInformation` handle table interfaces are internal and subject to change, and system-wide enumeration may expose unrelated process objects. The current owner approval explicitly forbade expanded file-handle enumeration. Neither such enumeration, foreign handle duplication, code injection, a kernel driver nor system policy changes are authorised by source-only GitHub authority.

Before implementing any native observer, specify a **strictly scoped** target-process/handle set (actual source-verified WebView children only), bounded observation time and maximum handles, no owner data or unrelated process scans, no raw public logs or uploads, no privilege/allowlist changes, deterministic cleanup, failure behavior for privilege or API unavailability, and an independent same-object verification strategy that does not rely on filenames alone. Require **new explicit source-pinned owner consent** for any actual Windows original-file-handle observation. If a trustworthy bridge cannot be constructed with available privileges, record the gap as **BLOCKED** rather than weakening the gate.

## Exact-source negative regression and limits

`tests/test_p4_n12_g2_9_original_file_handle_admission.py` uses existing actual source contracts and synthetic values to prohibit upgrading process handles, reopened names or unverified adapter outputs into file-path credit. Even a manually asserted complete original-file-handle witness returns `CONTAINED_CANDIDATE_ONLY` and `native_N12_acceptance=NOT_EVALUATED`, not a native PASS. The governing no-CDP FileIO reducer stays `BLOCKED` with all attractive synthetic summaries. These tests do not authenticate Windows identities; they guard the admission decision.

The GitHub source-only workflow runs the new focused suite, with **no** Windows/native workflow invocation. Record the actual exact-source CI run and count before claiming successful verification.

## Microsoft implementation references

- [DuplicateHandle and source-process rights](https://learn.microsoft.com/en-us/windows/win32/api/handleapi/nf-handleapi-duplicatehandle)
- [Process Security and Access Rights](https://learn.microsoft.com/en-us/windows/win32/procthread/process-security-and-access-rights)
- [NtQuerySystemInformation stability restrictions](https://learn.microsoft.com/en-us/windows/win32/api/winternl/nf-winternl-ntquerysysteminformation)
- [FileIo ReadWrite ETW FileObject and FileKey](https://learn.microsoft.com/en-us/windows/desktop/ETW/fileio-readwrite)
- [GetFinalPathNameByHandle](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-getfinalpathnamebyhandlea)

## Governing result

Both native GitHub workflows remain **DISARMED**; previously consumed approval markers remain immutable and the next future generated-only marker remains absent. No actual original WebView file handles, native collection, owner files, root exemptions, installer, or acceptance are created by this review.

G1 **PASSED**. G2 **OPEN**. Four-gate delivery **1/4 = 25%**; official R02.5 **0/5**, N12 **0/2**, P4 **14/20 (70%)** unchanged.

## Exact-source GitHub verification, after publication

- [G2.9 source commit `1cbc65cd7476d59889fa5b468b1bdb06bdf5c243`](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/1cbc65cd7476d59889fa5b468b1bdb06bdf5c243) changed exactly four files: the focused original-file-handle admission tests, Ubuntu-only CI, this source feasibility review and the four-gate execution tracker. It did **not** change either native capture workflow or any one-use consent marker.
- [Exact-source Linux Actions #45052136179](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/45052136179) **COMPLETED SUCCESS**, first attempt. GitHub job logs verified **181/181 source/synthetic tests across 12 suites**, including **13 new G2.9 negative-admission tests**. The preexisting 168 suites also passed, with no raw Windows trace, collector, application launch, foreign handle duplication, kernel driver or owner filesystem access.
- Even the all-true synthetic `original_file_handle` input remains **`CONTAINED_CANDIDATE_ONLY`**, with `native_N12_acceptance=NOT_EVALUATED`. The original strict no-CDP reducer remains **BLOCKED**. This validates conservative source handling only, not live native FileIO provenance.

**Status after CI:** Four-gate delivery **1/4 = 25%**, G2 OPEN, R02.5 **0/5**, N12 **0/2**, P4 **14/20 (70%)**, unchanged. The next engineering activity is to design and test a strictly bounded, original WebView2 writer-owned *file* handle acquisition witness with a defensible same-object Kernel-File ETW bridge. Actual Windows access remains separately consent-gated.
