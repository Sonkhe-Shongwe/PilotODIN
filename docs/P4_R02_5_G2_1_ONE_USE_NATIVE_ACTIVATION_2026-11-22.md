# PilotODIN P4 R02.5 | G2.1 one-use Windows baseline activation

**22 November 2026.** Record of an explicitly owner-approved one-use native action, not a native acceptance pass.

## Exact source and GitHub provenance

- Approved reviewed source: [`166dfa39efa6a1629c35cc4c2c6c3fc740078c3c`](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/166dfa39efa6a1629c35cc4c2c6c3fc740078c3c).
- Approved activation: [`58f72bf3e226b2a1d87ab11a6fe3727f424268b4`](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/58f72bf3e226b2a1d87ab11a6fe3727f424268b4). Diff: one previously disarmed workflow modified and one fresh marker added, direct child of reviewed source. The historical consumed marker was not modified.
- Triggered exactly one first-attempt GitHub-hosted Windows workflow: [#45041259808](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/45041259808), source HEAD pinned to activation commit; checkout detaches to the reviewed source after checking the direct-child marker and exact changed-file set.
- Immediate workflow re-disarm: [`5a4c14d7cfa8f9af003ef22c19b55ab43488d5b0`](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/5a4c14d7cfa8f9af003ef22c19b55ab43488d5b0). The only change is returning the guarded job to `if: ${{ false }}`; it does not cancel or retry the already pinned run.

## Evidence and restrictions

At the last 2026-11-22 16:00 UTC check, native run #45041259808 was **IN PROGRESS**, with exact-source owner guard completed and dependency preflight active. No completed build, TCP/UDP calibration, real app launch or FileIO conclusion was verified at that checkpoint. Run completion and fixed-label redacted summary remain to be assessed without downloading raw native traces or private job logs.

Approved scope was one isolated unpackaged QA build, temporary Sysmon and Kernel FileIO ETW, first generated TCP and UDP calibration before any app launch, at most one no-CDP app journey, original child **process** handle observation, same-capture write/restore control, private runner-only evidence and cleanup. No external firewall block was promised; WebView2 may make outbound connections. No installer, local owner dataset, protected owner paths, expanded file-handle collection, filesystem policy change, raw trace upload, automatic retry or full native acceptance was authorised.

If initial calibration fails, application launch must not occur. A failed or incomplete diagnostic still consumes this one-use approval. Even a complete diagnostic does not prove original **file** handle to FileObject/IRP attribution without a distinct trustworthy witness. The diagnostic returns `native_N12_acceptance=NOT_EVALUATED`, never strict PASS.

## Scorecard

- G1 PASSED (25% of four-gate delivery). G2 in progress (still **25%, not 50%**).
- Official R02.5 **0/5**, N12 **0/2**, P4 **14/20 (70%)**, historical engineering file mutation **3/4 (75%)** unchanged.
- Next step: review final step states and fixed-label redacted outcome, preserve calibration failures, decide whether current evidence suffices for G2 or whether separate narrowly approved evidence would be necessary. **No automatic rerun.**
