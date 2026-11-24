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
