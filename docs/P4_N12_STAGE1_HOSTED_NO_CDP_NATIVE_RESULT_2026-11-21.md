# P4 R02.5 | Stage 1 no-CDP native hosted-Windows result, BLOCKED

**21 November 2026 | One approved, one-use, unpackaged hosted-Windows native smoke.**

- **Authoritative actual run:** [N12 hosted app-lifetime #44888041646](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/44888041646), job `136797534570`, conclusion **FAILURE** because the strict lifetime reducer returned **BLOCKED**. This was not an application compilation error and cannot be relabelled a lifetime PASS.
- **Exact native source:** `78ae56b19ad24e357bfeb4181ec0134affc4e528`; activation-only direct child `1715b7d117c00342f0f4654366674c9aae09f53e` changed only dormant workflow and added one-use marker; immediately disarmed and removed marker in `84b1f21ee519c474b923fea8f24892d8f0fd24a8`.
- **Provenance:** isolated QA application identifier `com.pilotodin.p4isolatednativedev`, executable SHA-256 `2e67758948507743a23835cc302d0868b48e0bb8194626b59de60ff2552c13f3`, Cargo.lock SHA-256 `6fda67bc612a241200d7a644e01f00d299ce7b38221caa032e686cedd195339d`. Workflow step confirmed the exact reviewed checkout before compilation and the staged digest before capture.

## Native observations, not inferred successes

The real Windows Rust/Tauri **unpackaged build passed** (3m16s `dev` cargo build), following successful dependencies and source consent checks. The backend/Vite service stage, app-lifetime-ready stage (which encompasses the no-CDP app startup, actual readiness marker, normal peer/main close and path-count shutdown), worker completion, ETW start/stop, endpoint comparison, Sysmon export, ETW export and reducer stage all completed.

Protected endpoint snapshot comparison **MATCH**. Expected disposable QA home, WebView profile and QA-local directories changed; no unexpected snapshot changes were recorded. Process roles observed: **one app, six WebView and one WebView-network** process. ETW counters were **events_lost=0, log_buffers_lost=0, realtime_buffers_lost=0, buffers_written=5**. All eight process-start image comparisons were **exact-path-match**. These are valuable bounded observations but do **not** constitute full file mutation, network or original-data acceptance.

## Why strict identity was BLOCKED

The native reducer returned:

```text
verdict=BLOCKED
issues:
  app-or-launcher-handle-unverified
  etw-lifetime-order-unverified
  no-cdp-prior-lifetime-evidence-unverified
handle comparison: app=BLOCKED; launcher=MATCH
no_cdp_profile_identity.status=BLOCKED
native_N12_acceptance=NOT_EVALUATED
file_event_coverage=NOT_EVALUATED
network_isolation=NOT_EVALUATED
```

The **original app handle and ETW payload agreed exactly** on both birth and exit timestamps (zero tick delta). However, the app's ETW event-header start was **237 ticks earlier** than the creation payload. The other WebView starts ranged **30 to 1,816 ticks earlier**; WebView stop headers preceded unconfirmed exit payloads by roughly **2,975 to 3,584 ticks**. Each tick is 100 ns; these are sub-millisecond discrepancies. The independent launcher timing check passed.

Current `qa/p4_native/n12_exit_corroboration.py::EtwLifetimes._order_issues` strictly rejects `start-header-before-creation`; for a child without an exact independent retained handle, it also rejects `stop-header-before-unconfirmed-exit`. Consequently, `EtwLifetimes.find` blocked before the app and complete browser subtree could be certified. Because `no_cdp_profile_identity` requires the **preceding** strict lifetime proof, its result stayed BLOCKED. The native process/profile proof is not upgraded based on small offsets or zero collector loss.

## Next action and approval boundary

The precise next *source-only* investigation is to distinguish ETW process-event **header** timestamp semantics from payload CreateTime/ExitTime and original handle time, with positive and negative fixtures including the observed negative-offset shapes, wrong sequence/image/parent, capture loss, and missing child. Determine whether the strict verifier is testing a guaranteed ordering property or wrongly assuming it. Do not simply add an arbitrary tolerance, credit orphan child exits, or bypass the strict guards. An evidence-backed correction, if justified, needs its own source CI and explicit acceptance-scope review.

**Do not rerun native automatically.** This one-use approval is consumed, and the activated workflow has been restored to `if: false` with approval marker removed. Any later source-pinned hosted-Windows capture or full FileIO/network audit requires fresh one-use consent and must not install on or modify the owner's computer.

**Ledger unchanged:** file-mutation workstream **3/4 (75%)**; R02.5 **0/5**; N12 **0/2**; network **2/3 (67%)**; official P4 **14/20 (70%)**. Governing last complete native N12 #44838416004 remains filesystem **FAIL**, network **FAIL**, mutation coverage **BLOCKED**. Stage 1 is **BLOCKED**, despite successfully compiled and exercised native application.
