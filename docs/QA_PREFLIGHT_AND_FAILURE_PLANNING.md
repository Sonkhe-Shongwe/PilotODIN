# PilotODIN QA preflight and failure planning

Use this process for work where a failed run would cost another native session, touch existing data, or leave us unsure whether an acceptance requirement passed. For routine changes, write the expected result and the main regression check in the existing work note.

## Before the run

1. **Define the outcome and how to prove it.** Name the exact source, the environment, the existing acceptance requirement and the evidence that would close it. Decide what a partial or blocked result looks like.
2. **Trace every handoff.** Follow inputs through setup, execution, export, validation and reporting. At each boundary ask what could be missing, malformed, late, duplicated, misattributed or written to the wrong place. Prioritise previous failures, failures that could give a false pass, and failures that would waste the run.
3. **Prove a reachable pass at the cheapest realistic layer.** Run a known-good input through the same verdict path used for acceptance, then inject representative failures to verify the safeguards. Use generated inputs for environment-specific checks where possible. Record which assumptions still need live evidence.
4. **Make the run diagnosable.** Give each stage a recognisable start or completion marker. Preserve enough safe information to distinguish setup failure, invalid evidence and an unmet acceptance criterion. Define the recovery for each likely blocker and follow the existing rules for raw evidence and authorisation.
5. **Compare the result with the acceptance requirement.** Record the exact source, what passed, what remains unverified, and the next action. Turn a confirmed defect into a regression case before repeating the expensive part. Credit phase progress when the required evidence changes.

## Worked example for P4 / N12

The retained-child fixture-only run passed. Sysmon attributed both loopback messages on its first read with the four-second hold, and ETW produced a nonempty recording with zero reported loss. The generated clean trace passes both full audit reductions and the hosted CLI tests cover the passing exit status and three blocked cases. The next diagnostic question is whether the strict path comparison closes the same gaps on a live app trace. [Fixture evidence](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/44356802211/job/134986971018) · [Current handoff](./SESSION_HANDOFF_CURRENT.md#next-engineering-action)

Before a full acceptance attempt, review the last completed audit and the fixes for its known failures. If a build is needed to isolate a finding, describe the question, its measurable outcome and the evidence the run should retain. Keep the actual acceptance verdict and award points only on the governed result.

| Predicted failure | Before spending a combined Windows run | What still needs live evidence |
| --- | --- | --- |
| ETW export is empty, truncated, altered, outside the capture window, or missing its device mapping. | Exercise those inputs against the reducer's shared parser. Run the same parser against the expanded Windows ETW fixture and the calibration-only workload in regular P4 CI. | The real export from the combined window and its counters. |
| Sysmon XML is malformed, a record is missing, or the record boundaries are wrong. | Use synthetic XML to exercise malformed records and sequence gaps. Review the exact launch, the pinned binary and the record bounds. | Real XML, independent first and last record IDs, and continuous records from the combined run. |
| The collectors disagree about process identity or the fixture lacks either loopback protocol. | Keep synthetic cases for missing UDP, missing or ambiguous lifetimes, and ETW identity and file-object reuse. Check the real ETW file operations in regular P4 CI. | Unique process attribution between collectors and observed child TCP and UDP in the same run. |
| An unrelated writer mutates the protected directory, or file attribution is incomplete. | Verify that unknown writers, incomplete operations and cross-root renames fail or block coverage as appropriate. | Combined capture scope and, later, before/after snapshots during the native journey. |
| The run fails before producing usable evidence. | Verify that representative invalid inputs return exit 2 with a redacted stage or reason. Confirm workflow scope and expected output before launch. | The stage reached and the actual coverage result or blocker in the hosted run. |

The [combined rerun](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/43478728040) exposed a preflight gap. Regular CI exercised the same fixture, export and validation, but its fixture correlation tracked the generated paths. The combined reducer used strict correlation across the capture and blocked on unresolved mutations. Regular Windows CI now exercises strict correlation on real ETW fixture events with generated process evidence. A successful diagnostic job can report blocked ETW coverage when it captures all expected fixture operations, reports no file violations and isolates unresolved mutations. This result guides the next engineering change. Combined calibration still requires independent live Sysmon evidence and resolved ETW coverage.

For N12, a passing fixture is the evidence needed to move on to planning the separately approved native journey. If it blocks, use the named reason and the narrowest reproducible input to decide the next change. If the reason remains ambiguous, improve the evidence at that boundary before another provisioning run.
