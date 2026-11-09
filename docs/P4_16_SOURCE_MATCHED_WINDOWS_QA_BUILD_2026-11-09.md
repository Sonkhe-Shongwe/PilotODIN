# PilotODIN 1.0 | P4-16 Source-Matched Side-by-Side Windows QA Builder

## 9 November 2026 | P4-16 NSIS QA built, installed engine PASS, DESKTOP HASH MISMATCH; scoped corrective CI pending

- **Authority and exact latest source:** Owner said `next` following the P4-16 current-source native CI build. This continues bounded source-provenance troubleshooting, **not** permission to install anything on the owner's Windows PC, to handle real data, certify release, close P4 or start P5. Distinct QA identifier `com.pilotodin.p4nativeqa` continues to protect old installed `com.pilotodin.studio`. Latest corrective source [`bca3c57b94a425cd9ef489726e721328d12c2ead`](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/bca3c57b94a425cd9ef489726e721328d12c2ead).
- **Exact previous run is FAILURE, not pending:** [Windows QA #42615013119](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/42615013119) at `d9e561...` completed **FAILURE** at the final build-provenance gate, *after* successfully staging pinned offline Qwen3 and generating an authenticated completion, freezing/running the Python sidecar, compiling a **1.49 GiB separate P4 QA NSIS installer**, installing it onto a disposable GitHub Windows runner, and passing its bundled local backend auth/Origin/isolation smoke. **Compiled vs CI-installed desktop EXE SHA-256 mismatch**; manifest/installer upload steps skipped. No user installer can be accepted/downloaded from that run.
- **Evidence-based hypothesis, not proven root cause:** Actual Tauri build logs include `Patching ...pilotodin-desktop.exe with bundle type information: nsis`. Tauri CLI locked at **2.12.4** supports `--no-binary-patching` to suppress package-type executable patching. This is a documented option for single NSIS output, but **does not guarantee source-installed hash equality**; the mismatch must still be measured. See https://tauri.app/reference/cli/ and the P4-16 issue comments.
- **Correction:** Changes confined to `.github/workflows/p4-native-windows-milestone.yml` and `tests/test_p4_native_windows_milestone_source.py`. Build uses `npx tauri build --config src-tauri/tauri.p4-native-qa.conf.json --no-binary-patching`; source-safety contract verifies flag, unchanged app separation and strict SHA gate. Workflow now prints actual compiled/CI-installed EXE byte lengths and hashes before **failing closed** on any mismatch; it never relaxes this provenance control. No backend, P4 product logic, model, installed Windows executable or release changed.
- **Current corrected run:** [Windows QA #42621192759](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/42621192759) at `bca3c57...` **IN PROGRESS during this checkpoint**, with source checks, pinned model/Qwen3 stage passed and frozen sidecar packaging in progress. **Final installer/hash/CI installation/unpacked artifact NOT YET VERIFIED**. Confirm result and actual uploaded manifest before claiming acceptance. Older failed builds stay visible.
- **Phase boundaries:** P4-15 had scoped engineering/CI pass; current task is separate P4-16 **BUILD PROVENANCE ONLY**. Physical owner native WebView2/8 GB/offline tests **NOT TESTED**, and real label provenance, business decision/feature as-of-time/group-split/benefit/fairness **UNVERIFIED**. Master QA [#2](https://github.com/Sonkhe-Shongwe/PilotODIN/issues/2) OPEN; P4-16 [#9](https://github.com/Sonkhe-Shongwe/PilotODIN/issues/9) OPEN. **P4 ACTIVE, P5 NOT AUTHORISED, P8 NOT CERTIFIED**.
- **Next:** Once #42621192759 concludes, preserve its precise conclusion: if SUCCESS, check its installer and JSON SHA manifest separately before proposing one optional side-by-side owner milestone install; if FAIL, follow actual error and do not claim source-match. Do not request more old build ZIPs or ask owner to open old application for P4 acceptance.

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
