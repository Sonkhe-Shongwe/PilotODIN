# PilotODIN | Optional Persistent Shell Clock (UX Proposal Only)

**Date:** 9 November 2026  
**Status:** **PROPOSED, NOT IMPLEMENTED, NOT A P4 ACCEPTANCE BLOCKER.** The user asked whether an app clock is possible and what placement would work. No explicit request to develop or ship was provided.

## Grounded placement

The actual desktop's global header is the 52 px `.po-shell-title` in `frontend/src/UnifiedShell.tsx`. It contains the brand, flexible `LOCAL INTELLIGENCE WORKSPACE` caption, active project switcher, New project and Manage actions. The embedded `App.tsx` topbar is hidden by `frontend/src/unified-shell.css` in unified mode.

Recommend a low-contrast local-time group **between the flexible workspace caption and the existing project selector**, so it is visible across all modes but does not obstruct primary navigation. Do **not** add a dashboard KPI card, floating overlay, sidebar item or per-pane duplicated clock. A `HH:mm` 24-hour readout with smaller weekday/date is sufficient; seconds would add movement for little benefit.

## Behaviour and safety acceptance proposal

- Show **system local time**, update at a minute boundary (no server clock or internet), clean up timer on component unmount, refresh on returning to foreground if the laptop sleeps. Note a clock derived from system time is not a verified security timestamp or model-run time.
- Stable-width tabular numerals, restrained contrast, full date/time zone readable to assistive technology without a disruptive live announcement each minute. Support locale rather than assuming the user's time zone or modifying the OS clock.
- At small widths hide the date first, then the clock; never truncate project names more than existing controls already do or crowd the New project and Manage actions.
- No persistence in project data, experiment database, local storage, remote analytics, model training or report timestamps. Unit tests should use deterministic/frozen dates and fake timers if implemented later.
- Do not attach implementation to P4 phase closure or to a current-source installer build solely for this cosmetic addition.

**Next decision:** User can explicitly request the enhancement in a later UI-polish increment. Until then leave current application code unchanged.
