# PilotODIN QA preflight and failure planning

Use this process for work where a failed run would cost another native session, touch existing data, or leave us unsure whether an acceptance requirement passed. For routine changes, write the expected result and the main regression check in the existing work note.

## Before the run

1. **Define the outcome and how to prove it.** Name the exact source, the environment, the existing acceptance requirement and the evidence that would close it. Decide what a partial or blocked result looks like.
2. **Trace every handoff.** Follow inputs through setup, execution, export, validation and reporting. At each boundary ask what could be missing, malformed, late, duplicated, misattributed or written to the wrong place. Prioritise previous failures, failures that could give a false pass, and failures that would waste the run.
3. **Test the likely failures at the cheapest realistic layer.** Exercise the happy path and inject representative failures into the same code used for acceptance. Run environment-specific checks with generated inputs where possible. Record which assumptions still need the real environment.
4. **Make the run diagnosable.** Give each stage a recognisable start or completion marker. Preserve enough safe information to distinguish setup failure, invalid evidence and an unmet acceptance criterion. Define the recovery for each likely blocker and follow the existing rules for raw evidence and authorisation.
5. **Compare the result with the acceptance requirement.** Record the exact source, what passed, what remains unverified, and the next action. Turn a confirmed defect into a regression case before repeating the expensive part. Credit phase progress when the required evidence changes.

## Worked example for P4 / N12

The next combined rehearsal needs one generated fixture to produce a valid summary from real ETW and bounded Sysmon evidence. A completed result must establish continuous collector evidence, identifiable fixture lifetimes, loopback TCP and UDP, and the expected file mutations. A blocked result needs either a redacted validation error or a summary with named coverage blockers. [N12 runbook](../qa/p4_native/N12_TRACE.md#reduce-combined-etw-and-sysmon-evidence)

| Predicted failure | Before spending a combined Windows run | What still needs live evidence |
| --- | --- | --- |
| ETW export is empty, truncated, altered, outside the capture window, or missing its device mapping. | Exercise those inputs against the reducer's shared parser. Run the same parser against the expanded Windows ETW fixture and the calibration-only workload in regular P4 CI. | The real export from the combined window and its counters. |
| Sysmon XML is malformed, a record is missing, or the record boundaries are wrong. | Use synthetic XML to exercise malformed records and sequence gaps. Review the exact launch, the pinned binary and the record bounds. | Real XML, independent first and last record IDs, and continuous records from the combined run. |
| The collectors disagree about process identity or the fixture lacks either loopback protocol. | Keep synthetic cases for missing UDP, missing or ambiguous lifetimes, and ETW identity and file-object reuse. Check the real ETW file operations in regular P4 CI. | Unique process attribution between collectors and observed child TCP and UDP in the same run. |
| An unrelated writer mutates the protected directory, or file attribution is incomplete. | Verify that unknown writers, incomplete operations and cross-root renames fail or block coverage as appropriate. | Combined capture scope and, later, before/after snapshots during the native journey. |
| The run fails before producing usable evidence. | Verify that representative invalid inputs return exit 2 with a redacted stage or reason. Confirm workflow scope and expected output before launch. | The stage reached and the actual coverage result or blocker in the hosted run. |

The [combined rerun](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/43478728040) exposed a preflight gap. Regular CI exercised the same fixture, export and validation, but its fixture correlation tracked the generated paths. The combined reducer used strict correlation across the capture and blocked on unresolved mutations. The next preflight must exercise strict correlation on real ETW fixture events with generated process evidence so that this boundary is checked before another provisioning run.

For N12, a passing fixture is the evidence needed to move on to planning the separately approved native journey. If it blocks, use the named reason and the narrowest reproducible input to decide the next change. If the reason remains ambiguous, improve the evidence at that boundary before another provisioning run.
