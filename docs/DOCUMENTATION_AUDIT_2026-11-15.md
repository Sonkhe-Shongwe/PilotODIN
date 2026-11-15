# PilotODIN documentation audit · 15 November 2026

Audited branch `feature/live-dev-workspace-20261023` at baseline `07dbaa749fea9bf90bf4debf534246f875132395`. The inventory and internal link scan cover the tracked Markdown corpus. The editorial review focused on the entry points, current status and handoff, P4 acceptance, development and Windows trace guidance, and older guides with executable instructions.

## Findings and corrections

| Finding | Correction |
| --- | --- |
| The root README called an earlier CI run the latest and still described live collector calibration as pending. | The [README](../README.md) links to the latest P4 source CI and the separate live collector run at their tested revisions. |
| The 14 November navigation summary and acceptance worklist omitted the latest N12 result. | The [documentation index](./DOCUMENTATION_INDEX.md), [worklist](./P4_80_ACCEPTANCE_WORKLIST_AND_EVIDENCE_INTAKE_2026-11-12.md) and [runbook](../qa/p4_native/N12_TRACE.md) point to the 15 November prelaunch pass and unresolved ETW blocker. |
| The current handoff and phase status were 1,253,648 bytes together and contained dated instructions from multiple phases. | Compact [handoff](./SESSION_HANDOFF_CURRENT.md) and [phase ledger](./PROJECT_STATUS_CURRENT.md) now carry current decisions, evidence and next work. The complete originals remain available at the exact baseline commit below. This resolves the compression item from the [12 November audit](./DOCUMENTATION_CLEANING_AUDIT_2026-11-12.md). |
| Older desktop, patch and Build B–D.1 instructions could be mistaken for current operating procedures. The live development guide suggested intermediate packaged testing. | The legacy guides now link to current policy. The [live development guide](./LIVE_DEVELOPMENT.md) reflects the installer freeze and separate native approval boundary. |
| The frontend E2E guide linked to its own directory for a P1 Windows acceptance note. | The [E2E guide](../frontend/e2e/README.md) links to the tracked note under `docs/`. |

## Preservation and link checks

The pre-audit documents are preserved at immutable Git references with their original headings and text. SHA-256 values below were computed from the baseline Git blobs. The current handoff and status also retain the original heading fragment names. Existing branch-fragment URLs land at the historical navigation section. The worklist now links directly to the numbered or dated sections in the snapshot.

| Original at the audited commit | Bytes | SHA-256 |
| --- | ---: | --- |
| [Documentation index](https://github.com/Sonkhe-Shongwe/PilotODIN/blob/07dbaa749fea9bf90bf4debf534246f875132395/docs/DOCUMENTATION_INDEX.md) | 29,907 | `23fba106a59daeb28eacb5271bb8332210917d9f918411ad15b9e4932e227e88` |
| [Session handoff](https://github.com/Sonkhe-Shongwe/PilotODIN/blob/07dbaa749fea9bf90bf4debf534246f875132395/docs/SESSION_HANDOFF_CURRENT.md) | 726,176 | `6e901e7171d010a6065b8b384a58182ad9a0778a96683d0d2673641a9a7b5567` |
| [Project status](https://github.com/Sonkhe-Shongwe/PilotODIN/blob/07dbaa749fea9bf90bf4debf534246f875132395/docs/PROJECT_STATUS_CURRENT.md) | 527,472 | `b7456a20ac8164f9ad4c2d9332eb6bab3b8066a931984cc03f8d4e06a9b6822c` |

Before cleanup, the scan covered **214 Markdown files**, including **196 under `docs/`**, and found 92 broken internal file-link occurrences. One was in the live documentation and was corrected. The remaining 91 are in the pre-existing verbatim archives. Their relative links were copied from a different directory layout, and the original bytes are retained as historical evidence.

The final scan covered **215 Markdown files**, **553 internal path references** and **20 Markdown heading-fragment references**, with zero unresolved references outside the verbatim archives. All **582 original heading IDs** across the handoff and phase ledger were verified in the updated pages. The **19 new direct links** to historical chronology sections were separately matched against the original headings at the baseline commit. The handoff and phase ledger now total **64,931 bytes**, including the compatibility anchors.

The scan uses rendered Markdown link tokens and GitHub-style heading slugs for repository-relative targets and links pinned to the active branch. It excludes code examples and leaves third-party URLs, external artifacts and other branches outside the automated verification. The latest relevant Actions outcomes and open QA records were checked directly. Application and native acceptance tests were outside this documentation audit.

## Current engineering boundary

P4 stays active at 65/100 on the proposed engineering scorecard. N12 strict ETW coverage is blocked. The original-storage historical failure, physical offline Qwen preflight and owner signoff remain open. Both live N12 workflows remain disarmed. The [current handoff](./SESSION_HANDOFF_CURRENT.md#next-engineering-action) records the next implementation increment.
