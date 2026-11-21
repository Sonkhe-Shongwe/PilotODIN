# PilotODIN P4 | Fail-closed, read-only no-CDP application log witness

**Date:** 21 November 2026  
**Status:** Code/test contract prepared; **not yet connected to a native no-CDP run**. No owner authorization to run a new native app capture.

## Evidence question and source context

The first approved focused WebView diagnostic included the netlog flag and observed two ambient browser temp creates. The second, [debug-only #44852642468](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/44852642468), omitted netlog and **still** observed two browser `.tmp` CreateFile events in user-temp during readiness, at two distinct normalized path strings. Both captures required CDP remote debugging; they did not prove default production behavior or complete file-operation coverage.

[Prior no-CDP design](./P4_N12_NO_CDP_CLOSE_READINESS_DESIGN_2026-11-21.md) placed a source-guarded command in the Tauri host. After the frontend actually registers the native close listener, an explicitly flagged, debug-build-only, separately consenting exact local QA page may ask Rust to write **one fixed line** on the app stderr stream:

`N12 QA native close listener registered`

The command cannot close a window and does not change the one-use Rust close-ticket veto.

## Current source-only implementation

[`qa/p4_research/n12_no_cdp_log_witness.py`](../qa/p4_research/n12_no_cdp_log_witness.py) at source [`31987555`](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/31987555da1815b4ef2a08785b4f3439aa95a3ea) implements a pure read-only observation path, backed by local disposable tests [`test_p4_n12_no_cdp_log_witness.py`](../tests/test_p4_n12_no_cdp_log_witness.py).

### Three states and contracts

1. **Prelaunch capture**: The future supervisor must present a *new, empty* `app.log`, before starting the QA desktop. The reader checks filename, non-symlink regular file, zero size, available file identity and exact caller-supplied 40-character source/64-character executable SHA256 values. It preserves only internal `st_dev`/`st_ino` identity and pinned digests. It never prints/serializes a private runner pathname. **Important:** the existing `journey.spawn` opens the log with `xb` when spawning. Wiring this requirement into a future no-CDP runner will require capturing the empty file identity between its exclusive creation and `Popen`. This has **not** been wired or activated.
2. **Bounded provisional observation**: The reader requires a positive, exact app PID supplied by the future supervisor, an independently checked **single main window identity** boolean, a live app process, and an unchanged log identity. It reads up to **256 KiB**, requires a complete exact fixed marker line, and times out within an explicitly bounded **45-second maximum**. A duplicate marker, exceeded bound, swapped log, missing line, exited app or missing identity fails with a fixed non-private error label. A single marker only produces a **provisional** `SeenReadiness`; it never authorizes WM_CLOSE.
3. **Post-close verification**: Only after a separate helper reports that the verified Windows main-window `CloseMainWindow` request succeeded and the same app process exits with code **0**, the reader rereads the same log identity and requires **exactly one total marker**. Missing or duplicated later marker remains blocked. The returned status is deliberately `no-cdp-app-close-log-witness-only`; `browser_process_identity`, `file_event_coverage` and `native_N12_acceptance` are always **NOT_EVALUATED**.

Synthetic tests cover valid/invalid source and binary digests, stale prelaunch markers, duplicates before and after close, missing and partial lines, timeout, private-log non-disclosure, file replacement/symlink, oversized logs, app death, PID mismatch, window mismatch and required normal close. **Test-created temporary logs are not a native PilotODIN run.**

## Honest limitations and stop rules

- The source/executable and process identity values are **caller-supplied**. The reader requires matching values but **cannot independently attest** executable hashes, real process parentage, main-window uniqueness, event origin or genuine Windows close delivery. Future source-pinned supervisor integration and separate Windows OS evidence are needed. A fixed log string is not a cryptographic attestation, and the position of that string alone cannot prove frontend event registration without the matching reviewed Rust/React source and live corroboration.
- The reader is not integrated into `qa/p4_research/n12_app_lifetime.py`, which still waits for CDP port 9331 and calls the CDP readiness driver. The old storage reducer still relies on `cdp_browser_pid`. The new log reader **cannot** replace this PID with a guess.
- The existing normal native `CloseRequested` veto, live-window identity/handle, one-use ticket resolution and zero-exit checks **must remain independently enforced**. The reader never calls `kill`, creates or destroys windows, changes paths, permissions or firewall rules, runs a collector or starts any app.
- No synthetic or future log-only result earns N12 acceptance; full N12 still requires complete FileIO observation and independent network testing. Existing ProcMon `exit 1`, unresolved file paths/named pipes and WebView2 non-loopback egress remain open.
- The approved `debug-only` native capture was one-use and **consumed**. All native N12 workflows remain disabled. No installer through P7.

## Next genuinely useful engineering micro-step

**Source-only:** Bind WebView2's browser identity to the exact QA app and disposable profile from OS process ancestry, launch/exit stamps and command-line/profile evidence, without CDP and without inferring that every WebView role is the browser. If zero or multiple credible browser candidates remain, return **BLOCKED**. Separately, propose a safe prelaunch-log descriptor/identity handshake for the future no-CDP runner and remove debugger-port 9331 assumptions without relaxing readiness or close checks. Only after those contracts, compile and test the new Rust guard in an isolated native QA process under **newly scoped, explicit owner consent**.

**Ledger unchanged:** P4 **14/20 (70%)**, file-mutation **3/4 (75%)**, desktop network **2/3 (67%)**, N12 **0/2**, original app-data preservation **0/2**. Governing full N12 filesystem FAIL, network FAIL and file-mutation coverage BLOCKED.
