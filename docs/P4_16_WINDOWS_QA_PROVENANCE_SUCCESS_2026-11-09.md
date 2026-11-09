# PilotODIN 1.0 | P4-16 Windows QA Installer: Verified Source-to-Installed Provenance

**Evidence date:** 9 November 2026  
**Exact source commit:** [`bca3c57b94a425cd9ef489726e721328d12c2ead`](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/bca3c57b94a425cd9ef489726e721328d12c2ead)  
**CI Windows workflow:** [#42621192759](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/42621192759), **COMPLETED SUCCESS**  
**Owner milestone issue:** [P4-16 Issue #9](https://github.com/Sonkhe-Shongwe/PilotODIN/issues/9#issuecomment-6741132345)  
**Phase status:** P4 ACTIVE, P1/P2/P3 development-CLOSED, P5 NOT AUTHORISED, P8 NOT CERTIFIED.

## What was genuinely established

A GitHub-hosted Windows 2022 runner checked out the exact source SHA, ran three P4 QA safety contracts, staged pinned offline Qwen3/llama assets, performed a genuine authenticated Qwen3 generation, froze and ran the Windows Python analytical engine, compiled the Tauri frontend/NSIS package, **installed the NSIS on a disposable GitHub Windows runner**, and verified that the installed engine responds under local loopback/auth/Origin/storage safeguards.

Crucially, the workflow also checked that the installed desktop EXE **exactly matched the compiled desktop EXE**, rather than merely trusting the installer filename. The final Windows log reports:

| Evidence | Verified observed value |
| --- | --- |
| Run conclusion | **SUCCESS** |
| Source | `bca3c57b94a425cd9ef489726e721328d12c2ead` |
| QA product | `pilotODIN-P4-Native-QA` |
| QA app identifier | `com.pilotodin.p4nativeqa` |
| Existing app identifier | `com.pilotodin.studio` |
| Compiled desktop EXE bytes | **12,265,984** |
| Clean-CI-installed desktop EXE bytes | **12,265,984** |
| Both desktop EXE SHA256 | `7173b9c0e68295cca6bdf283daf8e61a86934d0575fac9915aea48bc9c009633` |
| Actual installed Python engine smoke | **PASS** |
| Source-matched Windows bundle | **PASS on GitHub runner only** |
| Owner Windows installation / native UI acceptance | **NOT TESTED** |
| Business data provenance, decision value and legal/fair status | **UNVERIFIED** |
| Release certification | **FALSE** |

## Artifact identity, provenance and expiration

The JSON `source-and-windows-artifact.json` was actually retrieved from GitHub Actions Artifact ID **13677687251** and inspected, including SHA and truth flags:

| Artifact/file | Provenance |
| --- | --- |
| QA NSIS filename | `pilotODIN-P4-Native-QA_1.0.0-alpha.1_x64-setup.exe` |
| QA NSIS bytes | **1,594,498,057** |
| QA NSIS SHA256 | `a38018dbe981c4269857a1e3ca87ecc98e54ca39cba40eebd792516af5b0e174` |
| Frozen Windows engine SHA256 | `64a48141de7f7f7a979ae4c24824112b7cf8f1514fb464f5cadafd916c588767` |
| Pinned inference binary SHA256 | `b2ace4b8aed7c60e217fcaed8541850f4998539b8478880f1c3264387a0a8d97` |
| Provenance artifact ID (892-byte ZIP) | **13677687251**, expires **16 Nov 2026 13:19 UTC** |
| Installer ZIP artifact ID | **13678755031**, `PilotODIN-P4-16-EXPERIMENTAL-Windows-NSIS-DO-NOT-INSTALL-YET`, **1,594,965,572 bytes**, expires **12 Nov 2026 13:19 UTC** |
| Uploaded ZIP archive SHA256 | `754de72c270e18fa8679f936b52078f7e51f4012d36d1a779d9ade440ed67def` (distinct from inner NSIS EXE) |

Provenance JSON explicitly sets `installed_on_owner_windows=false`, `native_owner_acceptance=NOT_TESTED`, `business_acceptance=UNVERIFIED`, `release_certified=false`. GitHub Actions artifacts are short-lived **development QA** deliverables, **not** product Releases or a user installation. The app variant uses a distinct Tauri identifier; *actual coexistence with the old October pilotODIN installation on the user's PC* remains to be observed, not presumed.

## Historical CI red runs (preserve)

- [#42614732584](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/42614732584): **FAILED** before packaging because Windows runner lacked pytest; corrected with stdlib source contracts.
- [#42615013119](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/42615013119): **FAILED** at compiled-versus-installed EXE SHA256 equality despite real NSIS building and installed engine checks; original Tauri log explicitly records bundle-type patching of desktop EXE.
- [#42621192759](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/42621192759): **SUCCESS** after P4 QA-only build used Tauri `--no-binary-patching` and retained byte-identical installed desktop hash. This supports the patching explanation, but no owner native test occurred.

## What is still required to close P4

**Owner native milestone:** With explicit human approval and appropriate backup/caution for the old install, obtain the verified QA NSIS, compare its **inner EXE SHA256** with the provenance JSON, then do a single safe local Windows P4-16 walkthrough on disposable synthetic projects (actual app start, target discovery, structural blockers, explicit manual choice/defer/abstain, project/version switching, no training), record observed outcomes. A successful clean GitHub runner install does **not** demonstrate that the owner app coexists safely with the October build, its real WebView2 native UI works, or it meets an 8 GB offline RAM/resource target.

**Independent business evidence:** Ground the outcome definition, original label source, inputs available at actual decision time, proper entity/group/time validation, measured baseline/benefit/false-positive costs, and lawful/fair use. User text in a description box and synthetic data do not prove these facts. Honest `NO SUITABLE PREDICTION GOAL YET` is an acceptable abstention when appropriate.

**Phase and QA control:** Master [QA Issue #2](https://github.com/Sonkhe-Shongwe/PilotODIN/issues/2) stays OPEN, including legacy BE-024 Prepare Windows concerns and other-phase historical Critical/High findings. P4-16 Issue #9 stays OPEN until owner evidence; no blanket closure, no automatic P4-17 signoff, no P5 or P8 certification.

**Disposition:** **Source-matched CI Windows build and disposable installation/provenance PASS. Physical owner acceptance NOT TESTED. P4 ACTIVE / P5 NOT AUTHORISED / P8 NOT CERTIFIED.**
