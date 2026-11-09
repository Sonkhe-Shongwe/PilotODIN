# PilotODIN 1.0 | P4-16 Windows QA Installer: Verified Source-to-Installed Provenance

## 9 November 2026 | Owner-native QA identity confirmed; empty-catalogue phantom archive banner found and source-fixed

- **Real owner's Windows observations:** Verified after local install that the old production desktop EXE remained **11,475,968 bytes / SHA256 `b2b18c070214ca92c6f1513c39d1526a7a9ac821c5043c2fe09f7e8e7da63d9`** (same as pre-install owner baseline), while separate `pilotODIN-P4-Native-QA` installed desktop EXE was **12,265,984 bytes / SHA256 `7173b9c0e68295cca6bdf283daf8e61a86934d0575fac9915aea48bc9c009633`**, identical to the earlier exact-source Windows CI #42621192759 compiled/CI-installed EXE. Separate QA local data directory present; original user data backed up independently before install (320 files, 77,897,688 bytes; source/destination counts/bytes matched, individual per-file hashes/restore not tested). Distinct install folder also observed. This proves installed **desktop binary provenance and initial side-by-side file separation**, not full unchanged-project restoration, native workflow acceptance or resource safety.
- **Owner-observed P4-16 UI finding:** Desktop window opened and rendered Home/rail/project UI. On an actually empty QA catalogue showing `No projects imported yet`, the yellow `This project was archived in another window` banner appeared and **recurred after closing and reopening QA app**. Source root cause is `heldArchivedRef.current===mountedId` true when both IDs are empty strings, even though there is no mounted project or verified archive. **False positive in empty-catalogue case**, not evidence that a real user project was archived. [Owner evidence and source finding: Issue #9](https://github.com/Sonkhe-Shongwe/PilotODIN/issues/9#issuecomment-6748726378); [master QA #2](https://github.com/Sonkhe-Shongwe/PilotODIN/issues/2#issuecomment-6748725434).
- **Bounded source hotfix and its red history:** First source [`9e6b39b`](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/9e6b39bac32ec60582b612cfeeac9600da57d264) added non-empty guard + three synthetic regression tests, but **CI FAILED** because an indentation-sensitive edit omitted the guard's local declaration. P1 frontend #42679079345: 162/163 source contracts; P2 report export #42679079261: TypeScript TS2304. Neither failure was overwritten or called green. Corrected commit [`84e589c`](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/84e589cd15a254d70e178135f9ee79405de321c4) inserts the missing variable and retains all archive safeguards for genuine non-empty matching IDs.
- **Exact corrected-source CI VERIFIED:** [P1 Isolated Frontend #42679384181](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/42679384181) **COMPLETED SUCCESS**, **163/163 Node tests**, TypeScript/Vite build **PASS**, **5/5 Chromium** isolated scenarios PASS. Adjacent [P1 real-HTTP #42679383988](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/42679383988), [P2 saved revision #42679384009](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/42679384009), and [P2 export safety #42679384414](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/42679384414) all **COMPLETED SUCCESS** at corrected SHA. This verifies source-level/no-owner-data CI; **NOT** a new Windows NSIS build/installation or physically retested corrected banner.
- **Owner next step, no more installer:** The previously installed QA app still contains the older pre-fix source `bca3c57...`; its cosmetic banner may persist until a later justified native build. **Only in the observed empty-project state**, ignore the false archive banner and import `p4_classification.csv` from the already extracted synthetic QA kit as a NEW QA-only project. Inspect **Prepare → Potential prediction opportunities**, no training or real-data access. Do not restore/archive any project or delete data to make the warning disappear. Do not call N1–N10 or real-business Gate C verified without observed tests.
- **Phase control:** P4 ACTIVE, N1–N10 substantive functionality not fully observed, operational source/label/decision evidence UNVERIFIED, P4 closure PENDING, P5 NOT AUTHORISED, P8 NOT CERTIFIED. QA Issue #2 and Issue #9 remain OPEN.


## 9 November 2026 | Owner authorised one controlled P4-16 Windows QA acceptance session; actual owner observations still NOT TESTED

- **New explicit owner decision in chat:** Owner answered `yes lets continue` to the immediately preceding request for **one-time testing of the separately identified PilotODIN QA application on the owner's Windows PC**. Scope: one *manual, observed* milestone of the distinct `pilotODIN-P4-Native-QA` / `com.pilotodin.p4nativeqa` build after checking the trusted artifact identity, with disposable synthetic projects. This is **not** approval to replace/uninstall the older `pilotODIN` / `com.pilotodin.studio`, overwrite personal projects/data, train models, bypass Windows trust warnings, publish a release, close P4, or start P5.
- **Verified live artifact availability:** [Windows Actions #42621192759](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/42621192759) remains `completed/success` at exact `bca3c57b94a425cd9ef489726e721328d12c2ead`. GitHub returned QA installer ZIP artifact **13678755031**, `expired=false`, expires **12 Nov 2026 13:19 UTC**, and independent provenance ZIP **13677687251**, `expired=false`, expires **16 Nov 2026 13:19 UTC**. These are **CI assets, not a product release or an observed owner installation**.
- **Source safety review:** `frontend/src-tauri/tauri.p4-native-qa.conf.json` changes product name and Tauri identifier, while `frontend/src-tauri/src/lib.rs::launch_backend` uses `app.path().app_local_data_dir()/data` for `PILOTODIN_HOME`. This suggests separate app-local data identities, **but does not independently prove the Windows installer path, registry coexistence or physical owner storage isolation**. The existing `desktop/Verify_Installed_PilotODIN.ps1` is a **disposable CI-only silent installer** and must **not** run on the owner's PC.
- **Owner procedure / stop conditions:** Download both artifacts manually from that exact trusted run, independently verify manifest origin and the extracted QA NSIS **1,594,498,057 bytes** SHA256 `a38018dbe981c4269857a1e3ca87ecc98e54ca39cba40eebd792516af5b0e174` using the existing **read-only** `qa/p4_native/verify_qa_installer_provenance.py` or Windows Get-FileHash. Record old installed EXE path/hash and protect saved project backups before installation. **Stop** for a mismatched hash/name, attempted overwrite of the old app/storage, unexpected elevation or Windows trust/antimalware warning until specifically reviewed. Do not suppress security protections. Manually install QA only into a clearly **different** path if the installer permits; no unattended `/S` installer. If separation cannot be established, mark BLOCKED rather than guessing. After installation record installed QA EXE hash (expected `7173b9c0e68295cca6bdf283daf8e61a86934d0575fac9915aea48bc9c009633` from CI) and compare old original EXE hash, then conduct [N1–N10](https://github.com/Sonkhe-Shongwe/PilotODIN/issues/9) with disposable P4 fixtures, avoiding Model Lab fitting.
- **Actual outcome today:** Artifact state verified; *no local Windows execution or manual test observations supplied*. Owner-native N1–N10 remain **NOT TESTED**; side-by-side isolation / physical 8 GB offline operation **NOT TESTED**; real decision/label/timing/group/baseline/fairness evidence **UNVERIFIED**. Master QA #2 and owner evidence Issue #9 OPEN; P4 ACTIVE; P4-17 owner phase close PENDING; P5 NOT AUTHORISED; P8 NOT CERTIFIED. The next meaningful step is for the owner to perform the first SHA check and present the observed output; only real observations can advance acceptance.


## 9 November 2026 | Hosted synthetic P4 verifier test registration PASS

At [workflow registration commit `9688862237ec39c8191b4e072c55f13eb0e68f14`](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/9688862237ec39c8191b4e072c55f13eb0e68f14), the existing P4 CI now explicitly runs `tests/test_p4_installer_provenance.py`. [Ubuntu P4 run #42634879419](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/42634879419) **COMPLETED SUCCESS** with **96/96 Python**, **27/27 Node**, build PASS and **8/8 disposable real-HTTP Chromium**. The 21 checksum tests use invented small non-executable bytes. They are **not an observed hash match against the real ~1.59 GB NSIS**, not a new Windows QA build and not installed owner's Windows acceptance. Previous Windows runner source-matched build #42621192759 remains the **separate** earlier `bca3...` pass. Physical side-by-side Windows, offline 8 GB and business evidence remain NOT TESTED/UNVERIFIED.


## 9 November 2026 | Additional read-only owner QA integrity-check preparation

At [P4 checker code commit `92c6cf31582994abb514bd8517fe4cb29b08b4d1`](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/92c6cf31582994abb514bd8517fe4cb29b08b4d1), new `qa/p4_native/verify_qa_installer_provenance.py` checks a **previously downloaded and extracted** QA NSIS file against a **separately independently sourced** JSON manifest. The helper validates the exact owner-supplied expected commit, the two different QA/production identities, positive CI-installed engine and executable-match flags, strictly false owner installation/release flags, installer name, byte size and streamed SHA-256. It does not unpack, run or install the EXE, fetch the manifest, touch projects or verify any real Windows workflow.

Run only as an optional **pre-install, read-only check** after obtaining the manifest from [verified run #42621192759](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/42621192759) by independently checking its origin:

```powershell
py qa/p4_native/verify_qa_installer_provenance.py --manifest "C:\\QA\\source-and-windows-artifact.json" --installer "C:\\QA\\pilotODIN-P4-Native-QA_1.0.0-alpha.1_x64-setup.exe" --expected-source bca3c57b94a425cd9ef489726e721328d12c2ead
```

**Synthetic verification only:** 21/21 local pytest checks PASS; `compileall` PASS; no real installer bytes were supplied, downloaded, hashed or installed during this increment. The current GitHub code blob was checked against tested local bytes; **subsequent scoped P4 CI at `968886...` passed the helper's synthetic tests, but no new Windows installer or owner native acceptance**. A PASS means *only supplied-manifest-to-file integrity*, not provenance authenticity, installed-app equality, native UI, side-by-side coexistence, 8 GB, business suitability or release. Owner-native acceptance requires an independently approved milestone test; Issue #9 and master QA #2 remain OPEN.


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
