# PilotODIN P4 R02.5 | G2.3 generated Sysmon bookend-only source harness

**22 November 2026. SOURCE-ONLY.** Future hosted Windows calibration is **NOT** authorised or executed by this change. The prior one-use full WebView2 capture approval is consumed. Official R02.5, N12 and P4 acceptance are unchanged.

## Why this exists

One-use native [run #45041259808](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/45041259808) compiled its isolated unpackaged QA executable, passed its initial generated TCP/UDP Sysmon fixture on the first read, completed the no-CDP app worker and same-capture write/restore stage, but failed final fixture `parent-birth-before-window`. Its redacted timestamps differ by approximately one millisecond, consistent with Sysmon ProcessCreate `UtcTime` truncation around an immediate pre-spawn window start. No complete FileIO report resulted. The source-only 50 ms final-fixture lead-in was reviewed and [CI #45042450714](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/45042450714) passed **139/139** tests. No second native measurement has confirmed that hypothesis.

## Bounded generated-only implementation

- `qa/p4_research/n12_generated_sysmon_bookends.py` is an explicitly gated generated-bookend driver. It uses only existing generated child fixture `n12_calibration.py` and the original `n12_app_journey.verify_fixture_sysmon` strict Sysmon checks. Two window starts occur **before** a 50 ms pre-spawn delay. There is one generated parent/child + loopback TCP/UDP fixture for `initial`, then exactly one for `final`. A failure ends the sequence without launching or retrying another fixture.
- Both bookends require process birth/exit, original identity, TCP and UDP, and existing strict window rules. There is no exception or tolerance permitting `parent-birth-before-window`. The internal handler fails closed on malformed callback, invalid monotonic timestamps and inconsistent fixture shape. Source-only tests use injected callbacks, **not** an actual Windows event collector.
- The source-pinned prospective Windows CLI refuses unless the process is on GitHub-hosted Windows, a new one-use generated-bookend consent matches the exact reviewed Git revision, and the approved runner temp scope is established. Only after those checks does it call the existing Sysmon channel reader and calibration fixture. It has no app build, WebView2 launch, original file-handle acquisition, installer, original user file, external service access beyond later Microsoft Sysmon provisioning, or protected-data operation.
- A new `-GeneratedBookendsOnly` option in `Invoke_P4_N12_Live_Calibration.ps1` reuses the existing Microsoft signature/hash-validated Sysmon provisioner and `finally` uninstall. This option refuses any app, FileIO, ProcMon, other collector mode, ambient storage variant, app executable hash or debug settings. `-WithEtw` is used only to select Sysmon without ProcMon; **no Kernel-File ETW session** is started in this generated-only mode.
- `.github/workflows/p4-n12-generated-sysmon-bookends.yml` is checked in with the sole Windows job **`if: ${{ false }}`**. It only watches a new marker path which is **not present**. A future activation must be separately authorised for one pinned source SHA and a direct-child commit that changes just this workflow and **adds** the fresh marker. No `workflow_dispatch`, retries or artifact uploads exist.
- The existing no-CDP native FileIO workflow remains DISARMED. The 2026-11-22 prior consumed native marker and older historical marker remain untouched. The strict N12 reducer, browser storage roots, file allowlist and installer restrictions are not changed.

## Reviewable evidence and test rules

- Synthetic regression tests cover initial then final ordering; start-before-delay-before-parent-spawn; unchanged strict verifier call; unique fixture count; abort without retry on initial, final or generator failure; malformed schemas and timestamps; Windows/source/consent refusal; no data leakage in fixed-label reports; disarmed source guard and disallowed product/installer modes.
- Existing FileIO source-only CI must remain Linux `contents: read`, pinned checkout, no product or collectors, and run the new suites alongside the prior 139 tests. **Do not claim new exact-source CI PASS until the GitHub run is verified.**
- A future approved host run could establish **generated Sysmon fixture calibration only**. Even two green generated bookends would not establish WebView2 real FileIO provenance, actual original WebView2 *file* handles, no ETW loss in a product run, protected-user-data safety or native mutation acceptance. Explicit future owner permission is still required to install Sysmon or start the Windows-only control.

## Progress and next gate

- Delivery G1 PASSED (25%); G2 open until separately authorised real native product FileIO evidence, trustworthy writer-to-original-file-handle joins, strict loss/protected controls and actual path attribution are independently demonstrated.
- Historical file-mutation preparation 3/4 (75%); official R02.5 **0/5**, N12 **0/2**, P4 **14/20 (70%)** remain unchanged.
- Next after source-only CI: review the generated-only host protocol and collect **separate exact-source one-use owner consent** if the user wants to run just the inexpensive disposable Sysmon control. Never silently reuse the failed full-app capture permission.
