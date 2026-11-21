# PilotODIN P4 R02.5 | One-use no-CDP Stage 1 native retest, BLOCKED

**21 November 2026.** The owner expressly authorized exactly **one** source-pinned, unpackaged, no-CDP startup and shutdown test on a disposable GitHub-hosted Windows runner, with source `3de78db79073aa1c6b9d99d8aa3b9941a9a9065e`. No installer, owner-PC changes, protected-data access, firewall actions or full N12 FileIO/network test were authorized or performed.

- **Actual native run:** [#44890538700](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/44890538700), job `136805166480`, **COMPLETED FAILURE** because the strict evidence reducer returned **BLOCKED**.
- **Reviewed and compiled source SHA:** `3de78db79073aa1c6b9d99d8aa3b9941a9a9065e`.
- **Activation commit:** `cd1de8fa932ed71ea88cf2d17ecf909b25c07d78`, a direct child of the approved source changing exactly the dormant lifetime workflow and adding its one-use marker; the workflow checked this structure, detached back to the approved source, and verified both distinct native and no-CDP consents.
- **Immediately disarmed:** `4699e5b4e2a4fdfb5b2f55a949c606b16e74c8ea`, restoring the **exact original disabled workflow blob** and removing the one-use marker. Subsequent verification confirmed `if: false` and marker absent. No replay is authorized.
- **Build identity:** isolated QA `com.pilotodin.p4isolatednativedev`; binary SHA-256 `1b97f484f4b4b4e1d0a4df0e930fc1f15bae58561e030a8b225a9fce6cb12ddf`; Cargo.lock SHA-256 `6fda67bc612a241200d7a644e01f00d299ce7b38221caa032e686cedd195339d`. The unpackaged Rust/Tauri build and binary-provenance check passed.

## Observed native evidence

The app-services, debugger-free ready/close, worker, ETW start/stop, protected endpoint comparison, Sysmon and ETW exports, and strict reducer completed. Protected endpoint comparison was **MATCH**: original app-data identities did not change; only expected disposable QA home, WebView and local paths changed, with no unexpected snapshot differences.

Captured scoped roles: **one app, six WebView and one WebView-network process**. All eight app/WebView start executable image comparisons were **exact-path-match**. All WebView stop image comparisons remained the previously observed fixed short-basename-prefix format. ETW collector: **events_lost=0, log_buffers_lost=0, realtime_buffers_lost=0, buffers_written=5**.

Crucially, the original retained app and launcher handles agreed exactly on both birth and exit with their ETW lifecycle payloads: **zero-tick payload-versus-handle deltas**. Their `etw_handle_order_comparison.ordering_issues` lists were both empty. Several WebView start headers still preceded provider creation payloads (small negative offsets), and all observed WebView stop headers preceded exit payloads by around 1,022 to 1,146 ticks; they remain diagnostic, not stand-alone lifetime proof.

## Exact blocker and what can be concluded

```text
verdict = BLOCKED
issues =
  app-or-launcher-handle-unverified
  no-cdp-prior-lifetime-evidence-unverified
  no-cdp-sysmon-lifetime-unverified
handle_comparison = {app: BLOCKED, launcher: BLOCKED}
no_cdp_profile_identity.status = BLOCKED
no_cdp_profile_identity.reason = no-cdp-prior-lifetime-evidence-unverified
native_N12_acceptance = NOT_EVALUATED
file_event_coverage = NOT_EVALUATED
network_isolation = NOT_EVALUATED
timing_comparisons = []
```

The new no-CDP `EtwLifetimes._no_cdp_sysmon_confirmed` gate checks several prerequisites together: non-disputed complete Sysmon process end, ETW sequence, capture bounds, existing Sysmon birth join, exact ETW exit payload equality with Sysmon exit, and exact mapped ETW start image. The reducer reported only the combined `no-cdp-sysmon-lifetime-unverified` label before reaching per-process timing comparisons, **including for the launcher and app**. The retained handles' exact match to ETW payloads does **not** establish that the separately recorded Sysmon exits are exact, nor does the redacted report isolate which clause failed. No claim about a specific Sysmon timestamp difference or missing record is justified yet.

**Source-only next action:** instrument a redacted, per-clause Sysmon/ETW/handle corroboration comparison that distinguishes absent/disputed Sysmon exit, Sysmon birth or exit delta, process image, sequence and capture-window failures while withholding PID, source paths and raw time. Add positive/negative source-only fixtures using real run shapes. Do not weaken an equality rule, introduce a tolerance, infer a PASS, or launch a third native test without separately reviewed evidence and a fresh one-use owner approval. Exact-source CI of this instrument would not be native Stage 1 acceptance.

**Official ledger unchanged:** Stage 1 native **BLOCKED**; file-mutation workstream **3/4 (75%)**, R02.5 **0/5**; N12 **0/2**; P4 **14/20 (70%)**. Last complete N12 [#44838416004](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/44838416004) remains filesystem **FAIL**, network **FAIL**, FileIO coverage **BLOCKED**. Stage 2 full FileIO/native network capture is not approved.
