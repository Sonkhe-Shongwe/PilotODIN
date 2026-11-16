# PilotODIN P4 Local analytics implementation plan

**15 November 2026.** The owner agreed to improve Ask ODIN's Local analytics first and evaluate additional model components only if they improve measured results. This plan groups interpretation, execution, follow-ups and verification into one implementation milestone. P4 is active at 65/100 on the existing scorecard.

## Current evidence

| Evidence | Result and scope |
| --- | --- |
| Ask ODIN on hosted Windows | The API test process returned all five expected fact sets using supported question forms at simulated 0.73 GiB available. Peak working set was 102.3 MiB. The measurement excluded the full desktop and WebView2. [Windows run](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/43744796818/job/132905610069) |
| Qwen3 1.7B batch comparison | Batch 512 peaked at 2,109.5 MiB and batch 128 at 2,068.9 MiB. Both scored 2 of 5. The batch 512 worker released 2,024.1 MiB at idle and answered after waking. The comparison retained batch 512. [Windows run](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/43740595746/job/132892675147) |
| Smaller generative models | Qwen3 0.6B peaked at 934.9 MiB and scored 2 of 4. SmolLM2 360M peaked at 420.0 MiB and scored 1 of 4. Neither cleared the earlier structured answer screen. These worker measurements exclude PilotODIN and its dataset. [Small-model run](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/43593329731/job/132442500969) |
| Model-free wording experiment | The separate word-overlap follow-up selector got 4 of 8 original questions and 2 of 8 paraphrases right. It correctly abstained on all 12 unclear questions. This tested selection from fixed options. [Benchmark](../desktop/evaluate_offline_follow_up_rules.py) |
| Physical 8 GB laptop | Earlier snapshots showed 0.73–0.82 GiB available with local analytics running. The offline Qwen test stopped at the 2.0 GiB application preflight. The owner later showed the overview, training status and missing-premium answers in the Windows Live Dev browser. That observation covers the browser preview. [P4 acceptance ledger](./PROJECT_STATUS_CURRENT.md#p4-acceptance) |

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

- **Correctness.** Use held-out datasets with different schemas from the smoke fixture. Include paraphrases, conflicting aliases, blank and zero values, empty groups, ambiguous denominators, stale versions and questions that require clarification. For each case, assert the chosen operation and fields before checking the numeric result, explanation and dataset version. Log correct answers, wrong answers, clarifications and unsupported requests separately.
- **Required regressions.** Pass the milestone examples, preserve all previously supported exact answers, and verify deterministic clarification when the field or denominator cannot be resolved. Confirm no unintended training, data edits, provider launches or external calls for the tested Local analytics requests.
- **Resource evidence.** Record cold and warm latency and process memory on representative small and larger fixtures, with repeated questions. In the physical desktop session record the app, backend and WebView2 working sets or private bytes, minimum system available RAM, paging and responsiveness across startup, workload and cooldown. Use the current baseline and agree workload-specific limits before the physical run. [Windows process memory counters](https://learn.microsoft.com/en-us/windows/win32/psapi/process-memory-usage-information)
- **P4 disposition.** A model-free desktop pass supports Local analytics on the tested hardware and build. R03 offline Qwen generation and coexistence remain separate acceptance evidence under the existing 2.0 GiB preflight. Use the [phase ledger](./PROJECT_STATUS_CURRENT.md#p4-acceptance) for N12, preservation and signoff.

## Proposed physical Windows session

The owner confirmed that the Live Dev check worked on 16 November and approved one unpackaged Tauri build and launch. The session exercises native WebView2 against an independently started, disposable loopback development backend. The [approval record](./P4_R03_OWNER_NATIVE_APPROVAL_2026-11-16.md) pins the reviewed application source. The existing [hosted runner](../qa/p4_native/Run_P4_71_Disposable_Windows.ps1) demonstrates the startup pattern and remains restricted to hosted CI.

1. Record the exact source and executable SHA-256. Verify the isolated Tauri identity, disposable backend workspace and separate WebView2 profile before running the questions. Use the same four-row fixture in the disposable workspace. Keep the installed PilotODIN closed and leave its projects outside the test.
2. Record system RAM and paging before launch, at the ready screen, during the questions and after cooldown. Attribute process readings to the native shell, its WebView2 profile and the development backend. Record sampled working sets and private bytes, elapsed response times and any visible UI stall.
3. Run the [five-question smoke workload](./LIVE_DEVELOPMENT.md#local-analytics-smoke-check) once through the native UI. The driver verifies the Tauri bridge, answers and filter follow-up and records click-to-verified-answer times. Record visible stalls and keep any incomplete run at the stage it reached.

Pull the updated development branch and close the installed app and both Live Dev consoles to free the required loopback ports. Run this from PowerShell in the PilotODIN checkout.

```powershell
py -3 .\tools\Verify_Local_Analytics_Windows_Native.py --run-approved
```

The preflight uses the existing Live Dev dependencies and checks for Rust x64 MSVC and the C++ build tools. The runner exports the reviewed backend, frontend and native source from Git into the temporary folder. It stages the committed QA helpers and copies the installed frontend dependencies. Local edits and untracked files can stay in the checkout. The runner compiles and launches once, generates its own four-row project, collects system and scoped process samples, closes the verified QA window and prints and saves `result.json`. A preflight block happens before compilation. A later failure is recorded with its stage and local logs.

The result covers model-free Local analytics in an unpackaged native shell. The packaged sidecar and offline Qwen coexistence are outside this session. The installer freeze remains in force.

### Resume after a WebView2 automation timeout

If the reviewed runner created an executable and ended at `native_launch` while polling `9331/json/version`, retain the original run folder. To approve and perform one relaunch of that exact build from the PilotODIN checkout, run:

```powershell
py -3 .\tools\Verify_Local_Analytics_Windows_Native.py --relaunch-approved pilotodin-r03-native-1v829nh2
```

The runner checks the prior receipt, executable hash and Cargo lockfile hash. It starts a fresh disposable backend and WebView2 profile with CDP disabled. It verifies all five responses through the API. The terminal prompts you to check the median and its follow-up inside the desktop window while RAM and paging are sampled. Press **P** in the terminal if both UI answers matched, or **F** if either failed. A successful result is recorded as `PASS_WITH_OWNER_OBSERVATION`. Click-to-render timings and a fully automated native UI pass remain unmeasured in this mode.

## Research references

- NL4DV separates detected dataset fields from inferred analytical tasks. DataTone surfaces ambiguity where the user can resolve it. [NL4DV](https://nl4dv.github.io/nl4dv/index.html) · [DataTone](https://cond.org/datatone.html)
- SParC evaluates context-dependent question sequences. The CLINC study evaluates out-of-scope requests separately from supported intents. [SParC](https://aclanthology.org/P19-1443/) · [Out-of-scope evaluation](https://aclanthology.org/D19-1131/)
- Character n-grams and compact quantized encoders provide candidates for a wording benchmark. Constrained decoding narrows the output format, and interpretation correctness still needs validation. [scikit-learn text features](https://scikit-learn.org/stable/modules/generated/sklearn.feature_extraction.text.TfidfVectorizer.html) · [ONNX Runtime quantization](https://onnxruntime.ai/docs/performance/model-optimizations/quantization.html) · [PICARD](https://aclanthology.org/2021.emnlp-main.779/)
- Pandas documents column selection and memory-aware scaling. DuckDB describes disk spilling and operations that can still exceed practical memory budgets. [Pandas scaling guide](https://pandas.pydata.org/docs/user_guide/scale.html) · [DuckDB memory troubleshooting](https://duckdb.org/docs/current/guides/troubleshooting/oom_errors)
