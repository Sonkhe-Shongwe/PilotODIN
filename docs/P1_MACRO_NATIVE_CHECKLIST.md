# P1 native acceptance checklist after the automation macro

Use only the **DEV ONLY Tauri Windows window**, the verified isolated backend and disposable projects. Each unverified item starts **NOT RUN**. Never mark native or physical Windows behaviour PASS because automated Chromium or backend tests pass.

## Previously accepted and not to be repeated

Native Quality Region correction v1 approval, v2 Undo, v3 Restore and visually retained history after the owner-reported restart; scoped Manager Rename/Archive/Restore; WIN-K1–K4 keyboard and dock behaviour; accepted native title-bar close and Stay/Leave.

## Batch 1: one P1-N1 native project-switch interaction

1. [ ] Select disposable **CSV** project and open Prepare. Edit a target field without saving. Note its value.
2. [ ] Select the disposable **XLSX** project in the top dropdown. Choose **Cancel/Stay** if prompted.
3. [ ] Confirm CSV remains active and the edited Prepare target remains intact.
4. [ ] Try switching again, explicitly consent to discard, confirm correct XLSX identity.
5. [ ] Safely switch back to CSV. Record **PASS**, **FAIL** or **BLOCKED**.
6. [ ] Deliberately unavailable source/backend recovery is covered by *isolated hosted CI and synthetic backend tests*. Do not rename a user's real data source or interrupt an unknown backend for a native fault-injection experiment. Native failure injection remains **UNVERIFIED** unless safely isolated and separately planned.

## Batch 2: physical Windows scales and Snap (S1–S4)

1. [ ] Windows **Settings > System > Display**: note original scale and resolution.
2. [ ] At original scale check selector, header, Quality+Prepare, dialogs and accessible controls.
3. [ ] Try 125% if supported and check the same, record actual result.
4. [ ] Try 150% if supported and check the same, record actual result.
5. [ ] **Restore the original Windows scale**, including if a visual check fails.
6. [ ] Try **Win+Left** or **Win+Right** Snap. If the ~1010px minimum window width prevents half-screen Snap on your monitor, record **UNSUPPORTED**, not a false PASS/FAIL.

## Batch 3: accessibility (A1–A2)

1. [ ] **Settings > Accessibility > Visual effects > Animation effects**: temporarily switch animations off. Check navigation/focus; then restore the original setting.
2. [ ] Turn Windows **Narrator** on using **Win+Ctrl+Enter**. Check spoken labels on the project selector, Quality, Corrections, History and the non-destructive review dialog. Check Tab, Shift+Tab, Escape and focus return; do not approve data changes.
3. [ ] Turn Narrator off with **Win+Ctrl+Enter**. Record missing announcements, focus traps, unusable controls or PASS. A reduced-animation badge alone is not acceptance.

## Batch 4: resource policy (R1)

1. [ ] View resource settings and confirm physical/available RAM is plausible against the read-only inventory (memory changes naturally over time).
2. [ ] Confirm mode and saved-settings label. Do not run actual model inference or 8 GB combined AI + ML stress.
3. [ ] Offline Qwen + ML coexistence on 8 GB and final packaging remain **UNDETERMINED** until tested separately.

## Final closure (C1)

- [ ] For each gate, record **PASS / FAIL / BLOCKED or UNSUPPORTED / NOT RUN** with any substantive limitation.
- [ ] Confirm no open critical/high P1 safety, data-loss, correctness or security defect.
- [ ] Review the exact tested Git SHA, GitHub QA Issue #2 and current closure register.
- [ ] Owner explicitly accepts the evidence and any permitted deferrals. **This macro does not close P1.**

Evidence or screenshots need only be shared for an unexpected error or an actual native requirement whose result cannot otherwise be described reliably.
