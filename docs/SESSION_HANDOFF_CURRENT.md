# PilotODIN 1.0 | Current continuation checkpoint

**16 November 2026.** Active branch `feature/live-dev-workspace-20261023`. **P4 Target Intelligence is active with 14 of 20 engineering checks evidenced (70%)**, up from 13 of 20 on the same checklist as of 15 November. The additional check is the owner-accepted native Local analytics exercise on the physical 8 GB laptop. The full N12 filesystem and network checks remain blocked. [P4 engineering scorecard](./PROJECT_STATUS_CURRENT.md#p4-engineering-scorecard) · [P4 worklist](./P4_80_ACCEPTANCE_WORKLIST_AND_EVIDENCE_INTAKE_2026-11-12.md)

## 16 November 2026 | Prepared backend loopback ownership check

The hosted journey now takes one read-only snapshot of established TCP sockets owned by the declared backend after local health passes and before the app launches. The reducer can match a Sysmon observation to a unique, reciprocal pair in the same verified process lifetime. The public report gives only a diagnostic classification and snapshot availability. Missing, stale, or ambiguous evidence leaves the connection unattributed. The live socket snapshot and updated WebView categories are **NOT RUN**. The prior Sysmon exit-image, exit-time and parent-lifetime blockers have no retained raw trace and remain open. [N12 runbook](../qa/p4_native/N12_TRACE.md#hosted-journey-etw-gap-diagnostics)

## 16 November 2026 | Prepared WebView network source categories

The latest retained job log matches five WebView sockets to request types but omits their destinations and initiators. The dev driver uses the local frontend and API and allows Tauri IPC. The two local HTTP/80 findings cannot be assigned to one of these routes from the retained report. Python's Windows asyncio socketpair is a plausible explanation for the backend startup TCP connection to an ephemeral local port. It still needs same-process socket evidence to establish that match.

The hosted reducer now emits fixed categories for uniquely linked WebView request destinations, initiators and DNS query names. Generated tests cover private values, lookalike hosts, unrelated DNS sources, timing and ambiguity. This prepares the next attribution pass. The live audit of this change is **NOT RUN**. [N12 runbook](../qa/p4_native/N12_TRACE.md#hosted-journey-etw-gap-diagnostics)

## 16 November 2026 | Hosted N12 completed with six unexpected connections

The [approved Windows 2022 job](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/43860270006/job/133274942156) ran on attempt 1 from launch `e65776f5d9617c53dd8b274b14f35856f22108c3` at reviewed source `622048ce023c8a339ebc03b0327a6639e9fa7817`. Preflight, the unpackaged build and pinned Sysmon 15.22 passed. Executable SHA-256 was `11e1ec8619b12a2da498fe23cff047c9c9bcd88ded45081508a0bc0fa6d10e22`. Cargo lock SHA-256 was `46cebbc90c1398c4dcd14a58a4bddb19026fea3b952d9600d77ae2101eab56af`.

Initial TCP and UDP calibration passed on read 1. Both launches and final calibration completed. The final report observed both protocols in both calibration fixtures and matched fingerprints for all four protected roots and the immutable CSV, with zero unexpected changes. The early network line and combined report both reached the job log.

**Job FAILED. Network FAIL, filesystem FAIL and strict coverage BLOCKED.** The audit observed six unexpected connections (previous completed audit eight) and 329 outside-scope operations (previously 608). WebView NetLog matched two DNS transactions, one HTTPS request and two loopback HTTP requests. The backend loopback connection remains unattributed. The earlier UDP/443 socket was not observed in this run and remains historically unattributed. The filesystem findings were 276 driver, 51 WebView and two backend operations. ETW still reported 199,123 WebView network-process writes with unresolved paths.

Two Sysmon exits, records 155 and 177, had unsupported image values and timestamps 2 ms before birth. The reducer also reported inconsistent parent lifetime. These findings leave the strict attribution unverified. The one-use approval was consumed and the workflow is disarmed. No artifacts were retained. R02.5 and R02.6 remain blocked and the score is 70%. [Comparison and next action](./P4_80_ACCEPTANCE_WORKLIST_AND_EVIDENCE_INTAKE_2026-11-12.md#p4-plan-to-reach-75)

## 16 November 2026 | Preserve network findings before ETW processing

The hosted journey now writes a redacted network observation to the job log immediately after final Sysmon reduction. It includes source and binary provenance, lifecycle and TCP/UDP calibration issues, unexpected connections by role and protocol, and attributable NetLog categories. ETW export or reduction failure still blocks the combined audit. The strict reducer consumes the same Sysmon evidence. Generated tests cover both ETW failure paths, missing UDP evidence and endpoint redaction. The [live retest](#16-november-2026--hosted-n12-completed-with-six-unexpected-connections) emitted the expected early network report. [N12 runbook](../qa/p4_native/N12_TRACE.md#hosted-journey-etw-gap-diagnostics)

## 16 November 2026 | Windows app journey passed both launches and blocked on exit time

The [approved Windows 2022 job #133226559390](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/43846107440/job/133226559390) ran once from launch `3692f4f5ab9d772a784e342636d3ed6cf5907756` at reviewed source `3d71d3e8ff7a797df69cf68cb114c954456f164d`. Build preflight and binary provenance passed. Executable SHA-256 was `1832f5cb45008f1aa7b5be7d145b031498dbfdcb7c56bd3e7de101462b7f9a33`. Cargo lock SHA-256 was `46cebbc90c1398c4dcd14a58a4bddb19026fea3b952d9600d77ae2101eab56af`.

Initial Sysmon calibration passed on read 1 with the updated UDP fixture. Both same-binary launches and the final fixture completed. All four protected roots and the immutable source CSV matched at the endpoints. The job **FAILED** when the final Sysmon parser reported `process exit precedes birth`. The log supplied neither the record number nor the timestamp delta. The final filesystem and network verdicts are unavailable. No artifacts were retained. The one-use approval was consumed and the workflow is disarmed.

## 16 November 2026 | Hosted audit retains findings after an invalid exit timestamp

The hosted final reducer can now retain later ETW and network findings when an exit matched by process GUID and PID has a timestamp before birth. It logs the record number and signed time delta, leaves the exit unverified, and blocks both acceptance checks. Generated tests cover clean and violating traces and conflicting repeated exits. Default strict reduction and prelaunch still reject the invalid timestamp. The [hosted result](#16-november-2026--hosted-n12-completed-with-six-unexpected-connections) verified that the reducer continued after two rejected exits and kept both acceptance checks blocked. [Reducer contract](../qa/p4_native/N12_TRACE.md#hosted-journey-etw-gap-diagnostics)

The local N12 and prospective preservation selection passed 299 tests with one platform skip. At [source `904d2a0`](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/904d2a038b1b2b7f69c27e2f8d570d86d46034e0), [routine P4 CI](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/43848218896) and [Windows FileIO fixture CI](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/43848219384) both passed.

## 16 November 2026 | Collector UDP prelaunch passed and ETW coverage blocked

The [approved Windows 2022 job #133223010351](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/43845055284/job/133223010351) ran on attempt 1 from launch `d9141fdba1fb043886cbbc8a7001021ba743b97f` at reviewed source `54d22cf906af27a7cee544ec4f069dc9d9869773`. Pinned Sysmon 15.22 installed and the shared prelaunch guard verified the expected child’s initiated loopback TCP and UDP on read 1. The fixture birth adjustment was unused. Both final reductions reported the expected generated file operations and zero filesystem violations.

**Strict coverage BLOCKED and overall job FAILED.** The reductions used the same exports. The process snapshots verified 126 stable background processes and cleared the 1,196 missing-lifetime findings. Path attribution remained unresolved for 704 writes and 492 resizes. There were 224 diagnostic outside-protected path candidates and 972 operations with no prior name in their lifetime. No unmatched writes were reported. The earlier rehearsal's 397 unresolved paths remain a separate observation. PilotODIN compilation, launch and the app audit were **NOT RUN**. No artifacts were retained. The one-use approval was consumed and the workflow is disarmed.

## 16 November 2026 | Collector-only UDP marker check prepared

The fixture now uses a connected UDP socket on loopback, and the receiver records the actual sender port privately. On missing protocol evidence, the prelaunch guard reports whether other loopback UDP records at the fixture port belong to the parent or another process, their direction, whether their source port matches the fixture and whether they arrived within the fixture event window. The child identity and both protocol requirements remain in force. Local tests verified the real TCP and UDP fixture exchange and replayed generated Sysmon records for parent inbound, unrelated outbound, missing markers and delayed delivery. The hosted prelaunch passed, so the added rejection diagnostic was unused in that run. [Runbook](../qa/p4_native/N12_TRACE.md#hosted-journey-etw-gap-diagnostics)

At [source `16b87ec`](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/16b87ece472ddce2c7aafdb7dd59213d012b0e69), the focused local selection passed 257 tests and the full P4 Python selection passed 516 with one skip and 18 passing subtests. All four [P4 CI jobs](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/43843967858) passed, including the real TCP/UDP exchange on the [generated Windows fixture](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/43843967858/job/133219356883). [Windows FileIO fixture CI](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/43843967974) also passed. The remaining live evidence is whether Sysmon sees the expected child’s UDP event.

## 16 November 2026 | Hosted N12 blocked before launch on the UDP marker

The [approved Windows 2022 job #133210995981](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/43841494049/job/133210995981) ran once from launch `fc917a5fbbcc925784068cf2b4e40feb30956347` at reviewed source `ff8ebb412aba41091f41f253f0801bd2fab98e28`. Dependency and driver preflight, the unpackaged build, executable provenance and pinned Sysmon 15.22 setup passed. Executable SHA-256 was `f6ae582027d89ac96f6a9568519825f89805de81530c56d222da2748ecf73bcc`. Resolved Cargo lock SHA-256 was `46cebbc90c1398c4dcd14a58a4bddb19026fea3b952d9600d77ae2101eab56af`.

The generated fixture completed its loopback exchange. On read 1, the Sysmon calibration guard saw neither expected child marker. On read 2 it verified one TCP marker inside the expected child's lifetime and no matching UDP marker. One UDP record at the fixture port carried a different process GUID. The log did not establish its direction, identify the sender or show why the child's UDP event was absent. Initial calibration was **BLOCKED** and the job **FAILED**. Both app launches, endpoint comparison and final reducer were **NOT RUN**. The earlier exit-image diagnostic remains unverified live. No artifacts were retained. The workflow is disarmed and the one-use approval is consumed.

## 16 November 2026 | Hosted N12 audit can report findings after an unsupported exit image

The hosted final reducer now reports filesystem and network findings when a Sysmon exit image is unsupported and its birth GUID, PID and event order agree. The exit remains unverified, coverage is **BLOCKED**, and the findings are labelled diagnostic only. Generated Sysmon and ETW evidence reproduced the fallback image category, retained a file violation and unexpected connection after the rejected record, and kept both checks blocked in a clean trace with the same unsupported image. Conflicting exit records still stop the reduction. The log exposes only fixed categories and flags. Local focused tests passed 269 cases. The broader N12 and preservation selection passed 324 cases with one platform skip. Live hosted verification is **NOT RUN**. [Reducer contract and approval scope](../qa/p4_native/N12_TRACE.md#hosted-journey-etw-gap-diagnostics)

At [source `1094560`](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/10945604abd2d935304ca28349712422ede61a8b), [P4 CI](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/43840030115) passed all four jobs with 513 Python passes, one skip, 18 passing subtests, 92 frontend checks and a successful TypeScript/Vite build. The [N12 FileIO fixture job](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/43840030039) passed 205 trace tests and the Windows controls. These results cover the routine synthetic suites and fixtures.

## 16 November 2026 | Hosted N12 endpoint match and Sysmon blocker

The [approved Windows 2022 job #133182543693](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/43832982495/job/133182543693) ran once from launch `9feea9d096fe9e1e3e72dbebfd5a3e7314784192` at reviewed source `7418ae2f2bc62df23c3ae2f764d6f10e62e2a1a3`. Dependency and driver preflight, the unpackaged build and executable provenance passed. Executable SHA-256 was `f54475a15a6282700ca6efb8219176a2ad23ab2a399b4681c54d82866dfc0186`. Resolved Cargo lock SHA-256 was `46cebbc90c1398c4dcd14a58a4bddb19026fea3b952d9600d77ae2101eab56af`. Initial Sysmon calibration passed on read 1. Both same-binary launches and the final calibration command completed.

**Protected snapshots MATCH on hosted fixtures.** The early report showed equal fingerprints for all four protected roots and the immutable Quality CSV, with zero unexpected changes and zero snapshot issues. It is endpoint evidence for that disposable runner. **Full audit BLOCKED.** Sysmon rejected Event ID 5, record 159, as `relative-or-unrecognized`. The earlier record 184 fell in the same category. The image form and process role remain unverified. The job **FAILED** with no fresh filesystem, network or strict coverage verdict. No artifacts were retained. The workflow is disarmed and the one-use approval is consumed.

## 16 November 2026 | N12 endpoint comparison before trace export

The hosted journey now logs the redacted comparison of protected roots and the immutable source fixture immediately after both endpoint snapshots. The same comparison serves the strict audit. Generated cases verify match, unexpected change and missing baseline. They also verify that the endpoint comparison survives Sysmon export and parser failures, and that an incomplete journey produces no endpoint comparison. All 49 focused journey cases and 320 broader local checks passed, with one platform skip in the broader check. The hosted result is recorded above. [Evidence and run scope](../qa/p4_native/N12_TRACE.md#hosted-journey-etw-gap-diagnostics)

At [source `a938772`](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/a93877253711b63676d41467499ea7263a7e3bcc), all four [P4 CI jobs](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/43832310316) passed with 509 Python passes, one skip, 18 passing subtests, 92 frontend checks, a TypeScript/Vite build and 13 disposable browser cases. The same Python list also passed locally. The [N12 FileIO fixture job](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/43832310314) passed 201 trace tests and both hosted Windows controls. Those CI runs exercised generated data and fixtures.

## 16 November 2026 | N12 final audit blocked on a process exit

The [approved hosted Windows job #133164634428](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/43827479369/job/133164634428) ran once from launch `5a891bd761e96ef319bd3e574e1dc510299887da` at reviewed source `b74f2ba2db3c873edc3b45ec155be96476381c5a`. The dependency and driver preflight passed. The unpackaged build and provenance checks passed. The executable SHA-256 was `9085421acb0bd9af17cfc47a79d2b951ec638e69d38c96b5ef8e4bfcf7fc20a1`. The resolved Cargo lock SHA-256 was `46cebbc90c1398c4dcd14a58a4bddb19026fea3b952d9600d77ae2101eab56af`.

Sysmon 15.22 setup and initial calibration passed on read 1. The first launch, same-binary relaunch and final calibration command completed. The final audit then rejected the image field on Sysmon Event ID 5, record 184, in category `relative-or-unrecognized`. The job failed before emitting the filesystem, network or protected-snapshot verdicts. The public log omits the image value and the run retained no downloadable artifacts. The exact image form and writer remain unverified. The one-use approval was consumed and the workflow is disarmed.

## 16 November 2026 | N12 redacted process-exit image diagnostics

The parser now distinguishes an executable basename matching the recorded birth basename, a different executable basename, a relative path, a quoted value, a dash placeholder and other unrecognised forms. All 201 generated trace cases passed locally with a standard-library harness. They confirm each unsupported image still blocks the audit. The error contains only the category, event type and record number. The process identity, event order and repeated-exit rules still apply. The live value from record 184 remains unknown. At [`510b748`](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/510b7484d61fbfa58588a5757d7268fa33e9aa8c), the [P4 CI](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/43829207980) and [N12 FileIO fixture CI](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/43829207728) both passed. [Diagnostic contract](../qa/p4_native/N12_TRACE.md#hosted-journey-etw-gap-diagnostics)

## 16 November 2026 | Owner Windows Live Dev checkpoint

The owner reported that the Windows Live Dev check worked after starting the launcher. The first attempt received WinError 10061 before it reached the fixture. The successful follow-up is an owner attestation. The printed result, measured response times and available RAM were not supplied. Reuse this checkpoint and the existing hosted browser and Windows API evidence.

The owner approved one [unpackaged Windows desktop session](./P4_LOCAL_ANALYTICS_IMPLEMENTATION_PLAN_2026-11-15.md#proposed-physical-windows-session) on the 8 GB laptop. The first attempt stopped before compilation because the runner rejected untracked files in the local checkout. The corrected runner exports the reviewed application commit and committed QA helpers into a temporary folder, so it can run independently of those files. See the native session results below.

## 16 November 2026 | Native Local analytics answers accepted

The owner relaunched the isolated Windows desktop from the reviewed application source `6381203` using runner `c3f0acc`. The relaunch reached the observation prompt after the five disposable API checks. Screenshots from Ask ODIN on the working dataset v0 in `r03-native` show two correct model-free answers.

- For `outcome = Yes`, median `premium` was 30 from two usable values in two matching rows.
- The follow-up “What about No?” reused the median and column, changed the outcome filter, and reported an unavailable median with zero usable values in one matching row.

**Scoped native interaction PASS by owner acceptance.** The owner reported that the terminal prompt timed out and accepted the screenshots as the result. The runner's final receipt, in-workload physical RAM and paging figures, and UI response timings remain unverified. The check used an unpackaged desktop with a disposable development backend. Physical offline Qwen coexistence and packaged-runtime acceptance remain open.

## 16 November 2026 | Owner native launch and automation timeout

The unpackaged build compiled and opened the isolated desktop window from application source `6381203` and runner `433f421`. The receipt ended `INCOMPLETE` at `native_launch` after the WebView2 debugging HTTP endpoint did not answer. The desktop log was empty, and the owner's Application log query returned no matching crash events. The screenshot confirms window launch. The exit cause was unverified. The 2,910 MiB available RAM reading preceded application launch.

The [relaunch mode](./P4_LOCAL_ANALYTICS_IMPLEMENTATION_PLAN_2026-11-15.md#resume-after-a-webview2-automation-timeout) reuses the hash-verified executable with a fresh disposable workspace. It verifies the five API answers and collects physical process measurements while the owner observes the median and follow-up in the native window.

## 15 November 2026 | Ask ODIN Local analytics milestone

Source `d95407b926a648ae3dea7fd770b1f48343258bc1` passed all four [P4 CI jobs](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/43753907245). The suite recorded 498 Python passes, one skip, 18 passing subtests, 92 frontend checks, a successful TypeScript/Vite build and 13 disposable real-HTTP browser cases. Ask ODIN returned the expected grouped missingness, two distinct rate denominators, filtered median, one filter-changing follow-up and clarification after a project switch. API regressions covered alternate schemas, conflicting aliases and stale Quality versions. The earlier [browser run](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/43753524007/job/132932509110) timed out on a duplicated API prefix in the final test matcher. The corrected run passed without changing feature code.

The current-source Windows API job passed the original five exact-fact checks at simulated 0.73 GiB available and measured 102.4 MiB peak resident. A separate Linux in-process API check on a generated 20,000-row, three-column fixture measured 80.0 ms for the first grouped missingness answer and 39.7 ms median over 20 repeat queries. Cumulative process peak was 114.4 MiB including imports and both fixture sizes. These measurements exclude the full desktop and WebView2. Physical 8 GB Windows acceptance is open.

## 15 November 2026 | R03 hosted Windows Local analytics measurement

The [hosted Windows job](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/43744796818/job/132905610069) passed all five generated Ask ODIN scenarios at source `99d36f680b50ab02ac8a4d9fa281f5a44ffa0d6c`. Simulated 0.73 GiB available RAM caused model preflight to defer, while Local analytics bypassed provider routing and returned the expected facts. The API test process peaked at 102.3 MiB resident and 180.4 MiB committed, including imports, test harness and two generated CSV imports. The workload took 0.295 seconds after setup. No scikit-learn or SciPy modules loaded. The hosted machine reported 15.995 GiB total and 13.425 GiB available before the workload. These are process-level measurements with a simulated admission reading. The desktop and WebView2 were outside the measurement.

The [first run](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/43744550356) returned five correct answers and measured 98.0 MiB peak resident RAM, then hit a Windows SQLite file lock during fixture cleanup. It also missed file events in the separate synthetic ETW fixture job. The harness now waits for its test process to exit before removing the temporary directory. All four jobs passed on the corrected source, including 495 Python tests with one skip, 92 frontend checks, 13 browser scenarios and the synthetic Windows preservation checks. Strict N12 and physical 8 GB Windows acceptance remain open.

## 15 November 2026 | R03 verified answers in Ask ODIN

Choose Local analytics in Ask ODIN to get working-version overview counts, missing-row counts with an unknown-cause explanation, a positive rate for an explicitly named outcome and observed label, or recorded training status. The denominator excludes unlabelled rows. Training reads current-version history and reports a selected model's saved cross-validation score when available. These answers bypass provider routing and model startup. The UI offers question shortcuts and editable examples for column-specific questions.

Five benchmark scenarios passed through the real API on generated datasets using the Local analytics question forms and the original expected facts. The provider benchmark used free-form prompts, including a 1,022-token context case. This check re-expresses that case as a structured overview request using the same expected facts. The Linux API test process peaked at 96.6 MiB, including fixture setup and the test harness. This evidence covers the model-free workload. Physical Windows coexistence and offline generation remain open.

## 15 November 2026 | R03 Windows comparison completed

The [approved hosted Windows run](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/43740595746/job/132892675147) completed on attempt 1. Launch commit `3d8641304edd8febb5e5b4c39f4aeded52bf5d56` checked out source `b19946e2f9e3327c71eee7371838d6ec69df6d41`. The runner reported 15.99 GiB visible and 13.64 GiB free before staging. The worker comparison used the pinned Qwen3 1.7B model and llama.cpp b10344 runtime with matching input lengths, including a 1,022-token overview prompt.

| Measure | Batch 512 | Batch 128 |
| --- | ---: | ---: |
| Resident RAM at model readiness | 1,989.0 MiB | 1,988.0 MiB |
| Peak resident RAM through analytics | 2,109.5 MiB | 2,068.9 MiB |
| Peak committed memory through analytics | 1,106.9 MiB | 1,063.3 MiB |
| Model readiness | 2.641 s | 2.359 s |
| Long overview response | 20.719 s | 19.719 s |
| Exact answers | 2 of 5 | 2 of 5 |

Batch 128 saved 40.6 MiB peak resident RAM and 43.6 MiB peak committed memory. Both profiles passed the labelled-rate and training-status cases and failed the dataset overview, unknown missingness cause and long overview cases. The comparison verdict was `retain_current_profile`.

The batch 512 worker dropped from 2,109.5 to 85.4 MiB resident after sleeping, releasing 2,024.1 MiB. Committed memory fell from 1,106.9 to 75.3 MiB. The authenticated wake request completed in 2.391 seconds, with 1,994.8 MiB resident after the answer. This verifies idle release and wake for the standalone hosted worker. Physical Windows coexistence with the desktop and analytics remains untested. The one-use approval is consumed and preserved in the launch history.

## 15 November 2026 | Consolidated R03 Windows worker comparison

The queued idle-release check is now part of one [hosted Windows run](../.github/workflows/p4-r03-qwen-idle-release.yml) that stages the pinned Qwen3 1.7B model and llama.cpp b10344 CPU runtime once. It starts a fresh worker for each physical batch size, 512 and 128, and holds the model, 2,048-token context, threads, and request sequence constant. The report includes startup time, per-request time, peak resident and committed memory, exact-answer scores, and the baseline worker's idle release and wake-up result. Four existing synthetic questions and one longer overview prompt exercise the batch sizes. The longer prompt must exceed 512 tokens while leaving room for the full response budget.

The review criteria required lower peak resident memory without increasing peak commit, matched prompt lengths, and all five answers correct before advancing the reduced batch to physical testing. The hosted comparison measures the worker alone. Physical coexistence with the desktop app and analytics remains a separate acceptance requirement.

## 15 November 2026 | Apply offline AI settings to automatic investigations

The investigation panel now reports when offline AI is disabled or Low-memory admission blocks a new plan. When these checks fail, a new run does not start and an interrupted run keeps its existing state. The backend checks again before each model call. Previously journalled evidence steps can still be recovered without a model. Manual analysis remains available.

## 15 November 2026 | Skip unnecessary Qwen startup for dataset insights

Ask ODIN and other dataset insight requests now check saved AI settings before starting the desktop worker. If offline inference is disabled or the effective provider is Local analytics, the authenticated preflight skips startup and sends the original insight request for normal processing. An explicit provider selection retains precedence over workspace and global defaults. Enabled offline requests still pass through the existing memory admission. This change covers dataset insights. Investigation autonomy continues to use its own execution path.

The focused local frontend and API checks passed, including an allowed launch request, a RAM defer and the deterministic answer after a settings skip. These checks use simulated launches. Physical Windows memory acceptance remains open. The prepared one-run idle-release workflow still targets its separately reviewed source.

## 15 November 2026 | Release bundled Qwen memory when idle

The desktop launcher now asks the existing pinned llama.cpp b10344 worker to sleep after 30 seconds of inactivity. The pinned server's sleep mode releases the model and inference cache and reloads them on the next inference request. Settings explains the reload delay. No model, context window, routing or admission floor changed. This targets RAM held between requests. It does not resolve the cold-start shortfall on the physical laptop.

The Windows verification command, `python desktop/verify_live_bundled_inference.py --verify-idle-release`, checks an authenticated completion, polls the non-waking `/props` endpoint, compares worker RAM before and during sleep, then verifies a second authenticated completion. The 11 resource/isolation source contracts and six simulated probe cases passed locally. The Windows runtime test and native compilation were **NOT RUN**. [Pinned runtime behavior](https://github.com/ggml-org/llama.cpp/blob/b10344/tools/server/README.md#sleeping-on-idle)

The [P1 frontend build and browser checks](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/43726167405) and [P2 export regression checks](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/43726167424) passed on [`ca811f3`](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/ca811f38dec9fe647ab7134039216b00e5e79ee6). Those jobs did not start Qwen.

The [one-run Windows workflow](../.github/workflows/p4-r03-qwen-idle-release.yml) is prepared. It triggers when its approval marker is added as the only change in a direct child of the reviewed source, then checks out that source before staging the pinned assets. The marker is absent. Both measured requests now use the same short prompt with thinking disabled and require complete, nonempty response text. This keeps a truncated reasoning response from deciding the memory test. Eight simulated checks passed, including sleep timeout, unchanged memory and failed or truncated wake completions. The live test is **NOT RUN**.

## 15 November 2026 | Lower memory use before modelling

The existing physical QA session already observed 0.73–0.82 GiB available with local analytics operational. That evidence establishes the R03 shortfall against the 2.0 GiB floor and does not need repeating on the same build. The backend now loads scikit-learn only on modelling paths. In a matched local Linux Python experiment, startup resident memory dropped from 150.7 to 89.3 MiB, and resident memory after an 80-row CSV import, Explore overview and Ask ODIN Local analytics dropped from 154.5 to 92.7 MiB. Both response digests matched and the lean path did not import scikit-learn or SciPy. Model catalogue construction, group and time split checks, and fitted-history reopen with prediction passed locally using a harness for the existing test functions. This is source-level Linux evidence. The Windows packaged process and physical 8 GB offline generation remain unmeasured for the change.

The [P4 workflow at `bcd5932`](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/43725536127) passed all three jobs, including 446 Python cases with one skip, the real HTTP browser suite and the generated Windows fixtures. It did not measure physical Windows memory or run Qwen.

## 15 November 2026 | Local AI memory readiness in Settings

Resource-Aware Mode now shows whether measured RAM meets the local AI start threshold when Low-memory mode is saved. Below the threshold it shows the shortfall and points to local analytics. An unavailable reading prompts a refresh. The notice uses the existing read-only RAM status and backend threshold. The admission policy and offline acceptance requirement still apply. Local verification passed five resource settings contract tests and eight direct display cases covering the laptop's observed headroom, the threshold, unavailable measurements and the other policy modes.

The [frontend workflow at `245b129`](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/43724819365) passed its TypeScript/Vite build, source contracts and targeted synthetic browser suite. The notice itself was exercised by the local display cases. The physical 8 GB inference test remains blocked pending its preflight.

## 15 November 2026 | N12 identifies the shared-request rejection

The fixture reports the failed eligibility check with a fixed label and omits raw identifiers. At [`b9da529`](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/b9da52957b408cc425da6acda378a89173590d43), [Windows CI](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/43724259651/job/132842635979) reported `extra-or-intervening-request-events`. The two candidate timestamps were distinct, the candidates agreed on the request ID and FileKey, and the last candidate matched an ordered successful completion. The full request sequence still differed from the required candidate records followed by exactly one completion. The fixture remained **BLOCKED**, with no path verdict. The log does not identify the extra events' types or positions.

All 62 focused generated cases passed using a standard-library harness because pytest was unavailable locally. [P4 CI](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/43724259651) passed all three jobs with 445 Python tests and one skip. [FileIO CI](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/43724259628) passed with 194 trace tests. The strict audit is unchanged. The 397 unresolved paths remain open.

## 15 November 2026 | N12 shared-request path trial

The fixture now trials a shared request only when candidate timestamps are distinct, the nonzero request ID and FileKey agree, and the observed sequence contains just those candidates and one ordered successful completion. The open and prior name must precede the first observation. A name change or conflicting identity through completion blocks the path. The strict app audit does not use this trial. Locally, 61 focused cases passed with the standard-library harness because pytest was unavailable.

At [`7a7aad7`](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/7a7aad7973ba6f66a1af0b05a64d842cf783ef89), [P4 CI](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/43723317752) passed all three jobs with 444 Python tests and one skip. [FileIO CI](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/43723317742) passed with 193 trace tests. The [Windows in-capture fixture](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/43723317752/job/132839782995) stayed **BLOCKED**. It again saw two candidates sharing one request ID and one candidate with an ordered successful completion. The trial did not reach a path verdict, and the published counts do not identify which eligibility check failed. The 397 unresolved paths remain open.

## 15 November 2026 | N12 adds a file created during capture

The ETW-only Windows fixture now creates a new disposable file after tracing starts. It seeds the file, verifies the handle path, records a distinct write and reads back its payload. The diagnostic compares the exact handle path with prior file-name evidence for that write's key. The report distinguishes a match, a mismatch and insufficient evidence. The existing pre-opened controls and strict audit remain independent. Locally, 42 focused generated cases passed with a standard-library harness because pytest was unavailable.

At [`f9a69d5`](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/f9a69d508b24df485ff6ee0490ac21205a59ba46), the [first Windows control](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/43721386304/job/132833924740) saw the file open but blocked on `write-missing-or-ambiguous`. The source and browser jobs and [FileIO rundown CI](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/43721386278) passed. The follow-up writes after the four-byte seed and adds redacted candidate counts for the same object, process, size and offset. Missing evidence is reported as a blocked control; an exact-path disagreement fails the job. Strict audit scoring remains in force.

At [`a18baa3`](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/a18baa3ccf401a765d32866a7625f65fdf7325f6), the first Windows job stopped at the generated dialog test. The [failed-job retry](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/43721624100/job/132835167658) passed the workflow checks and reported the added control as **BLOCKED**. Two events matched the measured size and offset. A follow-up constrains this control to the measured write call and excludes events explicitly marked as paging I/O. Generated cases include a paging record at the same size, offset and time window.

At [`31a04e3`](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/31a04e3492d039d1f97473f9ed1c8511be37c42d), [P4 CI](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/43722040972) and [FileIO CI](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/43722041052) passed. The [in-capture Windows control](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/43722040972/job/132835923106) stayed **BLOCKED**. Both events still matched the write window and neither was explicitly marked paging. The report could not choose one and emitted no request-time path verdict. This gives no new classification for the 397 unresolved paths from the collector rehearsal.

At [`4b601a9`](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/4b601a9e8071e228cba9e88cbfc8bc622afa3ab1), the [Windows fixture log](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/43722606777/job/132837622288) reported two candidate records, one shared request identifier and one candidate with an ordered successful completion under the existing matcher. This identifies a shared request ID within the measured write window. It leaves exact duplication versus identifier reuse unverified. The fixture still reports **BLOCKED** and emits no path verdict. All 49 focused local cases passed through a standard-library harness because pytest was unavailable locally. [P4 CI](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/43722606777) passed all three jobs, with 432 Python tests and one skip. [FileIO CI](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/43722606734) passed, including 181 trace tests. Strict audit scoring and the 397 unresolved paths remain open.

## 15 November 2026 | N12 request-time paths checked against fixture handles

The pre-opened fixture report now compares the ETW path at write time against the independently verified Windows handle. Stop-time rundown retains its own verdict. Previously, a missing or different rundown entry prevented the write-time comparison, including when the file was renamed after the write completed. Generated cases check renames before, during and after a write, an ordered key reset with a fresh name, conflicting names and object reuse. All 169 trace and 45 app-journey cases passed using a local standard-library harness because pytest was unavailable locally. Strict scoring was unchanged. The 366 candidates from the connection rehearsal remain unverified. [N12 runbook](../qa/p4_native/N12_TRACE.md#successful-writes-with-unresolved-paths)

At [source `147e00c`](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/147e00c80627e69f75669530089101d99515cc18), [P4 CI](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/43716555460) passed all three jobs, including 420 Python tests with one skip. [FileIO CI](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/43716555391) passed 169 trace tests and both Windows fixture steps. The baseline pre-opened controls in both workflows reported `no-prior-name-in-lifetime` for the protected and outside writes. Stop-time rundown recovered both control keys and the scoped strict control passed. The broader strict coverage blocker remained.

## 15 November 2026 | N12 connection rehearsal passed prelaunch and blocked on ETW paths

The [approved hosted Windows job #132816654192](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/43715705070/job/132816654192) ran on attempt 1 from launch `cef9615270de6b99b4f87e573dbd3ec21ba8e580` at reviewed source `071c5b92246306180b712378562ba7f26ce95c92`. Pinned Sysmon 15.22 and the shared prelaunch check **PASSED on read 1**. The expected child's TCP and UDP markers were observed, so the rejection diagnostics did not fire. The earlier app-journey failure did not recur in this collector-only setup. Both final reductions verified the expected fixture operations with zero reported file violations. The fixture birth precision correction was unused.

Strict coverage remained **BLOCKED** on `etw-mutation-coverage-unresolved`, and the job **FAILED**. Snapshots identified 131 stable background processes and removed all 397 missing process-lifetime findings. The same 376 writes and 21 resizes still lacked strict paths. Request-time diagnostics found 366 outside-protected path candidates, 24 operations with no prior name, six file-object lifetime changes and one possible name change. There were zero unmatched writes. Candidate paths remain diagnostic. PilotODIN compilation and launch were **NOT RUN** and no artifacts were uploaded. The one-use approval was consumed and the collector workflow is disarmed.

## 15 November 2026 | N12 prelaunch connection rejection diagnostics

The prelaunch log now distinguishes an export with no parseable records for a protocol from one with records rejected by the process, direction, address, port or timing criteria. It publishes counts and fixed categories only. Tests using generated XML verify missing protocols, identity and endpoint rejections, malformed out-of-window records, timing and the existing second-read recovery. All 45 journey cases passed through a local standard-library harness because pytest was unavailable locally. The nearby diagnostics and preservation unittest suites passed 13 cases with one platform skip. Live calibration with this diagnostic is **NOT RUN**. [Runbook](../qa/p4_native/N12_TRACE.md#hosted-journey-etw-gap-diagnostics)

At [implementation source `6173bd6`](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/6173bd6c5b651231448dead9ef1e83f7869b14e0), [P4 CI run 43714918726](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/43714918726) passed the source and frontend suite, browser checks and generated Windows checks.

## 15 November 2026 | N12 image-path run blocked at initial loopback calibration

The [approved Windows job #132810436882](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/43713653390/job/132810436882) ran once from launch `9ec403682d2b578fa9b8aac0c2d918b4903ee035` at reviewed source `11fa461761b2b8bd778f82a8efa5d1ed9a2f8ee6`. Dependency and driver preflight, the unpackaged build and provenance check, and reviewed Sysmon 15.22 setup passed. The executable SHA-256 was `2453afad97b0d0d33b9166bbaf95558f4064b418e387097a5f445ec24952c04b`. The resolved Cargo lock SHA-256 was `bec9d5bb1ab4fa30fc756bcd56677c5905005706ded3e6514af7d6429502e4d8`.

The fixture completed its local exchange. Both Sysmon reads reported empty matching TCP and UDP marker categories for the expected child. Initial calibration **BLOCKED** on read 2 with `child-loopback-tcp-or-udp-missing`; the job **FAILED**. The existing diagnostic cannot distinguish absent network records from records that fail the expected child, port or endpoint filters. Both app launches and the final audit were **NOT RUN**. The previous final image-path failure remains unverified against the updated parser, and comparison against 567 driver findings remains open. No artifacts were uploaded. The one-use approval was consumed and the workflow is disarmed.

## 15 November 2026 | N12 Sysmon image-path handling

The Sysmon parser now resolves explicit local DOS-drive aliases in process creation and exit records before comparing full executable paths. Generated cases cover both supported prefixes, prelaunch timing and identity mismatches. Unsupported image forms still block the audit with the event type, record number and a fixed path category. The public error omits raw paths. The hosted log did not identify the path form that failed, so recovery of that live case remains **UNVERIFIED**.

At implementation source [`6d1be2f`](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/6d1be2f6ec87ec1e1ec268e29e77632fc3d1fa8d), 204 focused cases and 444 broader local P4 tests passed with one broader platform skip. [P4 CI attempt 1](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/43712405057/job/132806632923) failed while generating the Windows loopback/file fixture before Sysmon parsing. The single failed-job retry passed on [attempt 2](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/43712405057/job/132807079532). The source, browser, and [N12 FileIO fixture checks](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/43712405079) also passed. The fixture's first failure cause was not identified.

## 15 November 2026 | N12 writer breakdown run blocked during Sysmon parsing

The [approved Windows job #132802635073](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/43711109138/job/132802635073) ran once from launch `d4caff4631f5fb79a2b2c27f8b017c519035ac00` at reviewed source `29e8aa8697920ec43d7ef6d29ef982eae7bc7d71`. Dependency and driver preflight, the unpackaged build and its provenance check, and reviewed Sysmon 15.22 setup passed. The executable SHA-256 was `a86702b3920349912526b2764f82ea019ea8744557c032f587bd34e2dfcecdf0`. The resolved Cargo lock SHA-256 was `bec9d5bb1ab4fa30fc756bcd56677c5905005706ded3e6514af7d6429502e4d8`.

Initial calibration passed on read 1. Both launches and the final calibration command completed. The final audit **BLOCKED** at `Sysmon XML: expected a drive-absolute Windows path` and the job **FAILED**. The public log does not identify the record or path form. No final writer breakdown, protected snapshot verdict, network verdict or filesystem verdict was emitted. The comparison against 567 driver findings remains **UNVERIFIED**. The one-use approval was consumed and the workflow is disarmed.

## 15 November 2026 | N12 writer breakdown prepared

The [fixture lead-in audit](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/43690425867/job/132739719330) recorded 567 driver findings. Of these, 489 fell solely under user-local or user-temp and 62 were renames spanning both categories. The other 16 were four frontend-dependency operations and 12 unsupported Windows-system operations. Vite, the interaction drivers and their descendants share the driver role, so those aggregates cannot identify the executable responsible.

The ETW audit now adds fixed writer categories to its redacted outside-scope summary. It uses the Sysmon identity already matched to each scored operation and reports Node, esbuild, PowerShell, Python, WebView2, or a generic fallback. Generated evidence confirmed that the existing counts and audit verdicts match with or without the new breakdown. Actual Windows writer counts for the new source are **NOT RUN**. [Runbook](../qa/p4_native/N12_TRACE.md#hosted-journey-etw-gap-diagnostics)

Local verification passed 192 focused tests and 432 broader P4 tests with one platform skip. All three [P4 source, browser and Windows fixture jobs](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/43710517133) and the [N12 FileIO fixture job](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/43710517058) passed at implementation source [`fd11e28`](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/fd11e28af8fc0260015e5d9cacf39dc035be8e2f).

## 15 November 2026 | N12 interaction driver scratch isolation

The two hosted interaction driver launches now set `TEMP` and `TMP` to a dedicated `driver-temp` directory within the disposable journey workspace. Playwright uses Node's operating-system temp directory for CDP scratch files. The backend, app, WebView and Vite retain their previous environment. The existing audit permits the new directory only for the driver role. Generated tests exercised both driver launches and verified that a write to a similarly named sibling, a write to a protected root and a backend write to the driver directory still fail. [N12 runbook](../qa/p4_native/N12_TRACE.md#hosted-journey-etw-gap-diagnostics)

This targets a known source of temp writes. The live report grouped 551 driver findings under user-temp or user-local, so the number redirected by this change is **UNVERIFIED**. No new hosted app journey ran for this change. The previous filesystem and network failures and strict coverage blockers remain open.

Local P4 regression: **431 passed, one platform skip**. At source [`e771cb3`](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/e771cb383e265e452954a53fdc7a13d18c0377f2), all three [P4 source, browser and Windows fixture jobs](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/43710018054) and the [N12 FileIO fixture job](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/43710017991) passed.

## 15 November 2026 | Fixture lead-in journey reached the final audit

The [approved hosted Windows job #132739719330](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/43690425867/job/132739719330) ran once from launch `a28959dbc10d02b8ceaf6b01e880c9fc40d21b93` at reviewed source `f8e02357f821b3483948606af23fe355a0dd8cbb`. The unpackaged build and provenance checks passed. The executable SHA-256 was `409b5374d916726827453e9ee158c8309be07eb2b97477989c8291e40f464a6b`. The resolved Cargo lock SHA-256 was `278c01520af08f34b8861fc8191f283e0e5bb2223c2458e5f99ca5d7cd7d374f`. Pinned Sysmon 15.22 provisioned successfully. Initial calibration passed on the first read with the 50 ms lead-in. Both launches, the interaction drivers, the final fixture command and the audit completed.

- **Protected snapshot comparison MATCH.** All four protected roots and the immutable source fixture matched at the before/after endpoints. The audit reported no protected-root mutation. The comparison covers the disposable runner.
- **Filesystem FAIL.** The audit recorded 608 outside-scope operation findings: 567 from the driver, 39 from WebView and two from the backend. Of the driver findings, 551 involved user-local or user-temp path categories.
- **Network FAIL.** Four unexpected loopback connections and four non-loopback connections were observed. Both WebView NetLogs parsed. The audit correlated two DNS transactions, one HTTPS request and three HTTP requests. One WebView UDP/443 connection matched a socket with unattributed purpose. The backend loopback connection was outside WebView attribution.
- **Strict coverage BLOCKED.** `calibration-tcp-or-udp-missing` and `etw-mutation-coverage-unresolved` remained. Initial calibration had passed and the final fixture file operations matched. The report did not identify the missing protocol in the full audit. ETW had 197,874 WebView network-process writes with unresolved paths. The overall job **FAILED**. The one-use approval was consumed and the workflow is disarmed.

## 15 November 2026 | Protocol diagnostic journey blocked by fixture birth timing

The [hosted Windows run #43689529985](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/43689529985/job/132737016063) ran once from launch `8a1efbe2f077dc8b957a4f5ad8aeb0008b96914c`, checking out reviewed source `4927e819bd19006057c3de056931d131b2a92178`. Dependency and driver preflight, the unpackaged QA build, executable provenance verification and pinned Sysmon 15.22 setup passed. The executable SHA-256 was `6d5b241e96400fbc6a671cfb9ae7892d1285d7680ab773f00c65b8a9f355086e`. The resolved Cargo lock SHA-256 was `278c01520af08f34b8861fc8191f283e0e5bb2223c2458e5f99ca5d7cd7d374f`.

**Job FAILED. Initial calibration BLOCKED** on read 1 with `parent-birth-before-window`. One matching Sysmon birth was 74 µs before the window start. The independent Windows process creation time was 574.9 µs inside, in the same millisecond, giving a 648.9 µs difference between sources. The child protocol diagnostic, both app launches and the final audit were **NOT RUN**. The prior missing-protocol finding still lacks protocol-specific live evidence. The one-use approval was consumed and the workflow is disarmed.

## 15 November 2026 | Protocol-specific prelaunch diagnostics

When initial calibration lacks a required child loopback marker, the shared guard now prints redacted TCP and UDP counts for matching records. It distinguishes absent markers from observed records before child birth, after child exit or outside the frozen read window. The existing lifetime check and bounded retry still apply. Generated Sysmon XML tests show that absent and out-of-window records block as before, and that a valid UDP record delivered on read 2 can pass. The earlier hosted failure cannot be assigned to a protocol from its retained summary.

## 15 November 2026 | Focused Windows app run blocked at initial calibration

The [approved hosted Windows run #43687529172](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/43687529172/job/132731018243) ran once from launch `9272850659d9e316ef96dba6d630bf5d2cc53908`, pinned to reviewed source `34557075a1e842eec47591a160441e4b934575cd`. Dependency and driver preflight, one unpackaged QA build, binary provenance verification and pinned Sysmon 15.22 setup passed. The executable SHA-256 was `2d000932ffce52ebddb0717785b829b2c67aa4e620589b2e14db3bf5d49eb424`. The resolved Cargo lock SHA-256 was `278c01520af08f34b8861fc8191f283e0e5bb2223c2458e5f99ca5d7cd7d374f`.

**Job FAILED. Initial calibration BLOCKED** on read 2 with `child-loopback-tcp-or-udp-missing`. The fixture command completed, which requires the parent to receive both marker payloads locally. The Sysmon export did not establish both protocol events for the identified child inside its accepted lifetime. The aggregate blocker leaves the missing protocol and the reason unresolved. **First launch, relaunch and final audit NOT RUN.** No new protected fingerprint comparison, filesystem verdict or network verdict was produced. The previous completed app-journey findings remain open. The one-use approval was consumed and the workflow is disarmed.

## 15 November 2026 | Focused isolation evidence

The app-journey audit now reports a direct comparison of the protected roots and immutable fixture fingerprints, alongside its existing filesystem and network verdicts. Generated cases show a fingerprint match alongside blocked trace coverage or a directly observed protected mutation. An unexpected fingerprint difference reports `CHANGED`, and a missing immutable fixture baseline blocks the comparison. The fingerprint result describes the observed endpoints of the test window. The collector reducer also reports what rundown contributes specifically to operations with no prior name. The generated comparison found one candidate among five such operations and preserved every strict finding. [Runbook](../qa/p4_native/N12_TRACE.md#reduce-combined-etw-and-sysmon-evidence)

## 15 November 2026 | Live FileKey diagnostic rehearsal

The [approved Windows job #132727321305](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/43686281881/job/132727321305) ran on attempt 1 from launch `495d9c990ffea58ecff355a173c51daa04daa1a2`, checking out reviewed source `bef278bff281357da87090467c28e6a423295c14`. Pinned Sysmon 15.22 setup and prelaunch passed on read 1. Both reductions verified the expected fixture operations with zero protected-file violations. `fixture_birth_adjusted=false` for this capture. The snapshots verified 129 stable background processes and resolved all 821 observed lifetime gaps. Both reductions gave identical path and completion diagnostics.

| Request-time diagnostic | Writes | Resizes | Total |
| --- | ---: | ---: | ---: |
| Candidate path outside protected roots | 257 | 22 | 279 |
| No prior name in the observed lifetime | 262 | 268 | 530 |
| File-object lifetime changed | 2 | 7 | 9 |
| Possible name change | 0 | 1 | 1 |
| Conflicting key on the same file object | 1 | 1 | 2 |
| Total strict path gaps | 522 | 299 | 821 |

**Job FAILED. Strict coverage BLOCKED** on `etw-mutation-coverage-unresolved`. The 279 candidates are diagnostic and all 821 strict path gaps remain. There were zero unmatched writes in this capture. The two unmatched writes in the previous capture remain recorded and their timing is unknown. No native rundown was collected and no PilotODIN compilation or launch occurred. The one-use authority was consumed and the workflow is disarmed.

## 15 November 2026 | FileKey and write-completion diagnostics

The combined reducer now reports redacted request-time path-candidate counts for successful writes and resizes with missing paths, plus the distance from unmatched write requests to the end of the audit window. An optional digest-pinned FileIO rundown adds diagnostic-only counts. Generated CLI evidence distinguished protected and outside candidates, conflicting names and object keys, cleanup, late names and a completion tied with rundown stop. The same fixture retained its strict blockers and protected violation with and without rundown. A modified rundown failed its digest check. Local P4 Python checks passed 403 tests with one platform skip. [Runbook](../qa/p4_native/N12_TRACE.md#reduce-combined-etw-and-sysmon-evidence)

## 15 November 2026 | Live collector process-snapshot comparison

The [approved Windows collector job #132723162580](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/43684880159/job/132723162580) ran once from launch `ecf3a43485d02fccbdb1f8c6e353a168387a6643` and checked out reviewed source `0ca097f0c346b3a4ebe231a7acccc3a29fc081ce`. Sysmon 15.22 verified against its pinned hash and prelaunch passed on read 1. The fixture birth precision rule was exercised: the Sysmon birth was 2 µs before the fixture window and the independent Windows creation time was 495.5 µs inside it, in the same millisecond. Both final summaries reported `fixture_birth_adjusted=true`, the expected fixture operations, and zero protected-file violations.

| Evidence from one capture | Without snapshots | With snapshots |
| --- | ---: | ---: |
| Background writes missing a process lifetime | 305 | 0 |
| Background resizes missing a process lifetime | 45 | 0 |
| Background writes missing a file path | 305 | 305 |
| Background resizes missing a file path | 45 | 45 |
| Writes without a matched completion | 2 | 2 |

The reducer verified 133 stable background processes. All 350 successful operations with a missing path had a FileKey and an observed header lifetime after the comparison. Issuing-thread identity remained unverified. **Job FAILED, strict coverage BLOCKED** on `etw-mutation-coverage-unresolved`. No PilotODIN compilation or launch occurred. The one-use approval was consumed and the workflow is disarmed.

## 15 November 2026 | Collector process snapshots integrated

The collector rehearsal now reduces the same capture with and without before-and-after process snapshots. Generated CLI evidence resolved one write, one resize and one rename lifetime gap for the stable background process. All five missing-path findings and the protected rename violation still blocked coverage. Reused PIDs, observed lifecycle transitions and the scoped calibration process could not seed a lifetime. An empty snapshot failed closed. The comparison emits aggregate counts. [N12 runbook](../qa/p4_native/N12_TRACE.md#reduce-combined-etw-and-sysmon-evidence).

## 15 November 2026 | Collector prelaunch passed and final ETW coverage blocked

The [approved collector-only run #43672824700](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/43672824700/job/132686419880) ran from launch `bf071287996748cd3e9d9df7511b6c7130353d00` at reviewed source `9301320baf5596ede34360f530ab17f2d1a16494`. Pinned Sysmon setup and the shared prelaunch guard passed on read 1. The combined reducer observed the expected fixture file operations and reported zero file violations. `fixture_birth_adjusted=false`; live evidence did not exercise the precision rule. The job failed on `etw-mutation-coverage-unresolved`. The summary recorded 732 background writes and 522 resizes lacking both path and process-lifetime attribution, plus one rename lacking a lifetime. The path and lifetime counters overlap for writes and resizes. [Full run record](https://github.com/Sonkhe-Shongwe/PilotODIN/blob/07dbaa749fea9bf90bf4debf534246f875132395/docs/SESSION_HANDOFF_CURRENT.md#15-november-2026--collector-prelaunch-passed-and-final-etw-coverage-blocked).

The [prior two-launch app journey](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/43629894863/job/132553947362) still has open network and filesystem failures. Successful fixture calibration alone cannot close those findings. The [physical 8 GB offline Qwen check](https://github.com/Sonkhe-Shongwe/PilotODIN/blob/07dbaa749fea9bf90bf4debf534246f875132395/docs/SESSION_HANDOFF_CURRENT.md#14-november-2026--r03-stopped-at-the-memory-preflight) stopped at memory preflight. R06 remains a historical strict failure with 74 differences and an unknown writer. Prospective owner-device preservation is pending.

## Next engineering action

Follow the [N12 plan review](./P4_80_ACCEPTANCE_WORKLIST_AND_EVIDENCE_INTAKE_2026-11-12.md#n12-plan-review-and-acceptance-risks). Generated traces reproduced false passes in connection identity, role-specific loopback scope and final calibration bracketing. First correct and regress those cases and verify that a sanitised failure checkpoint survives cleanup failures. Then validate the applicable Windows collector controls before requesting another unpackaged app build.

The live collector and hosted app-journey workflows are disarmed. Their one-use approvals were consumed. Any new live capture needs separate owner approval. The intermediate installer freeze and owner-data preservation restrictions remain in force. P4 engineering closure requires separate owner signoff. [Phase policy](./PHASE_FOCUS_AND_CLOSURE_POLICY_2026-10-28.md)

## Verified source checks

The fixture lead-in passed 35 focused local checks and 409 broader local Python tests with one platform skip. [P4 CI #43690121057](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/43690121057) passed at [`f6ad497`](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/f6ad497763f64d47765a419e0b4a516e449c172c). The approved live app journey with the lead-in has its own source and verdict above.

The protocol diagnostic passed 30 focused cases and 409 broader local Python tests with one platform skip. At source [`60d84db`](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/60d84dbe86ee5e8cf3a840565e97c78799619bde), [P4 CI #43688313628](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/43688313628) and [N12 FileIO fixture CI #43688313600](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/43688313600) passed. A live app journey with this diagnostic was NOT RUN.

Local Python verification passed 403 tests with one platform skip. At source [`a9e18fc`](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/a9e18fc9f20a95c63f231ef194b7d7e11035922a), all three [P4 CI jobs](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/43687194160) and the [N12 FileIO fixture job](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/43687194163) passed. The approved hosted follow-up has its own tested source and outcome above.

[P4 CI #43685954438](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/43685954438) passed the source, browser and Windows fixture jobs at [`c5e1a9a`](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/c5e1a9aa10925ff5c47570486f6b3985a24298a4). [N12 rundown CI #43685954469](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/43685954469) passed the generated regression suite and hosted FileIO fixture controls at the same source. The approved live capture has its own tested source and verdict above.

Local Python checks for the process-snapshot increment passed 403 tests with one platform skip. A local Node run passed 48 checks and could not load four test files because Playwright or TypeScript was absent from the checkout. At source [`859a39a`](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/859a39a40c06fc592110eff6843704ef9edcb87a), [P4 CI #43684527747](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/43684527747) passed its source, browser and Windows fixture jobs. [N12 rundown CI #43684527749](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/43684527749) passed the Python regression suite and hosted generated ETW controls. The live comparison used its own reviewed source and verdict above.

[P4 CI #43672531160](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/43672531160) passed all three jobs at source `8f57d22a374f0b56043e3789b3260291fecb78ce`: 381 Python tests, one platform skip, 80 Node checks, TypeScript/Vite, 12 browser cases and Windows fixture checks. [N12 rundown #43672531159](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/43672531159) passed 147 tests and hosted ETW controls at the same source. The live collector run above has its own source and verdict.

For issue history and new evidence, use [master QA #2](https://github.com/Sonkhe-Shongwe/PilotODIN/issues/2) and [P4 owner evidence #9](https://github.com/Sonkhe-Shongwe/PilotODIN/issues/9).

## Historical chronology

[Complete chronology as of 15 November 2026](https://github.com/Sonkhe-Shongwe/PilotODIN/blob/07dbaa749fea9bf90bf4debf534246f875132395/docs/SESSION_HANDOFF_CURRENT.md). Earlier section URLs lead here. Use the snapshot’s outline to locate the original entry.

- [Full app-journey audit failure](https://github.com/Sonkhe-Shongwe/PilotODIN/blob/07dbaa749fea9bf90bf4debf534246f875132395/docs/SESSION_HANDOFF_CURRENT.md#14-november-2026--n12-hosted-app-journey-completed-with-audit-failures)
- [Prospective R06 endpoint preparation](https://github.com/Sonkhe-Shongwe/PilotODIN/blob/07dbaa749fea9bf90bf4debf534246f875132395/docs/SESSION_HANDOFF_CURRENT.md#14-november-2026--prospective-r06-endpoint-checks-prepared)

<!-- These anchors preserve links to the previous chronology. -->

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
