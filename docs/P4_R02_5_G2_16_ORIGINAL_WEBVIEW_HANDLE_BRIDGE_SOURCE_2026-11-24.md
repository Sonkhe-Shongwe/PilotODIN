# PilotODIN P4 R02.5 | G2.16 dormant verified WebView2 handle-to-disk candidate bridge

**24 November 2026 | SOURCE INTEGRATION ONLY. No real WebView2 launch, original file-handle access or new native authorisation.**

## Why this is the next engineering step

- [Generated G2.14 Windows #45299036681](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/45299036681) observed a disposable PSS handle but not its `File` TypeName.
- [Generated G2.15 Windows #45300245828](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/45300245828) successfully duplicated one generated self-process file handle and observed `FILE_TYPE_DISK`, with independent source CI [#45300461556](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/45300461556) green.
- The remaining gap is **actual original WebView2 process identity plus source-handle classification**. The existing `n12_pss_win32_backend.py` already supports process-scoped `OpenProcess` identity (PID/birth/image) and complete bounded PSS walk, but had no real `DuplicateHandle`/ `GetFileType` bindings.

## Implemented G2.16 source bridge

Extend the **existing dormant** native PSS adapter with strict Win32 `DuplicateHandle` and `GetFileType` ABI bindings and close-on-success/failure of every duplicated **local** handle. It never sets `DUPLICATE_CLOSE_SOURCE`, never reads private file contents, requests paths/names, enumerates systemwide processes or changes source handles. The original process is opened with existing `PROCESS_QUERY_LIMITED_INFORMATION | PROCESS_DUP_HANDLE` only.

`ScopedPssApiAdapter.collect_private_disk_candidates(pid, birth)` holds one verified `msedgewebview2.exe` process handle, one complete process PSS snapshot and at most 256 rows, then classifies each original handle number through a short-lived local duplicate. Empty/unclassified GetFileType results are recorded as **unclassified**, never silently converted to disk. Malformed rows, duplicate numeric handles, incomplete table, process identity mismatch, failing Win32 operations or failed resource cleanup block the entire attempt. Successful return is a **private in-memory non-serializable handle list** (`_PrivateDiskCandidates`), not an N12 acceptance receipt or file-object proof. It is never passed to the existing strict N12 reducer or product.

The [Microsoft DuplicateHandle](https://learn.microsoft.com/en-us/windows/win32/api/handleapi/nf-handleapi-duplicatehandle) API requires source-process handle rights and can create a local duplicate with the same access. [GetFileType](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-getfiletype) classifies the duplicated handle, but even a disk-file observation does **not** authenticate the original handle's identity at a historical write. The original may have closed and the numeric value reused between snapshot and duplication. A caller must separately authenticate WebView2 ancestry, ETW process/handle lifetime and original FileObject/IRP/request-time path before G2 acceptance.

## Verification and permission boundary

Source-only unit tests inject a fake Win32 backend and enforce identity, bounds, complete walk, unknown/non-disk negatives, duplicate scope flags, failure cleanup, absence of name queries and privacy-safe public blocking. Existing Linux R02.5 source CI now watches and runs this test suite. The existing native G2.13, G2.14 and G2.15 workflows remain **DISARMED**, their approvals CONSUMED. The new method has **no new workflow entrypoint, consent activation or live caller**.

**Score:** G1–G4 **1/4 (25%)** (G2 still OPEN); official R02.5 **0/5**, N12 **0/2**, P4 **14/20 (70%)**, internal mutation preparation **3/4 (75%)**. P5 unauthorised. Installer freeze intact.

**Next bounded step:** use real source-based ETW write handle provenance to design the original file handle-to-FileObject/IRP/request-time canonical path join. Only after review and fresh exact-source one-use approval could a disposable hosted-Windows **real-app** capture test the integrated adapter. No evidence yet supports awarding any official R02.5 points.
