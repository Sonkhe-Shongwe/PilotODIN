# P3-04 W5 | Automation-first Windows native Quality acceptance

**Date:** 6 November 2026  
**Branch:** `feature/live-dev-workspace-20261023`  
**Source implementation:** [`ded194f10e21`](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/ded194f10e210d1ff9003b22285698f046be98a7)  
**Focused assertion correction:** [`4862e0ee23b1`](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/4862e0ee23b1d5bc4203249906846845127909d4)  
**Disposition:** SOURCE/FOCUSED TESTS VERIFIED. **Physical owner Windows WebView2 W5 NOT TESTED.** P3 stays active. Not full installer, P3 closure, P4 or release acceptance.

## Implemented bounded W5 route

A distinct, dev-only native W5 identity `com.pilotodin.p3qualityw5qa` and entry `p3_native_quality_w5_qa.html` use the existing UnifiedShell/Quality and Your data workspaces. The tester double-clicks [Run_PilotODIN_P3_Native_Quality_W5_QA.bat](../Run_PilotODIN_P3_Native_Quality_W5_QA.bat) in the clean, authorised source checkout. This is **not** the older W1–W4 editor QA runner; earlier W1–W4 native acceptance remains intact.

The preflight requires Windows, clean authorised branch, existing .venv-live Python, node_modules, npm, cargo and free 8000/5178 loopback ports. It never installs dependencies, checks out a new branch, discards/stashes owner work, touches installed projects, starts AI or builds an installer. A fresh isolated `qa_foundation.py` run under the existing DevQA root holds a generated 36-row CSV. Two Region values have surrounding spaces and exact unverified owner-described **synthetic** version-zero metadata is stored separately. The seeder checks project identity, source bytes, initial version, exact eligible whitespace issue and context.

The native UI hard-blocks non-allowlisted requests and all but one exact `operation=approve`, `expected_version=0`, preselected `issue_id` Quality proposal. The proposal response must be from the matching synthetic project, must report two changed cells and a valid receipt; then, and only then, one exact receipt-ID/hash Quality commit is allowed. Both allowances are consumed **before** network requests and the write budget survives page refresh. Refresh during an unfinished approval invalidates the in-memory receipt and therefore safely requires a fresh isolated run. Nothing in the test creates production editing privilege, and no automatic consent is granted: the owner must click the actual review/approval UI.

After the native window closes, PowerShell automatically verifies exact v1, history [v0,v1], absent old context on v1, stale v0 semantic GET+POST HTTP 409, two precise Region rows (immutable original versus committed working data), source SHA-256 unchanged, and a strictly ordered access-log audit: **one 200 proposal, one 200 Quality commit, one 409 intentionally rejected stale semantic POST**, with no other backend mutation. A single owner yes/no confirmation records whether physical WebView2 visibly showed current v1 and no prior semantic notes. The QA outcome remains `REVIEW_REQUIRED` and `product_acceptance=NOT_TESTED` even if all scoped checks pass. The test-owned Uvicorn PID is stopped in finally and process-level environment is restored. The generated status-only ZIP includes the result and two manifests, not the synthetic CSV, draft content, private database or raw logs.

## Exact minimum owner interaction once the source is synced

1. Review any uncommitted local GitHub Desktop changes without discarding them; use a clean checkout of the authorised branch.
2. Double-click `Run_PilotODIN_P3_Native_Quality_W5_QA.bat`. The runner stages synthetic data, compiles the existing frontend and starts a separate native development window.
3. In Quality, select **Region / Surrounding whitespace**, then **Review this correction**. Inspect the exact dialog, then click **Approve these changes**. This is an explicit consent action **only on the isolated synthetic project**.
4. Confirm native Quality shows **WORKING VERSION 1**, and **Your data** contains no old v0 owner descriptions. Close the window; answer the one native observation prompt. The remaining integrity, API/permission and evidence checks are automatic.
5. If the runner reports a passing synthetic result, submit its **status-only** `-p3-w5-status.zip` for independent QA disposition. Keep the result as REVIEW_REQUIRED until inspected. If blocked, use the precise failure category instead. Do not rerun accepted W1–W4.

## Actual automated source verification

| Source | CI run | Actual observed result | Boundary |
| --- | --- | --- | --- |
| `ded194f10e21` | [P1 isolated #42288574987](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/42288574987) | **COMPLETED SUCCESS**: 160/160 Node; TS/Vite PASS; 5/5 Chromium PASS | General frontend compatibility, not physical native W5 |
| `ded194f10e21` | [Build E Windows compile #42288574715](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/42288574715) | **COMPLETED SUCCESS**: Windows Rust/Tauri dev-profile compile, with intentional compile-only invalid assets | No native QA UI launched, no installer or shippable package |
| `ded194f10e21` | [P3 focus #42288574728](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/42288574728) | **COMPLETED FAILURE**: 32/33 Python passed; new Quality CORS test incorrectly asserted HTTP 403 for an unknown project at a disallowed origin, actual route returned 404 without CORS allow-origin. Windows PowerShell parser PASS | Static test expectation error, not a mutation or loss. Retain this failure history |
| `4862e0ee23b1` | [P3 focus #42288768189](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/42288768189) | **COMPLETED SUCCESS**: 33/33 Python; 11/11 Node; TS/Vite PASS; **both P3 PowerShell scripts parse on Windows-2022** | Corrected CORS assertion checks actual absent allow-origin; no real native window or owner W5 |

The latest source change after the original frontend/Tauri green builds is limited to the source test assertion. This correction was followed by the passing focused Python, Node, TypeScript/Vite and PowerShell workflow. It does not imply a new Tauri compilation at the test-only commit.

**Important distinction:** [Prior real-Uvicorn Chromium W5 #42282095666](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/42282095666) already passed 2/2 full synthetic browser scenarios at `805fb658`. The new runner prepares a **separate physical native** proof without pretending an automated Chromium run can certify WebView2. W1–W4 prior physical owner acceptance is not repeated.

## Remaining decisions and phase boundary

- Native W5 owner test and independent status ZIP review: **PENDING**, do not mark passed before evidence exists.
- P3-03 broader semantic truth/adjudication and phase closure-matrix scope: **owner decision remains open**. No automatic agreement, confirmation of owner text or model/target propagation was added.
- P3 active; P1/P2 bounded development closed; P4 not authorised; P8 offline Windows release not certified.

## Automated review of the future status-only archive

A second safety layer, [`tools/Verify_P3_Native_Quality_W5_Status.py`](../tools/Verify_P3_Native_Quality_W5_Status.py), is now implemented and source-tested. It is entirely read-only, standard-library Python, with no extraction, application launch, Git mutation or access to datasets. To review a **completed** W5 run's archive, use:

```powershell
python tools/Verify_P3_Native_Quality_W5_Status.py "C:\path\to\P3-NATIVE-QUALITY-W5-...-p3-w5-status.zip" --expected-source EXACT_40_CHARACTER_GIT_SHA
```

Supply the correct independently checked local source SHA, not a guessed SHA. An archive from a failed run yields `NOT_ACCEPTED`; an unexpected or corrupted archive yields `REFUSED`. Even a good archive reports `STATUS_ARCHIVE_INTEGRITY_PASS`, with `owner_native_observation=OWNER_REPORTED_PASS_NOT_INDEPENDENTLY_OBSERVED`, `native_acceptance=PENDING_INDEPENDENT_REVIEW`, and `product_acceptance=NOT_TESTED`. Check real owner Windows evidence and source provenance separately. Never relabel an archive verification as automatic native acceptance.

**Exact source CI:** [P3 #42291865357](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/42291865357) **COMPLETED SUCCESS**, 55/55 Python (including hostile/corrupted ZIP and false-PASS tests), 11/11 Node, TS/Vite and Windows PowerShell parser at [`b74c61a03ec3`](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/b74c61a03ec32ad39dc95bb7135cea9564773b32). This is no new physical WebView2 W5 observation.

## 6 November 2026 | P3 W5 native acceptance now checks historical v0 note retention
- **Specific acceptance gap:** The earlier native W5 runner proved **v1 does not inherit v0 descriptions**, but did not independently assert that **the original v0 descriptions remain stored after Quality approval**. The existing synthetic backend test covered that invariant, not the new native runner's own database.
- **Bounded implementation:** [Source `11c30a3514e7`](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/11c30a3514e7809cffa0cf6eaa8fe6086f59ad3b) adds `tools/Verify_P3_Native_Quality_W5_History_Local.py`. It checks the **fresh disposable W5 SQLite database in read-only mode** after the reviewed Quality v0→v1: one synthetic project; exact Quality versions [0,1]; exact original v0 domain, record-grain and `claim_amount` meaning; and **no v1 semantic-context row**. It refuses missing/modified original descriptions, stray newer notes, wrong workspace or unexpected version. The native runner requires `historical_semantic_context=PASS_V0_RETAINED_V1_ABSENT` before a REVIEW_REQUIRED result; the offline ZIP verifier requires the same field. No production app, source CSV, true user metadata, model or installer altered.
- **Exact verification:** Initial first run [#42293463414](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/42293463414) was **CANCELLED by a subsequent workflow correction**, not passed. [CI path-filter/compilation correction `9fc132254c25`](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/9fc132254c2529643a1cec55c23ef0273636f093) fixed a concatenated YAML path entry. [P3 focused #42293523261](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/42293523261) **COMPLETED SUCCESS at `9fc132254c25`**: 62/62 Python, 11/11 Node, TypeScript/Vite build PASS and Windows PowerShell parser PASS. Python tests include a real isolated Quality proposal+commit and deliberate synthetic missing/altered/accidentally migrated metadata. These are **not physical Windows WebView2 observations**.
- **Still required:** Actual owner-native W5 run and independent status-only ZIP review. Existing native W1–W4 remain accepted; no further W1–W4 retest. P3-03 adjudication/phase scope and owner matrix freeze open, P3 ACTIVE, P4 NOT AUTHORISED, P8 NOT CERTIFIED.


## One-run local ZIP self-check (6 November 2026)

The Windows W5 launcher now automatically invokes the existing **read-only** status-only ZIP verifier after creating the archive, using the Git HEAD attested earlier by its clean-checkout preflight. A successful launch-run exit requires both the native-scoped checks and the archive self-check, including the exact `STATUS_ARCHIVE_INTEGRITY_PASS` result, source SHA match, and preserved `PENDING_INDEPENDENT_REVIEW` and `NOT_TESTED` flags. An invalid ZIP changes the recorded runner outcome to blocked and produces a diagnostic-only replacement ZIP where possible. A failed archive creation exits with error. This removes the need to run the verifier manually after the launcher, but **does not replace independent owner Windows evidence review** and does not authorise P3 closure, P4, or release certification.

## 8 November 2026 | Native W5 clean-source preflight supports expected untracked Tauri outputs

Owner Windows screenshot confirmed a W5 preflight block from `?? frontend/src-tauri/Cargo.lock`, `?? frontend/src-tauri/target/`, followed by `?? frontend/src-tauri/gen/`. The owner already preserved Cargo.lock and target outside the repository; the remaining gen directory is **not** evidence of a broken Quality workflow. This is a build-artifact/worktree preflight mismatch, not native W5 acceptance.

The W5 runner now checks `git status --porcelain --untracked-files=normal` and allows **only** these three exact `??` untracked Tauri artifact paths while still rejecting all tracked, staged, deleted, modified or other untracked changes. It does not remove, stash, restore or conceal anything and does not modify global `.gitignore`. The run records `TRACKED_CLEAN_EXPECTED_UNTRACKED_TAURI` rather than claiming an entirely clean worktree when these artifacts are present; the independent status-only ZIP verifier recognises that narrowly scoped value. `Cargo.lock` remains visible for future intentional dependency-lock review, not silently ignored globally.

**Owner action after syncing this commit:** No further generated-directory moves. Confirm the expected branch in GitHub Desktop, fetch/pull the updated branch while preserving all local changes, then double-click `Run_PilotODIN_P3_Native_Quality_W5_QA.bat`. If the runner finds any *other* source changes it must still stop safely. The actual native W5 test and independent owner evidence remain pending; W1–W4 already accepted, P3 active, P4 unauthorised, P8 not certified.

