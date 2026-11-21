# PilotODIN 1.0 | P4-33 One owner-authorised GitHub-only Windows QA build: VERIFIED

**11 November 2026. P4 Target Intelligence ACTIVE.** This records one specifically authorised cloud CI build. It is **not** permission to install on the owner's PC, to replace or edit the original PilotODIN or its data, to waive preservation, to close P4 or to activate P5.

## Exact owner authority and trigger

Owner explicitly said: "I explicitly authorise one isolated, current-source PilotODIN P4 Windows QA build in GitHub Actions only. Verify source and executable provenance. Do not install it on my computer, change original application data, waive any failed acceptance gate, or advance to P5."

[Trigger commit `8c9370b83da4cd8fe7fb1b928ca8ca9b07b701c1`](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/8c9370b83da4cd8fe7fb1b928ca8ca9b07b701c1) modifies only **comments** in `.github/workflows/p4-native-windows-milestone.yml` on `feature/live-dev-workspace-20261023`. The existing workflow's push path filter triggered **one** CI native packaging run. The built application source is otherwise identical to the preceding audited branch state. No manual second dispatch, installer rebuilt elsewhere or release upload occurred.

## Windows CI execution and job-log verification

[GitHub Actions run #43070526666](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/43070526666) finished **COMPLETED SUCCESS, attempt 1**, on Windows 2022, exact event SHA `8c9370b83da4cd8fe7fb1b928ca8ca9b07b701c1`. All steps recorded **SUCCESS**, including:

1. Trusted exact-source checkout `GITHUB_SHA` match, distinct QA product `pilotODIN-P4-Native-QA` with identifier `com.pilotodin.p4nativeqa` versus original `com.pilotodin.studio`, four stdlib isolation/source contracts.
2. Pinned local Qwen3 generation and distributable license/model staging on the **GitHub runner**, plus the verified frozen Python engine and loopback-authenticated analytical backend smoke.
3. Production frontend/Tauri Windows NSIS packaging and compiled assets including the Satin Chronograph UI source class.
4. Disposable Windows CI installer verification: installed engine auth and wrong-Origin safety; CI-installed desktop EXE compared with compiled desktop EXE.

**Actual decoded CI job log values:**

| Verification | Value |
| --- | --- |
| Compiled desktop EXE length | **12,268,032 bytes** |
| CI-installed desktop EXE length | **12,268,032 bytes** |
| Compiled and CI-installed desktop EXE SHA-256 | **`978cf37b5f5acca03174bc0632117a3262b00a063ffecd7963c7e2e709c88749`** |
| Job-log verdict | **`Source-matched compiled and CI-installed Windows EXE SHA256: MATCH`** |
| Source SHA in job log | **`8c9370b83da4cd8fe7fb1b928ca8ca9b07b701c1`** |

These are real CI executable and disposable installation results, **not a claim that the owner-installed Windows EXE matches this source**. The owner installed the earlier `bca3c57` QA build; the latest source has not been installed or tested on the owner's hardware.

## Published artifacts and separately inspected manifest

The completed run published two distinct **short-lived development artifacts**, not a GitHub release:

| GitHub artifact | Artifact ID | ZIP archive bytes | Expiry policy |
| --- | ---: | ---: | --- |
| `PilotODIN-P4-16-Source-Provenance-NOT-OWNER-ACCEPTANCE` | `13880031309` | **891** | 7-day retention |
| `PilotODIN-P4-16-EXPERIMENTAL-Windows-NSIS-DO-NOT-INSTALL-YET` | `13877639265` | **1,595,044,240** | 3-day retention |

The **891-byte provenance ZIP was actually downloaded and extracted** from the connected GitHub artifact, then `source-and-windows-artifact.json` was parsed independently. Fields confirmed:

- `schema_version=1`; `source_commit=8c9370b83da4cd8fe7fb1b928ca8ca9b07b701c1`; `github_run_id=43070526666`; `github_run_attempt=1`; `github_ref=refs/heads/feature/live-dev-workspace-20261023`; `runner_os=Windows`.
- `qa_identifier=com.pilotodin.p4nativeqa`; `existing_product_identifier=com.pilotodin.studio`.
- `compiled_desktop_exe_sha256=978cf37b5f5acca03174bc0632117a3262b00a063ffecd7963c7e2e709c88749` (agrees with the separately downloaded CI job log above).
- `disposable_ci_install_engine_smoke_passed=true`, `compiled_exe_matches_disposable_ci_installed_exe=true`.
- Manifest **inner NSIS installer**: filename `pilotODIN-P4-Native-QA_1.0.0-alpha.1_x64-setup.exe`, **1,594,576,707 bytes**, and **CI-generated SHA-256 `945c0a7426430682ea2f6b21c90e373a0bed4fa36baafb7cb278f1b3c70d2ad4`**.
- Separate frozen Python engine SHA-256: `6531a1b5ad6b9b572454e3b2bcde12de011da1ddaf3ca4a98aa310c93371ff1f`.
- Pinned inference binary SHA-256: `b2ace4b8aed7c60e217fcaed8541850f4998539b8478880f1c3264387a0a8d97`.
- `installed_on_owner_windows=false`; `native_owner_acceptance=NOT_TESTED`; `business_acceptance=UNVERIFIED`; `release_certified=false`.

**Evidence limits:** The larger 1.6 GB installer ZIP was **not downloaded or locally rehashed**; its GitHub artifact archive digest (`sha256:9bd04fc480f908028f06dfaa43c1baf72ed336bcebc9329d6da3adc59db3b30c`) applies to the **ZIP**, not its enclosed NSIS executable. The manifest installer SHA-256 is an authenticated CI-produced claim supported by the completed build/step history, **not independently verified from the download's inner 1.595 GB installer bytes**. The smaller provenance artifact ZIP digest (`sha256:dbcc7a7c527fdce946b7a6764ef33df86f558abb46adc31c151f42d2d2a9a487`) likewise identifies the ZIP archive, not the embedded JSON.

## Original app protection and unpassed acceptance gates

Previously verified owner-native P4-24 evidence: independent backup matches baseline, original production EXE matches baseline, protected source-defined `data/` project store 0 detected changes; nevertheless the original **full application data directory fingerprint remains FAIL** (320 baseline files vs 346 current; 74 browser/cache *candidates*; historical process writer UNKNOWN). Owner-native P4-28 current process observation succeeded (26 current WebView2 processes, six QA-profile, zero original-profile, 20 other), but it cannot identify earlier cache writers or exclude past cross-app writes. No deletion, repair, waiver, backup replacement or test-baseline reset is authorised.

This GitHub CI run did **not** install on the owner PC, measure sustained memory on an 8 GB device, verify physically disconnected offline inference, retest current-source Windows dock/selection/Quality-version negatives or prove Gate C real-world label provenance, prediction-time features, group/time split, non-ML baseline, decision cost/benefit and fair/lawful purpose.

**Disposition: P4-33 GITHUB-ONLY QA BUILD PASS + CI SOURCE/EXE MATCH VERIFIED + MANIFEST INSPECTED; OWNER PHYSICAL INSTALL/ACCEPTANCE NOT TESTED. ORIGINAL FULL DATA-TREE PRESERVATION FAIL; BUSINESS GATE C UNVERIFIED. P4 ACTIVE; P4-R01–R06 OPEN; P5 NOT AUTHORISED; P8 NOT CERTIFIED.** Do not trigger another build or install without separate fresh owner authorisation.
