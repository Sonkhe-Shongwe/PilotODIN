# PilotODIN P4 | Bounded main-window readiness without CDP

**21 November 2026 | Source-only verification. No native application or capture run.**

## Specific defect addressed

The no-CDP lifecycle previously checked the main window once after process launch. On Windows the main window may appear after the app's retained process handle becomes live. The original selector emitted the same `no-cdp-window-missing-or-ambiguous` error for both **absence** and **duplicates**; blindly polling that error would treat a real identity defect as ordinary startup delay.

The selection contract in `qa/p4_research/n12_no_cdp_main_window.py` now emits **`no-cdp-window-not-yet-present` only when the reviewed OS snapshot contains neither an expected-PID window nor a matching expected-title window**, after the exact process image, handle birth, snapshot and title-collision validation. A visible or hidden wrong-title window from the expected process is not an allowed transient condition. Foreign exact-title collisions, duplicates, invalid/owned windows, stale PID/birth, unexpected observer errors and premature app exit remain hard stops.

## Small, bounded source implementation

`wait_for_main_window` accepts the original still-live process, its expected image/title and pinned creation ticks. It retries **only** that exact clean-absence condition with a 100 ms polling interval and a strictly validated maximum **20-second budget** (default 10 seconds); observation finishing after the deadline is rejected even if it found a good window. It does not use CDP, port 9331, shell polling or browser PID guesses. It exposes fixed, redacted error categories `no-cdp-window-wait-timeout`, `no-cdp-window-app-exited-before-ready`, and `no-cdp-window-clock-invalid` on relevant failures. The retained original handle's image and creation time are reverified by the actual Win32 observer on each attempt, and app liveness is checked before/after a successful observation.

The non-launching `NoCdpLifecycleObserver.observe_readiness` now waits for this unique window **before** requiring the one-time app-log marker, with a separately bounded `window_timeout_seconds`. The existing `prepare_normal_close` rechecks the same HWND/PID/birth. This module **does not launch or close a native process, call the real window observer in CI, set consent, enable a disabled workflow or mark N12 accepted**. The current `n12_app_lifetime.launch_and_close` still uses CDP/9331; WebView profile-active substring counts remain diagnostic only. A future native runner must handle any observed hidden peer timing without loosening the exact title/identity policy.

## Exact-source CI and negative controls

- [Source implementation `d02ee24`](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/d02ee24dc62a66aca45ad2d80b618f4fbf5eda73) introduced the absence-only wait. The first automatic run [#44876575099](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/44876575099) was **cancelled** after the focused deadline correction; it does not count as a pass.
- [Corrected source `298c402`](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/298c402a6c5522f0889e7ba9de848b08e4bd091e) makes late positive observations fail closed and tests that condition. [Exact-source routine CI #44876670006](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/44876670006) completed **4 of 4 jobs SUCCESS**: **871 Python passed, 6 skipped, 341 subtests passed, one warning**, **104 Node/frontend tests passed**, TypeScript/Vite build passed, **13 disposable real-HTTP Chromium passed**, hosted Windows synthetic lifecycle/ETW/FileIO controls passed and R03 Windows synthetic suite **4 passed**.
- New generated cases exercise normal startup delay with irrelevant foreign windows, strict refusal for duplicate, hidden, owned and wrong-title windows, app exit during startup, missing window timeout, invalid wait bounds, backward clock, forged process witness, a positive window observed after deadline, and lifecycle refusal before log/close when the window is ambiguous.

**Scope limit:** no real PilotODIN WebView2 main window was inspected. A successful test of generated records does not prove Win32 timing, browser process ancestry/profile, profile shutdown, network isolation, path-complete FileIO or the prior N12 failure fixed. The historical approved N12 capture still reports **filesystem FAIL, network FAIL, mutation coverage BLOCKED**. No installer, owner data, elevated identity, permissions, firewall or one-use native capture was touched.

## Next decision-making checkpoint

Prepare independent WebView2 browser/profile lifetime corroboration for the same post-close diagnostic without using CDP: unique Sysmon GUID + ETW birth/stop + retained app-handle parent sequence, exact disposable profile (or fail closed if no supported profile evidence), explicit capture-loss review and no inferred PID. Reconcile actual WebView2 browser startup command/profile conventions against available **approved** evidence without relaxing identity rules on speculation. Only after source verification and a fresh source-pinned, one-use owner authorisation may a real native test be considered. The existing restricted workflow stays disarmed.

**Official P4 score stays 14/20 (70%).** Workstreams unchanged: product fixes **7/7 (100%)**, QA dialog driver **3/3 (100%)**, firewall preflight **2/3 (67%)**, network isolation **2/3 (67%)**, file-mutation coverage **3/4 (75%)**, native N12 **0/2 (0%)**, physical offline inference **1/3 (33%)**, original-data preservation **0/2 (0%)**. No acceptance point was earned by source-only testing.
