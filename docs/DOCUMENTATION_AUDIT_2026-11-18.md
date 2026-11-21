# PilotODIN documentation audit | 18 November 2026

Reviewed `feature/live-dev-workspace-20261023` at `6e5bd7d1f01df28151ba3b97dcd82f0a941f9363`. GitHub's default `main` was `64bb85676f50ec507e8d0614f1cf9293f04c9291`. The documentation index and phase handoff identify the feature branch as the development source for this audit. [Current documentation index](./DOCUMENTATION_INDEX.md)

## Scope and corrections

The inventory covers all repository Markdown files. The content audit followed the current navigation into the governance, acceptance, hosted Windows, original-data, resource and developer guides. The release freeze and test scope were checked against the applicable workflow definitions. [Phase policy](./PHASE_FOCUS_AND_CLOSURE_POLICY_2026-10-28.md) · [Master QA #2](https://github.com/Sonkhe-Shongwe/PilotODIN/issues/2) · [Owner evidence #9](https://github.com/Sonkhe-Shongwe/PilotODIN/issues/9)

| Finding | Correction and evidence |
| --- | --- |
| README called a 17 November result the latest completed N12 audit. | The last completed app audit verified both launches and matching protected endpoints. It recorded 67 outside-scope file operations, seven unexpected connections and 200,077 unresolved WebView write paths. Preserve **FAIL** for the filesystem and network checks and **BLOCKED** for strict coverage. [Completed Windows job](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/44298639798/job/134782187614) |
| The latest full app attempt, earlier fixture-only pass and generated positive control answered different questions. | The latest pre-build helper and build passed. Initial Sysmon calibration blocked on process identity, so both app launches and reductions were **NOT RUN**. Earlier initial calibration passed in isolation on its first read with zero ETW losses. The generated trace and hosted CLI tests proved a reachable pass. Keep all three scopes explicit. [Blocked app job](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/44337564606/job/134918293248) · [Fixture-only result](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/44335300490/job/134910240433) · [Positive-control CI](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/44341573479) |
| The chronological handoff buried the next action and mixed current guidance with superseded notes. | Put the approval scope, success criteria and resource disposition before the history. Link each dated section to the exact Git revision and retain its original anchor. [Current handoff](./SESSION_HANDOFF_CURRENT.md) · [Complete pre-cleanup handoff](https://github.com/Sonkhe-Shongwe/PilotODIN/blob/6e5bd7d1f01df28151ba3b97dcd82f0a941f9363/docs/SESSION_HANDOFF_CURRENT.md) |
| The Local analytics plan mixed the physical Qwen attempt with a later Settings reading. | The 1.50 GiB candidate returned local rules after deferral. The later 0.936 GiB reading documents the shortfall against the 2.00 GiB admission floor. The analytics-only run separately measured a 735.27 MiB sampled combined working-set peak and verified the HTML export. Use existing evidence before another physical run. [Local analytics plan](./P4_LOCAL_ANALYTICS_IMPLEMENTATION_PLAN_2026-11-15.md#ordinary-laptop-memory-and-offline-inference) · [RAM result](./RESOURCE_AWARE_MODE_DESIGN.md#physical-everyday-ram-retest-result) |
| The native kit and browser pilot mixed historical first steps with current work. | Label the historical scope, retain the prior native guide anchors and correct the old installer paragraph to include later scoped owner evidence. Route active readers to current QA procedures and approvals. [Native kit](../qa/p4_native/README.md) · [Browser QA](../frontend/e2e/README.md) · [QA preflight](./QA_PREFLIGHT_AND_FAILURE_PLANNING.md) |

## Current disposition

P4 stays active at **14/20 (70%)**. The six open checks are R02.5, R02.6, R03.3, R03.4, R06.1 and R06.2. R06 original-tree history remains a strict failure with 74 differences and an unknown writer. Gates R01 and P8 retain their separate governance. QA #2 and owner-evidence #9 were open when reviewed. The installer jobs and both one-use N12 workflows were disarmed in the reviewed source. [P4 engineering scorecard](./PROJECT_STATUS_CURRENT.md#p4-engineering-scorecard)

The next separately approved step is the hosted fixture-only check of the four-second hold at the initial Sysmon calibration gate. Use the generated positive control and a defined diagnostic question before spending a build. [Next engineering action](./SESSION_HANDOFF_CURRENT.md#next-engineering-action)

## Verification

The inventory checked **221 Markdown files** and resolved **803 same-repository references outside the verbatim archive**, including 654 relative, 9 branch and 140 pinned references. It verified paths and Markdown fragments. The verbatim archive retains its 91 pre-existing unresolved relative references. Their historical layout and earlier navigation are available from the index. External destinations were sampled for current evidence and governing issues.

The scorecard check counted 20 rows and 70 points. A source comparison retained every existing handoff anchor and showed that tracked changes are Markdown only. `git diff --check` passed.

The last code and test revision, `6e5bd7d`, passed all four routine P4 jobs and the Windows FileIO integration job. The focused P4 run reported 675 passed, 2 skipped and 87 subtests passed. The FileIO run reported 256 passed before its generated Windows controls. This audit changes Markdown only. [Routine P4 CI](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/44341573479) · [Windows FileIO integration](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/44341573377)
