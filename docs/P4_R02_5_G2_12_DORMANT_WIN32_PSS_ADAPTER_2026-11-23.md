# PilotODIN R02.5 G2.12 | Dormant Windows PSS source adapter

**23 November 2026 | SOURCE-ONLY. No Windows API invoked; no native capture approved.**

## Implemented

- `qa/p4_research/n12_pss_win32_backend.py` exposes a Win32 ctypes ABI for `OpenProcess`, `GetProcessId`, `GetProcessTimes`, `QueryFullProcessImageNameW`, `PssCaptureSnapshot`, `PssWalkMarkerCreate`, `PssWalkSnapshot`, `PssWalkMarkerFree`, `PssFreeSnapshot`, and `CloseHandle`.
- Entry point `prepare_native_backend` refuses unless hosted Windows, first-attempt trusted push, exact reviewed SHA and a **new**, explicitly named PSS one-use consent are present. No existing workflow supplies this consent or imports/activates the adapter.
- A caller must supply a single exact WebView2 PID and original process birth FILETIME. The adapter rechecks process ID, birth and image basename before sampling, with no system-wide enumeration.
- Captures only `PSS_CAPTURE_HANDLES | PSS_CAPTURE_HANDLE_BASIC_INFORMATION` (0x14); no object-name capture, VA clone, traces, type-specific or thread capture. Uses `PSS_WALK_HANDLES` with an explicit maximum of 256 rows, querying the 257th to reject silent truncation.
- Returns handle/type metadata privately and frees walk markers, PSS snapshots and process handles in finally/context paths. The public blocker interface emits fixed labels, never names, paths, PIDs, handle values or raw API errors.
- `tests/test_p4_n12_g2_12_pss_win32_backend.py` tests scope refusal, ABI constants, exact PID/birth/image gate, overflow, malformed rows, cleanup and public redaction through mock API. Routine FileIO source-only CI includes the test and syntax check.

## Limits: no native credit

This is *not* a demonstrated WebView2 original-file-handle observation, does not authenticate file-handle ownership at the exact write request, cannot exclude handle reuse, and does not supply Kernel-File `FileObject` or a request-time physical path. PSS `CaptureTime` and sampling wall time are not a proven exact FileObject bridge. TypeName `File` availability with flags 0x14 remains unverified on Windows. Real privileges, actual C-ABI layout and target impact require a separate generated-only Windows check before any product capture.

There is **no** explicit one-use owner authorization to execute this live API. The older N12 native workflows remain disabled. No installer, owner PC, private paths, firewall, ACL or protected originals are touched.

**Scoring:** G1 1/4 (25%); G2 open. Official R02.5 0/5 and P4 14/20 (70%) remain unchanged.

Microsoft API contract: https://learn.microsoft.com/en-us/windows/win32/api/processsnapshot/nf-processsnapshot-psscapturesnapshot and https://learn.microsoft.com/en-us/windows/win32/api/processsnapshot/ns-processsnapshot-pss_handle_entry.
