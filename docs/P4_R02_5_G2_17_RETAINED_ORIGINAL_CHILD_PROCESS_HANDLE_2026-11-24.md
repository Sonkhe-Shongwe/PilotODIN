# PilotODIN R02.5 G2.17 | Retained original WebView2 process-handle admission

**24 November 2026 | SOURCE-ONLY VERIFIED. No actual WebView2 handle was opened by this step.**

## Source finding requiring a change

- The existing `qa/p4_research/n12_no_cdp_child_handles.py` observer retains original WebView2 descendant process handles for birth, image, exit and parent corroboration, but obtains them through `qa/p4_native/n12_lifetime_control.py::open_process_query_handle` with only `0x1000` (`PROCESS_QUERY_LIMITED_INFORMATION`).
- G2.16's `ScopedPssApiAdapter.collect_private_disk_candidates(pid,birth)` opens a **second process handle** with `0x1040` (`PROCESS_QUERY_LIMITED_INFORMATION | PROCESS_DUP_HANDLE`). Even with PID/birth/image agreement, this was not the previously retained original process handle.
- Windows [DuplicateHandle](https://learn.microsoft.com/en-us/windows/win32/api/handleapi/nf-handleapi-duplicatehandle) needs `PROCESS_DUP_HANDLE` access to the source process. The current 0x1000 observer handle is not eligible for this purpose. This is an actual **source-rights mismatch**, not proof that an original file handle or FileObject has been mapped.

## G2.17 implementation

- [Initial implementation `66d66bb`](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/66d66bbd902d357b7c05889cfac76c9b752d8ae3) adds `ScopedPssApiAdapter.collect_from_retained_original_process(process_handle,pid,birth,acquisition_rights)` to the **existing dormant** Win32 PSS adapter.
- It accepts a caller-owned, still-open original process HANDLE, never performs a new `OpenProcess(pid)`, verifies exactly `(PID, creation time, msedgewebview2.exe)` before and after bounded PSS snapshot + `DuplicateHandle` + `GetFileType`, and never closes or transfers ownership of the original process HANDLE. Snapshot, marker and **local** duplicates still undergo try/finally release.
- The `acquisition_rights` parameter accepts only exact `0x1040` and refuses existing 0x1000 query-only observer rights. **This declaration does not independently prove actual granted access or original provenance.** Win32 will enforce access at capture/duplication time. A separately approved observer capable of retaining an original 0x1040 handle still needs to be designed and verified.
- No private paths, process IDs, raw handles or OS exceptions are emitted as acceptance/public evidence. Returned `_PrivateDiskCandidates` are temporary type hypotheses only. This does **not** establish kernel original FileObject, issuing thread, IRP, write completion, physical path, or handle reuse exclusion.

## Actual source verification

- First exact-source [R02.5 CI #45306893241](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/45306893241) **FAILED** one new test expectation: a deliberately failing PSS marker cleanup prevented duplication as designed; the test wrongly assumed duplication would occur.
- Follow-up [`9f9a3b2`](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/9f9a3b223e0b5acc959e507a4d725b6baca18271) corrected that assertion to require **no duplicate attempt** on failed marker cleanup. [Exact-source FileIO source CI #45306971742](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/45306971742) **COMPLETED SUCCESS**, including the expanded injected original-handle tests and all existing FileIO source suites.
- The current N12 observer, all original FileIO reducers, all three consumed generated-only native G2.13/G2.14/G2.15 workflows, the user-data roots, network settings and installers remain unchanged and unactivated. No actual Windows WebView2 process was launched in G2.17.

## Next decisive engineering task

Specify a single-source, independently authorised acquisition of an original WebView2 descendant HANDLE **with proven necessary access** at the time of original process identification. Prevent a later PID reopen from being described as retained-original process evidence. Even that does **not** solve the separate original *file HANDLE* to ETW `FileObject`/`Irp` operation and physical-path join. Keep G2 blocked until the independent same-capture provenance, completeness, losses, request-time path and root containment are demonstrated.

**Before G2.17: 1/4 (25%); after G2.17: 1/4 (25%).** Official R02.5 **0/5**, N12 **0/2**, P4 **14/20 (70%)**, internal mutation engineering **3/4 (75%)**. P4 active; P5 not authorised; installer freeze unchanged.
