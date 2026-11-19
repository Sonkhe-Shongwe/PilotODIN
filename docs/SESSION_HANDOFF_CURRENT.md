# PilotODIN 1.0 | Current continuation checkpoint

**19 November 2026.** Work on `feature/live-dev-workspace-20261023`. **P4 Target Intelligence is active at 14 of 20 checks (70%).** P1 through P3 have bounded development closure records. P4 closure requires owner signoff after the remaining engineering gates. [Scorecard](./PROJECT_STATUS_CURRENT.md#p4-engineering-scorecard) · [Phase policy](./PHASE_FOCUS_AND_CLOSURE_POLICY_2026-10-28.md) · [Documentation index](./DOCUMENTATION_INDEX.md)

## Engineering progress and next checkpoints

The official P4 score is **14/20 (70%)**. Each bar below counts evidenced checkpoints in that workstream. A filled circle marks a completed checkpoint at the stated scope. Percentages are rounded from the counts. Workstream percentages guide the next work, and acceptance points come from the [P4 scorecard](./PROJECT_STATUS_CURRENT.md#p4-engineering-scorecard).

| Workstream | Checkpoints complete | Evidence so far | Next checkpoints |
| --- | --- | --- | --- |
| Firewall preflight | ●●○ **2/3 (67%)** | Rule and cleanup prepared. Synthetic decisions and Windows command parsing passed. [CI](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/44476232855) | Verify external TCP works before and after the temporary block, is denied during it, and local TCP works throughout. **Awaiting separate approval.** |
| Desktop network isolation | ●●○ **2/3 (67%)** | The retest matched three WebView loopback connections to known Tauri close requests. A backend same-process pair and three non-loopback Edge service connections remain. [Hosted result](#19-november-2026--hosted-webview-storage-and-ipc-retest) | Establish the backend socket purpose and review an enforcement candidate for non-loopback traffic. Live firewall enforcement requires separate approval. |
| File-mutation coverage | ●●●○ **3/4 (75%)** | The retest still recorded four ambient-temp creates. All twelve user-local operation events fell into `other-user-local`; the specific destination families remain unknown. [Hosted result](#19-november-2026--hosted-webview-storage-and-ipc-retest) | Establish the writer's actual ambient-temp path mechanism and a discriminating destination category before another full app run. |
| QA dialog driver | ●●● **3/3 (100%)** | Both dialog actions passed in the fixture. The app audit recorded zero driver outside-scope operations, versus six writes and six overwrites in the prior audit. This completes the scoped driver measurement checkpoint. [Hosted result](#19-november-2026--hosted-same-capture-app-audit) | Track the 43 unresolved driver write paths under file-mutation coverage. |
| N12 acceptance | ○○ **0/2 (0%)** | The approved retest completed and reported filesystem **FAIL**, network **FAIL**, coverage **BLOCKED**. [Hosted result](#19-november-2026--hosted-webview-storage-and-ipc-retest) | Pass calibrated filesystem and network acceptance. Either pass earns five P4 points. Both earn ten. **App workflow disarmed.** |
| Physical 8 GB offline inference | ●○○ **1/3 (33%)** | Bundled Qwen answered on hosted Windows. Physical startup was deferred on memory headroom. At simulated 0.936 GiB, Ask ODIN returned the verified filtered median after model deferral. [Physical checkpoint](#18-november-2026--ordinary-laptop-headroom-blocked-the-qwen-baseline) · [Fallback fix](#19-november-2026--keep-verified-answers-when-ask-odin-defers-the-model) | Measure an offline option at ordinary laptop headroom before proposing a physical retest. Then verify a bundled answer and coexistence. |
| Original app-data preservation | ○○ **0/2 (0%)** | The historical full-tree test failed with 74 differences and an unknown writer. [R06 worklist](./P4_80_ACCEPTANCE_WORKLIST_AND_EVIDENCE_INTAKE_2026-11-12.md#c-r06-non-intrusive-incident-evidence-intake) | Record an evidence-backed disposition of the historical incident. Then establish prospective preservation in a separately approved owner-device run. |

In each continuation update, show the official score, the previous and current count for any workstream worked on, the evidence that moved it or the blocker that held it, and the next checkpoints. Show completed and upcoming workstreams together. If a denominator changes, explain which checkpoints changed and why.

## Next engineering action

Keep WebView2 filesystem isolation the active work. The focused probe now resolves aliases and session subdirectories for its user-temp control. Check that resolution on the hosted runner before another source-pinned capture. The diagnostic will still target the four user-temp creates and the twelve user-local events from the earlier full audit. [Temp correction](#focused-probe-hosted-temp-correction) · [Focused run result](#focused-webview2-probe-blocked-on-runner-temp)

### Focused probe hosted temp correction

Validate the resolved local `TEMP` against the canonical hosted user-temp and runner-temp roots, including their session subdirectories. The generated control and the focused reporter use that same resolved path. Paths outside those roots still block. Reuse this check in routine Windows CI and at the start of the focused workflow, before dependency setup, native compilation and collector provisioning. The synthetic tests cover nested temp, an alias and an unrelated sibling; the scoped hosted check is read-only. [Path check](../qa/p4_research/n12_webview_storage_probe.py) · [Disarmed workflow](../.github/workflows/p4-n12-webview-storage.yml)

At source `e3a5e50c15f0eb8ac875e5fe1968bc4ed784637d`, the read-only hosted temp preflight and the nine focused tests passed on Windows. All four [routine P4 CI jobs](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/44563738207) passed. Local verification covered 63 passes and four Windows-only skips. The rerun of the live diagnostic still needs a fresh source-pinned approval. No acceptance check moved. [Hosted preflight](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/44563738207/job/135699723863)

### Focused WebView2 probe blocked on runner temp

The one approved Windows Server 2022 attempt ran from launch `2ca90fe5731532fe44a1f221d8eb5f08c2ba701f` at source `4d8c20bc91d1ce45122bc39baf9102b8203bb4e8`. The seven generated focused checks, driver preflight and one unpackaged build passed. Executable SHA-256 `dec2194d8c062b899910c12bd433b67a5dc8330fb2b09b7976b8dc846e641316`. The runner verified Sysmon 15.22 and Process Monitor 4.13. The job **FAILED** at `webview-storage-launch-and-controls`, when the prep code rejected the inherited temp directory. The condition combined a literal equality check against two expected roots with a resolved-path equality check. The report does not establish which comparison failed. Neither control write nor the app launch ran, so the diagnostic is **BLOCKED BEFORE STARTUP**. Earlier full N12 evidence remains current. The approval is consumed and the workflow is disarmed. [Job log](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/44561741364/job/135692573711) · [Approval marker](../qa/p4_research/N12_WEBVIEW_STORAGE_PROBE_APPROVAL.txt)

The [routine P4 run on the launch commit](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/44561741031) passed three jobs. Its synthetic Windows job stopped early because the independent PID close-status fixture window did not open. The Windows workflow at the reviewed implementation source passed previously. File-mutation coverage is **3/4 (75%)** and P4 is **14/20 (70%)**.

### Focused WebView2 probe prepared

The probe reuses the existing startup and graceful-close driver and the full journey's WebView2 environment settings. Its two generated file controls bracket the app activity. It reads the pinned Process Monitor CSV and Sysmon process records to associate successful file operations with a component, phase and path family. It records the runtime version from the verified process image path. The CSV supplies directly observed path events. It has no call stack, and any unrecognised app-data family remains unclassified. The covered result is diagnostic only. [Reducer and launch](../qa/p4_research/n12_webview_storage_probe.py) · [Generated cases](../tests/test_p4_n12_webview_storage.py)

The generated cases cover a reproduced render-process create, a recognised local app-data family, no reproduction, failed or wrong-identity controls, an ambiguous PID, wrong app digest, an in-window write to the immutable CSV and missing one-use consent. The focused capture workflow is disarmed. Its proposed approval is for one GitHub-hosted Windows Server 2022 attempt at the reviewed source, one unpackaged build, one startup and graceful close, the pinned Sysmon and Process Monitor collectors, and the two disposable control writes. A successful diagnostic reports a reproduced event with writer, stage and destination. **INCONCLUSIVE** preserves the earlier full-run failure. [Disarmed workflow](../.github/workflows/p4-n12-webview-storage.yml)

At source `f6b9a395ccf06aa435b4e988f9b94a079d97bbcd`, the seven focused tests passed. The five local suites recorded 61 passes and four Windows-only skips. [Routine P4 CI](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/44560859075) passed all four jobs, including PowerShell parsing and the generated focused suite on Windows. The [separate synthetic Windows FileIO integration](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/44560859079) also passed. The focused live capture is **NOT RUN**. File-mutation coverage is **3/4 (75%)** and P4 is **14/20 (70%)**.

### WebView2 filesystem isolation plan

**Decision to resolve.** Which component makes the file creates under user temp, at what stage, and what determines that destination? The last hosted report assigned all four to the `webview` role with writer `webview2` and destination `user-temp`. It recorded the twelve local app data events as four creates, four overwrites and four writes under `other-user-local`. The published report lacks per-event paths and component evidence, and GitHub retained no raw trace. [Hosted evidence](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/44554198359/job/135665715135)

The launcher uses a disposable `WEBVIEW2_USER_DATA_FOLDER` and sets `TMP`, `TEMP` and `TMPDIR` on the app environment. The generated Win32 child test verifies the launcher's environment with `GetTempPathW`. WebView2 has separate browser, renderer and helper processes. Its user data folder covers browser data, and the generated child result leaves the WebView2 writer and its temp-path mechanism open. [Launcher](../qa/p4_research/n12_app_journey.py) · [Child control](../tests/test_p4_n12_exit_corroboration.py) · [WebView2 process model](https://learn.microsoft.com/en-us/microsoft-edge/webview2/concepts/process-model) · [User data folder](https://learn.microsoft.com/en-us/microsoft-edge/webview2/concepts/user-data-folder)

| Order | Work | Evidence that advances it |
| --- | --- | --- |
| 1. Prepare the diagnostic | Start from the existing [startup and graceful-close probe](../qa/p4_research/n12_app_lifetime.py). Keep the app source, launch settings and temp redirection from the failed retest. Use a fresh disposable profile and record the exact binary and WebView2 runtime version. Reuse the existing pinned Process Monitor filesystem collector and Sysmon identity checks. | Before launch, validate that the planned output can distinguish a successful create in generated permitted scratch from a successful create in a generated subfolder of user temp. Check both writer and destination, and verify that missing or conflicting process evidence stays unclassified. Check that only redacted categories will be published. |
| 2. Reproduce and attribute | In one separately approved hosted session, run startup, ready and graceful close using the short probe. Mark the stages and check that the profile exits. Join the file operation to the app's process tree using the PID and process lifetime, and record the process role, operation result, stage and destination family. Retain raw paths and any stack data only in runner temp. | A reproduced create with a verified writer and path category advances the diagnosis. Use the writer's configuration or verified call-stack evidence to identify the path mechanism if the process role alone leaves it ambiguous. Report specific local app data folder families if the events recur. |
| 3. Make one correction | Change the setting or code path supported by the diagnosis. Carry the original reproducer and successful control forward. | A single candidate with a prediction of which operation should move and where it should land. |
| 4. Verify on Windows | Compare the correction against the reproduced baseline in the focused test. Confirm the same app readiness and exit, observed calibration writes, and protected endpoint matches. | Zero observed WebView2 creates in ambient temp with valid targeted coverage. Attribute any remaining local app data operations. Run the full N12 audit when the candidate is ready for wider acceptance verification. |

**Use these outcomes to stop or proceed.**

- **Setup or capture blocked:** If the collector pin or binary differs, a control write is missing, a process join is ambiguous, or export is incomplete, keep the last stage and the specific blocker. Correct that dependency before another approved attempt.
- **Target did not reproduce:** Keep the short-session evidence and the full-run failure. Use recorded stages to select the smallest relevant omitted action if the evidence points to one. The absence of an event in this shorter session cannot establish that the full journey is clean.
- **Reproduced with an identified cause:** Implement the one supported correction. If the cause remains ambiguous after the capture, record which evidence is missing and keep the targeted finding open.

Earlier runs encountered Sysmon identity or timing problems and unresolved ETW write paths. The focused diagnostic needs positive file-operation controls and trustworthy process evidence so an empty result cannot pass falsely. Full audit acceptance still uses its strict mutation and network rules. The current decision is the WebView2 file cause, with broader ETW coverage and network enforcement tracked in their existing workstreams. [Existing QA preflight](./QA_PREFLIGHT_AND_FAILURE_PLANNING.md#before-the-run) · [Collector procedures](../qa/p4_native/N12_TRACE.md) · [Process Monitor capabilities](https://learn.microsoft.com/en-us/sysinternals/downloads/procmon)

The source and published logs were reviewed at `21c8908`. The existing diagnostic and lifetime/scratch suites recorded 28 local passes and four Windows-only skips. The focused Windows capture still requires separate source-pinned approval. File-mutation coverage remains **3/4 (75%)** and P4 remains **14/20 (70%)**.

### 19 November 2026 | Hosted WebView storage and IPC retest

The one approved Windows Server 2022 attempt ran from launch `05eafb25cb5cbc169242f80f99fc0435bb62c129` at reviewed source `189d9b1dab35e7048465173dd8e2475e17f051fe`. One unpackaged build, both launches and exits, calibration, the protected endpoint comparison and both diagnostic reductions completed. All four protected roots and the immutable Quality CSV matched. Executable SHA-256 `d12838286c291c8ce28823556c6f952d63af823d4d19342d8e819772626a3a81`. ETW SHA-256 `b29d195deda1c0778dee6cc65e76db96cb69747fcf5b9785292a47d5dda2d3b4`. FileIO rundown SHA-256 `fd527b24302adae404cab2b56a67487e5a3bae3ec83c0e25c026b1c10d423801`. [Hosted job log](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/44554198359/job/135665715135) · [Consumed approval marker](../qa/p4_research/N12_APP_JOURNEY_WEBVIEW_STORAGE_APPROVAL.txt)

**Storage target missed.** The ordinary audit again counted four ambient-temp creates and 39 outside-scope operations, all WebView. The twelve user-local events comprised four creates, four overwrites and four writes. All were classified `other-user-local`; the logged file-type breakdown did not identify a narrower folder family. The WebView comparison identified 109 additional outside-scope writes and left 15 WebView-network write paths unresolved. The background comparison verified 65 of 3,756 write paths as outside tracked roots and left 3,691 unresolved. The earlier audit had 7,108 unresolved background writes across a different capture. Both comparisons are diagnostic. [Previous run](#19-november-2026--hosted-same-capture-app-audit)

**Network attribution.** There were seven unexpected connections, four loopback and three non-loopback. NetLog matched the three WebView loopback sockets to QA-origin POST requests, two `plugin:window|close` and one `resolve_native_close_request`. The other loopback socket matched the backend's same-process pair, with its precise purpose still unverified. The three non-loopback connections matched two DNS observations and one HTTPS request related to documented Edge service hosts. The ordinary verdict used the existing acceptance policy.

**The hosted job failed after both comparisons completed.** The ordinary audit reported filesystem **FAIL**, network **FAIL** and coverage **BLOCKED** on unresolved ETW mutations. GitHub retained zero artifacts. All four [routine P4 CI jobs](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/44554198399) passed at the launch SHA. File-mutation coverage holds at **3/4 (75%)** because scratch redirection missed its target and the user-local paths remain broadly classified. Desktop network isolation holds at **2/3 (67%)** because its checkpoint also requires the backend socket's purpose. N12 holds at **0/2 (0%)** and P4 at **14/20 (70%)**. The one-use workflow is disarmed.

### 19 November 2026 | Keep verified answers when Ask ODIN defers the model

Under simulated 0.936 GiB available RAM in Low-memory mode, selecting Offline Qwen and asking for the median premium for Yes outcomes previously returned a generic dataset overview. The fallback now reuses the verified calculator for supported standalone questions on the same working snapshot. The regression returned **30 from two matching and usable rows**, with the outcome filter, version, structured facts and resource-deferral reason. The source CSV remained identical and neither bundled inference, Ollama nor a cloud provider was called. Existing investigation responses, unsupported-question guidance and successful model responses passed their compatibility checks. [API regression](../tests/test_p4_r03_verified_answers.py)

All 12 focused API tests and the existing five-answer Local analytics workload passed locally. This is generated API evidence for working under model deferral. Physical Qwen startup and coexistence still need evidence. The R03 workstream remains **1/3 (33%)** and the phase score is **14/20 (70%)**. [R03 evidence and next checkpoint](./P4_LOCAL_ANALYTICS_IMPLEMENTATION_PLAN_2026-11-15.md#verification-and-decision)

At source `cff816148de93be1528f19285871d88b29aef442`, all four [P4 CI jobs](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/44548714165) and all seven adjacent P1–P3 workflows completed successfully. The new deferral regression passed in routine P4 CI. The Windows Local analytics job passed its separate model-free workload. The hosted N12 app retest and physical offline inference were **NOT RUN** at this source.

### 19 November 2026 | Keep Ask ODIN on one working version

The provider-backed insight route previously loaded the working dataset three times. An interleaved Quality approval sent v1 facts to the provider while the API labelled the answer v0. The route now materializes one version and reads its decision metadata in the same transaction. The findings, provider context and local calculations use that snapshot. The regression verifies that an in-flight answer stays on v0 and a later request uses v1. Ten API tests and the five known Local analytics answers passed locally. [API regression](../tests/test_p4_r03_verified_answers.py) · [Quality snapshot](../backend/quality.py)

On the same generated 4,000-row by 28-column CSV, seven warm synthetic Ask ODIN requests went from 21 materializations to seven. Median API time went from 412.7 ms to 345.0 ms in this Linux comparison with the provider stubbed. The stable-version provider-context digest matched and all nine insight contexts were exercised. No inference worker ran. Physical bundled inference and coexistence remain pending, so the R03 workstream is **1/3 (33%)** and P4 is **14/20 (70%)**. [R03 verification](./P4_LOCAL_ANALYTICS_IMPLEMENTATION_PLAN_2026-11-15.md#verification-and-decision)

At source `6415d7470085ff806add690624be5bcded1b43d1`, all four [P4 CI jobs](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/44543035365) passed, including the new version-consistency regression, disposable browser tests and the Windows model-free Local analytics workload. All seven adjacent P1–P3 workflows passed at that source, including [project lifecycle](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/44543035522), [saved report revisions](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/44543035542) and [semantic context](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/44543035515). The native N12 app and physical offline inference runs were **NOT RUN** at this source.

### 19 November 2026 | Retain Tauri IPC command evidence

The archived report establishes three WebView2 TCP connections to the Tauri IPC host from the QA frontend. The redacted output omitted the request method and command, and the original NetLogs were unavailable for replay. The reducer now reports a fixed command name and POST or OPTIONS when the verified launch, TCP loopback socket, unique linked request, exact QA origin and canonical Tauri URL agree. OPTIONS identifies an options request. POST identifies a request for the command. Both are diagnostic request evidence. Raw URLs and unknown command names stay in runner temp. [Archived attribution](#19-november-2026--reconcile-the-four-unexpected-loopback-connections) · [Pinned Tauri URL construction](https://github.com/tauri-apps/tauri/blob/tauri-v2.12.7/crates/tauri/scripts/core.js) · [Generated replay](../tests/test_p4_n12_journey_diagnostics.py)

The focused replay reproduced the missing attribution before the change. After the change it verified a known command, POST and OPTIONS, repeated or competing requests, the exact origin and redaction of unknown paths. The result can guide a request-specific policy review if an approved capture corroborates the attribution. The backend socket purpose remains unverified. This uses the existing capture and leaves the app and network policy in place. Hosted app retest **NOT RUN**. Desktop network isolation **2/3 (67%)**, with P4 **14/20 (70%)**.

At source `b79511b0131bc5e60a8cbbc57033bdcea64628f8`, all four [routine P4 CI jobs](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/44540987016) completed successfully, including the generated NetLog replay, native driver source tests, TypeScript/Vite build, disposable browser exercises and synthetic Windows jobs. Local Python checks recorded 79 passes and four Windows-only skips. The hosted N12 app journey was **NOT RUN** at this source. The previous combined audit remains the governing hosted result for R02.5 and R02.6.

### 19 November 2026 | Prepare the WebView storage retest

The prior hosted job retained category totals and no replay artifact. Exact destinations for its twelve user-local operations are **UNVERIFIED**. The ordinary audit now reports WebView creates under the ambient temp roots and a breakdown of user-local targets by operation, writer, fixed folder family and file type. It counts distinct targets and target events. Unrecognised paths appear as `other-user-local`. Raw paths stay in runner temp. The ordinary verdict and operation counts continue to govern acceptance. Generated replay passed the four ambient creates, twelve user-local operations, folder-prefix boundaries, writer scope and redaction checks. [Prior audit](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/44520473493/job/135547465484) · [Generated tests](../tests/test_p4_n12_journey_diagnostics.py)

The existing app workflow is disarmed. The proposed scope is one GitHub-hosted Windows Server 2022 attempt at the reviewed source, with existing dependencies and Sysmon, one unpackaged build, two launches and the same FileIO decoder. The launch requires a fresh `qa/p4_research/N12_APP_JOURNEY_WEBVIEW_STORAGE_APPROVAL.txt` marker. The temp verification target is zero ambient creates in both launches with valid capture evidence and matching protected endpoints. Record the user-local family breakdown and the governing audit verdict from the same capture. Native retest **NOT RUN**. [Disarmed workflow](../.github/workflows/p4-n12-app-journey.yml)

All four routine P4 jobs passed at source `8aa417e4f6710a1f91cbefd4513fa3ef3ef96f6f`. Local diagnostics and background-thread suites passed 23 tests. The approved app workflow stayed disarmed and the WebView storage retest was **NOT RUN**. [Exact-source CI](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/44535057895)

### 19 November 2026 | Isolate temporary files for the N12 app launches

The hosted baseline attributed four creates to WebView under the runner's user-temp path. Its separate user-local category contained four creates, four overwrites and four writes. The retained report gives directory categories and writer family, with exact targets unavailable for the twelve user-local operations. [Hosted evidence](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/44520473493/job/135547465484)

Both N12 app launches previously inherited the runner's ambient temporary environment. Generated children invoked through the launch path wrote there at `583817671756ac743f722832e6c47a697a82b754`. They now write to `webview/app-temp`, created beneath the already permitted disposable WebView profile. App and WebView descendants receive that scratch location through `TMP`, `TEMP` and `TMPDIR`. Generated replay passed for first launch and relaunch. The Win32-backed child test runs in existing Windows CI. The actual hosted N12 app retest is **NOT RUN**. The test target is zero creates in the ambient temp category while preserving the protected endpoint matches. [Launch code](../qa/p4_research/n12_app_journey.py) · [Child check](../tests/test_p4_n12_exit_corroboration.py)

All four routine P4 jobs passed at source `b1368d8658574068684e2a8901b01f039d75a61b`. The Windows job passed all 20 tests in the dialog, process and scratch suite, including the Win32 temporary-path child. The app retest remained disarmed. [P4 CI](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/44529322671) · [Windows job](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/44529322671/job/135578137250)

### 19 November 2026 | Hosted same-capture app audit

The one approved attempt on GitHub-hosted Windows Server 2022 used launch `15eee94ab96ce7b6a75cc4ab44dcf57f8b5b06f1` and reviewed source `231cfe34227b87ee2e4faa4304243fbacfa2c0f1`. The unpackaged build, both launches and both comparisons completed. Both Sysmon calibrations passed on read one, and all four protected roots and the immutable Quality CSV matched. Executable SHA-256 `bfba82b1dce81b40da8f6c1db33defcced6ea7d2e07b735b8f7e71ddd71e416a`. ETW SHA-256 `fc8edfd33b182680b1a394149a336dc4c30bb777ee3fca5660fc7972a44e6e6d`. FileIO rundown SHA-256 `42803606cb68ea743202ca939f760a103c0cde8067efe10ad6cb9f9838735366`. The approval was consumed and the workflow is disarmed. [Exact hosted job](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/44520473493/job/135547465484) · [Approval marker](../qa/p4_research/N12_APP_JOURNEY_RUNDOWN_APPROVAL.txt)

The ordinary audit reported **39 outside-scope operations**, down from 63 in the previous audit, and **eight unexpected connections**, up from seven. All 39 operations were WebView findings. The previous six driver writes and six driver overwrites were absent from the outside-scope findings. The latest audit still has 43 unresolved driver write paths. The WebView comparison recorded 157 outside-scope operations, including 118 attributed writes, and left 23 WebView network-process write paths unresolved. Four unexpected connections were loopback and four were non-loopback. The governing filesystem and network verdicts were **FAIL** and coverage **BLOCKED** on unresolved mutations. The hosted job therefore failed after emitting the verdicts. [Previous app audit](#19-november-2026--consolidated-driver-isolation-verification)

The same-capture background comparison **completed** and verified **95 of 7,203** write paths (1.3%), all outside tracked roots. It left **7,108** unresolved. The ordinary report counted **6,410** with an outside-tracked candidate name and unverified issuing thread. Stop-time names supplied limited coverage for this group under the current checks. P4 remains **14/20 (70%)**. All four routine P4 jobs passed at the launch SHA. The disarm commit restores the prepared false guard and skips duplicate CI. [Launch CI](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/44520473511)

### 19 November 2026 | Stage the same-capture app path comparison

The disarmed app workflow reuses the fixture's Windows FileIO recorder and decoder. It ends the audit before stopping FileIO and keeps ETW running during rundown. The ordinary audit and its WebView comparison keep their own outputs. A separate background comparison counts paths only when the request-time name agrees with the stop-time name, the thread snapshots agree, and the successful completion and stable key/object lifetime corroborate the write. It reconciles verified paths and remaining gaps to the ordinary audit. Raw evidence stays in runner temp. Generated cases verified both path outcomes and rejected name and completion conflicts, absent thread evidence, a closed handle, an invalid rundown window and ETW loss. [Generated replay](../tests/test_p4_n12_background_thread.py)

The proposed operation was one hosted Windows Server 2022 attempt at the reviewed source, with standard journey dependencies and Sysmon, one unpackaged build with two launches, and the small native FileIO decoder. The live comparison was **NOT RUN** at staging. [Subsequent hosted result](#19-november-2026--hosted-same-capture-app-audit)

At source `6de0fbe24116bcf0c0cbc99570e01dd4bb49cd45`, all four routine P4 jobs and the native Windows FileIO integration **PASSED**. The source suite passed 696 tests and 113 subtests, with five skipped. Windows FileIO passed 274 tests and 12 subtests and verified the existing protected/outside native control. Its strict coverage remained **BLOCKED**. The staged app workflow stayed disarmed. [P4 CI](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/44517561101) · [Windows FileIO job](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/44517561159/job/135537425470)

### 19 November 2026 | Archive review blocked background path replay

The archived app audit at `cd9b397a00a43db26018ce7b594e0938cbaa1c56` retained aggregate results and an ETW digest. The job's artifact list is empty, and the pinned collector did not take a companion FileIO rundown. The report has **6,743** unresolved background writes, of which **6,249** had a candidate name outside tracked roots and an unverified issuing thread. These counts lack the individual requests, completions and key lifetimes needed to verify paths. Historical replay is **BLOCKED**. [Archived job](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/44440131278/job/135278609026) · [Pinned collector](https://github.com/Sonkhe-Shongwe/PilotODIN/blob/cd9b397a00a43db26018ce7b594e0938cbaa1c56/qa/p4_research/n12_app_journey.py)

The earlier collector-only comparison attributed 719 writes and 507 resizes on its own capture. It left 392 path gaps and its governing job failed calibration. The latest Windows integration verified both known writes through pre-opened handles and still reported 119 unrelated write-path gaps. The fixture keys and objects are local to their capture. The earlier guarded comparison also withheld credit where a request-time name already existed, the pattern in the 6,249-write group. [Collector comparison](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/44064219314/job/133973584601) · [Windows FileIO job](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/44513951385/job/135524998486)

For a future separately approved app run, start Windows Performance Recorder alongside ETW. End the audit window before stopping the recorder and keep ETW recording through the stop-time rundown. Use paired process and thread snapshots, matching request and completion identities, and a unique same-capture name with a stable file lifetime. Evaluate the ordinary audit and the comparison against identical ETW evidence. Report how many writes are verified outside tracked roots, protected, or unresolved by reason. Keep the raw evidence in runner temp. The proposed scope is one source-pinned hosted Windows Server 2022 attempt using the existing unpackaged two-launch journey and small ProcessTrace decoder. This comparison is **NOT RUN**.

### 19 November 2026 | Reject conflicting file identities in rundown recovery

The strict FileIO rundown fallback checks a successful write completion against the request's file key and file object before counting the recovered path. A conflict produces an unresolved mutation and withholds path credit. The new reducer regression failed on mismatched key and object at parent source `7e662ed09b278e47869f385dba0a71634e90066f`. After the fix, six generated cases passed. Matching outside and protected writes resolved, a conflicting name stayed unresolved, and each key or object conflict remained unresolved. The local background-thread suite passed all 11 tests. The app audit remains **BLOCKED** on strict mutation coverage. [Reducer](../qa/p4_native/n12_etw_correlate.py) · [Regression](../tests/test_p4_n12_background_thread.py)

At source `dbd5ffbc2836d2ed15d2cfa09abda11b6dc516d0`, all four routine P4 jobs and Windows FileIO integration **PASSED**. The Windows job passed 273 synthetic tests and six subtests, detected the expected protected write in the existing native control, and completed the separate flush fixture. The native control reported strict mutation coverage **BLOCKED**. The full app audit was **NOT RUN**. [P4 CI](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/44513951370) · [Windows FileIO job](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/44513951385/job/135524998486)

### 19 November 2026 | Pre-opened write replay found a false path resolution

At `84f764dcea8c339ca7e3e8b1934ccaa21dbd9d81`, generated inputs exercised the existing ETW filesystem reducer with one stable background PID and TID, an Event 10 name before an Event 16 write, a successful Event 24 on the same request ID, and no in-trace open. The ordinary app-audit path left all three writes unresolved. With a generated stop-time FileIO name for the same key, the optional strict rundown fallback resolved the outside write, flagged one protected write, and held the write whose key had both protected and outside names. The guarded calibration comparison classified the candidate names and awarded zero path credits for these request-time-name cases.

The fallback incorrectly cleared the outside write when its completion file key was changed from 31 to 99 with the request key still 31. The focused replay assertions and ten existing background-thread tests **PASSED**. The contradictory case reproduced a reducer correctness **FAIL** at generated scope. The archived audit's file paths remain unresolved and full mutation coverage is **BLOCKED**. [Strict reducer](../qa/p4_native/n12_etw_correlate.py) · [Hosted writer result](#19-november-2026--hosted-background-writer-control-passed)

### 19 November 2026 | Hosted background writer control passed

The single approved attempt on GitHub-hosted Windows Server 2022 used launch commit `9a093d8f8d35d2dd643ed16e11e205005b7edbd7` and checked out reviewed source `d8b42f29372c7708a27f20355083174b140f9645`. ETW validated **9,082 events** with zero reported event or buffer loss. Both journey snapshots agreed with the ETW issuing thread for one successful write by the independently identified, pre-existing writer. The generated payload matched after the write. The control **PASSED** at thread-identity scope. The workflow is disarmed and the approval consumed. [Exact Windows job](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/44503331212/job/135488447650) · [Approval record](../qa/p4_research/N12_BACKGROUND_THREAD_APPROVAL.txt)

File-path attribution for the archived write group remains unresolved. Strict file-mutation coverage is **BLOCKED**, file-mutation coverage remains **3/4 (75%)**, and the P4 acceptance score is **14/20 (70%)**. [R02.5 scorecard](./PROJECT_STATUS_CURRENT.md#p4-engineering-scorecard)

### 19 November 2026 | Stage a known background writer

The generated writer opens an empty file before capture, stays alive across both app-journey snapshots and writes one payload after ETW calibration. The control verifies the final bytes, stable process and thread identity, the ETW issuing thread and one successful write completion in a digest-verified export with zero reported loss. Ten focused tests passed with generated inputs, including writer coordination, ID reuse, wrong issuer, ambiguous write, failed completion, reported loss and a tampered export. [Fixture](../qa/p4_native/n12_background_thread.py) · [Generated tests](../tests/test_p4_n12_background_thread.py)

The hosted control was **NOT RUN** at staging. The proposed one-use operation used cached Python 3.11, generated runner-temp files and the existing loopback calibration on `windows-2022`. The scope ended at the redacted thread-identity result. [Subsequent hosted result](#19-november-2026--hosted-background-writer-control-passed) · [Disarmed workflow](../.github/workflows/p4-n12-background-thread.yml)

All four routine P4 jobs and Windows FileIO integration **PASSED** at `15375ebe24db948fdeb9e11bee0fe34a8ebaa79f`. The Windows job passed 272 generated tests and the existing native controls. The existing rundown control continued to report **BLOCKED** strict mutation coverage. [Routine P4 CI](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/44502436374) · [Windows FileIO job](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/44502436344/job/135485377944)

### 19 November 2026 | Recover background thread context for file gaps

The archived app comparison at `cd9b397` reported 6,743 unresolved Event 16 writes in the `other` role. Of these, 6,249 paired an unverified issuing thread with a request-time candidate name outside the tracked roots. The app collector enabled thread lifecycle events and took two process snapshots. It had no thread snapshots for workers that were already running when capture began. The staged journey now records thread birth and owner at both endpoints. It uses only threads with matching identities in stable processes, excludes observed lifecycle transitions and withholds this diagnostic on ETW loss. Ordinary and comparison coverage rules still apply. [Archived app job](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/44440131278/job/135278609026) · [Reducer](../qa/p4_native/n12_trace.py)

Generated replay distinguished a verified snapshot match from an unverified thread. The verdicts, unresolved totals and known protected-write violation were preserved. Hosted execution was **NOT RUN** at this replay checkpoint. The later hosted control established one case, and the number of archived writes the snapshots would match remains unknown. [Replay and reuse checks](../tests/test_p4_n12_trace.py) · [Hosted result](#19-november-2026--hosted-background-writer-control-passed)

All four routine P4 jobs and the Windows FileIO job passed at `818e9cd4304ed0324c977d5cef1be1f5ff5e7059`. The FileIO job passed all 262 synthetic tests and the existing native controls. Their strict pre-opened-handle coverage remained blocked on unresolved mutations. [Routine P4 CI](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/44499548660) · [Windows FileIO job](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/44499548737/job/135475377571)

### 19 November 2026 | Hosted protected write and restore control passed

The first and only approved run used GitHub-hosted `windows-2022`. Launch `df2f7d52e168cec3896bd4dea517cb6795f23a68` checked out reviewed source `4df82715d762b55120e3447a3f485a5ab463e289`. The ETW export passed the integrity, bounds and zero-loss checks for 17,639 events. The control verified one completed write at the expected path by each independently identified writer. The intermediate content changed and the final digest matched the original. The write-and-restore control **PASSED**. Strict coverage was **BLOCKED** on `etw-mutation-coverage-unresolved`. The job did not launch PilotODIN. R02.5 and R02.6 retain the prior full-journey results and P4 remains at **14/20 (70%)**. [Exact Windows job](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/44498098710/job/135470364705) · [Reviewed source](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/4df82715d762b55120e3447a3f485a5ab463e289)

The source-pinned approval marker is retained as history and the launch workflow is disarmed. Further restricted runs require their own approval. The next file-coverage investigation starts with the outstanding mutation classes from the last full audit. [One-use workflow](../.github/workflows/p4-n12-protected-restore.yml) · [Prior full app audit](#19-november-2026--consolidated-driver-isolation-verification)

### 19 November 2026 | Remove the runbook-only CI trigger

The routine P4 workflow excludes the exact `qa/p4_native/N12_TRACE.md` path after the broader native QA filter. The previous audit's Markdown changes launched four routine jobs through that runbook path. An ordered filter comparison over tracked paths changed only the runbook match. A simultaneous reducer, test or workflow edit still matches. [Baseline CI](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/44486009036) · [Filter source](../.github/workflows/p4-target-ranking.yml)

The mixed workflow and runbook change triggered all four routine jobs, which passed at `90bf24d7118efc3ddd796a3b4482415e7d413ff9`. This follow-up contains Markdown changes only, including the separate restore-control instructions in the runbook. N12 acceptance still requires approved live evidence. [Mixed-change CI](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/44496580044)

### 19 November 2026 | Stage the protected write and restore control

The fixture seeds a generated protected file in runner temp. Two separately launched Python writers change and then restore it. The fixture records their PIDs and bounded timing, verifies the open handle path, checks the content after each change, and checks the final digest after capture stops. The reducer requires an exact ETW process lifetime for each writer, a completed write to the known path, and one protected write classified for each stage. The public result contains fixed labels and counts. [Fixture and reduction](../qa/p4_native/n12_protected_restore.py)

Generated replay detected both writes despite matching endpoints. Wrong-writer, failed-completion and trace-loss inputs blocked the control. An unrelated trace gap blocked strict coverage while the two verified writes retained their scoped result. Live execution was **NOT RUN** at this staging checkpoint. The proposed scope was one source-pinned run on **GitHub-hosted `windows-2022`**, using cached Python 3.11 and Windows ETW. It required matching endpoint digests, a different intermediate digest, both successfully completed protected writes, and capture bounds, digest and loss checks. No app build or Sysmon provisioning was in scope. [Subsequent hosted result](#19-november-2026--hosted-protected-write-and-restore-control-passed) · [Prior app audit](#19-november-2026--consolidated-driver-isolation-verification)

All four routine P4 jobs and the Windows FileIO job passed at `304e91e670f9e308caadaef3a83f9f89ed824332`. The FileIO job passed 262 synthetic tests, including the new reducer replay. Its existing native pre-opened-handle control detected a protected write while strict coverage remained **BLOCKED**. The new live restore workflow was disarmed throughout. [Routine CI](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/44494369015) · [Windows FileIO job](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/44494368977/job/135457695147)

### 19 November 2026 | Compare file collectors on paired evidence

Both audit paths recorded the same permitted backend write and rejected two protected writes despite identical endpoint snapshots. Unconfirmed Process Monitor coverage and a nonzero ETW loss counter each blocked a clean filesystem and network verdict. A separate generated CSV ended with an unterminated quote after both calibration bookends. The Process Monitor audit previously returned `PASS_SCOPED` and exit 0. Strict CSV parsing now returns `BLOCKED` and exit 2 without a clean report. [Paired replay and regression](../tests/test_p4_n12_trace.py) · [Reducer](../qa/p4_native/n12_trace.py)

Keep ETW as the primary candidate because the current path verifies capture bounds, the export hash and the collector's own loss counters. Process Monitor can corroborate observed paths. Its current live fixture deliberately leaves loss review unconfirmed, so the available evidence cannot support using it alone for coverage. Windows capture of this paired workload and a new app audit are **NOT RUN**. The earlier 15 gaps in the targeted WebView category and the 13 other unresolved categories remain open. [Existing fixture](../qa/p4_native/Invoke_P4_N12_Live_Calibration.ps1) · [Last app audit](#19-november-2026--consolidated-driver-isolation-verification)

All four routine P4 jobs and the separate Windows FileIO integration job passed at `de6658458a7ed441dfc65e2724d61e57367edf8c`. The FileIO job passed 261 synthetic tests and detected the protected write in its existing native pre-opened-handle control. That control passed its assertions while its strict capture verdict remained **BLOCKED** on unresolved mutations. [Routine CI](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/44491762040) · [Windows FileIO evidence](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/44491761989/job/135448882960)

### 19 November 2026 | Reconcile the four unexpected loopback connections

The redacted network and combined-audit outputs at `cd9b397a00a43db26018ce7b594e0938cbaa1c56` agree on the tested executable and the original verdict. The four local observations remain failures under the active policy. The other three findings were two DNS observations and one HTTPS observation associated with Edge service hosts. [Archived Windows job](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/44440131278/job/135278609026)

| Audit observations | Established by the archived evidence | Evidence needed for a narrow policy proposal |
| --- | --- | --- |
| 5, 6 and 7 · WebView2 TCP port 80 | Matched sockets led to the Tauri IPC hostname from the QA frontend origin. Tauri 2.12.7 uses HTTP POST for its custom IPC transport when available. | Identify the exact commands and tie each socket to the verified launch, QA origin and IPC request chain. An unrelated loopback port 80 request remains unexpected. [Tauri 2.12.7 bridge](https://github.com/tauri-apps/tauri/blob/tauri-v2.12.7/crates/tauri/scripts/ipc-protocol.js) |
| 1 · backend TCP | The connection preceded the first app launch. The startup snapshot matched a unique reciprocal pair in the same backend PID. Uvicorn 0.54.0 and CPython 3.11.9 support an asyncio wake-up pair as the likely cause. | Link the captured endpoints to the live event loop's wake-up pair in a future approved run. Same-process ownership alone leaves the code path unverified. [Uvicorn loop factory](https://github.com/encode/uvicorn/blob/0.54.0/uvicorn/loops/asyncio.py) · [CPython event loop](https://github.com/python/cpython/blob/v3.11.9/Lib/asyncio/proactor_events.py) · [CPython socket implementation](https://github.com/python/cpython/blob/v3.11.9/Lib/socket.py) |

The matched result supports a request- and process-specific review, with no basis for a general port 80 or dynamic-port allowance. Both reductions remain **FAIL** for network and filesystem, with coverage **BLOCKED**. The comparison leaves 15 gaps in the targeted WebView write class and 9,323 recorded events across 13 other unresolved categories. This was an archived evidence review. The 10 existing Python diagnostics and nine egress synthetic checks passed locally. The local frontend fixture was **BLOCKED** at import because Playwright was unavailable. The staged control's last routine Windows evidence remains at `a0a7c5e`. [Windows audit](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/44440131278/job/135278609026) · [Routine CI](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/44482975206)

### 19 November 2026 | Stage the app-specific egress control

The app journey can use an explicitly selected WebView2 runtime directory. It verifies temporary outbound rules for the exact staged PilotODIN, backend Python and WebView2 executables before capture. It checks the observed Sysmon images against those paths and blocks clean coverage on missing or mismatched evidence. Existing loopback acceptance rules apply. Both workflows remain disarmed. [Launcher](../qa/p4_research/n12_app_journey.py) · [Rule scope](../qa/p4_research/n12_egress.py)

All four routine P4 jobs passed at `a0a7c5eb2373e29c95cb3b97259fdfaad4c2f516`. The hosted Windows job passed all nine synthetic egress checks and parsed the firewall command and launcher. The checks cover refusal without approval, mismatched runtime images and cleanup after partial setup or capture failure. Live Windows enforcement, runtime selection on the hosted image and the staged app journey are **NOT RUN**. The last app audit's failures still stand. [Exact-source P4 CI](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/44482975206) · [Windows fixture](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/44482975206/job/135419440817) · [Last app audit](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/44440131278/job/135278609026)

### 19 November 2026 | Rework the N12 verification approach

1. **Network.** Define enforceable offline egress boundaries for the exact application and runtime processes. Use generated controls to check that a non-loopback connection fails and the required local API and IPC paths work. The QA-only frontend and debugger traffic need distinct provenance. Propose any necessary change to the expected connection policy for owner review. The next approved application run must measure the proposed control and the actual startup-to-exit journey together.
2. **Filesystem.** Remove avoidable QA-driver mutations at their source and account for driver activity independently in the report. Keep protected paths in scope for every writer. Before proposing another app audit, demonstrate a measured write to a permitted path and detection of an out-of-scope mutation with known writers and destinations. The observed WebView outside writes and unresolved paths remain open.
3. **Run decision.** Reuse the completed audit as the baseline. A new full run needs a candidate that changes the failing behaviour, a working preflight for the intended setup and fresh source-pinned approval. Synthetic cases establish whether a control is ready for that run. Credit applies at the evidence level defined by each acceptance gate.

### 19 November 2026 | Prepare a reversible Windows egress control

The Windows egress preflight stages an outbound block for one exact executable and verifies the effective rule in the Windows Firewall ActiveStore. Its fixture uses the runner's Python. A TCP connect to the same GitHub IPv4 endpoint must work before the rule, return Windows socket access denied while the rule is active, and work after removal. A generated local TCP listener must remain reachable while the rule is active. A timeout, incorrect effective rule or failed cleanup blocks the fixture. Routine CI checks the decisions and parses the Windows command. Native enforcement is **NOT RUN**. [Preflight](../qa/p4_research/n12_egress.py) · [Disarmed workflow](../.github/workflows/p4-n12-egress-preflight.yml)

The proposed one-use scope is the fixture alone on disposable hosted Windows Server 2022. It makes a DNS lookup and direct TCP connections to `github.com:443`, adds and removes one named outbound rule for the runner's Python executable, and records a redacted verdict. An app-specific follow-up needs the exact staged app, backend and WebView runtime images, verification of the required local connections and passing file-mutation coverage. All seven prior network findings retain their original dispositions. [Last app audit](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/44440131278/job/135278609026)

### 19 November 2026 | Protect immutable fixtures during Process Monitor audits

The Process Monitor journey audit previously applied in-window protection to the original-data roots and checked the immutable CSV at the endpoints. A generated capture with matching snapshots reproduced a filesystem **PASS** after writes by a permitted driver and an unscoped process, and a rename onto the CSV. Both collector paths now use the immutable paths in their in-window mutation checks. The same replay returns filesystem **FAIL** with three protected mutations, and a permitted scratch write still passes. This corrects the direct-path audit option. The historical ETW path gaps and the latest app-audit verdict are unaffected. [Reducer](../qa/p4_native/n12_trace.py) · [Regression](../tests/test_p4_n12_trace.py)

### 19 November 2026 | Replace the staged N12 PowerShell dialog launcher

The completed audit attributed six writes and six overwrites under `user-local` to PowerShell in the driver tree. The staged probe made six native project-switch calls through `powershell.exe`. The N12 route now uses the runner's existing Python and the same Win32 dialog title and exact button labels. The helper checks the staged image and process owner before sending the requested action. The other QA routes still use their established PowerShell launcher. [Native driver](../frontend/e2e/p4-71-native-webview-qa.mjs) · [Dialog control](../qa/p4_research/n12_project_switch.py)

All four routine P4 jobs passed at `ce61e4e1a03bb6e92df69cad32945c4fc571c7dc`. The Windows fixture passed all 19 checks, including Node command selection, both generated native button actions, image mismatch and a missing button. A full app audit is **NOT RUN** for this correction. The twelve historical file operations remain in the previous result, and hosted acceptance still needs verified file mutation and network evidence. [P4 CI](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/44451869208) · [Windows fixture](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/44451869208/job/135317523423)

### 19 November 2026 | Generated PowerShell dialog helper comparison

All four routine P4 CI jobs passed at `e634441da3858669eea3683b633eb2cf9fec1159`. The Windows fixture passed 17 checks, including both generated native button actions through Windows PowerShell 5.1. Both CLR usage-log candidates and the redirected module cache were absent at both endpoints for the Node-only control, startup, loading the shared `Add-Type` code, Stay and Switch project. That outcome leaves the six writes and six overwrites in the earlier app audit **UNVERIFIED** at the file-target level. The fixture-only FileIO capture is **NOT RUN**. [Exact-source P4 CI](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/44447286327) · [Windows job](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/44447286327/job/135302398220) · [Evidence contract](../qa/p4_native/N12_TRACE.md#generated-powershell-dialog-helper-endpoints)

## Windows audit evidence

| Scope | Latest applicable evidence |
| --- | --- |
| Last completed app audit | At `231cfe3`, both launches and both comparisons completed. Protected endpoints matched. The ordinary audit recorded 39 outside-scope operations and eight unexpected connections. Filesystem and network **FAIL**, coverage **BLOCKED**. [Hosted result](#19-november-2026--hosted-same-capture-app-audit) |
| Previous app results | At `02f807b`, Sysmon identity mismatches blocked both launches. At `022df1c`, an earlier completed audit reported 67 outside-scope operations, seven unexpected connections and 200,077 unresolved WebView network-process writes. [Blocked attempt](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/44337564606/job/134918293248) · [Earlier completed audit](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/44298639798/job/134782187614) |
| Fixture-only coverage | With the four-second hold at `5d4b8da`, Sysmon attributed both TCP and UDP to the fixture child on its first read. ETW wrote 276 buffers with zero event or buffer loss and produced a nonempty trace. Launch `8a3d05c` consumed the one-use approval. [Retained-child pass](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/44356802211/job/134986971018) · [Earlier immediate-exit pass](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/44335300490/job/134910240433) |
| WebView write comparison | On the latest digest-matched trace, the comparison attributed 198,949 paths to permitted scope and 118 to outside-scope violations, leaving 23 unresolved. The ordinary result governs acceptance. [Hosted result](#19-november-2026--hosted-same-capture-app-audit) · [Previous app audit](#19-november-2026--consolidated-driver-isolation-verification) |

### 19 November 2026 | Consolidated driver isolation verification

Launch `634a4411f837f71ad31301bdb30f5702e1008e25` ran once on disposable GitHub-hosted Windows Server 2022 at source `cd9b397a00a43db26018ce7b594e0938cbaa1c56`. The Vite preflight, unpackaged build, both launches and both reductions completed. Both standalone Sysmon checks passed on read one. All four protected roots and the immutable Quality CSV matched. Executable SHA-256 `e19a8514eeb821ce39092ab2925677921cc8ea6bdd389c6aed4b6a0a66bef6e3`. Both reductions used ETW export SHA-256 `99ab984a5922d5db859e00831586e078eb28c6a44c45eedff52591593ff2b30d`. [Windows job](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/44440131278/job/135278609026) · [Launch CI](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/44440131517)

| Driver operation group | Previous audit | Current audit |
| --- | --- | --- |
| Node under `frontend-dependencies` | Two creates, one write, one delete | **PASS for this group.** Zero in all three categories. |
| PowerShell under `user-local` | Six writes, six overwrites | **FAIL for this group.** Six writes, six overwrites. |

The comparison recorded 114 outside-scope WebView network-process writes, all in `other-path`. The fallback category provides no narrower destination. The 15 unresolved WebView write paths comprised one smaller-pair conflict and 14 cleanup-invalidated cases. The cleanup report attributed the blockers to 11 same-object key conflicts on Event 13, two on Event 15 and one unverified opener lifetime. [Report contract](../qa/p4_native/N12_TRACE.md#hosted-journey-etw-gap-diagnostics)

The ordinary report counted 63 outside-scope operations and the comparison counted 177. Seven connections were unexpected, comprising four loopback and three non-loopback. Coverage reported `etw-mutation-coverage-unresolved`. Both audits reported filesystem **FAIL**, network **FAIL** and coverage **BLOCKED**. The job **FAILED** after publishing both reports and retained no artifacts. The one-use marker `qa/p4_research/N12_APP_JOURNEY_DRIVER_ISOLATION_APPROVAL.txt` is consumed and the workflow is disarmed. [Prior baseline](#18-november-2026--live-cleanup-write-diagnostic)

### 18 November 2026 | Isolate Vite config loading in the QA driver

The ordinary audit counted two creates, one write and one delete by driver Node in `frontend-dependencies`. The N12 launcher used Vite's default config bundler. The launcher now selects `--configLoader runner` for the QA Vite process. The filesystem allowlist still grants the driver its existing optimized dependency cache and scratch directory. [Windows evidence](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/44379979033/job/135069239278) · [Vite 6 config loading](https://v6.vite.dev/config/#configuring-vite)

The generated comparison loads the project's actual TypeScript config with both loaders in disposable roots. It checks the configured Cargo watcher exclusions and whether each loader creates `node_modules/.vite-temp`. The old audit retained only directory-category counts, so the identity of its individual file targets is unverified. The [consolidated verification](#19-november-2026--consolidated-driver-isolation-verification) observed zero operations in the target group. [Vite fixture](../frontend/e2e/p4-n12-native-cases.test.mjs)

### 18 November 2026 | Isolate the QA driver PowerShell cache

The ordinary audit attributed six writes and six overwrites under the runner's local app data to PowerShell in the driver tree. The first-launch probe invokes Windows PowerShell six times for project-switch actions. PowerShell 5.1 defaults its module-analysis cache to local app data. The previous driver environment redirected temporary files but supplied no cache path. The audit published directory categories, so the file targets and their relationship to the cache are unverified. [Windows evidence](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/44379979033/job/135069239278) · [PowerShell cache documentation](https://learn.microsoft.com/en-us/powershell/module/microsoft.powershell.core/about/about_windows_powershell_5.1?view=powershell-5.1#module-analysis-cache)

The journey now gives the driver tree a cache filename under `driver-temp`. The hosted fixture exercises inheritance through a real Node-to-Windows-PowerShell child, and the generated journey checks role scoping. The [consolidated verification](#19-november-2026--consolidated-driver-isolation-verification) still recorded six writes and six overwrites under `user-local`. [Driver fixture](../tests/test_p4_n12_exit_corroboration.py) · [Runbook](../qa/p4_native/N12_TRACE.md#hosted-journey-etw-gap-diagnostics)

### 18 November 2026 | Cleanup write blocker breakdown

The cleanup diagnostic reports an open completion's conflicting FileKey separately from a mismatched key on another event for the same FileObject. The latter reports the event kind. It also distinguishes unavailable, failed or ambiguous open completions, intervening requests on the same IRP and unverifiable status. The shared completion rule still requires a unique status-zero completion in strict timestamp order before the boundary.

The generated replay evaluated 22 cleanup writes with three path candidates and 19 specific blockers. The ordinary audit findings were identical with the diagnostic enabled. Live validation of the finer counts is **NOT RUN**. The 12 key conflicts and two unverified open completions from the last app run stand at their original level of detail. [Replay tests](../tests/test_p4_n12_webview_replay.py) · [Runbook](../qa/p4_native/N12_TRACE.md#hosted-journey-etw-gap-diagnostics)

### 18 November 2026 | Live cleanup write diagnostic

Launch `572296373254fdf5c58b3436ba3bbd8dc4a1a27f` ran once on hosted Windows Server 2022 at source `2896266fdc3e2ef9d33d2e89cabf8a9db1dd473c`. One unpackaged build and both launches and exits completed. Both standalone Sysmon checks passed on read one and the four protected roots and immutable Quality CSV matched at the endpoints. The executable SHA-256 was `5ed9b8be04f842be7aa907a61e11f403c1e65de5f9b762047e294a8a2ce32ac9`. Both reductions used ETW export SHA-256 `8747552c39bbd04c7ff8f5d8bbe11596dd88df91d1d4c1474c97688ab3237b96`. [Windows job](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/44379979033/job/135069239278) · [Launch CI](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/44379978538)

The ordinary report evaluated 14 cleanup-invalidated writes. Twelve had conflicting FileObject and FileKey evidence and two had unverified open completions. It returned zero path candidates for the group. The comparison checked all 121 eligible writes in the smaller pairs, attributed one permitted path and 111 outside-scope paths, and retained nine conflicting object-to-key joins. The two dominant pairs added 198,110 permitted attributions. The 23 residual gaps in this capture consist of the 14 cleanup cases and the nine smaller-pair conflicts. The previous audit's 141 gaps reflect a separate capture.

Both reductions reported filesystem **FAIL**, network **FAIL** and coverage **BLOCKED**. The 111 newly identified outside-scope paths brought the comparison total from 68 to 179. The six unexpected connections comprised three non-loopback and three loopback. The combined audit recorded unresolved mutation coverage, final calibration before scoped exit, a missing process exit and unverified Sysmon exit image and time. The job **FAILED** after publishing both reports and retained no artifacts. The one-use marker was `qa/p4_research/N12_APP_JOURNEY_CLEANUP_OPEN_EVIDENCE_APPROVAL.txt`. The workflow is disarmed.

### 18 November 2026 | Cleanup write open evidence

The ordinary app report now evaluates each unresolved completed WebView network-process write whose first name invalidation was Event 13 Cleanup on a different FileObject. The report counts eligible writes and groups results by candidate scope or reason. It checks the issuing writer identity, a successful prior open on the write object, both completions, file identity and path continuity. Trace loss blocks evaluation. Only counts and fixed labels appear in the report.

The generated 14-write replay returned three path candidates (permitted, protected and outside scope) and 11 evidence blockers. The ordinary file findings stayed identical with the diagnostic enabled. The [subsequent hosted run](#18-november-2026--live-cleanup-write-diagnostic) evaluated the same class of writes in a fresh trace. [Replay tests](../tests/test_p4_n12_webview_replay.py) · [Report contract](../qa/p4_native/N12_TRACE.md#hosted-journey-etw-gap-diagnostics)

### 18 November 2026 | Two-handle cleanup control

The current routine Windows integration at `3407325b1519544dbbb671651b76ad71a1b92794` reran the existing known-file control. In both focused captures, a successful second open preceded the first handle's Cleanup. The Cleanup shared a FileKey with the surviving handle's write and was the first event that invalidated its matching name candidate. The completed open and write on the surviving FileObject independently established the expected path (`overlap` and `write_object_path` **PASS**). Final Cleanup was observed after write completion, while final Close was absent, so the full teardown verdict was **BLOCKED**. [Windows control logs](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/44362875085/job/135008702856) · [Original 14 November control](https://github.com/Sonkhe-Shongwe/PilotODIN/blob/07dbaa749fea9bf90bf4debf534246f875132395/docs/SESSION_HANDOFF_CURRENT.md#14-november-2026--n12-overlapping-handles-reproduce-name-invalidation)

The generated regression now includes a complete positive sequence with final Close, the observed missing-Close case, and reuse of the old FileObject by a different file before the write. The actual 14 WebView writes remain unresolved. Their aggregate report cannot establish a successful matching open, write completion and continuous lifetime for each object. The evidence needed is a redacted count of those checks and their blockers for the affected app writes. [Fixture tests](../tests/test_p4_n12_trace.py) · [File-object evidence](../qa/p4_native/N12_TRACE.md#successful-writes-with-unresolved-paths)

### 18 November 2026 | Remaining WebView write paths

The published [Windows report](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/44358315718/job/134992378756) accounts for 141 writes, with 127 eligible writes outside the two fully checked pairs and 14 whose name evidence was invalidated by Event 13 cleanup on another file object with the same key. The run published no raw ETW artifact for further reduction.

| Writes | Retained path evidence |
| --- | --- |
| 102 | 16 outside-scope candidates in the sample. The other 86 lacked an individual path check. |
| 15 | 15 outside-scope candidates. |
| 9 | 9 conflicting object-to-key associations. |
| 1 | 1 permitted path candidate. |
| 14 | 14 cleanup-invalidated names, excluded from pair selection. |

The strict comparison now evaluates retained requests from all eligible pairs with its existing path, completion, process, thread and audit-window checks. On a generated fixture with the same 141-write breakdown, the comparison attributed 118 paths, including 117 outside scope, and retained the 9 conflicts and 14 invalidations. A generated journey verifies that recovered outside-scope paths become violations. The ordinary report still checks the top two pairs for detailed diagnostics and governs acceptance. The [subsequent hosted run](#18-november-2026--live-cleanup-write-diagnostic) checked all eligible smaller-pair requests in a fresh trace. [Replay tests](../tests/test_p4_n12_webview_replay.py) · [N12 runbook](../qa/p4_native/N12_TRACE.md#hosted-journey-etw-gap-diagnostics)

### 18 November 2026 | Live WebView write-path comparison completed

Launch `f57e8bd` ran once at source `8d18c8ec7350e9a2dc726c69dc29863ae255b950`. Both app launches and exits completed. Initial and final standalone Sysmon checks passed on their first reads. All four protected roots and the immutable Quality CSV matched at the endpoints. The combined audit still reported that calibration did not bracket the journey, process roots or exits could not all be verified, and some mutation paths remained unresolved. GitHub recorded the job as **FAIL** while both reductions produced reports. [Windows evidence](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/44358315718/job/134992378756) · [Launch CI](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/44358315714)

The app and collector workflows are disarmed. Preserve the report on every failed or blocked run. Credit R02.5 and R02.6 only from their governed passing evidence. The owner’s installer freeze and protected-data rules apply. [P4 worklist](./P4_80_ACCEPTANCE_WORKLIST_AND_EVIDENCE_INTAKE_2026-11-12.md#p4-plan-to-reach-75)

## Physical Windows evidence

- **Local analytics.** The owner accepted the native filtered median and its follow-up. The updated physical RAM walkthrough on the separate QA build completed with a verified HTML export and a 735.27 MiB sampled combined working-set peak. Use roughly 1–3 GiB as the whole-app planning range and consider system headroom, paging and responsiveness. [Physical Local analytics record](./P4_LOCAL_ANALYTICS_IMPLEMENTATION_PLAN_2026-11-15.md#physical-windows-session-record) · [RAM measurements](./RESOURCE_AWARE_MODE_DESIGN.md#physical-everyday-ram-retest-result)
- **Offline Qwen.** The isolated 1.50 GiB candidate deferred startup and returned local rules. A later Settings observation showed 0.936 GiB available with a 2.00 GiB floor. The owner paused another physical run under ordinary conditions. Physical bundled generation and coexistence remain open. [Headroom decision](./P4_LOCAL_ANALYTICS_IMPLEMENTATION_PLAN_2026-11-15.md#ordinary-laptop-memory-and-offline-inference)
- **Original data preservation.** The historical full-tree comparison failed with 74 differences and an unknown writer. Prospective owner-device preservation awaits separately authorised evidence. [R06 evidence procedure](./P4_80_ACCEPTANCE_WORKLIST_AND_EVIDENCE_INTAKE_2026-11-12.md#c-r06-non-intrusive-incident-evidence-intake)

## Verified source checks

At `6e5bd7d1f01df28151ba3b97dcd82f0a941f9363`, all four routine P4 jobs and the Windows FileIO integration job passed. The clean generated trace passed both hosted reduction modes, and CLI regression cases verified success and the three failure paths. The positive control demonstrates a reachable pass on generated evidence. [Routine P4 CI](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/44341573479) · [Windows FileIO CI](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/44341573377)

## Historical chronology

The [complete handoff at the pre-cleanup revision](https://github.com/Sonkhe-Shongwe/PilotODIN/blob/6e5bd7d1f01df28151ba3b97dcd82f0a941f9363/docs/SESSION_HANDOFF_CURRENT.md) preserves the original entries, run outcomes and tested revisions. The dated links below retain the previous section URLs and lead to each exact entry.

- <a name="18-november-2026--pre-build-check-passed-and-traced-calibration-hit-sysmon-identity-mismatch"></a>[18 November 2026 | Pre-build check passed and traced calibration hit Sysmon identity mismatch](https://github.com/Sonkhe-Shongwe/PilotODIN/blob/6e5bd7d1f01df28151ba3b97dcd82f0a941f9363/docs/SESSION_HANDOFF_CURRENT.md#18-november-2026--pre-build-check-passed-and-traced-calibration-hit-sysmon-identity-mismatch)
- <a name="18-november-2026--initial-journey-fixture-passed-in-isolation"></a>[18 November 2026 | Initial journey fixture passed in isolation](https://github.com/Sonkhe-Shongwe/PilotODIN/blob/6e5bd7d1f01df28151ba3b97dcd82f0a941f9363/docs/SESSION_HANDOFF_CURRENT.md#18-november-2026--initial-journey-fixture-passed-in-isolation)
- <a name="18-november-2026--same-trace-hosted-attempt-blocked-before-app-launch"></a>[18 November 2026 | Same-trace hosted attempt blocked before app launch](https://github.com/Sonkhe-Shongwe/PilotODIN/blob/6e5bd7d1f01df28151ba3b97dcd82f0a941f9363/docs/SESSION_HANDOFF_CURRENT.md#18-november-2026--same-trace-hosted-attempt-blocked-before-app-launch)
- <a name="18-november-2026--same-trace-hosted-webview-comparison-prepared"></a>[18 November 2026 | Same-trace hosted WebView comparison prepared](https://github.com/Sonkhe-Shongwe/PilotODIN/blob/6e5bd7d1f01df28151ba3b97dcd82f0a941f9363/docs/SESSION_HANDOFF_CURRENT.md#18-november-2026--same-trace-hosted-webview-comparison-prepared)
- <a name="18-november-2026--generated-strict-webview-write-comparison"></a>[18 November 2026 | Generated strict WebView write comparison](https://github.com/Sonkhe-Shongwe/PilotODIN/blob/6e5bd7d1f01df28151ba3b97dcd82f0a941f9363/docs/SESSION_HANDOFF_CURRENT.md#18-november-2026--generated-strict-webview-write-comparison)
- <a name="18-november-2026--hosted-indexed-audit-checked-both-dominant-webview-write-pairs"></a>[18 November 2026 | Hosted indexed audit checked both dominant WebView write pairs](https://github.com/Sonkhe-Shongwe/PilotODIN/blob/6e5bd7d1f01df28151ba3b97dcd82f0a941f9363/docs/SESSION_HANDOFF_CURRENT.md#18-november-2026--hosted-indexed-audit-checked-both-dominant-webview-write-pairs)
- <a name="18-november-2026--hosted-dominant-write-result-and-indexed-fix"></a>[18 November 2026 | Hosted dominant-write result and indexed fix](https://github.com/Sonkhe-Shongwe/PilotODIN/blob/6e5bd7d1f01df28151ba3b97dcd82f0a941f9363/docs/SESSION_HANDOFF_CURRENT.md#18-november-2026--hosted-dominant-write-result-and-indexed-fix)
- <a name="18-november-2026--dominant-webview-write-diagnostic-prepared"></a>[18 November 2026 | Dominant WebView write diagnostic prepared](https://github.com/Sonkhe-Shongwe/PilotODIN/blob/6e5bd7d1f01df28151ba3b97dcd82f0a941f9363/docs/SESSION_HANDOFF_CURRENT.md#18-november-2026--dominant-webview-write-diagnostic-prepared)
- <a name="18-november-2026--generated-webview-replay-checked-199162-completions"></a>[18 November 2026 | Generated WebView replay checked 199162 completions](https://github.com/Sonkhe-Shongwe/PilotODIN/blob/6e5bd7d1f01df28151ba3b97dcd82f0a941f9363/docs/SESSION_HANDOFF_CURRENT.md#18-november-2026--generated-webview-replay-checked-199162-completions)
- <a name="18-november-2026--hosted-driver-ordering-audit-matched-31-retained-handles"></a>[18 November 2026 | Hosted driver ordering audit matched 31 retained handles](https://github.com/Sonkhe-Shongwe/PilotODIN/blob/6e5bd7d1f01df28151ba3b97dcd82f0a941f9363/docs/SESSION_HANDOFF_CURRENT.md#18-november-2026--hosted-driver-ordering-audit-matched-31-retained-handles)
- <a name="18-november-2026--driver-ordering-and-handle-diagnostics-prepared"></a>[18 November 2026 | Driver ordering and handle diagnostics prepared](https://github.com/Sonkhe-Shongwe/PilotODIN/blob/6e5bd7d1f01df28151ba3b97dcd82f0a941f9363/docs/SESSION_HANDOFF_CURRENT.md#18-november-2026--driver-ordering-and-handle-diagnostics-prepared)
- <a name="18-november-2026--full-hosted-audit-captured-27-driver-handles"></a>[18 November 2026 | Full hosted audit captured 27 driver handles](https://github.com/Sonkhe-Shongwe/PilotODIN/blob/6e5bd7d1f01df28151ba3b97dcd82f0a941f9363/docs/SESSION_HANDOFF_CURRENT.md#18-november-2026--full-hosted-audit-captured-27-driver-handles)
- <a name="18-november-2026--hosted-driver-exit-control-verified-18-process-lifetimes"></a>[18 November 2026 | Hosted driver exit control verified 18 process lifetimes](https://github.com/Sonkhe-Shongwe/PilotODIN/blob/6e5bd7d1f01df28151ba3b97dcd82f0a941f9363/docs/SESSION_HANDOFF_CURRENT.md#18-november-2026--hosted-driver-exit-control-verified-18-process-lifetimes)
- <a name="18-november-2026--backend-only-windows-control-did-not-reproduce-the-bytecode-writes"></a>[18 November 2026 | Backend-only Windows control did not reproduce the bytecode writes](https://github.com/Sonkhe-Shongwe/PilotODIN/blob/6e5bd7d1f01df28151ba3b97dcd82f0a941f9363/docs/SESSION_HANDOFF_CURRENT.md#18-november-2026--backend-only-windows-control-did-not-reproduce-the-bytecode-writes)
- <a name="18-november-2026--hosted-audit-identified-python-bytecode-writes"></a>[18 November 2026 | Hosted audit identified Python bytecode writes](https://github.com/Sonkhe-Shongwe/PilotODIN/blob/6e5bd7d1f01df28151ba3b97dcd82f0a941f9363/docs/SESSION_HANDOFF_CURRENT.md#18-november-2026--hosted-audit-identified-python-bytecode-writes)
- <a name="18-november-2026--retained-final-calibration-passed-in-the-full-audit"></a>[18 November 2026 | Retained final calibration passed in the full audit](https://github.com/Sonkhe-Shongwe/PilotODIN/blob/6e5bd7d1f01df28151ba3b97dcd82f0a941f9363/docs/SESSION_HANDOFF_CURRENT.md#18-november-2026--retained-final-calibration-passed-in-the-full-audit)
- <a name="18-november-2026--etw-boundary-control-reproduced-the-final-sysmon-blocker"></a>[18 November 2026 | ETW boundary control reproduced the final Sysmon blocker](https://github.com/Sonkhe-Shongwe/PilotODIN/blob/6e5bd7d1f01df28151ba3b97dcd82f0a941f9363/docs/SESSION_HANDOFF_CURRENT.md#18-november-2026--etw-boundary-control-reproduced-the-final-sysmon-blocker)
- <a name="18-november-2026--hosted-sysmon-socket-lifetime-control-passed-all-six-cases"></a>[18 November 2026 | Hosted Sysmon socket lifetime control passed all six cases](https://github.com/Sonkhe-Shongwe/PilotODIN/blob/6e5bd7d1f01df28151ba3b97dcd82f0a941f9363/docs/SESSION_HANDOFF_CURRENT.md#18-november-2026--hosted-sysmon-socket-lifetime-control-passed-all-six-cases)
- <a name="18-november-2026--hosted-n12-audited-both-launches-and-reproduced-blockers"></a>[18 November 2026 | Hosted N12 audited both launches and reproduced blockers](https://github.com/Sonkhe-Shongwe/PilotODIN/blob/6e5bd7d1f01df28151ba3b97dcd82f0a941f9363/docs/SESSION_HANDOFF_CURRENT.md#18-november-2026--hosted-n12-audited-both-launches-and-reproduced-blockers)
- <a name="18-november-2026--ordinary-laptop-headroom-blocked-the-qwen-baseline"></a>[18 November 2026 | Ordinary laptop headroom blocked the Qwen baseline](https://github.com/Sonkhe-Shongwe/PilotODIN/blob/6e5bd7d1f01df28151ba3b97dcd82f0a941f9363/docs/SESSION_HANDOFF_CURRENT.md#18-november-2026--ordinary-laptop-headroom-blocked-the-qwen-baseline)
- <a name="18-november-2026--physical-everyday-ram-retest-and-html-export-completed"></a>[18 November 2026 | Physical everyday RAM retest and HTML export completed](https://github.com/Sonkhe-Shongwe/PilotODIN/blob/6e5bd7d1f01df28151ba3b97dcd82f0a941f9363/docs/SESSION_HANDOFF_CURRENT.md#18-november-2026--physical-everyday-ram-retest-and-html-export-completed)
- <a name="17-november-2026--deliver-report-transfer-optimized"></a>[17 November 2026 | Deliver report transfer optimized](https://github.com/Sonkhe-Shongwe/PilotODIN/blob/6e5bd7d1f01df28151ba3b97dcd82f0a941f9363/docs/SESSION_HANDOFF_CURRENT.md#17-november-2026--deliver-report-transfer-optimized)
- <a name="17-november-2026--physical-r03-candidate-deferred"></a>[17 November 2026 | Physical R03 candidate deferred](https://github.com/Sonkhe-Shongwe/PilotODIN/blob/6e5bd7d1f01df28151ba3b97dcd82f0a941f9363/docs/SESSION_HANDOFF_CURRENT.md#17-november-2026--physical-r03-candidate-deferred)
- <a name="17-november-2026--isolated-r03-headroom-benchmark-kit-ready"></a>[17 November 2026 | Isolated R03 headroom benchmark kit ready](https://github.com/Sonkhe-Shongwe/PilotODIN/blob/6e5bd7d1f01df28151ba3b97dcd82f0a941f9363/docs/SESSION_HANDOFF_CURRENT.md#17-november-2026--isolated-r03-headroom-benchmark-kit-ready)
- <a name="17-november-2026--physical-r03-attempt-deferred-by-resource-policy"></a>[17 November 2026 | Physical R03 attempt deferred by resource policy](https://github.com/Sonkhe-Shongwe/PilotODIN/blob/6e5bd7d1f01df28151ba3b97dcd82f0a941f9363/docs/SESSION_HANDOFF_CURRENT.md#17-november-2026--physical-r03-attempt-deferred-by-resource-policy)
- <a name="17-november-2026--owner-offline-qa-kit-published"></a>[17 November 2026 | Owner offline QA kit published](https://github.com/Sonkhe-Shongwe/PilotODIN/blob/6e5bd7d1f01df28151ba3b97dcd82f0a941f9363/docs/SESSION_HANDOFF_CURRENT.md#17-november-2026--owner-offline-qa-kit-published)
- <a name="17-november-2026--hosted-desktop-qwen-startup-passed"></a>[17 November 2026 | Hosted desktop Qwen startup passed](https://github.com/Sonkhe-Shongwe/PilotODIN/blob/6e5bd7d1f01df28151ba3b97dcd82f0a941f9363/docs/SESSION_HANDOFF_CURRENT.md#17-november-2026--hosted-desktop-qwen-startup-passed)
- <a name="17-november-2026--offline-qwen-windows-crash"></a>[17 November 2026 | Offline Qwen Windows crash](https://github.com/Sonkhe-Shongwe/PilotODIN/blob/6e5bd7d1f01df28151ba3b97dcd82f0a941f9363/docs/SESSION_HANDOFF_CURRENT.md#17-november-2026--offline-qwen-windows-crash)
- <a name="17-november-2026--separate-final-sysmon-verification"></a>[17 November 2026 | Separate final Sysmon verification](https://github.com/Sonkhe-Shongwe/PilotODIN/blob/6e5bd7d1f01df28151ba3b97dcd82f0a941f9363/docs/SESSION_HANDOFF_CURRENT.md#17-november-2026--separate-final-sysmon-verification)
- <a name="17-november-2026--webview-repeat-write-evidence"></a>[17 November 2026 | WebView repeat-write evidence](https://github.com/Sonkhe-Shongwe/PilotODIN/blob/6e5bd7d1f01df28151ba3b97dcd82f0a941f9363/docs/SESSION_HANDOFF_CURRENT.md#17-november-2026--webview-repeat-write-evidence)
- <a name="17-november-2026--hosted-webview-path-audit"></a>[17 November 2026 | Hosted WebView path audit](https://github.com/Sonkhe-Shongwe/PilotODIN/blob/6e5bd7d1f01df28151ba3b97dcd82f0a941f9363/docs/SESSION_HANDOFF_CURRENT.md#17-november-2026--hosted-webview-path-audit)
- <a name="17-november-2026--webview-request-time-path-replay"></a>[17 November 2026 | WebView request-time path replay](https://github.com/Sonkhe-Shongwe/PilotODIN/blob/6e5bd7d1f01df28151ba3b97dcd82f0a941f9363/docs/SESSION_HANDOFF_CURRENT.md#17-november-2026--webview-request-time-path-replay)
- <a name="17-november-2026--collector-verified-1226-background-mutation-paths"></a>[17 November 2026 | Collector verified 1,226 background mutation paths](https://github.com/Sonkhe-Shongwe/PilotODIN/blob/6e5bd7d1f01df28151ba3b97dcd82f0a941f9363/docs/SESSION_HANDOFF_CURRENT.md#17-november-2026--collector-verified-1226-background-mutation-paths)
- <a name="17-november-2026--repeat-the-resize-on-a-pre-opened-handle"></a>[17 November 2026 | Repeat the resize on a pre-opened handle](https://github.com/Sonkhe-Shongwe/PilotODIN/blob/6e5bd7d1f01df28151ba3b97dcd82f0a941f9363/docs/SESSION_HANDOFF_CURRENT.md#17-november-2026--repeat-the-resize-on-a-pre-opened-handle)
- <a name="17-november-2026--one-named-file-resize"></a>[17 November 2026 | One named file resize](https://github.com/Sonkhe-Shongwe/PilotODIN/blob/6e5bd7d1f01df28151ba3b97dcd82f0a941f9363/docs/SESSION_HANDOFF_CURRENT.md#17-november-2026--one-named-file-resize)
- <a name="17-november-2026--known-filenames-first"></a>[17 November 2026 | Known filenames first](https://github.com/Sonkhe-Shongwe/PilotODIN/blob/6e5bd7d1f01df28151ba3b97dcd82f0a941f9363/docs/SESSION_HANDOFF_CURRENT.md#17-november-2026--known-filenames-first)
- <a name="17-november-2026--strict-comparison-credits-verified-background-paths"></a>[17 November 2026 | Strict comparison credits verified background paths](https://github.com/Sonkhe-Shongwe/PilotODIN/blob/6e5bd7d1f01df28151ba3b97dcd82f0a941f9363/docs/SESSION_HANDOFF_CURRENT.md#17-november-2026--strict-comparison-credits-verified-background-paths)
- <a name="17-november-2026--fileio-completion-check-supported-193-paths"></a>[17 November 2026 | FileIO completion check supported 193 paths](https://github.com/Sonkhe-Shongwe/PilotODIN/blob/6e5bd7d1f01df28151ba3b97dcd82f0a941f9363/docs/SESSION_HANDOFF_CURRENT.md#17-november-2026--fileio-completion-check-supported-193-paths)
- <a name="17-november-2026--fileio-filename-completion-check-prepared"></a>[17 November 2026 | FileIO filename completion check prepared](https://github.com/Sonkhe-Shongwe/PilotODIN/blob/6e5bd7d1f01df28151ba3b97dcd82f0a941f9363/docs/SESSION_HANDOFF_CURRENT.md#17-november-2026--fileio-filename-completion-check-prepared)
- <a name="17-november-2026--fileio-rundown-found-777-candidate-paths"></a>[17 November 2026 | FileIO rundown found 777 candidate paths](https://github.com/Sonkhe-Shongwe/PilotODIN/blob/6e5bd7d1f01df28151ba3b97dcd82f0a941f9363/docs/SESSION_HANDOFF_CURRENT.md#17-november-2026--fileio-rundown-found-777-candidate-paths)
- <a name="17-november-2026--fileio-filename-comparison-prepared"></a>[17 November 2026 | FileIO filename comparison prepared](https://github.com/Sonkhe-Shongwe/PilotODIN/blob/6e5bd7d1f01df28151ba3b97dcd82f0a941f9363/docs/SESSION_HANDOFF_CURRENT.md#17-november-2026--fileio-filename-comparison-prepared)
- <a name="17-november-2026--collector-verified-tcp-and-udp-and-blocked-on-etw-paths"></a>[17 November 2026 | Collector verified TCP and UDP and blocked on ETW paths](https://github.com/Sonkhe-Shongwe/PilotODIN/blob/6e5bd7d1f01df28151ba3b97dcd82f0a941f9363/docs/SESSION_HANDOFF_CURRENT.md#17-november-2026--collector-verified-tcp-and-udp-and-blocked-on-etw-paths)
- <a name="17-november-2026--filesystem-follow-up-stopped-at-initial-sysmon-calibration"></a>[17 November 2026 | Filesystem follow-up stopped at initial Sysmon calibration](https://github.com/Sonkhe-Shongwe/PilotODIN/blob/6e5bd7d1f01df28151ba3b97dcd82f0a941f9363/docs/SESSION_HANDOFF_CURRENT.md#17-november-2026--filesystem-follow-up-stopped-at-initial-sysmon-calibration)
- <a name="17-november-2026--n12-filesystem-follow-up-prepared"></a>[17 November 2026 | N12 filesystem follow-up prepared](https://github.com/Sonkhe-Shongwe/PilotODIN/blob/6e5bd7d1f01df28151ba3b97dcd82f0a941f9363/docs/SESSION_HANDOFF_CURRENT.md#17-november-2026--n12-filesystem-follow-up-prepared)
- <a name="17-november-2026--integrated-n12-audit-passed-both-app-lifetime-checks"></a>[17 November 2026 | Integrated N12 audit passed both app lifetime checks](https://github.com/Sonkhe-Shongwe/PilotODIN/blob/6e5bd7d1f01df28151ba3b97dcd82f0a941f9363/docs/SESSION_HANDOFF_CURRENT.md#17-november-2026--integrated-n12-audit-passed-both-app-lifetime-checks)
- <a name="17-november-2026--integrated-two-launch-n12-audit-prepared"></a>[17 November 2026 | Integrated two-launch N12 audit prepared](https://github.com/Sonkhe-Shongwe/PilotODIN/blob/6e5bd7d1f01df28151ba3b97dcd82f0a941f9363/docs/SESSION_HANDOFF_CURRENT.md#17-november-2026--integrated-two-launch-n12-audit-prepared)
- <a name="17-november-2026--generated-control-confirmed-a-shortened-etw-stop-image"></a>[17 November 2026 | Generated control confirmed a shortened ETW stop image](https://github.com/Sonkhe-Shongwe/PilotODIN/blob/6e5bd7d1f01df28151ba3b97dcd82f0a941f9363/docs/SESSION_HANDOFF_CURRENT.md#17-november-2026--generated-control-confirmed-a-shortened-etw-stop-image)
- <a name="17-november-2026--launcher-lifetime-passed-and-app-stop-image-blocked"></a>[17 November 2026 | Launcher lifetime passed and app stop image blocked](https://github.com/Sonkhe-Shongwe/PilotODIN/blob/6e5bd7d1f01df28151ba3b97dcd82f0a941f9363/docs/SESSION_HANDOFF_CURRENT.md#17-november-2026--launcher-lifetime-passed-and-app-stop-image-blocked)
- <a name="17-november-2026--original-windows-handles-matched-etw-payload-times"></a>[17 November 2026 | Original Windows handles matched ETW payload times](https://github.com/Sonkhe-Shongwe/PilotODIN/blob/6e5bd7d1f01df28151ba3b97dcd82f0a941f9363/docs/SESSION_HANDOFF_CURRENT.md#17-november-2026--original-windows-handles-matched-etw-payload-times)
- <a name="17-november-2026--app-image-paths-matched-and-etw-event-order-blocked"></a>[17 November 2026 | App image paths matched and ETW event order blocked](https://github.com/Sonkhe-Shongwe/PilotODIN/blob/6e5bd7d1f01df28151ba3b97dcd82f0a941f9363/docs/SESSION_HANDOFF_CURRENT.md#17-november-2026--app-image-paths-matched-and-etw-event-order-blocked)
- <a name="17-november-2026--hosted-process-image-path-control-passed"></a>[17 November 2026 | Hosted process image path control passed](https://github.com/Sonkhe-Shongwe/PilotODIN/blob/6e5bd7d1f01df28151ba3b97dcd82f0a941f9363/docs/SESSION_HANDOFF_CURRENT.md#17-november-2026--hosted-process-image-path-control-passed)
- <a name="16-november-2026--n12-capture-volume-map-correction"></a>[16 November 2026 | N12 capture volume map correction](https://github.com/Sonkhe-Shongwe/PilotODIN/blob/6e5bd7d1f01df28151ba3b97dcd82f0a941f9363/docs/SESSION_HANDOFF_CURRENT.md#16-november-2026--n12-capture-volume-map-correction)
- <a name="16-november-2026--hosted-n12-image-diagnostic-found-unmapped-device-paths"></a>[16 November 2026 | Hosted N12 image diagnostic found unmapped device paths](https://github.com/Sonkhe-Shongwe/PilotODIN/blob/6e5bd7d1f01df28151ba3b97dcd82f0a941f9363/docs/SESSION_HANDOFF_CURRENT.md#16-november-2026--hosted-n12-image-diagnostic-found-unmapped-device-paths)
- <a name="16-november-2026--n12-etw-start-image-diagnostic"></a>[16 November 2026 | N12 ETW start image diagnostic](https://github.com/Sonkhe-Shongwe/PilotODIN/blob/6e5bd7d1f01df28151ba3b97dcd82f0a941f9363/docs/SESSION_HANDOFF_CURRENT.md#16-november-2026--n12-etw-start-image-diagnostic)
- <a name="16-november-2026--app-shutdown-passed-and-lifetime-attribution-blocked"></a>[16 November 2026 | App shutdown passed and lifetime attribution blocked](https://github.com/Sonkhe-Shongwe/PilotODIN/blob/6e5bd7d1f01df28151ba3b97dcd82f0a941f9363/docs/SESSION_HANDOFF_CURRENT.md#16-november-2026--app-shutdown-passed-and-lifetime-attribution-blocked)
- <a name="16-november-2026--app-lifetime-retest-blocked-after-peer-closed"></a>[16 November 2026 | App lifetime retest blocked after peer closed](https://github.com/Sonkhe-Shongwe/PilotODIN/blob/6e5bd7d1f01df28151ba3b97dcd82f0a941f9363/docs/SESSION_HANDOFF_CURRENT.md#16-november-2026--app-lifetime-retest-blocked-after-peer-closed)
- <a name="16-november-2026--app-lifetime-run-blocked-at-graceful-close"></a>[16 November 2026 | App lifetime run blocked at graceful close](https://github.com/Sonkhe-Shongwe/PilotODIN/blob/6e5bd7d1f01df28151ba3b97dcd82f0a941f9363/docs/SESSION_HANDOFF_CURRENT.md#16-november-2026--app-lifetime-run-blocked-at-graceful-close)
- <a name="16-november-2026--single-app-lifetime-capture-prepared"></a>[16 November 2026 | Single app lifetime capture prepared](https://github.com/Sonkhe-Shongwe/PilotODIN/blob/6e5bd7d1f01df28151ba3b97dcd82f0a941f9363/docs/SESSION_HANDOFF_CURRENT.md#16-november-2026--single-app-lifetime-capture-prepared)
- <a name="16-november-2026--n12-disputed-exit-diagnostic-prepared"></a>[16 November 2026 | N12 disputed exit diagnostic prepared](https://github.com/Sonkhe-Shongwe/PilotODIN/blob/6e5bd7d1f01df28151ba3b97dcd82f0a941f9363/docs/SESSION_HANDOFF_CURRENT.md#16-november-2026--n12-disputed-exit-diagnostic-prepared)
- <a name="16-november-2026--etw-matched-windows-handles-and-sysmon-exits-differed"></a>[16 November 2026 | ETW matched Windows handles and Sysmon exits differed](https://github.com/Sonkhe-Shongwe/PilotODIN/blob/6e5bd7d1f01df28151ba3b97dcd82f0a941f9363/docs/SESSION_HANDOFF_CURRENT.md#16-november-2026--etw-matched-windows-handles-and-sysmon-exits-differed)
- <a name="16-november-2026--process-only-etw-lifetime-control-prepared"></a>[16 November 2026 | Process-only ETW lifetime control prepared](https://github.com/Sonkhe-Shongwe/PilotODIN/blob/6e5bd7d1f01df28151ba3b97dcd82f0a941f9363/docs/SESSION_HANDOFF_CURRENT.md#16-november-2026--process-only-etw-lifetime-control-prepared)
- <a name="16-november-2026--windows-lifetime-control-blocked-on-three-exit-timestamps"></a>[16 November 2026 | Windows lifetime control blocked on three exit timestamps](https://github.com/Sonkhe-Shongwe/PilotODIN/blob/6e5bd7d1f01df28151ba3b97dcd82f0a941f9363/docs/SESSION_HANDOFF_CURRENT.md#16-november-2026--windows-lifetime-control-blocked-on-three-exit-timestamps)
- <a name="16-november-2026--collector-control-checks-parent-timestamp-order"></a>[16 November 2026 | Collector control checks parent timestamp order](https://github.com/Sonkhe-Shongwe/PilotODIN/blob/6e5bd7d1f01df28151ba3b97dcd82f0a941f9363/docs/SESSION_HANDOFF_CURRENT.md#16-november-2026--collector-control-checks-parent-timestamp-order)
- <a name="16-november-2026--hosted-etw-write-name-evidence-prepared"></a>[16 November 2026 | Hosted ETW write-name evidence prepared](https://github.com/Sonkhe-Shongwe/PilotODIN/blob/6e5bd7d1f01df28151ba3b97dcd82f0a941f9363/docs/SESSION_HANDOFF_CURRENT.md#16-november-2026--hosted-etw-write-name-evidence-prepared)
- <a name="16-november-2026--collector-lifetime-control-prepared"></a>[16 November 2026 | Collector lifetime control prepared](https://github.com/Sonkhe-Shongwe/PilotODIN/blob/6e5bd7d1f01df28151ba3b97dcd82f0a941f9363/docs/SESSION_HANDOFF_CURRENT.md#16-november-2026--collector-lifetime-control-prepared)
- <a name="16-november-2026--n12-reducer-rejects-the-reproduced-false-passes"></a>[16 November 2026 | N12 reducer rejects the reproduced false passes](https://github.com/Sonkhe-Shongwe/PilotODIN/blob/6e5bd7d1f01df28151ba3b97dcd82f0a941f9363/docs/SESSION_HANDOFF_CURRENT.md#16-november-2026--n12-reducer-rejects-the-reproduced-false-passes)
- <a name="16-november-2026--prepared-backend-loopback-ownership-check"></a>[16 November 2026 | Prepared backend loopback ownership check](https://github.com/Sonkhe-Shongwe/PilotODIN/blob/6e5bd7d1f01df28151ba3b97dcd82f0a941f9363/docs/SESSION_HANDOFF_CURRENT.md#16-november-2026--prepared-backend-loopback-ownership-check)
- <a name="16-november-2026--prepared-webview-network-source-categories"></a>[16 November 2026 | Prepared WebView network source categories](https://github.com/Sonkhe-Shongwe/PilotODIN/blob/6e5bd7d1f01df28151ba3b97dcd82f0a941f9363/docs/SESSION_HANDOFF_CURRENT.md#16-november-2026--prepared-webview-network-source-categories)
- <a name="16-november-2026--hosted-n12-completed-with-six-unexpected-connections"></a>[16 November 2026 | Hosted N12 completed with six unexpected connections](https://github.com/Sonkhe-Shongwe/PilotODIN/blob/6e5bd7d1f01df28151ba3b97dcd82f0a941f9363/docs/SESSION_HANDOFF_CURRENT.md#16-november-2026--hosted-n12-completed-with-six-unexpected-connections)
- <a name="16-november-2026--preserve-network-findings-before-etw-processing"></a>[16 November 2026 | Preserve network findings before ETW processing](https://github.com/Sonkhe-Shongwe/PilotODIN/blob/6e5bd7d1f01df28151ba3b97dcd82f0a941f9363/docs/SESSION_HANDOFF_CURRENT.md#16-november-2026--preserve-network-findings-before-etw-processing)
- <a name="16-november-2026--windows-app-journey-passed-both-launches-and-blocked-on-exit-time"></a>[16 November 2026 | Windows app journey passed both launches and blocked on exit time](https://github.com/Sonkhe-Shongwe/PilotODIN/blob/6e5bd7d1f01df28151ba3b97dcd82f0a941f9363/docs/SESSION_HANDOFF_CURRENT.md#16-november-2026--windows-app-journey-passed-both-launches-and-blocked-on-exit-time)
- <a name="16-november-2026--hosted-audit-retains-findings-after-an-invalid-exit-timestamp"></a>[16 November 2026 | Hosted audit retains findings after an invalid exit timestamp](https://github.com/Sonkhe-Shongwe/PilotODIN/blob/6e5bd7d1f01df28151ba3b97dcd82f0a941f9363/docs/SESSION_HANDOFF_CURRENT.md#16-november-2026--hosted-audit-retains-findings-after-an-invalid-exit-timestamp)
- <a name="16-november-2026--collector-udp-prelaunch-passed-and-etw-coverage-blocked"></a>[16 November 2026 | Collector UDP prelaunch passed and ETW coverage blocked](https://github.com/Sonkhe-Shongwe/PilotODIN/blob/6e5bd7d1f01df28151ba3b97dcd82f0a941f9363/docs/SESSION_HANDOFF_CURRENT.md#16-november-2026--collector-udp-prelaunch-passed-and-etw-coverage-blocked)
- <a name="16-november-2026--collector-only-udp-marker-check-prepared"></a>[16 November 2026 | Collector-only UDP marker check prepared](https://github.com/Sonkhe-Shongwe/PilotODIN/blob/6e5bd7d1f01df28151ba3b97dcd82f0a941f9363/docs/SESSION_HANDOFF_CURRENT.md#16-november-2026--collector-only-udp-marker-check-prepared)
- <a name="16-november-2026--hosted-n12-blocked-before-launch-on-the-udp-marker"></a>[16 November 2026 | Hosted N12 blocked before launch on the UDP marker](https://github.com/Sonkhe-Shongwe/PilotODIN/blob/6e5bd7d1f01df28151ba3b97dcd82f0a941f9363/docs/SESSION_HANDOFF_CURRENT.md#16-november-2026--hosted-n12-blocked-before-launch-on-the-udp-marker)
- <a name="16-november-2026--hosted-n12-audit-can-report-findings-after-an-unsupported-exit-image"></a>[16 November 2026 | Hosted N12 audit can report findings after an unsupported exit image](https://github.com/Sonkhe-Shongwe/PilotODIN/blob/6e5bd7d1f01df28151ba3b97dcd82f0a941f9363/docs/SESSION_HANDOFF_CURRENT.md#16-november-2026--hosted-n12-audit-can-report-findings-after-an-unsupported-exit-image)
- <a name="16-november-2026--hosted-n12-endpoint-match-and-sysmon-blocker"></a>[16 November 2026 | Hosted N12 endpoint match and Sysmon blocker](https://github.com/Sonkhe-Shongwe/PilotODIN/blob/6e5bd7d1f01df28151ba3b97dcd82f0a941f9363/docs/SESSION_HANDOFF_CURRENT.md#16-november-2026--hosted-n12-endpoint-match-and-sysmon-blocker)
- <a name="16-november-2026--n12-endpoint-comparison-before-trace-export"></a>[16 November 2026 | N12 endpoint comparison before trace export](https://github.com/Sonkhe-Shongwe/PilotODIN/blob/6e5bd7d1f01df28151ba3b97dcd82f0a941f9363/docs/SESSION_HANDOFF_CURRENT.md#16-november-2026--n12-endpoint-comparison-before-trace-export)
- <a name="16-november-2026--n12-final-audit-blocked-on-a-process-exit"></a>[16 November 2026 | N12 final audit blocked on a process exit](https://github.com/Sonkhe-Shongwe/PilotODIN/blob/6e5bd7d1f01df28151ba3b97dcd82f0a941f9363/docs/SESSION_HANDOFF_CURRENT.md#16-november-2026--n12-final-audit-blocked-on-a-process-exit)
- <a name="16-november-2026--n12-redacted-process-exit-image-diagnostics"></a>[16 November 2026 | N12 redacted process-exit image diagnostics](https://github.com/Sonkhe-Shongwe/PilotODIN/blob/6e5bd7d1f01df28151ba3b97dcd82f0a941f9363/docs/SESSION_HANDOFF_CURRENT.md#16-november-2026--n12-redacted-process-exit-image-diagnostics)
- <a name="16-november-2026--owner-windows-live-dev-checkpoint"></a>[16 November 2026 | Owner Windows Live Dev checkpoint](https://github.com/Sonkhe-Shongwe/PilotODIN/blob/6e5bd7d1f01df28151ba3b97dcd82f0a941f9363/docs/SESSION_HANDOFF_CURRENT.md#16-november-2026--owner-windows-live-dev-checkpoint)
- <a name="16-november-2026--native-local-analytics-answers-accepted"></a>[16 November 2026 | Native Local analytics answers accepted](https://github.com/Sonkhe-Shongwe/PilotODIN/blob/6e5bd7d1f01df28151ba3b97dcd82f0a941f9363/docs/SESSION_HANDOFF_CURRENT.md#16-november-2026--native-local-analytics-answers-accepted)
- <a name="16-november-2026--owner-native-launch-and-automation-timeout"></a>[16 November 2026 | Owner native launch and automation timeout](https://github.com/Sonkhe-Shongwe/PilotODIN/blob/6e5bd7d1f01df28151ba3b97dcd82f0a941f9363/docs/SESSION_HANDOFF_CURRENT.md#16-november-2026--owner-native-launch-and-automation-timeout)
- <a name="15-november-2026--ask-odin-local-analytics-milestone"></a>[15 November 2026 | Ask ODIN Local analytics milestone](https://github.com/Sonkhe-Shongwe/PilotODIN/blob/6e5bd7d1f01df28151ba3b97dcd82f0a941f9363/docs/SESSION_HANDOFF_CURRENT.md#15-november-2026--ask-odin-local-analytics-milestone)
- <a name="15-november-2026--r03-hosted-windows-local-analytics-measurement"></a>[15 November 2026 | R03 hosted Windows Local analytics measurement](https://github.com/Sonkhe-Shongwe/PilotODIN/blob/6e5bd7d1f01df28151ba3b97dcd82f0a941f9363/docs/SESSION_HANDOFF_CURRENT.md#15-november-2026--r03-hosted-windows-local-analytics-measurement)
- <a name="15-november-2026--r03-verified-answers-in-ask-odin"></a>[15 November 2026 | R03 verified answers in Ask ODIN](https://github.com/Sonkhe-Shongwe/PilotODIN/blob/6e5bd7d1f01df28151ba3b97dcd82f0a941f9363/docs/SESSION_HANDOFF_CURRENT.md#15-november-2026--r03-verified-answers-in-ask-odin)
- <a name="15-november-2026--r03-windows-comparison-completed"></a>[15 November 2026 | R03 Windows comparison completed](https://github.com/Sonkhe-Shongwe/PilotODIN/blob/6e5bd7d1f01df28151ba3b97dcd82f0a941f9363/docs/SESSION_HANDOFF_CURRENT.md#15-november-2026--r03-windows-comparison-completed)
- <a name="15-november-2026--consolidated-r03-windows-worker-comparison"></a>[15 November 2026 | Consolidated R03 Windows worker comparison](https://github.com/Sonkhe-Shongwe/PilotODIN/blob/6e5bd7d1f01df28151ba3b97dcd82f0a941f9363/docs/SESSION_HANDOFF_CURRENT.md#15-november-2026--consolidated-r03-windows-worker-comparison)
- <a name="15-november-2026--apply-offline-ai-settings-to-automatic-investigations"></a>[15 November 2026 | Apply offline AI settings to automatic investigations](https://github.com/Sonkhe-Shongwe/PilotODIN/blob/6e5bd7d1f01df28151ba3b97dcd82f0a941f9363/docs/SESSION_HANDOFF_CURRENT.md#15-november-2026--apply-offline-ai-settings-to-automatic-investigations)
- <a name="15-november-2026--skip-unnecessary-qwen-startup-for-dataset-insights"></a>[15 November 2026 | Skip unnecessary Qwen startup for dataset insights](https://github.com/Sonkhe-Shongwe/PilotODIN/blob/6e5bd7d1f01df28151ba3b97dcd82f0a941f9363/docs/SESSION_HANDOFF_CURRENT.md#15-november-2026--skip-unnecessary-qwen-startup-for-dataset-insights)
- <a name="15-november-2026--release-bundled-qwen-memory-when-idle"></a>[15 November 2026 | Release bundled Qwen memory when idle](https://github.com/Sonkhe-Shongwe/PilotODIN/blob/6e5bd7d1f01df28151ba3b97dcd82f0a941f9363/docs/SESSION_HANDOFF_CURRENT.md#15-november-2026--release-bundled-qwen-memory-when-idle)
- <a name="15-november-2026--lower-memory-use-before-modelling"></a>[15 November 2026 | Lower memory use before modelling](https://github.com/Sonkhe-Shongwe/PilotODIN/blob/6e5bd7d1f01df28151ba3b97dcd82f0a941f9363/docs/SESSION_HANDOFF_CURRENT.md#15-november-2026--lower-memory-use-before-modelling)
- <a name="15-november-2026--local-ai-memory-readiness-in-settings"></a>[15 November 2026 | Local AI memory readiness in Settings](https://github.com/Sonkhe-Shongwe/PilotODIN/blob/6e5bd7d1f01df28151ba3b97dcd82f0a941f9363/docs/SESSION_HANDOFF_CURRENT.md#15-november-2026--local-ai-memory-readiness-in-settings)
- <a name="15-november-2026--n12-identifies-the-shared-request-rejection"></a>[15 November 2026 | N12 identifies the shared-request rejection](https://github.com/Sonkhe-Shongwe/PilotODIN/blob/6e5bd7d1f01df28151ba3b97dcd82f0a941f9363/docs/SESSION_HANDOFF_CURRENT.md#15-november-2026--n12-identifies-the-shared-request-rejection)
- <a name="15-november-2026--n12-shared-request-path-trial"></a>[15 November 2026 | N12 shared-request path trial](https://github.com/Sonkhe-Shongwe/PilotODIN/blob/6e5bd7d1f01df28151ba3b97dcd82f0a941f9363/docs/SESSION_HANDOFF_CURRENT.md#15-november-2026--n12-shared-request-path-trial)
- <a name="15-november-2026--n12-adds-a-file-created-during-capture"></a>[15 November 2026 | N12 adds a file created during capture](https://github.com/Sonkhe-Shongwe/PilotODIN/blob/6e5bd7d1f01df28151ba3b97dcd82f0a941f9363/docs/SESSION_HANDOFF_CURRENT.md#15-november-2026--n12-adds-a-file-created-during-capture)
- <a name="15-november-2026--n12-request-time-paths-checked-against-fixture-handles"></a>[15 November 2026 | N12 request-time paths checked against fixture handles](https://github.com/Sonkhe-Shongwe/PilotODIN/blob/6e5bd7d1f01df28151ba3b97dcd82f0a941f9363/docs/SESSION_HANDOFF_CURRENT.md#15-november-2026--n12-request-time-paths-checked-against-fixture-handles)
- <a name="15-november-2026--n12-connection-rehearsal-passed-prelaunch-and-blocked-on-etw-paths"></a>[15 November 2026 | N12 connection rehearsal passed prelaunch and blocked on ETW paths](https://github.com/Sonkhe-Shongwe/PilotODIN/blob/6e5bd7d1f01df28151ba3b97dcd82f0a941f9363/docs/SESSION_HANDOFF_CURRENT.md#15-november-2026--n12-connection-rehearsal-passed-prelaunch-and-blocked-on-etw-paths)
- <a name="15-november-2026--n12-prelaunch-connection-rejection-diagnostics"></a>[15 November 2026 | N12 prelaunch connection rejection diagnostics](https://github.com/Sonkhe-Shongwe/PilotODIN/blob/6e5bd7d1f01df28151ba3b97dcd82f0a941f9363/docs/SESSION_HANDOFF_CURRENT.md#15-november-2026--n12-prelaunch-connection-rejection-diagnostics)
- <a name="15-november-2026--n12-image-path-run-blocked-at-initial-loopback-calibration"></a>[15 November 2026 | N12 image-path run blocked at initial loopback calibration](https://github.com/Sonkhe-Shongwe/PilotODIN/blob/6e5bd7d1f01df28151ba3b97dcd82f0a941f9363/docs/SESSION_HANDOFF_CURRENT.md#15-november-2026--n12-image-path-run-blocked-at-initial-loopback-calibration)
- <a name="15-november-2026--n12-sysmon-image-path-handling"></a>[15 November 2026 | N12 Sysmon image-path handling](https://github.com/Sonkhe-Shongwe/PilotODIN/blob/6e5bd7d1f01df28151ba3b97dcd82f0a941f9363/docs/SESSION_HANDOFF_CURRENT.md#15-november-2026--n12-sysmon-image-path-handling)
- <a name="15-november-2026--n12-writer-breakdown-run-blocked-during-sysmon-parsing"></a>[15 November 2026 | N12 writer breakdown run blocked during Sysmon parsing](https://github.com/Sonkhe-Shongwe/PilotODIN/blob/6e5bd7d1f01df28151ba3b97dcd82f0a941f9363/docs/SESSION_HANDOFF_CURRENT.md#15-november-2026--n12-writer-breakdown-run-blocked-during-sysmon-parsing)
- <a name="15-november-2026--n12-writer-breakdown-prepared"></a>[15 November 2026 | N12 writer breakdown prepared](https://github.com/Sonkhe-Shongwe/PilotODIN/blob/6e5bd7d1f01df28151ba3b97dcd82f0a941f9363/docs/SESSION_HANDOFF_CURRENT.md#15-november-2026--n12-writer-breakdown-prepared)
- <a name="15-november-2026--n12-interaction-driver-scratch-isolation"></a>[15 November 2026 | N12 interaction driver scratch isolation](https://github.com/Sonkhe-Shongwe/PilotODIN/blob/6e5bd7d1f01df28151ba3b97dcd82f0a941f9363/docs/SESSION_HANDOFF_CURRENT.md#15-november-2026--n12-interaction-driver-scratch-isolation)
- <a name="15-november-2026--fixture-lead-in-journey-reached-the-final-audit"></a>[15 November 2026 | Fixture lead-in journey reached the final audit](https://github.com/Sonkhe-Shongwe/PilotODIN/blob/6e5bd7d1f01df28151ba3b97dcd82f0a941f9363/docs/SESSION_HANDOFF_CURRENT.md#15-november-2026--fixture-lead-in-journey-reached-the-final-audit)
- <a name="15-november-2026--protocol-diagnostic-journey-blocked-by-fixture-birth-timing"></a>[15 November 2026 | Protocol diagnostic journey blocked by fixture birth timing](https://github.com/Sonkhe-Shongwe/PilotODIN/blob/6e5bd7d1f01df28151ba3b97dcd82f0a941f9363/docs/SESSION_HANDOFF_CURRENT.md#15-november-2026--protocol-diagnostic-journey-blocked-by-fixture-birth-timing)
- <a name="15-november-2026--protocol-specific-prelaunch-diagnostics"></a>[15 November 2026 | Protocol-specific prelaunch diagnostics](https://github.com/Sonkhe-Shongwe/PilotODIN/blob/6e5bd7d1f01df28151ba3b97dcd82f0a941f9363/docs/SESSION_HANDOFF_CURRENT.md#15-november-2026--protocol-specific-prelaunch-diagnostics)
- <a name="15-november-2026--focused-windows-app-run-blocked-at-initial-calibration"></a>[15 November 2026 | Focused Windows app run blocked at initial calibration](https://github.com/Sonkhe-Shongwe/PilotODIN/blob/6e5bd7d1f01df28151ba3b97dcd82f0a941f9363/docs/SESSION_HANDOFF_CURRENT.md#15-november-2026--focused-windows-app-run-blocked-at-initial-calibration)
- <a name="15-november-2026--focused-isolation-evidence"></a>[15 November 2026 | Focused isolation evidence](https://github.com/Sonkhe-Shongwe/PilotODIN/blob/6e5bd7d1f01df28151ba3b97dcd82f0a941f9363/docs/SESSION_HANDOFF_CURRENT.md#15-november-2026--focused-isolation-evidence)
- <a name="15-november-2026--live-filekey-diagnostic-rehearsal"></a>[15 November 2026 | Live FileKey diagnostic rehearsal](https://github.com/Sonkhe-Shongwe/PilotODIN/blob/6e5bd7d1f01df28151ba3b97dcd82f0a941f9363/docs/SESSION_HANDOFF_CURRENT.md#15-november-2026--live-filekey-diagnostic-rehearsal)
- <a name="15-november-2026--filekey-and-write-completion-diagnostics"></a>[15 November 2026 | FileKey and write-completion diagnostics](https://github.com/Sonkhe-Shongwe/PilotODIN/blob/6e5bd7d1f01df28151ba3b97dcd82f0a941f9363/docs/SESSION_HANDOFF_CURRENT.md#15-november-2026--filekey-and-write-completion-diagnostics)
- <a name="15-november-2026--live-collector-process-snapshot-comparison"></a>[15 November 2026 | Live collector process-snapshot comparison](https://github.com/Sonkhe-Shongwe/PilotODIN/blob/6e5bd7d1f01df28151ba3b97dcd82f0a941f9363/docs/SESSION_HANDOFF_CURRENT.md#15-november-2026--live-collector-process-snapshot-comparison)
- <a name="15-november-2026--collector-process-snapshots-integrated"></a>[15 November 2026 | Collector process snapshots integrated](https://github.com/Sonkhe-Shongwe/PilotODIN/blob/6e5bd7d1f01df28151ba3b97dcd82f0a941f9363/docs/SESSION_HANDOFF_CURRENT.md#15-november-2026--collector-process-snapshots-integrated)
- <a name="15-november-2026--collector-prelaunch-passed-and-final-etw-coverage-blocked"></a>[15 November 2026 | Collector prelaunch passed and final ETW coverage blocked](https://github.com/Sonkhe-Shongwe/PilotODIN/blob/6e5bd7d1f01df28151ba3b97dcd82f0a941f9363/docs/SESSION_HANDOFF_CURRENT.md#15-november-2026--collector-prelaunch-passed-and-final-etw-coverage-blocked)

## Earlier preserved anchors

<a name="15-november-2026--collector-fixture-birth-precision-rule-prepared"></a>
<a name="15-november-2026--collector-rehearsal-measured-a-sub-millisecond-birth-difference"></a>
<a name="15-november-2026--redacted-sysmon-birth-timing-diagnostics"></a>
<a name="15-november-2026--collector-rehearsal-blocked-by-sysmon-birth-timestamp"></a>
<a name="15-november-2026--collector-only-prelaunch-rehearsal-staged"></a>
<a name="15-november-2026--n12-prelaunch-calibration-diagnostics"></a>
<a name="14-november-2026--n12-follow-up-blocked-at-initial-sysmon-calibration"></a>
<a name="14-november-2026--sysmon-identical-exit-records-can-be-replayed"></a>
<a name="14-november-2026--n12-hosted-diagnostic-audit-blocked-by-sysmon-exit-records"></a>
<a name="14-november-2026--prospective-r06-endpoint-checks-prepared"></a>
<a name="14-november-2026--n12-etw-process-and-path-gap-evidence-prepared"></a>
<a name="14-november-2026--n12-redacted-audit-diagnostics-prepared"></a>
<a name="14-november-2026--n12-hosted-app-journey-completed-with-audit-failures"></a>
<a name="14-november-2026--n12-hosted-workflow-and-native-cases-prepared"></a>
<a name="14-november-2026--n12-hosted-app-journey-wiring"></a>
<a name="14-november-2026--n12-unpackaged-build-staging-prepared"></a>
<a name="14-november-2026--n12-fallback-reporting-and-app-journey-readiness"></a>
<a name="14-november-2026--n12-trace-match-diagnostics-windows-result"></a>
<a name="14-november-2026--n12-trace-match-diagnostics-prepared"></a>
<a name="14-november-2026--n12-staggered-write-windows-result"></a>
<a name="14-november-2026--n12-staggered-write-comparison-prepared"></a>
<a name="14-november-2026--cross-window-archive-preserves-the-open-prepare-draft"></a>
<a name="14-november-2026--quality-approval-dialog-and-browser-walkthrough"></a>
<a name="14-november-2026--n12-cache-manager-operations-before-recorder-stop"></a>
<a name="14-november-2026--n12-protected-cache-manager-execution-path"></a>
<a name="14-november-2026--n12-isolated-comparison-and-stack-calibration-pass"></a>
<a name="14-november-2026--n12-stacks-on-the-unflushed-protected-control"></a>
<a name="14-november-2026--n12-stack-calibration-and-protected-target"></a>
<a name="14-november-2026--n12-paging-flag-on-strict-protected-writes"></a>
<a name="14-november-2026--n12-paging-flag-on-a-system-context-write"></a>
<a name="14-november-2026--hosted-smollm2-follow-up-evaluation"></a>
<a name="14-november-2026--hosted-offline-analytics-model-comparison"></a>
<a name="14-november-2026--hosted-windows-qwen-worker-memory-profile"></a>
<a name="14-november-2026--physical-windows-pilotodin-process-memory-snapshots"></a>
<a name="14-november-2026--physical-windows-local-analytics-under-memory-pressure"></a>
<a name="14-november-2026--r03-stopped-at-the-memory-preflight"></a>
<a name="14-november-2026--r03-physical-offline-readiness"></a>
<a name="14-november-2026--n12-pre-opened-handle-path-validation"></a>
<a name="14-november-2026--n12-request-time-path-evidence-without-opens"></a>
<a name="14-november-2026--n12-untouched-comparison-identity-verified"></a>
<a name="14-november-2026--n12-system-write-and-resize-timing"></a>
<a name="14-november-2026--n12-context-for-writes-without-an-observed-open"></a>
<a name="14-november-2026--n12-filebasicinformation-candidate-trial"></a>
<a name="14-november-2026--n12-basic-file-information-path-control"></a>
<a name="14-november-2026--n12-same-object-evidence-for-unresolved-writes"></a>
<a name="14-november-2026--n12-write-path-evidence-from-the-same-file-object"></a>
<a name="14-november-2026--n12-overlapping-handles-reproduce-name-invalidation"></a>
<a name="14-november-2026--n12-file-lifetime-controls-and-name-invalidations"></a>
<a name="14-november-2026--n12-successful-writes-with-unresolved-paths"></a>
<a name="14-november-2026--n12-hosted-compression-requests-reconciled"></a>
<a name="14-november-2026--p4-83-read-only-usn-journal-classification-corrected"></a>
<a name="14-november-2026--native-rundown-now-traverses-the-strict-reducer-for-pre-opened-controls"></a>
<a name="14-november-2026--rundown-and-etw-temporal-alignment-enforced"></a>
<a name="14-november-2026--n12-strict-rundown-integration-and-exact-source-verification"></a>
<a name="14-november-2026--n12-native-processtrace-rundown-successfully-recovers-pre-opened-paths"></a>
<a name="13-november-2026--n12-windows-fileio-rundown-experiment"></a>
<a name="13-november-2026--n12-pre-opened-file-handle-control"></a>
<a name="13-november-2026--n12-issuing-thread-evidence-preflight"></a>
<a name="13-november-2026--n12-background-process-identity-preflight"></a>
<a name="13-november-2026--n12-etw-allocation-and-background-write-context"></a>
<a name="13-november-2026--n12-strict-etw-diagnostic-preflight"></a>
<a name="13-november-2026--n12-combined-calibration-reaches-strict-etw-coverage-check"></a>
<a name="13-november-2026--n12-calibration-only-windows-preflight"></a>
<a name="13-november-2026--n12-preflight-catches-a-windows-timestamp-defect"></a>
<a name="13-november-2026--n12-combined-collector-rehearsal-blocked"></a>
<a name="13-november-2026--n12-combined-collector-rehearsal-staged"></a>
<a name="13-november-2026--n12-combined-etw-and-sysmon-audit"></a>
<a name="13-november-2026--n12-etw-failed-requests-and-protected-writes"></a>
<a name="13-november-2026--n12-etw-fixture-mutation-correlation"></a>
<a name="13-november-2026--n12-etw-fixture-feasibility"></a>
<a name="13-november-2026--n12-redacted-path-diagnostics"></a>
<a name="13-november-2026--n12-live-fixture-markers-observed"></a>
<a name="13-november-2026--n12-process-monitor-stop-and-export-correction"></a>
<a name="13-november-2026--n12-live-collector-calibration-blocked"></a>
<a name="13-november-2026--n12-hosted-collector-inventory"></a>
<a name="13-november-2026--n12-standalone-collector-check"></a>
<a name="13-november-2026--n12-trace-tools-prepared"></a>
<a name="13-november-2026--n12-offline-fonts-and-native-evidence-plan"></a>
<a name="13-november-2026--hosted-windows-r05-fitted-prepare-acceptance"></a>
<a name="13-november-2026--r05-windows-runner-prepared"></a>
<a name="13-november-2026--r05-windows-acceptance-rehearsal"></a>
<a name="13-november-2026--be-024-fitted-experiment-persistence"></a>
<a name="13-november-2026--be-024-per-field-encoded-column-estimates"></a>
<a name="13-november-2026--be-024-prepare-category-examples"></a>
<a name="13-november-2026--p4-closure-readiness-review"></a>
<a name="13-november-2026--synchronized-windows-docking-retest"></a>
<a name="13-november-2026--r04-wait-for-the-active-prepare-route"></a>
<a name="13-november-2026--focused-windows-docking-and-tcp-attribution"></a>
<a name="13-november-2026--r04-drag-gesture-and-n12-tcp-attribution-prepared"></a>
<a name="13-november-2026--remaining-p4-windows-acceptance"></a>
<a name="13-november-2026--targeted-r04-probe-prepared"></a>
<a name="13-november-2026--r04-windows-drag-and-drop-correction"></a>
<a name="13-november-2026--consolidated-hosted-windows-acceptance"></a>
<a name="13-november-2026--p4-quality-relaunch-checkpoint"></a>
<a name="13-november-2026--owner-decision-on-gate-c"></a>
<a name="13-november-2026--owner-restriction-no-cold-outreach-as-a-development-dependency"></a>
<a name="12-november-2026--p4-82-neso-innovation-research-proposal-unsent-draft"></a>
<a name="12-november-2026--p4-81-independently-sourced-online-gate-c-candidate-review"></a>
<a name="12-november-2026--p4-80-consolidated-acceptance-worklist-and-independent-evidence-intake"></a>
<a name="12-november-2026--p4-79-real-browser-saved-experiment-provenance-acceptance"></a>
<a name="12-november-2026--p4-78-saved-experiment-preprocessing-provenance-in-evaluatepredict"></a>
<a name="12-november-2026--p4-77-guarded-categorical-prepare-missing-value-option"></a>
<a name="12-november-2026--p4-76-supported-numeric-preprocessing-choice"></a>
<a name="12-november-2026--p4-75-selection-aware-prepare-resource-guidance"></a>
<a name="12-november-2026--p4-74-real-http-prepare-audit--quality-version-consistency-regression"></a>
<a name="12-november-2026--p4-73-testable-cdp-page-discovery-and-required-native-bridge-signal"></a>
<a name="12-november-2026--p4-72-native-webview-cdp-discovery-limitation-addressed-in-qa-source-only"></a>
<a name="12-november-2026--p4-71-one-approved-unpackaged-windows-native-build-pass-native-interactions-blocked"></a>
<a name="12-november-2026--p4-70-exact-owner-uploaded-elexonneso-forecast-historical-as-of-match-independently-reproduced"></a>
<a name="12-november-2026--p4-68-elexon-ndf-national-boundary-verifier-defect-corrected"></a>
<a name="12-november-2026--p4-67-executable-nesoelexon-no-fit-vintage-verifier-1111-synthetic-tests-pass"></a>
<a name="12-november-2026--p4-66-independent-elexon-vintage-evidence-route-1000-timing-exceptions"></a>
<a name="12-november-2026--p4-65-neso-public-data-no-fit-settlement-audit-and-frozen-retrospective-windows"></a>
<a name="12-november-2026--p4-64-prepare-and-feature-advice-version-pinned-all-ten-naturally-triggered-ci-success"></a>
<a name="12-november-2026--p4-63-scoped-prepare-feature-advice-source-ci-pass-p1-test-harness-regression-fixed"></a>
<a name="12-november-2026--p4-62-prepare-exclusion-approval-exact-source-ci-and-two-prospective-ci-shadow-witnesses"></a>
<a name="12-november-2026--p4-61-owner-approved-manual-prospective-ci-feasibility-zero-observations"></a>
<a name="12-november-2026--p4-60-target-intelligence-codenumber-only-false-readiness-corrected-exact-source-ci-pass"></a>
<a name="12-november-2026--p4-59-prepare-high-risk-identifier-review-aligned-exact-source-ci-pass"></a>
<a name="12-november-2026--documentation-cleaning-audit-current-navigation-repaired-historical-content-preserved"></a>
<a name="12-november-2026--p4-58-shadow-study-global-run-and-patch-identity-integrity-local-1616-pass"></a>
<a name="12-november-2026--p4-57-local-shadow-log-evidence-validator-1212-isolated-synthetic-tests-pass-not-gate-c"></a>
<a name="12-november-2026--p4-56-gate-c-self-owned-github-ci-decision-feasibility-audit-real-run-evidence-no-model"></a>
<a name="12-november-2026--p4-55-one-approved-disposable-real-public-data-research-fit-success-permission-consumed"></a>
<a name="12-november-2026--p4-54-independent-real-data-fixed-origin-calendar-baseline-no-fit-audit"></a>
<a name="12-november-2026--p4-53-nominal-calendar-type-research-fixture-exact-source-ci-pass"></a>
<a name="12-november-2026--p4-52-public-bike-chronological-split-and-no-fit-baselines-exact-source-ci-pass"></a>
<a name="12-november-2026--p4-51-public-bike-daily-data-actual-disposable-import--targetprepare-inspection-ci-pass"></a>
<a name="12-november-2026--p4-50-read-only-evidence-intake-and-no-build-acceptance-plan"></a>
<a name="12-november-2026--p4-49-mixed-case-identifier-screening-guard-exact-source-ci-pass"></a>
<a name="12-november-2026--p4-48-identifier-only-predictor-eligibility-guard-exact-source-ci-pass"></a>
<a name="12-november-2026--p4-47-one-approved-unpackaged-windows-native-compilation--smoke-pass-authority-consumed"></a>
<a name="12-november-2026--p4-46-evidence-feasibility-stop-prospective-patches-as-substitute-for-historical-proof"></a>
<a name="12-november-2026--p4-45-raw-tauri-cli-pre-command-guard-exact-source-p4--p1-ci-pass"></a>
<a name="12-november-2026--p4-44-guard-for-native-dev-production-identity-collision-and-owner-packaging-freeze-ci-pass"></a>
<a name="12-november-2026--p4-43-read-only-original-preservation-stability-exact-source-windows-ci-pass"></a>
<a name="12-november-2026--p4-42-ci-queue-bypass-worked-full-source-only-p4-verification-pass"></a>
<a name="12-november-2026--p4-42-exact-source-ci-still-queued-execution-evidence-blocked-no-source-change"></a>
<a name="11-november-2026--p4-42-final-quality-version-consistency-on-target-get-exact-source-ci-queued-no-ci-pass-claim"></a>
<a name="11-november-2026--p4-41-empty-directory-preservation-false-pass-closed-in-comparator-exact-source-ci-pass"></a>
<a name="11-november-2026--p4-40-categorical-datetime-outcome-guard-exact-source-ci-pass"></a>
<a name="11-november-2026--p4-39-numeric-categorical-non-finite-screening-bypass-fixed-exact-source-ci-pass"></a>
<a name="11-november-2026--p4-38-padded-text-predictor-variation-false-positive-fixed-exact-source-ci-pass"></a>
<a name="11-november-2026--p4-37-non-finite-numeric-predictor-structural-false-positive-corrected-ci-pass"></a>
<a name="11-november-2026--p4-36-fail-closed-whitespace-padded-target-labels-exact-source-ci-pass"></a>
<a name="11-november-2026--p4-35-prepare-high-risk-exclusion-stale-state-safety-exact-source-ci-pass"></a>
<a name="11-november-2026--p4-34-fail-closed-ci-guard-enforces-no-intermediate-installers-exact-source-tests-pass"></a>
<a name="11-november-2026--owner-standing-instruction-no-more-intermediate-installers-until-final-release-stage"></a>
<a name="11-november-2026--p4-33-one-owner-authorised-isolated-windows-qa-build-passed-exact-manifest-independently-inspected"></a>
<a name="11-november-2026--p4-32-owner-tested-binary-versus-current-source-parity-audit-no-build"></a>
<a name="11-november-2026--p4-31-workflow-trigger-coverage-gap-fixed-two-exact-source-ci-workflows-pass"></a>
<a name="11-november-2026--p4-30-blank-only-predictor-false-variation-fixed-source-ci-success"></a>
<a name="11-november-2026--p4-29-blank-text-target-labels-fail-closed-exact-source-ci-pass"></a>
<a name="11-november-2026--owner-native-p4-28-corrected-webview2-observer-pass-historical-writer-remains-unknown"></a>
<a name="11-november-2026--p4-28-owner-windows-observer-runtime-fail-fixed-for-windows-powershell-51-synthetic-ci-pass-native-rerun-open"></a>
<a name="11-november-2026--p4-27-owner-side-webview2-observation-procedure-ready-not-executed"></a>
<a name="11-november-2026--p4-26-webview2-quoted-argument-false-attribution-guard-exact-source-ci-pass"></a>
<a name="11-november-2026--p4-25-exact-head-ci-verification-reconciled-original-preservation-gate-unchanged"></a>
<a name="11-november-2026--p4-25-live-webview2-launch-profile-observer-ci-pass-owner-writer-attribution-open"></a>
<a name="11-november-2026--owner-native-p4-24-diagnostic-executed-original-exe-pass-critical-project-store-0-differences-full-tree-still-fail"></a>
<a name="11-november-2026--p4-24-source-only-project-storebrowser-drift-diagnostic-verified-by-windows-ci"></a>
<a name="11-november-2026--original-data-drift-6274-top-folder-changes-categorized-as-browsercache-no-attribution-yet"></a>
<a name="11-november-2026--p4-original-data-drift-anonymized-top-15-folder-summary-cause-unresolved"></a>
<a name="11-november-2026--original-data-difference-grouped-by-coarse-folder-category-43-still-unclassified"></a>
<a name="11-november-2026--p4-22-current-original-data-inventory-vs-verified-pre-test-backup-74-changed-files-root-cause-open"></a>
<a name="11-november-2026--post-offline-preservation-diagnosis-qa-hash-pass-original-data-tree-changed-cause-unresolved"></a>
<a name="11-november-2026--test-3-owner-observed-offline-ui-functioning-p4-22-integrity-preflight-fail-and-ram-not-tested"></a>
<a name="11-november-2026--owner-reports-windows-tab-draggingdocking-not-working-intuitive-content-drop-fixed-in-source-and-chromium-ci-native-retest-open"></a>
<a name="11-november-2026--n11-quality-history-persistence-and-cross-project-isolation-owner-native-scoped-pass-next-offline-check"></a>
<a name="11-november-2026--p4-n11-owner-windows-prepare-sees-approved-quality-v1-scoped-pass"></a>
<a name="11-november-2026--n11-owner-native-approved-v0-to-v1-quality-change-observed-prepare-rescreen-pending"></a>
<a name="11-november-2026--n12-post-n8n10-owner-native-original-data-preservation-read-only-integrity-pass"></a>
<a name="11-november-2026--n12-owner-native-home-experiment-count--0-after-n10-scoped-visual-pass-only"></a>
<a name="11-november-2026--p4-n10-owner-native-abstention-pass-manual-target-evidence-layout-fixed-in-source-ci-pass-not-native-retested"></a>
<a name="11-november-2026--p4-n9-insufficient-label-native-screening-owner-screenshot-pass-scoped"></a>
<a name="11-november-2026--p4-n8-rare-class-native-screening-owner-screenshot-pass-scoped"></a>
<a name="11-november-2026--owner-windows-current-source-p4-qa-installed-original-app-integrity-and-installed-exe-sha-pass-scope-limited"></a>
<a name="10-november-2026--p4-current-source-windows-qa-github-run-completed-success-manifest-independently-inspected"></a>
<a name="10-november-2026--p4-in-flight-windows-ci-review-not-a-completed-installer-acceptance"></a>
<a name="10-november-2026--one-current-source-p4-native-qa-installer-build-triggered-run-still-in-progress"></a>
<a name="10-november-2026--clock-browser-screenshots-published-and-responsive-layout-ci-pass"></a>
<a name="10-november-2026--selected-satin-chronograph-implemented-in-source-frontend-ci-pass"></a>
<a name="owner-design-selection-10-november-2026"></a>
<a name="9-november-2026--p4-23-controlled-windows-gono-go-plan-optional-shell-clock-proposed-only"></a>
<a name="9-november-2026--p4-22-read-only-windows-preservationram-probe-source-and-synthetic-ci-pass"></a>
<a name="9-november-2026--p4-21-atomic-target-context-save-integrity-fence-exact-p4-ci-green"></a>
<a name="9-november-2026--p4-20-labelled-row-predictor-screening-defect-source-fixed-exact-ci-108288-pass"></a>
<a name="9-november-2026--p4-19-compound-timestamp-header-screening-correction-exact-source-ci-pass"></a>
<a name="9-november-2026--p4-18-non-finite-numeric-label-fail-closed-fix-exact-source-ci-pass-phase-still-active"></a>
<a name="9-november-2026--owner-declined-risk-deferral-proposal-p4-stays-active"></a>
<a name="9-november-2026--p4-17-consolidated-closure-review-completed-explicit-owner-decision-pending"></a>
<a name="9-november-2026--owner-native-n3-pass-decision-usefulness-disclosure-legibility-defect-source-fixed"></a>
<a name="9-november-2026--owner-native-qa-identity-confirmed-empty-catalogue-phantom-archive-banner-found-and-source-fixed"></a>
<a name="9-november-2026--owner-authorised-one-controlled-p4-16-windows-qa-acceptance-session-actual-owner-observations-still-not-tested"></a>
<a name="9-november-2026--p4-checksum-safety-tests-integrated-into-hosted-p4-ci-exact-source-pass"></a>
<a name="9-november-2026--p4-16-read-only-installer-provenance-guard-implemented-owner-acceptance-still-open"></a>
<a name="9-november-2026--p4-16-source-matched-windows-ci-qa-installer-pass-owner-native-still-not-tested"></a>
<a name="9-november-2026--p4-16-nsis-qa-built-installed-engine-pass-desktop-hash-mismatch-scoped-corrective-ci-pending"></a>
<a name="9-november-2026--p4-16-current-source-separate-windows-qa-build-package-verification-in-progress"></a>
<a name="9-november-2026--p4-16-milestone-evidence-intake-open-nativebusiness-acceptance-still-untested"></a>
<a name="9-november-2026--p4-15-consolidated-engineering-acceptance-ci-pass-p4-exit-remains-open"></a>
<a name="9-november-2026--p4-14-full-recommendation-queue-resource-budget-p4-ci-pass"></a>
<a name="9-november-2026--p4-13-bounded-on-demand-inspection-of-widelong-targets-ci-pass"></a>
<a name="9-november-2026--p4-12-version-scoped-on-demand-manual-target-evidence-corrected-ci-pass"></a>
<a name="9-november-2026--p4-11-show-known-blockers-on-manual-target-choice-ci-pass"></a>
<a name="9-november-2026--p4-10-self-tested-disposable-windows-acceptance-kit-native-gate-not-tested"></a>
<a name="9-november-2026--p4-09-phase-exit-negative-matrix-automated-pass-overall-p4-closure-blocked"></a>
<a name="9-november-2026--p4-08-explicit-target-deferdeclineabstain-and-suitability-checkpoint-scoped-ci-pass"></a>
<a name="9-november-2026--p4-07-decision-usefulness-and-observed-entity-dependence-review-scoped-ci-pass"></a>
<a name="9-november-2026--p4-06-alternative-target-evidence-and-owner-context-review-scoped-ci-pass"></a>
<a name="9-november-2026--p4-active-explainable-target-review-queue-scoped-pass"></a>
<a name="9-november-2026--p3-owner-authorised-bounded-development-closure"></a>
<a name="9-november-2026--later-successful-native-w5-zip-independently-reviewed-w5-scoped-accepted"></a>
<a name="9-november-2026--p3-six-gate-closure-review-prepared-not-closed"></a>
<a name="8-november-2026--owner-approved-p3-03-option-a-bounded-human-semantic-review-source-and-browser-pass"></a>
<a name="8-november-2026--p3-next-scope-decision-is-ready-w5-owner-reported-success-not-independent-acceptance"></a>
<a name="8-november-2026--w5-independent-functional-verification-architecture-actual-known-goodknown-bad-ci-pass"></a>
<a name="8-november-2026--root-cause-repair-w5-fetch-sandbox-was-swallowing-tauri-ipc"></a>
<a name="8-november-2026--native-w5-no-longer-needs-a-separate-manual-finish-click"></a>
<a name="8-november-2026--w5-finish-ipc-before-destroy-fix-verified-source-native-acceptance-still-pending"></a>
<a name="8-november-2026--w5-exit-request-now-acknowledges-ipc-before-destroying-synthetic-webview"></a>
<a name="8-november-2026--exact-w5-qa-page-exit-gate-green-in-sourceci-owner-native-final-exit-still-pending"></a>
<a name="8-november-2026--w5-native-finish-gate-changed-to-exact-observed-qa-url-source-fix-owner-pending"></a>
<a name="8-november-2026--native-w5-finish-refusal-now-reports-bounded-actual-tauri-error-reason"></a>
<a name="8-november-2026--w5-owner-native-reviewed-change-observed-stuck-os-close-recovered-with-qa-only-explicit-finish"></a>
<a name="8-november-2026--owner-native-w5-ui-reached-v1-but-os-close-handshake-blocked-final-zip"></a>
<a name="8-november-2026--native-w5-clean-source-preflight-supports-expected-untracked-tauri-outputs"></a>
<a name="6-november-2026--native-w5-one-click-runner-now-self-checks-its-evidence-zip"></a>
<a name="6-november-2026--p3-w5-native-acceptance-now-checks-historical-v0-note-retention"></a>
<a name="6-november-2026--p3-w5-status-only-zip-independent-offline-review-automated-source-ci-pass"></a>
<a name="6-november-2026--p3-native-quality-w5-automated-runner-implemented-source-ci-verified-physical-w5-pending"></a>
<a name="6-november-2026--owner-process-direction-automation-first-p3-continuation"></a>
<a name="6-november-2026--p3-w5-actual-quality-ui-version-transition-pass-in-isolated-real-browser-native-w5-open"></a>
<a name="6-november-2026--p3-03b-read-only-review-states-and-owner-only-field-browser-pass-p3-remains-active"></a>
<a name="6-november-2026--p3-owner-native-w1w4-zip-independently-reviewed-scoped-accepted"></a>
<a name="6-november-2026--owner-native-windows-p3-w1w4-completed-runner-review_required-status-only-zip-awaits-review"></a>
<a name="6-november-2026--owner-native-p3-editor-screenshots-visible-ui-first-qa-save-locally-blocked-by-wrong-field"></a>
<a name="6-november-2026--owner-windows-p3-qa-attempt-blocked-by-dirty-source-checkout-actual-screenshot-native-not-tested"></a>
<a name="6-november-2026--p3-owner-native-qa-origin-blocker-fixed-source-ci-and-windows-compile-green"></a>
<a name="6-november-2026--p3-native-qa-reload-safe-write-guard-final-focused-ci-and-p1-compatibility-green"></a>
<a name="6-november-2026--p3-native-semantic-editor-owner-qa-entry-point-prepared-ci-verified-physical-windows-still-pending"></a>
<a name="6-november-2026--p3-04-real-quality-version-transition-regression-scoped-synthetic-ci-pass"></a>
<a name="6-november-2026--finalised-ci-status-for-p3-02d-adjacent-p1-real-http-regression"></a>
<a name="6-november-2026--p3-02d-unsaved-semantic-business-descriptions-guarded-scoped-ci-pass"></a>
<a name="6-november-2026--p3-03a-exact-field-semantic-review-source-and-actual-browser-pass"></a>
<a name="6-november-2026--p3-02-real-http-browser-savereopenedit--cross-project-boundary-pass"></a>
<a name="6-november-2026--p3-activated-p3-02-optional-dataset-business-context-implemented"></a>
<a name="6-november-2026--owner-frozen-p2-closure"></a>
<a name="6-november-2026--be-030-focused-production-renderer-ci-22-pass-at-d1159954b5d5"></a>
<a name="6-november-2026--owner-approved-advanced-only-be-028029-deferral-p2-adv-report-optional-2026-11-06"></a>
<a name="6-november-2026--be-028029-current-source-closure-scope-proposal-owner-decision-required"></a>
<a name="6-november-2026--be-030-refreshed-3-page-standard-pdf-owner-uploaded-artifact-independent-visualcontent-pass-scoped"></a>
<a name="6-november-2026--github-ci-scope-reconciliation-for-be-030-documentation-only"></a>
<a name="latest-p2-be-030-uploaded-pdf-audit--6-november-2026--four-page-chartvalues-split-confirmed-narrow-layout-patch-source-ready"></a>
<a name="latest-p2-be-030-windows-result--6-november-2026--real-legacy-pdf-sourceextraction-pass-visual-pending"></a>
<a name="latest-p2-be-030-scoped-implementation--6-november-2026--actual-standard-pdf-visual-review-qa-source-ready-owner-pending"></a>
<a name="latest-p2-native-accessibility-acceptance--6-november-2026--four-final-a01-runner-checks-scoped-closed"></a>
<a name="latest-p2-a01-windows-observations--6-november-2026--four-accessibility-interactions-owner-reported-pass-runner-final-pending"></a>
<a name="latest-p2-owner-residual-decisions--6-november-2026--tab-x-observation-deferred-focused-narrator-qa-required"></a>
<a name="latest-p2-binding-owner-scope-decision--6-november-2026--initial-10-uses-legacy-pdf-and-html-unicode-deferred"></a>
<a name="latest-p2-continuation--6-november-2026--current-acceptance-register-reconciled-owner-scope-decision-open"></a>
<a name="latest-p2-release-gate--6-november-2026--independent-original-ofl-and-metadata-confirmed-owner-approval-still-pending"></a>
<a name="latest-p2-owner-native-acceptance--6-november-2026--two-window-unsaved-deliver-cross-project-guard-scoped-closed"></a>
<a name="latest-p2-engineering-checkpoint--6-november-2026--isolated-two-window-native-deliver-selection-qa-source-ready"></a>
<a name="latest-p2-native-owner-acceptance--6-november-2026--five-full-shell-deliver-consent-observations-scoped-closed"></a>
<a name="latest-p2-native-new-project-consent-checkpoint--6-november-2026--keepleave-owner-report"></a>
<a name="latest-p2-owner-native-acceptance-checkpoint--6-november-2026--actual-deliver-keepleave-and-draft-disposition"></a>
<a name="latest-p2-owner-native-visual-checkpoint--6-november-2026--qa-badge-and-new-project-visibility-pass"></a>
<a name="latest-p2-native-qa-startup-checkpoint--6-november-2026--first-real-tauri-window-opened-header-badge-obstruction-fixed"></a>
<a name="latest-p2-owner-windows-acceptance-checkpoint--6-november-2026--cross-window-guard-focused-tests-and-production-build"></a>
<a name="latest-p2-verification-checkpoint--6-november-2026--exact-source-p2-external-project-regression"></a>
<a name="latest-p2-engineering-checkpoint--6-november-2026--native-deliver-cross-window-project-selection-is-fail-closed"></a>
<a name="latest-p2-engineering-checkpoint--6-november-2026--native-keepleave-for-closing-active-dirty-deliver-tab"></a>
<a name="latest-p2-engineering-checkpoint--6-november-2026--external-same-document-urlhash-deliver-native-exit-guard"></a>
<a name="latest-p2-engineering-checkpoint--6-november-2026--direct-studio-navigation-now-shares-native-dirty-deliver-consent"></a>
<a name="latest-p2-engineering-checkpoint--6-november-2026--safe-full-shell-owner-windows-consent-launcher-ready"></a>
<a name="latest-p2-engineering-checkpoint--6-november-2026--shell-initiated-native-deliver-exit-consent"></a>
<a name="latest-p2-engineering-checkpoint--5-november-2026--unsaved-new-report-status-visible-and-consistent"></a>
<a name="latest-p2-engineering-checkpoint--5-november-2026--mounted-incoming-evidence-withdrawal-and-stale-consent"></a>
<a name="latest-p2-engineering-checkpoint--5-november-2026--project-import-navigation-consent-verified"></a>
<a name="current-p2-engineering-checkpoint--5-november-2026--explore-to-deliver-handoff-and-cross-workspace-draft-consent"></a>
<a name="current-p2-engineering-checkpoint--5-november-2026--deliver-local-unsaved-draft-keepdiscard-acceptance"></a>
<a name="current-p2-engineering-checkpoint--5-november-2026--real-guided-save-and-legacy-export-parity-accepted"></a>
<a name="current-p2-engineering-checkpoint--5-november-2026--guided-human-authored-narrative-outlines-verified"></a>
<a name="current-p2-engineering-checkpoint--5-november-2026--verified-evidence-facts-inspector-hosted-full-route-acceptance"></a>
<a name="current-p2-engineering-checkpoint--5-november-2026--real-httpchromium-deliver-revision-comparison-accepted"></a>
<a name="current-p2-engineering-checkpoint--5-november-2026--native-independent-saved-report-revision-comparison"></a>
<a name="current-p2-engineering-checkpoint--5-november-2026--immutable-report-revision-no-change-acceptance"></a>
<a name="current-p2-engineering-checkpoint--5-november-2026--superseded-report-exports-vetoed"></a>
<a name="current-p2-engineering-checkpoint--5-november-2026--verified-count-denominator-reporting-correction"></a>
<a name="current-authoritative-state--p1-closed-for-development-p2-active-5-november-2026"></a>
<a name="latest-verified-state"></a>
<a name="historical-quality-focus-checkpoint-earlier-4-november-2026"></a>
<a name="native-acceptance-blocking-decision-4-november-2026-current-repo-reviewed"></a>
<a name="latest-development-increment-reversible-project-management-4-november-2026"></a>
<a name="latest-verified-increment-read-only-project-deletion-impact-4-november-2026"></a>
<a name="latest-verified-increment-cross-window-archive-protection-4-november-2026"></a>
<a name="latest-verified-increment-archived-project-http-mutation-guard-4-november-2026"></a>
<a name="latest-verified-increment-sqlite-transaction-bound-quality-archive-fence-4-november-2026"></a>
<a name="latest-verified-increment-report-saved-explore-and-investigation-archive-transaction-fence-4-november-2026"></a>
<a name="latest-scoped-native-and-ui-record-4-november-2026"></a>
<a name="latest-quality-usability-increment-and-owner-handoff-5-november-2026"></a>
<a name="owner-native-quality-acceptance-5-november-2026"></a>
<a name="p1-automated-macro-ready-for-owner-local-execution-5-november-2026"></a>
<a name="owner-local-p1-macro-pass-evidence-5-november-2026"></a>
<a name="owner-discovered-native-p1-n1-unsaved-project-switch-issue-5-november-2026"></a>
<a name="5-november-2026--p1-n1-final-ci-reconciliation-and-native-acceptance-boundary"></a>
<a name="5-november-2026--native-p1-n1-stay-owner-evidence-scoped-acceptance"></a>
<a name="5-november-2026--owner-native-positive-switch-project-acceptance"></a>
<a name="5-november-2026--native-windows-scale-and-snap-owner-report"></a>
<a name="5-november-2026--owner-a1a2-reduced-motion-and-narrator-accepted-in-reported-scope"></a>
<a name="historical-p1-closure-assignment-superseded-by-p2-current-state"></a>
<a name="exactly-one-current-next-assignment"></a>
<a name="read-in-this-order"></a>
<a name="safety--limits"></a>

Use the [15 November chronology](https://github.com/Sonkhe-Shongwe/PilotODIN/blob/07dbaa749fea9bf90bf4debf534246f875132395/docs/SESSION_HANDOFF_CURRENT.md) for entries that were archived before this cleanup.
