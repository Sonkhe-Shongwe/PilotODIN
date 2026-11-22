# PilotODIN R02.5 | G2.10 process-scoped PSS file-handle candidate design

**22 November 2026. Source-only feasibility check and candidate admission, not native operation or approval.**

## Decision

**PSS is a potentially narrower discovery candidate** than system-wide native handle-table enumeration. Microsoft documents `PssCaptureSnapshot(ProcessHandle, ...)`, `PSS_CAPTURE_HANDLES`, `PssWalkSnapshot(..., PSS_WALK_HANDLES, ...)` and `PSS_HANDLE_ENTRY` which carries a captured handle value, capture time, type name, and optionally object name. However, **PSS_OBJECT_TYPE contains no File enum**. `PSS_OBJECT_TYPE_UNKNOWN` means unsupported/unknown; `SECTION` is a file-mapping object, not a file handle. Treat a `File` type-name observation as *tentative*, pending actual Windows validation, not as a trusted classifier. Neither a PSS handle number nor the snapshot's name/metadata is a documented Kernel-File `FileObject` pointer.

Official Microsoft references: [PssCaptureSnapshot](https://learn.microsoft.com/en-us/windows/win32/api/processsnapshot/nf-processsnapshot-psscapturesnapshot), [PssWalkSnapshot](https://learn.microsoft.com/en-us/windows/win32/api/processsnapshot/nf-processsnapshot-psswalksnapshot), [PSS_CAPTURE_FLAGS](https://learn.microsoft.com/en-us/windows/win32/api/processsnapshot/ne-processsnapshot-pss_capture_flags), [PSS_HANDLE_ENTRY](https://learn.microsoft.com/en-us/windows/win32/api/processsnapshot/ns-processsnapshot-pss_handle_entry), [PSS_OBJECT_TYPE](https://learn.microsoft.com/en-us/windows/win32/api/processsnapshot/ne-processsnapshot-pss_object_type), [DuplicateHandle](https://learn.microsoft.com/en-us/windows/win32/api/handleapi/nf-handleapi-duplicatehandle), [process access rights](https://learn.microsoft.com/en-us/windows/win32/procthread/process-security-and-access-rights).

## Completed source-only work

- `qa/p4_research/n12_pss_file_handle_candidates.py` is an **inert**, pure Python admission gate. It **cannot** call native APIs, capture Windows processes, enumerate/duplicate handles, read owner files, run FileIO or launch PilotODIN. Every input is an untrusted caller claim. The maximum input is **one exact process PID + birth**, two complete, process-scoped PSS snapshot claims with **256 rows maximum each**, and a **5-second maximum** span enclosing one claimed write request/completion. Invalid process, incomplete/oversized table, reused duplicate handle row, wrong source, malformed timestamps, wrong type metadata or mismatched handle blocks.
- The most favorable synthetic scenario, same numeric handle with `File` type-name present on both sides, yields only **`CANDIDATE_ONLY`**. It explicitly reports `original_file_handle_provenance=NOT_VERIFIED`, `handle_reuse_excluded=false`, `kernel_fileobject_etw_join=NOT_ESTABLISHED`, `same_object_at_write=NOT_ESTABLISHED`, `physical_destination=NOT_VERIFIED`, `native_N12_acceptance=NOT_EVALUATED`. Even if all input Boolean claims are true, source does not transform them into independently authenticated evidence.
- `tests/test_p4_n12_g2_10_pss_file_handle_candidates.py` adds synthetic positive-candidate and fail-closed adversarial cases, plus an assertion that the contract contains no native system calls. GitHub's source-only Ubuntu CI watches and tests the new files. **Exact GitHub source CI must pass before this can be called verified.**

## Critical limitations

1. A process PSS snapshot is only a *time sample*, not a write-time proof. The same numeric handle might have been closed and reallocated to a different object between snapshots.
2. The documented PSS handle entry does **not** supply a matching ETW `FileObject` pointer. A handle's file name, file index or volume serial cannot be substituted for kernel object identity. Two snapshots do not close this gap.
3. An actual PSS call needs independently verified permission for the selected target process. PSS handle capture can have performance and privacy implications, even when process-scoped. The candidate gate therefore **does not implement a Windows adapter**, request privileges, alter ACLs, attach a debugger, probe memory, or scan the global handle table.
4. Any later observer must be explicitly constrained to disposable, source-verified WebView2 children with precise process birth/image provenance, bounded handle caps and timing, no foreign unrelated processes, no raw trace exports, no owner data, deterministic cleanup and fail-closed privilege/coverage errors. A separate generated-only PSS feasibility run may confirm whether the `File` TypeName is observable, but it would still not prove actual PilotODIN/WebView2 FileIO.
5. **Remaining gating evidence:** trustworthy original file-handle acquisition, same-object Kernel-File FileObject/FileKey correlation, unique IRP request/completion, request-time path/epoch, independently loss-reviewed full capture and restoration. None is provided by this source gate. Do not modify native acceptance or report 50%.

## Next minimal engineering step

Design and review a **mockable Windows PSS adapter** with explicit target-process ownership, exact capture flags and access rights, bounded walk and failure cleanup before requesting a new one-use generated-only native measurement. Independently validate the API's real file TypeName behavior. If no supported FileObject bridge can be established, retain **BLOCKED** rather than weakening original file-handle or physical-destination proof.

**Both native workflows remain disabled, no new one-use approval marker was created. G1 PASSED, G2 OPEN, four-gate delivery 25% (1/4); official R02.5 0/5, N12 0/2, P4 14/20 (70%).**
