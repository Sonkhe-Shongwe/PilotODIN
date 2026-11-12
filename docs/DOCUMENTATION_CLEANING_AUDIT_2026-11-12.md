# PilotODIN 1.0 | Documentation cleaning and navigation audit

**Audit date:** 12 November 2026. **Authoritative audited branch:** `feature/live-dev-workspace-20261023`. **Source checkpoint before cleanup:** `85dabd1644e4ed41cbbdf10865d8d3edf976023e`. **Scope:** read-only GitHub tree inventory and six-file relative Markdown link sample; bounded navigation/safety wording only. This is **not** a claim that every historical citation, external URL, heading anchor or document has been independently reviewed.

## 1. Verified repository inventory

- Recursive Git tree contained **817 entries** and **173 blobs under `docs/`**: **172 Markdown documents** and one PNG image.
- `docs/` Markdown corpus: **4,131,173 bytes** by immutable Git tree blob sizes; **61** `P4_` Markdown docs and **45** `P2_` docs.
- Five `docs/archive/` Markdown files retain historical records. **No identical blob SHA pairs** among the 172 Markdown documents; this does not prove lack of duplicated paragraphs.
- Largest files by Git blob size: `docs/archive/SESSION_HANDOFF_PRE_AUDIT_2026-11-04.md` 669,854 bytes, `SESSION_HANDOFF_CURRENT.md` 503,186 bytes, `PROJECT_STATUS_CURRENT.md` 444,472 bytes, `docs/archive/SESSION_HANDOFF_P1_2026-10-27_VERBATIM.md` 262,260 bytes, `docs/archive/P1_CLOSURE_REGISTER_PRE_AUDIT_2026-11-04.md` 176,459 bytes, and `P4_23_CONSOLIDATED_WINDOWS_ACCEPTANCE_GO_NO_GO_2026-11-09.md` 160,131 bytes.
- The two authoritative current chronology files alone total **947,658 bytes**, approximately **22.9%** of the entire Markdown doc byte inventory. This is a navigation and continuation burden, not proof that the historical claims are erroneous.

## 2. Confirmed navigation and stale-state defects

| Audit ID | Evidence | Disposition |
| --- | --- | --- |
| DOC-01 | Root `README.md` directly said **P1 active** as of 4 November, but current handoff/status and phase policy hold **P4 active, R01–R06 open** | **Corrected root summary**, previous P1 evidence explicitly dated |
| DOC-02 | `DOCUMENTATION_INDEX.md` still asserted historical P1 active, lacked P2/P3 closure and recent P4 acceptance entry points | **Current curated route added**, original 4 November list preserved under explicitly historical heading |
| DOC-03 | Existing index listed **4** P4-specific links while **61** P4 Markdown docs now exist | **P4 current routing added**; do not claim this is an exhaustive 61-document index |
| DOC-04 | `docs/CONTINUE_HERE.md` began with P3 W5 continuation dated 6 November while its filename suggests a current action | **Historical warning added**, full contents preserved |
| DOC-05 | `STUDIO_README.md` contained older startup and project migration instructions that might be mistaken for present-day safe practice | **Historical safety warning added**, original preview guide and migration text retained |
| DOC-06 | `SESSION_HANDOFF_CURRENT.md` and `PROJECT_STATUS_CURRENT.md` are oversized cumulative chronologies and duplicate many historical status paragraphs | **NOT REWRITTEN**; require a separately designed, lossless archive/continuation-compression pass, with link/reference preservation and an explicit rollback comparison |

## 3. Link and content checks actually performed

- Scanned Markdown relative file links in **six** sampled documents at initial checkpoint: `docs/DOCUMENTATION_INDEX.md`, `README.md`, `docs/CONTINUE_HERE.md`, `docs/LIVE_DEVELOPMENT.md`, `docs/DOCUMENTATION_AUDIT_2026-11-04.md`, and `docs/PHASE_FOCUS_AND_CLOSURE_POLICY_2026-10-28.md`.
- **139 relative file-link occurrences**, zero missing file targets by path normalisation against the exact Git tree. URLs, GitHub-hosted external destinations, heading-anchor fragments, files not in the sample, and Markdown syntax in nested formatting were **not fully audited**. Do not say full-repository link integrity PASS.
- Index links to historic `docs/archive` items remain valid; no file deletion, relocation or historical commit rewrite.
- After cleanup, the revised landing docs should be rechecked against the same Git tree (plus the new report), especially their newly added phase, QA and P4 report references.

## 4. Authorised cleanup boundaries

Changes intentionally limited to root `README.md`, `STUDIO_README.md` warning, `docs/CONTINUE_HERE.md` warning, and `docs/DOCUMENTATION_INDEX.md` current route and historical framing, plus this report and mandatory handoff/status/QA continuity. **No historical audit evidence discarded**, no project datasets/SQLite/models, EXE/installer, dependency, source implementation, CI workflow, licence/font binary, branch migration, baseline reset or release change.

No owner accepts P4 risks by virtue of clean docs. **P4 ACTIVE, P4-R01–R06 OPEN, real Gate C UNVERIFIED, historical original full app-data strict integrity FAIL (320 backup vs 346 observed, 74 WebView/cache candidates, historic writer unknown), P5 NOT AUTHORISED, P8 NOT CERTIFIED**. P4-47 single-use native and P4-55 one-time model-fit authority remain consumed.

## 5. Follow-up housekeeping, not part of this increment

1. If prioritised, develop a **lossless** archive plan for the large current handoff/status chronologies, preserving their exact prior bytes, original scope and historical failure records. Replace only after link checks and owner review of current status/next action; avoid turning historical failures into accepted tests.
2. Consider a separate comprehensive Markdown link/anchor checker in source-only CI, with filters for code fences, external links and GitHub-generated heading IDs. Six-file path checks are not enough to certify 172 documents.
3. Keep this index a curated route, not another competing authoritative status document. Update it when the current phase or key acceptance evidence changes.

**Verification label:** Documentation-only GitHub repository navigation audit and bounded link scan. No full-stack tests, native Windows testing, model fitting or release certification.
