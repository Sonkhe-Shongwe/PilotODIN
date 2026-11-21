# PilotODIN 1.0 | P4-83 N12 read-only USN journal classification

**Date:** 14 November 2026  
**Branch:** `feature/live-dev-workspace-20261023`  
**Implementation source:** [`dc3b74202a10320da580a91a5f8ad8851936cc65`](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/dc3b74202a10320da580a91a5f8ad8851936cc65)  
**Disposition:** Scoped correction verified by exact-source hosted CI. N12 remains partial; global strict mutation coverage remains blocked.

## Finding

The previous exact-source N12 control run [#43557856495](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/43557856495) reported Kernel-File Event 23 `InfoClass=0x000900BB` as an unsupported mutation. Microsoft identifies this control code as `FSCTL_READ_USN_JOURNAL`, which retrieves USN change-journal records. It is a read-only query, not a mutation of the target file.

Reference: [Microsoft Win32 FSCTL_READ_USN_JOURNAL](https://learn.microsoft.com/en-us/windows/win32/api/winioctl/ni-winioctl-fsctl_read_usn_journal).

## Change

- Added the explicit `FSCTL_READ_USN_JOURNAL = 0x000900BB` constant and classified it as `query` in `qa/p4_native/n12_etw_correlate.py`.
- Added a regression with no rundown path to prove the read-only request does not become an unresolved mutation.
- Changed the unknown-FSCTL fixture to `0xDEADBEEF`, preserving the fail-closed unsupported-operation and missing-path assertions.
- Documented the narrow Event 23 allowlist in [`qa/p4_native/N12_TRACE.md`](../qa/p4_native/N12_TRACE.md). `FSCTL_SET_COMPRESSION (0x0009C040)` remains a mutation. Unrecognised FSCTL codes remain unsupported.

No application code, owner data, saved project, model, installed executable or installer was changed.

## Exact-source verification

| Evidence | Result |
| --- | --- |
| [Dedicated N12 Windows run #43563056277](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/43563056277) | **SUCCESS**; 50/50 focused tests |
| Native ProcessTrace rundown | 376/376 records decoded; TDH metadata, FileObject and FileName each succeeded 376/376; zero metadata failures, decoder conflicts, undecoded records or callback errors; ProcessTrace and CloseTrace status 0 |
| Strict reducer controls | **PASS**; both pre-opened keys recovered; protected write detected; outside write classified outside protected roots; zero unresolved control mutations |
| [Broader P4 CI #43563056278](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/43563056278) | **SUCCESS, all 3 jobs**; 235 Python tests, 78 Node checks, TypeScript/Vite build, 13 Chromium scenarios and hosted synthetic Windows preservation checks |
| Second hosted native rundown in P4 CI | 340/340 records decoded; both strict reducer controls passed |

The previous `0x000900BB` unresolved event family no longer appears in the new N12 diagnostics. The `0xDEADBEEF` regression remains unsupported and fail-closed.

## Remaining blockers

The strict reducer still reports `etw-mutation-coverage-unresolved`. The generated N12 run retains unrelated `protected:other:write` and `protected:other:resize` violations, plus unresolved `other` write requests, missing path/process lifetime context, allocate/resize/delete operations, unsupported FileInfoClass operations and `FSCTL_SET_COMPRESSION` path/lifetime uncertainty. In the dedicated run, compression diagnostics remained 573/573; the separate P4 Windows run retained 287/287. These are mutation or attribution gaps, not safe-to-ignore queries.

Do not suppress `other` actors, unknown FSCTLs, ambiguous FileKeys, missing process lifetimes or compression operations. Do not infer that a generated control PASS is a clean global audit.

## Acceptance boundary

- P4 remains **ACTIVE**; R02/N12 remains **PARTIAL**.
- R03 physical offline 8 GB coexistence remains **NOT TESTED**.
- R06 historical original app-data integrity remains **STRICT FAIL**, with 74 file differences and historical writer **UNKNOWN**.
- Gate C remains **UNVERIFIED** before any specific real-world prediction use.
- P5 remains **NOT AUTHORISED**; P8 remains **NOT CERTIFIED**.
- No live combined Sysmon/ETW calibration, Sysmon provisioning, full PilotODIN startup-to-exit trace, desktop application build, installer, owner-device operation, original-data access or model training occurred in this increment.

## Next justified action

Continue investigating the remaining unrelated `other` actor event families using redacted event-type and process-identity diagnostics on disposable hosted fixtures. Preserve raw paths and identifiers in runner-private temporary storage. Do not weaken strict coverage, re-arm the disabled combined workflow, infer application attribution, or claim N12 acceptance until the remaining mutation and attribution evidence is complete.
