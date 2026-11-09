# P4-16 QA Installer Provenance | Failure and Scoped Correction

**Date:** 9 November 2026  
**Corrective code SHA:** [`bca3c57b94a425cd9ef489726e721328d12c2ead`](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/bca3c57b94a425cd9ef489726e721328d12c2ead)  
**GitHub owner-native milestone register:** [P4-16 Issue #9](https://github.com/Sonkhe-Shongwe/PilotODIN/issues/9)  
**Phase:** P4 ACTIVE; P5 NOT AUTHORISED; P8 NOT CERTIFIED.

## Historical build evidence to preserve

[Run #42614732584](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/42614732584) **FAILURE** before packaging due missing `pytest` on Windows runner. Corrected via three stdlib `runpy` source contract calls in `d9e56148...`.

[Run #42615013119](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/42615013119) **FAILURE** at the final executable identity gate despite a real **1.49 GiB** P4 isolated NSIS package successfully compiled and installed to disposable Windows GitHub CI. Its pinned offline Qwen3 startup/completion, frozen Python analytical sidecar, and **installed** sidecar loopback authentication/Origin/isolation checks passed. **The installed desktop executable SHA256 differed from the compiled desktop executable SHA256**, so the strict build-to-installed-file source-provenance gate failed and both hash-manifest and installer upload steps were skipped. No verified installer artifact was published. No owner's PC was accessed.

Actual Tauri output: `Info Patching ...pilotodin-desktop.exe with bundle type information: nsis`. As Tauri 2.12.4 supports `--no-binary-patching`, this could explain the digest difference, but **the logs do not yet prove that hypothesis**. Documentation: https://tauri.app/reference/cli/ .

## Corrective Windows CI source change

The P4-only workflow uses a distinct Tauri app identifier `com.pilotodin.p4nativeqa`, leaving production `com.pilotodin.studio` and the owner's older install untouched. Latest [`bca3c57...`](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/bca3c57b94a425cd9ef489726e721328d12c2ead) changes only:

1. `.github/workflows/p4-native-windows-milestone.yml`: add `--no-binary-patching` for its one NSIS target and output actual compiled versus disposable-installed EXE SHA-256 digests and byte sizes.
2. `tests/test_p4_native_windows_milestone_source.py`: assert new flag, strict mismatch rejection and same app-identity separation.

The mismatch remains a **hard gate**. Neither a successful NSIS extraction nor successful backend smoke alone proves identical source-to-installed desktop bytes.

[Corrected CI run #42621192759](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/42621192759) **RUNNING when this document was created**. The workflow must **COMPLETELY SUCCEED**, including exact compiled/installed hash equality, before any SHA provenance manifest or QA installer can count as verified. A CI-successful installer still does not prove the owner's Windows installed WebView2 behavior or real-business suitability; those gates remain separately blocked/unverified. This is a source-and-build milestone, not a public release.

**No owner installation, original project, saved experiment, model-training action or data migration was performed.** The older local October 2026 PilotODIN installation remains outside this source-matched verification.
