# PilotODIN 1.0 | P4-47 One owner-authorised isolated unpackaged native Windows acceptance

**Date:** 12 November 2026. **Owner approval:** one isolated native Windows developer compilation and controlled acceptance exercise with verified distinct identity/storage, disposable test data, **no owner original app/data**, **no installer**, P5/P8 NOT authorised. **Approval consumed by a single successful unpackaged compilation.**

## Exact authorised origin, environment and preflight

Owner explicitly approved **one** unpackaged native compilation and controlled acceptance, conditional on verified identity and storage before compilation. This was not permission to build a deployable full installer or train a model, to touch owner folders, to waive R06, to close P4 or to start P5/P8.

One-time [source commit `74f25b3a6b959d31cc520ef4d18b4a24842a819f`](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/74f25b3a6b959d31cc520ef4d18b4a24842a819f), [GitHub Actions #43159387547](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/43159387547), **COMPLETED SUCCESS 2/2 jobs**, attempt 1:
- `p4-preflight` Windows-2022 hosted runner job **SUCCESS before compilation job was eligible**. Verified exact source SHA and branch; 3 separate Tauri identifiers: production `com.pilotodin.studio`, old installed QA `com.pilotodin.p4nativeqa`, isolated dev `com.pilotodin.p4isolatednativedev`; no `appDirectoriesOverride` or window `dataDirectory`; isolated `bundle.active=false`, `externalBin=[]`, `resources=[]`; Rust backend `PILOTODIN_HOME` derived from Tauri `app_local_data_dir()/data`; production Tauri and npm launcher/build default-deny hooks unchanged. Verified GitHub-hosted environment (not self-hosted, not owner PC), no original/old-QA local/roaming app-data directories, and no inherited `PILOTODIN_HOME`.
- `p4-one-unpackaged-native` ran on a **second disposable Windows-2022 hosted runner**, and repeated the same preflight **before native compilation**. It used locked `npm ci` dependency install and Rust MSVC toolchain; performed **one** `npx --no-install tauri build --no-bundle --config src-tauri/tauri.p4-one-time-unpackaged-ci.conf.json` build of a native EXE with isolated ID. No Qwen model, native sidecars, real user datasets or owner-installed programs were used.
- Initial attempt to define the one-time GitHub workflow at [`0486da75`](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/0486da752533228d880a955f8237c570ced8b7d5) caused [Actions #43159203331](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/43159203331) **FAILURE with 0 jobs**, due to an unquoted YAML condition containing a colon. **NO native compilation happened on that failed run.** The quoted expression was corrected in `74f25b3a`, and this was the **only** build run.

## Native compile and bounded Windows smoke evidence

Direct Windows job log from [#43159387547](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/43159387547):

| Check | Observed result |
| --- | --- |
| One-time Windows source and identity/storage preflight | **PASS** (both runner jobs) |
| Compiled Tauri Rust native executable | **PASS**, original commit SHA `74f25b3a6b959d31cc520ef4d18b4a24842a819f` |
| Native EXE name | `pilotodin-desktop.exe` (located only within disposable CI workspace) |
| EXE size | **12,267,008 bytes** |
| EXE SHA-256 | `566baf6c2a7527c1e593dc06691f2b01ea1dcb9959d4cfa22275c865a36e72df` |
| Installer/package generation | **NONE**; `tauri build --no-bundle`; bundle output checked; no uploaded artifacts |
| App running after 12-second native process smoke | **TRUE** |
| Isolated native-development app-local-data path created | **TRUE** |
| Concurrent WebView2 processes with isolated native-dev profile argument | **6** |
| Original production app-local-data path created during smoke | **NO** |
| Existing independently installed QA app-local-data path created during smoke | **NO** |
| Native process cleanup | Stopped test process on disposable CI; GitHub runner tears down |

This verifies **limited native startup and current-profile separation on a disposable Windows 2022 CI runner**. No user desktop access or original files are involved. The 6 WebView processes prove only current launch-profile arguments, **not** that all possible filesystem writes are impossible, or that historic owner data was unaffected.

## Limitations and exact risk disposition

- **R01 real business Gate C: OPEN.** No independently verified decision owner, outcome/labels, as-of prediction timing, validation independence, baseline, benefit/cost or lawful/fair use was produced.
- **R02 native negative/version parity: OPEN, partial native bootstrap proof only.** No operator exercised N8–N11, project revisions, manual target selection or full native P4 API journeys in this 12-second smoke. CI native app excluded its Python sidecar, so full desktop workflows cannot be claimed.
- **R03 offline/8GB local AI: OPEN.** Model, local Qwen runtime and inference sidecar intentionally excluded. Hosted runner is not owner's physical 8 GB machine; no combined sustained memory/performance proof.
- **R04 source-fixed native UX: OPEN.** This test does not include owner visual screenshots of archive warning, Decision usefulness layout or selected-target strip.
- **R05 Prepare BE-024: OPEN.** Native Prepare controls and transformations not manually exercised; no full integration proof.
- **R06 whole original app-data preservation: OPEN/STRICT FAIL.** Earlier independently verified owner backup and original EXE hashes matched, and protected original project `data/` contained **0 detected differences**, but complete original app-data tree **FAIL** remains (320 backup vs 346 observed files, 74 browser/cache *candidates*, historical writer UNKNOWN). This clean disposable CI test proves **prospective scoped isolation**, **not** the historical writer or retroactive whole-tree PASS. No change to original preservation baseline or owner files, no waiver/cleanup/cache deletion.

The owner previously rejected phase closure via deferring risks. The restricted native build authorisation is **consumed** by this one success and does not modify that decision. No transfer or install of this unbundled EXE has been authorised, and it was not uploaded.

## Post-run freeze

The one-time temporary config/workflow is disabled and its temporary executable-build invocation must not run again without a **new** separate explicit owner decision. P4–P7 intermediate NSIS/MSI/EXE installer packaging remains frozen; normal development and production-default Tauri denial hooks remain in place.

**P4 ACTIVE | P4-R01–R06 OPEN | P5 NOT AUTHORISED | P8 NOT CERTIFIED.**

**Next meaningful closure:** Obtain independently sourced real Gate C business evidence; if the owner later authorises additional native tests, prepare a separate consolidated source-matched acceptance with functional backend and actual physical 8 GB/offline measurements. Historic R06 needs a separate incident disposition supported by evidence. Do not keep reusing this one-time approval.
