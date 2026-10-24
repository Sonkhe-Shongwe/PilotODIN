# PilotODIN Macro A2 — Consolidated Windows Acceptance

**Development branch:** `feature/live-dev-workspace-20261023`
**Status:** Source implemented; automated test execution and user Windows acceptance pending.
**Safety:** Do not merge to a release branch or build an installer solely because source-level checks pass.

## Validation policy

- The three development GitHub Actions workflows are **manual-only**, owing to exhausted hosted runner minutes.
- Execute checks locally with **one consolidated GitHub Desktop pull** when the A2 source freeze is announced.
- This checklist supplements, and does not supersede, Master QA Issue #2.
- Run tests using the isolated `PILOTODIN_HOME` environment; do not change installed PilotODIN production data.
- Any failure returns A2 to development. Capture the failing command and output instead of bypassing the test.

## Automatic local verification

From a PowerShell terminal in the repository root, with the existing frontend and Python test dependencies already installed:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\tools\Verify_Macro_A2_Local.ps1
```

The script runs:
1. `npm run test:workspace`
2. `npm run build`
3. `python -m compileall -q backend`
4. Focused `python -m pytest` suites for Explore, Quality, saved analytical evidence, and reports.

It creates a new isolated temp data directory and retains it to support debugging. It does **not** download packages, start GitHub Actions, deploy, train models, or build an installer.

## Manual functional acceptance

| Area | Exact acceptance criterion |
| --- | --- |
| Project switching | Two imports remain isolated. A saved analysis from Project A must not appear in Project B or be reportable under B. |
| Quality findings | Outlier counts equal **only** source records beyond a common finite-data IQR rule. Preview row numbers and detailed investigation match. Legitimate extremes remain untouched. |
| Identifier investigation | Review uniqueness, blank or null IDs, stored dtype, leading zeros and bounded original working rows. No auto-exclusion or edits. |
| Approved versions | After a reviewed Quality correction, old version snapshots remain historical; stale inspection requests fail safely. |
| Field dictionary | Search and inspect column names, stored types, missingness, numeric statistics, categorical distributions, and sample records on the current approved version. |
| Linked filters | Apply two independent filters; verify counts, chart and correlations change together. Clear filters; verify original approved version remains unchanged. |
| Bar chart | Count with and without Y uses explicitly stated denominators; clicking a category yields corresponding records. |
| Histogram | Contiguous numerical bins sum to valid finite observations; include the last right endpoint. A bin click returns exactly its count of matching rows. |
| Scatter | Valid-pair denominator, exclusions and sampling are disclosed. Category legend, 1×–8× zoom, directional pan, reset and point-to-record inspection work. |
| Line and box | Click a line point, inlier action, all-outlier action and individual outlier markers. Repeated outlier values yield all matching records. Missing/nonfinite values are excluded and counted correctly. |
| Null category collision | A literal text category named `(Missing)` remains different from a **null** cell; its chart counts and drill-down rows must not merge. |
| Correlation | Pearson/Spearman matrix is current-version and filter-linked. Pairwise counts and empty/ineligible cases are explained without causal claims. |
| Motion | Selecting a chart mark scrolls to the inspector at the deliberately slower speed. Manual scroll interrupts; pagination does not trigger another jump; reduced-motion makes navigation immediate. |
| Saved Explore analysis | Save, close, reopen and restore matching-version config without changing approved data. **Open** must scroll directly to its frozen history panel, not leave the view at the library; repeat Open must work. Reduced-motion preference jumps immediately, otherwise scrolling is interruptible and paced. Results and settings each have integrity protection. Library clearly distinguishes verified, legacy settings, and corrupt items. |
| Historical/legacy saved evidence | Historical verified results are frozen. Legacy result-only snapshots remain readable but cannot auto-restore unverified settings or be passed to Deliver as verified evidence. |
| Deliver handoff | One verified Explore snapshot opens as a selected new report exhibit. Legacy or corrupt snapshots are **absent** from report evidence options (while valid legacy results remain inspectable in Explore). Save revision, export PDF and HTML; check numerical values, source hashes and dataset versions. |
| Mixed report evidence | A report containing an Investigate artifact and Explore snapshot remains project-scoped, immutable and reproducible after reopening. |
| Export safety | Confirm correct file extension and filename; Save As destination is user-controlled on the intended Windows target. Note remaining defects in QA Issue #2. |

## Release boundary

A2 passing this script is **not** proof that A3 ML, A4 Reporting, B1 Ask ODIN, B2 Progress, or the integrated Windows installer is ready. Keep those milestones distinct and retain the offline 8 GB final acceptance gate. No installer until the integrated release phase.
