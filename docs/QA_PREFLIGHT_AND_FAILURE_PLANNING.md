# PilotODIN QA preflight and failure planning

Use this process for work where a failed run would cost another native session, touch existing data, or leave us unsure whether an acceptance requirement passed. For routine changes, write the expected result and the main regression check in the existing work note.

## Choose the next step

Start with the [current handoff](./SESSION_HANDOFF_CURRENT.md#next-engineering-action) and name the acceptance check or decision the step can move. Reuse source-matched evidence. A proposed check should answer a named question about user behaviour, data safety, an acceptance requirement or the reliability of its evidence. A plain continuation authorises in-scope preparation. Restricted work follows the owner and one-use approval boundaries. [Phase policy](./PHASE_FOCUS_AND_CLOSURE_POLICY_2026-10-28.md)

| What the evidence shows | Next step |
| --- | --- |
| Existing evidence answers the question. | Cite the tested revision and result. Continue to the next unresolved dependency. |
| A defect or evidence gap has a reproducible input. | Fix the failing behaviour or narrow the evidence gap using that input. Exercise the matching positive case and the failure that could otherwise pass. |
| The remaining question depends on live Windows behaviour. | Use the smallest existing fixture that can answer it. For a separately approved run, identify the reviewed source, environment, expected observation and how it changes the next decision. |
| The remaining question depends on the full desktop journey. | Use the full route with the already-reviewed candidate and fresh authority. Keep the last stage reached, exact source and binary identities, and the scoped verdict in the report. |

For a failed run, record the workflow conclusion and the last evidenced stage alongside the acceptance verdict. A useful diagnostic can coexist with **FAIL** or **BLOCKED** acceptance. Before a rerun, identify what changed or what new observation the same path can supply. Keep that decision and its evidence in the existing handoff. [Process audit](./WORK_AND_PROCESS_AUDIT_2026-11-19.md)

## Before the run

1. **Define the outcome and how to prove it.** Name the exact source, the environment, the existing acceptance requirement and the evidence that would close it. Decide what a partial or blocked result looks like.
2. **Trace every handoff.** Follow inputs through setup, execution, export, validation and reporting. At each boundary ask what could be missing, malformed, late, duplicated, misattributed or written to the wrong place. Prioritise previous failures, failures that could give a false pass, and failures that would waste the run.
3. **Prove a reachable pass at the cheapest realistic layer.** Run a known-good input through the same verdict path used for acceptance, then inject representative failures to verify the safeguards. Use generated inputs for environment-specific checks where possible. Record which assumptions still need live evidence.
4. **Make the run diagnosable.** Give each stage a recognisable start or completion marker. Preserve enough safe information to distinguish setup failure, invalid evidence and an unmet acceptance criterion. Define the recovery for each likely blocker and follow the existing rules for raw evidence and authorisation.
5. **Compare the result with the acceptance requirement.** Record the exact source, what passed, what remains unverified, and the next action. Turn a confirmed defect into a regression case before repeating the expensive part. Credit phase progress when the required evidence changes.

<a name="worked-example-for-p4--n12"></a>

## Historical worked example for P4 / N12

The retained-child fixture-only run passed on the first Sysmon read with zero reported ETW loss. The generated clean trace passes both full audit reductions, and the hosted CLI tests cover the passing exit status and three blocked cases. A subsequent hosted app diagnostic completed both reductions. The strict comparison resolved 199,268 previously unknown WebView network-process write paths on that run, while the ordinary audit failed both acceptance checks. [Fixture evidence](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/44356802211/job/134986971018) · [Live comparison](./SESSION_HANDOFF_CURRENT.md#18-november-2026--live-webview-write-path-comparison-completed)

Before a full acceptance attempt, review the last completed audit and the fixes for its known failures. If a build is needed to isolate a finding, describe the question, its measurable outcome and the evidence the run should retain. Keep the actual acceptance verdict and award points only on the governed result.

| Predicted failure | Before spending a combined Windows run | What still needs live evidence |
| --- | --- | --- |
| ETW export is empty, truncated, altered, outside the capture window, or missing its device mapping. | Exercise those inputs against the reducer's shared parser. Run the same parser against the expanded Windows ETW fixture and the calibration-only workload in regular P4 CI. | The real export from the combined window and its counters. |
| Sysmon XML is malformed, a record is missing, or the record boundaries are wrong. | Use synthetic XML to exercise malformed records and sequence gaps. Review the exact launch, the pinned binary and the record bounds. | Real XML, independent first and last record IDs, and continuous records from the combined run. |
| The collectors disagree about process identity or the fixture lacks either loopback protocol. | Keep synthetic cases for missing UDP, missing or ambiguous lifetimes, and ETW identity and file-object reuse. Check the real ETW file operations in regular P4 CI. | Unique process attribution between collectors and observed child TCP and UDP in the same run. |
| An unrelated writer mutates the protected directory, or file attribution is incomplete. | Verify that unknown writers, incomplete operations and cross-root renames fail or block coverage as appropriate. | Combined capture scope and, later, before/after snapshots during the native journey. |
| The run fails before producing usable evidence. | Verify that representative invalid inputs return exit 2 with a redacted stage or reason. Confirm workflow scope and expected output before launch. | The stage reached and the actual coverage result or blocker in the hosted run. |

The [combined rerun](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/43478728040) exposed a preflight gap. Regular CI exercised the same fixture, export and validation, but its fixture correlation tracked the generated paths. The combined reducer used strict correlation across the capture and blocked on unresolved mutations. Regular Windows CI now exercises strict correlation on real ETW fixture events with generated process evidence. A successful diagnostic job can report blocked ETW coverage when it captures all expected fixture operations, reports no file violations and isolates unresolved mutations. This result guides the next engineering change. Combined calibration still requires independent live Sysmon evidence and resolved ETW coverage.

For the current N12 candidate, use the same generated evidence to choose the collector path. It should preserve a permitted write, detect an in-window protected mutation followed by an endpoint restore, and produce **BLOCKED** when required evidence is incomplete. A fixture result applies to that case and scope. The full journey and its approval are tracked in the [handoff](./SESSION_HANDOFF_CURRENT.md#next-engineering-action).
