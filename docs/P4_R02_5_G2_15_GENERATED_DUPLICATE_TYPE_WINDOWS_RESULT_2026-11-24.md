# PilotODIN R02.5 | G2.15 real hosted-Windows generated duplicated-handle type result

**24 November 2026 | One-use generated-only Windows probe COMPLETED SUCCESS, positive disk-type observation. Not native PilotODIN/FileIO acceptance.**

## Provenance and actual evidence

- Exact reviewed source: [`f3962d21ab739f0d217457213e8809c82034a4e8`](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/f3962d21ab739f0d217457213e8809c82034a4e8), with the injected process-scoped G2.15 candidate module, negative tests and generated-only C++ API probe. [Source contracts #45300114224](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/45300114224) **COMPLETED SUCCESS** at this source.
- Fresh owner-scoped one-use activation: [`1975e71be4e0335966f7b421a426d0b1877d1b60`](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/1975e71be4e0335966f7b421a426d0b1877d1b60), a **direct child of reviewed source**, changed exactly (1) `.github/workflows/p4-r025-g215-generated-duplicate-type.yml` and (2) new two-line `qa/p4_research/N12_G215_GENERATED_DUPLICATE_OWNER_APPROVAL_FRESH_ONE_USE.txt` with `scope=g215-one-generated-self-process-duplicate-type`.
- Immediate workflow disarm: [`6b2aeba57ee70214bbc019165d45b1568233c4e5`](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/6b2aeba57ee70214bbc019165d45b1568233c4e5) changed **only** the native workflow to `if: ${{ false }}` and retained the new marker PRESENT AND CONSUMED. No retry, no reuse of G2.13/G2.14 markers.
- Real hosted Windows 2022 [Actions run #45300245828](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/45300245828) at activation SHA, **COMPLETED SUCCESS**, first attempt. Source/host/consent and two-file activation guards PASSED; MSVC x64 compilation and link PASSED. A generated self-process executable opened one delete-on-close fixture under verified disposable `RUNNER_TEMP`, called `DuplicateHandle` into the same process and `GetFileType` on the duplicated local handle. Its exact fixed-label output:
  `g2_15=G215_GENERATED_DISK_TYPE_PRESENT`
  C++ scope does not enumerate processes, query paths/names, read file contents, make app network requests or launch PilotODIN/WebView2. The return code and workflow were successful only after the probe's checked handle/fixture cleanup; generated EXE cleanup was in a PowerShell `finally` block.
- The source-only [disarmed-head run #45300250991](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/45300250991) **FAILED only** the historical source test asserting the previously absent marker remains absent after consumption. The source-test correction in the next commit now requires the exact retained marker, consumed activation SHA and `if: false`; it does not alter the native job or reauthorise its execution. Do not describe the historical failed run as passed.

## What is proved

The Win32 `DuplicateHandle` plus `GetFileType` approach produced a positive **FILE_TYPE_DISK** classification for one owned, generated file handle on actual hosted Windows, without PSS TypeName or filesystem path discovery. This is an independent API feasibility result and supersedes the `G213_GENERATED_FILE_TYPE_UNAVAILABLE` result **only for the new generated duplicated-handle method**. It does not imply that WebView2 uses the same handle rights or lifetimes.

## What remains open

No original WebView2 process handle was opened, no original browser file handle was duplicated, no original handle-to-FileObject/IRP mutation join, request/completion writer or canonical physical destination was verified. There was no full-app N12 ETW/Sysmon/ProcMon audit, complete loss/path coverage, original-owner data check, WebView2 UDF verification or product-side storage correction. The historical strict filesystem FAIL, network FAIL and mutation coverage BLOCKED all persist. The injected Python G2.15 classifier remains synthetic-only; live integration requires a separate reviewed and specifically authorised guarded capture.

The next decisive engineering step is a source-reviewed **single verified original WebView2 process scoped duplicator** that holds an independently authenticated process handle, uses only a bounded original PSS handle-table candidate list, classifies with `GetFileType` without filenames, releases every duplicate and refuses PID/birth/image mismatch. It still must be joined to original independent ETW FileObject/IRP/request-time path evidence before G2 or R02.5 acceptance. A separate fresh one-use owner decision is required before any real app run or private original-handle operation.

**Official scores unchanged:** R02.5 **0/5**, N12 **0/2**, P4 **14/20 (70%)**. Internal file-mutation preparation **3/4 (75%)**, four-gate G1-G4 delivery **1/4 (25%)**. P4 active, P5 not authorised and intermediate installer freeze remains.
