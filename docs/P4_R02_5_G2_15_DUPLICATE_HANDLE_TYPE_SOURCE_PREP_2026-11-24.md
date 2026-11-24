# PilotODIN R02.5 | G2.15 process-scoped handle-type candidate

**24 November 2026 | SOURCE-ONLY prepared, native generated probe DISARMED.**

## Why the mechanism changed

Actual one-use hosted Windows [G2.14 #45299036681](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/45299036681) completed a bounded PSS walk but returned `G213_GENERATED_FILE_TYPE_UNAVAILABLE`. Therefore PSS TypeName cannot supply a verified `File` classification using the tested flags. The original G2.13/G2.14 approvals remain consumed and the workflows disarmed.

Microsoft [DuplicateHandle](https://learn.microsoft.com/en-us/windows/win32/api/handleapi/nf-handleapi-duplicatehandle) can duplicate a source handle into the calling process, and [GetFileType](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-getfiletype) returns disk, character, pipe or unknown. Unknown is never accepted, irrespective of GetLastError. **Disk means type only; it is not original FileObject identity, writer attribution, request completion or path verification.**

## Exact implementation and safe limits

- `qa/p4_research/n12_duplicate_handle_type.py`: an injected, non-Windows-only candidate checker that requires independently verified original WebView2 process PID/birth/image and complete bounded PSS handle inventory (1 to 256), then verifies mock-scoped duplication and disk-type classification, guaranteeing duplicate and process cleanup and blocking unknown, API failure, invalid identity and partial/incomplete tables. All receipts redact handle, PID, path and OS errors, and keep `native_N12_acceptance=NOT_EVALUATED`.
- `tests/test_p4_n12_g2_15_duplicate_handle_type.py`: injected regression for identity mismatch, stale/lost witness, missing File type, duplicate failure, cleanup failure, overflow/duplicates and nonacceptance. No actual process/system calls.
- `qa/p4_native/g215_generated_duplicate_type.cpp`: Windows x64 **generated self-process only** source, one disposable delete-on-close file under verified runner temp, exactly one `DuplicateHandle` and `GetFileType`, fixed-label stdout and unconditional handle cleanup. It never opens another process, consults file names or inspects private data.
- `.github/workflows/p4-r025-g215-generated-duplicate-type.yml`: **DISARMED** one-use native generated probe; requires fresh exact source SHA, direct-parent activation changing only its workflow and a **distinct absent new marker** `qa/p4_research/N12_G215_GENERATED_DUPLICATE_OWNER_APPROVAL_FRESH_ONE_USE.txt`. No manual dispatch, no installer, no raw trace.
- R02.5 source-only CI watches the G2.15 files and verifies both synthetic decisions and source safety before *any* distinct one-use activation. Until an exact-source SUCCESS, nothing is credited as source-verified.

## Remaining decisive acceptance gap

The generated probe, even if later executed successfully, does **not** identify an original WebView2 writer. Full G2 requires separately authorised real-app original process/file-handle provenance, ETW FileObject/IRP request/completion path, physical destination, complete process lifetimes and calibrated loss review. G3 fixes observed product writes; G4 requires an independent complete strict pass.

**Scores unchanged:** R02.5 0/5; N12 0/2; P4 14/20 (70%); file-mutation engineering 3/4 (75%); remaining G1-G4 delivery 1/4 (25%). Intermediate installer freeze retained; P5 not authorised.

## G2.15 actual hosted Windows result and consumed approval | 24 November 2026

[Exact first-attempt generated-only Windows G2.15 #45300245828](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/45300245828) **SUCCESS** with `G215_GENERATED_DISK_TYPE_PRESENT`. The fresh reviewed-source approval was consumed at activation `1975e71be4e0335966f7b421a426d0b1877d1b60` and the workflow immediately disarmed in `6b2aeba57ee70214bbc019165d45b1568233c4e5`; source-only tests updated to enforce this historical state. This positive result is **generated self-process only** and does not prove real WebView2 original handle provenance, FileObject/IRP association or storage root containment. [Full evidence review](./P4_R02_5_G2_15_GENERATED_DUPLICATE_TYPE_WINDOWS_RESULT_2026-11-24.md). Official R02.5 0/5, P4 14/20, G1-G4 1/4 unchanged.
