# PilotODIN — Neural Horizon brand direction

**Decision date:** 24 October 2026  
**Status:** Preferred concept, **not approved final artwork**  
**Tracking:** [Branding issue #6](https://github.com/Sonkhe-Shongwe/PilotODIN/issues/6)  
**Implementation branch:** `feature/live-dev-workspace-20261023` (Draft PR #5, stacked on Build E)

## Decision and history

The user explored multiple groups of five PilotODIN logo proposals, starting from a circular blue/purple AI brain and developing more creative **planet-and-ring** concepts. The preferred direction is **Neural Horizon**: a purple planetary intelligence core with an electric cyan-to-teal orbital ring. This direction replaces the older **Navigator Route 2** as the current design candidate; it has **not yet been finalised or integrated into the application**.

A generated visual identity board from the October 24, 2026 design conversation illustrates the target with primary horizontal, stacked, monochrome, standalone and Windows/browser icon usages. **That generated PNG remains a concept-board reference in the design conversation and is not yet a committed source asset.** Use the actual illustration when reconstructing, not only this textual description.

## Non-negotiable visual elements

1. **Planet/core:** rounded, mostly royal purple/violet orb, visually substantial, recognisable as a coherent stand-alone emblem.
2. **Orbital ring:** dynamic cyan-blue / teal ring that arcs around and *in front of* the planet, carrying the **pilot** side of the identity. Its silhouette should be distinctive at a glance, not a generic circular outline.
3. **Neural pathways:** simplified white or very light connected circuit traces and circular terminals integrated into the purple planet. The network embodies the **ODIN** intelligence side. Preserve visual rhythm and deliberate asymmetry; avoid too many thin lines.
4. **Wordmark:** `pilotODIN`, one horizontal lock-up with the symbol **on its left**. **pilot** is lowercase, bright cyan/electric blue (can have an accessible blue gradient); **ODIN** is uppercase, dominant bold royal/deep purple. Keep wordmark optical spacing balanced.
5. **Standalone icon:** recognise the same signature at Windows taskbar size. Simplify details at 16–32px while retaining ring + purple planet + minimal neural cues.
6. **Cross-background:** retain legibility on workspace white and deep navy; monochrome fallback for situations where gradients cannot be used.

## Concept palette (illustrative values, not a final extraction)

| Role | Starting colour | Purpose |
| --- | --- | --- |
| Pilot cyan | `#00B4D8` | Orbital ring, `pilot` |
| Analytical teal | `#087B87` | Blue-to-teal accent and analytics |
| ODIN purple | `#5B18C8` | Intelligence core and `ODIN` |
| ODIN deep purple | `#381098` | Depth and shadows |
| Navigator navy | `#111B37` | Dark surfaces and text |
| Workspace neutral | `#F7F8FC` | Light surfaces |

**Important:** These approximations are a descriptive bridge to the concept, not definitive sampled or colour-managed production tokens. Determine final accessible colours while refining the actual design and document a solid-colour fallback.

## Deliverables **after final visual approval**

- A geometrically intentional SVG master, accessible light/dark and monochrome logo versions, and a horizontal/stacked/icon-only lock-up.
- Platform assets: Windows `.ico`/EXE, installer/shortcuts, web favicon/app preview and header symbol+wordmark.
- Size-tested optimisations at **16, 24, 32, 48, 128 and 256px**, adequate negative space, readable wordmark and safe bounds.
- Consistent application usage without mixed placeholder compass designs.
- Check for similarity/trademark concerns prior to a public or commercial launch.

## Guardrails

- Do **not** silently treat generated mockups as manufacturing-ready vector geometry.
- Do **not** independently swap to a different 'orbit' logo or a generic icon while implementing.
- Do **not** overwrite the running app branding or build another installer as part of design exploration.
- Request explicit sign-off on the final master before replacing `frontend/public/pilotodin-symbol.svg`, Tauri icon resources, header visuals or installer branding.

## Where development was paused

Brand exploration temporarily interrupted the **frontend foundation redesign**: a dynamic manually expanded/compact left navigation, persistent selection and a much more cohesive, less white light-first colour system. Track this separately in [UX issue #7](https://github.com/Sonkhe-Shongwe/PilotODIN/issues/7). Work iteratively in the already-running [Live Development workflow](../LIVE_DEVELOPMENT.md) without generating NSIS installers for each visual change.

## Current source reality

The code still contains a compass-like placeholder in `frontend/public/pilotodin-symbol.svg` and a text-based header wordmark. **No production logo has been replaced as part of this decision.**
