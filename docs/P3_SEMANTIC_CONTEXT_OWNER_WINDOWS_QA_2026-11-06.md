# PilotODIN P3-02 | Owner Windows semantic-context acceptance

**Prepared:** 6 November 2026  
**Gate:** P3-02 real owner Windows interaction; **PENDING OWNER EXECUTION**.  
**Phase:** P3 ACTIVE; P1/P2 CLOSED for bounded development; no installed/release certification.  
**Test scope:** A single controlled, synthetic, non-destructive Save/reopen/edit/project-switch/keyboard walkthrough. Never use a real owner's original dataset as the fixture.

## Current automated evidence (does not satisfy physical native acceptance)

- [Real Uvicorn + headless Chromium Playwright #42246639146](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/42246639146) at commit `7adb16f726b232863b73d6dbde17d8b91302f76d`: **1/1 PASS (8.6 seconds, one test)**. It proved two synthetic uploads, browser Save/reload/edit, project isolation, rejected stale dataset version, unchanged deterministic hypotheses/Quality history, two explicitly allowed POSTs and blocked unexpected remote/writes.
- Preserve initial [browser #42246390910 FAILURE](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/42246390910) at `8a15796c0b5a`: the test's fail-closed request guard expected `claim_amount` but the real editor defaulted new selection to the first field. The test was repaired to **explicitly select `claim_amount`**, and successful run followed. No production code/SQLite change was required for this test-fixture correction.
- [P1 isolated frontend #42246639107](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/42246639107) **SUCCESS** at `7adb16f726b2`. Earlier [P3 Python/Node/TS #42243211489](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/42243211489) and [P1 lifecycle #42243608383](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/42243608383) remain separately scoped PASS at their exact SHAs.
- **Not yet checked:** Actual owner Windows WebView2 rendering/focus/navigation, exact native developer-shell source SHA, installed Save As or release packaging. Do not mark owner PASS based on the CI result.

## Disposable CSVs and safe developer environment

1. In GitHub Desktop sync `feature/live-dev-workspace-20261023`; record the actual local HEAD using GitHub Desktop History or `git rev-parse HEAD`. Do not use the older installed 1.0 EXE as proof of the newly committed P3 UI.
2. Use the two tiny **repository-owned** files in `tests/fixtures`: [p3_semantic_owner_A.csv](../tests/fixtures/p3_semantic_owner_A.csv) and [p3_semantic_owner_B.csv](../tests/fixtures/p3_semantic_owner_B.csv). Each holds 20 **fully invented** records using `claim_id`, `claim_amount` and `policy_number`. Do not alter or import any real projects for this QA.
3. If using existing `Start_PilotODIN_Live_Dev.bat`, note that it opens **a browser preview** and writes to its separate `.pilotodin-dev-data` workspace, **not** the installed app's data. A PASS in that preview must be labelled **Windows browser developer PASS**, **not native WebView2 PASS**. If you already have a functioning native Tauri development shell, test the same synthetic flow in that shell and record its mode; do not create an installer or install new toolchains just for this gate.

## 6 November 2026 | P3-03a UI note
The current source also displays user field meanings in the tentative-role table, and places the system's domain/possible unique key beside the owner's domain/row descriptions. Verify they remain clearly labelled **unverified** in W1/W2. A guessed unique key does not confirm row meaning; there is no automatic semantic match or disagreement decision. This UI feature has real Chromium CI PASS [#42252331820](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/42252331820), but no physical owner Windows approval.

## Five narrowly scoped checks

| Check | Owner action | Required result |
| --- | --- | --- |
| **W1: Save A** | Import fixture A as a new disposable project. Open **Your data → Data dictionary and column investigation → Business meaning hypotheses**. Expand **Optional: describe what this dataset means**. Enter domain `Synthetic insurance case-handling records`, row meaning `One submitted synthetic claim per row`, click **Add field definition**, explicitly choose `claim_amount`, and enter `Amount requested for this synthetic claim`. Click **Save business descriptions**. | Button enabled only for meaningful inputs. A saved message appears and the **Owner-described business context** area displays the entered values separately from **UNVERIFIED** hypotheses. No automatic target, training or data correction. |
| **W2: Reopen/edit A** | Reload the page / revisit **Your data** without deleting the project. Expand **Review or revise your business descriptions**, verify existing values, edit the domain to `Synthetic insurance records for manual case review`, and save. | Existing text reappears before editing; revised text remains after another navigation/reload, with the **user-described/not independently verified** label still visible. |
| **W3: Isolate B** | Import fixture B as a separate disposable project. Navigate to its **Your data** panel. | B has **no** saved A context; it may show a similar deterministic hypothesis because the column names match, but must not show A's user-provided text. Switching back to A restores only A's description. |
| **W4: Keyboard and errors** | With the native shell (when available), use Tab/Enter/Space to expand the context editor, reach the text fields and Save button. Attempt to save a too-short field definition, then correct it. | Controls and focus remain usable; Save is unavailable for invalid text; error is not misleading and no invalid note is saved. Record any clipped controls, inaccessible action or lost input as a defect, not a PASS. |
| **W5: Version boundary** | Do **not** manufacture a destructive version change against a real project. Existing isolated CI already checks that stale expected-version GET/POST return 409. On owner Windows, simply verify ordinary A/B switch is correct. | No stale note silently appears in B. Real version-change GUI behaviour remains **outside this manual step** unless a separate safe approved Quality version fixture is available. |

## Evidence/reporting instructions

- Share a screenshot showing A's two separate sections (tentative **UNVERIFIED** hypothesis and **user-described/not independently verified** saved text), and a screenshot of B with no A description. A short text report is sufficient for reload/edit and keyboard observations. Never include original datasets, user identifiers, machine secrets, or complete local paths.
- Include mode **native Tauri WebView2 / Windows browser preview**, branch HEAD and **PASS/FAIL per W1–W4**. W5 automatic version test remains independently PASS; do not claim physical real-version behavior. A failing check should include which button/field was used and visible error text, not an invented issue classification.
- Leave synthetic projects in the isolated developer workspace or archive them using existing non-destructive project-management tools. **Do not permanently delete any projects**; permanent deletion is not authorised or implemented.
- **Acceptance rule:** Real hosted browser PASS is already recorded. Mark **owner-native P3-02 ACCEPTED** only after owner supplies genuine WebView2 test evidence (not just browser mode). P3-03 and final P3 development closure still require separate scope and owner decisions.
