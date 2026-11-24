# PilotODIN R02.5 G2.18 | Original WebView2 socket-safe PSS correction

**24 November 2026 | SOURCE-ONLY SAFETY FIX. No native WebView2 process accessed, no new one-use authorisation, no installer.**

## Source-verified API limitation

The source-positive G2.16/G2.17 `ScopedPssApiAdapter` previously walked every bounded PSS handle number and called `DuplicateHandle` on it, then `GetFileType`. This could duplicate arbitrary WebView2 sockets or other objects before classifying them, so a later `FILE_TYPE_DISK` result cannot make the **earlier duplication safe**. The full-app G2 test was never executed.

Microsoft [DuplicateHandle](https://learn.microsoft.com/en-us/windows/win32/api/handleapi/nf-handleapi-duplicatehandle) explicitly warns that using it on sockets interferes with their internal reference counting and advises `WSADuplicateSocket` instead. [PSS_OBJECT_TYPE](https://learn.microsoft.com/en-us/windows/win32/api/processsnapshot/ne-processsnapshot-pss_object_type) only enumerates UNKNOWN, PROCESS, THREAD, MUTANT, EVENT, SECTION and SEMAPHORE: it **does not provide a distinct regular disk-file-versus-socket enum**. Microsoft [Socket Handles](https://learn.microsoft.com/en-us/windows/win32/winsock/socket-handles-2) says Winsock handles can be Installable File System (IFS) file handles. Even a PSS TypeName of `File` is therefore **not adequate proof of a regular disk file**. The minimal PSS flags 0x14 in actual generated Windows [G2.14 #45299036681](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/45299036681) also failed to classify its own file as `File`.

## Implemented correction

- The two dormant original WebView2 candidate entrypoints `collect_private_disk_candidates(pid,birth)` and `collect_from_retained_original_process(process_handle,pid,birth,acquisition_rights)` now fail **before any process open, PSS capture or duplication**, returning the fixed error `PSS_SOCKET_UNSAFE_DUPLICATION_BLOCKED`. Invalid retained-handle/rights inputs are refused separately.
- The original-WebView2 `_Win32PssApi` removes its `DuplicateHandle` and `GetFileType` bindings and unsafe wrapper methods. The separately tested [G2.15 generated fixture-only Windows #45300245828](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/45300245828) remains intact as proof only for its explicitly created self-process disposable disk file.
- `inspect_private_pss_type_availability(snapshot)` is a **passive and bounded** type-availability summary, accepting an already authorized PSS snapshot and returning only counts of untyped, ambiguous File-or-socket and known-other handles. It performs **zero handle duplication**, exposes no handle identifiers or filenames, does not claim disk-file classification, and cannot award writer/path acceptance. Its tests include the actual G2.14 untyped shape and a typed `File` which remains ambiguous.
- Existing N12 original WebView2 observer remains **0x1000 query-only**, avoiding unnecessary `PROCESS_DUP_HANDLE` access escalation. The G2.17 retained process handle route and its historical exact-source tests stay in the audit as a *superseded* safety-unreviewed candidate, not an approved live operation.
- G2.18 source regression tests ensure both former entrypoints remain blocked, no original-WebView duplicate Win32 binding exists, type availability is a count-only private object, malformed/over-limit rows fail closed and PSS cleanup is retained. New source CI must pass at exact SHA before labeling verified.

## What can prove actual product writes instead

The existing `n12_etw_correlate.py`, `n12_fileio_pair_contract.py` and strict `n12_trace.py` provide independent FileIO IRP/FileObject/operation/path semantics without duplicating untrusted sockets. Next design should favor **passive, complete independently loss-reviewed ETW FileIO writer/process/window evidence** and a separately trustworthy original-file-object witness. Original file HANDLE provenance remains **unproven**. Do not infer it from PSS handle value, `GetFileType`, FileKey/volume serial, matching filenames, or a reconstructed PID.

Any new original WebView2 observation requires a fresh, separately scoped, first-attempt, exact-source one-use owner approval and must not access original user files or produce an installer. Do not reenable G2.13, G2.14, G2.15 or previous consumed native scopes.

**Scores unchanged:** P4 **14/20 (70%)**; official R02.5 **0/5**; N12 **0/2**; G1–G4 **1/4 (25%)**; internal mutation preparation **3/4 (75%)**. Historical filesystem FAIL, network FAIL, mutation coverage BLOCKED remain governing.

## Exact-source regression completion | 24 November 2026

[G2.18 source commit `1ae6229`](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/1ae62299b8e1abbea1024f8973fca11a8f3db81f) passed [FileIO source-only CI #45331514180](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/45331514180) **COMPLETED SUCCESS**. The new tests show previous WebView2 entrypoints refuse before any native operation, all foreign-process duplication bindings removed, count-only PSS summaries for untyped and `File`-ambiguous rows, no private handles or path output, unchanged query-only observer and disarmed generated-only Windows workflow. Historical G2.16 and G2.17 positive injected-source tests have been superseded by the new safety correction and **must not be cited as permission to enable native arbitrary WebView2 duplication**. No live original WebView2 process has been captured. Official G2/R02.5 acceptance remains blocked.
