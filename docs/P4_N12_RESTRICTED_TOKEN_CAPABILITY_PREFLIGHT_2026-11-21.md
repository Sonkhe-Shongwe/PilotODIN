# PilotODIN P4 | Restricted-token API capability preflight

**21 November 2026** | **Scope:** read-only Windows export lookup and synthetic failure tests, not N12 acceptance or authorization for a restricted process.

## What was implemented

At source [`839c2e1f`](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/839c2e1fbf398584c764d5601086d390ae0f4f9f), `qa/p4_research/n12_token_capability_preflight.py` reads the Win32 API surface without invoking any of the resolved exports. On Windows it uses Python `ctypes.WinDLL` to resolve the following exact names:

| Windows library | Exports checked |
| --- | --- |
| `advapi32.dll` | `OpenProcessToken`, `CreateRestrictedToken`, `DuplicateTokenEx`, `GetTokenInformation`, `IsTokenRestricted`, `AccessCheck`, `GetNamedSecurityInfoW`, `CreateProcessAsUserW` |
| `kernel32.dll` | `GetCurrentProcess`, `CloseHandle` |

Outside Windows it reports `windows-host-required`. Any load or symbol-resolution failure returns a fixed `BLOCKED` reason; raw loader exceptions and host paths are never published. `PRESENT` means **ten symbols were resolved, nothing more**. The implementation deliberately never calls the resolved exports; it does not open a token, modify privileges, create an account, launch a process, read an ACL, create files, apply permissions or run PilotODIN. `native_N12_acceptance` remains `NOT_EVALUATED`, `api_evidence_proves_security` remains `false` and `owner_native_execution_authorized` remains `false` in all results.

Routine Windows CI may exercise existing unrelated generated ETW and browser fixtures. This new preflight step itself is strictly a DLL/export availability check. `tests/test_p4_n12_token_capability_preflight.py` mocks API exports and verifies that **none of their functions is invoked**, even for a clean synthetic result.

## Exact-source Windows verification

[Routine P4 CI #44850133377](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/44850133377) passed **all four jobs** at exact source [`839c2e1f`](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/839c2e1fbf398584c764d5601086d390ae0f4f9f). Linux source job: **804 Python tests passed, 6 skipped, 300 subtests**; frontend **103 passes** plus Vite. Disposable browser: **13 passed**. Hosted Windows R03: **4 passed**. The Windows preservation/ETW fixture ran **6/6 new token-capability unit cases** and the actual *read-only* export lookup returned **`api_surface_status: PRESENT`, `exports_observed: 10`, `exports_expected: 10`**. It also returned **`native_token_created: false`, `acl_modified: false`, `file_access_attempted: false`, `file_protection_verified: false`** and **`native_N12_acceptance: NOT_EVALUATED`**. The result establishes API-symbol availability on that hosted Windows runner and nothing about restricted-token enforcement.

## Token and access facts required in a later, explicitly approved test

1. Prove a real restricted **primary token** for the generated writer by querying `TokenType`, `TokenGroups`, `TokenRestrictedSids`, `TokenPrivileges` and `TokenOwner`. In particular, verify a nonempty restricting SID list and Administrators enabled only for denial, with all relevant takeover and bypass privileges absent. `IsTokenRestricted` alone cannot prove these conditions.
2. Use a trusted supervisor to verify protected object ownership and effective DACL rights independently of the writer's own success/failure labels. `AccessCheck` accepts an **impersonation token**, whereas `CreateProcessAsUserW` needs a suitable **primary token**. Future code must manage both token types deliberately and verify resulting process identity. The read-only export probe does neither.
3. Explicitly account for `SeIncreaseQuotaPrivilege` requirements when using `CreateProcessAsUserW`, as well as the special `SeAssignPrimaryTokenPrivilege` exception for a restricted version of the caller's token. Unsupported privileges or process creation must **BLOCK**, never silently fall back to the administrative runner.
4. Verify `SeTakeOwnershipPrivilege`, `SeRestorePrivilege`, `SeBackupPrivilege`, `SeSecurityPrivilege`, `SeDebugPrivilege` and `SeImpersonatePrivilege` are not available for bypass in the generated writer; check ownership, `WRITE_DAC`, `WRITE_OWNER`, delete/rename/overwrite/truncate rights and the positive permitted control. Token presence is not an access decision.
5. Consider Microsoft's restricted-token warning about messaging to unrestricted applications on the default desktop. The proposed generated writer should be headless and independently isolated before any interactive use is contemplated.

Microsoft documentation: [Restricted tokens](https://learn.microsoft.com/en-us/windows/win32/secauthz/restricted-tokens), [CreateRestrictedToken](https://learn.microsoft.com/en-us/windows/win32/api/securitybaseapi/nf-securitybaseapi-createrestrictedtoken), [CreateProcessAsUserW](https://learn.microsoft.com/en-us/windows/win32/api/processthreadsapi/nf-processthreadsapi-createprocessasuserw), [AccessCheck](https://learn.microsoft.com/en-us/windows/win32/api/securitybaseapi/nf-securitybaseapi-accesscheck), [GetTokenInformation](https://learn.microsoft.com/en-us/windows/win32/api/securitybaseapi/nf-securitybaseapi-gettokeninformation).

## Critical separation between a test fixture and the product

A successful generated-writer isolation control would demonstrate a deliberately protected **test directory**, **not** that the PilotODIN app or its WebView2 subprocesses are confined to permitted folders. The application still does not use the proposed generated restricted writer, and earlier WebView2 outside-profile creates remain measured facts. Do not infer that Windows restricted tokens generally force all child storage into an application profile. A future product-specific design must verify actual process ancestry/token propagation and explain the deployment mechanism before making claims about PilotODIN isolation.

## Stop rules and next decision

- Do not use `PRESENT` to award P4, N12 or R02.5 evidence points.
- No owner-device access, original data, ACL updates, token creation, test-writer execution, installer or new native WebView capture is approved by this change.
- Do not bypass missing functions, OS/privilege limitations or the existing file-mutation coverage requirements.
- If the Windows export lookup is positive, the **next source-only decision** is whether this mechanism can realistically apply to the actual Tauri/WebView2/backend process tree; separately approve a protected-folder control only after that integration review shows it would answer an application-relevant question.

**Unchanged:** P4 14/20 (70%); file-mutation 3/4 (75%); N12 0/2; governing filesystem FAIL, network FAIL, mutation coverage BLOCKED; R06 historical protected-data issue open. One-use native WebView workflow remains disarmed.
