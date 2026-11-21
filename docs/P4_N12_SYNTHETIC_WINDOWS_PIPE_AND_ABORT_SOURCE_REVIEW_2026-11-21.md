# P4 N12 | Real Windows synthetic AF_PIPE and interrupted-child cleanup

**21 November 2026 | SOURCE-ONLY CHECKPOINT COMPLETE, native Stage 1 BLOCKED.**

- **Tested code**: [`0511aca1e192ff4aa0950ac1255dcbd1b887b8f2`](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/0511aca1e192ff4aa0950ac1255dcbd1b887b8f2).
- **Exact-source CI**: [GitHub Actions #44903523887](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/44903523887), **4/4 SUCCESS**. P4 focused synthetic/backend/frontend job reported **970 Python tests passed, 6 skipped, 417 subtests passed, 104 frontend Node tests passed and Vite build passed**. Windows synthetic collector, R03 Windows, and disposable real-HTTP browser jobs also passed.
- **Actual Windows AF_PIPE tested in an isolated synthetic subprocess**; **no PilotODIN Tauri/native application, real WebView2 process, installer, Sysmon instrumentation, N12 FileIO/network acceptance test, firewall change or owner-PC operation** was run. Native lifetime workflow remains **`if: false`** and its one-use approval marker remains absent.

## What is now tested

New `tests/test_p4_n12_private_child_pipe_windows.py` runs explicitly on the existing hosted-Windows **synthetic-only** workflow, after Python setup. It uses a fresh `\\.\pipe\pilotodin-n12-child-...` endpoint and a separate short-lived **Python subprocess** with synthetic, fixed-schema process-handle evidence. The Windows `AF_PIPE` step passed four cases: **authenticated valid message**, **malformed private message rejected**, **wrong authentication key rejected**, and **worker exits before sending with no witness granted**. This verifies the real Windows named-pipe transport code without running PilotODIN. The source-only AF_UNIX test remains a separate synthetic portability case.

## Abort and early-child safeguards

The default-off `ScopedQaChildHandleObserver` now:
1. Takes a **synchronous first descendant sample** before starting its 10-ms polling thread, to reduce startup gaps. The source-level recorded sampling start timestamp is taken **before** observer activation. A child that appears and disappears between snapshots is **not credited**: independent Sysmon/ETW GUID completeness plus unique retained original-handle joins must reveal the missing witness, making the shadow review **BLOCKED**.
2. Exposes idempotent `abort()` to stop the watcher, attempt a bounded thread join, close retained original Windows query handles, clear any partial witness inventory and record fixed `observer-interrupted` as **BLOCKED**.
3. Registers `abort` with a scoped `ExitStack` **before** `start_live`. Readiness, startup or close exceptions unwind the guard and release handles. An ordinary completed `finish()` closes originals and renders this later callback a no-op. `finish()` also uses a bounded join and refuses incomplete thread shutdown rather than hanging as a successful witness.

New synthetic negative fixtures verify actual injected handle cleanup/zero credited witnesses on abort, impossibility of crediting a short-lived child missed between snapshots, worker `start_live` and readiness exceptions invoking `abort`, and forbidden propagation of pipe credentials or separate child-handle consent into the app environment. They do not assert that 10-ms polling becomes lossless.

## Scope and interpretation

The **real last approved** no-CDP native [Stage 1 #44893498723](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/44893498723) still returned strict **BLOCKED** because Sysmon Event ID 5 `UtcTime` and the ETW process-provider `ExitTime` differ (launcher +3.2932 ms, app +7.7625 ms, seven WebView child exit discrepancies). The original strict `EtwLifetimes.find()`, full OS-profile verifier and N12 FileIO/network acceptance checks are **unchanged** by this work. The optional private-child observer and authenticated worker-to-reducer channel are **default-off**, require distinct fresh source-pinned GitHub-hosted Windows one-use consent, and produce at most `REVIEWABLE_ONLY` diagnostics, never native acceptance.

A 10-ms snapshot observer may still miss short-lived WebView2 children. Explicit original-handle completeness against independently collected Sysmon GUID/ETW sequences is mandatory; no missing witness may be guessed. A bounded abort also cannot guarantee immediate release of an in-flight unresponsive Win32 query: any such timeout is recorded as an observer fault, never evidence of success. A future native one-use test must separately establish complete child capture, not merely trust synthetic green CI.

## Continuation

**Next decision boundary:** review whether the current strict source-only negative coverage and independent child-handle completeness are sufficient to prepare an **explicitly owner-approved, one-use, source-pinned, disposable GitHub-hosted Windows native Stage 1 diagnostic**. Do not arm native workflows or infer permission from a general `okay next`. If approval is not granted, continue only with source-only instrumentation or principled independent process-clock analysis. **No Stage 2 FileIO/network, installer, owner PC, protected data or firewall testing was authorized by this checkpoint.**

**Scores unchanged:** official P4 **14/20 (70%)**; internal file-mutation tracker **3/4 (75%)**; R02.5 **0/5**; N12 **0/2**; desktop network isolation **2/3**. Prior full N12 run #44838416004 remains filesystem **FAIL**, network **FAIL**, FileIO coverage **BLOCKED**.
