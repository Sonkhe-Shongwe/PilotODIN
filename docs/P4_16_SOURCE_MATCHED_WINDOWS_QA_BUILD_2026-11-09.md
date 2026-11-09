# PilotODIN 1.0 | P4-16 Source-Matched Side-by-Side Windows QA Builder

**Created:** 9 November 2026  
**Current build source:** [`d9e56148bc41cf396fedc52819019575c4f481bd`](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/d9e56148bc41cf396fedc52819019575c4f481bd)  
**Windows CI:** [#42615013119](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/42615013119)  
**Source-only Rust compilation:** [#42614732208](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/42614732208)  
**Milestone evidence:** [Issue #9](https://github.com/Sonkhe-Shongwe/PilotODIN/issues/9)

## Owner scope and isolation

The owner has an older 22–23 October 2026 local `pilotodin-desktop.exe`/analytical engine installation under `AppData/Local/pilotODIN`, as visible in their screenshot. The owner said `okay next` after the proposal to prepare a **current-source QA Windows build without touching the older installation**. This scope does not authorise installing, uninstalling, replacing the app, altering existing user storage or training models.

The QA Tauri overlay has **`identifier=com.pilotodin.p4nativeqa`** and **`productName=pilotODIN-P4-Native-QA`**, versus old `com.pilotodin.studio`. It inherits the real offline AI bundle, Python engine and NSIS packaging settings from the original Tauri config. This is a distinct QA identity, **not** evidence of a safe human install until the final installer and file identities are verified.

## Windows runner source-to-binary chain

The new, source-triggered [workflow](https://github.com/Sonkhe-Shongwe/PilotODIN/blob/feature/live-dev-workspace-20261023/.github/workflows/p4-native-windows-milestone.yml):

1. Checks out the exact `GITHUB_SHA` on trusted development branch with no persisted credentials, verifies separate app identity.
2. Runs **three** stdlib Python source-safety checks without extra test dependencies.
3. Stages the pinned offline GGUF Qwen3 and llama.cpp runtime, verifies asset checksums/licence notices and **actual authenticated local completion on the Windows runner**.
4. Uses existing sidecar builder and real Windows backend loopback-authenticated smoke test, then builds a Tauri NSIS installer under the separate QA identifier.
5. If the NSIS exists and is plausible, installs **only on a disposable GitHub runner** with the existing verifier, checks an actual installed engine, checks compiled-versus-installed desktop EXE SHA-256, and emits a `source-and-windows-artifact.json` with exact source SHA, installer name/size/digest and runtime binary digests.
6. Publishes provenance separately from a short-lived **unsigned, NOT-RELEASE QA installer** artifact. Neither artifact alone is owner native acceptance. No changes to the old local installed app are possible through this CI workflow.

## Observed CI results at initial documentation checkpoint

| Evidence | Actual result |
| --- | --- |
| First [#42614732584](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/42614732584) at source `d9c71e9...` | **FAILED** at standalone source-check stage: no `pytest` installed on runner; did **not** build installer |
| Corrective [`d9e561...`](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/d9e56148bc41cf396fedc52819019575c4f481bd) | Replaced external pytest invocation with stdlib `runpy` of the same three source contracts |
| Second [#42615013119](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/42615013119) | Source contract, pinned AI asset stage, real authenticated Windows Qwen3 completion and frozen engine smoke **PASS**. NSIS compilation **IN PROGRESS at this checkpoint** |
| Compile-only [#42614732208](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/42614732208) | **COMPLETED SUCCESS**, intentionally invalid staged placeholders, **NOT** a runnable Windows installer |
| Final NSIS, installer hashes, CI installed engine/hash, GitHub Actions artifact | **PENDING FINAL RUN VERIFICATION**, no success claimed |
| Actual owner-installed source SHA, Windows WebView2 P4 flow, 8 GB/offline behavior | **NOT TESTED**, no owner PC modified |
| Real outcome meaning/label provenance/time/group split/business value | **UNVERIFIED** |

## Next gate and phase limits

Once the final CI result is actually known, record the source commit, output digest and CI installation result in [Issue #9](https://github.com/Sonkhe-Shongwe/PilotODIN/issues/9). **If the installer compilation fails, do not offer an installer download and do not mark native acceptance passed.** If successful, the still-needed owner's source-matched Windows WebView2 walkthrough should use disposable synthetic projects only and must be authorised separately. Keep the older installation untouched and maintain the user's preference for a single milestone rather than recurring downloaded test ZIPs.

P4 is ACTIVE; P1/P2/P3 development CLOSED; P5 NOT AUTHORISED; P8 NOT CERTIFIED. Master QA #2 remains OPEN.
