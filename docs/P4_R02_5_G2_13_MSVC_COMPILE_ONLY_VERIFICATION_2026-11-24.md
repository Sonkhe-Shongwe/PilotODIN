# R02.5 G2.13 | Windows MSVC compile-only ABI verification

**24 November 2026 | Ordinary source-only Windows compiler check. No native PSS execution approved or performed by this addition.**

## Reason
First one-use generated-only Windows PSS attempt [#45272822119](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/45272822119) failed at C2664, because `PssCaptureSnapshot` expected `PSS_CAPTURE_FLAGS` rather than `const DWORD`. The owner-approved single-use consent was consumed and the activation permanently disarmed. The correction at [`b62f0df`](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/b62f0dfa3df77e22c73df4bb02852cf14f94644b) adds an explicit cast and restores source-test contracts; [source-only CI #45273365424](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/45273365424) passed. That does **not** prove the C++ compiles on Windows.

## New bounded implementation
- `.github/workflows/p4-r025-g213-msvc-compile-only.yml` creates one first-attempt Windows 2022 source-only job, triggered only by changes to itself, the generated PSS C++ source or static contract.
- It verifies the checkout SHA, expected branch, GitHub-hosted runner and first attempt, then uses Visual Studio x64 MSVC to **compile only** with `cl /c`, `/W4 /WX` and an OBJ output under a unique child of `RUNNER_TEMP`. The temporary OBJ and directory are removed in a `finally` block. It does not link or launch anything.
- No native PSS capture, ETW/Sysmon/ProcMon, Tauri/WebView2 app, owner original files, CI artifact, installer, live network probe, workflow activation, new one-use marker or root-policy change.
- `tests/test_p4_n12_g2_13_source_contract.py` now includes a negative source guard asserting compile-only scope.
- Existing one-use G2.13 workflow **remains disabled**, with consumed approval marker retained and exact historical native failure documented.

## Acceptance and next decision
Only count Windows MSVC ABI compilation as verified **after** the new exact-source Windows run completes SUCCESS. Even if green, the live PSS generated File TypeName remains **NOT_MEASURED**. A separately authorised future generated-only runtime check or real-app capture requires a distinct source-pinned one-use owner decision. G2 original WebView2 handle/FileObject/IRP/physical-destination evidence remains **BLOCKED**.

**Before/after official score:** P4 **14/20**, R02.5 **0/5**, N12 **0/2**, file mutation engineering **3/4**, four-gate R02.5 delivery **1/4**. This is source/compile engineering only; no native acceptance point.

## Exact-source Windows CI verification: 24 November 2026

- [Windows MSVC compile-only run #45297206223](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/45297206223) at source [`15506fe1a5e462a73d5c007797a764bcdb0d3a5c`](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/15506fe1a5e462a73d5c007797a764bcdb0d3a5c): **COMPLETED SUCCESS, attempt 1**. Hosted Windows 2022, source and runner gates passed, Visual Studio 2022 x64 vcvars initialised, and `cl /nologo /c /std:c++17 /W4 /WX` compiled the corrected `g213_generated_pss_probe.cpp` to a disposable `g213_pss_abi.obj`. The workflow verified object existence and deleted its dedicated RUNNER_TEMP scratch directory. No compiler error or C2664. This is SDK compile/API/ABI evidence **only**.
- [FileIO source-contract run #45297206275](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/45297206275): **COMPLETED SUCCESS, attempt 1** at the identical SHA. Preceding broad P4 regression [#45273365418](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/45273365418) also completed SUCCESS for earlier corrected-source SHA `b62f0df`.
- **NOT TESTED:** linking, executing the generated probe, PSS handle walking or TypeName presence/absence; original WebView2 file handles, ETW FileObject/IRP paths, effective UDF, actual prohibited-write mechanism, loss completeness or strict N12. The one-use G2.13 workflow remained `if: false`, approval marker already consumed, no permission reuse. Future generated-only PSS runtime and product native captures require *separately scoped new owner approval and exact source pin*.
- **Official and delivery scores do not change:** R02.5 0/5, P4 14/20, N12 0/2, original mutation engineering 3/4, four-gate 1/4. P4 remains active; P5 prohibited; installer freeze retained.
