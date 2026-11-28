# PilotODIN 1.0 | Golden-reference direction and document-cleaning audit

**Audit date:** 21 November 2026. **Scope:** active P4 documentation/navigation, N12 Stage 1 verification strategy, historical evidence preservation and consent boundaries.  
**Branch:** `feature/live-dev-workspace-20261023`. **Before-cleanup HEAD:** [`e8cfda5`](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/e8cfda5bd734a0e94824ffa11937e997d484fc59); **first clean-entrypoint commit:** [`2f9cd10`](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/2f9cd10bf119ad18f0d3c80a63d2d375bd70d51d). **No product, QA collector, verifier, workflow or test code was modified in this audit.**

## Executive decision

**Direction: ACCEPT with qualifications.** The owner proposed establishing a genuine, independently supported successful process-lifetime reference, then deriving many deterministic positive, negative, boundary and crash tests by working backward. Adopt that **reference-first success contract** as the N12 Stage 1 engineering approach; do **not** reverse-engineer a PASS by modifying evidence or verifier requirements until the requirements themselves have been independently justified.

**One full green real native Stage 1 run does not yet exist.** The launcher and app previously showed exact ETW versus original Windows-handle FILETIME equality, but their Sysmon Event 5 termination stamps differed (+3.2932 ms and +7.7625 ms respectively). The real run included seven WebView2 descendants with event evidence but no original retained child handles. The *synthetic* Windows AF_PIPE tests later passed four CI jobs and represent tested support code, not native acceptance. No historical data can now recreate the absent original child handles.

**New authoritative direction:** [Stage 1 golden-reference correctness/evidence contract and backward verification matrix](./P4_N12_STAGE1_GOLDEN_REFERENCE_AND_BACKWARD_VERIFICATION_2026-11-21.md). This is a planning/evidence specification, **not a new acceptance rule**, code change or native permission. [Last real Stage 1 analysis](./P4_N12_STAGE1_NATIVE_SYSMON_ETW_EXIT_CLOCK_DIAGNOSIS_44893498723.md) · [Latest tested synthetic Windows pipe/abort report](./P4_N12_SYNTHETIC_WINDOWS_PIPE_AND_ABORT_SOURCE_REVIEW_2026-11-21.md).

## Findings and resolution

| Audit finding | Observed source conflict or risk | Cleanup disposition |
| --- | --- | --- |
| Active next step obscured | `SESSION_HANDOFF_CURRENT.md` accumulated approximately 21,010 characters of dated steps under one active “Next engineering action,” with previous one-use approval decisions mixed into the reading path | Retain exactly one current next-action heading, replace its body with the reference-first plan, and move the full dated previous contents to a same-directory archive |
| Scorecard hard to find | `PROJECT_STATUS_CURRENT.md` prefaced its canonical phase ledger with about 14,915 characters of chronological announcements, some labeled “latest” although superseded | Compact present-state introduction and direct scorecard links; preserve the previous preface in the archive. **All content from `## Phase ledger` onward is byte-for-byte unchanged** |
| Acceptance conditions crowded | `P4_80_ACCEPTANCE_WORKLIST...` led with about 9,109 characters of history before stating six active engineering checks | Replace preface with one truthful status/acceptance boundary and contract link; archive prior text. **All content from `## Six open engineering checks and the next evidence passes` onward is byte-for-byte unchanged** |
| References repeatedly called “latest” | `DOCUMENTATION_INDEX.md` had 9,119 characters of sequential source-only milestones under “Current development references,” including obsolete future-work promises | Group current reference, native counterexample, tested synthetic transport and downstream R02.5 records. Preserve original technical links in an archival reading list. **All content from `## Historical navigation` onward is byte-for-byte unchanged** |
| Green-case ambiguity | Repeated successful CI labels could be mistaken for a successfully closed real native Stage 1 | Explicitly distinguish **partial independently corroborated properties**, **synthetic regression green**, **native Stage 1 BLOCKED**, and **full N12 filesystem/network FAIL** |
| Timestamp assumption | Strict `Sysmon Event 5 UtcTime == ETW ExitTime` is empirically falsified by the last real test; app/launcher actual handles matched ETW | Add a **disputed invariant** with a source-to-predicate trace and required counterexamples; **no arbitrary 8 ms tolerance, test bypass or acceptance relaxation** |
| Child capture incompleteness | Seven historical WebView2 children lacked original handle evidence. The 10 ms observer can miss short-lived children. | Require unique independent child identity and complete original-handle corroboration; no hardcoded child count or imaginary full golden trace |
| Authorization | Prior no-CDP native approvals consumed; synthetic CI was not a grant for another native run | Keep the native workflow **disabled** and one-use approval marker **absent**. Require fresh, explicit source-pinned scope for any real native retest |
| Scope conflation | A Stage 1 profile-lifetime diagnostic could be mistaken for R02.5 native filesystem or R02.6 network acceptance | Explicit success-matrix separation: Stage 1 is preliminary evidence; full R02.5, R02.6, R03/R06 and P4 closure require their original separate gates |

## Authority map after cleanup

| Question | Authoritative home |
| --- | --- |
| What is the next source-only action and branch? | [Current handoff](./SESSION_HANDOFF_CURRENT.md#next-engineering-action) |
| What is a correct process lifetime, and which sources must prove it? | [Stage 1 golden-reference contract](./P4_N12_STAGE1_GOLDEN_REFERENCE_AND_BACKWARD_VERIFICATION_2026-11-21.md) |
| What is the official score, including six open checks? | [Current project scorecard](./PROJECT_STATUS_CURRENT.md#p4-engineering-scorecard) |
| What is required to award each R02-R06 check? | [P4 acceptance worklist](./P4_80_ACCEPTANCE_WORKLIST_AND_EVIDENCE_INTAKE_2026-11-12.md#six-open-engineering-checks-and-the-next-evidence-passes) |
| What permissions, phase and installer freeze are binding? | [Phase policy](./PHASE_FOCUS_AND_CLOSURE_POLICY_2026-10-28.md) |
| Which specific native/synthetic result supports a claim? | Dated immutable test/source links and technical records, beginning with [actual Stage 1 blocker](./P4_N12_STAGE1_NATIVE_SYSMON_ETW_EXIT_CLOCK_DIAGNOSIS_44893498723.md) and [synthetic pipe result](./P4_N12_SYNTHETIC_WINDOWS_PIPE_AND_ABORT_SOURCE_REVIEW_2026-11-21.md) |
| Where did old updates and references go? | [Preserved chronological progress archive](./P4_ENTRYPOINT_PROGRESS_CHRONOLOGY_ARCHIVE_2026-11-21.md). Same-directory location preserves ordinary relative document links; self-links refer back to their original document |

The [older 21 November documentation audit](./DOCUMENTATION_AUDIT_2026-11-21.md) is a **historical report about an earlier source SHA**, not a newer verification of this cleanup. Owner-held master DOCX blueprints and the complexity-last roadmap remain unchanged and are not silently replaced by this Stage 1 strategy.

## Exact cleanup preservation checks

Comparing the repository content immediately before and after the first cleaning commit:

| File | Earlier characters | New characters | Preserved remainder |
| --- | ---: | ---: | --- |
| `docs/SESSION_HANDOFF_CURRENT.md` | 311,493 | 293,009 | Entire section beginning `## Prior QA-local candidate` unchanged |
| `docs/PROJECT_STATUS_CURRENT.md` | 63,622 | 51,007 | Entire `## Phase ledger` and `## P4 engineering scorecard` onward unchanged |
| `docs/P4_80_ACCEPTANCE_WORKLIST_AND_EVIDENCE_INTAKE_2026-11-12.md` | 154,646 | 147,321 | All six open checks and detailed acceptance provisions unchanged |
| `docs/DOCUMENTATION_INDEX.md` | 12,765 | 5,972 | Existing historical navigation and explicit compatibility anchors unchanged |

The former leading progress blocks total **54,157 characters** and were copied to the new [55,521-character, provenance-tagged archive](./P4_ENTRYPOINT_PROGRESS_CHRONOLOGY_ARCHIVE_2026-11-21.md), including original evidence and source URLs. The active four-document route is shorter by **45,217 characters**, not a claim of fewer historical records. The old `#next-engineering-action` anchor remains active. The full old documents are also recoverable from [the pre-cleanup commit](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/e8cfda5bd734a0e94824ffa11937e997d484fc59).

### Validation performed

- Reopened the actual source-tree files instead of relying on chat summaries.
- Confirmed the old and new downstream sections listed above are **exactly equal** by string comparison, including the canonical P4 scorecard.
- Confirmed there is exactly **one** active `## Next engineering action` heading.
- Checked relative Markdown targets in the seven edited/new entrypoint files against the repository tree: initially **530** relative links, with **five references to this yet-to-be-written audit**; those five targets are resolved by committing this file. No unrelated relative path target was missing in that pre-final check.
- Checked **167 fragment references between five currently loaded entrypoint/archive documents** with GitHub-style repeated-space heading slugs and explicit named anchors: **zero missing anchors**. This is a **scoped fragment check**, not a full repository-wide anchor/URL crawl. The final check must repeat path validation after this audit file exists.
- The modified working tree is documentation only. Routine CI #44903523887 **4/4 PASS** at its *exact earlier tested source* [`0511aca`](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/0511aca1e192ff4aa0950ac1255dcbd1b887b8f2); a documentation commit is **not** a newly tested native build.

## Current truth table, unchanged

| Outcome | Verified current state |
| --- | --- |
| Official P4 engineering progress | **14/20 (70%)**. Six open: **R02.5, R02.6, R03.3, R03.4, R06.1, R06.2** |
| File-mutation preparation | **3/4 (75%)**, internal only; **R02.5 0/5** |
| Full native N12 | [#44838416004](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/44838416004): filesystem **FAIL**, network **FAIL**, FileIO coverage **BLOCKED** |
| Last native Stage 1 | [#44893498723](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/44893498723): **BLOCKED** on exact Sysmon/ETW exit equality, no original retained WebView child handles |
| Latest synthetic support | [#44903523887](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/44903523887): **4/4 SUCCESS**, 970 Python passed, 6 skipped, 417 subtests, 104 frontend/Vite and Windows AF_PIPE with synthetic subprocesses |
| Stage 1 reference status | **PARTIAL only**; real full child-handle reference not yet obtained |
| N12 / desktop network trackers | **0/2 / 2/3**, unchanged |
| Owner permission | No fresh source-pinned native authorization; existing native workflow disabled; historical approval consumed |
| Other unfinished P4 | R03 physical offline, R06 incident attribution/owner-data preservation and owner signoff independently remain open |

## Next task, not an automatic run permission

Build a **source-only reference evidence worksheet** that ties each S01-S11 success invariant to the current verifier's exact function/check, its independent observable event/handle evidence, and a valid/invalid fixture. Mark app and launcher *verified where the observed data actually supports them*, child original handles **missing**, and Sysmon-vs-ETW exit semantic equality **disputed**. Then decide whether revised evidence semantics are justified or whether the next evidence question requires a **fresh, separately owner-approved, exact-source, one-use disposable Windows native capture**.

Do not activate a native workflow, collect owner data, create installers, change ACL/firewall settings, begin Stage 2 or issue P4 credit from this document exercise.
