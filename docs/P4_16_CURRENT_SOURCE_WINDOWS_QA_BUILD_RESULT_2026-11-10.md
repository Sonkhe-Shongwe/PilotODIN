# PilotODIN 1.0 | P4-16 Current-Source Windows QA Build: Verified CI Provenance

**Observed:** 10 November 2026 UTC. **Phase:** P4 ACTIVE; original operational Gate C UNVERIFIED, no closure or P5 authorisation. **Meaning:** an experimental isolated GitHub-runner build/installation identity proof, **not** owner-native acceptance, offline 8 GB certification, or a product release.

## Exact run and tested source

- [Windows QA GitHub Actions run #42730585801](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/42730585801), attempt **1**, **COMPLETED SUCCESS** (10 November 2026 01:04:54 UTC).
- Exact executable source and workflow commit: [`0c7a2b4cf1bdb4b5dba6582dc306493c741e2d23`](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/0c7a2b4cf1bdb4b5dba6582dc306493c741e2d23).
- CI job ID **129547254066**, Windows 2022; exact SHA checkout; **4/4** source/clock contracts; pinned Qwen3 GGUF loaded in llama.cpp and returned an authenticated **actual local CI generation**; frozen Python engine built and launched; source-matched Tauri/NSIS package built; compiled frontend includes Satin Chronograph class; executable installed on disposable CI runner; offline payload installed and authenticated installed-engine smoke passed; compiled-versus-CI-installed EXE hash **MATCH**.
- **Scope qualification:** GitHub Windows runner had network during preparation; the phrase "offline payload installed" does not certify a physically isolated network-off clean install. The clock class-presence check does not prove owner's WebView2 visual rendering, and a single CI Qwen3 generation is not an 8 GB combined-workload or model-quality benchmark.

## Independent provenance artifact retrieved and inspected

The GitHub artifact named `PilotODIN-P4-16-Source-Provenance-NOT-OWNER-ACCEPTANCE` is [artifact ID **13725886209**](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/42730585801/artifacts/13725886209), **886 bytes as compressed ZIP**, created **2026-11-10 01:04:01 UTC**, expires **2026-11-17 01:04:01 UTC**. Retrieved through the connected GitHub artifact endpoint and inspected in an isolated local container. ZIP SHA256 calculated from the downloaded bytes **eda9748215d20ef8c19acf462c849f53f6cdedd9740d11c7f247d7a1a2dfb415**, equal to the digest reported by GitHub. Its single JSON member is `source-and-windows-artifact.json` (1209 uncompressed bytes; SHA256 **cd63b724b3082c26eb24132eb07d5f96d2dbcb3fe70b3b434cd513f55610a88c**). The JSON identifies exactly the above source SHA, run ID, attempt and separate QA identity.

| Manifest property | Verified manifest value |
| --- | --- |
| QA product identifier | `com.pilotodin.p4nativeqa` |
| Existing app identifier, deliberately distinct | `com.pilotodin.studio` |
| QA installer filename | `pilotODIN-P4-Native-QA_1.0.0-alpha.1_x64-setup.exe` |
| QA installer bytes (inside installer artifact ZIP) | **1,594,498,596** |
| QA installer SHA256 (manifest and CI calculated; **installer not separately downloaded/rehashed on review machine**) | `ad847b776fe8543ae3de8d29a913a2ae3eb0d3cd283cf7ae4e90ea1ebfd9ffd5` |
| Compiled desktop EXE SHA256 | `ce5083d5d58d01d712635df74b89163d0a5ba48febaebda428223b5a27071097` |
| Frozen Python engine SHA256 | `020f2fde83e4891effa315f1158d7c6d8511e1844973f31350eabdf883c51fa3` |
| Pinned inference executable SHA256 | `b2ace4b8aed7c60e217fcaed8541850f4998539b8478880f1c3264387a0a8d97` |
| CI installed-engine smoke | `true` |
| Compiled versus CI-installed EXE equality | `true`, independently corroborated by matching hashes printed in job logs |
| Owner installation | `false`; owner-native acceptance `NOT_TESTED` |
| Real business acceptance | `UNVERIFIED`; release certified `false` |

The **separate** experimental installer *artifact ZIP* is [artifact ID **13725312774**](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/42730585801/artifacts/13725312774), size **1,594,966,122 bytes**, GitHub-reported ZIP SHA256 `b65809fcc7dc80dec328e31d5b88b8738bcb04d76384f38396a9443baa1586fa`; expires **2026-11-13 01:04:02 UTC**. This ZIP hash is **not the installer EXE hash** above. The large installer ZIP was **not downloaded in this review**, to avoid unnecessary 1.59 GB transfer; record its bytes/hash as CI-issued provenance, not as an independent local rehash.

Job log reports the compiled desktop EXE and disposable CI-installed EXE each **12,266,496 bytes**, both SHA256 `ce5083d5d58d01d712635df74b89163d0a5ba48febaebda428223b5a27071097`, with `Source-matched compiled and CI-installed Windows EXE SHA256: MATCH`. It also reports `WINDOWS INSTALLATION CHECK PASSED: offline payload installed and installed engine booted`. All workflow steps and the overall run concluded successfully. Prior failing Windows workflow attempts remain failures and are not rewritten here.

## Strict continuation and next owner gate

- **Current branch HEAD at start of this review:** `5eec3fa83dc4ddf2a03b8a281eb018423dc75992`, a documentation-only descendant of the exact built application SHA. This review adds Markdown evidence only. It does **not** justify a fresh CI build or imply a documentation-only commit has passed fresh runtime tests.
- **No local install/download approval:** Prior owner approval covered one GitHub-hosted QA build only, **not** local installer download/execution or replacement of original PilotODIN. No user datasets, installed files, model weights, installer files or owner Windows environment were changed by this review. Preserve original `com.pilotodin.studio` and existing older QA installation until a separately approved action.
- **If owner separately approves:** Use the [P4-23 one-pass acceptance plan](./P4_23_CONSOLIDATED_WINDOWS_ACCEPTANCE_GO_NO_GO_2026-11-09.md). Verify the artifact ZIP and inner installer EXE SHA256 against these independently sourced values **before** execution; verify genuine GitHub provenance, a separate QA identifier/app-data location and a full read-only original EXE/data-tree baseline outside owner data before install. After a separately authorised side-by-side QA install, compare installed QA EXE to the manifest; perform condensed current-source UI/N8–N12 checks on **synthetic disposable projects only**; measure actual offline/8 GB usage honestly; verify original EXE/data tree unchanged; record Gate C separately using independent real operational evidence, if available. If any hash, provenance, headroom or preservation check fails, **STOP**.
- Owner-selected Satin Chronograph has been included in compiled frontend by CI presence check, **not owner visually accepted**.
- Owner's physical Windows N8–N12, actual 8 GB offline with inference+analytics, real business Gate C, full data restoration and P4 owner closure remain **OPEN**. Master QA [Issue #2](https://github.com/Sonkhe-Shongwe/PilotODIN/issues/2) and P4 owner [Issue #9](https://github.com/Sonkhe-Shongwe/PilotODIN/issues/9) remain open. **P4 ACTIVE; P5 NOT AUTHORISED; P8 NOT CERTIFIED.**

## Verification honesty

The current increment verified actual GitHub run/job metadata, the job log and the independently downloaded small provenance ZIP/JSON. It did **not** rerun source unit tests, retest installed Windows software on the owner PC, check the full installer bytes locally, perform air-gapped installation or apply any project-data changes. No new Actions installer build was invoked.
