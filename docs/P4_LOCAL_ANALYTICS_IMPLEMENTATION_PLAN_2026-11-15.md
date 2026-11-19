# PilotODIN P4 Local analytics implementation plan

**18 November 2026 checkpoint.** The owner agreed to improve Ask ODIN's Local analytics first and evaluate additional model components only if they improve measured results. The native median and filter-changing follow-up have scoped owner acceptance. The physical offline retest remains paused under ordinary laptop conditions. [P4 scorecard](./PROJECT_STATUS_CURRENT.md#p4-engineering-scorecard) · [Headroom decision](#ordinary-laptop-memory-and-offline-inference)

## Current evidence

| Evidence | Result and scope |
| --- | --- |
| Ask ODIN on hosted Windows | The expanded milestone's API test returned all five expected fact sets at simulated 0.73 GiB available and peaked at 102.4 MiB resident. The measurement covered the API process. [Milestone run](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/43753907245) · [Earlier 102.3 MiB baseline](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/43744796818/job/132905610069) |
| Qwen3 1.7B batch comparison | Batch 512 peaked at 2,109.5 MiB and batch 128 at 2,068.9 MiB. Both scored 2 of 5. The batch 512 worker released 2,024.1 MiB at idle and answered after waking. The comparison retained batch 512. [Windows run](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/43740595746/job/132892675147) |
| Smaller generative models | Qwen3 0.6B peaked at 934.9 MiB and scored 2 of 4. SmolLM2 360M peaked at 420.0 MiB and scored 1 of 4. Neither cleared the earlier structured answer screen. These worker measurements exclude PilotODIN and its dataset. [Small-model run](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/43593329731/job/132442500969) |
| Model-free wording experiment | The separate word-overlap follow-up selector got 4 of 8 original questions and 2 of 8 paraphrases right. It correctly abstained on all 12 unclear questions. This tested selection from fixed options. [Benchmark](../desktop/evaluate_offline_follow_up_rules.py) |
| Physical 8 GB laptop | The owner accepted the native filtered median and follow-up. The everyday retest measured a 735.27 MiB sampled combined working-set peak and verified the HTML export. The 1.50 GiB candidate deferred bundled Qwen and returned local rules. A later Settings reading showed 0.936 GiB available against the 2.00 GiB floor. Request-time memory, physical offline generation and coexistence need separate evidence. [Physical measurements](./RESOURCE_AWARE_MODE_DESIGN.md#physical-everyday-ram-retest-result) · [Headroom decision](#ordinary-laptop-memory-and-offline-inference) |

The pre-milestone Local analytics path supported exact overview, missingness, labelled-rate and training-status requests. In a disposable real API check at `98affa4`, an ordinary-language labelled-rate question, a filtered median question and a follow-up returned the general dataset overview. The group missingness question inspected the wrong field. The expanded milestone passed the API and browser checks. [Milestone evidence](./SESSION_HANDOFF_CURRENT.md#15-november-2026--ask-odin-local-analytics-milestone)

## Milestone acceptance examples

The smoke fixture uses four records. Outcomes are `Yes`, `No`, `Yes`, and blank. Premiums are `20`, blank, `40`, and `50` in the same order. Verify the interpreted request alongside the result.

| Ask ODIN request | Expected behaviour |
| --- | --- |
| Which outcomes have the most missing premiums? | Measure missingness in `premium` and group by `outcome`. Report `No` as 1/1 missing and `Yes` as 0/2 missing. Account explicitly for the one row with a blank outcome. If field resolution is ambiguous, ask the user to choose. |
| What percentage of labelled outcomes are Yes? | Count 2 Yes values among 3 labelled outcomes, or 66.6667%. Report the excluded blank outcome. |
| What percentage of all rows have a Yes outcome? | Count 2 Yes outcomes across 4 rows, or 50%. Show the denominator explicitly. |
| What is the median premium for Yes outcomes? | Return 30 from 2 usable rows and show the outcome filter. |
| What about No? | After the median question, keep the measure and operation and change the outcome filter to `No`. Report one matching row, zero usable premiums and no median. |
| What about No? after changing projects or dataset versions | Ask for the measure or a new question. The earlier filter and metric belong to the earlier project and version. |
| Why are premiums missing? | Report the observed missingness and qualify the cause as unknown from these records. |

## Implementation sequence

1. **Represent the request.** Use existing schema metadata to resolve the operation, measure, optional group, filters and denominator. Keep a small set of operations for dataset and quality questions, recorded training status, counts and rates, filtered summaries and grouped comparisons. Match common wording and unambiguous field aliases. Give users field or value choices when there is more than one valid interpretation. Preserve the existing question shortcuts.
2. **Validate before execution.** Check the active project and Quality version, field types, label values, supported filters and denominator. Treat missing fields, ambiguous wording, unsupported requests and empty selections explicitly. Include the exact group-missingness failure in the first regression. Route specific unsupported requests to a clear explanation and a relevant supported action.
3. **Reuse local computation.** Use the existing filtering and analytics code for a single working dataset. Reuse matching count, aggregation and missingness semantics from Explore and Investigate. Keep data access read-only for these operations. Show the measure, grouping, active filters, usable and excluded rows, and working dataset version with the answer. Report missing versus zero and distinguish a count from a rate. [Analytics](../backend/analytics.py) · [Filters](../backend/explore_filters.py) · [Investigation operations](../backend/investigations.py)
4. **Support one follow-up.** Retain the last validated analysis for the active project and Quality version. Resolve a follow-up that changes one filter value, then validate the revised request again. Clear the reference when the project or version changes. Keep follow-up interpretation visible alongside its result.
5. **Verify the complete workflow.** Run the held-out benchmark and browser checks on the same implementation. Prepare one source-matched physical Windows desktop session when the benchmark passes and the existing native approval conditions are met.

For the first milestone, the executor accepts a defined set of local operations and validated arguments. Keep arbitrary generated SQL or Python, automatic dataset edits, whole-table model prompts and per-row vector indexes outside this implementation. Keep the existing provider choices available under their current settings. The Local analytics workflow should complete without loading Qwen or invoking a cloud provider.

## Follow-on experiments

| Option | When to evaluate | What qualifies it |
| --- | --- | --- |
| Word and character n-grams with a linear classifier | Clear paraphrases remain unsupported after the rule-based baseline. | Additional correctly answered held-out prompts at comparable wrong-answer and abstention rates. It proposes the operation and leaves field and filter validation to the existing request checks. |
| Compact CPU embeddings | A classifier still misses semantic paraphrases or documented column aliases. | Measurable coverage beyond the cheaper baseline under the same desktop memory workload. Use questions or documented aliases as the matching corpus. |
| Small local LLM with constrained output | More complex phrasing has measurable unmet demand and the device can admit the worker. | Better end-to-end results against the same held-out set and an acceptable cold-start and peak-memory profile. Limit output to supported operations and validate the interpretation before executing it. |
| DuckDB or another execution engine | Profiling shows that current scans, copies or grouping dominate memory on representative larger datasets. | Lower peak memory or faster answers on those workloads with matching filter, null and aggregation semantics. Measure spill and total process memory as well. |

Prototype components against the same fixtures before adding dependencies. Start with current-data reuse and necessary columns when profiling shows excess materialisation. Compare actual resident and committed memory, cold and warm latency, and correct answers. Download size and well-formed structured output alone provide limited evidence about runtime fit and interpretation quality.

## Verification and decision

**19 November provider context result.** When Quality imputation was approved mid-request, the old Ask ODIN route sent the newly corrected facts to the provider under a response that named the earlier version. One working snapshot now supplies the Quality findings, provider input and local computations. All nine insight contexts passed a generated API comparison. The seven-request synthetic Ask ODIN workload reduced dataset materializations from three to one per request. This measured the Linux API with a stubbed provider. Physical memory, worker admission and coexistence require the tests below. [Exact results](./SESSION_HANDOFF_CURRENT.md#19-november-2026--keep-ask-odin-on-one-working-version)

- **Correctness.** Use held-out datasets with different schemas from the smoke fixture. Include paraphrases, conflicting aliases, blank and zero values, empty groups, ambiguous denominators, stale versions and questions that require clarification. For each case, assert the chosen operation and fields before checking the numeric result, explanation and dataset version. Log correct answers, wrong answers, clarifications and unsupported requests separately.
- **Required regressions.** Pass the milestone examples, preserve all previously supported exact answers, and verify deterministic clarification when the field or denominator cannot be resolved. Confirm no unintended training, data edits, provider launches or external calls for the tested Local analytics requests.
- **Resource evidence.** Record cold and warm latency and process memory on representative small and larger fixtures, with repeated questions. In the physical desktop session record the app, backend and WebView2 working sets or private bytes, minimum system available RAM, paging and responsiveness across startup, workload and cooldown. Use the current baseline and agree workload-specific limits before the physical run. [Windows process memory counters](https://learn.microsoft.com/en-us/windows/win32/psapi/process-memory-usage-information)
- **P4 disposition.** A model-free desktop pass supports Local analytics on the tested hardware and build. R03 offline Qwen generation and coexistence remain separate acceptance evidence under the existing 2.0 GiB preflight. Use the [phase ledger](./PROJECT_STATUS_CURRENT.md#p4-acceptance) for N12, preservation and signoff.

<a id="proposed-physical-windows-session"></a>

## Physical Windows session record

The owner confirmed that the Live Dev check worked on 16 November and approved one unpackaged Tauri build and launch. The build and approved relaunch have been exercised. The commands below document that session. A future native run needs its own applicable approval. The [approval record](./P4_R03_OWNER_NATIVE_APPROVAL_2026-11-16.md) pins the reviewed application source. The existing [hosted runner](../qa/p4_native/Run_P4_71_Disposable_Windows.ps1) demonstrates the startup pattern and remains restricted to hosted CI.

1. Record the exact source and executable SHA-256. Verify the isolated Tauri identity, disposable backend workspace and separate WebView2 profile before running the questions. Use the same four-row fixture in the disposable workspace. Keep the installed PilotODIN closed and leave its projects outside the test.
2. Record system RAM and paging before launch, at the ready screen, during the questions and after cooldown. Attribute process readings to the native shell, its WebView2 profile and the development backend. Record sampled working sets and private bytes, elapsed response times and any visible UI stall.
3. Run the [five-question smoke workload](./LIVE_DEVELOPMENT.md#local-analytics-smoke-check) once through the native UI. The driver verifies the Tauri bridge, answers and filter follow-up and records click-to-verified-answer times. Record visible stalls and keep any incomplete run at the stage it reached.

The procedure called for pulling the development branch and closing the installed app and both Live Dev consoles to free the required loopback ports. The approved launch command was:

```powershell
py -3 .\tools\Verify_Local_Analytics_Windows_Native.py --run-approved
```

The preflight uses the existing Live Dev dependencies and checks for Rust x64 MSVC and the C++ build tools. The runner exports the reviewed backend, frontend and native source from Git into the temporary folder. It stages the committed QA helpers and copies the installed frontend dependencies. Local edits and untracked files can stay in the checkout. The runner compiles and launches once, generates its own four-row project, collects system and scoped process samples, closes the verified QA window and prints and saves `result.json`. A preflight block happens before compilation. A later failure is recorded with its stage and local logs.

The result covers model-free Local analytics in an unpackaged native shell. The packaged sidecar and offline Qwen coexistence are outside this session. The installer freeze remains in force.

### Resume after a WebView2 automation timeout

The reviewed runner created an executable and ended at `native_launch` while polling `9331/json/version`. The owner retained the original run folder and used the one-time relaunch command for that exact build:

```powershell
py -3 .\tools\Verify_Local_Analytics_Windows_Native.py --relaunch-approved pilotodin-r03-native-1v829nh2
```

The runner checks the prior receipt, executable hash and Cargo lockfile hash. It starts a fresh disposable backend and WebView2 profile with CDP disabled. It verifies all five responses through the API. The terminal prompts you to check the median and its follow-up inside the desktop window while RAM and paging are sampled. Press **P** in the terminal if both UI answers matched, or **F** if either failed. A successful result is recorded as `PASS_WITH_OWNER_OBSERVATION`. Click-to-render timings and a fully automated native UI pass remain unmeasured in this mode.

On 16 November 2026 the owner accepted both native answers from screenshots after the terminal acknowledgment timed out. The [scoped result](./SESSION_HANDOFF_CURRENT.md#16-november-2026--native-local-analytics-answers-accepted) covers the median and its filter-changing follow-up. The later [everyday RAM walkthrough](./RESOURCE_AWARE_MODE_DESIGN.md#physical-everyday-ram-retest-result) supplies model-free resource measurements for its own workload.

## Owner offline Qwen retest

This section records the original test procedure. The owner paused the physical baseline under ordinary laptop conditions. Review the [current decision for ordinary laptop memory](#ordinary-laptop-memory-and-offline-inference) before planning a separately approved retest.

Use [the one-use build's GitHub Actions page](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/44095354691) to download `PilotODIN-P4-R03-Owner-QA` once the handoff records its successful publication. Extract it to its own folder. The kit contains the corrected desktop, the source-matched analytics engine and checksums. The [launcher](../tools/Start_P4_R03_Offline_QA.ps1) uses Qwen files already present in the separate `pilotODIN-P4-Native-QA` installation. It copies only the verified worker, GGUF and listed DLL files. The new app uses its own data identity and temporary WebView2 profile.

From the current development branch of the PilotODIN repository, run the launcher in PowerShell. Substitute your actual extracted folder if it differs from the example.

```powershell
& .\tools\Start_P4_R03_Offline_QA.ps1 -KitDirectory "$env:USERPROFILE\Downloads\PilotODIN-P4-R03-Owner-QA"
```

1. Import the generated CSV at the path printed as `Import this synthetic CSV`.
2. In Settings, select **Low-memory** and save the resource preference. Set **Operating mode** to **Offline**, enable model inference, set **Local timeout** to **120s**, keep cloud reasoning off, and save AI settings.
3. Disconnect the laptop from Wi-Fi and wired internet. With the desktop open, refresh the available RAM reading. Proceed when it shows at least **2.00 GiB**.
4. In Ask ODIN, select **Offline Qwen3 (desktop) / Ollama (dev)**. Ask once, “In one sentence, explain why I should check for missing values before training a model on this dataset.”
5. Record the launcher-reported desktop SHA-256, available RAM, answer or error, its provider label and whether the app stays open. A response labelled **BUNDLED · pilotodin-qwen3-1.7b** with the app still open satisfies the narrow R03.3 retest. If the launcher, memory check or request stops, preserve the exact output and the observed stage.

This test uses a generated CSV and evaluates one cold-start response. Sustained resource coexistence is assessed separately under R03.4.

### Ordinary laptop memory and offline inference

On 18 November the owner confirmed that 2.00 GiB of available system RAM is impractical in normal use. In the open `r03-memory` project, Settings showed **0.936 GiB available of 7.80 GiB physical RAM**, Low-memory mode saved and a **2.00 GiB** local AI admission floor. The display therefore reported a **1.064 GiB** shortfall. This was a Settings reading. Request-time memory and generation were outside this observation. The older 1.50 GiB QA candidate also deferred on its separate physical attempt.

Pause the current physical Qwen retest at this workload. Local analytics remains available. Before proposing another physical inference run, measure an offline option at representative system headroom around **0.9–1.0 GiB**, verify response quality, and record the app and worker memory, paging and responsiveness together. Retain the previously completed Local analytics and HTML export readings for comparison. [Everyday RAM range and results](./RESOURCE_AWARE_MODE_DESIGN.md#everyday-ram-range-and-system-headroom)

<a id="next-physical-run-at-the-200-gib-baseline"></a>

### Reference procedure for the 2.00 GiB baseline

Use the existing [PilotODIN-P4-R03-Headroom-QA build](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/44106241769/artifacts/14339122820) while the artifact is available. The launcher uses the bundled Qwen files from the separate `pilotODIN-P4-Native-QA` installation. Extract the kit, close PilotODIN and Live Dev windows, and pull the active branch. The normal-policy baseline uses a fresh disposable benchmark profile. The archive switch renames the previous baseline profile after staging and verifying the kit and runtime files.

```powershell
$kit = "$env:USERPROFILE\Downloads\PilotODIN-P4-R03-Headroom-QA"
& .\tools\Start_P4_R03_Offline_QA.ps1 -KitDirectory $kit -BenchmarkProfile baseline -ExpectedSource '8966edc781128baa94354df044bfadc45d069984' -ArchiveExistingQaProfile
```

Import the printed synthetic CSV. In Settings select **Low-memory** and **Offline**, enable local inference, and save with a **120-second local timeout**. Disconnect Wi-Fi and any wired network. Refresh available RAM with the desktop open and run the smoke question when the reading reaches at least **2.00 GiB**. Ask ODIN once through **Offline Qwen3 (desktop) / Ollama (dev)** using “In one sentence, explain why I should check for missing values before training a model on this dataset.” Capture the visible answer and provider or the exact deferral. Close the QA desktop to finish capture, then upload the printed `PilotODIN-R03-Offline-Evidence.zip` and the result screenshot. The ZIP records the admitted or deferred request, provider and fallback outcome when available, and system RAM, paging and desktop responsiveness. A missed Windows sample is flagged and collection continues.

R03.3 needs one verified bundled answer on the disconnected laptop. Measure process-attributed coexistence separately for R03.4. The [completed Local analytics RAM walkthrough](./RESOURCE_AWARE_MODE_DESIGN.md#physical-everyday-ram-retest-result) supplies the model-free comparison.

### R03 candidate at 1.50 GiB available

The 1.50 GiB candidate was exercised on the physical 8 GB laptop. Settings showed 1.474 and 1.517 GiB on separate refreshes. The request deferred bundled startup and returned verified rules. The screenshots leave request-time headroom and the precise deferral code unverified. Preserve the benchmark files and compare against the later [whole-app Local analytics baseline](./RESOURCE_AWARE_MODE_DESIGN.md#physical-everyday-ram-retest-result). The procedure below is the reproducibility record for a later separately approved R03 comparison. [Candidate result](./SESSION_HANDOFF_CURRENT.md#17-november-2026--physical-r03-candidate-deferred)

The existing Windows worker comparison measured approximately **2.06 GiB peak resident RAM** and **1.08 GiB peak committed memory** for the normal profile. These are worker-only measurements on the hosted machine and measure different things from pre-launch system availability. The comparison gives no proven minimum startup headroom on the laptop. [Worker evidence](./SESSION_HANDOFF_CURRENT.md#15-november-2026--r03-windows-comparison-completed)

Compare the current 2.00 GiB floor with the isolated 1.50 GiB candidate while keeping the model, inference arguments, fixture, question, timeout and offline setup fixed. Exercise one cold question per case on the physical 8 GB laptop near the relevant floor. Capture the admission decisions and exact readings, answer source, time to the visible result, lowest available RAM, paging and app responsiveness. The log interval runs from preflight to the backend result. Simulated readings cover policy branches. For a deferral or failure, keep the stage and diagnostic with the result.

Review the candidate against the baseline and agreed paging and responsiveness limits before changing the default. The target is a usable bundled answer under ordinary laptop conditions. Longer coexistence remains the R03.4 workload.

The benchmark kit uses one source-matched desktop and analytics engine for both cases. The launcher accepts `-BenchmarkProfile baseline` or `-BenchmarkProfile candidate`, with the tested commit supplied as `-ExpectedSource`. Each mode uses a fresh backend profile and WebView2 folder. Normal installs and the previous offline QA kit use their existing admission policies.

Download and extract `PilotODIN-P4-R03-Headroom-QA` from the [benchmark build](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/44106241769). From the PilotODIN development checkout in Windows PowerShell, update the launcher and start the baseline:

```powershell
git pull --ff-only
$kit = "$env:USERPROFILE\Downloads\PilotODIN-P4-R03-Headroom-QA"
$source = '8966edc781128baa94354df044bfadc45d069984'
& .\tools\Start_P4_R03_Offline_QA.ps1 -KitDirectory $kit -BenchmarkProfile baseline -ExpectedSource $source
```

After finishing and closing that app, use the same command with `-BenchmarkProfile candidate`. Check the Settings cutoff against the chosen profile and set `$kit` to the actual extraction folder. The launcher may refuse an existing QA profile even if no question was sent. Preserve its files if it refuses.

Run the two cases separately using the setup above. Use **Low-memory** and **Offline**, leave cloud reasoning off, set the local timeout to **120s**, and use only the supplied synthetic CSV. Start the baseline when its refreshed available RAM is at least **2.00 GiB**. Start the candidate when available RAM is near **1.50 GiB** and below **2.00 GiB**. Do not create artificial memory pressure when the desired level is unavailable. The request-time readings in the log determine the actual comparison window.

For each case, submit the same question once and capture the provider label and reply or error. Note any visible stall and close the QA desktop after recording the result. The launcher prints the admission JSON lines after exit and saves Windows available memory, system commit, pages read per second and a window responsiveness indicator to CSV. Use the timestamped admission and result records for preflight-to-result time. The user-observed UI timing and responsiveness supplement these measurements.

## Research references

- NL4DV separates detected dataset fields from inferred analytical tasks. DataTone surfaces ambiguity where the user can resolve it. [NL4DV](https://nl4dv.github.io/nl4dv/index.html) · [DataTone](https://cond.org/datatone.html)
- SParC evaluates context-dependent question sequences. The CLINC study evaluates out-of-scope requests separately from supported intents. [SParC](https://aclanthology.org/P19-1443/) · [Out-of-scope evaluation](https://aclanthology.org/D19-1131/)
- Character n-grams and compact quantized encoders provide candidates for a wording benchmark. Constrained decoding narrows the output format, and interpretation correctness still needs validation. [scikit-learn text features](https://scikit-learn.org/stable/modules/generated/sklearn.feature_extraction.text.TfidfVectorizer.html) · [ONNX Runtime quantization](https://onnxruntime.ai/docs/performance/model-optimizations/quantization.html) · [PICARD](https://aclanthology.org/2021.emnlp-main.779/)
- Pandas documents column selection and memory-aware scaling. DuckDB describes disk spilling and operations that can still exceed practical memory budgets. [Pandas scaling guide](https://pandas.pydata.org/docs/user_guide/scale.html) · [DuckDB memory troubleshooting](https://duckdb.org/docs/current/guides/troubleshooting/oom_errors)
