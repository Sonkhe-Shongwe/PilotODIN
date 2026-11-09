# PilotODIN | Persistent Live Clock, Research and Aesthetic Design Specification

## Owner design selection, 10 November 2026

**SELECTED:** **B. Satin Chronograph**, with the quiet visual restraint of A. The owner explicitly said **"okay b it is then"** after viewing three design studies. This authorises the aesthetic direction, **not automatically the implementation, an installer build, or a P4 phase transition**.

Frozen design intent: one compact light satin-lilac clock capsule in the persistent `UnifiedShell.tsx` 52px header, placed just before the project selector; deep-violet tabular `HH:mm` digits, a small readable day/date line, one fine teal accent, minimal shadow, soft border and no blinking or distracting motion. At narrower widths the date reduces first, then the clock hides to protect project actions. Use local system time with minute updates and accessible full-date/time-zone information, no network/data storage.

**Current state:** Design **SELECTED / NOT IMPLEMENTED**. Build and installation consent not given. P4 remains ACTIVE; P5 NOT AUTHORISED and P8 NOT CERTIFIED.


**Research date:** 9 November 2026  
**State:** **RESEARCHED DESIGN PROPOSAL ONLY. NOT IMPLEMENTED, NOT CURRENTLY A P4 ACCEPTANCE CONDITION.**  
**User priority:** A visually exceptional clock, not merely a working timer. User's request to **research aesthetics** does not itself authorise source changes, a new installer, local Windows testing or P4 closure.

## Grounded product context

The real persistent application header is **`frontend/src/UnifiedShell.tsx`**, within `<header className="po-shell-title">`, not the embedded `App.tsx` topbar (hidden in unified mode). The header height is **52 CSS px**, with logo at left, flexible `LOCAL INTELLIGENCE WORKSPACE` caption, project selector, New project and Manage at right. Existing palette: deep-violet PilotODIN brand, teal pilot accent, a near-white surface, and understated lilac/blue header gradient. `frontend/src/unified-shell.css` already hides the long mode caption under 800px and restricts project selector to `max-width:48vw`. Do not add a duplicated clock to each page, sidebar, dashboard KPI card or docked pane.

**Best position:** after the flexible mode caption and **before the active-project selector**, in the persistent top shell. This yields a consistent orientation marker while preserving workspace content and user-control hierarchy.

## Externally researched design references

| Reference | Supported practice | Interpretation for PilotODIN |
| --- | --- | --- |
| [Apple macOS clock settings](https://support.apple.com/en-mt/guide/mac-help/mchlb3236e90/mac) | Always-on menu-bar time with optional date/weekday, digital/analog and seconds; date may appear only when room exists | A clock should feel like compact permanent application chrome; choose date when room, not always a full calendar |
| [Routine desktop menu-bar widget](https://help.routine.co/articles/1167925-menu-bar-widget) and [visual reference](https://routine.co/features/menu-bar-widget) | At-a-glance task/time awareness in compact menu bar or system tray, detail on demand | Use persistent, quiet time, not a focus-stealing giant widget |
| [Microsoft Windows app typography](https://learn.microsoft.com/windows/apps/design/signature-experiences/typography) | Windows legibility and strong UI text hierarchy, with Segoe UI Variable as platform-oriented option | Keep existing Inter/Segoe system stack, clear hour/minute emphasis, small but readable date |
| [MDN tabular-nums](https://developer.mozilla.org/en-US/docs/Web/CSS/Reference/Properties/font-variant-numeric) | Fixed-width digit variants can align numerical changes | `font-variant-numeric: tabular-nums`, stable two-digit HH:mm, no shifting colon |
| [W3C WCAG 2.2 minimum contrast](https://www.w3.org/TR/WCAG22/#contrast-minimum) | Normal small text generally needs 4.5:1 contrast against background | Don't confuse washed-out silver text with premium design; test date and time contrast in both themes |
| [MDN reduced-motion](https://developer.mozilla.org/en-US/docs/Web/CSS/Reference/At-rules/%40media/prefers-reduced-motion) | Non-essential motion should respect OS-level preference | Do not pulse, blink the colon, flip digits continuously or use unnecessary transforms |
| [MDN Intl.DateTimeFormat](https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/Intl/DateTimeFormat) and [visibilitychange](https://developer.mozilla.org/en-US/docs/Web/API/Document/visibilitychange_event) | Locale and time-zone-aware formatting; browsers expose foreground/background events | Format the local PC clock and refresh immediately after sleeping/waking or foreground return |

**Inspiration only, not a license to clone:** Frosted-glass clocks (e.g. Glassclock) demonstrate tint and tonal hierarchy, while macOS/Routine demonstrate disciplined chrome density. No third-party imagery, licensed fonts, brand assets, exact decorative copy or external runtime dependencies need to ship.

## Three aesthetic directions considered

### A. Precision

A clear white header with `23:34` in deep-violet 16px semibold and a tiny muted `MON 09 NOV` underneath. No container beyond a hairline divider. **Pros:** quietly professional, zero depth cost, fits the narrow header. **Cons:** can look like an incidental timestamp rather than a designed PilotODIN signature.

### B. Satin Chronograph: RECOMMENDED

A delicate 156–176px wide by 38–40px high rounded capsule, built from a **slightly tinted near-white to lilac gradient**, a 1px lavender border and a barely visible shadow. A 2px teal accent line (or tiny teal dot, not both) marks PilotODIN identity. Main `23:34` has custom-feeling **tabular digits** and an intelligent 17–18px weight 750–800. Beneath it, `MON · 09 NOV` in readable 10.5–11px medium-bold with carefully increased tracking, avoiding the trap of unreadable washed-out captions. Align both text lines on the left, or time left and date right only if the 40px height remains legible. Don't use actual expensive real-time `backdrop-filter` blur; a satin finish can be achieved with CSS gradient and border alone.

**Visual traits:** compact, balanced, subtle material depth, identity-consistent violet/teal, instantly readable. On hover a modest border shift, not a glowing halo or animated colon. Accessible full date and timezone tooltip or equivalent non-hover alternative. This is the strongest compromise between luxury and a serious analytical workspace.

### C. Dark Instrument / HUD

Deep-indigo chip with bright teal numerals, segmented typography, tiny status indicator. **Pros:** striking, technical. **Cons:** too visually dominant in PilotODIN's light-first header; raises contrast/visual hierarchy risk; resembles a market ticker or simulation HUD, and weakens the purposeful project selector. Reserve for a future optional high-contrast theme, NOT the default.

**Recommendation:** **B with A's restraint**. Use the restrained tone, hierarchy and quietness of A within B's softly defined capsule. Do not add a clock-themed dial, analog hands, glass reflections, neon bloom, stopwatch seconds or large calendar by default.

## Proposed final visual and spacing rules (design tokens, not implemented)

| Property | Proposed target |
| --- | --- |
| Header | Keep exact existing **52px** global header height |
| Clock footprint | **156–176px x 38–40px** when room permits |
| Shape | **11–12px** corner radius, no floating overlay |
| Surface | Gentle white-to-violet `linear-gradient`, subtle 1px border. No `backdrop-filter` requirement |
| Primary digits | 17–18px, 750–800 weight, line height about 20px, tabular-nums; use brand deep violet or dark slate |
| Secondary line | 10.5–11px, semibold, letter spacing 0.3–0.5px, readable muted violet/neutral |
| Accent | **One** thin teal edge, tiny dot or fine vertical separator. No simultaneous competing decorative highlights |
| Position | Header, **before** project selector, after flexing mode caption |
| Tooltip/full label | Full weekday, long date, local time zone; must not be hover-only for assistive technology |
| Narrow view | Hide date first, then entire clock before project selector, New project or Manage become cramped |
| Update | Minute boundary, immediate foreground/focus refresh, initial render, no server/network |
| User preference | Follow locale/system hour-cycle by default, optionally future 12/24h preference; no forced UTC or hardcoded South Africa |
| Animation | None at rest; optional single 120ms hover tint/border only and respect reduced motion |
| Battery/resources | One lightweight timer, no heavy CSS blur, no animation loop, no backend endpoint, no dataset writes |
| Accessibility | Test text contrast (4.5:1 for small text), label content for screen readers without repeated minute announcements |

### Responsive fitting proposal

- **Wide header:** capsule time plus short date.
- **Medium header:** time-only capsule, 75–92px width and same height, before the project selector.
- **Narrow window:** hide clock **entirely**; project selection and New/Manage take priority. Determine the breakpoints from actual browser/native visual regression rather than guessing all widths in advance.
- Prefer actual available-space/container constraints to a rigid pixel-only breakpoint. No overlap with selector or implicit horizontal scrolling.

### Clock is not an event log

This is a local decorative/navigation chrome clock. Displaying system-local time cannot validate the accuracy of model-run timestamps, experiment creation dates, historical label timing, audit evidence, resource measurement, official time synchronization or business legality. Never reuse this UI time as a source of authoritative persistence.

## Future implementation and acceptance, only if separately requested

Use an isolated `ShellClock` component rendered once in `UnifiedShell.tsx` plus scoped CSS in `unified-shell.css`. Test with deterministic/frozen dates, minute transitions, midnight/day transition, DST/local time changes, laptop sleep/wake foreground return, unmount cleanup and reduced-motion preference. Visually inspect at 1920, 1366, 1024, 800 and 600px widths on both native Windows WebView2 and browser, including long project names and zoomed text. Confirm project dropdown, New project, Manage, sidebar and keyboard focus remain usable.

**No clock UI code, CI installer or other application source was changed by this research document.** It is not an open P4 safety defect, and P4 ACTIVE / P5 NOT AUTHORISED / P8 NOT CERTIFIED remain unaffected.
